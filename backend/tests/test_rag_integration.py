"""
Integration tests for RAG system to identify query handling failures.
"""
import pytest
import sys
import os
import tempfile
import shutil
import gc
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from rag_system import RAGSystem
from config import Config
from models import Course, Lesson, CourseChunk


@pytest.fixture
def test_config(request):
    """Create a test configuration with temporary paths.

    Uses request.addfinalizer to ensure temp directory cleanup happens last.
    """
    temp_dir = tempfile.mkdtemp()

    config = Config()
    config.CHROMA_PATH = os.path.join(temp_dir, "chroma_test")
    config.ANTHROPIC_API_KEY = "test_key_for_testing"
    config.MAX_RESULTS = 3
    config.MAX_HISTORY = 2

    def cleanup():
        gc.collect()
        shutil.rmtree(temp_dir, ignore_errors=True)

    request.addfinalizer(cleanup)

    return config


@pytest.fixture
def rag_system_with_mock_ai(test_config):
    """Create RAG system with mocked AI generator"""
    rag = RAGSystem(test_config)

    # Mock the AI generator to avoid real API calls
    mock_ai = Mock()
    mock_ai.generate_response.return_value = "This is a test response about API calls."
    rag.ai_generator = mock_ai

    yield rag

    # Cleanup before test_config finalizer runs
    del rag
    gc.collect()


@pytest.fixture
def rag_system_populated(test_config, sample_course, sample_chunks):
    """Create RAG system with populated vector store"""
    rag = RAGSystem(test_config)

    # Populate with test data
    rag.vector_store.add_course_metadata(sample_course)
    rag.vector_store.add_course_content(sample_chunks)

    # Mock AI to avoid API calls
    mock_ai = Mock()
    mock_ai.generate_response.return_value = "Based on the course content, here's the answer."
    rag.ai_generator = mock_ai

    yield rag

    # Cleanup before test_config finalizer runs
    del rag
    gc.collect()


class TestRAGSystemInitialization:
    """Test RAG system initialization"""

    def test_initialization(self, rag_system_with_mock_store):
        """Test that RAG system initializes all components"""
        rag = rag_system_with_mock_store

        assert rag.document_processor is not None
        assert rag.vector_store is not None
        assert rag.ai_generator is not None
        assert rag.session_manager is not None
        assert rag.tool_manager is not None
        assert rag.search_tool is not None

    def test_search_tool_registered(self, rag_system_with_mock_store):
        """Test that search tool is registered with tool manager"""
        rag = rag_system_with_mock_store

        tools = rag.tool_manager.get_tool_definitions()
        assert len(tools) > 0
        assert tools[0]["name"] == "search_course_content"


class TestRAGSystemQueryWithEmptyStore:
    """Test query behavior with empty vector store"""

    def test_query_empty_store(self, rag_system_with_mock_ai):
        """Test querying when vector store has no data"""
        # Vector store is empty after initialization
        response, sources = rag_system_with_mock_ai.query("What are API calls?")

        # Should still get a response (even if it's about no content found)
        assert isinstance(response, str)
        assert len(response) > 0

        # Sources should be a list (might be empty)
        assert isinstance(sources, list)

    def test_query_empty_store_with_session(self, rag_system_with_mock_ai):
        """Test querying empty store with session tracking"""
        session_id = rag_system_with_mock_ai.session_manager.create_session()

        response, sources = rag_system_with_mock_ai.query(
            "Tell me about API calls",
            session_id=session_id
        )

        assert isinstance(response, str)
        assert len(response) > 0

        # Session should have the exchange recorded
        history = rag_system_with_mock_ai.session_manager.get_conversation_history(session_id)
        assert history is not None
        assert "API calls" in history


class TestRAGSystemQueryWithData:
    """Test query behavior with populated vector store"""

    def test_query_with_content(self, rag_system_populated):
        """Test querying when vector store has content"""
        response, sources = rag_system_populated.query("Tell me about API calls")

        assert isinstance(response, str)
        assert len(response) > 0

        # Should get sources
        assert isinstance(sources, list)

    def test_query_triggers_tool_call(self, rag_system_populated):
        """Test that content queries trigger tool usage"""
        response, sources = rag_system_populated.query("What does lesson 1 teach?")

        # AI generator should have been called with tools
        call_args = rag_system_populated.ai_generator.generate_response.call_args

        assert call_args is not None
        assert "tools" in call_args.kwargs or len(call_args.args) > 2

    def test_query_passes_tool_manager(self, rag_system_populated):
        """Test that tool manager is passed to AI generator"""
        response, sources = rag_system_populated.query("Search for API information")

        call_args = rag_system_populated.ai_generator.generate_response.call_args

        # Should pass tool_manager
        assert "tool_manager" in call_args.kwargs
        assert call_args.kwargs["tool_manager"] is not None


class TestRAGSystemSessionManagement:
    """Test session management in queries"""

    def test_query_creates_session_if_none(self, rag_system_populated):
        """Test that query works without providing session_id"""
        response, sources = rag_system_populated.query("Test query")

        # Should complete without error
        assert isinstance(response, str)

    def test_query_with_existing_session(self, rag_system_populated):
        """Test query with existing session uses history"""
        session_id = rag_system_populated.session_manager.create_session()

        # First query
        response1, _ = rag_system_populated.query("What is an API?", session_id)

        # Second query
        response2, _ = rag_system_populated.query("Tell me more", session_id)

        # History should be passed on second call
        second_call_args = rag_system_populated.ai_generator.generate_response.call_args

        assert "conversation_history" in second_call_args.kwargs
        # History should contain previous exchange
        history = second_call_args.kwargs["conversation_history"]
        if history:
            assert "API" in history

    def test_query_updates_session_history(self, rag_system_populated):
        """Test that queries update session history"""
        session_id = rag_system_populated.session_manager.create_session()

        query_text = "What are prompt caching benefits?"
        response, _ = rag_system_populated.query(query_text, session_id)

        # Check history was updated
        history = rag_system_populated.session_manager.get_conversation_history(session_id)
        assert history is not None
        assert query_text in history


