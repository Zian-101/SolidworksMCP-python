"""Behavioural coverage tests for solidworks_mcp.adapters.mock_adapter.

These target methods/branches of ``MockSolidWorksAdapter`` that the rest of
the suite never exercises: ``select_feature``'s success path, the whole
``add_polyline`` body, ``add_spline``'s malformed-point guard,
``sketch_mirror``'s "must be a centerline" guard, ``add_sketch_constraint``
end to end, and the validation guards on ``create_reference_plane``,
``mirror_feature``, ``create_shell``, and ``pattern_linear``, plus the
success bodies of ``check_sketch_fully_defined``, ``export_image``, and the
STL branch of ``export_file``.

Every assertion below checks the actual returned payload (feature names,
ids, file bytes on disk, etc.) — not just that a call returns without
raising — per the "no coverage theater" rule for this branch.
"""

from __future__ import annotations

import pathlib

import pytest

from solidworks_mcp.adapters.base import AdapterResultStatus
from solidworks_mcp.adapters.mock_adapter import MockSolidWorksAdapter


async def _connected_with_part() -> MockSolidWorksAdapter:
    adapter = MockSolidWorksAdapter({})
    await adapter.connect()
    await adapter.create_part("TestPart")
    return adapter


class TestSelectFeature:
    @pytest.mark.asyncio
    async def test_select_feature_without_model_errors(self) -> None:
        adapter = MockSolidWorksAdapter({})
        await adapter.connect()
        result = await adapter.select_feature("Boss-Extrude1")
        assert result.status == AdapterResultStatus.ERROR
        assert result.error == "No active model"

    @pytest.mark.asyncio
    async def test_select_feature_success_reports_the_requested_feature(self) -> None:
        adapter = await _connected_with_part()
        result = await adapter.select_feature("Boss-Extrude1")
        assert result.status == AdapterResultStatus.SUCCESS
        assert result.data["selected"] is True
        assert result.data["feature_name"] == "Boss-Extrude1"
        assert result.data["entity_type"] == "mock"


class TestAddPolyline:
    @pytest.mark.asyncio
    async def test_add_polyline_without_sketch_errors(self) -> None:
        adapter = await _connected_with_part()
        result = await adapter.add_polyline([{"x": 0, "y": 0}, {"x": 1, "y": 1}])
        assert result.status == AdapterResultStatus.ERROR
        assert result.error == "No active sketch"

    @pytest.mark.asyncio
    async def test_add_polyline_rejects_fewer_than_two_points(self) -> None:
        adapter = await _connected_with_part()
        await adapter.create_sketch("Front Plane")
        result = await adapter.add_polyline([{"x": 0, "y": 0}])
        assert result.status == AdapterResultStatus.ERROR
        assert "at least 2 points" in result.error

    @pytest.mark.asyncio
    async def test_add_polyline_open_produces_n_minus_one_segments(self) -> None:
        adapter = await _connected_with_part()
        await adapter.create_sketch("Front Plane")
        points = [{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1}]
        result = await adapter.add_polyline(points, closed=False)
        assert result.status == AdapterResultStatus.SUCCESS
        assert result.data["segments"] == 2
        assert result.data["closed"] is False
        assert len(result.data["ids"]) == 2
        # Registered ids must be usable by downstream sketch calls.
        for entity_id in result.data["ids"]:
            assert entity_id in adapter._sketch_entity_ids

    @pytest.mark.asyncio
    async def test_add_polyline_closed_adds_a_closing_segment(self) -> None:
        adapter = await _connected_with_part()
        await adapter.create_sketch("Front Plane")
        points = [{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1}]
        result = await adapter.add_polyline(points, closed=True)
        assert result.status == AdapterResultStatus.SUCCESS
        # 3 points closed => 3 segments (n-1 open segments + 1 closing one).
        assert result.data["segments"] == 3
        assert result.data["closed"] is True
        assert len(result.data["ids"]) == 3


class TestAddSpline:
    @pytest.mark.asyncio
    async def test_add_spline_rejects_point_missing_xy_keys(self) -> None:
        adapter = await _connected_with_part()
        await adapter.create_sketch("Front Plane")
        result = await adapter.add_spline([{"x": 0, "y": 0}, {"x": 1}])
        assert result.status == AdapterResultStatus.ERROR
        assert "index 1" in result.error
        assert "'x' and/or 'y'" in result.error


class TestSketchMirror:
    @pytest.mark.asyncio
    async def test_sketch_mirror_rejects_non_centerline_mirror_axis(self) -> None:
        adapter = await _connected_with_part()
        await adapter.create_sketch("Front Plane")
        line_id = (await adapter.add_line(0, 0, 10, 0)).data
        # A plain line is a valid registered entity but not a centerline.
        result = await adapter.sketch_mirror([line_id], line_id)
        assert result.status == AdapterResultStatus.ERROR
        assert "must be a centerline" in result.error
        assert line_id in result.error


