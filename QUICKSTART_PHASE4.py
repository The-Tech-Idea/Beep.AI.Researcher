"""
Quick Start Guide for AI Template System (Phase 4)
==================================================

Follow these steps to get the AI template modal system running.
"""

# Step 1: Install Dependencies
print("Step 1: Installing required packages...")
print("""
pip install python-docx>=0.8.11
pip install weasyprint>=59.0
pip install markdown>=3.4.0
""")

# Step 2: Run Database Migration
print("\nStep 2: Running database migration...")
print("""
# If using Alembic:
alembic upgrade head

# Or manually in Python:
python
>>> from app import create_app
>>> from app.database import db
>>> app = create_app()
>>> with app.app_context():
...     db.create_all()
""")

# Step 3: Seed AI Templates
print("\nStep 3: Seeding AI templates...")
print("""
python seed_ai_templates.py

# This creates 12 system templates:
# - Academic Writing: Literature Review, Introduction, Method, Discussion, Conclusion, Abstract
# - Analysis: Summarize, Critique, Opposite View
# - Transcription: Rewrite, Historic Overview
""")

# Step 4: Configure AI Service
print("\nStep 4: Configuring AI service...")
print("""
# Option A: Use Mock Service (for testing)
# In your app initialization or route handler:
from app.services.ai_service import use_mock_service
use_mock_service()

# Option B: Connect to Beep.AI.Server
# Ensure Beep.AI.Server is running on http://localhost:5000
# The AI service will call /v1/chat/completions endpoint
""")

# Step 5: Start Application
print("\nStep 5: Starting the application...")
print("""
python run.py

# Or with specific settings:
FLASK_ENV=development python run.py
""")

# Step 6: Test the Modal
print("\nStep 6: Testing AI template modal...")
print("""
1. Open browser to http://localhost:5000
2. Login to your account
3. Navigate to Dashboard
4. Click any "AI Actions" card (e.g., "Literature Review")
5. Modal should open with template sidebar
6. Select a template from sidebar
7. Fill in the dynamic form fields
8. Adjust Advanced AI Settings (creativity, length, etc.)
9. Click "Generate with AI" button
10. Watch real-time streaming progress
11. Review generated content
12. Test export options:
    - Click Export dropdown
    - Try "Download as Markdown"
    - Try "Download as DOCX"
    - Try "Download as PDF"
    - Try "Copy to Clipboard"
13. Test workbook saving:
    - Click "Save to Workbook" button
    - Select existing workbook or create new
    - Enter document title and notes
    - Click "Save"
""")

# Step 7: Verify Database Records
print("\nStep 7: Verifying database records...")
print("""
python
>>> from app import create_app
>>> from app.database import db
>>> from app.models.researcher.ai_templates import AITemplate, AIWorkflowExecution, AIWorkbook
>>> app = create_app()
>>> with app.app_context():
...     # Check templates
...     templates = AITemplate.query.all()
...     print(f"Templates: {len(templates)}")  # Should be 12
...     
...     # Check executions
...     executions = AIWorkflowExecution.query.all()
...     print(f"Executions: {len(executions)}")
...     
...     # Check latest execution
...     if executions:
...         latest = executions[-1]
...         print(f"Status: {latest.status}")
...         print(f"Tokens: {latest.tokens_used}")
...         print(f"Result: {latest.result_text[:100]}...")
""")

