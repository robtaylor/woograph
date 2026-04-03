"""Video UAP enhancement pipeline.

Extracts a super-resolved still of a tracked object from short video clips.
Pipeline: detect → track → crop → align → weight → drizzle stack → deconvolve.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray
from scipy import ndimage
from scipy.signal import fftconvolve
from skimage.registration import phase_cross_correlation
from skimage.restoration import richardson_lucy

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


def _crop_with_padding(
    frames: list[NDArray[np.uint8]],
    bboxes: list[BBox | None],
    padding_factor: float = 2.0,
    uniform_size: tuple[int, int] | None = None,
) -> tuple[list[NDArray[np.uint8]], tuple[int, int]]:
    """Crop frames around detected object with padding.

    All crops are resized to a uniform size (the median bbox size * padding).
    Returns the list of crops and the crop size (h, w).
    """
    valid = [(f, b) for f, b in zip(frames, bboxes) if b is not None]
    assert len(valid) > 0, "No frames with detected objects to crop"

    if uniform_size is None:
        widths = [b.w for _, b in valid]
        heights = [b.h for _, b in valid]
        crop_w = int(np.median(widths) * padding_factor)
        crop_h = int(np.median(heights) * padding_factor)
        # Make even for easier upscaling
        crop_w += crop_w % 2
        crop_h += crop_h % 2
        uniform_size = (crop_h, crop_w)

    crop_h, crop_w = uniform_size
    crops: list[NDArray[np.uint8]] = []

    for frame, bbox in valid:
        assert bbox is not None
        h, w = frame.shape[:2]
        cx, cy = bbox.center

        # Compute crop region, clamped to frame bounds
        x1 = int(max(0, cx - crop_w / 2))
        y1 = int(max(0, cy - crop_h / 2))
        x2 = int(min(w, x1 + crop_w))
        y2 = int(min(h, y1 + crop_h))

        crop = frame[y1:y2, x1:x2]

        # Pad if crop is smaller than desired (near edges)
        if crop.shape[0] != crop_h or crop.shape[1] != crop_w:
            padded = np.zeros((crop_h, crop_w, 3), dtype=np.uint8)
            ph = min(crop.shape[0], crop_h)
            pw = min(crop.shape[1], crop_w)
            padded[:ph, :pw] = crop[:ph, :pw]
            crop = padded

        crops.append(crop)

    logger.info("Cropped %d frames to %dx%d", len(crops), crop_w, crop_h)
    return crops, uniform_size


def _align_crops(
    crops: list[NDArray[np.uint8]],
    upsample_factor: int = 20,
    max_shift_fraction: float = 0.5,
) -> tuple[list[NDArray[np.float64]], list[tuple[float, float]]]:
    """Sub-pixel align crops using phase cross-correlation.

    Uses the first crop as the reference. Crops with shifts exceeding
    max_shift_fraction of the crop size are rejected as outliers.

    Returns aligned crops (float64, 0-255 range) and the measured shifts.
    """
    assert len(crops) > 0

    h, w = crops[0].shape[:2]
    max_shift_px = max_shift_fraction * min(h, w)

    # Convert to grayscale float for correlation
    ref_gray = cv2.cvtColor(crops[0], cv2.COLOR_BGR2GRAY).astype(np.float64)

    aligned: list[NDArray[np.float64]] = [crops[0].astype(np.float64)]
    shifts: list[tuple[float, float]] = [(0.0, 0.0)]
    rejected = 0

    for crop in crops[1:]:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float64)
        shift, _error, _phasediff = phase_cross_correlation(
            ref_gray, gray, upsample_factor=upsample_factor,
        )

        # Reject outlier shifts (e.g. tracker jumped to different object)
        shift_mag = np.sqrt(shift[0]**2 + shift[1]**2)
        if shift_mag > max_shift_px:
            rejected += 1
            continue

        # shift is (row_shift, col_shift) i.e. (dy, dx)
        shifted = np.zeros_like(crop, dtype=np.float64)
        for c in range(crop.shape[2]):
            shifted[:, :, c] = ndimage.shift(
                crop[:, :, c].astype(np.float64),
                shift,
                order=3,
                mode="constant",
                cval=0.0,
            )

        aligned.append(shifted)
        shifts.append((float(shift[0]), float(shift[1])))

    if rejected > 0:
        logger.info("Rejected %d crops with shifts > %.0f px", rejected, max_shift_px)
    logger.info("Aligned %d crops (max shift: %.2f px)", len(aligned),
                max(max(abs(s[0]), abs(s[1])) for s in shifts) if shifts else 0)
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


def _simulate_lr(
    hr: NDArray[np.float64],
    shift: tuple[float, float],
    scale: int,
    psf: NDArray[np.float64],
    *,
    hr_fft: NDArray[np.complex128] | None = None,
    otf: NDArray[np.complex128] | None = None,
) -> NDArray[np.float64]:
    """Simulate the LR observation from an HR estimate.

    Forward model: HR → blur(PSF) → shift → downsample → LR
    Uses FFT for shift+blur when hr_fft and otf are provided.
    """
    h_hr, w_hr = hr.shape[:2]
    h_lr, w_lr = h_hr // scale, w_hr // scale

    if hr_fft is not None and otf is not None:
        # FFT path: shift + blur in one multiply
        dy, dx = shift[0] * scale, shift[1] * scale
        shifted_blurred_fft = _fft_shift_blur(hr_fft, dy, dx, otf)
        if hr.ndim == 3:
            shifted_blurred = np.real(np.fft.ifft2(shifted_blurred_fft, axes=(0, 1)))
        else:
            shifted_blurred = np.real(np.fft.ifft2(shifted_blurred_fft))
        return cv2.resize(shifted_blurred, (w_lr, h_lr), interpolation=cv2.INTER_AREA)

    # Spatial fallback
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
    """Back-project a LR error into HR space.

    Inverse of forward model: LR error → upsample → un-shift → blur(PSF^T) → HR correction
    Uses FFT for un-shift + adjoint blur when otf_conj is provided.
    """
    h_lr, w_lr = error.shape[:2]
    h_hr, w_hr = h_lr * scale, w_lr * scale

    # 1. Upsample
    upsampled = cv2.resize(error, (w_hr, h_hr), interpolation=cv2.INTER_CUBIC)

    if otf_conj is not None:
        # FFT path: un-shift + adjoint blur in one multiply
        dy, dx = -shift[0] * scale, -shift[1] * scale
        if upsampled.ndim == 3:
            up_fft = np.fft.fft2(upsampled, axes=(0, 1))
        else:
            up_fft = np.fft.fft2(upsampled)
        result_fft = _fft_shift_blur(up_fft, dy, dx, otf_conj)
        if upsampled.ndim == 3:
            return np.real(np.fft.ifft2(result_fft, axes=(0, 1)))
        return np.real(np.fft.ifft2(result_fft))

    # Spatial fallback
    psf_t = psf[::-1, ::-1]
    dy, dx = -shift[0] * scale, -shift[1] * scale
    unshifted = _warp_shift(upsampled, dy, dx)
    return cv2.filter2D(unshifted, cv2.CV_64F, psf_t)


def _ibp_super_resolve(
    aligned: list[NDArray[np.float64]],
    shifts: list[tuple[float, float]],
    weights: list[float],
    scale: int = 2,
    iterations: int = 20,
    psf_sigma: float = 1.0,
    learning_rate: float = 0.1,
) -> NDArray[np.float64]:
    """Iterative Back-Projection super-resolution (FFT-accelerated).

    Solves for the HR image that, when blurred + shifted + downsampled,
    best reproduces all observed LR frames. Each frame contributes a
    different sub-pixel constraint on the HR solution.

    The forward (blur+shift) and backward (un-shift+adjoint blur) operations
    are done in the frequency domain — shift is a phase ramp, blur is an OTF
    multiply — so each frame costs ~3 FFTs instead of spatial convolution +
    interpolation. This makes using all frames practical.

    Args:
        aligned: LR frames (float64, 0-255), already coarsely aligned.
        shifts: Sub-pixel shifts measured during alignment (dy, dx per frame).
        weights: Per-frame sharpness weights (higher = more influence).
        scale: Upscaling factor.
        iterations: Number of IBP iterations.
        psf_sigma: Estimated PSF sigma for the forward model.
        learning_rate: Step size for HR updates (0.05-0.2 typical).
    """
    assert len(aligned) == len(shifts) == len(weights)
    assert len(aligned) > 0

    # Build the scale-invariant forward PSF.
    # The physical imaging model is: scene → optical_blur(PSF) → sensor_integrate → sample
    # Sensor integration over each LR pixel is a box filter of width `scale` in HR pixels.
    # The effective blur kernel is PSF ⊛ box(scale), making the model consistent
    # regardless of the chosen upscaling factor.
    hr_psf_sigma = psf_sigma * scale
    psf_size = max(5, int(hr_psf_sigma * 6) | 1)  # 6-sigma kernel
    optical_psf = _make_gaussian_psf(size=psf_size, sigma=hr_psf_sigma)

    # Convolve optical PSF with sensor box filter for scale-invariant forward model
    box = np.ones((scale, scale), dtype=np.float64) / (scale * scale)
    psf = fftconvolve(optical_psf, box, mode="full")
    psf /= psf.sum()  # renormalise

    # Initial HR estimate: weighted average
    hr = _weighted_average_init(aligned, weights, scale)
    h_hr, w_hr = hr.shape[:2]
    logger.info("IBP: initial HR estimate %dx%d at %dx scale, %d frames (FFT), "
                "PSF sigma=%.1f LR px (%.1f HR px), kernel %dx%d",
                w_hr, h_hr, scale, len(aligned), psf_sigma, hr_psf_sigma,
                psf.shape[1], psf.shape[0])

    # Precompute OTF (combined PSF in frequency domain at HR resolution)
    psf_padded = np.zeros((h_hr, w_hr), dtype=np.float64)
    ph, pw = psf.shape
    psf_padded[:ph, :pw] = psf
    # Centre the PSF at origin for correct phase
    psf_padded = np.roll(psf_padded, -(ph // 2), axis=0)
    psf_padded = np.roll(psf_padded, -(pw // 2), axis=1)
    otf = np.fft.fft2(psf_padded)
    otf_conj = np.conj(otf)

    # Normalise weights for the update step
    w_total = sum(weights)
    norm_weights = [w / w_total for w in weights] if w_total > 0 else weights

    prev_mse = float("inf")
    it = 0
    for it in range(iterations):
        # Precompute HR FFT once per iteration (used by all frames)
        if hr.ndim == 3:
            hr_fft = np.fft.fft2(hr, axes=(0, 1))
        else:
            hr_fft = np.fft.fft2(hr)

        # Accumulate back-projected errors from all frames
        correction = np.zeros_like(hr)
        total_mse = 0.0

        for frame, shift, wt in zip(aligned, shifts, norm_weights):
            if wt <= 0:
                continue

            # Forward: simulate what this LR frame should look like (FFT path)
            simulated = _simulate_lr(hr, shift, scale, psf,
                                     hr_fft=hr_fft, otf=otf)

            # Ensure shapes match
            fh = min(frame.shape[0], simulated.shape[0])
            fw = min(frame.shape[1], simulated.shape[1])
            error = frame[:fh, :fw] - simulated[:fh, :fw]

            total_mse += float(np.mean(error ** 2)) * wt

            # Back-project the error into HR space (FFT path)
            bp = _back_project(error[:fh, :fw], shift, scale, psf,
                               otf_conj=otf_conj)
            correction += bp * wt * learning_rate

        hr += correction
        hr = np.clip(hr, 0, 255)

        # Convergence check
        if it % 5 == 0 or it == iterations - 1:
            logger.info("IBP iteration %d/%d: MSE=%.2f", it + 1, iterations, total_mse)

        # Early stopping if MSE increases (diverging)
        if total_mse > prev_mse * 1.05 and it > 5:
            logger.info("IBP: MSE increasing, stopping at iteration %d", it + 1)
            break
        prev_mse = total_mse

    logger.info("IBP super-resolution: %dx%d, %d iterations",
                hr.shape[1], hr.shape[0], min(it + 1, iterations))
    return hr


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
    padding_factor: float = 2.0,
    min_object_area: int = 100,
    warmup_frames: int = 10,
    psf_sigma: float = 1.5,
    deconv_iterations: int = 15,
    save_crops: bool = False,
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
        psf_sigma: Gaussian PSF sigma for deconvolution.
        deconv_iterations: Richardson-Lucy iterations.
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
    bboxes = _detect_and_track(
        frames, min_area=min_object_area, warmup_frames=warmup_frames,
        roi_y_max=roi_y_max,
    )

    raw_detected_count = sum(1 for b in bboxes if b is not None)
    if raw_detected_count < 3:
        logger.warning(
            "Only %d frames with detections — need at least 3 for stacking",
            raw_detected_count,
        )
        # Fall back: save the middle frame as best_frame
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

    # Step 3: Crop around object
    crops, crop_size = _crop_with_padding(
        frames, bboxes, padding_factor=padding_factor,
    )

    # Step 4: Align crops via phase correlation (rejects outlier shifts)
    aligned, shifts = _align_crops(crops)
    detected_count = len(aligned)

    if detected_count < 3:
        logger.warning(
            "Only %d usable frames after alignment — need at least 3",
            detected_count,
        )
        mid = len(frames) // 2
        best_path = output_dir / "best_frame.png"
        cv2.imwrite(str(best_path), frames[mid])
        meta = ProcessingMetadata(
            video_path=str(video_path),
            total_frames=total_frames,
            extracted_frames=total_frames,
            detected_frames=detected_count,
            crop_size=crop_size,
            scale_factor=scale,
            output_size=(frames[mid].shape[1], frames[mid].shape[0]),
            processed_at=datetime.now(timezone.utc).isoformat(),
        )
        (output_dir / "metadata.json").write_text(
            json.dumps(asdict(meta), indent=2) + "\n",
        )
        return output_dir

    # Step 5: Compute sharpness weights (on aligned crops, not originals)
    weights = _compute_sharpness(aligned)

    # Step 6: Best frame (for comparison output)
    best_idx = int(np.argmax(weights))
    best_crop = np.clip(aligned[best_idx], 0, 255).astype(np.uint8)
    best_path = output_dir / "best_frame.png"
    cv2.imwrite(str(best_path), best_crop)
    logger.info(
        "Best frame: index %d, sharpness weight %.4f", best_idx, weights[best_idx],
    )

    # Step 7: Iterative Back-Projection super-resolution
    stacked = _ibp_super_resolve(
        aligned, shifts, weights,
        scale=scale,
        iterations=20,
        psf_sigma=psf_sigma,
        learning_rate=0.1,
    )

    # Step 8: Richardson-Lucy deconvolution (sigma in HR pixel units)
    enhanced = _richardson_lucy_deconv(
        stacked, psf_sigma=psf_sigma * scale, iterations=deconv_iterations,
    )

    # Step 9: Adaptive contrast enhancement
    enhanced = _enhance_output(enhanced)

    # Save enhanced image
    enhanced_uint8 = np.clip(enhanced, 0, 255).astype(np.uint8)
    enhanced_path = output_dir / "enhanced.png"
    cv2.imwrite(str(enhanced_path), enhanced_uint8)
    logger.info("Saved enhanced image: %s", enhanced_path)

    # Optionally save individual aligned crops
    if save_crops:
        frames_dir = output_dir / "frames"
        frames_dir.mkdir(exist_ok=True)
        for i, crop in enumerate(aligned):
            crop_path = frames_dir / f"crop_{i:04d}.png"
            cv2.imwrite(str(crop_path), np.clip(crop, 0, 255).astype(np.uint8))
        logger.info("Saved %d aligned crops to %s", len(aligned), frames_dir)

    # Build and save metadata
    meta = ProcessingMetadata(
        video_path=str(video_path),
        total_frames=total_frames,
        extracted_frames=len(frames),
        detected_frames=detected_count,
        crop_size=crop_size,
        scale_factor=scale,
        output_size=(enhanced_uint8.shape[1], enhanced_uint8.shape[0]),
        shifts=[list(s) for s in shifts],
        sharpness_weights=[round(w, 6) for w in weights],
        best_frame_index=best_idx,
        best_frame_sharpness=round(weights[best_idx], 6),
        deconv_iterations=deconv_iterations,
        psf_sigma=psf_sigma,
        processed_at=datetime.now(timezone.utc).isoformat(),
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
        f"- Frames with detection: {detected_count}\n"
        f"- Crop size: {crop_size[1]}x{crop_size[0]}\n"
        f"- Output size: {enhanced_uint8.shape[1]}x{enhanced_uint8.shape[0]} "
        f"({scale}x drizzle)\n"
        f"- Deconvolution: {deconv_iterations} iterations, "
        f"sigma={psf_sigma}\n"
        f"- Best frame sharpness: {weights[best_idx]:.4f} "
        f"(frame {best_idx})\n\n"
        f"*Enhanced image saved as enhanced.png*\n"
    )

    return output_dir
