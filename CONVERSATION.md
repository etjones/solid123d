# Conversation Log

## 2026-08-13

**User**: Wants to transition from OpenSCAD/SolidPython to build123d. Asked
for a small bridge letting existing SolidPython code build build123d objects
by only changing imports, e.g. `from solid import translate, cube,
scad_render_to_file` → same API, build123d underneath.

**Assistant**: Built the `solid123d` package (uv project, build123d 0.11.1,
Python 3.13, branch `feature/solidpython-bridge`).

Key design decisions:
- Primitives return **native build123d `Shape` objects** (no wrapper class),
  so bridged code interoperates directly with build123d and migration can
  proceed file-by-file. Trade-off: SolidPython's `a * b` intersection
  operator is unavailable (`a & b` / `intersection()(a, b)` instead).
- Transforms are closures: `translate(v)` returns a callable applying
  `Pos * shape`; multiple children are implicitly unioned as in OpenSCAD.
- `rotate([x,y,z])` applies sequential global-axis rotations X→Y→Z to match
  OpenSCAD's fixed-axis order exactly; axis-angle and scalar forms supported.
- OpenSCAD alignment semantics preserved: `cube`/`square` corner at origin
  unless `center=True`; `cylinder` XY-centered sitting on z=0.
- `scad_render_to_file` exports real geometry: `.scad` filenames rewritten
  to `.step` with a `UserWarning`; `.stl`/`.step`/`.stp` honored as-is.
  `scad_render()` raises `NotImplementedError` (no SCAD source exists).
- `hull`, `minkowski`, `linear_extrude(twist=)` raise `NotImplementedError`
  (no BRep equivalent); `segments`/`$fn` accepted and ignored.
- `linear_extrude(scale=)` implemented via loft between base and scaled top.
- `rotate_extrude` maps the XY profile onto Plane.XZ then `revolve`s about Z.
- `solid123d.utils` provides `up/down/left/right/forward/back`.

Verification: 32 pytest tests pass (volumes/bboxes vs analytic values, e.g.
torus volume for `rotate_extrude`); user's exact example script runs with
only the import changed and emits a valid STEP file.

## 2026-08-13 (later)

**User**: OpenSCAD found "Academy Engraved LET" by name but build123d
couldn't. How does font identification work on both systems?

**Assistant**: Diagnosed on-machine: OpenSCAD uses fontconfig, which matches
the family name (nameID 1) and treats subfamily (nameID 2) as a style with
fuzzy best-match fallback. build123d uses OCCT `Font_FontMgr`, which only
folds standard subfamilies (Regular/Bold/Italic/Bold Italic) into font
aspects; this font's subfamily is "Plain", so OCCT registers it as
"Academy Engraved LET Plain" and a lookup by family name warns on stderr and
silently substitutes Arial. Verified: `Text(font="Academy Engraved LET
Plain")` and `font_path=` both render correctly.

**User**: Make `text()` resolve fonts by family name.

**Assistant**: Added `solid123d/fonts.py`: scans platform font dirs
(macOS/Linux/Windows) with fontTools (~0.06 s, `lru_cache`d), indexes
family -> {subfamily -> path} incl. .ttc collections, parses OpenSCAD's
`"Family:style=Style"` syntax, resolves to a concrete file path passed to
build123d as `font_path`. Unknown families fall through to build123d's own
name lookup (with standard styles mapped to `FontStyle`). Default style
preference: regular/plain/normal/book/roman/medium, else first face.
10 new tests (parse, resolution, end-to-end area check vs Arial fallback);
42 total pass.

## 2026-08-13 (later still)

**User**: Reported unions/differences "not applying" in sollie_token.py;
suspected linear_extrude without twist.

**Assistant**: linear_extrude is exact; real bug was solid123d `scale()`
padding a 2-vector with 0 instead of 1 (OpenSCAD identity), flattening
extruded text to degenerate solids so engraving subtractions no-op'd or
nulled. Fixed via `vec3(v, default=1.0)` + regression test (43 pass);
user's script verified end-to-end (embeds seat exactly into pockets).

**User**: Declined adding color-aware compound export to the bridge
(OpenSCAD exports colorless STL anyway). Asked how to make one STEP with
per-shape colors from two build123d Shapes.

