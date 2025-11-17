from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal, Union
from enum import Enum


# ============================================================================
# ENUMS - Define first for use in other models
# ============================================================================

class LayoutType(str, Enum):
    """Available layout types"""
    TITLE = "title"
    CONTENT = "content"
    SECTION = "section"
    TWO_COLUMN = "two_column"
    BLANK = "blank"
    DATA_VISUALIZATION = "data_visualization"
    ICON_COLUMNS = "icon_columns"
    GRID = "grid"


class ElementType(str, Enum):
    """Available element types"""
    ICON = "icon"
    TEXT = "text"
    TEXT_BULLETS = "text_bullets"
    IMAGE = "image"
    SHAPE = "shape"
    CHART = "chart"
    TABLE = "table"
    LOGO = "logo"
    PAGE_NUMBER = "page_number"


class ShapeType(str, Enum):
    """Shape types"""
    RECTANGLE = "rectangle"
    ROUNDED_RECTANGLE = "rounded_rectangle"
    CIRCLE = "circle"
    DIAMOND = "diamond"
    CUSTOM = "custom"


class AlignmentType(str, Enum):
    """Text alignment options"""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"


class BackgroundType(str, Enum):
    """Background types"""
    SOLID = "solid"
    GRADIENT = "gradient"
    IMAGE = "image"
    SPLIT = "split"
    INHERITED = "inherited"


# ============================================================================
# COLOR AND THEME MODELS
# ============================================================================

class ColorScheme(BaseModel):
    """Color scheme configuration for Arweqah template"""
    # Primary colors
    primary: str = Field(..., description="Primary brand color - Dark Teal (#01415C)")
    primary_dark: str = Field(..., description="Very dark teal (#0D2026)")
    primary_light: str = Field(..., description="Medium teal (#40697A)")
    
    # Secondary colors
    secondary: str = Field(..., description="Sage green (#84BA93)")
    secondary_dark: Optional[str] = Field(None, description="Darker sage green")
    secondary_light: Optional[str] = Field(None, description="Mint green (#B1D8BE)")
    
    # Accent colors
    accent: str = Field(..., description="Rust orange (#C26325)")
    accent_dark: Optional[str] = Field(None, description="Dark rust orange")
    accent_light: Optional[str] = Field(None, description="Light rust orange")
    accent_alt: Optional[str] = Field(None, description="Golden yellow (#F9D462)")
    accent_green: Optional[str] = Field(None, description="Mint green for accents")
    
    # Background colors
    background: str = Field(default="#FFFDED", description="Master background - cream")
    background_alt: str = Field(default="#FFFCEC", description="Ivory background")
    background_gray: Optional[str] = Field(None, description="Warm taupe (#C6C3BE)")
    background_beige: Optional[str] = Field(None, description="Off-white beige (#F7F4E7)")
    background_card: Optional[str] = None
    
    # Text colors
    text_primary: str = Field(default="#0D2026", description="Very dark teal for text")
    text_secondary: str = Field(default="#40697A", description="Medium teal for secondary text")
    text_muted: Optional[str] = Field(None, description="Muted text color")
    text_inverse: str = Field(default="#FFFCEC", description="Cream for dark backgrounds")
    text_light: Optional[str] = None
    
    # Border and UI colors
    border: Optional[str] = Field(None, description="Sage green border (#84BA93)")
    border_light: Optional[str] = None
    border_dark: Optional[str] = None
    
    # Status colors
    success: Optional[str] = Field(None, description="Success color")
    warning: Optional[str] = Field(None, description="Warning color")
    error: Optional[str] = Field(None, description="Error color")
    info: Optional[str] = Field(None, description="Info color")
    
    # Chart colors
    chart_colors: Optional[Dict[str, str]] = Field(
        None,
        description="Named chart colors (color_1, color_2, etc.)"
    )


class GradientConfig(BaseModel):
    """Gradient configuration"""
    start: str = Field(..., description="Start color (hex)")
    end: str = Field(..., description="End color (hex)")
    angle: int = Field(default=135, description="Gradient angle in degrees")
    direction: Optional[str] = Field(None, description="CSS-style direction (deprecated)")


# ============================================================================
# TYPOGRAPHY MODELS
# ============================================================================

