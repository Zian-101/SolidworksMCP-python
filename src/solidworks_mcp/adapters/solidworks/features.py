"""Feature-domain mixin for PyWin32 SolidWorks operations."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast

from ..base import (
    AdapterResult,
    AdapterResultStatus,
    ExtrusionParameters,
    LoftParameters,
    RevolveParameters,
    SolidWorksFeature,
    SweepParameters,
)


class SolidWorksFeaturesMixin:
    """Expose SolidWorks feature methods via mixin-local implementation helpers."""

    async def create_extrusion(
        self, params: ExtrusionParameters
    ) -> AdapterResult[SolidWorksFeature]:
        return _create_extrusion_impl(self, params)

    async def create_revolve(
        self, params: RevolveParameters
    ) -> AdapterResult[SolidWorksFeature]:
        return _create_revolve_impl(self, params)

    async def create_sweep(
        self, params: SweepParameters
    ) -> AdapterResult[SolidWorksFeature]:
        return _create_sweep_impl(self, params)

    async def create_loft(
        self, params: LoftParameters
    ) -> AdapterResult[SolidWorksFeature]:
        return _create_loft_impl(self, params)

    async def create_cut_extrude(
        self, params: ExtrusionParameters
    ) -> AdapterResult[SolidWorksFeature]:
        return _create_cut_extrude_impl(self, params)

    async def add_fillet(
        self, radius: float, edge_names: list[str]
    ) -> AdapterResult[SolidWorksFeature]:
        return _add_fillet_impl(self, radius, edge_names)

    async def add_chamfer(
        self, distance: float, edge_names: list[str]
    ) -> AdapterResult[SolidWorksFeature]:
        return _add_chamfer_impl(self, distance, edge_names)

    async def delete_feature(self, name: str) -> AdapterResult[dict[str, Any]]:
        return _delete_feature_impl(self, name)

    async def suppress_feature(
        self, name: str, suppress: bool = True
    ) -> AdapterResult[dict[str, Any]]:
        return _suppress_feature_impl(self, name, suppress)

    async def undo(self, count: int = 1) -> AdapterResult[dict[str, Any]]:
        return _undo_impl(self, count)

    async def create_reference_plane(
        self,
        reference: str,
        offset: float = 0.0,
        angle: float = 0.0,
        flip: bool = False,
    ) -> AdapterResult[dict[str, Any]]:
        return _create_reference_plane_impl(self, reference, offset, angle, flip)

    async def mirror_feature(
        self,
        features: list[str],
        mirror_plane: str,
        merge: bool = True,
    ) -> AdapterResult[dict[str, Any]]:
        return _mirror_feature_impl(self, features, mirror_plane, merge)

    async def create_shell(
        self,
        thickness: float,
        remove_faces: list[int] | None = None,
        outward: bool = False,
    ) -> AdapterResult[dict[str, Any]]:
        return _create_shell_impl(self, thickness, remove_faces, outward)

    async def pattern_linear(
        self,
        features: list[str],
        direction: str = "x",
        count: int = 2,
        spacing: float = 10.0,
        direction_edge: int | None = None,
    ) -> AdapterResult[dict[str, Any]]:
        return _pattern_linear_impl(
            self, features, direction, count, spacing, direction_edge
        )

    async def create_axis(self, reference: str = "z") -> AdapterResult[dict[str, Any]]:
        return _create_axis_impl(self, reference)

    async def add_draft(
        self,
        angle: float,
        neutral_face: int = 0,
        draft_faces: list[int] | None = None,
        outward: bool = False,
    ) -> AdapterResult[dict[str, Any]]:
        return _add_draft_impl(self, angle, neutral_face, draft_faces or [], outward)

    async def move_body(
        self,
        body: int = 0,
        dx: float = 0.0,
        dy: float = 0.0,
        dz: float = 0.0,
        copy: bool = False,
        copies: int = 1,
    ) -> AdapterResult[dict[str, Any]]:
        return _move_body_impl(self, body, dx, dy, dz, copy, copies)

    async def delete_body(
        self, bodies: list[int] | None = None
    ) -> AdapterResult[dict[str, Any]]:
        return _delete_body_impl(self, bodies or [])

    async def delete_face(
        self, faces: list[int] | None = None
    ) -> AdapterResult[dict[str, Any]]:
        return _delete_face_impl(self, faces or [])

    async def scale_model(
        self, factor: float = 1.0, factor_y: float = 0.0, factor_z: float = 0.0
    ) -> AdapterResult[dict[str, Any]]:
        return _scale_model_impl(self, factor, factor_y, factor_z)

    async def pattern_circular(
        self,
        features: list[str],
        axis: str = "z",
        count: int = 4,
        angle: float = 360.0,
        equal_spacing: bool = True,
    ) -> AdapterResult[dict[str, Any]]:
        return _pattern_circular_impl(self, features, axis, count, angle, equal_spacing)

    async def get_bounding_box(self) -> AdapterResult[dict[str, Any]]:
        return _get_bounding_box_impl(self)


def _create_extrusion_impl(
    adapter: Any, params: ExtrusionParameters
) -> AdapterResult[SolidWorksFeature]:
    """Create a boss-extrude feature from the active sketch profile.

    Attempts the modern ``FeatureExtrusion3`` COM call first; falls back to the
    legacy ``FeatureExtrusion2`` signature when the newer overload is absent.
    When ``params.thin_feature`` is truthy, the thin-wall variants
    (``FeatureExtrusionThin2`` / ``FeatureExtruThin2``) are used instead.

    All depth and thickness values are provided in millimetres and converted
    to metres internally.

    Args:
        adapter: A fully connected ``PyWin32Adapter`` instance.  Must have a
            non-``None`` ``currentModel`` and a valid ``FeatureManager``.
        params: Extrusion parameter bag.  Relevant fields:
            - ``depth`` (float): Extrude depth in mm.
            - ``draft_angle`` (float): Draft angle in degrees.  Default 0.
            - ``reverse_direction`` (bool): Flip the extrusion direction.
            - ``thin_feature`` (bool): Produce a thin-wall body.
            - ``thin_thickness`` (float | None): Wall thickness in mm when
              ``thin_feature`` is ``True``.
            - ``merge_result`` (bool): Merge with existing bodies.  Default
              ``True``.
            - ``both_directions`` (bool): Extrude symmetrically in both
              directions from the sketch plane.
            - ``auto_fillet_corners`` (bool): Round sharp thin-wall corners.
            - ``fillet_corners_radius`` (float): Corner fillet radius in mm.

    Returns:
        AdapterResult[SolidWorksFeature]: On success, ``data`` is a
        ``SolidWorksFeature`` whose ``type`` is ``"Extrusion"``.  On failure,
        ``status`` is ``ERROR`` and ``error`` contains a descriptive message.

    Raises:
        Exception: Propagated through ``_handle_com_operation`` when the COM
            call returns ``None`` for the created feature object.

    Example::

        from solidworks_mcp.adapters.base import ExtrusionParameters
        from solidworks_mcp.adapters import pywin32_feature_ops

        params = ExtrusionParameters(depth=25.0, draft_angle=2.0)
        result = pywin32_feature_ops.create_extrusion(adapter, params)
        print(result.data.name)  # e.g. "Boss-Extrude1"
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    def _extrusion_operation() -> SolidWorksFeature:
        """Inner COM closure that builds and returns the extrusion feature.

        Normalises ``params`` into a ``SimpleNamespace`` so every attribute
        access is guaranteed safe regardless of the dataclass version.  Picks
        the thin-wall or solid branch, then tries the modern API first before
        falling back to the legacy one.

        Returns:
            SolidWorksFeature: Populated feature descriptor on success.

        Raises:
            Exception: If both API variants return ``None``.
        """
        normalized = SimpleNamespace(
            depth=float(getattr(params, "depth", 0.0)),
            draft_angle=float(getattr(params, "draft_angle", 0.0)),
            reverse_direction=bool(getattr(params, "reverse_direction", False)),
            thin_feature=bool(getattr(params, "thin_feature", False)),
            thin_thickness=getattr(params, "thin_thickness", None),
            merge_result=bool(getattr(params, "merge_result", True)),
            both_directions=bool(getattr(params, "both_directions", False)),
            auto_fillet_corners=bool(getattr(params, "auto_fillet_corners", False)),
            fillet_corners_radius=float(getattr(params, "fillet_corners_radius", 0.0)),
        )
        feature_manager = adapter.currentModel.FeatureManager

        if normalized.thin_feature and normalized.thin_thickness:
            t0 = adapter.constants.get("swStartSketchPlane", 0)
            t1 = (
                adapter.constants["swEndCondMidPlane"]
                if normalized.both_directions
                else adapter.constants["swEndCondBlind"]
            )
            try:
                feature = feature_manager.FeatureExtrusionThin2(
                    True,
                    False,
                    normalized.reverse_direction,
                    t1,
                    adapter.constants["swEndCondBlind"],
                    normalized.depth / 1000.0,
                    0.0,
                    False,
                    False,
                    False,
                    False,
                    normalized.draft_angle * 3.14159 / 180.0,
                    0.0,
                    False,
                    False,
                    False,
                    False,
                    normalized.merge_result,
                    normalized.thin_thickness / 1000.0,
                    normalized.thin_thickness / 1000.0,
                    0.0,
                    0,
                    0,
                    normalized.auto_fillet_corners,
                    normalized.fillet_corners_radius / 1000.0,
                    False,
                    True,
                    t0,
                    0.0,
                    False,
                )
            except Exception:
                feature = feature_manager.FeatureExtruThin2(
                    normalized.depth / 1000.0,
                    0.0,
                    False,
                    normalized.draft_angle * 3.14159 / 180.0,
                    0.0,
                    False,
                    False,
                    normalized.merge_result,
                    False,
                    True,
                    normalized.thin_thickness / 1000.0,
                    normalized.thin_thickness / 1000.0,
                    False,
                    False,
                    False,
                    adapter.constants["swEndCondBlind"],
                    adapter.constants["swEndCondBlind"],
                )
        else:
            t0 = adapter.constants.get("swStartSketchPlane", 0)
            try:
                feature = feature_manager.FeatureExtrusion3(
                    True,
                    False,
                    normalized.reverse_direction,
                    adapter.constants["swEndCondBlind"],
                    adapter.constants["swEndCondBlind"],
                    normalized.depth / 1000.0,
                    0.0,
                    False,
                    False,
                    False,
                    False,
                    normalized.draft_angle * 3.14159 / 180.0,
                    0.0,
                    False,
                    False,
                    False,
                    False,
                    normalized.merge_result,
                    False,
                    True,
                    t0,
                    0.0,
                    False,
                )
            except Exception:
                feature = feature_manager.FeatureExtrusion2(
                    True,
                    False,
                    normalized.reverse_direction,
                    adapter.constants["swEndCondBlind"],
                    adapter.constants["swEndCondBlind"],
                    normalized.depth / 1000.0,
                    0.0,
                    False,
                    False,
                    False,
                    False,
                    normalized.draft_angle * 3.14159 / 180.0,
                    0.0,
                    False,
                    False,
                    False,
                    False,
                    normalized.merge_result,
                    False,
                    True,
                    t0,
                    0.0,
                    False,
                )

        if not feature:
            raise Exception("Failed to create extrusion feature")

        return SolidWorksFeature(
            name=feature.Name,
            type="Extrusion",
            id=adapter._get_feature_id(feature),
            parameters={
                "depth": normalized.depth,
                "draft_angle": normalized.draft_angle,
                "reverse_direction": normalized.reverse_direction,
                "thin_feature": normalized.thin_feature,
                "thin_thickness": normalized.thin_thickness,
            },
            properties={"created": datetime.now().isoformat()},
        )

    return cast(
        AdapterResult[SolidWorksFeature],
        adapter._handle_com_operation("create_extrusion", _extrusion_operation),
    )


