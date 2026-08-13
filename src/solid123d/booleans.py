"""OpenSCAD boolean operations: ``union()(a, b)``, ``difference()(a, b)``.

Note that because primitives are native build123d shapes, the algebra
operators also work directly: ``a + b`` (union), ``a - b`` (difference),
``a & b`` (intersection). SolidPython's ``a * b`` intersection operator
is NOT available — use ``a & b`` or ``intersection()(a, b)``.
"""

from collections.abc import Callable
from functools import reduce
from operator import and_, sub

from build123d import Shape

from ._common import flatten, group

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
        raise NotImplementedError(
            "hull() has no direct build123d equivalent; model the shape "
            "explicitly (e.g. loft/sweep) instead"
        )

    return apply


def minkowski() -> Applier:
    def apply(*children: Shape) -> Shape:
        raise NotImplementedError(
            "minkowski() has no build123d equivalent; use offset() or "
            "fillet/chamfer on the build123d object instead"
        )

    return apply
