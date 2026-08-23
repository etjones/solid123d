"""Analytic hull() and minkowski(): every case with a closed-form BRep
answer evaluates exactly; everything else raises NotImplementedError.

The geometry engines are shared with scad123d (which grew them first,
verified differentially against OpenSCAD's own output there); these tests
pin the solid123d-facing behavior and the closed forms.
"""

import math

import pytest
from build123d import GeomType

import solid123d as s


def _steiner(volume: float, area: float, edges: list[tuple[float, float]], r: float) -> float:
    return (
        volume
        + area * r
        + r * r / 2 * sum(length * angle for length, angle in edges)
        + (4 / 3) * math.pi * r**3
    )


def _pair_hull_volume(ra: float, rb: float, d: float) -> float:
    sin_a = (rb - ra) / d
    cos_a = math.sqrt(1 - sin_a**2)
    h1, h2 = ra * (1 - sin_a), rb * (1 + sin_a)
    rho1, rho2 = ra * cos_a, rb * cos_a
    length = d * cos_a**2
    return (
        math.pi * h1 * h1 * (3 * ra - h1) / 3
        + math.pi * length / 3 * (rho1**2 + rho1 * rho2 + rho2**2)
        + math.pi * h2 * h2 * (3 * rb - h2) / 3
    )


class TestHullEqualSpheres:
    def test_two_spheres_make_a_capsule(self):
        shape = s.hull()(s.sphere(3), s.translate([10, 0, 0])(s.sphere(3)))
        assert shape.volume == pytest.approx(
            math.pi * 9 * 10 + (4 / 3) * math.pi * 27, rel=1e-9
        )

    def test_eight_corner_spheres_match_steiner(self):
        a, b, c, r = 20.0, 15.0, 10.0, 3.0
        corners = [
            s.translate([x, y, z])(s.sphere(r))
            for x in (0, a)
            for y in (0, b)
            for z in (0, c)
        ]
        shape = s.hull()(*corners)
        edges = [(a, math.pi / 2)] * 4 + [(b, math.pi / 2)] * 4 + [(c, math.pi / 2)] * 4
        expected = _steiner(a * b * c, 2 * (a * b + b * c + c * a), edges, r)
        assert shape.volume == pytest.approx(expected, rel=1e-9)


class TestHullSpherePair:
    def test_unequal_pair_matches_the_closed_form(self):
        shape = s.hull()(s.sphere(3), s.translate([14, 0, 0])(s.sphere(5)))
        assert shape.volume == pytest.approx(_pair_hull_volume(3, 5, 14), rel=1e-9)
        kinds = {f.geom_type for f in shape.faces()}
        assert kinds == {GeomType.SPHERE, GeomType.CONE}

    def test_contained_sphere_yields_the_big_sphere(self):
        shape = s.hull()(s.sphere(1), s.translate([2, 0, 0])(s.sphere(5)))
        assert shape.volume == pytest.approx((4 / 3) * math.pi * 125, rel=1e-9)

    def test_overlapping_pair_still_exact(self):
        shape = s.hull()(s.sphere(3), s.translate([5, 0, 0])(s.sphere(5)))
        assert shape.volume == pytest.approx(_pair_hull_volume(3, 5, 5), rel=1e-9)

    def test_three_unequal_spheres_raise(self):
        with pytest.raises(NotImplementedError, match="tritangent"):
            s.hull()(
                s.sphere(3),
                s.translate([14, 0, 0])(s.sphere(5)),
                s.translate([7, 12, 0])(s.sphere(4)),
            )


class TestHullCylinders:
    def test_four_corner_posts_make_a_rounded_box(self):
        r, h, side = 2.0, 10.0, 20.0
        posts = [
            s.translate([x, y, 0])(s.cylinder(r=r, h=h))
            for x in (0, side)
            for y in (0, side)
        ]
        shape = s.hull()(*posts)
        expected = (side * side + 4 * r * side + math.pi * r * r) * h
        assert shape.volume == pytest.approx(expected, rel=1e-9)


class TestHull2D:
    def test_keyhole_of_two_circles(self):
        ra, rb, d = 3.0, 5.0, 10.0
        face = s.hull()(s.circle(ra), s.translate([d, 0, 0])(s.circle(rb)))
        alpha = math.asin((rb - ra) / d)
        expected = (
            0.5 * ra * ra * (math.pi - 2 * alpha - math.sin(2 * alpha))
            + 0.5 * rb * rb * (math.pi + 2 * alpha + math.sin(2 * alpha))
            + (ra + rb) * d * math.cos(alpha) ** 3
        )
        assert face.area == pytest.approx(expected, rel=1e-9)

    def test_equal_circles_make_a_stadium(self):
        face = s.hull()(s.circle(5), s.translate([10, 0, 0])(s.circle(5)))
        assert face.area == pytest.approx(math.pi * 25 + 100, rel=1e-9)

    def test_coincident_equal_circles_yield_the_circle(self):
        face = s.hull()(s.circle(5), s.circle(5))
        assert face.area == pytest.approx(math.pi * 25, rel=1e-9)

    def test_two_offset_squares(self):
        # The Gridfinity silverware tray's label-slot profile: hull of two
        # axis-aligned rectangles at different widths/offsets. The hull is a
        # trapezoid-sided hexagon; check against the shoelace area of the
        # exact vertex hull.
        face = s.hull()(
            s.translate([0, 10])(s.square([101.616, 20], center=True)),
            s.translate([0, -12.1])(s.square([84, 24.2], center=True)),
        )
        assert face is not None and not face.solids()
        # vertices of the hull, counterclockwise
        pts = [
            (50.808, 20.0),
            (-50.808, 20.0),
            (-50.808, 0.0),
            (-42.0, -24.2),
            (42.0, -24.2),
            (50.808, 0.0),
        ]
        shoelace = 0.5 * abs(
            sum(
                pts[i][0] * pts[(i + 1) % 6][1] - pts[(i + 1) % 6][0] * pts[i][1]
                for i in range(6)
            )
        )
        assert face.area == pytest.approx(shoelace, rel=1e-9)

    def test_contained_square_yields_outer_square(self):
        face = s.hull()(s.square(20, center=True), s.square(5, center=True))
        assert face.area == pytest.approx(400, rel=1e-9)

    def test_square_circle_mix_still_raises(self):
        # mixed curved + polygonal 2D hull has no rung yet
        with pytest.raises(NotImplementedError):
            s.hull()(s.square(10), s.translate([20, 0])(s.circle(3)))


