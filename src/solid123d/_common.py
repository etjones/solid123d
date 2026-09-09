"""Shared helpers for the SolidPython -> build123d bridge.

Boolean operations here use build123d's native operators. Their
seam-related geometry loss (gumyr/build123d#1428) is handled in one
place -- the gated Shape.clean patch in occt_workarounds.py -- so
solid123d's union()/difference(), a user's own ``a + b``, and scad123d
all behave identically.
"""

import math
import warnings
from collections.abc import Callable, Iterable, Iterator, Sequence

import webcolors
from build123d import Color, Compound, Location, Shape, Solid, Vector
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_COMPOUND, TopAbs_IN, TopAbs_SOLID
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS_Shape

Vec3 = tuple[float, float, float]

# A region body smaller than this is boolean dust, not material.
VOLUME_EPS = 1e-9

# Tolerance for classifying a point against a solid, and the fractions of
# a model's bounding-box diagonal tried as OCCT fuzzy values when a cut
# has to be retried. Fractions rather than distances: OCCT asks for a
# value measured against the geometry in question, and a constant means
# something different on a 400 mm assembly than on a 4 mm part.
POINT_TOL = 1e-7
FUZZ_FRACTIONS = (1e-7, 1e-5)


def vec3(v: float | Sequence[float], default: float = 0.0) -> Vec3:
    """Expand an OpenSCAD-style scalar or vector into an (x, y, z) tuple."""
    if isinstance(v, (int, float)):
        return (float(v), float(v), float(v))
    vals = [float(x) for x in v]
    while len(vals) < 3:
        vals.append(default)
    return (vals[0], vals[1], vals[2])


def flatten(children: Iterable[object]) -> list[Shape]:
    """Flatten nested lists/tuples of shapes (SolidPython allows both
    ``op()(a, b)`` and ``op()([a, b])``)."""
    out: list[Shape] = []
    for child in children:
        if isinstance(child, (list, tuple)):
            out.extend(flatten(child))
        elif child is not None:
            out.append(child)
    return out


def color_label(rgba: Sequence[float]) -> str:
    """A human-readable name for an rgba value: the exact CSS color name
    when there is one, otherwise the hex string. Used to label shapes so
    parts show up in STEP viewers and slicers under a recognizable name
    instead of OCCT's auto-generated ``COMPOUND``/``SOLID``.
    """
    r, g, b = (round(float(v) * 255) for v in list(rgba)[:3])
    try:
        return webcolors.rgb_to_name((r, g, b))
    except ValueError:
        return f"#{r:02x}{g:02x}{b:02x}"


def _carries_color(shape: Shape) -> bool:
    """Does this shape, or any shape nested under it, have an explicit color?

    Checks the private ``_color`` rather than the ``color`` property: the
    property walks *up* through parents and caches what it finds, so it
    reports inherited color, not authored color -- and it's authored color
    (an explicit ``color()`` call) that signals "these are distinct
    parts". Descends through ``children`` because a nested disjoint colored
    group arrives here as a Compound whose own color is unset but whose
    children carry theirs.
    """
    if shape._color is not None:
        return True
    return any(_carries_color(child) for child in shape.children)


