"""
Text formatting utilities for presentation content
Handles breaking long paragraphs into bullets and formatting text appropriately
"""

import re
from typing import List
from apps.app.models.presentation import BulletPoint


def break_long_paragraph_to_bullets(text: str, max_bullet_length: int = 120) -> List[BulletPoint]:
    """
    Convert long paragraph into concise bullet points (without periods)
    
    Args:
        text: Long paragraph text
        max_bullet_length: Maximum characters per bullet point
        
    Returns:
        List of BulletPoint objects (text without trailing periods)
    """
    if not text or len(text.strip()) == 0:
        return []
    
    text = text.strip()
    
    # If text is already short, return as single bullet (remove trailing period)
    if len(text) < 150:
        clean_text = text.rstrip('.')
        return [BulletPoint(text=clean_text, sub_bullets=[])]
    
    bullets = []
    
    # Try to split by numbered lists first (1. 2. 3. etc.)
    numbered_pattern = r'\d+\.\s+'
    if re.search(numbered_pattern, text):
        items = re.split(numbered_pattern, text)
        items = [item.strip() for item in items if item.strip()]
        
        for item in items[:6]:  # Max 6 bullets
            if len(item) > max_bullet_length:
                # Truncate without period
                sentences = re.split(r'[.!?]\s+', item)
                item = sentences[0].rstrip('.') if sentences else item[:max_bullet_length]
            # Remove trailing period from bullet text
            item_clean = item.rstrip('.')
            bullets.append(BulletPoint(text=item_clean, sub_bullets=[]))
        
        if bullets:
            return bullets
    
    # Split by double line breaks (paragraph breaks)
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    
    if len(paragraphs) > 1:
        for para in paragraphs[:6]:  # Max 6 bullets
            # Limit paragraph length
            if len(para) > max_bullet_length:
                # Get first sentence without period
                sentences = re.split(r'[.!?]\s+', para)
                para = sentences[0].rstrip('.') if sentences and len(sentences[0]) < max_bullet_length else para[:max_bullet_length]
            # Remove trailing period
            para_clean = para.rstrip('.')
            bullets.append(BulletPoint(text=para_clean, sub_bullets=[]))
        
        if bullets:
            return bullets
    
    # Split by sentences as last resort
    sentences = re.split(r'(?<=[.!?])\s+', text)
    current_bullet = ""
    
    for sentence in sentences:
        sentence = sentence.strip().rstrip('.')  # Remove period
        if not sentence:
            continue
        
        # If adding this sentence exceeds limit, save current and start new
        test_length = len(current_bullet) + len(sentence) + 1
        if test_length > max_bullet_length and current_bullet:
            bullets.append(BulletPoint(text=current_bullet.strip(), sub_bullets=[]))
            current_bullet = sentence
        else:
            current_bullet += " " + sentence if current_bullet else sentence
        
        # Stop if we have enough bullets
        if len(bullets) >= 5:
            break
    
    # Add remaining text (without period)
    if current_bullet and len(bullets) < 6:
        bullets.append(BulletPoint(text=current_bullet.strip(), sub_bullets=[]))
    
    return bullets[:6]  # Ensure max 6 bullets


def should_convert_to_bullets(text: str) -> bool:
    """
    Determine if paragraph text should be converted to bullets
    
    Args:
        text: Content text to evaluate
        
    Returns:
        True if text should be converted to bullets
    """
    if not text:
        return False
    
    text = str(text).strip()
    
    # Convert if longer than 500 chars
    if len(text) > 500:
        return True
    
    # Convert if has multiple sentences (more than 3)
    sentence_count = text.count('.') + text.count('!') + text.count('?')
    if sentence_count > 3:
        return True
    
    # Convert if has numbered list pattern
    if re.search(r'\d+\.\s+', text):
        return True
    
    # Convert if has multiple paragraphs
    if '\n\n' in text and len(text) > 300:
        return True
    
    return False


def format_assumptions_as_bullets(text: str) -> List[BulletPoint]:
    """
    Format assumptions text as bullet points
    
    Args:
        text: Assumptions text (may be numbered or paragraph)
        
    Returns:
        List of BulletPoint objects
    """
    if not text:
        return []
    
    bullets = []
    
    # Try numbered list pattern first
    numbered_items = re.split(r'\d+\.\s*', text)
    numbered_items = [item.strip() for item in numbered_items if item.strip()]
    
    if len(numbered_items) > 1:
        for item in numbered_items[:6]:
            # Clean up and limit length
            item = item.replace('\n', ' ').strip()
            if len(item) > 120:
                item = item[:117] + "..."
            
            # Ensure it starts with assumption context
            if not any(word in item.lower() for word in ['assume', 'assumption', 'based on']):
                item = f"Assumption: {item}"
            
            bullets.append(BulletPoint(text=item, sub_bullets=[]))
    else:
        # Split by periods or line breaks
        items = re.split(r'[.\n]+', text)
        items = [item.strip() for item in items if item.strip() and len(item) > 15]
        
        for item in items[:6]:
            if len(item) > 120:
                item = item[:117] + "..."
            
            if not any(word in item.lower() for word in ['assume', 'assumption']):
                item = f"Assumption: {item}"
            
            bullets.append(BulletPoint(text=item, sub_bullets=[]))
    
    return bullets[:6]


def truncate_text(text: str, max_length: int, add_ellipsis: bool = True) -> str:
    """
    Truncate text to max length at word boundary
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        add_ellipsis: Whether to add ... at end
        
    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    
    # Find last space before max_length
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')
    
    if last_space > max_length * 0.8:  # Only break at word if not too far back
        truncated = truncated[:last_space]
    
    if add_ellipsis:
        truncated += "..."
    
    return truncated


def clean_bullet_text(text: str, remove_periods: bool = True) -> str:
    """
    Clean bullet text - remove manual bullet symbols, extra whitespace, and periods
    
    Args:
        text: Bullet text to clean
        remove_periods: If True, removes trailing periods from bullet text
        
    Returns:
        Cleaned text without periods (for bullet points)
    """
    if not text:
        return ""
    
    # Remove common bullet symbols
    text = text.replace("●", "").replace("○", "").replace("■", "").replace("□", "")
    text = text.replace("•", "").replace("◦", "").replace("▪", "").replace("▫", "")
    text = text.replace("**", "").strip()
    
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Remove trailing periods (bullet points shouldn't have periods)
    if remove_periods:
        text = text.rstrip('.')
        # Also remove period before trailing spaces
        text = re.sub(r'\.\s*$', '', text)
    
    return text.strip()


def split_into_columns(items: List[str], max_per_column: int = 4) -> tuple:
    """
    Split list of items into two columns for two-column layout
    
    Args:
        items: List of items to split
        max_per_column: Maximum items per column
        
    Returns:
        (left_items, right_items) tuple
    """
    if len(items) <= max_per_column:
        return items, []
    
    mid = (len(items) + 1) // 2
    return items[:mid], items[mid:]


def format_percentage(value: float) -> str:
    """Format number as percentage"""
    return f"{value:.0f}%" if value >= 1 else f"{value*100:.0f}%"


def format_currency(value: float, currency: str = "$") -> str:
    """Format number as currency"""
    if value >= 1000000:
        return f"{currency}{value/1000000:.1f}M"
    elif value >= 1000:
        return f"{currency}{value/1000:.1f}K"
    else:
        return f"{currency}{value:.0f}"

