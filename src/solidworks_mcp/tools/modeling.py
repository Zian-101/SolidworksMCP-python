"""Modeling tools for SolidWorks MCP Server.

Provides tools for creating and manipulating SolidWorks models, including parts,
assemblies, drawings, and features like extrusions, revolves, etc.
"""

from typing import Any, TypeVar

from fastmcp import FastMCP
from loguru import logger
from pydantic import BaseModel, Field

from ..adapters.base import (
    ExtrusionParameters,
    LoftParameters,
    RevolveParameters,
    SolidWorksAdapter,
    SweepParameters,
)
from .input_compat import CompatInput

TInput = TypeVar("TInput", bound=BaseModel)


# Input schemas using Python 3.14 built-in types


def _result_value(data: Any, *keys: str, default: Any = None) -> Any:
    """Build internal result value.

    Args:
        data (Any): The data value.
        *keys (str): Additional positional arguments forwarded to the call.
        default (Any): Fallback value returned when the operation fails. Defaults to None.

    Returns:
        Any: The result produced by the operation.
    """
    if isinstance(data, dict):
        for key in keys:
            if key in data and data[key] is not None:
                return data[key]
        return default

    for key in keys:
        if hasattr(data, key):
            value = getattr(data, key)
            if value is not None:
                return value
    return default


def _normalize_input(input_data: Any, model_type: type[TInput]) -> TInput:
    """Build internal normalize input.

    Args:
        input_data (Any): The input data value.
        model_type (type[TInput]): The model type value.

    Returns:
        TInput: The result produced by the operation.
    """
    if isinstance(input_data, model_type):
        return input_data
    return model_type.model_validate(input_data)


class OpenModelInput(BaseModel):
    """Input schema for opening a SolidWorks model.

    Attributes:
        file_path (str): The file path value.
    """

    file_path: str = Field(
        description="Full path to the SolidWorks file (.sldprt, .sldasm, .slddrw)"
    )


class CreatePartInput(CompatInput):
    """Input schema for creating a new SolidWorks part.

    Attributes:
        material (str | None): The material value.
        name (str): The name value.
        template (str | None): The template value.
        units (str | None): The units value.
    """

    name: str = Field(description="Name for the new part")
    template: str | None = Field(
        default=None, description="Template file path for the new part"
    )
    units: str | None = Field(default=None, description="Document units")
    material: str | None = Field(default=None, description="Material name")

    def model_post_init(self, __context: Any) -> None:
        """Provide model post init support for the create part input.

        Args:
            __context (Any): The context value.

        Returns:
            None: None.

        Raises:
            ValueError: Name is required.
        """
        if not self.name.strip():
            raise ValueError("name is required")


class CreateExtrusionInput(CompatInput):
    """Input schema for creating an extrusion feature.

    Attributes:
        both_directions (bool): The both directions value.
        depth (float): The depth value.
        direction (str): The direction value.
        draft_angle (float): The draft angle value.
        end_condition (str): The end condition value.
        merge_result (bool): The merge result value.
        reverse (bool | None): The reverse value.
        reverse_direction (bool): The reverse direction value.
        sketch_name (str): The sketch name value.
        thin_feature (bool): The thin feature value.
        thin_thickness (float | None): The thin thickness value.
    """

    sketch_name: str = Field(description="Sketch name to extrude")
    depth: float = Field(description="Extrusion depth in millimeters")
    direction: str = Field(default="blind", description="Extrusion direction")
    reverse: bool | None = Field(default=None, description="Reverse direction alias")
    draft_angle: float = Field(default=0.0, description="Draft angle in degrees")
    reverse_direction: bool = Field(
        default=False, description="Reverse extrusion direction"
    )
    both_directions: bool = Field(
        default=False, description="Extrude in both directions"
    )
    thin_feature: bool = Field(default=False, description="Create as thin wall feature")
    thin_thickness: float | None = Field(
        default=None, description="Thickness for thin wall feature in mm"
    )
    end_condition: str = Field(default="Blind", description="End condition type")
    merge_result: bool = Field(default=True, description="Merge with existing geometry")

    def model_post_init(self, __context: Any) -> None:
        """Provide model post init support for the create extrusion input.

        Args:
            __context (Any): The context value.

        Returns:
            None: None.

        Raises:
            ValueError: Sketch_name is required.
        """
        if self.depth <= 0:
            raise ValueError("depth must be positive")
        if not self.sketch_name.strip():
            raise ValueError("sketch_name is required")
        if self.reverse is not None:
            self.reverse_direction = self.reverse


class CreateRevolveInput(CompatInput):
    """Input schema for creating a revolve feature.

    Attributes:
        angle (float): The angle value.
        axis_entity (str): The axis entity value.
        both_directions (bool): The both directions value.
        direction (str): The direction value.
        merge_result (bool): The merge result value.
        reverse_direction (bool): The reverse direction value.
        sketch_name (str): The sketch name value.
        thin_feature (bool): The thin feature value.
        thin_thickness (float | None): The thin thickness value.
    """

    sketch_name: str = Field(description="Sketch name to revolve")
    axis_entity: str = Field(description="Axis entity for the revolve")
    angle: float = Field(description="Revolve angle in degrees")
    direction: str = Field(default="one_direction", description="Revolve direction")
    reverse_direction: bool = Field(
        default=False, description="Reverse revolve direction"
    )
    both_directions: bool = Field(
        default=False, description="Revolve in both directions"
    )
    thin_feature: bool = Field(default=False, description="Create as thin wall feature")
    thin_thickness: float | None = Field(
        default=None, description="Thickness for thin wall feature in mm"
    )
    merge_result: bool = Field(default=True, description="Merge with existing geometry")

    def model_post_init(self, __context: Any) -> None:
        """Provide model post init support for the create revolve input.

        Args:
            __context (Any): The context value.

        Returns:
            None: None.

        Raises:
            ValueError: Angle must be positive.
        """
        if self.angle <= 0:
            raise ValueError("angle must be positive")


class CreateSweepInput(BaseModel):
    """Input schema for creating a sweep feature.

    Attributes:
        merge_result (bool): The merge result value.
        path (str): The path value.
        twist_along_path (bool): The twist along path value.
        twist_angle (float): The twist angle value.
    """

    path: str = Field(description="Name or ID of the sweep path")
    twist_along_path: bool = Field(default=False, description="Twist along path")
    twist_angle: float = Field(default=0.0, description="Twist angle in degrees")
    merge_result: bool = Field(default=True, description="Merge with existing geometry")


class CreateLoftInput(BaseModel):
    """Input schema for creating a loft feature.

    Attributes:
        end_tangent (str | None): The end tangent value.
        guide_curves (list[str] | None): The guide curves value.
        merge_result (bool): The merge result value.
        profiles (list[str]): The profiles value.
        start_tangent (str | None): The start tangent value.
    """

    profiles: list[str] = Field(description="List of profile names or IDs")
    guide_curves: list[str] | None = Field(
        default=None, description="List of guide curve names or IDs"
    )
    start_tangent: str | None = Field(
        default=None, description="Start tangent condition"
    )
    end_tangent: str | None = Field(default=None, description="End tangent condition")
    merge_result: bool = Field(default=True, description="Merge with existing geometry")


