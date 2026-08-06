"""Automation tools for SolidWorks MCP Server.

Use these when the workflow is already defined and you need repeatable execution.
Recommended order: generate_vba_code for complex steps, record or stop a macro when a
manual flow should be captured, batch_process_files for many files, manage_design_table
for configuration-driven variants, execute_workflow for scripted pipelines,
create_template for reusable standards, and optimize_performance for tuning.
"""

from typing import Any

from fastmcp import FastMCP
from loguru import logger
from pydantic import Field

from ..adapters.base import SolidWorksAdapter
from .input_compat import (
    CompatInput,
)
from .input_compat import (
    normalize_input as _normalize_input,
)

# Input schemas using Python 3.14 built-in types


class GenerateVBAInput(CompatInput):
    """Input schema for generating VBA code.

    Attributes:
        code_style (str): The code style value.
        include_error_handling (bool): The include error handling value.
        operation_description (str | None): The operation description value.
        operation_type (str | None): The operation type value.
        parameters (dict[str, Any]): The parameters value.
        target_document (str): The target document value.
    """

    operation_description: str | None = Field(
        default=None, description="Description of the operation to generate VBA for"
    )
    operation_type: str | None = Field(default=None, description="Operation type alias")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Operation parameters"
    )
    target_document: str = Field(
        default="Part", description="Target document type (Part, Assembly, Drawing)"
    )
    include_error_handling: bool = Field(
        default=True, description="Include error handling in generated code"
    )
    code_style: str = Field(
        default="professional",
        description="Code style (simple, professional, advanced)",
    )

    def model_post_init(self, __context: Any) -> None:
        """Provide model post init support for the generate vbainput.

        Args:
            __context (Any): The context value.

        Returns:
            None: None.
        """
        if self.operation_description is None:
            self.operation_description = self.operation_type or "SolidWorks Operation"


VBAGenerationInput = GenerateVBAInput


class RecordMacroInput(CompatInput):
    """Input schema for macro recording.

    Attributes:
        auto_start (bool): The auto start value.
        capture_keyboard (bool): The capture keyboard value.
        capture_mouse (bool): The capture mouse value.
        description (str): The description value.
        macro_name (str | None): The macro name value.
        output_file (str | None): The output file value.
        recording_mode (str | None): The recording mode value.
        recording_name (str | None): The recording name value.
    """

    macro_name: str | None = Field(
        default=None, description="Name for the recorded macro"
    )
    recording_name: str | None = Field(default=None, description="Recording name alias")
    output_file: str | None = Field(default=None, description="Output file alias")
    recording_mode: str | None = Field(default=None, description="Recording mode alias")
    capture_mouse: bool = Field(default=True, description="Capture mouse actions")
    capture_keyboard: bool = Field(default=True, description="Capture keyboard actions")
    description: str = Field(
        default="", description="Description of the macro functionality"
    )
    auto_start: bool = Field(default=True, description="Automatically start recording")

    def model_post_init(self, __context: Any) -> None:
        """Provide model post init support for the record macro input.

        Args:
            __context (Any): The context value.

        Returns:
            None: None.
        """
        if self.macro_name is None:
            self.macro_name = self.recording_name or "Recorded Macro"


class BatchProcessInput(CompatInput):
    """Input schema for batch processing.

    Attributes:
        batch_operation (str | None): The batch operation value.
        file_pattern (str | None): The file pattern value.
        filter_patterns (list[str]): The filter patterns value.
        operation (str | None): The operation value.
        operation_type (str | None): The operation type value.
        parallel_processing (bool): The parallel processing value.
        recursive (bool): The recursive value.
        source_directory (str): The source directory value.
        target_format (str | None): The target format value.
    """

    source_directory: str = Field(description="Directory containing SolidWorks files")
    operation_type: str | None = Field(
        default=None,
        description="Type of operation (rebuild, save_as, export, update_properties)",
    )
    batch_operation: str | None = Field(
        default=None, description="Batch operation alias"
    )
    target_format: str | None = Field(
        default=None, description="Target format for export operations"
    )
    file_pattern: str | None = Field(default=None, description="File pattern alias")
    parallel_processing: bool = Field(
        default=False, description="Parallel processing alias"
    )
    operation: str | None = Field(default=None, description="Operation alias")
    recursive: bool = Field(
        default=False, description="Process subdirectories recursively"
    )
    filter_patterns: list[str] = Field(
        default=["*.sldprt", "*.sldasm"], description="File patterns to process"
    )

    def model_post_init(self, __context: Any) -> None:
        """Provide model post init support for the batch process input.

        Args:
            __context (Any): The context value.

        Returns:
            None: None.
        """
        if self.operation_type is None:
            self.operation_type = self.batch_operation or self.operation or "export"


