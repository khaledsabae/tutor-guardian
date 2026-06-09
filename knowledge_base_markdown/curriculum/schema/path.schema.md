# Curriculum Path

## Metadata

| Field | Value |
| --- | --- |
| **$Id** | https://tutor-guardian.local/schemas/curriculum/path.schema.json |
| **$Schema** | https://json-schema.org/draft/2020-12/schema |
| **Additionalproperties** | No |
| **Required** | `id`, `title`, `age_group`, `domain`, `description`, `lesson_ids`, `estimated_days` |
| **Type** | object |

## Description

> مسار تربوي متكامل لفترة زمنية محددة (≤ 30 يوم) يجمع عدة دروس مرتبة في رحلة واحدة. كل مسار مرتبط بفئة عمرية ومجال محدد من taxonomy. ملاحظة: قيم enum هنا يجب أن تطابق backend/app/core/taxonomy.py.

## Properties

| Field | Value |
| --- | --- |
| **Age Group** | {"type": "string", "enum": ["0-3", "4-6", "7-9", "10-12", "13-15", "16-18"], "description": "الفئة العمرية المستهدفة (من CANONICAL_AGE_GROUPS في taxonomy.py — بدون unspecified للمسارات لأنها مرحلة عمرية محددة)."} |
| **Created At** | {"type": "string", "format": "date-time", "description": "تاريخ إنشاء المسار (ISO 8601)."} |
| **Description** | {"type": "string", "minLength": 10, "maxLength": 600, "description": "وصف موجز للمسار: ما سيتعلمه الوالد، ولماذا هذه المرحلة العمرية، وكيف يقاس النجاح."} |
| **Domain** | {"type": "string", "enum": ["medical", "cyber", "islamic_parenting", "development"], "description": "المجال الأساسي للمسار (من CANONICAL_DOMAINS في taxonomy.py). مسارات التربية الإسلامية تستند على Prophetic 7-7-7 + Ghazali tazkiyah."} |
| **Estimated Days** | {"type": "integer", "minimum": 1, "maximum": 30, "description": "المدة الإرشادية لإكمال المسار بالأيام. تنبيه: ≤ 30 يوماً — مسارات أطول من شهر تنقسم لمسارين."} |
| **Id** | {"type": "string", "pattern": "^path_[a-z0-9_\\-]{3,80}$", "description": "معرّف المسار. النمط: path_<age_group>_<domain>_<variant>. مثال: path_4-6_islamic_parenting_bond."} |
| **Is Published** | {"type": "boolean", "default": false, "description": "هل المسار منشور في الـ app (true) أم لا يزال في draft (false)."} |
| **Lesson Ids** | {"type": "array", "minItems": 1, "maxItems": 30, "items": {"type": "string", "pattern": "^lesson_[a-z0-9_\\-]{3,80}$"}, "description": "قائمة الدروس بالترتيب التعليمي (order=1 أولاً). كل lesson_id يجب أن يطابق ملف درس موجود في knowledge_base/curriculum/lessons/."} |
| **Pedagogical Framework** | {"type": "string", "enum": ["prophetic_7_7_7", "ghazali_tazkiyah", "attachment_rahma", "zpd_scaffolded"], "description": "الإطار التربوي المرجعي للمسار. معظم مسارات التربية الإسلامية تعتمد prophetic_7_7_7 (مرحلة 7-14) + ghazali_tazkiyah."} |
| **Prerequisites** | {"type": "array", "items": {"type": "string", "pattern": "^path_[a-z0-9_]{3,80}$"}, "default": [], "description": "مسارات يجب إكمالها قبل البدء بهذا المسار (اختياري)."} |
| **Primary Reference** | {"type": "object", "description": "المرجع العلمي/الشرعي الأساسي الذي بُني عليه المسار.", "additionalProperties": false, "properties": {"type": {"type": "string", "enum": ["DSM-5", "كتاب_فقهي", "حديث", "كتاب_تربوي", "تقرير_سيبراني", "إرشاد_مهني", "مقال_تنموي", "تقرير_طبي", "مقال_تربوي"]}, "info": {"type": "string", "minLength": 3, "maxLength": 200}}} |
| **Title** | {"type": "string", "minLength": 3, "maxLength": 120, "description": "عنوان المسار بالعربية الفصحى، موجّه للوالد."} |
| **Updated At** | {"type": "string", "format": "date-time", "description": "تاريخ آخر تعديل (ISO 8601)."} |
| **Version** | {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$", "description": "إصدار المسار (semver). مثال: 1.0.0."} |

## Raw JSON

<details>
<summary>Click to view raw JSON</summary>

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://tutor-guardian.local/schemas/curriculum/path.schema.json",
  "title": "Curriculum Path",
  "description": "مسار تربوي متكامل لفترة زمنية محددة (≤ 30 يوم) يجمع عدة دروس مرتبة في رحلة واحدة. كل مسار مرتبط بفئة عمرية ومجال محدد من taxonomy. ملاحظة: قيم enum هنا يجب أن تطابق backend/app/core/taxonomy.py.",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "title",
    "age_group",
    "domain",
    "description",
    "lesson_ids",
    "estimated_days"
  ],
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^path_[a-z0-9_\\-]{3,80}$",
      "description": "معرّف المسار. النمط: path_<age_group>_<domain>_<variant>. مثال: path_4-6_islamic_parenting_bond."
    },
    "title": {
      "type": "string",
      "minLength": 3,
      "maxLength": 120,
      "description": "عنوان المسار بالعربية الفصحى، موجّه للوالد."
    },
    "age_group": {
      "type": "string",
      "enum": [
        "0-3",
        "4-6",
        "7-9",
        "10-12",
        "13-15",
        "16-18"
      ],
      "description": "الفئة العمرية المستهدفة (من CANONICAL_AGE_GROUPS في taxonomy.py — بدون unspecified للمسارات لأنها مرحلة عمرية محددة)."
    },
    "domain": {
      "type": "string",
      "enum": [
        "medical",
        "cyber",
        "islamic_parenting",
        "development"
      ],
      "description": "المجال الأساسي للمسار (من CANONICAL_DOMAINS في taxonomy.py). مسارات التربية الإسلامية تستند على Prophetic 7-7-7 + Ghazali tazkiyah."
    },
    "description": {
      "type": "string",
      "minLength": 10,
      "maxLength": 600,
      "description": "وصف موجز للمسار: ما سيتعلمه الوالد، ولماذا هذه المرحلة العمرية، وكيف يقاس النجاح."
    },
    "lesson_ids": {
      "type": "array",
      "minItems": 1,
      "maxItems": 30,
      "items": {
        "type": "string",
        "pattern": "^lesson_[a-z0-9_\\-]{3,80}$"
      },
      "description": "قائمة الدروس بالترتيب التعليمي (order=1 أولاً). كل lesson_id يجب أن يطابق ملف درس موجود في knowledge_base/curriculum/lessons/."
    },
    "estimated_days": {
      "type": "integer",
      "minimum": 1,
      "maximum": 30,
      "description": "المدة الإرشادية لإكمال المسار بالأيام. تنبيه: ≤ 30 يوماً — مسارات أطول من شهر تنقسم لمسارين."
    },
    "pedagogical_framework": {
      "type": "string",
      "enum": [
        "prophetic_7_7_7",
        "ghazali_tazkiyah",
        "attachment_rahma",
        "zpd_scaffolded"
      ],
      "description": "الإطار التربوي المرجعي للمسار. معظم مسارات التربية الإسلامية تعتمد prophetic_7_7_7 (مرحلة 7-14) + ghazali_tazkiyah."
    },
    "primary_reference": {
      "type": "object",
      "description": "المرجع العلمي/الشرعي الأساسي الذي بُني عليه المسار.",
      "additionalProperties": false,
      "properties": {
        "type": {
          "type": "string",
          "enum": [
            "DSM-5",
            "كتاب_فقهي",
            "حديث",
            "كتاب_تربوي",
            "تقرير_سيبراني",
            "إرشاد_مهني",
            "مقال_تنموي",
            "تقرير_طبي",
            "مقال_تربوي"
          ]
        },
        "info": {
          "type": "string",
          "minLength": 3,
          "maxLength": 200
        }
      }
    },
    "prerequisites": {
      "type": "array",
      "items": {
        "type": "string",
        "pattern": "^path_[a-z0-9_]{3,80}$"
      },
      "default": [],
      "description": "مسارات يجب إكمالها قبل البدء بهذا المسار (اختياري)."
    },
    "is_published": {
      "type": "boolean",
      "default": false,
      "description": "هل المسار منشور في الـ app (true) أم لا يزال في draft (false)."
    },
    "version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+$",
      "description": "إصدار المسار (semver). مثال: 1.0.0."
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "تاريخ إنشاء المسار (ISO 8601)."
    },
    "updated_at": {
      "type": "string",
      "format": "date-time",
      "description": "تاريخ آخر تعديل (ISO 8601)."
    }
  }
}
```
</details>
