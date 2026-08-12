#!/usr/bin/env python3
import os
import subprocess
import time

ANDROID_HOME = "/home/khalednew/.hermes/profiles/research/home/android-sdk"
ADB = os.path.join(ANDROID_HOME, "platform-tools/adb")

def run_adb(args):
    """Helper to run adb commands."""
    cmd = [ADB] + args
    env = os.environ.copy()
    env["ANDROID_HOME"] = ANDROID_HOME
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

def capture_screen(output_path="/tmp/emulator_screen.png"):
    """Takes a screenshot of the active emulator and saves it locally."""
    print(f"Capturing screen to {output_path}...")
    # Using exec-out is much faster than running screencap and copying via adb pull
    cmd = [ADB, "exec-out", "screencap", "-p"]
    env = os.environ.copy()
    env["ANDROID_HOME"] = ANDROID_HOME
    try:
        with open(output_path, "wb") as f:
            subprocess.run(cmd, env=env, stdout=f, check=True)
        print("Screenshot saved successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to capture screen: {e}")
        return False

def tap(x, y):
    """Simulates a touch tap at coordinates x, y."""
    print(f"Tapping at ({x}, {y})...")
    code, stdout, stderr = run_adb(["shell", "input", "tap", str(x), str(y)])
    return code == 0

def type_text(text):
    """Types the specified text on the active input field."""
    print(f"Typing text: {text}...")
    # Replace spaces with %s as adb input doesn't support raw spaces easily
    safe_text = text.replace(" ", "%s")
    code, stdout, stderr = run_adb(["shell", "input", "text", safe_text])
    return code == 0

def press_back():
    """Simulates back button press."""
    print("Pressing Back button...")
    code, stdout, stderr = run_adb(["shell", "input", "keyevent", "4"])
    return code == 0

def launch_app(package_name="com.alsaba.almorabbi"):
    """Launches the app."""
    print(f"Launching app: {package_name}...")
    code, stdout, stderr = run_adb(["shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"])
    return code == 0

def stop_app(package_name="com.alsaba.almorabbi"):
    """Force closes the app."""
    print(f"Stopping app: {package_name}...")
    code, stdout, stderr = run_adb(["shell", "am", "force-stop", package_name])
    return code == 0

if __name__ == "__main__":
    # Check if a device is connected
    code, stdout, stderr = run_adb(["devices"])
    print("Connected devices:")
    print(stdout)
    
    if "emulator" in stdout or "device" in stdout.split("\n")[1]:
        print("Emulator detected! Running demo actions...")
        # 1. Stop app
        stop_app()
        time.sleep(1)
        # 2. Launch app
        launch_app()
        time.sleep(3)
        # 3. Capture screen
        capture_screen()
    else:
        print("No active emulator detected. Start the emulator first to run the controller!")
