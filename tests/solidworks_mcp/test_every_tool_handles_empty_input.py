"""Every registered tool must survive a minimal payload.

An MCP client will send an incomplete payload sooner or later — a missing
required field, an empty object. A tool that raises there produces a protocol
error rather than a useful message, and a tool that returns something other than
a dict breaks the response contract the whole server relies on.

This boots the real server, registers all tools, and calls each one with ``{}``.
No SolidWorks session is needed: the point is that validation failures come back
as ordinary error dicts.
"""

import inspect

import pytest


@pytest.mark.asyncio
async def test_every_tool_returns_a_dict_for_empty_input() -> None:
    """No tool may raise, and every tool must return a dict."""
    from solidworks_mcp.config import load_config
    from solidworks_mcp.server import SolidWorksMCPServer

    server = SolidWorksMCPServer(config=load_config())
    await server.setup()
    tools = await server.mcp.list_tools()

    assert tools, "no tools registered"

    raised: list[str] = []
    non_dict: list[str] = []

    for tool in tools:
        takes_args = bool(inspect.signature(tool.fn).parameters)
        try:
            result = await tool.fn({}) if takes_args else await tool.fn()
        except Exception as exc:  # noqa: BLE001 - that is what we are testing
            raised.append(f"{tool.name}: {type(exc).__name__}: {exc}")
            continue
        if not isinstance(result, dict):
            non_dict.append(f"{tool.name} -> {type(result).__name__}")

    assert not raised, (
        f"{len(raised)} tool(s) raised on an empty payload instead of "
        f"returning an error dict: {raised[:5]}"
    )
    assert not non_dict, f"tool(s) returned a non-dict response: {non_dict}"


@pytest.mark.asyncio
async def test_tool_names_are_unique() -> None:
    """Duplicate registrations silently shadow one another."""
    from solidworks_mcp.config import load_config
    from solidworks_mcp.server import SolidWorksMCPServer

    server = SolidWorksMCPServer(config=load_config())
    await server.setup()
    names = [tool.name for tool in await server.mcp.list_tools()]

    duplicates = sorted({name for name in names if names.count(name) > 1})
    assert not duplicates, f"duplicate tool names: {duplicates}"
