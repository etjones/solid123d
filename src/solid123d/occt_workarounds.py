"""Gated workarounds for upstream OCCT/build123d defects.

OCCT_SPHERE_SEAM_BUG_IS_UNFIXED gates the one active workaround. While
True (the current state of upstream), importing solid123d replaces
``build123d.Shape.clean`` with a volume-guarded version; set it to False
-- or delete the workaround entirely -- once upstream ships a fix, and
every call site reverts to stock build123d behavior. The canary test in
tests/test_occt_workarounds.py fails the moment an upgraded
build123d/OCCT no longer exhibits the bug, which is the signal to flip
this flag.

The bug (https://github.com/gumyr/build123d/issues/1428): ``clean()``
-- the ShapeUpgrade_UnifySameDomain pass build123d's boolean operators
run automatically -- deletes real geometry when the result contains a
face crossed by a curved surface's parametric seam. ``sphere(5) -
cube(8, center=True)`` loses the spherical cap its seam meridian
crosses (73.30 mm^3 instead of 87.96); the matching fuse loses the same
material and exports to STEP as faces only, which slicers read as zero
volume. The maintainer notes OCCT's seam handling as the underlying
culprit ("degenerate treatment of valid geometry containing curved
seams").

Patching ``Shape.clean`` -- rather than routing solid123d's own
booleans through raw BRepAlgoAPI calls -- is deliberate: it is the one
chokepoint every affected path shares. With it in place, solid123d's
``union()``/``difference()``/``intersection()``, build123d's native
``+``/``-``/``&`` on the shapes we hand out, and everything in scad123d
(which imports solid123d) all behave consistently. A call-site-only fix
would leave ``union()`` correct while a user's own ``a + b`` on the
same shapes silently lost material -- a confusing split.

The guarded clean preserves clean()'s contract exactly: it mutates
``self`` in place and returns it. The trial clean runs on a deepcopy
(clean() mutates as well as returns, so an in-place trial would destroy
the original), and its result is adopted only when volume is conserved.
Cost: one geometry copy and two mass computations per clean(); measured
cheaper than the unconditional clean it replaces (16.3 vs 22.9 ms per
sphere/cube fuse), since most cleans are accepted and the pathological
ones skip the expensive rebuild.

Caveat, stated in the upstream issue too: a volume guard protects
solids. A hypothetical clean() failure that conserved volume while
mangling faces would pass the guard.
"""

import copy
import math

from build123d import Shape
from build123d.topology.shape_core import SkipClean

OCCT_SPHERE_SEAM_BUG_IS_UNFIXED = True

_original_clean = Shape.clean
_original_bool_op = Shape._bool_op


def _volume_guarded_clean(self: Shape) -> Shape:
    """Drop-in Shape.clean: adopt the clean only if volume is conserved."""
    try:
        before = self.volume
    except Exception:  # noqa: BLE001 -- any OCP failure computing mass
        # properties (Standard_Failure etc.): fall back to stock clean,
        # which is strictly no worse than pre-workaround behavior
        return _original_clean(self)
    trial = copy.deepcopy(self)
    _original_clean(trial)
    if math.isclose(trial.volume, before, rel_tol=1e-9, abs_tol=1e-9):
        self.wrapped = trial.wrapped
    return self


def _guarded_bool_op(self: Shape, args, tools, operation) -> Shape:
    """Drop-in Shape._bool_op: raw boolean, then volume-guarded clean.

    _bool_op runs ShapeUpgrade_UnifySameDomain inline (not via
    Shape.clean), gated by build123d's own SkipClean flag -- so the
    boolean executes under SkipClean, and the unify pass is reapplied
    afterwards through the guarded clean.
    """
    with SkipClean():
        result = _original_bool_op(self, args, tools, operation)
    if result is not None and result.wrapped is not None:
        result = _volume_guarded_clean(result)
    return result


def install() -> None:
    """Activate the gated workarounds (idempotent). Called on import of
    solid123d."""
    if OCCT_SPHERE_SEAM_BUG_IS_UNFIXED:
        Shape.clean = _volume_guarded_clean
        Shape._bool_op = _guarded_bool_op


def uninstall() -> None:
    """Restore stock build123d behavior (used by the canary test)."""
    Shape.clean = _original_clean
    Shape._bool_op = _original_bool_op
