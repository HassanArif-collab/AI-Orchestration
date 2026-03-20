"""
Task classifier for intelligent model selection.

Analyzes incoming requests and classifies them into task categories
to route to the most appropriate free model.
"""

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import httpx


class TaskCategory(str, Enum):
    """Task categories for model selection."""

    SIMPLE_CHAT = "simple_chat"
    CODING = "coding"
    REASONING = "reasoning"
    AGENTIC = "agentic"
    VISION = "vision"
    LONG_CONTEXT = "long_context"
    RESEARCH = "research"


@dataclass
class ClassificationResult:
    """Result of task classification."""

    category: TaskCategory
    confidence: float
    reasoning: str
    recommended_model: str
    fallback_models: list[str]


# Classification prompts
CLASSIFIER_SYSTEM_PROMPT = """You are a task classifier for an LLM routing system.
Analyze the user's request and classify it into exactly ONE of these categories:

- simple_chat: General conversation, questions, simple tasks
- coding: Writing, debugging, or explaining code
- reasoning: Mathematical reasoning, logic puzzles, complex analysis
- agentic: Multi-step tasks requiring planning, tool use, or autonomous behavior
- vision: Tasks involving images or visual content
- long_context: Tasks requiring processing very long documents (>10k tokens)
- research: Research tasks requiring synthesis of multiple sources

Respond with ONLY a JSON object (no markdown):
{"category": "<category>", "confidence": <0.0-1.0>, "reasoning": "<brief reason>"}"""

CLASSIFIER_USER_PROMPT = """Classify this request:
{content}

Respond with only the JSON object."""


# Keyword-based classification patterns (fallback when classifier unavailable)
KEYWORD_PATTERNS = {
    TaskCategory.CODING: [
        r"\b(code|function|class|method|variable|bug|debug|error|exception|implement|refactor|api|script|program|algorithm)\b",
        r"\b(python|javascript|typescript|java|rust|go|c\+\+|ruby|swift)\b",
        r"\b(git|commit|pull request|merge|branch)\b",
        r"```",  # Code blocks
    ],
    TaskCategory.REASONING: [
        r"\b(reason|logic|analyze|derive|prove|calculate|solve|puzzle)\b",
        r"\b(math|mathematical|equation|formula)\b",
        r"\b(step[- ]by[- ]step|systematically)\b",
    ],
    TaskCategory.AGENTIC: [
        r"\b(plan|execute|autonomous|agent|workflow|pipeline|multi[- ]step)\b",
        r"\b(tool|function call|use.*tool)\b",
        r"\b(search|browse|fetch|download)\b",
    ],
    TaskCategory.VISION: [
        r"\b(image|picture|photo|screenshot|visual|see|look at)\b",
        r"\b(ocr|extract.*text.*image|describe.*image)\b",
        r"\.(png|jpg|jpeg|gif|webp|bmp)\b",
    ],
    TaskCategory.LONG_CONTEXT: [
        r"\b(entire|full|whole|complete|all)\b.*\b(document|file|codebase|book)\b",
        r"\b(analyze.*thousands|many.*files|large.*codebase)\b",
        r"\b(context.*window|token.*limit)\b",
    ],
    TaskCategory.RESEARCH: [
        r"\b(research|investigate|compare|contrast|synthesize|sources)\b",
        r"\b(multiple.*documents|several.*files)\b",
        r"\b(literature|academic|paper|study)\b",
    ],
}


