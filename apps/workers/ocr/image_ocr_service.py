import requests
import time
import uuid
from datetime import datetime
import logging
import os
from typing import List, Dict, Tuple, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class ImageOCRService:
    def __init__(self):
        self.ocr_key = os.getenv("OCR_KEY")
        self.ocr_endpoint = os.getenv("OCR_ENDPOINT")
        
        if not self.ocr_key or not self.ocr_endpoint:
            raise ValueError("OCR_KEY and OCR_ENDPOINT environment variables are required")
        
        logger.info("Image OCR Service initialized successfully")
    
    def extract_text_and_images_from_pdf(self, file_content: bytes, file_name: str) -> Tuple[List[Dict], List[Dict]]:
        """Extract both text and images from PDF using Azure Document Intelligence"""
        url = f"{self.ocr_endpoint}/formrecognizer/documentModels/prebuilt-layout:analyze?api-version=2023-07-31"
        
        headers = {
            'Ocp-Apim-Subscription-Key': self.ocr_key,
            'Content-Type': 'application/octet-stream'
        }
        
        try:
            logger.info(f"Starting enhanced OCR processing (text + images) for {file_name}")
            response = requests.post(url, headers=headers, data=file_content)
            
            if response.status_code == 202:
                operation_url = response.headers['Operation-Location']
                poll_headers = {'Ocp-Apim-Subscription-Key': self.ocr_key}
                
                logger.info(f"Enhanced OCR job submitted for {file_name}, polling for results...")
                return self._poll_for_results(operation_url, poll_headers, file_name)
                
            else:
                logger.error(f"Enhanced OCR request failed: HTTP {response.status_code}")
                return [], []
                
        except Exception as e:
            logger.error(f"Enhanced OCR Error for {file_name}: {e}")
            return [], []
    
    def _poll_for_results(self, operation_url: str, headers: Dict, file_name: str, max_attempts: int = 30) -> Tuple[List[Dict], List[Dict]]:
        """Poll for OCR results with timeout handling"""
        attempt = 0
        
        while attempt < max_attempts:
            try:
                result = requests.get(operation_url, headers=headers)
                data = result.json()
                
                if data['status'] == 'succeeded':
                    logger.info(f"Enhanced OCR processing completed successfully for {file_name}")
                    return self._process_ocr_results(data, file_name)
                    
                elif data['status'] == 'failed':
                    logger.error(f"Enhanced OCR failed for {file_name}: {data}")
                    return [], []
                    
                else:
                    time.sleep(2)
                    attempt += 1
                    
            except Exception as e:
                logger.error(f"Error polling OCR results for {file_name}: {e}")
                return [], []
        
        logger.error(f"Enhanced OCR polling timeout for {file_name}")
        return [], []
    
    def _process_ocr_results(self, data: Dict, file_name: str) -> Tuple[List[Dict], List[Dict]]:
        """Process OCR results to separate text and images"""
        text_results = []
        image_results = []
        
        if 'analyzeResult' not in data:
            logger.warning(f"No analyzeResult found in OCR response for {file_name}")
            return text_results, image_results
        
        analyze_result = data['analyzeResult']
        
        # Process text content from pages
        text_results = self._extract_text_content(analyze_result, file_name)
        
        # Process images/figures
        image_results = self._extract_image_content(analyze_result, file_name)
        
        logger.info(f"Extracted {len(text_results)} text sections and {len(image_results)} images from {file_name}")
        return text_results, image_results
    
    def _extract_text_content(self, analyze_result: Dict, file_name: str) -> List[Dict]:
        """Extract text content from OCR results"""
        text_results = []
        
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
                        "file_type": "supportive",
                        "page": page_idx + 1,
                        "content": content,
                        "word_count": len(content.split()),
                        "timestamp": datetime.now().isoformat()
                    })
        
        return text_results
    
    def _extract_image_content(self, analyze_result: Dict, file_name: str) -> List[Dict]:
        """Extract image/figure content from OCR results"""
        image_results = []
        
        if 'figures' not in analyze_result:
            logger.info(f"No figures found in {file_name}")
            return image_results
        
        logger.info(f"Processing {len(analyze_result['figures'])} figures/images for {file_name}")
        
        for fig_idx, figure in enumerate(analyze_result['figures']):
            image_info = self._extract_image_info(figure, fig_idx, file_name)
            if image_info:
                image_results.append(image_info)
        
        return image_results
    
    def _extract_image_info(self, figure: Dict, index: int, file_name: str) -> Optional[Dict]:
        """Extract image information from figure data"""
        try:
            # Determine image type based on content or properties
            image_type = self._classify_image_type(figure)
            
            # Extract any text within or near the image
            extracted_text = self._get_figure_text(figure)
            
            # Get page number
            page_num = self._get_page_number(figure)
            
            # Create unique image ID
            image_id = self._generate_image_id(file_name, index)
            
            # Get image dimensions and confidence
            dimensions = self._get_image_dimensions(figure)
            confidence = figure.get('confidence', 0.0)
            
            image_info = {
                'id': image_id,
                'type': image_type,
                'page': page_num,
                'extracted_text': extracted_text,
                'file_name': file_name,
                'dimensions': dimensions,
                'confidence': confidence,
                'bounding_regions': figure.get('boundingRegions', [])
            }
            
            logger.debug(f"Extracted image info: {image_id} (type: {image_type}, page: {page_num})")
            return image_info
            
        except Exception as e:
            logger.error(f"Error extracting image info for index {index}: {e}")
            return None
    
    def _get_figure_text(self, figure: Dict) -> str:
        """Extract text content from figure"""
        extracted_text = ""
        
        # Try to get caption text
        if 'caption' in figure:
            extracted_text = figure['caption'].get('content', '')
        
        # Try to get any associated text elements
        if not extracted_text and 'elements' in figure:
            text_elements = []
            for element in figure['elements']:
                if isinstance(element, dict) and 'content' in element:
                    text_elements.append(element['content'])
            extracted_text = ' '.join(text_elements)
        
        return extracted_text.strip()
    
    def _get_page_number(self, figure: Dict) -> int:
        """Get page number for the figure"""
        if 'boundingRegions' in figure and figure['boundingRegions']:
            return figure['boundingRegions'][0].get('pageNumber', 1)
        return 1
    
    def _generate_image_id(self, file_name: str, index: int) -> str:
        """Generate unique image ID"""
        base_name = os.path.splitext(file_name)[0]
        # Clean filename for ID
        clean_name = "".join(c for c in base_name if c.isalnum() or c in ('-', '_'))[:20]
        return f"{clean_name}_img_{index}_{uuid.uuid4().hex[:8]}"
    
    def _classify_image_type(self, figure: Dict) -> str:
        """Classify image type based on figure properties"""
        # Get figure text for classification
        figure_text = self._get_figure_text(figure).lower()
        
        # Classification based on text content
        if figure_text:
            # Logo detection
            if any(keyword in figure_text for keyword in ['logo', 'brand', 'company', 'trademark']):
                return 'company_logo'
            
            # Chart/Graph detection
            elif any(keyword in figure_text for keyword in ['chart', 'graph', 'plot', 'figure', 'data', 'statistics']):
                return 'business_chart'
            
            # Diagram detection
            elif any(keyword in figure_text for keyword in ['diagram', 'flow', 'process', 'workflow', 'schematic']):
                return 'process_diagram'
            
            # Signature detection
            elif any(keyword in figure_text for keyword in ['signature', 'sign', 'signed', 'authorized']):
                return 'signature'
            
            # Table detection
            elif any(keyword in figure_text for keyword in ['table', 'list', 'schedule', 'matrix']):
                return 'data_table'
        
        # Classification based on dimensions
        dimensions = self._get_image_dimensions(figure)
        if dimensions:
            width = dimensions.get('width', 0)
            height = dimensions.get('height', 0)
            
            # Small square images are likely logos
            if width < 150 and height < 150 and abs(width - height) < 50:
                return 'company_logo'
            
            # Wide images might be charts or headers
            elif width > height * 2:
                return 'business_chart'
            
            # Tall narrow images might be signatures
            elif height > width * 1.5 and width < 200:
                return 'signature'
        
        # Check confidence level
        confidence = figure.get('confidence', 0.0)
        if confidence < 0.5:
            return 'low_quality_image'
        
        return 'document_image'  # Default type
    
    def _get_image_dimensions(self, figure: Dict) -> Dict:
        """Extract image dimensions if available"""
        try:
            if 'boundingRegions' not in figure or not figure['boundingRegions']:
                return {}
            
            bounding_region = figure['boundingRegions'][0]
            if 'polygon' not in bounding_region:
                return {}
            
            polygon = bounding_region['polygon']
            if len(polygon) < 4:
                return {}
            
            # Calculate dimensions from polygon points
            x_coords = [point['x'] for point in polygon]
            y_coords = [point['y'] for point in polygon]
            
            width = max(x_coords) - min(x_coords)
            height = max(y_coords) - min(y_coords)
            
            return {
                'width': round(width, 2),
                'height': round(height, 2),
                'area': round(width * height, 2),
                'aspect_ratio': round(width / height if height > 0 else 0, 2)
            }
            
        except Exception as e:
            logger.error(f"Error calculating image dimensions: {e}")
            return {}
    
    def get_service_info(self) -> Dict:
        """Get service configuration information"""
        return {
            'service': 'Azure Document Intelligence Enhanced OCR',
            'endpoint': self.ocr_endpoint,
            'api_version': '2023-07-31',
            'features': [
                'Text extraction from PDFs',
                'Image/figure detection and extraction',
                'Multi-language support',
                'Layout analysis',
                'Caption extraction'
            ],
            'supported_image_types': [
                'company_logo',
                'business_chart',
                'process_diagram',
                'signature',
                'data_table',
                'document_image'
            ]
        }
    
    def validate_configuration(self) -> bool:
        """Validate service configuration"""
        try:
            if not self.ocr_key:
                logger.error("OCR_KEY not configured")
                return False
            
            if not self.ocr_endpoint:
                logger.error("OCR_ENDPOINT not configured")
                return False
            
            # Test endpoint connectivity
            test_url = f"{self.ocr_endpoint}/formrecognizer/info"
            headers = {'Ocp-Apim-Subscription-Key': self.ocr_key}
            
            response = requests.get(test_url, headers=headers, timeout=10)
            
            if response.status_code in [200, 404]:  # 404 is acceptable for info endpoint
                logger.info("OCR service configuration validated successfully")
                return True
            else:
                logger.error(f"OCR service validation failed: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"OCR service validation error: {e}")
            return False

# Global instance
_image_ocr_service = None

def get_image_ocr_service():
    """Get or create Image OCR service instance"""
    global _image_ocr_service
    if _image_ocr_service is None:
        _image_ocr_service = ImageOCRService()
    return _image_ocr_service

def is_image_ocr_available() -> bool:
    """Check if Image OCR service is available and configured"""
    try:
        service = get_image_ocr_service()
        return service.validate_configuration()
    except Exception as e:
        logger.error(f"Image OCR service not available: {e}")
        return False

if __name__ == "__main__":
    try:
        service = get_image_ocr_service()
        print("Image OCR Service initialized successfully")
        print("Service Info:", service.get_service_info())
        print("Configuration Valid:", service.validate_configuration())
    except Exception as e:
        print(f"Failed to initialize Image OCR Service: {e}")
