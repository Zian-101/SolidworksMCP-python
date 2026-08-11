"""Coverage for get_file_properties' three branches that read real filesystem
metadata: an existing file on disk, a path that is set but not on disk (already
covered elsewhere), a document with no saved path at all, and the tool's own
exception handler."""

from unittest.mock import AsyncMock, Mock

import pytest

from solidworks_mcp.tools.file_management import register_file_management_tools


async def _tools(mcp_server, adapter, mock_config):
    await register_file_management_tools(mcp_server, adapter, mock_config)
    return {t.name: t.fn for t in await mcp_server.list_tools()}


class TestGetFilePropertiesFilesystemBranches:
    @pytest.mark.asyncio
    async def test_real_file_on_disk_reports_size_and_dates(
        self, mcp_server, mock_adapter, mock_config, tmp_path
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        real_file = tmp_path / "saved_part.sldprt"
        real_file.write_bytes(b"solid geometry bytes")

        mock_adapter.get_model_info = AsyncMock(
            return_value=Mock(
                is_success=True,
                data={
                    "name": "saved_part",
                    "path": str(real_file),
                    "type": "Part",
                    "configuration": "Default",
                    "feature_count": 4,
                },
            )
        )

        result = await tools["get_file_properties"]()
        assert result["status"] == "success"
        props = result["properties"]
        # Upstream's get_file_properties reports raw stat values: size in bytes
        # and st_ctime/st_mtime floats. It does not emit the "file_size" MB
        # string or the "note" field this test originally asserted.
        assert props["file_size_bytes"] == real_file.stat().st_size
        assert props["created_date"] is not None
        assert props["modified_date"] is not None
        assert props["file_path"] == str(real_file)

    @pytest.mark.asyncio
    async def test_unsaved_document_has_no_path(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.get_model_info = AsyncMock(
            return_value=Mock(
                is_success=True,
                data={
                    "name": "InMemoryPart",
                    "path": "",
                    "type": "Part",
                    "configuration": "Default",
                    "feature_count": 0,
                },
            )
        )

        result = await tools["get_file_properties"]()
        assert result["status"] == "success"
        props = result["properties"]
        # An unsaved document has no path, so there are no stat values to
        # report. The keys are present but null rather than fabricated.
        assert props["file_path"] == ""
        assert props["file_size_bytes"] is None
        assert props["created_date"] is None
        assert props["modified_date"] is None

    @pytest.mark.asyncio
    async def test_exception_branch(self, mcp_server, mock_adapter, mock_config):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.get_model_info = AsyncMock(side_effect=RuntimeError("boom"))
        result = await tools["get_file_properties"]()
        assert result["status"] == "error"
        assert "boom" in result["message"]

    @pytest.mark.asyncio
    async def test_get_model_info_failure_is_reported(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.get_model_info = AsyncMock(
            return_value=Mock(is_success=False, error="no active document")
        )
        result = await tools["get_file_properties"]()
        assert result["status"] == "error"
        assert "no active document" in result["message"]


class TestSavePartAndAssemblyCurrentLocationErrorBranches:
    """save_part/save_assembly with no file_path save to the current location;
    both surface the adapter's error when that save fails."""

    @pytest.mark.asyncio
    async def test_save_part_current_location_error(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.save_file = AsyncMock(
            return_value=Mock(is_success=False, error="read-only")
        )
        result = await tools["save_part"](input_data=None)
        assert result["status"] == "error"
        assert "read-only" in result["message"]

    @pytest.mark.asyncio
    async def test_save_assembly_current_location_error(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        mock_adapter.save_file = AsyncMock(
            return_value=Mock(is_success=False, error="read-only")
        )
        result = await tools["save_assembly"](input_data=None)
        assert result["status"] == "error"
        assert "read-only" in result["message"]
