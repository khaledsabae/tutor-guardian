# TutorGuardian Knowledge Unit

## Metadata

| Field | Value |
| --- | --- |
| **$Schema** | http://json-schema.org/draft-07/schema# |
| **Required** | `id`, `domain`, `source_file`, `title`, `language`, `text_original`, `text_simplified`, `created_at` |
| **Type** | object |

## Properties

| Field | Value |
| --- | --- |
| **Age Group** | {"type": "string", "enum": ["infant", "toddler", "preschool", "school_age", "adolescent", "teen", "all", "unspecified"]} |
| **Behavior Type** | {"type": "string", "enum": ["physical", "emotional", "social", "cognitive", "spiritual", "digital", "academic", "disciplinary", "sleep", "unspecified"]} |
| **Created At** | {"type": "string", "format": "date-time"} |
| **Domain** | {"type": "string", "enum": ["medical", "islamic_parenting", "digital_safety", "development"]} |
| **Id** | {"type": "string", "description": "UUID v4"} |
| **Keywords** | {"type": "array", "items": {"type": "string"}} |
| **Language** | {"type": "string", "enum": ["ar", "en", "mixed"]} |
| **Source File** | {"type": "string", "description": "Original PDF filename"} |
| **Source Url** | {"type": "string"} |
| **Text Original** | {"type": "string", "description": "Full extracted text from PDF"} |
| **Text Simplified** | {"type": "string", "description": "2-3 sentence Arabic summary"} |
| **Title** | {"type": "string", "description": "Extracted or inferred title"} |

## Raw JSON

<details>
<summary>Click to view raw JSON</summary>

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "TutorGuardian Knowledge Unit",
  "type": "object",
  "required": [
    "id",
    "domain",
    "source_file",
    "title",
    "language",
    "text_original",
    "text_simplified",
    "created_at"
  ],
  "properties": {
    "id": {
      "type": "string",
      "description": "UUID v4"
    },
    "domain": {
      "type": "string",
      "enum": [
        "medical",
        "islamic_parenting",
        "digital_safety",
        "development"
      ]
    },
    "source_file": {
      "type": "string",
      "description": "Original PDF filename"
    },
    "source_url": {
      "type": "string"
    },
    "title": {
      "type": "string",
      "description": "Extracted or inferred title"
    },
    "language": {
      "type": "string",
      "enum": [
        "ar",
        "en",
        "mixed"
      ]
    },
    "age_group": {
      "type": "string",
      "enum": [
        "infant",
        "toddler",
        "preschool",
        "school_age",
        "adolescent",
        "teen",
        "all",
        "unspecified"
      ]
    },
    "behavior_type": {
      "type": "string",
      "enum": [
        "physical",
        "emotional",
        "social",
        "cognitive",
        "spiritual",
        "digital",
        "academic",
        "disciplinary",
        "sleep",
        "unspecified"
      ]
    },
    "text_original": {
      "type": "string",
      "description": "Full extracted text from PDF"
    },
    "text_simplified": {
      "type": "string",
      "description": "2-3 sentence Arabic summary"
    },
    "keywords": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    }
  }
}
```
</details>
