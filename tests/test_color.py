"""Color preservation through group()/union(), and part labeling.

Ported from scad123d, where this logic was developed and verified against
real STEP output in slicers. Three regimes, gated on authored color:

- No color() anywhere: plain fuse, bit-identical to prior behavior (and no
  mass-property bookkeeping).
- Colored children with zero shared volume (disjoint, or touching along a
  surface): kept as a Compound of separate bodies, each with its own color
  and label -- what multi-material workflows need from STEP export.
- Colored children genuinely overlapping: partitioned into touching
  bodies. Later children claim contested volume; each earlier child
  keeps its color on whatever nothing later covers. Adjacent
  same-colored children fuse first, and if partitioning ever loses
  volume to a boolean glitch, the plain fuse is returned instead.
"""

import math

import pytest

import solid123d as s


class TestColorLabels:
    def test_named_color_labels_with_the_authors_literal_name(self):
        assert s.color("red")(s.cube(1)).label == "red"
        assert s.color("SteelBlue")(s.cube(1)).label == "steelblue"

    def test_numeric_color_labels_with_css_name_when_exact(self):
        assert s.color([1, 0, 0])(s.cube(1)).label == "red"

    def test_numeric_color_without_a_name_labels_with_hex(self):
        assert s.color([0.2, 0.3, 0.4])(s.cube(1)).label == "#334c66"

    def test_existing_label_is_never_overwritten(self):
        shape = s.cube(1)
        shape.label = "my-part"
        colored = s.color("red")(shape)
        assert colored.label == "my-part"


