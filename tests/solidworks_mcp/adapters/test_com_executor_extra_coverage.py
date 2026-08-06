"""Extra coverage for solidworks_mcp.adapters.com_executor branches not hit
by the existing test_com_executor.py: the module-level ImportError fallback
for pythoncom, the cancelled-future skip inside the worker loop, and the
CoUninitialize exception being swallowed during stop().
"""

from __future__ import annotations

import importlib.util
import time
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace


def test_import_handles_missing_pythoncom() -> None:
    """PYWIN32_AVAILABLE should be False when pythoncom cannot be imported."""
    import builtins

    original_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name == "pythoncom":
            raise ImportError("blocked for test")
        return original_import(name, *args, **kwargs)

    builtins.__import__ = _blocked_import
    try:
        module_path = (
            Path(__file__).parents[3]
            / "src"
            / "solidworks_mcp"
            / "adapters"
            / "com_executor.py"
        )
        spec = importlib.util.spec_from_file_location(
            "com_executor_no_pythoncom", module_path
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.PYWIN32_AVAILABLE is False
    finally:
        builtins.__import__ = original_import


def _fake_pythoncom(*, fail_uninit: bool = False):
    calls: list[str] = []

    def _coinitialize():
        calls.append("init")

    def _couninitialize():
        calls.append("uninit")
        if fail_uninit:
            raise RuntimeError("uninit boom")

    return SimpleNamespace(CoInitialize=_coinitialize, CoUninitialize=_couninitialize), calls


def test_worker_skips_a_future_that_was_cancelled_before_it_ran(monkeypatch) -> None:
    """If the caller cancels the Future before the worker picks it up,
    set_running_or_notify_cancel() returns False and the worker must skip
    the item (continue) without crashing, then keep serving later work."""
    from solidworks_mcp.adapters import com_executor

    fake_pythoncom, _calls = _fake_pythoncom()
    monkeypatch.setattr(com_executor, "pythoncom", fake_pythoncom, raising=False)
    monkeypatch.setattr(com_executor, "PYWIN32_AVAILABLE", True)

    executor = com_executor.ComExecutor(name="test-cancel-skip")
    executor.start()
    try:
        # Manually enqueue an already-cancelled future, bypassing submit()'s
        # liveness check, to force the cancelled branch in _worker.
        cancelled_future: Future = Future()
        cancelled_future.cancel()
        assert cancelled_future.cancelled()
        executor._queue.put((lambda: "should not run", cancelled_future))

        # The executor must still be usable afterwards — proves the worker
        # looped past the cancelled item instead of dying.
        result = executor.run(lambda: "still alive")
        assert result == "still alive"
    finally:
        executor.stop()


def test_stop_swallows_couninitialize_exception(monkeypatch) -> None:
    """A CoUninitialize failure during shutdown must not propagate from stop()."""
    from solidworks_mcp.adapters import com_executor

    fake_pythoncom, calls = _fake_pythoncom(fail_uninit=True)
    monkeypatch.setattr(com_executor, "pythoncom", fake_pythoncom, raising=False)
    monkeypatch.setattr(com_executor, "PYWIN32_AVAILABLE", True)

    executor = com_executor.ComExecutor(name="test-uninit-fail")
    executor.start()
    assert executor.run(lambda: 1 + 1) == 2

    # Should not raise even though CoUninitialize raises internally.
    executor.stop()

    # Give the thread a brief moment to fully unwind past CoUninitialize.
    for _ in range(20):
        if "uninit" in calls:
            break
        time.sleep(0.01)
    assert "uninit" in calls
