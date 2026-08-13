"""solid123d: run SolidPython code on the build123d kernel.

Change ``from solid import ...`` to ``from solid123d import ...`` and the
same code produces native build123d shapes, which can be mixed freely
with regular build123d code and exported to STEP/STL.
"""

from build123d import Shape

from .booleans import difference, hull, intersection, minkowski, union
from .extrusions import linear_extrude, rotate_extrude
from .primitives import (
    circle,
    cube,
    cylinder,
    polygon,
    sphere,
    square,
    text,
)
from .render import scad_render, scad_render_to_file
from .transforms import (
    color,
    mirror,
    offset,
    resize,
    rotate,
    scale,
    translate,
)

# Typing aliases: SolidPython signatures like `-> OpenSCADObject` stay
# correct, since every solid123d function returns a build123d Shape.
OpenSCADObject = Shape
OpenSCADObjectPlus = Shape

__all__ = [
    "OpenSCADObject",
    "OpenSCADObjectPlus",
    "circle",
    "color",
    "cube",
    "cylinder",
    "difference",
    "hull",
    "intersection",
    "linear_extrude",
    "minkowski",
    "mirror",
    "offset",
    "polygon",
    "resize",
    "rotate",
    "rotate_extrude",
    "scad_render",
    "scad_render_to_file",
    "scale",
    "sphere",
    "square",
    "text",
    "translate",
    "union",
]
