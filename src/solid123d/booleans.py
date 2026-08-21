"""OpenSCAD boolean operations: ``union()(a, b)``, ``difference()(a, b)``.

Note that because primitives are native build123d shapes, the algebra
operators also work directly: ``a + b`` (union), ``a - b`` (difference),
``a & b`` (intersection). SolidPython's ``a * b`` intersection operator
is NOT available — use ``a & b`` or ``intersection()(a, b)``.

``hull()`` and ``minkowski()`` evaluate every case that has a closed-form
BRep answer (see hull.py and minkowski.py) and raise NotImplementedError
for the rest — build123d has no general convex-hull or Minkowski operator,
and a faceted approximation would defeat the point of a BRep kernel.
"""

from collections.abc import Callable
from functools import reduce
from operator import and_, sub

from build123d import Shape

from ._common import flatten, group
from .hull import analytic_hull
from .minkowski import analytic_minkowski

Applier = Callable[..., Shape]


def union() -> Applier:
    def apply(*children: Shape) -> Shape:
        return group(children)

    return apply


def difference() -> Applier:
    def apply(*children: Shape) -> Shape:
        shapes = flatten(children)
        if not shapes:
            raise ValueError("difference() requires at least one shape")
        return reduce(sub, shapes)

    return apply


def intersection() -> Applier:
    def apply(*children: Shape) -> Shape:
        shapes = flatten(children)
        if not shapes:
            raise ValueError("intersection() requires at least one shape")
        return reduce(and_, shapes)

    return apply


def hull() -> Applier:
    def apply(*children: Shape) -> Shape:
        shapes = flatten(children)
        if not shapes:
            raise ValueError("hull() requires at least one shape")
        result = analytic_hull(shapes)
        if result is not None:
            return result
        raise NotImplementedError(
            "hull() of these children has no closed-form BRep answer. "
            "Supported exactly: equal-radius spheres (any count/positions), "
            "equal-radius parallel cylinders sharing one span, exactly two "
            "spheres of any radii, exactly two 2D circles, and any "
            "collection of purely flat-faced (polyhedral) children. "
            "Notably NOT supported: three or more spheres of unequal radii "
            "(needs tritangent planes / power-diagram combinatorics) and "
            "mixed curved children -- model those explicitly (loft/sweep), "
            "or import through scad123d, which renders unsupported hulls "
            "as meshes via OpenSCAD"
        )

    return apply


def minkowski() -> Applier:
    def apply(*children: Shape) -> Shape:
        shapes = flatten(children)
        if not shapes:
            raise ValueError("minkowski() requires at least one shape")
        result = analytic_minkowski(shapes)
        if result is not None:
            return result
        raise NotImplementedError(
            "minkowski() has no general build123d equivalent; the common "
            "case of rounding a shape, minkowski()(A, sphere(r)) or "
            "minkowski()(A, circle(r)) -- including a sphere tessellated as "
            "a polyhedron, as BOSL2 rounding kernels are -- is computed "
            "exactly as offset(A, r) and works automatically. For anything "
            "else, use offset() or fillet/chamfer on the build123d object "
            "instead"
        )

    return apply
