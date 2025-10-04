"""
HyperSearch AI Platform - Main Flask Application Server
Enterprise-grade AI search platform with cognitive agents
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

# Import HyperSearch components
from cognitive.agent_manager import CognitiveAgentManager
from search.multimodal_engine import MultimodalSearchEngine
from monitoring.metrics import track_api_metrics, update_system_metrics
from localization import get_message, get_supported_languages

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/hypersearch.log')
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Configuration
app.config.update(
    SECRET_KEY=os.getenv('SECRET_KEY', 'hypersearch-dev-key-change-in-production'),
    MAX_CONTENT_LENGTH=100 * 1024 * 1024,  # 100MB max upload
    JSON_SORT_KEYS=False,
    JSONIFY_PRETTYPRINT_REGULAR=True
)

# Enable CORS for frontend integration
CORS(app, origins=[
    "http://localhost:3000",
    "https://hypersearch.your-domain.com",
    os.getenv('FRONTEND_URL', 'http://localhost:3000')
])

# Rate limiting
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["1000 per hour"],
    storage_uri=os.getenv('REDIS_URL', 'redis://localhost:6379')
)

# Initialize core components
try:
    cognitive_manager = CognitiveAgentManager()
    search_engine = MultimodalSearchEngine()
    logger.info("🧠 Cognitive agents and search engine initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize core components: {e}")
    cognitive_manager = None
    search_engine = None

# Health check endpoint
@app.route('/api/health', methods=['GET'])
@track_api_metrics
def health_check():
    """System health check endpoint"""
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0',
            'environment': os.getenv('FLASK_ENV', 'development'),
            'components': {
                'cognitive_agents': cognitive_manager.get_health_status() if cognitive_manager else 'unavailable',
                'search_engine': search_engine.get_health_status() if search_engine else 'unavailable',
                'database': 'connected',  # TODO: Add actual DB health check
                'cache': 'connected'      # TODO: Add actual Redis health check
            },
            'metrics': {
                'active_agents': cognitive_manager.get_active_agent_count() if cognitive_manager else 0,
                'total_searches': search_engine.get_search_count() if search_engine else 0,
                'uptime_seconds': 0  # TODO: Track actual uptime
            }
        }
        
        # Update system metrics
        update_system_metrics()
        
        return jsonify(health_status), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

# Cognitive agents endpoints
@app.route('/api/agents', methods=['GET'])
@limiter.limit("100 per minute")
@track_api_metrics
def get_agents():
    """Get list of active cognitive agents"""
    try:
        if not cognitive_manager:
            return jsonify({'error': get_message('error.server_error')}), 500
            
        agents = cognitive_manager.get_all_agents()
        return jsonify({
            'agents': agents,
            'total_count': len(agents),
            'active_count': cognitive_manager.get_active_agent_count()
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get agents: {e}")
        return jsonify({'error': get_message('error.server_error')}), 500

@app.route('/api/agents/<agent_id>/status', methods=['GET'])
@track_api_metrics
def get_agent_status(agent_id):
    """Get specific agent status and performance metrics"""
    try:
        if not cognitive_manager:
            return jsonify({'error': get_message('error.server_error')}), 500
            
        agent_status = cognitive_manager.get_agent_status(agent_id)
        if not agent_status:
            return jsonify({'error': get_message('error.resource.not_found')}), 404
            
        return jsonify(agent_status), 200
        
    except Exception as e:
        logger.error(f"Failed to get agent {agent_id} status: {e}")
        return jsonify({'error': get_message('error.server_error')}), 500

@app.route('/api/agents/<agent_id>/task', methods=['POST'])
@limiter.limit("10 per minute")
@track_api_metrics
def assign_task_to_agent(agent_id):
    """Assign a task to a specific cognitive agent"""
    try:
        if not cognitive_manager:
            return jsonify({'error': get_message('error.server_error')}), 500
            
        task_data = request.get_json()
        if not task_data or 'task_type' not in task_data:
            return jsonify({'error': get_message('api.error.invalid_request')}), 400
            
        result = cognitive_manager.assign_task(agent_id, task_data)
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Failed to assign task to agent {agent_id}: {e}")
        return jsonify({'error': get_message('error.server_error')}), 500

# Search endpoints
@app.route('/api/search', methods=['POST'])
@limiter.limit("30 per minute")
@track_api_metrics
def search():
    """Main multimodal search endpoint"""
    try:
        if not search_engine:
            return jsonify({'error': get_message('error.server_error')}), 500
            
        search_data = request.get_json()
        if not search_data or 'query' not in search_data:
            return jsonify({'error': get_message('api.error.invalid_request')}), 400
            
        # Extract search parameters
        query = search_data['query']
        search_type = search_data.get('type', 'comprehensive')
        modalities = search_data.get('modalities', ['text'])
        filters = search_data.get('filters', {})
        
        logger.info(f"Processing search: '{query}' (type: {search_type})")
        
        # Perform search with cognitive agents
        results = search_engine.search(
            query=query,
            search_type=search_type,
            modalities=modalities,
            filters=filters,
            use_cognitive_agents=True
        )
        
        return jsonify({
            'results': results,
            'query': query,
            'search_type': search_type,
            'modalities': modalities,
            'timestamp': datetime.utcnow().isoformat(),
            'processing_time': results.get('processing_time', 0)
        }), 200
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return jsonify({'error': get_message('error.server_error')}), 500

@app.route('/api/search/suggestions', methods=['POST'])
@limiter.limit("100 per minute")
@track_api_metrics
def search_suggestions():
    """Get search suggestions and auto-completions"""
    try:
        if not search_engine:
            return jsonify({'error': get_message('error.server_error')}), 500
            
        data = request.get_json()
        partial_query = data.get('query', '') if data else ''
        
        suggestions = search_engine.get_suggestions(partial_query)
        return jsonify({
            'suggestions': suggestions,
            'query': partial_query
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get suggestions: {e}")
        return jsonify({'error': get_message('error.server_error')}), 500

# Analytics and metrics endpoints
@app.route('/api/analytics/overview', methods=['GET'])
@track_api_metrics
def analytics_overview():
    """Get system analytics overview"""
    try:
        overview = {
            'total_searches': search_engine.get_search_count() if search_engine else 0,
            'active_agents': cognitive_manager.get_active_agent_count() if cognitive_manager else 0,
            'avg_response_time': search_engine.get_avg_response_time() if search_engine else 0,
            'search_accuracy': search_engine.get_accuracy_score() if search_engine else 0,
            'system_uptime': '0h 0m',  # TODO: Calculate actual uptime
            'error_rate': 0.01  # TODO: Calculate actual error rate
        }
        
        return jsonify(overview), 200
        
    except Exception as e:
        logger.error(f"Failed to get analytics: {e}")
        return jsonify({'error': get_message('error.server_error')}), 500

# Configuration endpoints
@app.route('/api/config/languages', methods=['GET'])
@track_api_metrics
def get_languages():
    """Get supported languages"""
    try:
        languages = get_supported_languages()
        return jsonify({
            'supported_languages': languages,
            'total_count': len(languages)
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get languages: {e}")
        return jsonify({'error': get_message('error.server_error')}), 500

# File upload endpoint
@app.route('/api/upload', methods=['POST'])
@limiter.limit("10 per minute")
@track_api_metrics
def upload_file():
    """Handle file uploads for multimodal analysis"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        # TODO: Implement file processing with search engine
        # For now, return mock response
        return jsonify({
            'file_id': 'mock-file-id',
            'filename': file.filename,
            'size': len(file.read()),
            'status': 'uploaded',
            'message': 'File uploaded successfully (mock implementation)'
        }), 200
        
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        return jsonify({'error': get_message('error.server_error')}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': get_message('error.resource.not_found')}), 404

@app.errorhandler(429)
def rate_limit_exceeded(error):
    return jsonify({'error': get_message('error.rate.limit.exceeded')}), 429

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': get_message('error.server_error')}), 500

# Metrics endpoint for Prometheus
@app.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus metrics endpoint"""
    try:
        from monitoring.prometheus_metrics import generate_latest
        return generate_latest(), 200, {'Content-Type': 'text/plain; charset=utf-8'}
    except ImportError:
        return "# Prometheus metrics not available\n", 200, {'Content-Type': 'text/plain'}

# Main application entry point
if __name__ == '__main__':
    # Development server configuration
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    
    logger.info(f"🚀 Starting HyperSearch AI Platform server...")
    logger.info(f"🌐 Environment: {os.getenv('FLASK_ENV', 'development')}")
    logger.info(f"🔗 Server: http://{host}:{port}")
    logger.info(f"🧠 Cognitive Agents: {'✅ Enabled' if cognitive_manager else '❌ Disabled'}")
    logger.info(f"🔍 Search Engine: {'✅ Enabled' if search_engine else '❌ Disabled'}")
    
    # Create logs directory if it doesn't exist
    Path('/app/logs').mkdir(parents=True, exist_ok=True)
    
    app.run(
        host=host,
        port=port,
        debug=debug_mode,
        threaded=True
    )