def group(children: Iterable[object]) -> Shape:
    """Combine children the way an OpenSCAD block does: implicit union.

    OpenSCAD refuses to mix 2D and 3D in one group and warns; adding a Face
    to a Solid in build123d silently degenerates instead, so filter
    explicitly and keep the 3D geometry.
    """
    shapes = flatten(children)
    if not shapes:
        raise ValueError("expected at least one shape")
    solid = [s for s in shapes if s.solids()]
    if solid and len(solid) != len(shapes):
        warnings.warn(
            "solid123d: a group mixes 2D and 3D children, which OpenSCAD "
            "does not support; the 2D children were dropped",
            stacklevel=3,
        )
        shapes = solid
    if len(shapes) == 1:
        return shapes[0]

    # One N-ary OCCT fuse, not a pairwise reduce: pairwise re-processes
    # the ever-growing accumulated result at every step, which is
    # quadratic once curved faces stop merging away (200 overlapping
    # cylinders: 19.5 s pairwise, 1.1 s in one operation), and every
    # timeout in the CodeCAD corpus runs was in that loop.
    fused = fuse_bodies(shapes)

    # Everything below exists only to keep authored color() information
    # alive; a group with no colors anywhere gets the plain fuse -- and
    # skips the mass-property computations, which OCCT reruns from scratch
    # on every access (nothing is cached).
    if not any(_carries_color(s) for s in shapes):
        return fused

    # A real boolean fuse can't tell us which color survives once it's
    # merged overlapping material away -- confirmed directly, it doesn't
    # even keep the first child's color, the result comes back with none.
    # But a fuse is only *necessary* when material actually merged, and
    # volume tells us exactly that: a union's volume equals the naive sum
    # of its children's volumes if and only if the children share zero
    # volume. In that case -- disjoint parts, or parts touching along a
    # shared surface (a part sitting exactly in a cavity cut for it) --
    # return a Compound of the children instead: same total volume, and
    # grouping (unlike fusing) doesn't touch each child's own
    # color/label/material. The colors are evidence the author means these
    # as distinct parts (a multi-material print, an assembly), so touching
    # parts deliberately stay separate bodies rather than getting
    # OpenSCAD's merged-solid union semantics -- that merge is exactly what
    # would destroy the colors.
    #
    # `children=` (not a flat `Compound(shapes)`) matters: it's what makes
    # this an assembly the STEP exporter walks node by node, applying each
    # child's own .color -- a flat Compound with no parent/child tree is
    # treated as one leaf and gets a single color splashed across every
    # solid inside it instead.
    naive_total = sum(total_volume(s) for s in shapes)
    if math.isclose(total_volume(fused), naive_total, rel_tol=1e-9, abs_tol=1e-9):
        return Compound(children=list(shapes))

    # Real overlap: partition instead of fusing. Later children claim
    # contested volume; each earlier child keeps its color on whatever
    # part of it nothing later covers. union(color("red") sphere, cube)
    # thus yields a red sphere-minus-cube body plus the uncolored cube --
    # same total volume as the fuse, but the colors survive.
    return _partitioned_union(shapes, fused)


def _rgba(shape: Shape) -> tuple | None:
    """The color a partitioned piece should carry, as a comparable key."""
    return tuple(shape.color) if shape.color is not None else None


def _color_leaves(shapes: Iterable[Shape]) -> list[Shape]:
    """Expand colorless Compounds whose children carry authored colors,
    so partitioning sees each colored body -- a nested disjoint colored
    group arrives as such a Compound."""
    out: list[Shape] = []
    for shape in shapes:
        if shape._color is None and shape.children and _carries_color(shape):
            out.extend(_color_leaves(list(shape.children)))
        else:
            out.append(shape)
    return out


def _recolored(shape: Shape, rgba: tuple | None, label: str) -> Shape:
    """Booleans drop color and label; restore a piece's own."""
    if rgba is not None:
        shape.color = Color(*rgba)
        shape.label = label or color_label(rgba)
    elif label:
        shape.label = label
    return shape


