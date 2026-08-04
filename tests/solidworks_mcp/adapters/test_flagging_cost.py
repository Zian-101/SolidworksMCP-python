"""Keep per-object interface flagging out of hot loops.

``flag_methods(obj, "IFeature")`` flags every method of the interface and caches
by ``id(obj)``. Inside a loop over fresh COM dispatches — walking a feature
tree, iterating edges or components — the cache never hits and the full cost is
paid per object. Measured live, that made ``list_features`` take 5.9 s on a
20-feature model and ``pattern_circular`` 11.4 s.

The fix is ``flag_members(obj, *names)``: flag only what the loop is about to
read. These tests pin that, so the expensive call cannot quietly come back.
"""

import ast
import pathlib

import pytest

from solidworks_mcp.adapters import sw_type_info

ADAPTERS = pathlib.Path(__file__).resolve().parents[3] / "src" / "solidworks_mcp" / "adapters"

#: Functions that walk many COM objects. None of them may flag a whole
#: interface per object.
HOT_LOOP_FUNCTIONS = {
    "_profile_feature_names",
    "_axis_features",
    "_edge_directions",
    "_component_boxes",
    "list_features",
}


def _calls_in(node: ast.AST) -> list[ast.Call]:
    return [n for n in ast.walk(node) if isinstance(n, ast.Call)]


def _flag_methods_calls(node: ast.AST) -> list[ast.Call]:
    """Return calls to flag_methods / _flag_feature_methods within `node`."""
    found = []
    for call in _calls_in(node):
        name = None
        if isinstance(call.func, ast.Attribute):
            name = call.func.attr
        elif isinstance(call.func, ast.Name):
            name = call.func.id
        if name in ("flag_methods", "_flag_feature_methods"):
            found.append(call)
    return found


@pytest.mark.parametrize("function_name", sorted(HOT_LOOP_FUNCTIONS))
def test_hot_loops_do_not_flag_whole_interfaces(function_name: str) -> None:
    """A per-object flag inside a loop must use flag_members, not flag_methods.

    Flagging the document once per call is fine — it is a single long-lived
    object, so the id(obj) cache does its job. Only calls *inside* a loop are
    the problem.
    """
    offenders = []
    for path in sorted(ADAPTERS.rglob("*.py")):
        # utf-8-sig: a stray BOM makes ast.parse fail with
        # "invalid non-printable character U+FEFF".
        source = path.read_text(encoding="utf-8-sig")
        for node in ast.walk(ast.parse(source)):
            if not (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == function_name
            ):
                continue
            for inner in ast.walk(node):
                if not isinstance(inner, (ast.For, ast.AsyncFor, ast.While)):
                    continue
                for call in _flag_methods_calls(inner):
                    offenders.append(f"{path.name}:{call.lineno}")

    assert not offenders, (
        f"{function_name} flags a whole interface per object inside a loop at "
        f"{offenders}. Use sw_type_info.flag_members(obj, *names) with just the "
        "members the loop reads - flag_methods costs ~27 ms per object here and "
        "its cache is keyed by id(obj), so it never hits for fresh dispatches."
    )


def test_no_source_file_carries_a_utf8_bom() -> None:
    """A BOM on a .py file breaks tooling that parses the decoded text.

    features.py picked one up from a PowerShell rewrite; ast.parse then failed
    with "invalid non-printable character U+FEFF" even though Python itself
    imported the module fine, so the breakage only showed up in tests.
    """
    root = ADAPTERS.parents[1]
    offenders = [
        str(path.relative_to(root))
        for path in sorted(root.rglob("*.py"))
        if path.read_bytes().startswith(b"\xef\xbb\xbf")
    ]
    assert not offenders, f"UTF-8 BOM found in: {offenders}"


def test_flag_members_exists_and_tolerates_junk() -> None:
    """flag_members must never raise, whatever it is handed."""
    assert callable(sw_type_info.flag_members)
    assert sw_type_info.flag_members(None, "Name") == 0
    assert sw_type_info.flag_members(object(), "Name", "GetTypeName2") == 0


def test_flag_members_flags_each_requested_name() -> None:
    """Names are flagged individually, and unknown ones are skipped quietly."""

    class FakeDispatch:
        def __init__(self) -> None:
            self.flagged: list[str] = []

        def _FlagAsMethod(self, name: str) -> None:  # noqa: N802 - pywin32 API
            if name == "NotOnThisInterface":
                raise AttributeError(name)
            self.flagged.append(name)

    dispatch = FakeDispatch()
    count = sw_type_info.flag_members(
        dispatch, "Name", "GetTypeName2", "NotOnThisInterface"
    )

    assert count == 2
    assert dispatch.flagged == ["Name", "GetTypeName2"]
