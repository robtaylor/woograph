"""VLM-guided scene detection for video processing.

Segments a video into scenes using histogram similarity, then classifies
each scene via a Vision LLM (title card, footage, credits, etc.).
Returns the frame range of the main footage section.
"""

import json
import logging
from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

from woograph.llm import LLMConfig, create_vision_completion

logger = logging.getLogger(__name__)


@dataclass
class SceneInfo:
    """Information about a detected scene segment."""

    start_idx: int
    end_idx: int
    frame_count: int
    classification: str  # "footage", "title_card", "credits", "other"
    description: str


def detect_scenes(
    frames: list[NDArray[np.uint8]],
    threshold: float = 0.4,
    min_scene_frames: int = 10,
) -> list[tuple[int, int]]:
    """Detect scene boundaries using HSV histogram comparison.

    Args:
        frames: List of BGR uint8 frames.
        threshold: Bhattacharyya distance threshold for a scene cut.
        min_scene_frames: Merge scenes shorter than this into neighbors.

    Returns:
        List of (start_idx, end_idx) tuples. end_idx is exclusive.
    """
    if len(frames) < 2:
        return [(0, len(frames))]

    # Compute HSV histograms for each frame
    histograms = []
    for frame in frames:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        histograms.append(hist)

    # Find scene boundaries by comparing consecutive histograms
    cuts = [0]  # first frame is always a boundary
    for i in range(1, len(histograms)):
        dist = cv2.compareHist(histograms[i - 1], histograms[i], cv2.HISTCMP_BHATTACHARYYA)
        if dist > threshold:
            cuts.append(i)

    # Build scene list
    scenes: list[tuple[int, int]] = []
    for i, start in enumerate(cuts):
        end = cuts[i + 1] if i + 1 < len(cuts) else len(frames)
        scenes.append((start, end))

    # Merge tiny scenes into their largest neighbor
    merged: list[tuple[int, int]] = []
    for start, end in scenes:
        if end - start < min_scene_frames and merged:
            # Merge into previous scene
            prev_start, _ = merged[-1]
            merged[-1] = (prev_start, end)
        else:
            merged.append((start, end))

    logger.info(
        "Scene detection: %d cuts → %d scenes (threshold=%.2f)",
        len(cuts) - 1, len(merged), threshold,
    )
    return merged if merged else [(0, len(frames))]


def _encode_frame_jpeg(
    frame: NDArray[np.uint8],
    max_dim: int = 768,
    quality: int = 80,
) -> bytes:
    """Resize and JPEG-encode a frame for the VLM API.

    Args:
        frame: BGR uint8 frame.
        max_dim: Maximum dimension (width or height).
        quality: JPEG quality (0-100).

    Returns:
        JPEG-encoded bytes.
    """
    h, w = frame.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)  # type: ignore[assignment]

    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    assert ok, "JPEG encoding failed"
    return buf.tobytes()


def classify_scenes_vlm(
    frames: list[NDArray[np.uint8]],
    scenes: list[tuple[int, int]],
    config: LLMConfig,
) -> list[SceneInfo]:
    """Classify each scene by sending its mid-frame to a VLM.

    Args:
        frames: All extracted frames (BGR uint8).
        scenes: Scene boundaries from detect_scenes().
        config: LLM provider configuration.

    Returns:
        List of SceneInfo with classification per scene.
        Returns unclassified scenes (all "footage") on VLM failure.
    """
    # Pick mid-frame from each scene, encode as JPEG
    images: list[bytes] = []
    for start, end in scenes:
        mid = (start + end) // 2
        images.append(_encode_frame_jpeg(frames[mid]))

    n = len(scenes)
    prompt = f"""You are analyzing {n} frame(s) sampled from different sections of a video.
Each image is the mid-frame of a distinct scene segment.

For each image (numbered 1 to {n}), classify the scene as one of:
- "footage": actual video content showing sky, landscape, objects, or events
- "title_card": text overlay, intro screen, channel name, video title, or watermark-dominated frame
- "credits": end credits, attribution text, or outro
- "other": anything else (blank frames, test patterns, etc.)

Also provide a brief description of what you see in each frame.

Respond in JSON format:
{{
  "scenes": [
    {{"scene": 1, "classification": "title_card", "description": "White text on black background showing video title"}},
    {{"scene": 2, "classification": "footage", "description": "Night sky with bright elongated object"}}
  ]
}}

Rules:
- Focus on whether the frame shows actual video content vs. overlaid text/graphics
- If a frame has both footage and text overlay, classify based on the dominant content
- Be concise in descriptions (under 20 words each)"""

    response = create_vision_completion(
        config, prompt, images, max_tokens=1024, json_mode=True,
    )

    if not response:
        logger.warning("VLM classification returned no response, treating all as footage")
        return _default_scenes(scenes)

    try:
        data = json.loads(response)
        vlm_scenes = data.get("scenes", [])
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("Failed to parse VLM response: %s", exc)
        return _default_scenes(scenes)

    results: list[SceneInfo] = []
    for i, (start, end) in enumerate(scenes):
        # Find matching VLM result (1-indexed)
        vlm_entry = next(
            (s for s in vlm_scenes if s.get("scene") == i + 1),
            None,
        )
        classification = "footage"
        description = ""
        if vlm_entry:
            classification = vlm_entry.get("classification", "footage")
            description = vlm_entry.get("description", "")
            # Normalize classification
            if classification not in ("footage", "title_card", "credits", "other"):
                classification = "footage"

        results.append(SceneInfo(
            start_idx=start,
            end_idx=end,
            frame_count=end - start,
            classification=classification,
            description=description,
        ))

    for s in results:
        logger.info(
            "Scene %d-%d (%d frames): %s — %s",
            s.start_idx, s.end_idx, s.frame_count, s.classification, s.description,
        )
    return results


def _default_scenes(scenes: list[tuple[int, int]]) -> list[SceneInfo]:
    """Return all scenes classified as footage (fallback)."""
    return [
        SceneInfo(
            start_idx=start,
            end_idx=end,
            frame_count=end - start,
            classification="footage",
            description="",
        )
        for start, end in scenes
    ]


def get_footage_range(
    scenes: list[SceneInfo],
    total_frames: int,
) -> tuple[int, int]:
    """Return (start, end) frame indices of the footage portion.

    Spans from the first footage scene start to the last footage scene end,
    including any non-footage gaps between them (short title cards or
    interstitials that the detection pipeline will naturally skip).
    Falls back to full range if no footage found.

    Args:
        scenes: Classified scene list.
        total_frames: Total number of frames.

    Returns:
        (start_idx, end_idx) tuple. end_idx is exclusive.
    """
    footage = [s for s in scenes if s.classification == "footage"]

    if not footage:
        logger.warning("No footage scenes found, using all frames")
        return (0, total_frames)

    # Use the longest footage scene — compilation videos contain multiple
    # unrelated clips and mixing them breaks the temporal median background
    # model used for object detection.
    longest = max(footage, key=lambda s: s.frame_count)
    start, end = longest.start_idx, longest.end_idx

    logger.info(
        "Footage range: frames %d-%d (%d frames, %.1f%% of video)",
        start, end, end - start,
        (end - start) / total_frames * 100,
    )
    return (start, end)
