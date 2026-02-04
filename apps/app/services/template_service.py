"""
Template Service Module
Manages template loading and access for native PPTX template mode.

This service handles:
- Loading template configurations
- Loading manifests (auto-generated or manual)
- Providing access to template metadata and layouts
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from ..config import settings
from ..models.template_manifest import TemplateManifest

logger = logging.getLogger("template_service")


class TemplateService:
    """
    Service for managing presentation templates.
    
    Templates are loaded from the templates directory and can include:
    - config.json: Template metadata and settings
    - manifest.json: Auto-generated layout information
    - template.pptx: Native PowerPoint template
    - Background/: Background images
    - theme.json: Theme colors and fonts
    - constraints.json: Layout constraints
    
    Usage:
        service = TemplateService()
        template = service.get_template("arweqah")
        manifest = service.get_manifest("arweqah")
    """
    
    def __init__(self):
        self.templates_dir = Path(settings.TEMPLATES_DIR)
        self.templates: Dict[str, Dict[str, Any]] = {}
        self.manifests: Dict[str, TemplateManifest] = {}
        self._load_templates()
    
    def _load_templates(self) -> None:
        """Load all template configurations"""
        logger.info(f"Loading templates from: {self.templates_dir}")
        
        if not self.templates_dir.exists():
            logger.warning(f"Templates directory not found: {self.templates_dir}")
            return
        
        for template_dir in self.templates_dir.iterdir():
            if template_dir.is_dir():
                try:
                    template_id = template_dir.name
                    self._load_template(template_id, template_dir)
                except Exception as e:
                    logger.warning(f"Failed to load template {template_dir.name}: {e}")
        
        logger.info(f"Loaded {len(self.templates)} templates")
    
    def _load_template(self, template_id: str, template_dir: Path) -> None:
        """Load a single template"""
        # Load config.json (required)
        config_path = template_dir / "config.json"
        if not config_path.exists():
            logger.debug(f"Skipping {template_id}: no config.json")
            return
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Load theme.json (optional)
        theme = {}
        theme_path = template_dir / "theme.json"
        if theme_path.exists():
            with open(theme_path, 'r', encoding='utf-8') as f:
                theme = json.load(f)
        
        # Load constraints.json (optional)
        constraints = {}
        constraints_path = template_dir / "constraints.json"
        if constraints_path.exists():
            with open(constraints_path, 'r', encoding='utf-8') as f:
                constraints = json.load(f)
        
        # Check for template.pptx
        has_pptx = (template_dir / "template.pptx").exists()
        
        # Load manifest.json (optional)
        manifest = None
        manifest_path = template_dir / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest_data = json.load(f)
                manifest = TemplateManifest(**manifest_data)
                self.manifests[template_id] = manifest
            except Exception as e:
                logger.warning(f"Failed to load manifest for {template_id}: {e}")
        
        # Store template data
        self.templates[template_id] = {
            'config': config,
            'theme': theme,
            'constraints': constraints,
            'has_pptx': has_pptx,
            'has_manifest': manifest is not None,
            'path': str(template_dir)
        }
        
        logger.info(f"  Loaded template: {template_id} (PPTX={has_pptx}, manifest={manifest is not None})")
    
    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """
        Get template configuration.
        
        Args:
            template_id: Template identifier
            
        Returns:
            Template configuration dict or None
        """
        if template_id not in self.templates:
            logger.warning(f"Template '{template_id}' not found")
            # Try to find a default
            if self.templates:
                default_id = list(self.templates.keys())[0]
                logger.info(f"Using default template: {default_id}")
                return self.templates.get(default_id)
            return None
        
        return self.templates[template_id]
    
    def get_manifest(self, template_id: str) -> Optional[TemplateManifest]:
        """
        Get template manifest.
        
        Args:
            template_id: Template identifier
            
        Returns:
            TemplateManifest or None
        """
        return self.manifests.get(template_id)
    
    def get_config(self, template_id: str) -> Dict[str, Any]:
        """Get template config.json content"""
        template = self.get_template(template_id)
        if template:
            return template.get('config', {})
        return {}
    
    def get_theme(self, template_id: str) -> Dict[str, Any]:
        """Get template theme"""
        template = self.get_template(template_id)
        if template:
            return template.get('theme', {})
        return {}
    
    def get_constraints(self, template_id: str) -> Dict[str, Any]:
        """Get template constraints"""
        template = self.get_template(template_id)
        if template:
            return template.get('constraints', {})
        return {}
    
    def get_template_path(self, template_id: str) -> Optional[Path]:
        """Get template directory path"""
        template = self.get_template(template_id)
        if template:
            return Path(template.get('path', ''))
        return None
    
    def get_pptx_path(self, template_id: str) -> Optional[Path]:
        """Get template.pptx path if exists"""
        template_path = self.get_template_path(template_id)
        if template_path:
            pptx_path = template_path / "template.pptx"
            if pptx_path.exists():
                return pptx_path
        return None
    
    def list_templates(self) -> List[str]:
        """Get list of available template IDs"""
        return list(self.templates.keys())
    
    def get_template_info(self, template_id: str) -> Optional[Dict[str, Any]]:
        """
        Get summary information about a template.
        
        Returns:
            Dictionary with template info
        """
        template = self.get_template(template_id)
        if not template:
            return None
        
        config = template.get('config', {})
        manifest = self.manifests.get(template_id)
        
        return {
            'template_id': template_id,
            'name': config.get('template_name', template_id),
            'version': config.get('version', '1.0.0'),
            'mode': config.get('template_mode', 'native'),
            'has_pptx': template.get('has_pptx', False),
            'has_manifest': template.get('has_manifest', False),
            'layout_count': len(manifest.layouts) if manifest else 0,
            'languages': config.get('language_settings', {}).get('supported', ['en']),
        }
    
    def list_template_info(self) -> List[Dict[str, Any]]:
        """Get info for all templates"""
        return [
            self.get_template_info(tid)
            for tid in self.templates.keys()
        ]
    
    def get_layout_for_content(self, template_id: str, content_type: str) -> Optional[Dict[str, Any]]:
        """
        Get layout configuration for a content type.
        
        Args:
            template_id: Template identifier
            content_type: Content type (title, content, section, etc.)
            
        Returns:
            Layout configuration dict
        """
        manifest = self.get_manifest(template_id)
        if manifest:
            layout_key = manifest.content_type_mapping.get(content_type)
            if layout_key:
                layout_def = manifest.layouts.get(layout_key)
                if layout_def:
                    return {
                        'index': layout_def.index,
                        'name': layout_def.name,
                        'placeholders': [
                            {'idx': p.idx, 'type': p.type, 'name': p.name}
                            for p in layout_def.placeholders
                        ]
                    }
        
        # Fallback to config layout_mapping
        config = self.get_config(template_id)
        layout_mapping = config.get('layout_mapping', {})
        layout_idx = layout_mapping.get(content_type)
        
        if layout_idx is not None:
            return {'index': layout_idx, 'name': content_type}
        
        return None
    
    def reload_template(self, template_id: str) -> bool:
        """
        Reload a specific template.
        
        Args:
            template_id: Template to reload
            
        Returns:
            True if successful
        """
        template_dir = self.templates_dir / template_id
        if not template_dir.exists():
            return False
        
        # Remove existing
        self.templates.pop(template_id, None)
        self.manifests.pop(template_id, None)
        
        # Reload
        try:
            self._load_template(template_id, template_dir)
            return True
        except Exception as e:
            logger.error(f"Failed to reload {template_id}: {e}")
            return False
    
    def reload_all(self) -> None:
        """Reload all templates"""
        self.templates.clear()
        self.manifests.clear()
        self._load_templates()


# ============================================================================
# GLOBAL SERVICE INSTANCE
# ============================================================================

_service_instance: Optional[TemplateService] = None


def get_template_service() -> TemplateService:
    """Get the global template service instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = TemplateService()
    return _service_instance


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def get_template(template_id: str) -> Optional[Dict[str, Any]]:
    """Get template configuration"""
    return get_template_service().get_template(template_id)


def get_manifest(template_id: str) -> Optional[TemplateManifest]:
    """Get template manifest"""
    return get_template_service().get_manifest(template_id)


def list_templates() -> List[str]:
    """List available templates"""
    return get_template_service().list_templates()
