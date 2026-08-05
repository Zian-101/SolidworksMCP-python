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
| `bb4b023` | Circular pattern + reference axis; patterns verify instance count |
| `c885a92` | Draft, move/copy body, delete body |
| `88099d4` | Auto-reconnect on stale COM; `create_assembly` stops overclaiming |
| `8af1a20` | `set_material`, `scale_model`, `delete_face`; material readback fixed |
| `17de730` | **Destructive `save_file` bug fixed**; drawing tools made real |
| `164afee` | Remaining fabricated payloads replaced with real data or honest errors |
| `4fe975a` | Assemblies: insert, list, measure |
| `6b6024e` | Assembly mates |
| `bbc9e8d` | `set_appearance` |
| `7dbbe56` | Regression tests for honesty + wrapper wiring |
| `6fbb154` | Live end-to-end workflow test; dict inputs fixed in drawing tools |
| `0b842c3` | **`list_features` 5.9 s → 0.8 s** |
| `e5b062a` | Targeted flagging across every feature-tree walk |
| `64d93cf` | Perf guard tests; UTF-8 BOM stripped |
| `07fe817` | Last fabricated payloads removed from automation/macro/template |

---

## The one to read first: `save_file` was destroying geometry

Saving a document **to its own path** took the Save-As branch, which closed the
document at the target path, deleted the file, then called `SaveAs3` on the
now-closed document. The result was a valid-looking part containing no solid
body.

Any "build a part, save it, save it again" sequence silently produced an empty
model. This is why parts reopened with zero bodies and zero volume — and it
poisoned several conclusions earlier in this branch, most notably the verdict
that assembly component insertion was unimplementable. SolidWorks was refusing
to insert the empty parts it was being handed.

Fixed: saving over the document's own path is a plain `Save`; only a *different*
document holding the target path is closed; the pre-emptive `os.remove` is gone,
so a failed Save-As no longer destroys the previous file too.

Verified: an 80×40×10 block reports 32000 mm³, survives save and reopen, and
still reports 32000 mm³.

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
| `get_material_properties` (again) | Always reported `assigned: false` — the out-parameter needed a byref VARIANT, so the name was always `None` | Reads the material and its library correctly |

## Added (did not exist)

`delete_feature` · `suppress_feature` · `undo` — a mistake previously meant
rebuilding from scratch
`create_reference_plane` — sketches were limited to the 6 built-in planes
`mirror_feature` · `create_shell` · `pattern_linear` · `add_polyline`
(N segments in 1 COM round-trip)
`get_bounding_box` — overall extents in mm, unioned across solid bodies
`pattern_circular` · `create_axis` — a fresh part has no axis to rotate about,
so the axis tool ships with the pattern or the pattern is unusable
`add_draft` · `move_body` · `delete_body` — the first body-level edits
`set_material` · `scale_model` · `delete_face` — material makes mass properties
mean something instead of defaulting to 1000 kg/m³
`insert_component` · `list_components` · `add_mate` — **assemblies work**
`add_drawing_view` · `create_standard_views` · `add_drawing_note` ·
`insert_model_dimensions` · `list_drawing_views` — **drawings work**
`set_appearance` — display colour and transparency

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

**Pattern verification** — both pattern tools now measure what *one* instance
is worth (suppress the source feature, re-read volume, unsuppress) and require
the result to account for `count - 1` of them. The old "did the volume change?"
guard could not tell 6 instances from 2, and twice only a render caught it.

**Auto-reconnect** — quitting and reopening SolidWorks left a dangling COM
pointer and every later call failed until the MCP server was restarted by hand.
The handle is now re-acquired and the operation retried once. Detection covers
both shapes: the `com_error` HRESULTs *and* the `AttributeError:
SldWorks.Application.<method>` that late binding actually raises — which is why
the old `except com_error` branch never caught it.

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
8. **`pattern_circular` needs an axis normal to the geometry.** An axis lying
   *in* the plane of the feature produces coincident copies. This is now
   caught and explained rather than reported as success, but it is the easiest
   way to misuse the tool.
9. **Pattern verification costs two suppress/unsuppress cycles** (≈1 s) per
   pattern call. Best-effort: if it fails, the tool falls back to the weaker
   guard and says so via `verification: "volume-changed"`.
