"""
Landing Page Routes for Beep.AI.Researcher
Handles public-facing landing page and onboarding
"""

from flask import Blueprint, render_template, redirect, url_for, session

landing_bp = Blueprint('landing', __name__)


@landing_bp.route('/')
def index():
    """
    Main landing page
    If user is already logged in, redirect to dashboard
    """
    if 'user_id' in session:
        return redirect(url_for('researcher.index'))
    
    return render_template('landing.html')


@landing_bp.route('/design-demo')
def design_demo():
    """
    Design system demonstration page
    Shows all UI components and design tokens
    """
    return render_template('design_system_demo.html')
