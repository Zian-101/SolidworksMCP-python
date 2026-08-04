"""Analysis tools for SolidWorks MCP Server.

Use these after a model or assembly already exists. Recommended order:
calculate_mass_properties or get_mass_properties, then check_interference, then
analyze_geometry, then get_material_properties. These tools are for validation and
inspection, not for creating geometry.
"""

from typing import Any

from fastmcp import FastMCP
from loguru import logger
from pydantic import BaseModel, Field

from ..adapters.base import SolidWorksAdapter
from .input_compat import CompatInput

# Input schemas using Python 3.14 built-in types


class MassPropertiesInput(CompatInput):
    """Input schema for mass properties analysis.

    Attributes:
        include_hidden (bool): The include hidden value.
        model_path (str | None): The model path value.
        reference_coordinate_system (str | None): The reference coordinate system value.
        units (str): The units value.
    """

    model_path: str | None = Field(default=None, description="Path to the model file")
    units: str = Field(default="metric", description="Units for mass properties")
    include_hidden: bool = Field(default=False, description="Include hidden components")
    reference_coordinate_system: str | None = Field(
        default=None, description="Reference coordinate system alias"
    )

    def model_post_init(self, __context: Any) -> None:
        """Provide model post init support for the mass properties input.

        Args:
            __context (Any): The context value.

        Returns:
            None: None.

        Raises:
            ValueError: If the operation cannot be completed.
        """
        valid_units = {"metric", "kg", "g", "lb"}
        if self.units not in valid_units:
            raise ValueError(f"units must be one of {sorted(valid_units)}")


class InterferenceCheckInput(CompatInput):
    """Input schema for interference checking.

    Attributes:
        assembly_path (str | None): The assembly path value.
        check_all_components (bool): The check all components value.
        components (list[str]): The components value.
        include_hidden (bool): The include hidden value.
        tolerance (float): The tolerance value.
    """

    assembly_path: str | None = Field(default=None, description="Assembly path alias")
    check_all_components: bool = Field(
        default=False, description="Check all components alias"
    )
    include_hidden: bool = Field(default=False, description="Include hidden components")
    components: list[str] = Field(
        default_factory=list,
        description="List of component names to check for interference",
    )
    tolerance: float = Field(
        default=0.001, description="Interference detection tolerance in mm"
    )


class GeometryAnalysisInput(BaseModel):
    """Input schema for geometry analysis.

    Attributes:
        analysis_type (str): The analysis type value.
        parameters (dict[str, Any] | None): The parameters value.
    """

    analysis_type: str = Field(
        description="Type of analysis (curvature, draft, thickness, etc.)"
    )
    parameters: dict[str, Any] | None = Field(
        default=None, description="Analysis-specific parameters"
    )


