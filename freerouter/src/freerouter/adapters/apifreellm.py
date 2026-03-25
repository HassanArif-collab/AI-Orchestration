"""
APIFreeLLM Adapter

APIFreeLLM uses a non-OpenAI-compatible API format. This adapter handles
the conversion between formats.

API Documentation (from user):
================================

Endpoint: POST https://apifreellm.com/api/v1/chat

Headers:
    Content-Type: application/json
    Authorization: Bearer YOUR_API_KEY (required)

Request Body:
    {
        "message": "Your prompt here",      // <- Note: "message" not "messages"
        "model": "apifreellm"               // Optional, defaults to "apifreellm"
    }

Response:
    {
        "success": true,
        "response": "AI response text...",
        "tier": "free",
        "features": {
            "unlimited": true,
            "delaySeconds": 25,
            "priorityProcessing": false
        }
    }

Error Codes:
    - 429: Rate limit — wait 25 seconds and try again
    - 401: Invalid API key
    - 400: Bad request - Missing parameters

Context Limits:
    - Free tier: 32k tokens (response truncated if exceeded)
    - Premium: 128k tokens

IMPORTANT: This API is NOT OpenAI-compatible!
- Uses "message" (singular) instead of "messages" (array)
- Returns "response" instead of "choices"
- Has a 25-second rate limit cooldown
"""

import asyncio
import time
from typing import Any, Optional

import httpx

from ..router import RouterError


