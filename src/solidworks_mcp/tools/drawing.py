"""Drawing tools for SolidWorks MCP Server.

Provides tools for creating drawing views, adding dimensions, annotations, and managing
technical drawings in SolidWorks.
"""

from typing import Any

from fastmcp import FastMCP
from loguru import logger
from pydantic import BaseModel, Field

from ..adapters.base import SolidWorksAdapter
from .input_compat import (
    CompatInput,
    normalize_input as _normalize_input,
)




# Input schemas using Python 3.14 built-in types


class CreateDrawingViewInput(BaseModel):
    """Input schema for creating drawing views.

    Attributes:
        model_path (str): The model path value.
        orientation (str): The orientation value.
        position_x (float): The position x value.
        position_y (float): The position y value.
        scale (float): The scale value.
        view_type (str): The view type value.
    """

    model_path: str = Field(description="Path to the SolidWorks model file")
    view_type: str = Field(
        description="Type of view (orthographic, isometric, section, detail)"
    )
    position_x: float = Field(default=100.0, description="X position in drawing (mm)")
    position_y: float = Field(default=200.0, description="Y position in drawing (mm)")
    scale: float = Field(default=1.0, description="View scale factor")
    orientation: str = Field(
        default="front", description="View orientation (front, top, right, isometric)"
    )


class AddDimensionInput(BaseModel):
    """Input schema for adding dimensions.

    Attributes:
        dimension_type (str): The dimension type value.
        entity1 (str): The entity1 value.
        entity2 (str | None): The entity2 value.
        position_x (float): The position x value.
        position_y (float): The position y value.
        precision (int): The precision value.
    """

    dimension_type: str = Field(
        description="Type of dimension (linear, radial, angular, diameter)"
    )
    entity1: str = Field(description="First entity to dimension (edge, face, point)")
    entity2: str | None = Field(
        default=None, description="Second entity for linear/angular dimensions"
    )
    position_x: float = Field(description="X position for dimension text")
    position_y: float = Field(description="Y position for dimension text")
    precision: int = Field(default=2, description="Number of decimal places")


class AddNoteInput(BaseModel):
    """Input schema for adding notes/annotations.

    Attributes:
        font_size (float): The font size value.
        leader_attachment (str | None): The leader attachment value.
        position_x (float): The position x value.
        position_y (float): The position y value.
        text (str): The text value.
    """

    text: str = Field(description="Note text content")
    position_x: float = Field(description="X position for note")
    position_y: float = Field(description="Y position for note")
    font_size: float = Field(default=12.0, description="Font size in points")
    leader_attachment: str | None = Field(
        default=None, description="Entity to attach leader line to"
    )


class CreateSectionViewInput(BaseModel):
    """Input schema for creating section views.

    Attributes:
        label (str): The label value.
        scale (float): The scale value.
        section_line_end (list[float]): The section line end value.
        section_line_start (list[float]): The section line start value.
        view_position_x (float): The view position x value.
        view_position_y (float): The view position y value.
    """

    section_line_start: list[float] = Field(
        description="Start point of section line as [x, y]",
        min_length=2,
        max_length=2,
        json_schema_extra={"items": {"type": "number"}},
    )
    section_line_end: list[float] = Field(
        description="End point of section line as [x, y]",
        min_length=2,
        max_length=2,
        json_schema_extra={"items": {"type": "number"}},
    )
    view_position_x: float = Field(description="X position for section view")
    view_position_y: float = Field(description="Y position for section view")
    scale: float = Field(default=1.0, description="Section view scale")
    label: str = Field(default="A", description="Section view label")


class CreateDetailViewInput(BaseModel):
    """Input schema for creating detail views.

    Attributes:
        center_x (float): The center x value.
        center_y (float): The center y value.
        label (str): The label value.
        radius (float): The radius value.
        scale (float): The scale value.
        view_position_x (float): The view position x value.
        view_position_y (float): The view position y value.
    """

    center_x: float = Field(description="X center of detail circle")
    center_y: float = Field(description="Y center of detail circle")
    radius: float = Field(description="Radius of detail circle")
    view_position_x: float = Field(description="X position for detail view")
    view_position_y: float = Field(description="Y position for detail view")
    scale: float = Field(default=2.0, description="Detail view scale")
    label: str = Field(default="A", description="Detail view label")


