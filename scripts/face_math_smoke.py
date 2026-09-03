"""
Face-Math Smoke-Test
====================

Phase A-Lite: prove that MediaPipe FaceMesh delivers the geometric
precision needed for region-composite face-swapping. Loads one or
more reference photos, runs FaceLandmarker, overlays 478 landmarks
plus colored region polygons (lips / eyes / brows / nose / face oval),
and writes annotated copies next to the originals.

Usage:
    python scripts/face_math_smoke.py [<image1> <image2> ...]

If no args given, processes the two reference photos in
C:/Users/User/Pictures/Camera Roll/WIN_20260520_22_09_2*.jpg
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/latest/face_landmarker.task"
)
MODEL_PATH = Path("E:/Vibemind_Tools/face_math_test/face_landmarker.task")
OUT_DIR = Path("E:/Vibemind_Tools/face_math_test")

DEFAULT_IMAGES = [
    Path(r"C:/Users/User/Pictures/Camera Roll/WIN_20260520_22_09_20_Pro.jpg"),
    Path(r"C:/Users/User/Pictures/Camera Roll/WIN_20260520_22_09_29_Pro.jpg"),
]

# Region polygon indices from mediapipe FACEMESH_* constants. These are
# the well-known FaceMesh topology subsets — same ones VisoMaster and
# every other tool reads. We render each region with its own color so
# you can visually verify the math hits the right pixels.
#
# Source: https://github.com/google/mediapipe/blob/master/mediapipe/python/solutions/face_mesh_connections.py
REGIONS = {
    "lips_outer": (
        # outer lip ring (clockwise)
        [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291,
         409, 270, 269, 267, 0, 37, 39, 40, 185, 61],
        (50, 50, 255),  # red (BGR)
    ),
    "lips_inner": (
        [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308,
         415, 310, 311, 312, 13, 82, 81, 80, 191, 78],
        (50, 150, 255),  # orange
    ),
    "left_eye": (
        # subject's LEFT (viewer's right) eye outline
        [263, 249, 390, 373, 374, 380, 381, 382, 362,
         263, 466, 388, 387, 386, 385, 384, 398, 362],
        (255, 200, 50),  # cyan
    ),
    "right_eye": (
        # subject's RIGHT (viewer's left)
        [33, 7, 163, 144, 145, 153, 154, 155, 133,
         33, 246, 161, 160, 159, 158, 157, 173, 133],
        (255, 200, 50),
    ),
    "left_brow": (
        [276, 283, 282, 295, 285, 336, 296, 334, 293, 300],
        (50, 255, 50),  # green
    ),
    "right_brow": (
        [46, 53, 52, 65, 55, 107, 66, 105, 63, 70],
        (50, 255, 50),
    ),
    "nose_bridge": (
        [168, 6, 197, 195, 5, 4, 1],
        (200, 100, 255),  # pink
    ),
    "face_oval": (
        [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361,
         288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149,
         150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103,
         67, 109, 10],
        (255, 255, 255),  # white
    ),
}


# ---------------------------------------------------------------------------
# Model fetch
# ---------------------------------------------------------------------------

def ensure_model() -> Path:
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 1_000_000:
        return MODEL_PATH
    print(f"[download] face_landmarker.task -> {MODEL_PATH}")
    urllib.request.urlretrieve(MODEL_URL, str(MODEL_PATH))
    size_mb = MODEL_PATH.stat().st_size / 1024 / 1024
    print(f"[download] done — {size_mb:.1f} MB")
    return MODEL_PATH


# ---------------------------------------------------------------------------
# Inference + overlay
# ---------------------------------------------------------------------------

def make_landmarker(model_path: Path) -> mp_vision.FaceLandmarker:
    base = mp_python.BaseOptions(model_asset_path=str(model_path))
    options = mp_vision.FaceLandmarkerOptions(
        base_options=base,
        running_mode=mp_vision.RunningMode.IMAGE,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=True,
    )
    return mp_vision.FaceLandmarker.create_from_options(options)


def landmarks_to_pixels(landmarks, w: int, h: int) -> np.ndarray:
    """Convert normalized (x,y,z) → pixel (x_px, y_px) Nx2 int32."""
    arr = np.array(
        [(lm.x * w, lm.y * h) for lm in landmarks],
        dtype=np.float32,
    )
    return arr.astype(np.int32)


def draw_overlay(img: np.ndarray, pixels: np.ndarray) -> np.ndarray:
    """Return a copy of img with all 478 landmarks + region polygons drawn."""
    out = img.copy()

    # 1. Every landmark as a small filled circle (faint, so polygons pop).
    for x, y in pixels:
        cv2.circle(out, (int(x), int(y)), 1, (180, 180, 180), -1)

    # 2. Region polygons with per-region color.
    for name, (idxs, color) in REGIONS.items():
        pts = pixels[idxs].reshape(-1, 1, 2)
        cv2.polylines(out, [pts], isClosed=False, color=color, thickness=2)

    # 3. Caption — print key blendshapes onto image for sanity-check.
    return out


def annotate_blendshapes(out: np.ndarray, blendshapes) -> np.ndarray:
    """Print top-5 active blendshapes (mouth-open, smile, blink…) as text."""
    if not blendshapes:
        return out
    # blendshapes is a list of one face's classifications; pick top by score
    cats = blendshapes[0]
    sorted_cats = sorted(cats, key=lambda c: c.score, reverse=True)[:6]
    y = 30
    for c in sorted_cats:
        label = f"{c.category_name}: {c.score:.2f}"
        cv2.putText(
            out, label, (12, y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1, cv2.LINE_AA,
        )
        y += 22
    return out


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def process(image_path: Path, landmarker: mp_vision.FaceLandmarker) -> Path | None:
    bgr = cv2.imread(str(image_path))
    if bgr is None:
        print(f"[err] cannot read {image_path}")
        return None
    h, w = bgr.shape[:2]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    result = landmarker.detect(mp_image)
    if not result.face_landmarks:
        print(f"[warn] no face in {image_path.name}")
        return None

    landmarks = result.face_landmarks[0]
    pixels = landmarks_to_pixels(landmarks, w, h)
    print(
        f"[ok] {image_path.name}: {len(landmarks)} landmarks, "
        f"{w}x{h}px"
    )

    out = draw_overlay(bgr, pixels)
    out = annotate_blendshapes(out, result.face_blendshapes)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{image_path.stem}__landmarks.jpg"
    cv2.imwrite(str(out_path), out, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(f"[ok] wrote {out_path}")

    # Also dump raw landmark array for downstream phases.
    npz_path = OUT_DIR / f"{image_path.stem}__landmarks.npz"
    blend = {}
    if result.face_blendshapes:
        for c in result.face_blendshapes[0]:
            blend[c.category_name] = c.score
    np.savez(
        npz_path,
        landmarks_px=pixels,
        landmarks_norm=np.array(
            [(lm.x, lm.y, lm.z) for lm in landmarks], dtype=np.float32
        ),
        image_size=np.array([w, h], dtype=np.int32),
        blendshapes=np.array(list(blend.items()), dtype=object),
    )
    print(f"[ok] wrote {npz_path}")
    return out_path


def main(argv: list[str]) -> int:
    images = [Path(p) for p in argv[1:]] if len(argv) > 1 else DEFAULT_IMAGES
    model = ensure_model()
    landmarker = make_landmarker(model)
    print(f"[init] FaceLandmarker ready, processing {len(images)} image(s)\n")

    results = []
    for img in images:
        if not img.exists():
            print(f"[skip] missing: {img}")
            continue
        out = process(img, landmarker)
        if out:
            results.append(out)
    landmarker.close()

    print()
    print("=" * 60)
    print(f"Wrote {len(results)} annotated images to {OUT_DIR}:")
    for r in results:
        print(f"  - {r}")
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
