"""Configuration management for the application."""

import os
from enum import Enum
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class Config:
    """Application configuration."""
    
    # Environment
    ENVIRONMENT: Environment = Environment.DEVELOPMENT if os.getenv("ENVIRONMENT", "development") == "development" else Environment.PRODUCTION
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/querymind")
    
    # API Keys - Groq and Gemini
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    
    # Application
    APP_NAME: str = "Unthinkable KBSE"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = ENVIRONMENT == Environment.DEVELOPMENT
    
    # CORS
    CORS_ORIGINS: list = ["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:3000", "http://127.0.0.1:5173"]


config = Config()