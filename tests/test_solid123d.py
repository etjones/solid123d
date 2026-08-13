import math
from pathlib import Path

import pytest
from build123d import Shape

from solid123d import (
    circle,
    cube,
    cylinder,
    difference,
    hull,
    intersection,
    linear_extrude,
    mirror,
    polygon,
    rotate,
    rotate_extrude,
    scad_render_to_file,
    scale,
    sphere,
    square,
    translate,
    union,
)
from solid123d.utils import up


def bbox(shape: Shape) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    bb = shape.bounding_box()
    return (
        (bb.min.X, bb.min.Y, bb.min.Z),
        (bb.max.X, bb.max.Y, bb.max.Z),
    )


def assert_close(a: tuple, b: tuple, tol: float = 1e-6) -> None:
    for x, y in zip(a, b):
        assert x == pytest.approx(y, abs=tol)


class TestPrimitives:
    def test_cube_corner_at_origin(self) -> None:
        lo, hi = bbox(cube(10))
        assert_close(lo, (0, 0, 0))
        assert_close(hi, (10, 10, 10))

    def test_cube_centered(self) -> None:
        lo, hi = bbox(cube(10, center=True))
        assert_close(lo, (-5, -5, -5))
        assert_close(hi, (5, 5, 5))

    def test_cube_vector_size(self) -> None:
        lo, hi = bbox(cube([1, 2, 3]))
        assert_close(hi, (1, 2, 3))

    def test_sphere_volume(self) -> None:
        s = sphere(r=5)
        assert s.volume == pytest.approx(4 / 3 * math.pi * 125, rel=1e-6)
        assert sphere(d=10).volume == pytest.approx(s.volume, rel=1e-9)

    def test_cylinder_sits_on_z0(self) -> None:
        c = cylinder(r=2, h=10)
        lo, hi = bbox(c)
        assert lo[2] == pytest.approx(0)
        assert hi[2] == pytest.approx(10)
        assert c.volume == pytest.approx(math.pi * 4 * 10, rel=1e-6)

    def test_cylinder_centered(self) -> None:
        lo, hi = bbox(cylinder(r=2, h=10, center=True))
        assert lo[2] == pytest.approx(-5)
        assert hi[2] == pytest.approx(5)

    def test_cone_r1_r2(self) -> None:
        c = cylinder(r1=4, r2=0, h=9)
        assert c.volume == pytest.approx(math.pi * 16 * 9 / 3, rel=1e-6)

    def test_cylinder_openscad_keyword_style(self) -> None:
        c = cylinder(h=10, d=4)
        assert c.volume == pytest.approx(math.pi * 4 * 10, rel=1e-6)

    def test_square_and_circle(self) -> None:
        lo, hi = bbox(square([4, 2]))
        assert_close(lo, (0, 0, 0))
        assert_close(hi, (4, 2, 0))
        assert circle(r=3).area == pytest.approx(math.pi * 9, rel=1e-6)

    def test_polygon(self) -> None:
        tri = polygon([[0, 0], [10, 0], [0, 10]])
        assert tri.area == pytest.approx(50)

    def test_polygon_with_hole(self) -> None:
        shape = polygon(
            points=[[0, 0], [10, 0], [10, 10], [0, 10],
                    [2, 2], [8, 2], [8, 8], [2, 8]],
            paths=[[0, 1, 2, 3], [4, 5, 6, 7]],
        )
        assert shape.area == pytest.approx(100 - 36)


class TestTransforms:
    def test_translate(self) -> None:
        lo, _ = bbox(translate([10, 0, 0])(cube(10, center=True)))
        assert_close(lo, (5, -5, -5))

    def test_translate_multiple_children_unions(self) -> None:
        shape = translate([0, 0, 5])(cube(2), cube(4))
        assert shape.volume == pytest.approx(64)
        lo, _ = bbox(shape)
        assert lo[2] == pytest.approx(5)

    def test_rotate_vector_openscad_order(self) -> None:
        # rotate([90, 0, 90]) applied to a unit-ish box off-axis:
        # X-rot first, then Z-rot, matching OpenSCAD's fixed-axis order.
        shape = rotate([90, 0, 90])(cube([1, 2, 3]))
        lo, hi = bbox(shape)
        assert_close(lo, (0, 0, 0), tol=1e-6)
        assert_close(hi, (3, 1, 2), tol=1e-6)

    def test_rotate_axis_angle(self) -> None:
        shape = rotate(a=45, v=[0, 0, 1])(cube(1, center=True))
        _, hi = bbox(shape)
        assert hi[0] == pytest.approx(math.sqrt(2) / 2, rel=1e-6)

    def test_rotate_scalar_is_about_z(self) -> None:
        shape = rotate(90)(translate([5, 0, 0])(cube(1, center=True)))
        lo, hi = bbox(shape)
        assert (lo[1] + hi[1]) / 2 == pytest.approx(5, abs=1e-6)

    def test_scale(self) -> None:
        shape = scale([2, 1, 0.5])(cube(10))
        _, hi = bbox(shape)
        assert_close(hi, (20, 10, 5))

    def test_scale_2d_vector_keeps_z(self) -> None:
        # OpenSCAD: scale([x, y]) implies z factor 1, not 0
        shape = scale([2, 3])(cube(10))
        _, hi = bbox(shape)
        assert_close(hi, (20, 30, 10))
        assert shape.volume == pytest.approx(6000)

    def test_mirror(self) -> None:
        shape = mirror([1, 0, 0])(translate([5, 0, 0])(cube(2)))
        lo, hi = bbox(shape)
        assert hi[0] == pytest.approx(-5)
        assert lo[0] == pytest.approx(-7)


