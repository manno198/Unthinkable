#!/bin/bash

echo "🚀 Starting Unthinkable KBSE in development mode..."

# Create .env file if it doesn't exist
if [ ! -f backend/.env ]; then
    echo "Creating .env file from template..."
    cp backend/env.example backend/.env
    echo "✅ Please edit backend/.env with your API keys"
fi

# Start backend with in-memory database
echo "📦 Starting backend..."
cd backend
source venv/bin/activate
python main.py