class UpdateSheetFormatInput(BaseModel):
    """Input schema for updating sheet format.

    Attributes:
        approved_by (str): The approved by value.
        checked_by (str): The checked by value.
        drawing_number (str): The drawing number value.
        drawn_by (str): The drawn by value.
        format_file (str): The format file value.
        sheet_size (str): The sheet size value.
        title (str): The title value.
    """

    format_file: str = Field(description="Path to sheet format template (.slddrt)")
    sheet_size: str = Field(default="A3", description="Sheet size (A4, A3, A2, A1, A0)")
    title: str = Field(default="", description="Drawing title")
    drawn_by: str = Field(default="", description="Drawn by field")
    checked_by: str = Field(default="", description="Checked by field")
    approved_by: str = Field(default="", description="Approved by field")
    drawing_number: str = Field(default="", description="Drawing number")


class DrawingCreationInput(CompatInput):
    """Input schema for creating a new drawing.

    Attributes:
        auto_populate_views (bool): The auto populate views value.
        model_file (str | None): The model file value.
        output_path (str | None): The output path value.
        scale (str): The scale value.
        sheet_format (str | None): The sheet format value.
        sheet_size (str): The sheet size value.
        template (str | None): The template value.
        title (str): The title value.
    """

    template: str | None = Field(default=None, description="Drawing template file path")
    model_file: str | None = Field(
        default=None, description="Model file to create drawing from"
    )
    sheet_size: str = Field(default="A3", description="Sheet size")
    title: str = Field(default="", description="Drawing title")
    output_path: str | None = Field(default=None, description="Output drawing path")
    sheet_format: str | None = Field(default=None, description="Sheet format")
    scale: str = Field(default="1:1", description="Drawing scale")
    auto_populate_views: bool = Field(
        default=False, description="Automatically populate standard views"
    )


class DrawingViewInput(CompatInput):
    """Input schema for drawing view operations.

    Attributes:
        drawing_path (str | None): The drawing path value.
        model_file (str | None): The model file value.
        operation (str): The operation value.
        parameters (dict[str, Any]): The parameters value.
        parent_view (str | None): The parent view value.
        position (list[float] | None): The position value.
        scale (str | None): The scale value.
        view_name (str | None): The view name value.
        view_type (str | None): The view type value.
    """

    drawing_path: str | None = Field(default=None, description="Path to drawing file")
    view_name: str | None = Field(default=None, description="Name of the drawing view")
    operation: str = Field(
        default="add", description="Operation to perform (create, update, delete)"
    )
    model_file: str | None = Field(default=None, description="Model file path")
    view_type: str | None = Field(default=None, description="Type of view")
    parent_view: str | None = Field(default=None, description="Parent view alias")
    position: list[float] | None = Field(default=None, description="View position")
    scale: str | None = Field(default=None, description="View scale")
    parameters: dict[str, Any] = Field(default={}, description="View parameters")


class DimensionInput(CompatInput):
    """Input schema for dimension operations.

    Attributes:
        dimension_name (str | None): The dimension name value.
        dimension_type (str | None): The dimension type value.
        drawing_path (str | None): The drawing path value.
        entities (list[str] | None): The entities value.
        entity1 (str | None): The entity1 value.
        entity2 (str | None): The entity2 value.
        operation (str | None): The operation value.
        position (list[float] | None): The position value.
        position_x (float | None): The position x value.
        position_y (float | None): The position y value.
        precision (int): The precision value.
        tolerance (str | None): The tolerance value.
        value (float | None): The value value.
    """

    drawing_path: str | None = Field(default=None, description="Path to drawing file")
    dimension_name: str | None = Field(
        default=None, description="Name of the dimension"
    )
    operation: str | None = Field(
        default="add", description="Operation to perform (add, update, delete)"
    )
    value: float | None = Field(default=None, description="Dimension value")
    dimension_type: str | None = Field(default=None, description="Type of dimension")
    entities: list[str] | None = Field(
        default=None, description="Entities to dimension"
    )
    entity1: str | None = Field(default=None, description="Primary entity alias")
    entity2: str | None = Field(default=None, description="Secondary entity alias")
    position: list[float] | None = Field(default=None, description="Dimension position")
    position_x: float | None = Field(default=None, description="Position X alias")
    position_y: float | None = Field(default=None, description="Position Y alias")
    precision: int = Field(default=2, description="Precision alias")
    tolerance: str | None = Field(default=None, description="Dimension tolerance")

    def model_post_init(self, __context: Any) -> None:
        """Provide model post init support for the dimension input.

        Args:
            __context (Any): The context value.

        Returns:
            None: None.
        """
        if self.entities:
            if self.entity1 is None and len(self.entities) >= 1:
                self.entity1 = self.entities[0]
            if self.entity2 is None and len(self.entities) >= 2:
                self.entity2 = self.entities[1]
        if self.position and len(self.position) >= 2:
            if self.position_x is None:
                self.position_x = float(self.position[0])
            if self.position_y is None:
                self.position_y = float(self.position[1])


