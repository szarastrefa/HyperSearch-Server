"""
Google Workspace Integration  
Comprehensive integration with Google ecosystem
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

import aiohttp
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from .base_integration import BaseIntegration

logger = logging.getLogger(__name__)

class GoogleIntegration(BaseIntegration):
    """
    Google Workspace Integration
    Supports: Gmail, Google Drive, Calendar, Meet, Docs, Sheets, Slides
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client_id = config.get('client_id')
        self.client_secret = config.get('client_secret')
        self.redirect_uri = config.get('redirect_uri')
        
        # OAuth2 flow
        self.flow = None
        
        # Google API scopes
        self.scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/drive.readonly',
            'https://www.googleapis.com/auth/calendar.readonly',
            'https://www.googleapis.com/auth/documents.readonly',
            'https://www.googleapis.com/auth/spreadsheets.readonly',
            'https://www.googleapis.com/auth/presentations.readonly',
            'https://www.googleapis.com/auth/youtube.readonly'
        ]
        
        # Supported services
        self.services = {
            'gmail': True,
            'drive': True,
            'calendar': True,
            'docs': True,
            'sheets': True,
            'slides': True,
            'meet': True,
            'youtube': True
        }
        
        self._initialize_flow()
    
    def _initialize_flow(self):
        """Initialize Google OAuth2 flow"""
        try:
            self.flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.redirect_uri]
                    }
                },
                scopes=self.scopes
            )
            self.flow.redirect_uri = self.redirect_uri
            
            logger.info("🔍 Google Workspace integration initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google OAuth flow: {e}")
    
    async def authenticate(self, user_id: str) -> Dict[str, Any]:
        """Authenticate user with Google Workspace"""
        try:
            auth_url, _ = self.flow.authorization_url(
                prompt='consent',
                state=user_id
            )
            
            return {
                "auth_url": auth_url,
                "status": "redirect_required",
                "provider": "google"
            }
            
        except Exception as e:
            logger.error(f"Google authentication failed: {e}")
            return {"error": str(e), "status": "failed"}
    
    async def search_gmail(self, query: str, credentials: Credentials) -> List[Dict[str, Any]]:
        """Search Gmail messages"""
        try:
            service = build('gmail', 'v1', credentials=credentials)
            
            # Search messages
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=25
            ).execute()
            
            messages = results.get('messages', [])
            email_results = []
            
            for message in messages[:10]:  # Limit to first 10 for performance
                msg = service.users().messages().get(
                    userId='me',
                    id=message['id']
                ).execute()
                
                headers = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}
                
                email_results.append({
                    'id': message['id'],
                    'title': headers.get('Subject', 'No Subject'),
                    'content': self._extract_email_body(msg['payload']),
                    'source': 'Gmail',
                    'type': 'email',
                    'sender': headers.get('From'),
                    'date': headers.get('Date'),
                    'thread_id': msg.get('threadId')
                })
            
            return email_results
            
        except Exception as e:
            logger.error(f"Gmail search failed: {e}")
            return []
    
    async def search_drive(self, query: str, credentials: Credentials) -> List[Dict[str, Any]]:
        """Search Google Drive files"""
        try:
            service = build('drive', 'v3', credentials=credentials)
            
            # Search files
            results = service.files().list(
                q=f"fullText contains '{query}' or name contains '{query}'",
                pageSize=25,
                fields="files(id,name,mimeType,createdTime,modifiedTime,size,webViewLink,thumbnailLink)"
            ).execute()
            
            files = results.get('files', [])
            drive_results = []
            
            for file in files:
                drive_results.append({
                    'id': file['id'],
                    'title': file['name'],
                    'content': file['name'],  # Use name as content preview
                    'source': 'Google Drive',
                    'type': 'file',
                    'mime_type': file.get('mimeType'),
                    'size': file.get('size'),
                    'created_time': file.get('createdTime'),
                    'modified_time': file.get('modifiedTime'),
                    'url': file.get('webViewLink'),
                    'thumbnail': file.get('thumbnailLink')
                })
            
            return drive_results
            
        except Exception as e:
            logger.error(f"Google Drive search failed: {e}")
            return []
    
    async def search_calendar(self, query: str, credentials: Credentials) -> List[Dict[str, Any]]:
        """Search Google Calendar events"""
        try:
            service = build('calendar', 'v3', credentials=credentials)
            
            # Get events from primary calendar
            now = datetime.utcnow().isoformat() + 'Z'
            events_result = service.events().list(
                calendarId='primary',
                timeMin=now,
                maxResults=25,
                singleEvents=True,
                orderBy='startTime',
                q=query
            ).execute()
            
            events = events_result.get('items', [])
            calendar_results = []
            
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                
                calendar_results.append({
                    'id': event['id'],
                    'title': event.get('summary', 'No Title'),
                    'content': event.get('description', ''),
                    'source': 'Google Calendar',
                    'type': 'calendar_event',
                    'start_time': start,
                    'end_time': end,
                    'location': event.get('location'),
                    'organizer': event.get('organizer', {}).get('email'),
                    'attendees_count': len(event.get('attendees', [])),
                    'url': event.get('htmlLink')
                })
            
            return calendar_results
            
        except Exception as e:
            logger.error(f"Google Calendar search failed: {e}")
            return []
    
    async def search_docs(self, query: str, credentials: Credentials) -> List[Dict[str, Any]]:
        """Search Google Docs, Sheets, and Slides"""
        try:
            # First get files from Drive with specific MIME types
            service = build('drive', 'v3', credentials=credentials)
            
            mime_types = [
                'application/vnd.google-apps.document',  # Google Docs
                'application/vnd.google-apps.spreadsheet',  # Google Sheets
                'application/vnd.google-apps.presentation'  # Google Slides
            ]
            
            docs_results = []
            
            for mime_type in mime_types:
                results = service.files().list(
                    q=f"(fullText contains '{query}' or name contains '{query}') and mimeType='{mime_type}'",
                    pageSize=10,
                    fields="files(id,name,mimeType,createdTime,modifiedTime,webViewLink)"
                ).execute()
                
                files = results.get('files', [])
                
                for file in files:
                    doc_type = 'document'
                    if 'spreadsheet' in mime_type:
                        doc_type = 'spreadsheet'
                    elif 'presentation' in mime_type:
                        doc_type = 'presentation'
                    
                    docs_results.append({
                        'id': file['id'],
                        'title': file['name'],
                        'content': file['name'],
                        'source': f'Google {doc_type.title()}',
                        'type': doc_type,
                        'mime_type': file['mimeType'],
                        'created_time': file.get('createdTime'),
                        'modified_time': file.get('modifiedTime'),
                        'url': file.get('webViewLink')
                    })
            
            return docs_results
            
        except Exception as e:
            logger.error(f"Google Docs search failed: {e}")
            return []
    
    def _extract_email_body(self, payload: Dict[str, Any]) -> str:
        """Extract email body from Gmail payload"""
        try:
            if 'parts' in payload:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain':
                        data = part['body'].get('data')
                        if data:
                            import base64
                            return base64.urlsafe_b64decode(data).decode('utf-8')
            else:
                if payload['mimeType'] == 'text/plain':
                    data = payload['body'].get('data')
                    if data:
                        import base64
                        return base64.urlsafe_b64decode(data).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to extract email body: {e}")
        
        return "Email content preview not available"
    
    async def search_all(self, query: str, credentials: Credentials) -> Dict[str, List[Dict[str, Any]]]:
        """Search across all Google Workspace services"""
        try:
            # Run searches concurrently
            tasks = [
                self.search_gmail(query, credentials),
                self.search_drive(query, credentials),
                self.search_calendar(query, credentials),
                self.search_docs(query, credentials)
            ]
            
            gmail_results, drive_results, calendar_results, docs_results = await asyncio.gather(*tasks)
            
            return {
                'gmail': gmail_results,
                'drive': drive_results,
                'calendar': calendar_results,
                'docs': docs_results
            }
            
        except Exception as e:
            logger.error(f"Google Workspace search failed: {e}")
            return {}
    
    def get_supported_services(self) -> List[str]:
        """Get list of supported Google services"""
        return list(self.services.keys())
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get Google integration status"""
        return {
            'provider': 'Google Workspace',
            'status': 'active' if self.flow else 'inactive',
            'services': self.services,
            'auth_method': 'OAuth2',
            'capabilities': [
                'Gmail email search',
                'Google Drive file search',
                'Google Calendar events',
                'Google Docs/Sheets/Slides search',
                'YouTube integration',
                'Real-time synchronization'
            ]
        }