def _partitioned_union(shapes: list[Shape], fused: Shape) -> Shape:
    """Union overlapping children as touching bodies, colors intact.

    Precedence, as the project settled it: an assigned color wins over
    uncolored material, and between two assigned colors the later operand
    wins. It affects only the contested material -- never the rest of
    either body -- so each body keeps its color on everything that no
    higher-priority body claims. A red sphere therefore stays whole under
    a later *uncolored* cube, while a later *blue* cube would take the
    shared material.

    Runs of one color that nothing else separates are fused first, so a
    plain OpenSCAD idiom (a union of many uncolored or identically colored
    parts) still yields one merged solid per color. If partitioning ever
    loses material, the plain fuse is returned instead: correct geometry
    beats color fidelity, and the substitution is announced, never silent.
    """
    leaves = _color_leaves(shapes)
    # Ascending priority: uncolored bodies first (in source order), then
    # colored ones (in source order). The sweep below runs from the top
    # down, so each body is cut by everything that outranks it.
    ordered = sorted(
        enumerate(leaves), key=lambda pair: (_rgba(pair[1]) is not None, pair[0])
    )

    runs: list[tuple[int, Shape]] = []
    for index, shape in ordered:
        if runs and _rgba(runs[-1][1]) == _rgba(shape):
            first, prev = runs[-1]
            runs[-1] = (first, _recolored(prev + shape, _rgba(prev), prev.label))
        else:
            runs.append((index, shape))
    if len(runs) == 1:
        return runs[0][1]

    kept: list[tuple[int, Shape]] = []
    higher: list[Shape] = []
    for index, shape in reversed(runs):
        piece = boolean([shape], higher, BRepAlgoAPI_Cut()) if higher else shape
        if total_volume(piece) > VOLUME_EPS:
            kept.append((index, _recolored(piece, _rgba(shape), shape.label)))
        higher.append(shape)
    # Ownership followed priority; the tree keeps the author's order.
    bodies = [shape for _, shape in sorted(kept, key=lambda pair: pair[0])]
    return checked(bodies, fused, "union")


def bodies_of(shape: Shape) -> list[Shape]:
    """A shape's constituent bodies, for use as boolean operands.

    One of four OCCT workarounds; ``occt_workarounds`` carries the map of
    all of them, including the two monkeypatches no call site reveals.

    OCCT mishandles a compound of touching or overlapping bodies passed as
    one boolean operand: the operation reports success and returns
    nonsense. For solids a cut can come back *larger* than its argument;
    for faces a fuse of a two-face sketch with a square returned a face of
    area 8e100. Passing the bodies separately is correct in both cases.

    Solids for 3D geometry, faces for 2D. A compound holding both is not
    produced here -- group() filters mixed 2D/3D children with a warning --
    so solids winning is safe.
    """
    return shape.solids() or shape.faces() or [shape]


def _operands(shapes: Iterable[Shape]) -> list[Shape]:
    return [body for shape in shapes for body in bodies_of(shape)]


def boolean(args: list[Shape], tools: list[Shape], operation) -> Shape:
    """A boolean with every body passed as its own operand.

    OCCT computes ``(union of args) OP (union of tools)``, so decomposing
    both sides is exactly equivalent to the operation on the compounds --
    except that it actually works. See ``bodies_of``.
    """
    flat_args = _operands(args)
    flat_tools = _operands(tools)
    if not flat_args:
        raise ValueError("a boolean needs at least one argument")
    if not flat_tools:
        return assemble(flat_args)
    return flat_args[0]._bool_op(flat_args, flat_tools, operation)


def fuse_bodies(shapes: list[Shape]) -> Shape:
    """The union of *shapes*, every body its own operand.

    A plain ``shapes[0].fuse(*shapes[1:])`` passes each child whole, so a
    child that is a multi-face sketch or multi-solid compound triggers the
    defect in ``bodies_of``.
    """
    bodies = _operands(shapes)
    if len(bodies) == 1:
        return bodies[0]
    return bodies[0]._bool_op([bodies[0]], bodies[1:], BRepAlgoAPI_Fuse())


def extent(shape: Shape) -> float:
    """The quantity a boolean must not silently leave unchanged: volume for
    3D geometry, area for 2D."""
    solids = shape.solids()
    if solids:
        return sum(abs(solid.volume) for solid in solids)
    return sum(abs(face.area) for face in shape.faces())


def _inside(solid: TopoDS_Shape, point: Vector) -> bool:
    """Is *point* strictly inside *solid*? ON the boundary does not count:
    a cut leaves its result flush against the tool it cut with, and that is
    the correct answer, not a violation."""
    classifier = BRepClass3d_SolidClassifier(
        solid, gp_Pnt(point.X, point.Y, point.Z), POINT_TOL
    )
    return classifier.State() == TopAbs_IN


