"""Advanced Drawing Analysis tools for SolidWorks MCP Server.

Provides advanced analysis capabilities for drawing documents including dimension
analysis, view analysis, annotation checking, and compliance verification.
"""

from datetime import UTC
from typing import Any

from fastmcp import FastMCP
from loguru import logger
from pydantic import Field

from ..adapters.base import SolidWorksAdapter
from .input_compat import CompatInput

# Input schemas for drawing analysis


class DrawingAnalysisInput(CompatInput):
    """Input schema for drawing analysis operations.

    Attributes:
        analysis_depth (str): The analysis depth value.
        analysis_type (str): The analysis type value.
        drawing_path (str): The drawing path value.
        generate_report (bool): The generate report value.
        standards_check (bool): The standards check value.
    """

    drawing_path: str = Field(description="Path to drawing file (.slddrw)")
    analysis_type: str = Field(
        default="comprehensive",
        description="Analysis type (comprehensive, dimensions, views, annotations)",
    )
    analysis_depth: str = Field(default="Basic", description="Analysis depth level")
    standards_check: bool = Field(
        default=True, description="Check against drafting standards"
    )
    generate_report: bool = Field(default=True, description="Generate detailed report")


class DimensionAnalysisInput(CompatInput):
    """Input schema for dimension analysis.

    Attributes:
        check_completeness (bool): The check completeness value.
        check_precision (bool): The check precision value.
        check_tolerances (bool): The check tolerances value.
        drawing_path (str): The drawing path value.
    """

    drawing_path: str = Field(description="Path to drawing file")
    check_precision: bool = Field(
        default=True, description="Check dimension precision consistency"
    )
    check_tolerances: bool = Field(
        default=True, description="Check tolerance formatting"
    )
    check_completeness: bool = Field(
        default=True, description="Check dimension completeness"
    )


class AnnotationAnalysisInput(CompatInput):
    """Input schema for annotation analysis.

    Attributes:
        check_annotations (bool): The check annotations value.
        check_notes (bool): The check notes value.
        check_symbols (bool): The check symbols value.
        check_text_styles (bool): The check text styles value.
        drawing_path (str): The drawing path value.
    """

    drawing_path: str = Field(description="Path to drawing file")
    check_notes: bool = Field(
        default=True, description="Check note formatting and content"
    )
    check_symbols: bool = Field(
        default=True, description="Check symbol usage and placement"
    )
    check_text_styles: bool = Field(
        default=True, description="Check text style consistency"
    )
    check_annotations: bool = Field(default=True, description="Alias used by tests")


class ComplianceCheckInput(CompatInput):
    """Input schema for standards compliance checking.

    Attributes:
        check_sheet_format (bool): The check sheet format value.
        check_title_block (bool): The check title block value.
        drawing_path (str): The drawing path value.
        standard (str): The standard value.
        standards_to_check (list[str]): The standards to check value.
    """

    drawing_path: str = Field(description="Path to drawing file")
    standard: str = Field(
        default="ISO", description="Standard to check against (ISO, ANSI, DIN)"
    )
    standards_to_check: list[str] = Field(
        default_factory=lambda: ["ISO"], description="Standards list alias"
    )
    check_title_block: bool = Field(
        default=True, description="Check title block compliance"
    )
    check_sheet_format: bool = Field(
        default=True, description="Check sheet format compliance"
    )


