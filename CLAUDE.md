# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# SolidWorks MCP Server (Python)

This file is the quick orientation guide for contributors and coding agents.

## Platform and Runtime

- Primary runtime is Python 3.11+.
- Real COM automation requires Windows + SolidWorks installed.
- Cross-platform development is possible in mock/test mode.

## Build and Development Commands

Use either micromamba environment commands or local virtualenv commands.

### Preferred PowerShell workflow

```powershell
# Show command help
.\dev-commands.ps1

# Full install in micromamba env
.\dev-commands.ps1 dev-install

# Fast test pass (no SolidWorks-required tests)
.\dev-commands.ps1 dev-test

# Full test run including real SolidWorks integration
.\dev-commands.ps1 dev-test-full

# Lint and format
.\dev-commands.ps1 dev-lint
.\dev-commands.ps1 dev-format

# Docs build/serve
.\dev-commands.ps1 dev-docs-build
.\dev-commands.ps1 dev-docs-strict
.\dev-commands.ps1 dev-docs-audit
.\dev-commands.ps1 dev-docs
```

### Virtualenv direct workflow

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -e ".[dev,test,docs]"

# Run server
.\.venv\Scripts\python.exe -m solidworks_mcp.server

# Lint/tests/docs
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m pytest tests -m "not solidworks_only"
.\.venv\Scripts\python.exe -m mkdocs build --clean
```

### Running tests

`addopts` in `pyproject.toml` enables coverage with `--cov-fail-under=90`, so a
partial run fails on coverage rather than on the tests. Pass `--no-cov` while
iterating.

```powershell
# One file
.\.venv\Scripts\python.exe -m pytest tests/solidworks_mcp/tools/test_drawing.py --no-cov

# One test
.\.venv\Scripts\python.exe -m pytest "tests/solidworks_mcp/adapters/test_adapters.py::TestPyWin32AdapterBranches::test_feature_creation_failure_paths" --no-cov

# Whole suite, no SolidWorks needed (~2.5 min, ~1750 tests)
.\.venv\Scripts\python.exe -m pytest tests -m "not solidworks_only" -q --no-cov

