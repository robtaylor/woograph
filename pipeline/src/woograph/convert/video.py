"""Video UAP enhancement pipeline.

Extracts a super-resolved still of a tracked object from short video clips.
Pipeline: detect → track → crop → align → weight → drizzle stack → deconvolve.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import median, mean

import cv2
import numpy as np
from numpy.typing import NDArray
from scipy.signal import fftconvolve
from skimage.registration import phase_cross_correlation
from skimage.restoration import richardson_lucy

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

logger = logging.getLogger(__name__)


@dataclass
class BBox:
    x: int
    y: int
    w: int
    h: int

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.w / 2, self.y + self.h / 2)

    @property
    def area(self) -> int:
        return self.w * self.h


@dataclass
class ProcessingMetadata:
    video_path: str
    total_frames: int
    extracted_frames: int
    detected_frames: int
    crop_size: tuple[int, int]
    scale_factor: int
    output_size: tuple[int, int]
    shifts: list[list[float]] = field(default_factory=list)
    sharpness_weights: list[float] = field(default_factory=list)
    best_frame_index: int = 0
    best_frame_sharpness: float = 0.0
    deconv_iterations: int = 0
    psf_sigma: float = 0.0
    processed_at: str = ""
    output_files: dict[str, str] = field(default_factory=dict)
    vlm_scene_count: int = 0
    vlm_footage_range: tuple[int, int] | None = None


def _extract_frames(
    video_path: Path,
    max_frames: int = 0,
    frame_step: int = 1,
) -> list[NDArray[np.uint8]]:
    """Read frames from video file.

    Args:
        video_path: Path to video file.
        max_frames: Maximum frames to extract (0 = all).
        frame_step: Extract every Nth frame.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    frames: list[NDArray[np.uint8]] = []
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % frame_step == 0:
            frames.append(frame)
        frame_idx += 1
        if max_frames > 0 and len(frames) >= max_frames:
            break

    cap.release()
    total = frame_idx
    logger.info(
        "Extracted %d frames from %d total (step=%d)",
        len(frames), total, frame_step,
    )
    assert len(frames) > 0, f"No frames extracted from {video_path}"
    return frames


