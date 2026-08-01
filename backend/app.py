from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

from .smartcar_connector import load_fleet_data, is_smartcar_configured
from .pipeline import engineer_features, compute_telemetry_summaries
from .ml_model import train_ml_models, predict_vehicle_diagnostics, FleetPredictiveModels
from .db import init_db, query_db, update_vehicle_status
from .graph_store import build_knowledge_graph, GraphRAGPipeline
from .vector_store import FleetVectorDB
from .agents import MultiAgentSystem
from .evaluator import run_evaluation_suite

app = FastAPI(title="DriveMind Fleet Intelligence API")

# Enable CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables to cache operational pipelines
fleet_data = {}
vector_db = None
graph_rag = None
agent_system = None
df_engineered_telemetry = None
ml_models = None

class QueryRequest(BaseModel):
    query: str

@app.on_event("startup")
def startup_event():
    """Initializes the entire fleet intelligence pipeline on startup."""
    global vector_db, graph_rag, agent_system, df_engineered_telemetry, ml_models
    
    print("DriveMind: Loading fleet data (live Smartcar API or synthetic simulator)...")
    df_v, df_t, df_m, df_w, docs = load_fleet_data()
    
    print("DriveMind: Running data engineering pipeline...")
    df_engineered_telemetry = engineer_features(df_t)
    df_summaries = compute_telemetry_summaries(df_t)
    
    print("DriveMind: Seeding SQLite structured database...")
    init_db(df_v, df_m, df_w, df_summaries)
    
    print("DriveMind: Training ML diagnostics models...")
    ml_models = train_ml_models(df_engineered_telemetry)
    
    print("DriveMind: Syncing vehicle prediction labels with SQLite status...")
    for _, row in df_v.iterrows():
        v_id = row["id"]
        try:
            diag = predict_vehicle_diagnostics(v_id, df_engineered_telemetry, ml_models)
            update_vehicle_status(v_id, diag["status"])
        except Exception as e:
            print(f"Failed status synchronization for {v_id}: {e}")
            
    print("DriveMind: Constructing Knowledge Graph...")
    kg = build_knowledge_graph(df_v, df_m, df_w)
    graph_rag = GraphRAGPipeline(kg)
    
    print("DriveMind: Constructing Qdrant In-Memory Vector Store...")
    vector_db = FleetVectorDB()
    vector_db.init_db(docs)
    
    print("DriveMind: Bootstrapping Multi-Agent Reasoning Pipeline...")
    agent_system = MultiAgentSystem(vector_db, graph_rag, ml_models)
    
    print("DriveMind Startup Sequence successfully finalized!")

@app.get("/api/fleet")
def get_fleet():
    """Returns the list of all vehicles with active statuses and models."""
    res = query_db("SELECT * FROM vehicles ORDER BY status DESC, id ASC")
    if res["success"]:
        # Add summary statistics
        for v in res["data"]:
            # Pull latest ML diagnostics info
            try:
                diag = predict_vehicle_diagnostics(v["id"], df_engineered_telemetry, ml_models)
                v["predicted_rul"] = diag.get("predicted_rul", 45.0)
                v["anomaly_score"] = diag.get("anomaly_score", 0.0)
                v["failure_class"] = diag.get("failure_class", "Healthy")
            except Exception:
                v["predicted_rul"] = 45.0
                v["anomaly_score"] = 0.0
                v["failure_class"] = "Healthy"
        return res["data"]
    else:
        raise HTTPException(status_code=500, detail=res["error"])

@app.get("/api/vehicle/{vehicle_id}")
def get_vehicle(vehicle_id: str):
    """Returns full details, latest telemetry metrics, and ML diagnostics for a vehicle."""
    # Query details
    v_res = query_db("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,))
    if not v_res["success"] or len(v_res["data"]) == 0:
        raise HTTPException(status_code=404, detail="Vehicle not found")
        
    vehicle_meta = v_res["data"][0]
    
    # Run ML diagnostics inference
    try:
        diagnostics = predict_vehicle_diagnostics(vehicle_id, df_engineered_telemetry, ml_models)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ML Diagnostic inference failure: {str(e)}")
        
    # Get recent maintenance logs
    m_res = query_db("SELECT date, component, description, cost FROM maintenance_logs WHERE vehicle_id = ? ORDER BY date DESC LIMIT 5", (vehicle_id,))
    maintenance_history = m_res["data"] if m_res["success"] else []
    
    return {
        "metadata": vehicle_meta,
        "diagnostics": diagnostics,
        "recent_maintenance": maintenance_history
    }

@app.get("/api/telemetry/{vehicle_id}")
def get_telemetry_history(vehicle_id: str):
    """Returns the historical telemetry stream for plotting."""
    v_data = df_engineered_telemetry[df_engineered_telemetry["vehicle_id"] == vehicle_id].sort_values("timestamp")
    if len(v_data) == 0:
         raise HTTPException(status_code=404, detail="Vehicle telemetry data not found")
         
    return v_data[["timestamp", "coolant_temp", "vibration", "voltage", "exhaust_temp", "oil_pressure", "engine_load"]].to_dict(orient="records")

@app.get("/api/graph")
def get_graph():
    """Returns Vis.js data structure for Knowledge Graph rendering."""
    return graph_rag.kg.to_json()

@app.get("/api/data-source")
def get_data_source():
    """Returns whether the app is using live Smartcar data or synthetic data."""
    if is_smartcar_configured():
        return {
            "source": "smartcar_live",
            "label": "Live — Smartcar API",
            "description": "Fleet data is streamed in real-time from connected vehicles via the Smartcar API."
        }
    return {
        "source": "synthetic_simulator",
        "label": "Synthetic — High-Fidelity Simulator",
        "description": "Fleet data is generated by the DriveMind physics-based telemetry simulator. Add SMARTCAR_CLIENT_ID / SMARTCAR_CLIENT_SECRET to .env to enable live data."
    }

@app.post("/api/diagnose")
def run_diagnose(request: QueryRequest):
    """Executes multi-agent RAG workflow for a user query."""
    if not agent_system:
        raise HTTPException(status_code=503, detail="Agent system not initialized yet")
    try:
        result = agent_system.run_agent_reasoning(request.query)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/evaluation")
def run_evaluation():
    """Executes the benchmark evaluation pipeline."""
    if not agent_system:
        raise HTTPException(status_code=503, detail="Agent system not initialized yet")
    try:
        evaluation_results = run_evaluation_suite(agent_system)
        return evaluation_results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Setup frontend static files mounting
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")
    
    @app.get("/")
    def read_root():
        return FileResponse(os.path.join(frontend_path, "index.html"))
