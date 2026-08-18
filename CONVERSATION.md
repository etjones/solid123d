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