class TestColorGroups:
    def test_disjoint_colored_children_keep_their_own_colors(self):
        u = s.union()(
            s.color("red")(s.cube(10)),
            s.color("blue")(s.translate([20, 0, 0])(s.cube(5))),
        )
        assert len(u.children) == 2
        (c1, c2) = u.children
        assert (str(c1.color), c1.label) == (
            "Color: (1.0, 0.0, 0.0, 1.0) is 'RED'",
            "red",
        )
        assert c2.label == "blue"
        assert u.volume == pytest.approx(1000 + 125, rel=1e-9)

    def test_touching_colored_children_stay_separate_bodies(self):
        u = s.union()(
            s.color("red")(s.cube(10)),
            s.color("blue")(s.translate([10, 0, 0])(s.cube(10))),
        )
        assert len(u.children) == 2
        assert u.volume == pytest.approx(2000, rel=1e-9)

    def test_touching_uncolored_children_still_fuse_to_one_solid(self):
        u = s.union()(s.cube(10), s.translate([10, 0, 0])(s.cube(10)))
        assert len(u.solids()) == 1
        assert u.volume == pytest.approx(2000, rel=1e-9)

    def test_uncolored_disjoint_children_get_the_plain_fuse(self):
        u = s.union()(s.cube(10), s.translate([20, 0, 0])(s.cube(5)))
        assert len(u.children) == 0
        assert len(u.solids()) == 2

    def test_overlapping_colored_children_partition_into_bodies(self):
        # Later children claim contested volume: red keeps cube-minus-blue,
        # blue survives whole. Total volume matches the plain fuse.
        u = s.union()(
            s.color("red")(s.cube(10)),
            s.color("blue")(s.translate([5, 5, 5])(s.cube(10))),
        )
        red, blue = u.children
        assert u.volume == pytest.approx(1000 + 1000 - 125, rel=1e-9)
        assert red.volume == pytest.approx(1000 - 125, rel=1e-9)
        assert blue.volume == pytest.approx(1000, rel=1e-9)
        assert (red.label, blue.label) == ("red", "blue")
        assert tuple(red.color) == pytest.approx((1.0, 0.0, 0.0, 1.0))
        assert tuple(blue.color) == pytest.approx((0.0, 0.0, 1.0, 1.0))

    def test_nested_color_overrides_the_outer_color(self):
        inner_blue = s.color("blue")(s.translate([20, 0, 0])(s.sphere(3)))
        outer = s.color("red")(s.cube(10), inner_blue)
        cube, sphere = outer.children
        assert tuple(outer.color) == pytest.approx((1.0, 0.0, 0.0, 1.0))
        # The cube has no authored color; build123d resolves it from the
        # nearest colored ancestor (the red outer group).
        assert cube._color is None
        assert tuple(cube.color) == pytest.approx((1.0, 0.0, 0.0, 1.0))
        assert tuple(sphere.color) == pytest.approx((0.0, 0.0, 1.0, 1.0))

    def test_colored_part_keeps_color_outside_an_uncolored_union(self):
        # The motivating example: union(color("red") sphere, cube) keeps
        # the sphere red wherever the cube doesn't claim the space.
        u = s.union()(
            s.color("red")(s.sphere(5)),
            s.cube(8, center=True),
        )
        red, base = u.children
        sphere_vol = 4 / 3 * math.pi * 125
        overlap = (s.sphere(5) & s.cube(8, center=True)).volume
        assert red.label == "red"
        assert red.volume == pytest.approx(sphere_vol - overlap, rel=1e-6)
        assert base._color is None
        assert base.volume == pytest.approx(512, rel=1e-9)
        assert u.volume == pytest.approx(sphere_vol - overlap + 512, rel=1e-6)

    def test_overlap_goes_to_the_later_child(self):
        # Reversed order: the colored sphere is later, so the contested
        # volume is red and the cube gets clipped.
        u = s.union()(
            s.cube(8, center=True),
            s.color("red")(s.sphere(5)),
        )
        base, red = u.children
        sphere_vol = 4 / 3 * math.pi * 125
        assert red.volume == pytest.approx(sphere_vol, rel=1e-6)
        assert base.volume < 512

    def test_fully_covered_child_disappears(self):
        u = s.union()(
            s.color("red")(s.cube(2, center=True)),
            s.color("blue")(s.cube(10, center=True)),
        )
        # red is entirely inside blue: only the blue body remains
        assert u.label == "blue"
        assert u.volume == pytest.approx(1000, rel=1e-9)

    def test_adjacent_same_color_children_fuse_to_one_body(self):
        u = s.union()(
            s.color("red")(s.cube(10)),
            s.color("red")(s.translate([5, 0, 0])(s.cube(10))),
            s.color("blue")(s.translate([100, 0, 0])(s.cube(5))),
        )
        red, blue = u.children
        assert len(red.solids()) == 1
        assert red.volume == pytest.approx(1500, rel=1e-9)
        assert red.label == "red"
        assert blue.label == "blue"

    def test_three_way_mixed_partition(self):
        u = s.union()(
            s.color("red")(s.cube(10)),
            s.translate([5, 0, 0])(s.cube(10)),
            s.color("blue")(s.translate([10, 0, 0])(s.cube(10))),
        )
        red, base, blue = u.children
        assert (red.label, blue.label) == ("red", "blue")
        assert red.volume == pytest.approx(500, rel=1e-9)  # clipped by base
        assert base.volume == pytest.approx(500, rel=1e-9)  # clipped by blue
        assert blue.volume == pytest.approx(1000, rel=1e-9)
        assert u.volume == pytest.approx(2000, rel=1e-9)

    def test_mixed_2d_3d_children_warn_and_drop_the_2d(self):
        with pytest.warns(UserWarning, match="mixes 2D and 3D"):
            u = s.union()(s.cube(10), s.circle(5))
        assert u.volume == pytest.approx(1000, rel=1e-9)

    def test_color_applies_alpha(self):
        shape = s.color("red", alpha=0.5)(s.cube(1))
        assert tuple(shape.color) == pytest.approx((1.0, 0.0, 0.0, 0.5))
        assert math.isclose(tuple(shape.color)[3], 0.5)