class TypographyConfig(BaseModel):
    """Typography configuration with bilingual support"""
    # Font families
    font_families: Dict[str, str] = Field(
        default={
            "primary": "Tajawal",
            "heading": "TajawalMedium",
            "body": "Tajawal",
            "bold": "TajawalExtraBold",
            "english_primary": "Montserrat SemiBold",
            "english_body": "Montserrat SemiBold",
            "fallback": "Arial"
        },
        description="Font families for different use cases"
    )
    
    # Font sizes
    font_sizes: Dict[str, int] = Field(
        default={
            "title": 44,
            "heading_1": 38,
            "heading_2": 32,
            "heading_3": 28,
            "subheading": 24,
            "body": 18,
            "body_small": 16,
            "caption": 14,
            "tiny": 12,
            "table_header": 16,
            "table_body": 14
        },
        description="Font sizes in points"
    )
    
    # Font weights
    font_weights: Dict[str, int] = Field(
        default={
            "light": 300,
            "regular": 400,
            "medium": 500,
            "semibold": 600,
            "bold": 700,
            "extrabold": 800
        }
    )
    
    # Line heights
    line_heights: Dict[str, float] = Field(
        default={
            "tight": 1.1,
            "normal": 1.2,
            "relaxed": 1.4,
            "loose": 1.6
        }
    )
    
    # RTL and bilingual support
    rtl_support: bool = Field(default=True, description="Right-to-left text support")
    bilingual_mode: bool = Field(default=True, description="Bilingual Arabic/English support")


# ============================================================================
# SPACING AND LAYOUT MODELS
# ============================================================================

class SpacingConfig(BaseModel):
    """Spacing configuration"""
    slide_padding: Dict[str, float] = Field(
        default={
            "top": 0.6,
            "right": 0.6,
            "bottom": 0.8,
            "left": 0.6
        },
        description="Slide padding in inches"
    )
    
    content_margins: Dict[str, float] = Field(
        default={
            "top": 1.0,
            "left": 0.6,
            "right": 0.6,
            "bottom": 0.8
        },
        description="Content area margins"
    )
    
    element_spacing: Dict[str, float] = Field(
        default={
            "tight": 0.1,
            "normal": 0.2,
            "relaxed": 0.3,
            "loose": 0.5
        },
        description="Spacing between elements"
    )
    
    sidebar_width: float = Field(default=0, description="Sidebar width if applicable")
    section_spacing: float = Field(default=0.3, description="Section spacing")


# ============================================================================
# ICON MODELS
# ============================================================================

class IconConfig(BaseModel):
    """Icon configuration"""
    default_size: int = Field(default=40, description="Default icon size in points")
    
    sizes: Dict[str, int] = Field(
        default={
            "tiny": 24,
            "small": 32,
            "medium": 40,
            "large": 60,
            "xlarge": 80,
            "huge": 90
        },
        description="Named icon sizes"
    )
    
    default_color: str = Field(default="secondary", description="Default icon color reference")
    
    # Icon keyword mapping for intelligent selection
    keyword_to_icon_map: Optional[Dict[str, str]] = Field(
        None,
        description="Map of keywords to icon names"
    )
    
    intelligent_mapping: Optional[Dict[str, List[str]]] = Field(
        None,
        description="Intelligent keyword groups for icon selection"
    )


