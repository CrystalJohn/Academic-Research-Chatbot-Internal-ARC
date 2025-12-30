#!/usr/bin/env python3
"""
Quick test to verify Converse API is available in boto3
"""

import sys

print("🔍 Checking Converse API availability...")
print("=" * 60)

# Check boto3 version
try:
    import boto3
    print(f"✅ boto3 version: {boto3.__version__}")
except ImportError:
    print("❌ boto3 not installed")
    sys.exit(1)

# Check if converse method exists
try:
    client = boto3.client('bedrock-runtime', region_name='ap-southeast-1')
    
    if hasattr(client, 'converse'):
        print("✅ converse() method is available")
    else:
        print("❌ converse() method NOT available")
        print("   → Need to upgrade boto3: pip install boto3>=1.35.0")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Error creating client: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ Converse API is ready!")
print("=" * 60)
print("\nYou can now:")
print("1. Restart backend: cd backend && uvicorn app.main:app --reload")
print("2. Test endpoint: POST /api/chat/agentic")
print("3. Run sample: python samples/test_agentic_rag.py")
