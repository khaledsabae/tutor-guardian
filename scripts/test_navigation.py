#!/usr/bin/env python3
import os
import subprocess
import time

ANDROID_HOME = "/home/khalednew/.hermes/profiles/research/home/android-sdk"
ADB = os.path.join(ANDROID_HOME, "platform-tools/adb")
ARTIFACT_DIR = "/home/khalednew/.gemini/antigravity/brain/e7f87f7e-9193-49c2-826d-53d7f99aa1cc"

def run_adb(args):
    cmd = [ADB] + args
    env = os.environ.copy()
    env["ANDROID_HOME"] = ANDROID_HOME
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr

def capture(name):
    path = os.path.join(ARTIFACT_DIR, name)
    print(f"Capturing screenshot to {path}...")
    cmd = [ADB, "exec-out", "screencap", "-p"]
    env = os.environ.copy()
    env["ANDROID_HOME"] = ANDROID_HOME
    with open(path, "wb") as f:
        subprocess.run(cmd, env=env, stdout=f)
    print(f"Captured {name}")

def test_nav():
    # Tap the second tab
    print("Tapping second tab (X=324, Y=2256)...")
    run_adb(["shell", "input", "tap", "324", "2256"])
    time.sleep(3)
    capture("test_tab2_clicked.png")
    
    # Tap the third tab
    print("Tapping third tab (X=675, Y=2256)...")
    run_adb(["shell", "input", "tap", "675", "2256"])
    time.sleep(3)
    capture("test_tab3_clicked.png")

if __name__ == "__main__":
    test_nav()
