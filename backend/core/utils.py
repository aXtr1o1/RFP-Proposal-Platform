import json, re, io, uuid, os
from core.logger import get_logger
logger = get_logger("utils")

def extract_json_array(text: str):
    """Extract the first JSON array from a text response."""
    s = text.strip()
    s = re.sub(r"^```(json)?", "", s)
    s = re.sub(r"```$", "", s)
    s = s.strip()
    start, end = s.find("["), s.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("No JSON array found in model output")
    return json.loads(s[start:end+1])

def uuid_like(prefix: str = "gen") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def bytesio_of(path: str):
    with open(path, "rb") as f:
        return io.BytesIO(f.read())

def save_bytes(path: str, data: bytes):
    with open(path, "wb") as f:
        f.write(data)

def safe_unlink(path: str):
    try:
        os.remove(path)
    except Exception:
        pass
