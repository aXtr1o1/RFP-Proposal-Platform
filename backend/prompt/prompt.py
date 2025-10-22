from typing import Dict, Any, List, Tuple

def build_dynamic_json_schema(layout_details: Dict[int, Dict]) -> Tuple[Dict[str, Any], List[Tuple[str, int, str]]]:
    """
    Build JSON schema and available layouts from template analysis.
    
    Args:
        layout_details: Dict of layout placeholder information
        
    Returns:
        Tuple of (schema_dict, available_layouts_list)
        - schema_dict: JSON schema for slide structure
        - available_layouts: List of (layout_type, layout_index, layout_name)
    """
    if not layout_details:
        schema = {
            "type": "object",
            "properties": {
                "layout_type": {
                    "type": "string",
                    "enum": ["TITLE_ONLY", "SINGLE_CONTENT", "TWO_CONTENT", "MULTI_CONTENT", "CHART"]
                },
                "layout_index": {"type": "integer"},
                "title": {"type": "string"},
                "content": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "string"}}
                },
                "chart": {"type": "object"}
            },
            "required": ["layout_type", "layout_index", "title"],
        }
        
        default_layouts = [
            ("TITLE_ONLY", 0, "Title Slide"),
            ("SINGLE_CONTENT", 1, "Title and Content"),
            ("TWO_CONTENT", 3, "Two Content")
        ]
        
        return schema, default_layouts
    
    avail = []
    for idx, det in layout_details.items():
        has_title = det["title_idx"] is not None
        n = len(det["content_indices"])
        
        if has_title and n == 0:
            avail.append(("TITLE_ONLY", idx, det["name"]))
        elif has_title and n == 1:
            avail.append(("SINGLE_CONTENT", idx, det["name"]))
        elif has_title and n == 2:
            avail.append(("TWO_CONTENT", idx, det["name"]))
        elif has_title and n >= 3:
            avail.append(("MULTI_CONTENT", idx, det["name"]))
        elif not has_title and n == 0:
            avail.append(("BLANK", idx, det["name"]))
    
    layout_types = [t for t, _, _ in avail if t != "BLANK"] or ["SINGLE_CONTENT"]
    layout_types.append("CHART")
    
    schema = {
        "type": "object",
        "properties": {
            "layout_type": {"type": "string", "enum": layout_types},
            "layout_index": {"type": "integer"},
            "title": {"type": "string"},
            "content": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "string"}}
            },
            "chart": {"type": "object"}
        },
        "required": ["layout_type", "layout_index", "title"],
    }
    
    return schema, avail


