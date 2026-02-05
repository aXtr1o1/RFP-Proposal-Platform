#!/usr/bin/env python3
"""
Standalone PPT Previewer
Generates a sample presentation with all slide types for template preview
"""

import sys
import os
from pathlib import Path
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Now import from apps
from apps.app.models.presentation import (
    PresentationData, 
    SlideContent, 
    BulletPoint, 
    ChartData, 
    ChartSeries,
    TableData
)
from apps.app.services.pptx_generator import PptxGenerator
from apps.app.config import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("previewer")


def create_sample_presentation(template_id: str = "standard", language: str = "English") -> PresentationData:
    """Create a sample presentation with all slide types"""
    
    slides = []
    
    # 1. Title Slide
    slides.append(SlideContent(
        layout_type="title",
        title="Template Preview Presentation",
        content="This is a preview of all available slide layouts"
    ))
    
    # 2. Agenda Slide
    slides.append(SlideContent(
        layout_type="content",
        layout_hint="agenda",
        title="Agenda",
        bullets=[
            BulletPoint(text="Introduction and Overview"),
            BulletPoint(text="Key Objectives and Goals"),
            BulletPoint(text="Methodology and Approach"),
            BulletPoint(text="Timeline and Deliverables"),
            BulletPoint(text="Team and Resources")
        ],
        icon_name="presentation-agenda"
    ))
    
    # 3. Introduction Slide
    slides.append(SlideContent(
        layout_type="content",
        layout_hint="introduction",
        title="Introduction",
        content="This is an introduction slide with paragraph text. It demonstrates how longer form content is displayed in the presentation template.",
        icon_name="introduction-overview"
    ))
    
    # 4. Section Header
    slides.append(SlideContent(
        layout_type="section",
        title="Section One: Overview",
        icon_name="target-goals"
    ))
    
    # 5. Content Slide with Bullets
    slides.append(SlideContent(
        layout_type="content",
        title="Key Features",
        bullets=[
            BulletPoint(text="Feature one with detailed description"),
            BulletPoint(text="Feature two with supporting information"),
            BulletPoint(text="Feature three highlighting benefits"),
            BulletPoint(text="Feature four showcasing capabilities")
        ],
        icon_name="lightbulb"
    ))
    
    # 6. Content Slide with Image
    slides.append(SlideContent(
        layout_type="content",
        title="Visual Content",
        bullets=[
            BulletPoint(text="This slide demonstrates image placement"),
            BulletPoint(text="Images are positioned on the right side"),
            BulletPoint(text="With proper spacing and alignment")
        ],
        needs_image=True,
        image_layout="right",
        image_caption="Sample Image",
        icon_name="image"
    ))
    
    # 7. Two Column Slide
    slides.append(SlideContent(
        layout_type="two_column",
        title="Comparison View",
        left_content=[
            "Left column item one",
            "Left column item two",
            "Left column item three"
        ],
        right_content=[
            "Right column item one",
            "Right column item two",
            "Right column item three"
        ],
        icon_name="columns"
    ))
    
    # 8. DNA Values Slide
    slides.append(SlideContent(
        layout_type="content",
        layout_hint="dna_values",
        title="Core Values",
        content="Our DNA represents our fundamental principles",
        icon_name="dna"
    ))
    
    # 9. Sectors Grid Slide
    slides.append(SlideContent(
        layout_type="content",
        layout_hint="sectors",
        title="Our Sectors",
        bullets=[
            BulletPoint(text="Sector One"),
            BulletPoint(text="Sector Two"),
            BulletPoint(text="Sector Three"),
            BulletPoint(text="Sector Four"),
            BulletPoint(text="Sector Five"),
            BulletPoint(text="Sector Six")
        ],
        icon_name="grid"
    ))
    
    # 10. Statistics Slide
    slides.append(SlideContent(
        layout_type="content",
        layout_hint="statistics",
        title="Our Achievements",
        bullets=[
            BulletPoint(text="15+ Projects"),
            BulletPoint(text="35+ Consultants"),
            BulletPoint(text="40M+ Project Value"),
            BulletPoint(text="120+ Researchers"),
            BulletPoint(text="4+ Partnerships"),
            BulletPoint(text="6+ Offices")
        ],
        icon_name="chart-bar"
    ))
    
    # 11. Added Value Slide
    slides.append(SlideContent(
        layout_type="two_column",
        layout_hint="added_value",
        title="Added Value",
        bullets=[
            BulletPoint(text="Strategic Alliances"),
            BulletPoint(text="Deep Sector Understanding"),
            BulletPoint(text="Strategy Development Experience"),
            BulletPoint(text="Operational Model Expertise"),
            BulletPoint(text="Expert Team")
        ],
        icon_name="value"
    ))
    
    # 12. Project Detail Slide
    slides.append(SlideContent(
        layout_type="content",
        layout_hint="project_detail",
        title="Project Overview",
        bullets=[
            BulletPoint(text="Project component one"),
            BulletPoint(text="Project component two"),
            BulletPoint(text="Project component three")
        ],
        icon_name="briefcase"
    ))
    
    # 13. Section Header
    slides.append(SlideContent(
        layout_type="section",
        title="Section Two: Data Visualization",
        icon_name="chart-line"
    ))
    
    # 14. Chart Slide - Bar Chart
    slides.append(SlideContent(
        layout_type="content",
        layout_hint="chart_slide",
        title="Performance Metrics",
        chart_data=ChartData(
            chart_type="bar",
            title="Quarterly Performance",
            categories=["Q1", "Q2", "Q3", "Q4"],
            series=[
                ChartSeries(name="Revenue", values=[100, 120, 140, 160]),
                ChartSeries(name="Growth", values=[10, 15, 18, 22])
            ],
            x_axis_label="Quarter",
            y_axis_label="Value",
            unit="%"
        ),
        icon_name="chart-bar"
    ))
    
    # 15. Chart Slide - Pie Chart
    slides.append(SlideContent(
        layout_type="content",
        layout_hint="chart_slide",
        title="Distribution Analysis",
        chart_data=ChartData(
            chart_type="pie",
            title="Resource Allocation",
            categories=["Development", "Design", "Testing", "Support"],
            series=[
                ChartSeries(name="Allocation", values=[40, 25, 20, 15])
            ]
        ),
        icon_name="chart-pie"
    ))
    
    # 16. Section Header
    slides.append(SlideContent(
        layout_type="section",
        title="Section Three: Detailed Information",
        icon_name="file-text"
    ))
    
    # 17. Table Slide
    slides.append(SlideContent(
        layout_type="content",
        layout_hint="table_slide",
        title="Project Timeline",
        table_data=TableData(
            headers=["Phase", "Duration", "Status"],
            rows=[
                ["Phase 1: Planning", "2 weeks", "Completed"],
                ["Phase 2: Development", "4 weeks", "In Progress"],
                ["Phase 3: Testing", "2 weeks", "Pending"],
                ["Phase 4: Deployment", "1 week", "Pending"]
            ]
        ),
        icon_name="table"
    ))
    
    # 18. Four Box Slide
    slides.append(SlideContent(
        layout_type="content",
        layout_hint="four_box_with_icons",
        title="Key Pillars",
        bullets=[
            BulletPoint(text="Pillar One: Innovation"),
            BulletPoint(text="Pillar Two: Excellence"),
            BulletPoint(text="Pillar Three: Collaboration"),
            BulletPoint(text="Pillar Four: Impact")
        ],
        icon_name="boxes"
    ))
    
    # 19. Content Paragraph Slide
    slides.append(SlideContent(
        layout_type="content",
        layout_hint="content_paragraph",
        title="Detailed Description",
        content="This is a paragraph-style slide that demonstrates how longer form text content is displayed. It allows for more detailed explanations and comprehensive information sharing. The text is properly formatted and spaced for optimal readability.",
        icon_name="file-text"
    ))
    
    # 20. Thank You Slide
    slides.append(SlideContent(
        layout_type="section",
        title="Thank You",
        icon_name="hand-waving"
    ))
    
    return PresentationData(
        title="Template Preview",
        subtitle="All Slide Types Demonstration",
        author="Impetus Strategy",
        language=language,
        slides=slides
    )


