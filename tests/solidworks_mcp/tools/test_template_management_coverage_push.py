"""Coverage for template_management.py branches missed by the existing suite:

- _load_library tolerating a corrupt JSON file and a well-formed-but-wrong-shape file.
- extract_template's real copy-to-destination fallback (unknown type, directory/suffix
  handling, and an actual successful write) - existing tests only reached the
  "source model not found" guard.
- compare_templates' "both paths required" guard and its real file-comparison success
  path - existing tests never supplied real files.
"""

import json

import pytest

from solidworks_mcp.tools.template_management import (
    TemplateComparisonInput,
    TemplateExtractionInput,
    _library_path,
    _load_library,
    register_template_management_tools,
)


async def _tools(mcp_server, adapter, mock_config):
    await register_template_management_tools(mcp_server, adapter, mock_config)
    return {t.name: t.fn for t in await mcp_server.list_tools()}


class TestLoadLibraryTolerance:
    def test_corrupt_json_returns_empty_templates(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        path = _library_path()
        path.write_text("{not valid json", encoding="utf-8")
        library = _load_library()
        assert library == {"templates": []}

    def test_wrong_shape_json_returns_empty_templates(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        path = _library_path()
        path.write_text(json.dumps({"templates": "not-a-list"}), encoding="utf-8")
        library = _load_library()
        assert library == {"templates": []}

        path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
        library2 = _load_library()
        assert library2 == {"templates": []}


class TestExtractTemplateFallback:
    @pytest.mark.asyncio
    async def test_unknown_template_type_is_rejected(
        self, mcp_server, mock_adapter, mock_config, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        tools = await _tools(mcp_server, object(), mock_config)
        source = tmp_path / "base.sldprt"
        source.write_bytes(b"solid part")

        result = await tools["extract_template"](
            input_data=TemplateExtractionInput(
                source_model=str(source),
                template_name="T1",
                template_type="bogus",
                save_path=str(tmp_path / "out.xyz"),
            )
        )
        assert result["status"] == "error"
        assert "Unknown template_type" in result["message"]

    @pytest.mark.asyncio
    async def test_successful_extraction_to_directory_save_path(
        self, mcp_server, mock_adapter, mock_config, tmp_path, monkeypatch
    ):
        """save_path with no suffix (a directory) gets the template name + extension
        appended."""
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        tools = await _tools(mcp_server, object(), mock_config)
        source = tmp_path / "base.sldprt"
        source.write_bytes(b"solid part bytes")
        save_dir = tmp_path / "templates_out"

        result = await tools["extract_template"](
            input_data=TemplateExtractionInput(
                source_model=str(source),
                template_name="MyExtracted",
                template_type="part",
                save_path=str(save_dir),
            )
        )
        assert result["status"] == "success"
        destination = save_dir / "MyExtracted.prtdot"
        assert destination.exists()
        assert destination.read_bytes() == b"solid part bytes"
        assert result["template"]["file_location"] == str(destination)

    @pytest.mark.asyncio
    async def test_successful_extraction_corrects_wrong_suffix(
        self, mcp_server, mock_adapter, mock_config, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        tools = await _tools(mcp_server, object(), mock_config)
        source = tmp_path / "base.sldasm"
        source.write_bytes(b"assembly bytes")
        save_path = tmp_path / "out.wrong"

        result = await tools["extract_template"](
            input_data=TemplateExtractionInput(
                source_model=str(source),
                template_name="AsmTemplate",
                template_type="assembly",
                save_path=str(save_path),
            )
        )
        assert result["status"] == "success"
        corrected = save_path.with_suffix(".asmdot")
        assert corrected.exists()
        assert result["template"]["file_location"] == str(corrected)


class TestExtractTemplateNotWrittenAndSaveToLibrary:
    @pytest.mark.asyncio
    async def test_destination_not_written_is_reported(
        self, mcp_server, mock_adapter, mock_config, tmp_path, monkeypatch
    ):
        import shutil

        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        tools = await _tools(mcp_server, object(), mock_config)
        source = tmp_path / "base.sldprt"
        source.write_bytes(b"data")

        monkeypatch.setattr(shutil, "copyfile", lambda *a, **k: None)

        result = await tools["extract_template"](
            input_data=TemplateExtractionInput(
                source_model=str(source),
                template_name="T1",
                template_type="part",
                save_path=str(tmp_path / "out.prtdot"),
            )
        )
        assert result["status"] == "error"
        assert "was not written" in result["message"]

    @pytest.mark.asyncio
    async def test_save_to_template_library_requires_template_path(
        self, mcp_server, mock_adapter, mock_config, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        tools = await _tools(mcp_server, object(), mock_config)
        result = await tools["save_to_template_library"](
            input_data={"template_path": ""}
        )
        assert result["status"] == "error"
        assert "template_path is required" in result["message"]


class TestCompareTemplatesRealFiles:
    @pytest.mark.asyncio
    async def test_both_paths_required(
        self, mcp_server, mock_adapter, mock_config, monkeypatch, tmp_path
    ):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        tools = await _tools(mcp_server, object(), mock_config)
        result = await tools["compare_templates"](
            input_data=TemplateComparisonInput(
                template1_path="", template2_path="b.prtdot"
            )
        )
        assert result["status"] == "error"
        assert "requires two template paths" in result["message"]

    @pytest.mark.asyncio
    async def test_real_files_identical(
        self, mcp_server, mock_adapter, mock_config, monkeypatch, tmp_path
    ):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        tools = await _tools(mcp_server, object(), mock_config)
        t1 = tmp_path / "a.prtdot"
        t2 = tmp_path / "b.prtdot"
        t1.write_bytes(b"same bytes")
        t2.write_bytes(b"same bytes")

        result = await tools["compare_templates"](
            input_data=TemplateComparisonInput(
                template1_path=str(t1), template2_path=str(t2)
            )
        )
        assert result["status"] == "success"
        assert result["comparison"]["identical"] is True
        assert "byte-identical" in result["message"]

    @pytest.mark.asyncio
    async def test_real_files_differ(
        self, mcp_server, mock_adapter, mock_config, monkeypatch, tmp_path
    ):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        tools = await _tools(mcp_server, object(), mock_config)
        t1 = tmp_path / "a.prtdot"
        t2 = tmp_path / "b.prtdot"
        t1.write_bytes(b"content one")
        t2.write_bytes(b"different content")

        result = await tools["compare_templates"](
            input_data=TemplateComparisonInput(
                template1_path=str(t1), template2_path=str(t2)
            )
        )
        assert result["status"] == "success"
        assert result["comparison"]["identical"] is False
        assert "differ" in result["message"]
