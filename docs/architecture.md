# Architecture

## System Overview
Pipeline-based system for bundle analysis.

## Components
- **Frontend** — React 18/Vite/Tailwind, served via nginx (port 3000)
- **API & Orchestration** — FastAPI on port 8000; routes: /health, /api/v1/bundles
- **Processing Pipeline** — Celery workers consuming Redis queue; tasks in app/workers/tasks.py
- **Storage** — MinIO (S3-compatible) for bundle files; PostgreSQL for metadata
- **Knowledge Base** — (Phase 4+)

## Data Flow
Upload → Extract → Parse → Detect → Report → Review → Store knowledge

## External Services
- Object storage
- Database
- AI model services

## Key Constraints
- Offline compatibility
- Security and isolation
