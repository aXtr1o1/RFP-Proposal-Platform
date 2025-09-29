import requests
import PyPDF2
from io import BytesIO
from openai import OpenAI
import json
from typing import List, Dict, Any
import re
import logging

logger = logging.getLogger("main")


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
            1. Locate each `selected_content` in the PDF text **exactly as provided**.
            2. Apply **only** the modifications specified in the corresponding comment.
            3. Keep all other content in the PDF **unchanged**.
            4. Maintain the original **structure, formatting, and organization**.
            5. Ensure the modified content integrates **seamlessly** into the original context.
            6. Work only with the proposal content provided in the PDF text.
            7. Do **not** add any new information, context, or assumptions.
            8. Do **not** paraphrase or reword untouched sections; keep them **identical**.
            9. Modify text **only** where an explicit instruction is provided.
            10. Preserve the structure, formatting, headings, lists, and tables exactly as in the original, unless a modification requires otherwise.
            11. Ensure that modifications are minimal but fit naturally within the surrounding context.
            12. The output must strictly conform to the provided **JSON schema** — no additional commentary or metadata.
            13. Do **not** include `\n` in the JSON output.
           """
        return instructions
    
    def process_proposal(self, payload: Dict[str, Any], language) -> Dict[str, Any]:
        """Main processing function"""

        pdf_text = self.extract_pdf_text(payload['proposal_url'])
        modification_instructions = self.create_modification_instructions(payload['items'])
        
        response_format =  r"""
                      Return ONLY a JSON object with this exact structure and keys (no extra keys, no prose, no extra wordings expect the JSON object):

                      {
                      "title": "Professional proposal title reflecting company name and project scope",
                      "sections": [
                          {
                          "heading": "string",
                          "content": "string",
                          "points": ["string", "..."],
                          "table": {
                              "headers": ["string", "..."],
                              "rows": [["string","..."], ["string","..."]]
                          }
                          }
                      ]
                      }
                      """


        
        
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
                5. Structure the final result according to the JSON schema{response_format}
                6. generate only in this lanuage : {language}
                7. Maintain correct spacing between words, and generate **only** the modified content. Do not invent or add extra points.(eg. For the "points" field: return each item as plain text only. Do NOT use dashes, hyphens, bullet symbols, or numbering. Example: ["HQ: Riyadh, KSA", "Mission-led: impact beyond profitability"])
            
                Return the complete modified proposal in the specified JSON format."""

        # User prompt
        user_prompt = f"""
            PDF CONTENT:
            {pdf_text}

            MODIFICATION INSTRUCTIONS:
            {modification_instructions}

            Please process this proposal and return the complete result with only the specified modifications applied.

            Note: Apply only the modification instructions to the PDF. Do not change any other content from the existing PDF.
            return only in this json scheme formate {response_format}
        """


        try:
            response = self.client.chat.completions.create(
                model="gpt-5",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                # response_format=response_format # type: ignore
            )
            
            result = json.loads(response.choices[0].message.content) # type: ignore
            print("-----------------------------------------")
            print(result)
            print("-----------------------------------------")
            def clean_newlines(obj):
                if isinstance(obj, str):
                    text = obj.replace("\n", " ")
                    text = text.lstrip("---").strip()
                    return text
                elif isinstance(obj, list):
                    return [clean_newlines(item) for item in obj]
                elif isinstance(obj, dict):
                    return {key: clean_newlines(value) for key, value in obj.items()}
                else:
                    return obj

            cleaned_data = clean_newlines(result)
            logger.info(f"this is the cleaned_data type : {type(cleaned_data)}")
            if not isinstance(cleaned_data, dict):
                
                raise ValueError("Expected dictionary output from OpenAI response")
                
            return cleaned_data

        
            
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