# ============================================================================
# ELEMENT MODELS
# ============================================================================

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
    type: ElementType = Field(..., description="Type of element")
    
    # Identification
    placeholder: Optional[str] = Field(
        None,
        description="Placeholder name (e.g., 'title', 'content', 'logo')"
    )
    
    # Positioning
    position: ElementPosition
    size: Optional[ElementSize] = None
    
    # Visual properties
    font: Optional[str] = Field(None, description="Font family")
    font_size: Optional[int] = Field(None, description="Font size in points")
    color: Optional[str] = Field(None, description="Text or fill color (hex)")
    fill_color: Optional[str] = Field(None, description="Background fill color")
    border_color: Optional[str] = Field(None, description="Border color")
    border_width: Optional[int] = Field(None, description="Border width in points")
    border_style: Optional[str] = Field(None, description="Border style (solid, dashed, etc.)")
    
    # Text properties
    alignment: Optional[AlignmentType] = Field(default="left", description="Text alignment")
    bold: bool = Field(default=False, description="Bold text")
    italic: bool = Field(default=False, description="Italic text")
    underline: bool = Field(default=False, description="Underline text")
    
    # Bullet properties
    bullet_style: Optional[str] = Field(None, description="Bullet point style")
    bullet_color: Optional[str] = Field(None, description="Bullet point color")
    line_spacing: Optional[float] = Field(None, description="Line spacing multiplier")
    
    # Shape properties
    shape_type: Optional[ShapeType] = Field(None, description="Shape type if element is shape")
    corner_radius: Optional[float] = Field(None, description="Corner radius for rounded shapes")
    opacity: Optional[float] = Field(default=1.0, description="Opacity (0.0 to 1.0)")
    
    # Layout properties
    z_index: int = Field(default=1, description="Stacking order (higher = front)")
    rtl_support: bool = Field(default=False, description="RTL text support for this element")
    optional: bool = Field(default=False, description="Whether element is optional")
    
    # Metadata
    metadata: Optional[str] = Field(None, description="Additional metadata or description")


# ============================================================================
# BACKGROUND MODELS
# ============================================================================

class BackgroundConfig(BaseModel):
    """Background configuration for a layout"""
    type: BackgroundType = Field(..., description="Background type")
    color: Optional[str] = Field(None, description="Solid color (hex)")
    gradient: Optional[GradientConfig] = Field(None, description="Gradient configuration")
    image_path: Optional[str] = Field(None, description="Path to background image")
    opacity: Optional[float] = Field(default=1.0, description="Background opacity")


class SplitBackgroundConfig(BaseModel):
    """Split background configuration (e.g., for title slide)"""
    type: Literal["split"] = "split"
    left_section: BackgroundConfig
    right_section: BackgroundConfig
    left_width_ratio: float = Field(default=0.35, description="Width ratio of left section")


# ============================================================================
# LAYOUT MODELS
# ============================================================================

class ContentStructure(BaseModel):
    """Content structure metadata for a layout"""
    title: Optional[Dict[str, Union[str, int, bool]]] = Field(
        None,
        description="Title specifications"
    )
    content: Optional[Dict[str, Union[str, int, bool, List]]] = Field(
        None,
        description="Content area specifications"
    )
    left_column: Optional[Dict[str, Union[str, int, float]]] = None
    right_column: Optional[Dict[str, Union[str, int, float]]] = None


class TableSupport(BaseModel):
    """Table support metadata"""
    enabled: bool = Field(default=True, description="Whether tables are supported")
    max_columns: int = Field(default=6, description="Maximum table columns")
    max_rows: int = Field(default=8, description="Maximum table rows")
    positioning: Optional[str] = Field(None, description="Positioning guidelines")
    width: Optional[str] = Field(None, description="Width specifications")
    styling: Optional[str] = Field(None, description="Styling recommendations")
    note: Optional[str] = Field(None, description="Additional notes")


class ChartSupport(BaseModel):
    """Chart support metadata"""
    enabled: bool = Field(default=True, description="Whether charts are supported")
    max_size: Optional[str] = Field(None, description="Maximum chart size")
    ideal_for: Optional[str] = Field(None, description="Ideal chart types")


class LayoutConstraints(BaseModel):
    """Layout constraints and positioning data"""
    content_area: Optional[Dict[str, float]] = Field(
        None,
        description="Content area dimensions (left, top, width, height)"
    )
    title_area: Optional[Dict[str, float]] = Field(
        None,
        description="Title area dimensions"
    )
    column_spacing: Optional[float] = None
    text_only: Optional[bool] = None
    no_bullet_points: Optional[bool] = None
    no_images: Optional[bool] = None
    placeholder_box: Optional[Dict[str, Union[str, float]]] = None
    none: Optional[bool] = None
    full_slide_available: Optional[Dict[str, float]] = None
    minimal_constraints: Optional[bool] = None
    recommended_margins: Optional[Dict[str, float]] = None
    text_color_recommendation: Optional[str] = None