def _create_revolve_impl(
    adapter: Any, params: RevolveParameters
) -> AdapterResult[SolidWorksFeature]:
    """Create a revolve feature from the active sketch profile around a centre axis.

    Uses ``FeatureRevolve2`` from the SolidWorks COM API.  The sketch must
    already contain a centre-line that SolidWorks will use as the rotation axis.

    Args:
        adapter: A fully connected ``PyWin32Adapter`` with a non-``None``
            ``currentModel``.
        params: Revolve parameter bag.  Relevant fields:
            - ``angle`` (float): Revolve angle in degrees.  Use 360 for a
              full revolution.
            - ``reverse_direction`` (bool): Flip the revolve direction.
            - ``both_directions`` (bool): Revolve symmetrically in both
              directions.
            - ``thin_feature`` (bool): Produce a thin-wall body.
            - ``thin_thickness`` (float | None): Wall thickness in mm.
            - ``merge_result`` (bool): Merge with existing bodies.

    Returns:
        AdapterResult[SolidWorksFeature]: On success, ``data`` is a
        ``SolidWorksFeature`` whose ``type`` is ``"Revolve"``.  On failure,
        ``status`` is ``ERROR``.

    Raises:
        Exception: Propagated through ``_handle_com_operation`` when
            ``FeatureRevolve2`` returns ``None``.

    Example::

        from solidworks_mcp.adapters.base import RevolveParameters
        from solidworks_mcp.adapters import pywin32_feature_ops

        params = RevolveParameters(angle=360.0, merge_result=True)
        result = pywin32_feature_ops.create_revolve(adapter, params)
        print(result.data.name)  # e.g. "Revolve1"
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    def _revolve_operation() -> SolidWorksFeature:
        """Inner COM closure that builds and returns the revolve feature.

        Converts the degree angle to radians and invokes ``FeatureRevolve2``.

        Returns:
            SolidWorksFeature: Populated feature descriptor on success.

        Raises:
            Exception: If ``FeatureRevolve2`` returns ``None``.
        """
        # Detect SW major version for FeatureRevolve2 API choice
        revolve_sw_major = 0
        if getattr(adapter, "swApp", None):
            rev = adapter._attempt(
                lambda: adapter._get_attr_or_call(adapter.swApp, "RevisionNumber"),
                default="0",
            )
            try:
                revolve_sw_major = int(str(rev).split(".")[0])
            except (ValueError, IndexError):
                revolve_sw_major = 0

        import math

        # Select the profile sketch.  FeatureRevolve2 acts on the current
        # selection; without this the call has nothing to revolve and returns
        # None.  Uses the flagged tree walk (raw GetTypeName2/GetNextFeature
        # property reads find nothing under pywin32 late binding).
        volume_before = _model_volume(adapter)
        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )
        for candidate in (
            ([_profile_feature_names(adapter)[-1]] if _profile_feature_names(adapter) else [])
            + ([adapter._last_sketch_name] if adapter._last_sketch_name else [])
        ):
            if _select_feature_by_name(adapter, candidate):
                adapter._last_sketch_name = candidate
                break

        if revolve_sw_major == 33:
            # IFeatureManager.FeatureRevolve2 - exact 20-parameter signature
            # read from the live gen_py type library for SW 2025:
            #   SingleDir, IsSolid, IsThin, IsCut, ReverseDir,
            #   BothDirectionUpToSameEntity, Dir1Type, Dir2Type,
            #   Dir1Angle(rad), Dir2Angle(rad), OffsetReverse1, OffsetReverse2,
            #   OffsetDistance1, OffsetDistance2, ThinType,
            #   ThinThickness1(m), ThinThickness2(m), Merge,
            #   UseFeatScope, UseAutoSelect
            # The previous version passed 19 args AND placed Merge where
            # ThinType belongs, so every revolve failed.
            feature_manager = adapter.currentModel.FeatureManager
            is_thin = bool(params.thin_feature and params.thin_thickness)
            feature = feature_manager.FeatureRevolve2(
                not params.both_directions,  # SingleDir
                True,  # IsSolid
                is_thin,  # IsThin
                False,  # IsCut
                params.reverse_direction,  # ReverseDir
                False,  # BothDirectionUpToSameEntity
                0,  # Dir1Type (swEndCondBlind)
                0,  # Dir2Type
                params.angle * math.pi / 180.0,  # Dir1Angle (rad)
                (params.angle * math.pi / 180.0)
                if params.both_directions
                else 0.0,  # Dir2Angle
                False,  # OffsetReverse1
                False,  # OffsetReverse2
                0.0,  # OffsetDistance1
                0.0,  # OffsetDistance2
                0,  # ThinType
                (params.thin_thickness or 0.0) / 1000.0,  # ThinThickness1
                0.0,  # ThinThickness2
                params.merge_result,  # Merge
                False,  # UseFeatScope
                True,  # UseAutoSelect
            )
        else:
            feature_manager = adapter.currentModel.FeatureManager
            feature = feature_manager.FeatureRevolve2(
                not params.both_directions,
                True,
                params.thin_feature,
                False,
                params.reverse_direction,
                False,
                adapter.constants["swEndCondBlind"],
                adapter.constants["swEndCondBlind"],
                params.angle * 3.14159 / 180.0,
                (params.angle * 3.14159 / 180.0) if params.both_directions else 0.0,
                False,
                False,
                0.0,
                0.0,
                0,
                (params.thin_thickness or 0.0) / 1000.0,
                0.0,
                params.merge_result,
                False,
                True,
            )

        # When SolidWorks hands back nothing at all, say so plainly. Falling
        # through to the volume check reported "produced no geometry" with a
        # pair of volumes, which describes the symptom rather than the cause.
        if not feature:
            raise Exception("Failed to create revolve feature")

        # Verify real material appeared rather than trusting the COM return
        # value, which can be a Feature object (or void) for a revolve that
        # produced nothing.
        volume_after = _model_volume(adapter)
        if volume_after <= volume_before * 1.001:
            # Re-measure after a rebuild before reporting failure.
            volume_after = _model_volume(adapter, rebuild=True)
        if volume_after <= volume_before * 1.001:
            raise Exception(
                "Revolve produced no geometry "
                f"(volume before={volume_before:.4g}, after={volume_after:.4g}). "
                "Check that the sketch contains a closed profile and a "
                "centerline for the axis, and that the profile does not cross "
                "the axis."
            )

        if not feature and revolve_sw_major != 33:
            raise Exception("Failed to create revolve feature")

        return SolidWorksFeature(
            name=feature.Name if feature else "Revolve-Auto",
            type="Revolve",
            id=adapter._get_feature_id(feature) if feature else "revolve_auto",
            parameters={
                "angle": params.angle,
                "reverse_direction": params.reverse_direction,
                "both_directions": params.both_directions,
                "thin_feature": params.thin_feature,
                "thin_thickness": params.thin_thickness,
            },
            properties={"created": datetime.now().isoformat()},
        )

    return cast(
        AdapterResult[SolidWorksFeature],
        adapter._handle_com_operation("create_revolve", _revolve_operation),
    )


def _select_named_feature(
    adapter: Any,
    name: str,
    mark: int,
    append: bool,
) -> bool:
    """Select a named feature under a specific selection mark via ``Select2``.

    Sweep and loft rely on selection marks to tell SolidWorks which selection
    is the profile (1), guide curve (2), or sweep path (4).  We resolve the
    feature with ``IModelDoc2::FeatureByName`` and select it with
    ``IFeature::Select2(append, mark)`` â€” the same proven path the rest of the
    adapter uses for plane/sketch selection.  ``IModelDocExtension::SelectByID2``
    is avoided deliberately: late-bound ``SelectByID2`` raises
    ``Type mismatch`` on some SolidWorks builds, whereas ``FeatureByName`` +
    ``Select2`` is reliable, works for sketches *and* reference curves such as
    a helix, and needs no entity-type string.

    Args:
        adapter: A connected adapter with a valid ``currentModel``.
        name: Feature name (e.g. ``"Sketch1"`` or ``"Helix/Spiral1"``).  Any
            ``@document`` qualifier is stripped before lookup.
        mark: Selection mark â€” 1=profile, 2=guide curve, 4=sweep path.
        append: ``True`` to add to the current selection set, ``False`` to
            replace it.

    Returns:
        bool: ``True`` when the feature was found and selected.
    """
    bare = name.split("@", 1)[0]
    feature = adapter._attempt(
        lambda: adapter.currentModel.FeatureByName(bare), default=None
    )
    if not feature:
        return False
    return bool(
        adapter._attempt(lambda: feature.Select2(append, mark), default=False)
    )


def _flag_feature_methods(obj: Any, interface: str) -> None:
    """Best-effort method flagging for a COM object via ``sw_type_info``.

    Flagging tells pywin32 late binding to resolve names like ``GetTypeName2``
    / ``GetNextFeature`` / ``FirstFeature`` as methods.  No-ops on plain test
    doubles (and any environment without the gen_py wrapper).

    Args:
        obj: The COM object (or test double) to flag.
        interface: SolidWorks interface name (e.g. ``"IFeature"``).
    """
    try:
        from solidworks_mcp.adapters import sw_type_info

        sw_type_info.flag_methods(obj, interface)
    except Exception:
        pass


def _flag_feature_members(obj: Any, *names: str) -> None:
    """Flag only the named members on ``obj``.

    Cheaper than :func:`_flag_feature_methods` inside a loop: flagging a whole
    interface costs a fixed price per object, and the flag cache is keyed by
    ``id(obj)``, so a walk over fresh dispatches never hits it.

    Args:
        obj: The COM object (or test double) to flag.
        *names: Member names about to be read.
    """
    try:
        from solidworks_mcp.adapters import sw_type_info

        sw_type_info.flag_members(obj, *names)
    except Exception:
        pass


#: Members read while walking the feature tree.
_TREE_WALK_MEMBERS = ("GetTypeName2", "GetNextFeature", "Name", "GetSpecificFeature2")


def _read_member(obj: Any, name: str) -> Any:
    """Read a COM member that pywin32 may expose as a property *or* a method.

    Late-bound pywin32 dispatches are inconsistent: an unflagged zero-arg
    accessor may come back as a bound method (needing a call) *or* as the
    already-resolved value - and when that value is itself a COM object it is
    also callable, so a naive "call if callable" check wrongly invokes its
    default dispatch (``Member not found``).  This helper calls the member and
    falls back to the raw member only for those two shapes.

    It deliberately does **not** fall back on every exception.  Doing so turned
    a genuinely failing call into a "value" that happened to be the bound
    method itself, which then flowed onward as a feature name or type -
    producing entries like ``type: '<bound method ...>'`` and, worse, a junk
    feature that made the caller think the tree walk had succeeded.

    Args:
        obj: The COM object (or test double) to read from.
        name: Member name.

    Returns:
        Any: The member's value, ``None`` when the attribute is absent, and
        ``None`` when calling it failed for a real reason.
    """
    member = getattr(obj, name, None)
    if not callable(member):
        return member
    try:
        return member()
    except TypeError:
        # pywin32 already resolved this to a value; the value is not callable.
        return member
    except Exception as exc:
        # A COM *object* value is callable, and calling it raises com_error
        # ("Member not found"). That one is still the value we want.
        if type(exc).__name__ == "com_error":
            return member
        return None


def _profile_feature_names(adapter: Any) -> list[str]:
    """Return sketch (``ProfileFeature``) names in feature-tree order.

    Walks ``FirstFeature`` -> ``GetNextFeature`` reading ``GetTypeName2`` and
    collecting features whose type is ``"ProfileFeature"`` (a 2D/3D sketch).
    Mirrors the tree walk used by :func:`_create_cut_extrude_impl`, but flags
    each feature for ``IFeature`` and reads members through
    :func:`_read_member` so it is robust to pywin32's method-vs-property
    late-binding ambiguity.

    Args:
        adapter: A connected adapter with a valid ``currentModel``.

    Returns:
        list[str]: Bare sketch names, earliest first.  Empty when the walk
        finds no sketches or the tree is inaccessible.
    """
    names: list[str] = []
    try:
        _flag_feature_methods(adapter.currentModel, "IModelDoc2")
        feat = _read_member(adapter.currentModel, "FirstFeature")
        # Bound the walk so a misbehaving GetNextFeature can't spin forever.
        for _ in range(5000):
            if not feat:
                break
            _flag_feature_members(feat, *_TREE_WALK_MEMBERS)
            try:
                if _read_member(feat, "GetTypeName2") == "ProfileFeature":
                    names.append(str(_read_member(feat, "Name")))
            except Exception:
                pass
            try:
                feat = _read_member(feat, "GetNextFeature")
            except Exception:
                break
    except Exception:
        pass
    return names


def _create_sweep_impl(
    adapter: Any, params: SweepParameters
) -> AdapterResult[SolidWorksFeature]:
    """Create a swept boss/protrusion from a profile sketch along a path sketch.

    Uses ``IFeatureManager::InsertProtrusionSwept4``.  Two sketches are
    required in the active part: a closed **profile** sketch and an open
    **path** sketch named by ``params.path``.  The path is selected under
    mark 4 and the profile under mark 1, per the SolidWorks selection-mark
    contract for sweeps.

    Because :class:`SweepParameters` only names the path, the profile is
    inferred as the first ``ProfileFeature`` sketch in the feature tree whose
    name is **not** the path.  In the common "draw profile, draw path, sweep"
    workflow this is unambiguous (exactly two sketches exist).

    Args:
        adapter: A fully connected ``PyWin32Adapter`` with a non-``None``
            ``currentModel``.
        params: Sweep parameter bag.  Relevant fields:
            - ``path`` (str): Name of the path sketch (e.g. ``"Sketch2"``).
            - ``twist_along_path`` (bool): Apply a constant twist along the
              path.
            - ``twist_angle`` (float): Twist angle in **degrees** (used only
              when ``twist_along_path`` is true).
            - ``merge_result`` (bool): Merge with existing bodies.

    Returns:
        AdapterResult[SolidWorksFeature]: On success, ``data`` is a
        ``SolidWorksFeature`` whose ``type`` is ``"Sweep"``.  On failure,
        ``status`` is ``ERROR`` with a descriptive message.

    Raises:
        Exception: Propagated through ``_handle_com_operation`` when the
            profile/path cannot be selected or the COM call returns ``None``.

    Example::

        from solidworks_mcp.adapters.base import SweepParameters

        params = SweepParameters(path="Sketch2", merge_result=True)
        result = await adapter.create_sweep(params)
        print(result.data.name)  # e.g. "Sweep1"
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    if not getattr(params, "path", None):
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="Sweep requires a 'path' sketch name",
        )

    def _sweep_operation() -> SolidWorksFeature:
        """Inner COM closure that selects profile + path and runs the sweep.

        Returns:
            SolidWorksFeature: Populated feature descriptor on success.

        Raises:
            Exception: When selections fail or ``InsertProtrusionSwept4``
                returns ``None``.
        """
        import math

        feature_manager = adapter.currentModel.FeatureManager

        # Resolve the path name against the actual tree sketches so the
        # profile/path comparison is on bare names, then pick the first
        # non-path sketch as the profile.
        sketch_names = _profile_feature_names(adapter)
        path_name = params.path
        for name in sketch_names:
            if name == params.path or name.lower() == params.path.lower():
                path_name = name
                break

        # Profile = the most recently created sketch that isn't the path.
        # Preferring the latest sketch handles both a sketch path (profile is
        # drawn first, so it's the only non-path sketch) and a helix/curve
        # path (the helix's base-circle sketch precedes the profile in the
        # tree, so "first non-path" would wrongly pick the base circle).
        profile_name = None
        last = getattr(adapter, "_last_sketch_name", None)
        if last and last != path_name and last in sketch_names:
            profile_name = last
        if profile_name is None:
            profile_name = next(
                (name for name in reversed(sketch_names) if name != path_name), None
            )
        if profile_name is None:
            raise Exception(
                "Sweep needs a profile sketch distinct from the path "
                f"'{params.path}'. Sketches found: {sketch_names or 'none'}"
            )

        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )

        if not _select_named_feature(adapter, profile_name, 1, False):
            raise Exception(f"Failed to select sweep profile sketch: {profile_name}")
        if not _select_named_feature(adapter, path_name, 4, True):
            raise Exception(f"Failed to select sweep path: {path_name}")

        twist = bool(getattr(params, "twist_along_path", False))
        twist_angle_deg = float(getattr(params, "twist_angle", 0.0))
        # swTwistControlType_e: 0 = follow path, 8 = constant twist along path.
        twist_ctrl = 8 if twist else 0
        twist_angle_rad = math.radians(twist_angle_deg) if twist else 0.0

        feature = feature_manager.InsertProtrusionSwept4(
            False,  # Propagate to next tangent edge
            False,  # Alignment (go through end faces)
            twist_ctrl,  # TwistCtrlOption (swTwistControlType_e)
            False,  # KeepTangency
            False,  # BAdvancedSmoothing
            0,  # StartMatchingType (swTangencyType_e)
            0,  # EndMatchingType
            False,  # IsThinBody
            0.0,  # Thickness1
            0.0,  # Thickness2
            0,  # ThinType (swThinWallType_e)
            0,  # PathAlign
            bool(getattr(params, "merge_result", True)),  # Merge
            True,  # UseFeatScope
            True,  # UseAutoSelect
            twist_angle_rad,  # TwistAngle (radians)
            True,  # BMergeSmoothFaces
            False,  # CircularProfile
            0.0,  # CircularProfileDiameter
            0,  # Direction
        )

        if not feature:
            raise Exception("Failed to create sweep feature")

        return SolidWorksFeature(
            name=feature.Name,
            type="Sweep",
            id=adapter._get_feature_id(feature),
            parameters={
                "profile": profile_name,
                "path": path_name,
                "twist_along_path": twist,
                "twist_angle": twist_angle_deg,
                "merge_result": bool(getattr(params, "merge_result", True)),
            },
            properties={"created": datetime.now().isoformat()},
        )

    return cast(
        AdapterResult[SolidWorksFeature],
        adapter._handle_com_operation("create_sweep", _sweep_operation),
    )


