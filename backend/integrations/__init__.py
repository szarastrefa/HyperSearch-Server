"""
HyperSearch Platform Integrations
Enterprise API integrations for major platforms
"""

from .microsoft_integration import MicrosoftIntegration
from .google_integration import GoogleIntegration
from .meta_integration import MetaIntegration
from .github_integration import GitHubIntegration
from .slack_integration import SlackIntegration
from .notion_integration import NotionIntegration
from .salesforce_integration import SalesforceIntegration
from .aws_integration import AWSIntegration
from .azure_integration import AzureIntegration

__all__ = [
    'MicrosoftIntegration',
    'GoogleIntegration', 
    'MetaIntegration',
    'GitHubIntegration',
    'SlackIntegration',
    'NotionIntegration',
    'SalesforceIntegration',
    'AWSIntegration',
    'AzureIntegration'
]

# Integration registry
INTEGRATION_REGISTRY = {
    'microsoft': MicrosoftIntegration,
    'google': GoogleIntegration,
    'meta': MetaIntegration,
    'facebook': MetaIntegration,
    'instagram': MetaIntegration,
    'threads': MetaIntegration,
    'whatsapp': MetaIntegration,
    'github': GitHubIntegration,
    'slack': SlackIntegration,
    'notion': NotionIntegration,
    'salesforce': SalesforceIntegration,
    'aws': AWSIntegration,
    'azure': AzureIntegration
}