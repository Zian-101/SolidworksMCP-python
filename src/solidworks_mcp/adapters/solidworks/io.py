"""Model I/O mixin for PyWin32 SolidWorks operations."""

from __future__ import annotations

import os
from datetime import datetime
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
            drw_template = self._resolve_template_path([10, 6], ".drwdot")
            if not drw_template:
                raise Exception(
                    "No drawing template configured in SolidWorks "
                    "(Tools > Options > File Locations > Document Templates)"
                )

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
        doc_type = adapter._attempt(
            lambda: adapter.currentModel.GetType(), default=None
        )
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

        def _get() -> float:
            """Get the dimension value."""
            dimension = adapter.currentModel.Parameter(name)
            if not dimension:
                raise Exception(f"Dimension '{name}' not found")
            # SystemValue is reliable on SW 2025 (in meters, convert to mm)
            value = adapter._attempt(
                lambda: dimension.SystemValue, default=None
            )
            if value is None:
                # Fall back to GetValue3 for older SW versions
                value = adapter._attempt(
                    lambda: dimension.GetValue3(0, 0), default=None
                )
            if value is None:
                raise Exception(f"Failed to read dimension '{name}'")
            return cast(float, float(value) * 1000)

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
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )

        def _get_info() -> dict[str, Any]:
            """Get model information."""
            active_config = adapter.currentModel.GetActiveConfiguration()
            # 'Name' on Configuration is a property, not a method.
            config_name = getattr(active_config, "Name", "Default") if active_config else "Default"
            # Try GetSaveFlag (method) first, fallback to property
            is_dirty_raw = adapter._attempt(
                lambda: adapter.currentModel.GetSaveFlag(), default=None
            )
            is_dirty = bool(is_dirty_raw) if is_dirty_raw is not None else None
            feature_count = adapter._attempt(
                lambda: int(adapter.currentModel.FeatureManager.GetFeatureCount(True) or 0),
                default=0,
            )
            rebuild_status_raw = adapter._attempt(
                lambda: adapter.currentModel.GetRebuildStatus(), default=None
            )
            # GetRebuildStatus returns 0=ok, 1=needs rebuild, or None=failed
            rebuild_status = rebuild_status_raw if rebuild_status_raw is not None else None
            return {
                "title": adapter.currentModel.GetTitle(),
                "path": adapter.currentModel.GetPathName(),
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

        doc_type = adapter._attempt(
            lambda: adapter.currentModel.GetType(), default=None
        )
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

        doc_type = adapter._attempt(
            lambda: adapter.currentModel.GetType(), default=None
        )
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
        for language in ("english", "Engl.ish"):
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
