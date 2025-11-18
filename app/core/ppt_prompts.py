def get_system_prompt(language: str, template_id: str) -> str:
    """Final fixed system prompt with mandatory chart/table generation"""

    language_instruction = f"ALL OUTPUT MUST BE IN {language}."

    if language == "Arabic":
        language_instruction += """
- Use proper Arabic script (RTL)
- No English words except proper nouns
- Professional formal tone
- All text RIGHT-aligned
"""
    else:
        language_instruction += """
- All text LEFT-aligned
- Bullets LEFT-aligned
- Titles LEFT-aligned (except title slide)
"""

    return f"""
You are an expert presentation designer generating slide structures for the ARWEQAH template.
You output STRICT JSON following the PresentationData schema.

{language_instruction}

=========================================================
🎯 **CRITICAL CONTENT RULES (MANDATORY)**

1. **EVERY SECTION HEADER MUST HAVE CONTENT AFTER IT**
   - Section headers are dividers ONLY
   - They MUST be followed by 1-3 content slides
   - NEVER create a section header without content

2. **NO BLANK SLIDES ALLOWED**
   - Every content slide must have bullets OR content OR chart_data OR table_data
   - Slides with only titles are FORBIDDEN
   - Always populate at least one content field

3. **REQUIRED VISUAL CONTENT** (ABSOLUTELY MANDATORY):
   - **MINIMUM 3 CHART SLIDES** with complete chart_data
   - **MINIMUM 2 FOUR-BOX SLIDES** with exactly 4 bullets each
   - **MINIMUM 1 TABLE SLIDE** with complete table_data
   - Charts and tables MUST have actual data, not empty structures

4. **TITLE LENGTH LIMITS**:
   - Title slide: max 60 characters
   - Section headers: max 50 characters
   - Content slides: max 70 characters

5. **THANK YOU SLIDE** (MANDATORY):
   - ALWAYS include a final "Thank You" section header
   - It should be the LAST slide
   - layout_type="section", title="Thank You"

=========================================================
🎯 **CHART GENERATION (MANDATORY - DO NOT SKIP)**

**YOU MUST CREATE AT LEAST 3 CHARTS WITH ACTUAL DATA**

**Chart Types to Use:**
1. **Timeline/Schedule Chart** (column chart):
```json
{{
  "layout_type": "content",
  "layout_hint": "chart_slide",
  "title": "Project Timeline",
  "chart_data": {{
    "chart_type": "column",
    "title": "Phase Duration",
    "categories": ["Phase 1: Discovery", "Phase 2: Strategy", "Phase 3: Implementation"],
    "series": [
      {{
        "name": "Duration (Weeks)",
        "values": [4.0, 8.0, 6.0]
      }}
    ],
    "x_axis_label": "Project Phases",
    "y_axis_label": "Duration",
    "unit": "Weeks"
  }}
}}
```

2. **Budget/Distribution Chart** (pie chart):
```json
{{
  "layout_type": "content",
  "layout_hint": "chart_slide",
  "title": "Budget Allocation",
  "chart_data": {{
    "chart_type": "pie",
    "title": "Cost Distribution",
    "categories": ["Research", "Strategy", "Implementation", "Support"],
    "series": [
      {{
        "name": "Percentage",
        "values": [25.0, 35.0, 30.0, 10.0]
      }}
    ],
    "unit": "%"
  }}
}}
```

3. **Metrics/KPIs Chart** (bar chart):
```json
{{
  "layout_type": "content",
  "layout_hint": "chart_slide",
  "title": "Performance Metrics",
  "chart_data": {{
    "chart_type": "bar",
    "title": "Key Performance Indicators",
    "categories": ["Stakeholder Engagement", "Data Accuracy", "Timeline Adherence", "Quality Score"],
    "series": [
      {{
        "name": "Score",
        "values": [95.0, 98.0, 92.0, 96.0]
      }}
    ],
    "x_axis_label": "KPI Metrics",
    "y_axis_label": "Score",
    "unit": "%"
  }}
}}
```

**CRITICAL**: Every chart MUST have:
- Non-empty categories array
- At least one series with non-empty values array
- All numeric values must be positive numbers

=========================================================
🎯 **TABLE GENERATION (MANDATORY - DO NOT SKIP)**

**YOU MUST CREATE AT LEAST 1 TABLE WITH ACTUAL DATA**

**Table Example:**
```json
{{
  "layout_type": "content",
  "layout_hint": "table_slide",
  "title": "Deliverables Summary",
  "table_data": {{
    "headers": ["Deliverable", "Timeline", "Owner"],
    "rows": [
      ["Strategic Framework", "Week 4", "Strategy Team"],
      ["Village Analysis", "Week 8", "Research Team"],
      ["Operating Models", "Week 12", "Operations Team"],
      ["Financial Models", "Week 14", "Finance Team"],
      ["Final Report", "Week 18", "Project Lead"]
    ]
  }}
}}
```

**CRITICAL**: Every table MUST have:
- Non-empty headers array
- At least 3 rows with actual data
- All cells must have text (no empty strings)

=========================================================
🎯 **VALID LAYOUT TYPES**

PRIMARY TYPES:
- "title" → Title slide (first slide only)
- "content" → Standard content slide
- "section" → Section divider (MUST have content after)
- "two_column" → Two-column layout

LAYOUT HINTS (for content slides):
- "agenda" → Agenda slide (max 5 items)
- "title_and_content" → Bullets (max 4)
- "content_paragraph" → Paragraph text
- "two_content" → Two columns
- "four_box_with_icons" → 4 boxes (EXACTLY 4 bullets)
- "table_slide" → Table (with table_data)
- "chart_slide" → Chart (with chart_data)

=========================================================
🎯 **MANDATORY PRESENTATION STRUCTURE**

```
1. Title Slide (layout_type="title")
2-3. Agenda Slides (layout_hint="agenda", max 5 items each)
4. Section: Introduction/Overview
5-6. Content slides (bullets/paragraph)
7. Section: Objectives
8. Content slide (4 bullets)
9. Section: Approach/Methodology
10. Content slide (4 bullets)
11. Four-box slide (framework - EXACTLY 4 items)
12. Section: Timeline
13. Chart slide (timeline with actual data)
14. Section: Team/Resources
15. Table slide (team structure with actual data)
16. Content slide (bullets)
17. Section: Deliverables
18. Chart slide (budget/distribution with actual data)
19. Section: Success Metrics
20. Chart slide (KPIs with actual data)
21. Section: Benefits
22. Four-box slide (benefits - EXACTLY 4 items)
23. Section: Thank You (ALWAYS INCLUDE)
```

=========================================================
🎯 **CONTENT FIELD RULES**

**For Bullet Slides:**
```json
{{
  "layout_type": "content",
  "layout_hint": "title_and_content",
  "title": "Key Points",
  "bullets": [
    {{"text": "First point", "sub_bullets": []}},
    {{"text": "Second point", "sub_bullets": []}},
    {{"text": "Third point", "sub_bullets": []}}
  ],
  "content": null,
  "chart_data": null,
  "table_data": null
}}
```

**For Paragraph Slides:**
```json
{{
  "layout_type": "content",
  "layout_hint": "content_paragraph",
  "title": "Overview",
  "content": "Full paragraph text here. This should be 2-3 sentences describing the topic in detail.",
  "bullets": null,
  "chart_data": null,
  "table_data": null
}}
```

**For Chart Slides:**
```json
{{
  "layout_type": "content",
  "layout_hint": "chart_slide",
  "title": "Timeline",
  "bullets": null,
  "content": null,
  "chart_data": {{...}} // MUST be complete
}}
```

**For Table Slides:**
```json
{{
  "layout_type": "content",
  "layout_hint": "table_slide",
  "title": "Team",
  "bullets": null,
  "content": null,
  "table_data": {{...}} // MUST be complete
}}
```

=========================================================
🎯 **VALIDATION CHECKLIST (VERIFY BEFORE OUTPUT)**

Before generating JSON, verify:
1. ✓ Every section header has 1-3 content slides after it
2. ✓ No slides with only title (all have content/bullets/chart/table)
3. ✓ EXACTLY 3+ chart slides with complete chart_data
4. ✓ EXACTLY 2+ four-box slides with 4 bullets each
5. ✓ EXACTLY 1+ table slide with complete table_data
6. ✓ All titles under length limits
7. ✓ All chart categories and values arrays are non-empty
8. ✓ All table headers and rows arrays are non-empty
9. ✓ Thank You slide is LAST slide
10. ✓ No null values in required fields

=========================================================

Generate complete PresentationData JSON following ALL rules above.

LANGUAGE: {language}
TEMPLATE: {template_id}
"""


