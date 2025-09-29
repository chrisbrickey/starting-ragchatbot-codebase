# ChromaDB Mocking Strategy

## Overview

This test suite uses **complete mocking** of ChromaDB to eliminate file system operations and ensure fast, reliable test execution.

## Why Mock ChromaDB?

### Problems with Real ChromaDB in Tests
1. **File System Operations**: Creates persistent SQLite databases and vector indexes
2. **Resource Management**: File handles and connections require careful cleanup
3. **Timing Issues**: Non-deterministic cleanup order causes "unable to open database file" errors
4. **Performance**: Real ChromaDB adds significant overhead (~40+ seconds)
5. **Environment Sensitivity**: Different OS/filesystem behaviors cause intermittent failures

### Benefits of Mocking
- ✅ **Fast**: 15 seconds vs 40+ seconds
- ✅ **Reliable**: No file system race conditions
- ✅ **Deterministic**: Same behavior on all platforms
- ✅ **No Cleanup**: No temp directories or resource management needed
- ✅ **Tests Logic**: Verifies application behavior, not database internals

## Mocking Architecture

### Two-Tier Fixture Strategy

#### 1. `mock_vector_store` Fixture (conftest.py:126-163)

**Purpose**: Provides a fully mocked VectorStore with no ChromaDB dependency

**Key Methods Mocked**:
```python
mock.add_course_metadata = Mock()
mock.add_course_content = Mock()
mock.clear_all_data = Mock()
mock.get_course_count = Mock(return_value=1)
mock.get_existing_course_titles = Mock(return_value=["Test Course"])
mock.get_all_courses_metadata = Mock(return_value=[...])
mock.get_lesson_link = Mock(return_value="https://example.com/lesson/1")
mock.get_course_link = Mock(return_value="https://example.com/course")

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
```

**Realistic Behavior**:
- Search returns plausible results based on query
- Metadata queries return consistent course information
- All methods are callable and return expected types

#### 2. `rag_system_with_mock_store` Fixture (conftest.py:167-204)

**Purpose**: Creates RAG system with mocked vector store

**Implementation Strategy**:
```python
# Bypass __init__ to avoid creating real VectorStore
rag = RAGSystem.__new__(RAGSystem)
rag.config = config

# Initialize components manually
rag.document_processor = DocumentProcessor(...)
rag.vector_store = mock_vector_store  # Inject mock
rag.ai_generator = AIGenerator(...)
rag.session_manager = SessionManager(...)

# Setup tools with mocked store
rag.tool_manager = ToolManager()
rag.search_tool = CourseSearchTool(mock_vector_store)
rag.tool_manager.register_tool(rag.search_tool)

# Mock AI to avoid API calls
mock_ai = Mock()
mock_ai.generate_response = Mock(return_value="Test response")
rag.ai_generator = mock_ai
```

**Why Bypass `__init__`?**
- `RAGSystem.__init__()` creates a real VectorStore
- Using `__new__` + manual initialization avoids ChromaDB entirely
- All components are real except VectorStore and AIGenerator

## Tests Using Mocked Fixtures

### Fully Mocked Tests (No ChromaDB)
These tests use `rag_system_with_mock_store` or `mock_vector_store`:

**test_rag_integration.py:**
- `TestRAGSystemInitialization::test_initialization` (line 83)
- `TestRAGSystemInitialization::test_search_tool_registered` (line 94)
- `TestRAGSystemDocumentLoading::test_add_course_folder` (line 239)
- `TestRAGSystemDocumentLoading::test_add_course_folder_empty` (line 262)
- `TestRAGSystemDocumentLoading::test_add_course_folder_nonexistent` (line 271)
- `TestRAGSystemAnalytics::test_get_course_analytics_empty` (line 308)

### Integration Tests (Real ChromaDB)
These tests use `populated_vector_store` or `empty_vector_store` when actual vector search behavior is needed:

- Query handling tests (need real semantic search)
- Session management tests (need real context retrieval)
- Source tracking tests (need real result metadata)

## Writing New Tests

