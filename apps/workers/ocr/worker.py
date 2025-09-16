import requests
import time
from datetime import datetime
import logging
import os
from dotenv import load_dotenv
from typing import List, Dict

load_dotenv()

logger = logging.getLogger(__name__)

class OCRWorker:
    def __init__(self):
        self.ocr_key = os.getenv("OCR_KEY")
        self.ocr_endpoint = os.getenv("OCR_ENDPOINT")
        
        if not self.ocr_key or not self.ocr_endpoint:
            raise ValueError("OCR_KEY and OCR_ENDPOINT environment variables are required")
        
        logger.info("OCR Worker initialized for text processing")
    
    def process_file(self, file_content: bytes, file_name: str, file_type: str = "document") -> List[Dict]:
        """Process a single file with OCR using Azure Document Intelligence - Text extraction only"""
        url = f"{self.ocr_endpoint}/formrecognizer/documentModels/prebuilt-layout:analyze?api-version=2023-07-31"
        
        headers = {
            'Ocp-Apim-Subscription-Key': self.ocr_key,
            'Content-Type': 'application/octet-stream'
        }
        
        try:
            logger.info(f"Starting OCR text processing for {file_name}")
            response = requests.post(url, headers=headers, data=file_content)
            
            if response.status_code == 202:
                operation_url = response.headers['Operation-Location']
                poll_headers = {'Ocp-Apim-Subscription-Key': self.ocr_key}
                
                max_attempts = 30
                attempt = 0
                
                logger.info(f"OCR job submitted for {file_name}, polling for results...")
                
                while attempt < max_attempts:
                    result = requests.get(operation_url, headers=poll_headers)
                    data = result.json()
                    
                    if data['status'] == 'succeeded':
                        logger.info(f"OCR processing completed successfully for {file_name}")
                        return self._extract_text_content(data, file_name, file_type)
                        
                    elif data['status'] == 'failed':
                        logger.error(f"OCR failed for {file_name}: {data}")
                        return []
                    else:
                        time.sleep(2)
                        attempt += 1
                
                logger.error(f"OCR polling timeout for {file_name}")
                return []
            else:
                logger.error(f"OCR request failed for {file_name}: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"OCR Error for {file_name}: {e}")
            return []
    
    def _extract_text_content(self, data: Dict, file_name: str, file_type: str) -> List[Dict]:
        """Extract only text content from OCR results - no image processing"""
        text_results = []
        
        if 'analyzeResult' not in data:
            logger.warning(f"No analyzeResult found in OCR response for {file_name}")
            return text_results
        
        analyze_result = data['analyzeResult']
        
        if 'pages' not in analyze_result:
            logger.warning(f"No pages found in OCR results for {file_name}")
            return text_results
        
        logger.info(f"Processing text from {len(analyze_result['pages'])} pages for {file_name}")
        
        for page_idx, page in enumerate(analyze_result['pages']):
            if 'lines' in page:
                content = ' '.join([line['content'] for line in page['lines']])
                if content.strip():
                    text_results.append({
                        "file_name": file_name,
                        "file_type": file_type,
                        "page": page_idx + 1,
                        "content": content,
                        "word_count": len(content.split()),
                        "timestamp": datetime.now().isoformat()
                    })
        
        logger.info(f"Extracted text from {len(text_results)} pages for {file_name}")
        return text_results
    
    def validate_configuration(self) -> bool:
        """Validate OCR service configuration"""
        try:
            if not self.ocr_key:
                logger.error("OCR_KEY not configured")
                return False
            
            if not self.ocr_endpoint:
                logger.error("OCR_ENDPOINT not configured")
                return False
            test_url = f"{self.ocr_endpoint}/formrecognizer/info"
            headers = {'Ocp-Apim-Subscription-Key': self.ocr_key}
            
            response = requests.get(test_url, headers=headers, timeout=10)
            
            if response.status_code in [200, 404]: 
                logger.info("OCR service configuration validated successfully")
                return True
            else:
                logger.error(f"OCR service validation failed: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"OCR service validation error: {e}")
            return False

# Global instance
_ocr_worker = None

def get_ocr_worker():
    """Get or create OCR worker instance"""
    global _ocr_worker
    if _ocr_worker is None:
        _ocr_worker = OCRWorker()
    return _ocr_worker

def is_ocr_available() -> bool:
    """Check if OCR service is available and configured"""
    try:
        worker = get_ocr_worker()
        return worker.validate_configuration()
    except Exception as e:
        logger.error(f"OCR service not available: {e}")
        return False

if __name__ == "__main__":
    try:
        worker = get_ocr_worker()
        print("OCR Worker initialized successfully (text-only processing)")
        print("Configuration Valid:", worker.validate_configuration())
    except Exception as e:
        print(f"Failed to initialize OCR Worker: {e}")
