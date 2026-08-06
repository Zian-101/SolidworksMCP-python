"""Coverage for the feature-editing modeling tools added on this branch.

These tools (create_cut_extrude, add_fillet, delete_feature, create_reference_plane,
pattern_linear/circular, add_draft, move_body, delete_body, delete_face, scale_model,
set_material, insert_component, set_appearance, add_mate, create_axis, create_shell,
mirror_feature, suppress_feature, undo) had no tests at all before this file: neither
their pydantic validation, nor their success/error/exception branches in
``register_modeling_tools``.

Where the real ``mock_adapter`` implements the operation without needing any
model/sketch state (confirmed by reading ``adapters/mock_adapter.py``), tests call it
unmocked so the assertions exercise genuine adapter logic, not a stand-in. Where the
mock adapter has no failure path for a given tool (e.g. ``insert_component`` always
succeeds), the adapter method is overridden with an ``AsyncMock`` returning
``is_success=False`` - the same pattern already used throughout ``test_modeling.py``
for tools like ``close_model``.

``create_cut_extrude`` and ``add_fillet`` are NOT implemented by MockSolidWorksAdapter;
calling them unmocked exercises the real "not implemented by this adapter" error
returned by the base ``SolidWorksAdapter`` class - a genuine error path, not a fabricated
one.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from solidworks_mcp.tools.modeling import (
    AddDraftInput,
    AddFilletInput,
    AddMateInput,
    CloseModelInput,
    CreateAssemblyInput,
    CreateAxisInput,
    CreateCutExtrudeInput,
    CreateExtrusionInput,
    CreateLoftInput,
    CreatePartInput,
    CreateReferencePlaneInput,
    CreateShellInput,
    CreateSweepInput,
    DeleteBodyInput,
    DeleteFaceInput,
    DeleteFeatureInput,
    GetDimensionInput,
    InsertComponentInput,
    MirrorFeatureInput,
    MoveBodyInput,
    PatternCircularInput,
    PatternLinearInput,
    ScaleModelInput,
    SetAppearanceInput,
    SetDimensionInput,
    SetMaterialInput,
    SuppressFeatureInput,
    UndoInput,
    register_modeling_tools,
)


async def _tools(mcp_server, mock_adapter, mock_config):
    """Register modeling tools and return {name: fn}."""
    await register_modeling_tools(mcp_server, mock_adapter, mock_config)
    return {t.name: t.fn for t in await mcp_server.list_tools()}


class TestModelPostInitValidation:
    """Every model_post_init ValueError branch for the feature-editing inputs."""

    def test_create_cut_extrude_requires_positive_depth(self):
        with pytest.raises(ValueError):
            CreateCutExtrudeInput(depth=0)
        with pytest.raises(ValueError):
            CreateCutExtrudeInput(depth=-1)

    def test_add_fillet_requires_positive_radius(self):
        with pytest.raises(ValueError):
            AddFilletInput(radius=0)
        with pytest.raises(ValueError):
            AddFilletInput(radius=-2.0)

    def test_create_reference_plane_requires_offset_or_angle(self):
        with pytest.raises(ValueError):
            CreateReferencePlaneInput(reference="Front Plane")

    def test_mirror_feature_requires_features(self):
        with pytest.raises(ValueError):
            MirrorFeatureInput(features=[])

    def test_create_shell_requires_positive_thickness(self):
        with pytest.raises(ValueError):
            CreateShellInput(thickness=0)
        with pytest.raises(ValueError):
            CreateShellInput(thickness=-1.0)

    def test_pattern_linear_requires_features_and_count(self):
        with pytest.raises(ValueError):
            PatternLinearInput(features=[])
        with pytest.raises(ValueError):
            PatternLinearInput(features=["Cut1"], count=1)

    def test_pattern_circular_requires_features_count_angle(self):
        with pytest.raises(ValueError):
            PatternCircularInput(features=[])
        with pytest.raises(ValueError):
            PatternCircularInput(features=["Cut1"], count=1)
        with pytest.raises(ValueError):
            PatternCircularInput(features=["Cut1"], angle=0)

    def test_add_draft_requires_angle_faces_and_distinct_neutral(self):
        with pytest.raises(ValueError):
            AddDraftInput(angle=0, draft_faces=[0])
        with pytest.raises(ValueError):
            AddDraftInput(angle=5, draft_faces=[])
        with pytest.raises(ValueError):
            AddDraftInput(angle=5, neutral_face=0, draft_faces=[0, 1])

    def test_move_body_requires_offset_and_valid_copies(self):
        with pytest.raises(ValueError):
            MoveBodyInput(dx=0, dy=0, dz=0)
        with pytest.raises(ValueError):
            MoveBodyInput(dx=1.0, make_copy=True, copies=0)

    def test_delete_body_requires_indices(self):
        with pytest.raises(ValueError):
            DeleteBodyInput(bodies=[])

    def test_delete_face_requires_indices(self):
        with pytest.raises(ValueError):
            DeleteFaceInput(faces=[])

    def test_scale_model_requires_positive_and_nonnegative_factors(self):
        with pytest.raises(ValueError):
            ScaleModelInput(factor=0)
        with pytest.raises(ValueError):
            ScaleModelInput(factor=1.0, factor_y=-1.0)
        with pytest.raises(ValueError):
            ScaleModelInput(factor=1.0, factor_z=-1.0)

    def test_set_material_requires_nonempty_name(self):
        with pytest.raises(ValueError):
            SetMaterialInput(name="")
        with pytest.raises(ValueError):
            SetMaterialInput(name="   ")

    def test_insert_component_requires_nonempty_path(self):
        with pytest.raises(ValueError):
            InsertComponentInput(file_path="")

    def test_set_appearance_requires_valid_channels_and_transparency(self):
        with pytest.raises(ValueError):
            SetAppearanceInput(red=-1, green=0, blue=0)
        with pytest.raises(ValueError):
            SetAppearanceInput(red=0, green=0, blue=0, transparency=1.5)

    def test_add_mate_requires_distinct_nonempty_components(self):
        with pytest.raises(ValueError):
            AddMateInput(component_a="", component_b="Part2-1")
        with pytest.raises(ValueError):
            AddMateInput(component_a="Part1-1", component_b="Part1-1")


class TestFeatureEditingSuccessPaths:
    """Success branches, driven through the real (unmocked) mock adapter."""

    @pytest.mark.asyncio
    async def test_delete_feature_success(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["delete_feature"](
            DeleteFeatureInput(name="Boss-Extrude3")
        )
        assert result["status"] == "success"
        assert result["deleted"] == "Boss-Extrude3"
        assert "Boss-Extrude3" in result["message"]

    @pytest.mark.asyncio
    async def test_suppress_feature_success(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["suppress_feature"](
            SuppressFeatureInput(name="Fillet2", suppress=True)
        )
        assert result["status"] == "success"
        assert result["feature"] == "Fillet2"
        assert result["suppressed"] is True
        assert "Suppressed" in result["message"]

        result2 = await tools["suppress_feature"](
            SuppressFeatureInput(name="Fillet2", suppress=False)
        )
        assert result2["suppressed"] is False
        assert "Unsuppressed" in result2["message"]

    @pytest.mark.asyncio
    async def test_undo_success(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["undo"](UndoInput(count=3))
        assert result["status"] == "success"
        assert result["undone"] == 3

    @pytest.mark.asyncio
    async def test_create_reference_plane_success(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["create_reference_plane"](
            CreateReferencePlaneInput(reference="Front Plane", offset=2.0)
        )
        assert result["status"] == "success"
        assert result["plane"]["reference"] == "Front Plane"
        assert result["plane"]["offset"] == 2.0

    @pytest.mark.asyncio
    async def test_pattern_linear_success(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["pattern_linear"](
            PatternLinearInput(features=["Cut-Extrude1"], direction="x", count=3,
                                spacing=15.0)
        )
        assert result["status"] == "success"
        assert result["pattern"]["count"] == 3
        assert result["pattern"]["features"] == ["Cut-Extrude1"]

    @pytest.mark.asyncio
    async def test_add_draft_success(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["add_draft"](
            AddDraftInput(angle=5.0, neutral_face=4, draft_faces=[0, 1, 2, 3])
        )
        assert result["status"] == "success"
        assert result["draft"]["angle"] == 5.0
        assert result["draft"]["draft_faces"] == [0, 1, 2, 3]

    @pytest.mark.asyncio
    async def test_move_body_success(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["move_body"](MoveBodyInput(body=1, dx=40.0))
        assert result["status"] == "success"
        assert result["move"]["body"] == 1
        assert result["move"]["offset"] == {"x": 40.0, "y": 0.0, "z": 0.0}

    @pytest.mark.asyncio
    async def test_delete_body_success(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["delete_body"](DeleteBodyInput(bodies=[1]))
        assert result["status"] == "success"
        assert result["delete"]["deleted"] == [1]

    @pytest.mark.asyncio
    async def test_delete_face_success(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["delete_face"](DeleteFaceInput(faces=[6]))
        assert result["status"] == "success"
        assert result["delete_face"]["deleted"] == [6]

    @pytest.mark.asyncio
    async def test_scale_model_success(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["scale_model"](ScaleModelInput(factor=2.0))
        assert result["status"] == "success"
        assert result["scale"]["volume_ratio"] == 8.0

    @pytest.mark.asyncio
    async def test_set_material_success(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["set_material"](SetMaterialInput(name="6061 Alloy"))
        assert result["status"] == "success"
        assert result["material"]["name"] == "6061 Alloy"

    @pytest.mark.asyncio
    async def test_insert_component_success(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["insert_component"](
            InsertComponentInput(file_path="C:/parts/plate.sldprt", x=100.0)
        )
        assert result["status"] == "success"
        assert result["component"]["file_path"] == "C:/parts/plate.sldprt"
        assert result["component"]["position"]["x"] == 100.0

    @pytest.mark.asyncio
    async def test_set_appearance_success(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["set_appearance"](
            SetAppearanceInput(red=255, green=0, blue=0)
        )
        assert result["status"] == "success"
        assert result["appearance"]["color_255"] == [255, 0, 0]

    @pytest.mark.asyncio
    async def test_add_mate_success(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["add_mate"](
            AddMateInput(component_a="Part1-1", component_b="Part2-1",
                         mate_type="coincident")
        )
        assert result["status"] == "success"
        assert result["mate"]["components"] == ["Part1-1", "Part2-1"]
        assert "geometry moved" in result["message"]

    @pytest.mark.asyncio
    async def test_add_mate_no_geometry_moved_message(
        self, mcp_server, mock_adapter, mock_config
    ):
        """The message branches on geometry_moved being False vs None vs True."""
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.add_mate = AsyncMock(
            return_value=Mock(
                is_success=True,
                data={"components": ["A", "B"], "geometry_moved": False},
                execution_time=0.1,
            )
        )
        result = await tools["add_mate"](
            AddMateInput(component_a="A", component_b="B")
        )
        assert "nothing moved" in result["message"]

    @pytest.mark.asyncio
    async def test_create_axis_success(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["create_axis"](CreateAxisInput(reference="x"))
        assert result["status"] == "success"
        assert result["axis"]["reference"] == "x"

    @pytest.mark.asyncio
    async def test_pattern_circular_success(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["pattern_circular"](
            PatternCircularInput(features=["Cut-Extrude1"], axis="z", count=6)
        )
        assert result["status"] == "success"
        assert result["pattern"]["axis"] == "z"
        assert result["pattern"]["count"] == 6

    @pytest.mark.asyncio
    async def test_create_shell_success(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["create_shell"](
            CreateShellInput(thickness=2.0, remove_faces=[0])
        )
        assert result["status"] == "success"
        assert result["shell"]["thickness"] == 2.0
        assert "opened face(s)" in result["message"]

    @pytest.mark.asyncio
    async def test_create_shell_closed_message(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["create_shell"](CreateShellInput(thickness=1.5))
        assert result["status"] == "success"
        assert "(closed)" in result["message"]

    @pytest.mark.asyncio
    async def test_mirror_feature_success(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["mirror_feature"](
            MirrorFeatureInput(features=["Boss-Extrude110"], mirror_plane="Front Plane")
        )
        assert result["status"] == "success"
        assert result["mirror"]["mirrored_features"] == ["Boss-Extrude110"]

    @pytest.mark.asyncio
    async def test_create_cut_extrude_success(
        self, mcp_server, mock_adapter, mock_config
    ):
        """create_cut_extrude is not on MockSolidWorksAdapter; mock the happy path."""
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.create_cut_extrude = AsyncMock(
            return_value=Mock(
                is_success=True, data={"feature_name": "Cut-Extrude5"},
                execution_time=0.4,
            )
        )
        result = await tools["create_cut_extrude"](CreateCutExtrudeInput(depth=10.0))
        assert result["status"] == "success"
        assert result["cut_extrude"]["name"] == "Cut-Extrude5"
        assert result["cut_extrude"]["depth"] == 10.0

    @pytest.mark.asyncio
    async def test_add_fillet_success(self, mcp_server, mock_adapter, mock_config):
        """add_fillet is not on MockSolidWorksAdapter; mock the happy path."""
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.add_fillet = AsyncMock(
            return_value=Mock(
                is_success=True, data={"feature_name": "Fillet3"}, execution_time=0.3,
            )
        )
        result = await tools["add_fillet"](
            AddFilletInput(radius=2.0, edge_names=["Edge<1>", "Edge<2>"])
        )
        assert result["status"] == "success"
        assert result["fillet"]["name"] == "Fillet3"
        assert result["fillet"]["radius"] == 2.0
        assert result["fillet"]["edges"] == ["Edge<1>", "Edge<2>"]

    @pytest.mark.asyncio
    async def test_close_model_success(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        await mock_adapter.create_part("ForClose")
        result = await tools["close_model"](CloseModelInput(save=False))
        assert result["status"] == "success"
        assert result["saved"] is False
        assert "closed" in result["message"].lower()


class TestFeatureEditingErrorPaths:
    """Real (not-implemented) or forced adapter errors."""

    @pytest.mark.asyncio
    async def test_create_cut_extrude_not_implemented_by_mock_adapter(
        self, mcp_server, mock_adapter, mock_config
    ):
        """No override: exercises the base adapter's real 'not implemented' error."""
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["create_cut_extrude"](CreateCutExtrudeInput(depth=10.0))
        assert result["status"] == "error"
        assert "not implemented" in result["message"]

    @pytest.mark.asyncio
    async def test_add_fillet_not_implemented_by_mock_adapter(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["add_fillet"](AddFilletInput(radius=2.0))
        assert result["status"] == "error"
        assert "not implemented" in result["message"]

    @pytest.mark.asyncio
    async def test_add_mate_unknown_mate_type_error(
        self, mcp_server, mock_adapter, mock_config
    ):
        """Real adapter-level validation error - mate_type is not pydantic-restricted."""
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["add_mate"](
            AddMateInput(component_a="A", component_b="B", mate_type="bogus")
        )
        assert result["status"] == "error"
        assert "bogus" in result["message"]

    @pytest.mark.asyncio
    async def test_create_axis_unknown_reference_error(
        self, mcp_server, mock_adapter, mock_config
    ):
        """Real adapter-level validation error - reference isn't pydantic-restricted."""
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["create_axis"](CreateAxisInput(reference="w"))
        assert result["status"] == "error"
        assert "Unknown axis reference" in result["message"]

    @pytest.mark.asyncio
    async def test_set_appearance_out_of_range_channels_error(
        self, mcp_server, mock_adapter, mock_config
    ):
        """Real adapter-level validation - pydantic only checks >= 0, not the <=255 cap."""
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["set_appearance"](
            SetAppearanceInput(red=999, green=0, blue=0)
        )
        assert result["status"] == "error"
        assert "0-1 or 0-255" in result["message"]

    @pytest.mark.asyncio
    async def test_forced_error_paths_for_remaining_tools(
        self, mcp_server, mock_adapter, mock_config
    ):
        """Force is_success=False for tools whose mock adapter has no failure path."""
        tools = await _tools(mcp_server, mock_adapter, mock_config)

        mock_adapter.delete_feature = AsyncMock(
            return_value=Mock(is_success=False, error="cannot delete")
        )
        mock_adapter.suppress_feature = AsyncMock(
            return_value=Mock(is_success=False, error="cannot suppress")
        )
        mock_adapter.undo = AsyncMock(
            return_value=Mock(is_success=False, error="nothing to undo")
        )
        mock_adapter.create_reference_plane = AsyncMock(
            return_value=Mock(is_success=False, error="bad reference")
        )
        mock_adapter.pattern_linear = AsyncMock(
            return_value=Mock(is_success=False, error="bad pattern")
        )
        mock_adapter.add_draft = AsyncMock(
            return_value=Mock(is_success=False, error="bad draft")
        )
        mock_adapter.move_body = AsyncMock(
            return_value=Mock(is_success=False, error="bad move")
        )
        mock_adapter.delete_body = AsyncMock(
            return_value=Mock(is_success=False, error="bad delete body")
        )
        mock_adapter.delete_face = AsyncMock(
            return_value=Mock(is_success=False, error="bad delete face")
        )
        mock_adapter.scale_model = AsyncMock(
            return_value=Mock(is_success=False, error="bad scale")
        )
        mock_adapter.set_material = AsyncMock(
            return_value=Mock(is_success=False, error="bad material")
        )
        mock_adapter.insert_component = AsyncMock(
            return_value=Mock(is_success=False, error="bad insert")
        )
        mock_adapter.pattern_circular = AsyncMock(
            return_value=Mock(is_success=False, error="bad circular pattern")
        )
        mock_adapter.create_shell = AsyncMock(
            return_value=Mock(is_success=False, error="bad shell")
        )
        mock_adapter.mirror_feature = AsyncMock(
            return_value=Mock(is_success=False, error="bad mirror")
        )
        mock_adapter.close_model = AsyncMock(
            return_value=Mock(is_success=False, error="bad close")
        )

        assert (await tools["delete_feature"](DeleteFeatureInput(name="F1")))[
            "status"
        ] == "error"
        assert (
            await tools["suppress_feature"](SuppressFeatureInput(name="F1"))
        )["status"] == "error"
        assert (await tools["undo"](UndoInput()))["status"] == "error"
        assert (
            await tools["create_reference_plane"](
                CreateReferencePlaneInput(offset=1.0)
            )
        )["status"] == "error"
        assert (
            await tools["pattern_linear"](PatternLinearInput(features=["F1"]))
        )["status"] == "error"
        assert (
            await tools["add_draft"](AddDraftInput(angle=5, draft_faces=[1]))
        )["status"] == "error"
        assert (
            await tools["move_body"](MoveBodyInput(dx=1.0))
        )["status"] == "error"
        assert (
            await tools["delete_body"](DeleteBodyInput(bodies=[0]))
        )["status"] == "error"
        assert (
            await tools["delete_face"](DeleteFaceInput(faces=[0]))
        )["status"] == "error"
        assert (
            await tools["scale_model"](ScaleModelInput(factor=1.0))
        )["status"] == "error"
        assert (
            await tools["set_material"](SetMaterialInput(name="Steel"))
        )["status"] == "error"
        assert (
            await tools["insert_component"](
                InsertComponentInput(file_path="C:/p.sldprt")
            )
        )["status"] == "error"
        assert (
            await tools["pattern_circular"](PatternCircularInput(features=["F1"]))
        )["status"] == "error"
        assert (
            await tools["create_shell"](CreateShellInput(thickness=1.0))
        )["status"] == "error"
        assert (
            await tools["mirror_feature"](MirrorFeatureInput(features=["F1"]))
        )["status"] == "error"
        assert (
            await tools["close_model"](CloseModelInput(save=False))
        )["status"] == "error"


class TestFeatureEditingExceptionPaths:
    """The except Exception branch for every feature-editing tool."""

    @pytest.mark.asyncio
    async def test_exception_paths(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)

        mock_adapter.create_cut_extrude = AsyncMock(side_effect=RuntimeError("x1"))
        mock_adapter.add_fillet = AsyncMock(side_effect=RuntimeError("x2"))
        mock_adapter.delete_feature = AsyncMock(side_effect=RuntimeError("x3"))
        mock_adapter.create_reference_plane = AsyncMock(side_effect=RuntimeError("x4"))
        mock_adapter.pattern_linear = AsyncMock(side_effect=RuntimeError("x5"))
        mock_adapter.add_draft = AsyncMock(side_effect=RuntimeError("x6"))
        mock_adapter.move_body = AsyncMock(side_effect=RuntimeError("x7"))
        mock_adapter.delete_body = AsyncMock(side_effect=RuntimeError("x8"))
        mock_adapter.delete_face = AsyncMock(side_effect=RuntimeError("x9"))
        mock_adapter.scale_model = AsyncMock(side_effect=RuntimeError("x10"))
        mock_adapter.set_material = AsyncMock(side_effect=RuntimeError("x11"))
        mock_adapter.insert_component = AsyncMock(side_effect=RuntimeError("x12"))
        mock_adapter.set_appearance = AsyncMock(side_effect=RuntimeError("x13"))
        mock_adapter.add_mate = AsyncMock(side_effect=RuntimeError("x14"))
        mock_adapter.create_axis = AsyncMock(side_effect=RuntimeError("x15"))
        mock_adapter.pattern_circular = AsyncMock(side_effect=RuntimeError("x16"))
        mock_adapter.create_shell = AsyncMock(side_effect=RuntimeError("x17"))
        mock_adapter.mirror_feature = AsyncMock(side_effect=RuntimeError("x18"))
        mock_adapter.suppress_feature = AsyncMock(side_effect=RuntimeError("x19"))
        mock_adapter.undo = AsyncMock(side_effect=RuntimeError("x20"))

        assert (
            await tools["create_cut_extrude"](CreateCutExtrudeInput(depth=1.0))
        )["status"] == "error"
        assert (await tools["add_fillet"](AddFilletInput(radius=1.0)))[
            "status"
        ] == "error"
        assert (await tools["delete_feature"](DeleteFeatureInput(name="F1")))[
            "status"
        ] == "error"
        assert (
            await tools["create_reference_plane"](
                CreateReferencePlaneInput(offset=1.0)
            )
        )["status"] == "error"
        assert (
            await tools["pattern_linear"](PatternLinearInput(features=["F1"]))
        )["status"] == "error"
        assert (
            await tools["add_draft"](AddDraftInput(angle=5, draft_faces=[1]))
        )["status"] == "error"
        assert (await tools["move_body"](MoveBodyInput(dx=1.0)))["status"] == "error"
        assert (await tools["delete_body"](DeleteBodyInput(bodies=[0])))[
            "status"
        ] == "error"
        assert (await tools["delete_face"](DeleteFaceInput(faces=[0])))[
            "status"
        ] == "error"
        assert (await tools["scale_model"](ScaleModelInput(factor=1.0)))[
            "status"
        ] == "error"
        assert (await tools["set_material"](SetMaterialInput(name="Steel")))[
            "status"
        ] == "error"
        assert (
            await tools["insert_component"](
                InsertComponentInput(file_path="C:/p.sldprt")
            )
        )["status"] == "error"
        assert (
            await tools["set_appearance"](SetAppearanceInput(red=0, green=0, blue=0))
        )["status"] == "error"
        assert (
            await tools["add_mate"](AddMateInput(component_a="A", component_b="B"))
        )["status"] == "error"
        assert (await tools["create_axis"](CreateAxisInput()))["status"] == "error"
        assert (
            await tools["pattern_circular"](PatternCircularInput(features=["F1"]))
        )["status"] == "error"
        assert (await tools["create_shell"](CreateShellInput(thickness=1.0)))[
            "status"
        ] == "error"
        assert (
            await tools["mirror_feature"](MirrorFeatureInput(features=["F1"]))
        )["status"] == "error"
        assert (
            await tools["suppress_feature"](SuppressFeatureInput(name="F1"))
        )["status"] == "error"
        assert (await tools["undo"](UndoInput()))["status"] == "error"


class TestCreateAssemblyPartialFailure:
    """create_assembly reports a warning when some components fail to insert."""

    @pytest.mark.asyncio
    async def test_create_assembly_partial_component_failure(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)

        call_count = {"n": 0}
        real_insert = mock_adapter.insert_component

        async def flaky_insert(path, x, y, z):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return Mock(is_success=False, error="file locked")
            return await real_insert(path, x, y, z)

        mock_adapter.insert_component = flaky_insert

        result = await tools["create_assembly"](
            CreateAssemblyInput(
                name="asm1", components=["bad.sldprt", "good.sldprt"]
            )
        )
        assert result["status"] == "success"
        assert result["assembly"]["components_inserted"] == 1
        assert "warning" in result
        assert "bad.sldprt: file locked" in result["warning"]
        assert "1 of 2" in result["warning"]


class TestRemainingModelingGaps:
    """A handful of individually-uncovered lines missed by the batches above.

    ``CreateExtrusionInput.model_post_init`` checks depth before sketch_name, so a
    combined invalid test (as in ``test_modeling.py``) never reaches the
    sketch_name-empty branch alone. ``create_part``'s error branch, list_components'
    error/exception branches, and create_sweep/create_loft's exception branches were
    likewise never exercised on their own.
    """

    def test_create_extrusion_empty_sketch_name_with_valid_depth(self):
        with pytest.raises(ValueError):
            CreateExtrusionInput(sketch_name="   ", depth=5.0)

    @pytest.mark.asyncio
    async def test_create_part_error_branch(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.create_part = AsyncMock(
            return_value=Mock(is_success=False, error="template missing")
        )
        result = await tools["create_part"](CreatePartInput(name="P1"))
        assert result["status"] == "error"
        assert "template missing" in result["message"]

    @pytest.mark.asyncio
    async def test_list_components_success_error_and_exception(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)

        ok = await tools["list_components"]()
        assert ok["status"] == "success"
        assert ok["components"] == []

        mock_adapter.list_components = AsyncMock(
            return_value=Mock(is_success=False, error="no assembly open")
        )
        result = await tools["list_components"]()
        assert result["status"] == "error"
        assert "no assembly open" in result["message"]

        mock_adapter.list_components = AsyncMock(side_effect=RuntimeError("boom"))
        result2 = await tools["list_components"]()
        assert result2["status"] == "error"
        assert "boom" in result2["message"]

    @pytest.mark.asyncio
    async def test_create_sweep_and_loft_exception_paths(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.create_sweep = AsyncMock(side_effect=RuntimeError("sweep boom"))
        mock_adapter.create_loft = AsyncMock(side_effect=RuntimeError("loft boom"))

        sweep_result = await tools["create_sweep"](CreateSweepInput(path="Sketch2"))
        assert sweep_result["status"] == "error"
        assert "sweep boom" in sweep_result["message"]

        loft_result = await tools["create_loft"](
            CreateLoftInput(profiles=["S1", "S2"])
        )
        assert loft_result["status"] == "error"
        assert "loft boom" in loft_result["message"]


class TestDimensionNameRequiredGuards:
    """The defensive 'name is required' branch guards a manually-mutated instance.

    GetDimensionInput/SetDimensionInput.model_post_init already raises ValueError for
    an empty name at construction time, so the tool's own ``if not input_data.name``
    check is unreachable through normal construction. It guards against a valid
    instance whose name is mutated to empty after construction (the models are
    mutable pydantic BaseModels), which _normalize_input passes through unchanged
    since ``isinstance(input_data, GetDimensionInput)`` is already True.
    """

    @pytest.mark.asyncio
    async def test_get_dimension_empty_name_after_construction(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        input_data = GetDimensionInput(name="D1@Sketch1")
        input_data.name = None
        result = await tools["get_dimension"](input_data)
        assert result["status"] == "error"
        assert "required" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_set_dimension_empty_name_after_construction(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        input_data = SetDimensionInput(name="D1@Sketch1", value=5.0)
        input_data.name = None
        result = await tools["set_dimension"](input_data)
        assert result["status"] == "error"
        assert "required" in result["message"].lower()
