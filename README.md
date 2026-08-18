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
part = fillet(part.edges(), radius=2)   # native build123d from here on
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
- **`minkowski()` with a sphere or circle** — `minkowski()(A, sphere(r))` /
  `minkowski()(A, circle(r))`, by far the most common use of `minkowski()`
  (rounding a shape), is computed exactly as `offset(A, r)`. This is exact
  BRep geometry, not an approximation — see Known differences below for what
  is still unsupported.
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
- `hull()` always raises `NotImplementedError` (no BRep convex hull operator);
  in build123d, a hull is usually a `loft` or an explicitly modeled shape.
- `minkowski()` raises `NotImplementedError` except for the sphere/circle case
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
