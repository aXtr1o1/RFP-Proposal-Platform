"""
Template Manifest Pydantic Models
Defines the schema for auto-generated template configurations.
"""

from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field


# ============================================================================
# POSITION AND SIZE MODELS
# ============================================================================

class Position(BaseModel):
    """Position and size in inches"""
    left: float = Field(..., description="Left position in inches")
    top: float = Field(..., description="Top position in inches")
    width: float = Field(..., description="Width in inches")
    height: float = Field(..., description="Height in inches")
    
    class Config:
        extra = "allow"


# ============================================================================
# STYLE MODELS
# ============================================================================

class StyleDef(BaseModel):
    """Text style definition"""
    font_name: Optional[str] = Field(None, description="Font family name")
    font_size: Optional[int] = Field(None, description="Font size in points")
    font_color: Optional[str] = Field(None, description="Font color (hex)")
    bold: bool = Field(default=False, description="Bold text")
    italic: bool = Field(default=False, description="Italic text")
    alignment: Optional[Literal["left", "center", "right", "justify"]] = Field(
        None, description="Text alignment"
    )
    line_spacing: Optional[float] = Field(None, description="Line spacing multiplier")
    
    class Config:
        extra = "allow"


# ============================================================================
# PLACEHOLDER MODELS
# ============================================================================

class PlaceholderSlot(BaseModel):
    """Placeholder slot definition"""
    idx: int = Field(..., description="Placeholder index (for accessing via slide.placeholders[idx])")
    type: str = Field(..., description="Placeholder type: title, body, subtitle, picture, chart, table, etc.")
    name: str = Field(..., description="Shape name from the template")
    position: Position = Field(..., description="Position and dimensions")
    style: Optional[StyleDef] = Field(None, description="Extracted text style")
    
    # Additional metadata
    is_required: bool = Field(default=True, description="Whether this placeholder must be filled")
    content_hint: Optional[str] = Field(None, description="Hint for AI content generation")
    
    class Config:
        extra = "allow"


# ============================================================================
# BACKGROUND MODELS
# ============================================================================

class BackgroundDef(BaseModel):
    """Background definition"""
    type: Literal["solid", "image", "gradient", "none"] = Field(
        ..., description="Background type"
    )
    color: Optional[str] = Field(None, description="Solid color (hex)")
    image_path: Optional[str] = Field(None, description="Path to background image")
    gradient_start: Optional[str] = Field(None, description="Gradient start color")
    gradient_end: Optional[str] = Field(None, description="Gradient end color")
    gradient_angle: Optional[int] = Field(None, description="Gradient angle")
    opacity: float = Field(default=1.0, description="Background opacity")
    
    class Config:
        extra = "allow"


# ============================================================================
# LAYOUT MODELS
# ============================================================================

class LayoutDefinition(BaseModel):
    """Complete layout definition"""
    index: int = Field(..., description="Layout index in slide_layouts collection")
    name: str = Field(..., description="Layout name from template")
    placeholders: List[PlaceholderSlot] = Field(
        default_factory=list, description="List of placeholders in this layout"
    )
    background: Optional[BackgroundDef] = Field(None, description="Background configuration")
    master_name: Optional[str] = Field(None, description="Name of parent slide master")
    
    # Layout metadata
    suitable_for: List[str] = Field(
        default_factory=list,
        description="Content types this layout is suitable for"
    )
    max_content_lines: Optional[int] = Field(None, description="Max content lines before overflow")
    supports_rtl: bool = Field(default=True, description="Whether layout supports RTL text")
    
    class Config:
        extra = "allow"
    
    def get_placeholder_by_type(self, placeholder_type: str) -> Optional[PlaceholderSlot]:
        """Get first placeholder matching the given type"""
        for ph in self.placeholders:
            if ph.type == placeholder_type:
                return ph
        return None
    
    def get_placeholder_by_idx(self, idx: int) -> Optional[PlaceholderSlot]:
        """Get placeholder by its index"""
        for ph in self.placeholders:
            if ph.idx == idx:
                return ph
        return None
    
    def has_placeholder_type(self, placeholder_type: str) -> bool:
        """Check if layout has a placeholder of the given type"""
        return any(ph.type == placeholder_type for ph in self.placeholders)


# ============================================================================
# THEME MODELS
# ============================================================================

class ThemeColor(BaseModel):
    """Theme color definition"""
    name: str = Field(..., description="Color name/role")
    hex_value: str = Field(..., description="Color value in hex")


