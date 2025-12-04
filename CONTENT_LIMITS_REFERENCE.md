# Content Limits - Quick Reference

## Slide Content Limits (Auto-Split Triggers)

### 📝 Bullet Slides

| Limit | Value | What Happens |
|-------|-------|--------------|
| **Max bullets per slide** | 3 | Slide splits into multiple parts |
| **Max characters per bullet** | 150 | Slide splits to accommodate |
| **Max total characters** | 600 | Content distributed across slides |
| **Max estimated height** | 4.0 inches | Smart split based on layout |

**Example**:
- ✅ GOOD: 3 bullets × 120 chars = 360 total
- ⚠️ SPLITS: 5 bullets × 100 chars = 500 total (too many bullets)
- ⚠️ SPLITS: 3 bullets × 200 chars = 600 total (bullets too long)

---

### 📊 Table Slides

| Limit | Value | What Happens |
|-------|-------|--------------|
| **Max data rows per slide** | 4 | Table splits with headers repeated |
| **Min columns** | 3 | Required for valid table |
| **Max columns** | 5 | Recommended for readability |

**Example**:
- ✅ GOOD: 4 data rows + 1 header = 5 total rows
- ⚠️ SPLITS: 8 data rows → 2 slides (4 rows + header each)

---

### 📋 Agenda Slides

| Limit | Value | What Happens |
|-------|-------|--------------|
| **Max items per agenda** | 5 | Splits into "Agenda" and "Agenda (Continued)" |

**Example**:
- ✅ GOOD: 5 agenda items
- ⚠️ SPLITS: 8 agenda items → 2 slides (5 + 3)

---

### 🎯 Four-Box Slides

| Limit | Value | What Happens |
|-------|-------|--------------|
| **Required items** | Exactly 4 | Splits into multiple four-box slides or pads with empty |

**Example**:
- ✅ GOOD: Exactly 4 items
- ⚠️ SPLITS: 7 items → 2 slides (4 + 3, third padded to 4)

---

## AI Generation Guidelines

### Bullet Text Guidelines

**✅ GOOD Examples** (120-150 chars):
```
• Strategic framework combines SWOT analysis, Porter's Five Forces, and PESTEL methodology
• Six-phase delivery: planning, analysis, alignment, training, enablers, and closure
• 10 role descriptions, SAQF qualifications, training curricula, and e-learning packages
```

**❌ BAD Examples** (200+ chars - WILL SPLIT):
```
• Impetus Strategy will design functional standards, align and register qualifications 
  to SAQF, and execute Arabic-first capacity-building for 1,000 candidates serving the 
  Guests of Allah with comprehensive training programs
```

---

### Table Design Guidelines

**✅ GOOD Table** (4 data rows):
```
┌──────────────┬────────────────┬──────────┬──────────┐
│ Phase        │ Activities     │ Duration │ Outputs  │
├──────────────┼────────────────┼──────────┼──────────┤
│ Planning     │ Charter & QA   │ 2 months │ Plan     │
│ Analysis     │ Research       │ 6 months │ Roles    │
│ Alignment    │ SAQF           │ 6 months │ Quals    │
│ Execution    │ Training       │ 12 months│ Complete │
└──────────────┴────────────────┴──────────┴──────────┘
```

**⚠️ SPLITS** (8 data rows - becomes 2 slides):
```
Slide 1: Title (Part 1 of 2)
- Rows 1-4 + header

Slide 2: Title (Part 2 of 2)
- Rows 5-8 + header
```

---

## Overflow Detection Logic

### What Triggers a Split?

```python
# Bullet slides split if ANY of these are true:
bullet_count > 3                    # Too many bullets
any(bullet_length > 150)            # Any single bullet too long
total_chars > 600                   # Total text too long
estimated_height > 4.0              # Visual height too tall

# Table slides split if:
data_rows > 4                       # Too many rows

# Agenda slides split if:
agenda_items > 5                    # Too many items
```

---

## Part Numbering Examples

### Bullet Splits
```
Original: "Key Commitments" (7 bullets)
Result:
  - "Key Commitments (Part 1 of 3)" - 3 bullets
  - "Key Commitments (Part 2 of 3)" - 3 bullets
  - "Key Commitments (Part 3 of 3)" - 1 bullet
```

### Table Splits
```
Original: "Project Timeline" (10 data rows)
Result:
  - "Project Timeline (Part 1 of 3)" - 4 rows + header
  - "Project Timeline (Part 2 of 3)" - 4 rows + header
  - "Project Timeline (Part 3 of 3)" - 2 rows + header
```

