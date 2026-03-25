"""
Complexity Assessor Module

Assesses topic complexity to determine research depth and script thoroughness.
NOT duration - that emerges naturally from the content.

Key insight: A "short" video might need complex research and storytelling.
A "long" video might be simple. Duration should NOT be hardcoded.

Complexity determines:
- Number of research dimensions to explore
- Depth of narrative structure
- Number of visual anchors needed
- Thoroughness of investigation

Based on Implementation Plan V4 requirements.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from packages.core.logger import get_logger
from packages.router.client import RouterClient

log = get_logger(__name__)


class ComplexityLevel(str, Enum):
    """Complexity levels for research depth."""
    SHALLOW = "shallow"      # Quick, focused content
    MODERATE = "moderate"    # Balanced depth
    DEEP = "deep"            # Comprehensive investigation


@dataclass
class ComplexityFactor:
    """A single complexity factor with its assessment."""
    name: str
    weight: float
    score: float  # 0.0 to 1.0
    reasoning: str
    indicators: list[str] = field(default_factory=list)


@dataclass
class ComplexityResult:
    """Complete complexity assessment result."""
    overall_score: float  # 1.0 to 3.0
    level: ComplexityLevel
    
    # Research parameters
    research_dimensions_needed: int  # 2-6
    narrative_complexity: str  # "simple", "multi-layered", "complex"
    visual_anchors_estimated: int  # 3-15
    
    # Factor breakdown
    factors: list[ComplexityFactor] = field(default_factory=list)
    
    # Recommendations
    depth_guidance: str = ""
    focus_areas: list[str] = field(default_factory=list)
    
    # Metadata
    topic: str = ""
    assessed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "overall_score": self.overall_score,
            "level": self.level.value,
            "research_dimensions_needed": self.research_dimensions_needed,
            "narrative_complexity": self.narrative_complexity,
            "visual_anchors_estimated": self.visual_anchors_estimated,
            "factors": [
                {
                    "name": f.name,
                    "weight": f.weight,
                    "score": f.score,
                    "reasoning": f.reasoning,
                    "indicators": f.indicators
                }
                for f in self.factors
            ],
            "depth_guidance": self.depth_guidance,
            "focus_areas": self.focus_areas,
            "topic": self.topic,
            "assessed_at": self.assessed_at
        }


class ComplexityAssessor:
    """
    Assesses topic complexity to determine research and script depth.
    
    Does NOT determine duration - that emerges from content.
    
    COMPLEXITY FACTORS:
    1. Hidden mechanisms to explain (weight: 0.25)
    2. Visual asset availability (weight: 0.20)
    3. Audience prior knowledge gap (weight: 0.25)
    4. Emotional depth needed (weight: 0.15)
    5. Source complexity/synthesis required (weight: 0.15)
    
    USAGE:
        assessor = ComplexityAssessor()
        result = await assessor.assess(
            topic="Pakistan's economic crisis",
            initial_research=research_summary
        )
        
        # Use result.level to determine research depth
        if result.level == ComplexityLevel.DEEP:
            # Do comprehensive research
            pass
    """
    
    COMPLEXITY_FACTORS = {
        "hidden_mechanisms": {
            "weight": 0.25,
            "description": "How many interconnected systems need explaining",
            "questions": [
                "How many interconnected systems need explaining?",
                "Is the mechanism visible or abstract?",
                "Can it be shown in a single diagram or multiple?",
                "Is this something the audience has seen before?"
            ],
            "indicators": {
                "low": ["Single clear cause", "Visible mechanism", "Familiar concept"],
                "medium": ["2-3 connected factors", "Partially abstract", "Some familiarity"],
                "high": ["5+ interconnected systems", "Highly abstract", "Novel concept"]
            }
        },
        
        "visual_availability": {
            "weight": 0.20,
            "description": "How much visual evidence is available",
            "questions": [
                "Are there existing visuals (archive, maps, data)?",
                "How much needs to be created from scratch?",
                "Is the visual evidence concrete or abstract?",
                "Are there primary source documents available?"
            ],
            "indicators": {
                "low": ["Rich archive footage", "Many primary documents", "Visual locations exist"],
                "medium": ["Some archive available", "Mix of sources", "Some visual gaps"],
                "high": ["Mostly conceptual", "Few visuals available", "Need heavy animation"]
            }
        },
        
        "audience_knowledge_gap": {
            "weight": 0.25,
            "description": "How much context the Pakistani audience needs",
            "questions": [
                "How familiar is the Pakistani audience with this topic?",
                "What background context is needed?",
                "Are there local equivalents or parallels?",
                "Is this being covered in Pakistani media?"
            ],
            "indicators": {
                "low": ["Topic is familiar", "Local coverage exists", "Easy parallels"],
                "medium": ["Some awareness", "Needs context", "Partial parallels"],
                "high": ["Unknown topic", "Needs extensive context", "No local reference"]
            }
        },
        
        "emotional_depth": {
            "weight": 0.15,
            "description": "How much emotional resonance is needed",
            "questions": [
                "Is there a human character with a compelling story?",
                "Does this affect people's daily lives?",
                "What's the emotional resonance potential?",
                "Are there personal stakes for the audience?"
            ],
            "indicators": {
                "low": ["Informational topic", "No direct impact", "Academic interest"],
                "medium": ["Some personal relevance", "Indirect impact", "Moderate stakes"],
                "high": ["Direct impact on audience", "Personal stories available", "High stakes"]
            }
        },
        
        "source_complexity": {
            "weight": 0.15,
            "description": "How complex is the source synthesis",
            "questions": [
                "How many sources need to be synthesized?",
                "Are sources readily available or hard to find?",
                "Is there conflicting information to navigate?",
                "Are sources in English or need translation?"
            ],
            "indicators": {
                "low": ["Few sources needed", "Easily available", "Consistent information"],
                "medium": ["Moderate sources", "Some digging needed", "Minor conflicts"],
                "high": ["Many sources", "Hard to find", "Major contradictions"]
            }
        }
    }
    
    def __init__(self, router_client: RouterClient = None):
        self.router = router_client
    
    async def assess(
        self,
        topic: str,
        initial_research: dict = None,
        genre: str = None,
        big_question: str = None
    ) -> ComplexityResult:
        """
        Assess complexity from topic and initial research.
        
        Args:
            topic: The topic statement
            initial_research: Optional initial research findings
            genre: Optional genre ID for context
            big_question: Optional big question the video answers
        
        Returns:
            ComplexityResult with assessment and recommendations
        """
        log.info(f"complexity_assessment_started: topic='{topic[:50]}...'")
        
        # Build context for assessment
        context = self._build_context(topic, initial_research, genre, big_question)
        
        # Assess each factor
        factors = []
        for factor_name, factor_config in self.COMPLEXITY_FACTORS.items():
            factor = await self._assess_factor(factor_name, factor_config, context)
            factors.append(factor)
        
        # Calculate overall score (1.0 to 3.0)
        weighted_sum = sum(f.score * f.weight for f in factors)
        # Normalize to 1.0-3.0 range
        overall_score = 1.0 + (weighted_sum * 2.0)
        
        # Determine complexity level
        if overall_score < 1.7:
            level = ComplexityLevel.SHALLOW
        elif overall_score < 2.3:
            level = ComplexityLevel.MODERATE
        else:
            level = ComplexityLevel.DEEP
        
        # Calculate research parameters
        dimensions = self._calculate_dimensions(level, factors)
        narrative = self._determine_narrative_complexity(level, factors)
        anchors = self._estimate_visual_anchors(level, factors)
        
        # Generate guidance
        guidance = self._generate_depth_guidance(level, factors)
        focus_areas = self._identify_focus_areas(factors)
        
        result = ComplexityResult(
            overall_score=round(overall_score, 2),
            level=level,
            research_dimensions_needed=dimensions,
            narrative_complexity=narrative,
            visual_anchors_estimated=anchors,
            factors=factors,
            depth_guidance=guidance,
            focus_areas=focus_areas,
            topic=topic
        )
        
        log.info(
            f"complexity_assessment_complete: score={overall_score:.2f} "
            f"level={level.value} dimensions={dimensions}"
        )
        
        return result
    
    def _build_context(
        self,
        topic: str,
        initial_research: dict,
        genre: str,
        big_question: str
    ) -> str:
        """Build context string for assessment."""
        parts = [f"TOPIC: {topic}"]
        
        if big_question:
            parts.append(f"BIG QUESTION: {big_question}")
        
        if genre:
            parts.append(f"GENRE: {genre}")
        
        if initial_research:
            # Extract key points from research
            if isinstance(initial_research, dict):
                if "facts" in initial_research:
                    facts = initial_research["facts"][:3]
                    parts.append(f"INITIAL FACTS: {facts}")
                if "sources" in initial_research:
                    parts.append(f"AVAILABLE SOURCES: {len(initial_research['sources'])} sources")
        
        return "\n".join(parts)
    
    async def _assess_factor(
        self,
        factor_name: str,
        factor_config: dict,
        context: str
    ) -> ComplexityFactor:
        """Assess a single complexity factor using LLM."""
        
        questions_text = "\n".join([f"- {q}" for q in factor_config["questions"]])
        
        indicators_text = "\n".join([
            f"Low complexity indicators: {', '.join(factor_config['indicators']['low'])}",
            f"Medium complexity indicators: {', '.join(factor_config['indicators']['medium'])}",
            f"High complexity indicators: {', '.join(factor_config['indicators']['high'])}"
        ])
        
        prompt = f"""Assess the complexity of this topic for a documentary video.