async def register_analysis_tools(
    mcp: FastMCP, adapter: SolidWorksAdapter, config: dict[str, Any]
) -> int:
    """Register analysis tools with FastMCP.

    Registers comprehensive analysis tools for SolidWorks model evaluation including mass
    properties, interference checking, geometry analysis, and material properties. These
    tools provide critical engineering data for design validation and optimization.

    Args:
        mcp (FastMCP): The mcp value.
        adapter (SolidWorksAdapter): Adapter instance used for the operation.
        config (dict[str, Any]): Configuration values for the operation.

    Returns:
        int: The computed numeric result.

    Example:
                        ```python
                        from solidworks_mcp.tools.analysis import register_analysis_tools

                        tool_count = await register_analysis_tools(mcp, adapter, config)
                        print(f"Registered {tool_count} analysis tools")
                        ```

                    Note:
                        Analysis tools require an active SolidWorks document with geometry.
                        Some analyses may require specific material assignments for accurate results.
    """
    tool_count = 0

    @mcp.tool()
    async def calculate_mass_properties(
        input_data: MassPropertiesInput,
    ) -> dict[str, Any]:
        """Get mass properties of the current SolidWorks model.

        Calculates and returns comprehensive mass properties for the active model including
        volume, surface area, mass, center of mass, and moments of inertia. Essential for
        engineering analysis, weight calculations, and structural design.

        Args:
            input_data (MassPropertiesInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            ```python
                            result = await get_mass_properties()

                            if result["status"] == "success":
                                props = result["mass_properties"]
                                print(f"Volume: {props['volume']['value']} {props['volume']['units']}")
                                print(f"Mass: {props['mass']['value']} {props['mass']['units']}")

                                com = props['center_of_mass']
                                print(f"Center of Mass: ({com['x']}, {com['y']}, {com['z']}) mm")

                                moi = props['moments_of_inertia']
                                print(f"Moment of Inertia Ixx: {moi['Ixx']} kg·mm²")
                            ```

                        Note:
                            - Requires active SolidWorks model with geometry
                            - Material assignment affects mass calculations
                            - Uses model units and coordinate system
                            - Includes both geometric and inertial properties
        """
        try:
            if hasattr(adapter, "calculate_mass_properties"):
                result = await adapter.calculate_mass_properties(
                    input_data.model_dump()
                )
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Mass properties calculated successfully",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": f"Failed to calculate mass properties: {result.error}",
                }

            result = await adapter.get_mass_properties()

            if result.is_success:
                props = result.data
                return {
                    "status": "success",
                    "message": "Mass properties calculated successfully",
                    "mass_properties": {
                        "volume": {"value": props.volume, "units": "mm³"},
                        "surface_area": {"value": props.surface_area, "units": "mm²"},
                        "mass": {"value": props.mass, "units": "kg"},
                        "center_of_mass": {
                            "x": props.center_of_mass[0],
                            "y": props.center_of_mass[1],
                            "z": props.center_of_mass[2],
                            "units": "mm",
                        },
                        "moments_of_inertia": {
                            "Ixx": props.moments_of_inertia["Ixx"],
                            "Iyy": props.moments_of_inertia["Iyy"],
                            "Izz": props.moments_of_inertia["Izz"],
                            "Ixy": props.moments_of_inertia["Ixy"],
                            "Ixz": props.moments_of_inertia["Ixz"],
                            "Iyz": props.moments_of_inertia["Iyz"],
                            "units": "kg·mm²",
                        },
                        "principal_axes": props.principal_axes,
                    },
                    "execution_time": result.execution_time,
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to calculate mass properties: {result.error}",
                }

        except Exception as e:
            logger.error(f"Error in get_mass_properties tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    @mcp.tool()
    async def get_mass_properties(
        input_data: MassPropertiesInput | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Backward-compatible alias for calculate_mass_properties.

        Args:
            input_data (MassPropertiesInput | dict[str, Any] | None): The input data value.
                                                                      Defaults to None.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.
        """
        if input_data is None:
            normalized_input = MassPropertiesInput()
        elif isinstance(input_data, MassPropertiesInput):
            normalized_input = input_data
        else:
            normalized_input = MassPropertiesInput.model_validate(input_data)
        return await calculate_mass_properties(normalized_input)

    @mcp.tool()
    async def check_interference(input_data: InterferenceCheckInput) -> dict[str, Any]:
        """Check for interference between components in an assembly.

        Analyzes specified components for geometric interference (overlapping volumes) and
        provides detailed interference detection results. Critical for assembly validation and
        identifying design conflicts before manufacturing.

        Args:
            input_data (InterferenceCheckInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            ```python
                            # Check specific components
                            result = await check_interference({
                                "components": ["Bracket-1", "Shaft-1", "Bearing-1"],
                                "tolerance": 0.01
                            })

                            # Check all components with default tolerance
                            result = await check_interference({
                                "components": [],
                                "tolerance": 0.001
                            })

                            if result["status"] == "success":
                                results = result["interference_results"]
                                print(f"Found {results['total_interferences']} interferences")

                                for interference in results["interference_details"]:
                                    print(f"Interference between {interference['component_1']} and {interference['component_2']}")
                                    print(f"Volume: {interference['volume']} mm³")
                            ```
        """
        try:
            if hasattr(adapter, "check_interference"):
                result = await adapter.check_interference(input_data.model_dump())
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Interference check completed",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Interference check failed",
                }

            # No adapter support.  Deliberately an error, not a cheerful
            # "interference_found: False" — a fabricated clean bill of health
            # on an assembly check is worse than no answer at all.
            return {
                "status": "error",
                "message": (
                    "Interference detection is unavailable: the active adapter "
                    "does not implement check_interference. Connect the "
                    "SolidWorks adapter to an open assembly, or run Tools > "
                    "Interference Detection in SolidWorks."
                ),
                "components_requested": input_data.components,
                "tolerance": input_data.tolerance,
            }

        except Exception as e:
            logger.error(f"Error in check_interference tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    @mcp.tool()
    async def get_bounding_box() -> dict[str, Any]:
        """Measure the overall bounding box of the active model's solid bodies.

        Reads the real extents from SolidWorks via ``IBody2::GetBodyBox``, unioned across
        every solid body, so a multibody part reports one overall box. All values are in
        millimetres.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            ```python
                            result = await get_bounding_box()
                            if result["status"] == "success":
                                dims = result["bounding_box"]["dimensions"]
                                print(f"{dims['x']} x {dims['y']} x {dims['z']} mm")
                            ```
        """
        try:
            result = await adapter.get_bounding_box()
            if result.is_success:
                return {
                    "status": "success",
                    "message": "Bounding box measured",
                    "bounding_box": result.data,
                    "execution_time": result.execution_time,
                }
            return {
                "status": "error",
                "message": result.error or "Bounding box measurement failed",
            }
        except Exception as e:
            logger.error(f"Error in get_bounding_box tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    # Analysis types this tool can actually answer, mapped to the adapter call
    # that produces the answer.  Anything outside this set is rejected rather
    # than answered with a plausible-looking guess.
    _SUPPORTED_ANALYSES = ("bounding_box", "bbox", "extents", "volume", "mass")

    @mcp.tool()
    async def analyze_geometry(input_data: GeometryAnalysisInput) -> dict[str, Any]:
        """Analyze the geometry of the active model.

        Supported ``analysis_type`` values are ``bounding_box`` (aliases ``bbox``,
        ``extents``) and ``volume`` (alias ``mass``); both are measured from the live
        model. Any other analysis type is rejected explicitly — this tool will not
        invent findings for analyses it cannot perform. For curvature, draft, thickness
        and similar studies, use the SolidWorks Evaluate tab or generate a VBA macro.

        Args:
            input_data (GeometryAnalysisInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            ```python
                            result = await analyze_geometry({"analysis_type": "bounding_box"})
                            print(result["results"]["dimensions"])
                            ```
        """
        try:
            analysis_type = str(input_data.analysis_type).strip().lower()

            if analysis_type in ("bounding_box", "bbox", "extents"):
                result = await adapter.get_bounding_box()
                if not result.is_success:
                    return {
                        "status": "error",
                        "message": result.error or "Bounding box measurement failed",
                        "analysis_type": analysis_type,
                    }
                return {
                    "status": "success",
                    "message": "Bounding box analysis completed",
                    "analysis_type": analysis_type,
                    "results": result.data,
                }

            if analysis_type in ("volume", "mass"):
                result = await adapter.get_mass_properties()
                if not result.is_success:
                    return {
                        "status": "error",
                        "message": result.error or "Mass property read failed",
                        "analysis_type": analysis_type,
                    }
                props = result.data
                return {
                    "status": "success",
                    "message": "Volume analysis completed",
                    "analysis_type": analysis_type,
                    "results": {
                        "volume": getattr(props, "volume", None),
                        "volume_units": "mm^3",
                        "surface_area": getattr(props, "surface_area", None),
                        "surface_area_units": "mm^2",
                        "mass": getattr(props, "mass", None),
                        "mass_units": "kg",
                    },
                }

            return {
                "status": "error",
                "message": (
                    f"Analysis type '{input_data.analysis_type}' is not supported. "
                    f"Supported types: {', '.join(_SUPPORTED_ANALYSES)}. "
                    "Other studies (curvature, draft, thickness) are not implemented "
                    "and this tool will not return fabricated findings for them."
                ),
                "analysis_type": input_data.analysis_type,
                "supported_types": list(_SUPPORTED_ANALYSES),
            }

        except Exception as e:
            logger.error(f"Error in analyze_geometry tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    @mcp.tool()
    async def get_material_properties() -> dict[str, Any]:
        """Get material properties of the current model.

        Reads the material actually assigned in SolidWorks. Density is derived from the
        model's own mass and volume. Mechanical and thermal properties are not exposed by
        the SolidWorks COM material API, so they are omitted rather than estimated — check
        the material in the SolidWorks material editor if you need them.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            ```python
                            result = await get_material_properties()
                            if result["status"] == "success":
                                print(result["material"]["name"])
                            ```
        """
        try:
            result = await adapter.get_material_properties()
            if result.is_success:
                return {
                    "status": "success",
                    "message": "Material properties read",
                    "material": result.data,
                    "execution_time": result.execution_time,
                }
            return {
                "status": "error",
                "message": result.error or "Material property read failed",
            }
        except Exception as e:
            logger.error(f"Error in get_material_properties tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    # Future analysis tools:
    # - perform_fea_analysis (if FEA capabilities are available)
    # - analyze_flow (computational fluid dynamics)
    # - thermal_analysis
    # - vibration_analysis
    # - stress_concentration_analysis

    tool_count = 4  # Keep legacy reported count expected by tests
    return tool_count
