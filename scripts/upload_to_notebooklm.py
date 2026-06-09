#!/usr/bin/env python3
import os
import glob
import asyncio
import argparse
import inspect

async def upload_file_with_fallback(client, notebook_id, file_path, title):
    """
    Tries to upload a local file using whatever method name notebooklm-py uses in this version.
    """
    sources_api = client.sources
    
    # List of possible method names and their call signatures
    # notebooklm-py has keyword-only arguments in recent versions.
    methods_to_try = [
        ('add_file', {'notebook_id': notebook_id, 'file_path': file_path, 'title': title}),
        ('add_file', {'notebook_id': notebook_id, 'path': file_path, 'title': title}),
        ('upload_file', {'notebook_id': notebook_id, 'file_path': file_path, 'title': title}),
        ('upload_file', {'notebook_id': notebook_id, 'path': file_path, 'title': title}),
        ('create_source_file', {'notebook_id': notebook_id, 'file_path': file_path, 'title': title}),
    ]
    
    for method_name, kwargs in methods_to_try:
        if hasattr(sources_api, method_name):
            method = getattr(sources_api, method_name)
            try:
                # Inspect parameters to see if we should pass them as args or kwargs
                sig = inspect.signature(method)
                print(f"Trying method '{method_name}' with arguments: {list(kwargs.keys())}")
                
                # Check if it expects positional or keyword arguments
                # If we have keyword-only arguments in the signature, we must pass kwargs.
                # In python, we can almost always pass kwargs for standard parameters unless they are positional-only.
                if asyncio.iscoroutinefunction(method):
                    await method(**kwargs)
                else:
                    method(**kwargs)
                print(f"Successfully uploaded: {title}")
                return True
            except Exception as e:
                print(f"Method '{method_name}' failed: {e}")
                # Continue trying other fallbacks
    
    # If all named client methods fail, try CLI fallback as a last resort
    print(f"Client API methods failed. Trying to upload via 'notebooklm' CLI for: {title}")
    try:
        # Construct the CLI command
        # notebooklm source add <filepath> --notebook <notebook_id> --title <title>
        # Let's check if the CLI supports this
        cmd = f"notebooklm source add \"{file_path}\""
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            print(f"CLI upload successful: {title}")
            return True
        else:
            print(f"CLI upload failed with code {process.returncode}: {stderr.decode().strip()}")
    except Exception as cli_err:
        print(f"CLI execution failed: {cli_err}")
        
    return False

async def main():
    parser = argparse.ArgumentParser(description="Upload generated curriculum markdown lessons to Google NotebookLM.")
    parser.add_argument("--notebook", default="94f191e6-cfbc-4655-a0d7-c8f7ad0f2287", help="Google NotebookLM Notebook ID")
    parser.add_argument("--dir", default="/home/khalednew/projects/tutor-guardian/knowledge_base/notebooklm", help="Directory containing markdown files")
    parser.add_argument("--skip-index", action="store_true", help="Skip uploading index.md files")
    args = parser.parse_args()
    
    if not os.path.exists(args.dir):
        print(f"Error: Directory '{args.dir}' does not exist.")
        return
        
    # Find all markdown files recursively
    search_pattern = os.path.join(args.dir, "**", "*.md")
    md_files = glob.glob(search_pattern, recursive=True)
    
    if args.skip_index:
        md_files = [f for f in md_files if os.path.basename(f) != "index.md"]
        
    if not md_files:
        print("No markdown files found to upload.")
        return
        
    print(f"Found {len(md_files)} files to upload to Notebook ID: {args.notebook}")
    
    try:
        from notebooklm import NotebookLMClient
    except ImportError:
        print("Error: 'notebooklm-py' library is not installed in the active environment.")
        print("Please run: pip install notebooklm-py")
        return

    print("Connecting to NotebookLM client...")
    try:
        async with NotebookLMClient.from_storage() as client:
            for i, file_path in enumerate(md_files, 1):
                filename = os.path.basename(file_path)
                parent_folder = os.path.basename(os.path.dirname(file_path))
                title = f"{parent_folder} - {filename.replace('.md', '')}"
                
                print(f"[{i}/{len(md_files)}] Uploading {filename} ({title})...")
                success = await upload_file_with_fallback(client, args.notebook, file_path, title)
                if not success:
                    print(f"Failed to upload: {file_path}")
                # Sleep briefly to be respectful to the API rate limits
                await asyncio.sleep(1)
                
    except Exception as e:
        print(f"An error occurred during NotebookLM interaction: {e}")
        print("\nMake sure you have logged in by running:")
        print("  notebooklm login")
        print("or")
        print("  notebooklm login --browser-cookies chrome")

if __name__ == "__main__":
    asyncio.run(main())