10. **Auto-reconnect is tested with simulated failures only.** The real
    dangling-pointer scenario cannot be produced without killing a live
    SolidWorks session. The detector, retry, bounded-attempt and
    recursion-guard paths are all covered.
11. **Wrong-overload hazard is real and silent.** `InsertScale` exists on both
    `IModelDoc2` *and* `IFeatureManager` with **different arity and argument
    order**; the document version is `(x, y, z, isUniform)`, so calling it with
    the FeatureManager arguments passes `0` as the X factor and quietly does
    nothing. Likewise `DeleteFaces2` is on `IBody2`, not `FeatureManager`, and
    `InsertMoveFace` is on `FeatureManager`, not `IModelDoc2`. Always confirm
    the owning interface in `gen_py`, not just the method name.
12. **Four APIs were tried and deliberately not shipped**, because each
    returns success-shaped nothing on this build and shipping them would mean
    shipping tools that never work:
    - `InsertCombineFeature` (boolean add/subtract/intersect) — reachable as a
      method, returns `None` for all three operation types, via both `IPartDoc`
      and `IFeatureManager`, with list/tuple/VARIANT tool arrays. Union and
      subtract remain available via `create_extrusion(merge_result=True)` and
      `create_cut_extrude`.
    - Assembly component insertion — `AddComponent4`, `AddComponent5` (config
      options 0–2), `AddComponents3` and `AddComponent` all return `None` and
      leave the component count at zero, before and after saving the assembly,
      with the part loaded and the assembly reactivated.
    - `InsertMoveFace` / `InsertMoveFace2` / `InsertMoveFace3` (direct face
      offset) — all return `None` and change nothing, across move types 0–2
      and both directions, with the face demonstrably selected.
    - `InsertRib` / `InsertRib2` — the `IModelDoc2` overload takes the
      arguments without complaint and produces no geometry; the
      `IFeatureManager` one wants a tenth argument and still produces none.
      A bad sketch setup cannot be ruled out here.
13. **`set_appearance` is verified more weakly than everything else here.** The
    values are confirmed by reading them back from SolidWorks, but the change
    was never *visually* confirmed — `export_image` was unreliable during that
    session, rendering an empty sheet for a part that demonstrably has
    geometry. A SolidWorks appearance applied on top can also override these
    values in the viewport.
14. **Still not working:** boolean combine (`InsertCombineFeature`), direct
    face offset (`InsertMoveFace`), rib (`InsertRib`/`InsertRib2`). All three
    were retried on a healthy session with real geometry after the `save_file`
    fix and still return nothing.
15. **Untouched:** hole wizard, split body.

---

## Performance

`list_features` took **5.9 seconds** on a 20-feature model — an agent calls it
constantly between edits. Everything else was under 600 ms.

Cause: `flag_methods(obj, "IFeature")` per feature. It flags all ~100 methods of
the interface (27 ms measured) and caches by `id(obj)` — every feature is a
fresh dispatch, so **the cache never hits**. The same pattern was in three more
loops.

`flag_members(obj, *names)` flags only what the loop reads:

| | before | after |
|---|---|---|
| `list_features` | 5906 ms | **~800 ms** |
| `create_cut_extrude` | 4411 ms | **937 ms** |
| `pattern_circular` | 11417 ms | **3028 ms** |

Output unchanged throughout: same features in the same order, patterned disc
still 45553.093 mm³, `instances_verified` still 6.0.

A single COM attribute read costs ~6.5 ms, so what remains is dominated by
round-trip count. `open_model` (3331 ms) is SolidWorks loading the file.

---

## The correction worth learning from

An earlier commit on this branch declared assembly component insertion
unimplementable after trying `AddComponent4`, `AddComponent5` across three
config options, `AddComponents3` and `AddComponent` — every one returning
`None`.

That verdict was wrong. SolidWorks silently refuses to insert a part with **no
solid geometry**, and the parts being fed to it were empty because of the
`save_file` bug. The first retry after that fix inserted a component
immediately.

The lesson is not "try harder". It is that a dead-looking API is evidence about
*the whole system*, not just the API — and when several unrelated APIs all go
quiet at once, suspect the inputs before concluding the platform cannot do it.

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
