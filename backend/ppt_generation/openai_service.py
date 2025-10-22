import os
from typing import List
from openai import OpenAI

from routes.config import OPENAI_API_KEY, OPENAI_MODEL, MAX_OUTPUT_TOKENS
from routes.logging import logger

client = OpenAI(api_key=OPENAI_API_KEY)


def upload_pdf_to_openai(file_path: str) -> str:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    try:
        logger.info(f"Uploading file to OpenAI: {file_path}")
        
        with open(file_path, "rb") as f:
            file_obj = client.files.create(
                file=f,
                purpose="assistants"
            )
        
        file_id = file_obj.id
        logger.info(f"File uploaded successfully. File ID: {file_id}")
        
        return file_id
        
    except Exception as e:
        logger.error(f"Error uploading file to OpenAI: {e}")
        raise


def generate_proposal_content(
    system_prompt: str,
    task_prompt: str,
    rfp_id: str,
    supporting_id: str
) -> str:
    try:
        logger.info("🚀 Calling OpenAI Responses API...")
        input_content = [
            {"type": "input_text", "text": system_prompt},
            {"type": "input_file", "file_id": rfp_id},
            {"type": "input_file", "file_id": supporting_id},
            {"type": "input_text", "text": task_prompt},
        ]

        response = client.responses.create(
            model=OPENAI_MODEL,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            input=[{
                "role": "user",
                "content": input_content
            }],
            stream=True
        )
        
        logger.info("📥 Streaming response from OpenAI...")
        print("\n" + "=" * 80)
        print("GENERATING PROPOSAL CONTENT (streaming)...")
        print("=" * 80 + "\n")
        
        chunks: List[str] = []
        
        for event in response:
            event_type = getattr(event, "type", "")
            
            if event_type == "response.output_text.delta":
                delta = getattr(event, "delta", "")
                if delta:
                    chunks.append(delta)
                    print(delta, end="", flush=True)
                    
            elif event_type == "response.error":
                error = getattr(event, "error", "OpenAI stream error")
                logger.error(f"❌ OpenAI API Error: {error}")
                print(f"\n\n❌ ERROR: {error}\n")
                raise RuntimeError(str(error))
                
            elif event_type == "response.completed":
                break
        
        print("\n" + "=" * 80 + "\n")
        
        raw_output = "".join(chunks)
        
        logger.info(f"✅ Received {len(raw_output)} characters from OpenAI")
        
        return raw_output
        
    except Exception as e:
        logger.error(f"❌ Error calling OpenAI Responses API: {e}")
        raise
