"""
OpenRouter Integration Client
400+ AI Models with Transparent Pricing and Provider Diversity
"""

import aiohttp
import json
import asyncio
from typing import Dict, List, Optional, Any, AsyncGenerator, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ProviderStatus(Enum):
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    DOWN = "down"
    UNKNOWN = "unknown"

@dataclass
class OpenRouterConfig:
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    site_url: str = "https://hypersearch.ai"
    app_name: str = "HyperSearch AI Platform"
    timeout: int = 30
    max_retries: int = 3
    enable_fallback: bool = True
    preferred_providers: List[str] = field(default_factory=list)

@dataclass
class OpenRouterModel:
    id: str
    name: str
    description: str
    pricing: Dict[str, float]
    context_length: int
    architecture: Dict[str, Any]
    top_provider: Dict[str, Any]
    per_request_limits: Optional[Dict[str, int]] = None

class OpenRouterClient:
    """
    OpenRouter Client - Access to 400+ AI Models from Major Providers
    Drop-in OpenAI replacement with intelligent provider routing
    """
    
    def __init__(self, config: OpenRouterConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.available_models: Dict[str, OpenRouterModel] = {}
        self.provider_status: Dict[str, ProviderStatus] = {}
        self.usage_stats = {
            "requests_made": 0,
            "total_cost": 0.0,
            "provider_costs": {},
            "fallback_used": 0,
            "errors": 0
        }
        self.generation_history: List[Dict] = []
        
    async def __aenter__(self):
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
        
    async def connect(self):
        """Initialize OpenRouter connection"""
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "HTTP-Referer": self.config.site_url,
            "X-Title": self.config.app_name,
            "Content-Type": "application/json"
        }
        
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        connector = aiohttp.TCPConnector(limit=50, limit_per_host=10)
        
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout,
            connector=connector
        )
        
        # Load available models and provider status
        await self.refresh_models()
        await self.update_provider_status()
        
        logger.info(f"🟢 OpenRouter connected - {len(self.available_models)} models available")
        
    async def disconnect(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()
        logger.info("🔴 OpenRouter disconnected")
        
    async def refresh_models(self):
        """Load/refresh available models from OpenRouter"""
        try:
            async with self.session.get(f"{self.config.base_url}/models") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    self.available_models.clear()
                    for model_data in data.get('data', []):
                        model = OpenRouterModel(
                            id=model_data['id'],
                            name=model_data['name'],
                            description=model_data.get('description', ''),
                            pricing=model_data.get('pricing', {}),
                            context_length=model_data.get('context_length', 4096),
                            architecture=model_data.get('architecture', {}),
                            top_provider=model_data.get('top_provider', {}),
                            per_request_limits=model_data.get('per_request_limits')
                        )
                        self.available_models[model.id] = model
                        
                    logger.info(f"📋 Loaded {len(self.available_models)} OpenRouter models")
                else:
                    logger.error(f"Failed to load models: HTTP {response.status}")
                    
        except Exception as e:
            logger.error(f"Error loading OpenRouter models: {e}")
            
    async def update_provider_status(self):
        """Update status of available providers"""
        try:
            # Check popular providers
            providers_to_check = ['openai', 'anthropic', 'meta', 'google', 'mistral']
            
            for provider in providers_to_check:
                try:
                    # Simple health check using a lightweight model
                    test_model = self._get_provider_test_model(provider)
                    if test_model:
                        start_time = datetime.now()
                        
                        test_payload = {
                            "model": test_model,
                            "messages": [{"role": "user", "content": "test"}],
                            "max_tokens": 1,
                            "provider": {"order": [provider]}
                        }
                        
                        async with self.session.post(
                            f"{self.config.base_url}/chat/completions",
                            json=test_payload
                        ) as response:
                            
                            response_time = (datetime.now() - start_time).total_seconds()
                            
                            if response.status == 200:
                                self.provider_status[provider] = ProviderStatus.AVAILABLE
                            elif response.status == 429:
                                self.provider_status[provider] = ProviderStatus.RATE_LIMITED
                            else:
                                self.provider_status[provider] = ProviderStatus.DOWN
                                
                except Exception:
                    self.provider_status[provider] = ProviderStatus.UNKNOWN
                    
        except Exception as e:
            logger.error(f"Error updating provider status: {e}")
            
    def _get_provider_test_model(self, provider: str) -> Optional[str]:
        """Get a lightweight model for provider testing"""
        test_models = {
            'openai': 'openai/gpt-3.5-turbo',
            'anthropic': 'anthropic/claude-3-haiku',
            'meta': 'meta-llama/llama-3-8b-instruct',
            'google': 'google/gemini-pro',
            'mistral': 'mistral/mistral-7b-instruct'
        }
        return test_models.get(provider)
        
    async def chat_completion(self, 
                            model: str, 
                            messages: List[Dict[str, str]], 
                            **kwargs) -> Dict[str, Any]:
        """Chat completion with intelligent provider routing"""
        
        # Validate model availability
        if model not in self.available_models:
            await self.refresh_models()
            if model not in self.available_models:
                raise ValueError(f"Model '{model}' not available on OpenRouter")
                
        # Prepare request payload
        payload = {
            "model": model,
            "messages": messages,
            **kwargs
        }
        
        # Add provider preferences if configured
        if self.config.preferred_providers:
            if "provider" not in payload:
                payload["provider"] = {}
            payload["provider"]["order"] = self.config.preferred_providers
            
        # Execute request with retry and fallback logic
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                start_time = datetime.now()
                
                async with self.session.post(
                    f"{self.config.base_url}/chat/completions",
                    json=payload
                ) as response:
                    
                    response_time = (datetime.now() - start_time).total_seconds()
                    
                    if response.status == 200:
                        result = await response.json()
                        
                        # Track usage and costs
                        await self._track_usage(result, response_time)
                        
                        return result
                        
                    elif response.status == 429:  # Rate limit
                        retry_after = int(response.headers.get('Retry-After', 2 ** attempt))
                        logger.warning(f"Rate limited, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue
                        
                    elif response.status == 502 and self.config.enable_fallback:
                        # Provider failure - try fallback
                        fallback_result = await self._try_fallback_provider(payload)
                        if fallback_result:
                            self.usage_stats["fallback_used"] += 1
                            return fallback_result
                        else:
                            if attempt < self.config.max_retries - 1:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            
                    else:
                        error_data = await response.json()
                        last_error = Exception(f"OpenRouter API error: {error_data}")
                        
                        if attempt < self.config.max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            raise last_error
                            
            except asyncio.TimeoutError:
                last_error = Exception("Request timeout")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                    
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                    
        self.usage_stats["errors"] += 1
        raise last_error or Exception("Max retries exceeded")
        
    async def _try_fallback_provider(self, original_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Try alternative providers for failed requests"""
        model_id = original_payload["model"]
        
        # Find alternative models/providers for same capability
        fallback_models = self._get_fallback_models(model_id)
        
        for fallback_model in fallback_models[:2]:  # Try top 2 alternatives
            try:
                fallback_payload = original_payload.copy()
                fallback_payload["model"] = fallback_model
                
                async with self.session.post(
                    f"{self.config.base_url}/chat/completions",
                    json=fallback_payload
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"Fallback successful: {model_id} -> {fallback_model}")
                        return result
                        
            except Exception as e:
                logger.warning(f"Fallback to {fallback_model} failed: {e}")
                continue
                
        return None
        
    def _get_fallback_models(self, original_model: str) -> List[str]:
        """Get fallback models for failed requests"""
        # Simplified fallback logic - in production would be more sophisticated
        fallback_mapping = {
            'openai/gpt-4': ['anthropic/claude-3-opus', 'google/gemini-pro'],
            'openai/gpt-3.5-turbo': ['anthropic/claude-3-haiku', 'meta-llama/llama-3-8b-instruct'],
            'anthropic/claude-3-opus': ['openai/gpt-4', 'google/gemini-pro'],
            'anthropic/claude-3-sonnet': ['openai/gpt-4', 'google/gemini-pro'],
            'meta-llama/llama-3-70b': ['openai/gpt-4', 'anthropic/claude-3-opus']
        }
        
        return fallback_mapping.get(original_model, ['openai/gpt-3.5-turbo'])
        
    async def stream_chat_completion(self, 
                                   model: str, 
                                   messages: List[Dict[str, str]], 
                                   **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """Streaming chat completion"""
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            **kwargs
        }
        
        try:
            async with self.session.post(
                f"{self.config.base_url}/chat/completions",
                json=payload
            ) as response:
                
                if response.status != 200:
                    error_data = await response.json()
                    raise Exception(f"Streaming error: {error_data}")
                    
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data: '):
                        data = line[6:]  # Remove 'data: ' prefix
                        if data == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data)
                            yield chunk
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            self.usage_stats["errors"] += 1
            raise e
            
    async def get_generation_stats(self) -> Dict[str, Any]:
        """Get detailed generation statistics from OpenRouter"""
        try:
            async with self.session.get(f"{self.config.base_url}/generation") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Store in history for trend analysis
                    self.generation_history.append({
                        "timestamp": datetime.now(),
                        "data": data
                    })
                    
                    return data
                else:
                    return {"error": f"Failed to get stats: HTTP {response.status}"}
                    
        except Exception as e:
            return {"error": str(e)}
            
    async def _track_usage(self, result: Dict[str, Any], response_time: float):
        """Track usage statistics and costs"""
        self.usage_stats["requests_made"] += 1
        
        # Extract cost information if available
        if 'usage' in result:
            usage = result['usage']
            
            # OpenRouter provides cost in the response
            if 'cost' in result:
                cost = result['cost']
                self.usage_stats["total_cost"] += cost
                
                # Track per-provider costs
                provider = result.get('provider', 'unknown')
                if provider not in self.usage_stats["provider_costs"]:
                    self.usage_stats["provider_costs"][provider] = 0
                self.usage_stats["provider_costs"][provider] += cost
                
    async def get_model_info(self, model_id: str) -> Optional[OpenRouterModel]:
        """Get detailed information about a specific model"""
        if model_id not in self.available_models:
            await self.refresh_models()
            
        return self.available_models.get(model_id)
        
    async def compare_models(self, 
                           model_ids: List[str], 
                           comparison_criteria: List[str] = None) -> Dict[str, Any]:
        """Compare multiple models across various criteria"""
        
        if not comparison_criteria:
            comparison_criteria = ['pricing', 'context_length', 'speed', 'quality']
            
        comparison = {
            "models": {},
            "criteria": comparison_criteria,
            "recommendations": {}
        }
        
        for model_id in model_ids:
            model = await self.get_model_info(model_id)
            if model:
                comparison["models"][model_id] = {
                    "name": model.name,
                    "pricing": model.pricing,
                    "context_length": model.context_length,
                    "provider": model.top_provider,
                    "architecture": model.architecture
                }
                
        # Generate recommendations
        if comparison["models"]:
            # Cheapest model
            cheapest = min(
                comparison["models"].items(),
                key=lambda x: x[1]["pricing"].get("prompt", float('inf'))
            )
            comparison["recommendations"]["most_cost_effective"] = cheapest
            
            # Largest context
            largest_context = max(
                comparison["models"].items(),
                key=lambda x: x[1]["context_length"]
            )
            comparison["recommendations"]["largest_context"] = largest_context
            
        return comparison
        
    def get_provider_status(self) -> Dict[str, str]:
        """Get current status of all providers"""
        return {provider: status.value for provider, status in self.provider_status.items()}
        
    def get_usage_statistics(self) -> Dict[str, Any]:
        """Get comprehensive usage statistics"""
        stats = self.usage_stats.copy()
        
        # Calculate derived metrics
        if stats["requests_made"] > 0:
            stats["average_cost_per_request"] = stats["total_cost"] / stats["requests_made"]
            stats["error_rate"] = stats["errors"] / stats["requests_made"]
            stats["fallback_rate"] = stats["fallback_used"] / stats["requests_made"]
            
        stats["models_available"] = len(self.available_models)
        stats["providers_available"] = len([p for p in self.provider_status.values() if p == ProviderStatus.AVAILABLE])
        stats["last_update"] = datetime.now().isoformat()
        
        return stats
        
    async def health_check(self) -> Dict[str, Any]:
        """Check OpenRouter service health"""
        try:
            start_time = datetime.now()
            
            # Test with a simple request
            test_payload = {
                "model": "openai/gpt-3.5-turbo",
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 1
            }
            
            async with self.session.post(
                f"{self.config.base_url}/chat/completions",
                json=test_payload
            ) as response:
                
                response_time = (datetime.now() - start_time).total_seconds()
                
                return {
                    "status": "healthy" if response.status == 200 else "degraded",
                    "response_time": response_time,
                    "models_available": len(self.available_models),
                    "providers_available": len([p for p in self.provider_status.values() if p == ProviderStatus.AVAILABLE]),
                    "last_check": datetime.now().isoformat()
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "last_check": datetime.now().isoformat()
            }