import sys
import traceback
import logging
import os

# Configure logging to console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_parity")

try:
    from apps.app.services.pptx_generator import PptxGenerator
    from apps.app.models.presentation import PresentationData, SlideContent

    print("Import successful")
    
    template_id = "arweqah_native"
    language = "en"
    
    # Check config first
    gen = PptxGenerator(template_id, language)
    config = gen.config
    print(f"Loaded config for {template_id}")
    print(f"Alignment EN: {config.get('language_settings', {}).get('en', {}).get('alignment')}")
    print(f"Page Numbering: {config.get('page_numbering', {}).get('enabled')}")

    slides = [
        SlideContent(title="Title Slide", subtitle="Subtitle Parity Test", layout_type="title_slide"),
        SlideContent(title="Content Slide", content="Checking alignment and page numbers.", layout_type="content"),
        SlideContent(title="Bullets Slide", bullets=[{"text": "Bullet 1"}, {"text": "Bullet 2"}], layout_type="bullets")
    ]
    data = PresentationData(title="Parity Test", slides=slides, language=language)
    
    output = gen.generate(data)
    print(f"Generated: {output}")

except Exception:
    with open("debug_parity_error.txt", "w") as f:
        traceback.print_exc(file=f)
    print("Error occurred, wrote to debug_parity_error.txt")
    traceback.print_exc()
