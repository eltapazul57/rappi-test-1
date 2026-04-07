# Rappi Operations Intelligence System

AI-powered conversational analytics for Rappi operations data — ask questions in natural language, get SQL-backed answers and automated weekly insights.

## Prerequisites

- Python 3.11+
- Node 18+
- OpenAI API key
- Poetry

## Setup

### 1. Environment

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and set OPENAI_API_KEY
```

### 2. Data

Place the Excel data file at `data/rappi_data.xlsx`. The backend loads this workbook directly and creates `data/rappi.db` on startup.

### 3. Backend (Poetry, no manual activation)

```bash
cd backend
poetry install
poetry run uvicorn app:app --reload
```

Or from the project root:

```bash
poetry -C backend install
poetry -C backend run uvicorn app:app --reload
```

If Poetry is not installed yet:

```bash
pipx install poetry
# or: pip install poetry
```

Legacy pip path (optional):

```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --reload
```

The first backend start loads the workbook into SQLite automatically. If you change the Excel file and want to rebuild the database, delete `data/rappi.db` and start the backend again.

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

## Status

Most backend functions are stubs (`NotImplementedError`) — implementation happens in the next phase.
