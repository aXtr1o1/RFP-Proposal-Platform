"""
Preview PPT Generation Script
Generates test presentations with various content types to verify the template system.

Usage:
    python preview_ppt.py                    # Generate with all templates
    python preview_ppt.py arweqah            # Generate with specific template
    python preview_ppt.py arweqah ar         # Generate with specific template and language
"""

import sys
import os
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.pptx_generator import PptxGenerator
from app.models.presentation import (
    PresentationData, 
    SlideContent, 
    BulletPoint, 
    TableData
)


def create_sample_presentation(language: str = "en") -> PresentationData:
    """Create a sample presentation with various content types"""
    
    if language == "ar":
        return create_arabic_presentation()
    else:
        return create_english_presentation()


def create_english_presentation() -> PresentationData:
    """Create sample English presentation"""
    
    slides = [
        # Section slide
        SlideContent(
            title="Introduction",
            layout_type="section"
        ),
        
        # Bullet points slide
        SlideContent(
            title="Key Features",
            layout_type="bullets",
            bullets=[
                BulletPoint(text="Native PPTX template support for maximum editability"),
                BulletPoint(text="Automatic layout selection based on content type"),
                BulletPoint(text="Full RTL/LTR language support"),
                BulletPoint(text="Background image overlays for custom branding"),
                BulletPoint(text="Smart placeholder filling with proper formatting"),
            ]
        ),
        
        # Another section
        SlideContent(
            title="Technical Overview",
            layout_type="section"
        ),
        
        # Content with paragraph
        SlideContent(
            title="How It Works",
            layout_type="paragraph",
            paragraph="""The system uses native PowerPoint templates with master slides and layouts. 
When generating a presentation, it analyzes the content type and selects the appropriate layout.
Content is then filled into the native placeholders, ensuring maximum editability in PowerPoint.
Background images can be overlaid for custom branding while maintaining the editable structure."""
        ),
        
        # Table slide
        SlideContent(
            title="Feature Comparison",
            layout_type="table",
            table_data=TableData(
                headers=["Feature", "JSON Mode", "Native Mode"],
                rows=[
                    ["Editability", "Limited", "Full"],
                    ["Configuration", "Complex JSON", "Simple PPTX"],
                    ["RTL Support", "Manual", "Automatic"],
                    ["Performance", "Slower", "Faster"],
                    ["Maintenance", "High", "Low"],
                ]
            )
        ),
        
        # Another bullet slide
        SlideContent(
            title="Benefits",
            layout_type="bullets",
            bullets=[
                BulletPoint(
                    text="Fully Editable Output",
                    sub_bullets=[
                        "Uses native PowerPoint placeholders",
                        "All text and elements can be modified",
                    ]
                ),
                BulletPoint(
                    text="Consistent Formatting",
                    sub_bullets=[
                        "Styles come from the template",
                        "No code-defined positioning needed",
                    ]
                ),
                BulletPoint(text="Easy Template Updates"),
                BulletPoint(text="Better Performance"),
            ]
        ),
        
        # Section for conclusion
        SlideContent(
            title="Summary",
            layout_type="section"
        ),
        
        # Final content slide
        SlideContent(
            title="Next Steps",
            layout_type="bullets",
            bullets=[
                BulletPoint(text="Test the generation with various content types"),
                BulletPoint(text="Create custom PPTX templates in PowerPoint"),
                BulletPoint(text="Run the analyzer to generate manifests"),
                BulletPoint(text="Deploy and monitor performance"),
            ]
        ),
    ]
    
    return PresentationData(
        title="Native Template System Demo",
        subtitle="Testing the New PPT Generation",
        author="Template System",
        language="en",
        slides=slides
    )