**Assistant**: Recipe: set `.color` (and optionally `.label`) on each
Shape, group with `Compound(children=[...])` (grouping, not fusing), then
`export_step`. Verified two-color output in combined_colored.step. Gotcha
documented: the 8 predefined STEP colours (yellow, red, ...) are written
as DRAUGHTING_PRE_DEFINED_COLOUR('name'), not COLOUR_RGB — grep both when
inspecting files.

**User**: Wants a typing alias in solid123d (aliasing build123d.Shape) so
old SolidPython return-type annotations stay correct. (First asked for
`SolidPythonObject`, then corrected: that name was a mistake.)

**Assistant**: Exported `OpenSCADObject` (SolidPython's real class name)
and `OpenSCADObjectPlus` (solid2's) as aliases of `build123d.Shape`.
Test added; 44 pass.

**User**: Chose the name `solid123d` (over solid-build123d etc., all
verified available on PyPI); asked to replace every "solidbd" occurrence.

**Assistant**: Renamed src/solidbd -> src/solid123d and
tests/test_solidbd.py -> tests/test_solid123d.py; updated pyproject.toml,
README, tests, sources, and CONVERSATION.md; re-locked and synced with uv;
also updated the imports in sollie_token_aug_2026/sollie_token.py. Grep
confirms zero remaining occurrences; 44 tests pass.

**User**: Commit, create public repo etjones/solid123d, push, add CI to
run tests, then local build (manual PyPI publish to follow).

**Assistant**: Publish prep: removed stale `[project.scripts]` from
pyproject; declared explicit fonttools dependency; added MIT LICENSE,
metadata/classifiers/URLs; relaxed requires-python to >=3.10 (verified
44 tests pass on 3.10 and 3.13 locally). Added .gitignore and GitHub
Actions CI (uv, ubuntu+macos x 3.10/3.13). Initial commit on main,
created github.com/etjones/solid123d, pushed; CI succeeded on all four
matrix legs. `uv build` produced sdist+wheel in dist/; wheel verified in
an isolated env. Ready for `uv publish` by user.

**User**: Add a GitHub CI badge to the README.

**Assistant**: Added the actions/workflows/ci.yml badge under the README
title, linked to the workflow page; committed and pushed.

**User**: Published to PyPI (https://pypi.org/project/solid123d/). Asked
for a release tag and GitHub release.

**Assistant**: Verified PyPI live + CI green, tagged v0.1.0 (annotated),
pushed the tag, and created the GitHub release with sdist + wheel
attached and release notes: highlights, install line, known limitations.
https://github.com/etjones/solid123d/releases/tag/v0.1.0

## 2026-08-18

**Context**: this patch was made from a separate downstream project,
`scad123d` (imports OpenSCAD files as build123d geometry, layered on top of
solid123d), during a session there. While designing scad123d's own
Minkowski handling, it became clear solid123d's `minkowski()` raised
`NotImplementedError` *unconditionally*, including for
`minkowski()(A, sphere(r))` -- the shape-rounding idiom that accounts for
the large majority of real-world `minkowski()` calls.

**User**: asked how solid123d handles `hull()`/`minkowski()`, noting the
sphere/circle case scad123d had just solved might apply here too, then
asked for the patch to be written.

**Assistant**: Patched `minkowski()` in `src/solid123d/booleans.py` to
detect a bare, untransformed `sphere()`/`circle()` at the origin as either
argument (via `BRepAdaptor_Surface`/`BRepAdaptor_Curve`, checking
`GeomType.SPHERE`/`GeomType.CIRCLE` and that the primitive's center is
within 1e-6 of the origin), and compute the sum as `offset(A, r,
kind=Kind.ARC)` -- exact BRep, not an approximation. Verified against the
3D and 2D Steiner formulas to ~1e-9 relative error, confirmed commutative
(ball as either argument), and confirmed `minkowski(sphere(2), sphere(3))`
resolves to a radius-5 sphere. Everything else -- general Minkowski sums,
`hull()` -- still raises `NotImplementedError` exactly as before: no new
dependencies, purely additive. Added `TestMinkowski` to
`tests/test_solid123d.py` (6 cases) and updated the README's Supported/Known
differences sections. All 50 tests pass. Committed directly to `main`
(5ba9785) with the user's explicit go-ahead, since v0.1.0 is already
published and this needs a version bump before the fix reaches PyPI users --
left that decision to the user rather than bumping unasked.

## 2026-08-21 — Analytic hull() and expanded minkowski() (ported from scad123d)

Ported scad123d's analytic geometry cores into solid123d as `hull.py` and
`minkowski.py`, making solid123d the canonical home (scad123d will import
them back in a follow-up). `hull()` now evaluates exactly: equal-radius
spheres (incl. collinear capsules), equal-radius parallel cylinders sharing
a span, two spheres of any radii (sewn cap/tangent-cone construction, with
containment and overlap handled), two 2D circles (keyhole/stadium), and
all-polyhedral children (via ConvexPolyhedron). `minkowski()` additionally
recognizes polyhedron-tessellated ball kernels (BOSL2-style). Added the
missing `polyhedron(points, faces)` primitive. Everything else still raises
NotImplementedError with messages naming exactly what is supported.
Zero new dependencies (scipy/numpy already come with build123d). 19 new
tests; 68 total pass. Version bumped to 0.2.0.

## 2026-08-21 — color() preservation and part labels (added to the same PR)

Ported scad123d's color-preservation core into `group()` (the implicit
union behind `union()` and every applier): colored children with zero
shared volume stay a Compound of separate bodies with their own colors;
overlap fuses with the first child's color; uncolored groups take the
plain fuse untouched (gated before any mass-property work). `color()` now
also labels parts -- with the author's literal name string (an improvement
scad123d can't match: OpenSCAD's CSG export discards names, forcing a
reverse lookup there), or CSS-name/hex for numeric colors. group() also
gained OpenSCAD's 2D/3D-mixing warning. `color_label` exported for
scad123d's dedup follow-up. 12 new tests; 80 total pass.

## 2026-08-23 — hull() of pre-fused/grouped children (Gridfinity bug)

A Gridfinity cup import produced silently-wrong geometry (10% of true
volume): OpenSCAD wraps module-call bodies in group(), so `hull()
corner_posts();` arrives as ONE pre-fused compound of four cylinders, and
analytic_hull's single-child identity shortcut returned it unchanged --
correct only for convex children. Fix: explode inputs into component
solids/faces before classification (hulls are decomposition-invariant),
and delete the identity shortcut outright (single convex primitives still
come back exact via their rungs; hull of a single non-convex child now
computes the true hull). Verified against the full Gridfinity cup:
0.03% volume agreement with OpenSCAD. 4 new tests; 84 pass. -> 0.2.1

## 2026-08-25

**User**: Wants OpenSCAD customizer behavior in solid123d: tune in
OpenSCAD's existing customizer UI, export the chosen parameter set, have
solid123d respect it. (Wants to avoid building any custom UI.) Asked for
a minimal OpenSCAD customizer example.

**Assistant**: Used OpenSCAD's native parameter-set JSON as the bridge
(the file the customizer's "+" button writes next to the .scad, same one
the CLI takes via `-p file.json -P set`). Added:
- examples/customizer/coin.scad — minimal annotated customizer example
  (tabs, slider/step/dropdown-range comments, [Hidden] section); verified
  by rendering all 3 sets through OpenSCAD 2025.07 CLI.
- examples/customizer/coin.json — 3 parameter sets in OpenSCAD's format
  (all values strings, fileFormatVersion 1).
- src/solid123d/customizer.py — load_params(path, set_name) +
  parameter_sets(path); accepts .json or .scad (finds sibling .json);
  coerces OpenSCAD literal strings via json.loads fallback-to-str.
- examples/customizer/coin.py — Python twin building the same coin from
  the same JSON: `coin(**load_params("coin.scad", "big_thin"))`.
- tests/test_customizer.py; README section. 112 tests pass; ruff clean.

Note: repo moved to ~/Dropbox/Projects/solid123d since last session;
a few files initially written to the old path were relocated and the
stale directory removed. Work is on branch feature/customizer,
uncommitted.

**User**: Customizer use should be the default behavior: a similarly
named JSON next to the target file should apply automatically, with a
command line switch to opt out.

**Assistant**: Added `customize()` to solid123d.customizer: called once
after module-level parameter defaults, it finds `<script>.json` beside
the calling script (via caller frame globals' __file__), applies the
chosen set to existing variables only (OpenSCAD semantics; unknown keys
warn), and is a silent no-op when no JSON exists. Set selection:
-P NAME > set named "default" > only set > KeyError naming candidates.
Switches (mirroring OpenSCAD CLI, consumed from sys.argv so user
argparse is undisturbed): -P/--parameter-set, -p/--parameter-file,
--no-customizer. Example coin.py rewritten to the default-on pattern;
README updated. 122 tests pass with warnings-as-errors; ruff clean.
Still uncommitted on feature/customizer.

**User** (mid-turn): Add CLI output confirming the parameter set is
being applied, so nobody is confused by values coming from a JSON file
they forgot about.

**Assistant**: customize() now prints to stderr:
"Applying customizer parameter set 'name' from /path/coin.json (use
--no-customizer to ignore it)". stderr so piped stdout stays clean;
quiet when skipped or when no file exists. Two tests added (announce
content, quiet with --no-customizer); 124 pass; ruff clean.

**User**: Confirmed the customizer round trip works. The missing piece
was that in recent OpenSCAD nightlies (2023.10+ incl. 2025.07.18),
presets are written to the JSON on normal file save (Cmd-S) after
pressing "+" — the documented "save preset" button no longer exists
(openscad/openscad#4804). Also confirmed intent: the customizer UI side
is OpenSCAD-only; Python models consume the JSON via customize(), with a
parameter-stub .scad as the tuning UI for Python-only designs.

**User**: With solid123d installed editable into scad123d, scad2step
didn't apply a parameter-set JSON sitting next to the input .scad.

**Assistant**: Diagnosis: customize() only serves Python scripts;
scad123d's converter had no customizer integration at all. Added public
`resolve_param_set(path, set_name)` to solid123d.customizer (shared
selection rules: named > "default" > only set > KeyError), refactored
customize() onto it. In scad123d (branch feature/customizer-param-sets):
scad2step now auto-applies a sibling <input>.json (announced on stderr),
with -P/--parameter-set, -p/--parameter-file, --no-customizer flags;
JSON params feed OpenSCAD as -D overrides, and explicit -D beats the
file (OpenSCAD's own precedence). 8 new CLI tests; 250 pass there,
126 here. Verified on the user's battery-organizer file (its JSON has
two sets, no "default", so -P is required — clear error says so).
Note: scad123d now uses solid123d.resolve_param_set, which is
unreleased; scad123d's `solid123d>=0.3.1` floor must bump when the next
solid123d version ships.

**User**: Agreed the twin-model example was contrived. Keep scad123d
as-is; add -D support to customize(); remove the customizer example and
README section (keep the functionality, document later if demand
appears). Then push/tag/publish both packages, restoring scad123d's
dependency on the PyPI solid123d.

**Assistant**: customize() now honors repeatable `-D name=value`
(OpenSCAD-literal coercion, beats the parameter file, still applies
under --no-customizer, consumed from argv). Deleted examples/ and the
README customizer section; tests rewritten self-contained (129 pass).
Version 0.3.1 -> 0.4.0; released.

**User**: Take a run at Route A now (color-partitioning union) —
feature branch, experimental.

**Assistant**: Branch feature/color-partition-union. group()'s overlap
path now partitions instead of fusing: nested colored compounds expand
to leaves; adjacent same-colored runs fuse first; later children clip
earlier ones (rule: "a color() region keeps its color wherever no later
sibling claims the space"); empty remainders drop; result is a Compound
of touching bodies with colors/labels restored after each boolean.
Motivating example verified in STEP: red sphere-minus-cube body beside
the uncolored cube, 3 PRODUCTs, red preserved. scad123d inherits the
behavior at its next solid123d version bump (its union delegates to
group()).

Discovered en route: build123d's plain `-` AND `+` silently lose
geometry when a curved face's parametric seam lies in the work region —
sphere(5)-cube(8,center) drops the +X cap (73.30 vs 87.96), and the
fuse loses the same material (551.64 vs 599.96). Any explicit OCCT
fuzzy value (even 1e-9) fixes both. Partition uses robust
_cut()/_fuse() helpers (BRepAlgoAPI + SetFuzzyValue 1e-9) and a
volume-conservation fallback to the plain fuse. Routing difference()/
intersection()/plain unions through the same helpers + upstream report
flagged as a separate task. 134 tests pass; ruff clean.

**User**: The regenerated cube_sphere_colored.step is missing one of six
domes and PrusaSlicer reads zero volume — is this the build123d bug?
Asked for the proposed workaround and its speed/clarity cost; work on
the existing branch; NO upstream bug report without preview.

**Assistant**: Confirmed (file had 0 solids, bbox x stopped at 4.0 where
the +X cap should reach 5.0). Root cause CORRECTED during the fix: the
OCCT boolean algorithms are fine, and fuzzy tolerance was a red
herring — the loss happens in build123d's automatic clean()
(ShapeUpgrade_UnifySameDomain), which collapses a face crossed by a
curved surface's parametric seam. build123d's +/- run that clean
unguarded. Workaround on feature/color-partition-union:
_raw_bool (BRepAlgoAPI Cut/Fuse/Common without clean) + _cleaned()
(clean on a deepcopy — clean() mutates in place! — kept only when
volume is conserved). union()/group()'s fuse, difference(),
intersection(), and the partition internals all routed through it;
2D operands keep native operators. Speed: guarded pair is FASTER than
the plain operators (16.3 vs 22.9 ms on the sphere/cube case; 3.3 vs
4.8 ms on cubes) because build123d cleans unconditionally. Clarity
cost: ~60 lines of documented helpers in _common.py. 137 tests pass;
both sample models now export with correct volume (599.9646) and
reimport as real solids. Upstream report to build123d drafted for
user preview, not submitted.

**User**: Approved the report after asking for a workaround demo, STEP
exports showing the loss visually, and the seam-rotation experiment.
Then: file it with scripts and STEP files attached.

**Assistant**: Rotation experiment confirmed causation (degenerate cap
follows the seam: 0->+X, 90->+Y, 180->-X; 45deg/edge-aimed is correct).
Filed https://github.com/gumyr/build123d/issues/1428 with the results
table, rotation evidence, guarded_clean workaround (+ its stated
volume-only caveat), inline repro script, and a public gist holding the
script plus 4 STEP pairs (broken vs workaround):
https://gist.github.com/etjones/c68e633b07dc7184504b9b303a93555e

**User**: (After maintainer replied on #1428 that OCCT sphere-seam
problems are well known.) Rejected the split behavior where union()
succeeds but native `+` fails; wants the fix applied everywhere
scad123d/solid123d works, gated by a flag like
OCCT_SPHERE_SEAM_BUG_IS_UNFIXED so stock behavior returns easily when
upstream fixes it.

**Assistant**: Restructured into src/solid123d/occt_workarounds.py, the
single home of the workaround, gated by
OCCT_SPHERE_SEAM_BUG_IS_UNFIXED=True. Discovery: build123d's _bool_op
runs ShapeUpgrade_UnifySameDomain inline (not via Shape.clean), gated
by build123d's own SkipClean flag — so patching Shape.clean alone
missed the operators. install() (run on solid123d import) now patches
two chokepoints: Shape.clean -> volume-guarded clean, and
Shape._bool_op -> original op under SkipClean + guarded clean after.
Every path is now consistent: solid123d's union()/difference()/
intersection(), users' native +/-/& on our shapes, and all of scad123d
(patch activates on import). All scattered call-site helpers
(_raw_bool/_cut/_fuse/_intersect/_cleaned) deleted; _common.py and
booleans.py are back to native operators. Canary test asserts the
upstream bug still exists via uninstall(); it fails (with instructions)
the moment a build123d upgrade fixes #1428 — flip the flag then.
141 tests pass. scad123d's suite run against the branch: 248 pass; the
3 failures are its tests asserting the old fuse-with-first-color
overlap semantics that Route A replaces (to update on its next
solid123d bump).

**User**: Asked how interleaved the seam workaround is with the color
partition; wants separate PRs/branches. Also noted the seam failure is
reliable/predictable — rotating the seam out of the intersection avoids
it; "seams & booleans don't mix" as manual intuition.

**Assistant**: After the consolidation the diff split cleanly by file.
Restructured into a stack: PR #9 (fix/occt-seam-clean off main):
occt_workarounds.py + __init__ hook + canary/seam tests — 136 tests
pass standalone. PR #8 (feature/color-partition-union, force-updated,
base retargeted onto #9): _common.py partition + test_color.py + README
bullet — 141 tests. Both CIs green. Merge #9 first; GitHub retargets #8
to main automatically. Noted in PR #9 that the failure is deterministic
(cap follows the seam meridian; rotation avoids it) but the guard makes
that knowledge unnecessary for correctness.

**User**: Merge both PRs; no release yet.

**Assistant**: Merged #9 (seam workaround) to main. Deleting its branch
auto-closed stacked #8, which GitHub cannot reopen once the base ref is
gone — opened #10 from the same branch (color-only diff after the merge)
and merged it after green CI. main now has both; 141 tests pass on main.
Unreleased — next solid123d release will carry the customizer work
(already on main since 0.4.0? no: customizer shipped in 0.4.0; this
adds seam guard + color partition) and scad123d's 3 overlap-semantics
tests need updating at its version bump.