class GetDimensionInput(CompatInput):
    """Input schema for getting a dimension value.

    Attributes:
        dimension_name (str | None): The dimension name value.
        name (str | None): The name value.
    """

    name: str | None = Field(
        default=None,
        description="Dimension name (e.g., 'D1@Sketch1', 'D1@Boss-Extrude1')",
    )
    dimension_name: str | None = Field(default=None, description="Dimension name alias")

    def model_post_init(self, __context: Any) -> None:
        """Provide model post init support for the get dimension input.

        Args:
            __context (Any): The context value.

        Returns:
            None: None.

        Raises:
            ValueError: Name is required.
        """
        if self.name is None:
            self.name = self.dimension_name
        if not self.name:
            raise ValueError("name is required")


class SetDimensionInput(CompatInput):
    """Input schema for setting a dimension value.

    Attributes:
        dimension_name (str | None): The dimension name value.
        name (str | None): The name value.
        units (str | None): The units value.
        value (float): The value value.
    """

    name: str | None = Field(
        default=None,
        description="Dimension name (e.g., 'D1@Sketch1', 'D1@Boss-Extrude1')",
    )
    dimension_name: str | None = Field(default=None, description="Dimension name alias")
    value: float = Field(description="New dimension value in millimeters")
    units: str | None = Field(default=None, description="Units alias")

    def model_post_init(self, __context: Any) -> None:
        """Provide model post init support for the set dimension input.

        Args:
            __context (Any): The context value.

        Returns:
            None: None.

        Raises:
            ValueError: Name is required.
        """
        if self.name is None:
            self.name = self.dimension_name
        if not self.name:
            raise ValueError("name is required")


class CloseModelInput(BaseModel):
    """Input schema for closing a model.

    Attributes:
        save (bool): The save value.
    """

    save: bool = Field(default=False, description="Save the model before closing")


class CreateCutExtrudeInput(CompatInput):
    """Input schema for creating a cut-extrude feature.

    Attributes:
        depth (float): Cut depth in millimeters.
        draft_angle (float): Draft angle in degrees.
        end_condition (str): End condition type.
        reverse_direction (bool): Reverse cut direction.
    """

    depth: float = Field(description="Cut depth in millimeters")
    draft_angle: float = Field(default=0.0, description="Draft angle in degrees")
    reverse_direction: bool = Field(default=False, description="Reverse cut direction")
    end_condition: str = Field(default="Blind", description="End condition type")

    def model_post_init(self, __context: Any) -> None:
        if self.depth <= 0:
            raise ValueError("depth must be positive")


class AddFilletInput(CompatInput):
    """Input schema for adding a fillet feature.

    Attributes:
        edge_names (list[str]): Edge names to fillet.
        radius (float): Fillet radius in millimeters.
    """

    radius: float = Field(description="Fillet radius in millimeters")
    edge_names: list[str] = Field(
        default_factory=list,
        description="Named edges to fillet (e.g. 'Edge<1>'). Leave empty to fillet all edges.",
    )

    def model_post_init(self, __context: Any) -> None:
        if self.radius <= 0:
            raise ValueError("radius must be positive")


class DeleteFeatureInput(CompatInput):
    """Input schema for deleting a feature or sketch.

    Attributes:
        name (str): Feature/sketch name to delete, e.g. ``"Boss-Extrude3"``.
    """

    name: str = Field(description="Feature or sketch name to delete, e.g. 'Boss-Extrude3'")


class SuppressFeatureInput(CompatInput):
    """Input schema for suppressing/unsuppressing a feature.

    Attributes:
        name (str): Feature name to toggle.
        suppress (bool): True to suppress, False to unsuppress.
    """

    name: str = Field(description="Feature name to suppress or unsuppress")
    suppress: bool = Field(
        default=True,
        description="True to suppress (hide/roll out), False to unsuppress",
    )


class CreateReferencePlaneInput(CompatInput):
    """Input schema for creating a reference plane.

    Attributes:
        reference (str): Reference plane/face name to offset from.
        offset (float): Offset distance in millimetres.
        angle (float): Angle in degrees (used instead of offset when non-zero).
        flip (bool): Reverse the offset/angle direction.
    """

    reference: str = Field(
        default="Front Plane",
        description="Reference plane or planar face name, e.g. 'Front Plane' or 'Plane2'",
    )
    offset: float = Field(
        default=0.0, description="Offset distance in mm from the reference plane"
    )
    angle: float = Field(
        default=0.0,
        description="Angle in degrees; used instead of offset when non-zero",
    )
    flip: bool = Field(
        default=False, description="Reverse the offset/angle direction"
    )

    def model_post_init(self, __context: Any) -> None:
        if not self.offset and not self.angle:
            raise ValueError("provide a non-zero offset or angle")


class MirrorFeatureInput(CompatInput):
    """Input schema for mirroring solid features about a plane.

    Attributes:
        features (list[str]): Feature names to mirror.
        mirror_plane (str): Mirror plane name.
        merge (bool): Merge the mirrored result into the existing body.
    """

    features: list[str] = Field(
        description="Feature names to mirror, e.g. ['Boss-Extrude110']"
    )
    mirror_plane: str = Field(
        default="Front Plane",
        description="Mirror plane or planar face name, e.g. 'Front Plane'",
    )
    merge: bool = Field(
        default=True, description="Merge the mirrored result into the existing body"
    )

    def model_post_init(self, __context: Any) -> None:
        if not self.features:
            raise ValueError("features must contain at least one feature name")


class CreateShellInput(CompatInput):
    """Input schema for hollowing a solid.

    Attributes:
        thickness (float): Wall thickness in millimetres.
        remove_faces (list[int]): Indices of faces to open.
        outward (bool): Thicken outward instead of inward.
    """

    thickness: float = Field(description="Wall thickness in millimetres")
    remove_faces: list[int] = Field(
        default_factory=list,
        description="Indices of faces to open (0-based). Omit for a closed hollow body.",
    )
    outward: bool = Field(
        default=False, description="Thicken outward instead of inward"
    )

    def model_post_init(self, __context: Any) -> None:
        if self.thickness <= 0:
            raise ValueError("thickness must be positive")


class PatternLinearInput(CompatInput):
    """Input schema for repeating features along an axis.

    Attributes:
        features (list[str]): Feature names to repeat.
        direction (str): Axis with optional sign, e.g. 'x', '-y'.
        count (int): Instances including the original.
        spacing (float): Distance between instances in millimetres.
        direction_edge (int | None): Explicit edge index override.
    """

    features: list[str] = Field(
        description="Feature names to repeat, e.g. ['Cut-Extrude1']"
    )
    direction: str = Field(
        default="x",
        description="Direction axis with optional sign: 'x', '-x', 'y', '-y', 'z', '-z'",
    )
    count: int = Field(
        default=2, description="Total instances including the original (>= 2)"
    )
    spacing: float = Field(
        default=10.0, description="Distance between instances in millimetres"
    )
    direction_edge: int | None = Field(
        default=None,
        description="Explicit edge index to use as direction, overriding 'direction'",
    )

    def model_post_init(self, __context: Any) -> None:
        if not self.features:
            raise ValueError("features must contain at least one feature name")
        if self.count < 2:
            raise ValueError("count must be >= 2 (it includes the original)")


