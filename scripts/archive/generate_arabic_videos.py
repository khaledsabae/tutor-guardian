#!/usr/bin/env python3
import os
import re
import json
import asyncio

CLI_PATH = "./notebooklm_env/bin/notebooklm"
VIDEOS_DIR = "docs/lesson_videos"

VIDEOS_TO_GENERATE = [
    {
        "filename": "186dd5fa_Teen_Mental_Health_ar.mp4",
        "source_id": "cb9959f3-12d6-46e3-a592-8c6d61c30522",
        "prompt": "أنشئ فيديو تعليمياً قصيراً (~5 دقائق) باللغة العربية الفصحى الميسرة موجهاً لأولياء أمور المراهقين (13-15 سنة) عن الاكتئاب والقلق عند المراهقين. النقاط الأساسية: الاكتئاب ليس مزاجاً عابراً ولا ضعف إيمان بل حالة طبية لها علاج؛ علاماته: حزن أو فراغ لأكثر من أسبوعين، فقدان الاستمتاع، تغير النوم والشهية، تعب وضعف تركيز وأفكار سلبية؛ علامات القلق: توتر دائم وتوقع الكوارث وتجنب المواقف؛ العلاج: العلاج المعرفي السلوكي والدواء عند الحاجة والدعم الأسري؛ رسالة للوالدين: استمعوا بلا أحكام وطمئنوا ابنكم أنه مرض كأي مرض وله علاج. نبرة دافئة متفهمة غير مخيفة."
    },
    {
        "filename": "189647f0_Self-Confidence_&_Identity_ar.mp4",
        "source_id": "dab0fff1-8180-4a3f-99ae-6791b243d690",
        "prompt": "أنشئ فيديو تعليمياً قصيراً (~5 دقائق) بالعربية لأولياء أمور أطفال 10-12 سنة عن بناء الثقة بالنفس والهوية في مرحلة التشكيك الذاتي. النقاط: قيمة الطفل عند الله بعمله لا بمظهره أو عدد أصدقائه أو درجاته؛ امدح الجهد لا النتيجة؛ أعطه مساحة قرار حقيقية؛ ادعُ له بالثبات؛ اربط ثقته بهويته الإيمانية: أنت ابن هذه الأمة والله يراك. نبرة محفزة إيجابية بطابع إسلامي أصيل."
    },
    {
        "filename": "6ca7b391_Islamic_Parenting_Tweens_ar.mp4",
        "source_id": "440183bc-479c-49c1-bb07-fe35fa62295f",
        "prompt": "أنشئ فيديو تعليمياً قصيراً (~5 دقائق) بالعربية لأولياء أمور أطفال 10-12 سنة عن تعليم الصلاة وترسيخها كهوية لا كروتين. النقاط: في هذا السن يبدأ الطفل فهم معنى التكليف؛ الصلاة صلة بالله وليست واجباً ثقيلاً؛ القدوة أقوى من الأوامر — صلِّ أمامه وبجانبه؛ ناقشه: لماذا نصلي؟ وكيف نخشع؟؛ التدرج والتشجيع لا العقاب والتخويف. نبرة إيمانية دافئة عملية."
    },
    {
        "filename": "823e565d_Adulthood_Mental_Health_ar.mp4",
        "source_id": "f9989ce3-a6e7-48dc-a627-87fee569c42d",
        "prompt": "أنشئ فيديو تعليمياً قصيراً (~5 دقائق) بالعربية موجهاً للشباب 16-18 سنة وأولياء أمورهم عن بناء شبكة أمان نفسية ذاتية عند الانتقال للجامعة أو العمل. النقاط: الانتقال يحمل ضغوطاً جديدة (غربة، أداء، علاقات، قرارات مالية)؛ الأدوات: روتين ثابت للنوم والحركة والغذاء كأساس كيميائي للدماغ، شبكة دعم (صديق موثوق، مرشد أكاديمي، مستشار نفسي)، كتابة علامات التحذير الشخصية ومراقبتها أسبوعياً، وخطة طوارئ تشمل الخط الساخن 937؛ الاستقلال يعني تولي مسؤولية صحتك النفسية. نبرة ناضجة محترمة تخاطب الشاب مباشرة."
    },
    {
        "filename": "82b4b434_Online_Safety_ar.mp4",
        "source_id": "5fb6588e-d31a-4cca-8e0c-052b364a72ac",
        "prompt": "أنشئ فيديو تعليمياً قصيراً (~5 دقائق) بالعربية لأولياء أمور أطفال 10-12 سنة عن أساسيات الأمان على الإنترنت. النقاط: قواعد الخصوصية الأساسية (لا مشاركة معلومات شخصية أو صور أو موقع مع غرباء)، إعدادات الخصوصية في التطبيقات والألعاب، التعامل مع الغرباء أونلاين، أهمية أن يعرف الطفل أنه يستطيع إخبار والديه بأي شيء مقلق دون خوف من العقاب، والمراقبة الذكية المبنية على الثقة لا التجسس. نبرة عملية مطمئنة."
    },
    {
        "filename": "9a511818_Cyberbullying_Pre-Teens_ar.mp4",
        "source_id": "5fb6588e-d31a-4cca-8e0c-052b364a72ac",
        "prompt": "أنشئ فيديو تعليمياً قصيراً (~5 دقائق) بالعربية لأولياء أمور أطفال 10-12 سنة عن التنمر الإلكتروني. النقاط: لماذا هو أخطر من التنمر التقليدي (يلاحق الطفل 24 ساعة، يصل إلى غرفته، ويبقى أثره)؛ علّم طفلك ثلاث خطوات: لا تشارك ولا تكن متفرجاً، التقط لقطة شاشة وأبلغ المنصة وأخبر والديك، وللبلاغات الجدية في مصر اتصل بخط 19099؛ دور الوالدين: افتحوا باب الحوار قبل وقوع المشكلة. نبرة جادة لكن غير مرعبة."
    },
    {
        "filename": "c2491bd6_Digital_Footprint_ar.mp4",
        "source_id": "b607c436-be69-4a32-839b-af09cae03dc4",
        "prompt": "أنشئ فيديو تعليمياً قصيراً (~5 دقائق) بالعربية للمراهقين 13-15 سنة وأولياء أمورهم عن البصمة الرقمية. النقاط: كل منشور وتعليق ولايك وبحث يُخزَّن ويُحلَّل وقد يُباع ويبقى لسنوات؛ الجامعات والشركات تفحص البصمة الرقمية قبل القبول والتوظيف؛ القاعدة الذهبية: لا تنشر ما لا تريد أن يراه والدك أو مديرك المستقبلي؛ عادة المراجعة الشهرية: احذف القديم، راجع إعدادات الخصوصية، نظّف الأثر. نبرة واقعية تخاطب المراهق باحترام.",
        "pre_generated_artifact_id": "a76b54ad-20f7-4c9f-bd02-860c0d8ab654"
    },
    {
        "filename": "c45e22b4_Digital_Detectives_ar.mp4",
        "source_id": "f7e6f02d-39fb-4888-ae4a-9e0644e75f5e",
        "prompt": "أنشئ فيديو تعليمياً قصيراً (~5 دقائق) بالعربية لأولياء أمور أطفال 10-12 سنة عن تعليم التفكير النقدي الرقمي. النقاط: الخوارزميات تُغذّي الطفل بما يحب لا بما يفيد؛ علّمه أربعة أسئلة قبل تصديق أي محتوى: من المصدر؟ هل يؤكده مصدر آخر موثوق? هل يحاول إثارة غضبي أو خوفي؟ هل بحثت في مواقع موثوقة؟؛ فعّل البحث الآمن SafeSearch؛ اجعلوا تقييم الأخبار لعبة عائلية. نبرة ذكية ممتعة."
    },
    {
        "filename": "f0060e8d_Adolescence_Safely_ar.mp4",
        "source_id": "20e00eef-fa60-4165-9364-ef869223c0f6",
        "prompt": "أنشئ فيديو تعليمياً قصيراً (~5 دقائق) بالعربية لأولياء أمور أطفال 10-12 سنة عن العادات الصحية قبل المراهقة. النقاط: العادات الآن تصنع صحة المستقبل؛ النوم 9-11 ساعة، حركة 60 دقيقة يومياً، غذاء حقيقي بأقل سكر ومعالجات، شاشات أقل من ساعتين يومياً ولا شاشات في غرفة النوم؛ الرسالة الأهم للوالدين: كونوا النموذج — طفلك يقلد ما يراك تفعله لا ما تقوله. نبرة عملية مشجعة."
    }
]

