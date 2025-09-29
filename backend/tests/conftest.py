"""
Test fixtures and configuration for RAG system tests.
"""
import pytest
import tempfile
import shutil
import gc
from unittest.mock import Mock
from typing import Dict, Any, List
import sys
import os

# Add backend directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from models import Course, Lesson, CourseChunk
from vector_store import VectorStore, SearchResults
from search_tools import CourseSearchTool, ToolManager
from ai_generator import AIGenerator


@pytest.fixture(scope="function")
def temp_chroma_dir(request):
    """Create a temporary directory for ChromaDB during tests.

    Uses request.addfinalizer to ensure cleanup happens AFTER all dependent fixtures.
    """
    temp_dir = tempfile.mkdtemp()

    def cleanup():
        # Force garbage collection to release ChromaDB connections
        gc.collect()
        # Use ignore_errors to handle any lingering file locks
        shutil.rmtree(temp_dir, ignore_errors=True)

    # Register cleanup to run after test and all fixtures
    request.addfinalizer(cleanup)

    return temp_dir


@pytest.fixture
def sample_course():
    """Create a sample course with lessons"""
    return Course(
        title="Building Towards Computer Use with Anthropic",
        course_link="https://www.deeplearning.ai/short-courses/building-toward-computer-use-with-anthropic/",
        instructor="Colt Steele",
        lessons=[
            Lesson(
                lesson_number=0,
                title="Introduction",
                lesson_link="https://learn.deeplearning.ai/courses/building-toward-computer-use-with-anthropic/lesson/a6k0z/introduction"
            ),
            Lesson(
                lesson_number=1,
                title="Getting Started with Claude API",
                lesson_link="https://learn.deeplearning.ai/courses/building-toward-computer-use-with-anthropic/lesson/b7l1a/getting-started"
            )
        ]
    )


@pytest.fixture
def sample_chunks(sample_course):
    """Create sample course chunks"""
    return [
        CourseChunk(
            content="Course Building Towards Computer Use with Anthropic Lesson 0 content: Welcome to Building Toward Computer Use with Anthropic. Built in partnership with Anthropic and taught by Colt Steele.",
            course_title=sample_course.title,
            lesson_number=0,
            chunk_index=0
        ),
        CourseChunk(
            content="This course covers tool calling, prompt caching, and computer use capabilities.",
            course_title=sample_course.title,
            lesson_number=0,
            chunk_index=1
        ),
        CourseChunk(
            content="Course Building Towards Computer Use with Anthropic Lesson 1 content: In this lesson, you'll learn how to make basic API calls to Claude.",
            course_title=sample_course.title,
            lesson_number=1,
            chunk_index=2
        )
    ]


@pytest.fixture
def populated_vector_store(temp_chroma_dir, sample_course, sample_chunks):
    """Create a vector store with sample data"""
    store = VectorStore(
        chroma_path=temp_chroma_dir,
        embedding_model="all-MiniLM-L6-v2",
        max_results=5
    )

    # Add course metadata and content
    store.add_course_metadata(sample_course)
    store.add_course_content(sample_chunks)

    yield store

    # Cleanup: delete object and force GC before temp_chroma_dir cleanup
    del store
    gc.collect()


@pytest.fixture
def empty_vector_store(temp_chroma_dir):
    """Create an empty vector store"""
    store = VectorStore(
        chroma_path=temp_chroma_dir,
        embedding_model="all-MiniLM-L6-v2",
        max_results=5
    )

    yield store

    # Cleanup: delete object and force GC before temp_chroma_dir cleanup
    del store
    gc.collect()


@pytest.fixture
def mock_vector_store():
    """Fully mocked VectorStore - no ChromaDB at all.

    Use this for tests that don't need real vector search behavior.
    """
    mock = Mock(spec=VectorStore)

    # Setup attributes
    mock.max_results = 5

    # Setup method mocks
    mock.add_course_metadata = Mock()
    mock.add_course_content = Mock()
    mock.clear_all_data = Mock()
    mock.get_course_count = Mock(return_value=1)
    mock.get_existing_course_titles = Mock(return_value=["Test Course"])
    mock.get_all_courses_metadata = Mock(return_value=[{
        "title": "Test Course",
        "instructor": "Test Instructor",
        "lessons": []
    }])
    mock.get_lesson_link = Mock(return_value="https://example.com/lesson/1")
    mock.get_course_link = Mock(return_value="https://example.com/course")

    # Mock search with realistic behavior
    def mock_search_func(query, course_name=None, lesson_number=None, limit=None):
        return SearchResults(
            documents=["Sample content about " + query],
            metadata=[{
                "course_title": "Test Course",
                "lesson_number": lesson_number or 1
            }],
            distances=[0.5]
        )

    mock.search = Mock(side_effect=mock_search_func)

    return mock