class LayoutMetadata(BaseModel):
    """Comprehensive metadata for a layout"""
    suitable_for: List[str] = Field(
        default_factory=list,
        description="List of use cases this layout is suitable for"
    )
    content_structure: Optional[ContentStructure] = Field(
        None,
        description="Content structure specifications"
    )
    table_support: Optional[TableSupport] = Field(
        None,
        description="Table support information"
    )
    chart_support: Optional[ChartSupport] = Field(
        None,
        description="Chart support information"
    )
    visual_elements: List[str] = Field(
        default_factory=list,
        description="Description of visual elements"
    )
    constraints: Optional[LayoutConstraints] = Field(
        None,
        description="Layout constraints and positioning"
    )


class SlideLayout(BaseModel):
    """Complete slide layout definition"""
    layout_type: LayoutType = Field(..., description="Type of layout")
    layout_name: str = Field(..., description="Display name of layout")
    background: str = Field(..., description="Background reference key")
    description: str = Field(..., description="Layout description")
    
    # Metadata
    metadata: Optional[LayoutMetadata] = Field(
        None,
        description="Comprehensive layout metadata"
    )
    
    # Elements
    elements: List[LayoutElement] = Field(
        default_factory=list,
        description="List of elements in this layout"
    )


# ============================================================================
# TABLE AND CHART MODELS
# ============================================================================

class TableConfig(BaseModel):
    """Table configuration"""
    rounded_corners: bool = Field(default=False, description="Use rounded corners")
    corner_radius: int = Field(default=0, description="Corner radius in EMUs")
    max_rows_per_slide: int = Field(default=8, description="Max rows per slide")
    cell_padding: float = Field(default=0.12, description="Cell padding in inches")
    border_width: int = Field(default=1, description="Border width in points")
    header_color: str = Field(..., description="Header background color")
    alternate_row_color: str = Field(..., description="Alternate row color")
    border_color: str = Field(..., description="Border color")
    text_alignment: Optional[str] = Field(default="right", description="Text alignment")
    rtl_support: bool = Field(default=True, description="RTL support")


class ChartConfig(BaseModel):
    """Chart configuration"""
    bar_colors: List[str] = Field(..., description="Bar chart colors")
    pie_colors: List[str] = Field(..., description="Pie chart colors")
    line_colors: List[str] = Field(..., description="Line chart colors")
    font: str = Field(..., description="Chart font")
    font_english: Optional[str] = Field(None, description="English chart font")
    font_size: int = Field(default=14, description="Chart font size")
    rtl_support: bool = Field(default=True, description="RTL support")


# ============================================================================
# TEMPLATE MODELS
# ============================================================================

class SlideDimensions(BaseModel):
    """Slide dimensions"""
    width: float = Field(..., description="Width in inches")
    height: float = Field(..., description="Height in inches")
    unit: str = Field(default="inches", description="Unit of measurement")
    width_emu: Optional[int] = Field(None, description="Width in EMUs")
    height_emu: Optional[int] = Field(None, description="Height in EMUs")
    aspect_ratio: str = Field(default="16:9", description="Aspect ratio")


class ContentLimits(BaseModel):
    """Content limits and constraints"""
    max_bullets_per_slide: int = Field(default=5, description="Max bullets per slide")
    max_title_length: int = Field(default=80, description="Max title characters")
    max_bullet_length: int = Field(default=120, description="Max bullet characters")
    max_sub_bullets: int = Field(default=3, description="Max sub-bullets per bullet")
    max_table_rows: int = Field(default=8, description="Max table rows")
    max_table_cols: int = Field(default=6, description="Max table columns")
    max_chart_points: Optional[int] = Field(default=8, description="Max chart data points")
    auto_pagination: bool = Field(default=True, description="Auto-paginate overflow content")
    rtl_text_support: bool = Field(default=True, description="RTL text support")


class LocalizationConfig(BaseModel):
    """Localization configuration"""
    rtl_support: bool = Field(default=True, description="RTL support enabled")
    default_text_direction: str = Field(default="rtl", description="Default text direction")
    bilingual_mode: bool = Field(default=True, description="Bilingual mode enabled")
    arabic_fonts: List[str] = Field(default_factory=list, description="Arabic font list")
    english_fonts: List[str] = Field(default_factory=list, description="English font list")


