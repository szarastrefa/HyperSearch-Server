"""
Base Integration Class
Foundation for all platform integrations
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class BaseIntegration(ABC):
    """
    Base class for all platform integrations
    Provides common functionality and interface
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get('name', self.__class__.__name__)
        self.enabled = config.get('enabled', True)
        self.rate_limit = config.get('rate_limit', 100)  # requests per minute
        self.timeout = config.get('timeout', 30)  # seconds
        
        # Common authentication fields
        self.client_id = config.get('client_id')
        self.client_secret = config.get('client_secret')
        self.redirect_uri = config.get('redirect_uri')
        
        # Integration metadata
        self.created_at = datetime.utcnow()
        self.last_sync = None
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
    
    @abstractmethod
    async def authenticate(self, user_id: str) -> Dict[str, Any]:
        """Authenticate user with the platform"""
        pass
    
    @abstractmethod
    async def search_all(self, query: str, user_token: str = None) -> Dict[str, List[Dict[str, Any]]]:
        """Search across all services in the platform"""
        pass
    
    @abstractmethod
    def get_supported_services(self) -> List[str]:
        """Get list of supported services"""
        pass
    
    @abstractmethod
    def get_integration_status(self) -> Dict[str, Any]:
        """Get integration status and health"""
        pass
    
    async def validate_token(self, token: str) -> bool:
        """Validate authentication token"""
        try:
            # Default implementation - should be overridden
            return bool(token)
        except Exception as e:
            logger.error(f"Token validation failed for {self.name}: {e}")
            return False
    
    def update_stats(self, success: bool = True):
        """Update integration statistics"""
        self.total_requests += 1
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get integration statistics"""
        success_rate = (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0
        
        return {
            'integration_name': self.name,
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'success_rate': round(success_rate, 2),
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'uptime': (datetime.utcnow() - self.created_at).total_seconds()
        }
    
    def is_healthy(self) -> bool:
        """Check if integration is healthy"""
        if not self.enabled:
            return False
        
        # Check success rate (should be > 80%)
        if self.total_requests > 10:
            success_rate = self.successful_requests / self.total_requests
            return success_rate > 0.8
        
        return True
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test connection to the platform"""
        try:
            # Basic connection test - should be overridden
            return {
                'status': 'connected',
                'message': f'{self.name} integration is active',
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def format_search_result(self, raw_result: Dict[str, Any], source: str, result_type: str) -> Dict[str, Any]:
        """Format search result to standard structure"""
        return {
            'id': raw_result.get('id', 'unknown'),
            'title': raw_result.get('title', raw_result.get('name', 'Untitled')),
            'content': raw_result.get('content', raw_result.get('description', '')),
            'source': source,
            'type': result_type,
            'url': raw_result.get('url', raw_result.get('link')),
            'created_time': raw_result.get('created_time', raw_result.get('created_at')),
            'updated_time': raw_result.get('updated_time', raw_result.get('updated_at')),
            'metadata': raw_result.get('metadata', {})
        }
    
    def __str__(self) -> str:
        return f"{self.name} Integration ({'enabled' if self.enabled else 'disabled'})"