def _interior_candidates(solid: Shape) -> Iterator[Vector]:
    """Points that might lie inside *solid*, cheapest first and computed
    only as far as they are needed -- the centre serves for almost every
    body, and eagerly preparing the rest cost more than the whole check."""
    yield solid.center()
    step = solid.bounding_box().diagonal * 1e-3
    for face in solid.faces():
        try:
            middle = face.center()
            yield middle - Vector(face.normal_at(middle)) * step
        except Exception:  # noqa: BLE001, S112 - no usable normal here; try the next face
            continue


def interior_point(solid: Shape, limit: int = 8) -> Vector | None:
    """A point strictly inside *solid*, or None if none was found.

    The centre of a non-convex body can fall outside it, so a few points
    just inside its faces are tried next. None means "could not tell",
    never "outside": a caller must not read it as a verdict.
    """
    for tried, point in enumerate(_interior_candidates(solid)):
        if tried >= limit:
            return None
        if _inside(solid.wrapped, point):
            return point
    return None


def material_left_in_tools(result: Shape, tools: list[Shape]) -> bool:
    """Does *result* still hold material inside one of the *tools*?

    The invariant a cut must satisfy, and the reason it is worth checking:
    it is a statement about the answer, not about how the kernel reached
    it, so it needs no reference render and no tolerance to compare
    against. Every way OCCT has been seen to get a cut wrong -- keeping
    the half of a sphere a box covered, handing back the whole minuend --
    violates it, and the plausibility guard in ``occt_workarounds`` cannot,
    because the most a cut may remove is everything, so its upper bound is
    the argument's own volume.

    Sampling one interior point per body detects a body wholly inside a
    tool, which is what those failures produce. It is a detector, not a
    proof: a body with only a lobe inside a tool can pass.
    """
    solids = [solid.wrapped for tool in tools for solid in (tool.solids() or [tool])]
    if not solids:
        return False
    for body in result.solids():
        point = interior_point(body)
        if point is None:
            continue
        if any(_inside(solid, point) for solid in solids):
            return True
    return False


def _repairs(
    args: list[Shape], tools: list[Shape]
) -> Iterator[tuple[str, Callable[[], Shape]]]:
    """Ways to retry a cut whose result kept material it should have lost,
    cheapest first.

    The fuzzy values are fractions of the model's own size, not fixed
    distances. OCCT's guidance is to measure the gap being bridged and
    pass slightly more than that; a constant cannot do that, and a
    constant 1e-5 is what regressed a model of small meshed hulls while
    helping a 110 mm sphere. Scaling keeps the same *meaning* at any size.
    """
    diagonal = max(
        (arg.bounding_box().diagonal for arg in args),
        default=1.0,
    )
    for fraction in FUZZ_FRACTIONS:
        fuzz = diagonal * fraction
        yield f"fuzzy {fuzz:.3g}", lambda f=fuzz: _cut(args, tools, fuzz=f)
    if len(tools) > 1:
        yield "one tool at a time", lambda: _folded(args, tools)


def _cut(args: list[Shape], tools: list[Shape], fuzz: float | None = None) -> Shape:
    operation = BRepAlgoAPI_Cut()
    if fuzz is not None:
        operation.SetFuzzyValue(fuzz)
    return boolean(args, tools, operation)


def _folded(args: list[Shape], tools: list[Shape]) -> Shape:
    result = args
    for tool in tools:
        result = [_cut(result, [tool])]
    return result[0]


def cut_all(args: list[Shape], tools: list[Shape]) -> Shape:
    """Cut by every tool, checking that the result kept nothing it should
    have removed, and retrying if it did.

    One of four OCCT workarounds; see ``occt_workarounds`` for the map.

    The single N-ary Cut comes first because it is much cheaper than a fold
    -- one pass over the argument instead of one per tool -- and that is
    what keeps a model with many subtrahends from crawling. Then
    ``material_left_in_tools`` asks whether the answer is actually a cut.
    Only if it is not does anything else run: a fuzzy retry at a couple of
    fractions of the model's size, then a fold tool by tool. The first
    candidate that satisfies the invariant wins.

    If none does, the original stands and a warning says so, so a cut we
    cannot verify behaves exactly as it did before this check existed.
    """
    at_once = _cut(args, tools)
    if not material_left_in_tools(at_once, tools):
        return at_once

    for description, attempt in _repairs(args, tools):
        candidate = attempt()
        if not material_left_in_tools(candidate, tools):
            return candidate
        del description

    warnings.warn(
        "solid123d: this cut kept material inside the shapes it was cutting "
        "with, and neither a fuzzy retry nor cutting one tool at a time "
        "fixed it; the result is probably wrong",
        stacklevel=4,
    )
    return at_once


