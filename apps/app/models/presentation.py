from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# ---------- Atomic pieces ----------

class BulletPoint(BaseModel):
    """Single bullet point with optional sub-bullets"""
    text: str = Field(default="", description="One concise heading for the bullet")
    sub_bullets: Optional[List[str]] = Field(
        default=None, 
        description="2–3 short supporting points"
    )

    class Config:
        extra = "ignore"


class ChartSeries(BaseModel):
    """Data series for charts (for multiple data sets)"""
    name: str = Field(..., description="Series name (e.g., 'Revenue', 'Duration')")
    values: List[float] = Field(..., description="Numeric values for the series")

    class Config:
        extra = "ignore"


class ChartData(BaseModel):
    """Chart/graph data - Enhanced with axis labels"""
    chart_type: Literal["bar", "column", "line", "pie"] = Field(
        default="column",
        description="Type of chart to create"
    )
    title: Optional[str] = Field(None, description="Chart title")
    
    # For single series (backward compatible)
    labels: Optional[List[str]] = Field(default=None, description="X-axis labels (deprecated, use categories)")
    values: Optional[List[float]] = Field(default=None, description="Y-axis values (deprecated, use series)")
    series_name: Optional[str] = Field(None, description="Series name (deprecated)")
    
    # New multi-series format
    categories: Optional[List[str]] = Field(default=None, description="X-axis labels / categories")
    series: Optional[List[ChartSeries]] = Field(default=None, description="Data series to plot")
    
    # NEW: Axis labels and units
    x_axis_label: Optional[str] = Field(None, description="X-axis label (e.g., 'Deliverables', 'Project Phases')")
    y_axis_label: Optional[str] = Field(None, description="Y-axis label (e.g., 'Duration', 'Cost', 'Percentage')")
    unit: Optional[str] = Field(None, description="Unit of measurement (e.g., 'Days', 'Months', 'Weeks', '%', '$')")

    class Config:
        extra = "ignore"

    
    def get_categories(self) -> List[str]:
        """Get categories (backward compatible)"""
        return self.categories or self.labels or []
    
    def get_series(self) -> List[ChartSeries]:
        """Get series (backward compatible)"""
        if self.series:
            return self.series
        elif self.values:
            # Convert old format to new
            return [ChartSeries(
                name=self.series_name or "Values",
                values=self.values
            )]
        return []


class TableData(BaseModel):
    """Table data"""
    headers: List[str] = Field(default_factory=list, description="Column headers")
    rows: List[List[str]] = Field(default_factory=list, description="Table rows")

    class Config:
        extra = "ignore"


# ---------- Slide ----------

class SlideContent(BaseModel):
    """Single slide content"""
    # Layout & title
    layout_type: Literal["title", "content", "section", "two_column"] = Field(
        default="content",
        description="Slide layout type: title | content | section | two_column"
    )
    layout_hint: Optional[str] = Field(
        default=None,
        description="Optional template hint (e.g., paragraph, short_boxes, four_box_with_icons)"
    )
    title: str = Field(default="", description="Slide title, <= 100 chars")

    # Icon
    icon_name: Optional[str] = Field(
        default=None, 
        description="Icon identifier (e.g., briefcase, rocket-launch, target)"
    )

    # Content blocks (only one should be populated)
    content: Optional[str] = Field(None, description="Plain text content")
    bullets: Optional[List[BulletPoint]] = Field(None, description="Bullet points")
    chart_data: Optional[ChartData] = Field(None, description="Chart data")
    table_data: Optional[TableData] = Field(None, description="Table data")
    
    # Two-column layout
    left_content: Optional[List[str]] = Field(None, description="Left column content")
    right_content: Optional[List[str]] = Field(None, description="Right column content")

    # Image intent (LLM hints)
    needs_image: Optional[bool] = Field(
        default=False,
        description="Whether this slide should have an AI-generated image"
    )
    image_layout: Optional[Literal["right", "left", "fullbleed", "top"]] = Field(
        default="right", 
        description="Image placement when used"
    )
    image_caption: Optional[str] = Field(
        default=None, 
        description="Optional short caption (<= 8 words)"
    )

    class Config:
        extra = "ignore"


# ---------- Deck ----------

class PresentationData(BaseModel):
    """Complete presentation data"""
    title: str = Field(default="Untitled Presentation", description="Presentation title")
    subtitle: Optional[str] = Field(None, description="Presentation subtitle")
    author: Optional[str] = Field("Impetus Strategy", description="Author/company name")
    slides: List[SlideContent] = Field(default_factory=list, description="List of slides")

    class Config:
        extra = "ignore"
