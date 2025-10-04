"""
Smart Home Manager - Unified Smart Home Platform Management
Enterprise-grade smart home device management and automation
"""

import logging
import asyncio
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

from .device_registry import DeviceRegistry, SmartDevice
from .samsung_smartthings import SmartThingsIntegration
from .philips_hue import PhilipsHueIntegration
from .tuya_integration import TuyaIntegration
from .automation_engine import AutomationEngine
from ..utils.cache import CacheManager
from ..monitoring.metrics import track_smart_home_metrics

logger = logging.getLogger(__name__)

class PlatformStatus(Enum):
    """Smart home platform status"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    AUTHENTICATING = "authenticating"
    ERROR = "error"
    MAINTENANCE = "maintenance"

@dataclass
class SmartHomeStats:
    """Smart home system statistics"""
    total_devices: int = 0
    active_devices: int = 0
    platforms_connected: int = 0
    automations_active: int = 0
    energy_saved_today: float = 0.0
    commands_processed_today: int = 0
    last_updated: datetime = None

class SmartHomeManager:
    """
    Smart Home Manager - Central hub for all smart home platforms
    Manages Samsung SmartThings, Philips Hue, Tuya, and other platforms
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.platforms: Dict[str, Any] = {}
        self.device_registry = DeviceRegistry()
        self.automation_engine = AutomationEngine()
        self.cache_manager = CacheManager()
        
        # System statistics
        self.stats = SmartHomeStats()
        self.startup_time = datetime.utcnow()
        self.command_history: List[Dict[str, Any]] = []
        
        # Initialize platforms
        self._initialize_platforms()
        
        logger.info("🏠 Smart Home Manager initialized")
    
    def _initialize_platforms(self):
        """Initialize all configured smart home platforms"""
        try:
            # Samsung SmartThings
            smartthings_config = self.config.get('samsung_smartthings', {})
            if smartthings_config.get('enabled', True):
                self.platforms['smartthings'] = SmartThingsIntegration(smartthings_config)
                logger.info("✅ Samsung SmartThings integration initialized")
            
            # Philips Hue
            hue_config = self.config.get('philips_hue', {})
            if hue_config.get('enabled', True):
                self.platforms['hue'] = PhilipsHueIntegration(hue_config)
                logger.info("✅ Philips Hue integration initialized")
            
            # Tuya Platform
            tuya_config = self.config.get('tuya', {})
            if tuya_config.get('enabled', True):
                self.platforms['tuya'] = TuyaIntegration(tuya_config)
                logger.info("✅ Tuya integration initialized")
            
            self.stats.platforms_connected = len(self.platforms)
            
        except Exception as e:
            logger.error(f"Failed to initialize smart home platforms: {e}")
    
    async def discover_all_devices(self, user_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """Discover devices from all connected platforms"""
        try:
            logger.info(f"🔍 Discovering devices for user {user_id}")
            
            all_devices = {}
            discovery_tasks = []
            
            # Run device discovery concurrently across all platforms
            for platform_name, platform in self.platforms.items():
                task = self._discover_platform_devices(platform_name, platform, user_id)
                discovery_tasks.append(task)
            
            # Wait for all discovery tasks
            platform_results = await asyncio.gather(*discovery_tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(platform_results):
                platform_name = list(self.platforms.keys())[i]
                
                if isinstance(result, Exception):
                    logger.error(f"Device discovery failed for {platform_name}: {result}")
                    all_devices[platform_name] = []
                else:
                    all_devices[platform_name] = result
                    
                    # Register devices in central registry
                    for device in result:
                        smart_device = SmartDevice.from_api_data(device, platform_name)
                        await self.device_registry.register_device(smart_device)
            
            # Update statistics
            total_devices = sum(len(devices) for devices in all_devices.values())
            self.stats.total_devices = total_devices
            self.stats.active_devices = await self.device_registry.get_active_device_count()
            self.stats.last_updated = datetime.utcnow()
            
            # Track metrics
            track_smart_home_metrics("device_discovery", {
                "user_id": user_id,
                "platforms": len(self.platforms),
                "devices_found": total_devices,
                "success": True
            })
            
            return all_devices
            
        except Exception as e:
            logger.error(f"Device discovery failed: {e}")
            track_smart_home_metrics("device_discovery", {
                "user_id": user_id,
                "error": str(e),
                "success": False
            })
            return {}
    
    async def _discover_platform_devices(self, platform_name: str, platform: Any, user_id: str) -> List[Dict[str, Any]]:
        """Discover devices from specific platform"""
        try:
            if hasattr(platform, 'discover_devices'):
                return await platform.discover_devices(user_id)
            else:
                logger.warning(f"Platform {platform_name} doesn't support device discovery")
                return []
        except Exception as e:
            logger.error(f"Device discovery failed for {platform_name}: {e}")
            return []
    
    async def control_device(self, device_id: str, command: str, parameters: Dict[str, Any] = None, user_id: str = None) -> Dict[str, Any]:
        """Control smart home device"""
        try:
            # Get device info from registry
            device = await self.device_registry.get_device(device_id)
            if not device:
                return {"error": "Device not found", "device_id": device_id}
            
            # Get platform integration
            platform = self.platforms.get(device.platform)
            if not platform:
                return {"error": f"Platform {device.platform} not available", "device_id": device_id}
            
            logger.info(f"🎮 Controlling device {device_id}: {command}")
            
            # Execute command
            start_time = datetime.utcnow()
            result = await platform.control_device(device_id, command, parameters or {})
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Log command execution
            command_log = {
                "device_id": device_id,
                "command": command,
                "parameters": parameters,
                "result": result,
                "execution_time": execution_time,
                "timestamp": datetime.utcnow(),
                "user_id": user_id
            }
            self.command_history.append(command_log)
            
            # Update device state if successful
            if result.get('success', False):
                await self.device_registry.update_device_state(device_id, result.get('new_state', {}))
                self.stats.commands_processed_today += 1
            
            # Track metrics
            track_smart_home_metrics("device_control", {
                "device_id": device_id,
                "command": command,
                "platform": device.platform,
                "execution_time": execution_time,
                "success": result.get('success', False),
                "user_id": user_id
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Device control failed for {device_id}: {e}")
            return {"error": str(e), "device_id": device_id}
    
    async def activate_scene(self, scene_name: str, user_id: str = None) -> Dict[str, Any]:
        """Activate smart home scene across multiple platforms"""
        try:
            logger.info(f"🎭 Activating scene: {scene_name}")
            
            # Get scene configuration
            scene_config = await self.automation_engine.get_scene_config(scene_name)
            if not scene_config:
                return {"error": f"Scene '{scene_name}' not found"}
            
            # Execute scene actions across platforms
            scene_results = []
            for action in scene_config.get('actions', []):
                platform = action.get('platform')
                device_id = action.get('device_id')
                command = action.get('command')
                parameters = action.get('parameters', {})
                
                if platform in self.platforms:
                    result = await self.control_device(device_id, command, parameters, user_id)
                    scene_results.append({
                        "device_id": device_id,
                        "platform": platform,
                        "result": result
                    })
            
            # Calculate success rate
            successful_actions = sum(1 for r in scene_results if r['result'].get('success', False))
            success_rate = successful_actions / len(scene_results) if scene_results else 0
            
            return {
                "success": success_rate > 0.8,
                "scene_name": scene_name,
                "actions_executed": len(scene_results),
                "successful_actions": successful_actions,
                "success_rate": success_rate,
                "results": scene_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Scene activation failed for {scene_name}: {e}")
            return {"error": str(e), "scene_name": scene_name}
    
    async def get_all_devices(self, user_id: str = None) -> List[Dict[str, Any]]:
        """Get all registered smart home devices"""
        try:
            devices = await self.device_registry.get_all_devices(user_id)
            return [device.to_dict() for device in devices]
        except Exception as e:
            logger.error(f"Failed to get devices: {e}")
            return []
    
    async def search_devices(self, query: str, user_id: str = None) -> List[Dict[str, Any]]:
        """Search for devices by name, type, or location"""
        try:
            devices = await self.device_registry.search_devices(query, user_id)
            return [device.to_dict() for device in devices]
        except Exception as e:
            logger.error(f"Device search failed: {e}")
            return []
    
    def get_platform_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all smart home platforms"""
        platform_status = {}
        
        for platform_name, platform in self.platforms.items():
            try:
                if hasattr(platform, 'get_status'):
                    status = platform.get_status()
                else:
                    status = {"status": "unknown", "message": "Status check not implemented"}
                
                platform_status[platform_name] = status
            except Exception as e:
                platform_status[platform_name] = {
                    "status": "error",
                    "message": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        return platform_status
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get smart home system statistics"""
        uptime = (datetime.utcnow() - self.startup_time).total_seconds()
        
        return {
            "system_stats": asdict(self.stats),
            "platform_count": len(self.platforms),
            "platform_names": list(self.platforms.keys()),
            "uptime_seconds": uptime,
            "recent_commands": len([cmd for cmd in self.command_history 
                                   if cmd['timestamp'] > datetime.utcnow() - timedelta(hours=1)]),
            "system_health": "healthy" if self.stats.platforms_connected > 0 else "degraded"
        }
    
    async def authenticate_platform(self, platform: str, user_id: str) -> Dict[str, Any]:
        """Authenticate user with specific smart home platform"""
        try:
            if platform not in self.platforms:
                return {"error": f"Platform {platform} not supported"}
            
            integration = self.platforms[platform]
            if hasattr(integration, 'authenticate'):
                return await integration.authenticate(user_id)
            else:
                return {"error": f"Platform {platform} doesn't support authentication"}
                
        except Exception as e:
            logger.error(f"Authentication failed for platform {platform}: {e}")
            return {"error": str(e), "platform": platform}
    
    async def sync_all_platforms(self, user_id: str) -> Dict[str, Any]:
        """Synchronize device states across all platforms"""
        try:
            logger.info("🔄 Synchronizing all smart home platforms")
            
            sync_results = {}
            sync_tasks = []
            
            for platform_name, platform in self.platforms.items():
                if hasattr(platform, 'sync_devices'):
                    task = platform.sync_devices(user_id)
                    sync_tasks.append((platform_name, task))
            
            # Wait for all sync operations
            for platform_name, task in sync_tasks:
                try:
                    result = await task
                    sync_results[platform_name] = result
                except Exception as e:
                    logger.error(f"Sync failed for {platform_name}: {e}")
                    sync_results[platform_name] = {"error": str(e)}
            
            # Update device registry with latest states
            await self.device_registry.refresh_all_devices()
            
            return {
                "success": True,
                "sync_results": sync_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Platform synchronization failed: {e}")
            return {"error": str(e), "success": False}
    
    async def create_automation(self, automation_config: Dict[str, Any], user_id: str = None) -> Dict[str, Any]:
        """Create new automation rule"""
        try:
            return await self.automation_engine.create_automation(automation_config, user_id)
        except Exception as e:
            logger.error(f"Automation creation failed: {e}")
            return {"error": str(e), "success": False}
    
    async def get_energy_analytics(self, timeframe: str = "today") -> Dict[str, Any]:
        """Get energy usage analytics"""
        try:
            # Collect energy data from all platforms
            energy_data = {}
            
            for platform_name, platform in self.platforms.items():
                if hasattr(platform, 'get_energy_data'):
                    platform_energy = await platform.get_energy_data(timeframe)
                    energy_data[platform_name] = platform_energy
            
            # Calculate totals and savings
            total_consumption = sum(
                data.get('total_kwh', 0) 
                for data in energy_data.values() 
                if isinstance(data, dict)
            )
            
            total_cost = sum(
                data.get('total_cost', 0) 
                for data in energy_data.values() 
                if isinstance(data, dict)
            )
            
            estimated_savings = sum(
                data.get('estimated_savings', 0) 
                for data in energy_data.values() 
                if isinstance(data, dict)
            )
            
            return {
                "timeframe": timeframe,
                "total_consumption_kwh": round(total_consumption, 2),
                "total_cost": round(total_cost, 2),
                "estimated_savings": round(estimated_savings, 2),
                "platform_breakdown": energy_data,
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Energy analytics failed: {e}")
            return {"error": str(e)}
    
    async def execute_smart_command(self, command: str, user_id: str = None) -> Dict[str, Any]:
        """Execute natural language smart home command"""
        try:
            logger.info(f"🗣️ Processing smart command: '{command}'")
            
            # Use automation engine to parse and execute command
            result = await self.automation_engine.process_natural_command(command, user_id)
            
            # Log command execution
            command_log = {
                "command": command,
                "user_id": user_id,
                "result": result,
                "timestamp": datetime.utcnow(),
                "processing_time": result.get('processing_time', 0)
            }
            self.command_history.append(command_log)
            
            # Keep command history manageable
            if len(self.command_history) > 1000:
                self.command_history = self.command_history[-800:]
            
            return result
            
        except Exception as e:
            logger.error(f"Smart command execution failed: {e}")
            return {"error": str(e), "command": command}
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get smart home system health status"""
        try:
            platform_health = self.get_platform_status()
            
            healthy_platforms = sum(
                1 for status in platform_health.values() 
                if status.get('status') == 'connected'
            )
            
            system_health = "healthy" if healthy_platforms > 0 else "unhealthy"
            if healthy_platforms < len(self.platforms):
                system_health = "degraded"
            
            return {
                "status": system_health,
                "platforms_healthy": healthy_platforms,
                "platforms_total": len(self.platforms),
                "devices_active": self.stats.active_devices,
                "devices_total": self.stats.total_devices,
                "uptime": (datetime.utcnow() - self.startup_time).total_seconds(),
                "last_command": self.command_history[-1]['timestamp'].isoformat() if self.command_history else None,
                "platform_details": platform_health
            }
            
        except Exception as e:
            logger.error(f"Health status check failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def shutdown(self):
        """Graceful shutdown of smart home manager"""
        try:
            logger.info("🛑 Shutting down Smart Home Manager")
            
            # Shutdown all platforms
            shutdown_tasks = []
            for platform_name, platform in self.platforms.items():
                if hasattr(platform, 'shutdown'):
                    shutdown_tasks.append(platform.shutdown())
            
            await asyncio.gather(*shutdown_tasks, return_exceptions=True)
            
            # Save final statistics
            await self.cache_manager.set('smart_home_final_stats', asdict(self.stats))
            
            logger.info("✅ Smart Home Manager shutdown complete")
            
        except Exception as e:
            logger.error(f"Smart Home Manager shutdown error: {e}")