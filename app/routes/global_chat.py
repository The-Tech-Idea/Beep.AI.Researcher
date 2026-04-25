"""Global AI Chat API - Works without project context."""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from app.config import is_feature_enabled
from app.services.beep_ai_client import is_configured, chat_reply

global_chat_bp = Blueprint('global_chat', __name__)


@global_chat_bp.route('/api/chat', methods=['POST'])
@login_required
def chat():
    """
    Global chat endpoint - AI assistant without project context.
    
    Request:
        {
            "message": "Your question here",
            "session_id": null  // Optional for conversation continuity
        }
    
    Response:
        {
            "success": true,
            "reply": "AI response text",
            "session_id": "..."
        }
    """
    data = request.get_json() or {}
    message = (data.get('message') or '').strip()
    session_id = data.get('session_id')
    
    if not message:
        return jsonify({
            'success': False,
            'error': 'Message is required'
        }), 400

    if not is_feature_enabled("chat_enabled"):
        return jsonify({
            'success': False,
            'error': 'Chat feature is disabled by administrator settings.'
        }), 403
    
    # Check if AI Server is configured
    if not is_configured():
        return jsonify({
            'success': False,
            'error': 'AI Server is not configured. Go to Admin → Settings to configure.'
        }), 503
    
    # Build conversation context
    # Get or create session history from local storage (client-side)
    # For now, we just send single message
    
    user_id = current_user.id if current_user.is_authenticated else None
    user_role = 'admin' if current_user.is_admin else 'user'
    
    # System prompt for research assistant
    system_prompt = """You are an AI research assistant for Beep.AI.Researcher. 
You help researchers with their qualitative and quantitative research tasks.
You can help with:
- Summarizing research documents
- Analyzing data patterns
- Suggesting research methodologies
- Answering questions about research best practices
- Helping with coding and thematic analysis
Be concise, accurate, and helpful."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message}
    ]
    
    # Call AI Server
    ok, reply = chat_reply(
        messages,
        user_id=user_id,
        user_role=user_role
    )
    
    if ok:
        return jsonify({
            'success': True,
            'reply': reply,
            'session_id': session_id  # Client manages session
        })
    else:
        return jsonify({
            'success': False,
            'error': reply or 'Failed to get response from AI Server'
        }), 500


@global_chat_bp.route('/api/chat/status', methods=['GET'])
@login_required
def chat_status():
    """Check if chat is available."""
    return jsonify({
        'enabled': is_feature_enabled("chat_enabled"),
        'configured': is_configured(),
        'user_id': current_user.id if current_user.is_authenticated else None
    })
