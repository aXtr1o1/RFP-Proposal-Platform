def get_system_prompt(language: str, template_id: str) -> str:
    """
    Get system prompt for presentation generation
    
    Args:
        language: "English" or "Arabic"
        template_id: Template identifier (e.g., "standard")
        
    Returns:
        str: System prompt
    """
    language_instruction = f"ALL OUTPUT MUST BE IN {language.upper()}."
    
    if language == "Arabic":
        language_instruction += """
        
ARABIC-SPECIFIC RULES:
- Use proper Arabic script (RTL)
- Formal business Arabic
- No English words except proper nouns or technical terms
- Professional tone suitable for business proposals"""
    
    return f"""You are an expert presentation designer creating visually balanced, engaging business presentations.

{language_instruction}

CRITICAL DESIGN MANDATE:
- BALANCED visual content: Mix of bullets, LIMITED tables, and charts
- ONE MAIN TOPIC per slide (no cramming multiple sections together)
- 3 MAIN POINTS maximum per slide for readability
- Each main section (Goals, Scope, Approach) gets its OWN slide

VISUAL FORMAT LIMITS (STRICTLY ENFORCE):
- TABLES: Maximum 3-4 in entire presentation (only for truly essential structured data)
- CHARTS: Maximum 5-6 in entire presentation (for timelines, metrics, budgets)
- BULLETS: Primary format for most content
- IMAGES: 40-50% of content slides should have images

TABLE USAGE (VERY SELECTIVE - MAX 4 TOTAL):
Use tables ONLY for:
1. Project team/roles (if 5+ people with detailed responsibilities)
2. Detailed deliverables with multiple attributes
3. Complex risk/quality matrices
4. Budget breakdown with multiple line items

NEVER use tables for simple lists - use bullets instead.

CHART USAGE (MAX 6 TOTAL):
Use charts for:
1. Project timeline/phases → column chart
2. Budget distribution → pie chart
3. KPI metrics/targets → bar chart
4. Progress tracking → line chart
5. Comparative data → grouped bar chart

CONTENT DISTRIBUTION RULES:
1. **Separate slides for each main heading**
2. **3 main points maximum per slide** with 2-3 sub-bullets each
3. **Sub-headings get their own slides**

STRUCTURE REQUIREMENTS:
1. Title slide
2. Executive Summary section + 1-2 overview slides WITH IMAGES
3. Company Introduction section + 1 slide WITH IMAGE
4. Content sections with clear focus
5. Each major heading on separate slide

BULLET FORMAT (PRIMARY):
- Main point: Clear, concise statement
  ○ Sub-point 1: Supporting detail
  ○ Sub-point 2: Supporting detail
  ○ Sub-point 3: Supporting detail

TEXT RULES:
- No markdown (**, *, #, \\)
- Titles ≤ 45 chars, descriptive and specific
- Never "(continued)" or "(1/2)"
- Bullet points: ≤ 90 chars main, ≤ 70 chars sub-bullets
- Professional, scannable content

IMAGE POLICY (GENEROUS):
- needs_image=true for 40-50% of content slides
- Prioritize: Overview, Introduction, Methodology, Approach, Vision slides
- Also add images to: Objectives, Strategy, Capabilities, Success factors
- NO images for: Tables, Charts, Data-heavy slides

ICON USAGE:
Every content slide should have an appropriate icon.

VALID ICONS: briefcase, package, steps, rocket-launch, users-three, bullseye, calendar-check, 
currency-dollar, file-text, certificate, graduation-cap, gear, shield-check, trophy, 
chart-pie-slice, target, brain, lightbulb, check-circle, eye, map-trifold, hand-waving, 
trend-up, network, flow-arrow, circle

REMEMBER:
- ALL content in {language}
- Preserve ALL content but format appropriately
- Quality over quantity
- Template: {template_id}"""


def get_user_prompt(markdown_content: str, language: str, user_preference: str = "") -> str:
    """
    Get user prompt with content and preferences
    
    Args:
        markdown_content: Source markdown
        language: Target language
        user_preference: User preferences
        
    Returns:
        str: User prompt
    """
    return f"""Convert this business content into a BALANCED PresentationData structure in {language}.

CONTENT:
{markdown_content}

USER PREFERENCES:
{user_preference if user_preference else "None"}

CRITICAL OUTPUT REQUIREMENTS:

1. CONTENT DISTRIBUTION:
   - **Separate main sections**: Goals, Scope, Approach each get their own slide
   - **3 points maximum** per slide with 2-3 sub-bullets each
   - **Add images** to 40-50% of content slides

2. FORMAT PRIORITY:
   A. BULLETS (PRIMARY - 70%): Use for most content
   B. CHARTS (SELECTIVE - 5-6 max): For numerical data only
   C. TABLES (VERY LIMITED - 3-4 max): For complex structured data only

3. ALL CONTENT MUST BE IN {language}

4. INCLUDE COMPLETE PRESENTATION STRUCTURE:
   - Title and subtitle
   - All slides with proper layout_type
   - Bullets with main text and sub_bullets
   - Charts with chart_type, title, labels, values
   - Tables with headers and rows
   - Icon names for each slide
   - needs_image=true for appropriate slides

OUTPUT:
Generate complete PresentationData in {language} following all rules above."""


def get_regeneration_prompt(
    markdown_content: str,
    language: str,
    regen_comments: list,
    user_preference: str = ""
) -> str:
    """
    Get user prompt for regeneration with feedback
    
    Args:
        markdown_content: Source markdown
        language: Target language
        regen_comments: List of feedback comments
        user_preference: User preferences
        
    Returns:
        str: User prompt for regeneration
    """
    comments_text = "\n".join([
        f"- {c['comment1']}: {c['comment2']}"
        for c in regen_comments
    ])
    
    return f"""Regenerate this presentation in {language} addressing the following feedback:

ORIGINAL CONTENT:
{markdown_content}

USER FEEDBACK:
{comments_text}

USER PREFERENCES:
{user_preference if user_preference else "None"}

REQUIREMENTS:
1. Address ALL feedback comments
2. Maintain overall structure and quality
3. Keep 3 points max per slide
4. Generate in {language}
5. Include charts, tables, icons, and images as appropriate
6. Follow all design rules from system prompt

OUTPUT:
Complete regenerated PresentationData in {language} with improvements based on feedback."""