class AnnotationInput(CompatInput):
    """Input schema for annotation operations.

    Attributes:
        annotation_type (str): The annotation type value.
        approved_by (str): The approved by value.
        checked_by (str): The checked by value.
        drawing_number (str): The drawing number value.
        drawing_path (str | None): The drawing path value.
        drawn_by (str): The drawn by value.
        font_size (float): The font size value.
        leader_attachment (str | None): The leader attachment value.
        position (list[float] | None): The position value.
        position_x (float | None): The position x value.
        position_y (float | None): The position y value.
        text (str): The text value.
    """

    drawing_path: str | None = Field(default=None, description="Path to drawing file")
    annotation_type: str = Field(
        description="Type of annotation (note, balloon, surface_finish, etc.)"
    )
    text: str = Field(description="Annotation text content")
    position_x: float | None = Field(
        default=None, description="X position for annotation"
    )
    position_y: float | None = Field(
        default=None, description="Y position for annotation"
    )
    position: list[float] | None = Field(
        default=None, description="Annotation position"
    )
    font_size: float = Field(default=12.0, description="Font size in points")
    leader_attachment: str | None = Field(
        default=None, description="Entity to attach leader line to"
    )
    drawn_by: str = Field(default="", description="Drawn by field")
    checked_by: str = Field(default="", description="Checked by field")
    approved_by: str = Field(default="", description="Approved by field")
    drawing_number: str = Field(default="", description="Drawing number")

    def model_post_init(self, __context: Any) -> None:
        """Provide model post init support for the annotation input.

        Args:
            __context (Any): The context value.

        Returns:
            None: None.
        """
        if self.position is not None and len(self.position) >= 2:
            if self.position_x is None:
                self.position_x = float(self.position[0])
            if self.position_y is None:
                self.position_y = float(self.position[1])


