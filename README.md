# NEXUS: Intelligent Career Guidance System

NEXUS is a comprehensive career intelligence platform that combines deterministic data processing with cutting-edge AI to provide personalized placement readiness assessments and upskilling roadmaps.

## Features

- **Student Assessment**: Analyzes resumes, GitHub, and LeetCode profiles to map technical skills against industry demands.
- **Agentic Workflow**: Uses a multi-agent system (Skill Agent, Resume Agent, Interview Agent, Gap Analysis Agent) for deep profile understanding.
- **Deterministic Grounding**: Every AI-generated insight is backed by traceable evidence and a validation pipeline.
- **Company Matching**: Scores students against specific company requirements with gap analysis.
- **Upskilling Roadmap**: Generates personalized learning paths to bridge skill gaps.
- **Placement Cell Dashboard**: Role-based access for faculty to monitor student progress and manage cohorts.
- **AI Career Assistant**: Includes a personalized, platform-aware AI chatbot to guide students through their placement journey.

## Tech Stack

### Backend
- **Framework**: FastAPI
- **AI/ML**: Pydantic, LangChain, LangGraph, Gemini API
- **Database**: PostgreSQL
- **Infrastructure**: Docker, Docker Compose

### Frontend
- **Framework**: Next.js (React)
- **Styling**: Tailwind CSS, Lucide React
- **Language**: TypeScript

## Getting Started

### Prerequisites
- Docker and Docker Compose
- Node.js and npm (for frontend)
- Python 3.91+ (for backend local development)

### 1. Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your PostgreSQL URI, Gemini API Key, and other required credentials.

4. Run the application:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### 2. Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Run the development server:
   ```bash
   npm run dev
   ```

## Project Structure

```
placement-bot/
├── backend/
│   ├── app/                 # Backend Core
│   │   ├── agents/          # AI Agent Logic
│   │   ├── config/          # Settings & Config
│   │   ├── api/             # API Endpoints
│   │   └── main.py          # FastAPI App Entry Point
│   └── requirements.txt     # Python Dependencies
├── frontend/                # Next.js UI
│   ├── src/                 # React Source Code
│   │   ├── components/      # Reusable UI Components
│   │   ├── lib/             # API Client & Utilities
│   │   └── app/             # Application Routes
│   └── package.json         # Node Dependencies
└── docker-compose.yml       # Container Orchestration
```

## Development

### Adding a New Agent
1. Create a new module in `backend/app/agents/`.
2. Define the agent node and logic.
3. Import and wire it up in `backend/app/agents/graph.py`.
