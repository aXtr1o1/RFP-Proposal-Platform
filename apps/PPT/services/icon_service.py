import json
import logging
from io import BytesIO
from typing import Optional, Dict, List
from pathlib import Path
from difflib import SequenceMatcher
import re

import cairosvg
from apps.PPT.config import settings

logger = logging.getLogger("icon_service")

MAX_CACHE_SIZE = 100


class IconService:
    """
    Enhanced Icon service with Arabic/English fuzzy matching
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
        
        # ✅ ENHANCED: Extended keyword mapping with more specific agenda-related icons
        self.enhanced_keywords = {
            # Greetings - English & Arabic
            'thank you': 'hand-waving',
            'thanks': 'hand-waving',
            'goodbye': 'hand-waving',
            'hello': 'hand-waving',
            'welcome': 'hand-waving',
            'شكر': 'hand-waving',
            'شكرا': 'hand-waving',
            'شكراً': 'hand-waving',
            'مرحبا': 'hand-waving',
            'أهلا': 'hand-waving',
            
            # Introduction & Overview
            'introduction': 'presentation-chart',
            'overview': 'presentation',
            'مقدمة': 'presentation-chart',
            'نظرة عامة': 'presentation',
            
            # Objectives & Goals
            'objective': 'target',
            'objectives': 'target',
            'goal': 'bullseye',
            'goals': 'bullseye',
            'target': 'crosshair',
            'targets': 'crosshair',
            'هدف': 'target',
            'أهداف': 'bullseye',
            'غاية': 'bullseye',
            
            # Approach & Methodology
            'approach': 'compass',
            'methodology': 'flow-arrow',
            'method': 'gear-six',
            'strategy': 'chess-knight',
            'منهج': 'compass',
            'منهجية': 'flow-arrow',
            'استراتيجية': 'chess-knight',
            'طريقة': 'compass',
            
            # Timeline & Milestones
            'timeline': 'calendar-check',
            'schedule': 'calendar',
            'milestone': 'flag-banner',
            'milestones': 'flag-banner',
            'deadline': 'clock',
            'جدول زمني': 'calendar-check',
            'زمني': 'calendar-check',
            'جدول': 'calendar',
            'موعد': 'clock',
            'مواعيد': 'calendar',
            'مرحلة': 'flag-banner',
            'مراحل': 'flag-banner',
            
            # Team & Resources
            'team': 'users-three',
            'people': 'users',
            'staff': 'user-circle',
            'resources': 'package',
            'roles': 'user-gear',
            'فريق': 'users-three',
            'أشخاص': 'users',
            'موظفين': 'user-circle',
            'أدوار': 'user-gear',
            'موارد': 'package',
            
            # Outcomes & Results
            'outcome': 'chart-line-up',
            'outcomes': 'chart-line-up',
            'result': 'trophy',
            'results': 'trophy',
            'deliverable': 'package',
            'deliverables': 'package',
            'success': 'medal',
            'نتيجة': 'trophy',
            'نتائج': 'chart-line-up',
            'مخرجات': 'package',
            'ملخص المخرجات': 'file-text',
            'نجاح': 'medal',
            'إنجاز': 'check-circle',
            
            # Next Steps & Questions
            'next': 'arrow-right',
            'next steps': 'arrow-circle-right',
            'questions': 'question',
            'q&a': 'chats-circle',
            'الخطوات التالية': 'arrow-circle-right',
            'الأسئلة': 'question',
            'لكم شكراً': 'hand-waving',
            
            # Assumptions & Pricing
            'assumption': 'lightbulb',
            'assumptions': 'lightbulb',
            'افتراضات': 'lightbulb',
            'الافتراضات': 'lightbulb',
            'pricing': 'currency-dollar',
            'التسعير': 'currency-dollar',
            'منهجية': 'gear-six',
            
            # Strategy specific
            'impetus strategy': 'sparkle',
            'strategy': 'chess-knight',
            
            # Business - English & Arabic
            'executive': 'briefcase',
            'summary': 'file-text',
            'company': 'buildings',
            'about': 'info',
            'تنفيذي': 'briefcase',
            'ملخص': 'file-text',
            'شركة': 'buildings',
            'عن': 'info',
            'نبذة': 'info',
            
            # Planning - English & Arabic
            'plan': 'calendar-check',
            'planning': 'calendar-check',
            'خطة': 'calendar-check',
            'تخطيط': 'calendar-check',
            'الجدول العمل خطة': 'calendar-check',
            
            # Money - English & Arabic
            'budget': 'currency-dollar',
            'pricing': 'coins',
            'cost': 'money',
            'investment': 'chart-line-up',
            'ميزانية': 'currency-dollar',
            'تسعير': 'coins',
            'تكلفة': 'money',
            'استثمار': 'chart-line-up',
            
            # Process - English & Arabic
            'process': 'gear',
            'workflow': 'arrows-split',
            'عملية': 'gear',
            'سير': 'arrows-split',
            
            # Analysis - English & Arabic
            'data': 'chart-bar',
            'analytics': 'chart-pie-slice',
            'metrics': 'gauge',
            'kpi': 'trendline-up',
            'بيانات': 'chart-bar',
            'تحليلات': 'chart-pie-slice',
            'مقاييس': 'gauge',
            
            # Technical - English & Arabic
            'architecture': 'blueprint',
            'design': 'pencil-ruler',
            'development': 'code',
            'implementation': 'hammer',
            'هندسة': 'blueprint',
            'تصميم': 'pencil-ruler',
            'تطوير': 'code',
            'تنفيذ': 'hammer',
            
            # Risk - English & Arabic
            'risk': 'warning',
            'risks': 'warning',
            'security': 'shield-check',
            'compliance': 'clipboard-check',
            'quality': 'seal-check',
            'مخاطر': 'warning',
            'الخطر': 'warning',
            'أمن': 'shield-check',
            'امتثال': 'clipboard-check',
            'جودة': 'seal-check',
            'ضمان': 'seal-check',
            'إدارة الجودة ضمان': 'shield-check',
            
            # Documents - English & Arabic
            'document': 'file-text',
            'report': 'newspaper',
            'proposal': 'file-doc',
            'contract': 'file-contract',
            'وثيقة': 'file-text',
            'تقرير': 'newspaper',
            'مقترح': 'file-doc',
            'عقد': 'file-contract',
            
            # Service & Performance
            'service': 'hand-heart',
            'performance': 'gauge',
            'indicators': 'gauge',
            'الخدمة': 'hand-heart',
            'مستويات الأداء مؤشرات': 'gauge',
            
            # Compliance & Requirements
            'متطلبات الإلتزام': 'clipboard-check',
            'الطرح بمتطلبات الإلتزام': 'clipboard-check',
            
            # Intellectual Property
            'intellectual': 'brain',
            'property': 'lock',
            'ip': 'lock-key',
            'الفكرية والملكية البيانات خصوصية': 'shield-check',
            
            # Project & Roles
            'project': 'briefcase',
            'والأدوار المشروع فريق': 'users-three',
            
            # Agenda specific - English & Arabic
            'agenda': 'presentation-chart',
            'أعمال': 'presentation-chart',
            'جدول الأعمال': 'presentation-chart',
            'الأعمال جدول': 'presentation-chart'
        }
        
        logger.info(f"IconService initialized (template: {template_id}, mappings: {len(self.icon_mapping)})")
    
    def detect_language(self, text: str) -> str:
        """Detect if text is Arabic or English"""
        if not text:
            return 'en'
        
        # Count Arabic characters
        arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
        total_chars = len(re.findall(r'[a-zA-Z\u0600-\u06FF]', text))
        
        if total_chars == 0:
            return 'en'
        
        # If more than 30% Arabic characters, treat as Arabic
        if arabic_chars / total_chars > 0.3:
            return 'ar'
        
        return 'en'
    
    def normalize_arabic_text(self, text: str) -> str:
        """Normalize Arabic text for better matching"""
        if not text:
            return text
        
        # Remove diacritics
        text = re.sub(r'[\u064B-\u065F]', '', text)
        
        # Normalize some characters
        text = text.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
        text = text.replace('ة', 'ه')
        
        # Remove extra spaces
        text = ' '.join(text.split())
        
        return text.strip()
    
    def fuzzy_match(self, text: str, keywords: List[str], threshold: float = 0.6) -> Optional[str]:
        """
        Fuzzy match text against keywords using similarity ratio
        Supports both Arabic and English
        """
        text_lower = text.lower()
        
        # Detect language and normalize if Arabic
        lang = self.detect_language(text)
        if lang == 'ar':
            text_lower = self.normalize_arabic_text(text_lower)
        
        best_match = None
        best_ratio = 0.0
        
        for keyword in keywords:
            keyword_lang = self.detect_language(keyword)
            keyword_normalized = keyword
            
            # Normalize Arabic keywords
            if keyword_lang == 'ar':
                keyword_normalized = self.normalize_arabic_text(keyword)
            
            # Check exact substring match first (highest priority)
            if keyword_normalized in text_lower or keyword in text_lower:
                return keyword
            
            # Check fuzzy similarity
            ratio = SequenceMatcher(None, text_lower, keyword_normalized).ratio()
            
            # Check word-level matching
            text_words = set(text_lower.split())
            keyword_words = set(keyword_normalized.split())
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
        ✅ ENHANCED: Fuzzy match icon_name against available icons in icons.json
        Now with better keyword extraction and multi-word matching
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
        
        # ✅ 3. NEW: Try matching against enhanced_keywords first (most reliable)
        for keyword, mapped_icon in self.enhanced_keywords.items():
            if keyword in icon_name_clean or icon_name_clean in keyword:
                if self.get_icon(mapped_icon):
                    logger.debug(f"✅ Enhanced keyword match: {icon_name_clean} → {mapped_icon} (via '{keyword}')")
                    return mapped_icon
        
        # 4. Extract keywords from icon_name and match against available icons
        icon_keywords = icon_name_clean.replace('-', ' ').replace('_', ' ').split()
        
        available_icons = [icon['name'] for icon in self.icons_data['icons']]
        best_match_name = None
        best_match_score = 0.0
        
        for available_icon in available_icons:
            # Calculate match score
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
        
        # 5. Try matching icon_name keywords against enhanced_keywords mapping
        for keyword in icon_keywords:
            if keyword in self.enhanced_keywords:
                matched_icon = self.enhanced_keywords[keyword]
                if self.get_icon(matched_icon):
                    logger.debug(f"✅ Icon keyword match: {keyword} → {matched_icon}")
                    return matched_icon
        
        # 6. Try matching against icon tags
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
        Supports both Arabic and English
        """
        text_lower = text.lower()
        lang = self.detect_language(text_lower)
        
        if lang == 'ar':
            text_lower = self.normalize_arabic_text(text_lower)
        
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
                    if tag and len(tag) > 2:
                        all_tags.append(tag)
                        tag_to_icon[tag] = icon['name']
        
        # Fuzzy match against all tags
        matched_tag = self.fuzzy_match(text_lower, all_tags, threshold=0.65)
        
        if matched_tag and matched_tag in tag_to_icon:
            return tag_to_icon[matched_tag]
        
        return None
    
    def auto_select_icon(self, title: str, content: str = "", icon_name: Optional[str] = None) -> str:
        """
        ✅ ENHANCED: Intelligently select icon with Arabic/English fuzzy matching
        Priority: icon_name parameter > enhanced keywords > tags > theme mapping > fallback
        """
        # STEP 0: Check icon_name parameter (HIGHEST PRIORITY)
        if icon_name and icon_name.strip():
            logger.debug(f"🎯 Attempting to match icon_name: {icon_name}")
            
            matched_icon = self.fuzzy_match_icon_name(icon_name)
            
            if matched_icon:
                logger.info(f"✅ Using icon from icon_name: {icon_name} → {matched_icon}")
                return matched_icon
            else:
                logger.warning(f"⚠️  icon_name '{icon_name}' not matched, falling back to text matching")
        
        # EXISTING LOGIC (fallback)
        if not title:
            return 'circle'
        
        text = f"{title} {content}".lower()
        lang = self.detect_language(text)
        
        # Normalize if Arabic
        if lang == 'ar':
            text = self.normalize_arabic_text(text)
        
        # 1. Check enhanced keywords with exact match
        for keyword, icon_name_mapped in self.enhanced_keywords.items():
            keyword_lang = self.detect_language(keyword)
            keyword_check = self.normalize_arabic_text(keyword) if keyword_lang == 'ar' else keyword
            
            if keyword_check in text:
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
            if lang == 'ar':
                first_word = self.normalize_arabic_text(first_word)
            
            matched = self.fuzzy_match(first_word, list(self.enhanced_keywords.keys()), threshold=0.75)
            if matched:
                icon_name_mapped = self.enhanced_keywords[matched]
                if self.get_icon(icon_name_mapped):
                    return icon_name_mapped
        
        # 6. Ultimate fallback
        logger.debug(f"⚠️  No match found for '{title[:30]}...', using circle")
        return 'circle'
    
    def render_to_png(
        self, 
        icon_name: str, 
        size: int, 
        color: str
    ) -> Optional[BytesIO]:
        """Convert SVG icon to PNG with caching"""
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
        """Get multiple icon suggestions for given text (supports Arabic)"""
        if not text:
            return ['circle']
        
        text_lower = text.lower()
        lang = self.detect_language(text_lower)
        
        if lang == 'ar':
            text_lower = self.normalize_arabic_text(text_lower)
        
        suggestions = []
        
        # Check enhanced keywords
        for keyword, icon_name in self.enhanced_keywords.items():
            keyword_lang = self.detect_language(keyword)
            keyword_check = self.normalize_arabic_text(keyword) if keyword_lang == 'ar' else keyword
            
            if keyword_check in text_lower and icon_name not in suggestions:
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