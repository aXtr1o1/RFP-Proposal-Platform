import json
import logging
from io import BytesIO
from typing import Optional, Dict, List
from pathlib import Path
from difflib import SequenceMatcher

import cairosvg
from config import settings

logger = logging.getLogger("icon_service")

MAX_CACHE_SIZE = 100


class IconService:
    """
    Enhanced Icon service with fuzzy matching for better icon selection
    """
    
    def __init__(self, template_id: str = "arweqah"):
        """Initialize icon service with template awareness"""
        self.template_id = template_id
        
        # Load icons data
        icons_path = Path(settings.ASSETS_DIR) / "icons.json"
        if not icons_path.exists():
            raise FileNotFoundError(f"Icons file not found: {icons_path}")
        
        try:
            with open(icons_path, 'r', encoding='utf-8') as f:
                self.icons_data = json.load(f)
            
            if "icons" not in self.icons_data:
                raise ValueError("Invalid icons.json structure: missing 'icons' key")
            
            logger.info(f"Loaded {len(self.icons_data['icons'])} icons from {icons_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in icons.json: {e}")
        
        # Load theme
        theme_path = Path(settings.TEMPLATES_DIR) / template_id / "theme.json"
        
        if not theme_path.exists():
            logger.warning(f"Theme file not found: {theme_path}, using default icon mapping")
            self.theme = {"icons": {"keyword_to_icon_map": {}}}
        else:
            try:
                with open(theme_path, 'r', encoding='utf-8') as f:
                    self.theme = json.load(f)
                logger.info(f"Loaded theme from {theme_path}")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid theme.json: {e}")
                self.theme = {"icons": {"keyword_to_icon_map": {}}}
        
        # Get icon mapping
        self.icon_mapping = self.theme.get("icons", {}).get("keyword_to_icon_map", {})
        
        # Cache with LRU
        self.cache: Dict[str, bytes] = {}
        self.cache_order: List[str] = []
        
        # Enhanced keyword to icon mapping
        self.enhanced_keywords = {
            # Greetings
            'thank you': 'hand-waving',
            'thanks': 'hand-waving',
            'goodbye': 'hand-waving',
            'hello': 'hand-waving',
            'welcome': 'hand-waving',
            
            # Business
            'executive': 'briefcase',
            'summary': 'file-text',
            'introduction': 'users-three',
            'company': 'buildings',
            'about': 'info',
            
            # Planning
            'timeline': 'calendar-check',
            'schedule': 'calendar',
            'deadline': 'clock',
            'milestone': 'flag-banner',
            
            # Team
            'team': 'users-three',
            'people': 'users',
            'staff': 'user-circle',
            'roles': 'user-gear',
            
            # Money
            'budget': 'currency-dollar',
            'pricing': 'coins',
            'cost': 'money',
            'investment': 'chart-line-up',
            
            # Goals
            'objective': 'target',
            'goal': 'bullseye',
            'target': 'crosshair',
            'strategy': 'chess-knight',
            
            # Process
            'methodology': 'flow-arrow',
            'approach': 'map-trifold',
            'process': 'gear',
            'workflow': 'arrows-split',
            
            # Results
            'deliverable': 'package',
            'outcome': 'check-circle',
            'result': 'trophy',
            'success': 'medal',
            
            # Analysis
            'data': 'chart-bar',
            'analytics': 'chart-pie-slice',
            'metrics': 'gauge',
            'kpi': 'trendline-up',
            
            # Technical
            'architecture': 'blueprint',
            'design': 'pencil-ruler',
            'development': 'code',
            'implementation': 'hammer',
            
            # Risk
            'risk': 'warning',
            'security': 'shield-check',
            'compliance': 'clipboard-check',
            'quality': 'seal-check',
            
            # Documents
            'document': 'file-text',
            'report': 'newspaper',
            'proposal': 'file-doc',
            'contract': 'file-contract'
        }
        
        logger.info(f"IconService initialized (template: {template_id}, mappings: {len(self.icon_mapping)})")
    
    def fuzzy_match(self, text: str, keywords: List[str], threshold: float = 0.6) -> Optional[str]:
        """
        Fuzzy match text against keywords using similarity ratio
        
        Args:
            text: Text to match
            keywords: List of keywords to match against
            threshold: Minimum similarity ratio (0.0 to 1.0)
            
        Returns:
            Optional[str]: Best matching keyword or None
        """
        text_lower = text.lower()
        best_match = None
        best_ratio = 0.0
        
        for keyword in keywords:
            # Check exact substring match first (highest priority)
            if keyword in text_lower:
                return keyword
            
            # Check fuzzy similarity
            ratio = SequenceMatcher(None, text_lower, keyword).ratio()
            
            # Check word-level matching
            text_words = set(text_lower.split())
            keyword_words = set(keyword.split())
            word_overlap = len(text_words.intersection(keyword_words))
            
            if word_overlap > 0:
                # Boost ratio if there's word overlap
                ratio = max(ratio, 0.7 + (word_overlap * 0.1))
            
            if ratio > best_ratio and ratio >= threshold:
                best_ratio = ratio
                best_match = keyword
        
        return best_match
    
    def get_icon(self, name: str) -> Optional[Dict]:
        """Get icon by exact name"""
        if not name:
            return None
        
        for icon in self.icons_data['icons']:
            if icon.get('name') == name:
                return icon
        
        logger.debug(f"Icon not found: {name}")
        return None
    
    def search_by_tags(self, text: str) -> Optional[str]:
        """
        Search icon by matching text against icon tags
        
        Args:
            text: Text to search
            
        Returns:
            Optional[str]: Icon name or None
        """
        text_lower = text.lower()
        
        # Try exact tag match first
        for icon in self.icons_data['icons']:
            tags = icon.get('tags', '').lower()
            if not tags:
                continue
            
            tag_list = [t.strip() for t in tags.split(',')]
            
            for tag in tag_list:
                if tag and tag in text_lower:
                    return icon['name']
        
        # Try fuzzy matching on tags
        all_tags = []
        tag_to_icon = {}
        
        for icon in self.icons_data['icons']:
            tags = icon.get('tags', '').lower()
            if tags:
                for tag in tags.split(','):
                    tag = tag.strip()
                    if tag and len(tag) > 2:  # Skip very short tags
                        all_tags.append(tag)
                        tag_to_icon[tag] = icon['name']
        
        # Fuzzy match against all tags
        matched_tag = self.fuzzy_match(text_lower, all_tags, threshold=0.65)
        
        if matched_tag and matched_tag in tag_to_icon:
            return tag_to_icon[matched_tag]
        
        return None
    
    def auto_select_icon(self, title: str, content: str = "") -> str:
        """
        Intelligently select icon with enhanced fuzzy matching
        
        Args:
            title: Slide title
            content: Slide content
            
        Returns:
            str: Icon name
        """
        if not title:
            return 'circle'
        
        text = f"{title} {content}".lower()
        
        # 1. Check enhanced keywords with exact match
        for keyword, icon_name in self.enhanced_keywords.items():
            if keyword in text:
                if self.get_icon(icon_name):
                    logger.debug(f"✅ Exact keyword match: '{keyword}' → {icon_name}")
                    return icon_name
        
        # 2. Fuzzy match against enhanced keywords
        matched_keyword = self.fuzzy_match(text, list(self.enhanced_keywords.keys()), threshold=0.7)
        if matched_keyword:
            icon_name = self.enhanced_keywords[matched_keyword]
            if self.get_icon(icon_name):
                logger.debug(f"✅ Fuzzy keyword match: '{matched_keyword}' → {icon_name}")
                return icon_name
        
        # 3. Search by icon tags
        tag_match = self.search_by_tags(text)
        if tag_match:
            logger.debug(f"✅ Tag match: {tag_match}")
            return tag_match
        
        # 4. Check theme mapping
        for keyword, icon_name in self.icon_mapping.items():
            if keyword in text:
                if self.get_icon(icon_name):
                    return icon_name
        
        # 5. Try first word of title
        first_word = title.split()[0].lower() if title else ""
        if first_word and len(first_word) > 2:
            # Fuzzy match first word
            matched = self.fuzzy_match(first_word, list(self.enhanced_keywords.keys()), threshold=0.75)
            if matched:
                icon_name = self.enhanced_keywords[matched]
                if self.get_icon(icon_name):
                    return icon_name
        
        # 6. Intelligent category mapping
        intelligent = self.theme.get('icons', {}).get('intelligent_mapping', {})
        
        for category, keywords in intelligent.items():
            if any(kw in text for kw in keywords):
                category_icon_map = {
                    'strategy_keywords': 'target',
                    'finance_keywords': 'currency-dollar',
                    'growth_keywords': 'chart-line-up',
                    'technology_keywords': 'cpu',
                    'people_keywords': 'users-three',
                    'timeline_keywords': 'clock',
                    'security_keywords': 'shield-check',
                    'innovation_keywords': 'lightbulb',
                    'problem_keywords': 'warning-circle',
                    'solution_keywords': 'check-circle',
                    'goal_keywords': 'target',
                    'data_keywords': 'chart-pie-slice'
                }
                
                icon_name = category_icon_map.get(category, 'circle')
                if self.get_icon(icon_name):
                    return icon_name
        
        # 7. Ultimate fallback
        logger.debug(f"⚠️  No match found for '{title[:30]}...', using circle")
        return 'circle'
    
    def render_to_png(
        self, 
        icon_name: str, 
        size: int, 
        color: str
    ) -> Optional[BytesIO]:
        """
        Convert SVG icon to PNG with caching
        
        Args:
            icon_name: Icon identifier
            size: Size in pixels
            color: Hex color code (e.g., "#FFFFFF")
            
        Returns:
            Optional[BytesIO]: PNG image data or None
        """
        if not icon_name:
            logger.warning("Empty icon name provided")
            return None
        
        cache_key = f"{icon_name}_{size}_{color}"
        
        # Check cache
        if cache_key in self.cache:
            logger.debug(f"Cache hit: {cache_key}")
            self.cache_order.remove(cache_key)
            self.cache_order.append(cache_key)
            return BytesIO(self.cache[cache_key])
        
        # Get icon
        icon = self.get_icon(icon_name)
        if not icon:
            logger.warning(f"Icon not found: {icon_name}, trying fallback")
            icon = self.get_icon('circle')
            if not icon:
                logger.error("Fallback icon 'circle' not found")
                return None
        
        # Replace color in SVG
        svg_content = icon.get('content', '')
        if not svg_content:
            logger.error(f"Empty SVG content for icon: {icon_name}")
            return None
        
        svg_content = svg_content.replace('currentColor', color)
        svg_content = svg_content.replace('fill="currentColor"', f'fill="{color}"')
        
        # Convert to PNG with high DPI
        try:
            png_data = cairosvg.svg2png(
                bytestring=svg_content.encode('utf-8'),
                output_width=size * 4,
                output_height=size * 4
            )
            
            # Cache with size limit (LRU eviction)
            if len(self.cache) >= MAX_CACHE_SIZE:
                oldest_key = self.cache_order.pop(0)
                del self.cache[oldest_key]
                logger.debug(f"Evicted from cache: {oldest_key}")
            
            self.cache[cache_key] = png_data
            self.cache_order.append(cache_key)
            
            logger.debug(f"Rendered and cached: {cache_key} ({len(png_data)} bytes)")
            return BytesIO(png_data)
            
        except Exception as e:
            logger.error(f"SVG render error for {icon_name}: {e}")
            return None
    
    def get_icon_suggestions(self, text: str, limit: int = 5) -> List[str]:
        """
        Get multiple icon suggestions for given text
        
        Args:
            text: Text to analyze
            limit: Maximum number of suggestions
            
        Returns:
            List[str]: List of icon names
        """
        if not text:
            return ['circle']
        
        text_lower = text.lower()
        suggestions = []
        
        # Check enhanced keywords
        for keyword, icon_name in self.enhanced_keywords.items():
            if keyword in text_lower and icon_name not in suggestions:
                suggestions.append(icon_name)
                if len(suggestions) >= limit:
                    break
        
        # Fuzzy match if not enough suggestions
        if len(suggestions) < limit:
            keywords = list(self.enhanced_keywords.keys())
            matched = self.fuzzy_match(text_lower, keywords, threshold=0.6)
            if matched:
                icon_name = self.enhanced_keywords[matched]
                if icon_name not in suggestions:
                    suggestions.append(icon_name)
        
        # Search by tags
        if len(suggestions) < limit:
            tag_match = self.search_by_tags(text_lower)
            if tag_match and tag_match not in suggestions:
                suggestions.append(tag_match)
        
        return suggestions if suggestions else ['circle']
    
    def clear_cache(self) -> None:
        """Clear the icon cache"""
        cache_size = len(self.cache)
        self.cache.clear()
        self.cache_order.clear()
        logger.info(f"Cleared icon cache ({cache_size} entries)")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            "size": len(self.cache),
            "max_size": MAX_CACHE_SIZE,
            "memory_bytes": sum(len(data) for data in self.cache.values())
        }