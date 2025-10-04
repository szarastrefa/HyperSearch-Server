"""
Philips Hue Integration
Advanced Hue lighting control with OpenHue API support
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
import colorsys

import aiohttp
from aiohttp import ClientSession, ClientTimeout
import zeroconf
from zeroconf import ServiceBrowser, Listener

logger = logging.getLogger(__name__)

class HueBridgeListener(Listener):
    """Zeroconf listener for Hue bridge discovery"""
    
    def __init__(self):
        self.bridges = []
    
    def add_service(self, zc: zeroconf.Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info and 'hue-bridgeid' in info.properties:
            bridge_id = info.properties[b'hue-bridgeid'].decode('utf-8')
            bridge_ip = str(info.parsed_addresses()[0]) if info.parsed_addresses() else None
            
            if bridge_ip:
                self.bridges.append({
                    'id': bridge_id,
                    'ip': bridge_ip,
                    'port': info.port,
                    'name': info.name
                })

class PhilipsHueIntegration:
    """
    Philips Hue Platform Integration
    Advanced lighting control with bridge discovery and OpenHue API
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.auto_discover = config.get('auto_discover', True)
        self.bridge_ip = config.get('bridge_ip')
        self.username = config.get('username')  # Hue bridge username
        
        # Discovered bridges
        self.bridges: Dict[str, Dict[str, Any]] = {}
        self.authenticated_bridges: Dict[str, str] = {}  # bridge_id -> username
        
        # Device cache
        self.light_cache: Dict[str, Dict[str, Any]] = {}
        self.sensor_cache: Dict[str, Dict[str, Any]] = {}
        self.scene_cache: Dict[str, Dict[str, Any]] = {}
        
        # Statistics
        self.commands_sent = 0
        self.successful_commands = 0
        self.discovery_attempts = 0
        
        # Start bridge discovery if enabled
        if self.auto_discover:
            asyncio.create_task(self._discover_bridges())
        
        logger.info("💡 Philips Hue integration initialized")
    
    async def _discover_bridges(self) -> List[Dict[str, Any]]:
        """Discover Hue bridges on network using mDNS"""
        try:
            self.discovery_attempts += 1
            logger.info("🔍 Discovering Hue bridges on network...")
            
            # Method 1: Zeroconf (mDNS) discovery
            zc = zeroconf.Zeroconf()
            listener = HueBridgeListener()
            browser = ServiceBrowser(zc, "_hue._tcp.local.", listener)
            
            # Wait for discovery
            await asyncio.sleep(3)
            
            # Method 2: Hue discovery service
            async with ClientSession() as session:
                try:
                    async with session.get("https://discovery.meethue.com/", timeout=ClientTimeout(total=5)) as response:
                        if response.status == 200:
                            discovery_data = await response.json()
                            for bridge_info in discovery_data:
                                listener.bridges.append({
                                    'id': bridge_info.get('id'),
                                    'ip': bridge_info.get('internalipaddress'),
                                    'port': 80,
                                    'name': f"Hue Bridge {bridge_info.get('id', '')[:6]}"
                                })
                except:
                    logger.warning("Hue discovery service unavailable")
            
            # Store discovered bridges
            for bridge in listener.bridges:
                if bridge['id'] and bridge['ip']:
                    self.bridges[bridge['id']] = bridge
            
            # Cleanup
            zc.close()
            
            logger.info(f"💡 Discovered {len(self.bridges)} Hue bridges")
            return list(self.bridges.values())
            
        except Exception as e:
            logger.error(f"Hue bridge discovery failed: {e}")
            return []
    
    async def authenticate_bridge(self, bridge_id: str, user_id: str) -> Dict[str, Any]:
        """Authenticate with Hue bridge (link button process)"""
        try:
            bridge = self.bridges.get(bridge_id)
            if not bridge:
                return {"error": "Bridge not found", "bridge_id": bridge_id}
            
            bridge_ip = bridge['ip']
            
            # Create new user on bridge
            auth_data = {
                "devicetype": f"HyperSearch#{user_id[:10]}",
                "generateclientkey": True
            }
            
            async with ClientSession() as session:
                async with session.post(f"http://{bridge_ip}/api", json=auth_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        if isinstance(result, list) and len(result) > 0:
                            first_result = result[0]
                            
                            if 'error' in first_result:
                                error = first_result['error']
                                if error.get('type') == 101:  # Link button not pressed
                                    return {
                                        "status": "link_button_required",
                                        "message": "Please press the link button on your Hue bridge and try again",
                                        "bridge_id": bridge_id,
                                        "bridge_ip": bridge_ip
                                    }
                                else:
                                    return {"error": error.get('description', 'Authentication failed')}
                            
                            elif 'success' in first_result:
                                username = first_result['success']['username']
                                self.authenticated_bridges[bridge_id] = username
                                
                                return {
                                    "success": True,
                                    "username": username,
                                    "bridge_id": bridge_id,
                                    "bridge_ip": bridge_ip
                                }
                    
                    return {"error": f"Authentication failed: HTTP {response.status}"}
                    
        except Exception as e:
            logger.error(f"Hue bridge authentication failed: {e}")
            return {"error": str(e)}
    
    async def discover_devices(self, user_id: str) -> List[Dict[str, Any]]:
        """Discover all Hue lights and sensors"""
        try:
            all_devices = []
            
            for bridge_id, username in self.authenticated_bridges.items():
                bridge = self.bridges.get(bridge_id)
                if not bridge:
                    continue
                
                bridge_ip = bridge['ip']
                
                async with ClientSession() as session:
                    # Get lights
                    async with session.get(f"http://{bridge_ip}/api/{username}/lights") as response:
                        if response.status == 200:
                            lights_data = await response.json()
                            
                            for light_id, light_info in lights_data.items():
                                device = {
                                    "id": f"hue_{bridge_id}_{light_id}",
                                    "name": light_info.get('name', f'Hue Light {light_id}'),
                                    "type": "light",
                                    "manufacturer": "Philips",
                                    "model": light_info.get('modelid', 'Unknown'),
                                    "platform": "hue",
                                    "bridge_id": bridge_id,
                                    "bridge_ip": bridge_ip,
                                    "light_id": light_id,
                                    "capabilities": {
                                        "on_off": True,
                                        "brightness": light_info.get('state', {}).get('bri') is not None,
                                        "color": light_info.get('state', {}).get('hue') is not None,
                                        "color_temp": light_info.get('state', {}).get('ct') is not None
                                    },
                                    "status": "online" if light_info.get('state', {}).get('reachable') else "offline",
                                    "current_state": light_info.get('state', {}),
                                    "raw_data": light_info
                                }
                                
                                all_devices.append(device)
                                self.light_cache[device['id']] = device
                    
                    # Get sensors
                    async with session.get(f"http://{bridge_ip}/api/{username}/sensors") as response:
                        if response.status == 200:
                            sensors_data = await response.json()
                            
                            for sensor_id, sensor_info in sensors_data.items():
                                if sensor_info.get('type') in ['ZLLPresence', 'ZLLLightLevel', 'ZLLTemperature']:
                                    device = {
                                        "id": f"hue_{bridge_id}_{sensor_id}",
                                        "name": sensor_info.get('name', f'Hue Sensor {sensor_id}'),
                                        "type": "sensor",
                                        "manufacturer": "Philips",
                                        "model": sensor_info.get('modelid', 'Unknown'),
                                        "platform": "hue",
                                        "bridge_id": bridge_id,
                                        "bridge_ip": bridge_ip,
                                        "sensor_id": sensor_id,
                                        "sensor_type": sensor_info.get('type'),
                                        "status": "online" if sensor_info.get('config', {}).get('reachable') else "offline",
                                        "current_state": sensor_info.get('state', {}),
                                        "raw_data": sensor_info
                                    }
                                    
                                    all_devices.append(device)
                                    self.sensor_cache[device['id']] = device
            
            logger.info(f"💡 Discovered {len(all_devices)} Hue devices")
            return all_devices
            
        except Exception as e:
            logger.error(f"Hue device discovery failed: {e}")
            return []
    
    async def control_device(self, device_id: str, command: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Control Hue device (light or sensor)"""
        try:
            self.commands_sent += 1
            
            # Get device from cache
            device = self.light_cache.get(device_id) or self.sensor_cache.get(device_id)
            if not device:
                return {"error": "Device not found in Hue cache", "device_id": device_id}
            
            bridge_id = device['bridge_id']
            bridge_ip = device['bridge_ip']
            username = self.authenticated_bridges.get(bridge_id)
            
            if not username:
                return {"error": "Bridge not authenticated", "bridge_id": bridge_id}
            
            # Map command to Hue API command
            hue_command = self._map_command_to_hue(command, parameters or {})
            if not hue_command:
                return {"error": f"Unsupported command: {command}"}
            
            # Execute command
            if device['type'] == 'light':
                light_id = device['light_id']
                url = f"http://{bridge_ip}/api/{username}/lights/{light_id}/state"
            else:
                return {"error": "Sensor control not supported"}
            
            async with ClientSession() as session:
                async with session.put(url, json=hue_command) as response:
                    if response.status == 200:
                        result_data = await response.json()
                        self.successful_commands += 1
                        
                        # Update cache with new state
                        if device_id in self.light_cache:
                            self.light_cache[device_id]['current_state'].update(hue_command)
                            self.light_cache[device_id]['last_updated'] = datetime.utcnow()
                        
                        return {
                            "success": True,
                            "device_id": device_id,
                            "command": command,
                            "new_state": hue_command,
                            "result": result_data,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"Command failed: {response.status} - {error_text}",
                            "device_id": device_id
                        }
                        
        except Exception as e:
            logger.error(f"Hue device control failed: {e}")
            return {"success": False, "error": str(e), "device_id": device_id}
    
    def _map_command_to_hue(self, command: str, parameters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Map generic command to Hue API command"""
        command_map = {
            "turn_on": {"on": True},
            "turn_off": {"on": False},
            "set_brightness": {
                "on": True,
                "bri": int(parameters.get('brightness', 50) * 2.54)  # 0-100 to 0-254
            },
            "set_color": {
                "on": True,
                "hue": int(parameters.get('hue', 0) * 182.04),  # 0-360 to 0-65535
                "sat": int(parameters.get('saturation', 100) * 2.54)  # 0-100 to 0-254
            },
            "set_color_temp": {
                "on": True,
                "ct": parameters.get('color_temp', 300)  # Mireds
            },
            "set_rgb": {
                "on": True,
                **self._rgb_to_hue(
                    parameters.get('red', 255),
                    parameters.get('green', 255), 
                    parameters.get('blue', 255)
                )
            }
        }
        
        base_command = command_map.get(command.lower())
        if not base_command:
            return None
        
        # Add transition time if specified
        if 'transition_time' in parameters:
            base_command['transitiontime'] = int(parameters['transition_time'] * 10)  # Seconds to deciseconds
        
        return base_command
    
    def _rgb_to_hue(self, red: int, green: int, blue: int) -> Dict[str, int]:
        """Convert RGB values to Hue HSB format"""
        try:
            # Normalize RGB values
            r, g, b = red / 255.0, green / 255.0, blue / 255.0
            
            # Convert to HSV
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            
            # Convert to Hue API format
            return {
                "hue": int(h * 65535),      # 0-1 to 0-65535
                "sat": int(s * 254),        # 0-1 to 0-254
                "bri": int(v * 254)         # 0-1 to 0-254
            }
            
        except Exception as e:
            logger.error(f"RGB to Hue conversion failed: {e}")
            return {"hue": 0, "sat": 254, "bri": 254}
    
    async def create_scene(self, scene_name: str, light_ids: List[str], states: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create new Hue scene"""
        try:
            # Find bridge for first light
            if not light_ids:
                return {"error": "No lights specified for scene"}
            
            first_light = self.light_cache.get(light_ids[0])
            if not first_light:
                return {"error": "Light not found"}
            
            bridge_id = first_light['bridge_id']
            bridge_ip = first_light['bridge_ip']
            username = self.authenticated_bridges.get(bridge_id)
            
            if not username:
                return {"error": "Bridge not authenticated"}
            
            # Prepare scene data
            scene_data = {
                "name": scene_name,
                "lights": [light.split('_')[-1] for light in light_ids],  # Extract Hue light IDs
                "recycle": False
            }
            
            async with ClientSession() as session:
                url = f"http://{bridge_ip}/api/{username}/scenes"
                
                async with session.post(url, json=scene_data) as response:
                    if response.status == 200:
                        result_data = await response.json()
                        
                        if isinstance(result_data, list) and len(result_data) > 0:
                            success_result = result_data[0].get('success')
                            if success_result:
                                scene_id = success_result.get('id')
                                
                                # Set light states for scene
                                for i, (light_id, state) in enumerate(zip(light_ids, states)):
                                    hue_light_id = light_id.split('_')[-1]
                                    state_url = f"http://{bridge_ip}/api/{username}/scenes/{scene_id}/lightstates/{hue_light_id}"
                                    
                                    await session.put(state_url, json=state)
                                
                                return {
                                    "success": True,
                                    "scene_id": scene_id,
                                    "scene_name": scene_name,
                                    "lights_count": len(light_ids)
                                }
                    
                    return {"error": f"Scene creation failed: {response.status}"}
                    
        except Exception as e:
            logger.error(f"Hue scene creation failed: {e}")
            return {"error": str(e)}
    
    async def activate_scene(self, scene_id: str) -> Dict[str, Any]:
        """Activate Hue scene"""
        try:
            # Find bridge for scene (simplified - assumes first authenticated bridge)
            if not self.authenticated_bridges:
                return {"error": "No authenticated bridges"}
            
            bridge_id = list(self.authenticated_bridges.keys())[0]
            bridge = self.bridges.get(bridge_id)
            username = self.authenticated_bridges.get(bridge_id)
            
            if not bridge or not username:
                return {"error": "Bridge not available"}
            
            async with ClientSession() as session:
                url = f"http://{bridge['ip']}/api/{username}/groups/0/action"
                command_data = {"scene": scene_id}
                
                async with session.put(url, json=command_data) as response:
                    if response.status == 200:
                        result_data = await response.json()
                        return {
                            "success": True,
                            "scene_id": scene_id,
                            "result": result_data,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    else:
                        return {"success": False, "error": f"Scene activation failed: {response.status}"}
                        
        except Exception as e:
            logger.error(f"Hue scene activation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """Get Hue integration status"""
        success_rate = (self.successful_commands / self.commands_sent * 100) if self.commands_sent > 0 else 100
        
        return {
            "platform": "Philips Hue",
            "status": "connected" if self.authenticated_bridges else "disconnected",
            "bridges_discovered": len(self.bridges),
            "bridges_authenticated": len(self.authenticated_bridges),
            "lights_cached": len(self.light_cache),
            "sensors_cached": len(self.sensor_cache),
            "commands_sent": self.commands_sent,
            "successful_commands": self.successful_commands,
            "success_rate": round(success_rate, 2),
            "discovery_attempts": self.discovery_attempts,
            "capabilities": [
                "Bridge discovery via mDNS",
                "Advanced lighting control",
                "RGB and color temperature",
                "Scene management",
                "Motion sensor integration",
                "Real-time state updates"
            ]
        }
    
    async def get_energy_data(self, timeframe: str = "today") -> Dict[str, Any]:
        """Get energy usage data from Hue lights"""
        try:
            # Calculate estimated energy usage based on light usage
            total_lights = len(self.light_cache)
            avg_power_per_light = 9  # Watts average for Hue bulbs
            estimated_hours_today = 8  # Average usage per day
            
            estimated_kwh = (total_lights * avg_power_per_light * estimated_hours_today) / 1000
            estimated_cost = estimated_kwh * 0.30  # €0.30 per kWh average
            
            return {
                "platform": "hue",
                "timeframe": timeframe,
                "total_kwh": round(estimated_kwh, 2),
                "total_cost": round(estimated_cost, 2),
                "estimated_savings": round(estimated_cost * 0.15, 2),  # 15% savings through optimization
                "device_count": total_lights,
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Hue energy data calculation failed: {e}")
            return {"error": str(e)}
    
    async def shutdown(self):
        """Graceful shutdown of Hue integration"""
        try:
            logger.info("🛑 Shutting down Philips Hue integration")
            self.bridges.clear()
            self.authenticated_bridges.clear()
            self.light_cache.clear()
            self.sensor_cache.clear()
            logger.info("✅ Philips Hue integration shutdown complete")
        except Exception as e:
            logger.error(f"Hue shutdown error: {e}")