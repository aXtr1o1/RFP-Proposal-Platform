from copy import deepcopy

WORD_ORIENTATION = {"portrait": 0, "landscape": 1}
WORD_ALIGNMENT = {"left": 0, "center": 1, "right": 2, "justify": 3}
WORD_READING_ORDER = {"ltr": 0, "rtl": 1}

def hex_to_bgr_int(hex_color: str) -> int:
    if not hex_color or not isinstance(hex_color, str):
        return 0

    hex_color = hex_color.strip().lstrip('#')

    if len(hex_color) != 6:
        return 0

    try:
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return (b << 16) + (g << 8) + r
    except (ValueError, IndexError):
        return 0 


def build_updated_config(default_config: dict, input_config: dict) -> dict:
    updated_config = deepcopy(default_config)
    
    if not input_config or not isinstance(input_config, dict):
        return updated_config
    
    for key, val in input_config.items():
        if val is None or val == "":
            continue
        
        try:
            if key == "page_orientation":
                updated_config["orientation"] = WORD_ORIENTATION.get(str(val).lower(), updated_config["orientation"])
            
            elif key == "text_alignment":
                updated_config["default_alignment"] = WORD_ALIGNMENT.get(str(val).lower(), updated_config["default_alignment"])
            
            elif key == "reading_direction":
                updated_config["reading_order"] = WORD_READING_ORDER.get(str(val).lower(), updated_config["reading_order"])
            
            elif key in ["top_margin", "bottom_margin", "left_margin", "right_margin"]:
                updated_config[f"margin_{key.split('_')[0]}"] = int(float(val) * 72)
            
            elif key.endswith("_font_size"):
                mapping = {
                    "body_font_size": "font_size",
                    "heading_font_size": "heading_font_size",
                    "title_font_size": "title_font_size",
                    "bullet_font_size": "points_font_size",
                    "table_font_size": "table_font_size",
                }
                if key in mapping:
                    updated_config[mapping[key]] = int(val)
            
            elif key.endswith("_color"):
                mapping = {
                    "title_color": "title_font_color",
                    "heading_color": "heading_font_color",
                    "body_color": "content_font_color",
                    "table_font_color": "table_font_color",
                    "border_color": "table_border_color",
                    "header_background": "table_header_shading_color",
                    "table_background": "table_body_shading_color",
                }
                if key in mapping and val: 
                    updated_config[mapping[key]] = hex_to_bgr_int(str(val))
            
            elif key == "auto_fit_tables":
                updated_config["table_autofit"] = bool(val)
            
            elif key == "table_width":
                updated_config["table_preferred_width"] = int(val)
            
            elif key == "show_table_borders":
                updated_config["table_border_visible"] = bool(val)
            
            elif key == "include_header":
                updated_config["enable_header"] = bool(val)
            
            elif key == "include_footer":
                updated_config["enable_footer"] = bool(val)
            
            elif key == "company_name":
                updated_config["company_name"] = str(val)
            
            elif key == "company_tagline":
                updated_config["company_tagline"] = str(val)
            
            elif key == "logo_file_path":
                updated_config["header_logo_path"] = str(val)
            
            elif key == "footer_left":
                updated_config["footer_left_text"] = str(val)
            
            elif key == "footer_center":
                updated_config["footer_center_text"] = str(val)
            
            elif key == "footer_right":
                updated_config["footer_right_text"] = str(val)
            
            elif key == "show_page_numbers":
                updated_config["footer_show_page_numbers"] = bool(val)
            
            # Additional mappings for missing properties
            elif key == "table_font_color":
                # This should map to table_font_color in the config
                updated_config["table_font_color"] = hex_to_bgr_int(str(val)) if val else 0
            
            elif key == "border_style":
                # Map border style to line style
                styles = {"single": 1, "double": 2, "dotted": 4, "dashed": 3}
                updated_config["table_border_line_style"] = styles.get(str(val).lower(), 1)
            
            elif key == "border_preset":
                updated_config["table_border_preset"] = str(val)
            
            elif key == "table_background":
                # Map table background to body shading color
                updated_config["table_body_shading_color"] = hex_to_bgr_int(str(val)) if val else None
            
            elif key == "header_background":
                # Map header background to header shading color
                updated_config["table_header_shading_color"] = hex_to_bgr_int(str(val)) if val else None
        
        except (ValueError, TypeError, KeyError) as e:
            import logging
            logger = logging.getLogger("config_setting")
            logger.warning(f"Failed to process config key '{key}' with value '{val}': {e}")
            continue
    
    return updated_config
