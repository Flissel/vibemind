"""Phase B static-composite test.

Loads a target frame + a source face, computes 478 landmarks on each,
and runs the region-compositor for every swap profile + every individual
region. Writes the outputs side-by-side for visual verification.

Usage:
    python scripts/face_math_compose_test.py <target.jpg> <source.jpg>

Default args use the two camera-roll photos for a "swap myself with
myself in a different pose" sanity check — perfect for proving the
geometry/warp math without needing an Eminem source yet.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Make backend package importable
_BACKEND = Path(__file__).resolve().parent.parent / "vibemind-os" / "spaces" / "desktop" / "Automation_ui" / "backend"
sys.path.insert(0, str(_BACKEND))

import cv2
import numpy as np

from app.services.face_math.alpha_mask import (
    make_all_region_masks,
    visualise_mask,
)
from app.services.face_math.compositor import compose_from_paths, compose
from app.services.face_math.landmark_detector import FaceLandmarkDetector
from app.services.face_math.regions import REGION_BY_NAME, SWAP_PROFILES


OUT_DIR = Path("E:/Vibemind_Tools/face_math_test/compose_out")
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TARGET = "C:/Users/User/Pictures/Camera Roll/WIN_20260520_22_09_20_Pro.jpg"
DEFAULT_SOURCE = "C:/Users/User/Pictures/Camera Roll/WIN_20260520_22_09_29_Pro.jpg"


def hstack_with_label(images: list[np.ndarray], labels: list[str]) -> np.ndarray:
    """Concatenate horizontally with text overlays."""
    h = max(img.shape[0] for img in images)
    resized = []
    for img, label in zip(images, labels):
        if img.shape[0] != h:
            scale = h / img.shape[0]
            new_w = int(img.shape[1] * scale)
            img = cv2.resize(img, (new_w, h))
        # add label bar at top
        bar = np.zeros((40, img.shape[1], 3), dtype=np.uint8)
        cv2.putText(bar, label, (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        resized.append(np.vstack([bar, img]))
    return np.hstack(resized)


def main(argv: list[str]) -> int:
    target_path = argv[1] if len(argv) > 1 else DEFAULT_TARGET
    source_path = argv[2] if len(argv) > 2 else DEFAULT_SOURCE
    print(f"target: {target_path}")
    print(f"source: {source_path}")
    print(f"outputs: {OUT_DIR}\n")

    target = cv2.imread(target_path)
    source = cv2.imread(source_path)
    if target is None or source is None:
        print(f"[err] cannot read images")
        return 1

    detector = FaceLandmarkDetector.get()
    target_result = detector.detect(cv2.cvtColor(target, cv2.COLOR_BGR2RGB))
    source_result = detector.detect(cv2.cvtColor(source, cv2.COLOR_BGR2RGB))
    if target_result is None:
        print(f"[err] no face in target")
        return 1
    if source_result is None:
        print(f"[err] no face in source")
        return 1
    print(f"target: {target_result.landmarks_px.shape[0]} landmarks")
    print(f"source: {source_result.landmarks_px.shape[0]} landmarks\n")

    # ------- 1. Per-region masks visualisation -------
    print("=== Per-region alpha-masks ===")
    masks = make_all_region_masks(
        target_result.landmarks_px,
        target_result.image_size,
        feather_px=15,
    )
    overlays = []
    labels = []
    for name, mask in masks.items():
        region = REGION_BY_NAME[name]
        ov = visualise_mask(target, mask, color=region.color, alpha_strength=0.6)
        overlays.append(cv2.resize(ov, (480, 270)))
        labels.append(f"{name} (max={mask.max():.2f})")

    rows = []
    per_row = 4
    for i in range(0, len(overlays), per_row):
        row_imgs = overlays[i:i + per_row]
        row_lbls = labels[i:i + per_row]
        # pad if short
        while len(row_imgs) < per_row:
            row_imgs.append(np.zeros_like(overlays[0]))
            row_lbls.append("")
        rows.append(hstack_with_label(row_imgs, row_lbls))
    region_grid = np.vstack(rows)
    cv2.imwrite(str(OUT_DIR / "01_per_region_masks.jpg"), region_grid,
                [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(f"  -> {OUT_DIR}/01_per_region_masks.jpg\n")

    # ------- 2. One composite per SWAP_PROFILE, both warp methods -------
    print("=== Composites per swap profile ===")
    composites = []
    comp_labels = []
    composites.append(cv2.resize(target, (480, 270)))
    comp_labels.append("target (you)")
    composites.append(cv2.resize(source, (480, 270)))
    comp_labels.append("source (eminem stand-in)")

    for profile_name in SWAP_PROFILES:
        t0 = time.time()
        try:
            result = compose(
                target_frame_bgr=target,
                target_landmarks_px=target_result.landmarks_px,
                source_image_bgr=source,
                source_landmarks_px=source_result.landmarks_px,
                profile=profile_name,
                warp_method="tps",
                feather_px=15,
                apply_color_match=True,
            )
        except Exception as e:
            print(f"  ! {profile_name}: {e}")
            continue
        dt = time.time() - t0
        cv2.imwrite(
            str(OUT_DIR / f"02_profile__{profile_name}.jpg"),
            result.composite, [cv2.IMWRITE_JPEG_QUALITY, 92],
        )
        # also save the mask for inspection
        mask_vis = (result.mask * 255).astype(np.uint8)
        cv2.imwrite(
            str(OUT_DIR / f"02_profile__{profile_name}__mask.jpg"),
            mask_vis, [cv2.IMWRITE_JPEG_QUALITY, 88],
        )
        print(f"  {profile_name}: {dt*1000:.0f}ms")
        composites.append(cv2.resize(result.composite, (480, 270)))
        comp_labels.append(profile_name)

    # Grid of all composites
    rows = []
    per_row = 4
    for i in range(0, len(composites), per_row):
        row_imgs = composites[i:i + per_row]
        row_lbls = comp_labels[i:i + per_row]
        while len(row_imgs) < per_row:
            row_imgs.append(np.zeros_like(composites[0]))
            row_lbls.append("")
        rows.append(hstack_with_label(row_imgs, row_lbls))
    grid = np.vstack(rows)
    cv2.imwrite(str(OUT_DIR / "03_profile_grid.jpg"), grid,
                [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(f"\n  -> {OUT_DIR}/03_profile_grid.jpg\n")

    # ------- 2b. Blend-mode A/B comparison -------
    print("=== Blend modes A/B (inner_face) ===")
    blend_results = []
    blend_labels = []
    blend_results.append(cv2.resize(target, (480, 270)))
    blend_labels.append("target")
    for mode in ("alpha", "hybrid", "poisson", "poisson_mixed"):
        try:
            r = compose(
                target_frame_bgr=target,
                target_landmarks_px=target_result.landmarks_px,
                source_image_bgr=source,
                source_landmarks_px=source_result.landmarks_px,
                profile="inner_face",
                warp_method="tps",
                feather_px=15,
                color_match_method="histogram",
                blend_mode=mode,
            )
            cv2.imwrite(
                str(OUT_DIR / f"05_blend__{mode}.jpg"),
                r.composite, [cv2.IMWRITE_JPEG_QUALITY, 92],
            )
            blend_results.append(cv2.resize(r.composite, (480, 270)))
            blend_labels.append(f"blend={mode}")
            print(f"  blend={mode}: OK")
        except Exception as e:
            print(f"  ! blend={mode}: {e}")
    grid = hstack_with_label(blend_results, blend_labels)
    cv2.imwrite(str(OUT_DIR / "05_blend_compare.jpg"), grid,
                [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(f"  -> {OUT_DIR}/05_blend_compare.jpg\n")

    # ------- 2c. Color-match method A/B -------
    print("=== Color-match methods A/B (inner_face, alpha-blend) ===")
    cm_results = []
    cm_labels = []
    cm_results.append(cv2.resize(target, (480, 270)))
    cm_labels.append("target")
    for cm in ("mean_std", "histogram"):
        r = compose(
            target_frame_bgr=target,
            target_landmarks_px=target_result.landmarks_px,
            source_image_bgr=source,
            source_landmarks_px=source_result.landmarks_px,
            profile="inner_face",
            warp_method="tps",
            feather_px=15,
            color_match_method=cm,
            blend_mode="alpha",
        )
        cm_results.append(cv2.resize(r.composite, (480, 270)))
        cm_labels.append(f"color={cm}")
        print(f"  color={cm}: OK")
    grid = hstack_with_label(cm_results, cm_labels)
    cv2.imwrite(str(OUT_DIR / "06_color_compare.jpg"), grid,
                [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(f"  -> {OUT_DIR}/06_color_compare.jpg\n")

    # ------- 3. Affine vs TPS comparison (one profile) -------
    print("=== Affine vs TPS warp comparison ===")
    a = compose(
        target_frame_bgr=target,
        target_landmarks_px=target_result.landmarks_px,
        source_image_bgr=source,
        source_landmarks_px=source_result.landmarks_px,
        profile="inner_face",
        warp_method="affine",
        feather_px=15,
    )
    t = compose(
        target_frame_bgr=target,
        target_landmarks_px=target_result.landmarks_px,
        source_image_bgr=source,
        source_landmarks_px=source_result.landmarks_px,
        profile="inner_face",
        warp_method="tps",
        feather_px=15,
    )
    pair = hstack_with_label(
        [cv2.resize(target, (640, 360)),
         cv2.resize(a.composite, (640, 360)),
         cv2.resize(t.composite, (640, 360))],
        ["original", "affine warp", "tps warp"],
    )
    cv2.imwrite(str(OUT_DIR / "04_affine_vs_tps.jpg"), pair,
                [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(f"  -> {OUT_DIR}/04_affine_vs_tps.jpg\n")

    print("All outputs written. Open the JPEGs to verify the math.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
