import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
from dotenv import load_dotenv

from pymilvus import connections, Collection

try:
	from openai import OpenAI
except Exception:
	OpenAI = None  # type: ignore

try:
	import win32com.client as win32  # type: ignore
except Exception:
	win32 = None  # type: ignore

try:
	from docx import Document  # type: ignore
except Exception:
	Document = None  # type: ignore


# Load environment variables from nearest .env up the tree
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=False)
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=False)
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)


app = FastAPI(title="WordGen Agent API")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wordgen-agent")


class GenerateProposalRequest(BaseModel):
	uuid: str
	config_text: str


class GenerateProposalResponse(BaseModel):
	status: str
	output_path: Optional[str] = None
	message: Optional[str] = None


# ---------- Milvus utilities ----------

def _connect_milvus() -> None:
	"""Connect to Milvus using either MILVUS_URI (+ optional MILVUS_TOKEN) or explicit host/port creds.

	Environment options supported:
	- MILVUS_URI (e.g., http://localhost:19530 or https://milvus.local:19530)
	- MILVUS_TOKEN (e.g., username:password)
	- MILVUS_HOST, MILVUS_PORT, MILVUS_SECURE (true/false), MILVUS_USER, MILVUS_PASSWORD
	- MILVUS_DB (database name, optional)
	"""
	uri = os.getenv("MILVUS_URI")
	token = os.getenv("MILVUS_TOKEN")
	db_name = os.getenv("MILVUS_DB")

	# If URI is provided, prefer that path
	if uri:
		kwargs = {"alias": "default", "uri": uri}
		if token:
			kwargs["token"] = token
		if db_name:
			kwargs["db_name"] = db_name
		try:
			connections.connect(**kwargs)
		except Exception as exc:
			raise HTTPException(status_code=500, detail=f"Milvus connection failed (URI): {exc}")
		return

	# Fallback to explicit host/port based configuration
	host = os.getenv("MILVUS_HOST", "localhost")
	port = int(os.getenv("MILVUS_PORT", "19530"))
	secure_env = os.getenv("MILVUS_SECURE", "false").strip().lower()
	secure = secure_env in ("1", "true", "yes", "on")
	user = os.getenv("MILVUS_USER")
	password = os.getenv("MILVUS_PASSWORD")

	connect_kwargs = {
		"alias": "default",
		"host": host,
		"port": str(port),
		"secure": secure,
	}
	if user and password:
		connect_kwargs["user"] = user
		connect_kwargs["password"] = password
	if db_name:
		connect_kwargs["db_name"] = db_name
	try:
		connections.connect(**connect_kwargs)
	except Exception as exc:
		raise HTTPException(status_code=500, detail=f"Milvus connection failed (host/port): {exc}")


def _get_collection() -> Collection:
	collection_name = os.getenv("MILVUS_COLLECTION", "documents")
	logger.info(f"Using Milvus collection: {collection_name}")
	try:
		col = Collection(collection_name)
		# Ensure loaded (for query on some setups). If load fails, continue with query.
		try:
			col.load()
		except Exception as load_exc:
			logger.warning(f"Milvus collection load warning: {load_exc}")
		return col
	except Exception as exc:
		raise HTTPException(status_code=500, detail=f"Milvus collection error: {exc}")


def fetch_text_by_folder_and_type(folder_uuid: str, file_type: str) -> str:
	"""Fetch concatenated text for a given folder_name (uuid) and file_type."""
	_connect_milvus()
	col = _get_collection()
	expr = f'folder_name == "{folder_uuid}" && file_type == "{file_type}"'
	logger.info(f"Milvus query expr: {expr}")
	try:
		results = col.query(expr=expr, output_fields=["content", "chunk_index", "file_name"], consistency_level="Strong", limit=10000)
		logger.info(f"Milvus query returned {len(results)} rows for type={file_type}")
		# Sort by chunk_index if present for deterministic ordering
		try:
			results.sort(key=lambda r: r.get("chunk_index", 0))
		except Exception as sort_exc:
			logger.warning(f"Sort warning: {sort_exc}")
		texts: List[str] = [r.get("content", "") for r in results if r.get("content")]
		return "\n\n".join(texts)
	except Exception as exc:
		logger.exception("Milvus query failed")
		raise HTTPException(status_code=500, detail=f"Milvus query failed: {exc}")


@app.get("/debug/vdb/{folder_uuid}")
def debug_vdb(folder_uuid: str):
	"""Return counts and samples for RFP and supportive records in Milvus for a uuid."""
	_connect_milvus()
	col = _get_collection()
	debug_info = {"collection": os.getenv("MILVUS_COLLECTION", "documents"), "uuid": folder_uuid}
	for ftype in ("RFP", "supportive"):
		expr = f'folder_name == "{folder_uuid}" && file_type == "{ftype}"'
		try:
			rows = col.query(expr=expr, output_fields=["id", "file_name", "chunk_index"], consistency_level="Strong", limit=10000)
			rows_sorted = sorted(rows, key=lambda r: r.get("chunk_index", 0))
			debug_info[ftype] = {
				"count": len(rows_sorted),
				"samples": rows_sorted[:5],
			}
		except Exception as exc:
			debug_info[ftype] = {"error": str(exc)}
	return debug_info


