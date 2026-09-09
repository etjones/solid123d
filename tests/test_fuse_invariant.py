"""The two things a union cannot do, and what happens when OCCT does them.

A union joins material: it can never return more separate pieces than it
was given, and its pieces can never overlap. Both are statements about
the answer, so they need no reference render -- which is the point, since
the volume guard's interval (largest input .. sum of inputs) is wide
enough to hold either failure.
"""

import warnings

import pytest
from build123d import Box, Compound, Pos, Solid

from solid123d._common import bodies_overlap, fuse_bodies, gained_bodies


def test_a_union_of_overlapping_boxes_is_one_body():
    fused = fuse_bodies([Box(10, 10, 10), Pos(5, 0, 0) * Box(10, 10, 10)])
    assert len(fused.solids()) == 1
    assert fused.volume == pytest.approx(1500)


def test_disjoint_parts_stay_separate_and_are_not_flagged():
    parts = [Pos(20 * i, 0, 0) * Box(10, 10, 10) for i in range(4)]
    fused = fuse_bodies(parts)
    assert len(fused.solids()) == 4
    assert fused.volume == pytest.approx(4000)
    assert not bodies_overlap(fused)
    assert not gained_bodies(parts, fused)


def test_touching_parts_do_not_count_as_overlapping():
    """A part sitting exactly in a pocket cut for it shares a face with
    its neighbour. Sharing a surface is not sharing material, and the
    check must not confuse the two."""
    left = Box(10, 10, 10)
    right = Pos(10, 0, 0) * Box(10, 10, 10)
    assert not bodies_overlap(Compound([left, right]))


def test_overlapping_bodies_are_detected():
    """What OCCT hands back when a fuse quietly does nothing: the operands
    themselves, still on top of each other."""
    unfused = Compound([Box(10, 10, 10), Pos(5, 0, 0) * Box(10, 10, 10)])
    assert bodies_overlap(unfused)


def test_a_result_in_more_pieces_than_it_was_given_is_detected():
    given = [Box(10, 10, 10), Pos(5, 0, 0) * Box(10, 10, 10)]
    shattered = Compound([Pos(30 * i, 0, 0) * Box(1, 1, 1) for i in range(3)])
    assert gained_bodies(given, shattered)
    assert not gained_bodies(given, Compound(given))


def test_one_body_can_never_violate_either_check():
    single = Box(10, 10, 10)
    assert not bodies_overlap(single)
    assert not gained_bodies([single, single], single)


class TestRetry:
    """A violation is retried with a fuzzy tolerance before it is believed."""

    @staticmethod
    def operands():
        return [Box(10, 10, 10), Pos(5, 0, 0) * Box(10, 10, 10)]

    def test_a_failed_fuse_is_retried_and_the_good_result_adopted(self, monkeypatch):
        import solid123d._common as common

        real = common._fuse
        seen: list[float | None] = []

        def flaky(bodies, fuzz=None):
            seen.append(fuzz)
            if fuzz is None:  # the exact pass "fails": operands unmerged
                return Compound(list(bodies))
            return real(bodies, fuzz=fuzz)

        monkeypatch.setattr(common, "_fuse", flaky)
        fused = fuse_bodies(self.operands())
        assert fused.volume == pytest.approx(1500)
        assert len(fused.solids()) == 1
        assert seen[0] is None and seen[1] is not None

    def test_a_fuse_that_cannot_be_repaired_warns_rather_than_hiding(
        self, monkeypatch
    ):
        import solid123d._common as common

        def always_unmerged(bodies, fuzz=None):
            return Compound(list(bodies))

        monkeypatch.setattr(common, "_fuse", always_unmerged)
        with pytest.warns(UserWarning, match="more pieces than it was given"):
            fused = fuse_bodies(self.operands())
        assert len(fused.solids()) == 2  # kept, but announced

    def test_a_correct_fuse_is_never_retried(self, monkeypatch):
        import solid123d._common as common

        real = common._fuse
        calls = [0]

        def counting(bodies, fuzz=None):
            calls[0] += 1
            return real(bodies, fuzz=fuzz)

        monkeypatch.setattr(common, "_fuse", counting)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            fuse_bodies(self.operands())
        assert calls[0] == 1

    def test_a_rung_that_throws_does_not_end_the_ladder(self, monkeypatch):
        """OCCT throws on some fuzzy values (a null shape, an empty
        sequence). That rung does not apply; the next one may still work."""
        import solid123d._common as common

        real = common._fuse
        attempts = [0]

        def throwing(bodies, fuzz=None):
            attempts[0] += 1
            if fuzz is None:
                return Compound(list(bodies))
            if attempts[0] == 2:
                raise ValueError("Null TopoDS_Shape object")
            return real(bodies, fuzz=fuzz)

        monkeypatch.setattr(common, "_fuse", throwing)
        fused = fuse_bodies(self.operands())
        assert fused.volume == pytest.approx(1500)
        assert attempts[0] == 3


def test_union_of_a_solid_with_an_exact_duplicate_of_itself():
    """The corpus case in miniature: a loop that lays its last copy on its
    first. The duplicate adds nothing and must not be left lying on top."""
    bar = Solid.make_box(2, 20, 2)
    fused = fuse_bodies([bar, Solid.make_box(2, 20, 2)])
    assert fused.volume == pytest.approx(80)
    assert not bodies_overlap(fused)
