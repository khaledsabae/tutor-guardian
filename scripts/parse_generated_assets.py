#!/usr/bin/env python3
import os
import re
import json

ASSETS_FILE = "/home/khalednew/projects/tutor-guardian/docs/lesson_7_9_medical_02_assets.md"
OUTPUT_DIR = "/home/khalednew/projects/tutor-guardian/docs"

# Output files
FLASHCARDS_OUTPUT = os.path.join(OUTPUT_DIR, "lesson_7_9_medical_02_flashcards.json")
SLIDES_OUTPUT = os.path.join(OUTPUT_DIR, "lesson_7_9_medical_02_slides.json")

def parse_flashcards(content):
    flashcards = []
    
    # Locate the flashcards section - look for the table after "Answer:"
    flashcards_part = re.search(r"Answer:.*?\n(\|.*?\|.*?\n\|.*?\n(?:.*?\n)+)", content, re.DOTALL)
    if not flashcards_part:
        print("Warning: Flashcards section not found or table layout matches failed.")
        return flashcards
        
    table_text = flashcards_part.group(1)
    raw_lines = table_text.strip().split("\n")
    if len(raw_lines) < 2:
        return flashcards
        
    # Process each line as a row
    for line in raw_lines:
        line_str = line.strip()
        if not line_str or "---" in line_str or ":---" in line_str:
            continue
            
        # Parse columns separated by pipe '|'
        cols = [c.strip() for c in line_str.split("|")]
        # Cols array: ['', category, front, back, '']
        if len(cols) >= 4:
            category = re.sub(r"\*\*|\[\d+\]", "", cols[1]).strip()
            front = re.sub(r"\[\d+\]", "", cols[2]).strip()
            back_raw = cols[3]
            
            # Clean citations and split back action points
            back_clean = re.sub(r"\[\d+(?:,\s*\d+)*\]", "", back_raw)
            back_steps = []
            # Split by <br> or markdown list numbering like 1. or 2.
            parts = re.split(r"<br>|\n|(?:\d+\.\s*)", back_clean)
            for part in parts:
                part_clean = re.sub(r"^\**|\**$", "", part).strip()
                if part_clean:
                    back_steps.append(part_clean)
            
            flashcards.append({
                "category": category,
                "front": front,
                "back_steps": back_steps
            })
            
    return flashcards

def parse_slides(content):
    slides = []
    
    # Locate slides section
    slides_part = re.search(r"## 📊 ثالثاً: شرائح الجلسات العائلية.*?\n(### الشريحة الأولى.*)", content, re.DOTALL)
    if not slides_part:
        print("Warning: Slides section not found.")
        return slides
        
    slides_text = slides_part.group(1)
    
    # Split by ### Shariha (Slide)
    slide_blocks = re.split(r"###\s+الشريحة\s+", slides_text)
    
    for block in slide_blocks:
        if not block.strip():
            continue
            
        lines = block.strip().split("\n")
        title_line = lines[0].strip()
        
        # Parse fields using regex matching bullet points
        title = ""
        visual = ""
        message = ""
        discussion = ""
        activity = ""
        
        block_content = "\n".join(lines[1:])
        
        title_m = re.search(r"-\s+\*\*عنوان الشريحة\*\*:\s*(.*?)(?=\n-\s+\*\*|\n\n|\Z)", block_content, re.DOTALL)
        visual_m = re.search(r"-\s+\*\*المحتوى البصري المقترح\*\*:\s*(.*?)(?=\n-\s+\*\*|\n\n|\Z)", block_content, re.DOTALL)
        message_m = re.search(r"-\s+\*\*الرسالة الأساسية\*\*:\s*(.*?)(?=\n-\s+\*\*|\n\n|\Z)", block_content, re.DOTALL)
        discussion_m = re.search(r"-\s+\*\*سؤال للنقاش العائلي\*\*:\s*(.*?)(?=\n-\s+\*\*|\n\n|\Z)", block_content, re.DOTALL)
        activity_m = re.search(r"-\s+\*\*نشاط عملي جماعي\*\*:\s*(.*?)(?=\n-\s+\*\*|\n\n|\Z)", block_content, re.DOTALL)
        
        if title_m: title = re.sub(r"\[\d+(?:,\s*\d+)*\]", "", title_m.group(1)).strip()
        if visual_m: visual = re.sub(r"\[\d+(?:,\s*\d+)*\]", "", visual_m.group(1)).strip()
        if message_m: message = re.sub(r"\[\d+(?:,\s*\d+)*\]", "", message_m.group(1)).strip()
        if discussion_m: discussion = re.sub(r"\[\d+(?:,\s*\d+)*\]", "", discussion_m.group(1)).strip()
        if activity_m: activity = re.sub(r"\[\d+(?:,\s*\d+)*\]", "", activity_m.group(1)).strip()
        
        # Fallback to cleaned title line if title not found in bullet
        if not title:
            title = re.sub(r"^(الأولى|الثانية|الثالثة|الرابعة|الخامسة|السادسة)\s*", "", title_line).strip()
            if not title:
                title = f"الشريحة {title_line}"
        
        slides.append({
            "title": title,
            "visual_suggestion": visual,
            "key_message": message,
            "discussion_question": discussion,
            "family_activity": activity
        })
        
    return slides

def main():
    if not os.path.exists(ASSETS_FILE):
        print(f"Error: {ASSETS_FILE} does not exist. Run generation script first.")
        return
        
    with open(ASSETS_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 1. Parse Flashcards
    flashcards = parse_flashcards(content)
    with open(FLASHCARDS_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(flashcards, f, ensure_ascii=False, indent=2)
    print(f"Parsed and saved {len(flashcards)} flashcards to: {FLASHCARDS_OUTPUT}")
    
    # 2. Parse Slides
    slides = parse_slides(content)
    with open(SLIDES_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(slides, f, ensure_ascii=False, indent=2)
    print(f"Parsed and saved {len(slides)} slides to: {SLIDES_OUTPUT}")

if __name__ == "__main__":
    main()