{context}

FACTOR TO ASSESS: {factor_name}
DESCRIPTION: {factor_config['description']}

QUESTIONS TO CONSIDER:
{questions_text}

INDICATORS:
{indicators_text}

Respond in JSON format:
{{
    "score": 0.0-1.0,
    "reasoning": "Brief explanation of why this score",
    "indicators_found": ["list of indicators that apply"]
}}

Score 0.0-0.33 = Low complexity
Score 0.34-0.66 = Medium complexity
Score 0.67-1.0 = High complexity
"""
        
        try:
            import json
            import re
            
            async with RouterClient() as router:
                response = await router.complete_text(
                    prompt,
                    system="You are a documentary complexity assessor. Respond only with valid JSON.",
                    max_tokens=300
                )
                
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    return ComplexityFactor(
                        name=factor_name,
                        weight=factor_config["weight"],
                        score=float(data.get("score", 0.5)),
                        reasoning=data.get("reasoning", "No reasoning provided"),
                        indicators=data.get("indicators_found", [])
                    )
        
        except Exception as e:
            log.warning(f"factor_assessment_failed: {factor_name} - {e}")
        
        # Default to medium complexity if assessment fails
        return ComplexityFactor(
            name=factor_name,
            weight=factor_config["weight"],
            score=0.5,
            reasoning="Assessment failed, using default medium",
            indicators=[]
        )
    
    def _calculate_dimensions(
        self,
        level: ComplexityLevel,
        factors: list[ComplexityFactor]
    ) -> int:
        """Calculate number of research dimensions needed."""
        base = {
            ComplexityLevel.SHALLOW: 2,
            ComplexityLevel.MODERATE: 4,
            ComplexityLevel.DEEP: 6
        }
        
        # Adjust based on hidden_mechanisms factor
        for f in factors:
            if f.name == "hidden_mechanisms":
                if f.score > 0.7:
                    return min(base[level] + 1, 6)
                elif f.score < 0.3:
                    return max(base[level] - 1, 2)
        
        return base[level]
    
    def _determine_narrative_complexity(
        self,
        level: ComplexityLevel,
        factors: list[ComplexityFactor]
    ) -> str:
        """Determine narrative complexity type."""
        mapping = {
            ComplexityLevel.SHALLOW: "simple",
            ComplexityLevel.MODERATE: "multi-layered",
            ComplexityLevel.DEEP: "complex"
        }
        return mapping[level]
    
    def _estimate_visual_anchors(
        self,
        level: ComplexityLevel,
        factors: list[ComplexityFactor]
    ) -> int:
        """Estimate number of visual anchors needed."""
        base = {
            ComplexityLevel.SHALLOW: 3,
            ComplexityLevel.MODERATE: 7,
            ComplexityLevel.DEEP: 12
        }
        
        # Adjust based on visual_availability factor
        for f in factors:
            if f.name == "visual_availability":
                if f.score > 0.7:  # High complexity = low availability
                    return base[level] + 3  # Need more creative visuals
                elif f.score < 0.3:
                    return base[level] - 1  # Rich visuals available
        
        return base[level]
    
    def _generate_depth_guidance(
        self,
        level: ComplexityLevel,
        factors: list[ComplexityFactor]
    ) -> str:
        """Generate guidance for research depth."""
        guidance = {
            ComplexityLevel.SHALLOW: (
                "Focus on clarity and efficiency. "
                "A single reveal is sufficient. "
                "Use familiar visual metaphors. "
                "Keep the narrative direct."
            ),
            ComplexityLevel.MODERATE: (
                "Balance depth with accessibility. "
                "2-3 key reveals work well. "
                "Build context before diving deep. "
                "Use multiple visual types."
            ),
            ComplexityLevel.DEEP: (
                "Full investigative depth is appropriate. "
                "Multiple layers of reveals. "
                "Comprehensive context building. "
                "Rich visual storytelling with variety."
            )
        }
        return guidance[level]
    
    def _identify_focus_areas(self, factors: list[ComplexityFactor]) -> list[str]:
        """Identify areas that need special attention."""
        focus_areas = []
        
        for f in factors:
            if f.score > 0.7:  # High complexity
                focus_areas.append(f"Deep focus needed: {f.name}")
            elif f.score < 0.3:  # Low complexity
                focus_areas.append(f"Strength area: {f.name}")
        
        return focus_areas


# ─── Quick Assessment (No LLM) ─────────────────────────────────────────────────

def quick_assess_complexity(topic: str, genre: str = None) -> ComplexityResult:
    """
    Quick complexity assessment without LLM calls.
    
    Uses heuristics based on topic keywords and genre.
    Useful for initial triage before full assessment.
    """
    # Heuristic scoring based on keywords
    topic_lower = topic.lower()
    
    # High complexity indicators
    high_keywords = [
        "system", "conspiracy", "hidden", "network", "corruption",
        "geopolitics", "economics", "mechanism", "complex", "crisis"
    ]
    
    # Low complexity indicators
    low_keywords = [
        "simple", "guide", "how to", "tips", "basics", "introduction"
    ]
    
    high_count = sum(1 for kw in high_keywords if kw in topic_lower)
    low_count = sum(1 for kw in low_keywords if kw in topic_lower)
    
    # Calculate base score
    base_score = 1.5 + (high_count * 0.2) - (low_count * 0.15)
    base_score = max(1.0, min(3.0, base_score))
    
    # Adjust by genre
    genre_complexity = {
        "tech_systems": 0.3,
        "economics": 0.3,
        "current_situation": 0.2,
        "history": 0.1,
        "islamic_history": 0.0,
        "south_asian_history": 0.0
    }
    
    if genre:
        base_score += genre_complexity.get(genre, 0)
        base_score = min(3.0, base_score)
    
    # Determine level
    if base_score < 1.7:
        level = ComplexityLevel.SHALLOW
    elif base_score < 2.3:
        level = ComplexityLevel.MODERATE
    else:
        level = ComplexityLevel.DEEP
    
    return ComplexityResult(
        overall_score=round(base_score, 2),
        level=level,
        research_dimensions_needed=2 if level == ComplexityLevel.SHALLOW else (4 if level == ComplexityLevel.MODERATE else 6),
        narrative_complexity="simple" if level == ComplexityLevel.SHALLOW else ("multi-layered" if level == ComplexityLevel.MODERATE else "complex"),
        visual_anchors_estimated=3 if level == ComplexityLevel.SHALLOW else (7 if level == ComplexityLevel.MODERATE else 12),
        factors=[],
        depth_guidance=f"Quick assessment based on topic analysis",
        focus_areas=[f"Heuristic assessment for: {topic[:30]}"],
        topic=topic
    )