def own_rgba(shape: Shape) -> tuple | None:
    """The color set on this very shape, ignoring inheritance."""
    return tuple(shape._color) if shape._color is not None else None


def total_volume(shape: Shape) -> float:
    """Volume of every solid under *shape*. Not ``shape.volume``: build123d's
    ``Compound.volume`` sums only the compound's direct Solid children, so
    a nested tree undercounts."""
    return sum(s.volume for s in shape.solids())


def world_leaves(shape: Shape) -> list[Shape]:
    """The leaf bodies of *shape*'s tree, each a copy placed in world
    coordinates with its resolved color and label.

    A moved Compound carries the move on itself; its children stay in the
    frame they were built in. Booleans against other shapes need world
    coordinates, so ancestor locations are composed onto each leaf here.
    """
    out: list[Shape] = []

    def walk(node: Shape, acc: Location) -> None:
        if node.children:
            here = acc * node.location
            for child in node.children:
                walk(child, here)
            return
        leaf = node.moved(acc)
        out.append(_recolored(leaf, _rgba(node), node.label))

    walk(shape, Location())
    return out


def fill_color(shape: Shape, color: Color, label: str) -> Shape:
    """Give *color* to every leaf body that has none. Explicit inner
    colors survive; the tree itself stays uncolored."""
    if shape.children:
        for child in shape.children:
            fill_color(child, color, label)
        if not shape.label:
            shape.label = label
        return shape
    if shape._color is None:
        shape.color = color
        if not shape.label:
            shape.label = label
    return shape


def assemble(bodies: list[Shape], label: str = "") -> Shape:
    """One body is itself; several become a flat tree of separate bodies."""
    if len(bodies) == 1:
        return bodies[0]
    result = Compound(children=bodies)
    if label:
        result.label = label
    return result


def checked(bodies: list[Shape], plain: Shape, operation: str) -> Shape:
    """The color-preserving result of *operation*, or the plain boolean
    result when the pieces do not add up to it: correct geometry beats
    color fidelity, and the substitution is announced, never silent."""
    if not bodies:
        return plain
    result = assemble(bodies)
    if not math.isclose(
        total_volume(result), total_volume(plain), rel_tol=1e-6, abs_tol=VOLUME_EPS
    ):
        warnings.warn(
            f"solid123d: color-preserving {operation} lost volume to a boolean "
            "glitch; returning the plain result without colors",
            stacklevel=4,
        )
        return plain
    return result


def baked_topods(shape: TopoDS_Shape) -> TopoDS_Shape:
    """The shape with its Location applied to the geometry itself.

    build123d's scale() leaves a shape's Location alone, so a moved body
    would scale about the wrong point; OCCT's STEP writer cannot attach
    layers to a located shape. A placed copy has neither problem."""
    loc = shape.Location()
    if loc.IsIdentity():
        return shape
    return BRepBuilderAPI_Transform(
        shape.Located(TopLoc_Location()), loc.Transformation(), True
    ).Shape()


def baked(shape: Shape) -> Shape:
    """*shape* as a copy whose geometry carries its placement."""
    if shape.wrapped is None or shape.wrapped.Location().IsIdentity():
        return shape
    placed = baked_topods(shape.wrapped)
    kind = placed.ShapeType()
    if kind == TopAbs_SOLID:
        out: Shape = Solid(placed)
    elif kind == TopAbs_COMPOUND:
        out = Compound(placed)
    else:
        out = Shape.cast(placed)
    return _recolored(out, own_rgba(shape) or _rgba(shape), shape.label)
