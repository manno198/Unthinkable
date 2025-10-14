@echo off
echo 🚀 Starting Unthinkable KBSE in development mode...

REM Create .env file if it doesn't exist
if not exist backend\.env (
    echo Creating .env file from template...
    copy backend\env.example backend\.env
    echo ✅ Please edit backend\.env with your API keys
)

REM Start backend with in-memory database
echo 📦 Starting backend...
cd backend
call venv\Scripts\activate.bat
python main.py

pause
