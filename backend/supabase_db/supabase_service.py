import os
from typing import List, Dict, Optional, Any
from supabase import create_client, Client

from routes.config import (
    SUPABASE_URL, SUPABASE_KEY, TABLE_NAME,
    RFP_BUCKET, SUPPORTING_BUCKET, PPT_TEMPLATE_BUCKET, PPT_BUCKET, PDF_BUCKET
)
from routes.logging import logger


class SupabaseService:
    
    def __init__(self):
        """Initialize Supabase client with credentials"""
        try:
            self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            logger.error(f"❌ Failed to initialize Supabase client: {e}")
            raise
    
    
    def get_all_templates(self) -> List[Dict[str, str]]:
        """
        List all PPT templates from ppt_template bucket.
        """
        try:
            logger.info(f"Fetching templates from bucket: {PPT_TEMPLATE_BUCKET}")
            files = self.client.storage.from_(PPT_TEMPLATE_BUCKET).list()
            
            templates = []
            
            for file in files:
                folder_name = file.get('name')
                
                if folder_name:
                    template_file_path = f"{folder_name}/Template.pptx"
                    template_url = self.client.storage.from_(PPT_TEMPLATE_BUCKET).get_public_url(template_file_path)
                    
                    templates.append({
                        "template_uuid": folder_name,
                        "template_name": f"Template {folder_name[:8]}",
                        "template_url": template_url
                    })
            
            logger.info(f"✅ Retrieved {len(templates)} templates")
            
            return templates
            
        except Exception as e:
            logger.error(f"❌ Error fetching templates: {e}")
            raise
    
    
    def fetch_generation_data(self, uuid: str, gen_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch record from ppt_table by uuid AND gen_id.
        """
        try:
            logger.info(f"Fetching record: uuid={uuid}, gen_id={gen_id}")
            response = self.client.table(TABLE_NAME).select("*").eq("uuid", uuid).eq("gen_id", gen_id).execute()
            
            if response.data and len(response.data) > 0:
                record = response.data[0]
                logger.info(f"✅ Record found")
                return record
            else:
                logger.warning(f"⚠️  No record found for uuid={uuid}, gen_id={gen_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error fetching generation data: {e}")
            raise
    
    
    def fetch_generation_data_by_uuid(self, uuid: str) -> Optional[Dict[str, Any]]:
        """
        Fetch record from ppt_table by uuid only.
        Used in /initialgen to get rfp_file and supporting_file URLs.
        """
        try:
            logger.info(f"Fetching record by uuid: {uuid}")
            
            response = self.client.table(TABLE_NAME).select("*").eq("uuid", uuid).execute()
            
            if response.data and len(response.data) > 0:
                record = response.data[0]
                logger.info(f"✅ Record found")
                return record
            else:
                logger.warning(f"⚠️  No record found for uuid={uuid}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error fetching data by uuid: {e}")
            raise
    
    
    def download_file_from_bucket(self, bucket_name: str, file_path: str, local_path: str) -> str:
        """
        Download file from Supabase bucket to local filesystem.
        """
        try:
            logger.info(f"Downloading from {bucket_name}/{file_path} to {local_path}")
            file_data = self.client.storage.from_(bucket_name).download(file_path)
            with open(local_path, 'wb') as f:
                f.write(file_data)
            
            file_size_mb = len(file_data) / (1024 * 1024)
            logger.info(f"✅ Downloaded {file_size_mb:.2f} MB to {local_path}")
            
            return local_path
            
        except Exception as e:
            logger.error(f"❌ Error downloading file from bucket: {e}")
            logger.error(f"   Bucket: {bucket_name}")
            logger.error(f"   File path: {file_path}")
            raise
    
    
    def upload_file_to_bucket(self, bucket_name: str, local_path: str, dest_name: str) -> str:
        """
        Upload file to Supabase bucket and return public URL.
        """
        try:
            logger.info(f"Uploading {local_path} to {bucket_name}/{dest_name}")
            with open(local_path, 'rb') as f:
                file_bytes = f.read()
            
            file_size_mb = len(file_bytes) / (1024 * 1024)
            logger.info(f"   File size: {file_size_mb:.2f} MB")
            
            self.client.storage.from_(bucket_name).upload(
                dest_name,
                file_bytes,
                {"content-type": "application/octet-stream"}
            )
            public_url = self.client.storage.from_(bucket_name).get_public_url(dest_name)
            
            logger.info(f"✅ Uploaded successfully")
            logger.info(f"   URL: {public_url}")
            
            return public_url
            
        except Exception as e:
            logger.error(f"❌ Error uploading file to bucket: {e}")
            logger.error(f"   Bucket: {bucket_name}")
            logger.error(f"   Local path: {local_path}")
            logger.error(f"   Dest name: {dest_name}")
            raise
    
    
    def update_record_by_uuid(self, uuid: str, updates: Dict[str, Any]) -> bool:
        """
        Update ppt_table record by uuid.
        Used in /initialgen to update all fields at once.
        """
        try:
            logger.info(f"Updating record: uuid={uuid}")
            logger.info(f"   Fields to update: {list(updates.keys())}")
            response = self.client.table(TABLE_NAME).update(updates).eq("uuid", uuid).execute()
            
            if response.data and len(response.data) > 0:
                logger.info(f"✅ Record updated successfully")
                return True
            else:
                logger.warning(f"⚠️  Update returned no data for uuid={uuid}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error updating record: {e}")
            logger.error(f"   UUID: {uuid}")
            logger.error(f"   Updates: {updates}")
            raise


# Global instance 
supabase_service = SupabaseService()
