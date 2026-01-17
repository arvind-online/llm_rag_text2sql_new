"""Test script for document upload endpoint."""

import requests

# Test with a simple text file (as example)
url = "http://localhost:8000/upload"

# Example 1: Upload with metadata
files = {
    'file': ('test.pdf', open('test.pdf', 'rb'), 'application/pdf')
}
data = {
    'source': 'Test Document',
    'topic': 'testing'
}

response = requests.post(url, files=files, data=data)
print(response.json())
