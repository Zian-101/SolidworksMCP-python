"""Coverage for the real (non-adapter) fallback implementations in automation.py.

``batch_process_files`` and ``create_template`` each do real work when the adapter has
no dedicated method for them (true of ``mock_adapter``, which defines neither): they
glob real files on disk and open/export/close them through the adapter, or copy a real
base file to a template destination and confirm the write. None of that fallback logic
had test coverage before this file - existing tests only ever hit the very first
guard clauses (empty source_directory, missing base_file).
"""

from unittest.mock import AsyncMock, Mock

import pytest

from solidworks_mcp.tools.automation import (
    BatchProcessInput,
    RecordMacroInput,
    TemplateInput,
    register_automation_tools,
)


async def _tools(mcp_server, adapter, mock_config):
    await register_automation_tools(mcp_server, adapter, mock_config)
    return {t.name: t.fn for t in await mcp_server.list_tools()}


class TestBatchProcessFilesFallback:
    """The real glob-and-open fallback used when the adapter has no batch method."""

    @pytest.mark.asyncio
    async def test_empty_source_directory_is_rejected(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["batch_process_files"](
            input_data={"source_directory": ""}
        )
        assert result["status"] == "error"
        assert "source_directory is required" in result["message"]

    @pytest.mark.asyncio
    async def test_nonexistent_directory_is_rejected(
        self, mcp_server, mock_adapter, mock_config, tmp_path
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        missing = tmp_path / "does_not_exist"
        result = await tools["batch_process_files"](
            input_data={"source_directory": str(missing)}
        )
        assert result["status"] == "error"
        assert "Not a directory" in result["message"]

    @pytest.mark.asyncio
    async def test_unsupported_operation_is_rejected(
        self, mcp_server, mock_adapter, mock_config, tmp_path
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        (tmp_path / "part1.sldprt").write_bytes(b"x")
        result = await tools["batch_process_files"](
            input_data=BatchProcessInput(
                source_directory=str(tmp_path), operation_type="rebuild"
            )
        )
        assert result["status"] == "error"
        assert "Unsupported operation" in result["message"]

    @pytest.mark.asyncio
    async def test_export_without_target_format_is_rejected(
        self, mcp_server, mock_adapter, mock_config, tmp_path
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        (tmp_path / "part1.sldprt").write_bytes(b"x")
        result = await tools["batch_process_files"](
            input_data=BatchProcessInput(
                source_directory=str(tmp_path), operation_type="export"
            )
        )
        assert result["status"] == "error"
        assert "target_format" in result["message"]

    @pytest.mark.asyncio
    async def test_no_matching_files_is_rejected(
        self, mcp_server, mock_adapter, mock_config, tmp_path
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["batch_process_files"](
            input_data=BatchProcessInput(
                source_directory=str(tmp_path), operation_type="open"
            )
        )
        assert result["status"] == "error"
        assert "No SolidWorks files found" in result["message"]

    @pytest.mark.asyncio
    async def test_open_operation_success_over_real_files(
        self, mcp_server, mock_adapter, mock_config, tmp_path
    ):
        """operation='open' really opens and closes each matching file."""
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        (tmp_path / "part1.sldprt").write_bytes(b"x")
        (tmp_path / "part2.sldprt").write_bytes(b"x")
        (tmp_path / "not_a_part.txt").write_bytes(b"x")
        # SolidWorks lock file: must be excluded even though it matches the suffix.
        (tmp_path / "~$part1.sldprt").write_bytes(b"x")

        result = await tools["batch_process_files"](
            input_data=BatchProcessInput(
                source_directory=str(tmp_path), operation_type="open"
            )
        )
        assert result["status"] == "success"
        assert result["batch_process"]["files_found"] == 2
        assert result["batch_process"]["files_successful"] == 2
        assert result["batch_process"]["files_failed"] == 0
        assert sorted(result["batch_process"]["succeeded"]) == [
            "part1.sldprt",
            "part2.sldprt",
        ]

    @pytest.mark.asyncio
    async def test_export_operation_success_over_real_files(
        self, mcp_server, mock_adapter, mock_config, tmp_path
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        (tmp_path / "part1.sldprt").write_bytes(b"x")

        result = await tools["batch_process_files"](
            input_data=BatchProcessInput(
                source_directory=str(tmp_path),
                operation_type="export",
                target_format="step",
            )
        )
        assert result["status"] == "success"
        assert result["batch_process"]["operation"] == "export"
        assert result["batch_process"]["target_format"] == "step"
        assert result["batch_process"]["files_successful"] == 1

    @pytest.mark.asyncio
    async def test_open_failure_is_recorded_and_reported_partial(
        self, mcp_server, mock_adapter, mock_config, tmp_path
    ):
        """A file that fails to open lands in failed_files and status is 'partial'."""
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        (tmp_path / "good.sldprt").write_bytes(b"x")
        (tmp_path / "bad.sldprt").write_bytes(b"x")

        real_open = mock_adapter.open_model

        async def flaky_open(path):
            if "bad" in path:
                return Mock(is_success=False, error="corrupt file")
            return await real_open(path)

        mock_adapter.open_model = flaky_open

        result = await tools["batch_process_files"](
            input_data=BatchProcessInput(
                source_directory=str(tmp_path), operation_type="open"
            )
        )
        assert result["status"] == "partial"
        assert result["batch_process"]["files_failed"] == 1
        assert any(
            f["file"] == "bad.sldprt" and f["error"] == "corrupt file"
            for f in result["batch_process"]["failed_files"]
        )

    @pytest.mark.asyncio
    async def test_export_failure_inside_loop_is_recorded(
        self, mcp_server, mock_adapter, mock_config, tmp_path
    ):
        """export_file failing (not raising) is recorded as a per-file failure."""
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        (tmp_path / "part1.sldprt").write_bytes(b"x")

        mock_adapter.export_file = AsyncMock(
            return_value=Mock(is_success=False, error="disk full")
        )

        result = await tools["batch_process_files"](
            input_data=BatchProcessInput(
                source_directory=str(tmp_path),
                operation_type="export",
                target_format="step",
            )
        )
        assert result["status"] == "partial"
        assert result["batch_process"]["failed_files"][0]["error"] == "disk full"

    @pytest.mark.asyncio
    async def test_per_file_exception_is_isolated(
        self, mcp_server, mock_adapter, mock_config, tmp_path
    ):
        """An exception raised for one file does not abort the whole batch."""
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        (tmp_path / "part1.sldprt").write_bytes(b"x")

        mock_adapter.export_file = AsyncMock(side_effect=RuntimeError("boom"))

        result = await tools["batch_process_files"](
            input_data=BatchProcessInput(
                source_directory=str(tmp_path),
                operation_type="export",
                target_format="step",
            )
        )
        assert result["status"] == "partial"
        assert "boom" in result["batch_process"]["failed_files"][0]["error"]

    @pytest.mark.asyncio
    async def test_recursive_glob_finds_nested_files(
        self, mcp_server, mock_adapter, mock_config, tmp_path
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        nested = tmp_path / "sub"
        nested.mkdir()
        (nested / "deep.sldprt").write_bytes(b"x")

        result = await tools["batch_process_files"](
            input_data=BatchProcessInput(
                source_directory=str(tmp_path), operation_type="open", recursive=True
            )
        )
        assert result["status"] == "success"
        assert result["batch_process"]["files_found"] == 1

    @pytest.mark.asyncio
    async def test_batch_process_files_outer_exception_handler(
        self, mcp_server, mock_adapter, mock_config
    ):
        """A payload _normalize_input cannot coerce hits the outer except handler."""
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["batch_process_files"](input_data=object())
        assert result["status"] == "error"
        assert "Failed batch processing" in result["message"]


class _MacroRecordingAdapterStub:
    """An adapter that implements start_macro_recording but fails."""

    async def start_macro_recording(self, _payload):
        from unittest.mock import Mock

        return Mock(is_success=False, error="recorder busy")


class TestStartMacroRecordingAdapterErrorBranch:
    """The hasattr(adapter, 'start_macro_recording') True-but-failed branch.

    mock_adapter has no start_macro_recording method at all, so this branch
    (as opposed to the 'not supported through this adapter' fallback) needs an
    adapter that implements the method and reports failure.
    """

    @pytest.mark.asyncio
    async def test_start_macro_recording_adapter_error(self, mcp_server, mock_config):
        tools = await _tools(mcp_server, _MacroRecordingAdapterStub(), mock_config)
        result = await tools["automation_start_macro_recording"](
            input_data=RecordMacroInput(macro_name="M1")
        )
        assert result["status"] == "error"
        assert "recorder busy" in result["message"]


class TestCreateTemplateFallback:
    """The real copy-to-destination fallback used when the adapter has no method."""

    @pytest.mark.asyncio
    async def test_missing_base_file_field_is_rejected(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["create_template"](
            input_data=TemplateInput(template_type="part", template_name="T1")
        )
        assert result["status"] == "error"
        assert "base_file is required" in result["message"]

    @pytest.mark.asyncio
    async def test_nonexistent_base_file_is_rejected(
        self, mcp_server, mock_adapter, mock_config
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        result = await tools["create_template"](
            input_data=TemplateInput(
                template_type="part",
                template_name="T1",
                base_file="C:/does/not/exist.sldprt",
            )
        )
        assert result["status"] == "error"
        assert "Base file not found" in result["message"]

    @pytest.mark.asyncio
    async def test_unknown_template_type_is_rejected(
        self, mcp_server, mock_adapter, mock_config, tmp_path
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        base = tmp_path / "base.sldprt"
        base.write_bytes(b"solid geometry here")
        result = await tools["create_template"](
            input_data=TemplateInput(
                template_type="bogus", template_name="T1", base_file=str(base)
            )
        )
        assert result["status"] == "error"
        assert "Unknown template_type" in result["message"]

    @pytest.mark.asyncio
    async def test_successful_template_copy_default_destination(
        self, mcp_server, mock_adapter, mock_config, tmp_path
    ):
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        base = tmp_path / "base.sldprt"
        base.write_bytes(b"real part bytes")

        result = await tools["create_template"](
            input_data=TemplateInput(
                template_type="part", template_name="MyTemplate", base_file=str(base)
            )
        )
        assert result["status"] == "success"
        destination = tmp_path / "MyTemplate.prtdot"
        assert destination.exists()
        assert destination.read_bytes() == b"real part bytes"
        assert result["template"]["file_location"] == str(destination)
        assert result["template"]["size_bytes"] == len(b"real part bytes")

    @pytest.mark.asyncio
    async def test_successful_template_copy_explicit_output_path_wrong_suffix(
        self, mcp_server, mock_adapter, mock_config, tmp_path
    ):
        """An output_path with the wrong extension is corrected to match the type."""
        tools = await _tools(mcp_server, mock_adapter, mock_config)
        base = tmp_path / "base.sldasm"
        base.write_bytes(b"assembly bytes")
        wrong_ext_output = tmp_path / "out" / "MyAsmTemplate.txt"

        result = await tools["create_template"](
            input_data=TemplateInput(
                template_type="assembly",
                template_name="MyAsmTemplate",
                base_file=str(base),
                output_path=str(wrong_ext_output),
            )
        )
        assert result["status"] == "success"
        corrected = wrong_ext_output.with_suffix(".asmdot")
        assert corrected.exists()
        assert result["template"]["file_location"] == str(corrected)

    @pytest.mark.asyncio
    async def test_destination_not_written_is_reported(
        self, mcp_server, mock_adapter, mock_config, tmp_path, monkeypatch
    ):
        """A copy that silently no-ops (destination missing afterward) is caught."""
        import shutil

        tools = await _tools(mcp_server, mock_adapter, mock_config)
        base = tmp_path / "base.sldprt"
        base.write_bytes(b"data")

        monkeypatch.setattr(shutil, "copyfile", lambda *a, **k: None)

        result = await tools["create_template"](
            input_data=TemplateInput(
                template_type="part", template_name="T1", base_file=str(base)
            )
        )
        assert result["status"] == "error"
        assert "was not written" in result["message"]

    @pytest.mark.asyncio
    async def test_create_template_exception_handler(
        self, mcp_server, mock_adapter, mock_config, tmp_path, monkeypatch
    ):
        """shutil.copyfile raising is caught by the tool's own exception handler."""
        import shutil

        tools = await _tools(mcp_server, mock_adapter, mock_config)
        base = tmp_path / "base.sldprt"
        base.write_bytes(b"data")

        def boom(*args, **kwargs):
            raise OSError("disk error")

        monkeypatch.setattr(shutil, "copyfile", boom)

        result = await tools["create_template"](
            input_data=TemplateInput(
                template_type="part", template_name="T1", base_file=str(base)
            )
        )
        assert result["status"] == "error"
        assert "Failed to create template" in result["message"]