class ColorScheme(BaseModel):
    """Complete color scheme extracted from template"""
    primary: Optional[str] = Field(None, description="Primary brand color")
    secondary: Optional[str] = Field(None, description="Secondary brand color")
    accent: Optional[str] = Field(None, description="Accent color")
    text: Dict[str, str] = Field(
        default_factory=lambda: {"dark": "0D2026", "light": "FFFCEC", "muted": "666666"},
        description="Text colors"
    )
    elements: Dict[str, str] = Field(
        default_factory=dict,
        description="Element-specific colors (separator_line, page_number_bg, etc.)"
    )
    four_box: Optional[Dict[str, str]] = Field(None, description="Four-box layout colors")
    
    class Config:
        extra = "allow"


class FontDef(BaseModel):
    """Font definition for an element"""
    name_en: Optional[str] = Field(None, description="English font name")
    name_ar: Optional[str] = Field(None, description="Arabic font name")
    name: Optional[str] = Field(None, description="Default font name")
    size: int = Field(default=18, description="Font size in points")
    bold: bool = Field(default=False, description="Bold text")
    color: Optional[str] = Field(None, description="Font color (hex)")
    
    class Config:
        extra = "allow"


class FontScheme(BaseModel):
    """Complete font scheme extracted from template"""
    title_slide: Dict[str, FontDef] = Field(default_factory=dict, description="Title slide fonts")
    section_header: Dict[str, FontDef] = Field(default_factory=dict, description="Section header fonts")
    content: Dict[str, FontDef] = Field(default_factory=dict, description="Content slide fonts")
    four_box: Optional[Dict[str, FontDef]] = Field(None, description="Four-box layout fonts")
    page_number: Optional[FontDef] = Field(None, description="Page number font")
    
    class Config:
        extra = "allow"


class IconDef(BaseModel):
    """Icon definition"""
    path: str = Field(..., description="Relative path to icon file")
    width: float = Field(default=0.5, description="Icon width in inches")
    height: float = Field(default=0.5, description="Icon height in inches")
    
    class Config:
        extra = "allow"


class IconScheme(BaseModel):
    """Icon definitions extracted from template"""
    default_title: Optional[str] = Field(None, description="Default icon for content titles")
    default_section: Optional[str] = Field(None, description="Default icon for section headers")
    agenda_items: List[str] = Field(default_factory=list, description="Icons for agenda items")
    box_icons: List[str] = Field(default_factory=list, description="Icons for four-box layouts")
    all_icons: Dict[str, IconDef] = Field(default_factory=dict, description="All extracted icons")
    
    class Config:
        extra = "allow"


class ThemeDefinition(BaseModel):
    """Theme definition extracted from template"""
    colors: List[ThemeColor] = Field(default_factory=list, description="Theme colors")
    fonts: Dict[str, str] = Field(
        default_factory=dict,
        description="Font mappings (heading, body, fallback, etc.)"
    )
    
    class Config:
        extra = "allow"
    
    def get_color(self, name: str, default: str = "#000000") -> str:
        """Get color by name with fallback"""
        for color in self.colors:
            if color.name == name:
                return color.hex_value
        return default
    
    def get_font(self, role: str, default: str = "Arial") -> str:
        """Get font by role with fallback"""
        return self.fonts.get(role, default)


# ============================================================================
# SLIDE DIMENSIONS
# ============================================================================

class SlideDimensions(BaseModel):
    """Slide dimensions"""
    width: float = Field(..., description="Width in inches")
    height: float = Field(..., description="Height in inches")
    units: str = Field(default="inches", description="Unit of measurement")
    aspect_ratio: Optional[str] = Field(None, description="Aspect ratio (e.g., 16:9)")


# ============================================================================
# LANGUAGE CONFIGURATION
# ============================================================================

class LanguageConfig(BaseModel):
    """Language-specific configuration"""
    rtl: bool = Field(default=False, description="Right-to-left text direction")
    alignment: Literal["left", "center", "right"] = Field(
        default="left", description="Default text alignment"
    )
    default_font: Optional[str] = Field(None, description="Default font for this language")
    heading_font: Optional[str] = Field(None, description="Heading font for this language")


class LanguageSettings(BaseModel):
    """Multi-language settings"""
    default: str = Field(default="en", description="Default language code")
    supported: List[str] = Field(default=["en"], description="Supported language codes")
    configurations: Dict[str, LanguageConfig] = Field(
        default_factory=dict, description="Per-language configurations"
    )


# ============================================================================
# ANALYSIS METADATA
# ============================================================================

class AnalysisMetadata(BaseModel):
    """Metadata about the template analysis"""
    source_file: str = Field(..., description="Original template filename")
    layout_count: int = Field(..., description="Number of layouts found")
    master_count: int = Field(default=1, description="Number of slide masters")
    analyzed_version: str = Field(default="1.0.0", description="Analyzer version")
    analyzed_at: Optional[str] = Field(None, description="Analysis timestamp")
    
    class Config:
        extra = "allow"


