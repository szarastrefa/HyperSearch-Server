"""
HyperSearch Smart Home Integration Suite
Enterprise-grade smart home platform integrations
"""

from .manager import SmartHomeManager
from .samsung_smartthings import SmartThingsIntegration
from .philips_hue import PhilipsHueIntegration
from .tuya_integration import TuyaIntegration
from .device_registry import DeviceRegistry
from .automation_engine import AutomationEngine

__all__ = [
    'SmartHomeManager',
    'SmartThingsIntegration',
    'PhilipsHueIntegration', 
    'TuyaIntegration',
    'DeviceRegistry',
    'AutomationEngine'
]

# Smart Home Platform Registry
SMART_HOME_PLATFORMS = {
    'smartthings': SmartThingsIntegration,
    'samsung': SmartThingsIntegration,
    'hue': PhilipsHueIntegration,
    'philips': PhilipsHueIntegration,
    'tuya': TuyaIntegration,
    'smart_life': TuyaIntegration
}

# Supported device categories
DEVICE_CATEGORIES = {
    'lighting': ['bulb', 'strip', 'fixture', 'dimmer'],
    'climate': ['thermostat', 'hvac', 'fan', 'humidifier'],
    'security': ['camera', 'sensor', 'lock', 'alarm'],
    'entertainment': ['tv', 'speaker', 'media_player'],
    'appliances': ['plug', 'switch', 'outlet', 'vacuum'],
    'sensors': ['motion', 'door', 'temperature', 'humidity']
}