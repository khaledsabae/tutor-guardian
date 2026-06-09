import os
import json
import glob
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="Convert curriculum lessons into structured Markdown format grouped by age category.")
    parser.add_argument("--output", default="/home/khalednew/projects/tutor-guardian/output/notebooklm", help="Target output directory")
    args = parser.parse_args()

    repo_dir = "/home/khalednew/projects/tutor-guardian"
    kb_dir = os.path.join(repo_dir, "knowledge_base")
    paths_dir = os.path.join(kb_dir, "curriculum", "paths")
    lessons_dir = os.path.join(kb_dir, "curriculum", "lessons")
    units_dir = os.path.join(kb_dir, "units")
    output_base_dir = args.output
    
    if not os.path.exists(paths_dir):
        print(f"Error: Paths directory {paths_dir} does not exist.")
        sys.exit(1)
    if not os.path.exists(lessons_dir):
        print(f"Error: Lessons directory {lessons_dir} does not exist.")
        sys.exit(1)
    if not os.path.exists(units_dir):
        print(f"Error: Units directory {units_dir} does not exist.")
        sys.exit(1)
        
    print("Loading paths...")
    path_titles = {}
    for path_file in glob.glob(os.path.join(paths_dir, "*.json")):
        try:
            with open(path_file, 'r', encoding='utf-8') as f:
                path_data = json.load(f)
                p_id = path_data.get("id")
                p_title = path_data.get("title")
                if p_id and p_title:
                    path_titles[p_id] = p_title
        except Exception as e:
            print(f"Error loading path {path_file}: {e}")
            
    print(f"Loaded {len(path_titles)} paths.")
    
    lessons_by_age = {}
    lesson_files = glob.glob(os.path.join(lessons_dir, "*.json"))
    print(f"Processing {len(lesson_files)} lesson files...")
    
    lessons_count_by_age = {}
    
    for lesson_file in lesson_files:
        try:
            with open(lesson_file, 'r', encoding='utf-8') as f:
                lesson = json.load(f)
            
            lesson_id = lesson.get("id")
            title = lesson.get("title")
            age_group = lesson.get("age_group")
            domain = lesson.get("domain")
            path_id = lesson.get("path_id")
            duration_minutes = lesson.get("estimated_minutes", 5)
            try_this = lesson.get("try_this", "")
            reflection_prompts = lesson.get("reflection_prompts", [])
            unit_ids = lesson.get("unit_ids", [])
            
            if not lesson_id or not age_group:
                continue
                
            path_title = path_titles.get(path_id, "غير محدد")
            
            age_folder_name = f"age_{age_group.replace('-', '_')}"
            age_folder_path = os.path.join(output_base_dir, age_folder_name)
            os.makedirs(age_folder_path, exist_ok=True)
            
            objectives = []
            sections = []
            
            for u_id in unit_ids:
                unit_file = os.path.join(units_dir, f"{u_id}.json")
                if os.path.exists(unit_file):
                    try:
                        with open(unit_file, 'r', encoding='utf-8') as uf:
                            unit = json.load(uf)
                        
                        b_type = unit.get("behavior_type", "").replace("_", " ")
                        int_type = unit.get("intervention_type", "")
                        sev = unit.get("severity", "")
                        
                        obj_str = f"فهم والتعامل مع {b_type}"
                        if int_type or sev:
                            details = []
                            if int_type: details.append(int_type)
                            if sev: details.append(f"مستوى الشدة: {sev}")
                            obj_str += f" ({', '.join(details)})"
                        if obj_str not in objectives:
                            objectives.append(obj_str)
                            
                        u_lang = unit.get("language", "")
                        u_title = unit.get("title")
                        
                        sec_title = ""
                        if u_lang == "ar" and u_title and u_title != "None":
                            sec_title = u_title
                        else:
                            sec_title = unit.get("behavior_type", "").replace("_", " ")
                            if not sec_title or sec_title == "None":
                                sec_title = unit.get("source_file", "وحدة معرفية")
                                
                        sec_text = unit.get("text_simplified")
                        if not sec_text or sec_text == "None":
                            sec_text = unit.get("text_original", "لا يوجد محتوى متاح.")
                            
                        sections.append(f"### {sec_title}\n\n{sec_text}\n")
                        
                    except Exception as ue:
                        print(f"Error loading unit {u_id} for lesson {lesson_id}: {ue}")
                else:
                    found = False
                    for root, dirs, files in os.walk(kb_dir):
                        if f"{u_id}.json" in files:
                            unit_file = os.path.join(root, f"{u_id}.json")
                            try:
                                with open(unit_file, 'r', encoding='utf-8') as uf:
                                    unit = json.load(uf)
                                b_type = unit.get("behavior_type", "").replace("_", " ")
                                int_type = unit.get("intervention_type", "")
                                sev = unit.get("severity", "")
                                obj_str = f"فهم والتعامل مع {b_type}"
                                if int_type or sev:
                                    details = []
                                    if int_type: details.append(int_type)
                                    if sev: details.append(f"مستوى الشدة: {sev}")
                                    obj_str += f" ({', '.join(details)})"
                                if obj_str not in objectives:
                                    objectives.append(obj_str)
                                u_lang = unit.get("language", "")
                                u_title = unit.get("title")
                                sec_title = ""
                                if u_lang == "ar" and u_title and u_title != "None":
                                    sec_title = u_title
                                else:
                                    sec_title = unit.get("behavior_type", "").replace("_", " ")
                                    if not sec_title or sec_title == "None":
                                        sec_title = unit.get("source_file", "وحدة معرفية")
                                sec_text = unit.get("text_simplified")
                                if not sec_text or sec_text == "None":
                                    sec_text = unit.get("text_original", "لا يوجد محتوى متاح.")
                                sections.append(f"### {sec_title}\n\n{sec_text}\n")
                                found = True
                                break
                            except Exception as ue:
                                print(f"Error loading unit {u_id} from walk: {ue}")
                    if not found:
                        print(f"Warning: Unit {u_id} not found anywhere.")
            
            obj_list_str = "\n".join([f"- {obj}" for obj in objectives]) if objectives else "- التعرف على المفاهيم الأساسية للدرس."
            sections_str = "\n".join(sections) if sections else "لا يوجد محتوى متاح حالياً."
            
            try_this_str = ""
            if isinstance(try_this, list):
                try_this_str = "\n".join([f"- {item}" for item in try_this])
            else:
                try_this_str = f"- {try_this}" if try_this else "- لا توجد أنشطة عملية مقترحة."
                
            reflection_str = ""
            if reflection_prompts:
                reflection_str = "\n".join([f"- {prompt}" for prompt in reflection_prompts])
            else:
                reflection_str = "- كيف يمكنك تطبيق ما تعلمته اليوم في حياة طفلك اليومية؟"
                
            md_content = f"""---
# {title}
**الفئة العمرية:** {age_group}
**المسار:** {path_title}
**المدة المقدرة:** {duration_minutes} دقيقة
---
## الأهداف
{obj_list_str}

## المحتوى
{sections_str}

## جرّب هذا
{try_this_str}

## للتأمل
{reflection_str}
---"""
            
            lesson_md_file = os.path.join(age_folder_path, f"{lesson_id}.md")
            with open(lesson_md_file, 'w', encoding='utf-8') as out_f:
                out_f.write(md_content)
                
            if age_folder_name not in lessons_by_age:
                lessons_by_age[age_folder_name] = []
            lessons_by_age[age_folder_name].append({
                "id": lesson_id,
                "title": title,
                "domain": domain,
                "path_title": path_title,
                "estimated_minutes": duration_minutes
            })
            
            lessons_count_by_age[age_folder_name] = lessons_count_by_age.get(age_folder_name, 0) + 1
            
        except Exception as e:
            print(f"Error processing lesson {lesson_file}: {e}")
            
    print("Generating index.md files...")
    for age_folder_name, lessons_list in lessons_by_age.items():
        lessons_list.sort(key=lambda l: (l["domain"], l["path_title"], l["id"]))
        age_label = age_folder_name.replace("age_", "").replace("_", "-")
        
        index_content = []
        index_content.append(f"# فهرس الدروس للفئة العمرية: {age_label} سنوات\n")
        index_content.append("يحتوي هذا الملف على ملخص للدروس المتاحة لهذه الفئة العمرية لمشروع المربي الذكي. تم تصميم هذه الدروس لتوفير إرشادات عملية ومحتوى تربوي مبني على أسس علمية وشرعية.\n")
        index_content.append("## قائمة الدروس\n")
        index_content.append("| الدرس | المجال | المسار | المدة المقدرة | الملف |")
        index_content.append("| --- | --- | --- | --- | --- |")
        
        for l in lessons_list:
            index_content.append(f"| **{l['title']}** | {l['domain']} | {l['path_title']} | {l['estimated_minutes']} دقيقة | [{l['id']}.md](./{l['id']}.md) |")
            
        index_file_path = os.path.join(output_base_dir, age_folder_name, "index.md")
        with open(index_file_path, 'w', encoding='utf-8') as idx_f:
            idx_f.write("\n".join(index_content))
            
    print("\nإحصائية الدروس المصدرة:")
    all_age_folders = sorted(lessons_count_by_age.keys())
    for f in all_age_folders:
        age_disp = f.replace("age_", "").replace("_", "-")
        print(f"- الفئة العمرية {age_disp}: {lessons_count_by_age[f]} درس")

if __name__ == "__main__":
    main()