class DesignTableInput(CompatInput):
    """Input schema for design table operations.

    Attributes:
        auto_create_configurations (bool): The auto create configurations value.
        auto_update (bool): The auto update value.
        configurations (list[str]): The configurations value.
        create_configurations (bool): The create configurations value.
        excel_file (str | None): The excel file value.
        model_path (str | None): The model path value.
        operation (str | None): The operation value.
        parameters (list[str]): The parameters value.
        table_file (str | None): The table file value.
        table_type (str | None): The table type value.
    """

    table_type: str | None = Field(
        default=None, description="Type of design table (create, update, import)"
    )
    model_path: str | None = Field(default=None, description="Model path alias")
    table_file: str | None = Field(default=None, description="Design table file alias")
    operation: str | None = Field(default=None, description="Operation alias")
    auto_update: bool = Field(default=False, description="Auto update alias")
    create_configurations: bool = Field(
        default=False, description="Create configurations alias"
    )
    auto_create_configurations: bool = Field(
        default=False, description="Auto-create alias"
    )
    excel_file: str | None = Field(
        default=None, description="Excel file path for import/export"
    )
    parameters: list[str] = Field(
        default=[], description="Parameters to include in design table"
    )
    configurations: list[str] = Field(default=[], description="Configuration names")

    def model_post_init(self, __context: Any) -> None:
        """Provide model post init support for the design table input.

        Args:
            __context (Any): The context value.

        Returns:
            None: None.
        """
        if self.table_type is None:
            self.table_type = self.operation or "create"
        if self.create_configurations:
            self.auto_create_configurations = True


class WorkflowInput(CompatInput):
    """Input schema for workflow automation.

    Attributes:
        error_handling (str): The error handling value.
        parallel_execution (bool): The parallel execution value.
        steps (list[dict[str, Any]]): The steps value.
        workflow_name (str): The workflow name value.
    """

    workflow_name: str = Field(description="Name of the workflow")
    steps: list[dict[str, Any]] = Field(description="List of workflow steps")
    parallel_execution: bool = Field(
        default=False, description="Execute compatible steps in parallel"
    )
    error_handling: str = Field(
        default="stop", description="Error handling strategy (stop, skip, retry)"
    )


class TemplateInput(CompatInput):
    """Input schema for template operations.

    Attributes:
        base_file (str | None): The base file value.
        include_custom_properties (bool): The include custom properties value.
        include_features (list[str]): The include features value.
        include_materials (bool): The include materials value.
        metadata (dict[str, Any]): The metadata value.
        output_path (str | None): The output path value.
        source_model (str | None): The source model value.
        template_name (str): The template name value.
        template_type (str): The template type value.
    """

    template_type: str = Field(description="Type of template (part, assembly, drawing)")
    template_name: str = Field(description="Name for the template")
    base_file: str | None = Field(
        default=None, description="Base file to create template from"
    )
    source_model: str | None = Field(default=None, description="Source model alias")
    output_path: str | None = Field(default=None, description="Output path alias")
    include_custom_properties: bool = Field(
        default=False, description="Include custom properties alias"
    )
    include_materials: bool = Field(
        default=False, description="Include materials alias"
    )
    include_features: list[str] = Field(
        default_factory=list, description="Include features alias"
    )
    metadata: dict[str, Any] = Field(
        default={}, description="Template metadata and properties"
    )


