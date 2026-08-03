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

        if revolve_sw_major == 33:
            # IFeatureManager.FeatureRevolve2 (20 params) per gen_py SW 2025
            # SingleDir, IsSolid, IsThin, IsCut, ReverseDir, BothDirUpToSame,
            # Dir1Type, Dir2Type, Dir1Angle(rad), Dir2Angle(rad),
            # OffsetRev1/2, OffsetDist1/2, Merge, ThinThick1/2(m), AutoSelect, Propagate
            feature_manager = adapter.currentModel.FeatureManager
            feature = feature_manager.FeatureRevolve2(
                True,  # SingleDir
                True,  # IsSolid
                False,  # IsThin
                False,  # IsCut
                params.reverse_direction,  # ReverseDir
                params.both_directions,  # BothDirUpToSame
                0,
                0,  # Dir1Type, Dir2Type
                params.angle * math.pi / 180.0,  # Dir1Angle (rad)
                (params.angle * math.pi / 180.0)
                if params.both_directions
                else 0.0,  # Dir2Angle
                False,
                False,  # OffsetRev1/2
                0.0,
                0.0,  # OffsetDist1/2
                params.merge_result,  # Merge
                (params.thin_thickness or 0.0) / 1000.0,
                0.0,  # ThinThick1/2
                True,  # AutoSelect
                False,  # Propagate
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

        # IModelDoc2.FeatureRevolve2 returns None (void) on SW 2025
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


def _read_member(obj: Any, name: str) -> Any:
    """Read a COM member that pywin32 may expose as a property *or* a method.

    Late-bound pywin32 dispatches are inconsistent: an unflagged zero-arg
    accessor may come back as a bound method (needing a call) *or* as the
    already-resolved value â€” and when that value is itself a COM object it is
    also callable, so a naive "call if callable" check wrongly invokes its
    default dispatch (``Member not found``).  This helper calls the member and
    falls back to the raw member if the call raises, so it yields the value in
    every case (flagged method, unflagged method, property-returning-object,
    or plain test double).

    Args:
        obj: The COM object (or test double) to read from.
        name: Member name.

    Returns:
        Any: The member's value, or ``None`` when the attribute is absent.
    """
    member = getattr(obj, name, None)
    if not callable(member):
        return member
    try:
        return member()
    except Exception:
        return member


def _profile_feature_names(adapter: Any) -> list[str]:
    """Return sketch (``ProfileFeature``) names in feature-tree order.

    Walks ``FirstFeature`` â†’ ``GetNextFeature`` reading ``GetTypeName2`` and
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
            _flag_feature_methods(feat, "IFeature")
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
              tangency at the start/end profile, anything else / ``None`` â†’
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


def _model_volume(adapter: Any) -> float:
    """Return the active model's total volume in mÂ³, or ``0.0`` if unavailable.

    Used to prove that a feature actually changed the solid.  SolidWorks COM
    calls frequently report success (or return a Feature object) while
    producing no geometry, so volume is the ground truth.

    ``Extension.CreateMassProperty()`` returns ``None`` on some builds, so this
    falls back to ``IModelDoc2::GetMassProperties``, which is exposed as a
    tuple property on some builds and a method on others; volume is index 3.

    Args:
        adapter: A connected adapter with a valid ``currentModel``.

    Returns:
        float: Volume in cubic metres, or ``0.0`` when it cannot be read.
    """
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)

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

    1. ``FeatureCut4`` Î“Ã‡Ã¶ most modern (SolidWorks 2015+).
    2. ``FeatureCut3`` modern signature Î“Ã‡Ã¶ SolidWorks 2010Î“Ã‡Ã´2014.
    3. ``FeatureCut3`` legacy argument order Î“Ã‡Ã¶ older installs.

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
        if not feature or _model_volume(adapter) >= volume_before * 0.999:
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
            else:
                cut_direction = flipped

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
            Exception: If any edge selection fails or the feature is ``None``.
        """
        # Detect SW major version for FeatureFillet3 parameter count
        fillet_sw_major = 0
        if getattr(adapter, "swApp", None):
            rev = adapter._attempt(
                lambda: adapter._get_attr_or_call(adapter.swApp, "RevisionNumber"),
                default="0",
            )
            try:
                fillet_sw_major = int(str(rev).split(".")[0])
            except (ValueError, IndexError):
                fillet_sw_major = 0

        for edge_name in edge_names:
            selected = adapter.currentModel.Extension.SelectByID2(
                edge_name,
                "EDGE",
                0,
                0,
                0,
                True,
                0,
                None,
                0,
            )
            if not selected:
                raise Exception(f"Failed to select edge: {edge_name}")

        # SW 2025 (major=33): IModelDoc2.FeatureFillet3 (9 params) verified.
        # Other versions: IFeatureManager.FeatureFillet3 (16 params, original code).
        if fillet_sw_major == 33:
            feature = adapter.currentModel.FeatureFillet3(
                radius / 1000.0,  # R1 in meters
                True,  # Propagate
                0,  # Ftyp
                0,
                0,  # VarRadTyp, OverflowType
                0,
                None,  # NRadii, Radii
                False,
                False,  # UseHelpPoint, UseTangentHoldLine
            )
        else:
            feature_manager = adapter.currentModel.FeatureManager
            feature = feature_manager.FeatureFillet3(
                radius / 1000.0,
                0,
                0,
                0,
                0,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                0,
                False,
            )

        # IModelDoc2.FeatureFillet3 returns int on SW 2025, not IFeature
        if not feature and fillet_sw_major != 33:
            raise Exception("Failed to create fillet")

        return SolidWorksFeature(
            name=feature.Name,
            type="Fillet",
            id=adapter._get_feature_id(feature),
            parameters={"radius": radius, "edges": edge_names},
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

    * ``offset`` non-zero â†’ ``swRefPlaneReferenceConstraint_Distance`` (8)
    * ``angle`` non-zero  â†’ ``swRefPlaneReferenceConstraint_Angle`` (16)
    * ``flip`` â†’ OR-ed with ``swRefPlaneReferenceConstraint_OptionFlip`` (256)

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

