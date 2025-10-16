# Unthinkable KBSE

A document querying system that allows you to upload documents and ask questions about their content using AI-powered search and response generation.

##  Features

- **Document Upload**: Support for PDF, TXT, JSON files and raw text input
- **AI-Powered Querying**: Ask natural language questions about your documents
- **Multiple AI Providers**: Groq (primary) and Gemini (fallback) for embeddings and text generation
- **JSON API**: RESTful API for programmatic document management
- **Modern UI**: React-based frontend with TypeScript and Tailwind CSS
- **Flexible Database**: PostgreSQL with in-memory fallback for development

##  Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **AI Services**: 
  - Groq API (primary) - for embeddings and text generation
  - Google Gemini API (fallback) - for embeddings and text generation
- **Database**: PostgreSQL with in-memory SQLite fallback
- **Document Processing**: PyPDF, BeautifulSoup4
- **Server**: Uvicorn with auto-reload

### Frontend
- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **UI Components**: Shadcn/ui components
- **Package Manager**: Yarn 4 with node-modules linker

### Development & Deployment
- **Environment**: Python virtual environment with pip
- **Database**: In-memory SQLite (automatic fallback, no setup required)
- **Scripts**: Cross-platform startup scripts (Windows/Linux)

##  Project Workflow

### 1. Document Ingestion Process
```
Document Upload → Text Extraction → Chunking → Embedding Generation → Database Storage
```

1. **Upload**: User uploads document (PDF/TXT/JSON) or provides raw text
2. **Extraction**: System extracts text content from the document
3. **Chunking**: Text is split into manageable chunks (1000 chars with 200 char overlap)
4. **Embedding**: Each chunk is converted to vector embeddings using AI services
5. **Storage**: Document metadata and chunks are stored in the database

### 2. Query Process
```
Question → Embedding Generation → Similarity Search → Context Retrieval → AI Response
```

1. **Question Processing**: User's question is converted to vector embedding
2. **Similarity Search**: System finds most relevant document chunks using vector similarity
3. **Context Building**: Retrieved chunks are combined to form context
4. **AI Response**: Context and question are sent to AI service for answer generation
5. **Response**: Structured response with answer and source citations

### 3. API Endpoints

#### Document Management
- `POST /api/v1/ingest/upload` - Upload and process documents
- `POST /api/v1/text/add` - Add multiple text documents via JSON
- `GET /api/v1/text/list` - List all documents

#### Querying
- `POST /api/v1/query/ask` - Query documents with natural language
- `POST /api/v1/text/query` - Query text documents via JSON API

#### Health & Status
- `GET /health` - API health check
- `GET /` - API information

##  Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Yarn 4 (Corepack)

### 1. Clone and Setup
```bash
git clone <repository-url>
cd query-mind-ai
```

### 2. Backend Setup
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.\.venv\Scripts\Activate.ps1
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
cd backend
pip install -r requirements.txt

# Set up environment variables
cp env.example .env
# Edit .env with your API keys
```

### 3. Frontend Setup
```bash
cd frontend
yarn install
```

### 4. Environment Configuration
Create a `.env` file in the project root:
```env
ENVIRONMENT=development
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
APP_NAME=Unthinkable KBSE
DEBUG=true
```

**Note**: No database setup required! The application automatically uses an in-memory database that works out of the box.

### 5. Run the Application

#### Option A: Simple Development (Recommended)
```bash
# Windows
start-dev.bat

# Linux/Mac
./start-dev.sh
```

#### Option B: Manual Start
```bash
# Terminal 1 - Backend
cd backend
python main.py

# Terminal 2 - Frontend
cd frontend
yarn dev
```


### 6. Access the Application
- **Frontend**: http://localhost:5173
- **Backend API**: http://127.0.0.1:8000
- **API Docs**: http://127.0.0.1:8000/docs

##  Usage Examples

### 1. Web Interface
1. Open http://localhost:5173
2. Upload a document (PDF, TXT, or JSON)
3. Ask questions about the document content
4. View AI-generated answers with source citations

### 2. JSON API Usage

#### Add Documents
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/text/add" \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      {
        "title": "Python Guide",
        "content": "Python is a programming language...",
        "category": "programming"
      }
    ]
  }'
```

#### Query Documents
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/text/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is Python?",
    "max_chunks": 5,
    "max_tokens": 500
  }'
```

## 🔧 Configuration

### API Keys Setup
1. **Groq API**: Get your API key from [Groq Console](https://console.groq.com/)
2. **Gemini API**: Get your API key from [Google AI Studio](https://makersuite.google.com/)

### Database Configuration
- **Development & Production**: Uses in-memory SQLite automatically (no setup required)
- **Optional**: PostgreSQL can be configured in `.env` if needed for persistent storage

### Frontend Configuration
- **API URL**: Configured in `frontend/src/config/api.ts`
- **Theme**: Customizable in `frontend/src/constants/default-theme.ts`

##  Project Structure

```
query-mind-ai/
├── backend/                 # FastAPI backend
│   ├── api/                # API endpoints
│   │   ├── ingest.py       # Document ingestion
│   │   ├── query.py        # Document querying
│   │   └── text_documents.py # JSON API
│   ├── config.py           # Configuration
│   ├── database.py         # Database connection
│   ├── database_memory.py  # In-memory database
│   ├── main.py            # Application entry point
│   └── requirements.txt   # Python dependencies
├── frontend/              # React frontend
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── pages/         # Page components
│   │   ├── services/      # API services
│   │   └── config/        # Frontend configuration
│   ├── package.json       # Node dependencies
│   └── vite.config.ts     # Vite configuration
├── start-dev.bat         # Windows startup script
├── start-dev.sh          # Linux/Mac startup script
└── README.md             # This file
```

##  Troubleshooting

### Common Issues

1. **502 API Errors**: Check that API keys are properly configured in `.env`
2. **Module Not Found**: Ensure virtual environment is activated
3. **Port Conflicts**: Change ports in configuration if 8000 or 5173 are in use
4. **Database Connection**: Uses in-memory database by default (no external dependencies)

### Debug Mode
Set `DEBUG=true` in `.env` to enable:
- Detailed error messages
- Auto-reload on file changes
- Enhanced logging

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request


## Acknowledgments

- FastAPI for the excellent Python web framework
- React and Vite for the modern frontend stack
- Groq and Google for AI services
- Shadcn/ui for beautiful UI components

## Made with ❤️ by Harshita Singh
