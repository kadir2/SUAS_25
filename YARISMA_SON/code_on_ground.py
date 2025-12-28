#!/usr/bin/env python3
"""
ground_mapper.py – watch /opt/incoming for new *.mp4 files,
extract frames, run OpenDroneMap, copy results to USB.
"""

import time, subprocess, logging, shutil, os, pathlib, sys
from datetime import datetime
from typing import Optional      # ← NEW

# ───── CONFIG ──────────────────
WATCH_DIR = pathlib.Path.home() / "incoming"           # e.g. /home/aziz/incoming
ODM_ROOT  = pathlib.Path.home() / "odm_projects"       # e.g. /home/aziz/odm_projects"
FRAME_STEP  = 7
USB_PARENT  = pathlib.Path("/media") / os.getenv("USER")
ODM_CMD     = "odm"              # "docker run …" if you prefer
# ----------------------------------------------------------------

logging.basicConfig(
    filename="ground_mapper.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("ground_mapper")


def file_is_stable(path: pathlib.Path, window_s: int = 4) -> bool:
    size = path.stat().st_size
    time.sleep(window_s)
    return size == path.stat().st_size


def extract_frames(mp4: pathlib.Path, img_dir: pathlib.Path, step: int):
    img_dir.mkdir(parents=True, exist_ok=True)
    subprocess.check_call([
        "ffmpeg", "-ss", "1","-loglevel", "error", "-i", str(mp4),
        "-vf", f"select='not(mod(n\\,{step}))'",
        "-vsync", "vfr",
        str(img_dir / "frame_%05d.jpg")
    ])


def run_odm(project_dir: pathlib.Path):
    subprocess.check_call(
        ODM_CMD.split() + ["--project-path", str(project_dir.parent), project_dir.name]
    )


def first_usb_mount() -> Optional[pathlib.Path]:   # ← CHANGED
    if not USB_PARENT.exists():
        return None
    mounts = sorted(USB_PARENT.iterdir(),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True)
    for m in mounts:
        if m.is_dir() and os.access(m, os.W_OK):
            return m
    return None


def copy_to_usb(src: pathlib.Path):
    target = first_usb_mount()
    if not target:
        log.warning("No writable USB drive detected – results stay on SSD.")
        return
    dest = target / src.name
    shutil.copytree(src, dest, dirs_exist_ok=True)
    log.info(f"Copied results to USB: {dest}")


def process_video(mp4: pathlib.Path):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    proj_dir = ODM_ROOT / f"run_{ts}"
    img_dir  = proj_dir / "images"

    log.info(f"=== Processing {mp4.name} → {proj_dir}")
    extract_frames(mp4, img_dir, FRAME_STEP)

    print('extracted frames.')




    # run_odm(proj_dir)

    ortho_dir = proj_dir / "odm_orthophoto"
    if ortho_dir.exists():
        copy_to_usb(ortho_dir)
    else:
        log.error("ODM completed but orthophoto folder not found.")

    mp4.unlink()
    log.info(f"{mp4.name} done and deleted.")


def main():
    # Ensure incoming directory exists
    WATCH_DIR.mkdir(parents=True, exist_ok=True)

    # Move any existing .mp4 files into an old_videos folder
    old_dir = WATCH_DIR / "old_videos"
    old_dir.mkdir(parents=True, exist_ok=True)
    for mp4 in WATCH_DIR.glob("*.mp4"):
        try:
            shutil.move(str(mp4), str(old_dir / mp4.name))
            log.info(f"Moved old video {mp4.name} to {old_dir}")
        except Exception as e:
            log.error(f"Failed to move {mp4.name} to old_videos: {e}")

    # Ensure ODM root exists
    ODM_ROOT.mkdir(parents=True, exist_ok=True)
    seen: set[pathlib.Path] = set()

    log.info("Ground mapper started – watching for videos …")
    try:
        while True:
            time.sleep(1)
            print('waiting for videos to come.')
            for mp4 in WATCH_DIR.glob("*.mp4"):
                if mp4 in seen:
                    print('mp4 in seen')
                    continue
                if not file_is_stable(mp4):
                    print('file is not stable.')
                    continue
                try:
                    print('processing video now.')
                    process_video(mp4)     # ← RE-ACTIVATED when ready
                    sys.exit(0)
                except Exception as e:
                    log.exception(f"Failed on {mp4}: {e}")
                seen.add(mp4)
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Ground mapper interrupted, exiting.")


if __name__ == "__main__":
    main()