from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# ---------- Atomic pieces ----------

class BulletPoint(BaseModel):
    text: str = Field(default="", description="One concise heading for the bullet")
    sub_bullets: Optional[List[str]] = Field(
        default=None, description="2–3 short supporting points"
    )

    class Config:
        extra = "ignore"


class ChartData(BaseModel):
    chart_type: Literal["bar", "column", "line", "pie"] = "column"
    title: Optional[str] = None
    labels: List[str] = Field(default_factory=list)
    values: List[float] = Field(default_factory=list)
    series_name: Optional[str] = None

    class Config:
        extra = "ignore"


class TableData(BaseModel):
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)

    class Config:
        extra = "ignore"


# ---------- Slide ----------

class SlideContent(BaseModel):
    # Layout & title
    layout_type: str = Field(
        default="content",
        description="One of: title | content | section | two_column (flexible for future layouts)"
    )
    title: str = Field(default="", description="Slide title, <= 60 chars")

    # Icon
    icon_name: Optional[str] = Field(default=None, description="Icon identifier (e.g., briefcase)")

    # Content blocks
    content: Optional[str] = None
    bullets: Optional[List[BulletPoint]] = None
    chart_data: Optional[ChartData] = None
    table_data: Optional[TableData] = None
    left_content: Optional[List[str]] = None   # for two_column
    right_content: Optional[List[str]] = None  # for two_column

    # Image intent (LLM hints; generator still gates)
    needs_image: Optional[bool] = Field(
        default=None,
        description="Model hint that this slide benefits from an image (generator decides finally)."
    )
    image_layout: Optional[Literal["right", "left", "fullbleed", "top"]] = Field(
        default=None, description="Preferred placement when image is used."
    )
    image_caption: Optional[str] = Field(default=None, description="Optional short caption (<= 8 words).")

    class Config:
        extra = "ignore"


# ---------- Deck ----------

class PresentationData(BaseModel):
    title: str = Field(default="Untitled Presentation")
    subtitle: Optional[str] = None
    author: Optional[str] = None
    slides: List[SlideContent] = Field(default_factory=list)

    class Config:
        extra = "ignore"
