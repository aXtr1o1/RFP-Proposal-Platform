import os
import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict
from azure.storage.blob import BlobServiceClient, ContentSettings 
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

logger = logging.getLogger(__name__)

class AzureBlobStorageService:
    def __init__(self):
        # Azure Blob Storage configuration
        self.connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        self.container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "rfp-images")
        
        if not self.connection_string:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING environment variable is required")
        
        try:
            # Initialize Azure Blob Service Client
            self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
            
            # Initialize container client
            self.container_client = self.blob_service_client.get_container_client(self.container_name)
            
            # Ensure container exists
            self._ensure_container_exists()
            
            logger.info("Azure Blob Storage initialized successfully")
            logger.info(f"Storage Account: {self.blob_service_client.account_name}")
            logger.info(f"Container: {self.container_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Azure Blob Storage: {e}")
            raise
    
    def _ensure_container_exists(self):
        """Create container if it doesn't exist"""
        try:
            # Check if container exists
            self.container_client.get_container_properties()
            logger.info(f"Container '{self.container_name}' already exists")
        except ResourceNotFoundError:
            try:
                # Create container with public blob access
                self.container_client.create_container(public_access="blob")
                logger.info(f"Created container '{self.container_name}' with public blob access")
            except ResourceExistsError:
                # Container was created by another process
                logger.info(f"Container '{self.container_name}' created by another process")
            except Exception as e:
                logger.error(f"Error creating container: {e}")
                raise
        except Exception as e:
            logger.error(f"Error checking container: {e}")
            raise
    
    def store_image(self, image_data: bytes, original_filename: str, folder_name: str) -> str:
        """Store image in Azure Blob Storage and return blob URL"""
        try:
            # Generate unique blob name with folder structure
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_extension = os.path.splitext(original_filename)[1]
            base_name = os.path.splitext(original_filename)[0]
            
            # Clean filename for blob storage
            clean_base_name = "".join(c for c in base_name if c.isalnum() or c in ('-', '_')).rstrip()
            if not clean_base_name:  # If no valid characters, use a default
                clean_base_name = "image"
            
            blob_name = f"{folder_name}/{timestamp}_{uuid.uuid4().hex[:8]}_{clean_base_name}{file_extension}"
            
            # Get blob client
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Set content type based on file extension
            content_type = self._get_content_type(file_extension)
            
            # ✅ FIXED: Use ContentSettings class properly
            content_settings = ContentSettings(
                content_type=content_type,
                cache_control='public, max-age=31536000',  # 1 year cache
            )
            
            # Upload image data with metadata
            blob_client.upload_blob(
                image_data, 
                overwrite=True,
                content_settings=content_settings,
                metadata={
                    'original_filename': original_filename,
                    'folder_name': folder_name,
                    'upload_timestamp': timestamp,
                    'file_size': str(len(image_data))
                }
            )
            
            # Get the blob URL
            blob_url = blob_client.url
            
            logger.info("Successfully uploaded image to Azure Blob Storage")
            logger.info(f"Blob name: {blob_name}")
            logger.info(f"Blob URL: {blob_url}")
            logger.info(f"File size: {len(image_data)} bytes")
            
            return blob_url
            
        except Exception as e:
            logger.error(f"Error storing image {original_filename} in Azure Blob Storage: {e}")
            return f"error_storing_{original_filename}"
    
    def _get_content_type(self, file_extension: str) -> str:
        """Get content type based on file extension"""
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            '.tiff': 'image/tiff',
            '.tif': 'image/tiff',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon'
        }
        return content_types.get(file_extension.lower(), 'application/octet-stream')
    
    def get_image_url(self, blob_name: str) -> Optional[str]:
        """Get URL for a specific blob"""
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            return blob_client.url
        except Exception as e:
            logger.error(f"Error getting image URL for {blob_name}: {e}")
            return None
    
    def list_images(self, folder_prefix: str = None) -> List[Dict]:
        """List all images in the container or specific folder"""
        try:
            blobs = []
            name_starts_with = f"{folder_prefix}/" if folder_prefix else None
            
            for blob in self.container_client.list_blobs(name_starts_with=name_starts_with):
                blob_info = {
                    'name': blob.name,
                    'url': f"https://{self.blob_service_client.account_name}.blob.core.windows.net/{self.container_name}/{blob.name}",
                    'size': blob.size,
                    'size_mb': round(blob.size / (1024 * 1024), 3),
                    'last_modified': blob.last_modified.isoformat() if blob.last_modified else None,
                    'content_type': blob.content_settings.content_type if blob.content_settings else None,
                    'folder': blob.name.split('/')[0] if '/' in blob.name else 'root',
                    'metadata': blob.metadata if blob.metadata else {}
                }
                blobs.append(blob_info)
            
            logger.info(f"Listed {len(blobs)} blobs from container '{self.container_name}'")
            if folder_prefix:
                logger.info(f"Filtered by folder prefix: {folder_prefix}")
            
            return blobs
            
        except Exception as e:
            logger.error(f"Error listing images from Azure Blob Storage: {e}")
            return []
    
    def delete_image(self, blob_name: str) -> bool:
        """Delete an image from Azure Blob Storage"""
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            blob_client.delete_blob()
            logger.info(f"Successfully deleted blob: {blob_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting image {blob_name} from Azure Blob Storage: {e}")
            return False
    
    def get_blob_metadata(self, blob_name: str) -> Dict:
        """Get metadata for a specific blob"""
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            properties = blob_client.get_blob_properties()
            
            return {
                'name': blob_name,
                'url': blob_client.url,
                'size': properties.size,
                'size_mb': round(properties.size / (1024 * 1024), 3),
                'last_modified': properties.last_modified.isoformat() if properties.last_modified else None,
                'content_type': properties.content_settings.content_type if properties.content_settings else None,
                'etag': properties.etag,
                'metadata': properties.metadata if properties.metadata else {},
                'creation_time': properties.creation_time.isoformat() if properties.creation_time else None
            }
        except Exception as e:
            logger.error(f"Error getting blob metadata for {blob_name}: {e}")
            return {}
    
    def get_storage_stats(self) -> Dict:
        """Get comprehensive storage statistics"""
        try:
            blobs = list(self.container_client.list_blobs())
            total_size = sum(blob.size for blob in blobs)
            
            # Group by folder
            folder_stats = {}
            file_types = {}
            
            for blob in blobs:
                # Folder statistics
                folder = blob.name.split('/')[0] if '/' in blob.name else 'root'
                if folder not in folder_stats:
                    folder_stats[folder] = {'count': 0, 'size': 0}
                folder_stats[folder]['count'] += 1
                folder_stats[folder]['size'] += blob.size
                
                # File type statistics
                if blob.content_settings and blob.content_settings.content_type:
                    content_type = blob.content_settings.content_type
                    if content_type not in file_types:
                        file_types[content_type] = {'count': 0, 'size': 0}
                    file_types[content_type]['count'] += 1
                    file_types[content_type]['size'] += blob.size
            
            # Add size in MB to folder stats
            for folder in folder_stats:
                folder_stats[folder]['size_mb'] = round(folder_stats[folder]['size'] / (1024 * 1024), 3)
            
            return {
                'container_name': self.container_name,
                'storage_account': self.blob_service_client.account_name,
                'total_blobs': len(blobs),
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 3),
                'total_size_gb': round(total_size / (1024 * 1024 * 1024), 3),
                'folder_statistics': folder_stats,
                'file_type_statistics': file_types,
                'container_url': f"https://{self.blob_service_client.account_name}.blob.core.windows.net/{self.container_name}"
            }
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {'error': str(e)}
    
    def check_blob_exists(self, blob_name: str) -> bool:
        """Check if a blob exists"""
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            blob_client.get_blob_properties()
            return True
        except ResourceNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error checking if blob exists {blob_name}: {e}")
            return False
    
    def get_container_info(self) -> Dict:
        """Get container information"""
        try:
            properties = self.container_client.get_container_properties()
            return {
                'name': self.container_name,
                'last_modified': properties.last_modified.isoformat() if properties.last_modified else None,
                'etag': properties.etag,
                'lease_status': properties.lease.status if properties.lease else None,
                'public_access': properties.public_access,
                'metadata': properties.metadata if properties.metadata else {},
                'account_name': self.blob_service_client.account_name
            }
        except Exception as e:
            logger.error(f"Error getting container info: {e}")
            return {'error': str(e)}
    
    def cleanup_old_blobs(self, days_old: int = 30) -> Dict:
        """Clean up blobs older than specified days"""
        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            deleted_count = 0
            total_size_freed = 0
            errors = []
            
            for blob in self.container_client.list_blobs():
                if blob.last_modified and blob.last_modified.replace(tzinfo=None) < cutoff_date:
                    try:
                        blob_client = self.container_client.get_blob_client(blob.name)
                        blob_client.delete_blob()
                        deleted_count += 1
                        total_size_freed += blob.size
                        logger.info(f"Deleted old blob: {blob.name}")
                    except Exception as e:
                        errors.append(f"Failed to delete {blob.name}: {str(e)}")
            
            return {
                'deleted_count': deleted_count,
                'total_size_freed_bytes': total_size_freed,
                'total_size_freed_mb': round(total_size_freed / (1024 * 1024), 3),
                'errors': errors,
                'cutoff_date': cutoff_date.isoformat()
            }
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {'error': str(e)}

# Global instance
_azure_blob_service = None

def get_blob_service():
    """Get or create Azure Blob Storage service instance"""
    global _azure_blob_service
    if _azure_blob_service is None:
        _azure_blob_service = AzureBlobStorageService()
    return _azure_blob_service

def is_blob_service_available() -> bool:
    """Check if Azure Blob Storage service is available"""
    try:
        service = get_blob_service()
        return service is not None
    except Exception as e:
        logger.error(f"Blob service not available: {e}")
        return False
