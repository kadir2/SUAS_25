#!/usr/bin/env python3
import subprocess, os, time

# ───────── CONFIG ──────────────────────────────────────────────
GROUND_IP   = "100.118.155.118"          # Tailscale IP of ground computer
GROUND_DIR  = "/home/aziz/incoming"      # Directory ground script watches
SSH_USER    = "aziz"                     # User on ground computer
FRAME_RATE_FALLBACK = 30
# ----------------------------------------------------------------

def check_connection():
    print(f"Checking connectivity to {SSH_USER}@{GROUND_IP}...")
    while True:
        try:
            subprocess.check_call(
                ["ssh", "-o", "BatchMode=yes", "-q", f"{SSH_USER}@{GROUND_IP}", "exit"]
            )
            print("Connectivity OK")
            break
        except subprocess.CalledProcessError:
            print("Connectivity failed, retrying in 5 seconds...")
            time.sleep(5)


def send_video(local_path: str):
    """
    Copy file to ground computer, then atomically rename it so the watcher
    starts only after the transfer is complete.  Retries indefinitely on
    any failure with exponential back-off that maxes out at 300 s.
    """
    check_connection()
    tmp = os.path.basename(local_path) + ".part"
    delay = 5                       # seconds; initial back-off
    attempt = 1

    while True:
        try:
            subprocess.check_call([
                "scp", "-q", local_path,
                f"{SSH_USER}@{GROUND_IP}:{GROUND_DIR}/{tmp}"
            ])
            subprocess.check_call([
                "ssh", f"{SSH_USER}@{GROUND_IP}",
                f"mv {GROUND_DIR}/{tmp} {GROUND_DIR}/{os.path.basename(local_path)}"
            ])
            print(f"Video sent → {GROUND_IP}:{GROUND_DIR}")
            break                              # success – exit loop
        except subprocess.CalledProcessError as e:
            print(f"SCP failed (attempt {attempt}): {e}")
        except Exception as e:
            print(f"Unexpected error (attempt {attempt}): {e}")

        attempt += 1
        print(f"Retrying in {delay} s…")
        time.sleep(delay)
        delay = min(delay * 2, 300)   # exponential back-off, max 5 min

# Example usage
send_video("video.mp4")
