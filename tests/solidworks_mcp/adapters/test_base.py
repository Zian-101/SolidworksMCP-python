"""Tests for base adapter defaults."""

from __future__ import annotations

import pytest

from solidworks_mcp.adapters.base import AdapterResultStatus, SolidWorksAdapter


class _Adapter(SolidWorksAdapter):
    """Minimal concrete adapter for testing defaults."""

    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None

    def is_connected(self) -> bool:
        return False

    async def health_check(self):
        return None

    async def open_model(self, file_path):
        return None

    async def close_model(self, save=False):
        return None

    async def get_model_info(self):
        return None

    async def list_features(self, include_suppressed=True):
        return None

    async def list_configurations(self):
        return None

    async def create_part(self, part_name, template=None, units=None, material=None):
        return None

    async def create_assembly(self, assembly_name, template=None):
        return None

    async def create_drawing(self, drawing_name, template=None, sheet_size=None):
        return None

    async def create_extrusion(
        self,
        depth,
        direction=None,
        reverse=False,
        thin_feature=False,
        thin_thickness=0.0,
        both_directions=False,
        auto_fillet_corners=False,
        fillet_corners_radius=0.0,
    ):
        return None

    async def create_revolve(self, angle, direction=None):
        return None

    async def create_sweep(self, path_sketch, profile_sketch):
        return None

    async def create_loft(self, profile_sketches, guide_curves=None):
        return None

    async def create_sketch(self, plane):
        return None

    async def add_line(self, x1, y1, x2, y2):
        return None

    async def add_circle(self, cx, cy, radius):
        return None

    async def add_rectangle(self, x1, y1, x2, y2):
        return None

    async def exit_sketch(self):
        return None

    async def get_mass_properties(self):
        return None

    async def export_image(self, payload):
        return None

    async def export_file(self, file_path, file_format):
        return None

    async def get_dimension(self, name):
        return None

    async def set_dimension(self, name, value):
        return None


def test_base_config_normalizes_unknown_object() -> None:
    """Non-mapping config objects should normalize to empty dict."""
    # Pass a plain object without model_dump to hit the fallback branch.
    adapter = _Adapter(object())
    assert adapter.config_dict == {}


@pytest.mark.asyncio
async def test_base_default_sketch_helpers_return_error() -> None:
    """Default sketch helper methods should return not-implemented errors."""
    # Exercise default error responses for unimplemented sketch helpers.
    adapter = _Adapter({})

    result = await adapter.add_polygon(0.0, 0.0, 1.0, 5)
    assert result.status == AdapterResultStatus.ERROR

    result = await adapter.add_ellipse(0.0, 0.0, 2.0, 1.0)
    assert result.status == AdapterResultStatus.ERROR

    result = await adapter.add_sketch_constraint("e1", None, "coincident")
    assert result.status == AdapterResultStatus.ERROR

    result = await adapter.sketch_linear_pattern(["e1"], 1.0, 0.0, 5.0, 2)
    assert result.status == AdapterResultStatus.ERROR

    result = await adapter.sketch_circular_pattern(["e1"], 90.0, 4)
    assert result.status == AdapterResultStatus.ERROR

    result = await adapter.sketch_mirror(["e1"], "line1")
    assert result.status == AdapterResultStatus.ERROR

    result = await adapter.sketch_offset(["e1"], 1.0, False)
    assert result.status == AdapterResultStatus.ERROR


@pytest.mark.asyncio
async def test_base_default_capability_stubs_return_named_errors() -> None:
    """Every unimplemented capability on the base adapter must return an ERROR
    AdapterResult that names the capability — never a success-shaped payload.

    This walks the full set of default (non-abstract) methods on
    ``SolidWorksAdapter`` that a bare subclass inherits unmodified, mirroring
    the "no fabricated payloads" rule enforced for the tools layer.
    """
    adapter = _Adapter({})

    calls: list[tuple[str, object]] = [
        ("add_polyline", adapter.add_polyline([{"x": 0, "y": 0}, {"x": 1, "y": 1}])),
        ("delete_feature", adapter.delete_feature("Boss-Extrude1")),
        ("suppress_feature", adapter.suppress_feature("Boss-Extrude1")),
        ("undo", adapter.undo()),
        ("create_reference_plane", adapter.create_reference_plane("Front Plane", offset=5.0)),
        ("mirror_feature", adapter.mirror_feature(["Boss-Extrude1"], "Front Plane")),
        ("create_shell", adapter.create_shell(2.0)),
        ("pattern_linear", adapter.pattern_linear(["Boss-Extrude1"])),
        ("create_axis", adapter.create_axis("z")),
        ("pattern_circular", adapter.pattern_circular(["Boss-Extrude1"])),
        ("add_draft", adapter.add_draft(5.0, draft_faces=[1])),
        ("move_body", adapter.move_body(dx=10.0)),
        ("delete_body", adapter.delete_body([0])),
        ("delete_face", adapter.delete_face([0])),
        ("scale_model", adapter.scale_model(2.0)),
        ("set_material", adapter.set_material("1060 Alloy")),
        ("insert_component", adapter.insert_component("C:/tmp/part.sldprt")),
        ("set_appearance", adapter.set_appearance(1.0, 0.0, 0.0)),
        ("add_mate", adapter.add_mate("CompA", "CompB")),
        ("list_components", adapter.list_components()),
        ("create_standard_views", adapter.create_standard_views("C:/tmp/part.sldprt")),
        ("add_drawing_note", adapter.add_drawing_note("note text")),
        ("insert_model_dimensions", adapter.insert_model_dimensions()),
        ("list_drawing_views", adapter.list_drawing_views()),
        ("get_bounding_box", adapter.get_bounding_box()),
        ("get_material_properties", adapter.get_material_properties()),
    ]

    for capability_name, coro in calls:
        result = await coro
        assert result.status == AdapterResultStatus.ERROR, (
            f"{capability_name} should return ERROR, got {result.status}"
        )
        assert result.data is None, (
            f"{capability_name} must not return a success-shaped payload"
        )
        assert result.error is not None and capability_name in result.error, (
            f"{capability_name} error message should name the capability: {result.error!r}"
        )
        assert "not implemented" in result.error
