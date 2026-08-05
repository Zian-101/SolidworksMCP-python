"""Guard against tools inventing their answers.

Several tools used to return confident, plausible, entirely fabricated payloads:
a 92% drafting-standards compliance score for a drawing they never opened, a
similarity percentage for templates they never read, a catalogue of templates
nobody had registered. Nothing errored, so nothing looked wrong.

These tests pin the two properties that matter:

1. Tools that cannot do the job report an error rather than a success-shaped
   invention.
2. Every registered tool either reaches the adapter or is one of the handful
   that legitimately never needs it.
"""

import ast
import pathlib

import pytest
from fastmcp import FastMCP

from solidworks_mcp.adapters.mock_adapter import MockSolidWorksAdapter
from solidworks_mcp.tools.drawing import (
    CreateDetailViewInput,
    CreateSectionViewInput,
    register_drawing_tools,
)

TOOLS_DIR = pathlib.Path(__file__).resolve().parents[3] / "src" / "solidworks_mcp" / "tools"

#: Tools that legitimately never touch SolidWorks: they generate VBA text,
#: search local documentation, delegate to a sibling tool, or compare files on
#: disk. Anything NOT on this list that skips the adapter is fabricating.
ADAPTER_FREE_TOOLS = {
    "get_mass_properties",  # delegates to calculate_mass_properties
    "stop_macro_recording",
    "discover_solidworks_docs",
    "search_solidworks_api_help",
    "generate_vba_part_modeling",
    "generate_vba_assembly_mates",
    "generate_vba_drawing_dimensions",
    "generate_vba_file_operations",
    "generate_vba_macro_recorder",
    # These refuse honestly instead of inventing a result.
    "create_section_view",
    "create_detail_view",
    "check_drawing_standards",
    "execute_workflow",
    "manage_design_table",
    "optimize_performance",
    "analyze_macro",
    "batch_execute_macros",
    "optimize_macro",
    "create_macro_library",
    "apply_template",
    "batch_apply_template",
    # File-level work that needs no SolidWorks session: comparisons read the
    # files, and the template tools copy a model to a template file.
    "compare_drawing_versions",
    "compare_templates",
    "create_template",
    "extract_template",
}


def _tools_without_adapter() -> set[str]:
    """Return the names of @mcp.tool functions that never reference `adapter`."""
    offenders: set[str] = set()
    for path in sorted(TOOLS_DIR.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            decorated = any(
                isinstance(d, ast.Call)
                and isinstance(d.func, ast.Attribute)
                and d.func.attr == "tool"
                for d in node.decorator_list
            )
            if not decorated:
                continue
            segment = ast.get_source_segment(source, node) or ""
            if "adapter." not in segment:
                offenders.add(node.name)
    return offenders


def test_no_new_tools_fabricate_their_answer() -> None:
    """Every tool either uses the adapter or is a known adapter-free tool."""
    offenders = _tools_without_adapter() - ADAPTER_FREE_TOOLS
    assert not offenders, (
        "These tools never reach the adapter, so they cannot be returning real "
        f"data: {sorted(offenders)}. Either wire them to the adapter or make "
        "them report an error."
    )


def test_no_simulation_markers_left_in_tools() -> None:
    """No tool still advertises that it is faking its result."""
    # "# Simulate " (imperative) slipped past an earlier version of this check
    # that only looked for "# For now, simulate" — five automation tools were
    # still inventing their entire answer behind it.
    markers = (
        "# For now, simulate",
        "# Simulate ",
        "# Simulated",
        "# Would be actual",
    )
    found: list[str] = []
    for path in sorted(TOOLS_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker in text:
                found.append(f"{path.name}: {marker}")
    assert not found, f"Simulation markers left behind: {found}"


@pytest.mark.asyncio
async def test_standards_check_refuses_instead_of_scoring() -> None:
    """check_drawing_standards must not invent a compliance score."""
    mcp = FastMCP("test")
    adapter = MockSolidWorksAdapter({})
    await adapter.connect()
    await register_drawing_tools(mcp, adapter, {})

    tools = {tool.name: tool.fn for tool in await mcp.list_tools()}
    result = await tools["check_drawing_standards"](input_data={})

    assert result["status"] == "error"
    assert "compliance_score" not in str(result)


@pytest.mark.asyncio
async def test_section_and_detail_views_refuse_clearly() -> None:
    """The view tools that cannot work explain why rather than pretending."""
    mcp = FastMCP("test")
    adapter = MockSolidWorksAdapter({})
    await adapter.connect()
    await register_drawing_tools(mcp, adapter, {})

    tools = {tool.name: tool.fn for tool in await mcp.list_tools()}

    section = await tools["create_section_view"](
        input_data=CreateSectionViewInput(
            section_line_start=[0.0, 0.0],
            section_line_end=[10.0, 0.0],
            view_position_x=100.0,
            view_position_y=100.0,
        )
    )
    assert section["status"] == "error"
    assert "section line" in section["message"].lower()

    detail = await tools["create_detail_view"](
        input_data=CreateDetailViewInput(
            center_x=0.0,
            center_y=0.0,
            radius=10.0,
            view_position_x=100.0,
            view_position_y=100.0,
        )
    )
    assert detail["status"] == "error"
    assert "detail circle" in detail["message"].lower()
