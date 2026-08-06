"""Coverage for drawing.py tools that had no tests at all: create_standard_views and
list_drawing_views, plus the error branches of add_note and auto_dimension_view."""

from unittest.mock import AsyncMock, Mock

import pytest

from solidworks_mcp.tools.drawing import AddNoteInput, register_drawing_tools


async def _tools(mcp_server, adapter, mock_config):
    await register_drawing_tools(mcp_server, adapter, mock_config)
    return {t.name: t.fn for t in await mcp_server.list_tools()}


class TestCreateStandardViews:
    @pytest.mark.asyncio
    async def test_missing_model_path_is_rejected(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["create_standard_views"](input_data={})
        assert result["status"] == "error"
        assert "model_path is required" in result["message"]

    @pytest.mark.asyncio
    async def test_success_via_real_mock_adapter(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["create_standard_views"](
            input_data={"model_path": "C:/parts/bracket.sldprt"}
        )
        assert result["status"] == "success"
        assert result["standard_views"]["model_path"] == "C:/parts/bracket.sldprt"
        assert len(result["standard_views"]["views"]) == 3
        assert "3 standard views" in result["message"]

    @pytest.mark.asyncio
    async def test_error_branch(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.create_standard_views = AsyncMock(
            return_value=Mock(is_success=False, error="no drawing open")
        )
        result = await tools["create_standard_views"](
            input_data={"model_path": "C:/parts/bracket.sldprt"}
        )
        assert result["status"] == "error"
        assert "no drawing open" in result["message"]

    @pytest.mark.asyncio
    async def test_exception_branch(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.create_standard_views = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        result = await tools["create_standard_views"](
            input_data={"model_path": "C:/parts/bracket.sldprt"}
        )
        assert result["status"] == "error"
        assert "boom" in result["message"]


class TestListDrawingViews:
    @pytest.mark.asyncio
    async def test_success_via_real_mock_adapter(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["list_drawing_views"]()
        assert result["status"] == "success"
        assert result["views"] == ["Drawing View1", "Drawing View2"]
        assert "2 view(s)" in result["message"]

    @pytest.mark.asyncio
    async def test_error_branch(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.list_drawing_views = AsyncMock(
            return_value=Mock(is_success=False, error="no drawing open")
        )
        result = await tools["list_drawing_views"]()
        assert result["status"] == "error"
        assert "no drawing open" in result["message"]

    @pytest.mark.asyncio
    async def test_exception_branch(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.list_drawing_views = AsyncMock(side_effect=RuntimeError("boom"))
        result = await tools["list_drawing_views"]()
        assert result["status"] == "error"
        assert "boom" in result["message"]


class TestAddNoteErrorBranch:
    @pytest.mark.asyncio
    async def test_error_branch(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.add_drawing_note = AsyncMock(
            return_value=Mock(is_success=False, error="no drawing open")
        )
        result = await tools["add_note"](
            input_data=AddNoteInput(text="hello", position_x=1, position_y=2)
        )
        assert result["status"] == "error"
        assert "no drawing open" in result["message"]


class TestAutoDimensionViewErrorBranch:
    @pytest.mark.asyncio
    async def test_error_branch(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.insert_model_dimensions = AsyncMock(
            return_value=Mock(is_success=False, error="no active views")
        )
        result = await tools["auto_dimension_view"](input_data={"all_views": True})
        assert result["status"] == "error"
        assert "no active views" in result["message"]
