import re
import json
import os
from typing import List, Dict, Any

from routes.logging import logger


def parse_slides_json(text: str) -> List[Dict[str, Any]]:
    try:
        logger.info("Parsing JSON from OpenAI response...")
        s = text.strip()
        
        # Remove ONLY markdown code fences
        # Remove ```
        if s.startswith('```json'):
            s = s[7:]  
        elif s.startswith('```'):
            s = s[3:]   
        if s.endswith('```'):
            s = s[:-3]  # Remove last 3 characters
        
        # Strip again
        s = s.strip()
        
        logger.info(f"After markdown removal (length: {len(s)} chars)")
        start = s.find("[")
        end = s.rfind("]")
        
        if start == -1 or end == -1:
            logger.error("No JSON array boundaries found")
            raise ValueError("No JSON array found in model output")
        json_str = s[start : end + 1]
        
        logger.info(f"Extracted JSON (length: {len(json_str)} chars)")
        logger.info("Parsing JSON...")
        arr = json.loads(json_str)
        if not isinstance(arr, list):
            raise ValueError("Parsed JSON is not an array")
        
        logger.info(f"[SUCCESS] Parsed {len(arr)} slides")
        
        return arr
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        logger.error(f"Position: {e.pos}, Line: {e.lineno}, Column: {e.colno}")
        debug_file = "debug_json_error.txt"
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write("=== ORIGINAL ===\n")
            f.write(text)
            f.write("\n\n=== AFTER MARKDOWN REMOVAL ===\n")
            f.write(s)
            f.write("\n\n=== EXTRACTED JSON ===\n")
            f.write(json_str if 'json_str' in locals() else "(Could not extract)")
            f.write(f"\n\n=== ERROR ===\n{e}\n")
        
        logger.error(f"Debug saved to: {debug_file}")
        raise ValueError(f"Failed to parse JSON: {str(e)}")
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise


def cleanup_temp_files(*file_paths: str):
    """Delete temporary files after processing."""
    if not file_paths:
        return
    
    logger.info(f"Cleaning up {len(file_paths)} temp files...")
    
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"  Deleted: {path}")
        except Exception as e:
            logger.warning(f"  Failed to delete {path}: {e}")
