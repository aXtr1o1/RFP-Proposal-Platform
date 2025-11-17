from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_DATA_LABEL_POSITION
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger("chart_service")

class ChartService:
    """Service for creating native PowerPoint charts with WHITE/VISIBLE axis text on dark backgrounds"""
    
    def __init__(self, template_id: str = "arweqah"):
        self.template_id = template_id
    
    def add_native_chart(
        self,
        slide,
        chart_data: Dict,
        position: Dict,
        size: Dict,
        background_rgb: Optional[Tuple[int, int, int]] = None
    ):
        """Add native PowerPoint chart with WHITE axis text for dark backgrounds"""
        try:
            chart_type = chart_data.get('chart_type', 'column')
            
            # Get labels (backward compatible)
            labels = chart_data.get('labels') or chart_data.get('categories', [])
            
            # Get values (backward compatible)
            values = chart_data.get('values', [])
            
            title = chart_data.get('title', '')
            series_name = chart_data.get('series_name', 'Values')
            
            # Get axis labels and unit
            x_axis_label = chart_data.get('x_axis_label', '')
            y_axis_label = chart_data.get('y_axis_label', '')
            unit = chart_data.get('unit', '')
            
            if not labels or not values:
                logger.warning("Missing chart data - labels or values empty")
                return None
            
            logger.info(f"Creating {chart_type} chart with {len(labels)} data points")
            
            # Map chart types
            chart_type_map = {
                'column': XL_CHART_TYPE.COLUMN_CLUSTERED,
                'bar': XL_CHART_TYPE.BAR_CLUSTERED,
                'line': XL_CHART_TYPE.LINE_MARKERS,
                'pie': XL_CHART_TYPE.PIE,
                'area': XL_CHART_TYPE.AREA
            }
            
            xl_chart_type = chart_type_map.get(chart_type, XL_CHART_TYPE.COLUMN_CLUSTERED)
            
            # Create chart data
            chart_data_obj = CategoryChartData()
            chart_data_obj.categories = labels
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

            # **CRITICAL FIX: DEFAULT WHITE COLORS FOR DARK BACKGROUNDS**
            color_config = {
                "font_color": chart_data.get("font_color", "#FFFFFF"),  # WHITE
                "data_label_color": chart_data.get("data_label_color", "#FFFFFF"),  # WHITE
                "axis_color": chart_data.get("axis_color", "#FFFFFF"),  # WHITE - CRITICAL FIX
                "axis_label_color": chart_data.get("axis_label_color", "#FFFFFF"),  # WHITE - CRITICAL FIX
                "grid_color": chart_data.get("grid_color", "#5C6F7A"),  # Light gray
                "legend_font_color": chart_data.get("legend_font_color", "#FFFFFF"),  # WHITE
                "plot_background_color": chart_data.get("plot_background_color"),  # Transparent
                "series_color": chart_data.get("series_color", "#F9D462")  # Yellow
            }
            
            # Apply modern styling with WHITE axis text
            self._apply_modern_chart_style(chart, chart_type, background_rgb, color_config)
            
            # Add data labels to all series
            self._add_data_labels(chart, chart_type, unit, color_config)
            
            # Configure legend
            self._configure_legend(chart, chart_type, color_config)
            
            # Add axis labels (WHITE text)
            self._add_axis_labels(chart, chart_type, x_axis_label, y_axis_label, unit, color_config)
            
            # Add title if provided
            if title:
                chart.has_title = True
                chart.chart_title.text_frame.text = title
                chart.chart_title.text_frame.paragraphs[0].font.size = Pt(16)
                chart.chart_title.text_frame.paragraphs[0].font.bold = True
                title_color = self._get_rgb(color_config.get("font_color"), (255, 255, 255))
                chart.chart_title.text_frame.paragraphs[0].font.color.rgb = RGBColor(*title_color)
            
            logger.info(f"✅ Chart created with WHITE axis text: {title} ({chart_type})")
            return chart
            
        except Exception as e:
            logger.error(f"❌ Chart creation error: {e}")
            import traceback
            traceback.print_exc()
            return None
        
    def _add_axis_labels(self, chart, chart_type: str, x_axis_label: str, y_axis_label: str, unit: str, color_config: Dict):
        """
        Add axis labels with WHITE text for visibility on dark backgrounds
        """
        try:
            # Pie charts don't have axes
            if chart_type == 'pie':
                return
            
            # **CRITICAL FIX: WHITE axis labels**
            axis_label_rgb = self._get_rgb(color_config.get("axis_label_color"), (255, 255, 255))

            # Category axis (X-axis) - WHITE TEXT
            if x_axis_label:
                try:
                    cat_axis = chart.category_axis
                    cat_axis.has_title = True
                    cat_axis.axis_title.text_frame.text = x_axis_label
                    cat_axis.axis_title.text_frame.paragraphs[0].font.size = Pt(12)
                    cat_axis.axis_title.text_frame.paragraphs[0].font.bold = True
                    cat_axis.axis_title.text_frame.paragraphs[0].font.color.rgb = RGBColor(*axis_label_rgb)
                    logger.info(f"  ✓ X-axis label (WHITE): {x_axis_label}")
                except Exception as e:
                    logger.warning(f"⚠️  X-axis label error: {e}")
            
            # Value axis (Y-axis) - WHITE TEXT (CRITICAL FIX)
            if y_axis_label or unit:
                try:
                    val_axis = chart.value_axis
                    val_axis.has_title = True
                    
                    # Combine Y-axis label with unit
                    if y_axis_label and unit:
                        axis_title = f"{y_axis_label} ({unit})"
                    elif y_axis_label:
                        axis_title = y_axis_label
                    else:
                        axis_title = unit
                    
                    val_axis.axis_title.text_frame.text = axis_title
                    val_axis.axis_title.text_frame.paragraphs[0].font.size = Pt(12)
                    val_axis.axis_title.text_frame.paragraphs[0].font.bold = True
                    val_axis.axis_title.text_frame.paragraphs[0].font.color.rgb = RGBColor(*axis_label_rgb)
                    logger.info(f"  ✓ Y-axis label (WHITE): {axis_title}")
                except Exception as e:
                    logger.warning(f"⚠️  Y-axis label error: {e}")
                    
        except Exception as e:
            logger.warning(f"⚠️  Axis labels configuration error: {e}")

    
    def _add_data_labels(self, chart, chart_type: str, unit: str, color_config: Dict):
        """
        Add data labels to chart series with WHITE text
        """
        try:
            for series_idx, series in enumerate(chart.series):
                # Enable data labels
                series.has_data_labels = True
                data_labels = series.data_labels
                
                # **WHITE for data labels on dark backgrounds**
                data_label_rgb = self._get_rgb(color_config.get("data_label_color"), (255, 255, 255))

                # Configure based on chart type
                if chart_type == 'pie':
                    # Pie charts: show percentages outside (use dark since outside)
                    data_labels.number_format = '0%'
                    data_labels.position = XL_DATA_LABEL_POSITION.OUTSIDE_END
                    data_labels.font.size = Pt(11)
                    data_labels.font.bold = True
                    pie_label_rgb = self._get_rgb(color_config.get("data_label_color"), (13, 32, 38))
                    data_labels.font.color.rgb = RGBColor(*pie_label_rgb)
                    
                elif chart_type in ['column', 'bar']:
                    # Column/Bar: WHITE text
                    data_labels.position = XL_DATA_LABEL_POSITION.OUTSIDE_END
                    data_labels.font.size = Pt(11)
                    data_labels.font.bold = True
                    data_labels.font.color.rgb = RGBColor(*data_label_rgb)
                    
                    # Add custom number format with unit
                    if unit:
                        if unit == '%':
                            data_labels.number_format = '0"%"'
                        elif unit == '$':
                            data_labels.number_format = '"$"0'
                        else:
                            data_labels.number_format = f'0" {unit}"'
                    
                elif chart_type == 'line':
                    # Line charts: WHITE text
                    data_labels.position = XL_DATA_LABEL_POSITION.ABOVE
                    data_labels.font.size = Pt(10)
                    data_labels.font.color.rgb = RGBColor(*data_label_rgb)
                    
                    if unit:
                        if unit == '%':
                            data_labels.number_format = '0"%"'
                        elif unit == '$':
                            data_labels.number_format = '"$"0'
                        else:
                            data_labels.number_format = f'0" {unit}"'
                
                logger.info(f"  ✓ Data labels (WHITE) added to series {series_idx + 1}")
                
        except Exception as e:
            logger.warning(f"⚠️  Data labels error: {e}")

    
    def _configure_legend(self, chart, chart_type: str, color_config: Dict):
        """
        Configure chart legend with WHITE text
        """
        try:
            # **WHITE legend text**
            legend_rgb = self._get_rgb(color_config.get("legend_font_color"), (255, 255, 255))
            
            # Pie charts MUST have legend
            if chart_type == 'pie':
                chart.has_legend = True
                chart.legend.position = XL_LEGEND_POSITION.RIGHT
                chart.legend.font.size = Pt(11)
                chart.legend.font.color.rgb = RGBColor(*legend_rgb)
                chart.legend.include_in_layout = False
                logger.info("  ✓ Legend (WHITE text, right position)")
                
            # Other charts: legend at bottom
            elif chart_type in ['column', 'bar', 'line', 'area']:
                if len(chart.series) > 1:
                    chart.has_legend = True
                    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
                    chart.legend.font.size = Pt(10)
                    chart.legend.font.color.rgb = RGBColor(*legend_rgb)
                    logger.info("  ✓ Legend (WHITE text, bottom position)")
                else:
                    chart.has_legend = False
                    logger.info("  ✓ Legend hidden (single series)")
            
        except Exception as e:
            logger.warning(f"⚠️  Legend configuration error: {e}")
    
    def _apply_modern_chart_style(self, chart, chart_type: str, background_rgb: Optional[Tuple], color_config: Dict):
        """
        Apply styling with WHITE axis text for dark backgrounds (CRITICAL FIX)
        """
        try:
            # Chart area background
            chart.chart_style = 2
            
            if background_rgb:
                chart.chart_area.fill.solid()
                chart.chart_area.fill.fore_color.rgb = RGBColor(*background_rgb)
            
            # Plot area - transparent
            try:
                plot_bg = color_config.get("plot_background_color")
                if plot_bg:
                    chart.plot_area.fill.solid()
                    plot_rgb = self._get_rgb(plot_bg, (255, 255, 255))
                    chart.plot_area.fill.fore_color.rgb = RGBColor(*plot_rgb)
                else:
                    chart.plot_area.fill.background()
            except Exception as e:
                logger.debug(f"Plot area styling skipped: {e}")
            
            # Series styling
            series_color = self._get_rgb(color_config.get("series_color"), (249, 212, 98))
            
            for series in chart.series:
                if chart_type == 'line':
                    series.format.line.color.rgb = RGBColor(*series_color)
                    series.format.line.width = Pt(2.5)
                    series.smooth = True
                    
                    try:
                        series.marker.style = 8
                        series.marker.size = 7
                        series.marker.format.fill.solid()
                        series.marker.format.fill.fore_color.rgb = RGBColor(*series_color)
                        series.marker.format.line.color.rgb = RGBColor(255, 255, 255)
                        series.marker.format.line.width = Pt(1.5)
                    except:
                        pass
                
                elif chart_type in ['column', 'bar']:
                    try:
                        series.format.fill.solid()
                        series.format.fill.fore_color.rgb = RGBColor(*series_color)
                    except:
                        pass
                
                elif chart_type == 'area':
                    try:
                        series.format.fill.solid()
                        series.format.fill.fore_color.rgb = RGBColor(*series_color)
                        series.format.line.color.rgb = RGBColor(*series_color)
                    except:
                        pass
            
            # **CRITICAL FIX: WHITE AXIS TEXT (X and Y)**
            if chart_type != 'pie':
                # **Category axis (X-axis) - WHITE TEXT**
                try:
                    axis_rgb = self._get_rgb(color_config.get("axis_color"), (255, 255, 255))
                    cat_axis = chart.category_axis
                    cat_axis.visible = True
                    cat_axis.tick_labels.font.size = Pt(11)
                    cat_axis.tick_labels.font.bold = True  # BOLD for visibility
                    cat_axis.tick_labels.font.color.rgb = RGBColor(*axis_rgb)  # WHITE
                    cat_axis.major_gridlines.format.line.fill.background()
                    cat_axis.format.line.color.rgb = RGBColor(180, 180, 180)
                    logger.info(f"  ✓ X-axis text: WHITE ({axis_rgb})")
                except Exception as e:
                    logger.debug(f"Category axis styling skipped: {e}")
                
                # **Value axis (Y-axis) - WHITE TEXT (CRITICAL FIX)**
                try:
                    axis_rgb = self._get_rgb(color_config.get("axis_color"), (255, 255, 255))
                    val_axis = chart.value_axis
                    val_axis.visible = True
                    val_axis.tick_labels.font.size = Pt(11)
                    val_axis.tick_labels.font.bold = True  # **BOLD for visibility**
                    val_axis.tick_labels.font.color.rgb = RGBColor(*axis_rgb)  # **WHITE**
                    
                    # Light gridlines
                    if val_axis.has_major_gridlines:
                        grid_rgb = self._get_rgb(color_config.get("grid_color"), (92, 111, 122))
                        val_axis.major_gridlines.format.line.color.rgb = RGBColor(*grid_rgb)
                        val_axis.major_gridlines.format.line.width = Pt(0.75)
                    
                    logger.info(f"  ✓ Y-axis text: WHITE ({axis_rgb})")
                except Exception as e:
                    logger.debug(f"Value axis styling skipped: {e}")
            
            logger.info("  ✅ Applied styling with WHITE axis text")
            
        except Exception as e:
            logger.warning(f"⚠️  Chart styling error: {e}")

    def _get_rgb(self, hex_color: Optional[str], fallback: Optional[Tuple[int, int, int]] = None) -> Tuple[int, int, int]:
        """Convert hex to RGB with WHITE fallback"""
        if not hex_color:
            return fallback or (255, 255, 255)
        try:
            value = hex_color.lstrip("#")
            return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))
        except Exception:
            return fallback or (255, 255, 255)