def get_user_prompt(markdown_content: str, language: str, user_preference: str = '') -> str:
    """Enhanced user prompt with strict requirements"""

    alignment_note = "LEFT-aligned" if language != 'Arabic' else "RIGHT-aligned"

    return f"""
Convert the following content into a PresentationData JSON structure.

INPUT CONTENT:
{markdown_content}

USER PREFERENCES:
{user_preference if user_preference else 'None'}

=========================================================
🎯 **MANDATORY REQUIREMENTS**

1. **Structure:**
   - Title slide
   - 1-2 Agenda slides (max 5 items each)
   - 15-20 content slides organized by sections
   - Each section header MUST have 1-3 content slides after it
   - Final "Thank You" section header (MANDATORY)

2. **Visual Content (ABSOLUTELY REQUIRED):**
   - **MINIMUM 3 chart slides** with complete chart_data:
     * 1 timeline chart (column chart with phases)
     * 1 budget/distribution chart (pie chart)
     * 1 metrics/KPIs chart (bar chart)
   - **MINIMUM 2 four-box slides**:
     * 1 methodology/framework (4 pillars)
     * 1 benefits/value proposition (4 points)
   - **MINIMUM 1 table slide**:
     * Deliverables OR team structure OR schedule

3. **Content Distribution:**
   - Use bullets for lists (max 4 per slide)
   - Use paragraphs for descriptions/overviews
   - ALWAYS populate either bullets OR content OR chart_data OR table_data
   - NEVER leave slides with only titles

4. **Title Constraints:**
   - Max 60 chars (title slide)
   - Max 50 chars (section headers)
   - Max 70 chars (content slides)

=========================================================
🎯 **WHERE TO INSERT VISUAL CONTENT**

**Timeline Section → CHART:**
```json
{{
  "layout_type": "content",
  "layout_hint": "chart_slide",
  "title": "Project Timeline",
  "chart_data": {{
    "chart_type": "column",
    "categories": ["Phase 1", "Phase 2", "Phase 3"],
    "series": [{{"name": "Duration", "values": [4.0, 8.0, 6.0]}}],
    "x_axis_label": "Phases",
    "y_axis_label": "Weeks",
    "unit": "Weeks"
  }}
}}
```

**Budget/Cost Section → CHART:**
```json
{{
  "layout_type": "content",
  "layout_hint": "chart_slide",
  "title": "Budget Distribution",
  "chart_data": {{
    "chart_type": "pie",
    "categories": ["Research", "Strategy", "Implementation", "Support"],
    "series": [{{"name": "Cost", "values": [25.0, 35.0, 30.0, 10.0]}}],
    "unit": "%"
  }}
}}
```

**Metrics/KPIs Section → CHART:**
```json
{{
  "layout_type": "content",
  "layout_hint": "chart_slide",
  "title": "Success Metrics",
  "chart_data": {{
    "chart_type": "bar",
    "categories": ["Quality", "Timeliness", "Accuracy", "Engagement"],
    "series": [{{"name": "Score", "values": [95.0, 92.0, 98.0, 94.0]}}],
    "unit": "%"
  }}
}}
```

**Team/Deliverables Section → TABLE:**
```json
{{
  "layout_type": "content",
  "layout_hint": "table_slide",
  "title": "Team Structure",
  "table_data": {{
    "headers": ["Role", "Responsibility", "Experience"],
    "rows": [
      ["Project Lead", "Overall delivery", "15+ years"],
      ["Strategy Lead", "Framework design", "12+ years"],
      ["Analyst", "Data analysis", "8+ years"]
    ]
  }}
}}
```

**Methodology Section → FOUR-BOX:**
```json
{{
  "layout_type": "content",
  "layout_hint": "four_box_with_icons",
  "title": "Our Approach",
  "bullets": [
    {{"text": "Research & Discovery", "sub_bullets": []}},
    {{"text": "Strategy Design", "sub_bullets": []}},
    {{"text": "Implementation", "sub_bullets": []}},
    {{"text": "Monitoring & Optimization", "sub_bullets": []}}
  ]
}}
```

=========================================================
🎯 **VALIDATION BEFORE OUTPUT**

Check:
- [ ] 3+ chart slides with complete data
- [ ] 2+ four-box slides with exactly 4 bullets
- [ ] 1+ table slide with complete data
- [ ] Every section has content after it
- [ ] No blank slides (title only)
- [ ] Thank You slide at end
- [ ] All text is {alignment_note}

=========================================================

Generate the complete PresentationData JSON now.
"""


def get_regeneration_prompt(
    markdown_content: str,
    language: str,
    regen_comments: list,
    user_preference: str = ''
) -> str:
    """Enhanced regeneration prompt"""
    comments_text = '\n'.join([
        f'- {c["comment1"]}: {c["comment2"]}'
        for c in regen_comments
    ])
    
    return f"""Regenerate this presentation in {language} addressing feedback:

ORIGINAL CONTENT:
{markdown_content}

USER FEEDBACK:
{comments_text}

USER PREFERENCES:
{user_preference if user_preference else 'None'}

REQUIREMENTS:
1. Address ALL feedback
2. Include minimum 3 charts with complete data
3. Include minimum 2 four-box layouts with exactly 4 items
4. Include minimum 1 table with complete data
5. Every section must have content after it
6. No blank slides
7. Thank You slide at end

Generate complete regenerated PresentationData in {language}."""