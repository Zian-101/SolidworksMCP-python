"""Coverage tests for ConnectionPoolAdapter's remaining pass-through methods.

Mirrors tests/solidworks_mcp/adapters/test_circuit_breaker_pass_through.py:
each pass-through (delete_feature, suppress_feature, ...) is called through a
pool backed by MockSolidWorksAdapter and the assertions check the specific
payload the mock produces, proving real delegation with the right arguments
rather than a stubbed-out short-circuit.
"""

from __future__ import annotations

import pytest

from solidworks_mcp.adapters.connection_pool import ConnectionPoolAdapter
from solidworks_mcp.adapters.mock_adapter import MockSolidWorksAdapter


async def _pool_with_part() -> ConnectionPoolAdapter:
    pool = ConnectionPoolAdapter(
        adapter_factory=lambda: MockSolidWorksAdapter({}), pool_size=1
    )
    await pool.connect()
    await pool.create_part("TestPart")
    return pool


class TestPoolPassThroughMethodsDelegateWithRealPayloads:
    @pytest.mark.asyncio
    async def test_delete_feature(self) -> None:
        pool = await _pool_with_part()
        result = await pool.delete_feature("Boss-Extrude1")
        assert result.is_success
        assert result.data == {"deleted": "Boss-Extrude1"}
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_suppress_feature(self) -> None:
        pool = await _pool_with_part()
        result = await pool.suppress_feature("Boss-Extrude1", suppress=False)
        assert result.is_success
        assert result.data == {"feature": "Boss-Extrude1", "suppressed": False}
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_undo(self) -> None:
        pool = await _pool_with_part()
        result = await pool.undo(count=2)
        assert result.is_success
        assert result.data == {"undone": 2}
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_create_reference_plane(self) -> None:
        pool = await _pool_with_part()
        result = await pool.create_reference_plane("Top Plane", offset=3.0)
        assert result.is_success
        assert result.data["reference"] == "Top Plane"
        assert result.data["offset"] == 3.0
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_mirror_feature(self) -> None:
        pool = await _pool_with_part()
        result = await pool.mirror_feature(["Boss-Extrude1"], "Right Plane")
        assert result.is_success
        assert result.data["mirror_plane"] == "Right Plane"
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_create_shell(self) -> None:
        pool = await _pool_with_part()
        result = await pool.create_shell(1.5)
        assert result.is_success
        assert result.data["thickness"] == 1.5
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_pattern_linear(self) -> None:
        pool = await _pool_with_part()
        result = await pool.pattern_linear(["Boss-Extrude1"], count=3)
        assert result.is_success
        assert result.data["count"] == 3
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_add_draft(self) -> None:
        pool = await _pool_with_part()
        result = await pool.add_draft(3.0, draft_faces=[2])
        assert result.is_success
        assert result.data["draft_faces"] == [2]
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_move_body(self) -> None:
        pool = await _pool_with_part()
        result = await pool.move_body(dz=4.0)
        assert result.is_success
        assert result.data["offset"]["z"] == 4.0
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_delete_body(self) -> None:
        pool = await _pool_with_part()
        result = await pool.delete_body([1])
        assert result.is_success
        assert result.data["deleted"] == [1]
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_delete_face(self) -> None:
        pool = await _pool_with_part()
        result = await pool.delete_face([3])
        assert result.is_success
        assert result.data["deleted"] == [3]
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_scale_model(self) -> None:
        pool = await _pool_with_part()
        result = await pool.scale_model(1.5)
        assert result.is_success
        assert result.data["factors"]["x"] == 1.5
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_set_material(self) -> None:
        pool = await _pool_with_part()
        result = await pool.set_material("Copper", database="custom.sldmat")
        assert result.is_success
        assert result.data["name"] == "Copper"
        assert result.data["database"] == "custom.sldmat"
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_insert_component(self) -> None:
        pool = await _pool_with_part()
        result = await pool.insert_component("C:/tmp/comp.sldprt", y=2.0)
        assert result.is_success
        assert result.data["position"]["y"] == 2.0
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_set_appearance(self) -> None:
        pool = await _pool_with_part()
        result = await pool.set_appearance(0.0, 1.0, 0.0)
        assert result.is_success
        assert result.data["color"] == {"r": 0.0, "g": 1.0, "b": 0.0}
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_add_mate(self) -> None:
        pool = await _pool_with_part()
        result = await pool.add_mate("CompX", "CompY", mate_type="tangent")
        assert result.is_success
        assert result.data["mate_type"] == "tangent"
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_list_components(self) -> None:
        pool = await _pool_with_part()
        await pool.insert_component("C:/tmp/comp.sldprt")
        result = await pool.list_components()
        assert result.is_success
        assert result.data == ["component-1"]
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_add_drawing_view(self) -> None:
        pool = await _pool_with_part()
        result = await pool.add_drawing_view("C:/tmp/part.sldprt", orientation="right")
        assert result.is_success
        assert result.data["orientation"] == "right"
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_create_standard_views(self) -> None:
        pool = await _pool_with_part()
        result = await pool.create_standard_views("C:/tmp/part.sldprt")
        assert result.is_success
        assert result.data["projection"] == "third_angle"
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_add_drawing_note(self) -> None:
        pool = await _pool_with_part()
        result = await pool.add_drawing_note("Pool note")
        assert result.is_success
        assert result.data["text"] == "Pool note"
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_insert_model_dimensions(self) -> None:
        pool = await _pool_with_part()
        result = await pool.insert_model_dimensions()
        assert result.is_success
        assert result.data["annotations_inserted"] == 6
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_list_drawing_views(self) -> None:
        pool = await _pool_with_part()
        result = await pool.list_drawing_views()
        assert result.is_success
        assert result.data == ["Drawing View1", "Drawing View2"]
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_create_axis(self) -> None:
        pool = await _pool_with_part()
        result = await pool.create_axis("x")
        assert result.is_success
        assert result.data["reference"] == "x"
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_pattern_circular(self) -> None:
        pool = await _pool_with_part()
        result = await pool.pattern_circular(["Boss-Extrude1"], count=5, angle=270.0)
        assert result.is_success
        assert result.data["count"] == 5
        assert result.data["angle"] == 270.0
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_add_polyline(self) -> None:
        pool = await _pool_with_part()
        await pool.create_sketch("Front Plane")
        points = [{"x": 0, "y": 0}, {"x": 2, "y": 0}]
        result = await pool.add_polyline(points, closed=False)
        assert result.is_success
        assert result.data["segments"] == 1
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_get_bounding_box(self) -> None:
        pool = await _pool_with_part()
        result = await pool.get_bounding_box()
        assert result.is_success
        assert result.data["units"] == "mm"
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_check_interference(self) -> None:
        pool = await _pool_with_part()
        result = await pool.check_interference()
        assert result.is_success
        assert result.data["interference_found"] is False
        await pool.disconnect()

    @pytest.mark.asyncio
    async def test_get_material_properties(self) -> None:
        pool = await _pool_with_part()
        result = await pool.get_material_properties()
        assert result.is_success
        assert result.data["name"] == "Plain Carbon Steel"
        await pool.disconnect()