@app.get("/debug/vdb/inspect/all")
def debug_inspect_all():
	"""Inspect all records to see what folder_name and file_type values exist."""
	_connect_milvus()
	col = _get_collection()
	try:
		# Get all records with key fields
		all_rows = col.query(expr="", output_fields=["id", "folder_name", "file_type", "file_name"], consistency_level="Strong", limit=1000)
		
		# Group by folder_name and file_type
		folders = {}
		file_types = set()
		
		for row in all_rows:
			folder = row.get("folder_name", "unknown")
			ftype = row.get("file_type", "unknown")
			file_types.add(ftype)
			
			if folder not in folders:
				folders[folder] = {}
			if ftype not in folders[folder]:
				folders[folder][ftype] = 0
			folders[folder][ftype] += 1
		
		return {
			"collection": os.getenv("MILVUS_COLLECTION", "documents"),
			"total_records": len(all_rows),
			"unique_file_types": sorted(list(file_types)),
			"folders_summary": {k: v for k, v in list(folders.items())[:10]},  # First 10 folders
			"sample_records": all_rows[:5]  # First 5 records
		}
	except Exception as exc:
		return {"error": str(exc)}


# ---------- LLM utilities ----------

def _extract_chat_content(resp) -> str:
	"""Extract text content from OpenAI chat response robustly."""
	try:
		choice = resp.choices[0]
		# Some SDKs provide message.content as str, others as list of parts
		msg = getattr(choice, "message", None) or {}
		content = getattr(msg, "content", None)
		if isinstance(content, str) and content.strip():
			return content
		# Fallback to delta/content from streaming-like objects if present
		delta = getattr(choice, "delta", None)
		if delta and isinstance(delta, dict) and delta.get("content"):
			return delta["content"]
		raise ValueError("No content returned from model")
	except Exception as exc:
		logger.exception("Failed to extract content from OpenAI response")
		raise


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def generate_outline_with_4omini(config_text: str, rfp_knowledge: str) -> str:
	if OpenAI is None:
		raise HTTPException(status_code=500, detail="openai package not available")
	api_key = os.getenv("OPENAI_API_KEY")
	if not api_key:
		raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")
	
	# Create client with minimal configuration to avoid proxy issues
	import httpx
	http_client = httpx.Client()
	client = OpenAI(api_key=api_key, http_client=http_client)
	
	# Detect language from RFP content
	language_prompt = f"Identify the primary language of this text and respond with only the language name (e.g., 'Arabic', 'English', 'Spanish'):\n\n{rfp_knowledge[:1000]}"
	lang_resp = client.chat.completions.create(
		model="gpt-4o-mini",
		messages=[{"role": "user", "content": language_prompt}],
		temperature=0.1,
		max_tokens=50,
	)
	detected_language = _extract_chat_content(lang_resp).strip()
	logger.info(f"Detected language: {detected_language}")
	
	messages = [
		{"role": "system", "content": f"You are an expert proposal writer. Create a comprehensive, professional outline for an RFP response in {detected_language}. Follow RFP requirements precisely and include all mandatory sections."},
		{"role": "user", "content": (
			"RFP DOCUMENT (Requirements & Specifications):\n" + (rfp_knowledge or "")[:120000] +
			"\n\nADDITIONAL GUIDELINES:\n" + (config_text or "") +
			"\n\nTASK: Create a detailed hierarchical outline in " + detected_language + " that:\n"
			"1. Addresses ALL RFP requirements and evaluation criteria\n"
			"2. Includes technical approach, methodology, timeline\n"
			"3. Covers compliance, certifications, and qualifications\n"
			"4. Has sections for pricing, terms, and conditions\n"
			"5. Includes required forms, matrices, and appendices\n"
			"6. Follows the exact structure and language of the RFP"
		)}
	]
	resp = client.chat.completions.create(
		model="gpt-4o-mini",
		messages=messages,
		temperature=0.2,
		max_tokens=2048,
	)
	return _extract_chat_content(resp).strip()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def generate_proposal_with_4omini(config_text: str, outline_text: str, supportive_knowledge: str) -> str:
	if OpenAI is None:
		raise HTTPException(status_code=500, detail="openai package not available")
	api_key = os.getenv("OPENAI_API_KEY")
	if not api_key:
		raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")
	
	# Create client with minimal configuration to avoid proxy issues
	import httpx
	http_client = httpx.Client()
	client = OpenAI(api_key=api_key, http_client=http_client)
	
	# Detect language from outline content
	language_prompt = f"Identify the primary language of this text and respond with only the language name (e.g., 'Arabic', 'English', 'Spanish'):\n\n{outline_text[:1000]}"
	lang_resp = client.chat.completions.create(
		model="gpt-4o-mini",
		messages=[{"role": "user", "content": language_prompt}],
		temperature=0.1,
		max_tokens=50,
	)
	detected_language = _extract_chat_content(lang_resp).strip()
	logger.info(f"Detected language for proposal: {detected_language}")
	
	messages = [
		{"role": "system", "content": f"You are an expert proposal writer crafting a winning RFP response in {detected_language}. Write as the company submitting the proposal, using their credentials and capabilities to demonstrate compliance and competitive advantage."},
		{"role": "user", "content": (
			"PROPOSAL OUTLINE TO FOLLOW:\n" + (outline_text or "")[:60000] +
			"\n\nCOMPANY INFORMATION & CREDENTIALS:\n" + (supportive_knowledge or "No additional company information available.")[:120000] +
			"\n\nADDITIONAL GUIDELINES:\n" + (config_text or "") +
			"\n\nTASK: Write a complete, professional proposal in " + detected_language + " that:\n"
			"1. Follows the outline structure exactly\n"
			"2. Uses the company's credentials, experience, and capabilities from the supportive documents\n"
			"3. Demonstrates clear understanding of RFP requirements\n"
			"4. Shows competitive advantages and unique value propositions\n"
			"5. Includes specific technical details, methodologies, and timelines\n"
			"6. Uses professional, persuasive language appropriate for the target audience\n"
			"7. Addresses all evaluation criteria mentioned in the RFP\n"
			"8. Maintains consistent tone and formatting throughout"
		)}
	]
	resp = client.chat.completions.create(
		model="gpt-4o-mini",
		messages=messages,
		temperature=0.3,
		max_tokens=4096,
	)
	return _extract_chat_content(resp).strip()


