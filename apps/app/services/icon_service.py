import json
import logging
from io import BytesIO
from typing import Optional, Dict, List
from pathlib import Path
from difflib import SequenceMatcher


import cairosvg
from ..config import settings


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
    
    def fuzzy_match_icon_name(self, icon_name: str) -> Optional[str]:
        """
        Fuzzy match icon_name against available icons in icons.json
        
        This handles cases where icon_name from LLM doesn't exactly match
        available icon names (e.g., "timeline-schedule" → "calendar-check")
        
        Args:
            icon_name: Icon name to match (e.g., "presentation-agenda", "timeline-schedule")
            
        Returns:
            Optional[str]: Best matching icon name from icons.json or None
        """
        if not icon_name:
            return None
        
        # Normalize icon_name
        icon_name_clean = icon_name.lower().strip()
        
        # 1. Try exact match first
        if self.get_icon(icon_name_clean):
            logger.debug(f"✅ Exact icon_name match: {icon_name_clean}")
            return icon_name_clean
        
        # 2. Try replacing hyphens with underscores and vice versa
        variants = [
            icon_name_clean.replace('-', '_'),
            icon_name_clean.replace('_', '-'),
            icon_name_clean.replace('-', ''),
            icon_name_clean.replace('_', '')
        ]
        
        for variant in variants:
            if self.get_icon(variant):
                logger.debug(f"✅ Icon variant match: {icon_name_clean} → {variant}")
                return variant
        
        # 3. Extract keywords from icon_name and match against available icons
        # e.g., "timeline-schedule" → ["timeline", "schedule"]
        icon_keywords = icon_name_clean.replace('-', ' ').replace('_', ' ').split()
        
        available_icons = [icon['name'] for icon in self.icons_data['icons']]
        best_match_name = None
        best_match_score = 0.0
        
        for available_icon in available_icons:
            # Calculate match score based on:
            # - Fuzzy string similarity
            # - Keyword overlap
            
            # String similarity
            similarity = SequenceMatcher(None, icon_name_clean, available_icon).ratio()
            
            # Keyword overlap
            available_keywords = available_icon.replace('-', ' ').replace('_', ' ').split()
            overlap = len(set(icon_keywords).intersection(set(available_keywords)))
            keyword_score = overlap / max(len(icon_keywords), len(available_keywords)) if icon_keywords and available_keywords else 0
            
            # Combined score (weighted)
            combined_score = (similarity * 0.6) + (keyword_score * 0.4)
            
            if combined_score > best_match_score:
                best_match_score = combined_score
                best_match_name = available_icon
        
        # Return match if score is above threshold
        if best_match_score >= 0.5:
            logger.debug(f"✅ Fuzzy icon_name match: {icon_name_clean} → {best_match_name} (score: {best_match_score:.2f})")
            return best_match_name
        
        # 4. Try matching icon_name keywords against enhanced_keywords mapping
        for keyword in icon_keywords:
            if keyword in self.enhanced_keywords:
                matched_icon = self.enhanced_keywords[keyword]
                if self.get_icon(matched_icon):
                    logger.debug(f"✅ Icon keyword match: {keyword} → {matched_icon}")
                    return matched_icon
        
        # 5. Try matching against icon tags
        for keyword in icon_keywords:
            tag_match = self.search_by_tags(keyword)
            if tag_match:
                logger.debug(f"✅ Icon tag match: {keyword} → {tag_match}")
                return tag_match
        
        logger.debug(f"⚠️  No fuzzy match found for icon_name: {icon_name_clean}")
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
    
    def auto_select_icon(self, title: str, content: str = "", icon_name: Optional[str] = None) -> str:
        """
        Intelligently select icon with enhanced fuzzy matching
        
        NEW: Now accepts icon_name parameter from LLM output and tries to match it first
        
        Args:
            title: Slide title
            content: Slide content
            icon_name: Icon name from LLM output (e.g., "presentation-agenda", "timeline-schedule")
            
        Returns:
            str: Icon name
        """
        # ============================================
        # STEP 0: Check icon_name parameter (NEW!)
        # ============================================
        if icon_name and icon_name.strip():
            logger.debug(f"🎯 Attempting to match icon_name: {icon_name}")
            
            # Try fuzzy matching icon_name against available icons
            matched_icon = self.fuzzy_match_icon_name(icon_name)
            
            if matched_icon:
                logger.info(f"✅ Using icon from icon_name: {icon_name} → {matched_icon}")
                return matched_icon
            else:
                logger.warning(f"⚠️  icon_name '{icon_name}' not matched, falling back to text matching")
        
        # ============================================
        # EXISTING LOGIC (fallback when icon_name doesn't match)
        # ============================================
        
        if not title:
            return 'circle'
        
        text = f"{title} {content}".lower()
        
        # 1. Check enhanced keywords with exact match
        for keyword, icon_name_mapped in self.enhanced_keywords.items():
            if keyword in text:
                if self.get_icon(icon_name_mapped):
                    logger.debug(f"✅ Exact keyword match: '{keyword}' → {icon_name_mapped}")
                    return icon_name_mapped
        
        # 2. Fuzzy match against enhanced keywords
        matched_keyword = self.fuzzy_match(text, list(self.enhanced_keywords.keys()), threshold=0.7)
        if matched_keyword:
            icon_name_mapped = self.enhanced_keywords[matched_keyword]
            if self.get_icon(icon_name_mapped):
                logger.debug(f"✅ Fuzzy keyword match: '{matched_keyword}' → {icon_name_mapped}")
                return icon_name_mapped
        
        # 3. Search by icon tags
        tag_match = self.search_by_tags(text)
        if tag_match:
            logger.debug(f"✅ Tag match: {tag_match}")
            return tag_match
        
        # 4. Check theme mapping
        for keyword, icon_name_mapped in self.icon_mapping.items():
            if keyword in text:
                if self.get_icon(icon_name_mapped):
                    return icon_name_mapped
        
        # 5. Try first word of title
        first_word = title.split()[0].lower() if title else ""
        if first_word and len(first_word) > 2:
            # Fuzzy match first word
            matched = self.fuzzy_match(first_word, list(self.enhanced_keywords.keys()), threshold=0.75)
            if matched:
                icon_name_mapped = self.enhanced_keywords[matched]
                if self.get_icon(icon_name_mapped):
                    return icon_name_mapped
        
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
                
                icon_name_mapped = category_icon_map.get(category, 'circle')
                if self.get_icon(icon_name_mapped):
                    return icon_name_mapped
        
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
