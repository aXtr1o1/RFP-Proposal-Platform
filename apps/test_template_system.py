#!/usr/bin/env python3
"""
Test Script for Dynamic Template System

This script tests the template analyzer, registry, and native_auto mode
with the existing arweqah template.

Run from the apps directory:
    python test_template_system.py
"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_template_analyzer():
    """Test the template analyzer module"""
    print("\n" + "=" * 60)
    print("TEST 1: Template Analyzer")
    print("=" * 60)
    
    try:
        from app.services.template_analyzer import (
            TemplateAnalyzer,
            analyze_template,
            print_template_summary
        )
        print("[OK] Template analyzer imported successfully")
        
        # Test with arweqah template directory
        template_dir = Path(__file__).parent / "app" / "templates" / "arweqah"
        
        if not template_dir.exists():
            print(f"[FAIL] Template directory not found: {template_dir}")
            return False
        
        print(f"[OK] Template directory found: {template_dir}")
        
        # Check for PPTX file
        pptx_path = template_dir / "template.pptx"
        if pptx_path.exists():
            print("[OK] Found template.pptx - can analyze")
            
            # Analyze template
            manifest = analyze_template(str(pptx_path))
            print("[OK] Template analyzed successfully")
            print(f"  - Layouts: {len(manifest.layouts)}")
            print(f"  - Content mappings: {len(manifest.content_type_mapping)}")
            
            # Print summary
            print_template_summary(manifest)
        else:
            print("[INFO] No template.pptx found (using legacy mode)")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_template_registry():
    """Test the template registry module"""
    print("\n" + "=" * 60)
    print("TEST 2: Template Registry")
    print("=" * 60)
    
    try:
        from app.services.template_registry import (
            TemplateRegistry,
            get_registry,
            register_template
        )
        print("[OK] Template registry imported successfully")
        
        # Get global registry
        registry = get_registry()
        print("[OK] Registry instance obtained")
        
        # Test registering arweqah template directory
        template_dir = Path(__file__).parent / "app" / "templates" / "arweqah"
        
        if template_dir.exists():
            # Register legacy template
            manifest = registry.register_legacy_template(str(template_dir), "arweqah_test")
            print(f"[OK] Legacy template registered: {manifest.template_id}")
            print(f"  - Mode: {manifest.template_mode}")
            print(f"  - Layouts: {len(manifest.layouts)}")
            
            # List templates
            templates = registry.list_templates()
            print(f"[OK] Registered templates: {templates}")
            
            # Get template info
            info = registry.get_template_info("arweqah_test")
            print("[OK] Template info retrieved")
            
            # Unregister
            registry.unregister("arweqah_test")
            print("[OK] Template unregistered")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_layout_mapper():
    """Test the layout mapper module"""
    print("\n" + "=" * 60)
    print("TEST 3: Layout Mapper")
    print("=" * 60)
    
    try:
        from app.services.layout_mapper import (
            LayoutMapper,
            suggest_mappings,
            explain_layout_choice
        )
        from app.services.template_registry import get_registry
        
        print("[OK] Layout mapper imported successfully")
        
        # Register template first
        template_dir = Path(__file__).parent / "app" / "templates" / "arweqah"
        registry = get_registry()
        manifest = registry.register_legacy_template(str(template_dir), "arweqah_mapper_test")
        
        # Create mapper
        mapper = LayoutMapper(manifest)
        print("[OK] Layout mapper created")
        
        # Get mappings
        mappings = mapper.suggest_layout_mapping()
        print(f"[OK] Suggested mappings: {len(mappings)}")
        
        for content_type, layout_key in mappings.items():
            print(f"  {content_type:15} -> {layout_key}")
        
        # Cleanup
        registry.unregister("arweqah_mapper_test")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pptx_generator_native_auto():
    """Test the PPTX generator with native_auto mode"""
    print("\n" + "=" * 60)
    print("TEST 4: PPTX Generator (native_auto mode)")
    print("=" * 60)
    
    try:
        from app.services.pptx_generator import PptxGenerator
        from app.models.presentation import PresentationData, SlideContent, BulletPoint
        
        print("[OK] PPTX generator imported successfully")
        
        # Create test presentation data
        test_slides = [
            SlideContent(
                layout_type="section",
                title="Introduction",
                content="Welcome to the presentation"
            ),
            SlideContent(
                layout_type="content",
                title="Key Points",
                bullets=[
                    BulletPoint(text="First important point"),
                    BulletPoint(text="Second important point"),
                    BulletPoint(text="Third important point"),
                ]
            ),
        ]
        
        test_presentation = PresentationData(
            title="Test Presentation",
            subtitle="Testing native_auto mode",
            author="Template System",
            slides=test_slides,
            language="en"
        )
        
        print("[OK] Test presentation data created")
        
        # Note: Actual generation requires proper template setup
        # This test just verifies the imports work
        
        print("[INFO] Full generation test requires template.pptx file")
        print("[INFO] Use 'python analyze_template.py --template path/to/template.pptx' to analyze")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_manifest_models():
    """Test the template manifest Pydantic models"""
    print("\n" + "=" * 60)
    print("TEST 5: Manifest Models")
    print("=" * 60)
    
    try:
        from app.models.template_manifest import (
            TemplateManifest,
            LayoutDefinition,
            PlaceholderSlot,
            Position,
            SlideDimensions,
            ThemeDefinition
        )
        print("[OK] Manifest models imported successfully")
        
        # Create test manifest
        test_layout = LayoutDefinition(
            index=0,
            name="Test Layout",
            placeholders=[
                PlaceholderSlot(
                    idx=0,
                    type="title",
                    name="Title 1",
                    position=Position(left=1.0, top=1.0, width=10.0, height=1.5)
                ),
                PlaceholderSlot(
                    idx=1,
                    type="body",
                    name="Content Placeholder",
                    position=Position(left=1.0, top=3.0, width=10.0, height=4.0)
                )
            ]
        )
        
        test_manifest = TemplateManifest(
            template_id="test_template",
            template_name="Test Template",
            slide_dimensions=SlideDimensions(width=13.33, height=7.5),
            layouts={"test_layout": test_layout},
            content_type_mapping={"content": "test_layout"},
            theme=ThemeDefinition(colors=[], fonts={"heading": "Arial", "body": "Arial"})
        )
        
        print("[OK] Test manifest created")
        print(f"  - ID: {test_manifest.template_id}")
        print(f"  - Layouts: {test_manifest.list_layout_keys()}")
        
        # Test helper methods
        layout = test_manifest.get_layout_for_content("content")
        if layout:
            print(f"[OK] get_layout_for_content works: {layout.name}")
        
        # Test serialization
        manifest_dict = test_manifest.model_dump(exclude_none=True)
        print(f"[OK] Manifest serialization works: {len(json.dumps(manifest_dict))} bytes")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("DYNAMIC TEMPLATE SYSTEM - TEST SUITE")
    print("=" * 60)
    
    results = {
        "Manifest Models": test_manifest_models(),
        "Template Analyzer": test_template_analyzer(),
        "Template Registry": test_template_registry(),
        "Layout Mapper": test_layout_mapper(),
        "PPTX Generator": test_pptx_generator_native_auto(),
    }
    
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results.items():
        status = "PASSED" if result else "FAILED"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print("-" * 60)
    print(f"  Total: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
