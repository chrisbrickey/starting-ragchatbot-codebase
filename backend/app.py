import warnings
warnings.filterwarnings("ignore", message="resource_tracker: There appear to be.*")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os

from config import config
from rag_system import RAGSystem

# Initialize FastAPI app
app = FastAPI(title="Course Materials RAG System", root_path="")

# Add trusted host middleware for proxy
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]
)

# Enable CORS with proper settings for proxy
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Initialize RAG system
rag_system = RAGSystem(config)

# Validate critical configuration on startup
if not config.ANTHROPIC_API_KEY or config.ANTHROPIC_API_KEY == "":
    print("\n" + "="*70)
    print("⚠️  WARNING: ANTHROPIC_API_KEY is not configured!")
    print("="*70)
    print("The application will not work without a valid API key.")
    print("\nTo fix this:")
    print("1. Create a .env file in the project root (if it doesn't exist)")
    print("2. Add your Anthropic API key:")
    print("   ANTHROPIC_API_KEY=sk-ant-your-key-here")
    print("3. Get your API key from: https://console.anthropic.com/")
    print("4. Restart this application")
    print("="*70 + "\n")
elif config.ANTHROPIC_API_KEY == "your-anthropic-api-key-here":
    print("\n" + "="*70)
    print("⚠️  WARNING: Using placeholder API key!")
    print("="*70)
    print("Please edit your .env file and replace the placeholder with your")
    print("actual Anthropic API key from: https://console.anthropic.com/")
    print("="*70 + "\n")

# Pydantic models for request/response
class QueryRequest(BaseModel):
    """Request model for course queries"""
    query: str
    session_id: Optional[str] = None

class QueryResponse(BaseModel):
    """Response model for course queries"""
    answer: str
    sources: List[str]
    session_id: str

class CourseStats(BaseModel):
    """Response model for course statistics"""
    total_courses: int
    course_titles: List[str]

class SessionClearRequest(BaseModel):
    """Request model for clearing a session"""
    session_id: str

class SessionClearResponse(BaseModel):
    """Response model for session clearing"""
    success: bool
    message: str

# API Endpoints

@app.post("/api/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """Process a query and return response with sources"""
    try:
        # Create session if not provided
        session_id = request.session_id
        if not session_id:
            session_id = rag_system.session_manager.create_session()
        
        # Process query using RAG system
        answer, sources = rag_system.query(request.query, session_id)
        
        return QueryResponse(
            answer=answer,
            sources=sources,
            session_id=session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/courses", response_model=CourseStats)
async def get_course_stats():
    """Get course analytics and statistics"""
    try:
        analytics = rag_system.get_course_analytics()
        return CourseStats(
            total_courses=analytics["total_courses"],
            course_titles=analytics["course_titles"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/session/clear", response_model=SessionClearResponse)
async def clear_session(request: SessionClearRequest):
    """Clear a conversation session"""
    try:
        rag_system.session_manager.clear_session(request.session_id)
        return SessionClearResponse(
            success=True,
            message=f"Session {request.session_id} cleared successfully"
        )
    except Exception as e:
        return SessionClearResponse(
            success=False,
            message=f"Error clearing session: {str(e)}"
        )

@app.on_event("startup")
async def startup_event():
    """Load initial documents on startup"""
    docs_path = "../docs"
    if os.path.exists(docs_path):
        print("Loading initial documents...")
        try:
            courses, chunks = rag_system.add_course_folder(docs_path, clear_existing=False)
            print(f"Loaded {courses} courses with {chunks} chunks")
        except Exception as e:
            print(f"Error loading documents: {e}")

# Custom static file handler with no-cache headers for development
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from pathlib import Path


class DevStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if isinstance(response, FileResponse):
            # Add no-cache headers for development
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response
    
    
# Serve static files for the frontend
app.mount("/", StaticFiles(directory="../frontend", html=True), name="static")