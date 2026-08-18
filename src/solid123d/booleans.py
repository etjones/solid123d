"""OpenSCAD boolean operations: ``union()(a, b)``, ``difference()(a, b)``.

Note that because primitives are native build123d shapes, the algebra
operators also work directly: ``a + b`` (union), ``a - b`` (difference),
``a & b`` (intersection). SolidPython's ``a * b`` intersection operator
is NOT available — use ``a & b`` or ``intersection()(a, b)``.
"""

from collections.abc import Callable
from functools import reduce
from operator import and_, sub

from build123d import GeomType, Kind, Shape
from build123d import offset as _bd_offset
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Sphere

from ._common import flatten, group

Applier = Callable[..., Shape]

_ORIGIN_TOL = 1e-6


def _ball_radius(shape: Shape) -> float | None:
    """The radius if ``shape`` is a bare sphere or circle at the origin.

    A Minkowski sum with a ball is exactly an ``offset()``, which build123d
    performs natively. This only recognizes the untransformed primitive —
    matching how the idiom is actually written, ``minkowski()(A, sphere(r))``
    — not any shape that merely happens to be spherical.
    """
    solids = shape.solids()
    faces = shape.faces()

    if len(solids) == 1 and len(faces) == 1 and faces[0].geom_type == GeomType.SPHERE:
        adaptor = BRepAdaptor_Surface(faces[0].wrapped)
        if adaptor.GetType() != GeomAbs_Sphere:
            return None
        sphere = adaptor.Sphere()
        center = sphere.Location()
        if max(abs(center.X()), abs(center.Y()), abs(center.Z())) > _ORIGIN_TOL:
            return None
        return sphere.Radius()

    edges = shape.edges()
    if not solids and len(faces) == 1 and len(edges) == 1 and edges[0].geom_type == GeomType.CIRCLE:
        adaptor = BRepAdaptor_Curve(edges[0].wrapped)
        if adaptor.GetType() != GeomAbs_Circle:
            return None
        circle = adaptor.Circle()
        center = circle.Location()
        if max(abs(center.X()), abs(center.Y()), abs(center.Z())) > _ORIGIN_TOL:
            return None
        return circle.Radius()

    return None


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
        shapes = flatten(children)
        if not shapes:
            raise ValueError("minkowski() requires at least one shape")

        if len(shapes) == 2:
            for i, candidate in enumerate(shapes):
                radius = _ball_radius(candidate)
                if radius is None:
                    continue
                target = shapes[1 - i]
                try:
                    result = _bd_offset(target, amount=radius, kind=Kind.ARC)
                except Exception:
                    break
                if result is not None and result.is_valid:
                    return result
                break

        raise NotImplementedError(
            "minkowski() has no general build123d equivalent; the common "
            "case of rounding a shape, minkowski()(A, sphere(r)) or "
            "minkowski()(A, circle(r)), is computed exactly as offset(A, r) "
            "and works automatically. For anything else, use offset() or "
            "fillet/chamfer on the build123d object instead"
        )

    return apply