# Live SolidWorks tests (deselected by default)
$env:SOLIDWORKS_MCP_RUN_REAL_INTEGRATION=1
.\.venv\Scripts\python.exe -m pytest tests -m "solidworks_only" --no-cov
```

`--tb=line` gives one line per failure with the file and line number, which is
usually all you need. PowerShell mangles pytest's ANSI colour codes — redirect
to a file with `--color=no` when parsing output.

## Architecture

- Server entrypoint: `src/solidworks_mcp/server.py`
- CLI entrypoint: `src/solidworks_mcp/server_cli_fixed.py`
- Adapters: `src/solidworks_mcp/adapters/`
  - `base.py`: `SolidWorksAdapter` ABC and the `AdapterResult` contract
  - `pywin32_adapter.py`: real SolidWorks COM adapter (Windows)
  - `mock_adapter.py`: mock adapter for tests and CI-like runs
  - `factory.py`: adapter selection/routing logic
  - `circuit_breaker.py`, `connection_pool.py`: decorators that wrap an adapter
- Tools: `src/solidworks_mcp/tools/` (modeling, sketching, drawing, export, analysis, automation, templates, VBA, docs discovery)
- Agent harness: `src/solidworks_mcp/agents/` (prompt schemas, smoke test CLI, run/error persistence)

`PyWin32Adapter` is a composition root, not a monolith. The COM implementations
live in mixins under `adapters/solidworks/` (`pywin32_adapter.py:1460`):

```python
class PyWin32Adapter(
    SolidWorksSketchMixin, SolidWorksFeaturesMixin,
    SolidWorksIOMixin, SolidWorksSelectionMixin, SolidWorksAdapter,
):
```

Where a capability actually lives:

- `adapters/solidworks/io.py` — open/save/close, assemblies (`insert_component`,
  `add_mate`), drawings (`add_drawing_view`, `create_standard_views`),
  materials, appearance
- `adapters/solidworks/features.py` — extrude/cut/revolve, patterns, fillet,
  draft, body operations, `get_bounding_box`
- `adapters/solidworks/sketch.py`, `adapters/solidworks/selection.py`

Tool-layer input normalization is shared, not per-module: use
`normalize_input(input_data, model_type)` from `tools/input_compat.py`
(imported as `_normalize_input` by six tool modules) rather than writing
another one.

## Key Patterns

### COM and Adapter Safety

- Prefer adapter abstraction, not direct COM calls from tool modules.
- Keep Windows/COM behavior behind adapter boundaries.
- Use mock adapter for tests unless a test explicitly requires real SolidWorks.

### Adding an adapter capability — five layers

A new adapter method needs **all five** of these plus tool registration. Miss
one of the last two and it fails only against real SolidWorks: mock mode never
exercises the decorators, and both decorators forward only methods they define
explicitly — there is no `__getattr__` catch-all.

1. Implementation in the relevant `adapters/solidworks/*.py` mixin.
2. A default in `adapters/base.py` that returns a "not supported" error.
3. A mock in `adapters/mock_adapter.py`.
4. A pass-through in `adapters/circuit_breaker.py`. Pattern
   (`circuit_breaker.py:862`):

   ```python
   async def set_material(self, name, database=None):
       return await self._execute_with_circuit_breaker(
           "set_material",
           lambda: self.adapter.set_material(name, database),
           input_dict={"name": name, "database": database},
       )
   ```

5. A pass-through in `adapters/connection_pool.py`.

Then register the tool with `@mcp.tool()` in the matching `tools/*.py`.

### Verification discipline

**Never trust a COM return value.** SolidWorks reports success for operations
that did nothing, or that did damage. Observed on this build: `FeatureFillet3`
returned `None` while the tool reported success; `pattern_circular` reported
6 instances when the model had 2; `delete_face` destroyed the solid (0 bodies)
and returned success. Confirm the effect independently — volume math, feature
or instance counts, bounding boxes, a render — and raise when the check fails.

**Never fabricate a payload.** A tool with no adapter support must return
`status: "error"`, never a plausible-looking result. A fabricated
`interference_found: False` is worse than no answer, because the caller acts on
it. Guarded by `tests/solidworks_mcp/tools/test_no_fabricated_payloads.py` and
`tests/solidworks_mcp/test_every_tool_handles_empty_input.py`.

The trap to avoid is the `hasattr` fallback: call the adapter on the happy path,
then invent a result when the capability is missing. It reads as defensive
coding and it lies.

```python
if hasattr(adapter, "create_technical_drawing"):
    ...                                  # real path
return {"status": "success",             # never do this
        "data": {"views_created": ["Front", "Right", "Top"]}}
```

`test_no_tool_invents_a_payload_when_the_adapter_cannot_help` flags any fallback
that returns success while touching neither `adapter` nor `result`. If a tool
genuinely needs no SolidWorks session (VBA text generation, comparing two files
on disk, the on-disk template library), add it to `ADAPTER_FREE_TOOLS` with a
reason instead.

### Logging and Output

- Use project logging utilities (`loguru`/configured helpers).
- Avoid ad-hoc print statements in runtime server paths.

### Validation and Tool Contracts

- Keep tool input schemas strict and explicit.
- Maintain stable response payload shapes (`status`, `message`, `execution_time`, plus data payload).

## Testing Guidance

- Default local path: run non-`solidworks_only` tests first.
- Real integration path: run `dev-test-full` on Windows with SolidWorks available.
- Harness and generated report artifacts may write under `tests/.generated/` and `.solidworks_mcp/`.

## Documentation Guidance

- Build docs before commit when touching docs pages:
  - `.\dev-commands.ps1 dev-docs-build`
  - `.\dev-commands.ps1 dev-docs-strict`
- For local preview:
  - `.\dev-commands.ps1 dev-docs`

## Agent and Model Notes

- VS Code Copilot subscription is suitable for chat-based workflows.
- Local Python smoke tests require explicit provider credentials:
  - GitHub Models: `GH_TOKEN` or `GITHUB_API_KEY`
  - OpenAI: `OPENAI_API_KEY`
  - Anthropic: `ANTHROPIC_API_KEY`

## Troubleshooting Runbook

When the bridge misbehaves, walk this list in order. Compiled from SolidWorks
forum threads, pywin32 issues, and observed failures on this install. Last
updated 2026-04-24.

### 1. `OpenDoc6` HRESULT failure — pass-by-ref params

- **Cause:** pywin32 `makepy`/`gencache` marks SW's pass-by-ref `errors` and
  `warnings` parameters as non-optional inputs. Calls fail unless
  `pythoncom.Missing` is passed explicitly.
- **Check:** grep server code for `OpenDoc6(`; every callsite should pass
  `pythoncom.Missing` for the last two params.
- **Fix:**
  `model, errors, warnings = sw.OpenDoc6(path, type, opts, '', pythoncom.Missing, pythoncom.Missing)`
- **Error codes:** warning=128 = already open (not fatal); error=1024 = generic
  open failure. S_OK with null return is also possible.

### 2. `Member not found` / `NoneType not callable` — stale gencache

- **Cause:** pywin32 caches SW type-library wrappers under `%TEMP%\gen_py\`.
  SW upgrades (e.g. 2024 → 2025) or patches leave wrappers pointing at the
  old TLB.
- **Fix:** delete `%TEMP%\gen_py\`, restart the MCP server. Rebuilds on first
  call.

### 3. `No active model` AND `OpenDoc6` errors together — stale COM handle

- **Cause:** MCP server process grabbed a COM pointer at startup; user has
  since quit and reopened SolidWorks. Pointer is dangling.
- **Check:** compare MCP server start time (Claude `main.log` →
  `Launching MCP Server: solidworks`) to current `SLDWORKS.exe` start time.
- **Fix:** restart Claude Desktop (respawns MCP server, which grabs a fresh
  SW handle). Restarting SolidWorks alone will NOT fix this.

### 4. `Circuit breaker is open for <tool>`

- **Cause:** server-side resilience library trips after N failures in a
  window. Subsequent calls fail fast even when the underlying issue is fixed.
- **Fix:** wait for breaker timeout (~30–60s) or restart the server.

### 5. COM apartment / threading mismatch — FastMCP async workers

- **Cause:** SolidWorks COM is STA (single-threaded apartment). An IDispatch
  proxy obtained on thread A cannot be invoked from thread B. FastMCP runs
  tool handlers on worker threads distinct from where `connect()` ran.
- **Signature (critical):** pywin32 late-binding surfaces this as
  ``AttributeError: SldWorks.Application.<method>`` at attribute lookup —
  **NOT** as ``pywintypes.com_error``. The `except com_error` branch in
  ``_handle_com_operation`` therefore misses it, and the generic handler
  flattens the message to the source+method name with no traceback.
- **Fix (applied 2026-04-24, revised same day):** dedicated STA worker
  thread. See "COM threading architecture" section below. The earlier
  thread-local fix (`_tls` / `_swapp_for_thread`) was a band-aid that was
  replaced by the proper executor-based design.

### 6. PDM vault files

- **Cause:** `OpenDoc6` on a file under a PDM working folder fails when the
  file isn't checked out or cached locally.
- **Check:** target path has PDM vault metadata / is under a PDM working
  folder.
- **Fix:** check the file out in PDM, or test with a copy outside the vault.

### 7. Silent-mode UI leak

- `swOpenDocOptions_Silent` still pops the UI on some SW-2025 SP levels.
  Cosmetic only; not a failure.

### 8. SW 2025 SP0 drawing crashes

- SP0 has reported `.slddrw` open crashes. If the target is a drawing,
  suggest upgrading to SP1+.

### 9. MCP log silence

- FastMCP banner output (emoji-prefixed lines to stdout) is misparsed as
  JSON-RPC by the Claude host — noise, not errors.
- Actual tool-call tracebacks go to **stderr** and are NOT captured in
  `%APPDATA%\Claude\logs\mcp-server-solidworks.log`. Check the
  `%LOCALAPPDATA%\solidworks_mcp\logs\` directory and the FastMCP install
  dir for a separate Python log.

### 10. Claude Code `settings.json` UTF-8 BOM (host-side, not SW)

- A BOM on `~/.claude/settings.json` makes Claude Code silently drop **all**
  user settings (`[SettingsIo] Failed to read ... Unexpected token '﻿'`).
  Strip the BOM; write plain UTF-8.

### 11. `SelectByID2` Callout type mismatch — use `VT_DISPATCH` null, not `None`

- **Signature:** `(-2147352571, 'Type mismatch.', None, 8)` on any `SelectByID2` call.
- **Cause:** The `Callout` parameter (8th arg) is typed `VT_DISPATCH`. Python `None`
  marshals as `VT_NULL` which SW rejects. Must pass an explicit COM null pointer:

  ```python
  import pythoncom, win32com.client as _win32com
  null_callout = _win32com.VARIANT(pythoncom.VT_DISPATCH, None)
  model.Extension.SelectByID2("", "EDGE", x, y, z, append, mark, null_callout, 0)
  ```

- **Applies to:** Every `SelectByID2` / `SelectByID` call with no real callout.

### 12. `InsertFeatureChamfer` is on `IFeatureManager`, not `IModelDocExtension`

- **Signature:** `<unknown>.InsertFeatureChamfer` when calling via `model.Extension`.
- **Cause:** `InsertFeatureChamfer` (DISPID 83) is on `IFeatureManager`.
  Routing through `model.Extension` (IModelDocExtension) causes `DISP_E_MEMBERNOTFOUND`.
- **Fix:** `fm = model.FeatureManager; fm.InsertFeatureChamfer(1, 1, width_m, pi/4, 0, 0, 0, 0)`
- **More detail:** See `docs/agents/com-api-pitfalls.md` for the full pattern catalogue.

### 13. `ForceRebuild3(True)` required before coordinate-based edge/face selection

- **Signature:** `SelectByID2("", "EDGE", x, y, z, ...)` returns `False` on a freshly
  created feature.
- **Cause:** New feature edges are not tessellated until an explicit rebuild.
  `SelectByID2` uses the tessellated mesh to resolve coordinates.
- **Fix:** Call `model.ForceRebuild3(True)` once before the first `SelectByID2` in a
  feature operation.

> **Full COM pitfall catalogue for LLM agents:** `docs/agents/com-api-pitfalls.md`

### Decision order when starting a debug session

1. Read recent `%APPDATA%\Claude\logs\main.log` entries for
   `Launching MCP Server: solidworks` and note the timestamp.
2. Compare to current `SLDWORKS.exe` process start (Task Manager). If SW is
   newer than the server → **#3**, restart Claude Desktop first.
3. If SW is older or same, try a trivial call (`get_model_info`). If it
   returns a circuit-breaker error, wait 60s and retry → **#4**.
4. If real error text surfaces, map to #1/#2/#5/#6 via the error signature
   above.
5. Only then read server source to confirm.

## COM threading architecture

Invariants every new COM-touching code path must respect. Written 2026-04-24
after the Phase 1+2 rewrite landed.

### 1. All COM calls run on the adapter's ComExecutor thread

The adapter owns a single dedicated worker thread (``PyWin32Adapter._com``,
instance of ``com_executor.ComExecutor``). COM is initialized on that thread
once via ``pythoncom.CoInitialize()``. All COM work — ``connect()``, every
``_handle_com_operation`` closure, every ``disconnect()`` cleanup — is
submitted to that executor and awaited via ``Future``.

Consequences:

- ``self.swApp`` and ``self.currentModel`` are **only** valid when touched
  from inside an executor job. Reading them from an async tool function
  or an HTTP handler thread directly will raise the cross-thread
  ``AttributeError`` described in runbook item #5.
- Do NOT call ``pythoncom.CoInitialize()`` anywhere else in the adapter
  code. The executor owns the apartment.
- Do NOT cache IDispatch references outside instance attributes that are
  only read from executor jobs.

### 2. Late binding is forced, always

``_do_connect`` uses ``win32com.client.dynamic.Dispatch`` instead of
``win32com.client.Dispatch``. Rationale: when the makepy-generated
``gen_py`` wrapper is loaded (it is, as soon as ``sw_type_info`` is
imported), plain ``Dispatch`` would auto-upgrade to an early-bound wrapper.
Early-bound wrappers reject the VARIANT-based pass-by-ref out-parameters
used by ``OpenDoc6`` and many other SW calls; migrating to ``pythoncom.Missing``
for every such call is a much larger change than we want.

If you add a new COM-touching function: call ``dynamic.Dispatch`` if you
need to acquire a fresh IDispatch, **not** ``EnsureDispatch``.

### 3. Method flagging via sw_type_info

``sw_type_info.flag_methods(obj, *interfaces)`` tells pywin32's late
binding to resolve specific names as methods (``Invoke`` with method
flags) rather than properties. Without flagging, zero-arg SW methods like
``GetTitle()`` raise ``TypeError: 'str' object is not callable`` because
the dispatch returns the string *value*, which Python then tries to call.

Apply flagging:

- On ``swApp`` after acquiring it → ``flag_methods(app, "ISldWorks")``
- On a newly-opened document → ``flag_doc(model, doc_type)`` (infers from
  doc type: Part=1, Assembly=2, Drawing=3)
- On any intermediate dispatch returned from a SW call →
  ``sw_type_info.flagged(x, "IInterfaceName")`` inline-style

Interface names come from the gen_py wrapper (run
``python -m win32com.client.makepy "C:\\Program Files\\SOLIDWORKS Corp\\SOLIDWORKS\\sldworks.tlb"``
to regenerate after a SW version upgrade).

### 4. Properties are still properties

Not every zero-arg accessor is a method. ``IConfiguration.Name``,
``ModelDoc2.Visible``, etc. are genuine properties — read them without
``()``. If you flag them as methods you'll get the opposite TypeError.
When in doubt, check the gen_py wrapper: methods live in the class body
as regular defs; properties use ``_prop_map_get_`` / ``_prop_map_put_``.

### 5. Flag only what you read

``flag_methods(obj, iface)`` flags ~100 names and costs ~27 ms. Its cache is
keyed on ``id(obj)``, so a loop over freshly-returned dispatches never hits it
and pays the full cost every iteration. Use
``sw_type_info.flag_members(obj, *names)`` (``sw_type_info.py:207``) to flag
just the members you are about to touch.

### 6. Flagging is per-object — mind fresh dispatches

``GetViews``, ``GetComponents`` and friends return **raw** ``PyIDispatch``
objects, not wrapped ones. Method flagging is a silent no-op on those — it
neither errors nor takes effect. Wrap each element with
``win32com.client.dynamic.Dispatch`` before flagging or calling it.

The same trap bites through ``swApp.ActiveDoc``, which returns a **fresh,
unflagged dispatch every time**. Flagging ``adapter.currentModel`` does not
apply to it, so ``swApp.ActiveDoc.GetActiveSketch2()`` raises "Member not
found", and if that call sits inside ``adapter._attempt`` the error becomes
``None`` — indistinguishable from "no sketch is open". That silently broke
``add_sketch_constraint`` and ``exit_sketch``. Always call through the
flagged ``adapter.currentModel``, falling back to ``swApp.ActiveDoc``:

```python
sw_active = adapter._attempt(
    lambda: adapter.currentModel.GetActiveSketch2()
) or adapter._attempt(lambda: adapter.swApp.ActiveDoc.GetActiveSketch2())
```

### 7. Byref VARIANT out-parameters

Nuances runbook item #1. ``pythoncom.Missing`` is not universally sufficient:
``OpenDoc6`` and ``GetMaterialPropertyName2`` need real byref VARIANTs
(``VARIANT(VT_BYREF | VT_I4)`` / ``VT_BSTR``) — with ``Missing`` they return
``None`` or raise. ``SetMaterialPropertyValues`` needs
``VARIANT(VT_ARRAY | VT_R8)``; a plain Python list raises.

### 8. Call-then-fallback is narrow

A late-bound member may resolve as a bound method *or* as a value, so the
read helper calls it and falls back. The fallback must be limited to
``TypeError`` (value not callable) and ``com_error`` (COM object value):

```python
try:
    return member()
except TypeError:
    return member                              # already a value
except Exception as exc:
    if type(exc).__name__ == "com_error":
        return member                          # COM object value
    return None                                # genuine failure
```

A blanket ``except Exception: return member`` returns the bound method as data
— that is how ``list_features`` came to report ``type: '<bound method ...>'``.

### 9. Interface ownership

The same method name can live on two interfaces with different signatures.
``InsertScale`` is on ``IModelDoc2`` as (x, y, z, isUniform) and on
``IFeatureManager`` as (Type, Uniform, X, Y, Z) — different arity *and* order.
``DeleteFaces2`` is on ``IBody2``; ``InsertMoveFace`` is on ``IFeatureManager``.
``IBody2::Select2`` takes a SelectData object as its second argument, while
``IFace2::Select2`` takes a mark. Confirm ownership in the gen_py wrapper or
via the `swapi-pilot` MCP before calling — never from memory.

### 10. Known-broken on this build

Do not re-litigate these; they were retried against valid solid geometry and
still fail: ``InsertCombineFeature`` (boolean ops), ``InsertMoveFace``,
``InsertRib``. Hole wizard and split body are simply unimplemented.

### 11. A "live" test is only live if it clears all three mock switches

``tests/conftest.py`` sets ``USE_MOCK_SOLIDWORKS=true`` at import time for the
whole session, and ``AdapterFactory._determine_adapter_type`` returns ``MOCK``
whenever ``config.testing or config.mock_solidworks`` is set — **before** it
looks at ``adapter_type``. A test that boots the server via ``load_config()``
therefore gets the mock even under ``SOLIDWORKS_MCP_RUN_REAL_INTEGRATION=1``
and the ``solidworks_only`` marker.

``test_live_workflow_e2e`` ran this way for its whole life, asserting against
invented volumes (24042.6, 37000.2, 95304.4 mm³ on consecutive runs of the
same 80×40×10 = 32000 mm³ box). To force the real adapter, clear all three:

```python
os.environ.pop("USE_MOCK_SOLIDWORKS", None)
config = load_config()
config.adapter_type = AdapterType.PYWIN32
config.testing = False
config.mock_solidworks = False
```

Quickest tell that a "live" test is secretly on the mock: runtime. Real
SolidWorks takes tens of seconds; the mock finishes in about one.

Tests using the ``connected_adapter`` fixture build ``PyWin32Adapter``
directly and are unaffected.

Do **not** call ``CloseAllDocuments`` to get a clean session. It reaches
across the whole SolidWorks application, including documents held by other
tests' adapters, and makes unrelated tests fail on ordering alone.

### 12. Regression tests

See ``tests/test_live_sw_regression.py`` for the safety net:

- ComExecutor start/stop/exception semantics
- flag_methods incrementality + per-interface correctness
- Late-bound ``swApp`` acquisition
- ``get_model_info`` fields populate correctly
- ``get_model_info`` works from a worker thread (the cross-thread bug
  reproducer)

Run these after any change to ``pywin32_adapter.py``, ``com_executor.py``,
or ``sw_type_info.py``::

    $env:SOLIDWORKS_MCP_RUN_REAL_INTEGRATION=1
    .\.venv\Scripts\python.exe -m pytest tests/test_live_sw_regression.py -v

### Reference sources

- [Problem with OpenDoc6 — SW Forums](https://forum.solidworks.com/thread/19519)
- [OpenDoc6 error — SW Forums](https://forum.solidworks.com/thread/100254)
- [Opendoc6/7 silent open — SW Forums](https://forum.solidworks.com/thread/245676)
- [pywin32 #337 SW pass-by-reference bug](https://sourceforge.net/p/pywin32/bugs/337/)
- [pywin32 #1585 strange issues with SW](https://github.com/mhammond/pywin32/issues/1585)
- [CodeStack SW macros troubleshooting](https://www.codestack.net/solidworks-api/troubleshooting/macros/)
- [SW 2025 SP0 drawing crash thread](https://forum.solidworks.com/forum-solidworks/MYfrK4r0RF6Fnd8tf5tAMA/solidworks-2025-sp0-crashes-when-opening-a-drawing-file)
- [pythoncom CoInitializeEx docs](https://timgolden.me.uk/pywin32-docs/pythoncom__CoInitializeEx_meth.html)
