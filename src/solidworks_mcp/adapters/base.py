"""Base adapter interface for SolidWorks integration.

Defines the common interface that all SolidWorks adapters must implement, following the
adapter pattern from the original TypeScript implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class AdapterHealth(BaseModel):
    """Health status information for adapters.

    Attributes:
        average_response_time (float): The average response time value.
        connection_status (str): The connection status value.
        error_count (int): The error count value.
        healthy (bool): The healthy value.
        last_check (datetime): The last check value.
        metrics (dict[str, Any] | None): The metrics value.
        success_count (int): The success count value.
    """

    healthy: bool
    last_check: datetime
    error_count: int
    success_count: int
    average_response_time: float
    connection_status: str
    metrics: dict[str, Any] | None = None

    def __getitem__(self, key: str) -> Any:
        """Build internal getitem.

        Args:
            key (str): The key value.

        Returns:
            Any: The result produced by the operation.
        """
        if key == "status":
            return "healthy" if self.healthy else "unhealthy"
        if key == "connected":
            return self.connection_status == "connected"
        if key == "adapter_type":
            return (self.metrics or {}).get("adapter_type")
        if key == "version":
            return (self.metrics or {}).get("version", "mock-1.0")
        if key == "uptime":
            return (self.metrics or {}).get("uptime", 0.0)
        return self.model_dump().get(key)

    def __contains__(self, key: str) -> bool:
        """Build internal contains.

        Args:
            key (str): The key value.

        Returns:
            bool: True if contains, otherwise False.
        """
        legacy_keys = {"status", "connected", "adapter_type", "version", "uptime"}
        if key in legacy_keys:
            return True
        return key in self.model_dump()


class AdapterResultStatus(StrEnum):
    """Result status for adapter operations.

    Attributes:
        ERROR (Any): The error value.
        SUCCESS (Any): The success value.
        TIMEOUT (Any): The timeout value.
        WARNING (Any): The warning value.
    """

    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    TIMEOUT = "timeout"


@dataclass
class AdapterResult(Generic[T]):
    """Result wrapper for adapter operations.

    Attributes:
        data (T | None): The data value.
        error (str | None): The error value.
        execution_time (float | None): The execution time value.
        metadata (dict[str, Any] | None): The metadata value.
        status (AdapterResultStatus): The status value.
    """

    status: AdapterResultStatus
    data: T | None = None
    error: str | None = None
    execution_time: float | None = None
    metadata: dict[str, Any] | None = None

    @property
    def is_success(self) -> bool:
        """Check if operation was successful.

        Returns:
            bool: True if success, otherwise False.
        """
        return self.status == AdapterResultStatus.SUCCESS

    @property
    def is_error(self) -> bool:
        """Check if operation had an error.

        Returns:
            bool: True if error, otherwise False.
        """
        return self.status == AdapterResultStatus.ERROR


# SolidWorks data models
class SolidWorksModel(BaseModel):
    """SolidWorks model information.

    Attributes:
        configuration (str | None): The configuration value.
        is_active (bool): The is active value.
        name (str): The name value.
        path (str): The path value.
        properties (dict[str, Any] | None): The properties value.
        type (str): The type value.
    """

    path: str
    name: str
    type: str  # "Part", "Assembly", "Drawing"
    is_active: bool
    configuration: str | None = None
    properties: dict[str, Any] | None = None

    def __getitem__(self, key: str) -> Any:
        """Build internal getitem.

        Args:
            key (str): The key value.

        Returns:
            Any: The result produced by the operation.
        """
        if key == "title":
            return self.name
        if key == "units":
            return (self.properties or {}).get("units")
        return self.model_dump().get(key)


class SolidWorksFeature(BaseModel):
    """SolidWorks feature information.

    Attributes:
        id (str | None): The id value.
        name (str): The name value.
        parameters (dict[str, Any] | None): The parameters value.
        parent (str | None): The parent value.
        properties (dict[str, Any] | None): The properties value.
        type (str): The type value.
    """

    name: str
    type: str
    id: str | None = None
    parent: str | None = None
    properties: dict[str, Any] | None = None
    parameters: dict[str, Any] | None = None

    def __getitem__(self, key: str) -> Any:
        """Build internal getitem.

        Args:
            key (str): The key value.

        Returns:
            Any: The result produced by the operation.
        """
        if self.parameters and key in self.parameters:
            return self.parameters.get(key)
        return self.model_dump().get(key)


class ExtrusionParameters(BaseModel):
    """Parameters for extrusion operations.

    Attributes:
        auto_select (bool): The auto select value.
        both_directions (bool): The both directions value.
        depth (float): The depth value.
        draft_angle (float): The draft angle value.
        end_condition (str): The end condition value.
        feature_scope (bool): The feature scope value.
        merge_result (bool): The merge result value.
        reverse_direction (bool): The reverse direction value.
        thin_feature (bool): The thin feature value.
        thin_thickness (float | None): The thin thickness value.
        up_to_surface (str | None): The up to surface value.
    """

    depth: float
    draft_angle: float = 0.0
    reverse_direction: bool = False
    both_directions: bool = False
    thin_feature: bool = False
    thin_thickness: float | None = None
    auto_fillet_corners: bool = False
    fillet_corners_radius: float = 0.0
    end_condition: str = "Blind"
    up_to_surface: str | None = None
    merge_result: bool = True
    feature_scope: bool = False
    auto_select: bool = True


class RevolveParameters(BaseModel):
    """Parameters for revolve operations.

    Attributes:
        angle (float): The angle value.
        both_directions (bool): The both directions value.
        merge_result (bool): The merge result value.
        reverse_direction (bool): The reverse direction value.
        thin_feature (bool): The thin feature value.
        thin_thickness (float | None): The thin thickness value.
    """

    angle: float
    reverse_direction: bool = False
    both_directions: bool = False
    thin_feature: bool = False
    thin_thickness: float | None = None
    merge_result: bool = True


class SweepParameters(BaseModel):
    """Parameters for sweep operations.

    Attributes:
        merge_result (bool): The merge result value.
        path (str): The path value.
        twist_along_path (bool): The twist along path value.
        twist_angle (float): The twist angle value.
    """

    path: str
    twist_along_path: bool = False
    twist_angle: float = 0.0
    merge_result: bool = True


class LoftParameters(BaseModel):
    """Parameters for loft operations.

    Attributes:
        end_tangent (str | None): The end tangent value.
        guide_curves (list[str] | None): The guide curves value.
        merge_result (bool): The merge result value.
        profiles (list[str]): The profiles value.
        start_tangent (str | None): The start tangent value.
    """

    profiles: list[str]
    guide_curves: list[str] | None = None
    start_tangent: str | None = None
    end_tangent: str | None = None
    merge_result: bool = True


class MassProperties(BaseModel):
    """Mass properties information.

    Attributes:
        center_of_mass (list[float]): The center of mass value.
        mass (float): The mass value.
        moments_of_inertia (dict[str, float]): The moments of inertia value.
        principal_axes (dict[str, list[float]] | None): The principal axes value.
        surface_area (float): The surface area value.
        volume (float): The volume value.
    """

    volume: float
    surface_area: float
    mass: float
    center_of_mass: list[float]  # [x, y, z]
    moments_of_inertia: dict[str, float]
    principal_axes: dict[str, list[float]] | None = None


class SolidWorksAdapter(ABC):
    """Base adapter interface for SolidWorks integration.

    Args:
        config (object | None): Configuration values for the operation. Defaults to None.

    Attributes:
        _metrics (Any): The metrics value.
        config (Any): The config value.
        config_dict (Any): The config dict value.
    """

    def __init__(self, config: object | None = None):
        """Initialize adapter with configuration.

        Args:
            config (object | None): Configuration values for the operation. Defaults to None.
        """
        if config is None:
            normalized_config: dict[str, Any] = {}
        elif isinstance(config, Mapping):
            normalized_config = dict(config)
        elif hasattr(config, "model_dump"):
            normalized_config = dict(config.model_dump())
        else:
            normalized_config = {}

        # Preserve original config object for compatibility with tests and
        # call sites that compare object identity/equality.
        self.config = config
        # Keep a normalized mapping for adapter internals.
        self.config_dict = normalized_config
        self._metrics = {
            "operations_count": 0,
            "errors_count": 0,
            "average_response_time": 0.0,
        }
        # SolidWorks-as-Code session logging. Set soc_session_id to enable
        # automatic ToolCallRecord writes for every adapter operation.
        self.soc_session_id: str | None = None
        self.soc_db_path: Path | None = None

    # Connection Management
    @abstractmethod
    async def connect(self) -> None:
        """Connect to SolidWorks application.

        Returns:
            None: None.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from SolidWorks application.

        Returns:
            None: None.
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to SolidWorks.

        Returns:
            bool: True if connected, otherwise False.
        """
        pass

    @abstractmethod
    async def health_check(self) -> AdapterHealth:
        """Get adapter health status.

        Returns:
            AdapterHealth: The result produced by the operation.
        """
        pass

    # Model Operations
    @abstractmethod
    async def open_model(self, file_path: str) -> AdapterResult[SolidWorksModel]:
        """Open a SolidWorks model (part, assembly, or drawing).

        Args:
            file_path (str): Path to the target file.

        Returns:
            AdapterResult[SolidWorksModel]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def close_model(self, save: bool = False) -> AdapterResult[None]:
        """Close the current model.

        Args:
            save (bool): The save value. Defaults to False.

        Returns:
            AdapterResult[None]: The result produced by the operation.
        """
        pass

    async def save_file(self, file_path: str | None = None) -> AdapterResult[Any]:
        """Save the active model to the existing path or the provided path.

        Args:
            file_path (str | None): Path to the target file. Defaults to None.

        Returns:
            AdapterResult[Any]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="save_file is not implemented by this adapter",
        )

    @abstractmethod
    async def get_model_info(self) -> AdapterResult[dict[str, Any]]:
        """Get metadata for the active model.

        Returns:
            AdapterResult[dict[str, Any]]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def list_features(
        self, include_suppressed: bool = False
    ) -> AdapterResult[list[dict[str, Any]]]:
        """List model features from the feature tree.

        Args:
            include_suppressed (bool): The include suppressed value. Defaults to False.

        Returns:
            AdapterResult[list[dict[str, Any]]]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def list_configurations(self) -> AdapterResult[list[str]]:
        """List configuration names for the active model.

        Returns:
            AdapterResult[list[str]]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def create_part(
        self, name: str | None = None, units: str | None = None
    ) -> AdapterResult[SolidWorksModel]:
        """Create a new part document.

        Args:
            name (str | None): The name value. Defaults to None.
            units (str | None): The units value. Defaults to None.

        Returns:
            AdapterResult[SolidWorksModel]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def create_assembly(
        self, name: str | None = None
    ) -> AdapterResult[SolidWorksModel]:
        """Create a new assembly document.

        Args:
            name (str | None): The name value. Defaults to None.

        Returns:
            AdapterResult[SolidWorksModel]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def create_drawing(
        self, name: str | None = None
    ) -> AdapterResult[SolidWorksModel]:
        """Create a new drawing document.

        Args:
            name (str | None): The name value. Defaults to None.

        Returns:
            AdapterResult[SolidWorksModel]: The result produced by the operation.
        """
        pass

    # Feature Operations
    @abstractmethod
    async def create_extrusion(
        self, params: ExtrusionParameters
    ) -> AdapterResult[SolidWorksFeature]:
        """Create an extrusion feature.

        Args:
            params (ExtrusionParameters): The params value.

        Returns:
            AdapterResult[SolidWorksFeature]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def create_revolve(
        self, params: RevolveParameters
    ) -> AdapterResult[SolidWorksFeature]:
        """Create a revolve feature.

        Args:
            params (RevolveParameters): The params value.

        Returns:
            AdapterResult[SolidWorksFeature]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def create_sweep(
        self, params: SweepParameters
    ) -> AdapterResult[SolidWorksFeature]:
        """Create a sweep feature.

        Args:
            params (SweepParameters): The params value.

        Returns:
            AdapterResult[SolidWorksFeature]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def create_loft(
        self, params: LoftParameters
    ) -> AdapterResult[SolidWorksFeature]:
        """Create a loft feature.

        Args:
            params (LoftParameters): The params value.

        Returns:
            AdapterResult[SolidWorksFeature]: The result produced by the operation.
        """
        pass

    # Sketch Operations
    @abstractmethod
    async def create_sketch(self, plane: str) -> AdapterResult[str]:
        """Create a new sketch on the specified plane.

        Args:
            plane (str): The plane value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def add_line(
        self, x1: float, y1: float, x2: float, y2: float
    ) -> AdapterResult[str]:
        """Add a line to the current sketch.

        Args:
            x1 (float): The x1 value.
            y1 (float): The y1 value.
            x2 (float): The x2 value.
            y2 (float): The y2 value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        pass

    async def add_polyline(
        self, points: list[dict[str, float]], closed: bool = False
    ) -> "AdapterResult[Any]":
        """Add a connected chain of line segments in one call.

        Draws a segment between each consecutive pair of ``points`` (and a
        closing segment when ``closed``), collapsing N ``add_line`` round-trips
        into a single COM operation.

        Args:
            points (list[dict[str, float]]): Ordered ``{"x": mm, "y": mm}`` verts.
            closed (bool): Close the contour (last point back to first).

        Returns:
            AdapterResult: ``{"segments": n, "closed": bool, "ids": [...]}`` or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_polyline is not implemented by this adapter",
        )

    @abstractmethod
    async def add_circle(
        self, center_x: float, center_y: float, radius: float
    ) -> AdapterResult[str]:
        """Add a circle to the current sketch.

        Args:
            center_x (float): The center x value.
            center_y (float): The center y value.
            radius (float): The radius value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def add_rectangle(
        self, x1: float, y1: float, x2: float, y2: float
    ) -> AdapterResult[str]:
        """Add a rectangle to the current sketch.

        Args:
            x1 (float): The x1 value.
            y1 (float): The y1 value.
            x2 (float): The x2 value.
            y2 (float): The y2 value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        pass

    async def add_arc(
        self,
        center_x: float,
        center_y: float,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
    ) -> AdapterResult[str]:
        """Add an arc to the current sketch.

        Args:
            center_x (float): The center x value.
            center_y (float): The center y value.
            start_x (float): The start x value.
            start_y (float): The start y value.
            end_x (float): The end x value.
            end_y (float): The end y value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_arc is not implemented by this adapter",
        )

    async def add_spline(self, points: list[dict[str, float]]) -> AdapterResult[str]:
        """Add a spline through the provided points.

        Args:
            points (list[dict[str, float]]): The points value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_spline is not implemented by this adapter",
        )

    async def add_centerline(
        self, x1: float, y1: float, x2: float, y2: float
    ) -> AdapterResult[str]:
        """Add a centerline to the current sketch.

        Args:
            x1 (float): The x1 value.
            y1 (float): The y1 value.
            x2 (float): The x2 value.
            y2 (float): The y2 value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_centerline is not implemented by this adapter",
        )

    async def add_polygon(
        self, center_x: float, center_y: float, radius: float, sides: int
    ) -> AdapterResult[str]:
        """Add a regular polygon to the current sketch.

        Args:
            center_x (float): The center x value.
            center_y (float): The center y value.
            radius (float): The radius value.
            sides (int): The sides value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_polygon is not implemented by this adapter",
        )

    async def add_ellipse(
        self,
        center_x: float,
        center_y: float,
        major_axis: float,
        minor_axis: float,
    ) -> AdapterResult[str]:
        """Add an ellipse to the current sketch.

        Args:
            center_x (float): The center x value.
            center_y (float): The center y value.
            major_axis (float): The major axis value.
            minor_axis (float): The minor axis value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_ellipse is not implemented by this adapter",
        )

    async def add_sketch_constraint(
        self,
        entity1: str,
        entity2: str | None,
        relation_type: str,
        entity3: str | None = None,
    ) -> AdapterResult[str]:
        """Apply a geometric constraint between sketch entities.

        Args:
            entity1 (str): The entity1 value.
            entity2 (str | None): The entity2 value.
            relation_type (str): The relation type value.
            entity3 (str | None): Third entity ID — only used by the
                ``symmetric`` relation (the centerline of symmetry). All
                other relation types reject a non-null ``entity3``.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_sketch_constraint is not implemented by this adapter",
        )

    async def add_sketch_dimension(
        self,
        entity1: str,
        entity2: str | None,
        dimension_type: str,
        value: float,
    ) -> AdapterResult[str]:
        """Add a sketch dimension.

        Args:
            entity1 (str): The entity1 value.
            entity2 (str | None): The entity2 value.
            dimension_type (str): The dimension type value.
            value (float): The value value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_sketch_dimension is not implemented by this adapter",
        )

    async def check_sketch_fully_defined(
        self, sketch_name: str | None = None
    ) -> AdapterResult[dict[str, Any]]:
        """Check whether a sketch is fully defined.

        Args:
            sketch_name (str | None): Optional sketch name to inspect. Defaults to None.

        Returns:
            AdapterResult[dict[str, Any]]: Definition status payload.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="check_sketch_fully_defined is not implemented by this adapter",
        )

    async def sketch_linear_pattern(
        self,
        entities: list[str],
        direction_x: float,
        direction_y: float,
        spacing: float,
        count: int,
    ) -> AdapterResult[str]:
        """Create a linear pattern of sketch entities.

        Args:
            entities (list[str]): The entities value.
            direction_x (float): The direction x value.
            direction_y (float): The direction y value.
            spacing (float): The spacing value.
            count (int): The count value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="sketch_linear_pattern is not implemented by this adapter",
        )

    async def sketch_circular_pattern(
        self,
        entities: list[str],
        angle: float,
        count: int,
    ) -> AdapterResult[str]:
        """Create a circular pattern of sketch entities around the sketch origin.

        The rotation axis is always the sketch origin — SW's
        ``CreateCircularSketchStepAndRepeat`` has no pattern-centre
        parameter and derives the axis from the seed's geometry. Place
        the seed entity at the desired radius from the origin.

        Args:
            entities (list[str]): The entities value.
            angle (float): The angle value.
            count (int): The count value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="sketch_circular_pattern is not implemented by this adapter",
        )

    async def sketch_mirror(
        self, entities: list[str], mirror_line: str
    ) -> AdapterResult[str]:
        """Mirror sketch entities about a mirror line.

        Args:
            entities (list[str]): The entities value.
            mirror_line (str): The mirror line value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="sketch_mirror is not implemented by this adapter",
        )

    async def sketch_offset(
        self,
        entities: list[str],
        offset_distance: float,
        reverse_direction: bool,
    ) -> AdapterResult[str]:
        """Offset sketch entities.

        Args:
            entities (list[str]): The entities value.
            offset_distance (float): The offset distance value.
            reverse_direction (bool): The reverse direction value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="sketch_offset is not implemented by this adapter",
        )

    async def add_sketch_circle(
        self,
        center_x: float,
        center_y: float,
        radius: float,
        construction: bool = False,
    ) -> AdapterResult[str]:
        """Alias for add_circle used by some tool flows.

        Args:
            center_x (float): The center x value.
            center_y (float): The center y value.
            radius (float): The radius value.
            construction (bool): The construction value. Defaults to False.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return await self.add_circle(center_x, center_y, radius)

    async def create_cut(self, sketch_name: str, depth: float) -> AdapterResult[str]:
        """Create a cut feature from an existing sketch.

        Args:
            sketch_name (str): The sketch name value.
            depth (float): The depth value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_cut is not implemented by this adapter",
        )

    async def create_cut_extrude(
        self, params: "ExtrusionParameters"
    ) -> "AdapterResult[Any]":
        """Create a cut-extrude feature from the active sketch.

        Cuts material from the current solid body using the active sketch profile.
        Equivalent to SolidWorks Insert > Cut > Extrude.

        Args:
            params (ExtrusionParameters): Depth and direction parameters.

        Returns:
            AdapterResult: Feature result or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_cut_extrude is not implemented by this adapter",
        )

    async def add_fillet(
        self, radius: float, edge_names: list[str]
    ) -> "AdapterResult[Any]":
        """Add a fillet feature to selected edges.

        Rounds the selected edges of the current solid body with the given radius.

        Args:
            radius (float): Fillet radius in millimeters.
            edge_names (list[str]): List of edge names to fillet.

        Returns:
            AdapterResult: Feature result or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_fillet is not implemented by this adapter",
        )

    async def delete_feature(self, name: str) -> "AdapterResult[Any]":
        """Delete a named feature (or sketch) from the active model.

        Equivalent to selecting the feature and pressing Delete in SolidWorks.
        Child features that depend on it are removed with it.

        Args:
            name (str): Feature/sketch name, e.g. ``"Boss-Extrude3"``.

        Returns:
            AdapterResult: ``{"deleted": name}`` on success, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="delete_feature is not implemented by this adapter",
        )

    async def suppress_feature(
        self, name: str, suppress: bool = True
    ) -> "AdapterResult[Any]":
        """Suppress or unsuppress a named feature (reversible, non-destructive).

        Args:
            name (str): Feature name to toggle.
            suppress (bool): ``True`` to suppress, ``False`` to unsuppress.

        Returns:
            AdapterResult: Action summary or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="suppress_feature is not implemented by this adapter",
        )

    async def undo(self, count: int = 1) -> "AdapterResult[Any]":
        """Undo the last ``count`` operations in the active model.

        Args:
            count (int): Number of operations to undo (>= 1).

        Returns:
            AdapterResult: ``{"undone": count}`` on success, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="undo is not implemented by this adapter",
        )

    async def create_reference_plane(
        self,
        reference: str,
        offset: float = 0.0,
        angle: float = 0.0,
        flip: bool = False,
    ) -> "AdapterResult[Any]":
        """Create a reference plane offset from (or angled to) an existing plane.

        Args:
            reference (str): Reference plane/face name, e.g. ``"Front Plane"``.
            offset (float): Offset distance in millimetres.
            angle (float): Angle in degrees (used instead of offset when non-zero).
            flip (bool): Reverse the offset/angle direction.

        Returns:
            AdapterResult: New plane name and parameters, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_reference_plane is not implemented by this adapter",
        )

    async def mirror_feature(
        self,
        features: list[str],
        mirror_plane: str,
        merge: bool = True,
    ) -> "AdapterResult[Any]":
        """Mirror one or more solid features about a plane.

        Args:
            features (list[str]): Feature names to mirror.
            mirror_plane (str): Mirror plane name, e.g. ``"Front Plane"``.
            merge (bool): Merge the mirrored result into the existing body.

        Returns:
            AdapterResult: New mirror feature details, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="mirror_feature is not implemented by this adapter",
        )

    async def create_shell(
        self,
        thickness: float,
        remove_faces: list[int] | None = None,
        outward: bool = False,
    ) -> "AdapterResult[Any]":
        """Hollow out the solid, optionally opening one or more faces.

        Args:
            thickness (float): Wall thickness in millimetres.
            remove_faces (list[int] | None): Indices of faces to open.
            outward (bool): Thicken outward instead of inward.

        Returns:
            AdapterResult: Shell details, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_shell is not implemented by this adapter",
        )

    async def pattern_linear(
        self,
        features: list[str],
        direction: str = "x",
        count: int = 2,
        spacing: float = 10.0,
        direction_edge: int | None = None,
    ) -> "AdapterResult[Any]":
        """Repeat features along a model axis.

        Args:
            features (list[str]): Feature names to repeat.
            direction (str): Axis with optional sign, e.g. ``"x"``, ``"-y"``.
            count (int): Instances including the original (>= 2).
            spacing (float): Distance between instances in millimetres.
            direction_edge (int | None): Explicit edge index override.

        Returns:
            AdapterResult: Pattern details, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="pattern_linear is not implemented by this adapter",
        )

    async def create_axis(self, reference: str = "z") -> "AdapterResult[Any]":
        """Create a reference axis along a principal model direction.

        Args:
            reference (str): ``"x"``, ``"y"`` or ``"z"``. Defaults to ``"z"``.

        Returns:
            AdapterResult: The new axis's feature name, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_axis is not implemented by this adapter",
        )

    async def pattern_circular(
        self,
        features: list[str],
        axis: str = "z",
        count: int = 4,
        angle: float = 360.0,
        equal_spacing: bool = True,
    ) -> "AdapterResult[Any]":
        """Repeat features around an axis.

        Args:
            features (list[str]): Names of features to repeat.
            axis (str): Axis feature name, or ``"x"``/``"y"``/``"z"``.
            count (int): Total instances including the original.
            angle (float): Degrees of sweep.
            equal_spacing (bool): Distribute instances evenly across ``angle``.

        Returns:
            AdapterResult: Pattern details, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="pattern_circular is not implemented by this adapter",
        )

    async def add_draft(
        self,
        angle: float,
        neutral_face: int = 0,
        draft_faces: list[int] | None = None,
        outward: bool = False,
    ) -> "AdapterResult[Any]":
        """Taper faces by a draft angle.

        Args:
            angle (float): Draft angle in degrees.
            neutral_face (int): Index of the face the draft is measured from.
            draft_faces (list[int] | None): Indices of the faces to taper.
            outward (bool): Taper outward instead of inward.

        Returns:
            AdapterResult: Draft details, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_draft is not implemented by this adapter",
        )

    async def move_body(
        self,
        body: int = 0,
        dx: float = 0.0,
        dy: float = 0.0,
        dz: float = 0.0,
        copy: bool = False,
        copies: int = 1,
    ) -> "AdapterResult[Any]":
        """Translate or copy a solid body.

        Args:
            body (int): Body index.
            dx (float): X offset in millimetres.
            dy (float): Y offset in millimetres.
            dz (float): Z offset in millimetres.
            copy (bool): Leave the original and move a copy.
            copies (int): Number of copies when ``copy`` is set.

        Returns:
            AdapterResult: Move details, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="move_body is not implemented by this adapter",
        )

    async def delete_body(
        self, bodies: list[int] | None = None
    ) -> "AdapterResult[Any]":
        """Delete solid bodies from a multibody part.

        Args:
            bodies (list[int] | None): Body indices to delete.

        Returns:
            AdapterResult: Remaining body count, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="delete_body is not implemented by this adapter",
        )

    async def delete_face(
        self, faces: list[int] | None = None
    ) -> "AdapterResult[Any]":
        """Remove faces from a solid, healing the opening.

        Args:
            faces (list[int] | None): Face indices to remove.

        Returns:
            AdapterResult: Face counts before and after, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="delete_face is not implemented by this adapter",
        )

    async def scale_model(
        self, factor: float = 1.0, factor_y: float = 0.0, factor_z: float = 0.0
    ) -> "AdapterResult[Any]":
        """Scale the model about its centroid.

        Args:
            factor (float): X factor, and all axes when uniform.
            factor_y (float): Y factor; ``0`` means uniform.
            factor_z (float): Z factor; ``0`` means uniform.

        Returns:
            AdapterResult: Factors applied and the volume ratio, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="scale_model is not implemented by this adapter",
        )

    async def set_material(
        self, name: str, database: str | None = None
    ) -> "AdapterResult[Any]":
        """Assign a material to the active part.

        Args:
            name (str): Material name as it appears in the library.
            database (str | None): Path to a ``.sldmat`` file.

        Returns:
            AdapterResult: The material assigned afterwards, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="set_material is not implemented by this adapter",
        )

    async def add_drawing_view(self, model_path: str, orientation: str = "front", x: float = 100.0, y: float = 150.0, scale: float = 0.0) -> "AdapterResult[Any]":
        """Place a view of a model on the active drawing sheet.

        Returns:
            AdapterResult: Operation payload, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_drawing_view is not implemented by this adapter",
        )

    async def create_standard_views(self, model_path: str, third_angle: bool = True) -> "AdapterResult[Any]":
        """Drop the three standard views onto the active drawing sheet.

        Returns:
            AdapterResult: Operation payload, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_standard_views is not implemented by this adapter",
        )

    async def add_drawing_note(self, text: str, x: float = 100.0, y: float = 50.0, font_size: float = 0.0) -> "AdapterResult[Any]":
        """Place a text note on the active drawing sheet.

        Returns:
            AdapterResult: Operation payload, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_drawing_note is not implemented by this adapter",
        )

    async def insert_model_dimensions(self, all_views: bool = True) -> "AdapterResult[Any]":
        """Import the model's dimensions onto the drawing views.

        Returns:
            AdapterResult: Operation payload, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="insert_model_dimensions is not implemented by this adapter",
        )

    async def list_drawing_views(self) -> "AdapterResult[Any]":
        """List the views on the active drawing.

        Returns:
            AdapterResult: Operation payload, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="list_drawing_views is not implemented by this adapter",
        )

    async def get_bounding_box(self) -> "AdapterResult[Any]":
        """Measure the axis-aligned bounding box of the model's solid bodies.

        Returns:
            AdapterResult: Min/max corners and per-axis dimensions in mm.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="get_bounding_box is not implemented by this adapter",
        )

    async def check_interference(
        self, params: dict[str, Any] | None = None
    ) -> "AdapterResult[Any]":
        """Detect interfering components in the active assembly.

        Args:
            params (dict[str, Any] | None): Detection options.

        Returns:
            AdapterResult: Interference count and component pairs, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="check_interference is not implemented by this adapter",
        )

    async def get_material_properties(self) -> "AdapterResult[Any]":
        """Read the material assigned to the active model.

        Returns:
            AdapterResult: Material name and derived density, or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="get_material_properties is not implemented by this adapter",
        )

    @abstractmethod
    async def exit_sketch(self) -> AdapterResult[None]:
        """Exit sketch editing mode.

        Returns:
            AdapterResult[None]: The result produced by the operation.
        """
        pass

    # Analysis Operations
    @abstractmethod
    async def get_mass_properties(self) -> AdapterResult[MassProperties]:
        """Get mass properties of the current model.

        Returns:
            AdapterResult[MassProperties]: The result produced by the operation.
        """
        pass

    # Export Operations
    @abstractmethod
    async def export_image(self, payload: dict) -> AdapterResult[dict]:
        """Export a viewport screenshot (PNG/JPG) of the current model.

        Payload keys: file_path (str): Absolute output path. width (int): Image width in pixels.
        height (int): Image height in pixels. view_orientation (str): One of "isometric",
        "front", "top", "right", "back", "bottom", "current".

        Args:
            payload (dict): The payload value.

        Returns:
            AdapterResult[dict]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def export_file(
        self, file_path: str, format_type: str
    ) -> AdapterResult[None]:
        """Export the current model to a file.

        Args:
            file_path (str): Path to the target file.
            format_type (str): The format type value.

        Returns:
            AdapterResult[None]: The result produced by the operation.
        """
        pass

    # Dimension Operations
    @abstractmethod
    async def get_dimension(self, name: str) -> AdapterResult[float]:
        """Get the value of a dimension.

        Args:
            name (str): The name value.

        Returns:
            AdapterResult[float]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def set_dimension(self, name: str, value: float) -> AdapterResult[None]:
        """Set the value of a dimension.

        Args:
            name (str): The name value.
            value (float): The value value.

        Returns:
            AdapterResult[None]: The result produced by the operation.
        """
        pass

    # Utility Methods
    def update_metrics(self, operation_time: float, success: bool) -> None:
        """Update adapter metrics.

        Args:
            operation_time (float): The operation time value.
            success (bool): The success value.

        Returns:
            None: None.
        """
        self._metrics["operations_count"] += 1
        if not success:
            self._metrics["errors_count"] += 1

        # Update average response time
        current_avg = self._metrics["average_response_time"]
        count = self._metrics["operations_count"]
        self._metrics["average_response_time"] = (
            current_avg * (count - 1) + operation_time
        ) / count

    def get_metrics(self) -> dict[str, Any]:
        """Get adapter metrics.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.
        """
        return self._metrics.copy()
