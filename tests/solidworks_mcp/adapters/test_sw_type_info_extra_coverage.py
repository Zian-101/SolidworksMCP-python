"""Extra coverage for solidworks_mcp.adapters.sw_type_info branches not hit
by the existing test_sw_type_info.py: the PYWIN32_AVAILABLE=False early
return in _load_wrapper, the EnsureModule fallback success path, the
empty-cache early return in flag_methods, and flagged()'s pass-through when
obj is not None.
"""

from __future__ import annotations

from types import SimpleNamespace


def test_load_wrapper_noop_when_pywin32_unavailable(monkeypatch) -> None:
    """_load_wrapper should return immediately when PYWIN32_AVAILABLE is False."""
    from solidworks_mcp.adapters import sw_type_info

    monkeypatch.setattr(sw_type_info, "PYWIN32_AVAILABLE", False)
    sw_type_info._wrapper_module = None
    sw_type_info._interface_methods.clear()

    sw_type_info._load_wrapper()

    # No wrapper should have been loaded; nothing should have been attempted.
    assert sw_type_info._wrapper_module is None
    assert sw_type_info._interface_methods == {}


def test_load_wrapper_recovers_via_ensure_module_fallback(monkeypatch) -> None:
    """When GetModuleForTypelib fails outright, EnsureModule should be tried
    and, on success, the second GetModuleForTypelib call should succeed."""
    from solidworks_mcp.adapters import sw_type_info

    class _FakeMethod:
        def dummy_method(self):
            ...

    fake_module = SimpleNamespace(__name__="fake_gen_py_module")

    call_count = {"get": 0}

    class _FakeCache:
        @staticmethod
        def GetModuleForTypelib(*_a, **_kw):
            call_count["get"] += 1
            # First pass (before EnsureModule): always fail.
            # Second pass (after EnsureModule succeeds): return the module.
            if call_count["get"] <= 6:
                return None
            return fake_module

        @staticmethod
        def EnsureModule(*_a, **_kw):
            # Succeeds silently — real gencache would generate the wrapper.
            return None

    monkeypatch.setattr(sw_type_info, "PYWIN32_AVAILABLE", True)
    monkeypatch.setattr(sw_type_info, "gencache", _FakeCache, raising=False)
    sw_type_info._wrapper_module = None
    sw_type_info._interface_methods.clear()

    sw_type_info._load_wrapper()

    assert sw_type_info._wrapper_module is fake_module


def test_flag_methods_returns_zero_when_obj_is_none() -> None:
    """flag_methods should short-circuit to 0 when obj is None, even with
    interface methods loaded."""
    from solidworks_mcp.adapters import sw_type_info

    sw_type_info._interface_methods["ISldWorks"] = frozenset({"GetTitle"})
    try:
        assert sw_type_info.flag_methods(None, "ISldWorks") == 0
    finally:
        sw_type_info._interface_methods.pop("ISldWorks", None)


def test_flagged_flags_and_returns_a_real_object() -> None:
    """flagged() should call flag_methods on a non-None obj, then return it."""
    from solidworks_mcp.adapters import sw_type_info

    flagged_names: list[str] = []

    class _FakeDispatch:
        def _FlagAsMethod(self, name: str) -> None:
            flagged_names.append(name)

    sw_type_info._interface_methods["IModelDoc2"] = frozenset({"GetTitle", "GetType"})
    sw_type_info._flag_cache.clear()
    try:
        obj = _FakeDispatch()
        result = sw_type_info.flagged(obj, "IModelDoc2")
        assert result is obj
        assert set(flagged_names) == {"GetTitle", "GetType"}
    finally:
        sw_type_info._interface_methods.pop("IModelDoc2", None)
        sw_type_info._flag_cache.clear()
