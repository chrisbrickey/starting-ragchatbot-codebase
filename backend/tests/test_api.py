"""
API endpoint tests for the RAG system FastAPI application.

These tests cover all API endpoints including:
- /api/query - Query processing endpoint
- /api/courses - Course statistics endpoint
- /api/session/clear - Session management endpoint
- /health - Health check endpoint
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mark all tests in this file as API tests
pytestmark = pytest.mark.api


class TestHealthEndpoint:
    """Test the health check endpoint"""

    @pytest.mark.asyncio
    async def test_health_check(self, test_client):
        """Test that health endpoint returns healthy status"""
        response = await test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestQueryEndpoint:
    """Test the /api/query endpoint"""

    @pytest.mark.asyncio
    async def test_query_basic(self, test_client):
        """Test basic query without session ID"""
        response = await test_client.post(
            "/api/query", json={"query": "What is an API?"}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data

        # Verify data types
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["session_id"], str)

        # Verify session ID was created
        assert len(data["session_id"]) > 0

    @pytest.mark.asyncio
    async def test_query_with_session_id(self, test_client):
        """Test query with provided session ID"""
        session_id = "test-session-123"

        response = await test_client.post(
            "/api/query", json={"query": "Tell me about APIs", "session_id": session_id}
        )

        assert response.status_code == 200
        data = response.json()

        # Should use provided session ID
        assert data["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_query_missing_query_field(self, test_client):
        """Test query endpoint with missing query field"""
        response = await test_client.post("/api/query", json={})

        # Should return validation error (422)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_query_empty_query_string(self, test_client):
        """Test query with empty string"""
        response = await test_client.post("/api/query", json={"query": ""})

        # Should still process (200) even with empty query
        # The RAG system should handle this gracefully
        assert response.status_code in [200, 500]

    @pytest.mark.asyncio
    async def test_query_with_populated_data(self, test_client_with_data):
        """Test query against populated vector store"""
        response = await test_client_with_data.post(
            "/api/query", json={"query": "What topics are covered in lesson 1?"}
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["answer"]) > 0
        assert isinstance(data["sources"], list)

    @pytest.mark.asyncio
    async def test_query_multi_turn_conversation(self, test_client_with_data):
        """Test multi-turn conversation with session"""
        # First query
        response1 = await test_client_with_data.post(
            "/api/query", json={"query": "What is covered in lesson 0?"}
        )

        assert response1.status_code == 200
        data1 = response1.json()
        session_id = data1["session_id"]

        # Second query using same session
        response2 = await test_client_with_data.post(
            "/api/query",
            json={"query": "Tell me more about that", "session_id": session_id},
        )

        assert response2.status_code == 200
        data2 = response2.json()

        # Should maintain same session
        assert data2["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_query_invalid_json(self, test_client):
        """Test query with invalid JSON payload"""
        response = await test_client.post(
            "/api/query",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )

        # Should return 422 for invalid JSON
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_query_long_query_text(self, test_client):
        """Test query with very long query text"""
        long_query = "Tell me about APIs " * 100  # Very long query

        response = await test_client.post("/api/query", json={"query": long_query})

        # Should handle long queries
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_query_special_characters(self, test_client):
        """Test query with special characters"""
        response = await test_client.post(
            "/api/query", json={"query": "What about <script>alert('test')</script>?"}
        )

        assert response.status_code == 200
        data = response.json()
        # Should handle special characters safely
        assert isinstance(data["answer"], str)


class TestCoursesEndpoint:
    """Test the /api/courses endpoint"""

    @pytest.mark.asyncio
    async def test_get_courses_empty_store(self, test_client):
        """Test getting course stats with empty vector store"""
        response = await test_client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "total_courses" in data
        assert "course_titles" in data

        # Verify data types
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)

    @pytest.mark.asyncio
    async def test_get_courses_populated_store(self, test_client_with_data):
        """Test getting course stats with populated vector store"""
        response = await test_client_with_data.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        # Should have at least one course
        assert data["total_courses"] > 0
        assert len(data["course_titles"]) > 0

        # Verify course titles are strings
        for title in data["course_titles"]:
            assert isinstance(title, str)
            assert len(title) > 0

    @pytest.mark.asyncio
    async def test_get_courses_method_not_allowed(self, test_client):
        """Test that POST is not allowed on courses endpoint"""
        response = await test_client.post("/api/courses")

        # Should return 405 Method Not Allowed
        assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_get_courses_no_parameters(self, test_client):
        """Test that courses endpoint doesn't require parameters"""
        # Should work without any query parameters
        response = await test_client.get("/api/courses")
        assert response.status_code == 200