def _create_loft_impl(
    adapter: Any, params: LoftParameters
) -> AdapterResult[SolidWorksFeature]:
    """Create a lofted boss/protrusion between two or more profile sketches.

    Uses ``IFeatureManager::InsertProtrusionBlend2``.  Each profile named in
    ``params.profiles`` is selected under mark 1 (in order â€” the selection
    order determines the loft direction), and any ``params.guide_curves`` are
    selected under mark 2.  Because a solid is produced, every profile must be
    a closed contour.

    Args:
        adapter: A fully connected ``PyWin32Adapter`` with a non-``None``
            ``currentModel``.
        params: Loft parameter bag.  Relevant fields:
            - ``profiles`` (list[str]): Ordered profile sketch names; at least
              two are required.
            - ``guide_curves`` (list[str] | None): Optional guide curve names.
            - ``start_tangent`` / ``end_tangent`` (str | None): ``"normal"``
              tangency at the start/end profile, anything else / ``None`` ->
              no tangency.
            - ``merge_result`` (bool): Merge with existing bodies.

    Returns:
        AdapterResult[SolidWorksFeature]: On success, ``data`` is a
        ``SolidWorksFeature`` whose ``type`` is ``"Loft"``.  On failure,
        ``status`` is ``ERROR`` with a descriptive message.

    Raises:
        Exception: Propagated through ``_handle_com_operation`` when a profile
            cannot be selected or the COM call returns ``None``.

    Example::

        from solidworks_mcp.adapters.base import LoftParameters

        params = LoftParameters(profiles=["Sketch1", "Sketch2"])
        result = await adapter.create_loft(params)
        print(result.data.name)  # e.g. "Loft1"
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    profiles = list(getattr(params, "profiles", None) or [])
    if len(profiles) < 2:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="Loft requires at least 2 profile sketches",
        )

    def _loft_operation() -> SolidWorksFeature:
        """Inner COM closure that selects profiles/guides and runs the loft.

        Returns:
            SolidWorksFeature: Populated feature descriptor on success.

        Raises:
            Exception: When a profile selection fails or
                ``InsertProtrusionBlend2`` returns ``None``.
        """
        guide_curves = list(getattr(params, "guide_curves", None) or [])

        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )

        # Profiles under mark 1, in order. First replaces the selection set,
        # the rest append so SW sees them as an ordered profile group.
        for index, profile in enumerate(profiles):
            if not _select_named_feature(adapter, profile, 1, append=index > 0):
                raise Exception(f"Failed to select loft profile sketch: {profile}")

        # Optional guide curves under mark 2 (a sketch or a reference curve).
        for guide in guide_curves:
            if not _select_named_feature(adapter, guide, 2, append=True):
                raise Exception(f"Failed to select loft guide curve: {guide}")

        # swTangencyType_e: 0 = none, 1 = tangent to profile normal.
        def _tangency(value: str | None) -> int:
            return 1 if str(value or "").strip().lower() == "normal" else 0

        start_match = _tangency(getattr(params, "start_tangent", None))
        end_match = _tangency(getattr(params, "end_tangent", None))

        feature_manager = adapter.currentModel.FeatureManager
        feature = feature_manager.InsertProtrusionBlend2(
            False,  # Closed loft
            True,  # KeepTangency
            False,  # ForceNonRational
            1.0,  # TessToleranceFactor
            start_match,  # StartMatchingType (swTangencyType_e)
            end_match,  # EndMatchingType
            1.0,  # StartTangentLength
            1.0,  # EndTangentLength
            True,  # StartTangentDir
            True,  # EndTangentDir
            False,  # IsThinBody
            0.0,  # Thickness1
            0.0,  # Thickness2
            0,  # ThinType
            bool(getattr(params, "merge_result", True)),  # Merge
            True,  # UseFeatScope
            True,  # UseAutoSelect
            2,  # GuideCurveInfluence (swGuideCurveInfluenceNextEdge)
        )

        if not feature:
            raise Exception("Failed to create loft feature")

        return SolidWorksFeature(
            name=feature.Name,
            type="Loft",
            id=adapter._get_feature_id(feature),
            parameters={
                "profiles": profiles,
                "guide_curves": guide_curves or None,
                "start_tangent": getattr(params, "start_tangent", None),
                "end_tangent": getattr(params, "end_tangent", None),
                "merge_result": bool(getattr(params, "merge_result", True)),
            },
            properties={"created": datetime.now().isoformat()},
        )

    return cast(
        AdapterResult[SolidWorksFeature],
        adapter._handle_com_operation("create_loft", _loft_operation),
    )


# swFeatureFilletOptions_e bitmask used for a plain constant-radius fillet
# (propagate to tangent faces + keep features).  Verified working on SW 2025.
_FILLET_DEFAULT_OPTIONS = 195


def _select_all_edges(adapter: Any) -> int:
    """Select every edge of every solid body in the active part.

    Enables "round all edges" without the caller having to know SolidWorks
    edge identifiers such as ``"Edge<1>"`` — there is no API in this adapter
    to enumerate those names, which previously made ``add_fillet`` unusable.

    Note ``IModelDocExtension::GetBodies2`` returns ``None`` on this build;
    the ``IPartDoc::GetBodies2`` form is the one that works.

    Args:
        adapter: A connected adapter with a valid ``currentModel``.

    Returns:
        int: Number of edges successfully added to the selection set.
    """
    model = adapter.currentModel
    bodies = adapter._attempt(lambda: model.GetBodies2(0, True), default=None)
    if not isinstance(bodies, (list, tuple)) or not bodies:
        bodies = adapter._attempt(
            lambda: model.Extension.GetBodies2(0, True), default=None
        )
    if not isinstance(bodies, (list, tuple)):
        return 0

    count = 0
    for body in bodies:
        edges = adapter._attempt(lambda b=body: b.GetEdges(), default=None)
        if not isinstance(edges, (list, tuple)):
            continue
        for edge in edges:
            if adapter._attempt(lambda e=edge: e.Select2(True, 0), default=False):
                count += 1
    return count


def _body_faces(adapter: Any) -> list[Any]:
    """Return every face of the first solid body in the active part.

    Face order is stable for a given model, so callers can address faces by
    index — there is no API here that enumerates SolidWorks face *names*.

    Args:
        adapter: A connected adapter with a valid ``currentModel``.

    Returns:
        list[Any]: Face COM objects, empty when no solid body is present.
    """
    model = adapter.currentModel
    bodies = adapter._attempt(lambda: model.GetBodies2(0, True), default=None)
    if not isinstance(bodies, (list, tuple)) or not bodies:
        bodies = adapter._attempt(
            lambda: model.Extension.GetBodies2(0, True), default=None
        )
    if not isinstance(bodies, (list, tuple)) or not bodies:
        return []
    faces = adapter._attempt(lambda: bodies[0].GetFaces(), default=None)
    return list(faces) if isinstance(faces, (list, tuple)) else []


def _component_boxes(adapter: Any, model: Any) -> list[Any]:
    """Return each assembly component's bounding box, in assembly coordinates.

    ``IComponent2::GetBox`` reports the component where it actually sits in the
    assembly.  Its *bodies* must not be used for this: ``IBody2::GetBodyBox``
    on a component body returns the box in the **part's own** coordinates, so
    three copies of one part at different positions all report the same extents
    — a plausible-looking but wrong answer.

    Args:
        adapter: A connected ``PyWin32Adapter``.
        model: The assembly document.

    Returns:
        list[Any]: Raw 6-value boxes in metres, empty when not an assembly.
    """
    from solidworks_mcp.adapters import sw_type_info

    components = adapter._attempt(
        lambda: sw_type_info.flagged(model, "IAssemblyDoc").GetComponents(True),
        default=None,
    )
    if not isinstance(components, (list, tuple)):
        return []

    boxes: list[Any] = []
    for component in components:
        wrapped = adapter._attempt(
            lambda c=component: _dynamic_dispatch(c), default=None
        )
        if wrapped is None:
            continue
        adapter._attempt(
            lambda w=wrapped: sw_type_info.flag_members(w, "GetBox"), default=None
        )
        box = adapter._attempt(lambda w=wrapped: w.GetBox(False, False), default=None)
        if isinstance(box, (list, tuple)) and len(box) >= 6:
            boxes.append(box)
    return boxes


def _dynamic_dispatch(obj: Any) -> Any:
    """Wrap a raw ``PyIDispatch`` so late binding can resolve its methods.

    Args:
        obj: The raw dispatch.

    Returns:
        Any: A late-bound wrapper, or ``None`` when pywin32 is unavailable.
    """
    try:
        import win32com.client.dynamic as dynamic
    except ImportError:  # pragma: no cover - non-Windows
        return None
    return dynamic.Dispatch(obj)


def _solid_bodies(adapter: Any) -> list[Any]:
    """Return every solid body in the active part, in a stable order.

    ``IModelDocExtension::GetBodies2`` returns ``None`` on this build, so the
    ``IPartDoc`` variant is tried first with the extension as fallback.

    **The order SolidWorks returns is not stable** — measured live, two
    identical builds of the same part handed back the bodies in opposite
    order.  Since callers address bodies by index, they are sorted by their
    bounding-box minimum corner so an index means the same body every time.

    Args:
        adapter: A connected adapter with a valid ``currentModel``.

    Returns:
        list[Any]: Body COM objects sorted by position, empty when the part
        holds no solid.
    """
    model = adapter.currentModel
    bodies = adapter._attempt(lambda: model.GetBodies2(0, True), default=None)
    if not isinstance(bodies, (list, tuple)) or not bodies:
        bodies = adapter._attempt(
            lambda: model.Extension.GetBodies2(0, True), default=None
        )
    if not isinstance(bodies, (list, tuple)):
        return []

    def _corner(body: Any) -> tuple[float, float, float]:
        """Sort key: the body's minimum bounding-box corner."""
        box = adapter._attempt(lambda b=body: b.GetBodyBox(), default=None)
        if not isinstance(box, (list, tuple)) or len(box) < 6:
            return (0.0, 0.0, 0.0)
        return (float(box[0]), float(box[1]), float(box[2]))

    return sorted(bodies, key=_corner)


def _flag_and_return(obj: Any, interface: str) -> Any:
    """Flag a COM object's methods for an interface and hand it back.

    Args:
        obj: The COM object.
        interface: Interface name, e.g. ``"IFace2"``.

    Returns:
        Any: The same object, with its methods resolvable.
    """
    _flag_feature_methods(obj, interface)
    return obj


def _select_body(adapter: Any, body: Any, mark: int, append: bool) -> bool:
    """Select a solid body under a selection mark.

    ``IBody2::Select2``'s second parameter is a *SelectData object*, not a
    mark — passing an integer there silently returns ``False``.  The older
    ``IBody2::Select(Append, Mark)`` does take a mark, and the body must be
    flagged for ``IBody2`` first or late binding resolves ``Select`` to a
    value instead of a method.

    Args:
        adapter: A connected ``PyWin32Adapter``.
        body: The body COM object.
        mark: Selection mark.
        append: Add to the current selection instead of replacing it.

    Returns:
        bool: True when the body was selected.
    """
    from solidworks_mcp.adapters import sw_type_info

    flagged = sw_type_info.flagged(body, "IBody2")
    return bool(
        adapter._attempt(lambda: flagged.Select(append, mark), default=False)
    )


def _add_draft_impl(
    adapter: Any,
    angle: float,
    neutral_face: int,
    draft_faces: list[int],
    outward: bool,
) -> AdapterResult[dict[str, Any]]:
    """Apply a draft angle to one or more faces.

    Wraps ``IFeatureManager::InsertMultiFaceDraft(Angle, FlipDir, EdgeDraft,
    PropType, IsStepDraft, IsBodyDraft)``.  Selection marks: the **neutral
    plane is mark 1** and each **face to draft is mark 2**.

    Faces are addressed by index into :func:`_body_faces` because SolidWorks
    exposes no way to enumerate face *names* through this adapter — the same
    approach ``create_shell`` uses.

    Args:
        adapter: A connected ``PyWin32Adapter`` with a valid ``currentModel``.
        angle: Draft angle in **degrees**.
        neutral_face: Index of the face the draft is measured from.
        draft_faces: Indices of the faces to taper.
        outward: Draft outward instead of inward.

    Returns:
        AdapterResult[dict[str, Any]]: Draft details on success; ``ERROR`` when
        an index is out of range, selection fails, or the volume is unchanged.

    Raises:
        Exception: Propagated through ``_handle_com_operation``.

    Example::

        # 5 degrees on face 2, measured from face 0
        await adapter.add_draft(5.0, 0, [2])
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if not angle:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_draft requires a non-zero angle",
        )
    if not draft_faces:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_draft requires at least one face index to draft",
        )

    def _draft_operation() -> dict[str, Any]:
        """Inner COM closure: select neutral + draft faces, then draft."""
        import math

        volume_before = _model_volume(adapter)

        faces = _body_faces(adapter)
        if not faces:
            raise Exception("No solid body found to draft")

        for label, index in [("neutral_face", neutral_face), *(
            ("draft_faces", i) for i in draft_faces
        )]:
            if index < 0 or index >= len(faces):
                raise Exception(
                    f"{label} index {index} out of range - the body has "
                    f"{len(faces)} faces (0-{len(faces) - 1})"
                )
        if neutral_face in draft_faces:
            raise Exception(
                f"Face {neutral_face} cannot be both the neutral plane and a "
                "face to draft"
            )

        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )

        if not adapter._attempt(
            lambda: faces[neutral_face].Select2(False, 1), default=False
        ):
            raise Exception(f"Failed to select neutral face {neutral_face}")

        for index in draft_faces:
            if not adapter._attempt(
                lambda i=index: faces[i].Select2(True, 2), default=False
            ):
                raise Exception(f"Failed to select face to draft: {index}")

        feature_manager = adapter.currentModel.FeatureManager
        feature = feature_manager.InsertMultiFaceDraft(
            math.radians(float(angle)),  # Angle
            # FlipDir is inverted relative to the name: measured live, FlipDir
            # True tapers the faces *inward* (60x40x20 block, 10 degrees,
            # 48000 -> 41278.6 mm3) and False tapers them outward
            # (48000 -> 55384.7 mm3).
            bool(not outward),  # FlipDir
            False,  # EdgeDraft
            0,  # PropType (neutral plane)
            False,  # IsStepDraft
            False,  # IsBodyDraft
        )

        volume_after = _model_volume(adapter)
        if volume_before and abs(volume_after - volume_before) <= volume_before * 0.0005:
            volume_after = _model_volume(adapter, rebuild=True)
        if volume_before and abs(volume_after - volume_before) <= volume_before * 0.0005:
            raise Exception(
                "Draft produced no geometry change "
                f"(volume before={volume_before:.4g}, after={volume_after:.4g}). "
                "Check that the neutral face is perpendicular to the faces "
                "being drafted."
            )

        return {
            "name": str(
                adapter._attempt(
                    lambda: adapter._get_attr_or_call(feature, "Name"), default="Draft"
                )
                if feature
                else "Draft"
            ),
            "angle": float(angle),
            "neutral_face": neutral_face,
            "draft_faces": list(draft_faces),
            "outward": bool(outward),
            "volume_change": volume_after - volume_before,
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("add_draft", _draft_operation),
    )


def _move_body_impl(
    adapter: Any,
    body: int,
    dx: float,
    dy: float,
    dz: float,
    copy: bool,
    copies: int,
) -> AdapterResult[dict[str, Any]]:
    """Translate (or copy) a solid body.

    Wraps ``IFeatureManager::InsertMoveCopyBody2(TransX, TransY, TransZ,
    TransDist, RotPointX..Z, RotAngleX..Z, BCopy, NumCopies)`` with the body
    preselected under mark 1.  ``TransX/Y/Z`` is a *direction*, with
    ``TransDist`` the distance along it, so the offset is split into a unit
    vector plus a magnitude.

    A pure translation is used — rotation angles are all zero.  Success is
    proved by the bounding box shifting, since a move changes position but not
    volume, so the usual volume guard cannot see it.

    Args:
        adapter: A connected ``PyWin32Adapter`` with a valid ``currentModel``.
        body: Index into :func:`_solid_bodies`.
        dx: X offset in millimetres.
        dy: Y offset in millimetres.
        dz: Z offset in millimetres.
        copy: Leave the original in place and move a copy.
        copies: Number of copies when ``copy`` is set.

    Returns:
        AdapterResult[dict[str, Any]]: Move details on success; ``ERROR`` when
        the index is out of range, the offset is zero, or nothing moved.

    Raises:
        Exception: Propagated through ``_handle_com_operation``.

    Example::

        # Shift body 1 by 30 mm along +x
        await adapter.move_body(1, 30.0, 0.0, 0.0)
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    distance = (dx * dx + dy * dy + dz * dz) ** 0.5
    if distance < 1e-9:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="move_body requires a non-zero offset",
        )
    if copy and copies < 1:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="move_body requires copies >= 1 when copy is set",
        )

    def _move_operation() -> dict[str, Any]:
        """Inner COM closure: select the body, then move it."""
        bodies = _solid_bodies(adapter)
        if body < 0 or body >= len(bodies):
            raise Exception(
                f"body index {body} out of range - the part has {len(bodies)} "
                f"bodies (0-{len(bodies) - 1})"
            )

        box_before = _body_box(adapter, bodies[body])

        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )
        if not _select_body(adapter, bodies[body], 1, append=False):
            raise Exception(f"Failed to select body {body}")

        feature_manager = adapter.currentModel.FeatureManager
        feature = feature_manager.InsertMoveCopyBody2(
            # TransX/Y/Z is the translation *vector* in metres, not a unit
            # direction: measured live, TransX=1.0 with TransDist=0.04 moved
            # the body 1000 mm, so TransDist is not applied on this build.
            dx / 1000.0,  # TransX (m)
            dy / 1000.0,  # TransY (m)
            dz / 1000.0,  # TransZ (m)
            distance / 1000.0,  # TransDist (m)
            0.0,  # RotPointX
            0.0,  # RotPointY
            0.0,  # RotPointZ
            0.0,  # RotAngleX
            0.0,  # RotAngleY
            0.0,  # RotAngleZ
            bool(copy),  # BCopy
            int(copies) if copy else 0,  # NumCopies
        )

        # A translation leaves the volume unchanged, so "did the volume move?"
        # cannot see it at all -- and "did the box change?" would accept a move
        # of the wrong distance, which is exactly what a mis-scaled TransDist
        # produces.  Require a body to exist at the requested destination.
        moved = None
        if box_before:
            expected = tuple(
                round(v + o, 3)
                for v, o in zip(box_before, (dx, dy, dz, dx, dy, dz))
            )
            for candidate in _solid_bodies(adapter):
                box = _body_box(adapter, candidate)
                if box and _boxes_match(expected, box):
                    moved = expected
                    break
            if moved is None:
                raise Exception(
                    f"Move did not land where asked: no body sits at "
                    f"{expected} after offsetting ({dx}, {dy}, {dz}) mm from "
                    f"{box_before}. The body may be fixed, or the offset was "
                    f"applied at the wrong scale."
                )

        return {
            "name": str(
                adapter._attempt(
                    lambda: adapter._get_attr_or_call(feature, "Name"),
                    default="Body-Move/Copy",
                )
                if feature
                else "Body-Move/Copy"
            ),
            "body": body,
            "offset": {"x": dx, "y": dy, "z": dz},
            "copy": bool(copy),
            "copies": int(copies) if copy else 0,
            "bodies_after": len(_solid_bodies(adapter)),
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("move_body", _move_operation),
    )


