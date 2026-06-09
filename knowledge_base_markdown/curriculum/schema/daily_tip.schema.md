# Daily Tip

## Metadata

| Field | Value |
| --- | --- |
| **$Id** | https://tutor-guardian.local/schemas/curriculum/daily_tip.schema.json |
| **$Schema** | https://json-schema.org/draft/2020-12/schema |
| **Additionalproperties** | No |
| **Required** | `id`, `age_group`, `domain`, `text`, `unit_id` |
| **Type** | object |

## Description

> نصيحة يومية قصيرة (≤ 280 حرف) مستخرجة من knowledge unit واحد. تظهر في الواجهة الرئيسية للـ app. لا تتبع مساراً معيناً — تُختار من pool حسب age_group + يوم الأسبوع (rotating). ملاحظة: enum تطابق backend/app/core/taxonomy.py.

## Properties

| Field | Value |
| --- | --- |
| **Age Group** | {"type": "string", "enum": ["0-3", "4-6", "7-9", "10-12", "13-15", "16-18"], "description": "الفئة العمرية. النصيحة تُفلتر على الواجهة بناءً على child profile."} |
| **Created At** | {"type": "string", "format": "date-time"} |
| **Day Of Week** | {"type": "integer", "minimum": 0, "maximum": 6, "description": "يوم الأسبوع المفضّل (0=الإثنين، 6=الأحد). اختياري. لو غير محدد تظهر في أي يوم (rotating)."} |
| **Domain** | {"type": "string", "enum": ["medical", "cyber", "islamic_parenting", "development"], "description": "المجال. يؤثر على badge/icon النصيحة في الـ UI."} |
| **Id** | {"type": "string", "pattern": "^tip_[0-9-]+_[0-9]{3,4}$", "description": "معرّف النصيحة. النمط: tip_<age_group>_<seq>. مثال: tip_4-6_001. الـ seq يتجدد لكل age_group."} |
| **Is Published** | {"type": "boolean", "default": true, "description": "النصائح في الـ pool تكون true افتراضياً (للتنويع في العرض)."} |
| **Tags** | {"type": "array", "maxItems": 5, "items": {"type": "string"}, "default": [], "description": "وسوم للبحث/الفلترة (مثل: 'صلاة', 'نوم', 'أكل')."} |
| **Text** | {"type": "string", "minLength": 20, "maxLength": 280, "description": "النصيحة المختصرة. جملة أو جملتان. مثال: 'قبل النوم: اقرأ لطفلك آية الكرسي واشرح له أنها حماية'."} |
| **Time Of Day** | {"type": "string", "enum": ["morning", "evening", "bedtime", "anytime"], "default": "anytime", "description": "الوقت الإرشادي للعرض في الواجهة."} |
| **Unit Id** | {"type": "string", "format": "uuid", "description": "معرّف knowledge unit الأصلي (من knowledge_base/units/*.json). النصيحة مختصرة من unit.text_simplified."} |
| **Version** | {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"} |

## Raw JSON

<details>
<summary>Click to view raw JSON</summary>

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://tutor-guardian.local/schemas/curriculum/daily_tip.schema.json",
  "title": "Daily Tip",
  "description": "نصيحة يومية قصيرة (≤ 280 حرف) مستخرجة من knowledge unit واحد. تظهر في الواجهة الرئيسية للـ app. لا تتبع مساراً معيناً — تُختار من pool حسب age_group + يوم الأسبوع (rotating). ملاحظة: enum تطابق backend/app/core/taxonomy.py.",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "age_group",
    "domain",
    "text",
    "unit_id"
  ],
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^tip_[0-9-]+_[0-9]{3,4}$",
      "description": "معرّف النصيحة. النمط: tip_<age_group>_<seq>. مثال: tip_4-6_001. الـ seq يتجدد لكل age_group."
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
      "description": "الفئة العمرية. النصيحة تُفلتر على الواجهة بناءً على child profile."
    },
    "domain": {
      "type": "string",
      "enum": [
        "medical",
        "cyber",
        "islamic_parenting",
        "development"
      ],
      "description": "المجال. يؤثر على badge/icon النصيحة في الـ UI."
    },
    "text": {
      "type": "string",
      "minLength": 20,
      "maxLength": 280,
      "description": "النصيحة المختصرة. جملة أو جملتان. مثال: 'قبل النوم: اقرأ لطفلك آية الكرسي واشرح له أنها حماية'."
    },
    "unit_id": {
      "type": "string",
      "format": "uuid",
      "description": "معرّف knowledge unit الأصلي (من knowledge_base/units/*.json). النصيحة مختصرة من unit.text_simplified."
    },
    "day_of_week": {
      "type": "integer",
      "minimum": 0,
      "maximum": 6,
      "description": "يوم الأسبوع المفضّل (0=الإثنين، 6=الأحد). اختياري. لو غير محدد تظهر في أي يوم (rotating)."
    },
    "time_of_day": {
      "type": "string",
      "enum": [
        "morning",
        "evening",
        "bedtime",
        "anytime"
      ],
      "default": "anytime",
      "description": "الوقت الإرشادي للعرض في الواجهة."
    },
    "tags": {
      "type": "array",
      "maxItems": 5,
      "items": {
        "type": "string"
      },
      "default": [],
      "description": "وسوم للبحث/الفلترة (مثل: 'صلاة', 'نوم', 'أكل')."
    },
    "is_published": {
      "type": "boolean",
      "default": true,
      "description": "النصائح في الـ pool تكون true افتراضياً (للتنويع في العرض)."
    },
    "version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+$"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    }
  }
}
```
</details>
