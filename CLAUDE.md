# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Retrieval-Augmented Generation (RAG) system for course materials built with FastAPI backend and vanilla JavaScript frontend. The system uses ChromaDB for vector storage, Anthropic's Claude for AI generation, and provides semantic search capabilities over course documents.

## Development Commands

### Running the Application
- Quick start: `./run.sh` (requires `chmod +x run.sh` first)
- Manual start: `cd backend && uv run uvicorn app:app --reload --port 8000`
- Environment setup: `uv sync` to install dependencies

### Code Quality Tools
- **Format code**: `./format.sh` - Automatically formats code with Black and organizes imports with isort
- **Lint code**: `./lint.sh` - Checks code formatting and style without making changes
- **Full quality check**: `./quality-check.sh` - Runs all checks including formatting, linting, type checking, and tests
- **Run tests**: `uv run pytest backend/tests/` - Runs the test suite
- **Type checking**: `uv run mypy backend/` - Checks types with mypy

### Code Quality Standards
This project enforces consistent code quality using:
- **Black**: Code formatter (line length: 88 characters)
- **isort**: Import statement organizer (Black-compatible profile)
- **flake8**: Linting for code style and common errors
- **mypy**: Static type checking for Python code
- **pytest**: Testing framework

All code should pass quality checks before committing. Run `./quality-check.sh` to verify.

### Environment Requirements
- Python 3.13+ with uv package manager
- Anthropic API key in `.env` file: `ANTHROPIC_API_KEY=your_key_here`
- For Windows: Use Git Bash for running commands

### Application URLs
- Web Interface: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## Architecture

### Backend Structure (`backend/`)
- **`app.py`**: FastAPI application with CORS middleware, static file serving, and API endpoints
- **`rag_system.py`**: Main orchestrator that coordinates all system components
- **`document_processor.py`**: Handles document parsing and chunking for various file formats
- **`vector_store.py`**: ChromaDB integration for vector storage and semantic search
- **`ai_generator.py`**: Anthropic Claude integration with tool calling capabilities
- **`session_manager.py`**: Conversation history management for multi-turn interactions
- **`search_tools.py`**: Tool-based search system that AI can call to retrieve relevant content
- **`models.py`**: Pydantic models for courses, lessons, and chunks
- **`config.py`**: Configuration management for all system settings

### Frontend Structure (`frontend/`)
- **`index.html`**: Main web interface for user interactions
- **`script.js`**: JavaScript handling API calls and UI interactions
- **`style.css`**: Styling for the web interface

### Key Data Flow
1. Documents in `docs/` are processed on startup via `add_course_folder()`
2. User queries trigger the RAG system through `/api/query` endpoint
3. AI uses search tools to find relevant course content from vector store
4. Response combines retrieved context with AI generation
5. Session manager maintains conversation history for context

### Core Components Integration
- **RAGSystem** orchestrates DocumentProcessor → VectorStore → AIGenerator → SessionManager
- **ToolManager** enables AI to perform semantic search via **CourseSearchTool**
- **VectorStore** handles both course metadata and content chunks for comprehensive search
- **AIGenerator** uses Claude with tool calling to decide when to search for information

### Document Processing Pipeline
- Supports PDF, DOCX, and TXT files
- Documents are chunked with configurable size and overlap
- Each chunk includes course metadata for better retrieval
- Vector embeddings created using sentence-transformers model

## Configuration
All settings managed through `config.py` including:
- Chunk size and overlap for document processing
- ChromaDB path and embedding model selection
- Anthropic API configuration
- Session and search result limits