def _body_box(adapter: Any, body: Any) -> tuple[float, ...] | None:
    """Return one body's bounding box in millimetres, or ``None``.

    Args:
        adapter: A connected ``PyWin32Adapter``.
        body: The body COM object.

    Returns:
        tuple[float, ...] | None: ``(minx, miny, minz, maxx, maxy, maxz)``, or
        ``None`` when ``GetBodyBox`` gives nothing usable.
    """
    box = adapter._attempt(lambda: body.GetBodyBox(), default=None)
    if not isinstance(box, (list, tuple)) or len(box) < 6:
        return None
    values = [float(v) * 1000.0 for v in box[:6]]
    low = [min(values[i], values[i + 3]) for i in range(3)]
    high = [max(values[i], values[i + 3]) for i in range(3)]
    return tuple(round(v, 3) for v in (*low, *high))


def _boxes_match(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    """Compare two bounding boxes with a 1 micron tolerance.

    Args:
        a: First box.
        b: Second box.

    Returns:
        bool: True when every corner matches.
    """
    return len(a) == len(b) and all(abs(x - y) < 1e-3 for x, y in zip(a, b))


def _scale_model_impl(
    adapter: Any, factor: float, factor_y: float, factor_z: float
) -> AdapterResult[dict[str, Any]]:
    """Scale the model about its centroid.

    Wraps ``IModelDoc2::InsertScale(Type, Uniform, Xscale, YScale, ZScale)``.
    ``Type`` 0 is ``swScaleAbout_Centroid``.

    Volume scales with the product of the three factors, which makes this
    exactly verifiable: a uniform factor *f* must multiply the volume by
    *f³*.  The guard checks that ratio rather than merely "did the volume
    change".

    Args:
        adapter: A connected ``PyWin32Adapter`` with a valid ``currentModel``.
        factor: Scale factor along X, and along all axes when uniform.
        factor_y: Y factor; ``0`` means uniform.
        factor_z: Z factor; ``0`` means uniform.

    Returns:
        AdapterResult[dict[str, Any]]: The factors applied and the measured
        volume ratio.  ``ERROR`` when the volume does not move as predicted.

    Raises:
        Exception: Propagated through ``_handle_com_operation``.

    Example::

        await adapter.scale_model(2.0)   # 8x the volume
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if factor <= 0:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="scale_model requires a positive factor",
        )

    uniform = not (factor_y or factor_z)
    sy = factor if uniform else (factor_y or factor)
    sz = factor if uniform else (factor_z or factor)

    def _scale_operation() -> dict[str, Any]:
        """Inner COM closure: scale, then check the volume ratio."""
        volume_before = _model_volume(adapter)
        if not volume_before:
            raise Exception("Cannot scale a model with no measurable volume")

        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )
        # Use the FeatureManager overload deliberately: IModelDoc2::InsertScale
        # is (ScaleFactor_x, ScaleFactor_y, ScaleFactor_z, IsUniform) - a
        # different arity *and* order - so calling it with these arguments
        # passes 0 as the X factor and silently does nothing.
        feature_manager = adapter.currentModel.FeatureManager
        feature = adapter._attempt(
            lambda: feature_manager.InsertScale(
                0,  # Type: about centroid
                bool(uniform),  # Uniform
                float(factor),  # Xscale
                float(sy),  # YScale
                float(sz),  # ZScale
            ),
            default=None,
        )

        volume_after = _model_volume(adapter, rebuild=True)
        expected = factor * sy * sz
        ratio = volume_after / volume_before if volume_before else 0.0
        if abs(ratio - expected) > max(expected * 0.005, 1e-9):
            raise Exception(
                f"Scale did not apply as asked: volume ratio is {ratio:.5g}, "
                f"expected {expected:.5g} for factors "
                f"({factor}, {sy}, {sz})."
            )

        return {
            "name": str(
                adapter._attempt(
                    lambda: adapter._get_attr_or_call(feature, "Name"), default="Scale"
                )
                if feature
                else "Scale"
            ),
            "factors": {"x": float(factor), "y": float(sy), "z": float(sz)},
            "uniform": bool(uniform),
            "volume_ratio": round(ratio, 6),
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("scale_model", _scale_operation),
    )


def _delete_face_impl(adapter: Any, faces: list[int]) -> AdapterResult[dict[str, Any]]:
    """Remove faces from a solid, healing the surrounding surfaces.

    Wraps ``IModelDoc2::InsertDeleteFace2(Refill)`` with the faces preselected,
    falling back to ``IModelDocExtension::InsertDeleteFace(Option)``.  Note
    that ``DeleteFaces2`` lives on **IBody2**, not on ``FeatureManager``: it is
    direct body surgery that leaves no feature behind, and calling it on the
    feature manager raises ``AttributeError: <unknown>.DeleteFaces2``.

    Faces are addressed by index into :func:`_body_faces`, the same as
    ``create_shell`` and ``add_draft``.

    Args:
        adapter: A connected ``PyWin32Adapter`` with a valid ``currentModel``.
        faces: Face indices to remove.

    Returns:
        AdapterResult[dict[str, Any]]: Face counts before and after.
        ``ERROR`` when an index is out of range or nothing was removed.

    Raises:
        Exception: Propagated through ``_handle_com_operation``.

    Example::

        await adapter.delete_face([3])
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if not faces:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="delete_face requires at least one face index",
        )

    def _delete_face_operation() -> dict[str, Any]:
        """Inner COM closure: resolve faces, then delete and heal."""
        all_faces = _body_faces(adapter)
        count_before = len(all_faces)
        if not all_faces:
            raise Exception("No solid body found")
        if len(faces) >= count_before:
            raise Exception(
                f"Refusing to delete {len(faces)} of {count_before} faces - "
                "that would leave nothing to heal."
            )

        for index in faces:
            if index < 0 or index >= count_before:
                raise Exception(
                    f"face index {index} out of range - the body has "
                    f"{count_before} faces (0-{count_before - 1})"
                )

        volume_before = _model_volume(adapter)

        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )
        for position, index in enumerate(faces):
            target = _flag_and_return(all_faces[index], "IFace2")
            if not adapter._attempt(
                lambda t=target, p=position: t.Select2(p > 0, 0), default=False
            ):
                raise Exception(f"Failed to select face {index}")

        # Option 1 (delete and patch) is the only variant that heals.
        # Measured live on a block with a through hole: option 1 gives
        # 7 -> 6 faces and restores the volume to the un-drilled 32000 mm3,
        # while option 0 and InsertDeleteFace2 leave 0 faces and 0 bodies
        # (the solid is gone) and option 2 changes nothing.  All of them
        # return True, so the COM return value proves nothing here.
        adapter._attempt(
            lambda: adapter.currentModel.Extension.InsertDeleteFace(1), default=None
        )
        adapter._attempt(
            lambda: adapter.currentModel.ForceRebuild3(False), default=None
        )

        count_after = len(_body_faces(adapter))
        volume_after = _model_volume(adapter)

        # Order matters: check the solid survived BEFORE celebrating a lower
        # face count, because destroying the body also lowers it.
        if not _solid_bodies(adapter) or volume_after <= 0:
            raise Exception(
                "Delete-face destroyed the solid instead of healing it "
                f"(volume {volume_before:.4g} -> {volume_after:.4g}). "
                "The opening left behind could not be patched - try a face "
                "whose surrounding surfaces can close over it."
            )
        if count_after >= count_before:
            raise Exception(
                f"Delete-face removed nothing - the body still has "
                f"{count_after} faces (was {count_before})."
            )

        return {
            "name": "Delete-Face",
            "deleted": list(faces),
            "faces_before": count_before,
            "faces_after": count_after,
            "volume_change": volume_after - volume_before,
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("delete_face", _delete_face_operation),
    )


def _delete_body_impl(adapter: Any, bodies: list[int]) -> AdapterResult[dict[str, Any]]:
    """Delete solid bodies from a multibody part.

    Wraps ``IFeatureManager::InsertDeleteBody2(KeepBodies=False)`` with the
    bodies preselected under mark 1.

    Args:
        adapter: A connected ``PyWin32Adapter`` with a valid ``currentModel``.
        bodies: Indices into :func:`_solid_bodies`.

    Returns:
        AdapterResult[dict[str, Any]]: Remaining body count on success;
        ``ERROR`` when an index is out of range or the count did not drop.

    Raises:
        Exception: Propagated through ``_handle_com_operation``.

    Example::

        await adapter.delete_body([1])
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if not bodies:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="delete_body requires at least one body index",
        )

    def _delete_body_operation() -> dict[str, Any]:
        """Inner COM closure: select the bodies, then delete them."""
        solids = _solid_bodies(adapter)
        count_before = len(solids)
        if count_before <= len(bodies):
            raise Exception(
                f"Refusing to delete {len(bodies)} of {count_before} bodies - "
                "that would leave the part with no solid."
            )

        for index in bodies:
            if index < 0 or index >= count_before:
                raise Exception(
                    f"body index {index} out of range - the part has "
                    f"{count_before} bodies (0-{count_before - 1})"
                )

        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )
        for position, index in enumerate(bodies):
            if not _select_body(adapter, solids[index], 1, append=position > 0):
                raise Exception(f"Failed to select body {index}")

        feature_manager = adapter.currentModel.FeatureManager
        feature = feature_manager.InsertDeleteBody2(False)

        count_after = len(_solid_bodies(adapter))
        if count_after >= count_before:
            raise Exception(
                f"Delete removed nothing - the part still has {count_after} "
                f"bodies (was {count_before})."
            )

        return {
            "name": str(
                adapter._attempt(
                    lambda: adapter._get_attr_or_call(feature, "Name"),
                    default="Body-Delete",
                )
                if feature
                else "Body-Delete"
            ),
            "deleted": list(bodies),
            "bodies_before": count_before,
            "bodies_after": count_after,
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("delete_body", _delete_body_operation),
    )


def _create_shell_impl(
    adapter: Any,
    thickness: float,
    remove_faces: list[int] | None,
    outward: bool,
) -> AdapterResult[dict[str, Any]]:
    """Hollow out the solid, optionally opening one or more faces.

    Wraps ``IModelDoc2::InsertFeatureShell(Thickness, Outward)``.  Faces to be
    removed must be selected beforehand; because nothing in this adapter can
    enumerate SolidWorks face *names*, faces are addressed by **index** into
    :func:`_body_faces` (stable for a given model).  With no indices the body
    is hollowed with no opening.

    Args:
        adapter: A connected ``PyWin32Adapter`` with a valid ``currentModel``.
        thickness: Wall thickness in **millimetres**.
        remove_faces: Indices of faces to open, or ``None``/empty for a fully
            closed hollow body.
        outward: Thicken outward instead of inward.

    Returns:
        AdapterResult[dict[str, Any]]: Wall thickness, removed faces and the
        resulting volume.  ``ERROR`` when the model has no solid, an index is
        out of range, or the volume does not change.

    Raises:
        Exception: Propagated through ``_handle_com_operation``.

    Example::

        # 2 mm walls, open the face at index 5
        await adapter.create_shell(2.0, remove_faces=[5])
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    if thickness <= 0:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_shell requires a positive wall thickness",
        )

    def _shell_operation() -> dict[str, Any]:
        """Inner COM closure: select faces to open, then shell the body."""
        volume_before = _model_volume(adapter)

        faces = _body_faces(adapter)
        if not faces:
            raise Exception("No solid body found to shell")

        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )

        selected: list[int] = []
        for index in remove_faces or []:
            if index < 0 or index >= len(faces):
                raise Exception(
                    f"Face index {index} out of range - the body has "
                    f"{len(faces)} faces (0-{len(faces) - 1})"
                )
            if adapter._attempt(
                lambda f=faces[index]: f.Select2(True, 0), default=False
            ):
                selected.append(index)

        if (remove_faces or []) and not selected:
            raise Exception(f"Failed to select any face from {remove_faces}")

        adapter.currentModel.InsertFeatureShell(thickness / 1000.0, bool(outward))

        # InsertFeatureShell returns void, so volume is the only proof it ran.
        volume_after = _model_volume(adapter)
        if volume_before and volume_after >= volume_before * 0.999:
            # Re-measure after a rebuild before reporting failure.
            volume_after = _model_volume(adapter, rebuild=True)
        if volume_before and volume_after >= volume_before * 0.999:
            raise Exception(
                "Shell produced no change in the model "
                f"(volume before={volume_before:.4g}, after={volume_after:.4g}). "
                f"A {thickness}mm wall may be too thick for this body."
            )

        return {
            "thickness": thickness,
            "removed_faces": selected,
            "face_count": len(faces),
            "outward": bool(outward),
            "volume": volume_after,
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("create_shell", _shell_operation),
    )


def _body_edges(adapter: Any) -> list[Any]:
    """Return every edge of the first solid body in the active part.

    Edge order is stable for a given model, so callers can address an edge by
    index — SolidWorks edge *names* cannot be enumerated through this adapter.

    Args:
        adapter: A connected adapter with a valid ``currentModel``.

    Returns:
        list[Any]: Edge COM objects, empty when no solid body is present.
    """
    model = adapter.currentModel
    bodies = adapter._attempt(lambda: model.GetBodies2(0, True), default=None)
    if not isinstance(bodies, (list, tuple)) or not bodies:
        bodies = adapter._attempt(
            lambda: model.Extension.GetBodies2(0, True), default=None
        )
    if not isinstance(bodies, (list, tuple)) or not bodies:
        return []
    edges = adapter._attempt(lambda: bodies[0].GetEdges(), default=None)
    return list(edges) if isinstance(edges, (list, tuple)) else []


