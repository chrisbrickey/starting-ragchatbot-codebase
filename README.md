# Course Materials RAG System

This is a Retrieval-Augmented Generation (RAG) system for querying course materials using semantic search and AI-powered responses. 
The application uses ChromaDB for vector storage, Anthropic's Claude for AI generation, and provides a web interface for interaction.

**Note:** This repository is forked from [https-deeplearning-ai/starting-ragchatbot-codebase](https://github.com/https-deeplearning-ai/starting-ragchatbot-codebase).
I'm using this repository as a sandbox for experimenting with Claude Code.


## Prerequisites

- Python 3.13 or higher
- uv (Python package manager)
- An Anthropic API key (for Claude AI)
- **For Windows**: Use Git Bash to run the application commands - [Download Git for Windows](https://git-scm.com/downloads/win)

## Installation

1. **Install uv** (if not already installed)
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Install Python dependencies**
   ```bash
   uv sync
   ```

3. **Set up environment variables**

   Create a `.env` file with your Anthropic API key:
   ```bash
   # Copy the template file
   cp .env.example .env

   # Edit .env and add your API key
   # Get your key from: https://console.anthropic.com/
   ```

   Your `.env` file should look like:
   ```
   ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
   ```

   **Important:**
   - The `.env` file is gitignored and will NOT be committed
   - Never commit your API key to version control
   - If you see "query failed" errors, check that your API key is set correctly

## Running the Application

### Quick Start

Use the provided shell script:
```bash
chmod +x run.sh
./run.sh
```

### Manual Start

```bash
cd backend
uv run uvicorn app:app --reload --port 8000
```

The application will be available at:
- Web Interface: `http://localhost:8000`
- API Documentation: `http://localhost:8000/docs`

## Troubleshooting

### "Query failed" Error

If you see "query failed" when asking questions:

1. **Check your API key is set**
   ```bash
   # In project root, verify .env file exists
   ls -la .env

   # Check if key is configured (won't show the actual key)
   grep ANTHROPIC_API_KEY .env
   ```

2. **Verify the key format**
   - Should start with `sk-ant-`
   - No quotes around the value
   - No spaces before or after the `=`

3. **Restart the application**
   - Stop the server (Ctrl+C)
   - Start it again - you should see a warning if the key is missing

4. **Check startup logs**
   - Look for warnings about API key configuration
   - The application will display clear messages if the key is missing or invalid

### Testing the System

Run the comprehensive test suite:
```bash
cd backend
uv run pytest tests/ -v
```

## Code Quality Tools

This project includes automated code quality tools to maintain consistent code formatting and catch common issues.

### Quick Commands

- **Format code**: `./format.sh` - Automatically formats all Python code
- **Check code style**: `./lint.sh` - Checks formatting without making changes
- **Run all quality checks**: `./quality-check.sh` - Comprehensive check (formatting, linting, type checking, tests)

### Development Workflow

Before committing code, run:
```bash
./quality-check.sh
```

This will:
1. Check code formatting (Black)
2. Verify import organization (isort)
3. Run linting checks (flake8)
4. Perform type checking (mypy)
5. Run the test suite

If formatting issues are found, fix them with:
```bash
./format.sh
```

### Quality Tools Included

- **Black**: Automatic code formatter (88 character line length)
- **isort**: Organizes imports alphabetically and by type
- **flake8**: Linting for style and common errors
- **mypy**: Static type checking
- **pytest**: Testing framework

### Configuration

Quality tool settings are defined in:
- `pyproject.toml` - Black, isort, and mypy configuration
- `.flake8` - flake8 configuration