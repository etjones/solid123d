"""The gated Shape.clean patch (see src/solid123d/occt_workarounds.py)
and its upstream canary."""

import pytest
from build123d import Box, Pos, Shape, Sphere

from solid123d import occt_workarounds

EXPECTED_CUT = 87.9646
EXPECTED_FUSE = 599.9646
BROKEN_CUT = 73.3038


class TestPatchInstalled:
    def test_importing_solid123d_installs_the_guarded_clean(self) -> None:
        assert occt_workarounds.OCCT_SPHERE_SEAM_BUG_IS_UNFIXED
        assert Shape.clean is occt_workarounds._volume_guarded_clean

    def test_native_operators_are_seam_safe(self) -> None:
        # the whole point of patching the chokepoint: a user's own +/-
        # behave exactly like solid123d's union()/difference()
        assert (Sphere(5) - Box(8, 8, 8)).volume == pytest.approx(
            EXPECTED_CUT, rel=1e-4
        )
        assert (Sphere(5) + Box(8, 8, 8)).volume == pytest.approx(
            EXPECTED_FUSE, rel=1e-4
        )

    def test_guarded_clean_still_merges_splitter_faces(self) -> None:
        # clean()'s real benefit is preserved when it is safe
        fused = Box(10, 10, 10) + (Pos(5, 0, 0) * Box(10, 10, 10))
        assert len(fused.faces()) == 6


class TestUpstreamCanary:
    def test_upstream_bug_still_present(self) -> None:
        """ATTENTION on failure: this test asserts the upstream bug still
        EXISTS. If it fails after a build123d/OCCT upgrade, upstream has
        fixed gumyr/build123d#1428 -- flip
        occt_workarounds.OCCT_SPHERE_SEAM_BUG_IS_UNFIXED to False (or
        delete the workaround) and delete this test.
        """
        occt_workarounds.uninstall()
        try:
            broken = (Sphere(5) - Box(8, 8, 8)).volume
        finally:
            occt_workarounds.install()
        assert broken == pytest.approx(BROKEN_CUT, rel=1e-4), (
            "Upstream clean() no longer loses seam-crossed geometry! "
            "Flip OCCT_SPHERE_SEAM_BUG_IS_UNFIXED to False and retire "
            "this workaround."
        )