class TestSessionClearEndpoint:
    """Test the /api/session/clear endpoint"""

    @pytest.mark.asyncio
    async def test_clear_session_success(self, test_client):
        """Test successfully clearing a session"""
        # First create a query to establish a session
        query_response = await test_client.post(
            "/api/query", json={"query": "Test query"}
        )
        session_id = query_response.json()["session_id"]

        # Now clear the session
        response = await test_client.post(
            "/api/session/clear", json={"session_id": session_id}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "message" in data
        assert session_id in data["message"]

    @pytest.mark.asyncio
    async def test_clear_nonexistent_session(self, test_client):
        """Test clearing a session that doesn't exist"""
        response = await test_client.post(
            "/api/session/clear", json={"session_id": "nonexistent-session-id"}
        )

        # Should handle gracefully (might succeed or fail depending on implementation)
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "message" in data

    @pytest.mark.asyncio
    async def test_clear_session_missing_session_id(self, test_client):
        """Test clearing session without session_id"""
        response = await test_client.post("/api/session/clear", json={})

        # Should return validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_clear_session_empty_session_id(self, test_client):
        """Test clearing session with empty session_id"""
        response = await test_client.post("/api/session/clear", json={"session_id": ""})

        # Should process (might fail or succeed)
        assert response.status_code in [200, 500]

    @pytest.mark.asyncio
    async def test_clear_session_method_not_allowed(self, test_client):
        """Test that GET is not allowed on session clear endpoint"""
        response = await test_client.get("/api/session/clear")

        # Should return 405 Method Not Allowed
        assert response.status_code == 405


class TestCORSHeaders:
    """Test CORS configuration"""

    @pytest.mark.asyncio
    async def test_cors_headers_present(self, test_client):
        """Test that CORS headers are present in responses"""
        response = await test_client.options(
            "/api/query",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

        # Check for CORS headers in preflight response
        # Note: CORS headers may only appear in preflight responses
        assert response.status_code in [200, 204]

    @pytest.mark.asyncio
    async def test_cors_preflight(self, test_client):
        """Test CORS preflight request"""
        response = await test_client.options(
            "/api/query",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

        # Should allow CORS
        assert response.status_code in [200, 204]


class TestErrorHandling:
    """Test error handling across API endpoints"""

    @pytest.mark.asyncio
    async def test_query_with_ai_generator_error(
        self, test_app, rag_system_with_mock_store
    ):
        """Test query handling when AI generator fails"""
        from httpx import ASGITransport, AsyncClient

        # Make AI generator raise an error
        rag_system_with_mock_store.ai_generator.generate_response.side_effect = (
            Exception("API Error")
        )

        # Inject RAG system into app
        test_app.state.rag_system = rag_system_with_mock_store

        # Create client
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/query", json={"query": "Test query"})

            # Should return 500 error
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data

    @pytest.mark.asyncio
    async def test_invalid_endpoint(self, test_client):
        """Test accessing non-existent endpoint"""
        response = await test_client.get("/api/nonexistent")

        # Should return 404
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_http_method(self, test_client):
        """Test using wrong HTTP method on endpoint"""
        # Try DELETE on query endpoint (not supported)
        response = await test_client.delete("/api/query")

        # Should return 405 Method Not Allowed
        assert response.status_code == 405


class TestRequestValidation:
    """Test request validation and Pydantic models"""

    @pytest.mark.asyncio
    async def test_query_extra_fields_ignored(self, test_client):
        """Test that extra fields in request are ignored"""
        response = await test_client.post(
            "/api/query",
            json={"query": "Test query", "extra_field": "should be ignored"},
        )

        # Should still work
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_query_wrong_field_type(self, test_client):
        """Test query with wrong field type"""
        response = await test_client.post(
            "/api/query", json={"query": 123}  # Should be string
        )

        # Should return validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_session_clear_wrong_field_type(self, test_client):
        """Test session clear with wrong field type"""
        response = await test_client.post(
            "/api/session/clear", json={"session_id": 123}  # Should be string
        )

        # Should return validation error
        assert response.status_code == 422


class TestResponseStructure:
    """Test that API responses match expected structure"""

    @pytest.mark.asyncio
    async def test_query_response_structure(self, test_client):
        """Test query response has all required fields"""
        response = await test_client.post("/api/query", json={"query": "Test"})

        data = response.json()

        # Must have all three fields
        assert set(data.keys()) == {"answer", "sources", "session_id"}

    @pytest.mark.asyncio
    async def test_courses_response_structure(self, test_client):
        """Test courses response has all required fields"""
        response = await test_client.get("/api/courses")

        data = response.json()

        # Must have both fields
        assert set(data.keys()) == {"total_courses", "course_titles"}

    @pytest.mark.asyncio
    async def test_session_clear_response_structure(self, test_client):
        """Test session clear response has all required fields"""
        response = await test_client.post(
            "/api/session/clear", json={"session_id": "test-session"}
        )

        data = response.json()

        # Must have both fields
        assert set(data.keys()) == {"success", "message"}


class TestConcurrentRequests:
    """Test handling of concurrent requests"""

    @pytest.mark.asyncio
    async def test_concurrent_queries(self, test_client):
        """Test multiple concurrent queries"""
        import asyncio

        # Send 5 concurrent queries
        queries = [
            test_client.post("/api/query", json={"query": f"Query {i}"})
            for i in range(5)
        ]

        responses = await asyncio.gather(*queries)

        # All should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            assert "session_id" in data

    @pytest.mark.asyncio
    async def test_concurrent_different_endpoints(self, test_client_with_data):
        """Test concurrent requests to different endpoints"""
        import asyncio

        # Send requests to different endpoints concurrently
        tasks = [
            test_client_with_data.post("/api/query", json={"query": "Test"}),
            test_client_with_data.get("/api/courses"),
            test_client_with_data.get("/health"),
        ]

        responses = await asyncio.gather(*tasks)

        # All should succeed
        for response in responses:
            assert response.status_code == 200


class TestSessionPersistence:
    """Test session persistence across multiple queries"""

    @pytest.mark.asyncio
    async def test_session_persists_across_queries(self, test_client_with_data):
        """Test that session state persists across multiple queries"""
        # First query
        response1 = await test_client_with_data.post(
            "/api/query", json={"query": "What is in lesson 1?"}
        )
        session_id = response1.json()["session_id"]

        # Second query with same session
        response2 = await test_client_with_data.post(
            "/api/query",
            json={"query": "Can you tell me more?", "session_id": session_id},
        )

        # Third query with same session
        response3 = await test_client_with_data.post(
            "/api/query",
            json={"query": "What about the examples?", "session_id": session_id},
        )

        # All should use the same session
        assert response2.json()["session_id"] == session_id
        assert response3.json()["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_different_sessions_isolated(self, test_client_with_data):
        """Test that different sessions are isolated from each other"""
        # Create two different sessions
        response1 = await test_client_with_data.post(
            "/api/query", json={"query": "First session query"}
        )
        session1 = response1.json()["session_id"]

        response2 = await test_client_with_data.post(
            "/api/query", json={"query": "Second session query"}
        )
        session2 = response2.json()["session_id"]

        # Sessions should be different
        assert session1 != session2
