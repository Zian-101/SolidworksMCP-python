"""Coverage for the handful of docs_discovery.py branches left after
test_docs_discovery_coverage_push.py: hidden-name skipping and the outer exception
guard in ``_enumerate_typeinfo_members``, the impl-type exception guard in
``_discover_com_via_typeinfo``, three genuine registry error paths in
``_discover_vba_references_via_registry`` (previously only exercised by forcing
platform.system() to "Linux", which short-circuits before reaching any of them), the
"no VBA references found" debug-log branch, the OSError guard in
``_detect_installed_solidworks_year``, the outer ITypeInfo-path exception handler in
``discover_com_objects``, and the generic-Exception branch of the RAG index rebuild
(the existing test with that name never actually made the rebuild raise).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from solidworks_mcp.config import SolidWorksMCPConfig
from solidworks_mcp.tools.docs_discovery import (
    HAS_WIN32COM,
    SolidWorksDocsDiscovery,
    _detect_installed_solidworks_year,
    _discover_com_via_typeinfo,
    _discover_vba_references_via_registry,
    _enumerate_typeinfo_members,
)

# --------------------------------------------------------------------------- #
# _enumerate_typeinfo_members
# --------------------------------------------------------------------------- #


class _TypeInfoWithHiddenName:
    """One visible method, one whose name starts with '_' (skipped)."""

    def GetTypeAttr(self):
        return SimpleNamespace(cFuncs=2, cImplTypes=0)

    def GetFuncDesc(self, i):
        return SimpleNamespace(memid=i + 1, invkind=1)

    def GetNames(self, memid):
        if memid == 1:
            return ["_HiddenMethod"]
        return ["VisibleMethod"]


def test_enumerate_typeinfo_members_skips_underscore_prefixed_names():
    if not HAS_WIN32COM:
        pytest.skip("win32com not available")
    methods, properties = _enumerate_typeinfo_members(_TypeInfoWithHiddenName())
    assert methods == ["VisibleMethod"]
    assert "_HiddenMethod" not in methods


class _TypeInfoAttrFails:
    """GetTypeAttr itself raises - the outer try/except must swallow it."""

    def GetTypeAttr(self):
        raise RuntimeError("no type attr available")


def test_enumerate_typeinfo_members_outer_exception_returns_empty():
    if not HAS_WIN32COM:
        pytest.skip("win32com not available")
    methods, properties = _enumerate_typeinfo_members(_TypeInfoAttrFails())
    assert methods == []
    assert properties == []


# --------------------------------------------------------------------------- #
# _discover_com_via_typeinfo
# --------------------------------------------------------------------------- #


class _ImplTypeInfoFails:
    """Main interface enumerates fine; walking its implemented type raises."""

    def GetTypeAttr(self):
        return SimpleNamespace(cFuncs=1, cImplTypes=1)

    def GetFuncDesc(self, i):
        return SimpleNamespace(memid=1, invkind=1)

    def GetNames(self, memid):
        return ["MainMethod"]

    def GetRefTypeOfImplType(self, idx):
        raise RuntimeError("impl type lookup failed")


class _OleObjWithFailingImpl:
    def GetTypeInfo(self):
        return _ImplTypeInfoFails()


class _AppWithFailingImplTypeInfo:
    _oleobj_ = _OleObjWithFailingImpl()


def test_discover_com_via_typeinfo_impl_type_exception_is_swallowed(monkeypatch):
    if not HAS_WIN32COM:
        pytest.skip("win32com not available")
    com_index, total_m, total_p = _discover_com_via_typeinfo(
        _AppWithFailingImplTypeInfo()
    )
    # The main interface's own members are still captured despite the impl
    # walk failing.
    assert "ISldWorks" in com_index
    assert "MainMethod" in com_index["ISldWorks"]["methods"]


class _TypeInfoAttrAlwaysFails:
    """GetTypeAttr raises on every call - both the initial member enumeration
    inside _enumerate_typeinfo_members AND the impl-walk's own separate call
    in _discover_com_via_typeinfo must tolerate it independently."""

    def GetTypeAttr(self):
        raise RuntimeError("type attr unavailable")


class _OleObjWithAlwaysFailingAttr:
    def GetTypeInfo(self):
        return _TypeInfoAttrAlwaysFails()


class _AppWithAlwaysFailingTypeAttr:
    _oleobj_ = _OleObjWithAlwaysFailingAttr()


def test_discover_com_via_typeinfo_impl_walk_outer_except_when_no_members():
    if not HAS_WIN32COM:
        pytest.skip("win32com not available")
    # _enumerate_typeinfo_members swallows the GetTypeAttr failure and returns
    # ([], []); with no methods/properties, com_index stays empty for
    # ISldWorks, but the impl-walk's own try/except around its *second*
    # GetTypeAttr() call must independently tolerate the same failure.
    com_index, total_m, total_p = _discover_com_via_typeinfo(
        _AppWithAlwaysFailingTypeAttr()
    )
    assert "ISldWorks" not in com_index
    assert total_m == 0
    assert total_p == 0


class _AppWhoseTypeInfoRaises:
    class _Ole:
        def GetTypeInfo(self):
            raise RuntimeError("no typeinfo for this app")

    _oleobj_ = _Ole()


def test_discover_com_via_typeinfo_top_level_exception_returns_empty():
    if not HAS_WIN32COM:
        pytest.skip("win32com not available")
    com_index, total_m, total_p = _discover_com_via_typeinfo(
        _AppWhoseTypeInfoRaises()
    )
    assert com_index == {}
    assert total_m == 0
    assert total_p == 0


# --------------------------------------------------------------------------- #
# _discover_vba_references_via_registry - real winreg monkeypatching
# --------------------------------------------------------------------------- #


def test_registry_scan_outer_open_failure(monkeypatch):
    """winreg.OpenKey for HKEY_CLASSES_ROOT\\TypeLib itself raising hits the
    outer 'Registry TypeLib scan failed' debug-log branch."""
    # winreg is Windows-only; importing it at module scope would turn this
    # file into a collection error on the Linux CI runner.
    winreg = pytest.importorskip("winreg")

    import solidworks_mcp.tools.docs_discovery as docs_mod

    monkeypatch.setattr(docs_mod.platform, "system", lambda: "Windows")

    def fail_open_key(*args, **kwargs):
        raise RuntimeError("registry unavailable")

    monkeypatch.setattr(winreg, "OpenKey", fail_open_key)

    refs = _discover_vba_references_via_registry()
    assert refs == {}


def test_registry_scan_guid_and_version_level_errors(monkeypatch):
    """Exercises both inner exception branches in one scan:

    - GUID_A: opening the guid-level key raises -> outer 'except: continue'
    - GUID_B: opens fine, has one version, but reading its value raises a
      non-OSError -> inner 'except: continue'
    """
    # See the note in test_registry_scan_outer_open_failure: winreg is
    # Windows-only and must not be imported at module scope.
    winreg = pytest.importorskip("winreg")

    import solidworks_mcp.tools.docs_discovery as docs_mod

    monkeypatch.setattr(docs_mod.platform, "system", lambda: "Windows")

    TYPELIB_KEY = object()
    GUID_B_KEY = object()
    VER_B_KEY = object()

    def fake_open_key(key, subkey=None, *args, **kwargs):
        if key is winreg.HKEY_CLASSES_ROOT and subkey == "TypeLib":
            return TYPELIB_KEY
        if key is TYPELIB_KEY and subkey == "GUID_A":
            raise RuntimeError("boom opening guid key")
        if key is TYPELIB_KEY and subkey == "GUID_B":
            return GUID_B_KEY
        if key is GUID_B_KEY and subkey == "1.0":
            return VER_B_KEY
        raise OSError(f"unexpected OpenKey({key!r}, {subkey!r})")

    def fake_enum_key(key, index):
        if key is TYPELIB_KEY:
            seq = ["GUID_A", "GUID_B"]
            if index < len(seq):
                return seq[index]
            raise OSError("no more guids")
        if key is GUID_B_KEY:
            if index == 0:
                return "1.0"
            raise OSError("no more versions")
        raise OSError("unknown key for EnumKey")

    def fake_query_value_ex(key, name):
        if key is VER_B_KEY:
            raise ValueError("boom reading value (not an OSError)")
        raise OSError("no value")

    def fake_close_key(key):
        return None

    monkeypatch.setattr(winreg, "OpenKey", fake_open_key)
    monkeypatch.setattr(winreg, "EnumKey", fake_enum_key)
    monkeypatch.setattr(winreg, "QueryValueEx", fake_query_value_ex)
    monkeypatch.setattr(winreg, "CloseKey", fake_close_key)

    refs = _discover_vba_references_via_registry()
    # Both GUID_A (outer except) and GUID_B's version (inner except) were
    # skipped without raising - the scan completes and returns cleanly.
    assert refs == {}


# --------------------------------------------------------------------------- #
# discover_vba_references: "no matching entries" debug-log branch
# --------------------------------------------------------------------------- #


def test_discover_vba_references_logs_when_none_found(monkeypatch, tmp_path: Path):
    import solidworks_mcp.tools.docs_discovery as docs_mod

    monkeypatch.setattr(
        docs_mod, "_discover_vba_references_via_registry", lambda: {}
    )
    discovery = SolidWorksDocsDiscovery(output_dir=tmp_path)
    refs = discovery.discover_vba_references()
    assert refs == {}


# --------------------------------------------------------------------------- #
# _detect_installed_solidworks_year: OSError on iterdir
# --------------------------------------------------------------------------- #


def test_detect_installed_solidworks_year_iterdir_oserror(monkeypatch):
    def fake_exists(self):
        return True

    def fake_iterdir(self):
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr(Path, "iterdir", fake_iterdir)

    result = _detect_installed_solidworks_year()
    assert result is None


# --------------------------------------------------------------------------- #
# discover_com_objects: outer exception around the ITypeInfo path itself
# --------------------------------------------------------------------------- #


def test_discover_com_objects_typeinfo_path_raises(monkeypatch, tmp_path: Path):
    import solidworks_mcp.tools.docs_discovery as docs_mod

    monkeypatch.setattr(docs_mod, "HAS_WIN32COM", True)

    def boom(_sw_app):
        raise RuntimeError("typeinfo path exploded")

    monkeypatch.setattr(docs_mod, "_discover_com_via_typeinfo", boom)

    discovery = SolidWorksDocsDiscovery(output_dir=tmp_path)
    discovery.sw_app = SimpleNamespace(
        ActiveDoc=None, RevisionNumber=lambda: "33.2"
    )
    # Falls through to the known-interface catalogue fallback instead of
    # propagating the exception.
    index = discovery.discover_com_objects()
    assert isinstance(index, dict)
    assert index  # the fallback catalogue always populates something


# --------------------------------------------------------------------------- #
# RAG index rebuild: genuine generic Exception (not ImportError)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_discover_docs_rag_rebuild_generic_exception_is_caught(
    mcp_server,
    mock_config: SolidWorksMCPConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import solidworks_mcp.tools.docs_discovery as docs_mod
    from solidworks_mcp.tools.docs_discovery import register_docs_discovery_tools

    await register_docs_discovery_tools(mcp_server, object(), mock_config)

    discover_tool = None
    for tool in await mcp_server.list_tools():
        if tool.name == "discover_solidworks_docs":
            discover_tool = tool.fn
            break
    assert discover_tool is not None

    class _FakeDiscovery:
        def __init__(self, output_dir=None):
            self.output_dir = output_dir or tmp_path

        def discover_all(self):
            return {
                "com_objects": {"ISldWorks": {"methods": ["OpenDoc6"]}},
                "vba_references": {},
                "total_methods": 1,
                "total_properties": 0,
                "solidworks_version": "33.2",
            }

        def save_index(self, filename="solidworks_docs_index.json"):
            path = self.output_dir / filename
            path.write_text("{}", encoding="utf-8")
            return path

        def create_search_summary(self):
            return {
                "total_com_objects": 1,
                "total_methods": 1,
                "total_properties": 0,
                "solidworks_version": "33.2",
                "available_vba_libs": [],
            }

    monkeypatch.setattr(docs_mod, "HAS_WIN32COM", True)
    monkeypatch.setattr(docs_mod.platform, "system", lambda: "Windows")
    monkeypatch.setattr(docs_mod, "SolidWorksDocsDiscovery", _FakeDiscovery)

    import solidworks_mcp.agents.vector_rag as vector_rag_mod

    def boom(output_file):
        raise RuntimeError("rag index build boom")

    monkeypatch.setattr(vector_rag_mod, "build_solidworks_api_docs_index", boom)

    result = await discover_tool({"output_dir": str(tmp_path)})
    # The RAG rebuild failure is logged and swallowed; discovery still succeeds.
    assert result["status"] == "success"
