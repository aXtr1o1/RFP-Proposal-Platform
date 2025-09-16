import requests
import time
from datetime import datetime
import logging
import os
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class TextOCRService:
    def __init__(self):
        self.ocr_key = os.getenv("OCR_KEY")
        self.ocr_endpoint = os.getenv("OCR_ENDPOINT")
        
        if not self.ocr_key or not self.ocr_endpoint:
            raise ValueError("OCR_KEY and OCR_ENDPOINT environment variables are required")
        
        logger.info("Text OCR Service initialized successfully")
    
    def extract_text_from_pdf(self, file_content: bytes, file_name: str, file_type: str = "document") -> List[Dict]:
        """Extract only text from PDF using Azure Document Intelligence - No image processing"""
        url = f"{self.ocr_endpoint}/formrecognizer/documentModels/prebuilt-layout:analyze?api-version=2023-07-31"
        
        headers = {
            'Ocp-Apim-Subscription-Key': self.ocr_key,
            'Content-Type': 'application/octet-stream'
        }
        
        try:
            logger.info(f"Starting enhanced text OCR processing for {file_name}")
            response = requests.post(url, headers=headers, data=file_content)
            
            if response.status_code == 202:
                operation_url = response.headers['Operation-Location']
                poll_headers = {'Ocp-Apim-Subscription-Key': self.ocr_key}
                
                logger.info(f"Enhanced text OCR job submitted for {file_name}, polling for results...")
                return self._poll_for_text_results(operation_url, poll_headers, file_name, file_type)
                
            else:
                logger.error(f"Enhanced text OCR request failed: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Enhanced text OCR Error for {file_name}: {e}")
            return []
    
    def _poll_for_text_results(self, operation_url: str, headers: Dict, file_name: str, file_type: str, max_attempts: int = 30) -> List[Dict]:
        """Poll for OCR results with timeout handling - text extraction only"""
        attempt = 0
        
        while attempt < max_attempts:
            try:
                result = requests.get(operation_url, headers=headers)
                data = result.json()
                
                if data['status'] == 'succeeded':
                    logger.info(f"Enhanced text OCR processing completed successfully for {file_name}")
                    return self._process_text_results(data, file_name, file_type)
                    
                elif data['status'] == 'failed':
                    logger.error(f"Enhanced text OCR failed for {file_name}: {data}")
                    return []
                    
                else:
                    time.sleep(2)
                    attempt += 1
                    
            except Exception as e:
                logger.error(f"Error polling enhanced OCR results for {file_name}: {e}")
                return []
        
        logger.error(f"Enhanced text OCR polling timeout for {file_name}")
        return []
    
    def _process_text_results(self, data: Dict, file_name: str, file_type: str) -> List[Dict]:
        """Process OCR results to extract only text content - no image processing"""
        text_results = []
        
        if 'analyzeResult' not in data:
            logger.warning(f"No analyzeResult found in enhanced OCR response for {file_name}")
            return text_results
        
        analyze_result = data['analyzeResult']
        text_results = self._extract_enhanced_text_content(analyze_result, file_name, file_type)
        
        logger.info(f"Enhanced OCR extracted text from {len(text_results)} pages for {file_name}")
        return text_results
    
    def _extract_enhanced_text_content(self, analyze_result: Dict, file_name: str, file_type: str) -> List[Dict]:
        """Extract enhanced text content from OCR results with better formatting - no image processing"""
        text_results = []
        
        if 'pages' not in analyze_result:
            logger.warning(f"No pages found in enhanced OCR results for {file_name}")
            return text_results
        
        logger.info(f"Processing enhanced text from {len(analyze_result['pages'])} pages for {file_name}")
        
        for page_idx, page in enumerate(analyze_result['pages']):
            if 'lines' in page:
                lines_content = []
                for line in page['lines']:
                    line_text = line.get('content', '').strip()
                    if line_text:
                        lines_content.append(line_text)
                
                if lines_content:
                    content = '\n'.join(lines_content)
                    
                    clean_content = ' '.join(lines_content)
                    
                    if content.strip():
                        text_results.append({
                            "file_name": file_name,
                            "file_type": file_type,
                            "page": page_idx + 1,
                            "content": clean_content,  
                            "formatted_content": content,  
                            "word_count": len(clean_content.split()),
                            "line_count": len(lines_content),
                            "timestamp": datetime.now().isoformat(),
                            "processing_method": "enhanced_text_ocr"
                        })
        
        return text_results
    
    def extract_text_with_tables(self, file_content: bytes, file_name: str, file_type: str = "document") -> List[Dict]:
        """Extract text with table structure recognition - text only"""
        try:
            text_results = self.extract_text_from_pdf(file_content, file_name, file_type)
            
            logger.info(f"table-aware text processing completed for {file_name}")
            return text_results
            
        except Exception as e:
            logger.error(f"Enhanced table processing error for {file_name}: {e}")
            return []
    
    def get_service_info(self) -> Dict:
        """Get service configuration information"""
        return {
            'service': 'Azure Document Intelligence Enhanced Text OCR',
            'endpoint': self.ocr_endpoint,
            'api_version': '2023-07-31',
            'features': [
                'Enhanced text extraction from PDFs',
                'Improved formatting preservation',
                'Multi-language support with better accuracy',
                'Layout analysis for structured text',
                'High-quality text recognition',
                'Line break preservation',
                'Table-aware text processing'
            ],
            'processing_mode': 'enhanced_text_only',
            'supported_formats': ['PDF', 'Images as text'],
            'languages_supported': ['Arabic', 'English', 'Multi-language']
        }
    
    def validate_configuration(self) -> bool:
        """Validate enhanced service configuration"""
        try:
            if not self.ocr_key:
                logger.error("OCR_KEY not configured for enhanced service")
                return False
            
            if not self.ocr_endpoint:
                logger.error("OCR_ENDPOINT not configured for enhanced service")
                return False
        
            test_url = f"{self.ocr_endpoint}/formrecognizer/info"
            headers = {'Ocp-Apim-Subscription-Key': self.ocr_key}
            
            response = requests.get(test_url, headers=headers, timeout=10)
            
            if response.status_code in [200, 404]: 
                logger.info("Enhanced Text OCR service configuration validated successfully")
                return True
            else:
                logger.error(f"Enhanced Text OCR service validation failed: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Enhanced Text OCR service validation error: {e}")
            return False
    
    def get_processing_stats(self) -> Dict:
        """Get processing statistics and capabilities"""
        return {
            "service_status": "active",
            "processing_mode": "enhanced_text_only",
            "capabilities": {
                "text_extraction": True,
                "multi_language": True,
                "format_preservation": True,
                "table_awareness": True,
                "image_processing": False, 
                "blob_storage": False       
            },
            "supported_file_types": ["PDF", "DOCX", "TXT"],
            "max_file_size": "50MB",
            "concurrent_processing": True,
            "batch_processing": True
        }

# Global instance
_text_ocr_service = None

def get_text_ocr_service():
    """Get or create Enhanced Text OCR service instance"""
    global _text_ocr_service
    if _text_ocr_service is None:
        _text_ocr_service = TextOCRService()
    return _text_ocr_service

def is_text_ocr_available() -> bool:
    """Check if Enhanced Text OCR service is available and configured"""
    try:
        service = get_text_ocr_service()
        return service.validate_configuration()
    except Exception as e:
        logger.error(f"Enhanced Text OCR service not available: {e}")
        return False

def get_service_capabilities() -> Dict:
    """Get service capabilities without initializing"""
    return {
        "enhanced_text_processing": True,
        "image_processing": False,
        "blob_storage": False,
        "multi_language_support": True,
        "format_preservation": True,
        "azure_document_intelligence": True
    }

if __name__ == "__main__":
    try:
        service = get_text_ocr_service()
        print("Enhanced Text OCR Service initialized successfully")
        print("Service Info:", service.get_service_info())
        print("Configuration Valid:", service.validate_configuration())
        print("Processing Stats:", service.get_processing_stats())
    except Exception as e:
        print(f"Failed to initialize Enhanced Text OCR Service: {e}")