async def register_drawing_tools(
    mcp: FastMCP, adapter: SolidWorksAdapter, config: dict[str, Any]
) -> int:
    """Register drawing tools with FastMCP.

    Registers comprehensive technical drawing tools for SolidWorks automation including view
    creation, dimensioning, annotation, and drawing standards validation. Essential for
    automated documentation workflows.

    Args:
        mcp (FastMCP): The mcp value.
        adapter (SolidWorksAdapter): Adapter instance used for the operation.
        config (dict[str, Any]): Configuration values for the operation.

    Returns:
        int: The computed numeric result.

    Example:
                        ```python
                        from solidworks_mcp.tools.drawing import register_drawing_tools

                        tool_count = await register_drawing_tools(mcp, adapter, config)
                        print(f"Registered {tool_count} drawing tools")
                        ```
    """
    tool_count = 0

    @mcp.tool()
    async def create_drawing_view(input_data: CreateDrawingViewInput) -> dict[str, Any]:
        """Create a drawing view of a SolidWorks model.

        Creates technical drawing views including orthographic projections, isometric views,
        section views, and detail views from 3D models. Essential for generating production
        drawings and technical documentation.

        Args:
            input_data (CreateDrawingViewInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            ```python
                            # Create front orthographic view of a part
                            result = await create_drawing_view({
                                "model_path": "C:/Models/bracket.sldprt",
                                "view_type": "orthographic",
                                "position_x": 150.0, "position_y": 250.0,
                                "scale": 1.0,
                                "orientation": "front"
                            })

                            if result["status"] == "success":
                                view = result["drawing_view"]
                                print(f"Created {view['view_type']} view at {view['scale']}:1 scale")
                                # Ready for dimensioning and annotation
                            ```

                        Note:
                            - Model file must exist and be accessible
                            - Drawing sheet must be active before creating views
                            - View positioning follows drawing sheet coordinate system
                            - Multiple views can reference the same model file
        """
        try:
            input_data = _normalize_input(input_data, CreateDrawingViewInput)
            result = await adapter.add_drawing_view(
                input_data.model_path,
                input_data.orientation,
                input_data.position_x,
                input_data.position_y,
                input_data.scale if input_data.scale and input_data.scale != 1.0 else 0.0,
            )
            if result.is_success:
                data = result.data if isinstance(result.data, dict) else {}
                return {
                    "status": "success",
                    "message": (
                        f"Created {data.get('name', 'view')} of "
                        f"{input_data.model_path}"
                    ),
                    "drawing_view": data,
                    "execution_time": result.execution_time,
                }
            return {
                "status": "error",
                "message": f"Failed to create drawing view: {result.error}",
            }

        except Exception as e:
            logger.error(f"Error in create_drawing_view tool: {e}")
            return {
                "status": "error",
                "message": f"Failed to create drawing view: {str(e)}",
            }

    @mcp.tool()
    async def create_standard_views(input_data: dict[str, Any]) -> dict[str, Any]:
        """Drop the three standard views of a model onto the active drawing sheet.

        Lays out front, top and side in one call — the fastest way to start a drawing.
        Requires an active drawing document (call ``create_drawing`` first) and a model
        with real solid geometry.

        Args:
            input_data (dict[str, Any]): ``model_path`` and optional ``third_angle``.

        Returns:
            dict[str, Any]: Status and the view names that were created.

        Example:
            ```python
            await create_standard_views({"model_path": "C:/parts/bracket.sldprt"})
            ```
        """
        try:
            model_path = str(input_data.get("model_path", "")).strip()
            if not model_path:
                return {"status": "error", "message": "model_path is required"}
            third_angle = bool(input_data.get("third_angle", True))

            result = await adapter.create_standard_views(model_path, third_angle)
            if result.is_success:
                data = result.data if isinstance(result.data, dict) else {}
                views = data.get("views", []) if isinstance(data, dict) else []
                return {
                    "status": "success",
                    "message": f"Created {len(views)} standard views",
                    "standard_views": data,
                    "execution_time": result.execution_time,
                }
            return {
                "status": "error",
                "message": f"Failed to create standard views: {result.error}",
            }
        except Exception as e:
            logger.error(f"Error in create_standard_views tool: {e}")
            return {"status": "error", "message": f"Failed to create standard views: {str(e)}"}

    @mcp.tool()
    async def list_drawing_views() -> dict[str, Any]:
        """List the views on the active drawing.

        Returns:
            dict[str, Any]: Status and the view names.
        """
        try:
            result = await adapter.list_drawing_views()
            if result.is_success:
                views = result.data if isinstance(result.data, list) else []
                return {
                    "status": "success",
                    "message": f"{len(views)} view(s) on the drawing",
                    "views": views,
                    "execution_time": result.execution_time,
                }
            return {
                "status": "error",
                "message": f"Failed to list drawing views: {result.error}",
            }
        except Exception as e:
            logger.error(f"Error in list_drawing_views tool: {e}")
            return {"status": "error", "message": f"Failed to list drawing views: {str(e)}"}

    @mcp.tool()
    async def add_dimension(input_data: AddDimensionInput) -> dict[str, Any]:
        """Add a dimension to the current drawing.

        Creates dimensional annotations on drawing views including linear, radial, angular, and
        diameter dimensions. Essential for manufacturing specifications and quality control
        documentation.

        Args:
            input_data (AddDimensionInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            ```python
                            # Add diameter dimension to a hole
                            result = await add_dimension({
                                "dimension_type": "diameter",
                                "entity1": "Circle1",
                                "entity2": None,
                                "position_x": 100.0, "position_y": 150.0,
                                "precision": 2
                            })

                            if result["status"] == "success":
                                dim = result["dimension"]
                                print(f"Added {dim['type']} dimension with {dim['precision']} decimals")
                                # Dimension now drives manufacturing specification
                            ```

                        Note:
                            - Entities must be visible in current drawing view
                            - Dimension placement affects drawing readability
                            - Precision should match manufacturing tolerances
                            - Some dimension types require specific entity combinations
        """
        try:
            if hasattr(input_data, "model_dump"):
                payload = input_data.model_dump()
            else:
                payload = dict(input_data)

            dimension_type = payload.get("dimension_type")
            entity1 = payload.get("entity1")
            entity2 = payload.get("entity2")
            position_x = payload.get("position_x")
            position_y = payload.get("position_y")
            precision = payload.get("precision", 2)

            if (entity1 is None or entity2 is None) and payload.get("entities"):
                entities = payload["entities"]
                if entity1 is None and len(entities) >= 1:
                    entity1 = entities[0]
                if entity2 is None and len(entities) >= 2:
                    entity2 = entities[1]

            if (position_x is None or position_y is None) and payload.get("position"):
                position = payload["position"]
                if len(position) >= 2:
                    if position_x is None:
                        position_x = position[0]
                    if position_y is None:
                        position_y = position[1]

            if hasattr(adapter, "add_dimension"):
                result = await adapter.add_dimension(payload)
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Dimension added successfully",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed to add dimension",
                }

            # Deliberately an error rather than an invented dimension.
            # Placing one needs the two drawing entities selected by name, and
            # this adapter cannot enumerate drawing entity names, so there is
            # no honest way to satisfy the request.
            return {
                "status": "error",
                "message": (
                    "Placing an individual dimension is not supported: it "
                    "requires selecting drawing entities, which this adapter "
                    "cannot enumerate. Use auto_dimension_view to import the "
                    "model's own dimensions, or add the dimension in the "
                    "SolidWorks UI."
                ),
                "requested": {
                    "type": dimension_type,
                    "entity1": entity1,
                    "entity2": entity2,
                    "position": {"x": position_x, "y": position_y},
                    "precision": precision,
                },
            }

        except Exception as e:
            logger.error(f"Error in add_dimension tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    @mcp.tool()
    async def add_note(input_data: AddNoteInput) -> dict[str, Any]:
        """Add a note or annotation to the current drawing.

        Creates text annotations, callouts, and notes on drawings for specifications,
        instructions, and additional manufacturing information. Essential for comprehensive
        technical documentation.

        Args:
            input_data (AddNoteInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                                    ```python
                                    # Add material specification note with leader
                                    result = await add_note({
                                        "text": "Material: AISI 1018 Steel
                        Hardness: 150-200 HB",
                                        "position_x": 200.0, "position_y": 50.0,
                                        "font_size": 10.0,
                                        "leader_attachment": "Face1"
                                    })

                                    if result["status"] == "success":
                                        note = result["note"]
                                        print(f"Added note at {note['font_size']}pt font size")
                                        # Note provides critical manufacturing information
                                    ```

                                Note:
                                    - Text supports standard annotation symbols and formatting
                                    - Leader attachment improves clarity for specific features
                                    - Font size should comply with drawing standards
                                    - Position carefully to avoid dimension conflicts
        """
        try:
            input_data = _normalize_input(input_data, AddNoteInput)
            result = await adapter.add_drawing_note(
                input_data.text,
                input_data.position_x,
                input_data.position_y,
                input_data.font_size or 0.0,
            )
            if result.is_success:
                data = result.data if isinstance(result.data, dict) else {}
                return {
                    "status": "success",
                    "message": f"Added note: {input_data.text[:30]}",
                    "note": data,
                    "execution_time": result.execution_time,
                }
            return {
                "status": "error",
                "message": f"Failed to add note: {result.error}",
            }

        except Exception as e:
            logger.error(f"Error in add_note tool: {e}")
            return {
                "status": "error",
                "message": f"Failed to add note: {str(e)}",
            }

    @mcp.tool()
    async def create_section_view(input_data: CreateSectionViewInput) -> dict[str, Any]:
        """Create a section view of the current drawing.

        Generates section views that show internal features by cutting through the part along a
        specified section line. Essential for revealing hidden geometry, internal structures,
        and complex assemblies.

        Args:
            input_data (CreateSectionViewInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            ```python
                            # Create vertical section through center of part
                            result = await create_section_view({
                                "section_line_start": (50.0, 0.0),
                                "section_line_end": (50.0, 100.0),
                                "view_position_x": 300.0, "view_position_y": 150.0,
                                "scale": 1.5,
                                "label": "A"
                            })

                            if result["status"] == "success":
                                section = result["section_view"]
                                print(f"Created section {section['label']}-A at {section['scale']}:1")
                                # Section reveals internal features clearly
                            ```

                        Note:
                            - Section line direction determines view orientation
                            - Section views automatically show cut surfaces with hatching
                            - Label follows ANSI/ISO drafting standards (A-A, B-B, etc.)
                            - Essential for showing internal features and assemblies
        """
        try:
            input_data = _normalize_input(input_data, CreateSectionViewInput)
            # A section view needs a section line sketched on a parent
            # view first; this adapter cannot create that sketch, so it says so
            # instead of reporting a view that does not exist.
            return {
                "status": "error",
                "message": (
                    "Section views are not supported: SolidWorks needs a "
                    "section line sketched on a parent view first, which this "
                    "adapter cannot create. Add the section view in the "
                    "SolidWorks UI."
                ),
                "requested": {
                    "section_line": {
                        "start": input_data.section_line_start,
                        "end": input_data.section_line_end,
                    },
                    "label": input_data.label,
                },
            }

        except Exception as e:
            logger.error(f"Error in create_section_view tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    @mcp.tool()
    async def create_detail_view(input_data: CreateDetailViewInput) -> dict[str, Any]:
        """Create a detail view of a specific area.

        Generates magnified detail views of specific regions to show fine features, tight
        tolerances, and intricate geometry that requires enhanced visibility for manufacturing
        and inspection.

        Args:
            input_data (CreateDetailViewInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            ```python
                            # Create 4x detail view of small threaded hole
                            result = await create_detail_view({
                                "center_x": 25.0, "center_y": 15.0,
                                "radius": 8.0,  # 16mm diameter detail area
                                "view_position_x": 250.0, "view_position_y": 300.0,
                                "scale": 4.0,   # 4:1 magnification
                                "label": "A"
                            })

                            if result["status"] == "success":
                                detail = result["detail_view"]
                                print(f"Created detail {detail['label']} at {detail['scale']}:1")
                                # Detail shows thread profile clearly for machining
                            ```

                        Note:
                            - Detail circle size determines what geometry is magnified
                            - Higher scale factors reveal fine features for precision work
                            - Label follows standard drafting conventions (Detail A, etc.)
                            - Essential for communicating tight tolerance requirements
        """
        try:
            input_data = _normalize_input(input_data, CreateDetailViewInput)
            # A detail view needs a detail circle sketched on a parent
            # view first; this adapter cannot create that sketch.
            return {
                "status": "error",
                "message": (
                    "Detail views are not supported: SolidWorks needs a detail "
                    "circle sketched on a parent view first, which this adapter "
                    "cannot create. Add the detail view in the SolidWorks UI."
                ),
                "requested": {
                    "detail_circle": {
                        "center": {"x": input_data.center_x, "y": input_data.center_y},
                        "radius": input_data.radius,
                    },
                    "label": input_data.label,
                },
            }

        except Exception as e:
            logger.error(f"Error in create_detail_view tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    @mcp.tool()
    async def update_sheet_format(input_data: UpdateSheetFormatInput) -> dict[str, Any]:
        """Update the sheet format and title block information.

        Applies drawing templates and updates title block fields with project information,
        revision data, and drawing metadata. Essential for standardized documentation and
        drawing control.

        Args:
            input_data (UpdateSheetFormatInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            ```python
                            # Apply company standard format with project info
                            result = await update_sheet_format({
                                "format_file": "C:/Templates/company_format.slddrt",
                                "sheet_size": "A3",
                                "title": "Mounting Bracket Assembly",
                                "drawn_by": "J. Smith",
                                "checked_by": "M. Johnson",
                                "approved_by": "R. Wilson",
                                "drawing_number": "DWG-001-Rev-A"
                            })

                            if result["status"] == "success":
                                format_info = result["sheet_format"]
                                print(f"Applied {format_info['sheet_size']} format")
                                # Drawing now has proper title block and company branding
                            ```

                        Note:
                            - Format file must exist and be compatible with SolidWorks version
                            - Title block fields support company-specific customization
                            - Sheet size affects drawing layout and scaling decisions
                            - Essential for drawing control and document management systems
        """
        try:
            input_data = _normalize_input(input_data, UpdateSheetFormatInput)
            # Reported nothing real: the sheet was never touched and the
            # title-block values were echoed straight back.
            return {
                "status": "error",
                "message": (
                    "Changing the sheet format is not supported by this "
                    "adapter. Set the sheet format and title block in the "
                    "SolidWorks UI, or apply a drawing template that already "
                    "carries them."
                ),
                "requested": {
                    "format_file": input_data.format_file,
                    "sheet_size": input_data.sheet_size,
                    "title": input_data.title,
                },
            }

        except Exception as e:
            logger.error(f"Error in update_sheet_format tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    @mcp.tool()
    async def auto_dimension_view(input_data: dict[str, Any]) -> dict[str, Any]:
        """Automatically dimension a drawing view.

        Analyzes drawing view geometry and automatically adds common dimensions including
        overall sizes, hole diameters, radii, and critical features. Accelerates drawing
        completion and ensures comprehensive dimensioning coverage.

        Args:
            input_data (dict[str, Any]): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            ```python
                            # Auto-dimension main view with baseline dimensions
                            result = await auto_dimension_view({
                                "view_name": "Front View",
                                "dimension_types": ["linear", "diameter"],
                                "include_baseline": True,
                                "include_centerlines": True
                            })

                            if result["status"] == "success":
                                auto_dims = result["auto_dimensions"]
                                print(f"Added {auto_dims['dimensions_added']} dimensions")
                                print(f"Coverage: {auto_dims['coverage']}")
                                # Drawing now has comprehensive dimensioning
                            ```

                        Note:
                            - Analyzes feature geometry to determine appropriate dimensions
                            - Follows drafting standards for dimension placement
                            - May require manual adjustment for optimal readability
                            - Significantly reduces manual dimensioning time
        """
        try:
            # "Auto dimension" in practice means importing the dimensions the
            # model was built with, rather than inventing new ones.
            all_views = bool(input_data.get("all_views", True))
            result = await adapter.insert_model_dimensions(all_views)
            if result.is_success:
                data = result.data if isinstance(result.data, dict) else {}
                return {
                    "status": "success",
                    "message": (
                        f"Imported {data.get('annotations_inserted', 0)} model "
                        "dimension(s) onto the drawing"
                    ),
                    "auto_dimensions": data,
                    "execution_time": result.execution_time,
                }
            return {
                "status": "error",
                "message": f"Failed to auto-dimension: {result.error}",
            }

        except Exception as e:  # pragma: no cover - defensive guard for future logic
            logger.error(f"Error in auto_dimension_view tool: {e}")
            return {
                "status": "error",
                "message": f"Failed to auto-dimension: {str(e)}",
            }

    @mcp.tool()
    async def check_drawing_standards(input_data: dict[str, Any]) -> dict[str, Any]:
        """Check the current drawing against drafting standards.

        Validates drawing compliance with industry drafting standards including ANSI Y14.5, ISO
        128, and DIN standards. Identifies non-compliance issues and provides recommendations
        for improvement.

        Args:
            input_data (dict[str, Any]): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.

        Example:
                            ```python
                            # Comprehensive ANSI standards check
                            result = await check_drawing_standards({
                                "standard": "ANSI",
                                "check_categories": ["dimensions", "tolerances", "symbols"],
                                "severity_filter": "warning"
                            })

                            if result["status"] == "success":
                                check = result["standards_check"]
                                print(f"Compliance Score: {check['compliance_score']}%")
                                print(f"Warnings: {len(check['warnings'])}")
                                print(f"Errors: {len(check['errors'])}")
                                # Address issues to improve drawing quality
                            ```

                        Note:
                            - Standards compliance ensures drawing acceptance in industry
                            - Regular checking prevents costly revision cycles
                            - Automated validation reduces human error in review process
                            - Essential for quality management and ISO certification
        """
        try:
            # This used to return a 92% compliance score and a list of
            # warnings for a drawing it never opened. A fabricated pass on a
            # standards check is exactly the kind of answer someone might act
            # on, so it now refuses.
            return {
                "status": "error",
                "message": (
                    "Drafting-standards checking is not implemented. The "
                    "previous compliance score and warnings were fabricated "
                    "and did not reflect the drawing. Use SolidWorks' own "
                    "Design Checker for a real result."
                ),
            }

        except Exception as e:  # pragma: no cover - defensive guard for future logic
            logger.error(f"Error in check_drawing_standards tool: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
            }

    @mcp.tool()
    async def create_technical_drawing(
        input_data: DrawingCreationInput,
    ) -> dict[str, Any]:
        """Create a technical drawing from a SolidWorks part or assembly.

        Supports selecting a template, output path, sheet format, scale, and optional auto-
        population of standard views for documentation.

        Args:
            input_data (DrawingCreationInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.
        """
        try:
            if hasattr(adapter, "create_technical_drawing"):
                result = await adapter.create_technical_drawing(input_data.model_dump())
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Technical drawing created successfully",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed to create technical drawing",
                }

            # This reported a drawing at output_path, with a list of views
            # that were never placed, for a file that was never created.
            return {
                "status": "error",
                "message": (
                    "Cannot create a technical drawing: this adapter does not "
                    "implement create_technical_drawing, so no drawing file "
                    "was produced."
                ),
            }
        except Exception as e:
            logger.error(f"Error in create_technical_drawing tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def add_drawing_view(input_data: DrawingViewInput) -> dict[str, Any]:
        """Add, update, or remove a drawing view in an existing drawing.

        Supports configuring the target drawing, view type, parent view, scale, and placement
        coordinates for common drawing view workflows.

        Args:
            input_data (DrawingViewInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.
        """
        try:
            if hasattr(adapter, "add_drawing_view"):
                result = await adapter.add_drawing_view(input_data.model_dump())
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Drawing view added successfully",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed to add drawing view",
                }

            return {
                "status": "error",
                "message": (
                    f"Cannot add the {input_data.view_type} view "
                    f"'{input_data.view_name}': this adapter does not "
                    "implement add_drawing_view, so the drawing is unchanged."
                ),
            }
        except Exception as e:
            logger.error(f"Error in add_drawing_view tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def add_annotation(input_data: AnnotationInput) -> dict[str, Any]:
        """Add an annotation such as a note, balloon, or surface symbol.

        Places annotation text in a drawing with optional font size, leader attachment, and
        title-block style metadata fields.

        Args:
            input_data (AnnotationInput): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.
        """
        try:
            if hasattr(adapter, "add_annotation"):
                result = await adapter.add_annotation(input_data.model_dump())
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Annotation added successfully",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed to add annotation",
                }

            return {
                "status": "error",
                "message": (
                    "Cannot add the annotation: this adapter does not "
                    "implement add_annotation, so nothing was placed on the "
                    "drawing."
                ),
            }
        except Exception as e:
            logger.error(f"Error in add_annotation tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def update_title_block(input_data: dict[str, Any]) -> dict[str, Any]:
        """Update title block fields for the active drawing.

        Applies drawing metadata such as title, drawing number, and approval fields to keep
        documentation aligned with standards.

        Args:
            input_data (dict[str, Any]): The input data value.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.
        """
        try:
            if hasattr(adapter, "update_title_block"):
                result = await adapter.update_title_block(input_data)
                if result.is_success:
                    return {
                        "status": "success",
                        "message": "Title block updated successfully",
                        "data": result.data,
                        "execution_time": result.execution_time,
                    }
                return {
                    "status": "error",
                    "message": result.error or "Failed to update title block",
                }

            return {
                "status": "error",
                "message": (
                    "Cannot update the title block: this adapter does not "
                    "implement update_title_block, so no fields were changed."
                ),
            }
        except Exception as e:
            logger.error(f"Error in update_title_block tool: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    tool_count = 8  # Number of tools registered
    return tool_count
