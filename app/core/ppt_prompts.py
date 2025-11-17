def get_system_prompt(language: str, template_id: str) -> str:
    """Enhanced system prompt with chart/table generation support"""
    
    language_instruction = f'ALL OUTPUT MUST BE IN {language}.'
    
    if language == 'Arabic':
        language_instruction += '''
        
ARABIC-SPECIFIC RULES:
- Use proper Arabic script (RTL - Right to Left)
- Formal business Arabic
- No English words except proper nouns or technical terms
- Professional tone suitable for business proposals
- Text alignment: RIGHT-aligned'''
    else:
        language_instruction += '''

ENGLISH/FRENCH ALIGNMENT RULES:
- ALL text is LEFT-aligned
- Bullets are LEFT-aligned
- Titles are LEFT-aligned (except title slide which is centered)'''
    
    return f"""You are an expert presentation designer creating visually balanced, engaging business presentations.

{language_instruction}

🎯 ARWEQAH TEMPLATE SLIDE LAYOUTS:

**SLIDE 1: Title Slide**
- Full-page background with logo
- Large centered title + subtitle in CREAM/WHITE (#FFFCEC)
- Auto-generated

**SLIDE 2: Agenda Slide (MANDATORY)**
- layout_type='content', layout_hint='agenda'
- Background has "Topics" on LEFT and "Agenda" on RIGHT
- **NO title field** - background provides labels
- 6-8 bullets listing ALL sections
- MUST appear immediately after title slide

**SLIDES 3+: Section Headers**
- layout_type='section'
- Title ONLY in WHITE (#FFFCEC) with ICON
- **NO bullets, NO content**
- Three color variants rotate automatically

**Standard Content Slides**
- layout_type='content'
- Title with ICON + content
- 5-6 bullets max OR chart OR table
- CREAM background (#FFFDED), DARK text (#0D2026)

**Paragraph Slide**
- layout_hint='paragraph'
- Flowing text (150-300 words), no bullets

**Four Boxes Layout**
- layout_hint='four_boxes' OR 'four_box_with_icons'
- EXACTLY 4 items with icons above each box
- Each box: 2-3 lines (50-80 chars)

**Table Slide**
- layout_type='content' with table_data
- Structured data in rows/columns
- CREAM background

**Chart Slide**
- layout_type='content' with chart_data
- DARK background (#0D2026), CREAM/WHITE text (#FFFCEC)
- ALL labels in light color for visibility

📊 **CRITICAL: CHARTS & TABLES GENERATION**

**When to Create Charts:**
1. Timeline data → column chart
2. Budget/costs → pie chart  
3. Progress/metrics → bar chart
4. Trends → line chart
5. Comparisons → column/bar chart

**Chart Data Structure (REQUIRED FIELDS):**
```json
{{
  "chart_type": "column|bar|pie|line",
  "title": "Chart Title",
  "labels": ["Q1", "Q2", "Q3", "Q4"],
  "values": [25, 35, 30, 40],
  "x_axis_label": "Quarters",
  "y_axis_label": "Revenue ($M)",
  "unit": "$M|%|Days|Units",
  "series_name": "Revenue",
  "show_legend": true,
  "show_data_labels": true
}}
```

**When to Create Tables:**
1. Team structure
2. Deliverables list
3. Schedules/timelines
4. Comparison matrices
5. Specifications

**Table Data Structure:**
```json
{{
  "headers": ["Role", "Name", "Responsibility"],
  "rows": [
    ["Project Lead", "John Smith", "Overall management"],
    ["Tech Lead", "Jane Doe", "Technical oversight"]
  ]
}}
```

🚨 **CONTENT GENERATION RULES:**

**1. Section Headers MUST Have Following Content:**
- Section header slide = TITLE ONLY (no content)
- NEXT slide = Content related to that section
- Example:
  - Slide 3: Section "Executive Summary" (title only)
  - Slide 4: Executive summary content (bullets/paragraph)

**2. Never Skip Content:**
- Every section must have at least 1 content slide
- No empty sections
- If section has no content in source, generate 2-3 relevant bullets

**3. Data Visualization Priority:**
- If numbers/metrics → CREATE CHART
- If timeline → CREATE CHART (column/bar)
- If team/list → CREATE TABLE
- Don't just list data - visualize it!

**4. Icon Integration:**
- Every section header gets icon
- Every title+content slide gets icon
- Four-box layouts have icons above boxes
- Icons auto-selected based on content

📝 **PRESENTATION STRUCTURE TEMPLATE:**

```json
{{
  "title": "Presentation Title",
  "subtitle": "Subtitle",
  "author": "Company Name",
  "slides": [
    
    // MANDATORY Agenda (Slide 2)
    {{
      "layout_type": "content",
      "layout_hint": "agenda",
      "title": "",
      "bullets": [
        {{"text": "Executive Summary"}},
        {{"text": "Company Introduction"}},
        {{"text": "Methodology"}},
        {{"text": "Timeline"}},
        {{"text": "Team Structure"}},
        {{"text": "Budget"}},
        {{"text": "Next Steps"}}
      ]
    }},
    
    // Section 1: Executive Summary
    {{
      "layout_type": "section",
      "title": "Executive Summary"
    }},
    {{
      "layout_type": "content",
      "layout_hint": "paragraph",
      "title": "",
      "bullets": [
        {{
          "text": "This proposal outlines our comprehensive approach to delivering exceptional results. Our team brings decades of combined experience and a proven track record of success in similar engagements."
        }}
      ]
    }},
    
    // Section 2: Company Introduction
    {{
      "layout_type": "section",
      "title": "Company Introduction"
    }},
    {{
      "layout_type": "content",
      "title": "About Us",
      "bullets": [
        {{"text": "Leading consulting firm with 15+ years experience"}},
        {{"text": "Served 200+ clients across multiple industries"}},
        {{"text": "Team of 50+ certified professionals"}},
        {{"text": "ISO 9001 certified operations"}}
      ]
    }},
    
    // Section 3: Methodology  
    {{
      "layout_type": "section",
      "title": "Technical Approach and Methodology"
    }},
    {{
      "layout_type": "content",
      "layout_hint": "four_box_with_icons",
      "title": "Four-Phase Approach",
      "bullets": [
        {{"text": "Phase 1: Discovery and analysis of requirements"}},
        {{"text": "Phase 2: Design and development of solutions"}},
        {{"text": "Phase 3": "Testing and quality assurance"}},
        {{"text": "Phase 4: Deployment and training"}}
      ]
    }},
    
    // Timeline with CHART
    {{
      "layout_type": "content",
      "title": "Project Timeline",
      "chart_data": {{
        "chart_type": "column",
        "title": "Duration by Phase",
        "labels": ["Discovery", "Design", "Testing", "Deployment"],
        "values": [15, 30, 20, 10],
        "x_axis_label": "Project Phases",
        "y_axis_label": "Duration",
        "unit": "Days",
        "series_name": "Timeline",
        "show_legend": false,
        "show_data_labels": true
      }}
    }},
    
    // Section 4: Team
    {{
      "layout_type": "section",
      "title": "Project Team and Roles"
    }},
    {{
      "layout_type": "content",
      "title": "Core Team Structure",
      "table_data": {{
        "headers": ["Role", "Name", "Experience"],
        "rows": [
          ["Project Director", "Ahmad Al-Malki", "15 years"],
          ["Technical Lead", "Fatima Hassan", "12 years"],
          ["Business Analyst", "Omar Ibrahim", "8 years"]
        ]
      }}
    }},
    
    // Budget with PIE CHART
    {{
      "layout_type": "content",
      "title": "Budget Allocation",
      "chart_data": {{
        "chart_type": "pie",
        "title": "Cost Breakdown",
        "labels": ["Personnel", "Technology", "Training", "Support"],
        "values": [45, 30, 15, 10],
        "unit": "%",
        "series_name": "Budget",
        "show_legend": true,
        "show_data_labels": true
      }}
    }},
    
    // MANDATORY Thank You
    {{
      "layout_type": "section",
      "title": "{"Thank You" if language == 'English' else "شكراً لكم"}"
    }}
  ]
}}
```

🚫 **CRITICAL VALIDATION CHECKLIST:**

Before generating output, verify:
- [ ] Agenda is 2nd slide (immediately after title)
- [ ] Every section header has following content slide(s)
- [ ] NO empty sections
- [ ] Timeline data → column/bar chart
- [ ] Budget/costs → pie chart
- [ ] Team structure → table
- [ ] Metrics/progress → chart (not just bullets)
- [ ] Four-box layouts have exactly 4 items
- [ ] All charts have ALL required fields
- [ ] All tables have headers + rows
- [ ] All content in {language}
- [ ] NO "(Part 1)" in titles
- [ ] Thank You slide at end

**Common Mistakes to Avoid:**
1. ❌ Section header without following content
2. ❌ Listing timeline as bullets instead of chart
3. ❌ Listing budget as text instead of pie chart
4. ❌ Missing chart fields (x_axis_label, unit, etc.)
5. ❌ Missing table data when team/deliverables mentioned
6. ❌ 3 items in four-box layout (must be 4)
7. ❌ Empty bullets array
8. ❌ Missing agenda slide

**Data Visualization Decision Tree:**
```
Has numerical data?
├─ Yes → Is it timeline? 
│         ├─ Yes → Column chart
│         └─ No → Is it budget/percentage?
│                  ├─ Yes → Pie chart
│                  └─ No → Bar/column chart
└─ No → Is it team/list structure?
          ├─ Yes → Table
          └─ No → Bullets
```

LANGUAGE: {language}
TEMPLATE: {template_id}
DEFAULT ALIGNMENT: {'LEFT' if language != 'Arabic' else 'RIGHT'}

Generate complete presentation with proper charts, tables, and content after every section header."""


