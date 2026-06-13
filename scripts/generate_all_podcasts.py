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
    cmd = [CLI_PATH, "generate", "audio", "--language", "ar_001", "-s", source_id]
    code, stdout, stderr = await run_command(cmd)
    
    match = re.search(r"(?:Task|Started):\s*([a-fA-F0-9\-]+)", stdout + stderr)
    if match:
        return match.group(1)
    
    if "RateLimitError" in stdout or "RateLimitError" in stderr or "quota" in stdout.lower() or "quota" in stderr.lower():
        return "RATELIMIT"
        
    print(f"Failed to trigger {source_id}: {stdout} {stderr}")
    return None

async def poll_task(task_id):
    cmd = [CLI_PATH, "artifact", "poll", task_id, "--json"]
    code, stdout, stderr = await run_command(cmd)
    if code == 0:
        try:
            data = json.loads(stdout)
            return data.get("status"), data.get("error")
        except:
            return "error", "Parse failed"
    return "error", stderr.strip()

async def download_podcast(task_id, output_path):
    cmd = [CLI_PATH, "download", "audio", "--artifact", task_id, output_path, "--force"]
    code, stdout, stderr = await run_command(cmd)
    if code == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1024 * 1024:
        return True
    return False

async def main():
    if not os.path.exists(MAP_PATH):
        print("Missing map path")
        return

    with open(MAP_PATH, "r") as f:
        lesson_map = json.load(f)

    with open(INDEX_PATH, "r") as f:
        index_data = json.load(f)

    lessons_dict = {l["lesson_id"]: l for l in index_data["lessons"]}

    missing_lessons = []
    
    for target in lesson_map:
        lesson_id = target["lesson_id"]
        source_id = target["source_id"]
        topic = target["topic_path"]
        age = target["age_group"]
        
        match = re.search(r'_(\d+)$', lesson_id)
        num = match.group(1) if match else "01"
        filename = f"docs/lesson_{age}_{topic}_{num}_podcast.mp3"
        
        if os.path.exists(filename) and os.path.getsize(filename) > 1024 * 1024:
            # Check if index already points to it
            existing_podcasts = lessons_dict[lesson_id].get("assets", {}).get("podcasts", [])
            has_valid = any(p.get("file") == filename for p in existing_podcasts)
            if not has_valid:
                lessons_dict[lesson_id].setdefault("assets", {})
                lessons_dict[lesson_id]["assets"]["podcasts"] = [{
                    "file": filename,
                    "size_bytes": os.path.getsize(filename),
                    "language": "ar"
                }]
            continue
            
        missing_lessons.append({
            "lesson_id": lesson_id,
            "source_id": source_id,
            "filename": filename
        })

    with open(INDEX_PATH, "w") as f:
        json.dump(index_data, f, indent=2)

    print(f"Found {len(missing_lessons)} missing podcasts.")
    
    active_tasks = []
    
    for idx, target in enumerate(missing_lessons, 1):
        lesson_id = target["lesson_id"]
        source_id = target["source_id"]
        filename = target["filename"]
        
        success_trigger = False
        while not success_trigger:
            print(f"[{idx}/{len(missing_lessons)}] Triggering {lesson_id}...")
            task_id = await generate_podcast(source_id)
            
            if task_id == "RATELIMIT":
                print("Rate limit reached. Sleeping 60 seconds before retrying...")
                await asyncio.sleep(60)
            elif task_id:
                print(f" -> Task ID: {task_id}")
                active_tasks.append({
                    "lesson_id": lesson_id,
                    "task_id": task_id,
                    "filename": filename
                })
                success_trigger = True
                await asyncio.sleep(3)
            else:
                print("Failed completely.")
                success_trigger = True
                
    while active_tasks:
        print(f"\nPolling {len(active_tasks)} tasks...")
        still_active = []
        for task in active_tasks:
            status, err = await poll_task(task["task_id"])
            if status == "completed":
                print(f"Downloading {task['lesson_id']}...")
                success = await download_podcast(task["task_id"], task["filename"])
                if success:
                    print(f" -> Downloaded!")
                    
                    with open(INDEX_PATH, "r") as f:
                        current_index = json.load(f)
                    current_dict = {l["lesson_id"]: l for l in current_index["lessons"]}
                    
                    current_dict[task["lesson_id"]].setdefault("assets", {})
                    current_dict[task["lesson_id"]]["assets"]["podcasts"] = [{
                        "file": task["filename"],
                        "size_bytes": os.path.getsize(task["filename"]),
                        "language": "ar"
                    }]
                    
                    with open(INDEX_PATH, "w") as f:
                        json.dump(current_index, f, indent=2)
                else:
                    print(f" -> Download failed.")
            elif status in ("failed", "error"):
                print(f"Task {task['lesson_id']} failed: {err}")
            else:
                still_active.append(task)
                
        active_tasks = still_active
        if active_tasks:
            await asyncio.sleep(20)
            
    print("\nAll tasks finished.")

if __name__ == "__main__":
    asyncio.run(main())
