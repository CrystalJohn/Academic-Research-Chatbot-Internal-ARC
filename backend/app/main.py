"""
ARC Chatbot Backend - FastAPI Application

Main entry point for the Academic Research Chatbot API.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.chat import router as chat_router
# from app.api.chat_agentic import router as chat_agentic_router  # Disabled for MVP - 3x cost
from app.api.auth import router as auth_router
from app.api.syllabus import router as syllabus_router
from app.api.syllabus_upload import router as syllabus_upload_router

app = FastAPI(
    title="ARC Chatbot API",
    description="Academic Research Chatbot - Document Processing & RAG Chat API",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(admin_router)
app.include_router(chat_router)
# app.include_router(chat_agentic_router)  # Disabled for MVP - 3x cost
app.include_router(auth_router)
app.include_router(syllabus_router)
app.include_router(syllabus_upload_router)


@app.get("/health")
async def health_check():
    """Health check endpoint for ALB."""
    return {"status": "healthy", "service": "arc-chatbot-api"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "ARC Chatbot API",
        "docs": "/docs",
        "health": "/health"
    }