class TaskClassifier:
    """Classifies tasks for intelligent model routing."""

    def __init__(
        self,
        classifier_model: str = "groq/llama-3.3-70b-versatile",
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        use_fast_classifier: bool = True,
        fallback_to_keywords: bool = True,
    ):
        """Initialize the task classifier.

        Args:
            classifier_model: Model to use for classification (should be fast/cheap)
            api_base: Base URL for the classifier API
            api_key: API key for the classifier
            use_fast_classifier: Whether to use AI-based classification
            fallback_to_keywords: Fall back to keyword matching if AI fails
        """
        self.classifier_model = classifier_model
        self.api_base = api_base
        self.api_key = api_key
        self.use_fast_classifier = use_fast_classifier
        self.fallback_to_keywords = fallback_to_keywords

    async def classify(self, content: str, images: Optional[list[str]] = None) -> ClassificationResult:
        """Classify a task based on content.

        Args:
            content: The text content to classify
            images: Optional list of image URLs/base64 data

        Returns:
            ClassificationResult with category and recommendations
        """
        # If images present, immediately classify as vision
        if images:
            return self._get_result(TaskCategory.VISION, 1.0, "Images detected in request")

        # Try AI classification first
        if self.use_fast_classifier:
            try:
                result = await self._ai_classify(content)
                if result and result.confidence > 0.7:
                    return result
            except Exception:
                pass  # Fall through to keyword classification

        # Fall back to keyword matching
        if self.fallback_to_keywords:
            category = self._keyword_classify(content)
            return self._get_result(category, 0.8, "Keyword-based classification")

        # Default to simple_chat
        return self._get_result(TaskCategory.SIMPLE_CHAT, 0.5, "Default classification")

    async def _ai_classify(self, content: str) -> Optional[ClassificationResult]:
        """Use AI model to classify the task."""
        if not self.api_key and not self.api_base:
            return None

        prompt = CLASSIFIER_USER_PROMPT.format(content=content[:2000])  # Truncate for speed

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Try local Ollama first if available
                if self.api_base and "ollama" in self.api_base:
                    response = await client.post(
                        f"{self.api_base}/api/chat",
                        json={
                            "model": self.classifier_model.replace("ollama/", ""),
                            "messages": [
                                {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
                                {"role": "user", "content": prompt},
                            ],
                            "stream": False,
                        },
                    )
                else:
                    # OpenAI-compatible API
                    response = await client.post(
                        f"{self.api_base or 'https://api.openai.com/v1'}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json={
                            "model": self.classifier_model,
                            "messages": [
                                {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
                                {"role": "user", "content": prompt},
                            ],
                            "max_tokens": 100,
                            "temperature": 0.1,
                        },
                    )

                if response.status_code == 200:
                    data = response.json()
                    content_text = data["choices"][0]["message"]["content"]
                    return self._parse_classification(content_text)

        except Exception:
            pass

        return None

    def _keyword_classify(self, content: str) -> TaskCategory:
        """Classify using keyword patterns."""
        content_lower = content.lower()
        scores = {category: 0 for category in TaskCategory}

        for category, patterns in KEYWORD_PATTERNS.items():
            for pattern in patterns:
                matches = len(re.findall(pattern, content_lower, re.IGNORECASE))
                scores[category] += matches

        # Also check content length for long_context
        if len(content) > 5000:  # Approximate token count
            scores[TaskCategory.LONG_CONTEXT] += 3

        # Get category with highest score
        max_category = max(scores, key=scores.get)

        # Default to simple_chat if no keywords matched
        if scores[max_category] == 0:
            return TaskCategory.SIMPLE_CHAT

        return max_category

    def _parse_classification(self, response: str) -> Optional[ClassificationResult]:
        """Parse AI classification response."""
        try:
            # Extract JSON from response
            json_match = re.search(r"\{[^}]+\}", response)
            if json_match:
                data = json.loads(json_match.group())
                category = TaskCategory(data.get("category", "simple_chat"))
                confidence = float(data.get("confidence", 0.5))
                reasoning = data.get("reasoning", "")
                return self._get_result(category, confidence, reasoning)
        except (json.JSONDecodeError, ValueError):
            pass

        return None

    def _get_result(self, category: TaskCategory, confidence: float, reasoning: str) -> ClassificationResult:
        """Get classification result with model recommendations."""
        # Model recommendations per category
        recommendations = {
            TaskCategory.SIMPLE_CHAT: ("free-router/fast", ["free-router/smart", "free-router/balanced"]),
            TaskCategory.CODING: ("free-router/coder", ["free-router/smart", "free-router/fast"]),
            TaskCategory.REASONING: ("free-router/reasoning", ["free-router/smart", "free-router/coder"]),
            TaskCategory.AGENTIC: ("free-router/smart", ["free-router/coder", "free-router/fast"]),
            TaskCategory.VISION: ("free-router/vision", ["free-router/smart"]),
            TaskCategory.LONG_CONTEXT: ("free-router/long-context", ["free-router/smart", "free-router/fast"]),
            TaskCategory.RESEARCH: ("free-router/long-context", ["free-router/smart", "free-router/reasoning"]),
        }

        recommended, fallbacks = recommendations.get(
            category, ("free-router/fast", ["free-router/smart"])
        )

        return ClassificationResult(
            category=category,
            confidence=confidence,
            reasoning=reasoning,
            recommended_model=recommended,
            fallback_models=fallbacks,
        )