@pytest.fixture
def rag_system_with_mock_store(mock_vector_store):
    """RAG system with fully mocked vector store - no ChromaDB, no temp dirs.

    Use this for tests that need RAG system but don't need real vector search.
    """
    from rag_system import RAGSystem
    from config import Config

    config = Config()
    config.ANTHROPIC_API_KEY = "test_key"

    # Create RAG system - it will create a real VectorStore
    # We'll replace it immediately
    rag = RAGSystem.__new__(RAGSystem)
    rag.config = config

    # Initialize components WITHOUT calling __init__ (which creates VectorStore)
    from document_processor import DocumentProcessor
    from session_manager import SessionManager
    from ai_generator import AIGenerator
    from search_tools import ToolManager, CourseSearchTool

    rag.document_processor = DocumentProcessor(config.CHUNK_SIZE, config.CHUNK_OVERLAP)
    rag.vector_store = mock_vector_store  # Use mock instead of real
    rag.ai_generator = AIGenerator(config.ANTHROPIC_API_KEY, config.ANTHROPIC_MODEL)
    rag.session_manager = SessionManager(config.MAX_HISTORY)

    # Initialize search tools with mocked store
    rag.tool_manager = ToolManager()
    rag.search_tool = CourseSearchTool(mock_vector_store)
    rag.tool_manager.register_tool(rag.search_tool)

    # Mock AI generator to avoid API calls
    mock_ai = Mock()
    mock_ai.generate_response = Mock(return_value="Test response")
    rag.ai_generator = mock_ai

    return rag


@pytest.fixture
def course_search_tool(populated_vector_store):
    """Create a CourseSearchTool with populated data"""
    return CourseSearchTool(populated_vector_store)


@pytest.fixture
def course_search_tool_empty(empty_vector_store):
    """Create a CourseSearchTool with empty vector store"""
    return CourseSearchTool(empty_vector_store)


@pytest.fixture
def tool_manager(course_search_tool):
    """Create a ToolManager with registered search tool"""
    manager = ToolManager()
    manager.register_tool(course_search_tool)
    return manager


@pytest.fixture
def mock_anthropic_client():
    """Create a mock Anthropic client"""
    mock_client = Mock()

    # Mock a simple text response
    mock_response = Mock()
    mock_response.content = [Mock(text="This is a test response", type="text")]
    mock_response.stop_reason = "end_turn"

    mock_client.messages.create.return_value = mock_response

    return mock_client


@pytest.fixture
def mock_anthropic_client_with_tool_use():
    """Create a mock Anthropic client that triggers tool use"""
    mock_client = Mock()

    # First response - tool use
    mock_tool_use = Mock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.id = "toolu_123"
    mock_tool_use.name = "search_course_content"
    mock_tool_use.input = {"query": "API calls"}

    first_response = Mock()
    first_response.content = [mock_tool_use]
    first_response.stop_reason = "tool_use"

    # Second response - final answer
    mock_text = Mock()
    mock_text.type = "text"
    mock_text.text = "Based on the search, here's information about API calls."

    second_response = Mock()
    second_response.content = [mock_text]
    second_response.stop_reason = "end_turn"

    # Setup the mock to return different responses on sequential calls
    mock_client.messages.create.side_effect = [first_response, second_response]

    return mock_client


@pytest.fixture
def ai_generator_with_mock_client(mock_anthropic_client):
    """Create an AIGenerator with mocked client"""
    generator = AIGenerator(api_key="test_key", model="claude-sonnet-4-20250514")
    generator.client = mock_anthropic_client
    return generator


@pytest.fixture
def sample_search_results():
    """Create sample search results"""
    return SearchResults(
        documents=[
            "This is content about API calls from lesson 1",
            "More information about Claude API basics"
        ],
        metadata=[
            {
                "course_title": "Building Towards Computer Use with Anthropic",
                "lesson_number": 1
            },
            {
                "course_title": "Building Towards Computer Use with Anthropic",
                "lesson_number": 1
            }
        ],
        distances=[0.3, 0.5]
    )


@pytest.fixture
def empty_search_results():
    """Create empty search results"""
    return SearchResults(
        documents=[],
        metadata=[],
        distances=[]
    )


@pytest.fixture
def error_search_results():
    """Create search results with error"""
    return SearchResults.empty("Search failed due to database error")