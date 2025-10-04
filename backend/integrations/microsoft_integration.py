"""
Microsoft 365 Integration
Comprehensive integration with Microsoft ecosystem
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

import aiohttp
from msal import ConfidentialClientApplication
from msgraph import GraphServiceClient
from azure.identity import ClientSecretCredential

from .base_integration import BaseIntegration
from ..utils.auth import OAuthHandler
from ..utils.cache import CacheManager

logger = logging.getLogger(__name__)

class MicrosoftIntegration(BaseIntegration):
    """
    Microsoft 365 Integration
    Supports: Teams, SharePoint, Outlook, OneDrive, Power BI, Azure AD
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client_id = config.get('client_id')
        self.client_secret = config.get('client_secret')
        self.tenant_id = config.get('tenant_id')
        self.redirect_uri = config.get('redirect_uri')
        
        # MSAL client for authentication
        self.msal_app = None
        self.graph_client = None
        
        # Supported services
        self.services = {
            'teams': True,
            'sharepoint': True,
            'outlook': True,
            'onedrive': True,
            'calendar': True,
            'contacts': True,
            'powerbi': True,
            'azure_ad': True
        }
        
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize Microsoft clients"""
        try:
            # MSAL confidential client
            self.msal_app = ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,
                authority=f"https://login.microsoftonline.com/{self.tenant_id}"
            )
            
            # Microsoft Graph client
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            
            self.graph_client = GraphServiceClient(
                credentials=credential,
                scopes=['https://graph.microsoft.com/.default']
            )
            
            logger.info("📊 Microsoft 365 integration initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize Microsoft clients: {e}")
    
    async def authenticate(self, user_id: str) -> Dict[str, Any]:
        """Authenticate user with Microsoft 365"""
        try:
            # Get authorization URL
            auth_url = self.msal_app.get_authorization_request_url(
                scopes=[
                    "https://graph.microsoft.com/User.Read",
                    "https://graph.microsoft.com/Mail.Read",
                    "https://graph.microsoft.com/Files.Read",
                    "https://graph.microsoft.com/Team.ReadBasic.All",
                    "https://graph.microsoft.com/Sites.Read.All",
                    "https://graph.microsoft.com/Calendars.Read"
                ],
                redirect_uri=self.redirect_uri,
                state=user_id
            )
            
            return {
                "auth_url": auth_url,
                "status": "redirect_required",
                "provider": "microsoft"
            }
            
        except Exception as e:
            logger.error(f"Microsoft authentication failed: {e}")
            return {"error": str(e), "status": "failed"}
    
    async def search_teams(self, query: str, user_token: str) -> List[Dict[str, Any]]:
        """Search Microsoft Teams messages and files"""
        try:
            headers = {
                'Authorization': f'Bearer {user_token}',
                'Content-Type': 'application/json'
            }
            
            # Search Teams messages
            search_payload = {
                "requests": [{
                    "entityTypes": ["message"],
                    "query": {
                        "queryString": query
                    },
                    "from": 0,
                    "size": 25
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://graph.microsoft.com/v1.0/search/query',
                    headers=headers,
                    json=search_payload
                ) as response:
                    data = await response.json()
                    
                    results = []
                    if 'value' in data:
                        for search_response in data['value']:
                            if 'hitsContainers' in search_response:
                                for container in search_response['hitsContainers']:
                                    for hit in container.get('hits', []):
                                        results.append({
                                            'id': hit.get('hitId'),
                                            'title': hit.get('summary', 'Teams Message'),
                                            'content': hit.get('summary'),
                                            'source': 'Microsoft Teams',
                                            'type': 'teams_message',
                                            'created_time': hit.get('lastModifiedTime'),
                                            'url': hit.get('webUrl')
                                        })
                    
                    return results
                    
        except Exception as e:
            logger.error(f"Teams search failed: {e}")
            return []
    
    async def search_sharepoint(self, query: str, user_token: str) -> List[Dict[str, Any]]:
        """Search SharePoint sites and documents"""
        try:
            headers = {
                'Authorization': f'Bearer {user_token}',
                'Content-Type': 'application/json'
            }
            
            # Search SharePoint
            search_payload = {
                "requests": [{
                    "entityTypes": ["site", "driveItem"],
                    "query": {
                        "queryString": query
                    },
                    "from": 0,
                    "size": 25
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://graph.microsoft.com/v1.0/search/query',
                    headers=headers,
                    json=search_payload
                ) as response:
                    data = await response.json()
                    
                    results = []
                    if 'value' in data:
                        for search_response in data['value']:
                            if 'hitsContainers' in search_response:
                                for container in search_response['hitsContainers']:
                                    for hit in container.get('hits', []):
                                        results.append({
                                            'id': hit.get('hitId'),
                                            'title': hit.get('summary', 'SharePoint Item'),
                                            'content': hit.get('summary'),
                                            'source': 'SharePoint',
                                            'type': 'sharepoint_document',
                                            'created_time': hit.get('createdDateTime'),
                                            'modified_time': hit.get('lastModifiedDateTime'),
                                            'url': hit.get('webUrl')
                                        })
                    
                    return results
                    
        except Exception as e:
            logger.error(f"SharePoint search failed: {e}")
            return []
    
    async def search_outlook(self, query: str, user_token: str) -> List[Dict[str, Any]]:
        """Search Outlook emails"""
        try:
            headers = {
                'Authorization': f'Bearer {user_token}',
                'Content-Type': 'application/json'
            }
            
            # Search Outlook emails
            search_url = f"https://graph.microsoft.com/v1.0/me/messages?$search=\"{query}\"&$top=25"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=headers) as response:
                    data = await response.json()
                    
                    results = []
                    if 'value' in data:
                        for email in data['value']:
                            results.append({
                                'id': email.get('id'),
                                'title': email.get('subject', 'No Subject'),
                                'content': email.get('bodyPreview', ''),
                                'source': 'Outlook',
                                'type': 'email',
                                'sender': email.get('from', {}).get('emailAddress', {}).get('address'),
                                'created_time': email.get('receivedDateTime'),
                                'importance': email.get('importance'),
                                'has_attachments': email.get('hasAttachments', False)
                            })
                    
                    return results
                    
        except Exception as e:
            logger.error(f"Outlook search failed: {e}")
            return []
    
    async def search_onedrive(self, query: str, user_token: str) -> List[Dict[str, Any]]:
        """Search OneDrive files"""
        try:
            headers = {
                'Authorization': f'Bearer {user_token}',
                'Content-Type': 'application/json'
            }
            
            # Search OneDrive
            search_url = f"https://graph.microsoft.com/v1.0/me/drive/root/search(q='{query}')?$top=25"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=headers) as response:
                    data = await response.json()
                    
                    results = []
                    if 'value' in data:
                        for file in data['value']:
                            results.append({
                                'id': file.get('id'),
                                'title': file.get('name'),
                                'content': file.get('name'),  # File name as content preview
                                'source': 'OneDrive',
                                'type': 'file',
                                'file_type': file.get('file', {}).get('mimeType'),
                                'size': file.get('size'),
                                'created_time': file.get('createdDateTime'),
                                'modified_time': file.get('lastModifiedDateTime'),
                                'url': file.get('webUrl'),
                                'download_url': file.get('@microsoft.graph.downloadUrl')
                            })
                    
                    return results
                    
        except Exception as e:
            logger.error(f"OneDrive search failed: {e}")
            return []
    
    async def get_calendar_events(self, user_token: str, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """Get upcoming calendar events"""
        try:
            headers = {
                'Authorization': f'Bearer {user_token}',
                'Content-Type': 'application/json'
            }
            
            # Get events for next N days
            start_time = datetime.utcnow().isoformat() + 'Z'
            end_time = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + 'Z'
            
            calendar_url = (
                f"https://graph.microsoft.com/v1.0/me/calendarview?"
                f"startDateTime={start_time}&endDateTime={end_time}&$top=50"
            )
            
            async with aiohttp.ClientSession() as session:
                async with session.get(calendar_url, headers=headers) as response:
                    data = await response.json()
                    
                    events = []
                    if 'value' in data:
                        for event in data['value']:
                            events.append({
                                'id': event.get('id'),
                                'title': event.get('subject'),
                                'content': event.get('body', {}).get('content', ''),
                                'source': 'Outlook Calendar',
                                'type': 'calendar_event',
                                'start_time': event.get('start', {}).get('dateTime'),
                                'end_time': event.get('end', {}).get('dateTime'),
                                'location': event.get('location', {}).get('displayName'),
                                'organizer': event.get('organizer', {}).get('emailAddress', {}).get('address'),
                                'attendees_count': len(event.get('attendees', [])),
                                'importance': event.get('importance'),
                                'url': event.get('webLink')
                            })
                    
                    return events
                    
        except Exception as e:
            logger.error(f"Calendar events retrieval failed: {e}")
            return []
    
    async def search_all(self, query: str, user_token: str) -> Dict[str, List[Dict[str, Any]]]:
        """Search across all Microsoft 365 services"""
        try:
            # Run searches concurrently
            tasks = [
                self.search_teams(query, user_token),
                self.search_sharepoint(query, user_token), 
                self.search_outlook(query, user_token),
                self.search_onedrive(query, user_token)
            ]
            
            teams_results, sharepoint_results, outlook_results, onedrive_results = await asyncio.gather(*tasks)
            
            return {
                'teams': teams_results,
                'sharepoint': sharepoint_results,
                'outlook': outlook_results,
                'onedrive': onedrive_results,
                'calendar': await self.get_calendar_events(user_token) if 'meeting' in query.lower() or 'calendar' in query.lower() else []
            }
            
        except Exception as e:
            logger.error(f"Microsoft 365 search failed: {e}")
            return {}
    
    def get_supported_services(self) -> List[str]:
        """Get list of supported Microsoft services"""
        return list(self.services.keys())
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get Microsoft integration status"""
        return {
            'provider': 'Microsoft 365',
            'status': 'active' if self.msal_app and self.graph_client else 'inactive',
            'services': self.services,
            'auth_method': 'OAuth2 + MSAL',
            'capabilities': [
                'Teams messaging search',
                'SharePoint document search', 
                'Outlook email search',
                'OneDrive file search',
                'Calendar events',
                'Azure AD integration',
                'Real-time notifications'
            ]
        }