#!/usr/bin/env python
"""Update SESSION_TIMEOUT in the database"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'daybook_lite.settings')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'daybook_lite'))

django.setup()

from manager.models import Configuration

# Update or create SESSION_TIMEOUT
config, created = Configuration.objects.get_or_create(
    key='SESSION_TIMEOUT',
    defaults={'group': 'APP', 'value': '1800'}
)

if not created:
    config.value = '1800'
    config.save()
    print(f"✓ Updated SESSION_TIMEOUT to 1800 seconds (30 minutes)")
else:
    print(f"✓ Created SESSION_TIMEOUT with value 1800 seconds (30 minutes)")

# Verify
current_value = Configuration.get_value('SESSION_TIMEOUT')
print(f"Current SESSION_TIMEOUT in database: {current_value} seconds")