def _edge_directions(adapter: Any) -> list[tuple[int, tuple[float, float, float]]]:
    """Return ``(index, direction_vector)`` for each straight edge of the body.

    Direction is read from the edge's curve parameters; the edge object must be
    flagged for ``IEdge`` first or the accessors come back as ``None`` under
    pywin32 late binding.  Vectors point from the edge's start to its end, so
    the sign matters: an edge running ``-x`` will march pattern instances off
    the left of the model.

    Args:
        adapter: A connected adapter with a valid ``currentModel``.

    Returns:
        list[tuple[int, tuple[float, float, float]]]: Index and direction for
        each edge whose direction could be determined.
    """
    from solidworks_mcp.adapters import sw_type_info

    results: list[tuple[int, tuple[float, float, float]]] = []
    for index, edge in enumerate(_body_edges(adapter)):
        # Only the members read below. Flagging the whole IEdge interface costs
        # a fixed price per edge and the flag cache is keyed by id(obj), so on a
        # body with many edges it dominates.
        adapter._attempt(
            lambda e=edge: sw_type_info.flag_members(
                e, "GetCurveParams2", "GetCurveParams", "Select2"
            ),
            default=0,
        )
        params: Any = None
        for method in ("GetCurveParams2", "GetCurveParams"):
            value = adapter._attempt(
                lambda e=edge, m=method: getattr(e, m)(), default=None
            )
            if isinstance(value, (list, tuple)) and len(value) >= 6:
                params = value
                break
        if params is None:
            continue

        nums = [float(v) for v in params[:6]]
        vector = (nums[3] - nums[0], nums[4] - nums[1], nums[5] - nums[2])
        length = max(abs(vector[0]), abs(vector[1]), abs(vector[2]))
        if length < 1e-9:
            continue
        results.append((index, vector))
    return results


def _resolve_direction_edge(adapter: Any, direction: str) -> int | None:
    """Find the index of an edge running along ``direction``.

    Args:
        adapter: A connected adapter with a valid ``currentModel``.
        direction: Axis with optional sign, e.g. ``"x"``, ``"+x"``, ``"-y"``.

    Returns:
        int | None: Matching edge index, or ``None`` when none matches.
    """
    wanted = (direction or "").strip().lower().replace("+", "")
    negative = wanted.startswith("-")
    axis = wanted.lstrip("-")
    axis_index = {"x": 0, "y": 1, "z": 2}.get(axis)
    if axis_index is None:
        return None

    for index, vector in _edge_directions(adapter):
        magnitude = max(abs(vector[0]), abs(vector[1]), abs(vector[2]))
        # Dominant component must be the requested axis.
        if abs(vector[axis_index]) < magnitude - 1e-9:
            continue
        if (vector[axis_index] < 0) == negative:
            return index
    return None


def _pattern_linear_impl(
    adapter: Any,
    features: list[str],
    direction: str,
    count: int,
    spacing: float,
    direction_edge: int | None,
) -> AdapterResult[dict[str, Any]]:
    """Repeat one or more features along a model axis.

    Wraps ``IFeatureManager::FeatureLinearPattern``.  Preselection marks,
    confirmed empirically on SW 2025: the **direction edge uses mark 1** and
    each **feature to repeat uses mark 4**.

    SolidWorks takes the pattern direction from a straight *edge*, and edge
    names cannot be enumerated through this adapter.  Rather than make callers
    guess an index, ``direction`` names an axis (``"x"``, ``"-y"``, ``"+z"``…)
    and a matching edge is resolved automatically via
    :func:`_resolve_direction_edge`.  **The sign matters**: an edge running
    ``-x`` marches instances off the left of the model, which SolidWorks
    happily accepts while producing malformed geometry.  ``direction_edge``
    remains available as an explicit override.

    Args:
        adapter: A connected ``PyWin32Adapter`` with a valid ``currentModel``.
        features: Names of features to repeat, e.g. ``["Cut-Extrude1"]``.
        direction: Axis with optional sign — ``"x"``, ``"-x"``, ``"y"``, etc.
        count: Total number of instances **including** the original (>= 2).
        spacing: Distance between instances in **millimetres**.
        direction_edge: Explicit edge index, overriding ``direction``.

    Returns:
        AdapterResult[dict[str, Any]]: Pattern details on success; ``ERROR``
        when no matching edge exists, selection fails, or the model does not
        change.

    Raises:
        Exception: Propagated through ``_handle_com_operation``.

    Example::

        # Three holes marching along +x, 15 mm apart
        await adapter.pattern_linear(["Cut-Extrude1"], "x", 3, 15.0)
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    feature_names = [f for f in (features or []) if f]
    if not feature_names:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="pattern_linear requires at least one feature name",
        )
    if count < 2:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="pattern_linear requires count >= 2 (count includes the original)",
        )

    def _pattern_operation() -> dict[str, Any]:
        """Inner COM closure: select direction edge + features, then pattern."""
        volume_before = _model_volume(adapter)

        # What one instance is worth, so the result can be checked against
        # (count - 1) instances rather than merely "something changed".  A
        # direction that marches copies off the side of the body still moves
        # the volume, which a "did it change?" guard reports as success.
        instance_volume = _feature_volume_contribution(adapter, feature_names)

        edges = _body_edges(adapter)
        if not edges:
            raise Exception("No solid body found to pattern along")

        if direction_edge is not None:
            edge_index = direction_edge
            if edge_index < 0 or edge_index >= len(edges):
                raise Exception(
                    f"direction_edge {edge_index} out of range - the body has "
                    f"{len(edges)} edges (0-{len(edges) - 1})"
                )
        else:
            resolved = _resolve_direction_edge(adapter, direction)
            if resolved is None:
                available = sorted(
                    {
                        ("-" if v[i] < 0 else "")
                        + "xyz"[i]
                        for _, v in _edge_directions(adapter)
                        for i in (0, 1, 2)
                        if abs(v[i]) >= max(abs(v[0]), abs(v[1]), abs(v[2])) - 1e-9
                    }
                )
                raise Exception(
                    f"No edge runs along '{direction}'. Directions available "
                    f"on this body: {', '.join(available) or 'none'}."
                )
            edge_index = resolved

        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )

        if not adapter._attempt(
            lambda: edges[edge_index].Select2(True, 1), default=False
        ):
            raise Exception(f"Failed to select direction edge {edge_index}")

        for name in feature_names:
            if not _select_named_feature(adapter, name, 4, append=True):
                raise Exception(f"Failed to select feature to pattern: {name}")

        feature_manager = adapter.currentModel.FeatureManager
        feature = feature_manager.FeatureLinearPattern(
            int(count),  # Num1
            spacing / 1000.0,  # Spacing1 (m)
            1,  # Num2 (second direction unused)
            0.0,  # Spacing2
            False,  # FlipDir1 - direction comes from the chosen edge
            False,  # FlipDir2
            "",  # DName1
            "",  # DName2
        )

        volume_after = _model_volume(adapter)
        if volume_before and abs(volume_after - volume_before) <= volume_before * 0.0005:
            # Re-measure after a rebuild before reporting failure.
            volume_after = _model_volume(adapter, rebuild=True)
        if volume_before and abs(volume_after - volume_before) <= volume_before * 0.0005:
            raise Exception(
                "Pattern produced no new geometry "
                f"(volume before={volume_before:.4g}, after={volume_after:.4g}). "
                f"The instances may fall outside the body - try the opposite "
                f"direction, a smaller spacing, or a lower count."
            )

        # Strong check: the change must account for every requested instance.
        instances_made: float | None = None
        if instance_volume:
            instances_made = 1.0 + abs(volume_after - volume_before) / instance_volume
            if instances_made < count - 0.05:
                raise Exception(
                    f"Pattern produced only ~{instances_made:.1f} of the {count} "
                    f"requested instances "
                    f"(volume moved {abs(volume_after - volume_before):.4g}, "
                    f"expected {(count - 1) * instance_volume:.4g}). "
                    f"Instances are running off the body - try the opposite "
                    f"direction, a smaller spacing, or a lower count."
                )

        return {
            "name": str(
                adapter._attempt(
                    lambda: adapter._get_attr_or_call(feature, "Name"),
                    default="LPattern",
                )
                if feature
                else "LPattern"
            ),
            "features": feature_names,
            "direction": direction if direction_edge is None else f"edge {edge_index}",
            "direction_edge": edge_index,
            "count": int(count),
            "spacing": spacing,
            "instances_verified": (
                round(instances_made, 2) if instances_made is not None else None
            ),
            "verification": "instance-count" if instance_volume else "volume-changed",
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("pattern_linear", _pattern_operation),
    )


#: Pairs of built-in planes whose intersection line is the named model axis.
#: Front = XY, Top = XZ, Right = YZ, so each axis is the line shared by the two
#: planes that both contain it.
_AXIS_PLANE_PAIRS: dict[str, tuple[str, str]] = {
    "x": ("Front Plane", "Top Plane"),
    "y": ("Front Plane", "Right Plane"),
    "z": ("Top Plane", "Right Plane"),
}


def _axis_features(adapter: Any) -> list[tuple[str, tuple[float, float, float] | None]]:
    """Return every reference axis in the tree with its unit direction vector.

    Same guarded ``FirstFeature`` -> ``GetNextFeature`` walk as
    :func:`_profile_feature_names`, filtering on the ``"RefAxis"`` type name.
    Members are read via :func:`_read_member` because pywin32 late binding may
    resolve them as either bound methods or values.

    The direction comes from ``IRefAxis::GetRefAxisParams()``, which returns
    two points on the line as ``[x1, y1, z1, x2, y2, z2]``.  Direction is what
    makes an axis reusable or not, so an axis whose parameters cannot be read
    is returned with ``None`` rather than silently assumed to fit.

    Args:
        adapter: A connected ``PyWin32Adapter`` with a valid ``currentModel``.

    Returns:
        list[tuple[str, tuple[float, float, float] | None]]: ``(name,
        direction)`` pairs in tree order.  Empty when the tree holds no axes
        or is inaccessible.
    """
    axes: list[tuple[str, tuple[float, float, float] | None]] = []
    try:
        _flag_feature_methods(adapter.currentModel, "IModelDoc2")
        feat = _read_member(adapter.currentModel, "FirstFeature")
        for _ in range(5000):
            if not feat:
                break
            _flag_feature_members(feat, *_TREE_WALK_MEMBERS)
            try:
                if _read_member(feat, "GetTypeName2") == "RefAxis":
                    name = str(_read_member(feat, "Name"))
                    axes.append((name, _axis_direction(adapter, feat)))
            except Exception:
                pass
            try:
                feat = _read_member(feat, "GetNextFeature")
            except Exception:
                break
    except Exception:
        pass
    return axes


def _axis_direction(
    adapter: Any, feature: Any
) -> tuple[float, float, float] | None:
    """Read a reference axis's unit direction vector.

    Args:
        adapter: A connected ``PyWin32Adapter``.
        feature: The ``RefAxis`` feature.

    Returns:
        tuple[float, float, float] | None: Unit direction, or ``None`` when the
        axis parameters cannot be read.
    """
    axis = adapter._attempt(
        lambda: adapter._get_attr_or_call(feature, "GetSpecificFeature2"), default=None
    )
    if axis is None:
        return None

    _flag_feature_methods(axis, "IRefAxis")
    params = adapter._attempt(lambda: _read_member(axis, "GetRefAxisParams"), default=None)
    if not isinstance(params, (list, tuple)) or len(params) < 6:
        return None

    vector = tuple(float(params[i + 3]) - float(params[i]) for i in range(3))
    length = sum(component * component for component in vector) ** 0.5
    if length < 1e-12:
        return None
    return cast(
        "tuple[float, float, float]", tuple(c / length for c in vector)
    )


def _feature_volume_contribution(adapter: Any, names: list[str]) -> float:
    """Measure how much volume the given features are worth, in m³.

    Suppresses them, re-reads the volume, then unsuppresses — so the model ends
    exactly where it started.  This is what turns a pattern check from "did
    anything change?" into "did every requested instance appear?".

    Best-effort by design: any failure returns ``0.0`` and the caller falls
    back to the weaker guard rather than blocking a legitimate operation.  The
    unsuppress runs even when the measurement fails, so a half-applied
    suppression cannot be left behind.

    Args:
        adapter: A connected ``PyWin32Adapter`` with a valid ``currentModel``.
        names: Feature names whose combined contribution to measure.

    Returns:
        float: Absolute volume difference in m³, or ``0.0`` when unavailable.
    """
    if not names:
        return 0.0

    suppressed: list[str] = []
    try:
        with_features = _model_volume(adapter, rebuild=True)
        if not with_features:
            return 0.0

        for name in names:
            adapter._attempt(
                lambda: adapter.currentModel.ClearSelection2(True), default=None
            )
            if not _select_named_feature(adapter, name, 0, append=False):
                return 0.0
            if not adapter._attempt(
                lambda: adapter.currentModel.EditSuppress2(), default=False
            ):
                return 0.0
            suppressed.append(name)

        without_features = _model_volume(adapter, rebuild=True)
        return abs(with_features - without_features)
    except Exception:
        return 0.0
    finally:
        for name in suppressed:
            adapter._attempt(
                lambda: adapter.currentModel.ClearSelection2(True), default=None
            )
            if _select_named_feature(adapter, name, 0, append=False):
                adapter._attempt(
                    lambda: adapter.currentModel.EditUnsuppress2(), default=False
                )
        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )


def _find_axis_along(adapter: Any, key: str) -> str | None:
    """Return the name of an existing axis running along ``key``, if any.

    An axis has no sign — a line along ``-z`` is the same line as ``+z`` — so
    the match is on absolute alignment.  Reusing *any* axis regardless of
    direction would silently pattern around the wrong one.

    Args:
        adapter: A connected ``PyWin32Adapter`` with a valid ``currentModel``.
        key: ``"x"``, ``"y"`` or ``"z"``.

    Returns:
        str | None: Matching axis feature name, or ``None``.
    """
    index = {"x": 0, "y": 1, "z": 2}.get(key)
    if index is None:
        return None

    for name, direction in _axis_features(adapter):
        if direction is None:
            continue
        if abs(direction[index]) > 0.999:
            return name
    return None


def _create_axis_impl(adapter: Any, reference: str) -> AdapterResult[dict[str, Any]]:
    """Create a reference axis along one of the model's principal directions.

    A circular pattern needs a rotation axis, and a fresh part has none — the
    six default planes are all SolidWorks provides.  This builds one from the
    intersection of the two built-in planes that share the requested direction
    (see :data:`_AXIS_PLANE_PAIRS`), which puts the axis exactly on the model
    origin without depending on any existing geometry.

    Wraps ``IModelDoc2::InsertAxis2(AutoSize)`` with both planes preselected
    under mark 0.

    Args:
        adapter: A connected ``PyWin32Adapter`` with a valid ``currentModel``.
        reference: ``"x"``, ``"y"`` or ``"z"`` (case-insensitive; a leading
            sign is ignored — an axis has no direction, only a line).

    Returns:
        AdapterResult[dict[str, Any]]: The new axis's feature name and the
        planes it was derived from.  ``ERROR`` for an unknown reference or when
        no new axis appears in the tree.

    Raises:
        Exception: Propagated through ``_handle_com_operation``.

    Example::

        await adapter.create_axis("z")   # vertical axis through the origin
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    key = str(reference or "").strip().lower().lstrip("+-")
    if key not in _AXIS_PLANE_PAIRS:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=(
                f"Unknown axis reference '{reference}'. "
                f"Use one of: {', '.join(sorted(_AXIS_PLANE_PAIRS))}."
            ),
        )

    plane_a, plane_b = _AXIS_PLANE_PAIRS[key]

    def _axis_operation() -> dict[str, Any]:
        """Inner COM closure: select both planes, then insert the axis."""
        before = {name for name, _ in _axis_features(adapter)}

        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )

        for index, plane in enumerate((plane_a, plane_b)):
            append = index > 0
            selected = _select_named_feature(adapter, plane, 0, append=append)
            if not selected:
                selected = bool(
                    adapter._attempt(
                        lambda p=plane, a=append: (
                            adapter.currentModel.Extension.SelectByID2(
                                p, "PLANE", 0.0, 0.0, 0.0, a, 0, None, 0
                            )
                        ),
                        default=False,
                    )
                )
            if not selected:
                raise Exception(f"Failed to select '{plane}' for the axis")

        adapter._attempt(lambda: adapter.currentModel.InsertAxis2(True), default=None)

        # InsertAxis2 returns nothing useful, so confirm against the tree.
        after = [name for name, _ in _axis_features(adapter)]
        new_axes = [n for n in after if n not in before]
        if not new_axes:
            raise Exception(
                f"No reference axis was created from {plane_a} + {plane_b}. "
                "InsertAxis2 reported nothing and the feature tree is unchanged."
            )

        return {
            "name": new_axes[-1],
            "reference": key,
            "planes": [plane_a, plane_b],
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("create_axis", _axis_operation),
    )


