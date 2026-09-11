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

**User**: Run the 0.5.0 release train and update scad123d's tests.

**Assistant**: solid123d 0.5.0: seam-guard workaround (gated,
process-wide, canary-tested) + color-partitioning union. Minor-version
bump because overlapping-colored-union semantics visibly change
(partition instead of fuse-with-first-color).

**User** (via scad123d): an oval prism from `hull()` of two lifted
cylinders lands in the wrong place in the STEP (CodeCAD 0586843_0).

**Assistant**: `_hull_of_cylinders` placed the stadium at whichever cap
face OCCT listed first and extruded along the placed face's normal; from
a top cap that goes up (z 16..28 instead of 4..16). Volume was right, so
the volume-only tests never caught it. Fix: `extrude(dir=dir0)` along the
shared axis; test now asserts the z-span. PR #14.

**User** (via scad123d): build the per-body color plan: region invariant,
color-aware difference/intersection, color() as a fill, own exporter with
optional group-by-color, hull/minkowski rule.

**Assistant**: Done on `feature/per-body-color`. `_common.py`: region
helpers (`world_leaves` composes ancestor Locations onto leaf copies,
`fill_color`, `assemble`, `checked`, `total_volume`, `baked`).
`booleans.py`: `difference()` cuts each region body and re-attaches its
color; `intersection()` applies the later-wins precedence pairwise; both
check volume against a plain boolean with every body passed as its own
argument -- a Compound of touching/overlapping solids is not a valid
single OCCT argument (the op "succeeds" and returns the input unchanged),
which is also what `difference()` on any colored model did before.
`hull()`/`minkowski()` warn and drop children's colors. `transforms.py`:
`color()` fills uncolored leaves (tree stays uncolored); `scale`/
`mirror`/`resize` map over baked world leaves, keeping tree and colors.
`export.py`: `region_bodies()` and `export_step(shape, path,
group_by_color=False)` build the XDE doc directly -- one colored product
per body, author's tree by default, per-color groups on request; single
solid exported as a free shape. `occt_workarounds`: the common-volume
bound is now group-wise (sum of args vs sum of tools). Tests:
test_regions.py (18), test_export.py (9); one old test updated to the
fill semantics; 183 pass.

**Assistant** (continued): a smoke test on a two-material lid caught
`union()` violating the agreed precedence: the shell measured 2384
instead of 2400 because a later *uncolored* cube took the overlap. That is
"later always wins", the option the project explicitly rejected in favour
of "an assigned color wins over uncolored material". Fixed by ordering the
partition sweep by priority -- (has a color, source index) ascending, each
body cut by everything that outranks it -- instead of by source position;
the output tree keeps the author's order. Two old tests encoded the
rejected rule and were rewritten, and the full contract table is now
pinned in test_regions.py (six rows plus volume conservation). Also
consolidated one `boolean()` helper in `_common` that passes every body as
its own OCCT argument, and fixed a local variable in `group()` that
shadowed the module-level `total_volume()`. 192 tests pass.