def create_arabic_presentation() -> PresentationData:
    """Create sample Arabic presentation"""
    
    slides = [
        # Section slide
        SlideContent(
            title="مقدمة",
            layout_type="section"
        ),
        
        # Bullet points slide
        SlideContent(
            title="الميزات الرئيسية",
            layout_type="bullets",
            bullets=[
                BulletPoint(text="دعم قوالب PPTX الأصلية لأقصى قابلية للتحرير"),
                BulletPoint(text="اختيار تلقائي للتخطيط بناءً على نوع المحتوى"),
                BulletPoint(text="دعم كامل للغات من اليمين لليسار"),
                BulletPoint(text="تراكب صور الخلفية للعلامة التجارية"),
                BulletPoint(text="ملء ذكي للعناصر النائبة"),
            ]
        ),
        
        # Another section
        SlideContent(
            title="نظرة تقنية",
            layout_type="section"
        ),
        
        # Content slide
        SlideContent(
            title="كيف يعمل النظام",
            layout_type="paragraph",
            paragraph="""يستخدم النظام قوالب PowerPoint الأصلية مع الشرائح الرئيسية والتخطيطات.
عند إنشاء عرض تقديمي، يقوم بتحليل نوع المحتوى واختيار التخطيط المناسب.
يتم ملء المحتوى في العناصر النائبة الأصلية، مما يضمن أقصى قابلية للتحرير في PowerPoint."""
        ),
        
        # Table slide
        SlideContent(
            title="مقارنة الميزات",
            layout_type="table",
            table_data=TableData(
                headers=["الميزة", "الوضع القديم", "الوضع الجديد"],
                rows=[
                    ["قابلية التحرير", "محدودة", "كاملة"],
                    ["التكوين", "JSON معقد", "PPTX بسيط"],
                    ["دعم RTL", "يدوي", "تلقائي"],
                    ["الأداء", "بطيء", "سريع"],
                ]
            )
        ),
        
        # Final section
        SlideContent(
            title="الخلاصة",
            layout_type="section"
        ),
        
        # Final content slide
        SlideContent(
            title="الخطوات التالية",
            layout_type="bullets",
            bullets=[
                BulletPoint(text="اختبار التوليد مع أنواع محتوى مختلفة"),
                BulletPoint(text="إنشاء قوالب PPTX مخصصة"),
                BulletPoint(text="تشغيل المحلل لإنشاء البيانات الوصفية"),
                BulletPoint(text="النشر ومراقبة الأداء"),
            ]
        ),
    ]
    
    return PresentationData(
        title="عرض نظام القوالب الأصلية",
        subtitle="اختبار توليد العروض التقديمية الجديد",
        author="نظام القوالب",
        language="ar",
        slides=slides
    )


def generate_preview(template_id: str = "arweqah", language: str = "en"):
    """Generate a preview presentation"""
    
    print("=" * 60)
    print(f"GENERATING PREVIEW")
    print(f"  Template: {template_id}")
    print(f"  Language: {language}")
    print("=" * 60)
    
    # Create sample data
    presentation_data = create_sample_presentation(language)
    
    try:
        # Initialize generator
        generator = PptxGenerator(template_id, language)
        
        # Generate presentation
        output_path = generator.generate(presentation_data)
        
        print("\n" + "=" * 60)
        print("SUCCESS!")
        print(f"  Output: {output_path}")
        print("=" * 60)
        
        return output_path
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_all_previews():
    """Generate previews for all templates and languages"""
    
    templates = ["arweqah", "arweqah_native", "standard"]
    languages = {
        "arweqah": ["en", "ar"],
        "arweqah_native": ["en", "ar"],
        "standard": ["en"],
    }
    
    results = []
    
    for template_id in templates:
        for lang in languages.get(template_id, ["en"]):
            print(f"\n{'#' * 60}")
            print(f"# {template_id} - {lang}")
            print(f"{'#' * 60}")
            
            output = generate_preview(template_id, lang)
            results.append({
                "template": template_id,
                "language": lang,
                "success": output is not None,
                "output": output
            })
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in results:
        status = "OK" if r["success"] else "FAILED"
        print(f"  [{status}] {r['template']} ({r['language']})")
        if r["output"]:
            print(f"        -> {r['output']}")
    
    return results


def main():
    """Main entry point"""
    
    if len(sys.argv) >= 2:
        template_id = sys.argv[1]
        language = sys.argv[2] if len(sys.argv) >= 3 else "en"
        
        if template_id == "all":
            generate_all_previews()
        else:
            generate_preview(template_id, language)
    else:
        # Default: generate arweqah English
        generate_preview("arweqah", "en")


if __name__ == "__main__":
    main()
