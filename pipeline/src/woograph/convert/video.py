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


def _detect_and_track(
    frames: list[NDArray[np.uint8]],
    min_area: int = 100,
    warmup_frames: int = 10,
) -> list[BBox | None]:
    """Detect the primary moving object in each frame via MOG2 + contours.

    The background subtractor needs a warmup period. After warmup, the largest
    contour above min_area is taken as the object in each frame.
    """
    bg_sub = cv2.createBackgroundSubtractorMOG2(
        history=max(warmup_frames * 2, 120),
        varThreshold=50,
        detectShadows=True,
    )
    bboxes: list[BBox | None] = []

    for i, frame in enumerate(frames):
        fg_mask = bg_sub.apply(frame)
        # Threshold: 255 = foreground, 127 = shadow (ignore shadows)
        _, thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

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

        # Pick the largest contour above min_area
        best: BBox | None = None
        best_area = 0
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area >= min_area and area > best_area:
                x, y, w, h = cv2.boundingRect(cnt)
                best = BBox(x, y, w, h)
                best_area = area

        bboxes.append(best)

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
) -> tuple[list[NDArray[np.float64]], list[tuple[float, float]]]:
    """Sub-pixel align crops using phase cross-correlation.

    Uses the first crop as the reference. Returns aligned crops (float64,
    0-255 range) and the measured shifts.
    """
    assert len(crops) > 0

    # Convert to grayscale float for correlation
    ref_gray = cv2.cvtColor(crops[0], cv2.COLOR_BGR2GRAY).astype(np.float64)

    aligned: list[NDArray[np.float64]] = [crops[0].astype(np.float64)]
    shifts: list[tuple[float, float]] = [(0.0, 0.0)]

    for crop in crops[1:]:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float64)
        shift, _error, _phasediff = phase_cross_correlation(
            ref_gray, gray, upsample_factor=upsample_factor,
        )

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

    logger.info("Aligned %d crops (max shift: %.2f px)", len(aligned),
                max(max(abs(s[0]), abs(s[1])) for s in shifts))
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


def _drizzle_stack(
    aligned: list[NDArray[np.float64]],
    weights: list[float],
    scale: int = 2,
) -> NDArray[np.float64]:
    """Shift-and-add super-resolution via drizzle algorithm.

    Each aligned crop is placed onto an upscaled canvas. Pixel contributions
    are weighted by the frame's sharpness score.
    """
    assert len(aligned) == len(weights)
    assert len(aligned) > 0

    h, w, c = aligned[0].shape
    out_h, out_w = h * scale, w * scale

    canvas = np.zeros((out_h, out_w, c), dtype=np.float64)
    weight_map = np.zeros((out_h, out_w), dtype=np.float64)

    for crop, wt in zip(aligned, weights):
        if wt <= 0:
            continue

        # Upscale the crop using bicubic interpolation
        upscaled = cv2.resize(
            crop, (out_w, out_h), interpolation=cv2.INTER_CUBIC,
        )

        # Mask: only accumulate non-zero pixels (avoid border artifacts)
        mask = np.any(upscaled > 1.0, axis=2).astype(np.float64)

        for ch in range(c):
            canvas[:, :, ch] += upscaled[:, :, ch] * wt * mask

        weight_map += wt * mask

    # Normalize by total weight per pixel
    weight_map = np.maximum(weight_map, 1e-10)
    for ch in range(c):
        canvas[:, :, ch] /= weight_map

    logger.info("Drizzle stack: %dx%d at %dx scale", out_w, out_h, scale)
    return canvas


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

    # Step 2: Detect and track object
    bboxes = _detect_and_track(
        frames, min_area=min_object_area, warmup_frames=warmup_frames,
    )

    detected_count = sum(1 for b in bboxes if b is not None)
    if detected_count < 3:
        logger.warning(
            "Only %d frames with detections — need at least 3 for stacking",
            detected_count,
        )
        # Fall back: save the middle frame as best_frame
        mid = len(frames) // 2
        best_path = output_dir / "best_frame.png"
        cv2.imwrite(str(best_path), frames[mid])
        meta = ProcessingMetadata(
            video_path=str(video_path),
            total_frames=total_frames,
            extracted_frames=total_frames,
            detected_frames=detected_count,
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

    # Step 4: Align crops via phase correlation
    aligned, shifts = _align_crops(crops)

    # Step 5: Compute sharpness weights
    weights = _compute_sharpness(crops)

    # Step 6: Best frame (for comparison output)
    best_idx = int(np.argmax(weights))
    best_crop = np.clip(aligned[best_idx], 0, 255).astype(np.uint8)
    best_path = output_dir / "best_frame.png"
    cv2.imwrite(str(best_path), best_crop)
    logger.info(
        "Best frame: index %d, sharpness weight %.4f", best_idx, weights[best_idx],
    )

    # Step 7: Drizzle super-resolution stack
    stacked = _drizzle_stack(aligned, weights, scale=scale)

    # Step 8: Richardson-Lucy deconvolution
    enhanced = _richardson_lucy_deconv(
        stacked, psf_sigma=psf_sigma, iterations=deconv_iterations,
    )

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
