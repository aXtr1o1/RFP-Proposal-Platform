import re
import json
import ast
from typing import Any, Dict, List, Union

def first_balanced_brace_block(s: str) -> str:
    """
    Return the first balanced {...} block from s (handles extra garbage/duplicates after it).
    """
    start = s.find('{')
    if start == -1:
        raise ValueError("No opening '{' found in input.")
    depth = 0
    for i in range(start, len(s)):
        ch = s[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return s[start:i+1]
    raise ValueError("No balanced closing '}' found.")

def normalize_quotes(s: str) -> str:
    """
    Normalize curly quotes and weird punctuation that often appear in copy-pastes.
    We DO NOT convert all single quotes to double quotes (that caused your error).
    """
    s = s.replace('\u2018', "'").replace('\u2019', "'")
    s = s.replace('\u201c', '"').replace('\u201d', '"')
    s = s.replace('،', ',')
    return s

def clean_corrupted_json_text(s: str) -> str:
    """
    Clean corrupted/duplicated text that appears in malformed JSON strings.
    """
    lines = s.split('\n')
    clean_lines = []
    seen_content = set()
    
    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
            
        if line_clean in seen_content and len(line_clean) > 50:
            continue
            
        clean_lines.append(line)
        if len(line_clean) > 20:  
            seen_content.add(line_clean)
    
    return '\n'.join(clean_lines)

def safe_literal_eval(s: str) -> Any:
    """
    Try to parse a Python-literal-style dict string robustly.
    Falls back to targeted fixes if trailing commas or duplicated commas appear.
    """
    e2=''
    e3=''
    try:
        print(f'Before shit:{s}')
        return ast.literal_eval(s)
    except Exception as e:
        print(f"First parse attempt failed: {e}")
        
        try:
            cleaned = clean_corrupted_json_text(s)
            cleaned_block = first_balanced_brace_block(cleaned)
            return ast.literal_eval(cleaned_block)
            
        except Exception as e2:
            e2=e2
            print(f"Second attempt with cleaning failed: {e2}")
        
        try:
            fixed = re.sub(r',\s*([}\]])', r'\1', s)   
            fixed = re.sub(r',\s*,', r', ', fixed)
            fixed_block = first_balanced_brace_block(fixed)
            return ast.literal_eval(fixed_block)
        except Exception as e3:
            e3=e3
            print(f"Third attempt with regex fixes failed: {e3}")
        
        try:
            aggressive_clean = re.sub(r'}\s*,\s*{[^}]*}\]\s*}\s*,.*$', '}]}', s, flags=re.DOTALL)
            aggressive_block = first_balanced_brace_block(aggressive_clean)
            return ast.literal_eval(aggressive_block)
        except Exception as e4:
            raise ValueError(f"Could not parse input as Python literal after multiple attempts.\n"
                           f"Original error: {e}\n"

                           f"After aggressive cleaning: {e4}")

def dedupe_sections_by_heading(obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove duplicate sections by 'heading' while preserving the first occurrence.
    Also removes sections with empty or missing headings.
    """
    sections = obj.get("sections", [])
    seen = set()
    deduped: List[Dict[str, Any]] = []
    
    for sec in sections:
        heading = sec.get("heading", "").strip()
        if heading and heading not in seen:
            seen.add(heading)
            cleaned_section = clean_section_content(sec)
            deduped.append(cleaned_section)
    
    obj["sections"] = deduped
    return obj

def clean_section_content(section: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean individual section content, removing duplicates and fixing formatting.
    """
    cleaned = {}
    
    heading = section.get("heading", "").strip()
    cleaned["heading"] = heading
    
    content = section.get("content", "").strip()
    if content:
        sentences = re.split(r'[.。]', content)
        unique_sentences = []
        seen_sentences = set()
        
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and sentence not in seen_sentences:
                unique_sentences.append(sentence)
                seen_sentences.add(sentence)
        
        cleaned["content"] = '. '.join(unique_sentences).strip()
        if cleaned["content"] and not cleaned["content"].endswith('.'):
            cleaned["content"] += '.'
    else:
        cleaned["content"] = ""
    
    points = section.get("points", [])
    if points:
        unique_points = []
        seen_points = set()
        for point in points:
            point_clean = str(point).strip()
            if point_clean and point_clean not in seen_points:
                unique_points.append(point_clean)
                seen_points.add(point_clean)
        cleaned["points"] = unique_points
    else:
        cleaned["points"] = []
    
    # Clean table
    table = section.get("table", {})
    if table and isinstance(table, dict):
        cleaned_table = {}
        
        # Clean headers
        headers = table.get("headers", [])
        if headers:
            cleaned_table["headers"] = [str(h).strip() for h in headers if str(h).strip()]
        else:
            cleaned_table["headers"] = []
        
        # Clean rows
        rows = table.get("rows", [])
        if rows:
            cleaned_rows = []
            for row in rows:
                if isinstance(row, list):
                    cleaned_row = [str(cell).strip() for cell in row if str(cell).strip()]
                    if cleaned_row:  
                        cleaned_rows.append(cleaned_row)
            cleaned_table["rows"] = cleaned_rows
        else:
            cleaned_table["rows"] = []
        
        cleaned["table"] = cleaned_table
    else:
        cleaned["table"] = {"headers": [], "rows": []}
    
    if "mermaid_diagram" in section:
        cleaned["mermaid_diagram"] = section["mermaid_diagram"]
    
    return cleaned

def validate_proposal_structure(obj: Any) -> Dict[str, Any]:
    """
    Validate and ensure the proposal has the correct structure.
    """
    if not isinstance(obj, dict):
        raise ValueError("Proposal must be a dictionary")
    
    if "title" not in obj:
        obj["title"] = "مقترح شامل للرد على طلب العروض (RFP)"
    
    if "sections" not in obj:
        obj["sections"] = []
    
    obj["title"] = str(obj["title"]).strip()
    
    if not isinstance(obj["sections"], list):
        obj["sections"] = []
    
    return obj

def proposal_cleaner(input_text: str) -> Union[str, Dict[str, Any]]:
    """
    Clean and parse proposal text into a well-formatted JSON structure.
    Returns cleaned proposal as JSON string or dictionary.
    """
    try:
        print("🧹 Starting proposal cleaning process...")
        
        print("📝 Step 1: Normalizing quotes and characters...")
        normalized = normalize_quotes(input_text)
        
        print("🎯 Step 2: Extracting balanced JSON block...")
        block = first_balanced_brace_block(normalized)
        
        print("⚙️ Step 3: Parsing JSON block...")
        parsed = safe_literal_eval(block)
        
        print("✅ Step 4: Validating proposal structure...")
        if isinstance(parsed, dict):
            parsed = validate_proposal_structure(parsed)
            
            print("🔄 Step 5: Removing duplicates and cleaning content...")
            parsed = dedupe_sections_by_heading(parsed)
            
        print("📄 Step 6: Converting to clean JSON...")
        cleaned_text = json.dumps(parsed, ensure_ascii=False, indent=2)
        
        print(f"✅ Cleaning completed successfully! Processed {len(parsed.get('sections', []))} unique sections.")
        
        return parsed
        
    except Exception as e:
        print(f"❌ Error during proposal cleaning: {e}")
        print("🔧 Attempting fallback cleaning...")
        
        try:
            fallback_match = re.search(r'\{.*"title".*"sections".*\}', input_text, re.DOTALL)
            if fallback_match:
                fallback_text = fallback_match.group(0)
                fallback_parsed = json.loads(fallback_text)
                return fallback_parsed
            else:
                raise ValueError("No valid proposal structure found in input")
                
        except Exception as fallback_error:
            print(f"❌ Fallback cleaning also failed: {fallback_error}")
            raise ValueError(f"Could not clean proposal: {e}. Fallback error: {fallback_error}")

if __name__ == "__main__":
    input_text = """
{'title': 'مقترح شامل للرد على طلب العروض (RFP)', 'sections': [{'heading': 'مقدمة', 'content': "تتضمن هذه الوثيقة تعريفات أساسية للمصطلحات المستخدمة في هذا المقترح، مثل 'الجهة الحكومية'، 'مقدم العرض'، 'المنافسة'، و'الخدمات'. سيتم استخدام هذه التعريفات لضمان فهم مشترك بين جميع الأطراف المعنية.", 'points': ['تعريف عن المنافسة', 'المواعيد المتعلقة بالمنافسة', 'أهلية مقدمي العروض'], 'table': {'headers': ['المصطلح', 'التعريف'], 'rows': [['الجهة الحكومية', 'الجهة المسؤولة عن طلب العروض'], ['مقدم العرض', 'الشخص أو الشركة التي تقدم العرض'], ['المنافسة', 'العملية التي يتم من خلالها تقديم العروض']]}}, {'heading': 'الأحكام العامة', 'content': 'تلتزم [اسم الشركة] بتوفير كافة المعلومات اللازمة للجهة الحكومية، مع ضمان عدم التمييز بين المتنافسين، مما يعزز من مبدأ الشفافية.', 'points': ['المساواة والشفافية', 'تعارض المصالح', 'السلوكيات والأخلاقيات'], 'table': {'headers': ['المبدأ', 'التفاصيل'], 'rows': [['المساواة', 'ضمان عدم التمييز بين المتنافسين'], ['شفافية', 'توفير كافة المعلومات اللازمة'], ['تعارض المصالح', 'الإفصاح عن أي حالات تعارض محتملة']]}}]}
"""
    
    try:
        result = proposal_cleaner(input_text)
        print("\n" + "="*50)
        print("CLEANED RESULT:")
        print("="*50)
        if isinstance(result, dict):
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(result)
    except Exception as e:
        print(f"Test failed: {e}")