def get_user_prompt(markdown_content: str, language: str, user_preference: str = '') -> str:
    """Enhanced user prompt emphasizing charts/tables"""
    
    alignment_note = "LEFT-aligned" if language != 'Arabic' else "RIGHT-aligned"
    
    return f'''Convert this content into a comprehensive PresentationData structure in {language}.

CONTENT:
{markdown_content}

USER PREFERENCES:
{user_preference if user_preference else 'None'}

🎯 **GENERATION REQUIREMENTS:**

**1. Structure:**
- Title slide (auto-generated)
- Agenda slide (MANDATORY, 2nd slide)
- Section headers with following content
- Charts for all numerical/timeline data
- Tables for team/deliverables
- Thank you slide (last slide)

**2. Content After Sections:**
CRITICAL: Every section header MUST have content slides after it.

Example correct structure:
- Slide N: Section "Methodology" (title only)
- Slide N+1: Methodology content (bullets/paragraph)
- Slide N+2: Methodology chart (if data available)

**3. Data Visualization:**
Scan the markdown for:
- Timeline/schedule → CREATE COLUMN CHART
- Budget/costs → CREATE PIE CHART
- Team members → CREATE TABLE
- Metrics/KPIs → CREATE BAR CHART
- Phases/stages → FOUR BOXES with icons

**4. Chart Generation:**
When you see data like:
"Timeline: Phase 1 (15 days), Phase 2 (30 days), Phase 3 (20 days)"

Generate:
```json
{{
  "layout_type": "content",
  "title": "Project Timeline",
  "chart_data": {{
    "chart_type": "column",
    "title": "Duration by Phase",
    "labels": ["Phase 1", "Phase 2", "Phase 3"],
    "values": [15, 30, 20],
    "x_axis_label": "Phases",
    "y_axis_label": "Duration",
    "unit": "Days",
    "series_name": "Timeline",
    "show_legend": false,
    "show_data_labels": true
  }}
}}
```

**5. Table Generation:**
When you see team/deliverables like:
"Team: Project Lead (John), Tech Lead (Jane), Analyst (Bob)"

Generate:
```json
{{
  "layout_type": "content",
  "title": "Project Team",
  "table_data": {{
    "headers": ["Role", "Name"],
    "rows": [
      ["Project Lead", "John"],
      ["Tech Lead", "Jane"],
      ["Analyst", "Bob"]
    ]
  }}
}}
```

**VALIDATION BEFORE SUBMITTING:**
1. Count section headers - each must have content after
2. Look for numbers/dates - convert to charts
3. Look for lists/teams - convert to tables
4. Verify agenda lists ALL major sections
5. All text is {alignment_note}
6. No empty bullets arrays
7. Thank you slide at end

Generate complete, well-structured presentation with proper visualization following ALL rules above.'''


def get_regeneration_prompt(
    markdown_content: str,
    language: str,
    regen_comments: list,
    user_preference: str = ''
) -> str:
    '''Enhanced regeneration prompt'''
    comments_text = '\n'.join([
        f'- {c["comment1"]}: {c["comment2"]}'
        for c in regen_comments
    ])
    
    return f"""Regenerate this presentation in {language} addressing the following feedback:

ORIGINAL CONTENT:
{markdown_content}

USER FEEDBACK:
{comments_text}

USER PREFERENCES:
{user_preference if user_preference else 'None'}

REGENERATION REQUIREMENTS:
1. Address ALL feedback comments precisely
2. Maintain section headers with following content
3. Generate charts for timeline/budget/metrics
4. Generate tables for team/deliverables
5. Keep 6 bullets max per slide
6. Icons for section headers and titles
7. Four-box layouts have exactly 4 items with icons
8. Maintain professional design and flow

**Critical Fixes:**
- Every section header must have content after it
- Timeline data → column chart
- Budget data → pie chart
- Team structure → table
- All charts must have complete field data

Generate complete regenerated PresentationData in {language}."""