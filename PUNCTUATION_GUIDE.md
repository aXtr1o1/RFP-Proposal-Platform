# Punctuation Guide - Bullets vs Paragraphs

## Rule: Use Dots as Bullet Symbols, NOT in Bullet Text

---

## ✅ CORRECT Format

### Bullet Points (NO Periods)

```
Programme Overview

● Impetus Strategy designs functional standards
● Arabic-first capacity-building for 1,000 candidates  
● Six-phase delivery from planning to closure
● Outputs include role descriptions and qualifications
```

**Key Points**:
- ✅ Bullet symbol (●) represents the point
- ✅ No period (.) at end of text
- ✅ Concise phrases, not full sentences
- ✅ Professional appearance

---

### Paragraph Content (WITH Periods)

```
Executive Summary

The project will deliver comprehensive strategic framework 
for capacity building. Implementation spans six phases from 
planning through closure. All deliverables will be SAQF-aligned 
and culturally appropriate.
```

**Key Points**:
- ✅ Normal sentence structure
- ✅ Periods at end of sentences
- ✅ Full paragraphs with proper punctuation
- ✅ For content field only (not bullets)

---

## ❌ INCORRECT Format

### Bullet Points (WITH Periods - WRONG)

```
Programme Overview

● Impetus Strategy designs functional standards.  ← ❌ Period!
● Arabic-first capacity-building for 1,000 candidates.  ← ❌ Period!
● Six-phase delivery from planning to closure.  ← ❌ Period!
```

**Why Wrong**:
- ❌ Redundant (bullet symbol already marks the point)
- ❌ Looks cluttered
- ❌ Not standard bullet formatting

---

## Implementation

### How It Works

```
AI Generates Content
        ↓
Text Formatter
(removes periods from bullets)
        ↓
Content Validator
(cleans all bullet text)
        ↓
PowerPoint Renderer
(adds ● symbols)
        ↓
Final Slide: ● Bullet text without period
```

---

## Examples by Slide Type

### 1. Title & Content Slide

**JSON**:
```json
{
  "bullets": [
    {"text": "Strategic framework design"},
    {"text": "Stakeholder engagement process"},
    {"text": "Quality assurance methodology"}
  ]
}
```

**Display**:
```
● Strategic framework design
● Stakeholder engagement process
● Quality assurance methodology
```

---

### 2. Four-Box Layout

**JSON**:
```json
{
  "bullets": [
    {"text": "Research & analysis"},
    {"text": "Strategy design"},
    {"text": "Implementation"},
    {"text": "Monitoring"}
  ]
}
```

**Display** (in colored boxes):
```
┌──────────────────┐  ┌──────────────────┐
│ Research &       │  │ Strategy design  │
│ analysis         │  │                  │
└──────────────────┘  └──────────────────┘

┌──────────────────┐  ┌──────────────────┐
│ Implementation   │  │ Monitoring       │
│                  │  │                  │
└──────────────────┘  └──────────────────┘
```

Note: No periods in any box!

---

### 3. Agenda Slide

**JSON**:
```json
{
  "layout_hint": "agenda",
  "bullets": [
    {"text": "Introduction & Overview"},
    {"text": "Objectives & Goals"},
    {"text": "Approach & Methodology"}
  ]
}
```

**Display**:
```
Agenda

● Introduction & Overview
● Objectives & Goals
● Approach & Methodology
```

---

### 4. Paragraph Slide (Periods OK)

**JSON**:
```json
{
  "layout_hint": "content_paragraph",
  "content": "The strategic framework integrates multiple methodologies. Implementation will occur over six phases. All deliverables will be SAQF-aligned."
}
```

**Display**:
```
Executive Overview

The strategic framework integrates multiple methodologies. 
Implementation will occur over six phases. All deliverables 
will be SAQF-aligned.
```

Note: Periods are correct for paragraphs!

---

## Automatic Cleaning

### What Gets Cleaned

**Input from AI**:
```
"text": "Strategic framework design."
```

**After text_formatter.py**:
```
"text": "Strategic framework design"
```

**After content_validator.py**:
```
"text": "Strategic framework design"  ← Verified clean
```

**In PowerPoint**:
```
● Strategic framework design
```

---

## Edge Cases Handled

### Multiple Periods
```
Input:  "Framework design..."
Clean:  "Framework design"
```

### Period in Middle (Kept)
```
Input:  "Dr. Smith's framework design"
Clean:  "Dr. Smith's framework design"
(Only removes TRAILING periods)
```

### Abbreviations (Kept)
```
Input:  "QA function for U.S. standards"
Clean:  "QA function for U.S. standards"
(Internal periods preserved)
```

### Trailing Period with Spaces
```
Input:  "Framework design .  "
Clean:  "Framework design"
```

---

## Testing Checklist

After generating a presentation:

### Bullet Slides
- [ ] NO bullets end with periods
- [ ] Bullet symbols (●) display properly
- [ ] Text is concise phrases
- [ ] Internal punctuation preserved (e.g., "U.S." stays)

### Paragraph Slides
- [ ] Sentences have periods
- [ ] Proper grammar and punctuation
- [ ] Full sentences, not phrases

### Four-Box Slides
- [ ] NO periods in box text
- [ ] Text fits in boxes
- [ ] Concise and clean

### Agenda Slides
- [ ] NO periods in agenda items
- [ ] Clean, professional list
- [ ] Bullet symbols display

---

## Configuration

```python
# File: apps/app/utils/text_formatter.py

def clean_bullet_text(text: str, remove_periods: bool = True):
    """
    Removes:
    - Bullet symbols (●, ○, •, etc.)
    - Trailing periods (.)
    - Extra whitespace
    - Formatting marks
    
    Preserves:
    - Internal punctuation (Dr., U.S., etc.)
    - Apostrophes and hyphens
    - Numbers and symbols
    """
```

---

## Summary

| Content Type | Symbol | Period | Example |
|--------------|--------|--------|---------|
| **Bullet Points** | ● | ❌ NO | "Strategic framework design" |
| **Four-Box** | (in box) | ❌ NO | "Research & analysis" |
| **Agenda** | ● | ❌ NO | "Introduction & Overview" |
| **Paragraphs** | (none) | ✅ YES | "The project delivers framework." |

---

## Files Modified

1. ✅ `apps/app/core/ppt_prompts.py` - AI formatting rules
2. ✅ `apps/app/utils/text_formatter.py` - Period removal
3. ✅ `apps/app/utils/content_validator.py` - Auto-cleaning

---

## Visual Guide

### CORRECT ✅

```
System Components

● Governance: Steering committee and QA function
● Role & Standards Engine: Job analysis repository  
● Qualification Management: SAQF documentation sets
● Learning Management: Provider network and curricula
● Performance & Impact: KPI dashboards and reporting
```

### INCORRECT ❌

```
System Components

● Governance: Steering committee and QA function.  ← Period!
● Role & Standards Engine: Job analysis repository.  ← Period!
● Qualification Management: SAQF documentation sets.  ← Period!
```

---

## Status

**Implementation**: ✅ Complete (Triple Protection)
**Testing**: Ready for validation
**Linting**: No errors ✅

**All bullet points will display without periods!**

