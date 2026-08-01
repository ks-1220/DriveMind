import sqlite3
import pandas as pd
import os

if os.environ.get("VERCEL"):
    DB_PATH = "/tmp/fleet.db"
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fleet.db")

def get_db_connection():
    """Returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(df_vehicles, df_maintenance, df_warranty, df_telemetry_summary=None):
    """Initializes the database schema and seeds it with generated data."""
    # Ensure any existing DB is removed for a clean rebuild on seed
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except OSError:
            pass
            
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Create Vehicles Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vehicles (
        id TEXT PRIMARY KEY,
        manufacturer TEXT,
        model TEXT,
        year INTEGER,
        status TEXT
    )
    """)
    
    # 2. Create Maintenance Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS maintenance_logs (
        id TEXT PRIMARY KEY,
        vehicle_id TEXT,
        date TEXT,
        component TEXT,
        description TEXT,
        cost REAL,
        FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
    )
    """)
    
    # 3. Create Warranty Claims Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS warranty_claims (
        id TEXT PRIMARY KEY,
        vehicle_id TEXT,
        component TEXT,
        claim_date TEXT,
        cost REAL,
        status TEXT,
        FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
    )
    """)
    
    # 4. Create Telemetry Summary Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS telemetry_summary (
        vehicle_id TEXT PRIMARY KEY,
        avg_coolant_temp REAL,
        max_coolant_temp REAL,
        avg_rpm REAL,
        max_rpm REAL,
        avg_oil_pressure REAL,
        min_oil_pressure REAL,
        avg_vibration REAL,
        max_vibration REAL,
        avg_voltage REAL,
        min_voltage REAL,
        avg_exhaust_temp REAL,
        max_exhaust_temp REAL,
        FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
    )
    """)
    
    conn.commit()
    
    # Insert metadata
    for _, row in df_vehicles.iterrows():
        cursor.execute(
            "INSERT INTO vehicles (id, manufacturer, model, year, status) VALUES (?, ?, ?, ?, ?)",
            (row["id"], row["manufacturer"], row["model"], int(row["year"]), row["initial_status"])
        )
        
    for _, row in df_maintenance.iterrows():
        cursor.execute(
            "INSERT INTO maintenance_logs (id, vehicle_id, date, component, description, cost) VALUES (?, ?, ?, ?, ?, ?)",
            (row["id"], row["vehicle_id"], row["date"], row["component"], row["description"], float(row["cost"]))
        )
        
    for _, row in df_warranty.iterrows():
        cursor.execute(
            "INSERT INTO warranty_claims (id, vehicle_id, component, claim_date, cost, status) VALUES (?, ?, ?, ?, ?, ?)",
            (row["id"], row["vehicle_id"], row["component"], row["claim_date"], float(row["cost"]), row["status"])
        )
        
    if df_telemetry_summary is not None:
        for _, row in df_telemetry_summary.iterrows():
            cursor.execute("""
            INSERT INTO telemetry_summary (
                vehicle_id, avg_coolant_temp, max_coolant_temp, avg_rpm, max_rpm,
                avg_oil_pressure, min_oil_pressure, avg_vibration, max_vibration,
                avg_voltage, min_voltage, avg_exhaust_temp, max_exhaust_temp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["vehicle_id"],
                float(row["avg_coolant_temp"]), float(row["max_coolant_temp"]),
                float(row["avg_rpm"]), float(row["max_rpm"]),
                float(row["avg_oil_pressure"]), float(row["min_oil_pressure"]),
                float(row["avg_vibration"]), float(row["max_vibration"]),
                float(row["avg_voltage"]), float(row["min_voltage"]),
                float(row["avg_exhaust_temp"]), float(row["max_exhaust_temp"])
            ))
            
    conn.commit()
    conn.close()

def update_vehicle_status(vehicle_id, status):
    """Updates the status of a specific vehicle in the DB."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE vehicles SET status = ? WHERE id = ?", (status, vehicle_id))
    conn.commit()
    conn.close()

def query_db(sql_query, params=None):
    """Executes a SELECT SQL query and returns list of dictionaries."""
    conn = get_db_connection()
    try:
        if params:
            df = pd.read_sql_query(sql_query, conn, params=params)
        else:
            df = pd.read_sql_query(sql_query, conn)
        results = df.to_dict(orient="records")
        return {
            "success": True,
            "data": results,
            "columns": list(df.columns)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": []
        }
    finally:
        conn.close()