class APIFreeLLMAdapter:
    """
    Adapter for APIFreeLLM's non-standard API.
    
    Converts OpenAI-format requests to APIFreeLLM format and back.
    """
    
    PROVIDER_NAME = "apifreellm"
    BASE_URL = "https://apifreellm.com/api/v1"
    DEFAULT_MODEL = "apifreellm"
    RATE_LIMIT_SECONDS = 25
    CONTEXT_LIMIT_FREE = 32000
    CONTEXT_LIMIT_PREMIUM = 128000
    
    def __init__(self, api_key: str):
        """
        Initialize the adapter with API key.
        
        Args:
            api_key: Your APIFreeLLM API key
        """
        self.api_key = api_key
        self._rate_limited_until: float = 0.0
    
    def _messages_to_string(self, messages: list[dict]) -> str:
        """
        Convert OpenAI messages array to single prompt string.
        
        APIFreeLLM expects a single "message" field, not an array.
        We combine all messages into one string with role markers.
        
        Args:
            messages: OpenAI-format messages array
            
        Returns:
            Combined prompt string
        """
        parts = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            # Handle different content types
            if isinstance(content, list):
                # Extract text from multimodal content
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif isinstance(item, str):
                        text_parts.append(item)
                content = "\n".join(text_parts)
            
            if role == "system":
                parts.append(f"[SYSTEM INSTRUCTIONS]\n{content}")
            elif role == "user":
                parts.append(f"[USER]\n{content}")
            elif role == "assistant":
                parts.append(f"[ASSISTANT]\n{content}")
        
        return "\n\n".join(parts)
    
    def _is_rate_limited(self) -> bool:
        """Check if we're in rate limit cooldown period."""
        return time.time() < self._rate_limited_until
    
    def _get_rate_limit_wait_time(self) -> float:
        """Get remaining wait time if rate limited."""
        if not self._is_rate_limited():
            return 0.0
        return max(0.0, self._rate_limited_until - time.time())
    
    async def _wait_for_rate_limit(self) -> None:
        """Wait until rate limit cooldown expires."""
        wait_time = self._get_rate_limit_wait_time()
        if wait_time > 0:
            await asyncio.sleep(wait_time)
    
    # ─── Non-streaming completion ─────────────────────────────────────────────
    
    async def complete(
        self,
        messages: list[dict],
        model: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """
        Perform non-streaming chat completion.
        
        Converts OpenAI format to APIFreeLLM format, makes request,
        and converts response back to OpenAI format.
        
        Args:
            messages: OpenAI-format messages array
            model: Model name (ignored, APIFreeLLM only has one model)
            temperature: Temperature parameter (passed through)
            max_tokens: Max tokens (passed through, may be truncated)
            
        Returns:
            OpenAI-format response dict
            
        Raises:
            RouterError: On API errors or rate limits
        """
        # Wait if rate limited
        if self._is_rate_limited():
            wait_time = self._get_rate_limit_wait_time()
            raise RouterError(
                f"APIFreeLLM rate limited. Wait {wait_time:.0f} more seconds."
            )
        
        # Convert messages to single string
        combined_message = self._messages_to_string(messages)
        
        # Estimate token count (rough: ~4 chars per token)
        estimated_tokens = len(combined_message) // 4
        if estimated_tokens > self.CONTEXT_LIMIT_FREE:
            # Truncate if over limit
            max_chars = self.CONTEXT_LIMIT_FREE * 4
            combined_message = combined_message[:max_chars]
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/chat",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}"
                    },
                    json={
                        "message": combined_message,
                        "model": self.DEFAULT_MODEL
                    }
                )
                
                # Handle rate limit (429)
                if response.status_code == 429:
                    self._rate_limited_until = time.time() + self.RATE_LIMIT_SECONDS
                    raise RouterError(
                        f"APIFreeLLM rate limited. Wait {self.RATE_LIMIT_SECONDS} seconds."
                    )
                
                # Handle auth error (401)
                if response.status_code == 401:
                    raise RouterError("Invalid APIFreeLLM API key")
                
                # Handle bad request (400)
                if response.status_code == 400:
                    try:
                        error_data = response.json()
                        raise RouterError(f"APIFreeLLM bad request: {error_data}")
                    except Exception:
                        raise RouterError(f"APIFreeLLM bad request: {response.text[:200]}")
                
                # Handle other errors
                if response.status_code != 200:
                    raise RouterError(
                        f"APIFreeLLM HTTP {response.status_code}: {response.text[:200]}"
                    )
                
                data = response.json()
                
                # Check for success
                if not data.get("success"):
                    raise RouterError(f"APIFreeLLM returned failure: {data}")
                
                # Convert to OpenAI format
                return self._to_openai_format(data.get("response", ""), model)
                
        except httpx.ConnectError:
            raise RouterError("Cannot connect to APIFreeLLM")
        except httpx.TimeoutException:
            raise RouterError("Timeout from APIFreeLLM")
        except RouterError:
            raise
        except Exception as e:
            raise RouterError(f"Unexpected APIFreeLLM error: {e}")
    
    # ─── Streaming completion ─────────────────────────────────────────────────
    
    async def stream(
        self,
        messages: list[dict],
        model: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        """
        Perform streaming chat completion.
        
        Note: APIFreeLLM doesn't support streaming in the traditional sense.
        We get the full response and yield it in chunks for compatibility.
        
        Args:
            messages: OpenAI-format messages array
            model: Model name
            temperature: Temperature parameter
            max_tokens: Max tokens
            
        Yields:
            OpenAI-format SSE chunks
        """
        import json
        
        # Check rate limit
        if self._is_rate_limited():
            wait_time = self._get_rate_limit_wait_time()
            yield f"data: {json.dumps({'error': f'APIFreeLLM rate limited. Wait {wait_time:.0f}s.'})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        # Get full response (APIFreeLLM doesn't support real streaming)
        try:
            result = await self.complete(messages, model, temperature, max_tokens)
            content = result["choices"][0]["message"]["content"]
            
            # Yield as simulated streaming chunks
            # First, send the meta chunk
            meta = {"_provider": self.PROVIDER_NAME, "_model": self.DEFAULT_MODEL}
            yield f"data: {json.dumps({'choices': [{'delta': {'role': 'assistant'}, 'index': 0}], 'meta': meta})}\n\n"
            
            # Yield content in chunks
            chunk_size = 50  # characters per chunk
            for i in range(0, len(content), chunk_size):
                chunk_content = content[i:i+chunk_size]
                chunk = {
                    "choices": [{
                        "delta": {"content": chunk_content},
                        "index": 0,
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0.01)  # Small delay for realistic streaming
            
            # Send final chunk
            final_chunk = {
                "choices": [{
                    "delta": {},
                    "index": 0,
                    "finish_reason": "stop"
                }]
            }
            yield f"data: {json.dumps(final_chunk)}\n\n"
            yield "data: [DONE]\n\n"
            
        except RouterError as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': f'APIFreeLLM error: {e}'})}\n\n"
            yield "data: [DONE]\n\n"
    
    # ─── Format conversion ─────────────────────────────────────────────────────
    
    def _to_openai_format(self, response_text: str, model: str) -> dict[str, Any]:
        """
        Convert APIFreeLLM response to OpenAI format.
        
        Args:
            response_text: The AI response text
            model: Model name for metadata
            
        Returns:
            OpenAI-format response dict
        """
        return {
            "id": f"apifreellm-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": self.DEFAULT_MODEL,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 0,  # APIFreeLLM doesn't provide this
                "completion_tokens": 0,
                "total_tokens": 0
            },
            "_provider": self.PROVIDER_NAME,
            "_model": self.DEFAULT_MODEL
        }