async def register_automation_tools(
    mcp: FastMCP, adapter: SolidWorksAdapter, config: dict[str, Any]
) -> int:
    """Register automation tools with FastMCP.

    Registers comprehensive automation tools for SolidWorks workflow orchestration including
    VBA generation, macro recording, batch processing, and template management.

    Args:
        mcp (FastMCP): The mcp value.
        adapter (SolidWorksAdapter): Adapter instance used for the operation.
        config (dict[str, Any]): Configuration values for the operation.

    Returns:
        int: The computed numeric result.
    """
    tool_count = 0

    @mcp.tool()
    async def generate_vba_code(input_data: GenerateVBAInput) -> dict[str, Any]:
        """Generate VBA code for SolidWorks automation.

        Analyzes operation description and generates appropriate VBA code with SolidWorks API
        calls, error handling, and documentation.

        Args:
            input_data (GenerateVBAInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            ```python
                            result = await generate_vba_code({
                                "operation_description": "Create rectangular extrusion",
                                "target_document": "Part",
                                "include_error_handling": True
                            })
                            ```
        """
        try:
            input_data = _normalize_input(input_data, GenerateVBAInput)
            if hasattr(adapter, "generate_vba_code"):
                result = await adapter.generate_vba_code(input_data.model_dump())
                if result.is_success:
                    return {
                        "status": "success",
                        "message": f"Generated VBA code for: {input_data.operation_description}",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed to generate VBA code",
                }

            # A skeleton, not a working macro: connection boilerplate,
            # optional error handling, and a TODO where the operation goes.
            # The response says so rather than implying it is runnable.
            sample_vba = f"""
' Generated VBA code for: {input_data.operation_description}
' Target: {input_data.target_document}
' Generated by: SolidWorks MCP Server

Option Explicit

Sub {input_data.operation_description.replace(" ", "_")}()
    Dim swApp As SldWorks.SldWorks
    Dim swModel As SldWorks.ModelDoc2

    {("On Error GoTo ErrorHandler" if input_data.include_error_handling else "")}

    ' Connect to SolidWorks
    Set swApp = Application.SldWorks
    Set swModel = swApp.ActiveDoc

    If swModel Is Nothing Then
        MsgBox "No active document found"
        Exit Sub
    End If

    ' Main operation code would go here
    ' TODO: Implement specific operation

    MsgBox "Operation completed successfully"
    Exit Sub

{("ErrorHandler:" if input_data.include_error_handling else "")}
{('    MsgBox "Error: " & Err.Description' if input_data.include_error_handling else "")}
{("    Resume Next" if input_data.include_error_handling else "")}

End Sub
"""

            return {
                "status": "success",
                "message": f"Generated VBA code for: {input_data.operation_description}",
                "vba_code": {
                    "code": sample_vba.strip(),
                    "operation": input_data.operation_description,
                    "target_document": input_data.target_document,
                    "style": input_data.code_style,
                    "lines_of_code": len(sample_vba.strip().split("\n")),
                    "includes_error_handling": input_data.include_error_handling,
                },
            }

        except Exception as e:
            logger.error(f"Error in generate_vba_code tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    @mcp.tool(name="automation_start_macro_recording")
    async def start_macro_recording(input_data: RecordMacroInput) -> dict[str, Any]:
        """Start recording a macro in SolidWorks.

        Begins macro recording to capture user actions and generate reusable automation scripts.

        Args:
            input_data (RecordMacroInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.
        """
        try:
            if hasattr(adapter, "start_macro_recording"):
                result = await adapter.start_macro_recording(input_data.model_dump())
                if result.is_success:
                    return {
                        "status": "success",
                        "message": f"Started recording macro: {input_data.macro_name}",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed to start macro recording",
                }

            # Nothing was ever started: this reported "recording" with a
            # fixed 2024 timestamp while SolidWorks did nothing.
            return {
                "status": "error",
                "message": (
                    "Starting a macro recording is not supported through this "
                    "adapter - SolidWorks drives recording from its UI. Use "
                    "Tools > Macro > Record, or generate a macro with the "
                    "generate_vba_* tools."
                ),
                "requested": {
                    "macro_name": input_data.macro_name,
                    "description": input_data.description,
                },
            }

        except Exception as e:
            logger.error(f"Error in start_macro_recording tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    @mcp.tool(name="automation_stop_macro_recording")
    async def stop_macro_recording(input_data: dict[str, Any]) -> dict[str, Any]:
        """Stop recording the current macro.

        This tool stops the active macro recording and saves the recorded actions as a VBA
        macro.

        Args:
            input_data (dict[str, Any]): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.
        """
        # Nothing was ever recording. This used to report a 5-minute session
        # with 15 actions captured to a macro file that does not exist.
        return {
            "status": "error",
            "message": (
                "Stopping a macro recording is not supported through this "
                "adapter - SolidWorks drives recording from its UI. Use "
                "Tools > Macro > Stop."
            ),
        }

    @mcp.tool()
    async def batch_process_files(input_data: BatchProcessInput) -> dict[str, Any]:
        """Run one operation over every matching file in a directory.

        Really opens each file, performs the operation and closes it, then reports
        what actually happened — which files were found, which succeeded, and the
        real error for each failure.

        Supported ``operation_type`` values: ``export`` (needs ``target_format``)
        and ``open`` (open-and-close, useful as a bulk health check on a folder).
        Anything else is rejected rather than reported as done.

        This tool used to invent its whole answer: 25 files found, 23 processed,
        "12.5 minutes", and two named failures — ``corrupted_part.sldprt`` and
        ``locked_assembly.sldasm`` — for a directory it never read. Someone would
        go looking for those files.

        Args:
            input_data (BatchProcessInput): Directory, operation and filters.

        Returns:
            dict[str, Any]: Real per-file results.
        """
        try:
            if hasattr(adapter, "batch_process_files"):
                result = await adapter.batch_process_files(
                    input_data.model_dump()
                    if hasattr(input_data, "model_dump")
                    else input_data
                )
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Batch processing completed",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed batch processing",
                }

            input_data = _normalize_input(input_data, BatchProcessInput)
            import time as _time
            from pathlib import Path as _Path

            source = str(getattr(input_data, "source_directory", "") or "").strip()
            if not source:
                return {"status": "error", "message": "source_directory is required"}
            directory = _Path(source)
            if not directory.is_dir():
                return {
                    "status": "error",
                    "message": f"Not a directory: {source}",
                }

            operation = str(
                getattr(input_data, "operation_type", None)
                or getattr(input_data, "operation", None)
                or "open"
            ).strip().lower()
            supported = {"export", "open"}
            if operation not in supported:
                return {
                    "status": "error",
                    "message": (
                        f"Unsupported operation '{operation}'. "
                        f"Supported: {', '.join(sorted(supported))}."
                    ),
                }

            target_format = str(
                getattr(input_data, "target_format", "") or ""
            ).strip().lower()
            if operation == "export" and not target_format:
                return {
                    "status": "error",
                    "message": "export requires target_format (step, stl, iges, pdf)",
                }

            pattern = str(getattr(input_data, "file_pattern", "") or "").strip()
            recursive = bool(getattr(input_data, "recursive", False))
            globber = directory.rglob if recursive else directory.glob
            candidates = sorted(
                path
                for path in globber(pattern or "*")
                if path.suffix.lower() in (".sldprt", ".sldasm", ".slddrw")
                # SolidWorks writes "~$name.sldprt" lock files next to open
                # documents. They match the extension but are not documents.
                and not path.name.startswith("~$")
            )

            if not candidates:
                return {
                    "status": "error",
                    "message": (
                        f"No SolidWorks files found in {source}"
                        + (f" matching '{pattern}'" if pattern else "")
                    ),
                }

            started = _time.perf_counter()
            succeeded: list[str] = []
            failed: list[dict[str, str]] = []

            for path in candidates:
                opened = await adapter.open_model(str(path))
                if not opened.is_success:
                    failed.append({"file": path.name, "error": str(opened.error)})
                    continue
                try:
                    if operation == "export":
                        exported = await adapter.export_file(
                            str(path.with_suffix("." + target_format)),
                            target_format,
                        )
                        if not exported.is_success:
                            failed.append(
                                {"file": path.name, "error": str(exported.error)}
                            )
                            continue
                    succeeded.append(path.name)
                except Exception as exc:  # noqa: BLE001 - per-file isolation
                    failed.append({"file": path.name, "error": str(exc)})
                finally:
                    await adapter.close_model(False)

            elapsed = _time.perf_counter() - started
            return {
                "status": "success" if not failed else "partial",
                "message": (
                    f"{len(succeeded)}/{len(candidates)} file(s) {operation}ed"
                ),
                "batch_process": {
                    "source_directory": str(directory),
                    "operation": operation,
                    "target_format": target_format or None,
                    "files_found": len(candidates),
                    "files_successful": len(succeeded),
                    "files_failed": len(failed),
                    "processing_seconds": round(elapsed, 2),
                    "succeeded": succeeded,
                    "failed_files": failed,
                },
            }

        except Exception as e:
            logger.error(f"Error in batch_process_files tool: {e}")
            return {
                "status": "error",
                "message": f"Failed batch processing: {str(e)}",
            }

    @mcp.tool()
    async def manage_design_table(input_data: DesignTableInput) -> dict[str, Any]:
        """Create or edit a model's design table.

        Not implemented. Design tables are driven through an embedded Excel
        worksheet, which this adapter cannot reach.

        It previously echoed the requested parameters back inside a success
        payload, counting "configurations" it had not created.

        Args:
            input_data (DesignTableInput): The requested table operation.

        Returns:
            dict[str, Any]: An error naming the alternative.
        """
        try:
            if hasattr(adapter, "manage_design_table"):
                payload = (
                    input_data.model_dump()
                    if hasattr(input_data, "model_dump")
                    else input_data
                )
                result = await adapter.manage_design_table(payload)
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Design table updated",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed: manage_design_table",
                }

            input_data = _normalize_input(input_data, DesignTableInput)
            return {
                "status": "error",
                "message": (
                    "Design table management is not implemented: it needs the "
                    "embedded Excel worksheet, which this adapter cannot reach. "
                    "Edit the design table in SolidWorks, or drive configurations "
                    "with set_dimension."
                ),
                "requested": {
                    "operation": getattr(input_data, "table_type", None)
                    or getattr(input_data, "operation", None),
                    "model_path": getattr(input_data, "model_path", None),
                },
            }
        except Exception as e:
            logger.error(f"Error in manage_design_table tool: {e}")
            return {
                "status": "error",
                "message": f"Failed to manage design table: {str(e)}",
            }

    @mcp.tool()
    async def execute_workflow(input_data: WorkflowInput) -> dict[str, Any]:
        """Run a named sequence of steps.

        Not implemented. There is no step executor behind this tool, so it cannot
        run a workflow.

        It used to report per-step durations ("2.1s", "1.8s") and a plausible
        failure ("step 3 failed: File not found") for a workflow it never ran.

        Args:
            input_data (WorkflowInput): The workflow definition.

        Returns:
            dict[str, Any]: An error naming the alternative.
        """
        try:
            if hasattr(adapter, "execute_workflow"):
                payload = (
                    input_data.model_dump()
                    if hasattr(input_data, "model_dump")
                    else input_data
                )
                result = await adapter.execute_workflow(payload)
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Workflow completed",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed: execute_workflow",
                }

            input_data = _normalize_input(input_data, WorkflowInput)
            return {
                "status": "error",
                "message": (
                    "Workflow execution is not implemented - there is no step "
                    "executor behind this tool. Call the individual tools in "
                    "sequence instead."
                ),
                "requested": {
                    "workflow_name": getattr(input_data, "workflow_name", None),
                    "step_count": len(getattr(input_data, "steps", []) or []),
                },
            }
        except Exception as e:
            logger.error(f"Error in execute_workflow tool: {e}")
            return {
                "status": "error",
                "message": f"Failed to execute workflow: {str(e)}",
            }

    @mcp.tool()
    async def create_template(input_data: TemplateInput) -> dict[str, Any]:
        """Create a document template from an existing model file.

        Copies the base model to the template location with the matching template
        extension (``.prtdot`` / ``.asmdot`` / ``.drwdot``) and confirms the file
        was written.

        It previously reported a template created at a
        ``C:\\ProgramData\\SolidWorks\\templates\\...`` path that it never wrote,
        so the next call that tried to use that template would fail with a
        confusing "template not found".

        Args:
            input_data (TemplateInput): Template type, name and base file.

        Returns:
            dict[str, Any]: The template path actually written.
        """
        try:
            if hasattr(adapter, "create_template"):
                result = await adapter.create_template(
                    input_data.model_dump()
                    if hasattr(input_data, "model_dump")
                    else input_data
                )
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Template created",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed to create template",
                }

            input_data = _normalize_input(input_data, TemplateInput)
            import shutil
            from pathlib import Path as _Path

            base = str(
                getattr(input_data, "base_file", None)
                or getattr(input_data, "source_model", None)
                or ""
            ).strip()
            if not base:
                return {
                    "status": "error",
                    "message": (
                        "base_file is required: a template is created from an "
                        "existing model"
                    ),
                }
            base_path = _Path(base)
            if not base_path.exists():
                return {"status": "error", "message": f"Base file not found: {base}"}

            template_type = str(
                getattr(input_data, "template_type", "part") or "part"
            ).strip().lower()
            extensions = {
                "part": ".prtdot",
                "assembly": ".asmdot",
                "drawing": ".drwdot",
            }
            if template_type not in extensions:
                return {
                    "status": "error",
                    "message": (
                        f"Unknown template_type '{template_type}'. "
                        f"Use one of: {', '.join(sorted(extensions))}."
                    ),
                }

            name = str(
                getattr(input_data, "template_name", "") or base_path.stem
            ).strip()
            output = getattr(input_data, "output_path", None)
            destination = (
                _Path(str(output))
                if output
                else base_path.with_name(name).with_suffix(extensions[template_type])
            )
            if destination.suffix.lower() != extensions[template_type]:
                destination = destination.with_suffix(extensions[template_type])

            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(base_path, destination)

            if not destination.exists():
                return {
                    "status": "error",
                    "message": f"Template was not written to {destination}",
                }

            return {
                "status": "success",
                "message": f"Created {template_type} template: {destination.name}",
                "template": {
                    "type": template_type,
                    "name": name,
                    "base_file": str(base_path),
                    "file_location": str(destination),
                    "size_bytes": destination.stat().st_size,
                },
            }

        except Exception as e:
            logger.error(f"Error in create_template tool: {e}")
            return {
                "status": "error",
                "message": f"Failed to create template: {str(e)}",
            }

    @mcp.tool()
    async def optimize_performance(input_data: dict[str, Any]) -> dict[str, Any]:
        """Report SolidWorks performance-related settings.

        Not implemented as an optimiser. Changing performance preferences is not
        something this adapter should do silently on a user's installation, and
        the previous version did not do it anyway: it reported "45 settings
        analyzed, 12 optimized, estimated 25% performance gain" without reading
        or writing a single setting.

        Args:
            input_data (dict[str, Any]): Ignored.

        Returns:
            dict[str, Any]: An error naming where these settings live.
        """
        try:
            if hasattr(adapter, "optimize_performance"):
                payload = (
                    input_data.model_dump()
                    if hasattr(input_data, "model_dump")
                    else input_data
                )
                result = await adapter.optimize_performance(payload)
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Performance optimization completed",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed: optimize_performance",
                }

            return {
                "status": "error",
                "message": (
                    "Performance optimisation is not implemented. The previous "
                    "figures - settings analysed, percentage gain - were "
                    "fabricated and read no settings at all. Adjust these in "
                    "SolidWorks under Tools > Options > Performance."
                ),
            }
        except Exception as e:
            logger.error(f"Error in optimize_performance tool: {e}")
            return {
                "status": "error",
                "message": f"Failed to optimize performance: {str(e)}",
            }

    tool_count = 8  # Number of tools registered
    return tool_count


class PerformanceOptimizationInput(CompatInput):
    """Input schema for performance optimization.

    Attributes:
        optimization_type (str): The optimization type value.
        parameters (dict[str, Any]): The parameters value.
        target_metric (str): The target metric value.
    """

    optimization_type: str = Field(description="Type of optimization to perform")
    target_metric: str = Field(default="speed", description="Target performance metric")
    parameters: dict[str, Any] = Field(
        default={}, description="Optimization parameters"
    )
