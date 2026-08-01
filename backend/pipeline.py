import pandas as pd
import numpy as np

def clean_telemetry(df_telemetry):
    """
    Cleans raw telemetry data: checks for nulls, sorts by timestamp, 
    and handles outliers or noise.
    """
    # Unique version marker to verify deployed code
    print("========== CLEAN_TELEMETRY VERSION 5 ==========")

    df = df_telemetry.copy()

    # Initial debug: columns as received
    try:
        print("1:", df.columns.tolist())
    except Exception:
        print("1: <could not print columns>")

    # Normalize column names (strip whitespace) and accept common alternatives
    df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]

    # Accept alternatives for vehicle id and timestamp (robust to upstream key differences)
    if "vehicle_id" not in df.columns:
        for alt in ("vehicleId", "vehicle", "veh_id", "id"):
            if alt in df.columns:
                df = df.rename(columns={alt: "vehicle_id"})
                break

    if "timestamp" not in df.columns:
        for alt in ("time", "ts", "date"):
            if alt in df.columns:
                df = df.rename(columns={alt: "timestamp"})
                break

    # If dataframe is empty or still missing vehicle_id/timestamp, return gracefully
    if df.empty:
        # Nothing to engineer — return empty frame
        return df

    if "vehicle_id" not in df.columns:
        raise KeyError(f"Telemetry DataFrame missing 'vehicle_id' column. Available columns: {df.columns.tolist()}")
    if "timestamp" not in df.columns:
        raise KeyError(f"Telemetry DataFrame missing 'timestamp' column. Available columns: {df.columns.tolist()}")

    # Convert timestamp and show columns after conversion
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    try:
        print("2:", df.columns.tolist())
    except Exception:
        print("2: <could not print columns after to_datetime>")

    # Sort and reset index
    df = df.sort_values(by=["vehicle_id", "timestamp"]).reset_index(drop=True)
    try:
        print("3:", df.columns.tolist())
    except Exception:
        print("3: <could not print columns after sort/reset>")

    # Use transform-based filling to avoid moving grouping key into the index
    fill_cols = [c for c in df.columns if c != "vehicle_id"]
    if fill_cols:
        try:
            df[fill_cols] = (
                df.groupby("vehicle_id")[fill_cols]
                  .transform(lambda s: s.ffill().bfill())
            )
        except Exception as e:
            print("Transform fill failed:", e)
            # Fallback to groupby.apply if transform unexpectedly fails
            df = df.groupby("vehicle_id", group_keys=False).apply(lambda group: group.ffill().bfill())
            if "vehicle_id" not in df.columns and "vehicle_id" in getattr(df.index, 'names', []):
                df = df.reset_index(level='vehicle_id')
    else:
        # Nothing to fill
        pass

    try:
        print("4:", df.columns.tolist())
        print("4 index:", df.index.names)
        print(df.head())
    except Exception:
        print("4: <could not print final debug info>")

    return df

def engineer_features(df_telemetry):
    """
    Calculates windowed and rolling aggregates for ML features:
    - 24-hour rolling averages (last 3 points)
    - 72-hour rolling averages (last 9 points)
    - Sensor standard deviations (vibration and temperature fluctuations)
    - Trend slopes (current value / rolling mean ratio)
    """
    df = clean_telemetry(df_telemetry)
    
    engineered_records = []

    # Debug: log the incoming DataFrame columns/shape before grouping
    try:
        print("Pipeline columns:", df.columns.tolist())
        print("Pipeline shape:", df.shape)
    except Exception as _:
        print("Pipeline columns/shape: <unavailable>")
    
    # Process group-by vehicle to keep time series indices intact
    for vehicle_id, group in df.groupby("vehicle_id"):
        group = group.copy().sort_values("timestamp")
        
        # 24-hour windows (assuming 3 points per day, size=3)
        group["coolant_temp_roll_avg_24h"] = group["coolant_temp"].rolling(window=3, min_periods=1).mean()
        group["vibration_roll_avg_24h"] = group["vibration"].rolling(window=3, min_periods=1).mean()
        group["voltage_roll_avg_24h"] = group["voltage"].rolling(window=3, min_periods=1).mean()
        group["exhaust_temp_roll_avg_24h"] = group["exhaust_temp"].rolling(window=3, min_periods=1).mean()
        
        # 72-hour windows (size=9)
        group["coolant_temp_roll_avg_72h"] = group["coolant_temp"].rolling(window=9, min_periods=1).mean()
        group["vibration_roll_std_72h"] = group["vibration"].rolling(window=9, min_periods=1).std().fillna(0.0)
        group["exhaust_temp_roll_avg_72h"] = group["exhaust_temp"].rolling(window=9, min_periods=1).mean()
        
        # Feature: Temp ratio (deviation from longer term average)
        group["coolant_temp_trend"] = group["coolant_temp"] / (group["coolant_temp_roll_avg_72h"] + 1e-5)
        group["exhaust_temp_trend"] = group["exhaust_temp"] / (group["exhaust_temp_roll_avg_72h"] + 1e-5)
        
        # Feature: Voltage variance
        group["voltage_variance_72h"] = group["voltage"].rolling(window=9, min_periods=1).var().fillna(0.0)
        
        engineered_records.append(group)
        
    df_engineered = pd.concat(engineered_records, ignore_index=True)
    return df_engineered

def compute_telemetry_summaries(df_telemetry):
    """
    Computes overall statistics for SQLite database seed.
    """
    df = clean_telemetry(df_telemetry)
    summary = df.groupby("vehicle_id").agg(
        avg_coolant_temp=("coolant_temp", "mean"),
        max_coolant_temp=("coolant_temp", "max"),
        avg_rpm=("engine_rpm", "mean"),
        max_rpm=("engine_rpm", "max"),
        avg_oil_pressure=("oil_pressure", "mean"),
        min_oil_pressure=("oil_pressure", "min"),
        avg_vibration=("vibration", "mean"),
        max_vibration=("vibration", "max"),
        avg_voltage=("voltage", "mean"),
        min_voltage=("voltage", "min"),
        avg_exhaust_temp=("exhaust_temp", "mean"),
        max_exhaust_temp=("exhaust_temp", "max")
    ).reset_index()
    
    return summary
