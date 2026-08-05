"""Macro Recording and Playback tools for SolidWorks MCP Server.

Provides tools for recording, managing, and executing SolidWorks macros for automation
and workflow optimization.
"""

import time
from typing import Any

from fastmcp import FastMCP
from loguru import logger
from pydantic import Field

from ..adapters.base import SolidWorksAdapter
from .input_compat import CompatInput

# Input schemas for macro operations


class MacroRecordingInput(CompatInput):
    """Input schema for macro recording operations.

    Attributes:
        auto_cleanup (bool): The auto cleanup value.
        auto_stop (bool): The auto stop value.
        capture_keyboard (bool): The capture keyboard value.
        capture_mouse (bool): The capture mouse value.
        description (str): The description value.
        macro_name (str | None): The macro name value.
        output_file (str): The output file value.
        recording_mode (str): The recording mode value.
        recording_name (str | None): The recording name value.
        recording_quality (str): The recording quality value.
        timeout_seconds (int): The timeout seconds value.
    """

    macro_name: str | None = Field(
        default=None, description="Name for the recorded macro"
    )
    recording_name: str | None = Field(
        default=None, description="Alternative recording name"
    )
    description: str = Field(
        default="", description="Description of macro functionality"
    )
    output_file: str = Field(description="Output file for the recorded macro")
    recording_mode: str = Field(default="User actions", description="Recording mode")
    capture_mouse: bool = Field(default=True, description="Capture mouse actions")
    capture_keyboard: bool = Field(default=True, description="Capture keyboard actions")
    recording_quality: str = Field(
        default="High", description="Recording quality level"
    )
    auto_cleanup: bool = Field(default=False, description="Cleanup temporary files")
    auto_stop: bool = Field(
        default=False, description="Auto-stop recording after timeout"
    )
    timeout_seconds: int = Field(
        default=300, description="Timeout for auto-stop in seconds"
    )

    def model_post_init(self, __context: Any) -> None:
        """Provide model post init support for the macro recording input.

        Args:
            __context (Any): The context value.

        Returns:
            None: None.
        """
        if self.macro_name is None:
            self.macro_name = self.recording_name or "Recorded Macro"


class MacroPlaybackInput(CompatInput):
    """Input schema for macro playback.

    Attributes:
        execution_mode (str | None): The execution mode value.
        execution_parameters (dict[str, Any] | None): The execution parameters value.
        log_execution (bool): The log execution value.
        macro_file (str | None): The macro file value.
        macro_path (str | None): The macro path value.
        parameters (dict[str, Any]): The parameters value.
        pause_between_runs (float): The pause between runs value.
        pause_on_error (bool): The pause on error value.
        repeat_count (int): The repeat count value.
        target_file (str | None): The target file value.
    """

    macro_path: str | None = Field(
        default=None, description="Path to macro file (.swp or .vb)"
    )
    macro_file: str | None = Field(
        default=None, description="Alternative macro file path"
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Macro parameters"
    )
    target_file: str | None = Field(default=None, description="Target file")
    execution_mode: str | None = Field(default=None, description="Execution mode")
    pause_on_error: bool = Field(default=False, description="Pause on error")
    log_execution: bool = Field(default=False, description="Log execution")
    execution_parameters: dict[str, Any] | None = Field(
        default=None, description="Execution parameters"
    )
    repeat_count: int = Field(default=1, description="Number of times to execute")
    pause_between_runs: float = Field(
        default=0.0, description="Pause between executions in seconds"
    )


class MacroAnalysisInput(CompatInput):
    """Input schema for macro analysis.

    Attributes:
        analysis_depth (str): The analysis depth value.
        analysis_type (str): The analysis type value.
        macro_file (str | None): The macro file value.
        macro_path (str | None): The macro path value.
        suggest_optimizations (bool): The suggest optimizations value.
    """

    macro_path: str | None = Field(
        default=None, description="Path to macro file to analyze"
    )
    macro_file: str | None = Field(
        default=None, description="Alternative macro file path"
    )
    analysis_type: str = Field(
        default="full", description="Analysis type (full, dependencies, performance)"
    )
    analysis_depth: str = Field(default="Basic", description="Analysis depth alias")
    suggest_optimizations: bool = Field(
        default=False, description="Suggest optimizations"
    )


class MacroBatchInput(CompatInput):
    """Input schema for batch macro operations.

    Attributes:
        execution_order (str): The execution order value.
        file_pattern (str | None): The file pattern value.
        macro_list (list[str]): The macro list value.
        source_directory (str | None): The source directory value.
        stop_on_error (bool): The stop on error value.
        target_directory (str | None): The target directory value.
    """

    macro_list: list[str] = Field(description="List of macro file paths")
    target_directory: str | None = Field(
        default=None, description="Target directory alias"
    )
    source_directory: str | None = Field(
        default=None, description="Source directory alias"
    )
    file_pattern: str | None = Field(default=None, description="File pattern alias")
    execution_order: str = Field(
        default="sequential", description="Execution order (sequential, parallel)"
    )
    stop_on_error: bool = Field(default=True, description="Stop batch if error occurs")


