"""Model I/O mixin for PyWin32 SolidWorks operations."""

from __future__ import annotations

import ctypes
import os
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from .. import sw_type_info as _sw_type_info
from ..base import AdapterResult, AdapterResultStatus, MassProperties, SolidWorksModel

try:
    import pythoncom
    import win32com.client
    import win32com.client.dynamic as _dynamic
except ImportError:  # pragma: no cover
    pythoncom = SimpleNamespace()
    win32com = SimpleNamespace(client=SimpleNamespace())
    _dynamic = SimpleNamespace(Dispatch=lambda *_a, **_kw: None)


#: SolidWorks named views accepted by ``CreateDrawViewFromModelView3``.
_NAMED_VIEWS: dict[str, str] = {
    "front": "*Front",
    "back": "*Back",
    "left": "*Left",
    "right": "*Right",
    "top": "*Top",
    "bottom": "*Bottom",
    "isometric": "*Isometric",
    "iso": "*Isometric",
    "trimetric": "*Trimetric",
    "dimetric": "*Dimetric",
    "current": "*Current",
}


def _byref_int() -> Any:
    """Return a byref long VARIANT for a SolidWorks out-parameter.

    See :func:`_byref_bstr` for why ``pythoncom.Missing`` does not work.

    Returns:
        Any: A ``VARIANT(VT_BYREF | VT_I4, 0)``, or ``0`` when pywin32 is
        unavailable (test/mock environments).
    """
    variant_ctor = getattr(getattr(win32com, "client", None), "VARIANT", None)
    if not callable(variant_ctor):
        return 0
    return variant_ctor(
        int(getattr(pythoncom, "VT_BYREF", 0)) | int(getattr(pythoncom, "VT_I4", 0)), 0
    )


#: ``swMateType_e`` values accepted by ``AddMate5``.
_MATE_TYPES: dict[str, int] = {
    "coincident": 0,
    "concentric": 1,
    "perpendicular": 2,
    "parallel": 3,
    "tangent": 4,
    "distance": 5,
    "angle": 6,
}

#: ``swMateAlign_e`` values.
_MATE_ALIGNMENTS: dict[str, int] = {
    "aligned": 0,
    "anti_aligned": 1,
    "closest": 2,
}


def _variant_doubles(values: list[float]) -> Any:
    """Wrap a list of floats as a COM ``SAFEARRAY`` of doubles.

    Several SolidWorks setters reject a plain Python list — measured live,
    ``SetMaterialPropertyValues`` raises on one and applies the colour when
    handed a ``VARIANT(VT_ARRAY | VT_R8, ...)``.

    Args:
        values (list[float]): The values to pass.

    Returns:
        Any: A VARIANT array, or the original list without pywin32.
    """
    variant_ctor = getattr(getattr(win32com, "client", None), "VARIANT", None)
    if not callable(variant_ctor):
        return values
    return variant_ctor(
        int(getattr(pythoncom, "VT_ARRAY", 0)) | int(getattr(pythoncom, "VT_R8", 0)),
        [float(v) for v in values],
    )


