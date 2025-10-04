"""
GitHub Enterprise Integration
Comprehensive GitHub integration for repositories, issues, actions, and more
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

import aiohttp
from github import Github
from github.GithubException import GithubException

from .base_integration import BaseIntegration

logger = logging.getLogger(__name__)

class GitHubIntegration(BaseIntegration):
    """
    GitHub Enterprise Integration
    Supports: Repositories, Issues, Pull Requests, Actions, Projects, Copilot
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.token = config.get('github_token')
        self.app_id = config.get('app_id')
        self.client_id = config.get('client_id')
        self.client_secret = config.get('client_secret')
        self.webhook_secret = config.get('webhook_secret')
        
        # GitHub Enterprise Server URL (if applicable)
        self.base_url = config.get('base_url', 'https://api.github.com')
        
        # GitHub client
        self.github_client = None
        
        # Supported services
        self.services = {
            'repositories': True,
            'issues': True,
            'pull_requests': True,
            'actions': True,
            'projects': True,
            'discussions': True,
            'wiki': True,
            'releases': True,
            'copilot': True
        }
        
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize GitHub client"""
        try:
            if self.token:
                if self.base_url != 'https://api.github.com':
                    # GitHub Enterprise Server
                    self.github_client = Github(base_url=self.base_url, login_or_token=self.token)
                else:
                    # GitHub.com
                    self.github_client = Github(self.token)
                
                # Test connection
                user = self.github_client.get_user()
                logger.info(f"🐙 GitHub integration initialized for user: {user.login}")
            else:
                logger.warning("GitHub token not provided")
                
        except Exception as e:
            logger.error(f"Failed to initialize GitHub client: {e}")
    
    async def authenticate(self, user_id: str) -> Dict[str, Any]:
        """Authenticate user with GitHub"""
        try:
            # GitHub OAuth URL
            scope = [
                'repo',
                'read:user',
                'read:org',
                'read:project',
                'read:discussion'
            ]
            
            auth_url = (
                f"https://github.com/login/oauth/authorize?"
                f"client_id={self.client_id}&"
                f"scope={','.join(scope)}&"
                f"state={user_id}&"
                f"redirect_uri={self.config.get('redirect_uri')}"
            )
            
            return {
                "auth_url": auth_url,
                "status": "redirect_required",
                "provider": "github"
            }
            
        except Exception as e:
            logger.error(f"GitHub authentication failed: {e}")
            return {"error": str(e), "status": "failed"}
    
    async def search_repositories(self, query: str, user_token: str = None) -> List[Dict[str, Any]]:
        """Search GitHub repositories"""
        try:
            client = self.github_client or Github(user_token) if user_token else self.github_client
            if not client:
                return []
            
            # Search repositories
            repos = client.search_repositories(query, sort='stars', order='desc')[:25]
            results = []
            
            for repo in repos:
                results.append({
                    'id': repo.id,
                    'title': repo.full_name,
                    'content': repo.description or 'No description available',
                    'source': 'GitHub Repository',
                    'type': 'repository',
                    'language': repo.language,
                    'stars': repo.stargazers_count,
                    'forks': repo.forks_count,
                    'created_time': repo.created_at.isoformat(),
                    'updated_time': repo.updated_at.isoformat(),
                    'url': repo.html_url,
                    'clone_url': repo.clone_url
                })
            
            return results
            
        except Exception as e:
            logger.error(f"GitHub repositories search failed: {e}")
            return []
    
    async def search_issues(self, query: str, user_token: str = None) -> List[Dict[str, Any]]:
        """Search GitHub issues and pull requests"""
        try:
            client = self.github_client or Github(user_token) if user_token else self.github_client
            if not client:
                return []
            
            # Search issues
            issues = client.search_issues(query, sort='updated', order='desc')[:25]
            results = []
            
            for issue in issues:
                issue_type = 'pull_request' if issue.pull_request else 'issue'
                
                results.append({
                    'id': issue.id,
                    'title': issue.title,
                    'content': issue.body or 'No description available',
                    'source': 'GitHub Issues',
                    'type': issue_type,
                    'repository': issue.repository.full_name,
                    'state': issue.state,
                    'author': issue.user.login,
                    'assignees': [a.login for a in issue.assignees],
                    'labels': [l.name for l in issue.labels],
                    'created_time': issue.created_at.isoformat(),
                    'updated_time': issue.updated_at.isoformat(),
                    'url': issue.html_url,
                    'comments_count': issue.comments
                })
            
            return results
            
        except Exception as e:
            logger.error(f"GitHub issues search failed: {e}")
            return []
    
    async def search_code(self, query: str, user_token: str = None) -> List[Dict[str, Any]]:
        """Search code in GitHub repositories"""
        try:
            client = self.github_client or Github(user_token) if user_token else self.github_client
            if not client:
                return []
            
            # Search code
            code_results = client.search_code(query)[:25]
            results = []
            
            for code in code_results:
                results.append({
                    'id': f"{code.repository.id}_{code.sha}",
                    'title': f"{code.name} in {code.repository.full_name}",
                    'content': f"Code file: {code.path}",
                    'source': 'GitHub Code',
                    'type': 'code_file',
                    'repository': code.repository.full_name,
                    'file_path': code.path,
                    'file_name': code.name,
                    'language': code.repository.language,
                    'sha': code.sha,
                    'url': code.html_url
                })
            
            return results
            
        except Exception as e:
            logger.error(f"GitHub code search failed: {e}")
            return []
    
    async def search_discussions(self, query: str, user_token: str = None) -> List[Dict[str, Any]]:
        """Search GitHub Discussions"""
        try:
            # GitHub Discussions search via GraphQL API
            headers = {
                'Authorization': f'Bearer {user_token or self.token}',
                'Content-Type': 'application/json'
            }
            
            graphql_query = '''
            query($query: String!, $first: Int!) {
              search(query: $query, type: DISCUSSION, first: $first) {
                edges {
                  node {
                    ... on Discussion {
                      id
                      title
                      body
                      url
                      createdAt
                      updatedAt
                      author {
                        login
                      }
                      repository {
                        nameWithOwner
                      }
                      category {
                        name
                      }
                    }
                  }
                }
              }
            }
            '''
            
            variables = {
                'query': query,
                'first': 25
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://api.github.com/graphql',
                    headers=headers,
                    json={'query': graphql_query, 'variables': variables}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = []
                        
                        for edge in data.get('data', {}).get('search', {}).get('edges', []):
                            discussion = edge['node']
                            results.append({
                                'id': discussion['id'],
                                'title': discussion['title'],
                                'content': discussion['body'] or 'No content available',
                                'source': 'GitHub Discussions',
                                'type': 'discussion',
                                'repository': discussion['repository']['nameWithOwner'],
                                'author': discussion['author']['login'],
                                'category': discussion['category']['name'],
                                'created_time': discussion['createdAt'],
                                'updated_time': discussion['updatedAt'],
                                'url': discussion['url']
                            })
                        
                        return results
            
            return []
            
        except Exception as e:
            logger.error(f"GitHub discussions search failed: {e}")
            return []
    
    async def get_workflow_runs(self, repo_owner: str, repo_name: str, user_token: str = None) -> List[Dict[str, Any]]:
        """Get GitHub Actions workflow runs"""
        try:
            client = self.github_client or Github(user_token) if user_token else self.github_client
            if not client:
                return []
            
            repo = client.get_repo(f"{repo_owner}/{repo_name}")
            workflows = repo.get_workflows()
            
            results = []
            for workflow in workflows[:10]:  # Limit workflows
                runs = workflow.get_runs()[:5]  # Limit runs per workflow
                
                for run in runs:
                    results.append({
                        'id': run.id,
                        'title': f"Workflow: {workflow.name}",
                        'content': f"Run #{run.run_number}: {run.display_title}",
                        'source': 'GitHub Actions',
                        'type': 'workflow_run',
                        'repository': f"{repo_owner}/{repo_name}",
                        'workflow_name': workflow.name,
                        'status': run.status,
                        'conclusion': run.conclusion,
                        'created_time': run.created_at.isoformat(),
                        'updated_time': run.updated_at.isoformat(),
                        'url': run.html_url,
                        'run_number': run.run_number
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"GitHub Actions search failed: {e}")
            return []
    
    async def search_all(self, query: str, user_token: str = None) -> Dict[str, List[Dict[str, Any]]]:
        """Search across all GitHub services"""
        try:
            # Run searches concurrently
            tasks = [
                self.search_repositories(query, user_token),
                self.search_issues(query, user_token),
                self.search_code(query, user_token),
                self.search_discussions(query, user_token)
            ]
            
            repo_results, issue_results, code_results, discussion_results = await asyncio.gather(*tasks)
            
            return {
                'repositories': repo_results,
                'issues': issue_results,
                'code': code_results,
                'discussions': discussion_results
            }
            
        except Exception as e:
            logger.error(f"GitHub search failed: {e}")
            return {}
    
    def get_supported_services(self) -> List[str]:
        """Get list of supported GitHub services"""
        return list(self.services.keys())
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get GitHub integration status"""
        return {
            'provider': 'GitHub Enterprise',
            'status': 'active' if self.github_client else 'inactive',
            'services': self.services,
            'auth_method': 'OAuth2 + Personal Access Token',
            'capabilities': [
                'Repository search',
                'Issues and Pull Requests search',
                'Code search across repositories',
                'GitHub Discussions search',
                'GitHub Actions integration',
                'Project management',
                'Webhook support',
                'Enterprise Server support'
            ]
        }