"""Face-math defect diagnosis — dump every pipeline stage separately.

For one target+source pair, runs the compose pipeline step by step and
writes each intermediate so we can see exactly WHERE a defect (pink
tint, hard edge, ghosting) is introduced:

  stage_0_target        the raw input frame
  stage_1_mask          the alpha mask (grayscale)
  stage_2_warped        source warped onto target geometry (pre-colour)
  stage_3_colormatched  warped source after histogram match
  stage_4_composite     final alpha blend
  stage_X_diff          composite minus target (amplified) — shows the
                        exact pixels that changed and by how much

Usage:
    python scripts/face_math_diagnose.py <target.jpg> <source.jpg> [profile]
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent / "vibemind-os" / "spaces" / "desktop" / "Automation_ui" / "backend"
sys.path.insert(0, str(_BACKEND))

import cv2
import numpy as np

from app.services.face_math.alpha_mask import make_profile_mask
from app.services.face_math.blending import alpha_blend, histogram_match_lab
from app.services.face_math.landmark_detector import FaceLandmarkDetector
from app.services.face_math.warp import warp_source_to_target

OUT = Path("E:/Vibemind_Tools/face_math_test/diagnose")
OUT.mkdir(parents=True, exist_ok=True)


def main(argv: list[str]) -> int:
    target_path = argv[1] if len(argv) > 1 else \
        "C:/Users/User/Pictures/Camera Roll/WIN_20260520_22_09_20_Pro.jpg"
    source_path = argv[2] if len(argv) > 2 else \
        "E:/Vibemind_Tools/face_math_test/marshall_versions/marshall_v5.jpg"
    profile = argv[3] if len(argv) > 3 else "inner_face"

    target = cv2.imread(target_path)
    source = cv2.imread(source_path)
    if target is None or source is None:
        print("[err] cannot read images")
        return 1

    det = FaceLandmarkDetector.get()
    tr = det.detect(cv2.cvtColor(target, cv2.COLOR_BGR2RGB))
    sr = det.detect(cv2.cvtColor(source, cv2.COLOR_BGR2RGB))
    if tr is None or sr is None:
        print("[err] face not detected")
        return 1
    h, w = target.shape[:2]
    print(f"target {w}x{h}, profile={profile}")

    # stage 0
    cv2.imwrite(str(OUT / "stage_0_target.jpg"), target)

    # stage 1 — mask
    mask = make_profile_mask(profile, tr.landmarks_px, (w, h), feather_px=15)
    cv2.imwrite(str(OUT / "stage_1_mask.jpg"), (mask * 255).astype(np.uint8))
    print(f"  mask: coverage={100*(mask>0.5).sum()/(h*w):.1f}%  max={mask.max():.2f}")

    # stage 2 — warped (affine, as live uses)
    warped = warp_source_to_target(
        source, sr.landmarks_px, tr.landmarks_px, (w, h), method="affine"
    )
    cv2.imwrite(str(OUT / "stage_2_warped.jpg"), warped)

    # measure colour of warped source inside the mask
    sample = mask > 0.3
    if sample.sum() > 0:
        w_lab = cv2.cvtColor(warped, cv2.COLOR_BGR2LAB)
        t_lab = cv2.cvtColor(target, cv2.COLOR_BGR2LAB)
        for ch, name in enumerate("Lab"):
            ws = w_lab[..., ch][sample]
            ts = t_lab[..., ch][sample]
            print(f"  {name}: warped {ws.mean():.0f}±{ws.std():.0f}  "
                  f"target {ts.mean():.0f}±{ts.std():.0f}")

    # stage 3 — colour-matched
    colored = histogram_match_lab(warped, target, mask)
    cv2.imwrite(str(OUT / "stage_3_colormatched.jpg"), colored)

    # stage 4 — composite
    composite = alpha_blend(target, colored, mask)
    cv2.imwrite(str(OUT / "stage_4_composite.jpg"), composite)

    # diff — amplified
    diff = cv2.absdiff(composite.astype(np.int16), target.astype(np.int16))
    diff_amp = np.clip(diff * 3, 0, 255).astype(np.uint8)
    cv2.imwrite(str(OUT / "stage_X_diff_amplified.jpg"), diff_amp)

    # per-channel diff to localise a colour cast
    bdiff, gdiff, rdiff = (diff[..., i][sample].mean() for i in range(3))
    print(f"  composite-vs-target diff inside mask: "
          f"B={bdiff:.1f} G={gdiff:.1f} R={rdiff:.1f}")
    if rdiff > gdiff + 4 and rdiff > bdiff + 4:
        print("  >>> RED CAST detected (R dominates the delta)")
    elif bdiff > gdiff + 4 and bdiff > rdiff + 4:
        print("  >>> BLUE CAST detected")

    print(f"\nWrote 6 stage images to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