# ============================================================================
# MAIN MANIFEST MODEL
# ============================================================================

class TemplateManifest(BaseModel):
    """
    Complete template manifest for dynamic PPT generation.
    
    This model represents the auto-generated configuration that captures
    all layout information from a PPTX template file.
    """
    # Identity
    template_id: str = Field(..., description="Unique template identifier")
    template_name: str = Field(..., description="Human-readable template name")
    version: str = Field(default="1.0.0", description="Manifest version")
    template_mode: Literal["native_auto", "native", "json_only"] = Field(
        default="native_auto", description="Template processing mode"
    )
    
    # Dimensions
    slide_dimensions: SlideDimensions = Field(..., description="Slide dimensions")
    
    # Layouts
    layouts: Dict[str, LayoutDefinition] = Field(
        default_factory=dict, description="Layout definitions keyed by normalized name"
    )
    
    # Content type to layout mapping
    content_type_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="Maps content types (title, content, section, etc.) to layout keys"
    )
    
    # Theme
    theme: ThemeDefinition = Field(
        default_factory=ThemeDefinition, description="Extracted theme"
    )
    
    # Colors extracted from template
    colors: Optional[ColorScheme] = Field(
        None, description="Color scheme extracted from template"
    )
    
    # Fonts extracted from template
    fonts: Optional[FontScheme] = Field(
        None, description="Font scheme extracted from template"
    )
    
    # Icons extracted from template
    icons: Optional[IconScheme] = Field(
        None, description="Icons extracted from template"
    )
    
    # Language settings
    language_settings: Optional[LanguageSettings] = Field(
        None, description="Multi-language configuration"
    )
    
    # Background images (optional override)
    background_images: Optional[Dict[str, str]] = Field(
        None, description="Optional background image overrides per layout type"
    )
    
    # Element positions
    element_positions: Optional[Dict[str, Any]] = Field(
        None, description="Element positions for each slide type"
    )
    
    # Page numbering
    page_numbering: Optional[Dict[str, Any]] = Field(
        None, description="Page numbering configuration"
    )
    
    # Metadata
    analysis_metadata: Optional[AnalysisMetadata] = Field(
        None, description="Analysis metadata"
    )
    
    class Config:
        extra = "allow"
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def get_layout_for_content(self, content_type: str) -> Optional[LayoutDefinition]:
        """
        Get the appropriate layout for a content type.
        
        Args:
            content_type: Type of content (title, content, section, bullets, etc.)
            
        Returns:
            LayoutDefinition if found, None otherwise
        """
        # Check direct mapping
        layout_key = self.content_type_mapping.get(content_type)
        if layout_key and layout_key in self.layouts:
            return self.layouts[layout_key]
        
        # Fallback mappings
        fallbacks = {
            "bullets": ["content", "title_and_content"],
            "paragraph": ["content", "title_and_content"],
            "table": ["content", "title_and_content"],
            "chart": ["content", "title_and_content"],
            "agenda": ["content", "title_and_content"],
            "section_header": ["section", "title_only"],
        }
        
        for fallback in fallbacks.get(content_type, []):
            fallback_key = self.content_type_mapping.get(fallback)
            if fallback_key and fallback_key in self.layouts:
                return self.layouts[fallback_key]
        
        # Last resort: return first layout with body placeholder
        for layout in self.layouts.values():
            if layout.has_placeholder_type("body"):
                return layout
        
        return None
    
    def get_layout_by_key(self, layout_key: str) -> Optional[LayoutDefinition]:
        """Get layout by its key"""
        return self.layouts.get(layout_key)
    
    def get_layout_by_index(self, index: int) -> Optional[LayoutDefinition]:
        """Get layout by its index"""
        for layout in self.layouts.values():
            if layout.index == index:
                return layout
        return None
    
    def list_layout_keys(self) -> List[str]:
        """Get list of all layout keys"""
        return list(self.layouts.keys())
    
    def get_background_for_content(self, content_type: str) -> Optional[str]:
        """Get background image path for content type"""
        if not self.background_images:
            return None
        
        # Direct match
        if content_type in self.background_images:
            return self.background_images[content_type]
        
        # Try layout key
        layout_key = self.content_type_mapping.get(content_type)
        if layout_key and layout_key in self.background_images:
            return self.background_images[layout_key]
        
        return None


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def create_manifest_from_dict(data: Dict) -> TemplateManifest:
    """Create TemplateManifest from dictionary"""
    return TemplateManifest(**data)


def create_manifest_from_json(json_path: str) -> TemplateManifest:
    """Load TemplateManifest from JSON file"""
    import json
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return create_manifest_from_dict(data)
