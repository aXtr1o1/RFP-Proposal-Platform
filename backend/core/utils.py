import re
import json
import uuid

def extract_json_array(text: str) -> list[dict]:
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    if s.endswith("```"):
        s = re.sub(r"\s*```$", "", s)

    start, end = s.find("["), s.rfind("]")
    if start == -1 or end == -1 or end < start:
        m = re.search(r"(\[.*\])", s, flags=re.DOTALL)
        if not m:
            raise ValueError("No JSON array found in model output")
        s = m.group(1)
    else:
        s = s[start : end + 1]

    data = json.loads(s)
    if not isinstance(data, list):
        raise ValueError("Parsed JSON is not an array")
    return data

def short_kb(n: int) -> int:
    return int(round(n / 1024))

def uuid_like(prefix: str = "") -> str:
    token = uuid.uuid4().hex[:8]
    return f"{prefix}_{token}" if prefix else token
