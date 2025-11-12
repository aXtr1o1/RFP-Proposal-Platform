from typing import List, Dict, Optional, Tuple
from models.presentation import SlideContent, BulletPoint, PresentationData
from utils.markdown_parser import MarkdownParser


class ContentMapper:
    """Map content to presentation slides with intelligent layout selection"""
    
    def __init__(self):
        self.parser = MarkdownParser()
    
    def map_markdown_to_slides(
        self,
        markdown_content: str,
        max_bullets_per_slide: int = 6
    ) -> PresentationData:
        """
        Convert markdown content to structured presentation slides
        
        Args:
            markdown_content: Raw markdown text
            max_bullets_per_slide: Maximum bullets per slide before splitting
            
        Returns:
            PresentationData object ready for PPTX generation
        """
        # Parse markdown
        parsed = self.parser.parse(markdown_content)
        
        # Extract title and subtitle
        title = parsed['title']
        subtitle = parsed.get('subtitle')
        
        # Convert sections to slides
        slides = []
        
        for section in parsed['sections']:
            section_title = section['title']
            section_content = section['content']
            
            # Detect layout type
            layout_type = self.parser.detect_slide_type(section_title)
            
            # Extract content based on layout
            if layout_type == 'two_column':
                slide = self._create_two_column_slide(section_title, section_content)
                slides.append(slide)
            
            elif layout_type == 'section':
                slide = self._create_section_header(section_title, section_content)
                slides.append(slide)
            
            else:  # content slide
                # Check if needs splitting
                if self.parser.should_split_section(section_content, max_bullets_per_slide):
                    split_slides = self._create_split_content_slides(
                        section_title,
                        section_content,
                        max_bullets_per_slide
                    )
                    slides.extend(split_slides)
                else:
                    slide = self._create_content_slide(section_title, section_content)
                    slides.append(slide)
        
        return PresentationData(
            title=title,
            subtitle=subtitle,
            slides=slides,
            template_id="standard"
        )
    
    def _create_content_slide(self, title: str, content: List[Dict]) -> SlideContent:
        """Create standard content slide with bullets"""
        bullets = []
        paragraph_text = []
        
        for item in content:
            if item['type'] in ['bullet', 'numbered']:
                bullets.append(BulletPoint(
                    text=item['text'],
                    sub_bullets=None
                ))
            elif item['type'] == 'paragraph':
                paragraph_text.append(item['text'])
            elif item['type'] == 'subsection':
                # Treat subsections as bullets
                bullets.append(BulletPoint(
                    text=item['text'],
                    sub_bullets=None
                ))
        
        # Combine paragraphs
        content_text = ' '.join(paragraph_text) if paragraph_text else None
        
        return SlideContent(
            layout_type='content',
            title=title,
            content=content_text,
            bullets=bullets if bullets else None
        )
    
    def _create_section_header(self, title: str, content: List[Dict]) -> SlideContent:
        """Create section header slide"""
        # Extract first paragraph as subtitle
        subtitle = None
        for item in content:
            if item['type'] == 'paragraph':
                subtitle = item['text']
                break
        
        return SlideContent(
            layout_type='section',
            title=title,
            content=subtitle
        )
    
    def _create_two_column_slide(self, title: str, content: List[Dict]) -> SlideContent:
        """Create two-column comparison slide"""
        left_items = []
        right_items = []
        current_side = 'left'
        
        for item in content:
            if item['type'] in ['bullet', 'numbered']:
                text = item['text']
                
                # Detect column switch (heuristic)
                if any(word in text.lower() for word in ['vs', 'versus', 'or', 'alternative']):
                    current_side = 'right'
                    continue
                
                if current_side == 'left':
                    left_items.append(text)
                else:
                    right_items.append(text)
        
        # If detection failed, split evenly
        if not right_items and len(left_items) > 4:
            mid = len(left_items) // 2
            right_items = left_items[mid:]
            left_items = left_items[:mid]
        
        return SlideContent(
            layout_type='two_column',
            title=title,
            left_content=left_items if left_items else None,
            right_content=right_items if right_items else None
        )
    
    def _create_split_content_slides(
        self,
        title: str,
        content: List[Dict],
        max_bullets: int
    ) -> List[SlideContent]:
        """Split content into multiple slides"""
        bullet_chunks = self.parser.split_bullets(content, max_bullets)
        
        slides = []
        for idx, chunk in enumerate(bullet_chunks):
            # Add part number to title if multiple slides
            slide_title = f"{title} ({idx + 1}/{len(bullet_chunks)})" if len(bullet_chunks) > 1 else title
            
            bullets = [
                BulletPoint(text=item['text'])
                for item in chunk
                if item['type'] in ['bullet', 'numbered']
            ]
            
            slides.append(SlideContent(
                layout_type='content',
                title=slide_title,
                bullets=bullets
            ))
        
        return slides
    
    def enhance_with_ai_suggestions(
        self,
        presentation: PresentationData,
        ai_suggestions: Dict
    ) -> PresentationData:
        """
        Enhance presentation with AI-generated suggestions
        
        Args:
            presentation: Original presentation data
            ai_suggestions: Dictionary with AI enhancements
                - icon_suggestions: Dict mapping slide titles to icon names
                - layout_improvements: Dict with layout recommendations
                - content_refinements: Dict with content improvements
        """
        icon_suggestions = ai_suggestions.get('icon_suggestions', {})
        
        for slide in presentation.slides:
            # Apply icon suggestions
            if slide.title in icon_suggestions:
                slide.icon_name = icon_suggestions[slide.title]
        
        return presentation
    
    def validate_content_fit(self, slide: SlideContent) -> Tuple[bool, Optional[str]]:
        """
        Validate if content fits properly in slide layout
        
        Returns:
            (is_valid, warning_message)
        """
        warnings = []
        
        # Check title length
        if len(slide.title) > 60:
            warnings.append(f"Title too long ({len(slide.title)} chars, max 60)")
        
        # Check bullet count
        if slide.bullets and len(slide.bullets) > 6:
            warnings.append(f"Too many bullets ({len(slide.bullets)}, max 6)")
        
        # Check bullet text length
        if slide.bullets:
            for bullet in slide.bullets:
                if len(bullet.text) > 150:
                    warnings.append(f"Bullet text too long ({len(bullet.text)} chars, max 150)")
        
        # Check two-column balance
        if slide.layout_type == 'two_column':
            left_count = len(slide.left_content) if slide.left_content else 0
            right_count = len(slide.right_content) if slide.right_content else 0
            
            if abs(left_count - right_count) > 3:
                warnings.append(f"Unbalanced columns (left: {left_count}, right: {right_count})")
        
        is_valid = len(warnings) == 0
        warning_message = '; '.join(warnings) if warnings else None
        
        return is_valid, warning_message
    
    def optimize_presentation(self, presentation: PresentationData) -> PresentationData:
        """Optimize presentation structure and content"""
        optimized_slides = []
        
        for slide in presentation.slides:
            # Validate and fix if needed
            is_valid, warning = self.validate_content_fit(slide)
            
            if not is_valid:
                print(f"Slide '{slide.title}': {warning}")
                
                # Auto-fix bullet count
                if slide.bullets and len(slide.bullets) > 6:
                    # Split into multiple slides
                    split_slides = self._split_slide_bullets(slide)
                    optimized_slides.extend(split_slides)
                    continue
            
            optimized_slides.append(slide)
        
        presentation.slides = optimized_slides
        return presentation
    
    def _split_slide_bullets(self, slide: SlideContent) -> List[SlideContent]:
        """Split slide with too many bullets into multiple slides"""
        max_bullets = 6
        all_bullets = slide.bullets
        
        slides = []
        for i in range(0, len(all_bullets), max_bullets):
            chunk = all_bullets[i:i + max_bullets]
            
            slide_title = f"{slide.title} ({i // max_bullets + 1})"
            
            slides.append(SlideContent(
                layout_type=slide.layout_type,
                title=slide_title,
                content=slide.content if i == 0 else None,
                bullets=chunk
            ))
        
        return slides


# Convenience functions
def quick_map(markdown_content: str) -> PresentationData:
    """Quick mapping function"""
    mapper = ContentMapper()
    return mapper.map_markdown_to_slides(markdown_content)
