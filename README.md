# Rappi Operations Intelligence System

AI-powered conversational analytics for Rappi operations data — ask questions in natural language, get SQL-backed answers and automated weekly insights.

## Prerequisites

- Python 3.11+
- Node 18+
- OpenAI API key

## Setup

### 1. Environment

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and set OPENAI_API_KEY
```

### 2. Data

Place the Excel data file at `data/rappi_data.xlsx`.

### 3. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --reload
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

## Status

Most backend functions are stubs (`NotImplementedError`) — implementation happens in the next phase.
