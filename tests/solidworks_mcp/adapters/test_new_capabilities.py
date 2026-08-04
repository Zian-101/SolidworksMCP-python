"""Contract tests for the capabilities added to the adapter surface.

Each of these exists on the base adapter, the mock, the circuit breaker and the
connection pool. A method missing from either wrapper silently degrades to the
base "not implemented" default at runtime, and mock mode cannot catch it —
the mock is not wrapped — so the wiring is asserted directly.
"""

import inspect

import pytest

from solidworks_mcp.adapters.base import SolidWorksAdapter
from solidworks_mcp.adapters.circuit_breaker import CircuitBreakerAdapter
from solidworks_mcp.adapters.connection_pool import ConnectionPoolAdapter
from solidworks_mcp.adapters.mock_adapter import MockSolidWorksAdapter

#: Capabilities added across this branch.
CAPABILITIES = [
    "delete_feature",
    "suppress_feature",
    "undo",
    "create_reference_plane",
    "mirror_feature",
    "create_shell",
    "pattern_linear",
    "pattern_circular",
    "create_axis",
    "add_draft",
    "move_body",
    "delete_body",
    "delete_face",
    "scale_model",
    "set_material",
    "set_appearance",
    "get_bounding_box",
    "check_interference",
    "get_material_properties",
    "insert_component",
    "list_components",
    "add_mate",
    "add_drawing_view",
    "create_standard_views",
    "add_drawing_note",
    "insert_model_dimensions",
    "list_drawing_views",
]

WRAPPERS = [SolidWorksAdapter, MockSolidWorksAdapter, CircuitBreakerAdapter,
            ConnectionPoolAdapter]


@pytest.mark.parametrize("capability", CAPABILITIES)
@pytest.mark.parametrize("cls", WRAPPERS, ids=lambda c: c.__name__)
def test_capability_exists_on_every_layer(capability: str, cls: type) -> None:
    """A capability missing from a wrapper degrades silently at runtime."""
    method = getattr(cls, capability, None)
    assert method is not None, f"{cls.__name__} is missing {capability}"
    assert inspect.iscoroutinefunction(method), (
        f"{cls.__name__}.{capability} must be async"
    )


@pytest.mark.parametrize("capability", CAPABILITIES)
def test_wrappers_do_not_silently_fall_through_to_base(capability: str) -> None:
    """The breaker and pool must define their own pass-through, not inherit."""
    for cls in (CircuitBreakerAdapter, ConnectionPoolAdapter):
        assert capability in vars(cls), (
            f"{cls.__name__} inherits {capability} from the base adapter, so "
            "calls to it return 'not implemented' instead of reaching the real "
            "adapter"
        )


@pytest.mark.asyncio
async def test_mock_rejects_bad_input_rather_than_inventing_success() -> None:
    """Input validation lives in the adapter, not only in the tool layer."""
    adapter = MockSolidWorksAdapter({})
    await adapter.connect()

    assert not (await adapter.add_draft(0.0, 0, [1])).is_success
    assert not (await adapter.add_draft(5.0, 0, [])).is_success
    assert not (await adapter.move_body(0, 0.0, 0.0, 0.0)).is_success
    assert not (await adapter.delete_body([])).is_success
    assert not (await adapter.delete_face([])).is_success
    assert not (await adapter.scale_model(0.0)).is_success
    assert not (await adapter.set_material("")).is_success
    assert not (await adapter.create_axis("q")).is_success
    assert not (await adapter.pattern_circular([], "z", 4)).is_success
    assert not (await adapter.pattern_circular(["Cut-Extrude1"], "z", 1)).is_success
    assert not (await adapter.set_appearance(-1.0, 0.0, 0.0)).is_success
    assert not (await adapter.set_appearance(300.0, 0.0, 0.0)).is_success
    assert not (await adapter.add_mate("a-1", "b-1", mate_type="bogus")).is_success


@pytest.mark.asyncio
async def test_mock_accepts_valid_input() -> None:
    """The happy paths still work, so the guards are not simply rejecting all."""
    adapter = MockSolidWorksAdapter({})
    await adapter.connect()

    assert (await adapter.add_draft(5.0, 4, [0, 1])).is_success
    assert (await adapter.move_body(0, 40.0, 0.0, 0.0)).is_success
    assert (await adapter.delete_body([1])).is_success
    assert (await adapter.delete_face([6])).is_success
    assert (await adapter.scale_model(2.0)).is_success
    assert (await adapter.set_material("6061 Alloy")).is_success
    assert (await adapter.create_axis("z")).is_success
    assert (await adapter.pattern_circular(["Cut-Extrude1"], "z", 6)).is_success
    assert (await adapter.set_appearance(255, 0, 0)).is_success
    assert (await adapter.set_appearance(0.2, 0.4, 1.0, 0.5)).is_success
    assert (await adapter.add_mate("a-1", "b-1")).is_success
    assert (await adapter.insert_component("C:/part.sldprt")).is_success
    assert (await adapter.create_standard_views("C:/part.sldprt")).is_success


@pytest.mark.asyncio
async def test_scale_reports_the_volume_ratio_it_implies() -> None:
    """A uniform factor f must report f**3; non-uniform reports the product."""
    adapter = MockSolidWorksAdapter({})
    await adapter.connect()

    uniform = await adapter.scale_model(2.0)
    assert uniform.data["volume_ratio"] == pytest.approx(8.0)
    assert uniform.data["uniform"] is True

    stretched = await adapter.scale_model(2.0, 1.0, 1.0)
    assert stretched.data["volume_ratio"] == pytest.approx(2.0)
    assert stretched.data["uniform"] is False
