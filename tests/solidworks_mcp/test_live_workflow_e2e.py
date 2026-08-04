"""End-to-end workflow through the MCP tool layer against live SolidWorks.

Most tests in this suite exercise the adapter directly. This one drives the real
registered tool functions, so the Pydantic schemas, the circuit breaker and the
COM adapter are all in the path — the same stack a user hits. It is the only
test that would have caught, for example, a tool that works when called with a
model but raises when handed a dict.

Requires SolidWorks. Skipped unless SOLIDWORKS_MCP_RUN_REAL_INTEGRATION=1.

Run with::

    $env:SOLIDWORKS_MCP_RUN_REAL_INTEGRATION=1
    .\\.venv\\Scripts\\python.exe -m pytest tests/solidworks_mcp/test_live_workflow_e2e.py -v
"""

import os
import time

import pytest

pytestmark = [
    pytest.mark.solidworks_only,
    pytest.mark.skipif(
        os.environ.get("SOLIDWORKS_MCP_RUN_REAL_INTEGRATION") != "1",
        reason="needs a live SolidWorks session",
    ),
]


def _ok(payload: dict, label: str) -> dict:
    """Assert a tool call succeeded, quoting its message on failure."""
    assert payload.get("status") == "success", (
        f"{label} failed: {payload.get('message')}"
    )
    return payload


@pytest.fixture
async def tools():
    """Boot the server, register every tool and open the COM connection."""
    from solidworks_mcp.config import load_config
    from solidworks_mcp.server import SolidWorksMCPServer

    server = SolidWorksMCPServer(config=load_config())
    await server.setup()
    adapter = getattr(server, "adapter", None)
    if adapter is not None and not adapter.is_connected():
        await adapter.connect()
    yield {tool.name: tool.fn for tool in await server.mcp.list_tools()}


@pytest.mark.asyncio
async def test_part_to_drawing_to_assembly(tools, tmp_path) -> None:
    """Build a part, draw it, assemble two copies and mate them."""
    stamp = int(time.time())
    part = str(tmp_path / f"e2e_{stamp}.SLDPRT")
    drawing = str(tmp_path / f"e2e_{stamp}.SLDDRW")
    assembly = str(tmp_path / f"e2e_{stamp}.SLDASM")

    # ---- part ----
    _ok(await tools["create_part"](input_data={"name": f"e2e_{stamp}"}), "create_part")
    _ok(await tools["save_as"](input_data={"file_path": part}), "save_as")

    _ok(await tools["create_sketch"](input_data={"plane": "Top"}), "create_sketch")
    _ok(
        await tools["add_rectangle"](
            input_data={
                "corner1_x": -40.0, "corner1_y": -20.0,
                "corner2_x": 40.0, "corner2_y": 20.0,
            }
        ),
        "add_rectangle",
    )
    _ok(await tools["exit_sketch"](), "exit_sketch")
    _ok(
        await tools["create_extrusion"](
            input_data={"depth": 10.0, "sketch_name": "Sketch1"}
        ),
        "create_extrusion",
    )

    # 80 x 40 x 10 = 32000 mm3, and the box must match.
    mass = _ok(await tools["get_mass_properties"](None), "get_mass_properties")
    volume = mass["mass_properties"]["volume"]["value"]
    assert volume == pytest.approx(32000.0, rel=1e-6), volume

    box = _ok(await tools["get_bounding_box"](), "get_bounding_box")
    dimensions = box["bounding_box"]["dimensions"]
    assert dimensions["x"] == pytest.approx(80.0, abs=1e-3)
    assert dimensions["y"] == pytest.approx(10.0, abs=1e-3)
    assert dimensions["z"] == pytest.approx(40.0, abs=1e-3)

    material = _ok(
        await tools["set_material"](input_data={"name": "6061 Alloy"}), "set_material"
    )
    assert material["material"]["name"] == "6061 Alloy"

    _ok(
        await tools["set_appearance"](input_data={"red": 0, "green": 128, "blue": 255}),
        "set_appearance",
    )
    _ok(await tools["save_file"](input_data={}), "save_file")

    # ---- drawing ----
    _ok(await tools["create_drawing"](input_data={"name": "e2e"}), "create_drawing")
    views = _ok(
        await tools["create_standard_views"](input_data={"model_path": part}),
        "create_standard_views",
    )
    assert len(views["standard_views"]["views"]) == 3

    # Passed as a dict on purpose: these tools must accept either shape.
    _ok(
        await tools["add_note"](
            input_data={
                "text": "E2E TEST DRAWING",
                "position_x": 40.0,
                "position_y": 30.0,
            }
        ),
        "add_note",
    )
    listed = _ok(await tools["list_drawing_views"](), "list_drawing_views")
    assert len(listed["views"]) == 3
    _ok(await tools["save_as"](input_data={"file_path": drawing}), "save_as(drawing)")

    # ---- assembly ----
    _ok(await tools["create_assembly"](input_data={"name": "e2e_asm"}), "create_assembly")
    _ok(
        await tools["insert_component"](input_data={"file_path": part}),
        "insert_component#1",
    )
    _ok(
        await tools["insert_component"](
            input_data={"file_path": part, "x": 100.0, "z": 60.0}
        ),
        "insert_component#2",
    )

    components = _ok(await tools["list_components"](), "list_components")
    assert len(components["components"]) == 2

    # Two copies of a 32000 mm3 part.
    mass = _ok(await tools["get_mass_properties"](None), "assembly mass")
    assert mass["mass_properties"]["volume"]["value"] == pytest.approx(
        64000.0, rel=1e-6
    )

    mate = _ok(
        await tools["add_mate"](
            input_data={
                "component_a": components["components"][0],
                "component_b": components["components"][1],
            }
        ),
        "add_mate",
    )
    # The second component sat 60 mm away in Z, so a coincident mate must move it.
    assert mate["mate"]["geometry_moved"] is True

    _ok(await tools["save_as"](input_data={"file_path": assembly}), "save_as(assembly)")
