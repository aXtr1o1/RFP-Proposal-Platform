"""
Template Registry Module
Manages multiple templates with dynamic loading and caching.
"""

import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from threading import Lock
from datetime import datetime

from ..models.template_manifest import (
    TemplateManifest,
    create_manifest_from_json,
    LayoutDefinition,
    SlideDimensions,
    ThemeDefinition,
    AnalysisMetadata
)
from .template_analyzer import TemplateAnalyzer, analyze_template

logger = logging.getLogger("template_registry")


class TemplateRegistry:
    """
    Central registry for managing presentation templates.
    
    Features:
    - Register templates from PPTX files (auto-analysis)
    - Register templates from existing JSON manifests
    - Cache manifests for performance
    - Support for multiple templates simultaneously
    - Thread-safe operations
    
    Usage:
        registry = TemplateRegistry()
        
        # Register from PPTX (auto-analyze)
        registry.register_from_pptx("path/to/template.pptx", "my_template")
        
        # Register from existing manifest
        registry.register_from_manifest("path/to/manifest.json", "my_template")
        
        # Get template
        manifest = registry.get_template("my_template")
        layout = manifest.get_layout_for_content("bullets")
    """
    
    _instance: Optional['TemplateRegistry'] = None
    _lock = Lock()
    
    def __new__(cls):
        """Singleton pattern for global registry access"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._templates: Dict[str, TemplateManifest] = {}
        self._template_paths: Dict[str, Path] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        self._analyzer = TemplateAnalyzer()
        self._initialized = True
        
        logger.info("Template Registry initialized")
    
    # ========================================================================
    # REGISTRATION METHODS
    # ========================================================================
    
    def register_from_pptx(
        self,
        pptx_path: str,
        template_id: Optional[str] = None,
        template_name: Optional[str] = None,
        save_manifest: bool = True
    ) -> TemplateManifest:
        """
        Register a template by analyzing a PPTX file.
        
        Args:
            pptx_path: Path to the PPTX template file
            template_id: Optional ID (defaults to filename)
            template_name: Optional name (defaults to filename)
            save_manifest: Whether to save the manifest JSON alongside the PPTX
            
        Returns:
            The generated TemplateManifest
        """
        path = Path(pptx_path)
        if not path.exists():
            raise FileNotFoundError(f"PPTX template not found: {pptx_path}")
        
        # Generate template ID from filename if not provided
        tid = template_id or path.stem
        tname = template_name or path.stem.replace("_", " ").title()
        
        logger.info(f"Registering template from PPTX: {tid}")
        
        # Analyze the template
        manifest = self._analyzer.analyze_template(
            str(path),
            template_id=tid,
            template_name=tname
        )
        
        # Save manifest if requested
        if save_manifest:
            manifest_path = path.parent / "manifest.json"
            manifest_dict = self._manifest_to_dict(manifest)
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest_dict, f, indent=2, ensure_ascii=False)
            logger.info(f"Manifest saved: {manifest_path}")
        
        # Register
        self._templates[tid] = manifest
        self._template_paths[tid] = path
        self._cache_timestamps[tid] = datetime.now()
        
        logger.info(f"Template registered: {tid} ({len(manifest.layouts)} layouts)")
        return manifest
    
    def register_from_manifest(
        self,
        manifest_path: str,
        template_id: Optional[str] = None
    ) -> TemplateManifest:
        """
        Register a template from an existing manifest JSON file.
        
        Args:
            manifest_path: Path to the manifest JSON file
            template_id: Optional override for template ID
            
        Returns:
            The loaded TemplateManifest
        """
        path = Path(manifest_path)
        if not path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")
        
        logger.info(f"Registering template from manifest: {manifest_path}")
        
        # Load manifest
        manifest = create_manifest_from_json(str(path))
        
        # Override ID if provided
        if template_id:
            manifest.template_id = template_id
        
        tid = manifest.template_id
        
        # Register
        self._templates[tid] = manifest
        self._template_paths[tid] = path
        self._cache_timestamps[tid] = datetime.now()
        
        logger.info(f"Template registered: {tid} ({len(manifest.layouts)} layouts)")
        return manifest
    
    def register_from_directory(
        self,
        template_dir: str,
        template_id: Optional[str] = None
    ) -> TemplateManifest:
        """
        Register a template from a directory containing either:
        - A manifest.json file
        - A template.pptx file
        
        Priority: manifest.json > template.pptx > *.pptx
        
        Args:
            template_dir: Path to template directory
            template_id: Optional template ID
            
        Returns:
            The loaded/generated TemplateManifest
        """
        dir_path = Path(template_dir)
        if not dir_path.exists() or not dir_path.is_dir():
            raise NotADirectoryError(f"Template directory not found: {template_dir}")
        
        tid = template_id or dir_path.name
        
        # Check for manifest first
        manifest_path = dir_path / "manifest.json"
        if manifest_path.exists():
            return self.register_from_manifest(str(manifest_path), tid)
        
        # Check for template.pptx
        pptx_path = dir_path / "template.pptx"
        if pptx_path.exists():
            return self.register_from_pptx(str(pptx_path), tid)
        
        # Check for any PPTX file
        pptx_files = list(dir_path.glob("*.pptx"))
        if pptx_files:
            return self.register_from_pptx(str(pptx_files[0]), tid)
        
        raise FileNotFoundError(
            f"No manifest.json or PPTX file found in: {template_dir}"
        )
    
    def register_legacy_template(
        self,
        template_dir: str,
        template_id: Optional[str] = None
    ) -> TemplateManifest:
        """
        Register a legacy template that uses config.json/layouts.json format.
        Converts to manifest format for unified handling.
        
        Args:
            template_dir: Path to template directory with config.json
            template_id: Optional template ID
            
        Returns:
            Converted TemplateManifest
        """
        dir_path = Path(template_dir)
        config_path = dir_path / "config.json"
        
        if not config_path.exists():
            raise FileNotFoundError(f"config.json not found in: {template_dir}")
        
        tid = template_id or dir_path.name
        
        logger.info(f"Converting legacy template: {tid}")
        
        # Load config.json
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Load layouts.json if exists
        layouts_path = dir_path / "layouts.json"
        layouts_data = {}
        if layouts_path.exists():
            with open(layouts_path, 'r', encoding='utf-8') as f:
                layouts_data = json.load(f)
        
        # Convert to manifest format
        manifest = self._convert_legacy_to_manifest(config, layouts_data, tid, dir_path)
        
        # Register
        self._templates[tid] = manifest
        self._template_paths[tid] = dir_path
        self._cache_timestamps[tid] = datetime.now()
        
        logger.info(f"Legacy template registered: {tid}")
        return manifest
    
    # ========================================================================
    # RETRIEVAL METHODS
    # ========================================================================
    
    def get_template(self, template_id: str) -> Optional[TemplateManifest]:
        """
        Get a registered template by ID.
        
        Args:
            template_id: Template identifier
            
        Returns:
            TemplateManifest if found, None otherwise
        """
        return self._templates.get(template_id)
    
    def get_template_or_raise(self, template_id: str) -> TemplateManifest:
        """
        Get a registered template by ID, raising exception if not found.
        
        Args:
            template_id: Template identifier
            
        Returns:
            TemplateManifest
            
        Raises:
            KeyError if template not found
        """
        manifest = self._templates.get(template_id)
        if not manifest:
            raise KeyError(f"Template not found: {template_id}")
        return manifest
    
    def list_templates(self) -> List[str]:
        """Get list of all registered template IDs"""
        return list(self._templates.keys())
    
    def get_template_info(self, template_id: str) -> Optional[Dict[str, Any]]:
        """
        Get summary information about a template.
        
        Returns:
            Dictionary with template info, or None if not found
        """
        manifest = self._templates.get(template_id)
        if not manifest:
            return None
        
        return {
            "template_id": manifest.template_id,
            "template_name": manifest.template_name,
            "version": manifest.version,
            "template_mode": manifest.template_mode,
            "layout_count": len(manifest.layouts),
            "layouts": list(manifest.layouts.keys()),
            "content_mappings": manifest.content_type_mapping,
            "cached_at": self._cache_timestamps.get(template_id),
            "source_path": str(self._template_paths.get(template_id, ""))
        }
    
    def list_template_info(self) -> List[Dict[str, Any]]:
        """Get info for all registered templates"""
        return [
            self.get_template_info(tid)
            for tid in self._templates.keys()
        ]
    
    # ========================================================================
    # MANAGEMENT METHODS
    # ========================================================================
    
    def unregister(self, template_id: str) -> bool:
        """
        Unregister a template.
        
        Args:
            template_id: Template to remove
            
        Returns:
            True if removed, False if not found
        """
        if template_id in self._templates:
            del self._templates[template_id]
            self._template_paths.pop(template_id, None)
            self._cache_timestamps.pop(template_id, None)
            logger.info(f"Template unregistered: {template_id}")
            return True
        return False
    
    def clear(self) -> None:
        """Clear all registered templates"""
        self._templates.clear()
        self._template_paths.clear()
        self._cache_timestamps.clear()
        logger.info("Template registry cleared")
    
    def reload(self, template_id: str) -> Optional[TemplateManifest]:
        """
        Reload a template from its source.
        
        Args:
            template_id: Template to reload
            
        Returns:
            Reloaded manifest, or None if source not found
        """
        source_path = self._template_paths.get(template_id)
        if not source_path:
            logger.warning(f"Cannot reload template (no source path): {template_id}")
            return None
        
        # Unregister first
        self.unregister(template_id)
        
        # Re-register based on file type
        if source_path.suffix == ".json":
            return self.register_from_manifest(str(source_path), template_id)
        elif source_path.suffix == ".pptx":
            return self.register_from_pptx(str(source_path), template_id)
        elif source_path.is_dir():
            return self.register_from_directory(str(source_path), template_id)
        
        return None
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _manifest_to_dict(self, manifest: TemplateManifest) -> Dict:
        """Convert manifest to dictionary for JSON serialization"""
        return manifest.model_dump(exclude_none=True)
    
    def _convert_legacy_to_manifest(
        self,
        config: Dict,
        layouts_data: Dict,
        template_id: str,
        template_dir: Path
    ) -> TemplateManifest:
        """Convert legacy config/layouts format to manifest"""
        
        # Extract dimensions
        dimensions = config.get("slide_dimensions", {})
        slide_dims = SlideDimensions(
            width=dimensions.get("width", 13.33),
            height=dimensions.get("height", 7.5),
            units=dimensions.get("units", "inches"),
            aspect_ratio=dimensions.get("aspect_ratio")
        )
        
        # Convert layouts
        converted_layouts = {}
        layout_mapping = config.get("layout_mapping", {})
        
        for layout_name, layout_info in layouts_data.items():
            # Skip if not a dict
            if not isinstance(layout_info, dict):
                continue
            
            # Get index from layout_mapping or use sequential
            layout_index = layout_mapping.get(layout_name, len(converted_layouts))
            if isinstance(layout_index, str):
                # If it's a string reference, try to resolve
                layout_index = layout_mapping.get(layout_index, len(converted_layouts))
            
            # Create layout definition
            layout_def = LayoutDefinition(
                index=layout_index if isinstance(layout_index, int) else 0,
                name=layout_name,
                placeholders=[],  # Legacy format doesn't have placeholder info
                master_name=None
            )
            
            converted_layouts[layout_name] = layout_def
        
        # Extract theme (minimal)
        theme = ThemeDefinition(
            colors=[],
            fonts=config.get("theme", {}).get("typography", {}).get("font_families", {})
        )
        
        # Content type mapping
        content_mapping = config.get("content_type_mapping", {})
        
        # Flatten list values in content mapping
        flat_mapping = {}
        for content_type, layout_ref in content_mapping.items():
            if isinstance(layout_ref, list):
                flat_mapping[content_type] = layout_ref[0] if layout_ref else content_type
            else:
                flat_mapping[content_type] = layout_ref
        
        # Normalize background image definitions to simple path mapping
        background_images_raw = config.get("background_images") or {}
        normalized_backgrounds = {}
        if isinstance(background_images_raw, dict):
            for key, value in background_images_raw.items():
                if isinstance(value, str):
                    normalized_backgrounds[key] = value
                elif isinstance(value, dict):
                    path = value.get("path")
                    if path:
                        normalized_backgrounds[key] = path
        if not normalized_backgrounds:
            normalized_backgrounds = None

        # Create manifest
        manifest = TemplateManifest(
            template_id=template_id,
            template_name=config.get("template_name", template_id),
            version=config.get("version", "1.0.0"),
            template_mode=config.get("template_mode", "json_only"),
            slide_dimensions=slide_dims,
            layouts=converted_layouts,
            content_type_mapping=flat_mapping,
            theme=theme,
            language_settings=None,  # Can be added from config if needed
            background_images=normalized_backgrounds,
            page_numbering=config.get("page_numbering"),
            analysis_metadata=AnalysisMetadata(
                source_file="config.json (legacy)",
                layout_count=len(converted_layouts),
                master_count=1,
                analyzed_version="legacy_conversion"
            )
        )
        
        return manifest


# ============================================================================
# GLOBAL REGISTRY INSTANCE
# ============================================================================

def get_registry() -> TemplateRegistry:
    """Get the global template registry instance"""
    return TemplateRegistry()


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def register_template(template_path: str, template_id: Optional[str] = None) -> TemplateManifest:
    """
    Convenience function to register a template.
    Automatically detects whether to use PPTX, manifest, or directory mode.
    
    Args:
        template_path: Path to template file or directory
        template_id: Optional template ID
        
    Returns:
        Registered TemplateManifest
    """
    registry = get_registry()
    path = Path(template_path)
    
    if path.is_dir():
        return registry.register_from_directory(str(path), template_id)
    elif path.suffix == ".pptx":
        return registry.register_from_pptx(str(path), template_id)
    elif path.suffix == ".json":
        return registry.register_from_manifest(str(path), template_id)
    else:
        raise ValueError(f"Unsupported template format: {template_path}")


def get_template(template_id: str) -> Optional[TemplateManifest]:
    """Convenience function to get a template"""
    return get_registry().get_template(template_id)


def list_templates() -> List[str]:
    """Convenience function to list template IDs"""
    return get_registry().list_templates()