class PatternCircularInput(CompatInput):
    """Input schema for repeating features around an axis.

    Attributes:
        features (list[str]): Feature names to repeat.
        axis (str): Axis feature name, or 'x'/'y'/'z'.
        count (int): Instances including the original.
        angle (float): Degrees of sweep.
        equal_spacing (bool): Distribute instances evenly across the angle.
    """

    features: list[str] = Field(
        description="Feature names to repeat, e.g. ['Cut-Extrude1']"
    )
    axis: str = Field(
        default="z",
        description=(
            "Rotation axis: an existing axis feature name (e.g. 'Axis1'), or "
            "'x'/'y'/'z' to use or create a reference axis through the origin"
        ),
    )
    count: int = Field(
        default=4, description="Total instances including the original (>= 2)"
    )
    angle: float = Field(
        default=360.0,
        description=(
            "Degrees. With equal_spacing this is the total sweep the instances "
            "are spread over; otherwise it is the angle between neighbours"
        ),
    )
    equal_spacing: bool = Field(
        default=True, description="Distribute instances evenly across 'angle'"
    )

    def model_post_init(self, __context: Any) -> None:
        if not self.features:
            raise ValueError("features must contain at least one feature name")
        if self.count < 2:
            raise ValueError("count must be >= 2 (it includes the original)")
        if not self.angle:
            raise ValueError("angle must be non-zero")


class AddDraftInput(CompatInput):
    """Input schema for tapering faces with a draft angle.

    Attributes:
        angle (float): Draft angle in degrees.
        neutral_face (int): Index of the face the draft is measured from.
        draft_faces (list[int]): Indices of the faces to taper.
        outward (bool): Taper outward instead of inward.
    """

    angle: float = Field(description="Draft angle in degrees")
    neutral_face: int = Field(
        default=0,
        description=(
            "Index of the face the draft is measured from. Must be "
            "perpendicular to the faces being drafted - typically the cap the "
            "feature was extruded from"
        ),
    )
    draft_faces: list[int] = Field(
        default_factory=list, description="Indices of the faces to taper"
    )
    outward: bool = Field(
        default=False, description="Taper outward (adds material) instead of inward"
    )

    def model_post_init(self, __context: Any) -> None:
        if not self.angle:
            raise ValueError("angle must be non-zero")
        if not self.draft_faces:
            raise ValueError("draft_faces must contain at least one face index")
        if self.neutral_face in self.draft_faces:
            raise ValueError(
                "neutral_face cannot also be listed in draft_faces"
            )


class MoveBodyInput(CompatInput):
    """Input schema for translating or copying a solid body.

    Attributes:
        body (int): Body index.
        dx (float): X offset in millimetres.
        dy (float): Y offset in millimetres.
        dz (float): Z offset in millimetres.
        make_copy (bool): Leave the original in place and move a copy.
        copies (int): Number of copies when make_copy is set.
    """

    body: int = Field(default=0, description="Body index (see get_bounding_box)")
    dx: float = Field(default=0.0, description="X offset in millimetres")
    dy: float = Field(default=0.0, description="Y offset in millimetres")
    dz: float = Field(default=0.0, description="Z offset in millimetres")
    # Named make_copy rather than copy: a field called "copy" shadows
    # BaseModel.copy and Pydantic warns about it.
    make_copy: bool = Field(
        default=False, description="Leave the original in place and move a copy"
    )
    copies: int = Field(
        default=1, description="Number of copies when make_copy is set"
    )

    def model_post_init(self, __context: Any) -> None:
        if not (self.dx or self.dy or self.dz):
            raise ValueError("at least one of dx, dy, dz must be non-zero")
        if self.make_copy and self.copies < 1:
            raise ValueError("copies must be >= 1 when make_copy is set")


class DeleteBodyInput(CompatInput):
    """Input schema for deleting solid bodies.

    Attributes:
        bodies (list[int]): Body indices to delete.
    """

    bodies: list[int] = Field(
        default_factory=list, description="Indices of the bodies to delete"
    )

    def model_post_init(self, __context: Any) -> None:
        if not self.bodies:
            raise ValueError("bodies must contain at least one body index")


class CreateAxisInput(CompatInput):
    """Input schema for creating a reference axis.

    Attributes:
        reference (str): Axis direction — 'x', 'y' or 'z'.
    """

    reference: str = Field(
        default="z",
        description="Axis direction through the model origin: 'x', 'y' or 'z'",
    )


class UndoInput(CompatInput):
    """Input schema for undoing recent operations.

    Attributes:
        count (int): Number of operations to undo (>= 1).
    """

    count: int = Field(default=1, description="Number of operations to undo (>= 1)")


class CreateAssemblyInput(CompatInput):
    """Input schema for creating a new assembly.

    Attributes:
        components (list[str]): The components value.
        name (str): The name value.
        template (str | None): The template value.
    """

    name: str = Field(description="Name for the new assembly")
    template: str | None = Field(
        default=None, description="Assembly template file path"
    )
    components: list[str] = Field(
        default_factory=list,
        description=(
            "Components to insert. NOT SUPPORTED: the assembly is created but "
            "no component is inserted, and the response says so. Insert them "
            "in the SolidWorks UI or via generate_vba_assembly_insert"
        ),
    )


class CreateDrawingInput(CompatInput):
    """Input schema for creating a new drawing.

    Attributes:
        model_path (str | None): The model path value.
        name (str): The name value.
        sheet_format (str | None): The sheet format value.
        template (str | None): The template value.
    """

    name: str = Field(description="Name for the new drawing")
    template: str | None = Field(default=None, description="Drawing template file path")
    model_path: str | None = Field(default=None, description="Source model path")
    sheet_format: str | None = Field(default=None, description="Sheet format template")