def main():
    """Main function to generate preview"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate PPT preview with all slide types")
    parser.add_argument(
        "--template",
        type=str,
        default="standard",
        help="Template ID to preview (default: standard)"
    )
    parser.add_argument(
        "--language",
        type=str,
        default="English",
        choices=["English", "Arabic"],
        help="Language for the presentation (default: English)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (default: preview_<template>_<lang>.pptx)"
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the generated file automatically"
    )
    
    args = parser.parse_args()
    
    template_id = args.template
    language = args.language
    
    # Generate output filename
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(f"preview_{template_id}_{language.lower()}.pptx")
    
    logger.info(f"🚀 Starting PPT Preview Generation")
    logger.info(f"   Template: {template_id}")
    logger.info(f"   Language: {language}")
    logger.info(f"   Output: {output_path}")
    
    try:
        # Create sample presentation
        logger.info("📝 Creating sample presentation data...")
        presentation_data = create_sample_presentation(template_id, language)
        logger.info(f"   Created {len(presentation_data.slides)} slides")
        
        # Initialize generator
        logger.info(f"🎨 Initializing generator for template '{template_id}'...")
        generator = PptxGenerator(template_id=template_id, language=language)
        
        # Generate PPTX
        logger.info("⚙️  Generating PPTX file...")
        generated_path = generator.generate(presentation_data)
        
        # Move to desired output location
        if str(generated_path) != str(output_path):
            import shutil
            shutil.move(str(generated_path), str(output_path))
            logger.info(f"   Moved to: {output_path}")
        
        logger.info(f"✅ Successfully generated: {output_path}")
        logger.info(f"   Total slides: {len(presentation_data.slides)}")
        
        # Open file if requested
        if args.open:
            import platform
            system = platform.system()
            if system == "Windows":
                os.startfile(str(output_path))
            elif system == "Darwin":  # macOS
                os.system(f"open '{output_path}'")
            else:  # Linux
                os.system(f"xdg-open '{output_path}'")
            logger.info("   Opened in default application")
        
        print(f"\n✅ Preview generated successfully!")
        print(f"   File: {output_path.absolute()}")
        print(f"   Slides: {len(presentation_data.slides)}")
        print(f"\nTo open manually, run:")
        print(f"   {output_path.absolute()}")
        
    except Exception as e:
        logger.error(f"❌ Error generating preview: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
