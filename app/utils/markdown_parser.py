import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path


class MarkdownParser:
    """Parse markdown content into structured presentation data"""
    
    def __init__(self):
        self.sections: List[Dict] = []
        self.title: Optional[str] = None
        self.subtitle: Optional[str] = None
    
    def parse(self, markdown_content: str) -> Dict:
        """
        Parse markdown content and extract structured information
        
        Args:
            markdown_content: Raw markdown text
            
        Returns:
            Structured dictionary with presentation data
        """
        lines = markdown_content.split('\n')
        self.sections = []
        self.title = None
        self.subtitle = None
        
        current_section = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # H1 - Main title
            if line.startswith('# '):
                if not self.title:
                    self.title = line[2:].strip()
                else:
                    # H1 after first one becomes section
                    if current_section:
                        self._save_section(current_section, current_content)
                    current_section = line[2:].strip()
                    current_content = []
            
            # H2 - Subtitle or section
            elif line.startswith('## '):
                if not self.subtitle and not current_section:
                    self.subtitle = line[3:].strip()
                else:
                    if current_section:
                        self._save_section(current_section, current_content)
                    current_section = line[3:].strip()
                    current_content = []
            
            # H3 - Subsection
            elif line.startswith('### '):
                if current_section:
                    current_content.append({
                        'type': 'subsection',
                        'text': line[4:].strip()
                    })
            
            # Bullet points
            elif line.startswith('- ') or line.startswith('* '):
                bullet_text = line[2:].strip()
                current_content.append({
                    'type': 'bullet',
                    'text': bullet_text
                })
            
            # Numbered lists
            elif re.match(r'^\d+\.\s', line):
                bullet_text = re.sub(r'^\d+\.\s', '', line)
                current_content.append({
                    'type': 'numbered',
                    'text': bullet_text
                })
            
            # Regular paragraph
            else:
                current_content.append({
                    'type': 'paragraph',
                    'text': line
                })
        
        # Save last section
        if current_section:
            self._save_section(current_section, current_content)
        
        return {
            'title': self.title or 'Untitled Presentation',
            'subtitle': self.subtitle,
            'sections': self.sections
        }
    
    def _save_section(self, section_title: str, content: List[Dict]):
        """Save section with its content"""
        self.sections.append({
            'title': section_title,
            'content': content
        })
    
    def parse_file(self, file_path: str) -> Dict:
        """Parse markdown from file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return self.parse(content)
    
    def extract_key_points(self, section_content: List[Dict], max_points: int = 6) -> List[str]:
        """Extract bullet points from section content"""
        points = []
        
        for item in section_content:
            if item['type'] in ['bullet', 'numbered']:
                points.append(item['text'])
                if len(points) >= max_points:
                    break
        
        return points
    
    def extract_paragraphs(self, section_content: List[Dict]) -> str:
        """Extract and combine paragraph text"""
        paragraphs = []
        
        for item in section_content:
            if item['type'] == 'paragraph':
                paragraphs.append(item['text'])
        
        return ' '.join(paragraphs)
    
    def detect_slide_type(self, section_title: str) -> str:
        """
        Detect appropriate slide type based on section title
        
        Returns:
            One of: 'title', 'content', 'section', 'two_column'
        """
        title_lower = section_title.lower()
        
        # Section headers (dividers)
        section_keywords = [
            'introduction', 'overview', 'agenda', 'summary',
            'conclusion', 'next steps', 'thank you'
        ]
        
        if any(kw in title_lower for kw in section_keywords):
            return 'section'
        
        # Two-column layouts (comparisons)
        comparison_keywords = [
            'vs', 'versus', 'comparison', 'before and after',
            'pros and cons', 'advantages and disadvantages'
        ]
        
        if any(kw in title_lower for kw in comparison_keywords):
            return 'two_column'
        
        # Default to content slide
        return 'content'
    
    def should_split_section(self, content: List[Dict], max_bullets: int = 6) -> bool:
        """Check if section should be split into multiple slides"""
        bullet_count = sum(1 for item in content if item['type'] in ['bullet', 'numbered'])
        return bullet_count > max_bullets
    
    def split_bullets(self, content: List[Dict], max_per_slide: int = 6) -> List[List[Dict]]:
        """Split content into multiple slides if too many bullets"""
        bullets = [item for item in content if item['type'] in ['bullet', 'numbered']]
        
        if len(bullets) <= max_per_slide:
            return [content]
        
        # Split into chunks
        chunks = []
        for i in range(0, len(bullets), max_per_slide):
            chunks.append(bullets[i:i + max_per_slide])
        
        return chunks


class DocxToMarkdownConverter:
    """Convert DOCX documents to markdown format"""
    
    @staticmethod
    def convert(docx_path: str) -> str:
        """Convert DOCX to markdown"""
        try:
            from docx import Document
        except ImportError:
            raise ImportError("python-docx required for DOCX conversion")
        
        doc = Document(docx_path)
        markdown_lines = []
        
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            
            # Handle different paragraph styles
            style = para.style.name.lower()
            
            if 'heading 1' in style:
                markdown_lines.append(f"# {text}")
            elif 'heading 2' in style:
                markdown_lines.append(f"## {text}")
            elif 'heading 3' in style:
                markdown_lines.append(f"### {text}")
            elif 'list' in style or text.startswith(('•', '-', '*')):
                clean_text = text.lstrip('•-* ').strip()
                markdown_lines.append(f"- {clean_text}")
            else:
                markdown_lines.append(text)
            
            markdown_lines.append('')  # Add blank line
        
        return '\n'.join(markdown_lines)


# Helper functions
def parse_markdown_from_file(file_path: str) -> Dict:
    """Quick helper to parse markdown file"""
    parser = MarkdownParser()
    return parser.parse_file(file_path)


def parse_markdown_from_string(content: str) -> Dict:
    """Quick helper to parse markdown string"""
    parser = MarkdownParser()
    return parser.parse(content)


def convert_docx_to_markdown(docx_path: str) -> str:
    """Quick helper to convert DOCX to markdown"""
    converter = DocxToMarkdownConverter()
    return converter.convert(docx_path)