async def register_modeling_tools(
    mcp: FastMCP, adapter: SolidWorksAdapter, config: dict[str, Any]
) -> int:
    """Register modeling tools with FastMCP.

    Registers comprehensive modeling tools for SolidWorks automation including model
    creation, feature creation, and model management operations.

    Args:
        mcp (FastMCP): The mcp value.
        adapter (SolidWorksAdapter): Adapter instance used for the operation.
        config (dict[str, Any]): Configuration values for the operation.

    Returns:
        int: The computed numeric result.

    Example:
                        ```python
                        from solidworks_mcp.tools.modeling import register_modeling_tools

                        tool_count = await register_modeling_tools(mcp, adapter, config)
                        print(f"Registered {tool_count} modeling tools")
                        ```
    """
    tool_count = 0

    @mcp.tool()
    async def open_model(input_data: OpenModelInput) -> dict[str, Any]:
        """Open a SolidWorks model (part, assembly, or drawing).

        Opens an existing SolidWorks file and makes it the active document for further
        operations. Supports all standard SolidWorks file formats and provides detailed model
        information upon successful opening.

        Args:
            input_data (OpenModelInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            ```python
                            result = await open_model({
                                "file_path": "C:/Models/bracket.sldprt"
                            })

                            if result["status"] == "success":
                                model = result["model"]
                                print(f"Opened {model['type']}: {model['name']}")
                                print(f"Configuration: {model['configuration']}")
                            ```

                        Note:
                            File path must be absolute and accessible to SolidWorks.
                            Model becomes the active document for subsequent operations.
        """
        try:
            input_data = _normalize_input(input_data, OpenModelInput)
            result = await adapter.open_model(input_data.file_path)

            if result.is_success:
                model = result.data
                title = _result_value(
                    model, "title", "name", default=input_data.file_path
                )
                model_type = _result_value(model, "type", default="Part")
                path = _result_value(
                    model, "path", "file_path", default=input_data.file_path
                )
                configuration = _result_value(model, "configuration", default="Default")
                return {
                    "status": "success",
                    "message": f"Opened {model_type}: {title}",
                    "model": {
                        "title": title,
                        "name": title,
                        "type": model_type,
                        "path": path,
                        "configuration": configuration,
                    },
                    "execution_time": result.execution_time,
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to open model: {result.error}",
                }

        except Exception as e:
            logger.error(f"Error in open_model tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    @mcp.tool()
    async def create_part(input_data: CreatePartInput) -> dict[str, Any]:
        """Create a new SolidWorks part document.

        Creates a new SolidWorks part document using the default part template. The new part
        becomes the active document and is ready for modeling operations such as sketch creation
        and feature addition.

        Args:
            input_data (CreatePartInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            ```python
                            result = await create_part()

                            if result["status"] == "success":
                                part = result["model"]
                                print(f"Created new part: {part['name']}")
                                # Ready for sketching and feature creation
                            ```

                        Note:
                            - Uses default SolidWorks part template
                            - Part document is created in memory (not saved)
                            - Use save operations to persist to disk
                            - Subsequent modeling operations will apply to this part
        """
        try:
            input_data = _normalize_input(input_data, CreatePartInput)
            result = await adapter.create_part(input_data.name, input_data.units)

            if result.is_success:
                model = result.data
                part_name = _result_value(model, "name", default=input_data.name)
                units = _result_value(model, "units", default=input_data.units or "mm")
                return {
                    "status": "success",
                    "message": f"Created new part: {part_name}",
                    "part": {
                        "name": part_name,
                        "units": units,
                        "material": input_data.material,
                        "template": input_data.template,
                    },
                    "execution_time": result.execution_time,
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to create part: {result.error}",
                }

        except Exception as e:
            logger.error(f"Error in create_part tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    @mcp.tool()
    async def create_assembly(input_data: CreateAssemblyInput) -> dict[str, Any]:
        """Create a new SolidWorks assembly document.

        Creates a new SolidWorks assembly document using the default assembly template. The new
        assembly becomes the active document and is ready for component insertion, mating, and
        assembly-level operations.

        Args:
            input_data (CreateAssemblyInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            ```python
                            result = await create_assembly()

                            if result["status"] == "success":
                                assembly = result["model"]
                                print(f"Created new assembly: {assembly['name']}")
                                # Ready for component insertion and mating
                            ```

                        Note:
                            - Uses default SolidWorks assembly template
                            - Assembly document is created in memory (not saved)
                            - Use save operations to persist to disk
                            - Ready for component insertion and mate creation
                            - Assembly tree will initially be empty

                        This tool creates a new assembly document using the default assembly template.
                        The new assembly will become the active document.
        """
        try:
            input_data = _normalize_input(input_data, CreateAssemblyInput)
            result = await adapter.create_assembly(input_data.name)

            if result.is_success:
                model = result.data
                assembly_name = _result_value(model, "name", default=input_data.name)
                payload: dict[str, Any] = {
                    "status": "success",
                    "message": f"Created new assembly: {assembly_name}",
                    "assembly": {
                        "name": assembly_name,
                        "components_inserted": 0,
                        "template": input_data.template,
                    },
                    "execution_time": result.execution_time,
                }
                if input_data.components:
                    # The assembly really is created, but nothing is inserted.
                    # This used to echo the requested components back inside a
                    # "success" payload, which read as though they had been
                    # added — an isometric render of the result was an empty
                    # scene. Say so instead.
                    payload["warning"] = (
                        f"{len(input_data.components)} component(s) were "
                        "requested but NONE were inserted: component insertion "
                        "is not available through this adapter. Insert them in "
                        "the SolidWorks UI, or generate a macro with "
                        "generate_vba_assembly_insert."
                    )
                    payload["components_requested"] = input_data.components
                return payload
            else:
                return {
                    "status": "error",
                    "message": f"Failed to create assembly: {result.error}",
                }

        except Exception as e:
            logger.error(f"Error in create_assembly tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    @mcp.tool()
    async def create_drawing(input_data: CreateDrawingInput) -> dict[str, Any]:
        """Create a new SolidWorks drawing document.

        This tool creates a new drawing document using the default drawing template. The new
        drawing will become the active document.

        Args:
            input_data (CreateDrawingInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.
        """
        try:
            input_data = _normalize_input(input_data, CreateDrawingInput)
            result = await adapter.create_drawing(input_data.name)

            if result.is_success:
                model = result.data
                drawing_name = _result_value(model, "name", default=input_data.name)
                sheet_format = _result_value(
                    model, "sheet_format", default=input_data.sheet_format
                )
                return {
                    "status": "success",
                    "message": f"Created new drawing: {drawing_name}",
                    "drawing": {
                        "name": drawing_name,
                        "model_path": input_data.model_path,
                        "sheet_format": sheet_format,
                        "template": input_data.template,
                    },
                    "execution_time": result.execution_time,
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to create drawing: {result.error}",
                }

        except Exception as e:
            logger.error(f"Error in create_drawing tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    @mcp.tool()
    async def close_model(input_data: CloseModelInput) -> dict[str, Any]:
        """Close the current SolidWorks model.

        Closes the currently active SolidWorks document with an option to save changes before
        closing. This is essential for proper model lifecycle management and preventing data
        loss.

        Args:
            input_data (CloseModelInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            ```python
                            # Close without saving
                            result = await close_model({"save": False})

                            # Save and close
                            result = await close_model({"save": True})

                            if result["status"] == "success":
                                print(f"Model closed, saved: {result['saved']}")
                            ```

                        Note:
                            - Unsaved changes will be lost if save=False
                            - Always save important work before closing
                            - Model must be open to close it
        """
        try:
            input_data = _normalize_input(input_data, CloseModelInput)
            result = await adapter.close_model(input_data.save)

            if result.is_success:
                return {
                    "status": "success",
                    "message": "Model closed successfully",
                    "saved": input_data.save,
                    "execution_time": result.execution_time,
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to close model: {result.error}",
                }

        except Exception as e:
            logger.error(f"Error in close_model tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    @mcp.tool()
    async def create_extrusion(input_data: CreateExtrusionInput) -> dict[str, Any]:
        """Create an extrusion feature from the active sketch.

        Creates a 3D extrusion feature (boss or cut) from the currently active 2D sketch.
        Supports advanced options like draft angles, thin features, bidirectional extrusion, and
        various end conditions for professional modeling workflows.

        Args:
            input_data (CreateExtrusionInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            ```python
                            # Simple boss extrusion
                            result = await create_extrusion({
                                "depth": 25.0,
                                "merge_result": True
                            })

                            # Cut with draft angle
                            result = await create_extrusion({
                                "depth": 10.0,
                                "reverse_direction": True,
                                "draft_angle": 2.0
                            })

                            # Thin wall feature
                            result = await create_extrusion({
                                "depth": 50.0,
                                "thin_feature": True,
                                "thin_thickness": 2.0
                            })
                            ```
        """
        try:
            input_data = _normalize_input(input_data, CreateExtrusionInput)
            # Convert input to ExtrusionParameters
            params = ExtrusionParameters(
                depth=input_data.depth,
                draft_angle=input_data.draft_angle,
                reverse_direction=input_data.reverse_direction,
                both_directions=input_data.both_directions,
                thin_feature=input_data.thin_feature,
                thin_thickness=input_data.thin_thickness,
                end_condition=input_data.end_condition,
                merge_result=input_data.merge_result,
                feature_scope=False,
                auto_select=True,
            )

            result = await adapter.create_extrusion(params)

            if result.is_success:
                feature = result.data
                return {
                    "status": "success",
                    "message": f"Created extrusion: {_result_value(feature, 'feature_name', 'name', default='Extrusion')}",
                    "extrusion": {
                        "name": _result_value(
                            feature, "feature_name", "name", default="Extrusion"
                        ),
                        "sketch": input_data.sketch_name,
                        "depth": input_data.depth,
                        "direction": input_data.direction,
                    },
                    "execution_time": result.execution_time,
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to create extrusion: {result.error}",
                }

        except Exception as e:
            logger.error(f"Error in create_extrusion tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    @mcp.tool()
    async def create_revolve(input_data: CreateRevolveInput) -> dict[str, Any]:
        """Create a revolve feature from the active sketch.

        Creates a 3D revolve feature by rotating the active 2D sketch profile around a specified
        axis of revolution. Supports full and partial revolves, thin features, and bidirectional
        revolution for comprehensive rotational modeling.

        Args:
            input_data (CreateRevolveInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            ```python
                            # Full revolution (cylinder)
                            result = await create_revolve({
                                "angle": 360.0,
                                "merge_result": True
                            })

                            # Partial revolution (arc section)
                            result = await create_revolve({
                                "angle": 120.0,
                                "both_directions": True
                            })

                            # Thin wall revolution (pipe)
                            result = await create_revolve({
                                "angle": 360.0,
                                "thin_feature": True,
                                "thin_thickness": 3.0
                            })
                            ```
        """
        try:
            input_data = _normalize_input(input_data, CreateRevolveInput)
            # Convert input to RevolveParameters
            params = RevolveParameters(
                angle=input_data.angle,
                reverse_direction=input_data.reverse_direction,
                both_directions=input_data.both_directions,
                thin_feature=input_data.thin_feature,
                thin_thickness=input_data.thin_thickness,
                merge_result=input_data.merge_result,
            )

            result = await adapter.create_revolve(params)

            if result.is_success:
                feature = result.data
                return {
                    "status": "success",
                    "message": f"Created revolve: {_result_value(feature, 'feature_name', 'name', default='Revolve')}",
                    "revolve": {
                        "name": _result_value(
                            feature, "feature_name", "name", default="Revolve"
                        ),
                        "sketch": input_data.sketch_name,
                        "axis_entity": input_data.axis_entity,
                        "angle": input_data.angle,
                        "direction": input_data.direction,
                    },
                    "execution_time": result.execution_time,
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to create revolve: {result.error}",
                }

        except Exception as e:
            logger.error(f"Error in create_revolve tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    @mcp.tool()
    async def get_dimension(input_data: GetDimensionInput) -> dict[str, Any]:
        """Get the value of a dimension from the current model.

        Retrieves the current value of a named dimension from the active SolidWorks model.
        Dimensions can be from sketches, features, or global dimensions. Useful for parametric
        modeling and design validation.

        Args:
            input_data (GetDimensionInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            ```python
                            # Get sketch dimension
                            result = await get_dimension({
                                "name": "D1@Sketch1"
                            })

                            if result["status"] == "success":
                                dim = result["dimension"]
                                print(f"Dimension {dim['name']}: {dim['value']} {dim['units']}")

                            # Get feature dimension
                            result = await get_dimension({
                                "name": "D1@Boss-Extrude1"
                            })
                            ```
        """
        try:
            input_data = _normalize_input(input_data, GetDimensionInput)
            if not input_data.name:
                return {"status": "error", "message": "Dimension name is required"}
            result = await adapter.get_dimension(input_data.name)

            if result.is_success:
                value = result.data
                dimension_value = _result_value(value, "value", default=value)
                dimension_units = _result_value(value, "units", default="mm")
                return {
                    "status": "success",
                    "message": f"Dimension {input_data.name} = {dimension_value} {dimension_units}",
                    "dimension": {
                        "name": input_data.name,
                        "value": dimension_value,
                        "units": dimension_units,
                    },
                    "execution_time": result.execution_time,
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to get dimension: {result.error}",
                }

        except Exception as e:
            logger.error(f"Error in get_dimension tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    @mcp.tool()
    async def set_dimension(input_data: SetDimensionInput) -> dict[str, Any]:
        """Set the value of a dimension in the current model.

        This tool modifies the value of a named dimension and rebuilds the model. Use this to
        parametrically modify your model dimensions.

        Args:
            input_data (SetDimensionInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.
        """
        try:
            input_data = _normalize_input(input_data, SetDimensionInput)
            if not input_data.name:
                return {"status": "error", "message": "Dimension name is required"}
            result = await adapter.set_dimension(input_data.name, input_data.value)

            if result.is_success:
                payload = result.data
                return {
                    "status": "success",
                    "message": f"Set dimension {input_data.name} = {input_data.value} mm",
                    "dimension_update": {
                        "name": input_data.name,
                        "old_value": _result_value(payload, "old_value"),
                        "new_value": _result_value(
                            payload, "new_value", default=input_data.value
                        ),
                        "units": input_data.units or "mm",
                    },
                    "execution_time": result.execution_time,
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to set dimension: {result.error}",
                }

        except Exception as e:
            logger.error(f"Error in set_dimension tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    @mcp.tool()
    async def create_cut_extrude(input_data: CreateCutExtrudeInput) -> dict[str, Any]:
        """Cut material from the active model using the current sketch profile.

        Creates a Cut-Extrude feature (Insert > Cut > Extrude) from the active sketch.
        Use this after exit_sketch when you want to remove material — e.g. to create
        windows, holes, slots, or any through/blind cut in an existing solid body.

        Args:
            input_data (CreateCutExtrudeInput): Depth, direction and draft parameters.

        Returns:
            dict[str, Any]: Status and feature details.

        Example:
            ```python
            # Cut a blind pocket 10 mm deep
            result = await create_cut_extrude({"depth": 10.0})

            # Through-all cut (use a depth larger than the solid)
            result = await create_cut_extrude({"depth": 200.0})
            ```
        """
        try:
            input_data = _normalize_input(input_data, CreateCutExtrudeInput)
            params = ExtrusionParameters(
                depth=input_data.depth,
                draft_angle=input_data.draft_angle,
                reverse_direction=input_data.reverse_direction,
                both_directions=False,
                thin_feature=False,
                thin_thickness=None,
                end_condition=input_data.end_condition,
                merge_result=False,
                feature_scope=False,
                auto_select=True,
            )
            result = await adapter.create_cut_extrude(params)
            if result.is_success:
                feature = result.data
                return {
                    "status": "success",
                    "message": f"Created cut-extrude: {_result_value(feature, 'feature_name', 'name', default='Cut-Extrude')}",
                    "cut_extrude": {
                        "name": _result_value(
                            feature, "feature_name", "name", default="Cut-Extrude"
                        ),
                        "depth": input_data.depth,
                    },
                    "execution_time": result.execution_time,
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to create cut-extrude: {result.error}",
                }
        except Exception as e:
            logger.error(f"Error in create_cut_extrude tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def add_fillet(input_data: AddFilletInput) -> dict[str, Any]:
        """Add a fillet (rounded edge) to selected edges of the current model.

        Rounds the specified named edges with the given radius. Edge names use the
        SolidWorks convention, e.g. 'Edge<1>', or you can leave edge_names empty to
        fillet all edges if the adapter supports it.

        Args:
            input_data (AddFilletInput): Radius and edge names.

        Returns:
            dict[str, Any]: Status and feature details.

        Example:
            ```python
            # Fillet two specific edges with 2 mm radius
            result = await add_fillet({"radius": 2.0, "edge_names": ["Edge<1>", "Edge<2>"]})
            ```
        """
        try:
            input_data = _normalize_input(input_data, AddFilletInput)
            result = await adapter.add_fillet(input_data.radius, input_data.edge_names)
            if result.is_success:
                feature = result.data
                return {
                    "status": "success",
                    "message": f"Created fillet: {_result_value(feature, 'feature_name', 'name', default='Fillet')}",
                    "fillet": {
                        "name": _result_value(
                            feature, "feature_name", "name", default="Fillet"
                        ),
                        "radius": input_data.radius,
                        "edges": input_data.edge_names,
                    },
                    "execution_time": result.execution_time,
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to add fillet: {result.error}",
                }
        except Exception as e:
            logger.error(f"Error in add_fillet tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def delete_feature(input_data: DeleteFeatureInput) -> dict[str, Any]:
        """Delete a feature or sketch from the active model by name.

        Equivalent to selecting the feature in the tree and pressing Delete.
        Features that depend on it are removed with it (SolidWorks' normal
        cascade). Use this to fix a mistake without rebuilding from scratch.

        Args:
            input_data (DeleteFeatureInput): The feature/sketch name to delete.

        Returns:
            dict[str, Any]: Status and the deleted feature name.

        Example:
            ```python
            result = await delete_feature({"name": "Boss-Extrude3"})
            ```
        """
        try:
            input_data = _normalize_input(input_data, DeleteFeatureInput)
            result = await adapter.delete_feature(input_data.name)
            if result.is_success:
                return {
                    "status": "success",
                    "message": f"Deleted feature: {input_data.name}",
                    "deleted": input_data.name,
                    "execution_time": result.execution_time,
                }
            return {
                "status": "error",
                "message": f"Failed to delete feature: {result.error}",
            }
        except Exception as e:
            logger.error(f"Error in delete_feature tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def create_reference_plane(
        input_data: CreateReferencePlaneInput,
    ) -> dict[str, Any]:
        """Create a reference plane offset from (or angled to) an existing plane.

        Removes the limitation that sketches can only be placed on the six
        built-in planes. Use this to make an offset plane (e.g. 2 mm in front of
        the Front Plane) and then pass its name to ``create_sketch``.

        Args:
            input_data (CreateReferencePlaneInput): Reference name, offset/angle, flip.

        Returns:
            dict[str, Any]: Status and the new plane's name.

        Example:
            ```python
            # Plane 2 mm off the Front Plane, then sketch on it
            r = await create_reference_plane({"reference": "Front Plane", "offset": 2.0})
            await create_sketch({"plane": r["plane"]["name"]})

            # Plane angled 30 degrees off the Right Plane
            await create_reference_plane({"reference": "Right Plane", "angle": 30})
            ```
        """
        try:
            input_data = _normalize_input(input_data, CreateReferencePlaneInput)
            result = await adapter.create_reference_plane(
                input_data.reference,
                input_data.offset,
                input_data.angle,
                input_data.flip,
            )
            if result.is_success:
                data = result.data if isinstance(result.data, dict) else {}
                return {
                    "status": "success",
                    "message": f"Created reference plane: {data.get('name', 'Plane')}",
                    "plane": data,
                    "execution_time": result.execution_time,
                }
            return {
                "status": "error",
                "message": f"Failed to create reference plane: {result.error}",
            }
        except Exception as e:
            logger.error(f"Error in create_reference_plane tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def pattern_linear(input_data: PatternLinearInput) -> dict[str, Any]:
        """Repeat one or more features along an axis (linear pattern).

        Creates a Linear Pattern feature — e.g. turning a single hole into a
        row of evenly spaced holes.

        SolidWorks takes the direction from a model edge, so ``direction``
        names an axis and a matching edge is found for you. **The sign
        matters**: patterning toward the near side of the body marches the
        copies off the edge and produces malformed geometry, so pick the
        direction that runs into the material.

        Args:
            input_data (PatternLinearInput): Features, direction, count, spacing.

        Returns:
            dict[str, Any]: Status and pattern details.

        Example:
            ```python
            # Three holes, 15 mm apart, marching along +x
            await pattern_linear({
                "features": ["Cut-Extrude1"],
                "direction": "x",
                "count": 3,
                "spacing": 15.0,
            })
            ```
        """
        try:
            input_data = _normalize_input(input_data, PatternLinearInput)
            result = await adapter.pattern_linear(
                input_data.features,
                input_data.direction,
                input_data.count,
                input_data.spacing,
                input_data.direction_edge,
            )
            if result.is_success:
                data = result.data if isinstance(result.data, dict) else {}
                return {
                    "status": "success",
                    "message": (
                        f"Patterned {len(input_data.features)} feature(s) into "
                        f"{input_data.count} instances along {input_data.direction}"
                    ),
                    "pattern": data,
                    "execution_time": result.execution_time,
                }
            return {
                "status": "error",
                "message": f"Failed to create linear pattern: {result.error}",
            }
        except Exception as e:
            logger.error(f"Error in pattern_linear tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def add_draft(input_data: AddDraftInput) -> dict[str, Any]:
        """Taper faces by a draft angle.

        Creates a Draft feature — the taper that lets a moulded part release from its
        tool. ``neutral_face`` is the face the angle is measured from and **must be
        perpendicular to the faces being tapered**; drafting a face against its own
        opposite face does nothing and is reported as an error.

        Faces are addressed by index because SolidWorks exposes no way to list face
        names here. Indices are stable for a given model.

        Args:
            input_data (AddDraftInput): Angle, neutral face, faces to taper.

        Returns:
            dict[str, Any]: Status and draft details, including the volume change.

        Example:
            ```python
            # 5 degrees on the four sides of a block, measured from its top face
            await add_draft({
                "angle": 5.0,
                "neutral_face": 4,
                "draft_faces": [0, 1, 2, 3],
            })
            ```
        """
        try:
            input_data = _normalize_input(input_data, AddDraftInput)
            result = await adapter.add_draft(
                input_data.angle,
                input_data.neutral_face,
                input_data.draft_faces,
                input_data.outward,
            )
            if result.is_success:
                data = result.data if isinstance(result.data, dict) else {}
                return {
                    "status": "success",
                    "message": (
                        f"Drafted {len(input_data.draft_faces)} face(s) at "
                        f"{input_data.angle} degrees"
                    ),
                    "draft": data,
                    "execution_time": result.execution_time,
                }
            return {
                "status": "error",
                "message": f"Failed to add draft: {result.error}",
            }
        except Exception as e:
            logger.error(f"Error in add_draft tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def move_body(input_data: MoveBodyInput) -> dict[str, Any]:
        """Translate a solid body, or place copies of it.

        Creates a Body-Move/Copy feature. A translation does not change the model's
        volume, so this tool verifies the move by checking that a body actually ends
        up at the requested destination — a move applied at the wrong scale is caught
        rather than reported as success.

        Bodies are addressed by index, ordered by position so an index means the same
        body between calls.

        Args:
            input_data (MoveBodyInput): Body index, offset, copy options.

        Returns:
            dict[str, Any]: Status and move details.

        Example:
            ```python
            # Shift body 1 by 40 mm along +x
            await move_body({"body": 1, "dx": 40.0})
            ```
        """
        try:
            input_data = _normalize_input(input_data, MoveBodyInput)
            result = await adapter.move_body(
                input_data.body,
                input_data.dx,
                input_data.dy,
                input_data.dz,
                input_data.make_copy,
                input_data.copies,
            )
            if result.is_success:
                data = result.data if isinstance(result.data, dict) else {}
                return {
                    "status": "success",
                    "message": (
                        f"Moved body {input_data.body} by "
                        f"({input_data.dx}, {input_data.dy}, {input_data.dz}) mm"
                    ),
                    "move": data,
                    "execution_time": result.execution_time,
                }
            return {
                "status": "error",
                "message": f"Failed to move body: {result.error}",
            }
        except Exception as e:
            logger.error(f"Error in move_body tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def delete_body(input_data: DeleteBodyInput) -> dict[str, Any]:
        """Delete solid bodies from a multibody part.

        Creates a Body-Delete feature. Refuses to delete every body, since that would
        leave the part with no solid. Success is confirmed by the body count actually
        dropping.

        Args:
            input_data (DeleteBodyInput): Body indices to delete.

        Returns:
            dict[str, Any]: Status and the remaining body count.

        Example:
            ```python
            await delete_body({"bodies": [1]})
            ```
        """
        try:
            input_data = _normalize_input(input_data, DeleteBodyInput)
            result = await adapter.delete_body(input_data.bodies)
            if result.is_success:
                data = result.data if isinstance(result.data, dict) else {}
                return {
                    "status": "success",
                    "message": (
                        f"Deleted {len(input_data.bodies)} body(ies), "
                        f"{data.get('bodies_after', '?')} remaining"
                    ),
                    "delete": data,
                    "execution_time": result.execution_time,
                }
            return {
                "status": "error",
                "message": f"Failed to delete body: {result.error}",
            }
        except Exception as e:
            logger.error(f"Error in delete_body tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def create_axis(input_data: CreateAxisInput | None = None) -> dict[str, Any]:
        """Create a reference axis through the model origin.

        A fresh part has no axes — only the six default planes — so this is the
        prerequisite for a circular pattern. The axis is built from the
        intersection of the two built-in planes that share the requested
        direction, which places it exactly on the origin without depending on
        any existing geometry.

        ``pattern_circular`` calls this for you when you pass 'x', 'y' or 'z',
        so you only need it directly to create an axis up front.

        Args:
            input_data (CreateAxisInput | None): Axis direction.

        Returns:
            dict[str, Any]: Status and the new axis's feature name.

        Example:
            ```python
            await create_axis({"reference": "z"})
            ```
        """
        try:
            input_data = _normalize_input(input_data, CreateAxisInput)
            result = await adapter.create_axis(input_data.reference)
            if result.is_success:
                data = result.data if isinstance(result.data, dict) else {}
                return {
                    "status": "success",
                    "message": (
                        f"Created axis {data.get('name', '')} along "
                        f"{input_data.reference}"
                    ),
                    "axis": data,
                    "execution_time": result.execution_time,
                }
            return {
                "status": "error",
                "message": f"Failed to create axis: {result.error}",
            }
        except Exception as e:
            logger.error(f"Error in create_axis tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def pattern_circular(input_data: PatternCircularInput) -> dict[str, Any]:
        """Repeat one or more features around an axis (circular pattern).

        Creates a Circular Pattern feature — e.g. turning a single hole into a
        ring of evenly spaced holes around a bolt circle.

        ``axis`` accepts an existing axis feature name, or 'x'/'y'/'z' to reuse
        an axis if the part has one and create it otherwise. **The axis must
        pass through the part** or the instances land outside the body; the
        tool measures volume before and after and reports an error rather than
        a false success if nothing changed.

        Args:
            input_data (PatternCircularInput): Features, axis, count, angle.

        Returns:
            dict[str, Any]: Status and pattern details.

        Example:
            ```python
            # Six holes evenly spaced around the Z axis
            await pattern_circular({
                "features": ["Cut-Extrude1"],
                "axis": "z",
                "count": 6,
            })
            ```
        """
        try:
            input_data = _normalize_input(input_data, PatternCircularInput)
            result = await adapter.pattern_circular(
                input_data.features,
                input_data.axis,
                input_data.count,
                input_data.angle,
                input_data.equal_spacing,
            )
            if result.is_success:
                data = result.data if isinstance(result.data, dict) else {}
                return {
                    "status": "success",
                    "message": (
                        f"Patterned {len(input_data.features)} feature(s) into "
                        f"{input_data.count} instances around {input_data.axis}"
                    ),
                    "pattern": data,
                    "execution_time": result.execution_time,
                }
            return {
                "status": "error",
                "message": f"Failed to create circular pattern: {result.error}",
            }
        except Exception as e:
            logger.error(f"Error in pattern_circular tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def create_shell(input_data: CreateShellInput) -> dict[str, Any]:
        """Hollow out the solid, optionally opening one or more faces.

        Creates a Shell feature (Insert > Features > Shell) — the standard way
        to turn a solid block into a walled enclosure.

        Faces are addressed by **index**, because SolidWorks face names cannot
        be enumerated through this adapter. The returned ``face_count`` tells
        you how many faces exist; indices are stable for a given model, so a
        quick call with no ``remove_faces`` reveals the count, then re-run with
        the index you want opened.

        Args:
            input_data (CreateShellInput): Thickness, faces to open, direction.

        Returns:
            dict[str, Any]: Status, wall thickness, opened faces and volume.

        Example:
            ```python
            # 2 mm walls, open face 0 (an enclosure with one side removed)
            await create_shell({"thickness": 2.0, "remove_faces": [0]})

            # Fully closed hollow body
            await create_shell({"thickness": 1.5})
            ```
        """
        try:
            input_data = _normalize_input(input_data, CreateShellInput)
            result = await adapter.create_shell(
                input_data.thickness, input_data.remove_faces, input_data.outward
            )
            if result.is_success:
                data = result.data if isinstance(result.data, dict) else {}
                return {
                    "status": "success",
                    "message": (
                        f"Shelled body to {input_data.thickness}mm walls"
                        + (
                            f", opened face(s) {data.get('removed_faces')}"
                            if data.get("removed_faces")
                            else " (closed)"
                        )
                    ),
                    "shell": data,
                    "execution_time": result.execution_time,
                }
            return {
                "status": "error",
                "message": f"Failed to shell body: {result.error}",
            }
        except Exception as e:
            logger.error(f"Error in create_shell tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def mirror_feature(input_data: MirrorFeatureInput) -> dict[str, Any]:
        """Mirror one or more solid features about a plane.

        Creates a real mirror feature (Insert > Pattern/Mirror > Mirror), so a
        symmetric half only needs to be modelled once. Previously only sketch
        entities could be mirrored, forcing solid features to be mirrored by
        hand in the SolidWorks UI.

        Args:
            input_data (MirrorFeatureInput): Features, mirror plane, merge flag.

        Returns:
            dict[str, Any]: Status and the new mirror feature details.

        Example:
            ```python
            # Mirror a shell half to the other side of the Front Plane
            await mirror_feature({
                "features": ["Boss-Extrude110"],
                "mirror_plane": "Front Plane",
            })
            ```
        """
        try:
            input_data = _normalize_input(input_data, MirrorFeatureInput)
            result = await adapter.mirror_feature(
                input_data.features, input_data.mirror_plane, input_data.merge
            )
            if result.is_success:
                data = result.data if isinstance(result.data, dict) else {}
                return {
                    "status": "success",
                    "message": (
                        f"Mirrored {len(input_data.features)} feature(s) about "
                        f"{input_data.mirror_plane}"
                    ),
                    "mirror": data,
                    "execution_time": result.execution_time,
                }
            return {
                "status": "error",
                "message": f"Failed to mirror feature: {result.error}",
            }
        except Exception as e:
            logger.error(f"Error in mirror_feature tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def suppress_feature(input_data: SuppressFeatureInput) -> dict[str, Any]:
        """Suppress or unsuppress a feature by name (reversible, non-destructive).

        Suppressing rolls a feature (and its children) out of the model without
        deleting it — the safe way to turn a bad feature off and back on.

        Args:
            input_data (SuppressFeatureInput): Feature name and suppress flag.

        Returns:
            dict[str, Any]: Status and the action performed.

        Example:
            ```python
            await suppress_feature({"name": "Fillet2", "suppress": True})   # hide
            await suppress_feature({"name": "Fillet2", "suppress": False})  # restore
            ```
        """
        try:
            input_data = _normalize_input(input_data, SuppressFeatureInput)
            result = await adapter.suppress_feature(
                input_data.name, input_data.suppress
            )
            if result.is_success:
                verb = "Suppressed" if input_data.suppress else "Unsuppressed"
                return {
                    "status": "success",
                    "message": f"{verb} feature: {input_data.name}",
                    "feature": input_data.name,
                    "suppressed": input_data.suppress,
                    "execution_time": result.execution_time,
                }
            return {
                "status": "error",
                "message": f"Failed to change suppression: {result.error}",
            }
        except Exception as e:
            logger.error(f"Error in suppress_feature tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def undo(input_data: UndoInput) -> dict[str, Any]:
        """Undo the last N operations in the active model.

        Steps the model back without rebuilding from scratch. Defaults to a
        single undo.

        Args:
            input_data (UndoInput): Number of operations to undo.

        Returns:
            dict[str, Any]: Status and the number of operations undone.

        Example:
            ```python
            await undo({"count": 1})
            ```
        """
        try:
            input_data = _normalize_input(input_data, UndoInput)
            result = await adapter.undo(input_data.count)
            if result.is_success:
                return {
                    "status": "success",
                    "message": f"Undid {input_data.count} operation(s)",
                    "undone": input_data.count,
                    "execution_time": result.execution_time,
                }
            return {
                "status": "error",
                "message": f"Failed to undo: {result.error}",
            }
        except Exception as e:
            logger.error(f"Error in undo tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def create_sweep(input_data: CreateSweepInput) -> dict[str, Any]:
        """Sweep the active profile sketch along a named path sketch.

        Creates a swept boss/protrusion (Insert > Boss/Base > Sweep). Requires
        two sketches in the active part: a closed profile sketch and an open
        path sketch named by ``path``. The profile is inferred as the sketch
        that is not the path (in the usual "draw profile, draw path, sweep"
        flow this is unambiguous). Optionally applies a constant twist along
        the path.

        Args:
            input_data (CreateSweepInput): Path name and twist/merge options.

        Returns:
            dict[str, Any]: Status and feature details.

        Example:
            ```python
            # Sweep a circular profile along "Sketch2"
            result = await create_sweep({"path": "Sketch2"})

            # Sweep with a 90-degree twist along the path
            result = await create_sweep({
                "path": "Sketch2",
                "twist_along_path": True,
                "twist_angle": 90.0,
            })
            ```
        """
        try:
            input_data = _normalize_input(input_data, CreateSweepInput)
            params = SweepParameters(
                path=input_data.path,
                twist_along_path=input_data.twist_along_path,
                twist_angle=input_data.twist_angle,
                merge_result=input_data.merge_result,
            )
            result = await adapter.create_sweep(params)
            if result.is_success:
                feature = result.data
                return {
                    "status": "success",
                    "message": f"Created sweep: {_result_value(feature, 'feature_name', 'name', default='Sweep')}",
                    "sweep": {
                        "name": _result_value(
                            feature, "feature_name", "name", default="Sweep"
                        ),
                        "path": input_data.path,
                        "twist_along_path": input_data.twist_along_path,
                        "twist_angle": input_data.twist_angle,
                    },
                    "execution_time": result.execution_time,
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to create sweep: {result.error}",
                }
        except Exception as e:
            logger.error(f"Error in create_sweep tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def create_loft(input_data: CreateLoftInput) -> dict[str, Any]:
        """Loft a solid between two or more profile sketches.

        Creates a lofted boss/protrusion (Insert > Boss/Base > Loft) blending
        the listed profile sketches in order. Each profile must be a closed
        contour. Optional guide curves shape the transition between profiles.

        Args:
            input_data (CreateLoftInput): Profile names, optional guide curves,
                and tangency/merge options.

        Returns:
            dict[str, Any]: Status and feature details.

        Example:
            ```python
            # Loft between two profiles (e.g. a tapered bevel)
            result = await create_loft({"profiles": ["Sketch1", "Sketch2"]})

            # Loft with guide curves
            result = await create_loft({
                "profiles": ["Sketch1", "Sketch2"],
                "guide_curves": ["Sketch3"],
            })
            ```
        """
        try:
            input_data = _normalize_input(input_data, CreateLoftInput)
            params = LoftParameters(
                profiles=input_data.profiles,
                guide_curves=input_data.guide_curves,
                start_tangent=input_data.start_tangent,
                end_tangent=input_data.end_tangent,
                merge_result=input_data.merge_result,
            )
            result = await adapter.create_loft(params)
            if result.is_success:
                feature = result.data
                return {
                    "status": "success",
                    "message": f"Created loft: {_result_value(feature, 'feature_name', 'name', default='Loft')}",
                    "loft": {
                        "name": _result_value(
                            feature, "feature_name", "name", default="Loft"
                        ),
                        "profiles": input_data.profiles,
                        "guide_curves": input_data.guide_curves,
                    },
                    "execution_time": result.execution_time,
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to create loft: {result.error}",
                }
        except Exception as e:
            logger.error(f"Error in create_loft tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    tool_count = 12  # Number of tools registered
    return tool_count
