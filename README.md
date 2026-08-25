# solid123d

[![CI](https://github.com/etjones/solid123d/actions/workflows/ci.yml/badge.svg)](https://github.com/etjones/solid123d/actions/workflows/ci.yml)

A bridge that runs [SolidPython](https://github.com/SolidCode/SolidPython)
(OpenSCAD-style) code on the [build123d](https://build123d.readthedocs.io/)
BRep kernel. Change one import and existing code produces native build123d
shapes instead of OpenSCAD source.

```python
# before
from solid import translate, cube, scad_render_to_file

# after
from solid123d import translate, cube, scad_render_to_file

c = translate([10, 0, 0])(cube(10, center=True))
scad_render_to_file(c, filename="c.scad")  # writes c.step (real BRep geometry)
```

Every object returned is a plain build123d `Shape`, so bridged code mixes
freely with native build123d — the intended migration path:

```python
from build123d import fillet
from solid123d import cube

part = cube(20, center=True)
part = fillet(part.edges(), radius=2)  # native build123d from here on
```

## Supported

- **Primitives**: `cube`, `sphere`, `cylinder` (incl. `r1`/`r2` cones,
  `d`/`d1`/`d2`), `square`, `circle`, `polygon` (incl. `paths` holes), `text`
- **Font resolution**: `text(font=...)` matches fonts by family name the way
  fontconfig/OpenSCAD does (incl. `"Family:style=Style"` syntax), by scanning
  system font directories with fontTools and handing build123d the resolved
  file path. This fixes fonts with nonstandard subfamilies (e.g.
  `"Academy Engraved LET"`, whose subfamily "Plain" makes OCCT's own lookup
  fall back to Arial).
- **Transforms** (callable style, `translate(v)(obj, ...)`): `translate`,
  `rotate` (vector, scalar, and axis-angle forms with OpenSCAD ordering),
  `scale`, `mirror`, `resize`, `color`, `offset`
- **Booleans**: `union()`, `difference()`, `intersection()` — plus native
  operators `a + b`, `a - b`, `a & b`
- **`minkowski()` with a ball** — `minkowski()(A, sphere(r))` /
  `minkowski()(A, circle(r))`, by far the most common use of `minkowski()`
  (rounding a shape), is computed exactly as `offset(A, r)` — including a
  ball tessellated as an explicit `polyhedron()`, the way BOSL2 builds its
  rounding kernels. Exact BRep geometry, not an approximation.
- **`hull()`, for every case with a closed-form answer** — all computed as
  exact BRep geometry: equal-radius spheres in any arrangement (including
  the collinear capsule/slot idiom), equal-radius parallel cylinders
  sharing a span (the "rounded box from corner posts" idiom), exactly two
  spheres of *any* radii (two spherical caps sewn to their external
  tangent cone; overlap and containment handled), exactly two 2D circles
  (the keyhole/slot idiom), and any collection of purely flat-faced
  children (cubes, `polyhedron()`s, extruded polygons — the hull is
  exactly the convex hull of their vertices). See Known differences for
  what still raises.
- **`polyhedron(points, faces)`** — explicit point/face solids, with
  OpenSCAD's tolerance for either winding direction.
- **`color()` that survives into STEP export** — colored parts that don't
  share volume (disjoint, or touching, like a part sitting in a cavity cut
  for it) stay separate bodies, each keeping its own color, and every part
  is labeled with the color name you wrote (`color("SteelBlue")` →
  `steelblue`, numeric colors get the CSS name or hex), so multi-material
  models open in slicers and CAD viewers with real per-part colors and
  recognizable names instead of one gray `COMPOUND`. Genuinely overlapping
  parts are partitioned instead of fused: later children claim contested
  volume, and each earlier `color()` region keeps its color wherever no
  later sibling claims the space — `union(color("red") sphere, cube)`
  yields a red sphere-minus-cube body beside the uncolored cube.
  Uncolored models are entirely unaffected.
- **2D → 3D**: `linear_extrude` (incl. `center`, `scale`; no `twist`),
  `rotate_extrude` (incl. partial `angle`)
- **Export**: `scad_render_to_file` writes `.step`/`.stl`; a `.scad`
  filename is rewritten to `.step` with a warning
- `solid123d.utils`: `up`, `down`, `left`, `right`, `forward`, `back`
- **Typing aliases**: `OpenSCADObject` and `OpenSCADObjectPlus` are
  aliases of `build123d.Shape`, so existing
  annotations like `def some_obj() -> OpenSCADObject:` remain correct
## Known differences

- `a * b` intersection is not overloaded; use `a & b` or `intersection()(a, b)`.
- `hull()` raises `NotImplementedError` outside the closed-form cases
  above — notably three or more spheres of unequal radii (their hull needs
  planes tangent to three spheres at once, a genuinely harder object) and
  mixtures of curved children. Model those explicitly (`loft`/`sweep`), or
  import through [scad123d](https://github.com/etjones/scad123d), which
  renders unsupported hulls as meshes via OpenSCAD.
- `minkowski()` raises `NotImplementedError` except for the ball cases
  above; general Minkowski sums have no BRep equivalent. Use `offset()` or
  fillet/chamfer on the build123d object instead.
- `linear_extrude(twist=...)` raises `NotImplementedError`.
- `$fn`/`segments` arguments are accepted and ignored — BRep curves are exact.
- `scad_render()` (source string) raises `NotImplementedError`.
- OpenSCAD modifiers (`#`, `%`, `!`) and `import()`/`surface()`/`projection()`
  are not implemented.

## Development

```bash
just test    # or: uv run pytest
```
