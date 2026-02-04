"""
Layout Mapper Module
Intelligent mapping of content types to template layouts.

This module provides algorithms for automatically suggesting which template
layout should be used for different types of content.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from ..models.template_manifest import (
    LayoutDefinition,
    PlaceholderSlot,
    TemplateManifest
)

logger = logging.getLogger("layout_mapper")


# ============================================================================
# LAYOUT SCORING RULES
# ============================================================================

# Placeholder type weights for different content types
# Higher weight = better match
PLACEHOLDER_WEIGHTS = {
    "title": {
        "title": 10,
        "center_title": 8,
        "body": 0,
        "subtitle": 2,
        "picture": 0,
    },
    "section": {
        "title": 10,
        "center_title": 12,  # Prefer center title for sections
        "body": -5,  # Penalize body placeholder for section headers
        "subtitle": 0,
        "picture": -2,
    },
    "content": {
        "title": 5,
        "body": 10,
        "subtitle": 0,
        "picture": 2,
    },
    "bullets": {
        "title": 5,
        "body": 10,
        "subtitle": 0,
    },
    "paragraph": {
        "title": 5,
        "body": 10,
        "subtitle": 0,
    },
    "two_column": {
        "title": 5,
        "body": 8,  # Need multiple body placeholders
        "subtitle": 0,
    },
    "table": {
        "title": 5,
        "body": 8,
        "object": 10,  # Tables often use object placeholder
    },
    "chart": {
        "title": 5,
        "body": 5,
        "chart": 15,
        "object": 10,
    },
    "image": {
        "title": 3,
        "picture": 15,
        "body": 0,
    },
    "agenda": {
        "title": 5,
        "body": 10,
        "subtitle": 0,
    },
}

# Layout name patterns for matching
LAYOUT_NAME_PATTERNS = {
    "title": ["title slide", "title", "intro", "opening"],
    "section": ["section", "header", "divider", "break"],
    "content": ["title and content", "content", "text", "body"],
    "bullets": ["bullet", "list", "points"],
    "two_column": ["two content", "comparison", "two column", "side by side"],
    "blank": ["blank", "empty"],
    "image": ["picture", "image", "photo", "media"],
    "chart": ["chart", "graph", "data"],
    "table": ["table", "grid"],
}


# ============================================================================
# LAYOUT MATCHER CLASS
# ============================================================================

@dataclass
class LayoutMatch:
    """Result of layout matching"""
    layout_key: str
    layout_def: LayoutDefinition
    score: float
    match_reasons: List[str]


class LayoutMapper:
    """
    Intelligent mapper for content types to template layouts.
    
    Uses a scoring system based on:
    1. Placeholder types present in the layout
    2. Layout name patterns
    3. Number of placeholders (for multi-content layouts)
    """
    
    def __init__(self, manifest: TemplateManifest):
        self.manifest = manifest
        self._cached_mappings: Dict[str, str] = {}
    
    def suggest_layout_mapping(self) -> Dict[str, str]:
        """
        Analyze all layouts and suggest content type mappings.
        
        Returns:
            Dictionary mapping content types to layout keys
        """
        if self._cached_mappings:
            return self._cached_mappings
        
        mappings = {}
        
        # Content types to map (in priority order)
        content_types = [
            "title", "section", "content", "bullets", "paragraph",
            "two_column", "table", "chart", "image", "agenda", "blank"
        ]
        
        for content_type in content_types:
            best_match = self.find_best_layout(content_type)
            if best_match:
                mappings[content_type] = best_match.layout_key
                logger.debug(
                    f"Mapped '{content_type}' -> '{best_match.layout_key}' "
                    f"(score: {best_match.score:.1f})"
                )
        
        # Add fallback mappings
        if "content" in mappings:
            mappings.setdefault("bullets", mappings["content"])
            mappings.setdefault("paragraph", mappings["content"])
            mappings.setdefault("table", mappings["content"])
            mappings.setdefault("chart", mappings["content"])
            mappings.setdefault("agenda", mappings["content"])
        
        self._cached_mappings = mappings
        return mappings
    
    def find_best_layout(
        self,
        content_type: str,
        exclude_layouts: Optional[List[str]] = None
    ) -> Optional[LayoutMatch]:
        """
        Find the best matching layout for a content type.
        
        Args:
            content_type: Type of content to match
            exclude_layouts: Layout keys to exclude from matching
            
        Returns:
            LayoutMatch with best matching layout, or None
        """
        exclude = set(exclude_layouts or [])
        matches: List[LayoutMatch] = []
        
        for layout_key, layout_def in self.manifest.layouts.items():
            if layout_key in exclude:
                continue
            
            score, reasons = self._score_layout(layout_def, content_type)
            
            if score > 0:
                matches.append(LayoutMatch(
                    layout_key=layout_key,
                    layout_def=layout_def,
                    score=score,
                    match_reasons=reasons
                ))
        
        if not matches:
            return None
        
        # Sort by score (descending)
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[0]
    
    def _score_layout(
        self,
        layout_def: LayoutDefinition,
        content_type: str
    ) -> Tuple[float, List[str]]:
        """
        Score a layout for a given content type.
        
        Returns:
            (score, list of match reasons)
        """
        score = 0.0
        reasons = []
        
        # 1. Score based on layout name
        name_score, name_reason = self._score_name_match(layout_def.name, content_type)
        if name_score > 0:
            score += name_score
            reasons.append(name_reason)
        
        # 2. Score based on placeholders
        ph_score, ph_reasons = self._score_placeholders(layout_def, content_type)
        score += ph_score
        reasons.extend(ph_reasons)
        
        # 3. Special scoring for specific content types
        special_score, special_reasons = self._score_special_cases(layout_def, content_type)
        score += special_score
        reasons.extend(special_reasons)
        
        return score, reasons
    
    def _score_name_match(self, layout_name: str, content_type: str) -> Tuple[float, str]:
        """Score based on layout name matching patterns"""
        name_lower = layout_name.lower()
        
        patterns = LAYOUT_NAME_PATTERNS.get(content_type, [])
        
        for pattern in patterns:
            if pattern in name_lower:
                return 20.0, f"Name match: '{pattern}' in '{layout_name}'"
        
        # Check for exact content type in name
        if content_type in name_lower:
            return 15.0, f"Content type in name: '{content_type}'"
        
        return 0.0, ""
    
    def _score_placeholders(
        self,
        layout_def: LayoutDefinition,
        content_type: str
    ) -> Tuple[float, List[str]]:
        """Score based on placeholder types present"""
        score = 0.0
        reasons = []
        
        weights = PLACEHOLDER_WEIGHTS.get(content_type, {})
        
        placeholder_types = [ph.type for ph in layout_def.placeholders]
        
        for ph_type in placeholder_types:
            weight = weights.get(ph_type, 0)
            if weight != 0:
                score += weight
                if weight > 0:
                    reasons.append(f"Has {ph_type} placeholder (+{weight})")
                else:
                    reasons.append(f"Has {ph_type} placeholder ({weight})")
        
        return score, reasons
    
    def _score_special_cases(
        self,
        layout_def: LayoutDefinition,
        content_type: str
    ) -> Tuple[float, List[str]]:
        """Score special cases that need custom logic"""
        score = 0.0
        reasons = []
        
        placeholder_types = [ph.type for ph in layout_def.placeholders]
        
        # Two-column: needs 2+ body placeholders
        if content_type == "two_column":
            body_count = placeholder_types.count("body")
            if body_count >= 2:
                score += 15.0
                reasons.append(f"Has {body_count} body placeholders (good for two-column)")
            elif body_count == 1:
                score -= 5.0
                reasons.append("Only 1 body placeholder (not ideal for two-column)")
        
        # Section headers: prefer layouts with ONLY title
        if content_type == "section":
            if "body" not in placeholder_types and "title" in placeholder_types:
                score += 10.0
                reasons.append("Title-only layout (ideal for section)")
        
        # Blank: prefer layouts with no placeholders
        if content_type == "blank":
            if len(layout_def.placeholders) == 0:
                score += 20.0
                reasons.append("No placeholders (blank layout)")
        
        return score, reasons
    
    def get_layout_for_content(self, content_type: str) -> Optional[LayoutDefinition]:
        """
        Get the best layout for a content type.
        
        Uses cached mapping if available, otherwise finds best match.
        """
        # Try cached mapping first
        if not self._cached_mappings:
            self.suggest_layout_mapping()
        
        layout_key = self._cached_mappings.get(content_type)
        
        if layout_key:
            return self.manifest.layouts.get(layout_key)
        
        # Fallback: find best match
        match = self.find_best_layout(content_type)
        return match.layout_def if match else None
    
    def explain_mapping(self, content_type: str) -> str:
        """
        Get explanation for why a layout was chosen for a content type.
        
        Returns human-readable explanation.
        """
        match = self.find_best_layout(content_type)
        
        if not match:
            return f"No suitable layout found for '{content_type}'"
        
        explanation = [
            f"Content Type: {content_type}",
            f"Selected Layout: {match.layout_key} ('{match.layout_def.name}')",
            f"Score: {match.score:.1f}",
            f"Reasons:"
        ]
        
        for reason in match.match_reasons:
            explanation.append(f"  - {reason}")
        
        return "\n".join(explanation)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def suggest_mappings(manifest: TemplateManifest) -> Dict[str, str]:
    """
    Convenience function to suggest layout mappings for a manifest.
    
    Args:
        manifest: TemplateManifest to analyze
        
    Returns:
        Dictionary mapping content types to layout keys
    """
    mapper = LayoutMapper(manifest)
    return mapper.suggest_layout_mapping()


def get_best_layout(
    manifest: TemplateManifest,
    content_type: str
) -> Optional[LayoutDefinition]:
    """
    Convenience function to get the best layout for a content type.
    
    Args:
        manifest: TemplateManifest to search
        content_type: Type of content
        
    Returns:
        Best matching LayoutDefinition, or None
    """
    mapper = LayoutMapper(manifest)
    match = mapper.find_best_layout(content_type)
    return match.layout_def if match else None


def explain_layout_choice(
    manifest: TemplateManifest,
    content_type: str
) -> str:
    """
    Get explanation for layout selection.
    
    Args:
        manifest: TemplateManifest to analyze
        content_type: Type of content
        
    Returns:
        Human-readable explanation
    """
    mapper = LayoutMapper(manifest)
    return mapper.explain_mapping(content_type)


def print_all_mappings(manifest: TemplateManifest) -> None:
    """Print all layout mappings with explanations"""
    mapper = LayoutMapper(manifest)
    mappings = mapper.suggest_layout_mapping()
    
    print("\n" + "=" * 60)
    print("LAYOUT MAPPINGS")
    print("=" * 60)
    
    for content_type, layout_key in mappings.items():
        print(f"\n{content_type.upper()}:")
        print("-" * 40)
        print(mapper.explain_mapping(content_type))
    
    print("\n" + "=" * 60)