# Step 8: Test API Endpoints Directly
print("\nStep 8: Testing API endpoints...")
print("""
# Get template by ID
curl http://localhost:5000/researcher/ai/templates/1

# Create execution
curl -X POST http://localhost:5000/researcher/ai/execute \\
  -H "Content-Type: application/json" \\
  -d '{
    "template_id": 1,
    "inputs": {
      "research_question": "What is AI?",
      "num_sources": 5,
      "_creativity": 70,
      "_maxLength": 500,
      "_citationStyle": "APA",
      "_tone": "academic"
    }
  }'

# Stream generation (use -N for no buffering)
curl -N http://localhost:5000/researcher/ai/stream/1

# Export as markdown
curl http://localhost:5000/researcher/ai/export/1/markdown -o result.md

# Export as DOCX
curl http://localhost:5000/researcher/ai/export/1/docx -o result.docx

# Export as PDF
curl http://localhost:5000/researcher/ai/export/1/pdf -o result.pdf

# List workbooks
curl http://localhost:5000/researcher/ai/workbooks

# Browse templates
curl http://localhost:5000/researcher/ai/browse?category=writing
""")

# Troubleshooting
print("\n" + "="*60)
print("TROUBLESHOOTING")
print("="*60)

print("""
Issue: Dashboard template modal doesn't open
Solution: The legacy dashboard AI template modal is no longer part of the live shell
  - Use the current project report and writing flows instead of the retired dashboard modal
  - If a template modal is reintroduced, wire it through dedicated live assets instead of the removed legacy `ai_template_modal.js` path

Issue: Templates not showing
Solution: Run seed script again
  python seed_ai_templates.py

Issue: Streaming not working
Solution: Check SSE support
  - Browser must support EventSource API
  - Check network tab for SSE connection
  - Verify Flask-SSE or standard Response streaming works

Issue: Export fails
Solution: Check dependencies
  pip install python-docx weasyprint markdown
  
  For weasyprint on Windows:
  - Install GTK3 runtime from https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
  
Issue: Mock service not working
Solution: Call use_mock_service()
  from app.services.ai_service import use_mock_service
  use_mock_service()

Issue: 500 Internal Server Error
Solution: Check Flask logs
  - Enable debug mode: FLASK_DEBUG=1 python run.py
  - Check database connection
  - Verify all models imported in app/__init__.py

Issue: Database column missing
Solution: Re-run migration
  alembic revision --autogenerate -m "update ai models"
  alembic upgrade head
""")

# Development Tips
print("\n" + "="*60)
print("DEVELOPMENT TIPS")
print("="*60)

print("""
1. Browser DevTools
   - Network tab: Monitor SSE streaming
   - Console: Check for JavaScript errors
   - Application tab: Check session storage

2. Flask Debug Mode
   FLASK_DEBUG=1 python run.py
   - Auto-reload on code changes
   - Detailed error pages
   - SQL query logging

3. Database Inspection
   - Use SQLite browser for app.db
   - Check execution records after each generation
   - Verify foreign key relationships

4. Mock vs Live AI
   - Start with mock service for fast development
   - Switch to live LLM after UI is stable
   - Monitor token usage for cost control

5. Template Customization
   - Edit seed_ai_templates.py
   - Modify prompt_template (Jinja2 syntax)
   - Update input_schema (JSON schema format)
   - Re-run seed script to update

6. Styling Adjustments
   - Embedded CSS in ai_template_modal.html
   - Design tokens in design-system.css
   - Bootstrap utilities available

7. Performance Monitoring
   - Check execution_time_ms in database
   - Monitor token_used for efficiency
   - Test with various creativity levels

8. Error Handling
   - Check error_message in executions table
   - Monitor Flask logs for exceptions
   - Use try/except in custom templates
""")

# Next Steps
print("\n" + "="*60)
print("NEXT STEPS")
print("="*60)

print("""
✅ Phase 4 Complete: AI Template Modal

Next: Phase 5 - Workbook Rich Text Editor
- Quill.js or TipTap integration
- Formatting toolbar
- Version history
- Collaboration features
- Auto-save functionality

To start Phase 5:
1. Review PHASE_5_PLAN.md (to be created)
2. Choose rich text editor (Quill.js recommended)
3. Design workbook editor UI
4. Implement auto-save
5. Add version control
""")

print("\n" + "="*60)
print("Ready to test! Start with Step 1 above.")
print("="*60)
