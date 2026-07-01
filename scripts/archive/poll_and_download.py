#!/usr/bin/env python3
"""Poll NotebookLM tasks and download completed podcasts automatically."""
import json, subprocess, re, os, time

CLI = "./notebooklm_env/bin/notebooklm"
NOTEBOOK = "94f191e6-cfbc-4655-a0d7-c8f7ad0f2287"
ENV = {**os.environ, "HOME": "/home/khalednew"}
DOCS = "docs"
POLL_INTERVAL = 120  # 2 minutes

with open("/tmp/gen_results.json") as f:
    tasks = json.load(f)

ok_tasks = [t for t in tasks if t["status"] == "ok"]
downloaded = set()

print(f"Polling {len(ok_tasks)} tasks every {POLL_INTERVAL}s...")

for round_num in range(60):  # Max 2 hours
    any_completed = False
    for t in ok_tasks:
        tid = t["task_id"]
        lid = t["lesson_id"]
        
        if tid in downloaded:
            continue
        
        cmd = [CLI, "artifact", "poll", tid, "-n", NOTEBOOK]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=ENV)
        out = res.stdout + res.stderr
        
        if "completed" in out.lower():
            safe = re.sub(r'[^\w\s-]', '', lid).strip()
            fname = f"{safe}_podcast.mp3"
            fpath = os.path.join(DOCS, fname)
            
            cmd_dl = [CLI, "download", "audio", "-a", tid, fpath, "--force"]
            res2 = subprocess.run(cmd_dl, capture_output=True, text=True, timeout=120, env=ENV)
            
            if res2.returncode == 0 and os.path.exists(fpath) and os.path.getsize(fpath) > 100000:
                size_mb = os.path.getsize(fpath) // 1024 // 1024
                print(f"[{time.strftime('%H:%M')}] DOWNLOADED: {lid[:50]} ({size_mb} MB)")
                downloaded.add(tid)
                any_completed = True
            else:
                print(f"[{time.strftime('%H:%M')}] DOWNLOAD FAIL: {lid[:50]} | {res2.stderr.strip()[:60]}")
                downloaded.add(tid)  # Don't retry failed downloads
    
    remaining = len(ok_tasks) - len(downloaded)
    if remaining == 0:
        print(f"\n=== ALL {len(ok_tasks)} TASKS COMPLETED ===")
        break
    
    print(f"[{time.strftime('%H:%M')}] Still pending: {remaining} | Next check in {POLL_INTERVAL}s...")
    time.sleep(POLL_INTERVAL)
else:
    print(f"\n=== TIMEOUT: {len(downloaded)}/{len(ok_tasks)} completed ===")
