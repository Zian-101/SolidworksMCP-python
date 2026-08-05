"""Template Management tools for SolidWorks MCP Server.

Provides tools for managing SolidWorks templates including extraction, application,
comparison, and library management.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from loguru import logger
from pydantic import BaseModel, Field

from ..adapters.base import SolidWorksAdapter
from .input_compat import CompatInput, normalize_input

# Input schemas for template management


class TemplateExtractionInput(BaseModel):
    """Input schema for extracting template from model.

    Attributes:
        include_custom_properties (bool): The include custom properties value.
        include_dimensions (bool): The include dimensions value.
        save_path (str): The save path value.
        source_model (str): The source model value.
        template_name (str): The template name value.
        template_type (str): The template type value.
    """

    source_model: str = Field(description="Path to source model file")
    template_name: str = Field(description="Name for the extracted template")
    template_type: str = Field(description="Template type (part, assembly, drawing)")
    save_path: str = Field(description="Path to save the template file")
    include_custom_properties: bool = Field(
        default=True, description="Include custom properties"
    )
    include_dimensions: bool = Field(default=True, description="Include dimensions")


class TemplateApplicationInput(BaseModel):
    """Input schema for applying template to model.

    Attributes:
        apply_dimensions (bool): The apply dimensions value.
        apply_materials (bool): The apply materials value.
        overwrite_existing (bool): The overwrite existing value.
        target_model (str): The target model value.
        template_path (str): The template path value.
    """

    template_path: str = Field(description="Path to template file")
    target_model: str = Field(description="Path to target model")
    overwrite_existing: bool = Field(
        default=False, description="Overwrite existing properties"
    )
    apply_dimensions: bool = Field(
        default=True, description="Apply dimension formatting"
    )
    apply_materials: bool = Field(default=True, description="Apply material settings")


class TemplateBatchInput(BaseModel):
    """Input schema for batch template operations.

    Attributes:
        backup_originals (bool): The backup originals value.
        file_pattern (str): The file pattern value.
        recursive (bool): The recursive value.
        source_folder (str): The source folder value.
        template_path (str): The template path value.
    """

    template_path: str = Field(description="Path to template file")
    source_folder: str = Field(description="Folder containing target models")
    file_pattern: str = Field(default="*.sldprt", description="File pattern to match")
    recursive: bool = Field(default=True, description="Process subfolders")
    backup_originals: bool = Field(default=True, description="Create backup copies")


class TemplateComparisonInput(CompatInput):
    """Input schema for comparing templates.

    Attributes:
        comparison_depth (str): The comparison depth value.
        comparison_type (str): The comparison type value.
        generate_report (bool): The generate report value.
        include_dimensions (bool): The include dimensions value.
        include_materials (bool): The include materials value.
        include_properties (bool): The include properties value.
        template1_path (str): The template1 path value.
        template2_path (str): The template2 path value.
    """

    template1_path: str = Field(description="Path to first template")
    template2_path: str = Field(description="Path to second template")
    comparison_type: str = Field(
        default="full", description="Comparison type (full, properties, dimensions)"
    )
    comparison_depth: str = Field(default="full", description="Comparison depth alias")
    include_properties: bool = Field(default=True, description="Include properties")
    include_dimensions: bool = Field(default=True, description="Include dimensions")
    include_materials: bool = Field(default=True, description="Include materials")
    generate_report: bool = Field(
        default=True, description="Generate comparison report"
    )


def _library_path() -> Path:
    """Return the on-disk path of the template library index.

    Returns:
        Path: ``template_library.json`` under the per-user app data directory.
    """
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    directory = Path(base) / "solidworks_mcp"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "template_library.json"


def _load_library() -> dict[str, Any]:
    """Read the template library, tolerating a missing or corrupt file.

    Returns:
        dict[str, Any]: ``{"templates": [...]}``.
    """
    path = _library_path()
    if not path.exists():
        return {"templates": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"templates": []}
    if not isinstance(data, dict) or not isinstance(data.get("templates"), list):
        return {"templates": []}
    return data


def _save_library(library: dict[str, Any]) -> None:
    """Write the template library index.

    Args:
        library (dict[str, Any]): The library to persist.
    """
    _library_path().write_text(
        json.dumps(library, indent=2, ensure_ascii=False), encoding="utf-8"
    )


async def register_template_management_tools(
    mcp: FastMCP, adapter: SolidWorksAdapter, config
) -> int:
    """Register template management tools with FastMCP.

    Args:
        mcp (FastMCP): The mcp value.
        adapter (SolidWorksAdapter): Adapter instance used for the operation.
        config (Any): Configuration values for the operation.

    Returns:
        int: The computed numeric result.

    Example:
                        >>> tool_count = await register_template_management_tools(mcp, adapter, config)
    """
    tool_count = 0

    @mcp.tool()
    async def extract_template(input_data: TemplateExtractionInput) -> dict[str, Any]:
        """Write a document template from an existing model.

        Copies the source model to ``save_path`` with the matching template
        extension (``.prtdot`` / ``.asmdot`` / ``.drwdot``) and confirms the file
        landed. That is what extracting a template amounts to in practice: the
        model's document settings, custom properties and drafting standards travel
        with the file.

        It used to report a successful extraction while inventing the contents —
        units "mm-kg-s", font "Century Gothic", and custom properties including
        ``Material: Steel`` and ``RevisionLevel: A`` — for a model it never opened.

        Args:
            input_data (TemplateExtractionInput): Source model, name and save path.

        Returns:
            dict[str, Any]: The template file actually written.
        """
        try:
            input_data = normalize_input(input_data, TemplateExtractionInput)
            import shutil

            if hasattr(adapter, "extract_template"):
                result = await adapter.extract_template(input_data.model_dump())
                if result.is_success:
                    return {
                        "status": "success",
                        "message": (
                            f"Template '{input_data.template_name}' extracted "
                            f"from {input_data.source_model}"
                        ),
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed to extract template",
                }

            source = Path(str(input_data.source_model))
            if not source.exists():
                return {
                    "status": "error",
                    "message": f"Source model not found: {input_data.source_model}",
                }

            extensions = {
                "part": ".prtdot",
                "assembly": ".asmdot",
                "drawing": ".drwdot",
            }
            template_type = str(input_data.template_type or "part").strip().lower()
            if template_type not in extensions:
                return {
                    "status": "error",
                    "message": (
                        f"Unknown template_type '{input_data.template_type}'. "
                        f"Use one of: {', '.join(sorted(extensions))}."
                    ),
                }

            destination = Path(str(input_data.save_path))
            if destination.is_dir() or not destination.suffix:
                destination = destination / (
                    str(input_data.template_name) + extensions[template_type]
                )
            elif destination.suffix.lower() != extensions[template_type]:
                destination = destination.with_suffix(extensions[template_type])

            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)

            if not destination.exists():
                return {
                    "status": "error",
                    "message": f"Template was not written to {destination}",
                }

            return {
                "status": "success",
                "message": (
                    f"Template '{input_data.template_name}' written to "
                    f"{destination.name}"
                ),
                "template": {
                    "name": input_data.template_name,
                    "type": template_type,
                    "source_model": str(source),
                    "file_location": str(destination),
                    "size_bytes": destination.stat().st_size,
                },
                "note": (
                    "The template carries whatever document settings and custom "
                    "properties the source model had. They are not enumerated "
                    "here - open the template to inspect them."
                ),
            }

        except Exception as e:
            logger.error(f"Error in extract_template tool: {e}")
            return {
                "status": "error",
                "message": f"Failed to extract template: {str(e)}",
            }

    @mcp.tool()
    async def apply_template(input_data: TemplateApplicationInput) -> dict[str, Any]:
        """Apply a template to a model.

        Not implemented.

        Previously: reported properties, materials and features applied to a model it never opened.

        Returns:
            dict[str, Any]: An error naming the alternative.
        """
        try:
            input_data = normalize_input(input_data, TemplateApplicationInput)
            return {
                "status": "error",
                "message": (
                    "Apply a template to a model is not implemented. Create documents from the template instead - create_part and create_assembly use the configured SolidWorks templates."
                ),
            }
        except Exception as e:
            logger.error(f"Error in apply_template tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def batch_apply_template(input_data: TemplateBatchInput) -> dict[str, Any]:
        """Apply a template across many files.

        Not implemented.

        Previously: reported a per-file success count for files it never opened.

        Returns:
            dict[str, Any]: An error naming the alternative.
        """
        try:
            input_data = normalize_input(input_data, TemplateBatchInput)
            return {
                "status": "error",
                "message": (
                    "Apply a template across many files is not implemented. Create documents from the template instead, or use batch_process_files for a real per-file operation."
                ),
            }
        except Exception as e:
            logger.error(f"Error in batch_apply_template tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def compare_templates(input_data: TemplateComparisonInput) -> dict[str, Any]:
        """Compare two template files.

        Reports file-level facts only: existence, size, modification time and whether
        the bytes are identical.

        This tool used to invent a similarity percentage and a list of differences —
        fonts, units, custom properties — for templates it never opened. Those
        numbers were not derived from the files at all.

        Args:
            input_data (CompareTemplatesInput): The two template paths.

        Returns:
            dict[str, Any]: File-level comparison, or an error.
        """
        try:
            input_data = normalize_input(input_data, TemplateComparisonInput)
            import hashlib
            from datetime import datetime, timezone
            from pathlib import Path

            first = str(getattr(input_data, "template1_path", "") or "").strip()
            second = str(getattr(input_data, "template2_path", "") or "").strip()
            if not first or not second:
                return {
                    "status": "error",
                    "message": "compare_templates requires two template paths",
                }

            missing = [p for p in (first, second) if not Path(p).exists()]
            if missing:
                return {
                    "status": "error",
                    "message": f"Template(s) not found: {', '.join(missing)}",
                }

            def describe(path_str: str) -> dict[str, Any]:
                """Read the file-level facts for one template."""
                path = Path(path_str)
                stat = path.stat()
                return {
                    "path": str(path),
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }

            info1, info2 = describe(first), describe(second)
            identical = info1["sha256"] == info2["sha256"]

            return {
                "status": "success",
                "message": (
                    "Templates are byte-identical"
                    if identical
                    else "Templates differ (content-level diff not available)"
                ),
                "comparison": {
                    "template1": info1,
                    "template2": info2,
                    "identical": identical,
                },
                "note": (
                    "Only file-level facts are reported. Comparing units, fonts "
                    "or custom properties is not implemented."
                ),
            }

        except Exception as e:
            logger.error(f"Error in compare_templates tool: {e}")
            return {
                "status": "error",
                "message": f"Failed to compare templates: {str(e)}",
            }

    @mcp.tool()
    async def save_to_template_library(input_data: dict[str, Any]) -> dict[str, Any]:
        """Record a template in the local template library.

        The library is a JSON file on disk (``template_library.json`` under the
        per-user application data directory), so entries persist across sessions and
        can be listed back. It used to return a fabricated ``total_templates: 47``
        alongside category counts for a library that did not exist.

        Args:
            input_data (dict[str, Any]): ``template_path`` plus optional
                ``template_name``, ``category``, ``version``, ``description``,
                ``author`` and ``tags``.

        Returns:
            dict[str, Any]: The stored entry and the library's real statistics.
        """
        try:
            if hasattr(adapter, "save_to_template_library"):
                result = await adapter.save_to_template_library(input_data)
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Template saved to library",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed to save to library",
                }

            template_path = str(input_data.get("template_path", "")).strip()
            if not template_path:
                return {"status": "error", "message": "template_path is required"}
            if not Path(template_path).exists():
                return {
                    "status": "error",
                    "message": f"Template file not found: {template_path}",
                }

            category = str(input_data.get("category", "uncategorized"))
            library = _load_library()
            entry = {
                "template_id": (
                    f"TPL-{category.upper()}-{len(library['templates']) + 1:04d}"
                ),
                "name": input_data.get(
                    "template_name", Path(template_path).stem
                ),
                "category": category,
                "version": str(input_data.get("version", "1.0")),
                "author": str(input_data.get("author", "")),
                "description": str(input_data.get("description", "")),
                "created": datetime.now(timezone.utc).isoformat(),
                "file_path": str(Path(template_path).resolve()),
                "size_bytes": Path(template_path).stat().st_size,
                "tags": list(input_data.get("tags", []) or []),
            }

            # Replace an existing entry for the same file rather than duplicating.
            library["templates"] = [
                t
                for t in library["templates"]
                if t.get("file_path") != entry["file_path"]
            ]
            library["templates"].append(entry)
            _save_library(library)

            categories: dict[str, int] = {}
            for template in library["templates"]:
                key = str(template.get("category", "uncategorized"))
                categories[key] = categories.get(key, 0) + 1

            return {
                "status": "success",
                "message": f"Saved to library as {entry['template_id']}",
                "library_entry": entry,
                "library_stats": {
                    "total_templates": len(library["templates"]),
                    "category_count": categories,
                    "library_file": str(_library_path()),
                },
            }

        except Exception as e:
            logger.error(f"Error in save_to_template_library tool: {e}")
            return {
                "status": "error",
                "message": f"Failed to save to library: {str(e)}",
            }

    @mcp.tool()
    async def list_template_library(input_data: dict[str, Any]) -> dict[str, Any]:
        """List the templates recorded in the local template library.

        Reads the JSON library written by ``save_to_template_library``. Entries whose
        file has since been deleted are flagged rather than silently listed as
        available. The previous version returned a fixed catalogue of templates that
        were never registered by anyone.

        Args:
            input_data (dict[str, Any] | None): Optional ``category`` filter.

        Returns:
            dict[str, Any]: The stored entries and real statistics.
        """
        try:
            if hasattr(adapter, "list_template_library"):
                result = await adapter.list_template_library(input_data or {})
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Template library listed",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed to list library",
                }

            payload = input_data or {}
            wanted = str(payload.get("category", "") or "").strip().lower()

            library = _load_library()
            templates = library["templates"]
            if wanted:
                templates = [
                    t
                    for t in templates
                    if str(t.get("category", "")).lower() == wanted
                ]

            for template in templates:
                template["file_exists"] = Path(
                    str(template.get("file_path", ""))
                ).exists()

            categories: dict[str, int] = {}
            for template in library["templates"]:
                key = str(template.get("category", "uncategorized"))
                categories[key] = categories.get(key, 0) + 1

            missing = [t["name"] for t in templates if not t["file_exists"]]
            return {
                "status": "success",
                "message": (
                    f"{len(templates)} template(s) in the library"
                    + (f"; {len(missing)} missing on disk" if missing else "")
                ),
                "templates": templates,
                "library_stats": {
                    "total_templates": len(library["templates"]),
                    "category_count": categories,
                    "library_file": str(_library_path()),
                },
            }

        except Exception as e:
            logger.error(f"Error in list_template_library tool: {e}")
            return {
                "status": "error",
                "message": f"Failed to list template library: {str(e)}",
            }

    tool_count = 6  # Template management tools
    return tool_count
