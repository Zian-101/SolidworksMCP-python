"""Coverage for the remaining un-exercised branches in analysis.py.

``check_interference``'s true "no adapter support" fallback is only reachable when the
adapter genuinely lacks the attribute - impossible for any ``SolidWorksAdapter``
subclass, since the base class always defines a default. The existing test in
``test_analysis.py`` deletes the mock's *override*, which still leaves the inherited
base-class method in place (hasattr stays True), so it actually exercises the "adapter
implements it but returns an error" branch, not the true fallback. That fallback needs
a bare ``object()`` adapter, matching the pattern already used for other
ADAPTER_FREE-style fallbacks in ``test_additional_coverage.py``.

``get_bounding_box``, ``analyze_geometry`` and ``get_material_properties`` also had no
tests for their error/exception branches, and ``analyze_geometry``'s two supported
analysis types (bounding_box, volume) had no tests driving real adapter data through
them at all.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from solidworks_mcp.tools.analysis import (
    GeometryAnalysisInput,
    InterferenceCheckInput,
    register_analysis_tools,
)


async def _tools(mcp_server, adapter, mock_config):
    await register_analysis_tools(mcp_server, adapter, mock_config)
    return {t.name: t.fn for t in await mcp_server.list_tools()}


class TestCheckInterferenceTrueFallback:
    @pytest.mark.asyncio
    async def test_bare_object_adapter_hits_no_adapter_support_branch(
        self, mcp_server, mock_config
    ):
        """A bare object() has no check_interference attribute at all: hasattr is
        False, so this hits the tool's own refusal message rather than any
        adapter-returned error."""
        tools = await _tools(mcp_server, object(), mock_config)
        result = await tools["check_interference"](
            input_data=InterferenceCheckInput(components=["A", "B"], tolerance=0.01)
        )
        assert result["status"] == "error"
        assert "does not implement check_interference" in result["message"]
        assert result["components_requested"] == ["A", "B"]
        assert result["tolerance"] == 0.01
        assert "interference_found" not in result


class TestGetBoundingBox:
    @pytest.mark.asyncio
    async def test_error_branch(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.get_bounding_box = AsyncMock(
            return_value=Mock(is_success=False, error="no solid bodies")
        )
        result = await tools["get_bounding_box"]()
        assert result["status"] == "error"
        assert "no solid bodies" in result["message"]

    @pytest.mark.asyncio
    async def test_exception_branch(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.get_bounding_box = AsyncMock(side_effect=RuntimeError("boom"))
        result = await tools["get_bounding_box"]()
        assert result["status"] == "error"
        assert "boom" in result["message"]


class TestAnalyzeGeometry:
    @pytest.mark.asyncio
    async def test_bounding_box_success_via_real_adapter(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["analyze_geometry"](
            input_data=GeometryAnalysisInput(analysis_type="bbox")
        )
        assert result["status"] == "success"
        assert result["analysis_type"] == "bbox"
        assert "results" in result

    @pytest.mark.asyncio
    async def test_bounding_box_error(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.get_bounding_box = AsyncMock(
            return_value=Mock(is_success=False, error="no geometry")
        )
        result = await tools["analyze_geometry"](
            input_data=GeometryAnalysisInput(analysis_type="bounding_box")
        )
        assert result["status"] == "error"
        assert "no geometry" in result["message"]
        assert result["analysis_type"] == "bounding_box"

    @pytest.mark.asyncio
    async def test_volume_success_via_real_adapter(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        await mock_adapter.create_part("ForVolume")
        result = await tools["analyze_geometry"](
            input_data=GeometryAnalysisInput(analysis_type="volume")
        )
        assert result["status"] == "success"
        assert result["analysis_type"] == "volume"
        assert "volume" in result["results"]
        assert result["results"]["volume_units"] == "mm^3"

    @pytest.mark.asyncio
    async def test_mass_alias_error(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.get_mass_properties = AsyncMock(
            return_value=Mock(is_success=False, error="no material")
        )
        result = await tools["analyze_geometry"](
            input_data=GeometryAnalysisInput(analysis_type="mass")
        )
        assert result["status"] == "error"
        assert "no material" in result["message"]
        assert result["analysis_type"] == "mass"

    @pytest.mark.asyncio
    async def test_unsupported_analysis_type_is_rejected(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["analyze_geometry"](
            input_data=GeometryAnalysisInput(analysis_type="curvature")
        )
        assert result["status"] == "error"
        assert "not supported" in result["message"]
        assert result["supported_types"] == [
            "bounding_box",
            "bbox",
            "extents",
            "volume",
            "mass",
        ]


class TestGetMaterialProperties:
    @pytest.mark.asyncio
    async def test_error_branch(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.get_material_properties = AsyncMock(
            return_value=Mock(is_success=False, error="no material assigned")
        )
        result = await tools["get_material_properties"]()
        assert result["status"] == "error"
        assert "no material assigned" in result["message"]

    @pytest.mark.asyncio
    async def test_exception_branch(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.get_material_properties = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        result = await tools["get_material_properties"]()
        assert result["status"] == "error"
        assert "boom" in result["message"]
