"""
Guided enrollment capture tool.

Walks the person through several poses (including mid/far distance and a
looking-up angle, matching a top-corner camera) with on-screen prompts,
captures N frames per pose, then automatically runs enrollment — all in one
command. Default is 8 poses x 3 shots = 24 frames; more variety + more samples
= better recognition across angles and distances.

Usage:
    python scripts/capture_enrollment_frames.py <name> [--shots N]

Example:
    python scripts/capture_enrollment_frames.py joshua            # 3 shots/pose (24 total)
    python scripts/capture_enrollment_frames.py joshua --shots 5  # 5 shots/pose (40 total)

Controls during capture:
    SPACE — capture current pose frame
    Q     — quit without saving

Why this matters: enrolling from phone photos vs. the IP webcam produces
embedding mismatches because ArcFace is sensitive to camera characteristics
(optics, compression, color balance). This script captures directly from the
same Pixel 4a stream the live pipeline uses, so embeddings match exactly.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import cv2
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
from loguru import logger

from engine.utils.stream import VideoStream

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FACES_DIR = PROJECT_ROOT / "data" / "faces"

# Guided poses. Distance + looking-up poses mirror a top-corner camera, so the
# recognizer gets reference embeddings at the angles/face-sizes it'll actually
# see at runtime — not just close-up frontal shots.
POSES = [
    ("LOOK STRAIGHT at the camera",            "straight"),
    ("TURN SLIGHTLY LEFT",                     "left"),
    ("TURN SLIGHTLY RIGHT",                    "right"),
    ("LOOK UP (as if at a high corner camera)", "up"),
    ("LOOK SLIGHTLY DOWN",                     "down"),
    ("STEP BACK a few steps (mid distance)",   "mid"),
    ("STEP BACK further away (far)",           "far"),
    ("ANY ANGLE you like (last one!)",         "free"),
]
DEFAULT_SHOTS_PER_POSE = 3


def draw_ui(frame, instruction: str, pose_num: int, total_poses: int,
            captured_this_pose: int, needed: int, total_captured: int):
    """Draw the guided capture overlay onto the frame."""
    h, w = frame.shape[:2]

    # Dark top bar
    cv2.rectangle(frame, (0, 0), (w, 90), (30, 30, 30), -1)

    # Pose progress
    cv2.putText(frame, f"Pose {pose_num}/{total_poses}",
                (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 200, 255), 2)

    # Main instruction
    cv2.putText(frame, instruction,
                (12, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 128), 2)

    # Bottom bar
    cv2.rectangle(frame, (0, h - 50), (w, h), (30, 30, 30), -1)

    remaining = needed - captured_this_pose
    cv2.putText(
        frame,
        f"SPACE = capture  ({remaining} more for this pose)  |  Total: {total_captured}  |  Q = quit",
        (12, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1,
    )

    # Flash green border when a capture just happened
    return frame


def main():
    parser = argparse.ArgumentParser(
        description="Guided enrollment capture — walks through poses and auto-enrolls."
    )
    parser.add_argument("name", help="Person's name (e.g. jordan, joshua)")
    parser.add_argument(
        "--shots", type=int, default=DEFAULT_SHOTS_PER_POSE,
        help=f"Frames captured per pose (default {DEFAULT_SHOTS_PER_POSE}; "
             f"{len(POSES)} poses, so total = shots x {len(POSES)})",
    )
    args = parser.parse_args()

    shots_per_pose = max(1, args.shots)
    name = args.name.lower().strip()
    save_dir = FACES_DIR / name
    save_dir.mkdir(parents=True, exist_ok=True)

    # Remove old photos for this person so we start fresh
    old_photos = [f for f in save_dir.iterdir()
                  if f.suffix.lower() in {".jpg", ".jpeg", ".png"}]
    if old_photos:
        logger.info(f"Removing {len(old_photos)} old photo(s) for '{name}'...")
        for f in old_photos:
            f.unlink()

    logger.info(f"Starting guided capture for '{name}'. Photos → {save_dir}")

    stream = VideoStream()
    try:
        stream.start()
    except ConnectionError as e:
        logger.error(str(e))
        return

    logger.success("Stream connected. Follow the on-screen prompts.")

    total_captured = 0
    aborted = False

    for pose_idx, (instruction, pose_tag) in enumerate(POSES):
        captured_this_pose = 0
        logger.info(f"Pose {pose_idx + 1}/{len(POSES)}: {instruction}")

        while captured_this_pose < shots_per_pose:
            frame = stream.read()
            if frame is None:
                continue

            display = frame.copy()
            draw_ui(
                display,
                instruction,
                pose_idx + 1, len(POSES),
                captured_this_pose, shots_per_pose,
                total_captured,
            )

            cv2.imshow(f"Enrollment — {name}", display)
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                logger.warning("Capture aborted.")
                aborted = True
                break

            if key == ord(' '):
                ts = datetime.now().strftime("%H%M%S_%f")[:9]
                filename = save_dir / f"{name}_{pose_tag}_{ts}.jpg"
                cv2.imwrite(str(filename), frame)
                captured_this_pose += 1
                total_captured += 1
                logger.success(f"  ✓ Captured {filename.name} ({captured_this_pose}/{shots_per_pose})")

                # Brief green flash feedback
                flash = frame.copy()
                cv2.rectangle(flash, (0, 0), (flash.shape[1], flash.shape[0]), (0, 255, 0), 8)
                cv2.putText(flash, "CAPTURED!", (flash.shape[1]//2 - 80, flash.shape[0]//2),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
                cv2.imshow(f"Enrollment — {name}", flash)
                cv2.waitKey(300)

        if aborted:
            break

    stream.stop()
    cv2.destroyAllWindows()

    if aborted or total_captured == 0:
        logger.error("No frames saved — enrollment cancelled.")
        return

    logger.success(f"Captured {total_captured} frames for '{name}'.")
    logger.info("Running enrollment automatically...")

    # Auto-enroll
    enroll_script = PROJECT_ROOT / "scripts" / "enroll_face.py"
    result = subprocess.run(
        [sys.executable, str(enroll_script), name],
        cwd=str(PROJECT_ROOT),
    )

    if result.returncode == 0:
        logger.success(f"Enrollment complete for '{name}'!")
    else:
        logger.error("Enrollment script returned an error — check output above.")


if __name__ == "__main__":
    main()