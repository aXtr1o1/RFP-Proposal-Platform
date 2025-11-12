from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from typing import Dict, Tuple, Optional


class ChartService:
    """Service for creating native PowerPoint charts with modern styling"""
    
    def __init__(self, template_id: str = "standard"):
        self.template_id = template_id
    
    def add_native_chart(
        self,
        slide,
        chart_data: Dict,
        position: Dict,
        size: Dict,
        background_rgb: Optional[Tuple[int, int, int]] = None
    ):
        """Add native PowerPoint chart with clean styling"""
        try:
            chart_type = chart_data.get('chart_type', 'column')
            labels = chart_data.get('labels', [])
            values = chart_data.get('values', [])
            title = chart_data.get('title', '')
            
            if not labels or not values:
                print("Missing chart data")
                return None
            
            # Map chart types
            chart_type_map = {
                'column': XL_CHART_TYPE.COLUMN_CLUSTERED,
                'bar': XL_CHART_TYPE.BAR_CLUSTERED,
                'line': XL_CHART_TYPE.LINE_MARKERS,  # Line with markers
                'pie': XL_CHART_TYPE.PIE,
                'area': XL_CHART_TYPE.AREA
            }
            
            xl_chart_type = chart_type_map.get(chart_type, XL_CHART_TYPE.COLUMN_CLUSTERED)
            
            # Create chart data
            chart_data_obj = CategoryChartData()
            chart_data_obj.categories = labels
            
            # Add series
            series_name = chart_data.get('series_name', 'Monthly Active Users')
            chart_data_obj.add_series(series_name, values)
            
            # Add chart to slide
            x = Inches(position['left'])
            y = Inches(position['top'])
            cx = Inches(size['width'])
            cy = Inches(size['height'])
            
            graphic_frame = slide.shapes.add_chart(
                xl_chart_type, x, y, cx, cy, chart_data_obj
            )
            
            chart = graphic_frame.chart
            
            # Apply modern styling
            self._apply_modern_chart_style(chart, chart_type, background_rgb)
            
            # Add title if provided
            if title:
                chart.has_title = True
                chart.chart_title.text_frame.text = title
                chart.chart_title.text_frame.paragraphs[0].font.size = Pt(16)
                chart.chart_title.text_frame.paragraphs[0].font.bold = True
                chart.chart_title.text_frame.paragraphs[0].font.color.rgb = RGBColor(31, 41, 55)
            
            print(f"Native chart added: {title} ({chart_type})")
            return chart
            
        except Exception as e:
            print(f"Chart creation error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _apply_modern_chart_style(self, chart, chart_type: str, background_rgb: Optional[Tuple]):
        """Apply clean, modern styling to chart"""
        try:
            # Chart area background
            chart.chart_style = 2  # Clean style
            
            if background_rgb:
                chart.chart_area.fill.solid()
                chart.chart_area.fill.fore_color.rgb = RGBColor(*background_rgb)
            
            # Plot area - transparent or white
            chart.plot_area.fill.solid()
            chart.plot_area.fill.fore_color.rgb = RGBColor(255, 255, 255)
            
            # Legend positioning
            if chart.has_legend:
                chart.legend.position = XL_LEGEND_POSITION.BOTTOM
                chart.legend.font.size = Pt(10)
                chart.legend.font.color.rgb = RGBColor(107, 114, 128)
            
            # Series styling
            for series in chart.series:
                # Line charts - Blue line with markers
                if chart_type == 'line':
                    # Line color - Professional blue
                    series.format.line.color.rgb = RGBColor(37, 99, 235)  # Blue #2563EB
                    series.format.line.width = Pt(2.5)
                    
                    # Marker style
                    series.marker.style = 8  # Circle markers
                    series.marker.size = 7
                    series.marker.format.fill.solid()
                    series.marker.format.fill.fore_color.rgb = RGBColor(37, 99, 235)
                    series.marker.format.line.color.rgb = RGBColor(255, 255, 255)
                    series.marker.format.line.width = Pt(1.5)
                
                # Column/Bar charts - Blue gradient
                elif chart_type in ['column', 'bar']:
                    series.format.fill.solid()
                    series.format.fill.fore_color.rgb = RGBColor(59, 130, 246)  # Blue
                
                # Pie charts - Multi-color palette
                elif chart_type == 'pie':
                    # Let PowerPoint handle default pie colors
                    pass
            
            # Axes styling
            if hasattr(chart, 'category_axis'):
                cat_axis = chart.category_axis
                cat_axis.tick_labels.font.size = Pt(10)
                cat_axis.tick_labels.font.color.rgb = RGBColor(107, 114, 128)
                
                # Hide major gridlines on category axis
                cat_axis.major_gridlines.format.line.fill.background()
            
            if hasattr(chart, 'value_axis'):
                val_axis = chart.value_axis
                val_axis.tick_labels.font.size = Pt(10)
                val_axis.tick_labels.font.color.rgb = RGBColor(107, 114, 128)
                
                # Light gray gridlines
                if val_axis.has_major_gridlines:
                    val_axis.major_gridlines.format.line.color.rgb = RGBColor(229, 231, 235)
                    val_axis.major_gridlines.format.line.width = Pt(0.75)
            
        except Exception as e:
            print(f"Chart styling warning: {e}")