def build_system_prompt(language: str, template_analysis: str, layout_details: Dict[int, Dict]) -> str:
    lang = (language or "english").lower().strip()
    lang_instruction = (
        "LANGUAGE_MODE: ENGLISH\nTOP PRIORITY: Output ALL content in English only."
        if lang == "english" else
        "LANGUAGE_MODE: ARABIC (Modern Standard Arabic)\nTOP PRIORITY: Output ALL content in Arabic only."
    )

    schema, available_layouts = build_dynamic_json_schema(layout_details)
    layout_desc = "\n".join([f"- Layout Index {idx}: {name} (type: {lt})" for lt, idx, name in available_layouts])
    def pick(typ: str, default: int) -> int:
        for lt, idx, _ in available_layouts:
            if lt == typ:
                return idx
        return default
    
    schema_example = f"""
AVAILABLE LAYOUTS IN YOUR TEMPLATE:
{layout_desc}

OUTPUT FORMAT - JSON ARRAY OF SLIDES (STRICT):
Each slide object MUST have:
{{
  "layout_type": "TITLE_ONLY" | "SINGLE_CONTENT" | "TWO_CONTENT" | "MULTI_CONTENT" | "CHART",
  "layout_index": <integer>,
  "title": "<string>",
  "content": [
    ["bullet 1", "bullet 2", "bullet 3"],
    ["bullet 1", "bullet 2"]
  ],
  "chart": {{
    "chart_type": "bar" | "line" | "pie" | "scatter" | "column",
    "title": "Chart Title",
    "data": {{
      "labels": ["Q1", "Q2", "Q3", "Q4"],
      "values": [100, 150, 120, 180]
    }},
    "x_label": "Optional X Label",
    "y_label": "Optional Y Label"
  }}
}}

CHART DATA SPECIFICATION EXAMPLES:

1. BAR CHART (Single Series):
{{
  "chart_type": "bar",
  "title": "Budget Allocation by Category",
  "data": {{
    "labels": ["Personnel", "Equipment", "Training", "Operations"],
    "values": [450000, 200000, 150000, 100000]
  }},
  "x_label": "Categories",
  "y_label": "Amount (USD)"
}}

2. BAR CHART (Multiple Series):
{{
  "chart_type": "bar",
  "title": "Year-over-Year Comparison",
  "data": {{
    "labels": ["Q1", "Q2", "Q3", "Q4"],
    "series": [
      {{"name": "2023", "values": [100, 120, 140, 160]}},
      {{"name": "2024", "values": [110, 130, 150, 180]}}
    ]
  }},
  "x_label": "Quarter",
  "y_label": "Revenue (K USD)"
}}

3. LINE CHART:
{{
  "chart_type": "line",
  "title": "Project Timeline Progress",
  "data": {{
    "labels": ["Month 1", "Month 2", "Month 3", "Month 4", "Month 5", "Month 6"],
    "values": [15, 30, 50, 70, 85, 100]
  }},
  "x_label": "Timeline",
  "y_label": "Completion Percentage"
}}

4. PIE CHART:
{{
  "chart_type": "pie",
  "title": "Resource Distribution",
  "data": {{
    "labels": ["Development", "Testing", "Deployment", "Support"],
    "values": [40, 25, 20, 15]
  }}
}}

5. COLUMN CHART:
{{
  "chart_type": "column",
  "title": "Monthly Performance Metrics",
  "data": {{
    "labels": ["Jan", "Feb", "Mar", "Apr", "May"],
    "values": [85, 90, 88, 92, 95]
  }},
  "x_label": "Month",
  "y_label": "Performance Score"
}}

CHART GENERATION RULES:
1. Use layout_type: "CHART" for data visualization slides
2. Place 2-3 chart slides in the MIDDLE of the presentation (slides 5-8)
3. For CHART slides, use layout_index {pick("SINGLE_CONTENT", 1)} or BLANK layout if available
4. Generate charts for:
   - Budget breakdown (pie/bar chart)
   - Timeline/milestones (line/bar chart)
   - Resource allocation (column chart)
   - Performance metrics (line chart)
   - Comparison data (grouped bar chart)
5. Extract REAL numerical data from RFP and supporting documents
6. All numeric values must be integers or floats (NOT strings)
7. Labels must be strings in double quotes
8. Use realistic data based on document content
9. Follow the strict JSON format without making error

LAYOUT TYPE GUIDELINES:
- TITLE_ONLY: Use layout index {pick("TITLE_ONLY", 0)} for title slides (no content)
- SINGLE_CONTENT: Use layout index {pick("SINGLE_CONTENT", 1)} for standard slides (1 content area)
- TWO_CONTENT: Use layout index {pick("TWO_CONTENT", 3)} for comparison slides (2 content areas)
- MULTI_CONTENT: Use layout index {pick("MULTI_CONTENT", 4)} for complex slides (3+ content areas)
- CHART: Use layout index {pick("SINGLE_CONTENT", 1)} for chart visualization slides
""".strip()
    
    return f"""{lang_instruction}

You are an expert proposal writer for PowerPoint content with data visualization capabilities.

TEMPLATE LAYOUT INFORMATION:
{template_analysis}

CORE RESPONSIBILITIES:
1. Analyze the RFP/BRD for requirements, evaluation criteria, scope, deliverables, timeline, and NUMERICAL DATA.
2. Extract company details AND metrics from the Supporting document (name, capabilities, credentials, case studies, statistics).
3. Generate concise, impactful slide content aligned to the RFP and grounded in the Supporting document.
4. IDENTIFY opportunities for data visualization and generate 2-3 chart slides with real data from documents.

{schema_example}

CRITICAL JSON FORMATTING RULES:
1. Output ONLY valid JSON array: [{{"layout_type":"...","layout_index":N,"title":"...","content":[...]}},...]
2. NO trailing commas: {{"key":"value",}} ← WRONG | {{"key":"value"}} ← CORRECT
3. NO extra closing braces: }}] ← WRONG | }}] ← CORRECT
4. Each slide object separated by comma: {{...}},{{...}}
5. NO text before [ or after ]
6. NO line breaks in property names or values
7. Use double quotes for ALL strings
8. NO comments in JSON
9. NO markdown code fences (```
10. All numeric values in charts must be numbers, not strings

EXAMPLE OF VALID FORMAT:
[{{"layout_type":"TITLE_ONLY","layout_index":0,"title":"Title"}},{{"layout_type":"SINGLE_CONTENT","layout_index":1,"title":"Content","content":[["Bullet 1","Bullet 2"]]}},{{"layout_type":"CHART","layout_index":1,"title":"Chart Title","chart":{{"chart_type":"bar","title":"Data","data":{{"labels":["A","B"],"values":}}}}}}]

INVALID EXAMPLES TO AVOID:
❌ [...}},{{...}}]  (Extra closing brace)
❌ [...}},]         (Trailing comma before ])
❌ {{key:value}}    (Missing quotes around key)
❌ {{"values":["1","2"]}}  (Numbers as strings)

VALID:
✓ [...}},{{...}}]
✓ [...}}]
✓ {{"key":"value"}}
✓ {{"values":}}[1]

CRITICAL CONTENT RULES:
1. Use real information from the documents (no placeholders like "TBD", "XXX", "Lorem ipsum")
2. Bullets must be concise (10-15 words maximum)
3. Use correct layout_index values for each slide
4. The length of "content" array must match the number of content placeholders in that layout
5. For CHART slides, DO NOT include "content" field - only "chart" field
6. Extract real numerical data from documents for charts - DO NOT use placeholder values
""".strip()


