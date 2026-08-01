# DriveMind

DriveMind is a fleet intelligence platform that combines a FastAPI backend, a frontend dashboard, and multi-agent reasoning for vehicle diagnostics and maintenance insights.

## What it does

- Visualizes fleet inventory and vehicle telemetry
- Shows diagnostic predictions and failure risk insights
- Exposes a knowledge graph and vector-backed retrieval workflow
- Includes a multi-agent Q&A console for fleet questions
- Supports local development and deployment to Railway/Vercel

## Project structure

- backend/ — FastAPI application, data pipeline, ML model logic, and agent orchestration
- frontend/ — static web app for the fleet dashboard
- react_ui/ — React/Vite-based UI experience
- models/ — model-related assets and helpers
- generate_static.py — static asset generation helper
- run_local.py — local launch script
- requirements.txt — Python dependencies
- pyproject.toml — Python project metadata

## Local development

1. Create and activate a virtual environment
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the app locally:
   ```bash
   python run_local.py
   ```
4. Open the frontend in your browser at the local address shown by the app.

## Backend API

The FastAPI app exposes endpoints such as:

- /health
- /api/fleet
- /api/vehicle/{vehicle_id}
- /api/telemetry/{vehicle_id}
- /api/graph
- /api/data-source
- /api/diagnose
- /api/evaluation

## Deployment notes

- Railway hosts the FastAPI backend and the /api routes.
- Vercel serves the frontend and should call the Railway backend URL for dynamic API requests.
- CORS is configured to allow Vercel-origin requests to the Railway backend.

## Notes

This project uses:

- FastAPI
- Pydantic
- SQLite
- pandas
- scikit-learn-style ML workflows
- a knowledge graph and vector store for RAG-style reasoning

## License

This project is provided as-is for demonstration and development purposes.
