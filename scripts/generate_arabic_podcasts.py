#!/usr/bin/env python3
import os
import re
import json
import asyncio

CLI_PATH = "./notebooklm_env/bin/notebooklm"
INDEX_PATH = "docs/lesson_index.json"
MAP_PATH = "/tmp/lesson_source_map.json"

async def run_command(cmd):
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode(), stderr.decode()

async def generate_podcast(source_id):
    # No --wait parameter so it starts the task and returns immediately with the task ID
    cmd = [CLI_PATH, "generate", "audio", "--language", "ar_001", "-s", source_id]
    print(f"Triggering generation for source {source_id}...")
    code, stdout, stderr = await run_command(cmd)
    if code != 0:
        print(f"Generation command returned non-zero code {code} for source {source_id}. Error: {stderr.strip()}")
    
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

async def download_podcast(task_id, output_path):
    cmd = [CLI_PATH, "download", "audio", "--artifact", task_id, output_path, "--force"]
    print(f"Downloading artifact {task_id} to {output_path}...")
    code, stdout, stderr = await run_command(cmd)
    if code == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        print(f"Successfully downloaded to {output_path}")
        return True
    print(f"Download failed for task {task_id}: {stderr.strip()}")
    return False

async def main():
    if not os.path.exists(MAP_PATH):
        print(f"Error: {MAP_PATH} does not exist. Please run mapping script first.")
        return

    with open(MAP_PATH, "r") as f:
        lesson_map = json.load(f)

    # Filter for age 0-3 lessons
    target_lessons = [m for m in lesson_map if m["age_group"] == "0-3"]
    print(f"Found {len(target_lessons)} target lessons for 0-3.")

    with open(INDEX_PATH, "r") as f:
        index_data = json.load(f)

    lessons_dict = {l["lesson_id"]: l for l in index_data["lessons"]}

    active_tasks = []

    # 1. Trigger all generations
    for idx, target in enumerate(target_lessons, 1):
        lesson_id = target["lesson_id"]
        source_id = target["source_id"]
        topic = target["topic_path"]
        
        match = re.search(r'_(\d+)$', lesson_id)
        num = match.group(1) if match else "01"
        filename = f"docs/lesson_0-3_{topic}_{num}_podcast.mp3"
        
        # Check if already generated
        if os.path.exists(filename) and os.path.getsize(filename) > 10 * 1024 * 1024:
            print(f"[{idx}/{len(target_lessons)}] {filename} already exists and looks valid. Skipping.")
            lessons_dict[lesson_id]["assets"]["podcasts"] = [{
                "file": filename,
                "size_bytes": os.path.getsize(filename)
            }]
            continue

        print(f"\n[{idx}/{len(target_lessons)}] Triggering {lesson_id} (Source: {source_id})...")
        task_id = await generate_podcast(source_id)
        if task_id:
            print(f"Triggered successfully. Task ID: {task_id}")
            active_tasks.append({
                "lesson_id": lesson_id,
                "task_id": task_id,
                "filename": filename
            })
            # Sleep briefly to avoid hammering the NotebookLM API
            await asyncio.sleep(4)
        else:
            print(f"Failed to trigger generation for {lesson_id}")
            
    if not active_tasks:
        print("\nNo active tasks to poll. Saving index.")
        with open(INDEX_PATH, "w") as f:
            json.dump(index_data, f, indent=2)
        return

    # 2. Poll active tasks concurrently
    print(f"\nPolling {len(active_tasks)} active tasks...")
    while active_tasks:
        print(f"\n--- Active tasks remaining: {len(active_tasks)} ---")
        still_active = []
        for task in active_tasks:
            lesson_id = task["lesson_id"]
            task_id = task["task_id"]
            filename = task["filename"]
            
            status, err = await poll_task(task_id)
            print(f"Task {task_id} ({lesson_id}): {status}")
            
            if status == "completed":
                # Download
                success = await download_podcast(task_id, filename)
                if success:
                    size_bytes = os.path.getsize(filename)
                    lessons_dict[lesson_id]["assets"]["podcasts"] = [{
                        "file": filename,
                        "size_bytes": size_bytes
                    }]
                    # Save index immediately on each success
                    with open(INDEX_PATH, "w") as f:
                        json.dump(index_data, f, indent=2)
                    print(f"Updated index and saved for {lesson_id}")
                else:
                    # Keep active to try downloading again next time
                    still_active.append(task)
            elif status == "failed" or status == "error":
                print(f"Task {task_id} failed: {err}. Removing from active queue.")
            else:
                # Still in progress/pending
                still_active.append(task)
                
        active_tasks = still_active
        if active_tasks:
            print("Sleeping 20 seconds before next poll...")
            await asyncio.sleep(20)

    print("\nAll tasks finished processing.")

if __name__ == "__main__":
    asyncio.run(main())
