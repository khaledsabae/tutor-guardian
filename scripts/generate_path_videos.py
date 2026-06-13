#!/usr/bin/env python3
import os
import re
import json
import asyncio

CLI_PATH = "./notebooklm_env/bin/notebooklm"
VIDEOS_DIR = "docs/path_videos"
MAPPING_PATH = "scratch/path_source_mapping.json"

async def run_command(cmd):
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode(), stderr.decode()

async def generate_video(source_id, prompt):
    # We use ar_eg for Egyptian Arabic dialect
    cmd = [CLI_PATH, "generate", "video", "--language", "ar_eg", "-s", source_id, prompt]
    print(f"Triggering video generation for source {source_id}...")
    code, stdout, stderr = await run_command(cmd)
    if code != 0:
        print(f"Video generation command returned non-zero code {code} for source {source_id}. Error: {stderr.strip()}")
    
    match = re.search(r"(?:Task|Started):\s*([a-fA-F0-9\-]+)", stdout + stderr)
    if match:
        return match.group(1)
    
    print(f"Could not find Task ID for source {source_id}. Output was:\n{stdout}\n{stderr}")
    return None

async def poll_task(task_id):
    cmd = [CLI_PATH, "artifact", "poll", task_id, "--json"]
    code, stdout, stderr = await run_command(cmd)
    if code == 0:
        try:
            data = json.loads(stdout)
            return data.get("status"), data.get("error")
        except Exception as e:
            print(f"Failed to parse poll JSON for task {task_id}: {e}")
            return "error", str(e)
    else:
        return "error", stderr.strip()

async def download_video(task_id, output_path):
    cmd = [CLI_PATH, "download", "video", "--artifact", task_id, output_path, "--force"]
    print(f"Downloading video artifact {task_id} to {output_path}...")
    code, stdout, stderr = await run_command(cmd)
    if code == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        print(f"Successfully downloaded to {output_path}")
        return True
    print(f"Download failed for task {task_id}: {stderr.strip()}")
    return False

async def main():
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    
    if not os.path.exists(MAPPING_PATH):
        print(f"Error: {MAPPING_PATH} does not exist. Please run map_paths_to_sources.py first.")
        return

    with open(MAPPING_PATH, "r", encoding="utf-8") as f:
        mappings = json.load(f)

    active_tasks = []

    # 1. Trigger generations
    for idx, target in enumerate(mappings, 1):
        path_id = target["path_id"]
        title = target["title"]
        source_id = target["source_id"]
        
        if not source_id:
            print(f"[{idx}/{len(mappings)}] Warning: No source_id mapped for {path_id}. Skipping.")
            continue
            
        filename = os.path.join(VIDEOS_DIR, f"{path_id}_ar_eg.mp4")
        
        # Check if already generated
        if os.path.exists(filename) and os.path.getsize(filename) > 5 * 1024 * 1024:
            print(f"[{idx}/{len(mappings)}] {filename} already exists and looks valid. Skipping.")
            continue

        prompt = (
            f"أنشئ فيديو تعريفي قصير وممتع (~5 دقائق) باللهجة المصرية كعرض تمهيدي لـ '{title}'. "
            f"اشرح للأمهات والآباء بأسلوب دافئ وعملي أهم الأهداف التربوية لهذا المسار، والخطوات العملية الرئيسية "
            f"التي سيتعلمونها من المنهج، ورسالة تربوية أو لفتة إيمانية تدعم هذا المنهج. "
            f"اجعل النبرة ودودة ومقنعة جداً كأنك صديق عائلي ينصحهم بلطف."
        )

        print(f"\n[{idx}/{len(mappings)}] Triggering Video for Path: {path_id} (Source: {source_id})...")
        task_id = await generate_video(source_id, prompt)
        if task_id:
            print(f"Triggered successfully. Task ID: {task_id}")
            active_tasks.append({
                "filename": filename,
                "task_id": task_id,
                "description": f"{path_id} video"
            })
            # Sleep briefly to avoid hammering the NotebookLM API
            await asyncio.sleep(5)
        else:
            print(f"Failed to trigger video generation for {path_id}")
            
    if not active_tasks:
        print("\nNo active tasks to poll.")
        return

    # 2. Poll active tasks concurrently
    print(f"\nPolling {len(active_tasks)} active video tasks...")
    while active_tasks:
        print(f"\n--- Active video tasks remaining: {len(active_tasks)} ---")
        still_active = []
        for task in active_tasks:
            filename = task["filename"]
            task_id = task["task_id"]
            desc = task["description"]
            
            status, err = await poll_task(task_id)
            print(f"Task {task_id} ({desc}): {status}")
            
            if status == "completed":
                # Download
                success = await download_video(task_id, filename)
                if not success:
                    # Keep active to try downloading again next time
                    still_active.append(task)
            elif status == "failed" or status == "error":
                print(f"Task {task_id} failed: {err}. Removing from active queue.")
            else:
                # Still in progress/pending
                still_active.append(task)
                
        active_tasks = still_active
        if active_tasks:
            print("Sleeping 45 seconds before next poll...")
            await asyncio.sleep(45)

    print("\nAll path video tasks finished processing.")

if __name__ == "__main__":
    asyncio.run(main())
