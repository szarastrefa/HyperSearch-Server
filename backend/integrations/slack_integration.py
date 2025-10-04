"""
Slack Workspace Integration
Integration with Slack channels, messages, and files
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

import aiohttp
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from .base_integration import BaseIntegration

logger = logging.getLogger(__name__)

class SlackIntegration(BaseIntegration):
    """
    Slack Workspace Integration
    Supports: Channels, Messages, Files, Users, Apps
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.bot_token = config.get('bot_token')
        self.signing_secret = config.get('signing_secret')
        
        # Slack client
        self.slack_client = None
        
        # Supported services
        self.services = {
            'channels': True,
            'messages': True,
            'files': True,
            'users': True,
            'apps': True
        }
        
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Slack client"""
        try:
            if self.bot_token:
                self.slack_client = WebClient(token=self.bot_token)
                
                # Test connection
                response = self.slack_client.auth_test()
                if response['ok']:
                    logger.info(f"💬 Slack integration initialized for team: {response.get('team')}")
                else:
                    logger.error("Slack authentication failed")
            else:
                logger.warning("Slack bot token not provided")
                
        except Exception as e:
            logger.error(f"Failed to initialize Slack client: {e}")
    
    async def authenticate(self, user_id: str) -> Dict[str, Any]:
        """Authenticate user with Slack"""
        try:
            # Slack OAuth URL
            scope = [
                'channels:history',
                'channels:read',
                'files:read',
                'groups:history',
                'groups:read',
                'im:history',
                'im:read',
                'mpim:history',
                'mpim:read',
                'search:read',
                'users:read'
            ]
            
            auth_url = (
                f"https://slack.com/oauth/v2/authorize?"
                f"client_id={self.client_id}&"
                f"scope={','.join(scope)}&"
                f"state={user_id}&"
                f"redirect_uri={self.redirect_uri}"
            )
            
            return {
                "auth_url": auth_url,
                "status": "redirect_required",
                "provider": "slack"
            }
            
        except Exception as e:
            logger.error(f"Slack authentication failed: {e}")
            return {"error": str(e), "status": "failed"}
    
    async def search_messages(self, query: str, user_token: str = None) -> List[Dict[str, Any]]:
        """Search Slack messages"""
        try:
            client = WebClient(token=user_token) if user_token else self.slack_client
            if not client:
                return []
            
            # Search messages
            response = client.search_messages(
                query=query,
                count=25,
                sort='timestamp',
                sort_dir='desc'
            )
            
            results = []
            if response['ok'] and 'messages' in response:
                for match in response['messages']['matches']:
                    message = match
                    channel_info = message.get('channel', {})
                    
                    results.append({
                        'id': message.get('ts'),
                        'title': f"Message from {message.get('username', 'Unknown')}",
                        'content': message.get('text', ''),
                        'source': 'Slack',
                        'type': 'message',
                        'channel_name': channel_info.get('name'),
                        'channel_id': channel_info.get('id'),
                        'user': message.get('username'),
                        'timestamp': message.get('ts'),
                        'permalink': message.get('permalink')
                    })
            
            return results
            
        except SlackApiError as e:
            logger.error(f"Slack message search failed: {e.response['error']}")
            return []
        except Exception as e:
            logger.error(f"Slack message search failed: {e}")
            return []
    
    async def search_files(self, query: str, user_token: str = None) -> List[Dict[str, Any]]:
        """Search Slack files"""
        try:
            client = WebClient(token=user_token) if user_token else self.slack_client
            if not client:
                return []
            
            # Search files
            response = client.search_files(
                query=query,
                count=25,
                sort='timestamp',
                sort_dir='desc'
            )
            
            results = []
            if response['ok'] and 'files' in response:
                for match in response['files']['matches']:
                    file_info = match
                    
                    results.append({
                        'id': file_info.get('id'),
                        'title': file_info.get('name', 'Untitled File'),
                        'content': file_info.get('title', ''),
                        'source': 'Slack Files',
                        'type': 'file',
                        'file_type': file_info.get('filetype'),
                        'size': file_info.get('size'),
                        'user': file_info.get('user'),
                        'created_time': file_info.get('created'),
                        'url': file_info.get('url_private'),
                        'permalink': file_info.get('permalink')
                    })
            
            return results
            
        except SlackApiError as e:
            logger.error(f"Slack file search failed: {e.response['error']}")
            return []
        except Exception as e:
            logger.error(f"Slack file search failed: {e}")
            return []
    
    async def get_channels(self, user_token: str = None) -> List[Dict[str, Any]]:
        """Get Slack channels"""
        try:
            client = WebClient(token=user_token) if user_token else self.slack_client
            if not client:
                return []
            
            # Get channels
            response = client.conversations_list(
                types="public_channel,private_channel",
                limit=100
            )
            
            results = []
            if response['ok']:
                for channel in response['channels']:
                    results.append({
                        'id': channel['id'],
                        'title': f"#{channel['name']}",
                        'content': channel.get('topic', {}).get('value', ''),
                        'source': 'Slack Channels',
                        'type': 'channel',
                        'name': channel['name'],
                        'is_private': channel.get('is_private', False),
                        'member_count': channel.get('num_members', 0),
                        'created_time': channel.get('created')
                    })
            
            return results
            
        except SlackApiError as e:
            logger.error(f"Slack channels retrieval failed: {e.response['error']}")
            return []
        except Exception as e:
            logger.error(f"Slack channels retrieval failed: {e}")
            return []
    
    async def search_all(self, query: str, user_token: str = None) -> Dict[str, List[Dict[str, Any]]]:
        """Search across all Slack services"""
        try:
            # Run searches concurrently
            tasks = [
                self.search_messages(query, user_token),
                self.search_files(query, user_token)
            ]
            
            messages_results, files_results = await asyncio.gather(*tasks)
            
            # Also get channels if query might be channel-related
            channels_results = []
            if any(keyword in query.lower() for keyword in ['channel', 'room', 'group']):
                channels_results = await self.get_channels(user_token)
                channels_results = [c for c in channels_results if query.lower() in c['title'].lower() or query.lower() in c['content'].lower()]
            
            return {
                'messages': messages_results,
                'files': files_results,
                'channels': channels_results
            }
            
        except Exception as e:
            logger.error(f"Slack search failed: {e}")
            return {}
    
    async def send_message(self, channel: str, message: str, user_token: str = None) -> Dict[str, Any]:
        """Send message to Slack channel"""
        try:
            client = WebClient(token=user_token) if user_token else self.slack_client
            if not client:
                return {"error": "Slack client not available"}
            
            response = client.chat_postMessage(
                channel=channel,
                text=message
            )
            
            if response['ok']:
                return {
                    "success": True,
                    "message_ts": response['ts'],
                    "channel": response['channel']
                }
            else:
                return {"error": response.get('error', 'Unknown error')}
                
        except SlackApiError as e:
            logger.error(f"Slack message sending failed: {e.response['error']}")
            return {"error": e.response['error']}
        except Exception as e:
            logger.error(f"Slack message sending failed: {e}")
            return {"error": str(e)}
    
    def get_supported_services(self) -> List[str]:
        """Get list of supported Slack services"""
        return list(self.services.keys())
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get Slack integration status"""
        return {
            'provider': 'Slack Workspace',
            'status': 'active' if self.slack_client else 'inactive',
            'services': self.services,
            'auth_method': 'OAuth2 + Bot Token',
            'capabilities': [
                'Message search across channels',
                'File search and access',
                'Channel management',
                'Direct messaging',
                'Bot integration',
                'Webhook support',
                'Real-time messaging'
            ]
        }