def _pattern_circular_impl(
    adapter: Any,
    features: list[str],
    axis: str,
    count: int,
    angle: float,
    equal_spacing: bool,
) -> AdapterResult[dict[str, Any]]:
    """Repeat one or more features around an axis.

    Wraps ``IFeatureManager::FeatureCircularPattern4(Number, Spacing,
    FlipDirection, DName, GeometryPattern, EqualSpacing, VaryInstance)``.
    Preselection marks match the linear pattern: **axis = mark 1**, each
    **feature to repeat = mark 4**.

    ``axis`` may name an existing axis feature (e.g. ``"Axis1"``) or one of
    ``"x"``/``"y"``/``"z"``.  For the latter an axis is reused if one already
    exists for that direction and created via :func:`_create_axis_impl`
    otherwise — a fresh part has no axes at all, so without this the tool would
    be unusable on the exact models people want to pattern.

    With ``equal_spacing`` (the default) ``angle`` is the **total** sweep the
    instances are distributed over; otherwise it is the angle **between**
    adjacent instances.

    Args:
        adapter: A connected ``PyWin32Adapter`` with a valid ``currentModel``.
        features: Names of features to repeat, e.g. ``["Cut-Extrude1"]``.
        axis: Axis feature name, or ``"x"``/``"y"``/``"z"``.
        count: Total instances **including** the original (>= 2).
        angle: Degrees — total sweep, or per-step when ``equal_spacing`` is off.
        equal_spacing: Distribute instances evenly across ``angle``.

    Returns:
        AdapterResult[dict[str, Any]]: Pattern details on success; ``ERROR``
        when the axis cannot be resolved, selection fails, or the model does
        not change.

    Raises:
        Exception: Propagated through ``_handle_com_operation``.

    Example::

        # Six holes evenly spaced around the Z axis
        await adapter.pattern_circular(["Cut-Extrude1"], "z", 6)
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    feature_names = [f for f in (features or []) if f]
    if not feature_names:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="pattern_circular requires at least one feature name",
        )
    if count < 2:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="pattern_circular requires count >= 2 (count includes the original)",
        )
    if not angle:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="pattern_circular requires a non-zero angle",
        )

    axis_request = str(axis or "z").strip()
    axis_key = axis_request.lower().lstrip("+-")

    def _circular_operation() -> dict[str, Any]:
        """Inner COM closure: resolve/select the axis and features, then pattern."""
        import math

        volume_before = _model_volume(adapter)

        axis_name = axis_request
        created_axis = False
        if axis_key in _AXIS_PLANE_PAIRS:
            # Reuse only an axis that actually runs along the requested
            # direction -- taking any existing axis would silently pattern
            # around the wrong one.
            existing = _find_axis_along(adapter, axis_key)
            if existing:
                axis_name = existing
            else:
                result = _create_axis_impl(adapter, axis_key)
                if not result.is_success or not result.data:
                    raise Exception(
                        f"Could not create a '{axis_key}' axis to pattern around: "
                        f"{result.error or 'unknown error'}"
                    )
                axis_name = str(result.data["name"])
                created_axis = True

        # Measure what ONE instance is worth, so the result can be checked
        # against (count - 1) instances instead of merely "something changed".
        # A rotation axis that lies *in* the plane of the geometry produces two
        # distinct positions and coincident copies for the rest -- the volume
        # moves, so a "did it change?" guard reports a confident success for a
        # part that is plainly wrong.  Done before patterning so the model is
        # already back in its original state by the time the pattern is built.
        instance_volume = _feature_volume_contribution(adapter, feature_names)

        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )

        if not _select_named_feature(adapter, axis_name, 1, append=False):
            raise Exception(
                f"Failed to select rotation axis '{axis_name}'. "
                "Pass an existing axis feature name, or 'x'/'y'/'z' to have "
                "one created."
            )

        for name in feature_names:
            if not _select_named_feature(adapter, name, 4, append=True):
                raise Exception(f"Failed to select feature to pattern: {name}")

        feature_manager = adapter.currentModel.FeatureManager
        feature = feature_manager.FeatureCircularPattern4(
            int(count),  # Number
            math.radians(float(angle)),  # Spacing (radians)
            False,  # FlipDirection
            "",  # DName
            False,  # GeometryPattern
            bool(equal_spacing),  # EqualSpacing
            False,  # VaryInstance
        )

        volume_after = _model_volume(adapter)
        if volume_before and abs(volume_after - volume_before) <= volume_before * 0.0005:
            # Re-measure after a rebuild before reporting failure.
            volume_after = _model_volume(adapter, rebuild=True)
        if volume_before and abs(volume_after - volume_before) <= volume_before * 0.0005:
            raise Exception(
                "Circular pattern produced no new geometry "
                f"(volume before={volume_before:.4g}, after={volume_after:.4g}). "
                "The instances may land on top of the original or outside the "
                "body - check that the axis actually passes through the part."
            )

        # Strong check: the change must account for every requested instance.
        instances_made: float | None = None
        if instance_volume:
            instances_made = 1.0 + abs(volume_after - volume_before) / instance_volume
            if instances_made < count - 0.05:
                raise Exception(
                    f"Circular pattern produced only ~{instances_made:.1f} of the "
                    f"{count} requested instances "
                    f"(volume moved {abs(volume_after - volume_before):.4g}, "
                    f"expected {(count - 1) * instance_volume:.4g}). "
                    f"The most common cause is a rotation axis that lies in the "
                    f"plane of the geometry instead of perpendicular to it: "
                    f"copies then coincide instead of spreading around. Check "
                    f"that '{axis_name}' is normal to the face the feature sits on."
                )

        return {
            "name": str(
                adapter._attempt(
                    lambda: adapter._get_attr_or_call(feature, "Name"),
                    default="CirPattern",
                )
                if feature
                else "CirPattern"
            ),
            "features": feature_names,
            "axis": axis_name,
            "axis_created": created_axis,
            "count": int(count),
            "angle": float(angle),
            "equal_spacing": bool(equal_spacing),
            "instances_verified": (
                round(instances_made, 2) if instances_made is not None else None
            ),
            "verification": "instance-count" if instance_volume else "volume-changed",
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("pattern_circular", _circular_operation),
    )


def _get_bounding_box_impl(adapter: Any) -> AdapterResult[dict[str, Any]]:
    """Measure the axis-aligned bounding box of the model's solid bodies.

    Uses ``IBody2::GetBodyBox``, which returns ``[x1, y1, z1, x2, y2, z2]`` in
    metres; results are converted to millimetres and unioned across every solid
    body so a multibody part reports one overall box.

    Args:
        adapter: A connected ``PyWin32Adapter`` with a valid ``currentModel``.

    Returns:
        AdapterResult[dict[str, Any]]: Min/max corners, per-axis dimensions and
        the number of bodies measured.  ``ERROR`` when the model holds no solid
        body or the box cannot be read.

    Raises:
        Exception: Propagated through ``_handle_com_operation``.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    def _bbox_operation() -> dict[str, Any]:
        model = adapter.currentModel
        low = [float("inf")] * 3
        high = [float("-inf")] * 3
        measured = 0

        def absorb(box: Any) -> bool:
            """Fold a 6-value box (in metres) into the running extents."""
            nonlocal measured
            if not isinstance(box, (list, tuple)) or len(box) < 6:
                return False
            values = [float(v) * 1000.0 for v in box[:6]]
            for axis in range(3):
                low[axis] = min(low[axis], values[axis], values[axis + 3])
                high[axis] = max(high[axis], values[axis], values[axis + 3])
            measured += 1
            return True

        bodies = _solid_bodies(adapter)
        for body in bodies:
            absorb(adapter._attempt(lambda b=body: b.GetBodyBox(), default=None))

        if not measured:
            # Assemblies own no bodies of their own: measure each component
            # where it sits, via IComponent2::GetBox.
            for box in _component_boxes(adapter, model):
                absorb(box)

        if not measured:
            raise Exception(
                "No solid bodies found to measure (the document may be empty, "
                "or an assembly whose components are suppressed)"
            )

        return {
            "min": {"x": low[0], "y": low[1], "z": low[2]},
            "max": {"x": high[0], "y": high[1], "z": high[2]},
            "dimensions": {
                "x": high[0] - low[0],
                "y": high[1] - low[1],
                "z": high[2] - low[2],
            },
            "bodies_measured": measured,
            "units": "mm",
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("get_bounding_box", _bbox_operation),
    )


def _model_volume(adapter: Any, rebuild: bool = False) -> float:
    """Return the active model's total volume in m³, or ``0.0`` if unavailable.

    Used to prove that a feature actually changed the solid.  SolidWorks COM
    calls frequently report success (or return a Feature object) while
    producing no geometry, so volume is the ground truth.

    ``Extension.CreateMassProperty()`` returns ``None`` on some builds, so this
    falls back to ``IModelDoc2::GetMassProperties``, which is exposed as a
    tuple property on some builds and a method on others; volume is index 3.

    ``rebuild`` defaults to ``False`` because ``ForceRebuild3`` dominates the
    cost of this call — measured at ~112 ms versus ~1 ms for the mass-property
    read alone on SW 2025 — while SolidWorks already reflects a just-created
    feature in its mass properties (reads before and after a rebuild were
    bit-identical in testing).  Since the guards call this twice per feature,
    skipping the rebuild saves roughly 225 ms per operation.  Force a rebuild
    only to re-check an apparent "nothing changed" result before failing.

    Args:
        adapter: A connected adapter with a valid ``currentModel``.
        rebuild: Force a rebuild before measuring.  Slow; see above.

    Returns:
        float: Volume in cubic metres, or ``0.0`` when it cannot be read.
    """
    if rebuild:
        adapter._attempt(
            lambda: adapter.currentModel.ForceRebuild3(False), default=None
        )

    mass_props = adapter._attempt(
        lambda: adapter.currentModel.Extension.CreateMassProperty(), default=None
    )
    if mass_props:
        volume = adapter._attempt(lambda: mass_props.Volume, default=None)
        try:
            if volume is not None:
                return float(volume)
        except (TypeError, ValueError):
            pass

    gmp = getattr(adapter.currentModel, "GetMassProperties", None)
    raw = adapter._attempt(gmp, default=None) if callable(gmp) else gmp
    try:
        if isinstance(raw, (list, tuple)) and len(raw) > 3:
            return float(raw[3])
    except (TypeError, ValueError):
        pass
    return 0.0