class TestRAGSystemSourceTracking:
    """Test source tracking functionality"""

    def test_query_returns_sources(self, rag_system_populated):
        """Test that queries return source information"""
        response, sources = rag_system_populated.query("API calls")

        assert isinstance(sources, list)
        # Sources format depends on tool execution

    def test_sources_reset_between_queries(self, rag_system_populated):
        """Test that sources are reset between different queries"""
        # First query
        response1, sources1 = rag_system_populated.query("API calls")

        # Second query
        response2, sources2 = rag_system_populated.query("Different topic")

        # Each should have its own sources
        # (might be empty if no search was triggered)
        assert isinstance(sources1, list)
        assert isinstance(sources2, list)


class TestRAGSystemDocumentLoading:
    """Test document loading functionality"""

    def test_add_course_folder(self, rag_system_with_mock_store, tmp_path):
        """Test loading courses from a folder"""
        rag = rag_system_with_mock_store

        # Configure mock to show no existing courses for this test
        rag.vector_store.get_existing_course_titles.return_value = []

        # Create test document
        test_file = tmp_path / "test_course.txt"
        test_file.write_text("""Course Title: Test Course
Course Link: https://example.com
Course Instructor: Test Instructor

Lesson 0: Introduction
This is lesson content about APIs and tools.
""")

        courses, chunks = rag.add_course_folder(str(tmp_path))

        assert courses == 1
        assert chunks > 0

        # Verify course was added (via mock calls)
        rag.vector_store.add_course_metadata.assert_called()
        rag.vector_store.add_course_content.assert_called()

    def test_add_course_folder_empty(self, rag_system_with_mock_store, tmp_path):
        """Test loading from empty folder"""
        rag = rag_system_with_mock_store

        courses, chunks = rag.add_course_folder(str(tmp_path))

        assert courses == 0
        assert chunks == 0

    def test_add_course_folder_nonexistent(self, rag_system_with_mock_store):
        """Test loading from nonexistent folder"""
        rag = rag_system_with_mock_store

        courses, chunks = rag.add_course_folder("/nonexistent/path")

        assert courses == 0
        assert chunks == 0


class TestRAGSystemErrorHandling:
    """Test error handling in RAG system"""

    def test_query_with_ai_error(self, rag_system_populated):
        """Test handling when AI generation fails"""
        # Make AI generator raise an error
        rag_system_populated.ai_generator.generate_response.side_effect = Exception("API Error")

        with pytest.raises(Exception) as exc_info:
            rag_system_populated.query("Test query")

        assert "API Error" in str(exc_info.value)

    def test_query_with_invalid_session(self, rag_system_populated):
        """Test querying with invalid session ID"""
        # Should handle gracefully - create new session or use no history
        response, sources = rag_system_populated.query(
            "Test query",
            session_id="invalid_session_id"
        )

        assert isinstance(response, str)


class TestRAGSystemAnalytics:
    """Test analytics functionality"""

    def test_get_course_analytics_empty(self, rag_system_with_mock_store):
        """Test analytics with empty vector store"""
        rag = rag_system_with_mock_store

        # Configure mock for empty store
        rag.vector_store.get_course_count.return_value = 0
        rag.vector_store.get_existing_course_titles.return_value = []

        analytics = rag.get_course_analytics()

        assert "total_courses" in analytics
        assert analytics["total_courses"] == 0
        assert "course_titles" in analytics
        assert len(analytics["course_titles"]) == 0

    def test_get_course_analytics_populated(self, rag_system_populated):
        """Test analytics with populated vector store"""
        analytics = rag_system_populated.get_course_analytics()

        assert "total_courses" in analytics
        assert analytics["total_courses"] > 0
        assert "course_titles" in analytics
        assert len(analytics["course_titles"]) > 0


class TestRAGSystemRealScenarios:
    """Test realistic usage scenarios"""

    def test_content_question_flow(self, rag_system_populated):
        """Test complete flow for content-related question"""
        # This mimics what happens when user asks about course content
        query = "What topics are covered in lesson 1?"

        response, sources = rag_system_populated.query(query)

        # Should get a response
        assert isinstance(response, str)
        assert len(response) > 0

        # Should get sources (if tool was used)
        assert isinstance(sources, list)

        # AI should have been called
        assert rag_system_populated.ai_generator.generate_response.called

    def test_general_question_flow(self, rag_system_populated):
        """Test flow for general knowledge question"""
        query = "What is an API?"

        response, sources = rag_system_populated.query(query)

        # Should still get a response
        assert isinstance(response, str)
        assert len(response) > 0

    def test_multi_turn_conversation(self, rag_system_populated):
        """Test multi-turn conversation with context"""
        session_id = rag_system_populated.session_manager.create_session()

        # Turn 1
        response1, _ = rag_system_populated.query(
            "What is covered in lesson 1?",
            session_id
        )

        # Turn 2 - follow-up question
        response2, _ = rag_system_populated.query(
            "Can you elaborate on that?",
            session_id
        )

        # Both should complete
        assert isinstance(response1, str)
        assert isinstance(response2, str)

        # History should contain both exchanges
        history = rag_system_populated.session_manager.get_conversation_history(session_id)
        assert history is not None