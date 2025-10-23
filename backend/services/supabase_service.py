from supabase import create_client, Client
from core.config import settings
from core.logger import get_logger

logger = get_logger("supabase")

class SupabaseService:
    def __init__(self):
        self.client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        logger.info("supabase client ready")

    def get_templates(self):
        files = self.client.storage.from_(settings.PPT_TEMPLATE_BUCKET).list()
        templates = []
        for file in files:
            folder_name = file.get("name")
            if folder_name:
                template_file = f"{folder_name}/Template.pptx"
                url = self.client.storage.from_(settings.PPT_TEMPLATE_BUCKET).get_public_url(template_file)
                templates.append({
                    "template_uuid": folder_name,
                    "template_name": f"Template {folder_name[:8]}",
                    "template_url": url,
                })
        return templates

    def fetch_record_by_uuid(self, uuid: str):
        res = self.client.table(settings.TABLE_NAME).select("*").eq("uuid", uuid).execute()
        rec = res.data[0] if res.data else None
        return rec

    def fetch_record(self, uuid: str, gen_id: str):
        res = self.client.table(settings.TABLE_NAME).select("*").eq("uuid", uuid).eq("gen_id", gen_id).execute()
        return res.data[0] if res.data else None

    def download_file(self, bucket: str, file_path: str) -> bytes:
        data = self.client.storage.from_(bucket).download(file_path)
        return data

    def upload_bytes(self, bucket: str, dest_name: str, file_bytes: bytes, content_type="application/octet-stream"):
        self.client.storage.from_(bucket).upload(dest_name, file_bytes, {"content-type": content_type})
        return self.client.storage.from_(bucket).get_public_url(dest_name)

    def update_record_by_uuid(self, uuid: str, updates: dict):
        self.client.table(settings.TABLE_NAME).update(updates).eq("uuid", uuid).execute()
        return True

supabase_service = SupabaseService()