### Agenda Splits
```
Original: "Agenda" (8 items)
Result:
  - "Agenda" - 5 items
  - "Agenda (Continued)" - 3 items
```

---

## Height Estimation Formula

```python
# Main bullet height calculation
characters = len(bullet_text)
lines = (characters + 69) // 70    # ~70 chars per line
height = 0.35 * lines              # 0.35 inches per line

# Sub-bullet height calculation
sub_chars = len(sub_bullet_text)
sub_lines = (sub_chars + 59) // 60 # ~60 chars per line
sub_height = 0.28 * sub_lines      # 0.28 inches per line

# Total bullet height
total = height + sub_height + spacing
spacing = 0.18 (with subs) or 0.12 (without)

# Slide overflows if total > 4.0 inches
```

---

## Configuration Constants

```python
# File: apps/app/utils/content_validator.py

MAX_BULLETS_PER_SLIDE = 3           # Bullets per slide
MAX_BULLET_LENGTH = 150             # Chars per bullet
CHAR_LIMIT_PER_SLIDE = 600          # Total chars per slide
MAX_CONTENT_HEIGHT_INCHES = 4.0     # Visual height limit
TABLE_MAX_ROWS = 4                  # Table data rows
AGENDA_MAX_BULLETS = 5              # Agenda items
MAX_SUB_BULLETS_PER_BULLET = 2      # Sub-bullets per bullet
```

---

## Visual Guidelines

### Slide Density

**✅ OPTIMAL** (3 bullets, ~450 chars):
```
□□□□□□□□□□□□□□□□□□□□□□□□
□                        □
□  TITLE                 □
□                        □
□  • Bullet one (120)    □
□                        □
□  • Bullet two (110)    □
□                        □
□  • Bullet three (130)  □
□                        □
□□□□□□□□□□□□□□□□□□□□□□□□

White space: ~40%
Readability: Excellent
```

**❌ CRAMPED** (5+ bullets, 800+ chars) - WILL AUTO-SPLIT:
```
□□□□□□□□□□□□□□□□□□□□□□□□
□  TITLE                 □
□  • Long bullet one...  □
□  • Long bullet two...  □
□  • Long bullet three...□
□  • Long bullet four... □
□  • Long bullet five... □
□□□□□□□□□□□□□□□□□□□□□□□□

White space: ~15%
Readability: Poor
```

---

## AI Prompt Compliance

### Checklist for AI-Generated Content

```
✓ Each bullet is 120-150 characters max
✓ Max 3-4 bullets per slide
✓ Table rows limited to 4-5 per slide
✓ Agenda items limited to 5 per slide
✓ No single bullet > 150 characters
✓ Total slide characters < 600
✓ Content is concise and scannable
```

---

## Testing Edge Cases

### Test 1: Boundary Cases
- Exactly 3 bullets × 150 chars = 450 total ✅ Should NOT split
- Exactly 4 bullets × 100 chars = 400 total ⚠️ Should split (4 > 3)
- Exactly 3 bullets × 151 chars = 453 total ⚠️ Should split (bullet > 150)

### Test 2: Table Boundaries
- Table with 4 data rows ✅ Should NOT split
- Table with 5 data rows ⚠️ Should split into 2 slides
- Table with 8 data rows ⚠️ Should split into 2 slides (4 + 4)

### Test 3: Mixed Content
- 2 bullets (100 chars each) + 1 bullet (200 chars) ⚠️ Should split
- 3 bullets (50 chars each) + large table ✅ Only table splits

---

## Troubleshooting

### "Why did my slide split?"

Check logs for:
```
📝 Long bullet detected at index X: Y chars (max 150)
📝 Bullet count overflow: X bullets (max 3)
📊 Table overflow detected: X rows (max 4)
📏 Height overflow: X inches (max 4.0)
🔤 Character overflow: X chars (max 600)
```

### "How to prevent splitting?"

1. Keep bullets under 150 characters
2. Limit to 3 bullets per slide
3. Keep tables to 4 rows
4. Use concise, scannable language
5. Break complex points into multiple slides

---

## Summary

| Content Type | Limit | Action |
|--------------|-------|--------|
| Bullets per slide | 3 | Auto-split |
| Bullet length | 150 chars | Auto-split |
| Total chars | 600 | Auto-split |
| Table rows | 4 | Auto-split |
| Agenda items | 5 | Auto-split |
| Slide height | 4.0" | Auto-split |

**All splits are automatic and logged for transparency.**