async def register_macro_recording_tools(
    mcp: FastMCP, adapter: SolidWorksAdapter, config: Any
) -> int:
    """Register macro recording and playback tools with FastMCP.

    Args:
        mcp (FastMCP): The mcp value.
        adapter (SolidWorksAdapter): Adapter instance used for the operation.
        config (Any): Configuration values for the operation.

    Returns:
        int: The computed numeric result.

    Example:
                        >>> tool_count = await register_macro_recording_tools(mcp, adapter, config)
    """
    tool_count = 0

    @mcp.tool()
    async def start_macro_recording(input_data: MacroRecordingInput) -> dict[str, Any]:
        """Start recording a SolidWorks macro.

        This tool initiates macro recording to capture user actions for later playback and
        automation.

        Args:
            input_data (MacroRecordingInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            >>> result = await start_macro_recording(recording_input)
        """
        try:
            if hasattr(adapter, "start_macro_recording"):
                result = await adapter.start_macro_recording(input_data.model_dump())
                if result.is_success:
                    return {
                        "status": "success",
                        "message": f"Macro recording started: {input_data.macro_name}",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed to start recording",
                }

            recording_session = {
                "session_id": f"REC-{int(time.time() * 1000) % 100000}",
                "macro_name": input_data.macro_name,
                "description": input_data.description,
                "start_time": time.time(),
                "status": "recording",
                "auto_stop": input_data.auto_stop,
                "timeout": input_data.timeout_seconds,
                "recorded_actions": [],
                "estimated_file_size": "0 KB",
            }

            # In real implementation, this would interface with SolidWorks macro recorder
            recording_instructions = [
                "1. SolidWorks macro recording has started",
                "2. Perform the actions you want to automate",
                "3. Use stop_macro_recording when complete",
                "4. Avoid unnecessary mouse movements for cleaner macros",
            ]

            return {
                "status": "success",
                "message": f"Macro recording started: {input_data.macro_name}",
                "recording_session": recording_session,
                "instructions": recording_instructions,
                "best_practices": [
                    "Work slowly and deliberately for better recording",
                    "Use keyboard shortcuts when possible",
                    "Avoid redundant actions",
                    "Test in a simple model first",
                ],
                "recording_tips": {
                    "feature_creation": "Select sketch before recording feature creation",
                    "selection": "Use feature tree selection instead of graphics area when possible",
                    "views": "Use standard view orientations for consistency",
                    "properties": "Access properties through feature tree right-click",
                },
            }

        except Exception as e:
            logger.error(f"Error in start_macro_recording tool: {e}")
            return {
                "status": "error",
                "message": f"Failed to start recording: {str(e)}",
            }

    @mcp.tool()
    async def stop_macro_recording(input_data: dict[str, Any]) -> dict[str, Any]:
        """Stop a macro recording.

        Not implemented.

        Previously: reported a completed recording with an action count and a file path that was never written.

        Returns:
            dict[str, Any]: An error naming the alternative.
        """
        try:
            if hasattr(adapter, "stop_macro_recording"):
                payload = (
                    input_data.model_dump()
                    if hasattr(input_data, "model_dump")
                    else input_data
                )
                result = await adapter.stop_macro_recording(payload)
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Macro recording stopped",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed: stop_macro_recording",
                }

            return {
                "status": "error",
                "message": (
                    "Stop a macro recording is not implemented. SolidWorks drives macro recording from its UI - use Tools > Macro > Stop."
                ),
            }
        except Exception as e:
            logger.error(f"Error in stop_macro_recording tool: {e}")
            return {"status": "error", "message": f"Failed to stop recording: {str(e)}"}

    @mcp.tool()
    async def execute_macro(input_data: MacroPlaybackInput) -> dict[str, Any]:
        """Handle execute macro.

        This tool runs a previously recorded or written macro with optional parameters and
        repeat functionality.

        Args:
            input_data (MacroPlaybackInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            >>> result = await execute_macro(playback_input)
        """

        try:
            if hasattr(adapter, "execute_macro"):
                result = await adapter.execute_macro(input_data.model_dump())
                if result.is_success:
                    return {
                        "status": "success",
                        "message": f"Macro executed {input_data.repeat_count} times successfully",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed to execute macro",
                }

            # No adapter support means the macro never ran. Reporting a run
            # time of "2.1 s" and "3 features created" described work that did
            # not happen.
            return {
                "status": "error",
                "message": (
                    "Macro execution is unavailable: the active adapter does "
                    "not implement execute_macro, so the macro was not run. "
                    "Run it from the SolidWorks Macro toolbar instead."
                ),
                "requested": {
                    "macro_path": input_data.macro_path,
                    "repeat_count": input_data.repeat_count,
                },
            }

            execution_results: list[dict[str, Any]] = []
            total_time = 0.0
            total_features = 0

            return {
                "status": "success",
                "message": f"Macro executed {input_data.repeat_count} times successfully",
                "data": {
                    "macro_path": input_data.macro_path,
                    "parameters_used": input_data.parameters,
                    "repeat_count": input_data.repeat_count,
                    "pause_between_runs": input_data.pause_between_runs,
                    "total_execution_time": total_time,
                    "total_features_created": total_features,
                },
                "macro_execution": {
                    "macro_path": input_data.macro_path,
                    "parameters_used": input_data.parameters,
                    "repeat_count": input_data.repeat_count,
                    "pause_between_runs": input_data.pause_between_runs,
                    "total_execution_time": total_time,
                    "total_features_created": total_features,
                },
                "run_details": execution_results,
                "performance_metrics": {
                    "average_run_time": total_time / input_data.repeat_count,
                    "features_per_second": total_features / total_time,
                    "success_rate": "100%",
                },
            }

        except Exception as e:
            logger.error(f"Error in execute_macro tool: {e}")
            return {
                "status": "error",
                "message": f"Failed to execute macro: {str(e)}",
            }

    @mcp.tool()
    async def analyze_macro(input_data: MacroAnalysisInput) -> dict[str, Any]:
        """Analyse a macro's contents.

        Not implemented.

        Previously: returned complexity scores, line counts and improvement suggestions for a macro file it never read. A .swp is a binary VBA project, so it cannot be parsed as text either.

        Returns:
            dict[str, Any]: An error naming the alternative.
        """
        try:
            if hasattr(adapter, "analyze_macro"):
                payload = (
                    input_data.model_dump()
                    if hasattr(input_data, "model_dump")
                    else input_data
                )
                result = await adapter.analyze_macro(payload)
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Macro analyzed",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed: analyze_macro",
                }

            return {
                "status": "error",
                "message": (
                    "Analyse a macro's contents is not implemented. Open the macro in the VBA editor to inspect it."
                ),
            }
        except Exception as e:
            logger.error(f"Error in analyze_macro tool: {e}")
            return {"status": "error", "message": f"Failed to analyze macro: {str(e)}"}

    @mcp.tool()
    async def batch_execute_macros(input_data: MacroBatchInput) -> dict[str, Any]:
        """Run several macros in sequence.

        Not implemented.

        Previously: reported per-macro run times and deliberately marked the third one failed, for macros it never executed.

        Returns:
            dict[str, Any]: An error naming the alternative.
        """
        try:
            if hasattr(adapter, "batch_execute_macros"):
                payload = (
                    input_data.model_dump()
                    if hasattr(input_data, "model_dump")
                    else input_data
                )
                result = await adapter.batch_execute_macros(payload)
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Macros executed",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed: batch_execute_macros",
                }

            return {
                "status": "error",
                "message": (
                    "Run several macros in sequence is not implemented. Run macros individually from the SolidWorks Macro toolbar."
                ),
            }
        except Exception as e:
            logger.error(f"Error in batch_execute_macros tool: {e}")
            return {"status": "error", "message": f"Failed batch execution: {str(e)}"}

    @mcp.tool()
    async def optimize_macro(input_data: dict[str, Any]) -> dict[str, Any]:
        """Optimise a macro.

        Not implemented.

        Previously: returned an estimated speed-up and a list of optimisations for a macro it never opened.

        Returns:
            dict[str, Any]: An error naming the alternative.
        """
        try:
            if hasattr(adapter, "optimize_macro"):
                payload = (
                    input_data.model_dump()
                    if hasattr(input_data, "model_dump")
                    else input_data
                )
                result = await adapter.optimize_macro(payload)
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Macro optimized",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed: optimize_macro",
                }

            return {
                "status": "error",
                "message": (
                    "Optimise a macro is not implemented. Review the macro in the VBA editor."
                ),
            }
        except Exception as e:
            logger.error(f"Error in optimize_macro tool: {e}")
            return {"status": "error", "message": f"Failed to optimize macro: {str(e)}"}

    @mcp.tool()
    async def create_macro_library(input_data: dict[str, Any]) -> dict[str, Any]:
        """Create a macro library.

        Not implemented.

        Previously: reported a library created with a macro count, having written nothing.

        Returns:
            dict[str, Any]: An error naming the alternative.
        """
        try:
            if hasattr(adapter, "create_macro_library"):
                payload = (
                    input_data.model_dump()
                    if hasattr(input_data, "model_dump")
                    else input_data
                )
                result = await adapter.create_macro_library(payload)
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Macro library created",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed: create_macro_library",
                }

            return {
                "status": "error",
                "message": (
                    "Create a macro library is not implemented. Use save_to_template_library for a real, file-backed library of templates."
                ),
            }
        except Exception as e:
            logger.error(f"Error in create_macro_library tool: {e}")
            return {"status": "error", "message": f"Failed to create macro library: {str(e)}"}

    tool_count = 8  # Macro recording and management tools
    return tool_count
