import sys
import traceback
from pathlib import Path
import logging

# Configure logging to console
logging.basicConfig(level=logging.INFO)

try:
    from apps.app.services.pptx_generator import PptxGenerator
    from apps.app.models.presentation import PresentationData, SlideContent

    print("Import successful")
    
    template_id = "arweqah_native"
    gen = PptxGenerator(template_id, "en")
    print("Generator initialized")
    
    slides = [
        SlideContent(title="Debug Title", content="Debug Content", layout_type="title_and_content")
    ]
    data = PresentationData(title="Debug Pres", slides=slides, language="en")
    
    output = gen.generate(data)
    print(f"Generated: {output}")

except Exception:
    with open("debug_error.txt", "w") as f:
        traceback.print_exc(file=f)
    traceback.print_exc()
