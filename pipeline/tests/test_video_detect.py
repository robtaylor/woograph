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
    _merge_nearby_candidates,
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
        for i in range(50)
    }
    for i in range(10, 30):  # 20-frame dropout > default max_gap of 15
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


def test_merge_combines_fragments_of_one_object():
    """Contour fragments of one object must become a single candidate.

    Pins the fragmentation lottery: a smeared speck (or the moon's rim)
    thresholding into several contours per frame would spawn parallel
    tracks, splitting the object's temporal coverage between them.
    """
    fragments = [
        _Candidate(BBox(100, 100, 5, 4), 0.8),
        _Candidate(BBox(107, 101, 4, 4), 0.7),  # 2px gap from the first
    ]
    far_away = _Candidate(BBox(300, 50, 6, 6), 0.8)

    merged = _merge_nearby_candidates(fragments + [far_away], merge_dist=8.0)

    assert len(merged) == 2
    union = next(c for c in merged if c.bbox.x == 100)
    assert (union.bbox.w, union.bbox.h) == (11, 5)
    assert far_away in merged


def test_fragmented_object_still_wins_coverage():
    """An object drawn as two close fragments must form ONE winning track."""
    n, w, h = 60, 320, 240
    frames = []
    dot_positions = []
    for i in range(n):
        f = np.full((h, w, 3), 120, dtype=np.uint8)
        x = 40 + int(240 * i / (n - 1))
        y = 60 + int(120 * i / (n - 1))
        # Same object smeared into two blobs 6px apart
        cv2.circle(f, (x - 3, y), 2, (255, 255, 255), -1)
        cv2.circle(f, (x + 3, y), 2, (255, 255, 255), -1)
        dot_positions.append((x, y))
        if i < 15:
            cv2.circle(f, (80, 180), 25, (255, 255, 255), -1)
        frames.append(f)

    bboxes = _detect_median_subtraction(frames)

    detected = [(i, b) for i, b in enumerate(bboxes) if b is not None]
    assert len(detected) > n * 0.6, f"only {len(detected)}/{n} frames detected"
    for i, b in detected:
        cx, cy = b.center
        x, y = dot_positions[i]
        assert abs(cx - x) < 6 and abs(cy - y) < 6, (
            f"frame {i}: detection at ({cx:.0f},{cy:.0f}), object at ({x},{y})"
        )


def test_stabilisation_does_not_create_phantom_objects():
    """Border fill must not mirror real objects into the frame.

    BORDER_REFLECT_101 fill created phantom mirror-copies of the moon and
    specks in the bands exposed by stabilisation shifts; each phantom was
    tracked as a separate object, splitting coverage unpredictably across
    platforms.
    """
    from woograph.convert.video import _stabilise_frames

    n, w, h = 12, 320, 240
    frames = []
    for _ in range(n):
        f = np.full((h, w, 3), 120, dtype=np.uint8)
        cv2.circle(f, (40, 120), 10, (255, 255, 255), -1)  # near left edge
        frames.append(f)
    # Transforms with a large rightward shift expose a band on the left
    transforms = [
        np.array([[1.0, 0.0, 60.0], [0.0, 1.0, 0.0]]) for _ in range(n)
    ]

    stabilised = _stabilise_frames(frames, transforms)

    for f in stabilised:
        gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        bright = (gray > 200).astype(np.uint8)
        n_objects, _ = cv2.connectedComponents(bright)
        assert n_objects - 1 <= 1, "phantom object created by border fill"


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


def test_filter_detections_keeps_speck_near_edge():
    """A speck track riding near the border must survive the edge filter.

    Stabilisation drift can park a track 20-40px from the frame edge for
    most of a clip; a 5%-of-frame margin (96px at full HD) rejected those
    wholesale on CI. The margin only needs to clear the padded crop.
    """
    from woograph.convert.video import _filter_detections

    bboxes = [BBox(25, 400 + i, 8, 9) for i in range(40)]

    filtered = _filter_detections(bboxes, (1080, 1920), padding_factor=2.0)

    kept = sum(1 for b in filtered if b is not None)
    assert kept == 40


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