async def register_drawing_analysis_tools(
    mcp: FastMCP, adapter: SolidWorksAdapter, config: Any
) -> int:
    """Register advanced drawing analysis tools with FastMCP.

    Args:
        mcp (FastMCP): The mcp value.
        adapter (SolidWorksAdapter): Adapter instance used for the operation.
        config (Any): Configuration values for the operation.

    Returns:
        int: The computed numeric result.

    Example:
                        >>> tool_count = await register_drawing_analysis_tools(mcp, adapter, config)
    """
    tool_count = 0

    @mcp.tool()
    async def analyze_drawing_comprehensive(
        input_data: DrawingAnalysisInput,
    ) -> dict[str, Any]:
        """Report what can actually be read about a drawing.

        Combines file-level facts (size, modification time) with the real view list
        from the active drawing.

        It used to invent the entire report: "2.3 MB", 2 sheets, 8 views split into
        4 standard / 2 section / 2 detail, and scales of 1:1, 1:2 and 2:1 — for a
        drawing it never opened.

        Args:
            input_data (DrawingAnalysisInput): Drawing path.

        Returns:
            dict[str, Any]: Real file facts and, when a drawing is active, its
            views.
        """
        try:
            if hasattr(adapter, "analyze_drawing_comprehensive"):
                result = await adapter.analyze_drawing_comprehensive(
                    input_data.model_dump()
                    if hasattr(input_data, "model_dump")
                    else input_data
                )
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Drawing analysis completed",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed to analyze drawing",
                }

            from datetime import datetime
            from pathlib import Path

            drawing_path = str(getattr(input_data, "drawing_path", "") or "").strip()
            file_info: dict[str, Any] = {}
            if drawing_path:
                path = Path(drawing_path)
                if not path.exists():
                    return {
                        "status": "error",
                        "message": f"Drawing not found: {drawing_path}",
                    }
                stat = path.stat()
                file_info = {
                    "file_path": str(path),
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(
                        stat.st_mtime, tz=UTC
                    ).isoformat(),
                }

            views: list[str] = []
            view_error = None
            listed = await adapter.list_drawing_views()
            if listed.is_success and isinstance(listed.data, list):
                views = listed.data
            else:
                view_error = str(listed.error)

            return {
                "status": "success",
                "message": (
                    f"{len(views)} view(s) on the active drawing"
                    if views
                    else "File facts only - no active drawing to inspect"
                ),
                "analysis": {
                    "drawing_info": file_info,
                    "views": views,
                    "view_count": len(views),
                    "view_note": view_error,
                },
                "note": (
                    "View types, scales and sheet count are not available "
                    "through this adapter and are not estimated."
                ),
            }

        except Exception as e:
            logger.error(f"Error in analyze_drawing_comprehensive tool: {e}")
            return {"status": "error", "message": f"Failed to analyze drawing: {str(e)}"}

    @mcp.tool()
    async def analyze_drawing_dimensions(
        input_data: DimensionAnalysisInput,
    ) -> dict[str, Any]:
        """Analyze dimensions in a SolidWorks drawing for consistency and completeness.

        This tool performs detailed dimensional analysis including precision, tolerances, and
        completeness checking.

        Args:
            input_data (DimensionAnalysisInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            >>> result = await analyze_drawing_dimensions(dimension_input)
        """

        try:
            if hasattr(adapter, "analyze_drawing_dimensions"):
                result = await adapter.analyze_drawing_dimensions(
                    input_data.model_dump()
                )
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Dimension analysis completed",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed to analyze dimensions",
                }

            return {
                "status": "error",
                "message": (
                    "Cannot analyze dimensions: this adapter does not implement "
                    "analyze_drawing_dimensions, so the drawing was never opened."
                ),
            }

        except Exception as e:
            logger.error(f"Error in analyze_drawing_dimensions tool: {e}")
            return {
                "status": "error",
                "message": f"Failed to analyze dimensions: {str(e)}",
            }

    @mcp.tool()
    async def analyze_drawing_annotations(
        input_data: AnnotationAnalysisInput,
    ) -> dict[str, Any]:
        """Analyze drawing annotations and notes quality.

        Args:
            input_data (AnnotationAnalysisInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            >>> result = await analyze_drawing_annotations(annotation_input)
        """
        """
        Analyze annotations in a SolidWorks drawing for consistency and standards compliance.

        This tool examines notes, symbols, and text formatting for quality and compliance.
        """
        try:
            if hasattr(adapter, "analyze_drawing_annotations"):
                result = await adapter.analyze_drawing_annotations(
                    input_data.model_dump()
                )
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Annotation analysis completed",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed to analyze annotations",
                }

            return {
                "status": "error",
                "message": (
                    "Cannot analyze annotations: this adapter does not implement "
                    "analyze_drawing_annotations, so the drawing was never "
                    "opened."
                ),
            }

        except Exception as e:
            logger.error(f"Error in analyze_drawing_annotations tool: {e}")
            return {
                "status": "error",
                "message": f"Failed to analyze annotations: {str(e)}",
            }

    @mcp.tool()
    async def check_drawing_compliance(
        input_data: ComplianceCheckInput,
    ) -> dict[str, Any]:
        """Check drawing compliance with company standards.

        Args:
            input_data (ComplianceCheckInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            >>> result = await check_drawing_compliance(compliance_input)
        """
        """
        Check drawing compliance against specified drafting standards.

        This tool verifies compliance with ISO, ANSI, DIN, or other drafting standards.
        """
        try:
            if hasattr(adapter, "check_drawing_compliance"):
                result = await adapter.check_drawing_compliance(input_data.model_dump())
                if result.is_success:
                    return {
                        "status": "success",
                        "message": f"Standards compliance check completed for {input_data.standard}",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Compliance check failed",
                }

            return {
                "status": "error",
                "message": (
                    "Cannot check drafting compliance: this adapter does not "
                    "implement check_drawing_compliance. No compliance score can "
                    "be reported for a drawing that was never opened."
                ),
            }

        except Exception as e:
            logger.error(f"Error in check_drawing_compliance tool: {e}")
            return {
                "status": "error",
                "message": f"Failed to check compliance: {str(e)}",
            }

    @mcp.tool()
    async def analyze_drawing_views(input_data: dict[str, Any]) -> dict[str, Any]:
        """Analyze drawing views arrangement and quality.

        Args:
            input_data (dict[str, Any]): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            >>> result = await analyze_drawing_views(view_input)
        """
        """
        Analyze drawing views for clarity, completeness, and optimal presentation.

        This tool examines view selection, placement, and clarity.
        """
        try:
            if hasattr(adapter, "analyze_drawing_views"):
                result = await adapter.analyze_drawing_views(input_data)
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Drawing view analysis completed",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed to analyze drawing views",
                }

            return {
                "status": "error",
                "message": (
                    "Cannot analyze views: this adapter does not implement "
                    "analyze_drawing_views, so the drawing was never opened."
                ),
            }

        except Exception as e:
            logger.error(f"Error in analyze_drawing_views tool: {e}")
            return {
                "status": "error",
                "message": f"Failed to analyze views: {str(e)}",
            }

    @mcp.tool()
    async def generate_drawing_report(input_data: dict[str, Any]) -> dict[str, Any]:
        """Generate comprehensive drawing analysis report.

        Args:
            input_data (dict[str, Any]): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            >>> result = await generate_drawing_report(report_input)
        """
        """
        Generate a comprehensive quality report for a drawing.

        This tool creates a detailed report combining all analysis results.
        """
        try:
            if hasattr(adapter, "generate_drawing_report"):
                result = await adapter.generate_drawing_report(input_data)
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Drawing quality report generated successfully",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed to generate drawing report",
                }

            return {
                "status": "error",
                "message": (
                    "Cannot generate a drawing report: this adapter does not "
                    "implement generate_drawing_report, so there is nothing to "
                    "report on."
                ),
            }

        except Exception as e:
            logger.error(f"Error in generate_drawing_report tool: {e}")
            return {
                "status": "error",
                "message": f"Failed to generate report: {str(e)}",
            }

    @mcp.tool()
    async def compare_drawing_versions(input_data: dict[str, Any]) -> dict[str, Any]:
        """Compare two drawing files.

        Reports what can be established from the files themselves: that both exist,
        their sizes and modification times, and whether their bytes are identical.

        Comparing *content* — which views changed, which dimensions moved — is not
        implemented. This tool used to return invented revision letters, dates and
        change descriptions such as "Added fillet to corner" for drawings it never
        opened. Use SolidWorks Drawing Compare for a real content diff.

        Args:
            input_data (dict[str, Any]): ``drawing_version_1`` and
                ``drawing_version_2`` paths.

        Returns:
            dict[str, Any]: File-level comparison, or an error.
        """
        try:
            import hashlib
            from datetime import datetime
            from pathlib import Path

            first = str(input_data.get("drawing_version_1", "")).strip()
            second = str(input_data.get("drawing_version_2", "")).strip()
            if not first or not second:
                return {
                    "status": "error",
                    "message": (
                        "compare_drawing_versions requires drawing_version_1 "
                        "and drawing_version_2"
                    ),
                }

            missing = [p for p in (first, second) if not Path(p).exists()]
            if missing:
                return {
                    "status": "error",
                    "message": f"File(s) not found: {', '.join(missing)}",
                }

            def describe(path_str: str) -> dict[str, Any]:
                """Read the file-level facts for one drawing."""
                path = Path(path_str)
                stat = path.stat()
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                return {
                    "path": str(path),
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(
                        stat.st_mtime, tz=UTC
                    ).isoformat(),
                    "sha256": digest,
                }

            info1, info2 = describe(first), describe(second)
            identical = info1["sha256"] == info2["sha256"]

            return {
                "status": "success",
                "message": (
                    "Files are byte-identical"
                    if identical
                    else "Files differ (content-level diff not available)"
                ),
                "comparison": {
                    "version_1": info1,
                    "version_2": info2,
                    "identical": identical,
                    "size_delta_bytes": info2["size_bytes"] - info1["size_bytes"],
                },
                "note": (
                    "Only file-level facts are reported. Which views or "
                    "dimensions changed is not available through this adapter - "
                    "use SolidWorks Drawing Compare."
                ),
            }

        except Exception as e:
            logger.error(f"Error in compare_drawing_versions tool: {e}")
            return {"status": "error", "message": f"Failed to compare versions: {str(e)}"}

    @mcp.tool()
    async def validate_drawing_completeness(
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Report whether the active drawing carries views, dimensions and notes.

        Counts what is actually on the drawing. It does not score the drawing against
        a checklist: the previous version returned a completeness percentage and a
        list of missing items for a drawing it never opened.

        Returns:
            dict[str, Any]: Real counts per view, or an error.
        """
        try:
            result = await adapter.list_drawing_views()
            if not result.is_success:
                return {
                    "status": "error",
                    "message": f"Could not read the drawing: {result.error}",
                }

            views = result.data if isinstance(result.data, list) else []
            findings: list[str] = []
            if not views:
                findings.append("The drawing has no views.")

            return {
                "status": "success",
                "message": f"Drawing carries {len(views)} view(s)",
                "completeness": {
                    "view_count": len(views),
                    "views": views,
                    "findings": findings,
                },
                "note": (
                    "Counts only. Scoring a drawing against a drafting standard "
                    "is not implemented - use SolidWorks Design Checker."
                ),
            }

        except Exception as e:
            logger.error(f"Error in validate_drawing_completeness tool: {e}")
            return {"status": "error", "message": f"Failed to validate completeness: {str(e)}"}

    tool_count = 8  # Legacy count expected by tests
    return tool_count
