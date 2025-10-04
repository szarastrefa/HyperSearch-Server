"""
Integration Manager
Manages all platform integrations and provides unified interface
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Type
from datetime import datetime
import json

from .base_integration import BaseIntegration
from .microsoft_integration import MicrosoftIntegration
from .google_integration import GoogleIntegration
from .meta_integration import MetaIntegration
from .github_integration import GitHubIntegration
from .slack_integration import SlackIntegration
from .notion_integration import NotionIntegration
from . import INTEGRATION_REGISTRY

logger = logging.getLogger(__name__)

class IntegrationManager:
    """
    Central manager for all platform integrations
    Provides unified interface for authentication and search
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.integrations: Dict[str, BaseIntegration] = {}
        self.user_tokens: Dict[str, Dict[str, str]] = {}  # user_id -> {platform: token}
        
        # Integration statistics
        self.stats = {
            'total_searches': 0,
            'successful_searches': 0,
            'failed_searches': 0,
            'integrations_active': 0
        }
        
        self._initialize_integrations()
    
    def _initialize_integrations(self):
        """Initialize all configured integrations"""
        try:
            for integration_name, integration_config in self.config.get('integrations', {}).items():
                if integration_config.get('enabled', True):
                    self._load_integration(integration_name, integration_config)
            
            self.stats['integrations_active'] = len(self.integrations)
            logger.info(f"🔗 Integration Manager initialized with {len(self.integrations)} integrations")
            
        except Exception as e:
            logger.error(f"Failed to initialize integrations: {e}")
    
    def _load_integration(self, name: str, config: Dict[str, Any]):
        """Load a specific integration"""
        try:
            integration_class = INTEGRATION_REGISTRY.get(name.lower())
            if integration_class:
                integration = integration_class(config)
                self.integrations[name] = integration
                logger.info(f"✅ Loaded integration: {name}")
            else:
                logger.warning(f"Unknown integration: {name}")
                
        except Exception as e:
            logger.error(f"Failed to load integration {name}: {e}")
    
    async def authenticate_user(self, user_id: str, platform: str) -> Dict[str, Any]:
        """Authenticate user with specific platform"""
        try:
            if platform not in self.integrations:
                return {"error": f"Integration {platform} not available"}
            
            integration = self.integrations[platform]
            return await integration.authenticate(user_id)
            
        except Exception as e:
            logger.error(f"Authentication failed for {platform}: {e}")
            return {"error": str(e), "status": "failed"}
    
    def store_user_token(self, user_id: str, platform: str, token: str):
        """Store user authentication token"""
        if user_id not in self.user_tokens:
            self.user_tokens[user_id] = {}
        
        self.user_tokens[user_id][platform] = token
        logger.info(f"Token stored for user {user_id} on platform {platform}")
    
    def get_user_token(self, user_id: str, platform: str) -> Optional[str]:
        """Get user authentication token for platform"""
        return self.user_tokens.get(user_id, {}).get(platform)
    
    async def search_platform(self, platform: str, query: str, user_id: str) -> Dict[str, Any]:
        """Search specific platform"""
        try:
            if platform not in self.integrations:
                return {"error": f"Integration {platform} not available"}
            
            integration = self.integrations[platform]
            user_token = self.get_user_token(user_id, platform)
            
            # Perform search
            start_time = datetime.utcnow()
            results = await integration.search_all(query, user_token)
            search_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Update statistics
            self.stats['total_searches'] += 1
            if results:
                self.stats['successful_searches'] += 1
                integration.update_stats(True)
            else:
                self.stats['failed_searches'] += 1
                integration.update_stats(False)
            
            return {
                "platform": platform,
                "query": query,
                "results": results,
                "search_time": search_time,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Search failed for platform {platform}: {e}")
            self.stats['failed_searches'] += 1
            return {"error": str(e), "platform": platform, "query": query}
    
    async def search_all_platforms(self, query: str, user_id: str, 
                                  platforms: Optional[List[str]] = None) -> Dict[str, Any]:
        """Search across all or specified platforms"""
        try:
            if platforms is None:
                platforms = list(self.integrations.keys())
            
            # Filter to available integrations
            available_platforms = [p for p in platforms if p in self.integrations]
            
            if not available_platforms:
                return {"error": "No available platforms to search"}
            
            logger.info(f"Searching platforms: {available_platforms} for query: '{query}'")
            
            # Run searches concurrently
            tasks = [
                self.search_platform(platform, query, user_id)
                for platform in available_platforms
            ]
            
            start_time = datetime.utcnow()
            platform_results = await asyncio.gather(*tasks, return_exceptions=True)
            total_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Combine results
            combined_results = {}
            total_results = 0
            
            for i, result in enumerate(platform_results):
                platform = available_platforms[i]
                
                if isinstance(result, Exception):
                    logger.error(f"Platform {platform} search failed: {result}")
                    combined_results[platform] = {"error": str(result)}
                elif 'error' in result:
                    combined_results[platform] = result
                else:
                    combined_results[platform] = result
                    # Count total results
                    if 'results' in result:
                        for service_results in result['results'].values():
                            if isinstance(service_results, list):
                                total_results += len(service_results)
            
            return {
                "query": query,
                "platforms_searched": available_platforms,
                "results": combined_results,
                "total_results": total_results,
                "search_time": total_time,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Multi-platform search failed: {e}")
            return {"error": str(e), "query": query}
    
    def get_available_integrations(self) -> List[Dict[str, Any]]:
        """Get list of available integrations"""
        return [
            {
                'name': name,
                'status': integration.get_integration_status(),
                'supported_services': integration.get_supported_services(),
                'is_healthy': integration.is_healthy(),
                'stats': integration.get_stats()
            }
            for name, integration in self.integrations.items()
        ]
    
    def get_user_connected_platforms(self, user_id: str) -> List[str]:
        """Get platforms user has connected to"""
        return list(self.user_tokens.get(user_id, {}).keys())
    
    async def test_all_integrations(self) -> Dict[str, Any]:
        """Test all integrations connectivity"""
        test_results = {}
        
        for name, integration in self.integrations.items():
            try:
                result = await integration.test_connection()
                test_results[name] = result
            except Exception as e:
                test_results[name] = {
                    'status': 'error',
                    'message': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                }
        
        return {
            'test_results': test_results,
            'healthy_integrations': sum(1 for r in test_results.values() if r.get('status') == 'connected'),
            'total_integrations': len(test_results),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_manager_stats(self) -> Dict[str, Any]:
        """Get integration manager statistics"""
        return {
            'integrations_loaded': len(self.integrations),
            'integrations_active': self.stats['integrations_active'],
            'total_searches': self.stats['total_searches'],
            'successful_searches': self.stats['successful_searches'],
            'failed_searches': self.stats['failed_searches'],
            'success_rate': (self.stats['successful_searches'] / self.stats['total_searches'] * 100) if self.stats['total_searches'] > 0 else 0,
            'connected_users': len(self.user_tokens),
            'available_platforms': list(self.integrations.keys())
        }
    
    def reload_integration(self, name: str) -> bool:
        """Reload specific integration"""
        try:
            if name in self.config.get('integrations', {}):
                config = self.config['integrations'][name]
                self._load_integration(name, config)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to reload integration {name}: {e}")
            return False
    
    def disable_integration(self, name: str) -> bool:
        """Disable specific integration"""
        try:
            if name in self.integrations:
                integration = self.integrations[name]
                integration.enabled = False
                logger.info(f"Disabled integration: {name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to disable integration {name}: {e}")
            return False
    
    def enable_integration(self, name: str) -> bool:
        """Enable specific integration"""
        try:
            if name in self.integrations:
                integration = self.integrations[name]
                integration.enabled = True
                logger.info(f"Enabled integration: {name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to enable integration {name}: {e}")
            return False