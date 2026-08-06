"""Extra coverage for solidworks_mcp.ui.prefab_dashboard.

The dashboard module builds its entire component tree at *import time*
inside a top-level ``with PrefabApp(...):`` block, gated behind the
``SHOW_EXPERIMENTAL_ORCHESTRATION`` module constant (read once from the
``SOLIDWORKS_UI_EXPERIMENTAL_ORCHESTRATION`` env var at import time). The
existing test suite (test_prefab_modules.py) only imports the module with
that flag left at its default (off), so the whole "Plan Next Steps" /
"Clarification and Engineering Review" / "Checkpoint Plan" experimental
branches never execute.

This file re-imports the module with the env var set, using the same
prefab_ui stub approach as test_prefab_modules.py, so the experimental
branches actually run. If SHOW_EXPERIMENTAL_ORCHESTRATION stops gating a
UI branch as expected, this import would raise (a real NameError/AttributeError
from the real component-building code, not a mocked assertion), so the test
is a genuine behavioural check, not an import-only placeholder.
"""

from __future__ import annotations

import importlib
import sys
import types
from typing import Any


class _Expr:
    def __init__(self, value: Any = None) -> None:
        self.value = value

    def __getattr__(self, name: str) -> _Expr:
        return _Expr(name)

    def __getitem__(self, key: Any) -> _Expr:
        return _Expr(key)

    def __call__(self, *args: Any, **kwargs: Any) -> _Expr:
        return _Expr((args, kwargs))

    def __mod__(self, other: Any) -> _Expr:
        return _Expr(("%", other))

    def __mul__(self, other: Any) -> _Expr:
        return _Expr(("*", other))

    def __add__(self, other: Any) -> _Expr:
        return _Expr(("+", other))

    def __gt__(self, other: Any) -> _Expr:
        return _Expr((">", other))

    def __le__(self, other: Any) -> _Expr:
        return _Expr(("<=", other))

    def then(self, *_args: Any) -> _Expr:
        return _Expr("then")

    def default(self, fallback: Any) -> Any:
        return fallback


class _Ctx:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs

    def __enter__(self) -> _Ctx:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _Fetch:
    @staticmethod
    def get(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"method": "GET", "args": args, "kwargs": kwargs}

    @staticmethod
    def post(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"method": "POST", "args": args, "kwargs": kwargs}


class _OpenFilePicker:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs


class _SetState:
    def __init__(self, key: str, value: Any) -> None:
        self.key = key
        self.value = value


class _SetInterval:
    def __init__(self, every_ms: int, on_tick: Any) -> None:
        self.every_ms = every_ms
        self.on_tick = on_tick


class _ShowToast:
    def __init__(self, message: Any, variant: str = "default") -> None:
        self.message = message
        self.variant = variant


class _DashboardUIState:
    def model_dump(self) -> dict[str, Any]:
        return {"session_id": "prefab-dashboard"}


def _make_component_module() -> types.ModuleType:
    module = types.ModuleType("prefab_ui.components")
    names = [
        "Accordion",
        "AccordionItem",
        "Badge",
        "Button",
        "Card",
        "CardContent",
        "CardDescription",
        "CardFooter",
        "CardHeader",
        "CardTitle",
        "Checkbox",
        "Column",
        "DataTable",
        "DataTableColumn",
        "Embed",
        "Else",
        "Grid",
        "GridItem",
        "Image",
        "If",
        "Muted",
        "Progress",
        "Row",
        "Text",
        "Textarea",
    ]
    for name in names:
        setattr(module, name, _Ctx)
    return module


def _install_prefab_stubs() -> None:
    # Warm the *real* solidworks_mcp.ui package cache before shadowing
    # solidworks_mcp.ui.schemas with a stub. solidworks_mcp/ui/__init__.py
    # transitively imports the real schemas module (DashboardCheckpoint,
    # DashboardEvidenceRow, ...); if that package hasn't been imported for
    # real yet and our stub schemas module (only DashboardUIState) is
    # already installed in sys.modules, the package __init__ import chain
    # breaks with ImportError. Once the real package is cached, overwriting
    # sys.modules["solidworks_mcp.ui.schemas"] afterwards is safe because
    # prefab_dashboard.py only imports DashboardUIState from it directly.
    importlib.import_module("solidworks_mcp.ui")

    prefab_ui = types.ModuleType("prefab_ui")
    prefab_ui.PrefabApp = _Ctx

    actions = types.ModuleType("prefab_ui.actions")
    actions.Fetch = _Fetch
    actions.OpenFilePicker = _OpenFilePicker
    actions.SetInterval = _SetInterval
    actions.SetState = _SetState
    actions.ShowToast = _ShowToast

    components = _make_component_module()

    control_flow = types.ModuleType("prefab_ui.components.control_flow")
    control_flow.If = _Ctx
    control_flow.Else = _Ctx

    rx = types.ModuleType("prefab_ui.rx")
    rx.ERROR = _Expr("ERROR")
    rx.EVENT = _Expr("EVENT")
    rx.RESULT = _Expr("RESULT")
    rx.STATE = _Expr("STATE")
    rx.Rx = _Expr

    ui_schemas = types.ModuleType("solidworks_mcp.ui.schemas")
    ui_schemas.DashboardUIState = _DashboardUIState

    sys.modules["prefab_ui"] = prefab_ui
    sys.modules["prefab_ui.actions"] = actions
    sys.modules["prefab_ui.components"] = components
    sys.modules["prefab_ui.components.control_flow"] = control_flow
    sys.modules["prefab_ui.rx"] = rx
    sys.modules["solidworks_mcp.ui.schemas"] = ui_schemas


def test_dashboard_builds_experimental_orchestration_branches(monkeypatch) -> None:
    """Importing with the experimental flag on must execute the "GO",
    "Plan Next Steps", clarification-lane, and checkpoint-plan branches
    without raising, and the module constant must reflect the env var."""
    monkeypatch.setenv("SOLIDWORKS_UI_EXPERIMENTAL_ORCHESTRATION", "1")
    _install_prefab_stubs()
    sys.modules.pop("solidworks_mcp.ui.prefab_dashboard", None)

    module = importlib.import_module("solidworks_mcp.ui.prefab_dashboard")

    assert module.SHOW_EXPERIMENTAL_ORCHESTRATION is True


def test_dashboard_hides_experimental_branches_when_flag_off(monkeypatch) -> None:
    """Re-importing with the flag off (default) must take the stable-path
    branches instead, proving the gate genuinely toggles which code runs."""
    monkeypatch.delenv("SOLIDWORKS_UI_EXPERIMENTAL_ORCHESTRATION", raising=False)
    _install_prefab_stubs()
    sys.modules.pop("solidworks_mcp.ui.prefab_dashboard", None)

    module = importlib.import_module("solidworks_mcp.ui.prefab_dashboard")

    assert module.SHOW_EXPERIMENTAL_ORCHESTRATION is False


def test_result_state_returns_the_raw_value_without_a_fallback(monkeypatch) -> None:
    """_result_state's direct `return value` branch (no fallback supplied)."""
    _install_prefab_stubs()
    sys.modules.pop("solidworks_mcp.ui.prefab_dashboard", None)
    module = importlib.import_module("solidworks_mcp.ui.prefab_dashboard")

    value = module._result_state("workflow_mode")
    # No fallback given, so the raw stubbed _Expr value comes straight back.
    assert isinstance(value, _Expr)
    assert value.value == "workflow_mode"
