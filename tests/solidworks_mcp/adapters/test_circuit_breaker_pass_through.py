"""Coverage tests for CircuitBreakerAdapter's pass-through methods and the
per-operation circuit breaker state machine.

The pass-through methods (delete_feature, suppress_feature, ... etc.) are
one-line wrappers around ``_execute_with_circuit_breaker``. A test that only
calls them and checks ``is_success`` would pass even if the wrapper called
the wrong underlying method or dropped an argument, so each test below
asserts on the *specific payload content* the underlying MockSolidWorksAdapter
produces for that call, proving the circuit breaker actually delegated with
the right arguments rather than short-circuiting.

The state-machine tests exercise the real closed -> open -> half-open ->
closed transition cycle for both the aggregate circuit and a per-operation
circuit, including isolation between operations.
"""

from __future__ import annotations

import time

import pytest

from solidworks_mcp.adapters.base import AdapterResult, AdapterResultStatus
from solidworks_mcp.adapters.circuit_breaker import CircuitBreakerAdapter, CircuitState
from solidworks_mcp.adapters.mock_adapter import MockSolidWorksAdapter


async def _breaker_with_part() -> CircuitBreakerAdapter:
    breaker = CircuitBreakerAdapter(adapter=MockSolidWorksAdapter({}))
    await breaker.connect()
    await breaker.create_part("TestPart")
    return breaker