def _bounding_box_tuple(adapter: Any) -> tuple[float, ...] | None:
    """Return the model's overall box, for before/after comparison.

    Args:
        adapter: A connected ``PyWin32Adapter``.

    Returns:
        tuple[float, ...] | None: ``(minx, miny, minz, maxx, maxy, maxz)`` in
        millimetres, or ``None`` when nothing measurable is present.
    """
    from .features import _get_bounding_box_impl

    result = _get_bounding_box_impl(adapter)
    data = getattr(result, "data", None)
    if not isinstance(data, dict):
        return None
    low, high = data.get("min", {}), data.get("max", {})
    try:
        return (
            round(float(low["x"]), 3),
            round(float(low["y"]), 3),
            round(float(low["z"]), 3),
            round(float(high["x"]), 3),
            round(float(high["y"]), 3),
            round(float(high["z"]), 3),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _doc_type(adapter: Any) -> int | None:
    """Return the active document's type: 1 part, 2 assembly, 3 drawing.

    ``GetType`` is one of the members pywin32 late binding may expose as either
    a bound method or a plain value, so calling it directly returns ``None`` on
    some documents.  ``_get_attr_or_call`` handles both shapes.

    Args:
        adapter: A connected ``PyWin32Adapter``.

    Returns:
        int | None: The document type, or ``None`` when it cannot be read.
    """
    value = adapter._attempt(
        lambda: adapter._get_attr_or_call(adapter.currentModel, "GetType"),
        default=None,
    )
    return int(value) if isinstance(value, (int, float)) else None


def _component_names(adapter: Any, assembly: Any) -> list[str]:
    """Return the names of an assembly's top-level components.

    ``AddComponent*`` can return an object having added nothing, so the
    component list is the ground truth for whether an insert worked.

    Args:
        adapter: A connected ``PyWin32Adapter``.
        assembly: The assembly document, flagged for ``IAssemblyDoc``.

    Returns:
        list[str]: Component names, empty when the assembly holds none.
    """
    components = adapter._attempt(lambda: assembly.GetComponents(True), default=None)
    if not isinstance(components, (list, tuple)):
        return []

    names: list[str] = []
    for component in components:
        wrapped = _as_com(adapter, component, "IComponent2")
        if wrapped is None:
            names.append("<unnamed>")
            continue
        name = adapter._attempt(lambda c=wrapped: c.Name2, default=None)
        if not name:
            name = adapter._attempt(lambda c=wrapped: c.GetPathName(), default=None)
        names.append(str(name) if name else "<unnamed>")
    return names


def _as_com(adapter: Any, obj: Any, interface: str) -> Any:
    """Wrap a raw dispatch and flag its methods for an interface.

    Objects handed back inside arrays (``GetViews`` and friends) arrive as raw
    ``PyIDispatch``.  Method flagging is a no-op on those, so every call
    against them raises until they are wrapped through ``dynamic.Dispatch``.

    Args:
        adapter: A connected ``PyWin32Adapter``.
        obj: The raw dispatch.
        interface: Interface name, e.g. ``"IView"``.

    Returns:
        Any: The wrapped, flagged object, or ``None``.
    """
    wrapped = adapter._attempt(lambda: _dynamic.Dispatch(obj), default=None)
    if wrapped is None:
        return None
    adapter._attempt(
        lambda: _sw_type_info.flag_methods(wrapped, interface), default=None
    )
    return wrapped


def _view_names(adapter: Any, drawing: Any) -> list[str]:
    """Return the drawing's view names, excluding sheet formats.

    ``CreateDrawViewFromModelView3`` returns ``None`` for a model SolidWorks
    could not resolve, so the view list is the ground truth for whether a view
    was really added.

    Args:
        adapter: A connected ``PyWin32Adapter``.
        drawing: The drawing document, flagged for ``IDrawingDoc``.

    Returns:
        list[str]: View names in sheet order.
    """
    sheets = adapter._attempt(lambda: drawing.GetViews(), default=None)
    if not isinstance(sheets, (list, tuple)):
        return []

    names: list[str] = []
    for sheet in sheets:
        views = sheet if isinstance(sheet, (list, tuple)) else [sheet]
        for index, view in enumerate(views):
            # GetViews returns (sheet, view, view, ...) per sheet; entry 0 is
            # the sheet itself, not a drawing view.
            if index == 0 and isinstance(sheet, (list, tuple)):
                continue
            wrapped = _as_com(adapter, view, "IView")
            if wrapped is None:
                continue
            name = adapter._attempt(lambda w=wrapped: w.GetName2(), default=None)
            if name:
                names.append(str(name))
    return names


def _byref_bstr() -> Any:
    """Return a byref string VARIANT for a SolidWorks out-parameter.

    pywin32's makepy wrapper marks SolidWorks' pass-by-ref out-parameters as
    required inputs.  ``pythoncom.Missing`` does not satisfy them: measured
    live, ``GetMaterialPropertyName2(config, pythoncom.Missing)`` *raises*,
    while the same call with a byref VARIANT returns the material name and
    fills the VARIANT with the library name.  The same trap governs
    ``OpenDoc6``.

    Returns:
        Any: A ``VARIANT(VT_BYREF | VT_BSTR, "")``, or ``""`` when pywin32 is
        unavailable (test/mock environments).
    """
    variant_ctor = getattr(getattr(win32com, "client", None), "VARIANT", None)
    if not callable(variant_ctor):
        return ""
    return variant_ctor(
        int(getattr(pythoncom, "VT_BYREF", 0)) | int(getattr(pythoncom, "VT_BSTR", 0)),
        "",
    )


def _read_material_name(adapter: Any, model: Any, config_name: str) -> tuple[Any, Any]:
    """Read the assigned material name and its library.

    Args:
        adapter: A connected ``PyWin32Adapter``.
        model: The part document.
        config_name: Configuration to read.

    Returns:
        tuple[Any, Any]: ``(name, database)``; either may be ``None``.
    """
    holder = _byref_bstr()
    name = adapter._attempt(
        lambda: model.GetMaterialPropertyName2(config_name, holder), default=None
    )
    if isinstance(name, (list, tuple)):
        name = name[0] if name else None
    database = getattr(holder, "value", None)
    return name, database

try:
    import comtypes  # type: ignore[import-untyped]
    import comtypes.client as _comtypes_client  # type: ignore[import-untyped]

    _COMTYPES_AVAILABLE = True
except ImportError:  # pragma: no cover
    _COMTYPES_AVAILABLE = False

# SolidWorks type library GUID (stable across SW versions)
_SW_TLB_GUID = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"
# Cached comtypes wrapper module (loaded once per process)
_sw_comtypes_lib: Any = None


def _get_sw_comtypes_lib() -> Any:
    """Return the comtypes wrapper for the SolidWorks type library.

    Tries SW version numbers 35..30 (newest to oldest). Returns ``None`` when
    comtypes is unavailable or the TLB cannot be found in the registry.
    """
    global _sw_comtypes_lib
    if _sw_comtypes_lib is not None:
        return _sw_comtypes_lib
    if not _COMTYPES_AVAILABLE:
        return None
    for major in (35, 34, 33, 32, 31, 30):  # pragma: no cover
        try:
            _sw_comtypes_lib = _comtypes_client.GetModule(
                (comtypes.GUID(_SW_TLB_GUID), major, 0)
            )
            return _sw_comtypes_lib
        except Exception:
            continue
    return None  # pragma: no cover


def _bridge_com_to_comtypes(pywin32_obj: Any, iface: Any) -> Any:  # pragma: no cover
    """Bridge a pywin32 CDispatch/COM object to a comtypes interface pointer.

    Extracts the raw IUnknown pointer from pywin32's repr string, then
    QueryInterface-es for *iface* via comtypes.  The AddRef keeps the object
    alive through the Python reference.
    """
    unk = pywin32_obj._oleobj_.QueryInterface(pythoncom.IID_IUnknown)
    m = re.search(r"obj at (0x[0-9a-fA-F]+)", repr(unk))
    if not m:
        raise RuntimeError(f"Could not extract COM pointer from {repr(unk)!r}")
    ptr_int = int(m.group(1), 16)
    ct_unk = ctypes.cast(ptr_int, ctypes.POINTER(comtypes.IUnknown))
    ct_unk.AddRef()
    return ct_unk.QueryInterface(iface)


class SolidWorksIOMixin:
    """Expose model open/save/create/configuration methods through a mixin."""

    @staticmethod
    def _adapter(obj: Any) -> Any:
        """Return the runtime adapter object for dynamic attribute access."""
        return cast(Any, obj)

    @staticmethod
    def _is_success(value: Any) -> bool:
        """Interpret SolidWorks save API return values consistently.

        Args:
            value: Return value from ``Save*`` COM calls.

        Returns:
            bool: ``True`` when return value indicates success.
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value == 0
        return bool(value)

    def _resolve_template_path(
        self, preferred_indices: list[int], extension: str
    ) -> str | None:
        """Resolve a template path from SolidWorks user preference slots.

        Args:
            preferred_indices: Preference indices to probe in order.
            extension: Expected template extension such as ``.prtdot``.

        Returns:
            str | None: First existing template match, otherwise first non-empty
            path candidate, or ``None`` if nothing is configured.
        """
        adapter = self._adapter(self)
        existing_match: str | None = None
        first_non_empty: str | None = None
        app = adapter.swApp
        if app is None:
            return None

        for index in preferred_indices:
            template = adapter._attempt(
                lambda idx=index: app.GetUserPreferenceStringValue(idx)
            )
            if not template or not isinstance(template, str):
                continue
            if first_non_empty is None:
                first_non_empty = template
            if template.lower().endswith(extension.lower()) and os.path.exists(
                template
            ):
                existing_match = template
                break

        return existing_match or first_non_empty

    def _read_model_title(self, model: Any) -> str:
        """Read a model title regardless of COM exposing method or property.

        Args:
            model: SolidWorks model COM object.

        Returns:
            str: Best-effort model title, defaulting to ``"Untitled"``.
        """
        adapter = self._adapter(self)
        title = adapter._attempt(lambda: adapter._get_attr_or_call(model, "GetTitle"))
        if isinstance(title, str) and title:
            return title

        title_value = getattr(model, "Title", None)
        if isinstance(title_value, str) and title_value:
            return title_value

        return "Untitled"

    async def open_model(self, file_path: str) -> AdapterResult[SolidWorksModel]:
        """Open a SolidWorks model file and set it as active on the adapter.

        Args:
            file_path: Path to a ``.sldprt``, ``.sldasm``, or ``.slddrw`` file.

        Returns:
            AdapterResult[SolidWorksModel]: Model metadata for the opened document.
        """
        adapter = self._adapter(self)
        if not adapter.is_connected():
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="Not connected to SolidWorks"
            )

        def _open() -> SolidWorksModel:
            """Open the model document."""
            resolved_path = os.path.abspath(file_path)
            file_path_lower = resolved_path.lower()
            if file_path_lower.endswith(".sldprt"):
                doc_type = adapter.constants["swDocPART"]
                model_type = "Part"
            elif file_path_lower.endswith(".sldasm"):
                doc_type = adapter.constants["swDocASSEMBLY"]
                model_type = "Assembly"
            elif file_path_lower.endswith(".slddrw"):
                doc_type = adapter.constants["swDocDRAWING"]
                model_type = "Drawing"
            else:
                raise ValueError(f"Unsupported file type: {resolved_path}")

            app = adapter.swApp
            variant_ctor = getattr(getattr(win32com, "client", None), "VARIANT", None)
            vt_byref = int(getattr(pythoncom, "VT_BYREF", 0))
            vt_i4 = int(getattr(pythoncom, "VT_I4", 0))
            if callable(variant_ctor):
                errors = variant_ctor(vt_byref | vt_i4, 0)
                warnings = variant_ctor(vt_byref | vt_i4, 0)
            else:
                errors = 0
                warnings = 0
            model = app.OpenDoc6(resolved_path, doc_type, 1, "", errors, warnings)
            if not model:
                raise Exception(f"Failed to open model: {resolved_path}")

            adapter._attempt(
                lambda: _sw_type_info.flag_doc(model, int(doc_type)), default=0
            )

            adapter.currentModel = model
            # Remembered so a reconnect after a dropped COM handle can restore
            # THIS document rather than whatever happens to be active.
            adapter._active_doc_path = resolved_path
            title = self._read_model_title(model)
            active_config = adapter._attempt(lambda: model.GetActiveConfiguration())
            config = (
                adapter._attempt(lambda: active_config.GetName(), default="Default")
                if active_config
                else "Default"
            )

            return SolidWorksModel(
                path=resolved_path,
                name=title,
                type=model_type,
                is_active=True,
                configuration=config,
                properties={
                    "last_modified": (
                        model.GetSaveTime()
                        if callable(getattr(model, "GetSaveTime", None))
                        else None
                    ),
                },
            )

        return cast(
            AdapterResult[SolidWorksModel],
            adapter._handle_com_operation("open_model", _open),
        )

    async def close_model(self, save: bool = False) -> AdapterResult[None]:
        """Close the current SolidWorks model and optionally save first.

        Args:
            save: When ``True``, calls ``Save`` before closing.

        Returns:
            AdapterResult[None]: Result of the close operation.
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.WARNING, error="No active model to close"
            )
        model = adapter.currentModel
        app = adapter.swApp
        if model is None or app is None:
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error="SolidWorks application is not connected",
            )

        def _close() -> None:
            """Close the model document."""
            if save:
                model.Save()
            app.CloseDoc(model.GetTitle())
            adapter.currentModel = None

        return cast(
            AdapterResult[None],
            adapter._handle_com_operation("close_model", _close),
        )

    async def create_part(
        self, name: str | None = None, units: str | None = None
    ) -> AdapterResult[SolidWorksModel]:
        """Create a new part document and set it as active.

        Args:
            name: Reserved for future naming policy.
            units: Reserved for future units policy.

        Returns:
            AdapterResult[SolidWorksModel]: Metadata for the new part document.
        """
        adapter = self._adapter(self)
        if not adapter.is_connected():
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="Not connected to SolidWorks"
            )

        def _create() -> SolidWorksModel:
            """Create a new part."""
            _ = name, units
            model = None
            app = adapter.swApp
            if app is None:
                raise Exception("SolidWorks application is not connected")

            new_part = getattr(app, "NewPart", None)
            if callable(new_part):
                model = adapter._attempt(new_part)

            if not model:
                part_template = self._resolve_template_path([8, 0, 1, 2, 3], ".prtdot")
                if not part_template:
                    raise Exception("No part template configured in SolidWorks")
                model = app.NewDocument(part_template, 0, 0, 0)

            if not model:
                raise Exception("Failed to create new part")

            adapter._attempt(lambda: _sw_type_info.flag_doc(model, 1), default=0)
            adapter.currentModel = model
            adapter._active_doc_path = None
            title = self._read_model_title(model)
            return SolidWorksModel(
                path="",
                name=title,
                type="Part",
                is_active=True,
                configuration="Default",
                properties={"created": datetime.now().isoformat()},
            )

        return cast(
            AdapterResult[SolidWorksModel],
            adapter._handle_com_operation("create_part", _create),
        )

    async def create_assembly(
        self, name: str | None = None
    ) -> AdapterResult[SolidWorksModel]:
        """Create a new assembly document and set it as active.

        Args:
            name: Reserved for future naming policy.

        Returns:
            AdapterResult[SolidWorksModel]: Metadata for the new assembly document.
        """
        adapter = self._adapter(self)
        if not adapter.is_connected():
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="Not connected to SolidWorks"
            )

        def _create() -> SolidWorksModel:
            """Create a new assembly."""
            _ = name
            model = None
            app = adapter.swApp
            if app is None:
                raise Exception("SolidWorks application is not connected")

            new_assembly = getattr(app, "NewAssembly", None)
            if callable(new_assembly):
                model = adapter._attempt(new_assembly)

            if not model:
                asm_template = self._resolve_template_path([9, 2, 3, 1, 0], ".asmdot")
                if not asm_template:
                    raise Exception("No assembly template configured in SolidWorks")
                model = app.NewDocument(asm_template, 0, 0, 0)

            if not model:
                raise Exception("Failed to create new assembly")

            adapter._attempt(lambda: _sw_type_info.flag_doc(model, 2), default=0)
            adapter.currentModel = model
            adapter._active_doc_path = None
            title = self._read_model_title(model)
            return SolidWorksModel(
                path="",
                name=title,
                type="Assembly",
                is_active=True,
                configuration="Default",
                properties={"created": datetime.now().isoformat()},
            )

        return cast(
            AdapterResult[SolidWorksModel],
            adapter._handle_com_operation("create_assembly", _create),
        )

    async def create_drawing(
        self, name: str | None = None
    ) -> AdapterResult[SolidWorksModel]:
        """Create a new drawing document and set it as active.

        Args:
            name: Reserved for future naming policy.

        Returns:
            AdapterResult[SolidWorksModel]: Metadata for the new drawing document.
        """
        adapter = self._adapter(self)
        if not adapter.is_connected():
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="Not connected to SolidWorks"
            )

        def _create() -> SolidWorksModel:
            """Create a new drawing."""
            _ = name
            app = adapter.swApp
            if app is None:
                raise Exception("SolidWorks application is not connected")

            # swDefaultTemplateDrawing is preference 10. Index 1 was being read
            # here, which is empty on a stock install, so NewDocument got ""
            # and every create_drawing call failed.
            drw_template = self._resolve_template_path([10, 1, 6], ".drwdot")
            if not drw_template:
                # Last resort: derive it from the part template's location.
                part_template = adapter._attempt(
                    lambda: app.GetUserPreferenceStringValue(8), default=""
                )
                if isinstance(part_template, str) and part_template:
                    drw_template = part_template.replace("Part", "Drawing")

            model = app.NewDocument(drw_template, 12, 0.2794, 0.2159)
            if not model:
                raise Exception(
                    f"Failed to create new drawing from template '{drw_template}'"
                )

            adapter._attempt(lambda: _sw_type_info.flag_doc(model, 3), default=0)
            adapter.currentModel = model
            adapter._active_doc_path = None
            title = self._read_model_title(model)
            return SolidWorksModel(
                path="",
                name=title,
                type="Drawing",
                is_active=True,
                configuration="Default",
                properties={"created": datetime.now().isoformat()},
            )

        return cast(
            AdapterResult[SolidWorksModel],
            adapter._handle_com_operation("create_drawing", _create),
        )

    async def insert_component(
        self, file_path: str, x: float = 0.0, y: float = 0.0, z: float = 0.0
    ) -> AdapterResult[dict[str, Any]]:
        """Insert a part or sub-assembly into the active assembly.

        Wraps ``IAssemblyDoc::AddComponent4(CompName, ConfigName, X, Y, Z)``,
        falling back to ``AddComponent5``.  Position is in **millimetres**.

        **The component file must contain solid geometry.**  SolidWorks
        silently refuses to insert an empty part — every overload returns
        ``None`` and the component count stays put.  That behaviour is what
        made this look unimplementable until the ``save_file`` bug that was
        writing empty parts got fixed.

        Success is confirmed by the assembly's component count going up, since
        ``AddComponent*`` gives no usable failure signal.

        Args:
            file_path (str): Absolute path to the ``.sldprt`` or ``.sldasm``.
            x (float): X position in millimetres.
            y (float): Y position in millimetres.
            z (float): Z position in millimetres.

        Returns:
            AdapterResult[dict[str, Any]]: Component name and before/after
            counts.  ``ERROR`` when the active document is not an assembly, the
            file is missing, or nothing was inserted.

        Raises:
            Exception: Propagated through ``_handle_com_operation``.

        Example::

            await adapter.insert_component(r"C:\\parts\\bracket.sldprt", 0, 0, 0)
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )

        path = os.path.abspath(file_path)
        if not os.path.exists(path):
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error=f"Component file not found: {file_path}",
            )

        doc_type = _doc_type(adapter)
        if doc_type != 2:
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error=(
                    "insert_component requires an assembly document "
                    f"(active document type is {doc_type!r}, expected 2). "
                    "Call create_assembly first."
                ),
            )

        def _insert() -> dict[str, Any]:
            assembly = _sw_type_info.flagged(adapter.currentModel, "IAssemblyDoc")
            before = _component_names(adapter, assembly)

            # The document has to be loaded before it can be inserted, and the
            # errors/warnings out-parameters must be byref VARIANTs: with
            # pythoncom.Missing OpenDoc6 returns None and the part stays
            # unloaded, after which every AddComponent overload does nothing.
            app = adapter.swApp
            opened = adapter._attempt(
                lambda: app.OpenDoc6(
                    path,
                    2 if path.lower().endswith(".sldasm") else 1,
                    1,
                    "",
                    _byref_int(),
                    _byref_int(),
                ),
                default=None,
            )
            if not opened:
                raise Exception(
                    f"Could not load '{file_path}' - OpenDoc6 returned nothing."
                )

            title = adapter._attempt(
                lambda: _sw_type_info.flagged(
                    adapter.currentModel, "IModelDoc2"
                ).GetTitle(),
                default=None,
            )
            if title:
                adapter._attempt(
                    lambda: app.ActivateDoc3(title, False, 0, _byref_int()),
                    default=None,
                )

            component = adapter._attempt(
                lambda: assembly.AddComponent4(
                    path, "", x / 1000.0, y / 1000.0, z / 1000.0
                ),
                default=None,
            )
            if component is None:
                component = adapter._attempt(
                    lambda: assembly.AddComponent5(
                        path, 0, "", False, "",
                        x / 1000.0, y / 1000.0, z / 1000.0,
                    ),
                    default=None,
                )

            adapter._attempt(lambda: assembly.EditRebuild3(), default=None)

            after = _component_names(adapter, assembly)
            if len(after) <= len(before):
                raise Exception(
                    f"Component was not inserted - the assembly still has "
                    f"{len(after)} component(s). The most common cause is a "
                    f"part with no solid geometry: SolidWorks refuses those "
                    f"silently. Check '{file_path}' opens with a body."
                )

            added = [n for n in after if n not in before]
            return {
                "component": added[-1] if added else after[-1],
                "file_path": path,
                "position": {"x": x, "y": y, "z": z},
                "components_before": len(before),
                "components_after": len(after),
            }

        return cast(
            AdapterResult[dict[str, Any]],
            adapter._handle_com_operation("insert_component", _insert),
        )

    async def add_mate(
        self,
        component_a: str,
        component_b: str,
        entity_a: str = "Front Plane",
        entity_b: str = "Front Plane",
        mate_type: str = "coincident",
        alignment: str = "aligned",
        distance: float = 0.0,
        angle: float = 0.0,
    ) -> AdapterResult[dict[str, Any]]:
        """Mate two components together.

        Wraps ``IAssemblyDoc::AddMate5``.  The two entities are selected via
        ``IComponent2::FeatureByName`` + ``IFeature::Select2`` rather than
        ``SelectByID2``, which raises ``Type mismatch`` on this build.

        That restricts the entities to *named tree features* — the reference
        planes and axes of each component.  Plane-to-plane mating covers
        alignment and stacking, which is the common case; mating to a specific
        face or edge needs entity names this adapter cannot enumerate.

        Args:
            component_a (str): First component instance name, as reported by
                :meth:`list_components`.
            component_b (str): Second component instance name.
            entity_a (str): Named feature on the first component.
            entity_b (str): Named feature on the second component.
            mate_type (str): ``coincident``, ``concentric``, ``perpendicular``,
                ``parallel``, ``tangent``, ``distance`` or ``angle``.
            alignment (str): ``aligned``, ``anti_aligned`` or ``closest``.
            distance (float): Distance in millimetres, for a distance mate.
            angle (float): Angle in degrees, for an angle mate.

        Returns:
            AdapterResult[dict[str, Any]]: The mate created, plus the bounding
            box before and after so the caller can see what moved.  ``ERROR``
            when the entities cannot be selected or SolidWorks rejects the
            mate.

        Raises:
            Exception: Propagated through ``_handle_com_operation``.

        Example::

            await adapter.add_mate("plate-1", "plate-2")
        """
        adapter = self._adapter(self)
        if _doc_type(adapter) != 2:
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error="add_mate requires an assembly document",
            )

        mate_key = str(mate_type).strip().lower()
        if mate_key not in _MATE_TYPES:
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error=(
                    f"Unknown mate type '{mate_type}'. "
                    f"Use one of: {', '.join(sorted(_MATE_TYPES))}."
                ),
            )
        align_key = str(alignment).strip().lower()
        if align_key not in _MATE_ALIGNMENTS:
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error=(
                    f"Unknown alignment '{alignment}'. "
                    f"Use one of: {', '.join(sorted(_MATE_ALIGNMENTS))}."
                ),
            )

        def _mate() -> dict[str, Any]:
            import math

            model = adapter.currentModel
            assembly = _sw_type_info.flagged(model, "IAssemblyDoc")

            components = adapter._attempt(
                lambda: assembly.GetComponents(True), default=None
            )
            if not isinstance(components, (list, tuple)):
                raise Exception("Could not read the assembly's components")

            wanted = {component_a: entity_a, component_b: entity_b}
            found: dict[str, Any] = {}
            for component in components:
                wrapped = _as_com(adapter, component, "IComponent2")
                if wrapped is None:
                    continue
                name = adapter._attempt(lambda w=wrapped: w.Name2, default=None)
                if name and str(name) in wanted:
                    found[str(name)] = wrapped

            missing = [n for n in (component_a, component_b) if n not in found]
            if missing:
                available = [
                    str(adapter._attempt(lambda c=c: _as_com(adapter, c, "IComponent2").Name2, default="?"))
                    for c in components
                ]
                raise Exception(
                    f"Component(s) not found: {', '.join(missing)}. "
                    f"The assembly holds: {', '.join(available)}."
                )

            adapter._attempt(lambda: model.ClearSelection2(True), default=None)
            for index, component_name in enumerate((component_a, component_b)):
                wrapped = found[component_name]
                entity_name = wanted[component_name]
                feature = adapter._attempt(
                    lambda w=wrapped, e=entity_name: w.FeatureByName(e), default=None
                )
                if feature is None:
                    raise Exception(
                        f"'{entity_name}' not found on {component_name}. "
                        "Only named tree features (reference planes and axes) "
                        "can be selected here."
                    )
                flagged = _as_com(adapter, feature, "IFeature")
                if flagged is None or not adapter._attempt(
                    lambda f=flagged, a=index > 0: f.Select2(a, 0), default=False
                ):
                    raise Exception(
                        f"Failed to select '{entity_name}' on {component_name}"
                    )

            selected = adapter._attempt(
                lambda: model.SelectionManager.GetSelectedObjectCount2(-1), default=0
            )
            if selected != 2:
                raise Exception(
                    f"Expected 2 selected entities for the mate, got {selected}"
                )

            box_before = _bounding_box_tuple(adapter)
            status = _byref_int()
            mate = adapter._attempt(
                lambda: assembly.AddMate5(
                    _MATE_TYPES[mate_key],
                    _MATE_ALIGNMENTS[align_key],
                    False,  # Flip
                    distance / 1000.0,  # Distance (m)
                    distance / 1000.0,  # upper limit
                    distance / 1000.0,  # lower limit
                    0.0,  # gear ratio numerator
                    0.0,  # gear ratio denominator
                    math.radians(float(angle)),
                    math.radians(float(angle)),
                    math.radians(float(angle)),
                    False,  # ForPositioningOnly
                    False,  # LockRotation
                    0,  # WidthMateOption
                    status,
                ),
                default=None,
            )
            adapter._attempt(lambda: model.EditRebuild3(), default=None)

            error_status = getattr(status, "value", None)
            # swAddMateError_e reports 1 for success on this build (measured:
            # a mate that demonstrably moved a component returned 1).
            if mate is None or (error_status not in (None, 1)):
                raise Exception(
                    f"SolidWorks rejected the {mate_key} mate "
                    f"(error status {error_status!r}). Check the two entities "
                    "can actually satisfy this mate type."
                )

            box_after = _bounding_box_tuple(adapter)
            return {
                "mate_type": mate_key,
                "alignment": align_key,
                "components": [component_a, component_b],
                "entities": [entity_a, entity_b],
                "distance": distance or None,
                "angle": angle or None,
                "bounding_box_before": box_before,
                "bounding_box_after": box_after,
                "geometry_moved": box_before != box_after,
            }

        return cast(
            AdapterResult[dict[str, Any]],
            adapter._handle_com_operation("add_mate", _mate),
        )

    async def list_components(self) -> AdapterResult[list[str]]:
        """List the top-level components of the active assembly.

        Returns:
            AdapterResult[list[str]]: Component names, or an error when the
            active document is not an assembly.
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )
        doc_type = _doc_type(adapter)
        if doc_type != 2:
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error=(
                    "list_components requires an assembly document "
                    f"(active document type is {doc_type!r}, expected 2)"
                ),
            )

        def _list() -> list[str]:
            assembly = _sw_type_info.flagged(adapter.currentModel, "IAssemblyDoc")
            return _component_names(adapter, assembly)

        return cast(
            AdapterResult[list[str]],
            adapter._handle_com_operation("list_components", _list),
        )

    def _require_drawing(self) -> AdapterResult[Any] | None:
        """Return an error result unless the active document is a drawing.

        Returns:
            AdapterResult[Any] | None: ``None`` when the active document is a
            drawing, otherwise the error to hand back.
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )
        doc_type = _doc_type(adapter)
        if doc_type != 3:
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error=(
                    "This operation requires a drawing document "
                    f"(active document type is {doc_type!r}, expected 3). "
                    "Call create_drawing first."
                ),
            )
        return None

    async def add_drawing_view(
        self,
        model_path: str,
        orientation: str = "front",
        x: float = 100.0,
        y: float = 150.0,
        scale: float = 0.0,
    ) -> AdapterResult[dict[str, Any]]:
        """Place a view of a model on the active drawing sheet.

        Wraps ``IDrawingDoc::CreateDrawViewFromModelView3(ModelName, ViewName,
        LocX, LocY, LocZ)``.  ``ViewName`` is a SolidWorks *named view*
        (``"*Front"``, ``"*Isometric"``, …); position is in **millimetres** and
        converted to metres.

        The model has to be loaded before a view of it can be placed, so it is
        opened first and the drawing reactivated.

        Success is confirmed by the sheet's view count going up — this call
        returns ``None`` for a model SolidWorks could not resolve.

        Args:
            model_path (str): Absolute path to the part or assembly.
            orientation (str): ``front``, ``back``, ``left``, ``right``,
                ``top``, ``bottom``, ``isometric``, ``trimetric``,
                ``dimetric``, or a raw ``*Name``.
            x (float): Sheet X position in millimetres.
            y (float): Sheet Y position in millimetres.
            scale (float): View scale; ``0`` keeps the sheet scale.

        Returns:
            AdapterResult[dict[str, Any]]: The new view's name and position.

        Raises:
            Exception: Propagated through ``_handle_com_operation``.

        Example::

            await adapter.add_drawing_view(r"C:\\parts\\bracket.sldprt", "front")
        """
        adapter = self._adapter(self)
        guard = self._require_drawing()
        if guard is not None:
            return cast("AdapterResult[dict[str, Any]]", guard)

        path = os.path.abspath(model_path)
        if not os.path.exists(path):
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error=f"Model file not found: {model_path}",
            )

        view_name = _NAMED_VIEWS.get(str(orientation).strip().lower())
        if view_name is None:
            view_name = orientation if str(orientation).startswith("*") else None
        if view_name is None:
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error=(
                    f"Unknown orientation '{orientation}'. Use one of: "
                    f"{', '.join(sorted(_NAMED_VIEWS))}, or a raw '*Name'."
                ),
            )

        def _add() -> dict[str, Any]:
            drawing = _sw_type_info.flagged(adapter.currentModel, "IDrawingDoc")
            before = _view_names(adapter, drawing)

            app = adapter.swApp
            doc_type = 2 if path.lower().endswith(".sldasm") else 1
            opened = adapter._attempt(
                lambda: app.OpenDoc6(
                    path, doc_type, 1, "", _byref_int(), _byref_int()
                ),
                default=None,
            )
            if not opened:
                raise Exception(
                    f"Could not load '{model_path}' - OpenDoc6 returned nothing."
                )
            title = adapter._attempt(
                lambda: _sw_type_info.flagged(
                    adapter.currentModel, "IModelDoc2"
                ).GetTitle(),
                default=None,
            )
            if title:
                adapter._attempt(
                    lambda: app.ActivateDoc3(title, False, 0, _byref_int()),
                    default=None,
                )

            view = adapter._attempt(
                lambda: drawing.CreateDrawViewFromModelView3(
                    path, view_name, x / 1000.0, y / 1000.0, 0.0
                ),
                default=None,
            )

            after = _view_names(adapter, drawing)
            if len(after) <= len(before):
                raise Exception(
                    f"View was not created - the sheet still has {len(after)} "
                    f"view(s). Check that '{model_path}' opens on its own."
                )

            added = [n for n in after if n not in before]
            new_view = added[-1] if added else after[-1]
            if scale and view is not None:
                wrapped = _as_com(adapter, view, "IView")
                if wrapped is not None:
                    adapter._attempt(
                        lambda: setattr(wrapped, "ScaleRatio", [scale, 1.0]),
                        default=None,
                    )

            return {
                "name": new_view,
                "model_path": path,
                "orientation": view_name,
                "position": {"x": x, "y": y},
                "scale": scale or None,
                "views_before": len(before),
                "views_after": len(after),
            }

        return cast(
            AdapterResult[dict[str, Any]],
            adapter._handle_com_operation("add_drawing_view", _add),
        )

    async def create_standard_views(
        self, model_path: str, third_angle: bool = True
    ) -> AdapterResult[dict[str, Any]]:
        """Drop the three standard views of a model onto the active sheet.

        Wraps ``IDrawingDoc::Create3rdAngleViews2`` (or
        ``Create1stAngleViews2``), which lays out front, top and side in one
        call and is the fastest way to start a drawing.

        Args:
            model_path (str): Absolute path to the part or assembly.
            third_angle (bool): Third-angle projection (US) rather than
                first-angle (ISO).

        Returns:
            AdapterResult[dict[str, Any]]: The view names that appeared.
            ``ERROR`` when the active document is not a drawing, the model is
            missing, or no views were added.

        Raises:
            Exception: Propagated through ``_handle_com_operation``.

        Example::

            await adapter.create_standard_views(r"C:\\parts\\bracket.sldprt")
        """
        adapter = self._adapter(self)
        guard = self._require_drawing()
        if guard is not None:
            return cast("AdapterResult[dict[str, Any]]", guard)

        path = os.path.abspath(model_path)
        if not os.path.exists(path):
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error=f"Model file not found: {model_path}",
            )

        def _standard() -> dict[str, Any]:
            drawing = _sw_type_info.flagged(adapter.currentModel, "IDrawingDoc")
            before = _view_names(adapter, drawing)

            created = adapter._attempt(
                lambda: (
                    drawing.Create3rdAngleViews2(path)
                    if third_angle
                    else drawing.Create1stAngleViews2(path)
                ),
                default=False,
            )

            after = _view_names(adapter, drawing)
            added = [n for n in after if n not in before]
            if not added:
                raise Exception(
                    f"No views were created from '{model_path}' (the call "
                    f"returned {created!r}). Check the model has solid "
                    "geometry and opens on its own."
                )

            return {
                "views": added,
                "model_path": path,
                "projection": "third_angle" if third_angle else "first_angle",
                "views_before": len(before),
                "views_after": len(after),
            }

        return cast(
            AdapterResult[dict[str, Any]],
            adapter._handle_com_operation("create_standard_views", _standard),
        )

    async def add_drawing_note(
        self, text: str, x: float = 100.0, y: float = 50.0, font_size: float = 0.0
    ) -> AdapterResult[dict[str, Any]]:
        """Place a text note on the active drawing sheet.

        Wraps ``IModelDoc2::InsertNote(Text)`` and then positions the returned
        annotation.  ``InsertNote`` places the note wherever SolidWorks likes,
        so the position is applied afterwards via ``IAnnotation::SetPosition``.

        Args:
            text (str): Note text.
            x (float): Sheet X position in millimetres.
            y (float): Sheet Y position in millimetres.
            font_size (float): Text height in millimetres; ``0`` keeps the
                document default.

        Returns:
            AdapterResult[dict[str, Any]]: The note text and where it landed.

        Raises:
            Exception: Propagated through ``_handle_com_operation``.

        Example::

            await adapter.add_drawing_note("MATERIAL: AISI 1018", 200.0, 50.0)
        """
        adapter = self._adapter(self)
        guard = self._require_drawing()
        if guard is not None:
            return cast("AdapterResult[dict[str, Any]]", guard)
        if not text:
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error="add_drawing_note requires text",
            )

        def _add_note() -> dict[str, Any]:
            model = adapter.currentModel
            adapter._attempt(lambda: model.ClearSelection2(True), default=None)

            note = adapter._attempt(lambda: model.InsertNote(str(text)), default=None)
            if note is None:
                raise Exception(
                    "InsertNote returned nothing - the note was not created."
                )

            positioned = False
            annotation = adapter._attempt(
                lambda: _sw_type_info.flagged(note, "INote").GetAnnotation(),
                default=None,
            )
            if annotation is not None:
                positioned = bool(
                    adapter._attempt(
                        lambda: _sw_type_info.flagged(
                            annotation, "IAnnotation"
                        ).SetPosition(x / 1000.0, y / 1000.0, 0.0),
                        default=False,
                    )
                )

            if font_size:
                adapter._attempt(
                    lambda: _sw_type_info.flagged(note, "INote").SetTextFormat(
                        0, False, font_size / 1000.0
                    ),
                    default=None,
                )

            adapter._attempt(lambda: model.EditRebuild3(), default=None)
            return {
                "text": text,
                "position": {"x": x, "y": y},
                "positioned": positioned,
                "font_size": font_size or None,
            }

        return cast(
            AdapterResult[dict[str, Any]],
            adapter._handle_com_operation("add_drawing_note", _add_note),
        )

    async def insert_model_dimensions(
        self, all_views: bool = True
    ) -> AdapterResult[dict[str, Any]]:
        """Import the model's dimensions onto the drawing views.

        Wraps ``IDrawingDoc::InsertModelAnnotations3(Option, Types, AllViews,
        DuplicateDims, HiddenFeatureDims, UsePlacementInSketch)`` with
        ``Types`` set to dimensions only.  This is what "auto dimension" means
        in practice: the dimensions used to build the model are shown, rather
        than new ones being invented.

        Args:
            all_views (bool): Annotate every view instead of only the active
                one.

        Returns:
            AdapterResult[dict[str, Any]]: How many annotations were inserted.

        Raises:
            Exception: Propagated through ``_handle_com_operation``.
        """
        adapter = self._adapter(self)
        guard = self._require_drawing()
        if guard is not None:
            return cast("AdapterResult[dict[str, Any]]", guard)

        def _insert_dims() -> dict[str, Any]:
            drawing = _sw_type_info.flagged(adapter.currentModel, "IDrawingDoc")
            inserted = adapter._attempt(
                lambda: drawing.InsertModelAnnotations3(
                    0,  # Option: import from the whole model
                    1,  # Types: swInsertAnnotation_DisplayData / dimensions
                    bool(all_views),
                    True,  # DuplicateDims
                    False,  # HiddenFeatureDims
                    False,  # UsePlacementInSketch
                ),
                default=None,
            )
            adapter._attempt(
                lambda: adapter.currentModel.EditRebuild3(), default=None
            )

            count = int(inserted) if isinstance(inserted, (int, float)) else 0
            if count <= 0:
                raise Exception(
                    "No dimensions were inserted. The views may already carry "
                    "them, or the model may have no dimensions marked for "
                    "drawing."
                )
            return {"annotations_inserted": count, "all_views": bool(all_views)}

        return cast(
            AdapterResult[dict[str, Any]],
            adapter._handle_com_operation("insert_model_dimensions", _insert_dims),
        )

    async def list_drawing_views(self) -> AdapterResult[list[str]]:
        """List the views on the active drawing.

        Returns:
            AdapterResult[list[str]]: View names, sheet formats excluded.
        """
        adapter = self._adapter(self)
        guard = self._require_drawing()
        if guard is not None:
            return cast("AdapterResult[list[str]]", guard)

        def _list() -> list[str]:
            drawing = _sw_type_info.flagged(adapter.currentModel, "IDrawingDoc")
            return _view_names(adapter, drawing)

        return cast(
            AdapterResult[list[str]],
            adapter._handle_com_operation("list_drawing_views", _list),
        )

    async def get_dimension(self, name: str) -> AdapterResult[float]:
        """Read a named model dimension in millimetres.

        Args:
            name: Fully-qualified dimension name.

        Returns:
            AdapterResult[float]: Dimension value in millimetres.
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )

        def _get() -> float:  # pragma: no cover
            """Get the dimension value."""
            dimension = adapter.currentModel.Parameter(name)
            if not dimension:
                raise Exception(f"Dimension '{name}' not found")
            # SystemValue is reliable on SW 2025 (in meters, convert to mm)
            value = adapter._attempt(lambda: dimension.SystemValue, default=None)
            if value is None:
                # Fall back to GetValue3 for older SW versions
                value = adapter._attempt(
                    lambda: dimension.GetValue3(0, 0), default=None
                )
            if value is None:
                raise Exception(f"Failed to read dimension '{name}'")
            return float(value) * 1000

        return cast(
            AdapterResult[float],
            adapter._handle_com_operation("get_dimension", _get),
        )

    async def set_dimension(self, name: str, value: float) -> AdapterResult[None]:
        """Set a named model dimension in millimetres and rebuild.

        Args:
            name: Fully-qualified dimension name.
            value: New value in millimetres.

        Returns:
            AdapterResult[None]: Result of the set operation.
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )

        def _set() -> None:
            """Set the dimension value."""
            dimension = adapter.currentModel.Parameter(name)
            if not dimension:
                raise Exception(f"Dimension '{name}' not found")

            # SetValue3 has gen_py parameter mapping issues on SW 2025.
            # SystemValue (in meters) is reliable.
            value_m = value / 1000.0
            adapter._attempt(
                lambda: setattr(dimension, "SystemValue", value_m),
                default=None,
            )

            # Rebuild: try EditRebuild3 first, fall back to ForceRebuild3
            rebuilt = adapter._attempt(
                lambda: adapter.currentModel.EditRebuild3(), default=None
            )
            if rebuilt is None:
                rebuilt = adapter._attempt(
                    lambda: adapter.currentModel.ForceRebuild3(True), default=None
                )
            if rebuilt is None:
                raise Exception("Failed to set dimension")

        return cast(
            AdapterResult[None],
            adapter._handle_com_operation("set_dimension", _set),
        )

    async def save_file(self, file_path: str | None = None) -> AdapterResult[None]:
        """Save the active model to its current path or to a new file path.

        Args:
            file_path: Optional target path for Save As.

        Returns:
            AdapterResult[None]: Result of the save operation.
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )

        def _save() -> None:
            """Save the model."""
            if file_path:
                resolved_path = os.path.abspath(file_path)
                directory = os.path.dirname(resolved_path)
                if directory:
                    os.makedirs(directory, exist_ok=True)

                current_path = adapter._attempt(
                    lambda: adapter._get_attr_or_call(
                        adapter.currentModel, "GetPathName"
                    ),
                    default="",
                )
                same_file = bool(current_path) and os.path.normcase(
                    os.path.abspath(str(current_path))
                ) == os.path.normcase(resolved_path)

                if same_file:
                    # Saving a document over its own path is a plain Save.
                    # It used to run the Save-As branch below, which closed the
                    # document and deleted the file before calling SaveAs3 on
                    # the now-closed doc - that wrote an empty part and lost the
                    # geometry.
                    save_result = adapter._attempt(
                        lambda: adapter.currentModel.Save3(1, None, None)
                    )
                    if save_result is None:
                        save_fn = getattr(adapter.currentModel, "Save", None)
                        if callable(save_fn):
                            save_result = save_fn()
                    if not os.path.exists(resolved_path):
                        raise Exception(f"File not written after save: {resolved_path}")
                    adapter._active_doc_path = resolved_path
                    return

                # A *different* document may be holding the target path open.
                # Close that one only - never the document being saved.
                if adapter.swApp:
                    adapter._attempt(
                        lambda: adapter.swApp.CloseDoc(os.path.basename(resolved_path))
                    )

                # Deliberately no os.remove here: SaveAs3 overwrites, and
                # deleting first meant a failed save destroyed the old file too.
                save_as3_result = adapter.currentModel.SaveAs3(resolved_path, 0, 0)
                if not self._is_success(save_as3_result):
                    save_as = getattr(adapter.currentModel, "SaveAs", None)
                    if callable(save_as):
                        fallback_result = save_as(resolved_path)
                        if not self._is_success(fallback_result):
                            raise Exception(f"Failed to save as: {resolved_path}")
                    else:
                        raise Exception(f"Failed to save as: {resolved_path}")

                if not os.path.exists(resolved_path):
                    raise Exception(f"File not written after save: {resolved_path}")
                adapter._active_doc_path = resolved_path
                return

            save_result = adapter._attempt(
                lambda: adapter.currentModel.Save3(1, None, None)
            )
            if save_result is None:
                save_fn = getattr(adapter.currentModel, "Save", None)
                if callable(save_fn):
                    save_result = save_fn()
                else:
                    raise Exception("Failed to save file")

            if self._is_success(save_result):
                return

            path_attr = getattr(adapter.currentModel, "GetPathName", "")
            model_path = path_attr() if callable(path_attr) else path_attr
            if model_path and os.path.exists(model_path):
                return
            raise Exception("Failed to save file")

        return cast(
            AdapterResult[None],
            adapter._handle_com_operation("save_file", _save),
        )

    async def rebuild_model(self) -> AdapterResult[None]:
        """Force a model rebuild.

        Returns:
            AdapterResult[None]: Result of the rebuild operation.
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )

        def _rebuild() -> None:
            """Rebuild the model."""
            success = adapter.currentModel.ForceRebuild3(False)
            if not success:
                raise Exception("Failed to rebuild model")

        return cast(
            AdapterResult[None],
            adapter._handle_com_operation("rebuild_model", _rebuild),
        )

    async def get_model_info(self) -> AdapterResult[dict[str, Any]]:
        """Collect summary metadata about the active model.

        Returns:
            AdapterResult[dict[str, Any]]: Model information payload.
        """
        adapter = self._adapter(self)
        active_model = (
            getattr(adapter.swApp, "ActiveDoc", None) if adapter.swApp else None
        )
        if active_model is not None:
            adapter.currentModel = active_model
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )

        def _get_info() -> dict[str, Any]:
            """Get model information."""
            # With late-bound SolidWorks COM, GetActiveConfiguration is
            # exposed as an object-valued property even though the API names
            # it like a method. Calling that COM object raises "member not
            # found", so read it directly.
            active_config = getattr(
                adapter.currentModel, "GetActiveConfiguration", None
            )
            # 'Name' on Configuration is a property, not a method.
            config_name = (
                getattr(active_config, "Name", "Default")
                if active_config
                else "Default"
            )
            # Try GetSaveFlag (method) first, fallback to property
            is_dirty_raw = adapter._attempt(
                lambda: adapter._get_attr_or_call(adapter.currentModel, "GetSaveFlag"),
                default=None,
            )
            is_dirty = bool(is_dirty_raw) if is_dirty_raw is not None else None
            feature_count = adapter._attempt(
                lambda: int(
                    adapter.currentModel.FeatureManager.GetFeatureCount(True) or 0
                ),
                default=0,
            )
            rebuild_status_raw = adapter._attempt(
                lambda: adapter.currentModel.GetRebuildStatus(), default=None
            )
            # GetRebuildStatus returns 0=ok, 1=needs rebuild, or None=failed
            rebuild_status = (
                rebuild_status_raw if rebuild_status_raw is not None else None
            )
            return {
                "title": adapter._get_attr_or_call(adapter.currentModel, "GetTitle"),
                "path": adapter._get_attr_or_call(adapter.currentModel, "GetPathName"),
                "type": adapter._get_document_type(),
                "configuration": config_name,
                "is_dirty": is_dirty,
                "feature_count": feature_count,
                "rebuild_status": rebuild_status,
            }

        return cast(
            AdapterResult[dict[str, Any]],
            adapter._handle_com_operation("get_model_info", _get_info),
        )

    async def list_configurations(self) -> AdapterResult[list[str]]:
        """List all configuration names on the active model.

        Returns:
            AdapterResult[list[str]]: Configuration names, or empty list when unavailable.
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error="No active model",
            )

        def _list() -> list[str]:
            """List configurations."""
            raw_names = getattr(adapter.currentModel, "GetConfigurationNames", None)
            names = raw_names() if callable(raw_names) else raw_names
            if names is None:
                names = []
            if isinstance(names, str):
                return [names]

            normalized_names = [str(name) for name in names]
            if normalized_names:
                return normalized_names

            active_config = adapter._attempt(
                lambda: adapter.currentModel.GetActiveConfiguration(), default=None
            )
            active_name = adapter._attempt(
                lambda: active_config.GetName(), default=None
            )
            if active_name:
                return [str(active_name)]
            return []

        return cast(
            AdapterResult[list[str]],
            adapter._handle_com_operation("list_configurations", _list),
        )

    async def get_mass_properties(self) -> AdapterResult[MassProperties]:
        """Get mass properties for the active model.

        Returns:
            AdapterResult[MassProperties]: Computed mass, volume, area, COM, and inertia.
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )

        def _get() -> MassProperties:
            """Get mass properties."""
            adapter._attempt(
                lambda: adapter.currentModel.ForceRebuild3(False), default=None
            )

            # Primary: Extension.CreateMassProperty() object API (most detailed)
            mass_props = adapter._attempt(
                lambda: adapter.currentModel.Extension.CreateMassProperty(),
                default=None,
            )

            if mass_props:
                volume = mass_props.Volume * 1e9
                surface_area = mass_props.SurfaceArea * 1e6
                mass = mass_props.Mass

                center_of_mass = [0.0, 0.0, 0.0]
                com = adapter._attempt(lambda: mass_props.CenterOfMass, default=None)
                if isinstance(com, (list, tuple)) and len(com) >= 3:
                    center_of_mass = [com[0] * 1000, com[1] * 1000, com[2] * 1000]

                moi = adapter._attempt(
                    lambda: mass_props.GetMomentOfInertia(0), default=None
                )
                if not isinstance(moi, (list, tuple)) or len(moi) < 9:
                    moi = [0.0] * 9
            else:
                # Fallback: GetMassProperties as attribute (tuple) or callable (SW 2022)
                gmp = getattr(adapter.currentModel, "GetMassProperties", None)
                if callable(gmp):
                    raw = adapter._attempt(gmp, default=None)
                elif isinstance(gmp, (list, tuple)):
                    raw = gmp
                else:
                    raw = None

                if not isinstance(raw, (list, tuple)) or len(raw) < 6:
                    raise Exception("Failed to get mass properties")

                center_of_mass = [
                    raw[0] * 1000.0,
                    raw[1] * 1000.0,
                    raw[2] * 1000.0,
                ]
                volume = raw[3] * 1e9
                surface_area = raw[4] * 1e6
                mass = raw[5]

                moi = [0.0] * 9
                if len(raw) >= 12:
                    moi[0] = raw[6]
                    moi[4] = raw[7]
                    moi[8] = raw[8]
                    moi[1] = raw[9]
                    moi[5] = raw[10]
                    moi[2] = raw[11]

            return MassProperties(
                volume=volume,
                surface_area=surface_area,
                mass=mass,
                center_of_mass=center_of_mass,
                moments_of_inertia={
                    "Ixx": moi[0],
                    "Iyy": moi[4],
                    "Izz": moi[8],
                    "Ixy": moi[1],
                    "Ixz": moi[2],
                    "Iyz": moi[5],
                },
            )

        return cast(
            AdapterResult[MassProperties],
            adapter._handle_com_operation("get_mass_properties", _get),
        )

    async def check_interference(
        self, params: dict[str, Any] | None = None
    ) -> AdapterResult[dict[str, Any]]:
        """Run SolidWorks' interference detection on the active assembly.

        Uses ``IAssemblyDoc::ToolsCheckInterference2``, whose gen_py signature is
        ``(NumComponents, LpComponents, CoincidentInterference, PComp[out],
        PFace[out]) -> long``.  The **return value is a count**, which is what
        makes an honest answer possible here: ``0`` means SolidWorks really
        found nothing, while a COM failure raises and is reported as an error
        rather than being flattened into a false "no interference".

        Passing ``NumComponents=0`` checks the whole assembly.

        Args:
            params (dict[str, Any] | None): Optional settings.  ``coincident``
                (bool, default ``False``) treats coincident faces as
                interference.

        Returns:
            AdapterResult[dict[str, Any]]: ``interference_found``, the
            ``interference_count``, and the component-name pairs SolidWorks
            reported.  ``ERROR`` when there is no active model or the active
            document is not an assembly.

        Raises:
            Exception: Propagated through ``_handle_com_operation``.
        """
        adapter = self._adapter(self)
        options = params or {}

        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )

        doc_type = _doc_type(adapter)
        if doc_type != 2:
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error=(
                    "Interference detection requires an assembly document "
                    f"(active document type is {doc_type!r}, expected 2)"
                ),
            )

        coincident = bool(options.get("coincident", False))

        def _check() -> dict[str, Any]:
            import pythoncom

            raw = adapter.currentModel.ToolsCheckInterference2(
                0, None, coincident, pythoncom.Missing, pythoncom.Missing
            )

            # Out-parameters come back appended to the return value under
            # late binding, so the shape is either a bare count or
            # (count, comps, faces).
            comps: Any = None
            if isinstance(raw, (list, tuple)):
                count = int(raw[0]) if raw else 0
                if len(raw) > 1:
                    comps = raw[1]
            else:
                count = int(raw or 0)

            # ToolsCheckInterference2 returns components two-per-interference.
            names: list[str] = []
            if isinstance(comps, (list, tuple)):
                for comp in comps:
                    name = adapter._attempt(lambda c=comp: c.Name2, default=None)
                    if not name:
                        name = adapter._attempt(
                            lambda c=comp: c.GetSelectByIDString(), default=None
                        )
                    names.append(str(name) if name else "<unnamed>")

            pairs = [
                {"component_1": names[i], "component_2": names[i + 1]}
                for i in range(0, len(names) - 1, 2)
            ]

            return {
                "interference_found": count > 0,
                "interference_count": count,
                "interferences": pairs,
                "coincident_treated_as_interference": coincident,
            }

        return cast(
            AdapterResult[dict[str, Any]],
            adapter._handle_com_operation("check_interference", _check),
        )

    async def set_material(
        self, name: str, database: str | None = None
    ) -> AdapterResult[dict[str, Any]]:
        """Assign a material to the active part.

        Wraps ``IPartDoc::SetMaterialPropertyName2(ConfigName, Database,
        Name)``.  When ``database`` is omitted the stock SolidWorks library is
        located from the application's install path, since the call needs a
        real ``.sldmat`` file rather than a bare library name.

        The assignment is confirmed by reading the material back — the setter
        returns nothing useful, so it cannot be trusted on its own.

        Args:
            name (str): Material name exactly as it appears in the library,
                e.g. ``"Plain Carbon Steel"`` or ``"6061 Alloy"``.
            database (str | None): Path to a ``.sldmat`` file. Defaults to the
                stock ``solidworks materials.sldmat``.

        Returns:
            AdapterResult[dict[str, Any]]: The material that is actually
            assigned afterwards.  ``ERROR`` when the active document is not a
            part or the name did not take.

        Raises:
            Exception: Propagated through ``_handle_com_operation``.

        Example::

            await adapter.set_material("Plain Carbon Steel")
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )
        if not name or not str(name).strip():
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error="set_material requires a material name",
            )

        doc_type = _doc_type(adapter)
        if doc_type != 1:
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error=(
                    "set_material requires a part document "
                    f"(active document type is {doc_type!r}, expected 1)"
                ),
            )

        def _set() -> dict[str, Any]:
            model = adapter.currentModel
            config = adapter._attempt(
                lambda: model.GetActiveConfiguration(), default=None
            )
            config_name = adapter._attempt(lambda: config.Name, default="") or ""

            resolved_db = database or self._default_material_database()
            adapter._attempt(
                lambda: model.SetMaterialPropertyName2(
                    config_name, resolved_db or "", str(name)
                ),
                default=None,
            )
            adapter._attempt(lambda: model.ForceRebuild3(False), default=None)

            # The setter reports nothing useful; read the material back.
            applied, library = _read_material_name(adapter, model, config_name)
            applied = str(applied) if applied else None

            if not applied or applied.strip().lower() != str(name).strip().lower():
                raise Exception(
                    f"Material did not take: asked for '{name}', the part now "
                    f"reports {applied!r}. Check the name matches the library "
                    f"exactly (database: {resolved_db or '<default>'})."
                )

            return {
                "name": applied,
                "database": str(library) if library else resolved_db,
                "configuration": config_name or None,
            }

        return cast(
            AdapterResult[dict[str, Any]],
            adapter._handle_com_operation("set_material", _set),
        )

    def _default_material_database(self) -> str:
        """Locate the stock SolidWorks material library.

        ``SetMaterialPropertyName2`` wants a real ``.sldmat`` path, not a
        library name, so this walks out from the running executable.

        Returns:
            str: Absolute path to ``solidworks materials.sldmat``, or ``""``
            when it cannot be found.
        """
        adapter = self._adapter(self)
        app = adapter.swApp
        if app is None:
            return ""

        exe = adapter._attempt(
            lambda: adapter._get_attr_or_call(app, "GetExecutablePath"), default=None
        )
        if not isinstance(exe, str) or not exe:
            return ""

        root = exe if os.path.isdir(exe) else os.path.dirname(exe)
        # Only "english" is worth special-casing; any other locale is found by
        # the lang/ directory walk below. A second entry here used to read
        # "Engl.ish", which no install directory can ever match.
        for language in ("english",):
            candidate = os.path.join(
                root, "lang", language, "sldmaterials", "solidworks materials.sldmat"
            )
            if os.path.exists(candidate):
                return candidate

        lang_root = os.path.join(root, "lang")
        if os.path.isdir(lang_root):
            for entry in os.listdir(lang_root):
                candidate = os.path.join(
                    lang_root, entry, "sldmaterials", "solidworks materials.sldmat"
                )
                if os.path.exists(candidate):
                    return candidate
        return ""

    async def set_appearance(
        self,
        red: float,
        green: float,
        blue: float,
        transparency: float = 0.0,
    ) -> AdapterResult[dict[str, Any]]:
        """Set the model's display colour and transparency.

        Wraps ``IModelDocExtension::SetMaterialPropertyValues``, whose array is
        nine doubles in 0..1: ``[R, G, B, ambient, diffuse, specular,
        shininess, transparency, emission]``.  Existing lighting values are
        preserved — only the colour and transparency entries are replaced — so
        setting a colour does not flatten the model's shading.

        Colour channels are accepted as 0..1 or 0..255 and normalised.

        The result is confirmed by reading the values back.

        Args:
            red (float): Red channel.
            green (float): Green channel.
            blue (float): Blue channel.
            transparency (float): 0 opaque .. 1 fully transparent.

        Returns:
            AdapterResult[dict[str, Any]]: The colour actually applied.

        Raises:
            Exception: Propagated through ``_handle_com_operation``.

        Example::

            await adapter.set_appearance(255, 0, 0)      # red
            await adapter.set_appearance(0.2, 0.4, 1.0, transparency=0.5)
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )

        channels = [red, green, blue]
        if any(c < 0 for c in channels) or transparency < 0 or transparency > 1:
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error=(
                    "Colour channels must be >= 0 and transparency between "
                    "0 and 1"
                ),
            )
        # Accept either 0..1 or 0..255.
        if any(c > 1.0 for c in channels):
            if any(c > 255.0 for c in channels):
                return AdapterResult(
                    status=AdapterResultStatus.ERROR,
                    error="Colour channels must be 0-1 or 0-255",
                )
            channels = [c / 255.0 for c in channels]

        def _apply() -> dict[str, Any]:
            extension = adapter.currentModel.Extension
            current = adapter._attempt(
                lambda: extension.GetMaterialPropertyValues(1, None), default=None
            )
            values = (
                [float(v) for v in current]
                if isinstance(current, (list, tuple)) and len(current) >= 9
                else [0.5, 0.5, 0.5, 1.0, 1.0, 0.3, 0.3, 0.0, 0.0]
            )
            values[0], values[1], values[2] = channels
            values[7] = float(transparency)

            # SetMaterialPropertyValues raises on a plain Python list; it needs
            # a real SAFEARRAY of doubles.
            adapter._attempt(
                lambda: extension.SetMaterialPropertyValues(
                    _variant_doubles(values), 1, None
                ),
                default=None,
            )
            adapter._attempt(
                lambda: adapter.currentModel.GraphicsRedraw2(), default=None
            )

            applied = adapter._attempt(
                lambda: extension.GetMaterialPropertyValues(1, None), default=None
            )
            if not isinstance(applied, (list, tuple)) or len(applied) < 9:
                raise Exception(
                    "Colour could not be read back, so it cannot be confirmed"
                )

            close = all(
                abs(float(applied[i]) - channels[i]) < 0.01 for i in range(3)
            )
            if not close:
                raise Exception(
                    f"Colour did not take: asked for "
                    f"{[round(c, 3) for c in channels]}, the model reports "
                    f"{[round(float(applied[i]), 3) for i in range(3)]}."
                )

            return {
                "color": {
                    "r": round(float(applied[0]), 4),
                    "g": round(float(applied[1]), 4),
                    "b": round(float(applied[2]), 4),
                },
                "color_255": [round(float(applied[i]) * 255) for i in range(3)],
                "transparency": round(float(applied[7]), 4),
            }

        return cast(
            AdapterResult[dict[str, Any]],
            adapter._handle_com_operation("set_appearance", _apply),
        )

    async def get_material_properties(self) -> AdapterResult[dict[str, Any]]:
        """Read the material actually assigned to the active part.

        Name comes from ``IPartDoc::GetMaterialPropertyName2(ConfigName,
        Database[out])``.  Density is derived from the model's own mass and
        volume rather than looked up, so it reflects what SolidWorks is really
        using.

        Mechanical properties (elastic modulus, yield strength, Poisson's
        ratio, thermal values) are **not** exposed through this COM path —
        ``GetMaterialPropertyValues2`` returns *visual* properties, not
        physical ones.  They are reported as ``None`` with an explanatory
        ``notes`` entry instead of being filled in with plausible defaults.

        Returns:
            AdapterResult[dict[str, Any]]: Material name, database, derived
            density, and the config it was read from.  ``ERROR`` when there is
            no active model.

        Raises:
            Exception: Propagated through ``_handle_com_operation``.
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )

        def _get() -> dict[str, Any]:
            model = adapter.currentModel
            config = adapter._attempt(
                lambda: model.GetActiveConfiguration(), default=None
            )
            config_name = adapter._attempt(lambda: config.Name, default="") or ""

            name, database = _read_material_name(adapter, model, config_name)
            name = str(name) if name else None
            assigned = bool(name and name.strip())

            # Density from the model itself: kg / m^3.
            density = None
            gmp = getattr(model, "GetMassProperties", None)
            mass_raw = adapter._attempt(gmp, default=None) if callable(gmp) else gmp
            if isinstance(mass_raw, (list, tuple)) and len(mass_raw) > 5:
                volume_m3 = float(mass_raw[3])
                mass_kg = float(mass_raw[5])
                if volume_m3 > 0:
                    density = mass_kg / volume_m3

            return {
                "assigned": assigned,
                "name": name if assigned else None,
                "database": str(database) if database else None,
                "configuration": config_name or None,
                "density": (
                    {"value": density, "units": "kg/m^3"}
                    if density is not None
                    else None
                ),
                "notes": (
                    "Density is derived from the model's mass and volume. "
                    "Mechanical and thermal properties are not available "
                    "through the SolidWorks COM material API and are omitted "
                    "rather than estimated."
                ),
            }

        return cast(
            AdapterResult[dict[str, Any]],
            adapter._handle_com_operation("get_material_properties", _get),
        )

    async def pack_and_go_assembly(  # pragma: no cover
        self,
        source_path: str,
        target_dir: str,
    ) -> AdapterResult[dict[str, Any]]:
        """Copy an assembly and all its referenced components to a self-contained folder.

        Uses ``IModelDocExtension.GetPackAndGo()`` → ``IPackAndGo`` via the
        comtypes vtable interface (bypassing the broken IDispatch path present
        in SolidWorks 2026's late-binding layer), then calls
        ``IModelDocExtension.SavePackAndGo()`` to execute the copy.  All file
        paths inside the copied assembly are automatically updated by
        SolidWorks — this is the native Pack-and-Go mechanism.

        Args:
            source_path: Absolute path to the source ``.sldasm`` file.
            target_dir: Directory where the assembly and parts will be copied.
                        Created if it does not exist.

        Returns:
            AdapterResult[dict]: On success, ``data`` is a dict with keys:
            ``source_assembly``, ``target_dir``, ``copied_files``,
            ``source_files``, ``save_statuses``, and ``all_files_saved``.
        """
        adapter = self._adapter(self)
        source = Path(source_path)
        out_dir = Path(target_dir)

        def _do_pack_and_go() -> dict[str, Any]:  # pragma: no cover
            # Load comtypes TLB (cached after first call)
            sw_lib = _get_sw_comtypes_lib()
            if sw_lib is None:
                raise RuntimeError(
                    "comtypes SolidWorks type library not available. "
                    "Ensure comtypes is installed and SolidWorks is registered."
                )

            # Prepare a clean target directory. SW holds file locks on previously
            # opened assemblies so rmtree raises WinError 32. We rename the old
            # dir aside (Windows allows rename with open handles) and delete the
            # backup afterwards; if rename also fails we just proceed and let SW
            # overwrite existing files.
            if out_dir.exists():
                backup = out_dir.parent / f"{out_dir.name}_bak_{uuid.uuid4().hex[:8]}"
                try:
                    os.rename(out_dir, backup)
                    try:
                        shutil.rmtree(backup)
                    except Exception:
                        pass  # best-effort cleanup; stale backup is harmless
                except OSError:
                    pass  # rename also failed — proceed; SW will overwrite files
            out_dir.mkdir(parents=True, exist_ok=True)

            # Open the source assembly
            vt = pythoncom.VT_BYREF | pythoncom.VT_I4
            from win32com.client import VARIANT  # noqa: PLC0415

            err = VARIANT(vt, 0)
            warn = VARIANT(vt, 0)
            model = adapter.swApp.OpenDoc6(str(source), 2, 1, "", err, warn)
            if model is None and err.value == 65536:
                adapter.swApp.CloseAllDocuments(False)
                err = VARIANT(vt, 0)
                warn = VARIANT(vt, 0)
                model = adapter.swApp.OpenDoc6(str(source), 2, 1, "", err, warn)
            if model is None:
                raise RuntimeError(f"OpenDoc6 failed err={err.value} warn={warn.value}")
            _sw_type_info.flag_doc(model, 2)
            adapter.currentModel = model

            # Bridge model.Extension → IModelDocExtension via comtypes vtable
            ext_ct = _bridge_com_to_comtypes(model.Extension, sw_lib.IModelDocExtension)

            # GetPackAndGo() via vtable (IDispatch path broken in SW 2026)
            pg = ext_ct.GetPackAndGo()

            # Configure: flatten all files to root of target directory
            pg.FlattenToSingleFolder = True
            pg.SetSaveToName(True, str(out_dir) + "\\")

            # Record what files will be packed
            names_result = pg.GetDocumentNames()
            source_files: list[str] = list(names_result[0]) if names_result[0] else []

            # Execute Pack and Go — SavePackAndGo returns a tuple of per-file status codes
            ext_ct2 = _bridge_com_to_comtypes(
                model.Extension, sw_lib.IModelDocExtension
            )
            status_arr = ext_ct2.SavePackAndGo(pg)
            save_statuses: list[int] = list(status_arr) if status_arr else []

            copied_files = sorted(
                str(p)
                for p in out_dir.rglob("*")
                if p.is_file() and p.suffix.lower() in {".sldasm", ".sldprt", ".slddrw"}
            )
            return {
                "source_assembly": str(source),
                "target_dir": str(out_dir),
                "copied_files": copied_files,
                "source_files": source_files,
                "save_statuses": save_statuses,
                "all_files_saved": all(s == 0 for s in save_statuses),
            }

        result = adapter._handle_com_operation("pack_and_go_assembly", _do_pack_and_go)
        if not result.is_success:
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error=f"Pack and Go failed: {result.error}",
            )
        return AdapterResult(
            status=AdapterResultStatus.SUCCESS,
            data=result.data,
            execution_time=result.execution_time,
        )
