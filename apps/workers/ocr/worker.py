import requests
import time
from datetime import datetime
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class OCRWorker:
    def __init__(self):
        self.ocr_key = os.getenv("OCR_KEY")
        self.ocr_endpoint = os.getenv("OCR_ENDPOINT")
    
    def process_file(self, file_content, file_name, file_type="document"):
        """Process a single file with OCR using Azure Document Intelligence"""
        url = f"{self.ocr_endpoint}/formrecognizer/documentModels/prebuilt-layout:analyze?api-version=2023-07-31"
        
        headers = {
            'Ocp-Apim-Subscription-Key': self.ocr_key,
            'Content-Type': 'application/octet-stream'
        }
        
        try:
            logger.info(f"Starting OCR processing for {file_name}")
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
                        pages_data = []
                        if 'analyzeResult' in data and 'pages' in data['analyzeResult']:
                            for page_idx, page in enumerate(data['analyzeResult']['pages']):
                                if 'lines' in page:
                                    content = ' '.join([line['content'] for line in page['lines']])
                                    if content.strip():
                                        pages_data.append({
                                            "file_name": file_name,
                                            "file_type": file_type,
                                            "page": page_idx + 1,
                                            "content": content,
                                            "word_count": len(content.split()),
                                            "timestamp": datetime.now().isoformat()
                                        })
                        
                        logger.info(f"Extracted text from {len(pages_data)} pages for {file_name}")
                        return pages_data
                        
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

if __name__ == "__main__":
    worker = OCRWorker()
    print("OCR Worker initialized and ready")
