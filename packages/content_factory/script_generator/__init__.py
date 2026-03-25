"""
Script Generator Package

Provides the self-evolving script generation system:
- Evolution loop with no max iterations
- Self-evaluation against quality criteria
- Prompt strategy adjustment
- Johnny Harris style templates
- Complexity assessment for depth determination
- Decision logging for learning from past decisions

KEY FEATURES:
1. Self-evolving loop: Generates → Evaluates → Adjusts → Repeats (until 85% threshold)
2. Learning log: Tracks what improved and what didn't work
3. Decision history: Records strategy decisions and their outcomes
4. Pattern recognition: Uses historical patterns for better decisions
5. Complexity assessment: Determines research depth, NOT duration
"""

# Core evolution system
from .evolution_loop import (
    ScriptEvolutionLoop,
    EvolutionLog,
    ImprovementRecord,
    FailureRecord,
    IterationDecision,
    PatternLearner,
)

# Evaluation and adjustment
from .self_evaluator import SelfEvaluator, EVALUATION_CRITERIA
from .prompt_adjuster import PromptAdjuster

# Generation
from .jh_style import JHStyleGenerator

# Models
from .models import (
    DualColumnScript,
    DualColumnEntry,
    SectionLabel,
    VisualType,
    EvaluationResult,
    SelfEvaluationReport,
    IterationLog,
)

# Complexity assessment
from .complexity_assessor import (
    ComplexityAssessor,
    ComplexityResult,
    ComplexityLevel,
    ComplexityFactor,
    quick_assess_complexity,
)

# Decision logging
from .decision_log import (
    DecisionLog,
    DecisionRecord,
    DecisionType,
    DecisionOutcome,
    DecisionContext,
    DecisionExpected,
    DecisionActual,
)

__all__ = [
    # Core evolution
    "ScriptEvolutionLoop",
    "EvolutionLog",
    "ImprovementRecord",
    "FailureRecord",
    "IterationDecision",
    "PatternLearner",
    
    # Evaluation
    "SelfEvaluator",
    "EVALUATION_CRITERIA",
    "PromptAdjuster",
    
    # Generation
    "JHStyleGenerator",
    
    # Models
    "DualColumnScript",
    "DualColumnEntry",
    "SectionLabel",
    "VisualType",
    "EvaluationResult",
    "SelfEvaluationReport",
    "IterationLog",
    
    # Complexity
    "ComplexityAssessor",
    "ComplexityResult",
    "ComplexityLevel",
    "ComplexityFactor",
    "quick_assess_complexity",
    
    # Decision logging
    "DecisionLog",
    "DecisionRecord",
    "DecisionType",
    "DecisionOutcome",
    "DecisionContext",
    "DecisionExpected",
    "DecisionActual",
]
