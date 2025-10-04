"""
Meta Platforms Integration
Integration with Facebook, Instagram, Threads, WhatsApp Business
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

import aiohttp
import requests
from facebook import GraphAPI

from .base_integration import BaseIntegration

logger = logging.getLogger(__name__)

class MetaIntegration(BaseIntegration):
    """
    Meta Platforms Integration
    Supports: Facebook Pages/Groups, Instagram Business, Threads, WhatsApp Business
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.app_id = config.get('app_id')
        self.app_secret = config.get('app_secret')
        self.redirect_uri = config.get('redirect_uri')
        
        # Meta API versions
        self.facebook_api_version = config.get('facebook_api_version', 'v18.0')
        self.instagram_api_version = config.get('instagram_api_version', 'v18.0')
        
        # WhatsApp Business API
        self.whatsapp_phone_id = config.get('whatsapp_phone_id')
        self.whatsapp_token = config.get('whatsapp_token')
        
        # Supported services
        self.services = {
            'facebook_pages': True,
            'facebook_groups': True,
            'instagram_business': True,
            'threads': True,
            'whatsapp_business': bool(self.whatsapp_phone_id),
            'messenger': True
        }
        
        logger.info("📱 Meta Platforms integration initialized")
    
    async def authenticate(self, user_id: str) -> Dict[str, Any]:
        """Authenticate user with Meta platforms"""
        try:
            # Facebook OAuth URL
            scope = [
                'pages_read_engagement',
                'pages_read_user_content', 
                'instagram_basic',
                'instagram_content_publish',
                'groups_access_member_info',
                'user_posts'
            ]
            
            auth_url = (
                f"https://www.facebook.com/{self.facebook_api_version}/dialog/oauth?"
                f"client_id={self.app_id}&"
                f"redirect_uri={self.redirect_uri}&"
                f"scope={','.join(scope)}&"
                f"state={user_id}&"
                f"response_type=code"
            )
            
            return {
                "auth_url": auth_url,
                "status": "redirect_required",
                "provider": "meta"
            }
            
        except Exception as e:
            logger.error(f"Meta authentication failed: {e}")
            return {"error": str(e), "status": "failed"}
    
    async def search_facebook_pages(self, query: str, access_token: str) -> List[Dict[str, Any]]:
        """Search Facebook Pages content"""
        try:
            graph = GraphAPI(access_token, version=self.facebook_api_version)
            
            # Get user's pages
            pages = graph.get_object('me/accounts')
            results = []
            
            for page in pages.get('data', []):
                page_id = page['id']
                page_token = page['access_token']
                
                # Search posts on this page
                try:
                    page_graph = GraphAPI(page_token, version=self.facebook_api_version)
                    posts = page_graph.get_object(f'{page_id}/posts', fields='id,message,created_time,permalink_url')
                    
                    for post in posts.get('data', []):
                        message = post.get('message', '')
                        if query.lower() in message.lower():
                            results.append({
                                'id': post['id'],
                                'title': f"Facebook Post from {page['name']}",
                                'content': message,
                                'source': 'Facebook Page',
                                'type': 'social_post',
                                'page_name': page['name'],
                                'created_time': post.get('created_time'),
                                'url': post.get('permalink_url')
                            })
                            
                except Exception as page_error:
                    logger.warning(f"Failed to search page {page['name']}: {page_error}")
                    continue
            
            return results[:25]  # Limit results
            
        except Exception as e:
            logger.error(f"Facebook Pages search failed: {e}")
            return []
    
    async def search_instagram_business(self, query: str, access_token: str) -> List[Dict[str, Any]]:
        """Search Instagram Business account content"""
        try:
            graph = GraphAPI(access_token, version=self.instagram_api_version)
            
            # Get Instagram Business Account
            pages = graph.get_object('me/accounts')
            results = []
            
            for page in pages.get('data', []):
                try:
                    # Get Instagram account connected to page
                    instagram_account = graph.get_object(f"{page['id']}?fields=instagram_business_account")
                    
                    if 'instagram_business_account' in instagram_account:
                        ig_account_id = instagram_account['instagram_business_account']['id']
                        
                        # Get Instagram media
                        media_data = graph.get_object(
                            f'{ig_account_id}/media',
                            fields='id,caption,media_type,created_time,permalink,thumbnail_url'
                        )
                        
                        for media in media_data.get('data', []):
                            caption = media.get('caption', '')
                            if query.lower() in caption.lower():
                                results.append({
                                    'id': media['id'],
                                    'title': f"Instagram {media.get('media_type', 'Post')}",
                                    'content': caption,
                                    'source': 'Instagram Business',
                                    'type': 'social_media',
                                    'media_type': media.get('media_type'),
                                    'created_time': media.get('created_time'),
                                    'url': media.get('permalink'),
                                    'thumbnail': media.get('thumbnail_url')
                                })
                                
                except Exception as ig_error:
                    logger.warning(f"Failed to search Instagram for page {page['name']}: {ig_error}")
                    continue
            
            return results[:25]
            
        except Exception as e:
            logger.error(f"Instagram Business search failed: {e}")
            return []
    
    async def search_whatsapp_business(self, query: str) -> List[Dict[str, Any]]:
        """Search WhatsApp Business messages (limited by API)"""
        try:
            if not self.whatsapp_phone_id or not self.whatsapp_token:
                logger.warning("WhatsApp Business credentials not configured")
                return []
            
            # WhatsApp Business API has limited search capabilities
            # This is a placeholder for available message templates and business info
            
            headers = {
                'Authorization': f'Bearer {self.whatsapp_token}',
                'Content-Type': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                # Get message templates that contain the query
                templates_url = f"https://graph.facebook.com/{self.facebook_api_version}/{self.whatsapp_phone_id}/message_templates"
                
                async with session.get(templates_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = []
                        
                        for template in data.get('data', []):
                            if query.lower() in template.get('name', '').lower():
                                results.append({
                                    'id': template.get('id'),
                                    'title': f"WhatsApp Template: {template.get('name')}",
                                    'content': template.get('name'),
                                    'source': 'WhatsApp Business',
                                    'type': 'message_template',
                                    'status': template.get('status'),
                                    'language': template.get('language')
                                })
                        
                        return results
            
            return []
            
        except Exception as e:
            logger.error(f"WhatsApp Business search failed: {e}")
            return []
    
    async def search_threads(self, query: str, access_token: str) -> List[Dict[str, Any]]:
        """Search Threads content (via Threads API when available)"""
        try:
            # Threads API is still limited - this is a placeholder implementation
            # Currently, Threads content might be accessible through Instagram Business API
            
            logger.info(f"Threads search requested for: {query}")
            
            # Placeholder implementation
            return [{
                'id': 'threads_placeholder',
                'title': 'Threads Integration Coming Soon',
                'content': 'Threads API integration will be available when Meta releases full API access.',
                'source': 'Threads',
                'type': 'info',
                'created_time': datetime.utcnow().isoformat()
            }]
            
        except Exception as e:
            logger.error(f"Threads search failed: {e}")
            return []
    
    async def search_all(self, query: str, access_token: str) -> Dict[str, List[Dict[str, Any]]]:
        """Search across all Meta platforms"""
        try:
            # Run searches concurrently
            tasks = [
                self.search_facebook_pages(query, access_token),
                self.search_instagram_business(query, access_token),
                self.search_whatsapp_business(query),
                self.search_threads(query, access_token)
            ]
            
            facebook_results, instagram_results, whatsapp_results, threads_results = await asyncio.gather(*tasks)
            
            return {
                'facebook': facebook_results,
                'instagram': instagram_results, 
                'whatsapp': whatsapp_results,
                'threads': threads_results
            }
            
        except Exception as e:
            logger.error(f"Meta platforms search failed: {e}")
            return {}
    
    async def send_whatsapp_message(self, to_number: str, message: str) -> Dict[str, Any]:
        """Send WhatsApp Business message"""
        try:
            if not self.whatsapp_phone_id or not self.whatsapp_token:
                return {"error": "WhatsApp credentials not configured"}
            
            headers = {
                'Authorization': f'Bearer {self.whatsapp_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'messaging_product': 'whatsapp',
                'to': to_number,
                'type': 'text',
                'text': {'body': message}
            }
            
            async with aiohttp.ClientSession() as session:
                url = f"https://graph.facebook.com/{self.facebook_api_version}/{self.whatsapp_phone_id}/messages"
                
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {"success": True, "message_id": data.get('messages', [{}])[0].get('id')}
                    else:
                        error_data = await response.json()
                        return {"error": error_data}
                        
        except Exception as e:
            logger.error(f"WhatsApp message sending failed: {e}")
            return {"error": str(e)}
    
    def get_supported_services(self) -> List[str]:
        """Get list of supported Meta services"""
        return list(self.services.keys())
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get Meta integration status"""
        return {
            'provider': 'Meta Platforms',
            'status': 'active',
            'services': self.services,
            'auth_method': 'OAuth2',
            'capabilities': [
                'Facebook Pages content search',
                'Instagram Business content search',
                'WhatsApp Business messaging',
                'Threads integration (coming soon)',
                'Social media analytics',
                'Cross-platform messaging'
            ]
        }