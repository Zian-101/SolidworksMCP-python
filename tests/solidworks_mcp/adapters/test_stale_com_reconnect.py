"""Stale-COM detection and the reconnect-and-retry path.

When the user quits and reopens SolidWorks, the COM pointer this process grabbed
at startup dangles and every later call fails until the whole MCP server is
restarted by hand. The adapter now detects that specific failure and re-acquires
the application once before retrying.

These tests drive the logic with simulated failures. They deliberately do not
require SolidWorks: the real dangling-pointer scenario cannot be produced without
killing a live SolidWorks session.
"""

import pytest

pywintypes = pytest.importorskip("pywintypes")

from solidworks_mcp.adapters.pywin32_adapter import (  # noqa: E402
    PyWin32Adapter,
    _is_stale_com,
)


def _com_error(hresult: int, text: str = "boom"):
    """Build a ``pywintypes.com_error`` with a specific HRESULT."""
    return pywintypes.com_error(hresult, text, None, None)


@pytest.mark.parametrize(
    ("label", "error"),
    [
        ("RPC_S_SERVER_UNAVAILABLE", _com_error(-2147023174)),
        ("RPC_E_DISCONNECTED", _com_error(-2147417848)),
        ("CO_E_OBJNOTCONNECTED", _com_error(-2147221164)),
        # Under late binding a dangling application pointer surfaces at
        # attribute lookup, not as a com_error - this shape is why the original
        # `except com_error` branch never caught it.
        ("late-bound dangling app", AttributeError("SldWorks.Application.GetTitle")),
        ("message marker", Exception("The RPC server is unavailable")),
    ],
)
def test_detects_stale_handles(label: str, error: BaseException) -> None:
    """Dropped-connection failures are recognised."""
    assert _is_stale_com(error), label


@pytest.mark.parametrize(
    ("label", "error"),
    [
        ("ordinary COM failure", _com_error(-2147352571, "Type mismatch")),
        ("ordinary error", ValueError("bad angle")),
        ("unrelated attribute", AttributeError("'dict' object has no attribute 'x'")),
    ],
)
def test_ignores_ordinary_failures(label: str, error: BaseException) -> None:
    """A wrong call must not be mistaken for a dropped connection."""
    assert not _is_stale_com(error), label


def test_retries_once_after_stale_handle() -> None:
    """A stale handle triggers exactly one reconnect, then the retry succeeds."""
    adapter = PyWin32Adapter({})
    reconnects: list[str] = []
    adapter._reacquire_after_stale_com = lambda name: (  # type: ignore[method-assign]
        reconnects.append(name) or True
    )

    calls: list[int] = []

    def flaky() -> str:
        calls.append(1)
        if len(calls) == 1:
            raise _com_error(-2147023174)
        return "recovered"

    result = adapter._handle_com_operation("flaky", flaky)

    assert result.is_success
    assert result.data == "recovered"
    assert len(calls) == 2
    assert reconnects == ["flaky"]


def test_ordinary_error_does_not_reconnect() -> None:
    """An ordinary COM failure is reported without touching the connection."""
    adapter = PyWin32Adapter({})
    reconnects: list[str] = []
    adapter._reacquire_after_stale_com = lambda name: (  # type: ignore[method-assign]
        reconnects.append(name) or True
    )

    calls: list[int] = []

    def always_bad() -> None:
        calls.append(1)
        raise _com_error(-2147352571, "Type mismatch")

    result = adapter._handle_com_operation("bad", always_bad)

    assert not result.is_success
    assert len(calls) == 1
    assert reconnects == []


def test_unrecoverable_stale_handle_does_not_loop() -> None:
    """When reconnecting cannot help, the error is reported instead of retried."""
    adapter = PyWin32Adapter({})
    adapter._reacquire_after_stale_com = lambda name: False  # type: ignore[method-assign]

    calls: list[int] = []

    def always_stale() -> None:
        calls.append(1)
        raise _com_error(-2147023174)

    result = adapter._handle_com_operation("stale", always_stale)

    assert not result.is_success
    assert len(calls) == 1


def test_reconnect_guard_blocks_recursion() -> None:
    """A failure raised during recovery must not re-enter recovery."""
    adapter = PyWin32Adapter({})
    adapter._reconnect_in_progress = True

    assert adapter._reacquire_after_stale_com("anything") is False