class TestHullPolyhedral:
    def test_two_cubes(self):
        shape = s.hull()(s.cube(10), s.translate([20, 0, 0])(s.cube(10)))
        assert shape.volume == pytest.approx(3000, rel=1e-9)

    def test_rotated_cube_still_polyhedral(self):
        shape = s.hull()(
            s.cube(10), s.rotate([0, 0, 45])(s.translate([25, 0, 0])(s.cube(10)))
        )
        assert shape.is_valid
        assert shape.volume > 2000

    def test_mixed_curved_child_raises(self):
        with pytest.raises(NotImplementedError):
            s.hull()(s.cube(10), s.translate([20, 0, 0])(s.sphere(3)))


class TestHullBasics:
    def test_single_child_is_returned_unchanged(self):
        shape = s.hull()(s.cube(10))
        assert shape.volume == pytest.approx(1000, rel=1e-9)

    def test_empty_raises_value_error(self):
        with pytest.raises(ValueError):
            s.hull()()


class TestMinkowski:
    def test_cube_plus_sphere_matches_steiner(self):
        shape = s.minkowski()(s.cube([20, 15, 10], center=True), s.sphere(3))
        edges = [(20, math.pi / 2)] * 4 + [(15, math.pi / 2)] * 4 + [(10, math.pi / 2)] * 4
        expected = _steiner(3000, 2 * (300 + 200 + 150), edges, 3)
        assert shape.volume == pytest.approx(expected, rel=1e-9)

    def test_polyhedron_ball_kernel_is_recognized(self):
        # BOSL2-style: a rounding kernel tessellated as an explicit
        # polyhedron rather than sphere(). Build a 96-vertex ball.
        pts = []
        for i in range(8):
            theta = math.pi * (i + 0.5) / 8
            for j in range(12):
                phi = 2 * math.pi * j / 12
                pts.append(
                    [
                        2 * math.sin(theta) * math.cos(phi),
                        2 * math.sin(theta) * math.sin(phi),
                        2 * math.cos(theta),
                    ]
                )
        faces = []
        for i in range(7):
            for j in range(12):
                a = i * 12 + j
                b = i * 12 + (j + 1) % 12
                faces.append([a, b, b + 12, a + 12])
        top = list(range(11, -1, -1))
        bottom = list(range(84, 96))
        faces += [top, bottom]
        ball = s.polyhedron(pts, faces)
        shape = s.minkowski()(s.cube(10, center=True), ball)
        assert shape.is_valid
        assert shape.volume > 1000

    def test_unsupported_minkowski_raises(self):
        with pytest.raises(NotImplementedError):
            s.minkowski()(s.cube(10), s.cube(5))


class TestHullGroupedChildren:
    """hull() of pre-fused inputs: OpenSCAD wraps module-call bodies in
    group(), so real hulls often arrive as ONE compound child. Inputs are
    exploded into component solids before classification (decomposition
    never changes a hull), and there is deliberately no single-child
    identity shortcut -- hull(X) == X only for convex X. A Gridfinity cup
    silently lost its rounded-box hull to that shortcut.
    """

    def test_hull_of_prefused_corner_posts_is_the_rounded_box(self):
        import math

        posts = s.union()(
            *[
                s.translate([x, y, 0])(s.cylinder(r=2, h=10))
                for x in (0, 20)
                for y in (0, 20)
            ]
        )
        shape = s.hull()(posts)
        expected = (400 + 4 * 2 * 20 + math.pi * 4) * 10
        assert shape.volume == pytest.approx(expected, rel=1e-9)

    def test_hull_of_prefused_sphere_pair_is_the_tangent_cone_hull(self):
        pair = s.union()(s.sphere(3), s.translate([14, 0, 0])(s.sphere(5)))
        shape = s.hull()(pair)
        assert shape.volume == pytest.approx(_pair_hull_volume(3, 5, 14), rel=1e-9)

    def test_hull_of_single_convex_primitives_is_identity_via_rungs(self):
        import math

        assert s.hull()(s.cube(10)).volume == pytest.approx(1000, rel=1e-9)
        assert s.hull()(s.sphere(3)).volume == pytest.approx(
            (4 / 3) * math.pi * 27, rel=1e-9
        )
        assert s.hull()(s.cylinder(r=2, h=5)).volume == pytest.approx(
            math.pi * 4 * 5, rel=1e-9
        )

    def test_hull_of_single_nonconvex_child_is_its_true_hull(self):
        lshape = s.union()(s.cube([20, 10, 10]), s.cube([10, 20, 10]))
        shape = s.hull()(lshape)
        # The L's hull fills in the missing corner: a 10x10 right-triangle
        # prism of volume 500 on top of the L's own 3000.
        assert shape.volume == pytest.approx(3500, rel=1e-9)