**User** (via scad123d): the tweezers STEP shows a flat rectangle
(CodeCAD 11838043_0, 6e10 against OpenSCAD's 7802).

**Assistant**: 6e10 is exactly 100000 x 100000 x 6 -- the whole helper
square of Oskar Linde's 2D `fillet()`, whose `inverse()` is
`square(1e5) - children()`. Measured the idiom step by step: the first
inversion came back at 1e10 + 38.5, i.e. *larger* than the square it was
cutting from. Cause: a boolean whose operand is a compound of bodies
rather than the bodies themselves. Demonstrated on a two-face sketch and a
1e5 square -- cut gave 1e10 + 38.5 (correct: 1e10 - 2632), fuse gave a
face of area 8e100, intersection double-counted the overlap; passing the
same faces as separate operands gave all three correctly. The same trap
found earlier for solids, except `boolean()` only decomposed `.solids()`,
so 2D slipped through and nothing caught it (the volume guard measures
volume, and 2D geometry has none).

Fix: `bodies_of()` decomposes a shape to solids, else faces, else itself;
`boolean()` and a new `fuse_bodies()` use it, `group()` fuses through it,
and difference/intersection route their uncoloured paths through it too
(`_intersect_plain` folds operand by operand, which keeps OpenSCAD's
semantics since OCCT's Common is `(union of args) OP (union of tools)`).
Side effect worth noting: the tweezers profile -- a circle joined by two
mirrored legs -- now unions to one merged face where it used to stay two,
so the idiom no longer produces a multi-face operand at all.

Tweezers now 7802.73 against OpenSCAD's 7802.51 (0.003%), `scad123d-diff`
agrees, and the render is a pair of tweezers rather than a plate. 14 new
tests; 206 pass in solid123d, 367 in scad123d.

**User** (via scad123d): look at `codecad-review-3/003-16362263_0-table-eq-wire_V2`
(1.9e7 against OpenSCAD's 88,521).

**Assistant**: `scad123d-diff` localized it to one inner `difference()`:
ours 66,668,695.19, OpenSCAD 65,168.47. That figure is *exactly* the
minuend -- a cone capped by a disk -- so the cut removed nothing at all.
Each of the five subtrahends removes 33-99% on its own, and folding all
five removes 99.9%; handing all five to one OCCT Cut returns the argument
untouched. Four tools cut correctly; adding the fifth (a second cone)
triggers it. No smaller combination reproduces it, and the plausibility
guard cannot see it, because a cut whose tools miss legitimately removes
nothing -- the Cut upper bound is the argument's own volume.

Fix: `cut_all()` keeps the one-pass N-ary cut (the optimisation that
stopped many-subtrahend models from crawling) and folds tool by tool only
when the fast path removed *exactly* nothing, adopting the fold only if it
removed something. A genuine miss therefore costs one wasted fold and the
same answer. Added `extent()` -- volume for 3D, area for 2D -- so the
check also covers 2D cuts. 10 new tests, including one that asserts the
raw N-ary path really does no-op on this geometry, so the regression test
stops silently passing if OCCT ever fixes it.

Model now 88,590.29 against 88,521.24 (0.08%), `scad123d-diff` agrees, and
the render matches OpenSCAD's. 216 pass in solid123d, 367 in scad123d.

**User**: Revert #18 and merge the mesh fix. Do you have a proposal, or
should we accept that CGAL and OCCT differ?

**Assistant**: Reverted #18, merged scad123d #30. Corrected an
overstatement first: of the three "regressions" I reported, only reversi
was one. The seal (9,568.86) and rpi_bracket (0.00) produce the same
values at the published 0.8.0, so their ledger rows were simply stale --
nothing has ever re-run an `ok` file, so the 56,000 passing rows are of
unknown age, and one of them records `ok` for a model that converts to
nothing.

On the question: divergence is acceptable for tessellation (bounded,
convergent, already documented) but not for wrong answers, which is what
all four of tonight's bugs were. Proposed asserting a semantic invariant
on our own output instead of chasing OpenSCAD's number.

**User**: Let's implement that invariant check.

**Assistant**: Done on `feature/cut-invariant`. A cut may not keep
material inside the shapes it cut with. `material_left_in_tools` samples
one interior point per result body (`interior_point`: centre first, then
points just inside faces, since a non-convex body's centre can fall
outside it) and classifies it against the tools; ON the boundary is not a
violation, as a cut leaves its result flush against its tool. Only on
violation does anything retry -- fuzzy at fractions of the model's
bounding-box diagonal, then a fold tool by tool -- and the first candidate
satisfying the invariant wins, else the original stands with a warning.

Cost: the check is ~0.45 ms, near-constant, so 23% of a trivial cut and
under 5% of a real one; eager candidate generation had made it 60% until
it was made lazy. Measured 40 previously-ok models bit-identical to main
at +1.0% total runtime -- the validation skipped before #18.

Fixes both saucers, the wire, and the seal (8,008.98, which neither #18
nor anything else recovered), while leaving reversi at 118.80 because its
plain cut satisfies the invariant so no fuzzy is applied. rpi_bracket
still converts to 0.00: a different defect, producing nothing rather than
keeping too much. 227 pass in solid123d, 373 in scad123d.

---

## The union invariant

A union joins material. It can never return more separate pieces than it
was given, and its pieces can never overlap. `fuse_bodies` now asserts
both and retries on violation, the same shape as `cut_all`.

Found by looking at the eight corpus models that convert to exactly zero
volume while OpenSCAD renders a real solid. Six of the eight were one
operation failing: OCCT's n-ary fuse. Measured at the subtree the
bisector blamed:

| operands | OCCT returned | correct |
|---|---|---|
| 13 sheared bars | 3 solids, 637.74 | 616.37 |
| 6 bodies | 14 solids, 20,393 | 28,072 |
| 7 bodies | 21 solids, -0.00 | 51,313 |
| 2 mesh polyhedra | 336 solids, -0.00 | 21.67 |
| 19 bodies | 2 solids, 0.00 | 3,905 |
| 2 bodies | 1 solid, 0.00 | 54,963 |

The existing bounds check in `occt_workarounds` sees none of the first
four, because the interval it tests -- largest input to sum of inputs --
is wide enough to hold every one of those answers. Counting bodies costs
nothing and catches three of them; an overlap test catches the bars,
where the count stayed legal.

Two things changed alongside. `bodies_overlap` samples several interior
points per body rather than one, because the centre of a body and the
centre of the body it half-covers can both land exactly on the other's
face, where a point is neither in nor out. And the bounds check's retry
now climbs a ladder of tolerances scaled to the operands' own size,
where it used to try a single fixed 1e-5 mm: the spike array needed
1e-4 of its diagonal, 0.013 mm, and returned exactly zero at everything
smaller. Some rungs make OCCT throw, so a rung that throws is skipped
rather than ending the ladder.

Results with this and the scad123d zero-scale rule, on the eight:
spikes 0 -> 53,979.84 (0.08% off), pool adapter 0 -> 51,107.86 (0.40%),
pruning saw 0 -> 1,583.37 (0.05%), coin calibration 0 -> 1,682.00
(exact), seed of life 0 -> 31,652.91 (1.54%, still a mismatch).
Snowflake stays at 0, and no tolerance from exact to 1e-3 of its
diagonal changes that; the helix is the same. Those two want OpenSCAD's
mesh for the subtree, not a tolerance.

---

## The union invariant, in two dimensions

`pieces_of` now answers with solids, or faces when there are none -- the
same distinction `extent` already draws -- so both halves of the union
invariant apply to 2D geometry. A sheet has no solids, so before this the
checks silently passed everything 2D.

`bodies_overlap` needed a containment test for faces (`Face.is_inside`)
and interior points that work on one: the centre, then points drawn from
each edge's middle toward it, which lands inside a crescent whose centre
falls in the bite.

Honest about the evidence: this is defensive. The model that looked like a
2D union failure -- a stack of 21 concentric circles reporting 27,479 of
summed area against OpenSCAD's 1,438 -- turned out to be a transform bug
instead. The circles sat at 21 different z heights in our build, so they
genuinely did not overlap and the union was right to leave them alone.
See the scad123d side for what actually caused it.

---

## A colored 2D union never merged

`group()` decides whether colored children overlap by comparing the fused
total against the naive sum. It measured with `total_volume`, and every
2D shape has volume 0, so "they share nothing" was trivially true for
every colored 2D union: the children came back stacked on each other,
never merged.

Found in `Butterdose2.scad`, one of the two genuine errors among the
fifteen worst mismatches. Its lid profile is a blue square unioned with
red lens pieces, and it reached `linear_extrude()` as three overlapping
faces of 24,552 where the region is 8,056. Extruded, that was 1,930,728
against OpenSCAD's 35,487.

`extent()` already answers this correctly -- volume for solids, area for
2D -- and using it makes the whole model convert at 35,527.23 against
35,486.57.

---

## text() was 28% too small, everywhere

OpenSCAD's `text()` size is the em square in model units. build123d's
`font_size` goes to OCCT, which measures a font the typographic way: 72
points to the inch against a 100-unit em. We passed one straight to the
other, so asking for 20 drew a glyph 14.35 tall where OpenSCAD draws
19.93 -- **28% short in each direction, 48% short in area** -- for every
string in the corpus.

Measured against OpenSCAD on two installed fonts, so it is the size
convention and not one font's metrics:

| font | OpenSCAD | before | after |
|---|---|---|---|
| Helvetica | 15.81 x 19.93, area 133.202 | 11.39 x 14.35 | 15.81 x 19.92, area 133.234 |
| Arial | 15.60 x 19.88, area 128.879 | 11.23 x 14.32 | 15.60 x 19.88, area 128.892 |

Within 0.02% of area on both.

How much this matters, from the corpus: **44.5% of the 3,000 remaining
mismatches use `text()`, against 5.5% of the 56,327 models that pass.**
Text-using models are eight times over-represented among the failures.
That is correlation rather than proof, but it is a strong hint that this
one conversion has been quietly costing a large share of them.

Found via `cookie_cutter.scad`, which it does *not* fix -- that model's
remaining error is in a `minkowski()` mesh fallback.

---

## And the font it falls back to

Chasing `cookie_cutter.scad` further: it asks for `font = "fontawesome"`,
and **neither tool can resolve that name** -- not even with Font Awesome
installed, since the family is really "Font Awesome 6 Free". Both fall
back, to different fonts, silently.

| | fallback | `"ï"` at size 20 |
|---|---|---|
| OpenSCAD | Liberation Sans, which it bundles | 46.925, box 7.55 x 19.03 |
| us, via OCCT | Arial | 49.347, box 7.61 x 20.01 |

5% apart in area and a visibly different glyph. `fallback_font_path()`
now prefers an installed Liberation Sans and otherwise the copy inside
OpenSCAD's own application bundle, and the same glyph comes out at 46.932
against OpenSCAD's 46.925.

Worth being clear about what this is not: it does not render Font Awesome
icons. Nothing can, when the name in the model matches no family either
tool can find. It makes us wrong in exactly the way OpenSCAD is wrong,
which is the only way those models can agree.

---

## Where the text goes

`build123d` has two alignment ideas and only one of them is OpenSCAD's.
`align` moves the finished bounding box; `text_align` positions text
within its own layout, which is where the pen and the baseline live. We
were passing OpenSCAD's halign and valign to `align`, so the *ink* landed
at the origin: `"H"` began at x=0 where OpenSCAD begins at 2.279, its
left side bearing, and `"Wg"` sat wholly above the axis where OpenSCAD
lets the g descend to -5.764.

Reading the manuals rather than guessing settled every case:

* **halign measures the layout box**, pen origin to advance, not the ink.
  That is why `left` leaves a bearing's worth of gap. `text_align` means
  the same thing, so the three map straight across.
* **OCCT's "bottom" is the baseline** of the last line, which is
  OpenSCAD's baseline -- no adjustment needed for the default.
* **top, bottom and center are measured on the ink** ("the tallest
  character", "the lowest-reaching character", "the centre of the
  bounding box"), so they are a shift off the baseline. OCCT's own TOP
  and CENTER follow the font's line metrics instead, which is a different
  answer.

All twelve halign x valign combinations now match OpenSCAD's own render
to within 0.009 of a millimetre, and the table of its measurements is in
the tests.

---

## Naming what OCCT will not do

`bigme-highbreak-pro.scad` cuts a plate by two slabs and comes back
inside out: -28,194 where OpenSCAD says 8,462. Both operands match
OpenSCAD to a third of a percent, both report `is_valid`, and no repair
touches it -- not the fuzzy ladder from 1e-7 to 1e-3 of the diagonal, not
folding tool by tool, not pre-fusing the tools, not `SetGlue` in either
mode, not `ShapeFix`, not `UnifySameDomain`.

OCCT's own `BOPAlgo_ArgumentAnalyzer` says why: **both operands intersect
themselves**, and carry edges below tolerance. BRepCheck does not test for
self-intersection, so the shapes call themselves valid right up to the
point where every boolean on them fails. OCCT's booleans are only defined
on arguments that do not self-intersect, so the kernel is behaving as
specified on input it was never promised.

`why_occt_struggled()` now asks it and puts the answer in the warning. It
does **not** fix the model; it stops a silent wrong answer being reported
as a plain volume disagreement.

**Gated so nothing healthy pays for it.** The analyzer is a full
intersection pass, as expensive as the boolean itself, so it runs only
after an invariant has already failed *and* no repair has helped -- never
as a precondition. Measured: across 25 models that convert correctly, it
ran **zero** times. A control on ordinary geometry -- a cube, a cube
minus a cylinder, a union of two cubes, a cylinder, a sphere -- reports
nothing, so the finding on this model is real rather than noise.