def _create_cut_extrude_impl(
    adapter: Any, params: ExtrusionParameters
) -> AdapterResult[SolidWorksFeature]:
    """Create a cut-extrude feature from the active sketch profile.

    The function first attempts to locate and select the sketch profile that
    should be cut.  It walks the feature tree looking for the most recent
    ``ProfileFeature``; if that fails, it falls back to the ``_last_sketch_name``
    tracker and then to an enumerated ``Sketch<N>`` name search.

    Three COM API variants are attempted in order of preference:

    1. ``FeatureCut4`` -- most modern (SolidWorks 2015+).
    2. ``FeatureCut3`` modern signature -- SolidWorks 2010-2014.
    3. ``FeatureCut3`` legacy argument order -- older installs.

    All depth values are in millimetres and converted to metres internally.

    Args:
        adapter: A fully connected ``PyWin32Adapter`` with a non-``None``
            ``currentModel``.
        params: Extrusion parameter bag reused for cut parameters:
            - ``depth`` (float): Cut depth in mm.
            - ``draft_angle`` (float): Draft angle in degrees.
            - ``reverse_direction`` (bool): Flip the cut direction.
            - ``end_condition`` (str): ``"Blind"`` (default) or
              ``"ThroughAll"`` / ``"through_all"``.
            - ``feature_scope`` (bool): Limit cut to selected bodies.
            - ``auto_select`` (bool): Auto-select bodies in scope.

    Returns:
        AdapterResult[SolidWorksFeature]: On success, ``data`` is a
        ``SolidWorksFeature`` whose ``type`` is ``"Cut-Extrude"``.  On
        failure, ``status`` is ``ERROR`` and ``error`` lists every API
        variant that was tried.

    Raises:
        Exception: Propagated through ``_handle_com_operation`` when all
            three COM variants fail.

    Example::

        from solidworks_mcp.adapters.base import ExtrusionParameters
        from solidworks_mcp.adapters import pywin32_feature_ops

        params = ExtrusionParameters(depth=10.0, end_condition="ThroughAll")
        result = pywin32_feature_ops.create_cut_extrude(adapter, params)
        print(result.data.name)  # e.g. "Cut-Extrude1"
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    def _cut_operation() -> SolidWorksFeature:
        """Inner COM closure that locates the active sketch and performs the cut.

        Normalises ``params``, resolves the end-condition constant, selects the
        sketch profile, then cascades through three ``FeatureCut`` overloads.

        Returns:
            SolidWorksFeature: Populated feature descriptor on success.

        Raises:
            Exception: When all COM cut variants return ``None``.
        """
        normalized = SimpleNamespace(
            depth=float(getattr(params, "depth", 0.0)),
            draft_angle=float(getattr(params, "draft_angle", 0.0)),
            reverse_direction=bool(getattr(params, "reverse_direction", False)),
            end_condition=str(getattr(params, "end_condition", "Blind")),
            feature_scope=bool(getattr(params, "feature_scope", False)),
            auto_select=bool(getattr(params, "auto_select", True)),
        )
        feature_manager = adapter.currentModel.FeatureManager

        end_condition = (normalized.end_condition or "Blind").strip().lower()
        t1 = adapter.constants["swEndCondBlind"]
        depth_m = normalized.depth / 1000.0
        if end_condition in {"throughall", "through all", "through_all"}:
            t1 = adapter.constants["swEndCondThroughAll"]

        t0 = adapter.constants.get("swStartSketchPlane", 0)

        # Capture the starting volume BEFORE selecting the sketch: reading mass
        # properties forces a rebuild, and a rebuild clears the selection set.
        # Measuring afterwards would silently deselect the profile and make
        # every first-attempt cut fail.
        volume_before = _model_volume(adapter)

        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )
        sketch_selected = False

        # Resolve the profile sketch to cut with.  Use the flagged tree walk
        # (``_profile_feature_names``) rather than reading ``GetTypeName2`` /
        # ``GetNextFeature`` as raw properties: without method flagging those
        # accessors return bound methods, so the raw walk silently finds zero
        # sketches, nothing gets selected, and FeatureCut* returns None.
        # Prefer the most recently created sketch, then the tracked name.
        candidates: list[str] = []
        sketch_names = _profile_feature_names(adapter)
        if sketch_names:
            candidates.append(sketch_names[-1])
        if adapter._last_sketch_name:
            candidates.append(adapter._last_sketch_name)

        for candidate in candidates:
            if _select_feature_by_name(adapter, candidate):
                sketch_selected = True
                adapter._last_sketch_name = candidate
                break

        if not sketch_selected:
            for candidate in (
                [adapter._last_sketch_name] if adapter._last_sketch_name else []
            ) + [f"Sketch{n}" for n in range(adapter._sketch_count, 0, -1)]:
                sel_result = adapter._attempt(
                    lambda c=candidate: adapter.currentModel.Extension.SelectByID2(
                        c, "SKETCH", 0.0, 0.0, 0.0, False, 0, None, 0
                    ),
                    default=False,
                )
                sketch_selected = bool(sel_result)
                if sketch_selected:
                    adapter._last_sketch_name = candidate
                    break

        feature = None
        fallback_errors: list[str] = []
        is_through = end_condition in {"throughall", "through all", "through_all"}

        # Detect SW major version for FeatureCut4 parameter count
        # SW 2025 (major=33) verified with 27 params; other versions use 28.
        sw_major = 0
        if getattr(adapter, "swApp", None):
            rev = adapter._attempt(
                lambda: adapter._get_attr_or_call(adapter.swApp, "RevisionNumber"),
                default="0",
            )
            try:
                sw_major = int(str(rev).split(".")[0])
            except (ValueError, IndexError):
                sw_major = 0

        # 1. FeatureCut4 (SW 2015+)
        # Note: SW 2025 (major=33) verified with 27 params against the live
        # type library (the 27th, OptimizeGeometry, was previously omitted and
        # produced DISP_E_PARAMNOTOPTIONAL).
        # Other versions use 28 params (original code).
        #
        # ``cut_direction`` is toggled by the retry loop below: SolidWorks
        # silently returns None when a cut is aimed away from the solid, so
        # both directions are attempted before giving up.
        cut_direction = normalized.reverse_direction
        if sw_major == 33:
            feature, cut4_error = adapter._attempt_with_error(
                lambda: feature_manager.FeatureCut4(
                    is_through,  # Sd
                    False,  # Flip
                    cut_direction,  # Dir
                    t1,  # T1
                    adapter.constants["swEndCondBlind"],  # T2
                    depth_m,  # D1
                    0.0,  # D2
                    False,
                    False,
                    False,
                    False,  # Dchk1/2, Ddir1/2
                    normalized.draft_angle * 3.14159 / 180.0,  # Dang1
                    0.0,  # Dang2
                    False,
                    False,
                    False,
                    False,  # OffsetRev1/2, TranslateSurf1/2
                    False,  # NormalCut
                    normalized.feature_scope,  # UseFeatScope
                    normalized.auto_select,  # UseAutoSelect
                    False,  # AssemblyFeatureScope
                    False,  # AutoSelectComponents
                    False,  # PropagateFeatureToParts
                    t0,  # T0
                    0.0,  # StartOffset
                    False,  # FlipStartOffset
                    True,  # OptimizeGeometry
                )
            )
        else:
            feature, cut4_error = adapter._attempt_with_error(
                lambda: feature_manager.FeatureCut4(
                    True,
                    False,
                    normalized.reverse_direction,
                    t1,
                    adapter.constants["swEndCondBlind"],
                    depth_m,
                    0.0,
                    False,
                    False,
                    False,
                    False,
                    normalized.draft_angle * 3.14159 / 180.0,
                    0.0,
                    False,
                    False,
                    False,
                    False,
                    False,
                    normalized.feature_scope,
                    normalized.auto_select,
                    False,
                    False,
                    False,
                    t0,
                    0.0,
                    False,
                    False,
                )
            )
        if cut4_error is not None:
            fallback_errors.append(f"FeatureCut4: {cut4_error}")

        if not feature:
            # 2. FeatureCut3 modern (SW 2010+, 26 params, corrected for SW 2022)
            # Signature: Sd, Flip, Dir, T1, T2, D1, D2, Dchk1, Dchk2, Ddir1, Ddir2,
            #   Dang1, Dang2, OffsetReverse1, OffsetReverse2, TranslateSurface1,
            #   TranslateSurface2, NormalCut, UseFeatScope, UseAutoSelect,
            #   AssemblyFeatureScope, AutoSelectComponents, PropagateFeatureToParts,
            #   T0, StartOffset, FlipStartOffset
            feature, cut3_modern_error = adapter._attempt_with_error(
                lambda: feature_manager.FeatureCut3(
                    is_through,
                    normalized.reverse_direction,
                    False,
                    t1,
                    0,
                    normalized.depth / 1000.0,
                    normalized.depth / 1000.0,
                    False,
                    False,
                    False,
                    False,
                    normalized.draft_angle * 3.14159 / 180.0,
                    0.0,
                    False,
                    False,
                    False,
                    False,
                    False,
                    normalized.feature_scope,
                    normalized.auto_select,
                    False,
                    False,
                    False,
                    t0,
                    0.0,
                    False,
                )
            )
            if cut3_modern_error is not None:
                fallback_errors.append(f"FeatureCut3 modern: {cut3_modern_error}")

        if not feature:
            # 3. FeatureCut3 legacy (older installs, alternate arg order)
            feature, cut3_legacy_error = adapter._attempt_with_error(
                lambda: feature_manager.FeatureCut3(
                    True,
                    False,
                    normalized.reverse_direction,
                    adapter.constants["swEndCondBlind"],
                    adapter.constants["swEndCondBlind"],
                    False,
                    False,
                    False,
                    False,
                    normalized.draft_angle * 3.14159 / 180.0,
                    0.0,
                    False,
                    False,
                    False,
                    False,
                    False,
                    normalized.feature_scope,
                    normalized.auto_select,
                    normalized.depth / 1000.0,
                    0.0,
                )
            )
            if cut3_legacy_error is not None:
                fallback_errors.append(f"FeatureCut3 legacy: {cut3_legacy_error}")

        # Retry with the opposite direction when the first pass produced
        # nothing.  A cut aimed away from the solid is rejected silently
        # (FeatureCut4 returns None) or leaves the volume untouched, so rather
        # than making the caller guess which way points "into" the material we
        # simply try the other side.
        flipped = not cut_direction
        # Only retry when the volume is actually measurable. Without mass
        # properties _model_volume returns 0.0, and "0.0 >= 0.0" made this fire
        # on every cut - deleting a perfectly good feature and then reporting
        # failure when the flipped retry returned nothing.
        volume_says_no_op = bool(volume_before) and (
            _model_volume(adapter) >= volume_before * 0.999
        )
        original_feature = feature
        if not feature or volume_says_no_op:
            if feature:
                # Remove the no-op cut before retrying so the tree stays clean.
                adapter._attempt(
                    lambda f=feature: f.Select2(False, 0), default=False
                )
                adapter._attempt(
                    lambda: adapter.currentModel.EditDelete(), default=None
                )
                feature = None

            for candidate in candidates:
                if _select_feature_by_name(adapter, candidate):
                    break

            feature, retry_error = adapter._attempt_with_error(
                lambda: feature_manager.FeatureCut4(
                    is_through,
                    False,
                    flipped,
                    t1,
                    adapter.constants["swEndCondBlind"],
                    depth_m,
                    0.0,
                    False,
                    False,
                    False,
                    False,
                    normalized.draft_angle * 3.14159 / 180.0,
                    0.0,
                    False,
                    False,
                    False,
                    False,
                    False,
                    normalized.feature_scope,
                    normalized.auto_select,
                    False,
                    False,
                    False,
                    t0,
                    0.0,
                    False,
                    True,
                )
                if sw_major == 33
                else feature_manager.FeatureCut4(
                    is_through,
                    False,
                    flipped,
                    t1,
                    adapter.constants["swEndCondBlind"],
                    depth_m,
                    0.0,
                    False,
                    False,
                    False,
                    False,
                    normalized.draft_angle * 3.14159 / 180.0,
                    0.0,
                    False,
                    False,
                    False,
                    False,
                    False,
                    normalized.feature_scope,
                    normalized.auto_select,
                    False,
                    False,
                    False,
                    t0,
                    0.0,
                    False,
                    False,
                )
            )
            if retry_error is not None:
                fallback_errors.append(f"FeatureCut4 (flipped): {retry_error}")
            elif feature:
                cut_direction = flipped
            elif original_feature is not None and not volume_says_no_op:
                # The retry produced nothing, but the first attempt had already
                # succeeded and was not a measured no-op. Keep it rather than
                # discarding a real feature.
                feature = original_feature

        if not feature:
            if fallback_errors:
                raise Exception(
                    "Failed to create cut extrude feature. "
                    + " | ".join(fallback_errors)
                )
            raise Exception("Failed to create cut extrude feature")

        # Prove material was actually removed rather than trusting the COM
        # return value, which can be a valid Feature for a cut that did nothing.
        volume_after = _model_volume(adapter)
        if volume_before and volume_after >= volume_before * 0.999:
            # Re-measure after a rebuild before reporting failure.
            volume_after = _model_volume(adapter, rebuild=True)
        if volume_before and volume_after >= volume_before * 0.999:
            raise Exception(
                "Cut created no change in the model "
                f"(volume before={volume_before:.4g}, after={volume_after:.4g}). "
                "The sketch profile probably does not overlap the solid in "
                "either direction. Check the sketch position and end condition."
            )

        return SolidWorksFeature(
            name=feature.Name,
            type="Cut-Extrude",
            id=adapter._get_feature_id(feature),
            parameters={
                "depth": normalized.depth,
                "draft_angle": normalized.draft_angle,
                "reverse_direction": cut_direction,
                "volume_removed": max(0.0, volume_before - volume_after),
            },
            properties={"created": datetime.now().isoformat()},
        )

    return cast(
        AdapterResult[SolidWorksFeature],
        adapter._handle_com_operation("create_cut_extrude", _cut_operation),
    )


def _add_fillet_impl(
    adapter: Any, radius: float, edge_names: list[str]
) -> AdapterResult[SolidWorksFeature]:
    """Create a constant-radius fillet on one or more named edges.

    Each edge in ``edge_names`` is selected by name using
    ``Extension.SelectByID2`` with entity type ``"EDGE"``.  After all edges
    are in the selection set, ``FeatureFillet3`` is called to build the
    feature.

    Args:
        adapter: A fully connected ``PyWin32Adapter`` with a non-``None``
            ``currentModel``.
        radius: Fillet radius in **millimetres**.  Converted to metres
            internally before the COM call.
        edge_names: List of SolidWorks edge entity names to fillet, e.g.
            ``["Edge<1>", "Edge<2>"]``.

    Returns:
        AdapterResult[SolidWorksFeature]: On success, ``data`` is a
        ``SolidWorksFeature`` whose ``type`` is ``"Fillet"``.  On failure,
        ``status`` is ``ERROR``.

    Raises:
        Exception: Propagated through ``_handle_com_operation`` when an
            edge cannot be selected or ``FeatureFillet3`` returns ``None``.

    Example::

        result = pywin32_feature_ops.add_fillet(
            adapter, radius=3.0, edge_names=["Edge<1>", "Edge<3>"]
        )
        print(result.data.name)  # e.g. "Fillet1"
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    def _fillet_operation() -> SolidWorksFeature:
        """Inner COM closure that selects edges and invokes FeatureFillet3.

        Returns:
            SolidWorksFeature: Populated feature descriptor.

        Raises:
            Exception: If no edge could be selected or no material changed.
        """
        volume_before = _model_volume(adapter)
        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )

        selected_count = 0
        if edge_names:
            for edge_name in edge_names:
                ok = adapter._attempt(
                    lambda n=edge_name: adapter.currentModel.Extension.SelectByID2(
                        n, "EDGE", 0, 0, 0, True, 0, None, 0
                    ),
                    default=False,
                )
                if ok:
                    selected_count += 1
            if not selected_count:
                raise Exception(
                    f"Failed to select any of the named edges: {edge_names}. "
                    "Omit edge_names to fillet every edge of the solid instead."
                )
        else:
            selected_count = _select_all_edges(adapter)
            if not selected_count:
                raise Exception(
                    "No edges found to fillet - the model has no solid bodies."
                )

        # IFeatureManager::FeatureFillet3 with its full 14-argument signature,
        # read from the live gen_py type library.  The previous code called a
        # 9-argument IModelDoc2 variant (and a 15-argument FeatureManager one),
        # neither of which matches this build, so fillets always failed.
        feature_manager = adapter.currentModel.FeatureManager
        feature = feature_manager.FeatureFillet3(
            _FILLET_DEFAULT_OPTIONS,  # Options bitmask
            radius / 1000.0,  # R1 (m)
            0.0,  # R2
            0.0,  # Rho
            0,  # Ftyp (constant radius)
            0,  # OverflowType
            0,  # ConicRhoType
            None,  # Radii
            None,  # Dist2Arr
            None,  # RhoArr
            None,  # SetBackDistances
            None,  # PointRadiusArray
            None,  # PointDist2Array
            None,  # PointRhoArray
        )

        # SolidWorks returning nothing means the fillet was rejected outright.
        # Without this the volume guard below was the only check, and it is
        # skipped when the volume is unmeasurable - so a rejected fillet was
        # reported as success. add_chamfer has always had this check.
        if not feature:
            raise Exception("Failed to create fillet")

        # Verify the solid actually changed: SolidWorks can return a Feature
        # for a fillet that rounded nothing.
        volume_after = _model_volume(adapter)
        if volume_before and abs(volume_after - volume_before) <= volume_before * 0.0005:
            # Re-measure after a rebuild before reporting failure.
            volume_after = _model_volume(adapter, rebuild=True)
        if volume_before and abs(volume_after - volume_before) <= volume_before * 0.0005:
            raise Exception(
                "Fillet produced no change in the model "
                f"(volume before={volume_before:.4g}, after={volume_after:.4g}). "
                f"Radius {radius}mm may be too large for the selected edges."
            )

        return SolidWorksFeature(
            name=str(
                adapter._attempt(
                    lambda: adapter._get_attr_or_call(feature, "Name"),
                    default="Fillet",
                )
                if feature
                else "Fillet"
            ),
            type="Fillet",
            id=adapter._get_feature_id(feature) if feature else "fillet",
            parameters={
                "radius": radius,
                "edges": edge_names or f"all ({selected_count} edges)",
            },
            properties={"created": datetime.now().isoformat()},
        )

    return cast(
        AdapterResult[SolidWorksFeature],
        adapter._handle_com_operation("add_fillet", _fillet_operation),
    )


