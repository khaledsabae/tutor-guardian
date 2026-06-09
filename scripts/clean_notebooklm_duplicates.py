#!/usr/bin/env python3
import os
import json
import re
import asyncio
import argparse
import subprocess

def extract_key(title):
    """
    Extracts the core key from a NotebookLM source title.
    If it's a lesson, extracts the lesson ID like 'lesson_16-18_medical_adult_transition_03'.
    Otherwise, returns a normalized title.
    """
    # Regex to find lesson IDs, e.g. lesson_16-18_medical_adult_transition_03 or lesson_4-6_islamic_parenting_adab_01
    match = re.search(r'(lesson_[\d\-]+_[a-zA-Z0-9_\-]+)', title)
    if match:
        return match.group(1).lower().replace('.md', '')
    
    # Otherwise, normalize the whole title
    normalized = title.lower().strip()
    # Remove file extensions
    for ext in ['.pdf', '.txt', '.md', '.docx', '.html']:
        if normalized.endswith(ext):
            normalized = normalized[:-len(ext)]
    return normalized

async def delete_source_with_fallback(client, notebook_id, source_id, title):
    """
    Tries to delete a source using the Python client first, then falls back to CLI.
    """
    try:
        # Try python client
        if hasattr(client.sources, 'delete'):
            # In notebooklm-py, sources.delete(notebook_id, source_id) is typical
            # Let's try passing both first, then fall back to single argument
            try:
                if asyncio.iscoroutinefunction(client.sources.delete):
                    await client.sources.delete(notebook_id, source_id)
                else:
                    client.sources.delete(notebook_id, source_id)
                print(f"Successfully deleted duplicate source: '{title}' (ID: {source_id})")
                return True
            except TypeError as te:
                print(f"Two-argument delete failed, trying single: {te}")
                if asyncio.iscoroutinefunction(client.sources.delete):
                    await client.sources.delete(source_id)
                else:
                    client.sources.delete(source_id)
                print(f"Successfully deleted duplicate source: '{title}' (ID: {source_id})")
                return True
    except Exception as e:
        print(f"Client delete failed for '{title}': {e}")
        
    # Fallback to CLI
    try:
        cmd = f"./notebooklm_env/bin/notebooklm source delete \"{source_id}\" -y"
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            print(f"CLI deleted duplicate source: '{title}' (ID: {source_id})")
            return True
        else:
            print(f"CLI delete failed: {stderr.decode().strip()}")
    except Exception as cli_err:
        print(f"CLI execution failed: {cli_err}")
        
    return False

async def main():
    parser = argparse.ArgumentParser(description="Clean duplicate files from Google NotebookLM.")
    parser.add_argument("--notebook", default="94f191e6-cfbc-4655-a0d7-c8f7ad0f2287", help="Google NotebookLM Notebook ID")
    parser.add_argument("--yes", "-y", action="store_true", help="Bypass interactive confirmation prompt")
    args = parser.parse_args()
    
    # Step 1: Get the list of sources in JSON format using CLI
    print(f"Fetching sources for Notebook: {args.notebook}...")
    try:
        cmd = f"./notebooklm_env/bin/notebooklm source list --notebook {args.notebook} --json"
        process = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        data = json.loads(process.stdout)
    except Exception as e:
        print(f"Error fetching sources list: {e}")
        return
        
    sources = data.get("sources", [])
    print(f"Total sources currently in notebook: {len(sources)}")
    
    if not sources:
        print("No sources found.")
        return
        
    # Group sources by their core key
    grouped_sources = {}
    for src in sources:
        title = src.get("title", "")
        sid = src.get("id")
        created_at = src.get("created_at", "")
        
        if not sid:
            continue
            
        key = extract_key(title)
        if key not in grouped_sources:
            grouped_sources[key] = []
        grouped_sources[key].append(src)
        
    # Identify duplicates
    duplicates_to_delete = []
    keys_with_duplicates = 0
    
    for key, src_list in grouped_sources.items():
        if len(src_list) > 1:
            keys_with_duplicates += 1
            print(f"\nFound duplicate group for key '{key}':")
            # Sort the sources:
            # We prefer:
            # 1. Title starting with 'age_' (which represents our new upload format)
            # 2. Earliest created_at (if same format)
            def sort_key(s):
                title = s.get("title", "")
                created = s.get("created_at", "")
                is_age_format = 1 if title.startswith("age_") else 0
                return (-is_age_format, created)
                
            sorted_list = sorted(src_list, key=sort_key)
            
            # The first one is kept
            kept_source = sorted_list[0]
            print(f"  [KEEP] Title: '{kept_source['title']}' (ID: {kept_source['id']}, Created: {kept_source['created_at']})")
            
            # The rest are marked for deletion
            for dup in sorted_list[1:]:
                print(f"  [DELETE] Title: '{dup['title']}' (ID: {dup['id']}, Created: {dup['created_at']})")
                duplicates_to_delete.append(dup)
                
    if not duplicates_to_delete:
        print("\nNo duplicates found to clean!")
        return
        
    print(f"\nFound {len(duplicates_to_delete)} duplicate files to delete (from {keys_with_duplicates} groups).")
    if not args.yes:
        confirm = input("Do you want to proceed with deletion? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Clean up cancelled by user.")
            return
        
    # Initialize NotebookLM client to execute deletions
    try:
        from notebooklm import NotebookLMClient
    except ImportError:
        print("Error: notebooklm-py is not installed in the active environment.")
        return
        
    async with NotebookLMClient.from_storage() as client:
        deleted_count = 0
        for dup in duplicates_to_delete:
            sid = dup["id"]
            title = dup["title"]
            success = await delete_source_with_fallback(client, args.notebook, sid, title)
            if success:
                deleted_count += 1
            # Sleep to respect rate limits
            await asyncio.sleep(0.5)
            
    print(f"\nCompleted! Deleted {deleted_count} duplicate sources.")

if __name__ == "__main__":
    asyncio.run(main())
