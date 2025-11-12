from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal
from enum import Enum


class ColorScheme(BaseModel):
    """Color scheme configuration"""
    primary: str = Field(..., description="Primary brand color (hex)")
    primary_dark: Optional[str] = None
    primary_light: Optional[str] = None
    secondary: str = Field(..., description="Secondary accent color")
    secondary_dark: Optional[str] = None
    secondary_light: Optional[str] = None
    accent: str = Field(..., description="Accent color for highlights")
    background: str = "#FFFFFF"
    background_alt: Optional[str] = None
    text_primary: str = "#1F2937"
    text_secondary: str = "#6B7280"
    text_muted: Optional[str] = None
    border: Optional[str] = None


class GradientConfig(BaseModel):
    """Gradient configuration"""
    start: str = Field(..., description="Start color (hex)")
    end: str = Field(..., description="End color (hex)")
    direction: str = Field(default="135deg", description="Gradient direction")


class TypographyConfig(BaseModel):
    """Typography configuration"""
    font_families: Dict[str, str] = Field(
        default={
            "primary": "Calibri",
            "secondary": "Arial",
            "monospace": "Consolas"
        }
    )
    font_sizes: Dict[str, int] = Field(
        default={
            "title": 44,
            "heading_1": 36,
            "heading_2": 32,
            "body": 18,
            "caption": 14
        }
    )
    font_weights: Optional[Dict[str, int]] = None
    line_heights: Optional[Dict[str, float]] = None


class SpacingConfig(BaseModel):
    """Spacing configuration"""
    slide_padding: Dict[str, float] = Field(
        default={
            "top": 0.5,
            "right": 0.5,
            "bottom": 0.5,
            "left": 0.5
        }
    )
    element_spacing: Dict[str, float] = Field(
        default={
            "tight": 0.1,
            "normal": 0.2,
            "relaxed": 0.3
        }
    )


class IconConfig(BaseModel):
    """Icon configuration"""
    default_size: int = 32
    sizes: Dict[str, int] = Field(
        default={
            "small": 24,
            "medium": 32,
            "large": 48,
            "xlarge": 64
        }
    )
    default_color: str = "primary"


class ElementPosition(BaseModel):
    """Position of an element on slide"""
    left: float = Field(..., description="Left position in inches")
    top: float = Field(..., description="Top position in inches")


class ElementSize(BaseModel):
    """Size of an element"""
    width: float = Field(..., description="Width in inches")
    height: float = Field(..., description="Height in inches")


class LayoutElement(BaseModel):
    """Individual element in a slide layout"""
    type: Literal["icon", "text", "text_bullets", "image", "shape"] = Field(
        ..., description="Type of element"
    )
    placeholder: Optional[str] = Field(
        None, description="Placeholder name (e.g., 'title', 'content')"
    )
    position: ElementPosition
    size: Optional[ElementSize] = None
    font_size: Optional[int] = None
    color: Optional[str] = None
    alignment: Optional[Literal["left", "center", "right"]] = "left"
    bold: bool = False
    bullet_style: Optional[str] = None


class SlideLayout(BaseModel):
    """Complete slide layout definition"""
    layout_type: Literal["title", "content", "section", "two_column", "blank"]
    elements: List[LayoutElement]


class TemplateTheme(BaseModel):
    """Complete theme configuration"""
    theme_id: str
    name: str
    description: Optional[str] = None
    version: str = "1.0.0"
    colors: ColorScheme
    gradients: Optional[Dict[str, GradientConfig]] = None
    typography: TypographyConfig
    spacing: SpacingConfig
    icons: IconConfig


class TemplateConfig(BaseModel):
    """Complete template configuration"""
    template_id: str = Field(..., description="Unique template identifier")
    name: str = Field(..., description="Template display name")
    description: Optional[str] = None
    version: str = "1.0.0"
    theme: ColorScheme
    typography: TypographyConfig
    slide_dimensions: Dict[str, float] = Field(
        default={
            "width": 10,
            "height": 5.625,
            "unit": "inches"
        }
    )
    icon_config: IconConfig


class TemplateLayouts(BaseModel):
    """Collection of slide layouts"""
    title_slide: SlideLayout
    content_slide: SlideLayout
    section_header: SlideLayout
    two_column: SlideLayout
    blank: Optional[SlideLayout] = None


class FullTemplate(BaseModel):
    """Complete template with config and layouts"""
    config: TemplateConfig
    layouts: TemplateLayouts


class TemplateMetadata(BaseModel):
    """Template metadata for listing/browsing"""
    template_id: str
    name: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    author: Optional[str] = None
    created_at: Optional[str] = None
    is_premium: bool = False


class TemplateCustomization(BaseModel):
    """User customization options for templates"""
    template_id: str
    custom_colors: Optional[ColorScheme] = None
    custom_fonts: Optional[Dict[str, str]] = None
    logo_url: Optional[str] = None
    watermark_text: Optional[str] = None


# Enums
class LayoutType(str, Enum):
    """Available layout types"""
    TITLE = "title"
    CONTENT = "content"
    SECTION = "section"
    TWO_COLUMN = "two_column"
    BLANK = "blank"


class ElementType(str, Enum):
    """Available element types"""
    ICON = "icon"
    TEXT = "text"
    TEXT_BULLETS = "text_bullets"
    IMAGE = "image"
    SHAPE = "shape"
    CHART = "chart"


class AlignmentType(str, Enum):
    """Text alignment options"""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"