def _add_chamfer_impl(
    adapter: Any, distance: float, edge_names: list[str]
) -> AdapterResult[SolidWorksFeature]:
    """Create an equal-distance chamfer on one or more named edges.

    Each edge in ``edge_names`` is selected by name using
    ``Extension.SelectByID2`` with entity type ``"EDGE"``.  After all edges
    are in the selection set, ``FeatureChamfer`` is called in
    equal-distance mode (type ``1``).

    Args:
        adapter: A fully connected ``PyWin32Adapter`` with a non-``None``
            ``currentModel``.
        distance: Chamfer distance in **millimetres**.  Converted to metres
            internally.
        edge_names: List of SolidWorks edge entity names, e.g.
            ``["Edge<2>", "Edge<5>"]``.

    Returns:
        AdapterResult[SolidWorksFeature]: On success, ``data`` is a
        ``SolidWorksFeature`` whose ``type`` is ``"Chamfer"``.  On failure,
        ``status`` is ``ERROR``.

    Raises:
        Exception: Propagated through ``_handle_com_operation`` when an
            edge cannot be selected or ``FeatureChamfer`` returns ``None``.

    Example::

        result = pywin32_feature_ops.add_chamfer(
            adapter, distance=2.0, edge_names=["Edge<2>"]
        )
        print(result.data.name)  # e.g. "Chamfer1"
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    def _chamfer_operation() -> SolidWorksFeature:
        """Inner COM closure that selects edges and invokes FeatureChamfer.

        Returns:
            SolidWorksFeature: Populated feature descriptor.

        Raises:
            Exception: If any edge selection fails or the feature is ``None``.
        """
        for edge_name in edge_names:
            selected = adapter.currentModel.Extension.SelectByID2(
                edge_name, "EDGE", 0, 0, 0, True, 0, None, 0
            )
            if not selected:
                raise Exception(f"Failed to select edge: {edge_name}")

        feature_manager = adapter.currentModel.FeatureManager
        feature = feature_manager.FeatureChamfer(
            1,
            distance / 1000.0,
            distance / 1000.0,
            0,
            0,
            False,
            False,
            False,
            False,
        )

        if not feature:
            raise Exception("Failed to create chamfer")

        return SolidWorksFeature(
            name=feature.Name,
            type="Chamfer",
            id=adapter._get_feature_id(feature),
            parameters={"distance": distance, "edges": edge_names},
            properties={"created": datetime.now().isoformat()},
        )

    return cast(
        AdapterResult[SolidWorksFeature],
        adapter._handle_com_operation("add_chamfer", _chamfer_operation),
    )


def _select_feature_by_name(adapter: Any, name: str) -> bool:
    """Select a feature or sketch by name for an edit operation.

    Resolves the entity with ``IModelDoc2::FeatureByName`` and selects it with
    ``IFeature::Select2(False, 0)`` â€” the same reliable path used elsewhere in
    this adapter (avoids ``SelectByID2`` entity-type strings, which raise
    ``Type mismatch`` on some SW builds and differ for sketches vs solid
    features). Any ``name@document`` qualifier is stripped before lookup.

    Args:
        adapter: A connected adapter with a valid ``currentModel``.
        name: Feature or sketch name (e.g. ``"Boss-Extrude3"`` or ``"Sketch5"``).

    Returns:
        bool: ``True`` when the entity was found and selected.
    """
    bare = name.split("@", 1)[0]
    adapter._attempt(lambda: adapter.currentModel.ClearSelection2(True), default=None)
    feature = adapter._attempt(
        lambda: adapter.currentModel.FeatureByName(bare), default=None
    )
    if not feature:
        return False
    return bool(adapter._attempt(lambda: feature.Select2(False, 0), default=False))


def _delete_feature_impl(adapter: Any, name: str) -> AdapterResult[dict[str, Any]]:
    """Delete a named feature (or sketch) from the active model.

    Selects the feature via :func:`_select_feature_by_name`, then removes it with
    ``IModelDoc2::EditDelete``. Deleting a parent feature also removes its
    children (SolidWorks' normal cascade), which is the intended "erase this and
    what depends on it" behaviour.

    Args:
        adapter: A connected ``PyWin32Adapter`` with a non-``None`` ``currentModel``.
        name: Name of the feature/sketch to delete.

    Returns:
        AdapterResult[dict[str, Any]]: ``data`` = ``{"deleted": name}`` on success;
        ``status`` ``ERROR`` when the model is missing or the feature is not found.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    def _delete_operation() -> dict[str, Any]:
        if not _select_feature_by_name(adapter, name):
            raise Exception(f"Feature not found: {name}")
        deleted = adapter._attempt(
            lambda: adapter.currentModel.EditDelete(), default=None
        )
        # EditDelete returns void on some builds; treat "no exception" as success
        # but confirm the feature is gone to avoid a false positive.
        still_there = adapter._attempt(
            lambda: adapter.currentModel.FeatureByName(name.split("@", 1)[0]),
            default=None,
        )
        if still_there:
            raise Exception(f"EditDelete did not remove feature: {name}")
        return {"deleted": name, "result": bool(deleted) if deleted is not None else True}

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("delete_feature", _delete_operation),
    )


def _suppress_feature_impl(
    adapter: Any, name: str, suppress: bool
) -> AdapterResult[dict[str, Any]]:
    """Suppress or unsuppress a named feature in the active model.

    Selects the feature, then calls ``IModelDoc2::EditSuppress2`` (suppress) or
    ``EditUnsuppress2`` (unsuppress) on the selection. Suppressing rolls the
    feature (and its children) out of the model without deleting it â€” the safe,
    reversible way to "turn off" a bad feature.

    Args:
        adapter: A connected adapter with a valid ``currentModel``.
        name: Feature name to toggle.
        suppress: ``True`` to suppress, ``False`` to unsuppress.

    Returns:
        AdapterResult[dict[str, Any]]: ``data`` describes the action; ``ERROR``
        when the model is missing, the feature is absent, or the COM call fails.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    def _suppress_operation() -> dict[str, Any]:
        if not _select_feature_by_name(adapter, name):
            raise Exception(f"Feature not found: {name}")
        if suppress:
            ok, err = adapter._attempt_with_error(
                lambda: adapter.currentModel.EditSuppress2()
            )
        else:
            ok, err = adapter._attempt_with_error(
                lambda: adapter.currentModel.EditUnsuppress2()
            )
        if err is not None:
            raise Exception(
                f"Failed to {'suppress' if suppress else 'unsuppress'} {name}: {err}"
            )
        return {"feature": name, "suppressed": suppress}

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("suppress_feature", _suppress_operation),
    )


def _undo_impl(adapter: Any, count: int) -> AdapterResult[dict[str, Any]]:
    """Undo the last ``count`` operations in the active model.

    Calls ``IModelDoc2::EditUndo2(count)``, falling back to the older
    ``EditUndo(count)`` signature on builds that lack the 2-suffix overload.
    Lets an agent step back a bad feature without rebuilding from scratch.

    Args:
        adapter: A connected adapter with a valid ``currentModel``.
        count: Number of operations to undo (>= 1).

    Returns:
        AdapterResult[dict[str, Any]]: ``data`` = ``{"undone": count}`` on success.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    n = max(1, int(count))

    def _undo_operation() -> dict[str, Any]:
        result, err = adapter._attempt_with_error(
            lambda: adapter.currentModel.EditUndo2(n)
        )
        if err is not None:
            result, err2 = adapter._attempt_with_error(
                lambda: adapter.currentModel.EditUndo(n)
            )
            if err2 is not None:
                raise Exception(f"Undo failed: {err} | legacy: {err2}")
        return {"undone": n}

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("undo", _undo_operation),
    )


# swRefPlaneReferenceConstraints_e values used by _create_reference_plane_impl.
_REF_PLANE_DISTANCE = 8
_REF_PLANE_ANGLE = 16
_REF_PLANE_OPTION_FLIP = 256


def _create_reference_plane_impl(
    adapter: Any,
    reference: str,
    offset: float,
    angle: float,
    flip: bool,
) -> AdapterResult[dict[str, Any]]:
    """Create a reference plane offset from (or angled to) an existing plane/face.

    Wraps ``IFeatureManager::InsertRefPlane``.  Per the SolidWorks API contract,
    the reference entity must first be selected under **mark 0**; this is done
    with ``IModelDocExtension::SelectByID2``, trying entity type ``"PLANE"``
    first and falling back to ``"FACE"`` so either a datum plane or a planar
    model face can be used as the reference.

    Constraint selection:

    * ``offset`` non-zero -> ``swRefPlaneReferenceConstraint_Distance`` (8)
    * ``angle`` non-zero  -> ``swRefPlaneReferenceConstraint_Angle`` (16)
    * ``flip`` -> OR-ed with ``swRefPlaneReferenceConstraint_OptionFlip`` (256)

    This removes the long-standing gap where sketches could only be placed on
    the six built-in planes, forcing offset planes to be created by hand in the
    SolidWorks UI.

    Args:
        adapter: A connected ``PyWin32Adapter`` with a valid ``currentModel``.
        reference: Name of the reference plane or planar face, e.g.
            ``"Front Plane"`` or ``"Plane18"``.
        offset: Offset distance in **millimetres** (converted to metres).
        angle: Angle in **degrees**; used instead of ``offset`` when non-zero.
        flip: Reverse the offset/angle direction.

    Returns:
        AdapterResult[dict[str, Any]]: ``data`` contains the new plane's name
        plus the parameters used.  ``ERROR`` when the reference cannot be
        selected or the COM call returns ``None``.

    Raises:
        Exception: Propagated through ``_handle_com_operation``.

    Example::

        # Plane 2 mm in front of the Front Plane
        await adapter.create_reference_plane("Front Plane", offset=2.0)
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    if not reference:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_reference_plane requires a reference plane/face name",
        )

    if not offset and not angle:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_reference_plane requires a non-zero offset or angle",
        )

    def _plane_operation() -> dict[str, Any]:
        """Inner COM closure: select the reference, then insert the plane."""
        import math

        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )

        # The reference entity must be selected under mark 0.  Prefer
        # FeatureByName + Select2 (reliable across builds -- SelectByID2 raises
        # "Type mismatch" on some SolidWorks versions), then fall back to
        # SelectByID2 for planar faces that are not named tree features.
        selected = _select_named_feature(adapter, reference, 0, append=False)
        if not selected:
            for entity_type in ("PLANE", "FACE"):
                selected = bool(
                    adapter._attempt(
                        lambda t=entity_type: adapter.currentModel.Extension.SelectByID2(
                            reference, t, 0.0, 0.0, 0.0, False, 0, None, 0
                        ),
                        default=False,
                    )
                )
                if selected:
                    break

        if not selected:
            raise Exception(
                f"Failed to select reference plane/face: {reference}. "
                "Use an existing plane name (e.g. 'Front Plane') or planar face."
            )

        if angle:
            constraint = _REF_PLANE_ANGLE
            value = math.radians(float(angle))
        else:
            constraint = _REF_PLANE_DISTANCE
            value = float(offset) / 1000.0

        if flip:
            constraint |= _REF_PLANE_OPTION_FLIP

        feature_manager = adapter.currentModel.FeatureManager
        plane = feature_manager.InsertRefPlane(constraint, value, 0, 0.0, 0, 0.0)

        if not plane:
            raise Exception(
                f"InsertRefPlane returned no plane for reference '{reference}'"
            )

        plane_name = adapter._attempt(
            lambda: adapter._get_attr_or_call(plane, "Name"), default=None
        )
        if not plane_name:
            # RefPlane objects expose their name via the owning feature.
            plane_name = "Plane"

        return {
            "name": str(plane_name),
            "reference": reference,
            "offset": offset,
            "angle": angle,
            "flip": flip,
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("create_reference_plane", _plane_operation),
    )


def _mirror_feature_impl(
    adapter: Any,
    features: list[str],
    mirror_plane: str,
    merge: bool,
) -> AdapterResult[dict[str, Any]]:
    """Mirror one or more solid features about a plane.

    Wraps ``IFeatureManager::InsertMirrorFeature``.  Per the SolidWorks API
    contract the entities must be preselected under specific marks:

    * **mark 1** â€” each feature to be mirrored
    * **mark 2** â€” the mirror plane (or planar face)

    Features are resolved with ``FeatureByName`` + ``Select2`` (robust across
    builds); the plane falls back to ``SelectByID2`` with ``"PLANE"``/``"FACE"``
    when it is not a named tree feature.

    Previously only *sketch* mirroring existed, so mirroring a solid feature
    (e.g. the second half of a shell) had to be done by hand in the UI.

    **Scope (verified on SW 2025):** feature mirroring resolves when the
    mirrored feature's sketch sits on â€” or passes through â€” the mirror plane
    (volume doubles, confirmed).  A feature built on a *different* plane offset
    from the mirror plane cannot be resolved as a feature mirror by SolidWorks;
    the COM call still returns a Feature object but produces no geometry, so
    this function verifies the model volume actually grew and raises an
    explanatory error rather than reporting a false success.

    Args:
        adapter: A connected ``PyWin32Adapter`` with a valid ``currentModel``.
        features: Names of the features to mirror, e.g. ``["Boss-Extrude110"]``.
        mirror_plane: Mirror plane name, e.g. ``"Front Plane"``.
        merge: Merge the mirrored result into the existing body.

    Returns:
        AdapterResult[dict[str, Any]]: ``data`` describes the new mirror
        feature.  ``ERROR`` when a selection fails or the COM call returns
        ``None``.

    Raises:
        Exception: Propagated through ``_handle_com_operation``.

    Example::

        await adapter.mirror_feature(["Boss-Extrude110"], "Front Plane")
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    feature_names = [f for f in (features or []) if f]
    if not feature_names:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="mirror_feature requires at least one feature name",
        )
    if not mirror_plane:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="mirror_feature requires a mirror plane name",
        )

    def _volume() -> float:
        """Return the model's total volume, or 0.0 when unavailable.

        Used to prove the mirror actually produced geometry.  ``InsertMirrorFeature``
        can return a non-``None`` Feature while silently mirroring nothing, so the
        COM return value alone must never be treated as success.
        """
        adapter._attempt(
            lambda: adapter.currentModel.ForceRebuild3(False), default=None
        )
        mass_props = adapter._attempt(
            lambda: adapter.currentModel.Extension.CreateMassProperty(),
            default=None,
        )
        if mass_props:
            volume = adapter._attempt(lambda: mass_props.Volume, default=None)
            try:
                if volume is not None:
                    return float(volume)
            except (TypeError, ValueError):
                pass

        # Fallback used by get_mass_properties(): IModelDoc2::GetMassProperties
        # is exposed as a tuple property on some builds and a method on others.
        gmp = getattr(adapter.currentModel, "GetMassProperties", None)
        raw = adapter._attempt(gmp, default=None) if callable(gmp) else gmp
        try:
            if isinstance(raw, (list, tuple)) and len(raw) > 3:
                return float(raw[3])
        except (TypeError, ValueError):
            pass
        return 0.0

    def _mirror_operation() -> dict[str, Any]:
        """Inner COM closure: select features (mark 1) + plane (mark 2), mirror."""
        volume_before = _volume()

        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )

        # Features to mirror -> mark 1 (first replaces selection, rest append).
        for index, name in enumerate(feature_names):
            if not _select_named_feature(adapter, name, 1, append=index > 0):
                raise Exception(f"Failed to select feature to mirror: {name}")

        # Mirror plane -> mark 2.  Try the feature-tree path first, then
        # SelectByID2 for built-in planes / planar faces.
        plane_selected = _select_named_feature(adapter, mirror_plane, 2, append=True)
        if not plane_selected:
            for entity_type in ("PLANE", "FACE"):
                plane_selected = bool(
                    adapter._attempt(
                        lambda t=entity_type: adapter.currentModel.Extension.SelectByID2(
                            mirror_plane, t, 0.0, 0.0, 0.0, True, 2, None, 0
                        ),
                        default=False,
                    )
                )
                if plane_selected:
                    break
        if not plane_selected:
            raise Exception(f"Failed to select mirror plane: {mirror_plane}")

        feature_manager = adapter.currentModel.FeatureManager
        feature = feature_manager.InsertMirrorFeature(
            False,  # BMirrorBody - False mirrors a feature/face, not a body
            False,  # BGeometryPattern - solve the whole feature
            bool(merge),  # BMerge
            False,  # BKnit
        )

        if not feature:
            raise Exception(
                "InsertMirrorFeature returned no feature "
                f"(features={feature_names}, plane={mirror_plane})"
            )

        # Never trust the COM return value alone: verify real geometry appeared.
        volume_after = _volume()
        if volume_before and volume_after <= volume_before * 1.001:
            raise Exception(
                "Mirror produced no new geometry "
                f"(volume before={volume_before:.4g}, after={volume_after:.4g}). "
                "SolidWorks returned a feature but mirrored nothing. Feature "
                "mirroring only resolves when the mirrored feature's own sketch "
                "sits on (or passes through) the mirror plane. Here "
                f"{feature_names} appears to be built on a different/offset "
                f"plane relative to '{mirror_plane}', which SolidWorks cannot "
                "resolve as a feature mirror. Either mirror about the feature's "
                "own sketch plane, or mirror the solid body manually via "
                "Insert > Pattern/Mirror > Mirror (Bodies to Mirror)."
            )

        return {
            "name": str(
                adapter._attempt(
                    lambda: adapter._get_attr_or_call(feature, "Name"),
                    default="Mirror",
                )
            ),
            "mirrored_features": feature_names,
            "mirror_plane": mirror_plane,
            "merge": bool(merge),
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("mirror_feature", _mirror_operation),
    )