### Use Mocks When:
- Testing RAG system initialization
- Testing component wiring
- Testing document loading logic
- Testing analytics/metadata queries
- Testing error handling
- **Speed and reliability are priorities**

### Use Real ChromaDB When:
- Testing actual vector search behavior
- Testing semantic similarity
- Testing search filters (course_name, lesson_number)
- Verifying search result quality
- **Search accuracy is being validated**

## Common Patterns

### Pattern 1: Configure Mock Return Values
```python
def test_something(self, rag_system_with_mock_store):
    rag = rag_system_with_mock_store

    # Override default mock behavior
    rag.vector_store.get_course_count.return_value = 5
    rag.vector_store.get_existing_course_titles.return_value = ["Course A", "Course B"]

    # Test code...
```

### Pattern 2: Verify Mock Calls
```python
def test_add_course(self, rag_system_with_mock_store, tmp_path):
    rag = rag_system_with_mock_store

    # Configure for fresh course
    rag.vector_store.get_existing_course_titles.return_value = []

    # Perform operation
    courses, chunks = rag.add_course_folder(str(tmp_path))

    # Verify interactions
    rag.vector_store.add_course_metadata.assert_called()
    rag.vector_store.add_course_content.assert_called()
```

### Pattern 3: Realistic Mock Search
```python
def test_search_behavior(self, mock_vector_store):
    # Mock is pre-configured with realistic search
    results = mock_vector_store.search("API calls", lesson_number=1)

    assert results.documents[0] == "Sample content about API calls"
    assert results.metadata[0]["lesson_number"] == 1
```

## Test Performance

### Before Mocking
- **Duration**: 40-45 seconds
- **Failures**: 5-7 intermittent failures
- **Issue**: ChromaDB resource cleanup race conditions

### After Mocking
- **Duration**: 15 seconds (62% faster)
- **Failures**: 1 known semantic search behavior
- **Result**: 61/62 tests passing (98.4%)

## Maintenance

### When to Update Mocks

**If VectorStore adds new methods:**
1. Add method to `mock_vector_store` fixture with reasonable defaults
2. Document expected behavior in comments

**If search behavior changes:**
1. Update `mock_search_func` in conftest.py
2. Ensure return values match new SearchResults structure

**If RAGSystem initialization changes:**
1. Update `rag_system_with_mock_store` fixture
2. Ensure all components are initialized correctly

## Troubleshooting

### Test Fails with "AttributeError: Mock object has no attribute..."
**Solution**: Add missing method to `mock_vector_store` fixture

### Test Expects Different Search Results
**Solution**: Override mock behavior in test:
```python
def custom_search(query, **kwargs):
    return SearchResults(documents=["Your custom result"], ...)

rag.vector_store.search.side_effect = custom_search
```

### Need Real ChromaDB for One Test
**Solution**: Use existing fixtures instead:
```python
def test_real_search(self, populated_vector_store):
    # Uses real ChromaDB
    results = populated_vector_store.search("query")
```

## Best Practices

1. **Prefer Mocks for Unit Tests**: Fast and isolated
2. **Use Real ChromaDB Sparingly**: Only for integration tests
3. **Document Mock Assumptions**: Comment what behavior is mocked
4. **Keep Mocks Realistic**: Return plausible data structures
5. **Test Integration Separately**: Have dedicated integration test suite

## Files Modified

### Primary Files
- `backend/tests/conftest.py` - Added mock fixtures (lines 126-204)
- `backend/tests/test_rag_integration.py` - Updated 6 tests to use mocks

### Documentation
- `backend/tests/CHROMADB_MOCKING_GUIDE.md` - This file
- `backend/tests/FINAL_SOLUTION.md` - Historical pytest finalizer solution
- `backend/tests/TEST_FIXES.md` - Resource management approach

## Summary

**Problem**: ChromaDB creates file system resources that cause test failures
**Solution**: Complete mocking of VectorStore for unit tests
**Result**: Fast, reliable tests that verify application logic without database operations

For tests requiring real vector search, existing fixtures (`populated_vector_store`, `empty_vector_store`) remain available.