def build_task_prompt(user_preference: str, layout_details: Dict[int, Dict]) -> str:
    user_pref = f"\n\nUSER PREFERENCES:\n{user_preference}\n\nIncorporate these throughout the presentation." if user_preference else ""
    if layout_details:
        available_types = set()
        for _, det in layout_details.items():
            n = len(det["content_indices"])
            if det["title_idx"] is not None and n == 0:
                available_types.add("TITLE_ONLY")
            elif det["title_idx"] is not None and n == 1:
                available_types.add("SINGLE_CONTENT")
            elif det["title_idx"] is not None and n == 2:
                available_types.add("TWO_CONTENT")
            elif det["title_idx"] is not None and n >= 3:
                available_types.add("MULTI_CONTENT")
        
        available_types.add("CHART")
        
        slide_guidance = f"""
Your template supports: {', '.join(sorted(available_types))}.
Generate 10-14 slides using appropriate layout_type and layout_index:
- Slide 1: TITLE_ONLY (project title)
- Slides 2-4: SINGLE_CONTENT or TWO_CONTENT (introduction, objectives, approach)
- Slides 5-7: Include 2-3 CHART slides (budget, timeline, resources)
- Slides 8-12: SINGLE_CONTENT or TWO_CONTENT (methodology, team, deliverables)
- Last slide: SINGLE_CONTENT (conclusion, contact information)
""".strip()
    else:
        slide_guidance = """
Generate 10-14 slides:
- Slide 1: TITLE_ONLY
- Slides 2-4: Introduction slides
- Slides 5-7: Include 2-3 CHART slides with data visualization
- Remaining: Mix of content slides
- Last slide: Conclusion
""".strip()
    
    return f"""
TASK: Generate a complete proposal deck in JSON format (array of slides) WITH DATA VISUALIZATIONS.

INSTRUCTIONS:
1. From the RFP document: extract project title, objectives, requirements, scoring criteria, scope, timeline, budget figures, and ANY NUMERICAL DATA
2. From the Supporting document: extract company name, capabilities, team size, past project metrics, certifications, case studies with numbers, and STATISTICAL DATA
3. {slide_guidance}
4. Map RFP requirements to company strengths with specific examples and data points
5. CRITICAL: Generate 2-3 chart slides with real data extracted from documents:
   - Budget allocation/breakdown (use actual budget figures from RFP)
   - Project timeline/phases (use actual timeline from RFP)
   - Resource distribution (use team size/resources from supporting doc)
   - Performance metrics (use past project statistics from supporting doc)
   - Capability comparisons (use certifications/experience data)

CHART PLACEMENT STRATEGY:
- Place charts strategically in the MIDDLE of the presentation (after introduction, before detailed methodology)
- Each chart must visualize actual data extracted from RFP or supporting documents
- Use appropriate chart types:
  * Bar charts for comparisons and budgets
  * Line charts for timelines and progress
  * Pie charts for distributions and percentages
  * Column charts for performance metrics

DATA EXTRACTION GUIDELINES:
- Look for budget amounts, percentages, durations, team sizes, success rates
- Convert text descriptions to numerical data where possible
- Use realistic estimates based on context if exact numbers not available
- Ensure all chart values are actual numbers (not strings)

CRITICAL OUTPUT REQUIREMENTS:
- Output ONLY a JSON array (no prose, markdown, or explanations)
- Each slide must include: layout_type, layout_index, title
- Content slides must include: content array matching placeholder count
- Chart slides must include: chart object with complete specification
- NO trailing commas anywhere in the JSON
- NO extra closing braces
- ALL strings in double quotes
- ALL numeric values as numbers (not quoted strings)
{user_pref}

Begin generating the JSON array now. Start with [ and end with ]. No other text.
""".strip()