class TestAddSketchConstraint:
    @pytest.mark.asyncio
    async def test_add_sketch_constraint_without_sketch_errors(self) -> None:
        adapter = await _connected_with_part()
        result = await adapter.add_sketch_constraint("e1", None, "coincident")
        assert result.status == AdapterResultStatus.ERROR
        assert result.error == "No active sketch"

    @pytest.mark.asyncio
    async def test_add_sketch_constraint_rejects_unsupported_relation(self) -> None:
        adapter = await _connected_with_part()
        await adapter.create_sketch("Front Plane")
        result = await adapter.add_sketch_constraint("e1", None, "not_a_real_relation")
        assert result.status == AdapterResultStatus.ERROR
        assert "Unsupported relation type" in result.error

    @pytest.mark.asyncio
    async def test_add_sketch_constraint_symmetric_requires_three_entities(self) -> None:
        adapter = await _connected_with_part()
        await adapter.create_sketch("Front Plane")
        line_id = (await adapter.add_line(0, 0, 10, 0)).data
        result = await adapter.add_sketch_constraint(line_id, None, "symmetric")
        assert result.status == AdapterResultStatus.ERROR
        assert "entity1, entity2, and entity3" in result.error

    @pytest.mark.asyncio
    async def test_add_sketch_constraint_rejects_entity3_on_non_symmetric_relation(
        self,
    ) -> None:
        adapter = await _connected_with_part()
        await adapter.create_sketch("Front Plane")
        line_a = (await adapter.add_line(0, 0, 10, 0)).data
        line_b = (await adapter.add_line(0, 0, 0, 10)).data
        line_c = (await adapter.add_line(5, 5, 6, 6)).data
        result = await adapter.add_sketch_constraint(
            line_a, line_b, "parallel", line_c
        )
        assert result.status == AdapterResultStatus.ERROR
        assert "does not accept entity3" in result.error

    @pytest.mark.asyncio
    async def test_add_sketch_constraint_rejects_unknown_entity_id(self) -> None:
        adapter = await _connected_with_part()
        await adapter.create_sketch("Front Plane")
        line_a = (await adapter.add_line(0, 0, 10, 0)).data
        result = await adapter.add_sketch_constraint(line_a, "Line_bogus", "parallel")
        assert result.status == AdapterResultStatus.ERROR
        assert "Unknown sketch entity" in result.error

    @pytest.mark.asyncio
    async def test_add_sketch_constraint_success_returns_constraint_id(self) -> None:
        adapter = await _connected_with_part()
        await adapter.create_sketch("Front Plane")
        line_a = (await adapter.add_line(0, 0, 10, 0)).data
        line_b = (await adapter.add_line(0, 0, 0, 10)).data
        result = await adapter.add_sketch_constraint(line_a, line_b, "perpendicular")
        assert result.status == AdapterResultStatus.SUCCESS
        assert result.data.startswith("Constraint_perpendicular_")


class TestCreateReferencePlane:
    @pytest.mark.asyncio
    async def test_requires_nonzero_offset_or_angle(self) -> None:
        adapter = await _connected_with_part()
        result = await adapter.create_reference_plane("Front Plane", offset=0.0, angle=0.0)
        assert result.status == AdapterResultStatus.ERROR
        assert "non-zero offset or angle" in result.error


class TestMirrorFeature:
    @pytest.mark.asyncio
    async def test_requires_at_least_one_feature(self) -> None:
        adapter = await _connected_with_part()
        result = await adapter.mirror_feature([], "Front Plane")
        assert result.status == AdapterResultStatus.ERROR
        assert "at least one feature name" in result.error


class TestCreateShell:
    @pytest.mark.asyncio
    async def test_requires_positive_thickness(self) -> None:
        adapter = await _connected_with_part()
        result = await adapter.create_shell(0.0)
        assert result.status == AdapterResultStatus.ERROR
        assert "positive wall thickness" in result.error

        result = await adapter.create_shell(-1.0)
        assert result.status == AdapterResultStatus.ERROR


class TestPatternLinear:
    @pytest.mark.asyncio
    async def test_requires_at_least_one_feature(self) -> None:
        adapter = await _connected_with_part()
        result = await adapter.pattern_linear([])
        assert result.status == AdapterResultStatus.ERROR
        assert "at least one feature name" in result.error

    @pytest.mark.asyncio
    async def test_requires_count_at_least_two(self) -> None:
        adapter = await _connected_with_part()
        result = await adapter.pattern_linear(["Boss-Extrude1"], count=1)
        assert result.status == AdapterResultStatus.ERROR
        assert "count >= 2" in result.error


class TestCheckSketchFullyDefined:
    @pytest.mark.asyncio
    async def test_success_defaults_to_current_sketch(self) -> None:
        adapter = await _connected_with_part()
        await adapter.create_sketch("Front Plane")
        result = await adapter.check_sketch_fully_defined()
        assert result.status == AdapterResultStatus.SUCCESS
        assert result.data["sketch_name"] == "Sketch1"
        assert result.data["is_fully_defined"] is True
        assert result.data["source"] == "mock"

    @pytest.mark.asyncio
    async def test_unknown_sketch_name_errors(self) -> None:
        adapter = await _connected_with_part()
        await adapter.create_sketch("Front Plane")
        result = await adapter.check_sketch_fully_defined(sketch_name="Sketch99")
        assert result.status == AdapterResultStatus.ERROR
        assert "Sketch not found: Sketch99" == result.error


class TestExportImage:
    @pytest.mark.asyncio
    async def test_export_image_writes_a_real_png_file(self, tmp_path: pathlib.Path) -> None:
        adapter = await _connected_with_part()
        out_file = tmp_path / "shot.png"
        result = await adapter.export_image(
            {
                "file_path": str(out_file),
                "width": 640,
                "height": 480,
                "view_orientation": "isometric",
            }
        )
        assert result.status == AdapterResultStatus.SUCCESS
        assert result.data["dimensions"] == "640x480"
        assert result.data["view"] == "isometric"
        assert out_file.exists()
        # PNG signature.
        assert out_file.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


class TestExportFileStl:
    @pytest.mark.asyncio
    async def test_export_file_stl_writes_placeholder_geometry(
        self, tmp_path: pathlib.Path
    ) -> None:
        adapter = await _connected_with_part()
        out_file = tmp_path / "part.stl"
        result = await adapter.export_file(str(out_file), "stl")
        assert result.status == AdapterResultStatus.SUCCESS
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert content.startswith("solid mock")
        assert "endsolid mock" in content
