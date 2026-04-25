import sys
import os

# Add the app directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app
from flask import render_template
from app.models.researcher import ResearchProject

app = create_app()
with app.app_context():
    p = ResearchProject.query.first()
    try:
        # Mock the 't' function if it's injected by context processors
        render_template('project/report.html', project=p, report=None, base_template='base.html')
        print("Template rendered successfully.")
    except Exception as e:
        import traceback
        traceback.print_exc()