class TemplateTheme(BaseModel):
    """Complete theme configuration"""
    theme_id: str = Field(..., description="Unique theme identifier")
    name: str = Field(..., description="Theme name")
    description: Optional[str] = Field(None, description="Theme description")
    version: str = Field(default="1.0.0", description="Theme version")
    
    # Core configuration
    colors: ColorScheme
    gradients: Optional[Dict[str, GradientConfig]] = None
    typography: TypographyConfig
    spacing: SpacingConfig
    icons: IconConfig
    
    # Additional configurations
    bullet_styles: Optional[Dict[str, Dict[str, Union[str, int, float]]]] = None
    chart_colors: Optional[List[str]] = None
    table_styles: Optional[Dict[str, Union[Dict, bool, int]]] = None
    image_config: Optional[Dict[str, Union[bool, str, float]]] = None
    content_limits: Optional[ContentLimits] = None
    pagination: Optional[Dict[str, Union[bool, str]]] = None
    localization: Optional[LocalizationConfig] = None


class TemplateConfig(BaseModel):
    """Complete template configuration"""
    template_id: str = Field(..., description="Unique template identifier")
    name: str = Field(..., description="Template display name")
    description: Optional[str] = Field(None, description="Template description")
    version: str = Field(default="1.0.0", description="Template version")
    
    # Core configuration
    theme: ColorScheme
    typography: TypographyConfig
    slide_dimensions: SlideDimensions
    icon_config: IconConfig
    
    # Background definitions
    backgrounds: Optional[Dict[str, Union[BackgroundConfig, Dict]]] = Field(
        None,
        description="Background definitions for different layout types"
    )
    
    # Additional configurations
    decorative_elements: Optional[Dict[str, Dict]] = None
    content_limits: Optional[ContentLimits] = None
    table_config: Optional[TableConfig] = None
    image_generation: Optional[Dict] = None
    ai_config: Optional[Dict[str, bool]] = None


class TemplateConstraints(BaseModel):
    """Template constraints"""
    table: TableConfig
    chart: ChartConfig
    layout: Dict[str, float] = Field(
        ...,
        description="Layout constraints (margins, heights, etc.)"
    )
    text: Optional[Dict[str, Union[float, str]]] = Field(
        None,
        description="Text-specific constraints"
    )
    spacing: Optional[Dict[str, float]] = Field(
        None,
        description="Spacing constraints"
    )


class TemplateLayouts(BaseModel):
    """Collection of slide layouts"""
    # Core layouts (required)
    title_slide_1: SlideLayout
    title_and_content: SlideLayout
    section_header_1: SlideLayout
    section_header_2: SlideLayout
    section_header_3: SlideLayout
    
    # Optional layouts
    two_content: Optional[SlideLayout] = None
    title_only: Optional[SlideLayout] = None
    blank_dark: Optional[SlideLayout] = None
    blank_light: Optional[SlideLayout] = None
    blank_gray: Optional[SlideLayout] = None
    custom_layout: Optional[SlideLayout] = None
    
    # Special layouts
    data_visualization: Optional[SlideLayout] = None
    icon_columns: Optional[SlideLayout] = None
    four_box_grid: Optional[SlideLayout] = None
    circular_progress: Optional[SlideLayout] = None
    content_with_image: Optional[SlideLayout] = None


class FullTemplate(BaseModel):
    """Complete template with all configurations"""
    config: TemplateConfig
    theme: TemplateTheme
    constraints: TemplateConstraints
    layouts: Dict[str, SlideLayout] = Field(
        ...,
        description="Dictionary of all layouts (layout_key -> SlideLayout)"
    )


# ============================================================================
# TEMPLATE METADATA AND CUSTOMIZATION
# ============================================================================

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
    updated_at: Optional[str] = None
    is_premium: bool = False
    is_bilingual: bool = False
    supports_rtl: bool = False
    aspect_ratio: str = "16:9"
    layout_count: int = 0


class TemplateCustomization(BaseModel):
    """User customization options for templates"""
    template_id: str
    custom_colors: Optional[ColorScheme] = None
    custom_fonts: Optional[Dict[str, str]] = None
    logo_url: Optional[str] = None
    logo_position: Optional[ElementPosition] = None
    logo_size: Optional[ElementSize] = None
    watermark_text: Optional[str] = None
    company_name: Optional[str] = None
    footer_text: Optional[str] = None
    show_page_numbers: bool = True
    page_number_style: Optional[str] = None
