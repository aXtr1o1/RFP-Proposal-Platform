import logging
import os
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from supabase import Client, create_client
from postgrest.exceptions import APIError
from config import settings

logger = logging.getLogger("supabase_service")


class SupabaseService:
    """
    Service for all Supabase database and storage operations
    """
    
    def __init__(self):
        """Initialize Supabase client with validation"""
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be configured")
        
        # Validate URL format
        if not settings.SUPABASE_URL.startswith(('http://', 'https://')):
            raise ValueError(f"Invalid SUPABASE_URL format: {settings.SUPABASE_URL}")
        
        self.client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        self.word_table = os.getenv("WORD_TABLE", "word_gen")
        self.ppt_table = os.getenv("PPT_TABLE", "ppt_gen")
        self.ppt_bucket = os.getenv("PPT_BUCKET", "ppt")
        
        logger.info("SupabaseService initialized")
        logger.info(f"   Word Table: {self.word_table}")
        logger.info(f"   PPT Table: {self.ppt_table}")
        logger.info(f"   PPT Bucket: {self.ppt_bucket}")
    
    # ==================== MARKDOWN FETCHING ====================
    
    async def fetch_markdown_content(
        self, 
        uuid_str: str, 
        gen_id: str,
        max_retries: int = 3
    ) -> str:
        """
        Fetch markdown content from word_gen table with retry logic
        """
        if not uuid_str or not gen_id:
            raise ValueError("UUID and Gen ID are required")
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Fetching markdown (attempt {attempt}/{max_retries}): uuid={uuid_str}, gen_id={gen_id}")
                
                response = (
                    self.client.table(self.word_table)
                    .select("generated_markdown")
                    .eq("uuid", uuid_str)
                    .eq("gen_id", gen_id)
                    .single()
                    .execute()
                )
                
                if not response.data:
                    raise RuntimeError(f"No data found for uuid={uuid_str}, gen_id={gen_id}")
                
                markdown = response.data.get("generated_markdown")
                
                if not markdown:
                    raise RuntimeError(f"Markdown field is empty for uuid={uuid_str}, gen_id={gen_id}")
                
                logger.info(f"Fetched markdown: {len(markdown)} characters")
                return markdown
            
            except APIError as e:
                logger.warning(f"Supabase API error on attempt {attempt}: {e}")
                if attempt < max_retries:
                    import asyncio
                    wait_time = 2 ** attempt
                    logger.info(f"   Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("Max retries reached")
                    raise RuntimeError(f"Failed to fetch markdown after {max_retries} attempts") from e
            
            except Exception as e:
                logger.exception(f"fetch_markdown_content failed: {e}")
                raise RuntimeError(f"Failed to fetch markdown: {str(e)}") from e
        
        raise RuntimeError("Failed to fetch markdown after all retries")
    
    # ==================== INITIAL GENERATION ====================
    
    async def save_generation_record(
        self,
        uuid_str: str,
        gen_id: str,
        ppt_genid: str,
        ppt_url: str,
        generated_content: Dict[str, Any],
        language: str,
        template_id: str,  # This is the template name (e.g., "arweqah")
        user_preference: str = "",
        max_retries: int = 3
    ) -> str:
        """
        Save generation record to ppt_gen table with retry logic
        """
        if not all([uuid_str, gen_id, ppt_genid, ppt_url, template_id]):
            raise ValueError("uuid, gen_id, ppt_genid, ppt_url, and template_id are required")
        
        if not generated_content:
            raise ValueError("generated_content cannot be empty")
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"💾 Saving generation record (attempt {attempt}/{max_retries}): ppt_genid={ppt_genid}")
                
                payload = {
                    "uuid": uuid_str,
                    "gen_id": gen_id,
                    "ppt_genid": ppt_genid,
                    "ppt_template": template_id,  # ✅ Template name goes here
                    "general_preference": user_preference if user_preference else None,
                    "generated_content": json.dumps(generated_content),
                    "proposal_ppt": ppt_url,
                    "regen_comments": None,
                    "created_at": datetime.utcnow().isoformat()
                }
                
                self.client.table(self.ppt_table).insert(payload).execute()
                logger.info(f"✅ Generation record saved: {ppt_genid}")
                logger.info(f"   Template: {template_id}")
                logger.info(f"   Language: {language}")
                
                return ppt_genid
            
            except APIError as e:
                logger.warning(f"Supabase API error on attempt {attempt}: {e}")
                if attempt < max_retries:
                    import asyncio
                    wait_time = 2 ** attempt
                    logger.info(f"   Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("Max retries reached")
                    raise RuntimeError(f"Failed to save generation record after {max_retries} attempts") from e
            
            except Exception as e:
                logger.exception(f"save_generation_record failed: {e}")
                raise RuntimeError(f"Failed to save generation record: {str(e)}") from e
        
        raise RuntimeError("Failed to save generation record after all retries")

    
    # ==================== REGENERATION ====================
    
    async def save_regeneration_record(
        self,
        uuid_str: str,
        gen_id: str,
        ppt_genid: str,
        ppt_url: str,
        generated_content: Dict[str, Any],
        language: str,
        regen_comments: List[Dict[str, str]],
        max_retries: int = 3
    ) -> str:
        """
        Save regeneration record to ppt_gen table with retry logic
        """
        if not all([uuid_str, gen_id, ppt_genid, ppt_url]):
            raise ValueError("UUID, Gen ID, PPT Gen ID, and PPT URL are required")
        
        if not regen_comments:
            raise ValueError("Regeneration comments are required")
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Saving regeneration record (attempt {attempt}/{max_retries}): ppt_genid={ppt_genid}")
                
                payload = {
                    "uuid": uuid_str,
                    "gen_id": gen_id,
                    "ppt_genid": ppt_genid,
                    "general_preference": None,
                    "generated_content": json.dumps(generated_content),
                    "proposal_ppt": ppt_url,
                    "ppt_template": generated_content.get("template_id"),
                    "regen_comments": json.dumps(regen_comments),
                    "created_at": datetime.utcnow().isoformat()
                }
                
                self.client.table(self.ppt_table).insert(payload).execute()
                logger.info(f"Regeneration record saved: {ppt_genid}")
                
                return ppt_genid
            
            except APIError as e:
                logger.warning(f"Supabase API error on attempt {attempt}: {e}")
                if attempt < max_retries:
                    import asyncio
                    wait_time = 2 ** attempt
                    logger.info(f"   Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("Max retries reached")
                    raise RuntimeError(f"Failed to save regeneration record after {max_retries} attempts") from e
            
            except Exception as e:
                logger.exception(f"save_regeneration_record failed: {e}")
                raise RuntimeError(f"Failed to save regeneration record: {str(e)}") from e
        
        raise RuntimeError("Failed to save regeneration record after all retries")
    
    # ==================== CONTENT RETRIEVAL ====================
    
    async def get_generation_content(
        self, 
        uuid_str: str, 
        gen_id: str, 
        ppt_genid: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Retrieve generation content from ppt_gen table with retry logic
        """
        if not all([uuid_str, gen_id, ppt_genid]):
            raise ValueError("UUID, Gen ID, and PPT Gen ID are required")
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Fetching generation content (attempt {attempt}/{max_retries}): ppt_genid={ppt_genid}")
                
                response = (
                    self.client.table(self.ppt_table)
                    .select("generated_content, ppt_template")
                    .eq("uuid", uuid_str)
                    .eq("gen_id", gen_id)
                    .eq("ppt_genid", ppt_genid)
                    .single()
                    .execute()
                )
                
                if not response.data:
                    raise RuntimeError(f"No content found for ppt_genid={ppt_genid}")
                
                content_json = response.data.get("generated_content", "{}")
                
                # Parse JSON string
                if isinstance(content_json, str):
                    content = json.loads(content_json)
                else:
                    content = content_json
                
                # Add template_id from ppt_template field
                if "template_id" not in content and response.data.get("ppt_template"):
                    content["template_id"] = response.data["ppt_template"]
                
                logger.info(f"Retrieved generation content")
                return content
            
            except APIError as e:
                logger.warning(f"Supabase API error on attempt {attempt}: {e}")
                if attempt < max_retries:
                    import asyncio
                    wait_time = 2 ** attempt
                    logger.info(f"   Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("Max retries reached")
                    raise RuntimeError(f"Failed to get generation content after {max_retries} attempts") from e
            
            except Exception as e:
                logger.exception(f"get_generation_content failed: {e}")
                raise RuntimeError(f"Failed to get generation content: {str(e)}") from e
        
        raise RuntimeError("Failed to get generation content after all retries")
    
    # ==================== FILE UPLOAD ====================
    
    async def upload_pptx(
        self, 
        local_path: str, 
        uuid_str: str, 
        gen_id: str, 
        ppt_genid: str,
        max_retries: int = 3
    ) -> str:
        """
        Upload PPTX file to Supabase storage with retry logic
        """
        if not all([local_path, uuid_str, gen_id, ppt_genid]):
            raise ValueError("All parameters are required")
        
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"PPTX file not found: {local_path}")
        
        # Check file size
        file_size = os.path.getsize(local_path)
        logger.info(f"📊 File size: {file_size / 1024 / 1024:.2f} MB")
        
        if file_size > 100 * 1024 * 1024:  # 100 MB limit
            raise ValueError(f"File too large: {file_size / 1024 / 1024:.2f} MB (max 100 MB)")
        
        # Create storage path
        remote_key = f"{uuid_str}/{gen_id}/{ppt_genid}.pptx"
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"☁️ Uploading PPTX (attempt {attempt}/{max_retries}) to bucket={self.ppt_bucket}, key={remote_key}")
                
                # Read file
                with open(local_path, "rb") as file_obj:
                    file_data = file_obj.read()
                
                # Remove existing file if present
                try:
                    self.client.storage.from_(self.ppt_bucket).remove([remote_key])
                    logger.info(f"   Removed existing file: {remote_key}")
                except Exception:
                    pass  # File doesn't exist, that's fine
                
                # Upload new file
                self.client.storage.from_(self.ppt_bucket).upload(
                    remote_key,
                    file_data,
                    {
                        "content-type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        "upsert": "true"
                    }
                )
                
                # Get public URL
                public_url = self.client.storage.from_(self.ppt_bucket).get_public_url(remote_key)
                
                logger.info(f"PPTX uploaded: {remote_key}")
                logger.info(f"   Public URL: {public_url}")
                
                return public_url
            
            except Exception as e:
                logger.warning(f"Upload error on attempt {attempt}: {e}")
                if attempt < max_retries:
                    import asyncio
                    wait_time = 2 ** attempt
                    logger.info(f"   Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("Max retries reached")
                    raise RuntimeError(f"Failed to upload PPTX after {max_retries} attempts") from e
        
        raise RuntimeError("Failed to upload PPTX after all retries")
    
    # ==================== DOWNLOAD ====================
    
    async def get_proposal_url(
        self, 
        uuid_str: str, 
        gen_id: str, 
        ppt_genid: str,
        max_retries: int = 3
    ) -> Optional[str]:
        """
        Get proposal PPT URL for download with retry logic
        """
        if not all([uuid_str, gen_id, ppt_genid]):
            raise ValueError("UUID, Gen ID, and PPT Gen ID are required")
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f" Fetching proposal URL (attempt {attempt}/{max_retries}): ppt_genid={ppt_genid}")
                
                response = (
                    self.client.table(self.ppt_table)
                    .select("proposal_ppt")
                    .eq("uuid", uuid_str)
                    .eq("gen_id", gen_id)
                    .eq("ppt_genid", ppt_genid)
                    .single()
                    .execute()
                )
                
                if not response.data:
                    logger.warning(f"No record found for ppt_genid={ppt_genid}")
                    return None
                
                url = response.data.get("proposal_ppt")
                
                if url:
                    logger.info(f"Proposal URL found")
                else:
                    logger.warning(f"No proposal_ppt URL in record")
                
                return url
            
            except APIError as e:
                logger.warning(f"Supabase API error on attempt {attempt}: {e}")
                if attempt < max_retries:
                    import asyncio
                    wait_time = 2 ** attempt
                    logger.info(f"   Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("Max retries reached")
                    return None
            
            except Exception as e:
                logger.exception(f"get_proposal_url failed: {e}")
                return None
        
        return None


# ==================== STANDALONE FUNCTIONS ====================

async def get_proposal_url(uuid_str: str, gen_id: str, ppt_genid: str) -> Optional[str]:
    """Standalone function for API endpoint"""
    service = SupabaseService()
    return await service.get_proposal_url(uuid_str, gen_id, ppt_genid)