class TestBooleans:
    def test_union(self) -> None:
        shape = union()(cube(10), translate([5, 0, 0])(cube(10)))
        assert shape.volume == pytest.approx(1500)

    def test_difference(self) -> None:
        shape = difference()(cube(10), translate([5, 0, 0])(cube(10)))
        assert shape.volume == pytest.approx(500)

    def test_intersection(self) -> None:
        shape = intersection()(cube(10), translate([5, 0, 0])(cube(10)))
        assert shape.volume == pytest.approx(500)

    def test_native_operators(self) -> None:
        a, b = cube(10), translate([5, 0, 0])(cube(10))
        assert (a + b).volume == pytest.approx(1500)
        assert (a - b).volume == pytest.approx(500)
        assert (a & b).volume == pytest.approx(500)

    def test_hull_raises(self) -> None:
        with pytest.raises(NotImplementedError):
            hull()(cube(1), sphere(1))


class TestExtrusions:
    def test_linear_extrude(self) -> None:
        shape = linear_extrude(height=5)(square([4, 3]))
        assert shape.volume == pytest.approx(60)
        lo, hi = bbox(shape)
        assert lo[2] == pytest.approx(0)
        assert hi[2] == pytest.approx(5)

    def test_linear_extrude_center(self) -> None:
        lo, hi = bbox(linear_extrude(height=4, center=True)(square(2)))
        assert lo[2] == pytest.approx(-2)
        assert hi[2] == pytest.approx(2)

    def test_linear_extrude_scale_tapers(self) -> None:
        shape = linear_extrude(height=6, scale=0.5)(square(4, center=True))
        _, hi = bbox(shape)
        assert hi[2] == pytest.approx(6)
        full = linear_extrude(height=6)(square(4, center=True))
        assert shape.volume < full.volume

    def test_rotate_extrude_torus(self) -> None:
        shape = rotate_extrude()(translate([10, 0, 0])(circle(r=2)))
        # torus volume: 2 * pi^2 * R * r^2
        assert shape.volume == pytest.approx(
            2 * math.pi**2 * 10 * 4, rel=1e-6
        )

    def test_rotate_extrude_partial(self) -> None:
        shape = rotate_extrude(angle=180)(translate([10, 0, 0])(circle(r=2)))
        assert shape.volume == pytest.approx(math.pi**2 * 10 * 4, rel=1e-6)


class TestRender:
    def test_scad_filename_becomes_step(self, tmp_path: Path) -> None:
        target = tmp_path / "c.scad"
        with pytest.warns(UserWarning):
            out = scad_render_to_file(cube(10), filename=str(target))
        assert out == str(tmp_path / "c.step")
        assert Path(out).exists()

    def test_stl_export(self, tmp_path: Path) -> None:
        out = scad_render_to_file(sphere(5), filepath=str(tmp_path / "s.stl"))
        assert Path(out).stat().st_size > 0

    def test_readme_example(self, tmp_path: Path) -> None:
        c = translate([10, 0, 0])(cube(10, center=True))
        with pytest.warns(UserWarning):
            scad_render_to_file(c, filename=str(tmp_path / "c.scad"))
        assert (tmp_path / "c.step").exists()


class TestTypingAliases:
    def test_aliases_are_shape(self) -> None:
        from solid123d import OpenSCADObject, OpenSCADObjectPlus

        assert OpenSCADObject is Shape
        assert OpenSCADObjectPlus is Shape
        assert isinstance(cube(1), OpenSCADObject)


class TestUtils:
    def test_up(self) -> None:
        lo, _ = bbox(up(3)(cube(1)))
        assert lo[2] == pytest.approx(3)
