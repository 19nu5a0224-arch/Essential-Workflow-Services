"""
Test script for n8n async wrapper functionality

This script tests the async wrapper implementation for n8n workflows API
that accepts *args and **kwargs parameters.
"""

import asyncio
import httpx
from typing import Dict, Any


async def test_async_wrapper_endpoints(base_url: str = "http://localhost:8000"):
    """Test all async wrapper endpoints"""

    async with httpx.AsyncClient() as client:
        print("Testing n8n async wrapper endpoints...")

        # Test GET request
        print("\n1. Testing GET /features/n8n-workflows/wrapper")
        try:
            response = await client.get(f"{base_url}/features/n8n-workflows/wrapper")
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print("GET test passed")
            else:
                print(f"GET test failed: {response.text}")
        except Exception as e:
            print(f"GET test error: {e}")

        # Test GET with parameters
        print("\n2. Testing GET with query parameters")
        try:
            response = await client.get(
                f"{base_url}/features/n8n-workflows/wrapper",
                params={
                    "limit": 10,
                    "includeData": "false"
                }
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print("GET with parameters test passed")
            else:
                print(f"GET with parameters test failed: {response.text}")
        except Exception as e:
            print(f"GET with parameters test error: {e}")

        # Test POST request
        print("\n3. Testing POST /features/n8n-workflows/wrapper")
        try:
            workflow_data = {
                "name": "Test Workflow",
                "nodes": [],
                "connections": {},
                "settings": {
                    "executionOrder": "v1",
                    "timezone": "UTC"
                }
            }
            response = await client.post(
                f"{base_url}/features/n8n-workflows/wrapper",
                json=workflow_data
            )
            print(f"Status: {response.status_code}")
            if response.status_code in [200, 201]:
                print("POST test passed")
            else:
                print(f"POST test failed: {response.text}")
        except Exception as e:
            print(f"POST test error: {e}")

        # Test PUT request with custom endpoint
        print("\n4. Testing PUT with custom endpoint")
        try:
            response = await client.put(
                f"{base_url}/features/n8n-workflows/wrapper",
                json=[{"id": "test_tag_id"}],
                params={"endpoint": "/workflows/test_workflow_id/tags"}
            )
            print(f"Status: {response.status_code}")
            if response.status_code in [200, 201]:
                print("PUT test passed")
            else:
                print(f"PUT test failed: {response.text}")
        except Exception as e:
            print(f"PUT test error: {e}")

        # Test DELETE request
        print("\n5. Testing DELETE with custom endpoint")
        try:
            response = await client.delete(
                f"{base_url}/features/n8n-workflows/wrapper",
                params={"endpoint": "/workflows/test_workflow_id"}
            )
            print(f"Status: {response.status_code}")
            if response.status_code in [200, 204]:
                print("DELETE test passed")
            else:
                print(f"DELETE test failed: {response.text}")
        except Exception as e:
            print(f"DELETE test error: {e}")

        # Test original endpoint (backward compatibility)
        print("\n6. Testing original GET /features/n8n-workflows")
        try:
            response = await client.get(f"{base_url}/features/n8n-workflows")
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print("Original endpoint test passed")
            else:
                print(f"Original endpoint test failed: {response.text}")
        except Exception as e:
            print(f"Original endpoint test error: {e}")


async def test_n8n_service_wrapper():
    """Test the N8NService async wrapper directly"""
    print("\n7. Testing N8NService async wrapper directly")

    try:
        from app.services.n8n_service import N8NService
        n8n_service = N8NService()

        # Test GET request
        result = await n8n_service.async_wrapper(
            method="GET",
            endpoint="/workflows"
        )
        print(f"Direct wrapper GET result: {result}")

        # Test with parameters
        result = await n8n_service.async_wrapper(
            method="GET",
            endpoint="/workflows",
            limit=5,
            includeData="false"
        )
        print(f"Direct wrapper GET with params result: {result}")

    except Exception as e:
        print(f"Direct wrapper test error: {e}")


def print_usage_examples():
    """Print usage examples for the async wrapper"""
    print("\n" + "="*60)
    print("ASYNC WRAPPER USAGE EXAMPLES")
    print("="*60)

    print("""
### Python Usage:
```python
import httpx

# Get all workflows
response = await httpx.get("/features/n8n-workflows/wrapper")

# Get workflows with parameters
response = await httpx.get(
    "/features/n8n-workflows/wrapper",
    params={"limit": 10, "includeData": "false"}
)

# Create workflow
response = await httpx.post(
    "/features/n8n-workflows/wrapper",
    json={
        "name": "My Workflow",
        "nodes": [...],
        "connections": {...}
    }
)

# Update workflow tags
response = await httpx.put(
    "/features/n8n-workflows/wrapper",
    json=[{"id": "tag_id"}],
    params={"endpoint": "/workflows/{id}/tags"}
)

# Delete workflow
response = await httpx.delete(
    "/features/n8n-workflows/wrapper",
    params={"endpoint": "/workflows/{id}"}
)
```

### cURL Examples:
```bash
# Get all workflows
curl -X GET "http://localhost:8000/features/n8n-workflows/wrapper"

# Get with parameters
curl -X GET "http://localhost:8000/features/n8n-workflows/wrapper?limit=10&includeData=false"

# Create workflow
curl -X POST "http://localhost:8000/features/n8n-workflows/wrapper" \\
  -H "Content-Type: application/json" \\
  -d '{"name": "Test", "nodes": [], "connections": {}}'

# Custom endpoint
curl -X PUT "http://localhost:8000/features/n8n-workflows/wrapper?endpoint=/workflows/123/tags" \\
  -H "Content-Type: application/json" \\
  -d '[{"id": "tag_id"}]'
```
""")


async def main():
    """Main test function"""
    print("N8N Async Wrapper Test Script")
    print("=" * 40)

    await test_async_wrapper_endpoints()
    await test_n8n_service_wrapper()
    print_usage_examples()

    print("\nTest completed!")


if __name__ == "__main__":
    asyncio.run(main())
```

This test script provides comprehensive testing for the new async wrapper functionality. It includes:

1. **HTTP endpoint testing** - Tests all HTTP methods (GET, POST, PUT, DELETE)
2. **Parameter handling** - Tests query parameters and request bodies
3. **Custom endpoints** - Tests different n8n API endpoints
4. **Backward compatibility** - Tests the original endpoint still works
5. **Direct service testing** - Tests the N8NService wrapper directly
6. **Usage examples** - Provides Python and cURL examples

The script will help verify that the async wrapper properly handles the `*args` and `**kwargs` parameters as shown in your Swagger documentation.
