"""Tests for video object detection and track selection.

The scenario behind test_coverage_beats_large_transient is the ben-s-ufo-film
failure: a large bright object (the moon) in shot for the opening seconds
out-scored a small object that was in shot for the whole clip.
"""

import cv2
import numpy as np

from woograph.convert.video import (
    BBox,
    _Candidate,
    _Track,
    _detect_median_subtraction,
    _link_tracks,
    _select_best_track,
)


def test_coverage_beats_large_transient():
    """A small dot present throughout must win over a big early transient."""
    n, w, h = 60, 320, 240
    frames = []
    dot_positions = []
    for i in range(n):
        f = np.full((h, w, 3), 120, dtype=np.uint8)
        # Small dot crossing the sky for the whole clip
        x = 40 + int(240 * i / (n - 1))
        y = 60 + int(120 * i / (n - 1))
        cv2.circle(f, (x, y), 3, (255, 255, 255), -1)
        dot_positions.append((x, y))
        # Big "moon" only in the opening frames
        if i < 15:
            cv2.circle(f, (80, 180), 25, (255, 255, 255), -1)
        frames.append(f)

    bboxes = _detect_median_subtraction(frames)

    detected = [(i, b) for i, b in enumerate(bboxes) if b is not None]
    assert len(detected) > n * 0.6, f"only {len(detected)}/{n} frames detected"
    for i, b in detected:
        cx, cy = b.center
        x, y = dot_positions[i]
        assert abs(cx - x) < 5 and abs(cy - y) < 5, (
            f"frame {i}: detection at ({cx:.0f},{cy:.0f}), dot at ({x},{y})"
        )


def test_link_tracks_bridges_gaps():
    """A few frames of detection dropout must not split a track."""
    fc = {
        i: [_Candidate(BBox(10 + 4 * i, 50, 6, 6), 0.8)]
        for i in range(20)
    }
    fc[7] = []
    fc[8] = []

    tracks = _link_tracks(fc, max_jump=60.0)

    assert len(tracks) == 1
    assert len(tracks[0].frame_indices) == 18


def test_link_tracks_splits_after_max_gap():
    """A dropout longer than max_gap must end the track and start a new one."""
    fc = {
        i: [_Candidate(BBox(10 + 2 * i, 50, 6, 6), 0.8)]
        for i in range(20)
    }
    for i in range(7, 14):  # 7-frame dropout > default max_gap of 5
        fc[i] = []

    tracks = _link_tracks(fc, max_jump=60.0)

    assert len(tracks) == 2


def test_link_tracks_size_gate_separates_objects():
    """A candidate of wildly different size must not join an existing track."""
    fc = {
        0: [_Candidate(BBox(50, 50, 6, 6), 0.8)],
        1: [_Candidate(BBox(50, 50, 60, 60), 0.8)],
    }

    tracks = _link_tracks(fc, max_jump=100.0)

    assert len(tracks) == 2


def test_link_tracks_separates_distant_objects():
    """Two objects far apart must produce two tracks."""
    fc = {
        i: [
            _Candidate(BBox(10 + 2 * i, 50, 6, 6), 0.8),
            _Candidate(BBox(10 + 2 * i, 200, 6, 6), 0.8),
        ]
        for i in range(20)
    }

    tracks = _link_tracks(fc, max_jump=30.0)

    assert len(tracks) == 2
    assert all(len(t.frame_indices) == 20 for t in tracks)


def test_select_prefers_coverage_over_size():
    big_short = _Track(
        list(range(15)), [_Candidate(BBox(0, 0, 50, 50), 0.8)] * 15,
    )
    small_long = _Track(
        list(range(60)), [_Candidate(BBox(0, 0, 6, 6), 0.7)] * 60,
    )

    best = _select_best_track([big_short, small_long], n_frames=60)

    assert best is small_long


def test_select_prefers_compact_over_diffuse():
    """Equal coverage: a dense object beats sparse noise (tree branches)."""
    diffuse = _Track(
        list(range(60)), [_Candidate(BBox(0, 0, 80, 40), 0.1)] * 60,
    )
    compact = _Track(
        list(range(60)), [_Candidate(BBox(0, 0, 8, 6), 0.75)] * 60,
    )

    best = _select_best_track([diffuse, compact], n_frames=60)

    assert best is compact


def test_select_ignores_short_tracks():
    short = _Track(list(range(5)), [_Candidate(BBox(0, 0, 6, 6), 0.9)] * 5)

    assert _select_best_track([short], n_frames=60) is None


def test_detect_handles_empty_frames():
    assert _detect_median_subtraction([]) == []


def test_border_anchored_noise_never_wins():
    """A jittering border band (trees under bad stabilisation) must lose.

    Pins the CI failure where a huge frame-edge-anchored vegetation region
    won track selection and its giant crops exhausted runner memory.
    """
    n, w, h = 60, 320, 240
    frames = []
    dot_positions = []
    for i in range(n):
        f = np.full((h, w, 3), 120, dtype=np.uint8)
        x = 40 + int(240 * i / (n - 1))
        y = 30 + int(100 * i / (n - 1))
        cv2.circle(f, (x, y), 3, (255, 255, 255), -1)
        dot_positions.append((x, y))
        # Full-width "treeline" band at the bottom, jittering vertically so
        # it differs from the median background in every frame
        band_top = 200 + (i % 5)
        f[band_top:, :] = 40
        frames.append(f)

    bboxes = _detect_median_subtraction(frames)

    detected = [(i, b) for i, b in enumerate(bboxes) if b is not None]
    assert len(detected) > n * 0.5, f"only {len(detected)}/{n} frames detected"
    for i, b in detected:
        cx, cy = b.center
        x, y = dot_positions[i]
        assert abs(cx - x) < 5 and abs(cy - y) < 5, (
            f"frame {i}: detection at ({cx:.0f},{cy:.0f}), dot at ({x},{y})"
        )
