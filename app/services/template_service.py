import json
from pathlib import Path
from typing import Dict, Any, Optional
from config import settings

class TemplateService:
    def __init__(self):
        self.templates_dir = Path(settings.TEMPLATES_DIR)
        self.templates: Dict[str, Dict] = {}
        self._load_templates()
    
    def _load_templates(self):
        """Load all template configurations with error handling"""
        try:
            if not self.templates_dir.exists():
                print(f"  Templates directory not found: {self.templates_dir}")
                self._create_default_template()
                return
            
            for template_dir in self.templates_dir.iterdir():
                if template_dir.is_dir():
                    try:
                        config_path = template_dir / "config.json"
                        layouts_path = template_dir / "layouts.json"
                        
                        if config_path.exists() and layouts_path.exists():
                            with open(config_path, 'r', encoding='utf-8') as f:
                                config = json.load(f)
                            with open(layouts_path, 'r', encoding='utf-8') as f:
                                layouts = json.load(f)
                            
                            template_id = config['template_id']
                            self.templates[template_id] = {
                                'config': config,
                                'layouts': layouts
                            }
                            print(f"Loaded template: {template_id}")
                        else:
                            print(f"  Missing config/layouts for: {template_dir.name}")
                    
                    except Exception as e:
                        print(f"Failed to load template {template_dir.name}: {e}")
            
            if not self.templates:
                print("  No templates loaded, creating default...")
                self._create_default_template()
        
        except Exception as e:
            print(f"Template loading error: {e}")
            self._create_default_template()
    
    def _create_default_template(self):
        """Create minimal default template in memory"""
        self.templates['standard'] = {
            'config': {
                'template_id': 'standard',
                'name': 'Standard',
                'theme': {
                    'primary': '#3B82F6',
                    'secondary': '#10B981',
                    'accent': '#F59E0B',
                    'background': '#FFFFFF',
                    'text': '#1F2937'
                },
                'typography': {
                    'title_font': 'Calibri',
                    'body_font': 'Calibri',
                    'title_size': 44,
                    'heading_size': 32,
                    'body_size': 18
                },
                'slide_dimensions': {
                    'width': 10,
                    'height': 5.625
                }
            },
            'layouts': {
                'title_slide': {
                    'layout_type': 'title',
                    'elements': []
                },
                'content_slide': {
                    'layout_type': 'content',
                    'elements': []
                }
            }
        }
        print("Default template created in memory")
    
    def get_template(self, template_id: str) -> Dict[str, Any]:
        """Get template configuration"""
        if template_id not in self.templates:
            print(f"  Template '{template_id}' not found, using 'standard'")
            template_id = 'standard'
        
        return self.templates.get(template_id, self.templates.get('standard'))
    
    def get_theme(self, template_id: str) -> Dict[str, str]:
        """Get color theme"""
        template = self.get_template(template_id)
        return template['config']['theme']
    
    def get_layout(self, template_id: str, layout_type: str) -> Dict:
        """Get specific layout definition"""
        template = self.get_template(template_id)
        layouts = template['layouts']
        
        # Map layout types
        layout_map = {
            'title': 'title_slide',
            'content': 'content_slide',
            'section': 'section_header',
            'two_column': 'two_column'
        }
        
        layout_key = layout_map.get(layout_type, 'content_slide')
        
        if layout_key not in layouts:
            print(f"  Layout '{layout_key}' not found, using 'content_slide'")
            layout_key = 'content_slide'
        
        return layouts.get(layout_key, layouts.get('content_slide', {'layout_type': 'content', 'elements': []}))
