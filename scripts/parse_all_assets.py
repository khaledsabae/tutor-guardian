#!/usr/bin/env python3
"""
Parse markdown asset files -> JSON flashcards + slides
Updates lesson_index.json and creates JSON files in docs/lesson_assets/
"""
import os
import re
import json
import uuid
from pathlib import Path

ASSETS_DIR = "/home/khalednew/projects/tutor-guardian/docs/lesson_assets"
FLASHCARDS_DIR = os.path.join(ASSETS_DIR, "flashcards")
SLIDES_DIR = os.path.join(ASSETS_DIR, "slides")
INDEX_FILE = "/home/khalednew/projects/tutor-guardian/docs/lesson_index.json"

os.makedirs(FLASHCARDS_DIR, exist_ok=True)
os.makedirs(SLIDES_DIR, exist_ok=True)
def parse_flashcards(content):
    """Parse flashcards from markdown table format"""
    flashcards = []
    
    header_patterns = [
        r'## 🃏 ثانياً: الفلاش كاردز التفاعلية',
        r'الفلاش كاردز التفاعلية',
        r'Answer:.*?الفلاش كاردز',
    ]
    
    table_start = -1
    for pattern in header_patterns:
        match = re.search(pattern, content)
        if match:
            table_start = match.end()
            break
    
    if table_start == -1:
        match = re.search(r'\|.*?الفئة والمجال.*?\|.*?الوجه الأول.*?\|', content)
        if match:
            table_start = match.start()
    
    if table_start == -1:
        print("Warning: Flashcards table header not found")
        return flashcards
    
    remaining = content[table_start:]
    section_end = re.search(r'\n## |\n---+\n', remaining)
    table_text = remaining[:section_end.start()] if section_end else remaining
    
    lines = table_text.strip().split('\n')
    
    data_rows = []
    current_row = ""
    header_seen = False
    
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
            
        pipe_count = line_str.count('|')
        
        # Skip separator rows
        if pipe_count >= 4 and ('---' in line_str or ':---' in line_str):
            continue
            
        # Detect header row
        if pipe_count >= 4 and ('الفئة والمجال' in line_str or 'الوجه الأول' in line_str):
            header_seen = True
            continue
            
        if not header_seen:
            continue
        
        # Accumulate lines into current_row
        if current_row:
            current_row += ' ' + line_str
        else:
            current_row = line_str
        
        # Check if accumulated row has 4 pipes (complete row with 3 columns)
        total_pipes = current_row.count('|')
        if total_pipes >= 4:
            data_rows.append(current_row)
            current_row = ""
    
    # Don't forget any remaining (incomplete) row
    if current_row.strip():
        data_rows.append(current_row)
    
    # Now parse each complete row
    for row in data_rows:
        cols = [c.strip() for c in row.split('|')]
        if len(cols) >= 4:
            category = re.sub(r'\*\*|\[\d+\]', '', cols[1]).strip()
            front = re.sub(r'\[\d+\]', '', cols[2]).strip()
            back_raw = cols[3]
            
            back_clean = re.sub(r'\[\d+(?:,\s*\d+)*\]', '', back_raw)
            back_steps = []
            parts = re.split(r'<br>|\n|(?:\d+\.\s*)', back_clean)
            for part in parts:
                part_clean = re.sub(r'^\*\*|\*\*$', '', part).strip()
                if part_clean:
                    back_steps.append(part_clean)
            
            back = ' | '.join(back_steps) if back_steps else back_clean
            
            flashcards.append({
                "front": front,
                "back": back
            })
    
    return flashcards

