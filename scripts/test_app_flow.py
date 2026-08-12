#!/usr/bin/env python3
import os
import subprocess
import time

ANDROID_HOME = "/home/khalednew/.hermes/profiles/research/home/android-sdk"
ADB = os.path.join(ANDROID_HOME, "platform-tools/adb")
ARTIFACT_DIR = "/home/khalednew/.gemini/antigravity/brain/e7f87f7e-9193-49c2-826d-53d7f99aa1cc"
SCREENSHOT_PATH = os.path.join(ARTIFACT_DIR, "test_app_started.png")

def run_adb(args):
    cmd = [ADB] + args
    env = os.environ.copy()
    env["ANDROID_HOME"] = ANDROID_HOME
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr

def test_flow():
    print("Stopping app...")
    run_adb(["shell", "am", "force-stop", "com.alsaba.almorabbi"])
    time.sleep(1)
    
    print("Launching com.alsaba.almorabbi/.MainActivity...")
    run_adb(["shell", "am", "start", "-n", "com.alsaba.almorabbi/.MainActivity"])
    
    print("Waiting 5 seconds for the app to render...")
    time.sleep(5)
    
    print(f"Capturing screenshot to {SCREENSHOT_PATH}...")
    cmd = [ADB, "exec-out", "screencap", "-p"]
    env = os.environ.copy()
    env["ANDROID_HOME"] = ANDROID_HOME
    
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    with open(SCREENSHOT_PATH, "wb") as f:
        subprocess.run(cmd, env=env, stdout=f)
        
    if os.path.exists(SCREENSHOT_PATH) and os.path.getsize(SCREENSHOT_PATH) > 1024:
        print(f"Successfully saved screenshot! Size: {os.path.getsize(SCREENSHOT_PATH)} bytes")
        return True
    else:
        print("Failed to save screenshot or screenshot is empty.")
        return False

if __name__ == "__main__":
    test_flow()
