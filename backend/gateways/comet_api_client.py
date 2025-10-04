"""
CometAPI Integration Client
500+ AI Models with Enterprise Stability and 20% Cost Savings
"""

import asyncio
import aiohttp
import json
from typing import Dict, List, Optional, AsyncGenerator, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class CometModelType(Enum):
    CHAT = "chat"
    COMPLETION = "completion"
    IMAGE_GENERATION = "image-generation"
    MULTIMODAL = "multimodal"
    EMBEDDING = "embedding"

@dataclass
class CometAPIConfig:
    api_key: str
    base_url: str = "https://api.cometapi.com/v1"
    timeout: int = 30
    max_retries: int = 3
    enable_streaming: bool = True
    enable_caching: bool = True
    cost_optimization: bool = True

@dataclass
class CometModel:
    id: str
    name: str
    provider: str
    model_type: CometModelType
    pricing: Dict[str, float]
    capabilities: List[str]
    context_length: int
    description: str
    performance_tier: str = "standard"  # standard, premium, enterprise

class CometAPIClient:
    """
    CometAPI Client - Access to 500+ AI Models with Enterprise Features
    Provides 20% cost savings and high stability for production workloads
    """
    
    def __init__(self, config: CometAPIConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.available_models: Dict[str, CometModel] = {}
        self.usage_stats = {
            "requests_made": 0,
            "total_cost": 0.0,
            "total_tokens": 0,
            "errors": 0,
            "cache_hits": 0
        }
        self.model_cache: Dict[str, Any] = {}
        self.last_model_refresh = datetime.min
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()
        
    async def connect(self):
        """Initialize connection and load available models"""
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "HyperSearch-Platform/1.0",
            "X-API-Version": "2024-10-01"
        }
        
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=10)
        
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout,
            connector=connector
        )
        
        # Load available models
        await self.refresh_models()
        
        logger.info(f"🟢 CometAPI connected - {len(self.available_models)} models available")
        
    async def disconnect(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()
        logger.info("🔴 CometAPI disconnected")
        
    async def refresh_models(self, force: bool = False):
        """Load/refresh available models from CometAPI"""
        # Cache models for 1 hour
        if not force and (datetime.now() - self.last_model_refresh) < timedelta(hours=1):
            return
            
        try:
            async with self.session.get(f"{self.config.base_url}/models") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    self.available_models.clear()
                    for model_data in data.get('models', []):
                        model = CometModel(
                            id=model_data['id'],
                            name=model_data['name'],
                            provider=model_data.get('provider', 'Unknown'),
                            model_type=CometModelType(model_data.get('type', 'chat')),
                            pricing=model_data.get('pricing', {}),
                            capabilities=model_data.get('capabilities', []),
                            context_length=model_data.get('context_length', 4096),
                            description=model_data.get('description', ''),
                            performance_tier=model_data.get('tier', 'standard')
                        )
                        self.available_models[model.id] = model
                        
                    self.last_model_refresh = datetime.now()
                    logger.info(f"📋 Loaded {len(self.available_models)} CometAPI models")
                else:
                    logger.error(f"Failed to load models: HTTP {response.status}")
                    
        except Exception as e:
            logger.error(f"Error loading CometAPI models: {e}")
            
    async def chat_completion(self, 
                            model: str, 
                            messages: List[Dict[str, str]], 
                            **kwargs) -> Dict[str, Any]:
        """Chat completion with enhanced error handling and optimization"""
        
        # Validate model
        if model not in self.available_models:
            await self.refresh_models(force=True)
            if model not in self.available_models:
                raise ValueError(f"Model '{model}' not available in CometAPI")
                
        # Prepare request payload
        payload = {
            "model": model,
            "messages": messages,
            **kwargs
        }
        
        # Add cost optimization features
        if self.config.cost_optimization:
            payload["cost_optimize"] = True
            
        # Add caching if enabled
        cache_key = None
        if self.config.enable_caching:
            cache_key = self._generate_cache_key(payload)
            cached_response = self.model_cache.get(cache_key)
            if cached_response:
                self.usage_stats["cache_hits"] += 1
                return cached_response
                
        # Execute request with retry logic
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
                        
                        # Track usage statistics
                        self._update_usage_stats(result, response_time)
                        
                        # Cache successful response
                        if cache_key and self.config.enable_caching:
                            self.model_cache[cache_key] = result
                            
                        return result
                        
                    elif response.status == 429:  # Rate limit
                        retry_after = int(response.headers.get('Retry-After', 2 ** attempt))
                        logger.warning(f"Rate limited, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue
                        
                    elif response.status >= 500:  # Server error
                        if attempt < self.config.max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            error_data = await response.json()
                            raise Exception(f"Server error: {error_data}")
                            
                    else:
                        error_data = await response.json()
                        raise Exception(f"API error: {error_data}")
                        
            except asyncio.TimeoutError:
                if attempt < self.config.max_retries - 1:
                    logger.warning(f"Request timeout, retrying (attempt {attempt + 1})")
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    self.usage_stats["errors"] += 1
                    raise Exception("Request timeout after retries")
                    
            except Exception as e:
                if attempt < self.config.max_retries - 1:
                    logger.warning(f"Request failed, retrying: {e}")
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    self.usage_stats["errors"] += 1
                    raise e
                    
        raise Exception("Max retries exceeded")
        
    async def stream_chat_completion(self, 
                                   model: str, 
                                   messages: List[Dict[str, str]], 
                                   **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """Streaming chat completion"""
        
        if not self.config.enable_streaming:
            # Fallback to regular completion
            result = await self.chat_completion(model, messages, **kwargs)
            yield result
            return
            
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
            
    async def image_generation(self, 
                             prompt: str, 
                             model: str = "dall-e-3", 
                             **kwargs) -> Dict[str, Any]:
        """Generate images using CometAPI image models"""
        
        payload = {
            "model": model,
            "prompt": prompt,
            "n": kwargs.get("n", 1),
            "size": kwargs.get("size", "1024x1024"),
            "quality": kwargs.get("quality", "standard"),
            "style": kwargs.get("style", "vivid")
        }
        
        try:
            start_time = datetime.now()
            
            async with self.session.post(
                f"{self.config.base_url}/images/generations",
                json=payload
            ) as response:
                
                response_time = (datetime.now() - start_time).total_seconds()
                
                if response.status == 200:
                    result = await response.json()
                    self._update_usage_stats(result, response_time, is_image=True)
                    return result
                else:
                    error_data = await response.json()
                    raise Exception(f"Image generation error: {error_data}")
                    
        except Exception as e:
            self.usage_stats["errors"] += 1
            raise e
            
    async def get_embeddings(self, 
                           texts: Union[str, List[str]], 
                           model: str = "text-embedding-ada-002") -> Dict[str, Any]:
        """Generate text embeddings"""
        
        if isinstance(texts, str):
            texts = [texts]
            
        payload = {
            "model": model,
            "input": texts
        }
        
        try:
            async with self.session.post(
                f"{self.config.base_url}/embeddings",
                json=payload
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    self.usage_stats["requests_made"] += 1
                    return result
                else:
                    error_data = await response.json()
                    raise Exception(f"Embeddings error: {error_data}")
                    
        except Exception as e:
            self.usage_stats["errors"] += 1
            raise e
            
    def _generate_cache_key(self, payload: Dict[str, Any]) -> str:
        """Generate cache key for request"""
        import hashlib
        
        # Create deterministic hash from request payload
        cache_data = {
            "model": payload.get("model"),
            "messages": payload.get("messages"),
            "temperature": payload.get("temperature", 0.7),
            "max_tokens": payload.get("max_tokens")
        }
        
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_str.encode()).hexdigest()
        
    def _update_usage_stats(self, result: Dict[str, Any], response_time: float, is_image: bool = False):
        """Update usage statistics"""
        self.usage_stats["requests_made"] += 1
        
        if not is_image:
            usage = result.get('usage', {})
            total_tokens = usage.get('total_tokens', 0)
            self.usage_stats["total_tokens"] += total_tokens
            
            # Estimate cost (with 20% CometAPI discount)
            model_id = result.get('model', '')
            if model_id in self.available_models:
                model = self.available_models[model_id]
                input_cost = usage.get('prompt_tokens', 0) * model.pricing.get('input', 0) * 0.8  # 20% discount
                output_cost = usage.get('completion_tokens', 0) * model.pricing.get('output', 0) * 0.8
                total_cost = input_cost + output_cost
                self.usage_stats["total_cost"] += total_cost
        else:
            # Image generation cost
            self.usage_stats["total_cost"] += 0.032 * 0.8  # DALL-E-3 with 20% discount
            
    async def get_model_info(self, model_id: str) -> Optional[CometModel]:
        """Get detailed information about a specific model"""
        if model_id not in self.available_models:
            await self.refresh_models(force=True)
            
        return self.available_models.get(model_id)
        
    async def list_models(self, 
                        model_type: Optional[CometModelType] = None,
                        provider: Optional[str] = None,
                        performance_tier: Optional[str] = None) -> List[CometModel]:
        """List available models with optional filtering"""
        
        models = list(self.available_models.values())
        
        if model_type:
            models = [m for m in models if m.model_type == model_type]
            
        if provider:
            models = [m for m in models if m.provider.lower() == provider.lower()]
            
        if performance_tier:
            models = [m for m in models if m.performance_tier == performance_tier]
            
        return models
        
    async def get_cost_estimate(self, 
                              model: str, 
                              input_tokens: int, 
                              output_tokens: int = None) -> Dict[str, float]:
        """Estimate cost for request"""
        
        if model not in self.available_models:
            return {"error": "Model not found"}
            
        model_info = self.available_models[model]
        
        input_cost = input_tokens * model_info.pricing.get('input', 0) * 0.8  # 20% discount
        output_cost = (output_tokens or input_tokens) * model_info.pricing.get('output', 0) * 0.8
        
        return {
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": input_cost + output_cost,
            "discount_applied": 0.2,
            "currency": "USD"
        }
        
    def get_usage_statistics(self) -> Dict[str, Any]:
        """Get client usage statistics"""
        stats = self.usage_stats.copy()
        
        # Calculate derived metrics
        if stats["requests_made"] > 0:
            stats["average_cost_per_request"] = stats["total_cost"] / stats["requests_made"]
            stats["error_rate"] = stats["errors"] / stats["requests_made"]
            stats["cache_hit_rate"] = stats["cache_hits"] / stats["requests_made"]
            
        if stats["total_tokens"] > 0:
            stats["average_cost_per_token"] = stats["total_cost"] / stats["total_tokens"]
            
        stats["models_available"] = len(self.available_models)
        stats["last_model_refresh"] = self.last_model_refresh.isoformat()
        
        return stats
        
    async def health_check(self) -> Dict[str, Any]:
        """Check CometAPI service health"""
        try:
            start_time = datetime.now()
            
            async with self.session.get(f"{self.config.base_url}/health") as response:
                response_time = (datetime.now() - start_time).total_seconds()
                
                if response.status == 200:
                    return {
                        "status": "healthy",
                        "response_time": response_time,
                        "models_available": len(self.available_models),
                        "last_check": datetime.now().isoformat()
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "response_time": response_time,
                        "error": f"HTTP {response.status}",
                        "last_check": datetime.now().isoformat()
                    }
                    
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "last_check": datetime.now().isoformat()
            }