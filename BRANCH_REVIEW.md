# Branch review — `feat/feature-editing-and-breaker-isolation`

**8 commits · 20 files · +3400 / −190** · branched from `main` @ `8034624`

Everything below was verified against **live SolidWorks 2025**, not mock mode.
Success was always confirmed with an independent signal — model volume,
a feature-gone check, or a render — never the COM return value.

---

## Why this branch exists

A full reverse-engineering session (toy car: chassis, twin gear motors,
battery bay, shell, spinner) ran end-to-end through this adapter. Everything
subtractive had to be done by hand in the SolidWorks UI, mistakes could not be
undone, and one broken tool would take the whole session down. This branch
closes those gaps.

---

## Commits

| Commit | What |
|---|---|
| `9f0d32e` | 6 new tools (delete/suppress/undo/polyline/ref-plane/mirror) + per-operation circuit breaker |
| `a0a1481` | `create_cut_extrude` actually removes material |
| `841918e` | `create_revolve` and `add_fillet` repaired against real COM signatures |
| `522fa4d` | `create_shell` |
| `b17a2f0` | `list_features` returns the real tree |
| `fb4c4a2` | `pattern_linear` with axis-based direction |
| `59929d5` | Drop redundant rebuilds (~225 ms/op); `get_file_properties` reports the real file |
| `b9c364c` | Analysis tools measure instead of simulating |

---

## Fixed (previously broken)

| Tool | Root cause | Verification |
|---|---|---|
| `create_cut_extrude` | 3 stacked bugs — 26 of 27 args (missing `OptimizeGeometry`); profile walk found 0 sketches (late binding); `ForceRebuild3` cleared the selection | Ø20 hole in 60×40×20 block, through-all + blind, −13.1% volume exactly |
| `create_revolve` | 19 args in wrong order (`Merge` in `ThinType`'s slot); profile never selected | 1.5708e-05 m³, matches Pappus to 4 s.f. |
| `add_fillet` | Wrong overload (9/15 args vs real 14); required un-enumerable `Edge<1>` names | 4 mm on all 12 edges, −3.26% |
| `list_features` | Returned **1** entry (`Comments`) — plausible but wrong | 1 → **23** entries, all real features |
| `get_file_properties` | Returned a hardcoded `Example.sldprt` block for every model | Real path, size, mtime, mass |
| `check_interference` | Always `interference_found: False` **without checking** | Real `ToolsCheckInterference2`; refuses non-assembly docs with a reason |
| `analyze_geometry` | Always `findings: ["No issues found"]` for any analysis type | Measures bounding box / volume; rejects unsupported types explicitly |
| `get_material_properties` | Hardcoded plain-carbon-steel for every model | Real material name; density derived from the model's own mass and volume |

## Added (did not exist)

`delete_feature` · `suppress_feature` · `undo` — a mistake previously meant
rebuilding from scratch
`create_reference_plane` — sketches were limited to the 6 built-in planes
`mirror_feature` · `create_shell` · `pattern_linear` · `add_polyline`
(N segments in 1 COM round-trip)
`get_bounding_box` — overall extents in mm, unioned across solid bodies

## Infrastructure

**Circuit breaker** — state was **global**, so one known-broken tool blocked
every healthy one; and `failure_count` never decayed, so sporadic errors
accumulated across a long session into a spurious trip. Now per-operation with
a 120 s rolling window. Legacy `call()`/`connect()` path and all existing test
assertions unchanged.

**Performance** — `_model_volume`'s verification read called `ForceRebuild3`
(~112 ms) twice per feature; SolidWorks already reflects a just-created feature
in its mass properties, so the rebuild is now opt-in and only runs to re-check
an apparent "nothing changed" before failing. ~225 ms saved per modeling op.

**Caching** — the analysis tools were in the intelligent router's cacheable
set. Now that they read live geometry they are excluded, alongside the mass
properties already excluded for the same reason: the router has no
invalidation, so caching them serves stale values mid-build.

---

## Reviewer notes / risk

1. **No pytest run.** `pytest` is not installed in `.venv`. Existing
   circuit-breaker assertions were replicated manually and pass, but a real
   `dev-test` pass is worth doing before merge.
2. **`add_fillet` behaviour change.** Empty `edge_names` used to be a no-op;
   it now fillets **every** edge. Intentional — it is what makes the tool
   usable — but it is a semantic change.
3. **Circuit-breaker defaults changed**: threshold 5 → 8, recovery 60 s → 25 s,
   plus new `circuit_breaker_failure_window` (120 s).
4. **`mirror_feature` has a real scope limit.** Feature mirroring only resolves
   when the mirrored feature's sketch lies on the mirror plane. The other case
   raises an explanatory error rather than reporting false success.
5. **`pattern_linear` direction sign matters.** Patterning toward the near side
   marches copies off the body; SolidWorks accepts this and produces malformed
   geometry. Documented in the tool description.
6. **`analyze_geometry` is now narrower on purpose.** `curvature`, `draft` and
   `thickness` return an explicit "not supported" error instead of a
   confident-looking fake result. This is a deliberate downgrade in apparent
   capability in exchange for honesty.
7. **`check_interference` is untested on a real assembly.** The signature came
   from `gen_py`, and the return value is a *count*, so a failure surfaces as
   an error rather than a false "no interference" — but it has only been
   exercised against a part document (where it correctly refuses).
8. **Untouched:** auto-reconnect on stale COM (deliberately deferred — it
   touches STA `ComExecutor` threading and the RPC failure mode cannot be
   forced safely to test); live assembly insert + mate (still VBA-generation
   only); circular pattern, draft, rib and hole wizard.

---

## Two lessons worth keeping

**Read the real signature.** Three "unfixable" APIs were all wrong argument
counts. `%TEMP%\gen_py\<guid>.py` holds the exact signature for the installed
SolidWorks — faster and more authoritative than documentation.

**Never trust a COM return value.** `InsertMirrorFeature` returned a Feature
object having mirrored nothing; `FeatureLinearPattern` reported success while
patterning a hole off the side of the block. Volume checks caught the first;
only a **render** caught the second.

**A tool that always succeeds is a broken tool.** Three tools returned
plausible, confident, entirely fabricated results — `interference_found: False`
without checking, `"No issues found"` for any analysis, plain-carbon-steel for
every model. Nothing errored, so nothing looked wrong. These are more dangerous
than the tools that failed loudly.

A corollary: adding a method requires wiring it through **five** layers —
adapter impl, `base.py` default, mock, and *both* the circuit-breaker and
connection-pool wrappers — or it silently returns "not implemented". Mock mode
cannot catch a missing wrapper pass-through, because mock is not wrapped.
