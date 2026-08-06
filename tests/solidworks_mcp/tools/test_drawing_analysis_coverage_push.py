"""Coverage for drawing_analysis.py branches missed by the existing test suite:

- analyze_drawing_comprehensive's fallback file_info branch (a real existing file)
  and its view_error branch (list_drawing_views failing), both of which were
  previously skipped over because existing tests either hit the "file not found"
  guard first or used a bare object() adapter that raises AttributeError before
  reaching them.
- compare_drawing_versions' real success path (two real, identical/different files) -
  existing tests only ever exercised the "missing args" / "file(s) not found" guards.
- validate_drawing_completeness's error branch (list_drawing_views failing) and its
  "no views" branch (an empty view list) - existing tests only used the mock
  adapter's default non-empty view list or an exception side effect.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from solidworks_mcp.tools.drawing_analysis import (
    DrawingAnalysisInput,
    register_drawing_analysis_tools,
)


async def _tools(mcp_server, adapter, mock_config):
    await register_drawing_analysis_tools(mcp_server, adapter, mock_config)
    return {t.name: t.fn for t in await mcp_server.list_tools()}


class _ListViewsOnlyAdapter:
    """Lacks analyze_drawing_comprehensive so the fallback runs, but implements
    list_drawing_views so the fallback can get past that call."""

    def __init__(self, list_views_result):
        self._result = list_views_result

    async def list_drawing_views(self):
        return self._result


class TestAnalyzeDrawingComprehensiveFallback:
    @pytest.mark.asyncio
    async def test_real_existing_file_reports_file_info(
        self, mcp_server, mock_config, tmp_path
    ):
        drawing = tmp_path / "part.slddrw"
        drawing.write_bytes(b"fake drawing bytes")
        adapter = _ListViewsOnlyAdapter(
            Mock(is_success=True, data=["Front", "Top"])
        )
        tools = await _tools(mcp_server, adapter, mock_config)

        result = await tools["analyze_drawing_comprehensive"](
            input_data=DrawingAnalysisInput(drawing_path=str(drawing))
        )
        assert result["status"] == "success"
        assert result["analysis"]["drawing_info"]["file_path"] == str(drawing)
        assert result["analysis"]["drawing_info"]["size_bytes"] == len(
            b"fake drawing bytes"
        )
        assert result["analysis"]["views"] == ["Front", "Top"]

    @pytest.mark.asyncio
    async def test_list_views_failure_reports_view_note(
        self, mcp_server, mock_config
    ):
        adapter = _ListViewsOnlyAdapter(
            Mock(is_success=False, error="no active drawing", data=None)
        )
        tools = await _tools(mcp_server, adapter, mock_config)

        result = await tools["analyze_drawing_comprehensive"](
            # No drawing_path: skips the file_info branch, goes straight to
            # the view listing.
            input_data=DrawingAnalysisInput(drawing_path="")
        )
        assert result["status"] == "success"
        assert result["analysis"]["view_note"] == "no active drawing"
        assert result["analysis"]["views"] == []

    @pytest.mark.asyncio
    async def test_exception_branch_via_missing_list_drawing_views(
        self, mcp_server, mock_config
    ):
        """A bare object() has neither method: the AttributeError on
        list_drawing_views is caught by the tool's own exception handler."""
        tools = await _tools(mcp_server, object(), mock_config)
        result = await tools["analyze_drawing_comprehensive"](
            input_data=DrawingAnalysisInput(drawing_path="")
        )
        assert result["status"] == "error"
        assert "Failed to analyze drawing" in result["message"]


class TestCompareDrawingVersionsRealFiles:
    @pytest.mark.asyncio
    async def test_identical_files(self, mcp_server, mock_config, tmp_path):
        tools = await _tools(mcp_server, object(), mock_config)
        first = tmp_path / "rev_a.slddrw"
        second = tmp_path / "rev_b.slddrw"
        first.write_bytes(b"same content")
        second.write_bytes(b"same content")

        result = await tools["compare_drawing_versions"](
            input_data={
                "drawing_version_1": str(first),
                "drawing_version_2": str(second),
            }
        )
        assert result["status"] == "success"
        assert result["comparison"]["identical"] is True
        assert "byte-identical" in result["message"]
        assert result["comparison"]["version_1"]["sha256"] == (
            result["comparison"]["version_2"]["sha256"]
        )

    @pytest.mark.asyncio
    async def test_different_files(self, mcp_server, mock_config, tmp_path):
        tools = await _tools(mcp_server, object(), mock_config)
        first = tmp_path / "rev_a.slddrw"
        second = tmp_path / "rev_b.slddrw"
        first.write_bytes(b"content one")
        second.write_bytes(b"content two, longer")

        result = await tools["compare_drawing_versions"](
            input_data={
                "drawing_version_1": str(first),
                "drawing_version_2": str(second),
            }
        )
        assert result["status"] == "success"
        assert result["comparison"]["identical"] is False
        assert "differ" in result["message"]
        assert result["comparison"]["size_delta_bytes"] == len(
            b"content two, longer"
        ) - len(b"content one")


class TestValidateDrawingCompletenessBranches:
    @pytest.mark.asyncio
    async def test_error_branch(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.list_drawing_views = AsyncMock(
            return_value=Mock(is_success=False, error="no drawing open")
        )
        result = await tools["validate_drawing_completeness"](
            input_data={"drawing_path": "demo.slddrw"}
        )
        assert result["status"] == "error"
        assert "no drawing open" in result["message"]

    @pytest.mark.asyncio
    async def test_no_views_branch(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.list_drawing_views = AsyncMock(
            return_value=Mock(is_success=True, data=[])
        )
        result = await tools["validate_drawing_completeness"](
            input_data={"drawing_path": "demo.slddrw"}
        )
        assert result["status"] == "success"
        assert result["completeness"]["view_count"] == 0
        assert result["completeness"]["findings"] == ["The drawing has no views."]