# ---------- Word document generation ----------

def save_docx(content: str, base_filename: str) -> str:
	base_dir = Path(__file__).resolve().parents[1]
	output_dir = base_dir / "output"
	output_dir.mkdir(parents=True, exist_ok=True)
	timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
	file_path = output_dir / f"{base_filename}_{timestamp}.docx"

	# Try COM first
	if win32 is not None:
		try:
			word = win32.Dispatch("Word.Application")
			word.Visible = False
			doc = word.Documents.Add()
			selection = word.Selection
			selection.TypeText(content)
			doc.SaveAs(str(file_path))
			doc.Close(False)
			word.Quit()
			return str(file_path)
		except Exception:
			# Fall through to python-docx
			try:
				word.Quit()
			except Exception:
				pass

	# Fallback to python-docx
	if Document is None:
		raise HTTPException(status_code=500, detail="Neither Word COM nor python-docx is available to create .docx")
	doc = Document()
	doc.add_paragraph(content)
	doc.save(str(file_path))
	return str(file_path)


@app.post("/generate-proposal", response_model=GenerateProposalResponse)
def generate_proposal(request: GenerateProposalRequest) -> GenerateProposalResponse:
	try:
		# 1) Retrieve knowledge from Milvus
		rfp_text = fetch_text_by_folder_and_type(request.uuid, "RFP")
		if not rfp_text:
			raise HTTPException(status_code=404, detail="No RFP knowledge found for provided uuid")
		
		# Try to get supportive text, but don't fail if it doesn't exist
		supportive_text = fetch_text_by_folder_and_type(request.uuid, "supportive")
		if not supportive_text:
			logger.warning(f"No supportive knowledge found for uuid {request.uuid}, proceeding with RFP only")
			supportive_text = "No additional supportive documents available."

		# 2) Generate outline
		outline = generate_outline_with_4omini(request.config_text, rfp_text)
		print("Outline: ", outline)
		
		# 3) Generate full proposal
		proposal = generate_proposal_with_4omini(request.config_text, outline, supportive_text)

		# 4) Create Word document
		outfile = save_docx(proposal, base_filename=f"proposal_{request.uuid}")

		return GenerateProposalResponse(status="ok", output_path=outfile)
	except RetryError as rex:
		# Unwrap root cause to aid debugging
		cause = getattr(rex, "last_attempt", None)
		root_exc = None
		try:
			if cause is not None:
				exc_attr = getattr(cause, "exception", None)
				if callable(exc_attr):
					root_exc = exc_attr()
				else:
					root_exc = exc_attr
		except Exception:
			root_exc = None
		msg = f"OpenAI retry failed: {type(root_exc).__name__ if root_exc else type(rex).__name__}: {root_exc or rex}"
		logger.exception(msg)
		raise HTTPException(status_code=502, detail=msg)
	except HTTPException:
		raise
	except Exception as exc:
		logger.exception("Unhandled error in generate_proposal")
		raise HTTPException(status_code=500, detail=str(exc))
