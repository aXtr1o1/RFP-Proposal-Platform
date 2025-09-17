input = {'page_orientation': 'portrait', 'text_alignment': 'left', 'reading_direction': 'ltr', 'top_margin': '1.0', 'bottom_margin': '1.0', 'left_margin': '1.0', 'right_margin': '1.0', 'body_font_size': '11', 'heading_font_size': '14', 'title_font_size': '16', 'bullet_font_size': '11', 'table_font_size': '10', 'title_color': '#1a1a1a', 'heading_color': '#2d2d2d', 'body_color': '#4a4a4a', 'auto_fit_tables': True, 'table_width': '100', 'show_table_borders': True, 'border_color': '#cccccc', 'border_style': 'single', 'border_preset': 'grid', 'header_background': '#f8f9fa', 'table_background': '#ffffff', 'include_header': True, 'include_footer': True, 'company_name': '', 'company_tagline': '', 'logo_file_path': '', 'footer_left': '', 'footer_center': '', 'footer_right': '', 'show_page_numbers': True}

CONFIG = {
    "visible_word": False,         
    "output_path": "output/proposal.docx",
    "language_lcid": 1025,         
    "default_alignment": 2,        
    "reading_order": 1,           
    "space_before": 0,
    "space_after": 6,
    "line_spacing_rule": 0,     
    "orientation": 0,             
    "margin_top": 72,              
    "margin_bottom": 72,
    "margin_left": 72,
    "margin_right": 72,

    "table_autofit": True,
    "table_preferred_width": None, 
    "title_style": "Title",
    "heading_style": "Heading 1",
    "normal_style": "Normal",
    "font_size": 14,        
    "heading_font_size": 16, 
    "title_font_size": 20,
    "points_font_size": 14,  
    "table_font_size": 12,   
    "title_font_color": 0,
    "heading_font_color": 0,
    "content_font_color": 0,

    "table_font_color": 0,           
    "table_border_visible": True,    
    "table_border_color": 0,        
    "table_border_line_style": 1,    
    "table_border_line_width": 1,   
    "table_border_preset": "all",    
    "table_header_shading_color": None, 
    "table_body_shading_color": None,   
    
    "enable_header": False,
    "enable_footer": False,
    "company_name": "aXtrLabs",
    "company_tagline": "Your Trusted Partner in Hajj and Umrah Services",
    "header_logo_path": r"C:\Users\sanje_3wfdh8z\OneDrive\Desktop\RFP\RFP-Proposal-Platform\apps\wordgen-agent\app\asserts\download.png",   # absolute or relative to project root
    "header_logo_width": 5,   
    "header_logo_height": 2, 
    "header_logo_max_width": 120,   
    "header_logo_max_height": 60, 
    "header_padding": 6,       
    "footer_left_text": "",
    "footer_center_text": "",
    "footer_right_text": "",
    "footer_show_page_numbers": True,
    "footer_padding": 6,
}


from copy import deepcopy


from copy import deepcopy

# Word constants (MS Word COM equivalents)
WORD_ORIENTATION = {"portrait": 0, "landscape": 1}
WORD_ALIGNMENT = {"left": 0, "center": 1, "right": 2, "justify": 3}
WORD_READING_ORDER = {"ltr": 1, "rtl": 0}

def hex_to_bgr_int(hex_color: str) -> int:
    """Convert hex #RRGGBB to Word BGR integer"""
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return (b << 16) + (g << 8) + r

def build_updated_config(default_config: dict, input_config: dict) -> dict:
    updated_config = deepcopy(default_config)

    for key, val in input_config.items():
        if key == "page_orientation":
            updated_config["orientation"] = WORD_ORIENTATION.get(val.lower(), updated_config["orientation"])
        elif key == "text_alignment":
            updated_config["default_alignment"] = WORD_ALIGNMENT.get(val.lower(), updated_config["default_alignment"])
        elif key == "reading_direction":
            updated_config["reading_order"] = WORD_READING_ORDER.get(val.lower(), updated_config["reading_order"])
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
            if key in mapping:
                updated_config[mapping[key]] = hex_to_bgr_int(val)
        elif key == "auto_fit_tables":
            updated_config["table_autofit"] = bool(val)
        elif key == "table_width":
            updated_config["table_preferred_width"] = int(val)
        elif key == "show_table_borders":
            updated_config["table_border_visible"] = bool(val)
        elif key == "border_style":
            styles = {"single": 1, "double": 2, "dotted": 4, "dashed": 3}
            updated_config["table_border_line_style"] = styles.get(val.lower(), 1)
        elif key == "border_preset":
            updated_config["table_border_preset"] = val
        elif key == "include_header":
            updated_config["enable_header"] = bool(val)
        elif key == "include_footer":
            updated_config["enable_footer"] = bool(val)
        elif key == "company_name":
            updated_config["company_name"] = val
        elif key == "company_tagline":
            updated_config["company_tagline"] = val
        elif key == "logo_file_path":
            updated_config["header_logo_path"] = val
        elif key == "footer_left":
            updated_config["footer_left_text"] = val
        elif key == "footer_center":
            updated_config["footer_center_text"] = val
        elif key == "footer_right":
            updated_config["footer_right_text"] = val
        elif key == "show_page_numbers":
            updated_config["footer_show_page_numbers"] = bool(val)

    return updated_config