def parse_slides(content):
    """Parse slides from markdown"""
    slides = []
    
    # Find slides section
    slides_match = re.search(r'## 📊 ثالثاً: شرائح الجلسات العائلية.*?\n(### .*)', content, re.DOTALL)
    if not slides_match:
        return slides
    
    slides_text = slides_match.group(1)
    slide_blocks = re.split(r'###\s+', slides_text)
    
    for block in slide_blocks:
        if not block.strip():
            continue
            
        lines = block.strip().split('\n')
        title_line = lines[0].strip()
        
        block_content = '\n'.join(lines[1:])
        
        title_m = re.search(r'-\s+\*\*عنوان الشريحة\*\*:\s*(.*?)(?=\n-\s+\*\*|\n\n|\Z)', block_content, re.DOTALL)
        visual_m = re.search(r'-\s+\*\*المحتوى البصري المقترح\*\*:\s*(.*?)(?=\n-\s+\*\*|\n\n|\Z)', block_content, re.DOTALL)
        message_m = re.search(r'-\s+\*\*الرسالة الأساسية\*\*:\s*(.*?)(?=\n-\s+\*\*|\n\n|\Z)', block_content, re.DOTALL)
        discussion_m = re.search(r'-\s+\*\*سؤال للنقاش العائلي\*\*:\s*(.*?)(?=\n-\s+\*\*|\n\n|\Z)', block_content, re.DOTALL)
        activity_m = re.search(r'-\s+\*\*نشاط عملي جماعي\*\*:\s*(.*?)(?=\n-\s+\*\*|\n\n|\Z)', block_content, re.DOTALL)
        
        def clean(text):
            if not text:
                return ""
            return re.sub(r'\[\d+(?:,\s*\d+)*\]', '', text).strip()
        
        title = clean(title_m.group(1)) if title_m else title_line
        visual = clean(visual_m.group(1)) if visual_m else ""
        message = clean(message_m.group(1)) if message_m else ""
        discussion = clean(discussion_m.group(1)) if discussion_m else ""
        activity = clean(activity_m.group(1)) if activity_m else ""
        
        slides.append({
            "title": title,
            "visual_suggestion": visual,
            "key_message": message,
            "discussion_question": discussion,
            "family_activity": activity
        })
    
    return slides

def get_asset_type_from_name(name):
    """Determine asset type category from lesson name"""
    name_lower = name.lower()
    if 'islamic' in name_lower or 'quran' in name_lower or 'prayer' in name_lower or 'adab' in name_lower or 'worship' in name_lower or 'bond' in name_lower or 'identity' in name_lower:
        return 'Islamic_Flashcards'
    elif 'cyber' in name_lower or 'digital' in name_lower or 'citizenship' in name_lower or 'bullying' in name_lower or 'safety' in name_lower:
        return 'Cybersecurity_Flashcards'
    elif 'parenting' in name_lower or 'positive' in name_lower or 'development' in name_lower or 'brain' in name_lower or 'mental' in name_lower or 'emotional' in name_lower or 'wellbeing' in name_lower or 'health' in name_lower or 'puberty' in name_lower or 'transition' in name_lower:
        return 'Parenting_Flashcards'
    else:
        return 'General_Flashcards'

def process_markdown_file(md_path, lesson_name):
    """Process a single markdown asset file"""
    print(f"\nProcessing: {lesson_name}")
    
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse flashcards
    flashcards = parse_flashcards(content)
    if flashcards:
        asset_id = str(uuid.uuid4())
        asset_type = get_asset_type_from_name(lesson_name)
        filename = f"{asset_id}_{asset_type}.json"
        filepath = os.path.join(FLASHCARDS_DIR, filename)
        
        data = {
            "title": asset_type.replace('_', ' '),
            "cards": flashcards
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  ✅ Flashcards: {len(flashcards)} cards -> {filename}")
    else:
        print(f"  ⚠️ No flashcards found")
    
    # Parse slides
    slides = parse_slides(content)
    if slides:
        asset_id = str(uuid.uuid4())
        filename = f"{asset_id}_Slides.json"
        filepath = os.path.join(SLIDES_DIR, filename)
        
        data = {
            "title": "Family Slides",
            "slides": slides
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  ✅ Slides: {len(slides)} slides -> {filename}")
    
    return {
        "flashcards": flashcards,
        "slides": slides
    }

def main():
    # Find all markdown asset files
    docs_dir = "/home/khalednew/projects/tutor-guardian/docs"
    md_files = []
    
    # New ones we generated today
    for fname in os.listdir(docs_dir):
        if fname.endswith('_assets.md') and not fname.startswith('lesson_') and not fname.startswith('grounded') and not fname.startswith('demo'):
            md_files.append((os.path.join(docs_dir, fname), fname.replace('_assets.md', '')))
    
    # Also existing lesson_*_assets.md
    for fname in os.listdir(docs_dir):
        if fname.startswith('lesson_') and fname.endswith('_assets.md'):
            md_files.append((os.path.join(docs_dir, fname), fname.replace('_assets.md', '')))
    
    print(f"Found {len(md_files)} markdown asset files to process")
    
    results = {}
    for md_path, lesson_name in md_files:
        try:
            results[lesson_name] = process_markdown_file(md_path, lesson_name)
        except Exception as e:
            print(f"  ❌ Error processing {lesson_name}: {e}")
    
    print(f"\n✅ Processed {len(results)} files")
    return results

if __name__ == "__main__":
    main()