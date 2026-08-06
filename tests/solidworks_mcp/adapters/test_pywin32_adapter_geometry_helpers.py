"""Coverage for the pure-Python geometry math in PyWin32Adapter's internal
``_SketchGeometryService`` and the ``_ComSessionCoordinator`` server-ready
retry loop.

These branches need no live COM session — only objects that look enough
like SolidWorks COM entities (plain attributes / SimpleNamespace) to drive
the math. Per CLAUDE.md's adapter-testing guidance this mirrors the
established ``_build_adapter(monkeypatch)`` pattern in
tests/solidworks_mcp/adapters/test_adapters.py::TestPyWin32AdapterBranches.

Lines targeted (from `coverage report --show-missing`):
  - 302: wait_for_server_ready returns once RevisionNumber becomes truthy
    after an initial None reading.
  - 535, 539: set_display_dimension_value's GetDimension()/direct-object
    fallback chain when GetDimension2 is unavailable.
  - 617: set_point_xyz short-circuits to False for a None point object.
  - 658: read_segment_endpoints returns None when the entity exposes no
    usable GetStartPoint/GetEndPoint tuples.
  - 703, 707, 714: shared_segment_vertex's inner-loop "continue" on
    unreadable points, and the final "no shared vertex found" return.
  - 772: single_line_dimension_placement returns None when endpoints are
    unavailable.
  - 816: angular_dimension_placement returns None when either segment's
    endpoints are unavailable.
  - 848: angular_dimension_placement returns None for a degenerate
    (zero-length) ray.
  - 857-858: the anti-parallel-rays bisector fallback (perpendicular to
    ray1 when the two ray directions cancel out).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter


def _build_adapter(monkeypatch) -> PyWin32Adapter:
    """Same construction pattern as TestPyWin32AdapterBranches._build_adapter."""
    monkeypatch.setattr(
        "solidworks_mcp.adapters.pywin32_adapter.PYWIN32_AVAILABLE", True
    )
    monkeypatch.setattr(
        "solidworks_mcp.adapters.pywin32_adapter.platform.system",
        lambda: "Windows",
    )
    monkeypatch.setattr(
        "solidworks_mcp.adapters.pywin32_adapter.pywintypes",
        SimpleNamespace(com_error=RuntimeError),
        raising=False,
    )
    return PyWin32Adapter({})


class TestWaitForServerReady:
    @pytest.mark.asyncio
    async def test_returns_once_revision_number_becomes_available(self, monkeypatch) -> None:
        adapter = _build_adapter(monkeypatch)
        readings = iter([None, None, "33.2"])

        async def _no_sleep(_seconds: float) -> None:
            return None

        monkeypatch.setattr(
            "solidworks_mcp.adapters.pywin32_adapter.asyncio.sleep", _no_sleep
        )

        app = SimpleNamespace(RevisionNumber=lambda: next(readings))
        # Should not raise and should return normally once a non-None
        # reading appears (third attempt).
        await adapter._session_coordinator.wait_for_server_ready(app)


class TestSetDisplayDimensionValue:
    def test_falls_back_to_get_dimension_when_get_dimension2_unavailable(
        self, monkeypatch
    ) -> None:
        adapter = _build_adapter(monkeypatch)
        legacy_dim = SimpleNamespace(
            SetSystemValue3=None,
            SetSystemValue2=lambda value, unit: True,
        )
        # GetDimension2 raises (unsupported on this SW version); GetDimension()
        # returns a usable dimension object instead.
        display_dim = SimpleNamespace(
            GetDimension2=lambda idx: (_ for _ in ()).throw(AttributeError()),
            GetDimension=lambda: legacy_dim,
        )
        # Should not raise; exercises the GetDimension() fallback branch.
        adapter._sketch_geometry.set_display_dimension_value(display_dim, 25.0)

    def test_falls_back_to_the_display_dim_object_itself(self, monkeypatch) -> None:
        adapter = _build_adapter(monkeypatch)

        class _DisplayDim:
            SystemValue = None

            def GetDimension2(self, idx):
                raise AttributeError("not supported")

            def GetDimension(self):
                raise AttributeError("not supported either")

        display_dim = _DisplayDim()
        # Neither GetDimension2 nor GetDimension work, so the service must
        # fall back to using display_dim itself as the dimension object.
        adapter._sketch_geometry.set_display_dimension_value(display_dim, 12.5)
        assert display_dim.SystemValue == pytest.approx(0.0125)


class TestSetPointXyz:
    def test_returns_false_for_none_point_object(self, monkeypatch) -> None:
        adapter = _build_adapter(monkeypatch)
        assert adapter._sketch_geometry.set_point_xyz(None, 1.0, 2.0, 3.0) is False


class TestReadSegmentEndpoints:
    def test_returns_none_when_entity_lacks_point_tuples(self, monkeypatch) -> None:
        adapter = _build_adapter(monkeypatch)
        entity = SimpleNamespace()  # no GetStartPoint / GetEndPoint at all
        assert adapter._sketch_geometry.read_segment_endpoints(entity) is None


class TestSharedSegmentVertex:
    @staticmethod
    def _line(start: tuple, end: tuple) -> SimpleNamespace:
        return SimpleNamespace(
            GetStartPoint2=SimpleNamespace(X=start[0], Y=start[1], Z=start[2]),
            GetEndPoint2=SimpleNamespace(X=end[0], Y=end[1], Z=end[2]),
        )

    def test_finds_the_shared_vertex_between_two_lines(self, monkeypatch) -> None:
        adapter = _build_adapter(monkeypatch)
        # Two lines sharing the point (0, 0, 0).
        line1 = self._line((0.0, 0.0, 0.0), (0.01, 0.0, 0.0))
        line2 = self._line((0.0, 0.0, 0.0), (0.0, 0.01, 0.0))

        result = adapter._sketch_geometry.shared_segment_vertex(line1, line2)
        assert result is not None
        vertex, ray1, ray2 = result
        assert adapter._sketch_geometry.point_xyz(vertex) == pytest.approx(
            (0.0, 0.0, 0.0)
        )

    def test_returns_none_when_no_shared_vertex_exists(self, monkeypatch) -> None:
        adapter = _build_adapter(monkeypatch)
        # Disjoint lines: no endpoint pair is within tolerance.
        line1 = self._line((0.0, 0.0, 0.0), (0.01, 0.0, 0.0))
        line2 = self._line((5.0, 5.0, 0.0), (5.0, 6.0, 0.0))

        assert adapter._sketch_geometry.shared_segment_vertex(line1, line2) is None

    def test_skips_points_that_fail_to_resolve_xyz(self, monkeypatch) -> None:
        """One endpoint on each segment can't be read (point_xyz -> None);
        the loop must `continue` past it rather than raising, and still find
        the shared vertex among the remaining points."""
        adapter = _build_adapter(monkeypatch)
        unreadable = SimpleNamespace()  # no X/Y/Z, no GetCoords -> point_xyz None
        line1 = SimpleNamespace(
            GetStartPoint2=unreadable,
            GetEndPoint2=SimpleNamespace(X=1.0, Y=1.0, Z=0.0),
        )
        line2 = SimpleNamespace(
            GetStartPoint2=SimpleNamespace(X=1.0, Y=1.0, Z=0.0),
            GetEndPoint2=unreadable,
        )
        result = adapter._sketch_geometry.shared_segment_vertex(line1, line2)
        assert result is not None


class TestSingleLineDimensionPlacement:
    def test_returns_none_when_endpoints_unavailable(self, monkeypatch) -> None:
        adapter = _build_adapter(monkeypatch)
        entity = SimpleNamespace()  # read_segment_endpoints -> None
        assert adapter._sketch_geometry.single_line_dimension_placement(entity) is None


class TestAngularDimensionPlacement:
    @staticmethod
    def _line(start: tuple, end: tuple) -> SimpleNamespace:
        return SimpleNamespace(GetStartPoint=start, GetEndPoint=end)

    def test_returns_none_when_either_segment_endpoints_unavailable(
        self, monkeypatch
    ) -> None:
        adapter = _build_adapter(monkeypatch)
        good = self._line((0.0, 0.0, 0.0), (0.01, 0.0, 0.0))
        bad = SimpleNamespace()  # no usable endpoints
        assert (
            adapter._sketch_geometry.angular_dimension_placement(good, bad) is None
        )

    def test_returns_none_for_a_degenerate_zero_length_ray(self, monkeypatch) -> None:
        adapter = _build_adapter(monkeypatch)
        # Both lines share vertex (0,0,0); line2's "other" endpoint is the
        # vertex itself too, giving a zero-length ray (l2 <= 1e-9).
        line1 = self._line((0.0, 0.0, 0.0), (0.01, 0.0, 0.0))
        line2 = self._line((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        assert (
            adapter._sketch_geometry.angular_dimension_placement(line1, line2)
            is None
        )

    def test_uses_perpendicular_fallback_when_rays_are_anti_parallel(
        self, monkeypatch
    ) -> None:
        """Two collinear, opposite-direction rays from the shared vertex sum
        to (~0, ~0); the bisector must fall back to a perpendicular of ray1."""
        adapter = _build_adapter(monkeypatch)
        # Shared vertex at (0,0,0); ray1 points +X, ray2 points -X (opposite).
        line1 = self._line((0.0, 0.0, 0.0), (0.01, 0.0, 0.0))
        line2 = self._line((0.0, 0.0, 0.0), (-0.01, 0.0, 0.0))

        result = adapter._sketch_geometry.angular_dimension_placement(line1, line2)
        assert result is not None
        text_x, text_y, text_z, direction = result
        # ray1 direction is (1, 0); the documented fallback is
        # bis = (-ray1_y, ray1_x) = (0, 1), i.e. +Y. A fallback that instead
        # rotated the other way ((ray1_y, -ray1_x) = (0, -1), i.e. -Y) would
        # place the dimension text on the wrong side of the angle — assert
        # the exact sign, not just "nonzero", so that regression is caught.
        assert text_x == pytest.approx(0.0, abs=1e-9)
        assert text_y > 0.0