def _estimate_global_motion(
    frames: list[NDArray[np.uint8]],
    mask: NDArray[np.uint8] | None = None,
) -> list[NDArray[np.float64]]:
    """Estimate cumulative camera motion using ORB feature matching.

    Returns a list of 2×3 affine transforms that map each frame back to
    the coordinate system of the reference frame (frame 0).

    Args:
        frames: Video frames.
        mask: Optional binary mask (255 = use for feature detection).
              Use this to exclude UI overlays or foreground from matching.
    """
    orb = cv2.ORB_create(nfeatures=1000)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

    # Identity for the reference frame
    identity = np.eye(2, 3, dtype=np.float64)
    cumulative: list[NDArray[np.float64]] = [identity.copy()]

    prev_gray = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
    prev_kp, prev_desc = orb.detectAndCompute(prev_gray, mask)

    failed = 0
    for i in range(1, len(frames)):
        gray = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
        kp, desc = orb.detectAndCompute(gray, mask)

        if prev_desc is None or desc is None or len(prev_kp) < 10 or len(kp) < 10:
            cumulative.append(cumulative[-1].copy())
            prev_gray, prev_kp, prev_desc = gray, kp, desc
            failed += 1
            continue

        matches = bf.knnMatch(prev_desc, desc, k=2)

        # Lowe's ratio test
        good = []
        for pair in matches:
            if len(pair) == 2:
                m, n = pair
                if m.distance < 0.75 * n.distance:
                    good.append(m)

        if len(good) < 6:
            cumulative.append(cumulative[-1].copy())
            prev_gray, prev_kp, prev_desc = gray, kp, desc
            failed += 1
            continue

        src_pts = np.float32([prev_kp[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

        # Estimate rigid affine (translation + rotation only, no scale/shear)
        # This models camera pan/tilt well
        mat, inliers = cv2.estimateAffinePartial2D(
            dst_pts, src_pts, method=cv2.RANSAC, ransacReprojThreshold=3.0,
        )

        if mat is None:
            cumulative.append(cumulative[-1].copy())
            failed += 1
        else:
            # Chain: cumulative[i] = cumulative[i-1] @ frame_transform
            # But affine is 2x3, so extend to 3x3 for multiplication
            prev_3x3 = np.vstack([cumulative[-1], [0, 0, 1]])
            cur_3x3 = np.vstack([mat, [0, 0, 1]])
            chained = prev_3x3 @ cur_3x3
            cumulative.append(chained[:2, :])

        prev_gray, prev_kp, prev_desc = gray, kp, desc

    if failed > 0:
        logger.info("Motion estimation: %d/%d frames failed feature matching",
                     failed, len(frames) - 1)
    logger.info("Estimated camera motion for %d frames", len(frames))
    return cumulative


def _stabilise_frames(
    frames: list[NDArray[np.uint8]],
    transforms: list[NDArray[np.float64]],
) -> list[NDArray[np.uint8]]:
    """Warp frames to undo camera motion, aligning all to frame 0.

    Also applies motion smoothing to avoid high-frequency jitter while
    preserving intentional pans.
    """
    h, w = frames[0].shape[:2]
    stabilised: list[NDArray[np.uint8]] = []

    # Smooth the transforms to reduce jitter but allow slow pans
    # Extract translation components
    tx = np.array([t[0, 2] for t in transforms])
    ty = np.array([t[1, 2] for t in transforms])
    angles = np.array([np.arctan2(t[1, 0], t[0, 0]) for t in transforms])

    # Moving average for smoothing (window ~0.5s at 60fps = 30 frames)
    window = min(31, len(frames) // 4)
    if window % 2 == 0:
        window += 1
    if window >= 3:
        from scipy.signal import savgol_filter
        smooth_tx = savgol_filter(tx, window, polyorder=2)
        smooth_ty = savgol_filter(ty, window, polyorder=2)
        smooth_angles = savgol_filter(angles, window, polyorder=2)
    else:
        smooth_tx, smooth_ty, smooth_angles = tx, ty, angles

    for i, frame in enumerate(frames):
        # Build smoothed transform
        cos_a = np.cos(smooth_angles[i])
        sin_a = np.sin(smooth_angles[i])
        mat = np.array([
            [cos_a, -sin_a, smooth_tx[i]],
            [sin_a, cos_a, smooth_ty[i]],
        ], dtype=np.float64)

        warped = cv2.warpAffine(
            frame, mat, (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )
        stabilised.append(warped)

    logger.info("Stabilised %d frames (smoothing window=%d)", len(frames), window)
    return stabilised


def _detect_ui_region(frames: list[NDArray[np.uint8]]) -> float:
    """Detect video player UI overlay at the bottom of the frame.

    Looks for a characteristic dark separator bar (near-black horizontal band)
    in the bottom 40% of the frame. This is common in screen recordings of
    video players — a dark bar separates the video content from the controls.

    Returns the Y-coordinate (as fraction of frame height) above which is safe.
    A value of 1.0 means no UI detected (use full frame).
    """
    sample_indices = np.linspace(0, len(frames) - 1, min(20, len(frames)), dtype=int)
    h, w = frames[0].shape[:2]

    # Compute average row brightness across sampled frames
    avg_brightness = np.zeros(h, dtype=np.float64)
    for idx in sample_indices:
        gray = cv2.cvtColor(frames[idx], cv2.COLOR_BGR2GRAY).astype(np.float64)
        avg_brightness += gray.mean(axis=1)
    avg_brightness /= len(sample_indices)

    # Scan bottom 40% looking for a dark band (mean brightness < 5)
    # followed by brighter content (UI controls)
    scan_start = int(h * 0.6)
    dark_band_start = None
    dark_band_end = None

    for row in range(scan_start, h):
        if avg_brightness[row] < 5.0:
            if dark_band_start is None:
                dark_band_start = row
            dark_band_end = row
        elif dark_band_start is not None and dark_band_end is not None:
            band_height = dark_band_end - dark_band_start + 1
            # Need a meaningful dark band (at least 5px or 1% of frame height)
            if band_height >= max(5, h * 0.01):
                # Check if there's brighter content below the dark band
                remaining = avg_brightness[dark_band_end + 1:]
                if len(remaining) > 5 and np.max(remaining) > 15:
                    cutoff = dark_band_start / h
                    logger.info(
                        "Detected player UI: dark separator at row %d (%.0f%%), "
                        "excluding bottom %.0f%% of frame",
                        dark_band_start, cutoff * 100, (1 - cutoff) * 100,
                    )
                    return cutoff
            # Reset if the band was too small
            dark_band_start = None
            dark_band_end = None

    # Also check: is the bottom 15% mostly black with a bright stripe in it?
    # (e.g. just a scrubber bar on black background)
    bottom_15 = avg_brightness[int(h * 0.85):]
    if len(bottom_15) > 0:
        mean_bottom = float(np.mean(bottom_15))
        max_bottom = float(np.max(bottom_15))
        # Dark overall but has bright elements = UI overlay on black
        if mean_bottom < 20 and max_bottom > 40:
            # Find where content brightness drops off
            for row in range(int(h * 0.7), h):
                # Use a sliding window to find brightness drop
                window = avg_brightness[row:row + 10]
                if len(window) >= 10 and np.mean(window) < 10:
                    cutoff = row / h
                    logger.info(
                        "Detected player UI (dark region): excluding below %.0f%%",
                        cutoff * 100,
                    )
                    return cutoff

    return 1.0


def _detect_and_track(
    frames: list[NDArray[np.uint8]],
    min_area: int = 100,
    warmup_frames: int = 10,
    max_jump: float = 0.0,
    roi_y_max: float = 1.0,
) -> list[BBox | None]:
    """Detect the primary moving object in each frame via MOG2 + contours.

    The background subtractor needs a warmup period. After warmup, the largest
    contour above min_area is taken as the object in each frame.

    Args:
        max_jump: Maximum distance (pixels) the object can jump between frames.
                  0 = auto (15% of frame diagonal).
        roi_y_max: Fraction of frame height to use (1.0 = full frame).
                   Excludes bottom portion (e.g. player UI).
    """
    h, w = frames[0].shape[:2]

    if max_jump <= 0:
        max_jump = 0.15 * np.sqrt(h**2 + w**2)

    # Apply CLAHE to improve detection of dim objects
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))

    bg_sub = cv2.createBackgroundSubtractorMOG2(
        history=max(warmup_frames * 2, 120),
        varThreshold=50,
        detectShadows=True,
    )
    bboxes: list[BBox | None] = []
    last_center: tuple[float, float] | None = None
    y_limit = int(h * roi_y_max)

    for i, frame in enumerate(frames):
        # Enhance contrast before background subtraction
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        fg_mask = bg_sub.apply(enhanced)
        # Threshold: 255 = foreground, 127 = shadow (ignore shadows)
        _, thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

        # Mask out UI region
        if y_limit < h:
            thresh[y_limit:] = 0

        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

        if i < warmup_frames:
            bboxes.append(None)
            continue

        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
        )

        # Score contours: prefer large area near last known position
        candidates: list[tuple[BBox, float]] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            bbox = BBox(x, y, bw, bh)

            # Skip detections in the excluded UI region
            if bbox.center[1] >= y_limit:
                continue

            score = float(area)
            if last_center is not None:
                dist = np.sqrt(
                    (bbox.center[0] - last_center[0]) ** 2
                    + (bbox.center[1] - last_center[1]) ** 2
                )
                if dist > max_jump:
                    continue  # too far from last position
                # Proximity bonus: closer to last position = better
                score *= max(0.1, 1.0 - dist / max_jump)

            candidates.append((bbox, score))

        if candidates:
            best = max(candidates, key=lambda c: c[1])[0]
            bboxes.append(best)
            last_center = best.center
        else:
            bboxes.append(None)

    detected = sum(1 for b in bboxes if b is not None)
    logger.info("Detected object in %d / %d frames", detected, len(frames))
    return bboxes


def _detect_median_subtraction(
    frames: list[NDArray[np.uint8]],
    min_area: int = 30,
    threshold: int = 15,
    roi_y_max: float = 1.0,
    max_jump: float = 0.0,
) -> list[BBox | None]:
    """Detect moving objects via temporal median subtraction.

    Computes the median frame as a background model, then finds objects in
    each frame by thresholding the absolute difference from the median.
    Much more effective than MOG2 for small objects against uniform backgrounds
    (e.g. aircraft in sky).

    Args:
        min_area: Minimum contour area in pixels.
        threshold: Absolute difference threshold (0-255).
        roi_y_max: Fraction of frame height to use (1.0 = full frame).
        max_jump: Maximum distance the object can jump between frames.
                  0 = auto (15% of frame diagonal).
    """
    h, w = frames[0].shape[:2]
    logger.debug(f"_detect_median_subtraction: w={w}, h={h}")
    if max_jump <= 0:
        max_jump = 0.15 * np.sqrt(h**2 + w**2)

    y_limit = int(h * roi_y_max)

    # Compute temporal median background
    gray_frames = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    median_bg = np.median(gray_frames, axis=0).astype(np.uint8)

    bboxes: list[BBox | None] = []
    last_center: tuple[float, float] | None = None
    last_area = 0
    frame_candidates = {}

    for i, g in enumerate(gray_frames):
        diff = cv2.absdiff(g, median_bg)
        _, thresh_mask = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)

        # Mask out UI region
        if y_limit < h:
            thresh_mask[y_limit:] = 0

        # Light morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        thresh_mask = cv2.morphologyEx(thresh_mask, cv2.MORPH_CLOSE, kernel)
        thresh_mask = cv2.morphologyEx(thresh_mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(
            thresh_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
        )

        # Score contours: prefer compact objects near last known position.
        # Compactness (fill ratio) distinguishes real objects from diffuse
        # noise like tree branches — a jet fills its bounding box densely,
        # tree edges are sparse and spread over a large bbox.
        max_bbox_area = 0.25 * w * h  # ignore contours > 25% of frame
        candidates: list[NDArray[np.int32]] = []
        for contour in contours:
            bbox = BBox(*cv2.boundingRect(contour))

            if bbox.center[1] >= y_limit:
                continue
            if bbox.area < min_area or bbox.area > max_bbox_area:
                continue

            candidates.append(contour)
        frame_candidates[i] = candidates

    # find candidates with most similar areas and smoothest centre path

    logger.debug([cv2.contourArea(contour) for i, candidates in frame_candidates.items() for contour in candidates])
    median_area = median([cv2.contourArea(contour) for i, candidates in frame_candidates.items() for contour in candidates])

    def similarity(a,b):
        return abs(a - b)/max(a, b)

    def centroid(contour):
        M = cv2.moments(contour)
        cx = int(M['m10']/M['m00'])
        cy = int(M['m01']/M['m00'])
        return (cx,cy)

    last_center = None
    for i, candidates in frame_candidates.items():
        best_bbox = None
        best_score = 0
        for contour in candidates:
            area = cv2.contourArea(contour)
            center = centroid(contour)
            bbox = BBox(*cv2.boundingRect(contour))
            score = 1.0 - abs(area - median_area)/max(area, median_area)
            if last_center:
                score *= 1.0 - similarity(center[0], last_center[0]) - similarity(center[1], last_center[1])

            logger.debug(f"score = {score}, area ={area}, center={center}, bbox.area={bbox.area}, bbox.center={bbox.center}")
            if score > best_score:
                best_bbox = bbox
                best_score = score
        if best_bbox is not None:
            logger.debug(f"frame {i}, best score = {best_score}, best area = {best_bbox.area}, best center = {best_bbox.center}")
        else:
            logger.debug(f"frame {i}, no valid detection")
        bboxes.append(best_bbox)
        last_center = center

    detected = sum(1 for b in bboxes if b is not None)
    logger.info(
        "Median subtraction: detected object in %d / %d frames (threshold=%d)",
        detected, len(frames), threshold,
    )
    return bboxes


def _filter_detections(
    bboxes: list[BBox | None],
    frame_size: tuple[int, int],
    edge_margin: float = 0.05,
    size_tolerance: float = 2.0,
) -> list[BBox | None]:
    """Filter out detections that are outliers in size or near frame edges.

    Rejects detections where:
    - The bbox centre is within edge_margin of the frame border
    - The bbox area is more than size_tolerance× the median area
    - The bbox aspect ratio flips dramatically from the median

    This removes frames where the object is leaving the frame or banking
    (changing silhouette shape), which would add noise to the stack.
    """
    h, w = frame_size
    valid_bboxes = [b for b in bboxes if b is not None]
    if len(valid_bboxes) < 5:
        return bboxes  # too few to filter

    # Compute median bbox properties
    areas = [b.w * b.h for b in valid_bboxes]
    median_area = float(np.median(areas))
    aspect_ratios = [b.w / max(b.h, 1) for b in valid_bboxes]
    median_ar = float(np.median(aspect_ratios))

    x_margin = w * edge_margin
    y_margin = h * edge_margin
    filtered: list[BBox | None] = []
    rejected = 0

    for b in bboxes:
        if b is None:
            filtered.append(None)
            continue

        cx, cy = b.center
        area = b.w * b.h
        ar = b.w / max(b.h, 1)

        # Reject if too close to frame edge
        if cx < x_margin or cx > w - x_margin or cy < y_margin or cy > h - y_margin:
            filtered.append(None)
            rejected += 1
            continue

        # Reject if area is too different from median
        if area > median_area * size_tolerance or area < median_area / size_tolerance:
            filtered.append(None)
            rejected += 1
            continue

        # Reject if aspect ratio flipped (e.g. wide→tall from banking)
        if median_ar > 1 and ar < 0.7 or median_ar < 1 and ar > 1.4:
            filtered.append(None)
            rejected += 1
            continue

        filtered.append(b)

    if rejected > 0:
        remaining = sum(1 for b in filtered if b is not None)
        logger.info(
            "Filtered %d outlier detections (edge/size/aspect), %d remain",
            rejected, remaining,
        )
    return filtered


def _filter_trajectory(
    bboxes: list[BBox | None],
    max_jump: float = 0.0,
    window: int = 7,
) -> list[BBox | None]:
    """Filter detections to follow a smooth trajectory.

    Uses a running median of bbox centres to predict where the object should
    be. Rejects detections that jump too far from the predicted position —
    these are typically the detection switching to a second object.

    Args:
        bboxes: Detection list (None = no detection in that frame).
        max_jump: Maximum allowed distance from predicted position (pixels).
                  0 = auto-compute from median inter-frame motion × 3.
        window: Running median window size (frames).
    """
    valid_indices = [i for i, b in enumerate(bboxes) if b is not None]
    if len(valid_indices) < window:
        return bboxes

    # Extract centre positions for valid detections
    centers_x = np.array([bboxes[i].center[0] for i in valid_indices])  # type: ignore[union-attr]
    centers_y = np.array([bboxes[i].center[1] for i in valid_indices])  # type: ignore[union-attr]

    # Auto-compute max_jump from typical inter-frame motion
    if max_jump <= 0:
        dx = np.abs(np.diff(centers_x))
        dy = np.abs(np.diff(centers_y))
        dists = np.sqrt(dx**2 + dy**2)
        median_step = float(np.median(dists))
        max_jump = max(median_step * 3.0, 5.0)
        logger.info("Trajectory filter: median step=%.1f px, max_jump=%.1f px",
                    median_step, max_jump)

    # Compute bbox areas for size-jump filtering
    areas = np.array([bboxes[i].w * bboxes[i].h for i in valid_indices])  # type: ignore[union-attr]
    median_area = float(np.median(areas))

    # Running median filter for predicted trajectory
    half_w = window // 2
    filtered: list[BBox | None] = list(bboxes)  # start with copy
    rejected_pos = 0
    rejected_size = 0

    for idx_pos, frame_idx in enumerate(valid_indices):
        # Window of nearby valid detections
        lo = max(0, idx_pos - half_w)
        hi = min(len(valid_indices), idx_pos + half_w + 1)
        pred_x = float(np.median(centers_x[lo:hi]))
        pred_y = float(np.median(centers_y[lo:hi]))

        actual_x, actual_y = centers_x[idx_pos], centers_y[idx_pos]
        dist = np.sqrt((actual_x - pred_x)**2 + (actual_y - pred_y)**2)

        if dist > max_jump:
            filtered[frame_idx] = None
            rejected_pos += 1
            continue

        # Reject frames with sudden bbox size jump vs local median
        local_areas = areas[lo:hi]
        local_median_area = float(np.median(local_areas))
        area_ratio = areas[idx_pos] / max(local_median_area, 1.0)
        if area_ratio > 1.5 or area_ratio < 0.667:
            filtered[frame_idx] = None
            rejected_size += 1

    rejected = rejected_pos + rejected_size
    if rejected > 0:
        remaining = sum(1 for b in filtered if b is not None)
        logger.info("Trajectory filter rejected %d detections (%d position jumps > %.0f px, %d size jumps), %d remain",
                    rejected, rejected_pos, max_jump, rejected_size, remaining)
    return filtered


def _crop_with_padding(
    frames: list[NDArray[np.uint8]],
    bboxes: list[BBox | None],
    padding_factor: float = 2.0,
    uniform_size: tuple[int, int] | None = None,
    float_centers: list[tuple[float, float] | None] | None = None,
) -> tuple[list[NDArray[np.uint8]], tuple[int, int], list[tuple[float, float]], list[tuple[int, int]], list[int]]:
    """Crop frames around detected object with padding.

    All crops are resized to a uniform size (the median bbox size * padding).
    Returns (crops, crop_size, bbox_centers, crop_corners, frame_indices)
    where crop_corners are the actual (x1, y1) integer positions used for
    slicing and frame_indices are the original frame numbers.

    If float_centers is provided, those exact float values are returned as
    the centres (for sub-pixel offset calculation) instead of recomputing
    from the integer bbox coordinates.
    """
    valid_indices = [i for i, b in enumerate(bboxes) if b is not None]
    valid = [(frames[i], bboxes[i]) for i in valid_indices]
    assert len(valid) > 0, "No frames with detected objects to crop"

    if uniform_size is None:
        widths = [b.w for _, b in valid]  # type: ignore[union-attr]
        heights = [b.h for _, b in valid]  # type: ignore[union-attr]
        crop_w = int(np.median(widths) * padding_factor)
        crop_h = int(np.median(heights) * padding_factor)
        # Make even for easier upscaling
        crop_w += crop_w % 2
        crop_h += crop_h % 2
        uniform_size = (crop_h, crop_w)

    fixed_h, fixed_w = uniform_size
    crops: list[NDArray[np.uint8]] = []
    centers: list[tuple[float, float]] = []
    crop_corners: list[tuple[int, int]] = []  # actual (x1, y1) used for slicing

    for idx in valid_indices:
        frame = frames[idx]
        bbox = bboxes[idx]
        assert bbox is not None
        h, w = frame.shape[:2]
        cx, cy = bbox.center

        # Compute crop region, clamped to frame bounds
        x1 = int(max(0, cx - fixed_w / 2))
        y1 = int(max(0, cy - fixed_h / 2))
        x2 = int(min(w, x1 + fixed_w))
        y2 = int(min(h, y1 + fixed_h))

        crop = frame[y1:y2, x1:x2]

        crops.append(crop)
        crop_corners.append((x1, y1))
        # Use exact float centre if available, else fall back to bbox.center
        if float_centers is not None and float_centers[idx] is not None:
            centers.append(float_centers[idx])  # type: ignore[arg-type]
        else:
            centers.append((cx, cy))

    logger.info("Cropped %d frames to %dx%d", len(crops), fixed_w, fixed_h)
    return crops, uniform_size, centers, crop_corners, valid_indices


def _subtract_background(
    frames: list[NDArray[np.uint8]],
    bboxes: list[BBox | None],
    crop_size: tuple[int, int],
) -> NDArray[np.float64]:
    """Compute median background and return it as a full-frame image.

    The median is computed over all frames (stabilised), giving a static
    background model.  Callers can crop regions from this to subtract
    from individual object crops.
    """
    gray_stack = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    if len(gray_stack) > 100:
        median_bg = np.median(gray_stack[::3], axis=0)
    else:
        median_bg = np.median(gray_stack, axis=0)
    # Return as colour (3-channel) float for subtraction from BGR crops
    return np.stack([median_bg] * 3, axis=-1)


def _crop_and_subtract_bg(
    frames: list[NDArray[np.uint8]],
    bboxes: list[BBox | None],
    bg_model: NDArray[np.float64],
    crop_size: tuple[int, int],
) -> list[NDArray[np.float64]]:
    """Crop detected regions and subtract median background.

    For each detected frame, crops the same region from both the frame
    and the background model, subtracts, and keeps the absolute
    difference.  This isolates the moving object from the static scene.
    """
    crop_h, crop_w = crop_size
    valid = [(f, b) for f, b in zip(frames, bboxes) if b is not None]
    fg_crops: list[NDArray[np.float64]] = []

    for frame, bbox in valid:
        assert bbox is not None
        h, w = frame.shape[:2]
        cx, cy = bbox.center

        x1 = int(max(0, cx - crop_w / 2))
        y1 = int(max(0, cy - crop_h / 2))
        x2 = int(min(w, x1 + crop_w))
        y2 = int(min(h, y1 + crop_h))

        frame_crop = frame[y1:y2, x1:x2].astype(np.float64)
        bg_crop = bg_model[y1:y2, x1:x2]

        # Subtract background — object pixels remain, background → ~0
        fg = np.abs(frame_crop - bg_crop)

        # Pad if crop is smaller than desired
        if fg.shape[0] != crop_h or fg.shape[1] != crop_w:
            padded = np.zeros((crop_h, crop_w, 3), dtype=np.float64)
            ph = min(fg.shape[0], crop_h)
            pw = min(fg.shape[1], crop_w)
            padded[:ph, :pw] = fg[:ph, :pw]
            fg = padded

        fg_crops.append(fg)

    logger.info("Background-subtracted %d crops (%dx%d)", len(fg_crops), crop_w, crop_h)
    return fg_crops


def _save_crop_video(
    crops: list[NDArray],
    output_path: Path,
    fps: int = 10,
    scale_up: int = 4,
    raw_centers: list[tuple[float, float]] | None = None,
    crop_corners: list[tuple[int, int]] | None = None,
    frame_indices: list[int] | None = None,
) -> None:
    """Save a diagnostic video of aligned crops.

    Each crop is scaled up for visibility and annotated with original frame
    index.  If *raw_centers* and *crop_corners* are provided, a crosshair
    is drawn at the bbox centroid position within each crop so drift is
    visible.
    """
    if not crops:
        return

    sample = np.clip(crops[0], 0, 255).astype(np.uint8)
    h, w = sample.shape[:2]
    out_h, out_w = h * scale_up, w * scale_up

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (out_w, out_h))

    for i, crop in enumerate(crops):
        frame = np.clip(crop, 0, 255).astype(np.uint8)
        frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_NEAREST)
        label = f"F{frame_indices[i]}" if frame_indices is not None else f"#{i}"
        cv2.putText(
            frame, label, (5, 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1,
        )
        # Draw bbox centroid within crop as a crosshair
        if raw_centers is not None and crop_corners is not None:
            cx, cy = raw_centers[i]
            x1, y1 = crop_corners[i]
            # Centroid position relative to crop origin, scaled up
            rel_x = int((cx - x1) * scale_up)
            rel_y = int((cy - y1) * scale_up)
            arm = 6  # crosshair arm length in pixels
            colour = (0, 0, 255)  # red
            cv2.line(frame, (rel_x - arm, rel_y), (rel_x + arm, rel_y), colour, 1)
            cv2.line(frame, (rel_x, rel_y - arm), (rel_x, rel_y + arm), colour, 1)
        writer.write(frame)

    writer.release()
    logger.info("Saved crop video: %s (%d frames, %dx%d)", output_path, len(crops), out_w, out_h)


def _save_debug_video(
    frames: list[NDArray[np.uint8]],
    raw_bboxes: list[BBox | None],
    filtered_bboxes: list[BBox | None],
    output_path: Path,
    fps: int = 30,
) -> None:
    """Save full-size video with bounding boxes, centroids, and frame numbers.

    Shows raw detections in green (kept) or red (filtered out).
    Filtered frames are labelled "FILTERED".
    """
    if not frames:
        return

    h, w = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (w, h))

    for i, frame in enumerate(frames):
        annotated = frame.copy()
        raw_bb = raw_bboxes[i] if i < len(raw_bboxes) else None
        kept_bb = filtered_bboxes[i] if i < len(filtered_bboxes) else None

        # Determine if this frame was filtered out
        was_filtered = raw_bb is not None and kept_bb is None

        # Frame number (top-left)
        label_color = (0, 0, 255) if was_filtered else (255, 255, 255)
        status = f"#{i} FILTERED" if was_filtered else f"#{i}"
        cv2.putText(
            annotated, status, (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, label_color, 2,
        )

        if raw_bb is not None:
            # Box colour: green=kept, red=filtered
            box_color = (0, 0, 255) if was_filtered else (0, 255, 0)
            cv2.rectangle(
                annotated,
                (raw_bb.x, raw_bb.y),
                (raw_bb.x + raw_bb.w, raw_bb.y + raw_bb.h),
                box_color, 1,
            )
            # Centroid
            cx, cy = raw_bb.center
            cv2.circle(annotated, (int(cx), int(cy)), 3, (0, 0, 255), -1)
            # Label: bbox size and centre
            info = f"{raw_bb.w}x{raw_bb.h} ({cx:.1f},{cy:.1f})"
            cv2.putText(
                annotated, info, (raw_bb.x, raw_bb.y - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, box_color, 1,
            )

        writer.write(annotated)

    writer.release()
    logger.info("Saved debug video: %s (%d frames, %dx%d)", output_path, len(frames), w, h)


def _estimate_crop_transform(
    ref_gray: NDArray[np.uint8],
    crop_gray: NDArray[np.uint8],
    orb: cv2.ORB,
    matcher: cv2.BFMatcher,
    min_matches: int = 4,
) -> NDArray[np.float64] | None:
    """Estimate similarity transform between two crops using ORB features.

    Returns a 2x3 affine matrix (similarity: rotation + scale + translation)
    or None if insufficient matches.
    """
    kp1, des1 = orb.detectAndCompute(ref_gray, None)
    kp2, des2 = orb.detectAndCompute(crop_gray, None)

    if des1 is None or des2 is None or len(kp1) < min_matches or len(kp2) < min_matches:
        return None

    matches = matcher.knnMatch(des1, des2, k=2)

    # Lowe's ratio test
    good = []
    for pair in matches:
        if len(pair) == 2:
            m, n = pair
            if m.distance < 0.75 * n.distance:
                good.append(m)

    if len(good) < min_matches:
        return None

    src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

    # estimateAffinePartial2D: rotation + scale + translation (4 DOF)
    mat, inliers = cv2.estimateAffinePartial2D(
        dst_pts, src_pts,  # dst→src because we want to warp crop to match ref
        method=cv2.RANSAC,
        ransacReprojThreshold=3.0,
    )

    if mat is None or inliers is None:
        return None

    inlier_count = int(inliers.sum())
    if inlier_count < min_matches:
        return None

    return mat


def _decompose_similarity(mat: NDArray[np.float64]) -> tuple[float, float, float, float]:
    """Extract (scale, angle_deg, tx, ty) from a 2x3 similarity matrix."""
    a, b = mat[0, 0], mat[0, 1]
    scale = float(np.sqrt(a**2 + b**2))
    angle = float(np.degrees(np.arctan2(b, a)))
    tx, ty = float(mat[0, 2]), float(mat[1, 2])
    return scale, angle, tx, ty


def _estimate_silhouette_transform(
    ref_gray: NDArray[np.uint8],
    crop_gray: NDArray[np.uint8],
) -> NDArray[np.float64] | None:
    """Estimate similarity transform by matching silhouette contours.

    Uses image moments to find the orientation and scale of the dark
    object in each crop, then computes the transform to align them.
    Works well for small, featureless silhouettes where ORB fails.
    """
    h, w = ref_gray.shape[:2]

    def _get_silhouette_props(gray: NDArray[np.uint8]) -> tuple[float, float, float, float, float] | None:
        """Extract (cx, cy, angle, major_axis, minor_axis) from darkest region."""
        # Threshold to isolate dark object against lighter background
        median_val = float(np.median(gray))
        thresh_val = max(median_val - 15, 10)
        _, mask = cv2.threshold(gray, int(thresh_val), 255, cv2.THRESH_BINARY_INV)

        # Clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        # Largest contour
        cnt = max(contours, key=cv2.contourArea)
        if cv2.contourArea(cnt) < 20:
            return None

        # Fit ellipse if enough points
        if len(cnt) >= 5:
            ellipse = cv2.fitEllipse(cnt)
            (cx, cy), (major, minor), angle = ellipse
            return cx, cy, angle, major, minor

        # Fall back to moments
        moments = cv2.moments(cnt)
        if moments["m00"] < 1:
            return None
        cx = moments["m10"] / moments["m00"]
        cy = moments["m01"] / moments["m00"]
        # Orientation from central moments
        mu20 = moments["mu20"]
        mu02 = moments["mu02"]
        mu11 = moments["mu11"]
        angle = 0.5 * np.degrees(np.arctan2(2 * mu11, mu20 - mu02))
        return cx, cy, float(angle), 0.0, 0.0

    ref_props = _get_silhouette_props(ref_gray)
    crop_props = _get_silhouette_props(crop_gray)

    if ref_props is None or crop_props is None:
        return None

    ref_cx, ref_cy, ref_angle, ref_major, ref_minor = ref_props
    crop_cx, crop_cy, crop_angle, crop_major, crop_minor = crop_props

    # Compute relative rotation
    d_angle = crop_angle - ref_angle
    # Normalize to [-90, 90] to avoid 180° ambiguity in ellipse orientation
    while d_angle > 90:
        d_angle -= 180
    while d_angle < -90:
        d_angle += 180

    # Compute relative scale from ellipse axes
    if ref_major > 0 and crop_major > 0:
        scale_ratio = crop_major / ref_major
    else:
        scale_ratio = 1.0

    # Build similarity transform: rotate around crop centre, then translate
    # to match reference centre
    center = (w / 2.0, h / 2.0)
    # getRotationMatrix2D applies rotation around a point with scale
    rot_mat = cv2.getRotationMatrix2D(center, -d_angle, 1.0 / scale_ratio)

    # After rotation, the crop centre maps to a new position.
    # Adjust translation so the object centres align.
    # The rotation matrix maps crop→rotated, we need to add translation
    # so that crop_centre → ref_centre.
    rotated_cx = rot_mat[0, 0] * crop_cx + rot_mat[0, 1] * crop_cy + rot_mat[0, 2]
    rotated_cy = rot_mat[1, 0] * crop_cx + rot_mat[1, 1] * crop_cy + rot_mat[1, 2]
    rot_mat[0, 2] += ref_cx - rotated_cx
    rot_mat[1, 2] += ref_cy - rotated_cy

    return rot_mat


def _align_crops(
    crops: list[NDArray[np.uint8]],
    upsample_factor: int = 20,
    max_shift_fraction: float = 0.5,
    max_scale_change: float = 0.3,
    max_rotation_deg: float = 15.0,
) -> tuple[list[NDArray[np.float64]], list[NDArray[np.float64]], list[NDArray[np.float64]]]:
    """Align crops using similarity transforms (rotation + scale + translation).

    First attempts ORB feature matching for a full similarity transform.
    Falls back to phase cross-correlation (translation only) when features
    are insufficient — common for small featureless objects.

    After geometric alignment, rejects crops that differ too much from the
    reference (catches yaw/pitch changes that no 2D warp can fix).

    Returns:
        aligned: List of aligned crops (float64, 0-255 range) — for diagnostics.
        originals: List of original (unwarped) crops that passed filtering.
                   These have pristine pixel values (no interpolation blur).
        transforms: List of 2x3 affine matrices mapping each crop to reference.
                    Identity matrix for the reference crop.
    """
    assert len(crops) > 0

    h, w = crops[0].shape[:2]
    max_shift_px = max_shift_fraction * min(h, w)

    # ORB feature detector and brute-force matcher
    orb = cv2.ORB.create(nfeatures=500)
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

    ref_gray_u8 = cv2.cvtColor(crops[0], cv2.COLOR_BGR2GRAY)
    ref_gray_f = ref_gray_u8.astype(np.float64)

    identity = np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float64)
    aligned: list[NDArray[np.float64]] = [crops[0].astype(np.float64)]
    originals: list[NDArray[np.float64]] = [crops[0].astype(np.float64)]
    transforms: list[NDArray[np.float64]] = [identity]

    rejected_geom = 0
    rejected_diff = 0
    feature_aligned = 0
    silhouette_aligned = 0
    phase_aligned = 0

    # (warped_crop, original_crop_f64, transform)
    candidates: list[tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]] = []

    for crop in crops[1:]:
        crop_gray_u8 = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        mat: NDArray[np.float64] | None = None
        method = ""

        # Try 1: ORB feature-based similarity transform
        mat = _estimate_crop_transform(ref_gray_u8, crop_gray_u8, orb, matcher)
        if mat is not None:
            method = "feature"

        # Try 2: Silhouette-based rotation + scale (for small featureless objects)
        if mat is None:
            mat = _estimate_silhouette_transform(ref_gray_u8, crop_gray_u8)
            if mat is not None:
                method = "silhouette"

        # Apply transform if we got one (feature or silhouette)
        if mat is not None:
            scale_est, angle, tx, ty = _decompose_similarity(mat)

            # Sanity check: reject extreme transforms
            if (abs(scale_est - 1.0) > max_scale_change
                    or abs(angle) > max_rotation_deg
                    or abs(tx) > max_shift_px
                    or abs(ty) > max_shift_px):
                rejected_geom += 1
                continue

            # Coarse warp: apply rotation + scale
            warped = cv2.warpAffine(
                crop.astype(np.float64), mat, (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0.0, 0.0, 0.0),
            )

            # Sub-pixel refinement: phase correlation on the warped result
            warped_gray = cv2.cvtColor(
                np.clip(warped, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY,
            ).astype(np.float64)
            residual, _, _ = phase_cross_correlation(
                ref_gray_f, warped_gray, upsample_factor=upsample_factor,
            )
            res_dy, res_dx = float(residual[0]), float(residual[1])

            # Apply residual translation if non-trivial
            if abs(res_dy) > 0.01 or abs(res_dx) > 0.01:
                refine_mat = np.array([[1, 0, res_dx], [0, 1, res_dy]], dtype=np.float64)
                warped = cv2.warpAffine(
                    warped, refine_mat, (w, h),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_CONSTANT,
                    borderValue=(0.0, 0.0, 0.0),
                )
                # Compose into the full transform for IBP
                full_3x3 = np.eye(3, dtype=np.float64)
                full_3x3[:2, :] = mat
                refine_3x3 = np.eye(3, dtype=np.float64)
                refine_3x3[:2, :] = refine_mat
                composed = refine_3x3 @ full_3x3
                mat = composed[:2, :]

            crop_f = crop.astype(np.float64)
            candidates.append((warped, crop_f, mat))
            if method == "feature":
                feature_aligned += 1
            else:
                silhouette_aligned += 1

        else:
            # Fallback: Phase cross-correlation (translation only)
            crop_gray_f = crop_gray_u8.astype(np.float64)
            shift, _error, _phasediff = phase_cross_correlation(
                ref_gray_f, crop_gray_f, upsample_factor=upsample_factor,
            )

            shift_mag = np.sqrt(shift[0]**2 + shift[1]**2)
            if shift_mag > max_shift_px:
                rejected_geom += 1
                continue

            dy, dx = float(shift[0]), float(shift[1])
            mat_shift = np.array([[1, 0, dx], [0, 1, dy]], dtype=np.float64)
            warped = cv2.warpAffine(
                crop.astype(np.float64), mat_shift, (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0.0, 0.0, 0.0),
            )
            crop_f = crop.astype(np.float64)
            candidates.append((warped, crop_f, mat_shift))
            phase_aligned += 1

    # Second pass: reject aligned crops that differ too much from reference.
    # This catches yaw/pitch changes that no 2D transform can fix.
    if candidates:
        ref_f = aligned[0]
        diffs = []
        for warped, _orig, _mat in candidates:
            mse = float(np.mean((warped - ref_f) ** 2))
            diffs.append(mse)
        median_diff = float(np.median(diffs))
        diff_threshold = max(median_diff * 3.0, 100.0)
        for (warped, orig, mat), mse in zip(candidates, diffs):
            if mse > diff_threshold:
                rejected_diff += 1
                continue
            aligned.append(warped)
            originals.append(orig)
            transforms.append(mat)

    if rejected_geom > 0:
        logger.info("Rejected %d crops (geometry outliers)", rejected_geom)
    if rejected_diff > 0 and candidates:
        logger.info("Rejected %d crops with high diff (threshold=%.0f, median=%.0f)",
                    rejected_diff, diff_threshold, median_diff)
    logger.info(
        "Aligned %d crops (%d feature, %d silhouette, %d phase-corr)",
        len(aligned), feature_aligned, silhouette_aligned, phase_aligned,
    )
    return aligned, originals, transforms


def _align_crops_by_detection(
    crops: list[NDArray[np.uint8]],
    bbox_centers: list[tuple[float, float]],
    ref_idx: int = 0,
    upsample_factor: int = 20,
    max_mse_ratio: float = 3.0,
) -> tuple[list[NDArray[np.float64]], list[tuple[float, float]]]:
    """Align crops using detection coordinates + sub-pixel phase correlation.

    Instead of estimating rotation/scale from silhouettes (error-prone for
    small objects), uses the bbox center positions directly as the coarse
    shift, then refines to sub-pixel with phase cross-correlation.

    This is translation-only — no rotation or scale estimation — which avoids
    interpolation blur from warpAffine and is appropriate when the object's
    apparent rotation/scale change is small between frames.

    Args:
        crops: Raw crops (uint8 BGR).
        bbox_centers: (cx, cy) for each crop in stabilized frame coordinates.
        ref_idx: Index of the reference crop (usually sharpest).
        upsample_factor: Phase correlation sub-pixel precision.
        max_mse_ratio: Reject crops with MSE > median * this ratio.

    Returns:
        aligned: Filtered crops as float64 (shifted to align with reference).
        shifts: (dy, dx) sub-pixel shifts for each surviving crop.
    """
    assert len(crops) == len(bbox_centers)
    assert len(crops) > 0

    h, w = crops[0].shape[:2]

    # Compute background color (median of all crop borders) for shift padding
    border_pixels = []
    for crop in crops:
        border_pixels.extend([
            crop[0, :].mean(axis=0),   # top row
            crop[-1, :].mean(axis=0),  # bottom row
            crop[:, 0].mean(axis=0),   # left col
            crop[:, -1].mean(axis=0),  # right col
        ])
    bg_color = np.median(border_pixels, axis=0)  # BGR
    logger.info("Background color (BGR): [%.0f, %.0f, %.0f]",
                bg_color[0], bg_color[1], bg_color[2])

    # The crops are ALREADY centered on the bbox centre, so the coarse
    # alignment is done by the cropping step itself. The only shifts we
    # need are the sub-pixel fractional parts.
    #
    # Each crop is extracted at:
    #   x1 = int(cx - crop_w/2), y1 = int(cy - crop_h/2)
    # So the object centre within the crop is at:
    #   in_crop_x = cx - x1 = cx - int(cx - crop_w/2)
    #   in_crop_y = cy - y1 = cy - int(cy - crop_h/2)
    #
    # For the reference frame:
    #   ref_in_crop_x, ref_in_crop_y
    #
    # Shift = ref_in_crop - crop_in_crop (sub-pixel difference)
    ref_cx, ref_cy = bbox_centers[ref_idx]
    ref_in_x = ref_cx - int(ref_cx - w / 2)
    ref_in_y = ref_cy - int(ref_cy - h / 2)

    ref_gray = cv2.cvtColor(crops[ref_idx], cv2.COLOR_BGR2GRAY).astype(np.float64)

    # Phase 1: compute shifts and aligned crops
    candidates: list[tuple[NDArray[np.float64], tuple[float, float], int]] = []

    for i, (crop, (cx, cy)) in enumerate(zip(crops, bbox_centers)):
        # Sub-pixel shift from detection coordinates.
        # Crops are already coarse-aligned by centering on bbox.
        # The fractional pixel offset is what differs between crops.
        in_x = cx - int(cx - w / 2)
        in_y = cy - int(cy - h / 2)
        frac_dx = ref_in_x - in_x
        frac_dy = ref_in_y - in_y

        # Phase correlation for sub-pixel refinement within the crop.
        # Use a central mask to focus on the object region, not background.
        crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float64)

        # First apply fractional shift, then refine
        if abs(frac_dy) > 0.01 or abs(frac_dx) > 0.01:
            frac_mat = np.array([[1, 0, frac_dx], [0, 1, frac_dy]], dtype=np.float64)
            shifted_gray = cv2.warpAffine(
                crop_gray, frac_mat, (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )
        else:
            shifted_gray = crop_gray

        # Phase correlation residual — capped to ±1.5px since the detection
        # coordinates should be accurate to ~1px
        residual, _, _ = phase_cross_correlation(
            ref_gray, shifted_gray, upsample_factor=upsample_factor,
        )
        res_dy, res_dx = float(residual[0]), float(residual[1])
        max_residual = 1.5
        res_dy = max(-max_residual, min(max_residual, res_dy))
        res_dx = max(-max_residual, min(max_residual, res_dx))

        total_dy = frac_dy + res_dy
        total_dx = frac_dx + res_dx

        # Apply total shift
        shift_mat = np.array([[1, 0, total_dx], [0, 1, total_dy]], dtype=np.float64)
        aligned_crop = cv2.warpAffine(
            crop.astype(np.float64), shift_mat, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

        candidates.append((aligned_crop, (total_dy, total_dx), i))

    # Phase 2: reject high-MSE outliers
    ref_f = crops[ref_idx].astype(np.float64)
    mses = []
    for aligned_crop, _, _ in candidates:
        mse = mean((aligned_crop - ref_f) ** 2)
        mses.append(mse)
    median_mse = median(mses)
    threshold = max(median_mse * max_mse_ratio, 100.0)

    aligned: list[NDArray[np.float64]] = []
    shifts: list[tuple[float, float]] = []
    rejected = 0
    for (acrop, shift, idx), mse in zip(candidates, mses):
        if mse > threshold:
            rejected += 1
            continue
        aligned.append(acrop)
        shifts.append(shift)

    if rejected > 0:
        logger.info("Rejected %d crops with high MSE (threshold=%.0f, median=%.0f)",
                    rejected, threshold, median_mse)
    logger.info("Aligned %d crops by detection coordinates (translation-only, "
                "sub-pixel refined)", len(aligned))
    return aligned, shifts


def _compute_sharpness(crops: list[NDArray]) -> list[float]:
    """Compute sharpness of each crop via Laplacian variance."""
    weights: list[float] = []
    for crop in crops:
        if crop.dtype != np.uint8:
            gray = cv2.cvtColor(
                np.clip(crop, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY,
            )
        else:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        weights.append(float(lap.var()))

    # Normalize to sum to 1
    total = sum(weights)
    if total > 0:
        weights = [w / total for w in weights]

    return weights


def _weighted_average_init(
    aligned: list[NDArray[np.float64]],
    weights: list[float],
    scale: int = 2,
) -> NDArray[np.float64]:
    """Weighted average initial HR estimate for IBP.

    Simple shift-and-add: upscale each frame, accumulate weighted by sharpness.
    This provides a reasonable starting point for iterative refinement.
    """
    h, w, c = aligned[0].shape
    out_h, out_w = h * scale, w * scale

    canvas = np.zeros((out_h, out_w, c), dtype=np.float64)
    weight_map = np.zeros((out_h, out_w), dtype=np.float64)

    for crop, wt in zip(aligned, weights):
        if wt <= 0:
            continue

        upscaled = cv2.resize(
            crop, (out_w, out_h), interpolation=cv2.INTER_CUBIC,
        )
        mask = np.any(upscaled > 1.0, axis=2).astype(np.float64)

        for ch in range(c):
            canvas[:, :, ch] += upscaled[:, :, ch] * wt * mask
        weight_map += wt * mask

    weight_map = np.maximum(weight_map, 1e-10)
    for ch in range(c):
        canvas[:, :, ch] /= weight_map

    return canvas


def _warp_shift(
    image: NDArray[np.float64],
    dy: float,
    dx: float,
) -> NDArray[np.float64]:
    """Sub-pixel shift using cv2.warpAffine (much faster than ndimage.shift)."""
    h, w = image.shape[:2]
    mat = np.float64([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(
        image, mat, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0.0,
    )


def _fft_shift_blur(
    image_fft: NDArray[np.complex128],
    dy: float,
    dx: float,
    otf: NDArray[np.complex128],
) -> NDArray[np.complex128]:
    """Apply shift + blur in frequency domain (single multiply).

    Shift is a phase ramp: exp(-j2π(u·dx + v·dy))
    Blur is OTF multiplication.
    Combined into one element-wise multiply.
    """
    h, w = image_fft.shape[:2]
    # Frequency grids (matching fft2 layout)
    v = np.fft.fftfreq(h).reshape(-1, 1)
    u = np.fft.fftfreq(w).reshape(1, -1)
    phase_ramp = np.exp(-2j * np.pi * (v * dy + u * dx))

    # Combined: OTF * phase_ramp
    kernel = otf * phase_ramp

    if image_fft.ndim == 3:
        return image_fft * kernel[:, :, np.newaxis]
    return image_fft * kernel


def _scale_transform_to_hr(
    mat: NDArray[np.float64],
    scale: int,
) -> NDArray[np.float64]:
    """Scale a 2x3 affine matrix from LR to HR pixel coordinates.

    A similarity transform at LR scale needs its translation components
    multiplied by the scale factor. Rotation and scale components stay
    the same since they're ratios.
    """
    hr_mat = mat.copy()
    hr_mat[0, 2] *= scale  # tx
    hr_mat[1, 2] *= scale  # ty
    return hr_mat


def _invert_affine(mat: NDArray[np.float64]) -> NDArray[np.float64]:
    """Invert a 2x3 affine transform.

    Extends to 3x3 (adding [0,0,1] row), inverts, returns top 2 rows.
    """
    full = np.eye(3, dtype=np.float64)
    full[:2, :] = mat
    inv = np.linalg.inv(full)
    return inv[:2, :]


def _simulate_lr(
    hr: NDArray[np.float64],
    shift: tuple[float, float],
    scale: int,
    psf: NDArray[np.float64],
    *,
    hr_fft: NDArray[np.complex128] | None = None,
    otf: NDArray[np.complex128] | None = None,
) -> NDArray[np.float64]:
    """Simulate the LR observation from an HR estimate (translation-only).

    Forward model: HR → blur(PSF) → shift → downsample → LR
    Uses FFT for shift+blur when hr_fft and otf are provided.
    """
    h_hr, w_hr = hr.shape[:2]
    h_lr, w_lr = h_hr // scale, w_hr // scale

    if hr_fft is not None and otf is not None:
        dy, dx = shift[0] * scale, shift[1] * scale
        shifted_blurred_fft = _fft_shift_blur(hr_fft, dy, dx, otf)
        if hr.ndim == 3:
            shifted_blurred = np.real(np.fft.ifft2(shifted_blurred_fft, axes=(0, 1)))
        else:
            shifted_blurred = np.real(np.fft.ifft2(shifted_blurred_fft))
        return cv2.resize(shifted_blurred, (w_lr, h_lr), interpolation=cv2.INTER_AREA)

    blurred = cv2.filter2D(hr, cv2.CV_64F, psf)
    dy, dx = shift[0] * scale, shift[1] * scale
    shifted = _warp_shift(blurred, dy, dx)
    return cv2.resize(shifted, (w_lr, h_lr), interpolation=cv2.INTER_AREA)


def _back_project(
    error: NDArray[np.float64],
    shift: tuple[float, float],
    scale: int,
    psf: NDArray[np.float64],
    *,
    otf_conj: NDArray[np.complex128] | None = None,
) -> NDArray[np.float64]:
    """Back-project a LR error into HR space (translation-only).

    Adjoint: LR error → upsample → un-shift → blur(PSF^T) → HR correction
    Uses FFT for un-shift + adjoint blur when otf_conj is provided.
    """
    h_lr, w_lr = error.shape[:2]
    h_hr, w_hr = h_lr * scale, w_lr * scale

    upsampled = cv2.resize(error, (w_hr, h_hr), interpolation=cv2.INTER_CUBIC)

    if otf_conj is not None:
        dy, dx = -shift[0] * scale, -shift[1] * scale
        if upsampled.ndim == 3:
            up_fft = np.fft.fft2(upsampled, axes=(0, 1))
        else:
            up_fft = np.fft.fft2(upsampled)
        result_fft = _fft_shift_blur(up_fft, dy, dx, otf_conj)
        if upsampled.ndim == 3:
            return np.real(np.fft.ifft2(result_fft, axes=(0, 1)))
        return np.real(np.fft.ifft2(result_fft))

    psf_t = psf[::-1, ::-1]
    dy, dx = -shift[0] * scale, -shift[1] * scale
    unshifted = _warp_shift(upsampled, dy, dx)
    return cv2.filter2D(unshifted, cv2.CV_64F, psf_t)


def _simulate_lr_affine(
    hr: NDArray[np.float64],
    transform: NDArray[np.float64],
    scale: int,
    psf: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Simulate the LR observation from an HR estimate (affine forward model).

    Forward model: HR (ref coords) → inverse_warp (ref→crop) → blur(PSF) → downsample → LR
    The transform maps crop→ref, so we invert it to go ref→crop.
    """
    h_hr, w_hr = hr.shape[:2]
    h_lr, w_lr = h_hr // scale, w_hr // scale

    # Scale transform to HR coordinates and invert (ref→crop direction)
    hr_mat = _scale_transform_to_hr(transform, scale)
    inv_mat = _invert_affine(hr_mat)

    # Warp HR to this crop's coordinate frame
    warped = cv2.warpAffine(
        hr, inv_mat, (w_hr, h_hr),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0.0, 0.0, 0.0) if hr.ndim == 3 else (0.0,),
    )

    # Blur
    blurred = cv2.filter2D(warped, cv2.CV_64F, psf)

    # Downsample
    return cv2.resize(blurred, (w_lr, h_lr), interpolation=cv2.INTER_AREA)


def _back_project_affine(
    error: NDArray[np.float64],
    transform: NDArray[np.float64],
    scale: int,
    psf: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Back-project a LR error into HR space (affine adjoint model).

    Adjoint: LR error (crop coords) → upsample → blur(PSF^T) → warp(crop→ref) → HR correction
    The transform maps crop→ref, which is the direction we need to go back to HR space.
    """
    h_lr, w_lr = error.shape[:2]
    h_hr, w_hr = h_lr * scale, w_lr * scale

    # Upsample
    upsampled = cv2.resize(error, (w_hr, h_hr), interpolation=cv2.INTER_CUBIC)

    # Blur with transposed PSF
    psf_t = psf[::-1, ::-1]
    blurred = cv2.filter2D(upsampled, cv2.CV_64F, psf_t)

    # Warp crop→ref (forward transform brings error back to ref/HR coords)
    hr_mat = _scale_transform_to_hr(transform, scale)
    return cv2.warpAffine(
        blurred, hr_mat, (w_hr, h_hr),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0.0, 0.0, 0.0) if blurred.ndim == 3 else (0.0,),
    )


def _ibp_super_resolve(
    observations: list[NDArray[np.float64]],
    transforms: list[NDArray[np.float64]],
    weights: list[float],
    scale: int = 2,
    iterations: int = 20,
    psf_sigma: float = 1.0,
    learning_rate: float = 0.1,
    aligned_for_init: list[NDArray[np.float64]] | None = None,
) -> NDArray[np.float64]:
    """Iterative Back-Projection super-resolution with affine forward model.

    Solves for the HR image that, when affine-warped + blurred + downsampled,
    best reproduces all observed LR frames. Uses original (unwarped) pixel
    data for the observation model to avoid interpolation blur.

    Args:
        observations: Original LR frames (float64, 0-255) — pristine pixels.
        transforms: 2x3 affine matrices (crop→ref) from alignment.
        weights: Per-frame sharpness weights (higher = more influence).
        scale: Upscaling factor.
        iterations: Number of IBP iterations.
        psf_sigma: Estimated PSF sigma for the forward model (LR pixels).
        learning_rate: Step size for HR updates (0.05-0.2 typical).
        aligned_for_init: Pre-aligned crops for building the initial HR estimate.
                         If None, uses observations directly (translation-only case).
    """
    assert len(observations) == len(transforms) == len(weights)
    assert len(observations) > 0

    # Build the scale-invariant forward PSF.
    hr_psf_sigma = psf_sigma * scale
    psf_size = max(5, int(hr_psf_sigma * 6) | 1)  # 6-sigma kernel
    optical_psf = _make_gaussian_psf(size=psf_size, sigma=hr_psf_sigma)

    # Convolve optical PSF with sensor box filter for scale-invariant forward model
    box = np.ones((scale, scale), dtype=np.float64) / (scale * scale)
    psf = fftconvolve(optical_psf, box, mode="full")
    psf /= psf.sum()  # renormalise

    # Initial HR estimate: weighted average of aligned crops (or observations if no aligned)
    init_frames = aligned_for_init if aligned_for_init is not None else observations
    hr = _weighted_average_init(init_frames, weights, scale)
    h_hr, w_hr = hr.shape[:2]

    # Check if all transforms are near-identity (translation-only)
    # If so, we can use the faster FFT path
    is_translation_only = all(
        abs(t[0, 0] - 1.0) < 1e-6 and abs(t[0, 1]) < 1e-6
        and abs(t[1, 0]) < 1e-6 and abs(t[1, 1] - 1.0) < 1e-6
        for t in transforms
    )

    if is_translation_only:
        logger.info("IBP: %dx%d at %dx scale, %d frames (FFT, translation-only), "
                    "PSF sigma=%.1f LR px (%.1f HR px), kernel %dx%d",
                    w_hr, h_hr, scale, len(observations), psf_sigma, hr_psf_sigma,
                    psf.shape[1], psf.shape[0])

        # Fast FFT path (original)
        psf_padded = np.zeros((h_hr, w_hr), dtype=np.float64)
        ph, pw = psf.shape
        psf_padded[:ph, :pw] = psf
        psf_padded = np.roll(psf_padded, -(ph // 2), axis=0)
        psf_padded = np.roll(psf_padded, -(pw // 2), axis=1)
        otf = np.fft.fft2(psf_padded)
        otf_conj = np.conj(otf)

        # Extract shifts from transform matrices
        shifts = [(float(t[1, 2]), float(t[0, 2])) for t in transforms]  # (dy, dx)

        w_total = sum(weights)
        norm_weights = [w / w_total for w in weights] if w_total > 0 else weights

        prev_mse = float("inf")
        it = 0
        for it in range(iterations):
            if hr.ndim == 3:
                hr_fft = np.fft.fft2(hr, axes=(0, 1))
            else:
                hr_fft = np.fft.fft2(hr)

            correction = np.zeros_like(hr)
            total_mse = 0.0

            for frame, shift, wt in zip(observations, shifts, norm_weights):
                if wt <= 0:
                    continue
                simulated = _simulate_lr(hr, shift, scale, psf,
                                         hr_fft=hr_fft, otf=otf)
                fh = min(frame.shape[0], simulated.shape[0])
                fw = min(frame.shape[1], simulated.shape[1])
                error = frame[:fh, :fw] - simulated[:fh, :fw]
                total_mse += float(np.mean(error ** 2)) * wt
                bp = _back_project(error[:fh, :fw], shift, scale, psf,
                                   otf_conj=otf_conj)
                correction += bp * wt * learning_rate

            hr += correction
            hr = np.clip(hr, 0, 255)

            if it % 5 == 0 or it == iterations - 1:
                logger.info("IBP iteration %d/%d: MSE=%.2f", it + 1, iterations, total_mse)
            if total_mse > prev_mse * 1.05 and it > 5:
                logger.info("IBP: MSE increasing, stopping at iteration %d", it + 1)
                break
            prev_mse = total_mse
    else:
        logger.info("IBP: %dx%d at %dx scale, %d frames (affine, rotation+scale), "
                    "PSF sigma=%.1f LR px (%.1f HR px), kernel %dx%d",
                    w_hr, h_hr, scale, len(observations), psf_sigma, hr_psf_sigma,
                    psf.shape[1], psf.shape[0])

        # Affine path — uses spatial warp for rotation + scale
        w_total = sum(weights)
        norm_weights = [w / w_total for w in weights] if w_total > 0 else weights

        prev_mse = float("inf")
        it = 0
        for it in range(iterations):
            correction = np.zeros_like(hr)
            total_mse = 0.0

            for frame, transform, wt in zip(observations, transforms, norm_weights):
                if wt <= 0:
                    continue
                simulated = _simulate_lr_affine(hr, transform, scale, psf)
                fh = min(frame.shape[0], simulated.shape[0])
                fw = min(frame.shape[1], simulated.shape[1])
                error = frame[:fh, :fw] - simulated[:fh, :fw]
                total_mse += float(np.mean(error ** 2)) * wt
                bp = _back_project_affine(error[:fh, :fw], transform, scale, psf)
                correction += bp * wt * learning_rate

            hr += correction
            hr = np.clip(hr, 0, 255)

            if it % 5 == 0 or it == iterations - 1:
                logger.info("IBP iteration %d/%d: MSE=%.2f", it + 1, iterations, total_mse)
            if total_mse > prev_mse * 1.05 and it > 5:
                logger.info("IBP: MSE increasing, stopping at iteration %d", it + 1)
                break
            prev_mse = total_mse

    logger.info("IBP super-resolution: %dx%d, %d iterations",
                hr.shape[1], hr.shape[0], min(it + 1, iterations))
    return hr


def _ibp_mosaic_resolve(
    crops: list[NDArray[np.float64]],
    offsets: list[tuple[float, float]],
    weights: list[float],
    scale: int = 3,
    iterations: int = 20,
    psf_sigma: float = 0.5,
    learning_rate: float = 0.1,
) -> NDArray[np.float64]:
    """Mosaic IBP: super-resolve from crops at known sub-pixel positions.

    Each crop observes a different (overlapping) region of the scene.
    The HR canvas covers the union of all crop footprints. The sub-pixel
    fractional part of each offset provides the shift diversity needed
    for genuine super-resolution.

    Forward model per crop:
        HR canvas → extract patch at integer offset → sub-pixel shift by
        fractional offset → blur(PSF) → downsample → simulated LR crop

    Args:
        crops: LR crops (float64, 0-255), all same size.
        offsets: (ox, oy) sub-pixel offset of each crop's top-left corner
                 relative to a common origin. Integer part = canvas position,
                 fractional part = sub-pixel shift for SR.
        weights: Per-crop sharpness weights.
        scale: Upscaling factor.
        iterations: IBP iterations.
        psf_sigma: PSF sigma in LR pixels.
        learning_rate: Update step size.
    """
    assert len(crops) == len(offsets) == len(weights)
    assert len(crops) > 0

    crop_h, crop_w = crops[0].shape[:2]
    channels = crops[0].shape[2] if crops[0].ndim == 3 else 1

    # Split offsets into integer (canvas position) and fractional (sub-pixel)
    int_offsets = [(int(np.floor(ox)), int(np.floor(oy))) for ox, oy in offsets]
    frac_offsets = [(ox - int(np.floor(ox)), oy - int(np.floor(oy)))
                    for ox, oy in offsets]

    # Log sub-pixel diversity
    frac_xs = [fx for fx, _ in frac_offsets]
    frac_ys = [fy for _, fy in frac_offsets]
    unique_frac = len(set((round(fx, 2), round(fy, 2)) for fx, fy in frac_offsets))
    logger.info("Sub-pixel diversity: %d unique positions (frac_x std=%.3f, frac_y std=%.3f)",
                unique_frac, np.std(frac_xs), np.std(frac_ys))

    # Compute HR canvas size from integer offset extents
    max_iox = max(ox for ox, _ in int_offsets)
    max_ioy = max(oy for _, oy in int_offsets)
    hr_h = (max_ioy + crop_h + 1) * scale  # +1 for fractional overflow
    hr_w = (max_iox + crop_w + 1) * scale

    # Build PSF
    hr_psf_sigma = psf_sigma * scale
    psf_size = max(5, int(hr_psf_sigma * 6) | 1)
    optical_psf = _make_gaussian_psf(size=psf_size, sigma=hr_psf_sigma)
    box = np.ones((scale, scale), dtype=np.float64) / (scale * scale)
    psf = fftconvolve(optical_psf, box, mode="full")
    psf /= psf.sum()

    # Initial HR estimate: place each crop (bicubic upscaled) and average
    canvas = np.zeros((hr_h, hr_w, channels), dtype=np.float64)
    count = np.zeros((hr_h, hr_w), dtype=np.float64)

    for crop, (iox, ioy), wt in zip(crops, int_offsets, weights):
        if wt <= 0:
            continue
        hr_y, hr_x = ioy * scale, iox * scale
        upscaled = cv2.resize(crop, (crop_w * scale, crop_h * scale),
                              interpolation=cv2.INTER_CUBIC)
        uh, uw = upscaled.shape[:2]
        eh = min(uh, hr_h - hr_y)
        ew = min(uw, hr_w - hr_x)
        canvas[hr_y:hr_y+eh, hr_x:hr_x+ew] += upscaled[:eh, :ew] * wt
        count[hr_y:hr_y+eh, hr_x:hr_x+ew] += wt

    count = np.maximum(count, 1e-10)
    for c in range(channels):
        canvas[:, :, c] /= count

    hr = canvas
    logger.info("Mosaic IBP: HR canvas %dx%d at %dx scale, %d crops (%dx%d), "
                "PSF sigma=%.1f LR px, kernel %dx%d",
                hr_w, hr_h, scale, len(crops), crop_w, crop_h,
                psf_sigma, psf.shape[1], psf.shape[0])

    # Normalize weights
    w_total = sum(weights)
    norm_weights = [w / w_total for w in weights] if w_total > 0 else weights

    psf_t = psf[::-1, ::-1]
    ch_hr, cw_hr = crop_h * scale, crop_h * scale

    prev_mse = float("inf")
    for it in range(iterations):
        correction = np.zeros_like(hr)
        total_mse = 0.0

        for crop, (iox, ioy), (fox, foy), wt in zip(
            crops, int_offsets, frac_offsets, norm_weights,
        ):
            if wt <= 0:
                continue

            hr_y, hr_x = ioy * scale, iox * scale
            patch_h, patch_w = crop_h * scale, crop_w * scale
            eh = min(patch_h, hr_h - hr_y)
            ew = min(patch_w, hr_w - hr_x)

            # Forward model: extract HR patch → sub-pixel shift → blur → downsample
            hr_patch = hr[hr_y:hr_y+eh, hr_x:hr_x+ew].copy()

            if abs(fox) > 0.01 or abs(foy) > 0.01:
                shift_mat = np.array([[1, 0, fox], [0, 1, foy]],
                                     dtype=np.float64)
                hr_patch = cv2.warpAffine(
                    hr_patch, shift_mat, (ew, eh),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE,
                )

            blurred = cv2.filter2D(hr_patch, cv2.CV_64F, psf)
            simulated = cv2.resize(blurred, (crop_w, crop_h),
                                   interpolation=cv2.INTER_AREA)

            # Error
            fh = min(crop.shape[0], simulated.shape[0])
            fw = min(crop.shape[1], simulated.shape[1])
            error = crop[:fh, :fw] - simulated[:fh, :fw]
            total_mse += float(np.mean(error**2)) * wt

            # Adjoint: upsample → blur^T → un-shift → place in HR
            upsampled = cv2.resize(error[:fh, :fw], (ew, eh),
                                   interpolation=cv2.INTER_CUBIC)
            bp = cv2.filter2D(upsampled, cv2.CV_64F, psf_t)

            # Reverse the sub-pixel shift
            if abs(fox) > 0.01 or abs(foy) > 0.01:
                unshift_mat = np.array([[1, 0, -fox], [0, 1, -foy]],
                                       dtype=np.float64)
                bp = cv2.warpAffine(
                    bp, unshift_mat, (ew, eh),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE,
                )

            correction[hr_y:hr_y+eh, hr_x:hr_x+ew] += bp * wt * learning_rate

        hr += correction
        hr = np.clip(hr, 0, 255)

        if it % 5 == 0 or it == iterations - 1:
            logger.info("Mosaic IBP iteration %d/%d: MSE=%.2f",
                        it + 1, iterations, total_mse)
        if total_mse > prev_mse * 1.05 and it > 5:
            logger.info("Mosaic IBP: MSE increasing, stopping at iteration %d",
                        it + 1)
            break
        prev_mse = total_mse

    return hr


# ── Real-ESRGAN neural super-resolution ──────────────────────────────────
# Classes below require torch; only instantiated inside _esrgan_upscale()
# which checks HAS_TORCH at runtime.

class _ResidualDenseBlock(nn.Module if HAS_TORCH else object):  # type: ignore[misc]
    def __init__(self, nf: int = 64, gc: int = 32):
        super().__init__()
        self.conv1 = nn.Conv2d(nf, gc, 3, 1, 1)
        self.conv2 = nn.Conv2d(nf + gc, gc, 3, 1, 1)
        self.conv3 = nn.Conv2d(nf + 2 * gc, gc, 3, 1, 1)
        self.conv4 = nn.Conv2d(nf + 3 * gc, gc, 3, 1, 1)
        self.conv5 = nn.Conv2d(nf + 4 * gc, nf, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
        return x5 * 0.2 + x


class _RRDB(nn.Module if HAS_TORCH else object):  # type: ignore[misc]
    def __init__(self, nf: int = 64, gc: int = 32):
        super().__init__()
        self.rdb1 = _ResidualDenseBlock(nf, gc)
        self.rdb2 = _ResidualDenseBlock(nf, gc)
        self.rdb3 = _ResidualDenseBlock(nf, gc)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.rdb1(x)
        out = self.rdb2(out)
        out = self.rdb3(out)
        return out * 0.2 + x


class _RRDBNet(nn.Module if HAS_TORCH else object):  # type: ignore[misc]
    def __init__(self, in_nc: int = 3, out_nc: int = 3, nf: int = 64,
                 nb: int = 23, gc: int = 32):
        super().__init__()
        self.conv_first = nn.Conv2d(in_nc, nf, 3, 1, 1)
        self.body = nn.Sequential(*[_RRDB(nf=nf, gc=gc) for _ in range(nb)])
        self.conv_body = nn.Conv2d(nf, nf, 3, 1, 1)
        self.conv_up1 = nn.Conv2d(nf, nf, 3, 1, 1)
        self.conv_up2 = nn.Conv2d(nf, nf, 3, 1, 1)
        self.conv_hr = nn.Conv2d(nf, nf, 3, 1, 1)
        self.conv_last = nn.Conv2d(nf, out_nc, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feat = self.conv_first(x)
        body_feat = self.conv_body(self.body(feat))
        feat = feat + body_feat
        feat = self.lrelu(self.conv_up1(F.interpolate(feat, scale_factor=2, mode='nearest')))
        feat = self.lrelu(self.conv_up2(F.interpolate(feat, scale_factor=2, mode='nearest')))
        return self.conv_last(self.lrelu(self.conv_hr(feat)))


_ESRGAN_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
_ESRGAN_CACHE = Path.home() / ".cache" / "realesrgan" / "RealESRGAN_x4plus.pth"


def _esrgan_upscale(img_bgr: NDArray[np.uint8]) -> NDArray[np.uint8] | None:
    """Upscale a BGR uint8 image 4x using Real-ESRGAN (RRDBNet).

    Downloads model weights on first call (~64 MB).
    Uses MPS on Apple Silicon, falls back to CPU.
    Returns None if torch is not available.
    """
    if not HAS_TORCH:
        logger.warning("ESRGAN skipped: torch not installed")
        return None
    import urllib.request

    _ESRGAN_CACHE.parent.mkdir(parents=True, exist_ok=True)
    if not _ESRGAN_CACHE.exists():
        logger.info("Downloading Real-ESRGAN model to %s ...", _ESRGAN_CACHE)
        urllib.request.urlretrieve(_ESRGAN_URL, _ESRGAN_CACHE)

    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    model = _RRDBNet(in_nc=3, out_nc=3, nf=64, nb=23, gc=32)
    state = torch.load(_ESRGAN_CACHE, map_location="cpu", weights_only=True)
    if "params_ema" in state:
        state = state["params_ema"]
    elif "params" in state:
        state = state["params"]
    model.load_state_dict(state, strict=True)
    model.eval().to(device)

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    tensor = torch.from_numpy(img_rgb).permute(2, 0, 1).unsqueeze(0).to(device)

    with torch.no_grad():
        output = model(tensor)

    result = output.squeeze(0).permute(1, 2, 0).cpu().numpy()
    result = np.clip(result * 255.0, 0, 255).astype(np.uint8)
    return cv2.cvtColor(result, cv2.COLOR_RGB2BGR)


def _align_crops_phase(
    crops: list[NDArray],
    ref_idx: int,
    max_shift: float = 3.0,
) -> tuple[list[NDArray], list[tuple[float, float]], list[int]]:
    """Align crops to a reference via phase correlation.

    Returns:
        aligned_crops: Integer-shifted crops (pixels physically moved to align).
        fractional_shifts: Residual sub-pixel (dx, dy) for drizzle placement.
        kept_indices: Which original crop indices survived the max_shift filter.

    Crops whose total shift exceeds *max_shift* pixels are rejected — they
    are too dissimilar to the reference (wrong object, different angle, etc.)
    and would blur the drizzle stack rather than sharpen it.
    """
    def _to_gray(img: NDArray) -> NDArray[np.float64]:
        if img.ndim == 3:
            return cv2.cvtColor(
                np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY,
            ).astype(np.float64)
        return img.astype(np.float64)

    ref = _to_gray(crops[ref_idx])
    h, w = ref.shape
    # Hanning window to reduce edge effects in FFT
    win_y = np.hanning(h).reshape(-1, 1)
    win_x = np.hanning(w).reshape(1, -1)
    window = win_y * win_x

    ref_fft = np.fft.fft2(ref * window)

    def _subpix(arr: NDArray, idx: int, size: int) -> float:
        i0 = (idx - 1) % size
        i2 = (idx + 1) % size
        denom = arr[i0] - 2 * arr[idx] + arr[i2]
        if abs(denom) < 1e-12:
            return 0.0
        return 0.5 * (arr[i0] - arr[i2]) / denom

    raw_shifts: list[tuple[float, float]] = []
    for i, crop in enumerate(crops):
        if i == ref_idx:
            raw_shifts.append((0.0, 0.0))
            continue

        img = _to_gray(crop)
        img_fft = np.fft.fft2(img * window)

        # Cross-power spectrum
        cross = ref_fft * np.conj(img_fft)
        cross /= np.abs(cross) + 1e-10
        cc = np.fft.ifft2(cross).real

        # Integer peak
        peak = np.unravel_index(np.argmax(cc), cc.shape)
        py, px = peak

        # Wrap to signed offsets
        dy = py if py <= h // 2 else py - h
        dx = px if px <= w // 2 else px - w

        sub_dy = _subpix(cc[:, px], py, h)
        sub_dx = _subpix(cc[py, :], px, w)

        raw_shifts.append((dx + sub_dx, dy + sub_dy))

    # Log raw shift statistics
    dxs = [s[0] for s in raw_shifts]
    dys = [s[1] for s in raw_shifts]
    logger.info(
        "Phase alignment: %d crops, dx range [%.2f, %.2f], dy range [%.2f, %.2f]",
        len(raw_shifts), min(dxs), max(dxs), min(dys), max(dys),
    )

    # Filter by max_shift, integer-align kept crops, extract fractional residual
    aligned_crops: list[NDArray] = []
    fractional_shifts: list[tuple[float, float]] = []
    kept_indices: list[int] = []
    rejected = 0

    for i, (dx, dy) in enumerate(raw_shifts):
        dist = np.sqrt(dx**2 + dy**2)
        if dist > max_shift:
            rejected += 1
            continue

        # Split into integer shift and fractional residual
        idx_shift = int(np.round(dx))
        idy_shift = int(np.round(dy))
        frac_dx = dx - idx_shift
        frac_dy = dy - idy_shift

        # Integer-shift via np.roll (wraps edges, but the object is centred
        # with padding so the wrapped border is just background)
        shifted = np.roll(crops[i], -idx_shift, axis=1)  # shift X
        shifted = np.roll(shifted, -idy_shift, axis=0)    # shift Y

        aligned_crops.append(shifted)
        fractional_shifts.append((frac_dx, frac_dy))
        kept_indices.append(i)

    logger.info(
        "Phase alignment: kept %d/%d crops (rejected %d with shift > %.1f px)",
        len(kept_indices), len(crops), rejected, max_shift,
    )

    # Log sub-pixel diversity of kept crops
    if fractional_shifts:
        frac_x = [s[0] for s in fractional_shifts]
        frac_y = [s[1] for s in fractional_shifts]
        unique_frac = len(set(
            (round(fx, 2), round(fy, 2)) for fx, fy in zip(frac_x, frac_y)
        ))
        logger.info(
            "Sub-pixel diversity: %d unique fractional positions "
            "(frac_x std=%.3f, frac_y std=%.3f)",
            unique_frac, np.std(frac_x), np.std(frac_y),
        )

    return aligned_crops, fractional_shifts, kept_indices


def _drizzle(
    crops: list[NDArray[np.float64]],
    weights: list[float],
    scale: int = 3,
    pixfrac: float = 0.7,
    shifts: list[tuple[float, float]] | None = None,
) -> NDArray[np.float64]:
    """Drizzle using STScI's C-accelerated implementation.

    Each input pixel's footprint is shrunk by pixfrac and its flux is
    distributed onto a finer output grid, weighted by overlap area.

    Args:
        crops: LR crops (float64, 0-255), all same size.
        weights: Per-crop quality weights.
        scale: Output upscaling factor.
        pixfrac: Drop size as fraction of input pixel (0.0-1.0).
                 Smaller = sharper but noisier. 0.7 is typical.
        shifts: Per-crop (dx, dy) sub-pixel shifts from phase alignment.
                If None, all crops are placed at the same grid position
                (equivalent to a weighted average).
    """
    from drizzle.resample import Drizzle

    crop_h, crop_w = crops[0].shape[:2]
    channels = crops[0].shape[2] if crops[0].ndim == 3 else 1

    if shifts is None:
        shifts = [(0.0, 0.0)] * len(crops)

    # Process each channel separately (STScI drizzle works on 2D)
    result_channels = []
    for ch in range(channels):
        driz = Drizzle(kernel="square", out_shape=(crop_h * scale, crop_w * scale))

        for crop, wt, (dx, dy) in zip(crops, weights, shifts):
            if wt <= 0:
                continue
            # Extract single channel as float32 (drizzle requirement)
            if channels > 1:
                data = crop[:, :, ch].astype(np.float32)
            else:
                data = crop.astype(np.float32)

            # Build pixmap: maps each input pixel (iy, ix) to output (x, y)
            # The shift (dx, dy) offsets this crop's placement on the output grid
            iy_grid, ix_grid = np.mgrid[0:crop_h, 0:crop_w]
            pixmap = np.zeros((crop_h, crop_w, 2), dtype=np.float64)
            pixmap[:, :, 0] = (ix_grid.astype(np.float64) + dx) * scale  # output X
            pixmap[:, :, 1] = (iy_grid.astype(np.float64) + dy) * scale  # output Y

            # Weight map: uniform per-crop weight
            wht = np.full((crop_h, crop_w), wt, dtype=np.float32)

            driz.add_image(
                data, exptime=1.0, pixmap=pixmap,
                weight_map=wht, pixfrac=pixfrac,
                in_units="cps",
            )

        result_channels.append(driz.out_img.astype(np.float64))

    if channels > 1:
        result = np.stack(result_channels, axis=-1)
    else:
        result = result_channels[0]

    logger.info("Drizzle (STScI): %d crops (%dx%d) at %dx, pixfrac=%.2f",
                len(crops), crop_w, crop_h, scale, pixfrac)
    return result


def _make_gaussian_psf(size: int = 15, sigma: float = 1.5) -> NDArray[np.float64]:
    """Create a 2D Gaussian PSF kernel."""
    assert size % 2 == 1, "PSF size must be odd"
    ax = np.arange(size) - size // 2
    xx, yy = np.meshgrid(ax, ax)
    psf = np.exp(-(xx**2 + yy**2) / (2 * sigma**2))
    psf /= psf.sum()
    return psf


def _richardson_lucy_deconv(
    image: NDArray[np.float64],
    psf_sigma: float = 1.5,
    iterations: int = 15,
) -> NDArray[np.float64]:
    """Apply Richardson-Lucy deconvolution per channel.

    Uses a Gaussian PSF estimate. The image is expected in 0-255 float range.
    """
    psf = _make_gaussian_psf(size=15, sigma=psf_sigma)

    # RL works on positive values; normalize to 0-1
    img_norm = np.clip(image, 0, 255) / 255.0

    result = np.zeros_like(img_norm)
    for ch in range(img_norm.shape[2]):
        channel = img_norm[:, :, ch]
        # RL requires strictly positive input
        channel = np.maximum(channel, 1e-7)
        result[:, :, ch] = richardson_lucy(
            channel, psf, num_iter=iterations, clip=True,
        )

    logger.info(
        "Richardson-Lucy deconvolution: %d iterations, sigma=%.1f",
        iterations, psf_sigma,
    )
    return result * 255.0


def _enhance_output(image: NDArray[np.float64]) -> NDArray[np.float64]:
    """Apply adaptive contrast enhancement to the final image.

    Uses CLAHE in LAB colour space, but only when the image has enough
    non-dark content to benefit. For isolated bright objects on dark
    backgrounds, CLAHE creates tile-boundary artifacts, so we skip it
    and just do a gentle brightness stretch instead.
    """
    img_u8 = np.clip(image, 0, 255).astype(np.uint8)
    gray = cv2.cvtColor(img_u8, cv2.COLOR_BGR2GRAY)

    # Check what fraction of pixels are very dark (< 20)
    dark_fraction = float(np.mean(gray < 20))

    if dark_fraction > 0.7:
        # Mostly dark image — CLAHE would amplify noise and create rings.
        # Instead, do a percentile stretch on just the bright region.
        p_low = float(np.percentile(gray[gray > 10], 5)) if np.any(gray > 10) else 0
        p_high = float(np.percentile(gray[gray > 10], 99)) if np.any(gray > 10) else 255
        if p_high > p_low:
            scale = 255.0 / (p_high - p_low)
            result = np.clip((image - p_low) * scale, 0, 255)
            logger.info(
                "Output stretch: %.0f%% dark pixels, stretch [%.0f, %.0f] → [0, 255]",
                dark_fraction * 100, p_low, p_high,
            )
            return result
        return image

    lab = cv2.cvtColor(img_u8, cv2.COLOR_BGR2LAB)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    logger.info("Output CLAHE applied (%.0f%% dark pixels)", dark_fraction * 100)
    return result.astype(np.float64)


def convert_video(
    video_path: Path,
    output_dir: Path,
    *,
    scale: int = 2,
    max_frames: int = 0,
    frame_step: int = 1,
    padding_factor: float = 1.3,
    min_object_area: int = 100,
    warmup_frames: int = 10,
    psf_sigma: float = 0.5,
    deconv_iterations: int = 0,
    save_crops: bool = False,
    use_vlm: bool = True,
) -> Path:
    """Process a UAP video clip into a super-resolved still.

    Args:
        video_path: Path to input video file.
        output_dir: Directory for output files.
        scale: Upscaling factor for drizzle (2 or 3).
        max_frames: Max frames to extract (0 = all).
        frame_step: Extract every Nth frame.
        padding_factor: Crop padding around detected object.
        min_object_area: Minimum contour area for detection (pixels).
        warmup_frames: Frames for MOG2 warmup before detection starts.
        psf_sigma: Gaussian PSF sigma in LR pixels (0.3-0.8 for phone video).
        deconv_iterations: Richardson-Lucy iterations (0 = skip, IBP already deconvolves).
        save_crops: If True, save individual aligned crops to frames/ subdir.

    Returns:
        Path to the output directory containing enhanced.png and metadata.json.
    """
    assert video_path.exists(), f"Video not found: {video_path}"
    assert scale in (2, 3), f"Scale must be 2 or 3, got {scale}"

    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Processing video: %s → %s", video_path, output_dir)

    # Step 1: Extract frames
    frames = _extract_frames(video_path, max_frames=max_frames, frame_step=frame_step)
    total_frames = len(frames)
    logger.info(f"Total frames extracted: {total_frames}")

    # Step 1.3: Scene-based frame filtering (optional VLM)
    vlm_scene_count = 0
    vlm_footage_range: tuple[int, int] | None = None
    if use_vlm:
        try:
            from woograph.convert.vlm_detect import (
                classify_scenes_vlm,
                detect_scenes,
                get_footage_range,
            )
            from woograph.llm import load_llm_config

            scenes = detect_scenes(frames)
            vlm_scene_count = len(scenes)
            if len(scenes) > 1:
                vlm_config = load_llm_config()
                if vlm_config:
                    scene_info = classify_scenes_vlm(frames, scenes, vlm_config)
                    start, end = get_footage_range(scene_info, len(frames))
                    vlm_footage_range = (start, end)
                    logger.info(
                        "VLM scene selection: using frames %d-%d of %d",
                        start, end, len(frames),
                    )
                    frames = frames[start:end]
                    total_frames = len(frames)
                else:
                    logger.info("No API key for VLM scene classification")
            else:
                logger.info("Single scene detected, skipping VLM classification")
        except Exception:
            logger.warning(
                "VLM scene detection failed, using all frames", exc_info=True,
            )

    # Step 1.5: Detect and exclude video player UI overlay
    roi_y_max = _detect_ui_region(frames)

    # Step 1.6: Stabilise camera (Pass 1 of two-pass approach)
    # Build a mask that excludes UI regions for feature matching
    h, w = frames[0].shape[:2]
    feature_mask = np.full((h, w), 255, dtype=np.uint8)
    y_limit = int(h * roi_y_max)
    if y_limit < h:
        feature_mask[y_limit:] = 0

    transforms = _estimate_global_motion(frames, mask=feature_mask)
    frames = _stabilise_frames(frames, transforms)

    # Step 2: Detect and track object (Pass 2 — on stabilised frames)
    # Try temporal median subtraction first (better for small objects in sky),
    # fall back to MOG2 if it doesn't find enough detections.
    bboxes = _detect_median_subtraction(
        frames, min_area=min_object_area, roi_y_max=roi_y_max,
    )
    raw_detected_count = sum(1 for b in bboxes if b is not None)
    logger.info(f"bboxes = {bboxes}")

    # if raw_detected_count < 10:
    #     logger.info(
    #         "Median subtraction found only %d frames — trying MOG2 fallback",
    #         raw_detected_count,
    #     )
    #     bboxes_mog2 = _detect_and_track(
    #         frames, min_area=min_object_area, warmup_frames=warmup_frames,
    #         roi_y_max=roi_y_max,
    #     )
    #     mog2_count = sum(1 for b in bboxes_mog2 if b is not None)
    #     if mog2_count > raw_detected_count:
    #         logger.info("MOG2 found more detections (%d vs %d), using MOG2",
    #                     mog2_count, raw_detected_count)
    #         bboxes = bboxes_mog2
    #         raw_detected_count = mog2_count

    logger.info("Detected %d frames", raw_detected_count)

    # Step 2.5: Filter outlier detections (edge proximity, size jumps, banking)
    raw_bboxes = list(bboxes)  # save pre-filter state for debug video
    bboxes = _filter_detections(bboxes, (h, w))

    # Step 2.6: Trajectory filter — reject detections that jump to a second
    # object. Keeps only the smooth path of one consistent target.
    bboxes = _filter_trajectory(bboxes)

    raw_detected_count = sum(1 for b in bboxes if b is not None)

    logger.info("%d frames after filtering", raw_detected_count)

    # Step 2.8: Save debug video with raw + filtered bboxes
    if save_crops:
        _save_debug_video(frames, raw_bboxes, bboxes,
                          output_dir / "debug_detections.mp4")

    if raw_detected_count < 3:
        logger.warning(
            "Only %d frames with detections — need at least 3 for stacking",
            raw_detected_count,
        )
        mid = len(frames) // 2
        best_path = output_dir / "best_frame.png"
        cv2.imwrite(str(best_path), frames[mid])
        meta = ProcessingMetadata(
            video_path=str(video_path),
            total_frames=total_frames,
            extracted_frames=total_frames,
            detected_frames=raw_detected_count,
            crop_size=(0, 0),
            scale_factor=scale,
            output_size=(frames[mid].shape[1], frames[mid].shape[0]),
            processed_at=datetime.now(timezone.utc).isoformat(),
        )
        (output_dir / "metadata.json").write_text(
            json.dumps(asdict(meta), indent=2) + "\n",
        )
        logger.warning("Insufficient detections, saved fallback best_frame.png only")
        return output_dir

    # Step 3: Crop around object at raw bbox centres (object stays centred)
    crops, crop_size, raw_centers, crop_corners, frame_indices = _crop_with_padding(
        frames, bboxes, padding_factor=padding_factor,
    )

    logger.debug(f"crop corners = {crop_corners}")
    # Step 4: Compute offsets from the ACTUAL crop corner positions.
    crop_h, crop_w = crop_size

    # Log per-frame detail: frame_idx, bbox, centre, crop corner
    valid_bboxes = [b for b in bboxes if b is not None]
    for i in range(len(crops)):
        bb = valid_bboxes[i]
        cx, cy = raw_centers[i]
        x1, y1 = crop_corners[i]
        logger.debug(
            "crop %3d: bbox=(%d,%d,%d,%d) centre=(%.1f,%.1f) "
            "crop_corner=(%d,%d) float_origin=(%.1f,%.1f)",
            i, bb.x, bb.y, bb.w, bb.h, cx, cy,
            x1, y1, cx - crop_w / 2, cy - crop_h / 2,
        )

    # Use actual integer crop corners as origins (matches where pixels came from)
    raw_origins = [(float(x1), float(y1)) for x1, y1 in crop_corners]
    min_ox = min(ox for ox, _ in raw_origins)
    min_oy = min(oy for _, oy in raw_origins)
    offsets = [(ox - min_ox, oy - min_oy) for ox, oy in raw_origins]

    ox_span = max(ox for ox, _ in offsets)
    oy_span = max(oy for _, oy in offsets)
    logger.info("Crop offsets: span %.1f×%.1f px, %d crops at %dx%d",
                ox_span, oy_span, len(crops), crop_w, crop_h)
    logger.debug("Origin min: (%.2f, %.2f), offsets (first 5): %s",
                 min_ox, min_oy, offsets[:5])

    # Step 5: Compute sharpness weights on raw crops
    weights = _compute_sharpness(crops)

    # Step 6: Best frame (for comparison output)
    best_idx = int(np.argmax(weights))
    best_crop = crops[best_idx]
    best_path = output_dir / "best_frame.png"
    cv2.imwrite(str(best_path), best_crop)
    logger.info(
        "Best frame: index %d, sharpness weight %.4f", best_idx, weights[best_idx],
    )

    # Step 6.5: Save diagnostic video
    if save_crops:
        _save_crop_video(
            [c.astype(np.float64) for c in crops],
            output_dir / "crops.mp4", fps=10,
            raw_centers=raw_centers, crop_corners=crop_corners,
            frame_indices=frame_indices,
        )

    # Step 7: Phase-correlation alignment — integer-align crops and extract
    # sub-pixel residuals.  Crops with large shifts (dissimilar frames) are
    # rejected so they don't blur the stack.
    aligned_crops, frac_shifts, kept = _align_crops_phase(
        crops, ref_idx=best_idx, max_shift=3.0,
    )
    aligned_weights = [weights[i] for i in kept]

    if len(aligned_crops) < 3:
        logger.warning(
            "Phase alignment kept only %d crops — falling back to all crops without alignment",
            len(aligned_crops),
        )
        aligned_crops = [c.astype(np.float64) for c in crops]
        frac_shifts = [(0.0, 0.0)] * len(crops)
        aligned_weights = list(weights)

    # Step 7b: Select frame subsets and build transforms.
    #
    # "all" — every aligned crop (may blur rotating objects)
    # "consecutive" — 5 frames nearest the best frame (minimal rotation)
    # "similar" — top N most similar to reference (NCC-ranked)

    def _build_transforms(shifts: list[tuple[float, float]]) -> list[NDArray[np.float64]]:
        return [np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float64)
                for dx, dy in shifts]

    def _ncc_to_ref(crops_list: list[NDArray], ref: NDArray) -> NDArray[np.float64]:
        """Normalised cross-correlation of each crop with the reference."""
        ref_gray = cv2.cvtColor(np.clip(ref, 0, 255).astype(np.uint8),
                                cv2.COLOR_BGR2GRAY).astype(np.float64) if ref.ndim == 3 \
            else ref.astype(np.float64)
        ref_norm = ref_gray - ref_gray.mean()
        ref_std = ref_norm.std()
        if ref_std < 1e-6:
            return np.ones(len(crops_list))
        scores = np.zeros(len(crops_list))
        for i, c in enumerate(crops_list):
            g = cv2.cvtColor(np.clip(c, 0, 255).astype(np.uint8),
                             cv2.COLOR_BGR2GRAY).astype(np.float64) if c.ndim == 3 \
                else c.astype(np.float64)
            g_norm = g - g.mean()
            g_std = g_norm.std()
            if g_std < 1e-6:
                scores[i] = 0.0
            else:
                scores[i] = float(np.sum(ref_norm * g_norm) / (ref_std * g_std * ref_gray.size))
        return scores

    def _select_consecutive(n: int = 5) -> tuple[list[NDArray], list[tuple[float, float]], list[float]]:
        """Select n frames centred on the best frame (within aligned set)."""
        # Find best_idx within aligned_crops
        ref_pos = None
        for i, ki in enumerate(kept):
            if ki == best_idx:
                ref_pos = i
                break
        if ref_pos is None:
            ref_pos = 0
        half = n // 2
        lo = max(0, ref_pos - half)
        hi = min(len(aligned_crops), lo + n)
        lo = max(0, hi - n)
        sel = list(range(lo, hi))
        return ([aligned_crops[i] for i in sel],
                [frac_shifts[i] for i in sel],
                [aligned_weights[i] for i in sel])

    def _select_similar(n: int = 15) -> tuple[list[NDArray], list[tuple[float, float]], list[float]]:
        """Select n crops most similar to reference by NCC."""
        ref_pos = None
        for i, ki in enumerate(kept):
            if ki == best_idx:
                ref_pos = i
                break
        if ref_pos is None:
            ref_pos = 0
        ncc = _ncc_to_ref(aligned_crops, aligned_crops[ref_pos])
        top_n = min(n, len(aligned_crops))
        sel = np.argsort(ncc)[-top_n:][::-1].tolist()
        return ([aligned_crops[i] for i in sel],
                [frac_shifts[i] for i in sel],
                [aligned_weights[i] for i in sel])

    def _run_drizzle_ibp(sel_crops: list[NDArray], sel_shifts: list[tuple[float, float]],
                         sel_weights: list[float], label: str) -> None:
        """Run drizzle, IBP, and drizzle+IBP for a frame selection, save outputs."""
        sel_transforms = _build_transforms(sel_shifts)
        sel_f64 = [c.astype(np.float64) for c in sel_crops]

        # Drizzle
        driz = _drizzle(sel_f64, sel_weights, scale=scale, pixfrac=0.7, shifts=sel_shifts)
        driz_out = _enhance_output(driz)
        cv2.imwrite(str(output_dir / f"drizzle_{label}.png"),
                    np.clip(driz_out, 0, 255).astype(np.uint8))
        logger.info("Saved drizzle_%s: %d frames", label, len(sel_crops))

        # IBP only (weighted-average init)
        ibp = _ibp_super_resolve(
            observations=sel_f64, transforms=sel_transforms, weights=sel_weights,
            scale=scale, iterations=20, psf_sigma=psf_sigma, learning_rate=0.1,
        )
        ibp_out = _enhance_output(ibp)
        cv2.imwrite(str(output_dir / f"ibp_{label}.png"),
                    np.clip(ibp_out, 0, 255).astype(np.uint8))
        logger.info("Saved ibp_%s: %d frames", label, len(sel_crops))

        # Drizzle + IBP
        driz_ibp = _ibp_super_resolve(
            observations=sel_f64, transforms=sel_transforms, weights=sel_weights,
            scale=scale, iterations=20, psf_sigma=psf_sigma, learning_rate=0.1,
            aligned_for_init=sel_f64,
        )
        driz_ibp_out = _enhance_output(driz_ibp)
        cv2.imwrite(str(output_dir / f"drizzle_ibp_{label}.png"),
                    np.clip(driz_ibp_out, 0, 255).astype(np.uint8))
        logger.info("Saved drizzle_ibp_%s: %d frames", label, len(sel_crops))

    # ── Save all output variants for comparison ──

    # 1. All aligned frames
    _run_drizzle_ibp(aligned_crops, frac_shifts, aligned_weights, "all")

    # 2. 5 consecutive frames around best
    cons_crops, cons_shifts, cons_weights = _select_consecutive(5)
    _run_drizzle_ibp(cons_crops, cons_shifts, cons_weights, "consecutive5")

    # 3. Top 15 most similar frames
    sim_crops, sim_shifts, sim_weights = _select_similar(15)
    _run_drizzle_ibp(sim_crops, sim_shifts, sim_weights, "similar15")

    # 4. Best frame bicubic upscale (baseline comparison)
    bicubic = cv2.resize(best_crop, (best_crop.shape[1] * scale, best_crop.shape[0] * scale),
                         interpolation=cv2.INTER_CUBIC)
    cv2.imwrite(str(output_dir / "best_frame_bicubic.png"), bicubic)
    logger.info("Saved bicubic %dx: %s", scale, output_dir / "best_frame_bicubic.png")

    # 4. Best frame neural upscale (Real-ESRGAN 4x) — optional, requires torch
    best_u8 = np.clip(best_crop, 0, 255).astype(np.uint8)
    esrgan_result = _esrgan_upscale(best_u8)
    if esrgan_result is not None:
        cv2.imwrite(str(output_dir / "best_frame_esrgan4x.png"), esrgan_result)
        logger.info("Saved ESRGAN 4x: %s (%dx%d)", output_dir / "best_frame_esrgan4x.png",
                    esrgan_result.shape[1], esrgan_result.shape[0])

    # Optionally save individual crops
    if save_crops:
        frames_dir = output_dir / "frames"
        frames_dir.mkdir(exist_ok=True)
        for i, crop in enumerate(crops):
            crop_path = frames_dir / f"crop_{i:04d}.png"
            cv2.imwrite(str(crop_path), crop)
        logger.info("Saved %d crops to %s", len(crops), frames_dir)

    # Collect output file manifest
    output_files: dict[str, str] = {}
    for f in sorted(output_dir.iterdir()):
        if f.suffix in (".png", ".mp4"):
            output_files[f.stem] = f.name

    # Build and save metadata
    meta = ProcessingMetadata(
        video_path=str(video_path),
        total_frames=total_frames,
        extracted_frames=len(frames),
        detected_frames=raw_detected_count,
        crop_size=crop_size,
        scale_factor=scale,
        output_size=(best_crop.shape[1] * scale, best_crop.shape[0] * scale),
        shifts=[list(o) for o in offsets],
        sharpness_weights=[round(w, 6) for w in weights],
        best_frame_index=best_idx,
        best_frame_sharpness=round(weights[best_idx], 6),
        deconv_iterations=deconv_iterations,
        psf_sigma=psf_sigma,
        processed_at=datetime.now(timezone.utc).isoformat(),
        output_files=output_files,
        vlm_scene_count=vlm_scene_count,
        vlm_footage_range=vlm_footage_range,
    )

    meta_path = output_dir / "metadata.json"
    meta_path.write_text(json.dumps(asdict(meta), indent=2) + "\n")
    logger.info("Saved metadata: %s", meta_path)

    # Also write a content.md summary for the graph pipeline to consume
    content_path = output_dir / "content.md"
    content_path.write_text(
        f"# Video Enhancement Results\n\n"
        f"Source: {video_path.name}\n\n"
        f"## Processing Summary\n\n"
        f"- Frames extracted: {len(frames)}\n"
        f"- Frames with detection: {raw_detected_count}\n"
        f"- Crop size: {crop_size[1]}x{crop_size[0]}\n"
        f"- Output size: {best_crop.shape[1] * scale}x{best_crop.shape[0] * scale} "
        f"({scale}x drizzle)\n"
        f"- Deconvolution: {deconv_iterations} iterations, "
        f"sigma={psf_sigma}\n"
        f"- Best frame sharpness: {weights[best_idx]:.4f} "
        f"(frame {best_idx})\n\n"
        f"*Enhanced image saved as enhanced.png*\n"
    )

    return output_dir
