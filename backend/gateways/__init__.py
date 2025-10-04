"""
HyperSearch Multi-AI Gateway Platform
Enterprise-grade AI model access through unified interface
"""

from .comet_api_client import CometAPIClient, CometAPIConfig
from .openrouter_client import OpenRouterClient, OpenRouterConfig
from .aiml_api_client import AIMLAPIClient, AIMLAPIConfig
from .huggingface_client import HuggingFaceClient, HuggingFaceConfig, HuggingFaceTask
from .gateway_orchestrator import GatewayOrchestrator, GatewayType

__all__ = [
    'CometAPIClient',
    'CometAPIConfig',
    'OpenRouterClient', 
    'OpenRouterConfig',
    'AIMLAPIClient',
    'AIMLAPIConfig',
    'HuggingFaceClient',
    'HuggingFaceConfig',
    'HuggingFaceTask',
    'GatewayOrchestrator',
    'GatewayType'
]

# Gateway platform registry
GATEWAY_PLATFORMS = {
    'comet_api': CometAPIClient,
    'openrouter': OpenRouterClient,
    'aiml_api': AIMLAPIClient,
    'huggingface': HuggingFaceClient
}

# Supported capabilities across gateways
CAPABILITIES = {
    'text_generation': ['comet_api', 'openrouter', 'aiml_api', 'huggingface'],
    'chat_completion': ['comet_api', 'openrouter', 'aiml_api', 'huggingface'],
    'image_generation': ['comet_api', 'aiml_api'],
    'speech_to_text': ['aiml_api'],
    'text_to_speech': ['aiml_api'],
    'multimodal': ['comet_api', 'aiml_api'],
    'function_calling': ['openrouter'],
    'custom_models': ['huggingface'],
    'open_source': ['huggingface']
}