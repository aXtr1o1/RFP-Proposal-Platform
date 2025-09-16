import os
import sys
import base64
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import re
import json
import logging
from typing import Dict, Optional, Tuple

# Load environment variables
load_dotenv()

logger = logging.getLogger("wordgen-agent")

class ProposalArchitectureDiagramGenerator:
    """
    Generate vertical architecture diagrams from proposal content using OpenAI and Mermaid.
    Updated to generate vertical (top-to-bottom) diagrams.
    """
    
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.output_dir = "apps/wordgenAgent/output/diagrams"
        os.makedirs(self.output_dir, exist_ok=True)
        
        if not self.openai_api_key:
            logger.warning("⚠️ Warning: OPENAI_API_KEY not found. Architecture diagrams will not be generated.")
            self.openai_api_key = None
        else:
            logger.info(f"✅ Architecture diagram generator initialized with model: {self.openai_model}")
    
    def extract_proposal_content(self, proposal_dict: Dict) -> str:
        """
        Extract text content from proposal dictionary for analysis.
        """
        proposal_text = ""
        
        if proposal_dict.get("title"):
            proposal_text += f"Title: {proposal_dict['title']}\n\n"
        
        for section in proposal_dict.get("sections", []):
            heading = section.get("heading", "")
            content = section.get("content", "")
            points = section.get("points", [])
            
            proposal_text += f"Section: {heading}\n"
            proposal_text += f"Content: {content}\n"
            
            if points:
                proposal_text += f"Key Points: {', '.join(points)}\n"
            
            table = section.get("table", {})
            if table.get("rows"):
                proposal_text += f"Table Data: {json.dumps(table)}\n"
            
            proposal_text += "\n"
        
        logger.info(f"Extracted {len(proposal_text)} characters from proposal for analysis")
        return proposal_text.strip()
    
    def analyze_with_openai(self, proposal_text: str, native_language: str = "Arabic") -> str:
        """
        Analyze proposal content and generate vertical Mermaid architecture diagram using OpenAI.
        """
        if not self.openai_api_key:
            raise RuntimeError("❌ OPENAI_API_KEY not available")
        
        system_prompts = {
            "Arabic": """أنت خبير في هندسة الأنظمة. 
قم بتحليل وثيقة المقترح المقدمة واستخراج المكونات الأساسية للنظام.
استخدم مخطط 'Mermaid' لعرض الهندسة التقنية بتصميم عمودي (من الأعلى إلى الأسفل).
يرجى تقديم الكود فقط بصيغة Mermaid، دون أي تفاصيل أو شروحات إضافية.
يجب أن يكون الإخراج باللغة **العربية**.
استخدم التصميم العمودي (TB أو TD) وليس الأفقي.
أرجع كود Mermaid فقط، بدون أي تنسيق إضافي.""",
            
            "English": """You are an expert system architect. 
Analyze the provided proposal document and extract the core components of the system.
Use a 'Mermaid' diagram to present the technical architecture in VERTICAL layout (top-to-bottom flow).
Please provide only the code in Mermaid format, without any additional details or explanations.
The output should be in **English** language.
Use vertical layout (TB or TD) NOT horizontal layout (LR or RL).
Return only Mermaid code, no additional formatting."""
        }
        
        user_prompts = {
            "Arabic": f"""حلل هذا المقترح وأنشئ مخططاً هندسياً عمودياً منظماً للمكونات الرئيسية للمشروع.

المقترح:
{proposal_text[:8000]}

أنشئ مخطط Mermaid عمودي (من الأعلى إلى الأسفل) يوضح:
1. المكونات الأساسية للنظام
2. تدفق البيانات العمودي
3. التكاملات الخارجية
4. واجهات المستخدم
5. طبقات الأمان

متطلبات مهمة:
- ابدأ بـ "flowchart TB"
- استخدم أسماء عربية قصيرة ومفهومة
- أرجع كود Mermaid فقط""",
            
            "English": f"""Analyze this proposal and create a structured VERTICAL architecture diagram for the main components of the project.

Proposal:
{proposal_text[:8000]}

Create a vertical Mermaid diagram (top-to-bottom flow) showing:
1. Core system components
2. Vertical data flow
3. External integrations
4. User interfaces
5. Security layers

Important requirements:
- Start with "flowchart TB"
- Use clear, concise English names
- Return only Mermaid code"""
        }
        
        system_prompt = system_prompts.get(native_language, system_prompts["Arabic"])
        user_prompt = user_prompts.get(native_language, user_prompts["Arabic"])
        
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.openai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 1500,
            "temperature": 0.1,
        }
        
        logger.info("🤖 Analyzing proposal content with OpenAI for vertical diagram...")
        
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            
            if "choices" not in result or not result["choices"]:
                raise ValueError("❌ OpenAI returned no choices")
            
            raw_content = result["choices"]["message"]["content"]
            logger.info(f"OpenAI raw response type: {type(raw_content)}")
            logger.info(f"OpenAI raw response: {str(raw_content)[:300]}...")
            
            if isinstance(raw_content, dict):
                mermaid_code = str(raw_content.get('content', raw_content))
            elif isinstance(raw_content, list):
                mermaid_code = '\n'.join(str(item) for item in raw_content if item)
            else:
                mermaid_code = str(raw_content).strip()
            
            mermaid_code = self._clean_and_verticalize_mermaid_code(mermaid_code)
            
            logger.info("✅ Vertical architecture diagram generated successfully")
            return mermaid_code
            
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAI API request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Error analyzing proposal with OpenAI: {e}")
            logger.info("Returning default vertical diagram due to error")
            return """flowchart TB
    A[المستخدم/User] --> B[واجهة النظام/System Interface]
    B --> C[معالج التطبيق/Application Processor]
    C --> D[قاعدة البيانات/Database]
    D --> E[النتائج/Results]
    E --> F[التقارير/Reports]"""
    
    def _clean_and_verticalize_mermaid_code(self, code: str) -> str:
        """
        Clean Mermaid code and ensure it uses vertical layout.
        Fixed to handle all possible input types properly.
        """
        logger.info(f"Input code type: {type(code)}, content: {str(code)[:200]}...")
        if isinstance(code, list):
            code = '\n'.join(str(item) for item in code if item)
            logger.info("Converted list to string")
        elif isinstance(code, dict):
            if 'content' in code:
                code = str(code['content'])
            elif 'text' in code:
                code = str(code['text'])
            else:
                code = str(code)
            logger.info("Converted dict to string")
        elif not isinstance(code, str):
            code = str(code)
            logger.info(f"Converted {type(code)} to string")
        if not code or not code.strip():
            logger.warning("Empty or invalid code, using default vertical diagram")
            return """flowchart TB
    A[المستخدم/User] --> B[واجهة النظام/System Interface]
    B --> C[معالج التطبيق/Application Processor]
    C --> D[قاعدة البيانات/Database]
    D --> E[النتائج/Results]"""
        code = code.strip()
        
        if code.startswith("```"):
            lines = code.split('\n')
            start_idx = 0
            for i, line in enumerate(lines):
                if not line.strip().startswith("```") and line.strip():
                    start_idx = i
                    break
            
            end_idx = len(lines)
            for i in range(len(lines)-1, -1, -1):
                if not lines[i].strip().startswith("```") and lines[i].strip():
                    end_idx = i + 1
                    break
            
            code = '\n'.join(lines[start_idx:end_idx])
        
        lines = []
        for line in code.split("\n"):
            line = line.strip()
            if line and not line.startswith("```") and not line.startswith("```mermaid"):
                lines.append(line)
        
        if not lines:
            logger.warning("No valid lines found, using default vertical diagram")
            return """flowchart TB
    A[المستخدم/User] --> B[واجهة النظام/System Interface]
    B --> C[معالج التطبيق/Application Processor]
    C --> D[قاعدة البيانات/Database]
    D --> E[النتائج/Results]"""
        
        clean_lines = []
        flowchart_declared = False
        
        for line in lines:
            try:
                if not line:
                    continue
                
                if line.startswith("flowchart") or line.startswith("graph"):
                    if not flowchart_declared:
                        if "TB" in line or "TD" in line:
                            clean_lines.append(line)  
                            logger.info("Found existing vertical layout")
                        elif "LR" in line or "RL" in line:
                            new_line = line.replace("LR", "TB").replace("RL", "TB")
                            clean_lines.append(new_line)
                            logger.info(f"Converted horizontal to vertical: {line} -> {new_line}")
                        else:
                            new_line = f"{line} TB"
                            clean_lines.append(new_line)
                            logger.info(f"Added vertical direction: {line} -> {new_line}")
                        flowchart_declared = True
                    continue
                
                clean_lines.append(line)
                
            except Exception as line_error:
                logger.warning(f"Error processing line '{line}': {line_error}")
                continue
        
        if not flowchart_declared:
            clean_lines.insert(0, "flowchart TB")
            logger.info("Added default vertical flowchart declaration")
        
        if not clean_lines:
            logger.warning("No valid lines after processing, using default")
            return """flowchart TB
    A[المستخدم/User] --> B[واجهة النظام/System Interface]
    B --> C[معالج التطبيق/Application Processor]
    C --> D[قاعدة البيانات/Database]
    D --> E[النتائج/Results]"""
        
        result = "\n".join(clean_lines)
        logger.info(f"Final vertical Mermaid code: {result[:200]}...")
        return result
    
    def _validate_mermaid_code(self, code: str) -> str:
        """
        Validate and ensure Mermaid code is properly formatted.
        """
        if not code or len(code.strip()) < 10:
            logger.warning("Mermaid code too short, using default")
            return """flowchart TB
    A[المستخدم/User] --> B[واجهة النظام/System Interface]
    B --> C[معالج التطبيق/Application Processor]
    C --> D[قاعدة البيانات/Database]
    D --> E[النتائج/Results]"""
        
        if "flowchart" not in code.lower() and "graph" not in code.lower():
            code = f"flowchart TB\n{code}"
        
        if "-->" not in code:
            logger.warning("No arrows found in Mermaid code, might be invalid")
        
        return code
    
    def save_mermaid_code(self, mermaid_code: str, output_filename: str) -> str:
        """
        Save Mermaid code to file with timestamp.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mermaid_path = os.path.join(self.output_dir, f"{output_filename}_{timestamp}.mmd")
        
        with open(mermaid_path, "w", encoding="utf-8") as f:
            f.write(mermaid_code)
        
        logger.info(f"📝 Vertical Mermaid code saved: {mermaid_path}")
        return mermaid_path
    
    def render_mermaid_to_png(self, mermaid_code: str, output_filename: str) -> str:
        """
        Render vertical Mermaid diagram to PNG using mermaid.ink service.
        """
        try:
            encoded_diagram = base64.urlsafe_b64encode(mermaid_code.encode("utf-8")).decode("ascii")
            image_url = f"https://mermaid.ink/img/{encoded_diagram}"
            
            logger.info(f"🎨 Rendering vertical diagram via mermaid.ink")
            
            response = requests.get(image_url, timeout=60)
            response.raise_for_status()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_path = os.path.join(self.output_dir, f"{output_filename}_{timestamp}.png")
            
            with open(image_path, "wb") as f:
                f.write(response.content)
            
            logger.info(f"✅ Vertical PNG saved: {image_path}")
            return image_path
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to render vertical diagram: {e}")
            raise
        except Exception as e:
            logger.error(f"Error rendering vertical Mermaid diagram: {e}")
            raise
    
    def generate_architecture_diagram_from_proposal(
        self, 
        proposal_dict: Dict, 
        rfp_text: str = "", 
        native_language: str = "Arabic"
    ) -> Dict:
        """
        Main method to generate vertical architecture diagram from proposal.
        Returns diagram data including Mermaid code and file paths.
        """
        try:
            start_time = datetime.now()
            
            proposal_text = self.extract_proposal_content(proposal_dict)
            
            if rfp_text:
                proposal_text += f"\n\nOriginal RFP Context:\n{rfp_text[:2000]}"
            
            if len(proposal_text) < 100:
                raise ValueError("Extracted proposal text too short for analysis")
            
            mermaid_code = self.analyze_with_openai(proposal_text, native_language)
            mermaid_code = self._validate_mermaid_code(mermaid_code)  
            
            proposal_title = proposal_dict.get("title", "proposal")
            output_filename = re.sub(r'[^\w\s-]', '', proposal_title).strip()
            output_filename = re.sub(r'[-\s]+', '_', output_filename)
            if not output_filename:
                output_filename = f"proposal_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            mermaid_path = self.save_mermaid_code(mermaid_code, output_filename)
            
            image_path = self.render_mermaid_to_png(mermaid_code, output_filename)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            diagram_title = "الهندسة التقنية العمودية" if native_language == "Arabic" else "Vertical Technical Architecture"
            diagram_description = (
                "يوضح المخطط التالي الهندسة المعمارية المقترحة للنظام بتصميم عمودي يظهر طبقات النظام وتدفق البيانات من الأعلى إلى الأسفل."
                if native_language == "Arabic" else
                "The following vertical diagram illustrates the proposed system architecture with top-to-bottom data flow showing system layers."
            )
            
            return {
                "success": True,
                "mermaid_code": mermaid_code,
                "mermaid_file": mermaid_path,
                "image_file": image_path,
                "processing_time": processing_time,
                "diagram_section": {
                    "heading": diagram_title,
                    "content": diagram_description,
                    "points": [
                        "مخطط الهندسة المعمارية العمودي للنظام المقترح" if native_language == "Arabic" else "Vertical system architecture diagram",
                        "تدفق البيانات والعمليات من الأعلى إلى الأسفل" if native_language == "Arabic" else "Top-to-bottom data flow and processes",
                        "طبقات النظام والتكاملات الخارجية" if native_language == "Arabic" else "System layers and external integrations"
                    ],
                    "mermaid_diagram": { 
                        "code": mermaid_code,
                        "image_path": image_path,
                        "mermaid_path": mermaid_path,
                        "layout": "vertical"
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating vertical architecture diagram: {e}")
            return {
                "success": False,
                "error": str(e),
                "diagram_section": None
            }
