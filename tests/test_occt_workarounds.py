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

    def test_guard_accepts_integration_noise_but_not_lost_geometry(
        self, monkeypatch
    ) -> None:
        """Volumes integrated over a fragmented and a unified face set differ
        by ~1e-7 relative -- measured on a 52-wedge servo-horn gear from the
        CodeCAD corpus. At the original 1e-9 tolerance that noise rejected
        20 of 21 cleans, fragments piled up (26 -> 822 faces) and OCCT's
        fuse finally returned an inverted 8-face shape. The guard must let
        noise through and still catch the seam bug's ~17% loss."""
        import copy

        shape = Box(10, 10, 10)
        true_volume = shape.volume
        applied: list[float] = []

        def fake_clean(target: Shape, factor: float) -> Shape:
            # "clean" that returns a scaled copy: volume moves by factor^3
            scaled = copy.deepcopy(target).scale(factor)
            target.wrapped = scaled.wrapped
            applied.append(factor)
            return target

        for factor, expect_adopted in ((1 + 3e-8, True), (0.94, False)):
            monkeypatch.setattr(
                occt_workarounds,
                "_original_clean",
                lambda t, f=factor: fake_clean(t, f),
            )
            probe = Box(10, 10, 10)
            occt_workarounds._volume_guarded_clean(probe)
            moved = probe.volume != pytest.approx(true_volume, rel=1e-12)
            assert moved is expect_adopted, (factor, probe.volume)
        assert len(applied) == 2


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


class TestImplausibleBooleanRetry:
    def test_fuse_that_loses_material_is_retried_with_fuzzy_tolerance(
        self, monkeypatch
    ) -> None:
        """OCCT can return a valid-looking fuse with most of the material
        gone (an operand nearly coincident with the accumulated result).
        Simulate it: the exact fuse returns a sliver, the fuzzy retry the
        real union. The guarded op must notice from the input-implied
        bounds and adopt the retry."""
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse

        a, b = Box(10, 10, 10), Pos(5, 0, 0) * Box(10, 10, 10)
        real = occt_workarounds._original_bool_op
        calls: list[float] = []

        def flaky(self, args, tools, operation):
            calls.append(operation.FuzzyValue())
            # build123d's own + already carries a small fuzzy value (1e-6);
            # only the guard's larger retry value counts as the retry.
            if (
                isinstance(operation, BRepAlgoAPI_Fuse)
                and operation.FuzzyValue() != occt_workarounds.BOOLEAN_RETRY_FUZZ
            ):
                return Box(1, 1, 1)  # "valid", but 1 mm^3 of a 1500 mm^3 union
            return real(self, args, tools, operation)

        monkeypatch.setattr(occt_workarounds, "_original_bool_op", flaky)
        fused = a + b
        assert fused.volume == pytest.approx(1500)
        assert len(calls) == 2 and calls[-1] == occt_workarounds.BOOLEAN_RETRY_FUZZ

    def test_plausible_results_are_not_retried(self, monkeypatch) -> None:
        real = occt_workarounds._original_bool_op
        calls: list[float] = []

        def counting(self, args, tools, operation):
            calls.append(operation.FuzzyValue())
            return real(self, args, tools, operation)

        monkeypatch.setattr(occt_workarounds, "_original_bool_op", counting)
        assert (Box(10, 10, 10) - Box(4, 4, 4)).volume == pytest.approx(1000 - 64)
        assert (Box(10, 10, 10) & Box(4, 4, 4)).volume == pytest.approx(64)
        assert len(calls) == 2 and occt_workarounds.BOOLEAN_RETRY_FUZZ not in calls

    def test_unfixable_result_warns_rather_than_hiding(self, monkeypatch) -> None:
        def always_sliver(self, args, tools, operation):
            return Box(1, 1, 1)

        monkeypatch.setattr(occt_workarounds, "_original_bool_op", always_sliver)
        with pytest.warns(UserWarning, match="implausible volume"):
            fused = Box(10, 10, 10) + Pos(5, 0, 0) * Box(10, 10, 10)
        assert fused.volume == pytest.approx(1)  # the sliver, kept but warned about
