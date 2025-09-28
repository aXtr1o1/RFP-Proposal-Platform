import requests
import PyPDF2
from io import BytesIO
from openai import OpenAI
import json
from typing import List, Dict, Any
import re

class ProposalModifier:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
    
    def extract_pdf_text(self, pdf_url: str) -> str:
        """Download and extract text from PDF URL"""
        try:
            response = requests.get(pdf_url)
            response.raise_for_status()
            
            pdf_file = BytesIO(response.content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            return text.strip()
        except Exception as e:
            raise Exception(f"Error extracting PDF text: {str(e)}")
    
    def create_modification_instructions(self, items: List[Dict[str, str]]) -> str:
        """Create clear instructions for content modifications"""
        instructions = "You must modify ONLY the following specific content pieces:\n\n"
        
        for i, item in enumerate(items, 1):
            instructions += f"{i}. FIND THIS EXACT TEXT:\n"
            instructions += f'"{item["selected_content"]}"\n\n'
            instructions += f"MODIFICATION INSTRUCTION: {item['comment']}\n\n"
            instructions += "---\n\n"
        
        instructions += """
            IMPORTANT RULES:

            1. Find each selected_content in the PDF text EXACTLY as provided
            2. Apply ONLY the modification specified in the comment for that content
            3. Keep ALL other content in the PDF unchanged
            4. Maintain the original structure, formatting, and organization
            5. The modified content should seamlessly fit into the original context
            6. Work only with the proposal content provided in the PDF text.  
            7. Do not add new information, context, or assumptions.  
            8. Do not paraphrase or reword untouched sections. Keep them identical.  
            9. Only modify text where an explicit instruction is provided.  
            10. Maintain the structure, formatting, headings, lists, and tables exactly as in the original, unless a modification requires otherwise.  
            11. Ensure that modified text integrates seamlessly but minimally into its surrounding context.  
            12. Output must strictly conform to the JSON schema provided. No additional commentary or metadata.  
            """
        return instructions
    
    def process_proposal(self, payload: Dict[str, Any], language) -> Dict[str, Any]:
        """Main processing function"""

        pdf_text = self.extract_pdf_text(payload['proposal_url'])
        modification_instructions = self.create_modification_instructions(payload['items'])
        
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "proposal_response",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Professional proposal title reflecting client name and project scope"
                        },
                        "sections": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "heading": {"type": "string"},
                                    "content": {"type": "string"},
                                    "points": {
                                        "type": "array",
                                        "items": {"type": "string"}
                                    },
                                    "table": {
                                        "type": ["object", "null"],
                                        "properties": {
                                            "headers": {
                                                "type": "array",
                                                "items": {"type": "string"}
                                            },
                                            "rows": {
                                                "type": "array",
                                                "items": {
                                                    "type": "array",
                                                    "items": {"type": "string"}
                                                }
                                            }
                                        },
                                        "required": ["headers", "rows"],
                                        "additionalProperties": False
                                    }
                                },
                                "required": ["heading", "content", "points", "table"],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required": ["title", "sections"],
                    "additionalProperties": False
                }
            }
        }
        
        # System prompt
        system_prompt = f"""You are an expert in technical and development proposal writing.

                You will receive:
                1. The full text of a PDF proposal
                2. Specific content pieces that need modification with their modification instructions

                Your task:
                1. Analyze and understand the entire PDF content
                2. Find each specified content piece in the PDF
                3. Apply ONLY the requested modifications to those specific pieces
                4. Keep everything else exactly the same
                5. Structure the final result according to the JSON schema
                6. generate only in this lanuage : {language}

                Return the complete modified proposal in the specified JSON format."""

        # User prompt
        user_prompt = f"""
            PDF CONTENT:
            {pdf_text}

            MODIFICATION INSTRUCTIONS:
            {modification_instructions}

            Please process this proposal and return the complete result with only the specified modifications applied.
            """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=response_format # type: ignore
            )
            
            result = json.loads(response.choices[0].message.content) # type: ignore
            return result
            
        except Exception as e:
            raise Exception(f"Error processing with OpenAI: {str(e)}")

import os
from dotenv import load_dotenv
from typing import Dict, Any

# Load environment variables from .env file
load_dotenv()
def regen_proposal_chat(payload: Dict[str, Any], language ) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Missing OPENAI_API_KEY in environment variables")
    modifier = ProposalModifier(api_key)
    return modifier.process_proposal(payload, language)