async def run_command(cmd):
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode(), stderr.decode()

async def generate_video(source_id, prompt):
    # No --wait parameter so it starts the task and returns immediately with the task ID
    cmd = [CLI_PATH, "generate", "video", "--language", "ar_001", "-s", source_id, prompt]
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
    active_tasks = []

    # 1. Trigger or reuse generations
    for idx, target in enumerate(VIDEOS_TO_GENERATE, 1):
        filename = os.path.join(VIDEOS_DIR, target["filename"])
        source_id = target["source_id"]
        prompt = target["prompt"]
        
        # Check if already generated
        if os.path.exists(filename) and os.path.getsize(filename) > 10 * 1024 * 1024:
            print(f"[{idx}/{len(VIDEOS_TO_GENERATE)}] {filename} already exists and looks valid. Skipping.")
            continue

        pre_gen_id = target.get("pre_generated_artifact_id")
        if pre_gen_id:
            print(f"[{idx}/{len(VIDEOS_TO_GENERATE)}] Re-using pre-generated artifact ID {pre_gen_id} for {target['filename']}")
            # Immediately add to poll queue as completed
            active_tasks.append({
                "filename": filename,
                "task_id": pre_gen_id,
                "description": f"Pre-generated artifact {pre_gen_id}"
            })
            continue

        print(f"\n[{idx}/{len(VIDEOS_TO_GENERATE)}] Triggering Video {target['filename']} (Source: {source_id})...")
        task_id = await generate_video(source_id, prompt)
        if task_id:
            print(f"Triggered successfully. Task ID: {task_id}")
            active_tasks.append({
                "filename": filename,
                "task_id": task_id,
                "description": target["filename"]
            })
            # Sleep briefly to avoid hammering the NotebookLM API
            await asyncio.sleep(5)
        else:
            print(f"Failed to trigger video generation for {target['filename']}")
            
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
            print("Sleeping 30 seconds before next poll...")
            await asyncio.sleep(30)

    print("\nAll video tasks finished processing.")

if __name__ == "__main__":
    asyncio.run(main())
