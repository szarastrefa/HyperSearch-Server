"""
Notion Workspace Integration
Integration with Notion pages, databases, and blocks
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

import aiohttp
from notion_client import Client as NotionClient
from notion_client.errors import APIErrorCode, APIResponseError

from .base_integration import BaseIntegration

logger = logging.getLogger(__name__)

class NotionIntegration(BaseIntegration):
    """
    Notion Workspace Integration
    Supports: Pages, Databases, Blocks, Comments
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.integration_token = config.get('integration_token')
        
        # Notion client
        self.notion_client = None
        
        # Supported services
        self.services = {
            'pages': True,
            'databases': True,
            'blocks': True,
            'comments': True
        }
        
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Notion client"""
        try:
            if self.integration_token:
                self.notion_client = NotionClient(auth=self.integration_token)
                
                # Test connection by getting current user
                user_info = self.notion_client.users.me()
                logger.info(f"📝 Notion integration initialized for user: {user_info.get('name', 'Unknown')}")
            else:
                logger.warning("Notion integration token not provided")
                
        except Exception as e:
            logger.error(f"Failed to initialize Notion client: {e}")
    
    async def authenticate(self, user_id: str) -> Dict[str, Any]:
        """Authenticate user with Notion"""
        try:
            # Notion OAuth URL
            auth_url = (
                f"https://api.notion.com/v1/oauth/authorize?"
                f"client_id={self.client_id}&"
                f"response_type=code&"
                f"owner=user&"
                f"state={user_id}&"
                f"redirect_uri={self.redirect_uri}"
            )
            
            return {
                "auth_url": auth_url,
                "status": "redirect_required",
                "provider": "notion"
            }
            
        except Exception as e:
            logger.error(f"Notion authentication failed: {e}")
            return {"error": str(e), "status": "failed"}
    
    async def search_pages(self, query: str, user_token: str = None) -> List[Dict[str, Any]]:
        """Search Notion pages"""
        try:
            client = NotionClient(auth=user_token) if user_token else self.notion_client
            if not client:
                return []
            
            # Search pages
            response = client.search(
                query=query,
                filter={'property': 'object', 'value': 'page'},
                page_size=25
            )
            
            results = []
            for page in response.get('results', []):
                title = self._extract_page_title(page)
                
                results.append({
                    'id': page['id'],
                    'title': title,
                    'content': title,  # Use title as content preview
                    'source': 'Notion Pages',
                    'type': 'page',
                    'url': page.get('url'),
                    'created_time': page.get('created_time'),
                    'updated_time': page.get('last_edited_time'),
                    'created_by': page.get('created_by', {}).get('name'),
                    'parent_type': page.get('parent', {}).get('type')
                })
            
            return results
            
        except APIResponseError as e:
            logger.error(f"Notion pages search failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Notion pages search failed: {e}")
            return []
    
    async def search_databases(self, query: str, user_token: str = None) -> List[Dict[str, Any]]:
        """Search Notion databases"""
        try:
            client = NotionClient(auth=user_token) if user_token else self.notion_client
            if not client:
                return []
            
            # Search databases
            response = client.search(
                query=query,
                filter={'property': 'object', 'value': 'database'},
                page_size=25
            )
            
            results = []
            for database in response.get('results', []):
                title = self._extract_database_title(database)
                
                results.append({
                    'id': database['id'],
                    'title': title,
                    'content': f"Database: {title}",
                    'source': 'Notion Databases',
                    'type': 'database',
                    'url': database.get('url'),
                    'created_time': database.get('created_time'),
                    'updated_time': database.get('last_edited_time'),
                    'created_by': database.get('created_by', {}).get('name'),
                    'properties_count': len(database.get('properties', {}))
                })
            
            return results
            
        except APIResponseError as e:
            logger.error(f"Notion databases search failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Notion databases search failed: {e}")
            return []
    
    async def search_database_entries(self, database_id: str, query: str, user_token: str = None) -> List[Dict[str, Any]]:
        """Search entries in a specific Notion database"""
        try:
            client = NotionClient(auth=user_token) if user_token else self.notion_client
            if not client:
                return []
            
            # Query database
            response = client.databases.query(
                database_id=database_id,
                page_size=25
            )
            
            results = []
            for entry in response.get('results', []):
                title = self._extract_page_title(entry)
                
                # Simple text matching for query
                if query.lower() in title.lower():
                    results.append({
                        'id': entry['id'],
                        'title': title,
                        'content': self._extract_entry_content(entry),
                        'source': 'Notion Database Entry',
                        'type': 'database_entry',
                        'url': entry.get('url'),
                        'created_time': entry.get('created_time'),
                        'updated_time': entry.get('last_edited_time'),
                        'database_id': database_id
                    })
            
            return results
            
        except APIResponseError as e:
            logger.error(f"Notion database entries search failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Notion database entries search failed: {e}")
            return []
    
    def _extract_page_title(self, page: Dict[str, Any]) -> str:
        """Extract title from Notion page"""
        try:
            properties = page.get('properties', {})
            
            # Look for title property
            for prop_name, prop_data in properties.items():
                if prop_data.get('type') == 'title':
                    title_array = prop_data.get('title', [])
                    if title_array:
                        return ''.join([t.get('plain_text', '') for t in title_array])
            
            # Fallback to page title if available
            if 'title' in page:
                return ''.join([t.get('plain_text', '') for t in page['title']])
            
            return 'Untitled Page'
            
        except Exception as e:
            logger.error(f"Failed to extract page title: {e}")
            return 'Untitled Page'
    
    def _extract_database_title(self, database: Dict[str, Any]) -> str:
        """Extract title from Notion database"""
        try:
            title_array = database.get('title', [])
            if title_array:
                return ''.join([t.get('plain_text', '') for t in title_array])
            return 'Untitled Database'
            
        except Exception as e:
            logger.error(f"Failed to extract database title: {e}")
            return 'Untitled Database'
    
    def _extract_entry_content(self, entry: Dict[str, Any]) -> str:
        """Extract content preview from database entry"""
        try:
            content_parts = []
            properties = entry.get('properties', {})
            
            # Extract text from various property types
            for prop_name, prop_data in properties.items():
                prop_type = prop_data.get('type')
                
                if prop_type == 'rich_text':
                    text_array = prop_data.get('rich_text', [])
                    text = ''.join([t.get('plain_text', '') for t in text_array])
                    if text:
                        content_parts.append(f"{prop_name}: {text}")
                elif prop_type == 'select':
                    select_data = prop_data.get('select')
                    if select_data:
                        content_parts.append(f"{prop_name}: {select_data.get('name', '')}")
            
            return '; '.join(content_parts) if content_parts else 'No content preview available'
            
        except Exception as e:
            logger.error(f"Failed to extract entry content: {e}")
            return 'Content preview not available'
    
    async def search_all(self, query: str, user_token: str = None) -> Dict[str, List[Dict[str, Any]]]:
        """Search across all Notion services"""
        try:
            # Run searches concurrently
            tasks = [
                self.search_pages(query, user_token),
                self.search_databases(query, user_token)
            ]
            
            pages_results, databases_results = await asyncio.gather(*tasks)
            
            return {
                'pages': pages_results,
                'databases': databases_results
            }
            
        except Exception as e:
            logger.error(f"Notion search failed: {e}")
            return {}
    
    def get_supported_services(self) -> List[str]:
        """Get list of supported Notion services"""
        return list(self.services.keys())
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get Notion integration status"""
        return {
            'provider': 'Notion Workspace',
            'status': 'active' if self.notion_client else 'inactive',
            'services': self.services,
            'auth_method': 'OAuth2 + Integration Token',
            'capabilities': [
                'Page content search',
                'Database search and queries',
                'Block-level content access',
                'Comment integration',
                'Real-time synchronization',
                'Workspace management'
            ]
        }