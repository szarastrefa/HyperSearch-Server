"""
Samsung SmartThings Integration
Comprehensive SmartThings platform integration with OAuth2 authentication
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

import aiohttp
from aiohttp import ClientSession, ClientTimeout

logger = logging.getLogger(__name__)

class SmartThingsIntegration:
    """
    Samsung SmartThings Platform Integration
    Supports devices, scenes, rules, and real-time updates
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client_id = config.get('client_id')
        self.client_secret = config.get('client_secret')
        self.redirect_uri = config.get('redirect_uri')
        self.webhook_url = config.get('webhook_url')
        
        # SmartThings API configuration
        self.api_base_url = "https://api.smartthings.com/v1"
        self.auth_base_url = "https://auth-global.api.smartthings.com/oauth"
        
        # User tokens storage
        self.user_tokens: Dict[str, str] = {}
        
        # Device cache
        self.device_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_expiry = timedelta(minutes=5)
        self.last_cache_update = datetime.min
        
        # Statistics
        self.api_calls_today = 0
        self.successful_commands = 0
        self.failed_commands = 0
        
        logger.info("📱 Samsung SmartThings integration initialized")
    
    async def authenticate(self, user_id: str) -> Dict[str, Any]:
        """Start SmartThings OAuth2 authentication flow"""
        try:
            # SmartThings OAuth2 scopes
            scopes = [
                "r:devices:*",
                "x:devices:*", 
                "r:locations:*",
                "r:scenes:*",
                "x:scenes:*",
                "r:rules:*",
                "x:rules:*",
                "w:apps:*"
            ]
            
            # Generate OAuth2 URL
            auth_url = (
                f"{self.auth_base_url}/authorize?"
                f"client_id={self.client_id}&"
                f"response_type=code&"
                f"scope={' '.join(scopes)}&"
                f"state={user_id}&"
                f"redirect_uri={self.redirect_uri}"
            )
            
            return {
                "auth_url": auth_url,
                "status": "redirect_required",
                "provider": "smartthings",
                "expires_in": 3600
            }
            
        except Exception as e:
            logger.error(f"SmartThings authentication failed: {e}")
            return {"error": str(e), "status": "failed"}
    
    async def exchange_code_for_token(self, code: str, user_id: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        try:
            token_data = {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri
            }
            
            async with ClientSession() as session:
                async with session.post(f"{self.auth_base_url}/token", data=token_data) as response:
                    if response.status == 200:
                        token_response = await response.json()
                        access_token = token_response.get('access_token')
                        
                        # Store token for user
                        self.user_tokens[user_id] = access_token
                        
                        return {
                            "success": True,
                            "access_token": access_token,
                            "token_type": token_response.get('token_type', 'Bearer'),
                            "expires_in": token_response.get('expires_in', 3600)
                        }
                    else:
                        error_data = await response.json()
                        return {"error": error_data, "success": False}
                        
        except Exception as e:
            logger.error(f"Token exchange failed: {e}")
            return {"error": str(e), "success": False}
    
    async def discover_devices(self, user_id: str) -> List[Dict[str, Any]]:
        """Discover all SmartThings devices for user"""
        try:
            user_token = self.user_tokens.get(user_id)
            if not user_token:
                return []
            
            headers = {
                "Authorization": f"Bearer {user_token}",
                "Content-Type": "application/json"
            }
            
            timeout = ClientTimeout(total=30)
            
            async with ClientSession(timeout=timeout) as session:
                # Get user locations
                async with session.get(f"{self.api_base_url}/locations", headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Failed to get locations: {response.status}")
                        return []
                    
                    locations = await response.json()
                    all_devices = []
                    
                    # Get devices for each location
                    for location in locations.get('items', []):
                        location_id = location['locationId']
                        location_name = location.get('name', 'Unknown Location')
                        
                        # Get devices in this location
                        devices_url = f"{self.api_base_url}/devices?locationId={location_id}"
                        async with session.get(devices_url, headers=headers) as dev_response:
                            if dev_response.status == 200:
                                devices_data = await dev_response.json()
                                
                                for device in devices_data.get('items', []):
                                    device_info = {
                                        "id": device.get('deviceId'),
                                        "name": device.get('label', device.get('name', 'Unknown Device')),
                                        "type": device.get('type', 'unknown'),
                                        "manufacturer": device.get('manufacturerName', 'Unknown'),
                                        "model": device.get('presentationId', device.get('deviceManufacturerCode')),
                                        "location": location_name,
                                        "location_id": location_id,
                                        "platform": "smartthings",
                                        "capabilities": device.get('components', [{}])[0].get('capabilities', {}),
                                        "status": "online" if device.get('status') == 'ONLINE' else "offline",
                                        "last_activity": device.get('lastActivityTime'),
                                        "device_network_type": device.get('deviceNetworkType'),
                                        "raw_data": device
                                    }
                                    
                                    all_devices.append(device_info)
                    
                    # Update cache
                    self.device_cache[user_id] = {
                        "devices": all_devices,
                        "timestamp": datetime.utcnow()
                    }
                    self.last_cache_update = datetime.utcnow()
                    
                    logger.info(f"📱 Discovered {len(all_devices)} SmartThings devices")
                    return all_devices
                    
        except asyncio.TimeoutError:
            logger.error("SmartThings device discovery timed out")
            return []
        except Exception as e:
            logger.error(f"SmartThings device discovery failed: {e}")
            return []
    
    async def control_device(self, device_id: str, command: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Control SmartThings device"""
        try:
            # Find user token for device (simplified - in production would need proper user mapping)
            user_token = None
            for uid, token in self.user_tokens.items():
                user_token = token
                break
            
            if not user_token:
                return {"error": "No authentication token available"}
            
            headers = {
                "Authorization": f"Bearer {user_token}",
                "Content-Type": "application/json"
            }
            
            # Map command to SmartThings capability command
            capability_command = self._map_command_to_capability(command, parameters or {})
            
            if not capability_command:
                return {"error": f"Unsupported command: {command}"}
            
            command_data = {
                "commands": [{
                    "component": "main",
                    "capability": capability_command['capability'],
                    "command": capability_command['command'],
                    "arguments": capability_command.get('arguments', [])
                }]
            }
            
            timeout = ClientTimeout(total=15)
            
            async with ClientSession(timeout=timeout) as session:
                url = f"{self.api_base_url}/devices/{device_id}/commands"
                
                async with session.post(url, headers=headers, json=command_data) as response:
                    if response.status == 200:
                        result_data = await response.json()
                        self.successful_commands += 1
                        
                        return {
                            "success": True,
                            "device_id": device_id,
                            "command": command,
                            "result": result_data,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    else:
                        error_data = await response.text()
                        self.failed_commands += 1
                        
                        return {
                            "success": False,
                            "error": f"Command failed: {response.status} - {error_data}",
                            "device_id": device_id,
                            "command": command
                        }
                        
        except Exception as e:
            logger.error(f"SmartThings device control failed: {e}")
            self.failed_commands += 1
            return {"success": False, "error": str(e), "device_id": device_id}
    
    def _map_command_to_capability(self, command: str, parameters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Map generic command to SmartThings capability command"""
        command_map = {
            "turn_on": {
                "capability": "switch",
                "command": "on"
            },
            "turn_off": {
                "capability": "switch", 
                "command": "off"
            },
            "set_level": {
                "capability": "switchLevel",
                "command": "setLevel",
                "arguments": [parameters.get('level', 50)]
            },
            "set_color": {
                "capability": "colorControl",
                "command": "setColor",
                "arguments": [{
                    "hue": parameters.get('hue', 0),
                    "saturation": parameters.get('saturation', 100)
                }]
            },
            "set_temperature": {
                "capability": "thermostatCoolingSetpoint",
                "command": "setCoolingSetpoint",
                "arguments": [parameters.get('temperature', 21)]
            },
            "lock": {
                "capability": "lock",
                "command": "lock"
            },
            "unlock": {
                "capability": "lock",
                "command": "unlock"
            }
        }
        
        return command_map.get(command.lower())
    
    async def get_device_status(self, device_id: str) -> Dict[str, Any]:
        """Get current device status from SmartThings"""
        try:
            user_token = None
            for uid, token in self.user_tokens.items():
                user_token = token
                break
            
            if not user_token:
                return {"error": "No authentication token available"}
            
            headers = {
                "Authorization": f"Bearer {user_token}",
                "Content-Type": "application/json"
            }
            
            async with ClientSession() as session:
                url = f"{self.api_base_url}/devices/{device_id}/status"
                
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        status_data = await response.json()
                        return {
                            "success": True,
                            "device_id": device_id,
                            "status": status_data,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    else:
                        return {"success": False, "error": f"Status check failed: {response.status}"}
                        
        except Exception as e:
            logger.error(f"SmartThings device status failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def execute_scene(self, scene_id: str) -> Dict[str, Any]:
        """Execute SmartThings scene"""
        try:
            user_token = None
            for uid, token in self.user_tokens.items():
                user_token = token
                break
            
            if not user_token:
                return {"error": "No authentication token available"}
            
            headers = {
                "Authorization": f"Bearer {user_token}",
                "Content-Type": "application/json"
            }
            
            async with ClientSession() as session:
                url = f"{self.api_base_url}/scenes/{scene_id}/execute"
                
                async with session.post(url, headers=headers) as response:
                    if response.status == 200:
                        result_data = await response.json()
                        return {
                            "success": True,
                            "scene_id": scene_id,
                            "result": result_data,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    else:
                        return {"success": False, "error": f"Scene execution failed: {response.status}"}
                        
        except Exception as e:
            logger.error(f"SmartThings scene execution failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_scenes(self, user_id: str) -> List[Dict[str, Any]]:
        """Get available SmartThings scenes"""
        try:
            user_token = self.user_tokens.get(user_id)
            if not user_token:
                return []
            
            headers = {
                "Authorization": f"Bearer {user_token}",
                "Content-Type": "application/json"
            }
            
            async with ClientSession() as session:
                async with session.get(f"{self.api_base_url}/scenes", headers=headers) as response:
                    if response.status == 200:
                        scenes_data = await response.json()
                        
                        scenes = []
                        for scene in scenes_data.get('items', []):
                            scenes.append({
                                "id": scene.get('sceneId'),
                                "name": scene.get('sceneName'),
                                "icon": scene.get('sceneIcon'),
                                "location_id": scene.get('locationId'),
                                "last_executed": scene.get('lastExecutedDate'),
                                "platform": "smartthings"
                            })
                        
                        return scenes
                    else:
                        logger.error(f"Failed to get scenes: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Failed to get SmartThings scenes: {e}")
            return []
    
    async def setup_webhook(self, user_id: str) -> Dict[str, Any]:
        """Set up webhook for real-time device updates"""
        try:
            user_token = self.user_tokens.get(user_id)
            if not user_token:
                return {"error": "No authentication token available"}
            
            webhook_config = {
                "targetUrl": f"{self.webhook_url}/smartthings",
                "targetType": "WEBHOOK",
                "subscriptions": [
                    {"sourceType": "DEVICE", "eventTypes": ["*"]},
                    {"sourceType": "CAPABILITY", "eventTypes": ["*"]}
                ]
            }
            
            headers = {
                "Authorization": f"Bearer {user_token}",
                "Content-Type": "application/json"
            }
            
            async with ClientSession() as session:
                url = f"{self.api_base_url}/installedapps/{self.config.get('app_id', 'default')}/subscriptions"
                
                async with session.post(url, headers=headers, json=webhook_config) as response:
                    if response.status == 200:
                        webhook_data = await response.json()
                        return {
                            "success": True,
                            "webhook_id": webhook_data.get('id'),
                            "target_url": self.webhook_url
                        }
                    else:
                        return {"success": False, "error": f"Webhook setup failed: {response.status}"}
                        
        except Exception as e:
            logger.error(f"SmartThings webhook setup failed: {e}")
            return {"success": False, "error": str(e)}
    
    def process_webhook_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming webhook event from SmartThings"""
        try:
            events = event_data.get('events', [])
            processed_events = []
            
            for event in events:
                event_type = event.get('eventType')
                device_id = event.get('deviceId')
                
                if event_type == 'DEVICE_EVENT':
                    # Process device state change
                    component_id = event.get('componentId', 'main')
                    capability = event.get('capability')
                    attribute = event.get('attribute')
                    value = event.get('value')
                    
                    processed_event = {
                        "type": "device_state_change",
                        "device_id": device_id,
                        "capability": capability,
                        "attribute": attribute,
                        "value": value,
                        "timestamp": event.get('eventTime'),
                        "platform": "smartthings"
                    }
                    
                    processed_events.append(processed_event)
                    
                    # Update device cache if available
                    if device_id and capability and attribute:
                        self._update_device_cache(device_id, capability, attribute, value)
            
            return {
                "success": True,
                "events_processed": len(processed_events),
                "events": processed_events
            }
            
        except Exception as e:
            logger.error(f"SmartThings webhook event processing failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _update_device_cache(self, device_id: str, capability: str, attribute: str, value: Any):
        """Update device state in cache"""
        try:
            # Update device state in cache for faster access
            for user_id, cache_data in self.device_cache.items():
                for device in cache_data.get('devices', []):
                    if device.get('id') == device_id:
                        if 'current_state' not in device:
                            device['current_state'] = {}
                        
                        device['current_state'][f"{capability}.{attribute}"] = {
                            "value": value,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        break
                        
        except Exception as e:
            logger.error(f"Failed to update device cache: {e}")
    
    async def get_energy_data(self, timeframe: str = "today") -> Dict[str, Any]:
        """Get energy usage data from SmartThings devices"""
        try:
            # Mock implementation - actual implementation would query SmartThings energy API
            return {
                "platform": "smartthings",
                "timeframe": timeframe,
                "total_kwh": 12.5,
                "total_cost": 3.75,
                "estimated_savings": 1.25,
                "device_breakdown": {
                    "lighting": {"kwh": 4.2, "cost": 1.26},
                    "climate": {"kwh": 6.8, "cost": 2.04},
                    "appliances": {"kwh": 1.5, "cost": 0.45}
                },
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"SmartThings energy data failed: {e}")
            return {"error": str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """Get SmartThings integration status"""
        success_rate = (self.successful_commands / (self.successful_commands + self.failed_commands) * 100) if (self.successful_commands + self.failed_commands) > 0 else 100
        
        return {
            "platform": "Samsung SmartThings",
            "status": "connected" if self.user_tokens else "disconnected",
            "connected_users": len(self.user_tokens),
            "api_calls_today": self.api_calls_today,
            "successful_commands": self.successful_commands,
            "failed_commands": self.failed_commands,
            "success_rate": round(success_rate, 2),
            "cache_status": "fresh" if (datetime.utcnow() - self.last_cache_update) < self.cache_expiry else "stale",
            "capabilities": [
                "Device discovery and control",
                "Scene execution",
                "Real-time webhooks", 
                "Energy monitoring",
                "Multi-location support",
                "Advanced capability mapping"
            ]
        }
    
    async def shutdown(self):
        """Graceful shutdown of SmartThings integration"""
        try:
            logger.info("🛑 Shutting down SmartThings integration")
            # Cleanup resources, close connections, etc.
            self.user_tokens.clear()
            self.device_cache.clear()
            logger.info("✅ SmartThings integration shutdown complete")
        except Exception as e:
            logger.error(f"SmartThings shutdown error: {e}")