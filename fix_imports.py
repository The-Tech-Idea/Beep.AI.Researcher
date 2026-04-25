#!/usr/bin/env python
"""Fix imports in test_monitoring.py"""

# Read file
with open('tests/test_monitoring.py', 'r') as f:
    content = f.read()

# Replace all occurrences
new_content = content.replace('from app import db', 'from app.database import db')

# Write back
with open('tests/test_monitoring.py', 'w') as f:
    f.write(new_content)

# Count replacements
count = content.count('from app import db')
print(f'Replaced {count} occurrences')