class TestPassThroughMethodsDelegateWithRealPayloads:
    """Each pass-through must return the mock adapter's real, specific data."""

    @pytest.mark.asyncio
    async def test_delete_feature(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.delete_feature("Boss-Extrude1")
        assert result.is_success
        assert result.data == {"deleted": "Boss-Extrude1"}

    @pytest.mark.asyncio
    async def test_suppress_feature(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.suppress_feature("Boss-Extrude1", suppress=True)
        assert result.is_success
        assert result.data == {"feature": "Boss-Extrude1", "suppressed": True}

    @pytest.mark.asyncio
    async def test_undo(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.undo(count=3)
        assert result.is_success
        assert result.data == {"undone": 3}

    @pytest.mark.asyncio
    async def test_create_reference_plane_error_bubbles_through(self) -> None:
        breaker = await _breaker_with_part()
        # offset=0, angle=0 is invalid — proves the breaker forwards the
        # real validation error, not a canned success.
        result = await breaker.create_reference_plane("Front Plane")
        assert result.is_error
        assert "non-zero offset or angle" in result.error

    @pytest.mark.asyncio
    async def test_create_reference_plane_success(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.create_reference_plane("Front Plane", offset=10.0)
        assert result.is_success
        assert result.data["reference"] == "Front Plane"
        assert result.data["offset"] == 10.0

    @pytest.mark.asyncio
    async def test_mirror_feature(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.mirror_feature(["Boss-Extrude1"], "Front Plane")
        assert result.is_success
        assert result.data["mirrored_features"] == ["Boss-Extrude1"]
        assert result.data["mirror_plane"] == "Front Plane"

    @pytest.mark.asyncio
    async def test_create_shell(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.create_shell(2.5, remove_faces=[1, 2])
        assert result.is_success
        assert result.data["thickness"] == 2.5
        assert result.data["removed_faces"] == [1, 2]

    @pytest.mark.asyncio
    async def test_pattern_linear(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.pattern_linear(["Boss-Extrude1"], count=4, spacing=5.0)
        assert result.is_success
        assert result.data["count"] == 4
        assert result.data["spacing"] == 5.0

    @pytest.mark.asyncio
    async def test_add_draft(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.add_draft(5.0, draft_faces=[1])
        assert result.is_success
        assert result.data["angle"] == 5.0
        assert result.data["draft_faces"] == [1]

    @pytest.mark.asyncio
    async def test_move_body(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.move_body(dx=10.0, dy=2.0)
        assert result.is_success
        assert result.data["offset"] == {"x": 10.0, "y": 2.0, "z": 0.0}

    @pytest.mark.asyncio
    async def test_delete_body(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.delete_body([0])
        assert result.is_success
        assert result.data["deleted"] == [0]

    @pytest.mark.asyncio
    async def test_delete_face(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.delete_face([2])
        assert result.is_success
        assert result.data["deleted"] == [2]

    @pytest.mark.asyncio
    async def test_scale_model(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.scale_model(2.0)
        assert result.is_success
        assert result.data["factors"] == {"x": 2.0, "y": 2.0, "z": 2.0}

    @pytest.mark.asyncio
    async def test_set_material(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.set_material("1060 Alloy")
        assert result.is_success
        assert result.data["name"] == "1060 Alloy"

    @pytest.mark.asyncio
    async def test_insert_component(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.insert_component("C:/tmp/part.sldprt", x=1.0)
        assert result.is_success
        assert result.data["file_path"] == "C:/tmp/part.sldprt"
        assert result.data["position"]["x"] == 1.0

    @pytest.mark.asyncio
    async def test_set_appearance(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.set_appearance(1.0, 0.0, 0.0)
        assert result.is_success
        assert result.data["color"] == {"r": 1.0, "g": 0.0, "b": 0.0}

    @pytest.mark.asyncio
    async def test_add_mate(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.add_mate("CompA", "CompB", mate_type="concentric")
        assert result.is_success
        assert result.data["mate_type"] == "concentric"
        assert result.data["components"] == ["CompA", "CompB"]

    @pytest.mark.asyncio
    async def test_list_components(self) -> None:
        breaker = await _breaker_with_part()
        await breaker.insert_component("C:/tmp/part.sldprt")
        result = await breaker.list_components()
        assert result.is_success
        assert result.data == ["component-1"]

    @pytest.mark.asyncio
    async def test_add_drawing_view(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.add_drawing_view("C:/tmp/part.sldprt", orientation="top")
        assert result.is_success
        assert result.data["orientation"] == "top"
        assert result.data["model_path"] == "C:/tmp/part.sldprt"

    @pytest.mark.asyncio
    async def test_create_standard_views(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.create_standard_views("C:/tmp/part.sldprt", third_angle=False)
        assert result.is_success
        assert result.data["projection"] == "first_angle"

    @pytest.mark.asyncio
    async def test_add_drawing_note(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.add_drawing_note("Hello note", x=5.0)
        assert result.is_success
        assert result.data["text"] == "Hello note"
        assert result.data["position"]["x"] == 5.0

    @pytest.mark.asyncio
    async def test_insert_model_dimensions(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.insert_model_dimensions(all_views=False)
        assert result.is_success
        assert result.data["all_views"] is False

    @pytest.mark.asyncio
    async def test_list_drawing_views(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.list_drawing_views()
        assert result.is_success
        assert result.data == ["Drawing View1", "Drawing View2"]

    @pytest.mark.asyncio
    async def test_create_axis(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.create_axis("y")
        assert result.is_success
        assert result.data["reference"] == "y"

    @pytest.mark.asyncio
    async def test_pattern_circular(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.pattern_circular(["Boss-Extrude1"], count=6, angle=180.0)
        assert result.is_success
        assert result.data["count"] == 6
        assert result.data["angle"] == 180.0

    @pytest.mark.asyncio
    async def test_add_polyline(self) -> None:
        breaker = await _breaker_with_part()
        await breaker.create_sketch("Front Plane")
        points = [{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1}]
        result = await breaker.add_polyline(points, closed=True)
        assert result.is_success
        assert result.data["segments"] == 3
        assert result.data["closed"] is True

    @pytest.mark.asyncio
    async def test_get_bounding_box(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.get_bounding_box()
        assert result.is_success
        assert result.data["units"] == "mm"
        assert result.data["dimensions"] == {"x": 60.0, "y": 40.0, "z": 20.0}

    @pytest.mark.asyncio
    async def test_check_interference(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.check_interference({"coincident": True})
        assert result.is_success
        assert result.data["interference_found"] is False
        assert result.data["coincident_treated_as_interference"] is True

    @pytest.mark.asyncio
    async def test_get_material_properties(self) -> None:
        breaker = await _breaker_with_part()
        result = await breaker.get_material_properties()
        assert result.is_success
        assert result.data["name"] == "Plain Carbon Steel"


class TestPerOperationCircuitStateMachine:
    """Exercise the real CLOSED -> OPEN -> HALF_OPEN -> CLOSED cycle,
    scoped to a single operation, with isolation from other operations."""

    @staticmethod
    def _failing_adapter_pair():
        """Adapter whose get_bounding_box always errors but other ops succeed."""

        class _FlakyAdapter(MockSolidWorksAdapter):
            async def get_bounding_box(self):
                return AdapterResult(
                    status=AdapterResultStatus.ERROR, error="boom: geometry unavailable"
                )

        return _FlakyAdapter({})

    @pytest.mark.asyncio
    async def test_operation_circuit_opens_after_threshold_failures(self) -> None:
        breaker = CircuitBreakerAdapter(
            adapter=self._failing_adapter_pair(), failure_threshold=3, recovery_timeout=60
        )
        await breaker.connect()
        await breaker.create_part("P1")

        for _ in range(3):
            result = await breaker.get_bounding_box()
            assert result.is_error

        circuit = breaker._op_circuits["get_bounding_box"]
        assert circuit["state"] == CircuitState.OPEN

        # A 4th call must fail fast with the circuit-open message, not
        # attempt the underlying (still-broken) operation again.
        blocked = await breaker.get_bounding_box()
        assert blocked.is_error
        assert "Circuit breaker is open for get_bounding_box" in blocked.error
        assert blocked.metadata["circuit_state"] == "open"

    @pytest.mark.asyncio
    async def test_other_operations_remain_available_while_one_is_open(self) -> None:
        """Per-operation isolation: a broken op must not block healthy ones."""
        breaker = CircuitBreakerAdapter(
            adapter=self._failing_adapter_pair(), failure_threshold=2, recovery_timeout=60
        )
        await breaker.connect()
        await breaker.create_part("P1")

        for _ in range(2):
            await breaker.get_bounding_box()
        assert breaker._op_circuits["get_bounding_box"]["state"] == CircuitState.OPEN

        # A completely different operation must still work normally.
        healthy = await breaker.set_material("1060 Alloy")
        assert healthy.is_success
        assert "set_material" not in breaker._op_circuits or (
            breaker._op_circuits["set_material"]["state"] == CircuitState.CLOSED
        )

    @pytest.mark.asyncio
    async def test_half_open_probe_recovers_to_closed_on_success(self) -> None:
        breaker = CircuitBreakerAdapter(
            adapter=self._failing_adapter_pair(), failure_threshold=1, recovery_timeout=0.05
        )
        await breaker.connect()
        await breaker.create_part("P1")

        failed = await breaker.get_bounding_box()
        assert failed.is_error
        circuit = breaker._op_circuits["get_bounding_box"]
        assert circuit["state"] == CircuitState.OPEN

        # Wait past recovery_timeout so the next call is allowed as a
        # half-open probe.
        time.sleep(0.08)

        # Swap in a healthy adapter to simulate the underlying issue
        # having cleared, then let the probe succeed.
        breaker.adapter = MockSolidWorksAdapter({})
        await breaker.adapter.connect()
        await breaker.adapter.create_part("P1")

        probe = await breaker.get_bounding_box()
        assert probe.is_success
        assert circuit["state"] == CircuitState.CLOSED
        assert circuit["failure_count"] == 0

    @pytest.mark.asyncio
    async def test_half_open_probe_reopens_on_repeat_failure(self) -> None:
        breaker = CircuitBreakerAdapter(
            adapter=self._failing_adapter_pair(), failure_threshold=1, recovery_timeout=0.05
        )
        await breaker.connect()
        await breaker.create_part("P1")

        await breaker.get_bounding_box()  # trips to OPEN
        circuit = breaker._op_circuits["get_bounding_box"]
        assert circuit["state"] == CircuitState.OPEN

        time.sleep(0.08)  # past recovery_timeout -> next call is HALF_OPEN probe

        # Still-broken adapter: the probe itself fails, so the breaker
        # must snap straight back to OPEN.
        probe = await breaker.get_bounding_box()
        assert probe.is_error
        assert circuit["state"] == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_half_open_allows_limited_trial_calls(self) -> None:
        """While HALF_OPEN, only half_open_max_calls trials are allowed
        before further calls are blocked again."""
        breaker = CircuitBreakerAdapter(
            adapter=self._failing_adapter_pair(),
            failure_threshold=1,
            recovery_timeout=0.02,
            half_open_max_calls=1,
        )
        await breaker.connect()
        await breaker.create_part("P1")

        await breaker.get_bounding_box()  # OPEN
        circuit = breaker._op_circuits["get_bounding_box"]
        assert circuit["state"] == CircuitState.OPEN

        time.sleep(0.05)

        # Manually force HALF_OPEN with the trial budget already spent,
        # to exercise the "half_open_calls < half_open_max_calls" gate.
        circuit["state"] = CircuitState.HALF_OPEN
        circuit["half_open_calls"] = 1  # budget (max 1) already used

        blocked = await breaker.get_bounding_box()
        assert blocked.is_error
        assert "half_open" in blocked.error

    @pytest.mark.asyncio
    async def test_rolling_failure_window_resets_stale_operation_failures(self) -> None:
        """A failure recorded long after failure_window has elapsed must not
        accumulate onto old failures — it starts a fresh count of 1."""
        breaker = CircuitBreakerAdapter(
            adapter=self._failing_adapter_pair(),
            failure_threshold=5,
            recovery_timeout=60,
            failure_window=0.05,
        )
        await breaker.connect()
        await breaker.create_part("P1")

        await breaker.get_bounding_box()
        circuit = breaker._op_circuits["get_bounding_box"]
        assert circuit["failure_count"] == 1

        time.sleep(0.08)  # exceed failure_window

        await breaker.get_bounding_box()
        # Old failure should have been discarded before incrementing, so the
        # count is 1 again, not 2 — and nowhere near the threshold of 5.
        assert circuit["failure_count"] == 1
        assert circuit["state"] == CircuitState.CLOSED


class TestAggregateCircuitRollingWindow:
    """The legacy/aggregate circuit (connect()/call()) has its own rolling
    failure-window reset, mirrored from the per-operation logic."""

    @pytest.mark.asyncio
    async def test_aggregate_failure_count_resets_after_window_elapses(self) -> None:
        breaker = CircuitBreakerAdapter(
            adapter=MockSolidWorksAdapter({}), failure_threshold=10, failure_window=0.05
        )

        async def _raise() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await breaker.call(_raise)
        assert breaker.failure_count == 1

        time.sleep(0.08)

        with pytest.raises(RuntimeError):
            await breaker.call(_raise)
        # Old failure discarded due to window rollover -> back to 1, not 2.
        assert breaker.failure_count == 1
