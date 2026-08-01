import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, GradientBoostingClassifier, GradientBoostingRegressor
import os
import pickle

if os.environ.get("VERCEL"):
    MODEL_DIR = "/tmp/models"
else:
    MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")

os.makedirs(MODEL_DIR, exist_ok=True)

# Features we use for training our models
FEATURES = [
    "coolant_temp", "engine_rpm", "oil_pressure", "engine_load", 
    "vibration", "voltage", "exhaust_temp",
    "coolant_temp_roll_avg_24h", "vibration_roll_avg_24h", "voltage_roll_avg_24h",
    "exhaust_temp_roll_avg_24h", "coolant_temp_roll_avg_72h", "vibration_roll_std_72h",
    "exhaust_temp_roll_avg_72h", "coolant_temp_trend", "exhaust_temp_trend", "voltage_variance_72h"
]

# Baseline normal values for features (from healthy operations)
HEALTHY_MEANS = {
    "coolant_temp": 190.0, "engine_rpm": 1200.0, "oil_pressure": 50.0, "engine_load": 55.0,
    "vibration": 0.25, "voltage": 13.9, "exhaust_temp": 750.0 + 55.0 * 3,
    "coolant_temp_roll_avg_24h": 190.0, "vibration_roll_avg_24h": 0.25, "voltage_roll_avg_24h": 13.9,
    "exhaust_temp_roll_avg_24h": 915.0, "coolant_temp_roll_avg_72h": 190.0, "vibration_roll_std_72h": 0.02,
    "exhaust_temp_roll_avg_72h": 915.0, "coolant_temp_trend": 1.0, "exhaust_temp_trend": 1.0, "voltage_variance_72h": 0.0025
}

class FleetPredictiveModels:
    def __init__(self):
        self.anomaly_detector = None
        self.failure_classifier = None
        self.rul_regressor = None
        
    def save(self):
        with open(os.path.join(MODEL_DIR, "fleet_models.pkl"), "wb") as f:
            pickle.dump(self, f)
            
    @staticmethod
    def load():
        path = os.path.join(MODEL_DIR, "fleet_models.pkl")
        if os.path.exists(path):
            with open(path, "rb") as f:
                return pickle.load(f)
        return None

def train_ml_models(df_engineered):
    """
    Trains classification and regression models on engineered historical telemetry:
    - Isolation Forest for anomaly detection
    - Gradient Boosting Classifier for failure type (Healthy vs EGR/Coolant, Turbo, Alternator)
    - Gradient Boosting Regressor for RUL prediction
    """
    X = df_engineered[FEATURES].values
    
    # 1. Create labels for training
    # For simulation, we label points based on known vehicles and timestamps
    y_class = np.zeros(len(df_engineered), dtype=int)
    y_rul = np.full(len(df_engineered), 45.0) # Baseline healthy RUL is 45 days
    
    # We parse timestamp to see how close we are to the end of the simulation (30 days)
    df_temp = df_engineered.copy()
    df_temp["timestamp_dt"] = pd.to_datetime(df_temp["timestamp"])
    max_time = df_temp["timestamp_dt"].max()
    
    for idx, row in df_temp.iterrows():
        v_id = row["vehicle_id"]
        days_to_end = (max_time - row["timestamp_dt"]).days
        
        # TRK-427 (Volvo EGR/Coolant overheat failure on day 30, i.e., days_to_end -> 0)
        if v_id == "TRK-427":
            y_rul[idx] = max(0.0, days_to_end)
            if days_to_end <= 15:
                y_class[idx] = 1 # EGR Leak Failure Mode
                
        # TRK-454 (Freightliner Turbocharger failure on day 25, i.e., days_to_end -> 5)
        elif v_id == "TRK-454":
            y_rul[idx] = max(0.0, days_to_end - 5)
            if days_to_end <= 12:
                y_class[idx] = 2 # Turbo failure
                
        # TRK-481 (Kenworth Alternator electrical failure on day 28, i.e., days_to_end -> 2)
        elif v_id == "TRK-481":
            y_rul[idx] = max(0.0, days_to_end - 2)
            if days_to_end <= 10:
                y_class[idx] = 3 # Electrical/Alternator failure
                
        # Other healthy trucks have high RUL (40+ days) and are Class 0
        else:
            y_rul[idx] = 45.0 + np.random.uniform(-5, 0)
            y_class[idx] = 0

    # 2. Fit Isolation Forest
    # Fit only on features that indicate physical anomalies
    iso_features = ["coolant_temp", "vibration", "voltage", "exhaust_temp", "oil_pressure"]
    X_iso = df_engineered[iso_features].values
    iso = IsolationForest(n_estimators=100, contamination=0.1, random_state=42)
    iso.fit(X_iso)
    
    # 3. Fit Failure Classifier
    clf = GradientBoostingClassifier(n_estimators=50, random_state=42)
    clf.fit(X, y_class)
    
    # 4. Fit RUL Regressor
    reg = GradientBoostingRegressor(n_estimators=50, random_state=42)
    reg.fit(X, y_rul)
    
    # Pack and save
    models = FleetPredictiveModels()
    models.anomaly_detector = iso
    models.failure_classifier = clf
    models.rul_regressor = reg
    models.save()
    
    print("ML models successfully trained and cached.")
    return models

def explain_prediction(sample_features, model_importances):
    """
    Computes local feature attribution (SHAP-like explanation).
    Compares the current vehicle's telemetry features against baseline healthy means,
    weighted by the classifier's feature importances.
    """
    attributions = {}
    total_importance = sum(model_importances)
    
    for i, feature in enumerate(FEATURES):
        val = sample_features[i]
        healthy_mean = HEALTHY_MEANS.get(feature, 0.0)
        
        # Calculate directional deviation
        # For oil pressure and voltage, LOWER is generally worse (negative deviation is bad)
        # For coolant temp, exhaust temp, vibration, HIGHER is worse (positive deviation is bad)
        deviation = val - healthy_mean
        
        # Scale by importance to get relative contribution
        importance = model_importances[i] / (total_importance + 1e-9)
        
        # Directional attribution
        if feature in ["oil_pressure", "voltage", "voltage_roll_avg_24h"]:
            # Drop is bad
            contrib = -deviation * importance
        else:
            # Rise is bad
            contrib = deviation * importance
            
        attributions[feature] = float(contrib)
        
    # Group attributions into parent sensor groups for clean visualization
    sensor_groups = {
        "Coolant Temperature": ["coolant_temp", "coolant_temp_roll_avg_24h", "coolant_temp_roll_avg_72h", "coolant_temp_trend"],
        "Exhaust Temperature": ["exhaust_temp", "exhaust_temp_roll_avg_24h", "exhaust_temp_roll_avg_72h", "exhaust_temp_trend"],
        "Vibration & Mechanical": ["vibration", "vibration_roll_avg_24h", "vibration_roll_std_72h"],
        "Electrical / Voltage": ["voltage", "voltage_roll_avg_24h", "voltage_variance_72h"],
        "Oil Pressure": ["oil_pressure"],
        "Engine Load / RPM": ["engine_rpm", "engine_load"]
    }
    
    grouped_attrib = {}
    for group_name, features_in_group in sensor_groups.items():
        grouped_attrib[group_name] = sum(attributions.get(f, 0.0) for f in features_in_group)
        
    # Normalize contributions so they sum up to absolute total contribution (or scale to percentage)
    total_abs = sum(abs(v) for v in grouped_attrib.values()) + 1e-9
    for k in grouped_attrib:
        grouped_attrib[k] = round((grouped_attrib[k] / total_abs) * 100, 1)
        
    return grouped_attrib

def predict_vehicle_diagnostics(vehicle_id, df_engineered, models=None):
    """
    Computes real-time analytics for a specific vehicle's latest record:
    - Anomaly score
    - Failure probability
    - Predicted RUL
    - Feature attributions (SHAP-like)
    """
    if models is None:
        models = FleetPredictiveModels.load()
        if models is None:
            raise FileNotFoundError("ML Models not trained or loaded. Please train first.")
            
    v_data = df_engineered[df_engineered["vehicle_id"] == vehicle_id].sort_values("timestamp")
    if len(v_data) == 0:
        return {"error": f"No telemetry found for vehicle {vehicle_id}"}
        
    latest_row = v_data.iloc[-1]
    X_sample = latest_row[FEATURES].values.reshape(1, -1)
    
    # 1. Anomaly detection (Isolation Forest)
    # Isolation Forest decision_function returns negative values for anomalies, positive for normal
    iso_features = ["coolant_temp", "vibration", "voltage", "exhaust_temp", "oil_pressure"]
    X_iso_sample = latest_row[iso_features].values.reshape(1, -1)
    # Score mapped to 0-100 (0 = highly anomalous, 100 = completely normal)
    raw_anomaly_score = models.anomaly_detector.decision_function(X_iso_sample)[0]
    anomaly_pct = float(np.clip((raw_anomaly_score + 0.5) * 100, 0, 100))
    
    # 2. Failure probability classification
    class_probs = models.failure_classifier.predict_proba(X_sample)[0]
    failure_classes = ["Healthy", "EGR/Coolant Leak", "Turbocharger Underboost", "Electrical System Decay"]
    pred_class_idx = np.argmax(class_probs)
    pred_class = failure_classes[pred_class_idx]
    
    # 3. RUL Regression
    pred_rul = float(models.rul_regressor.predict(X_sample)[0])
    # Clamp RUL between 0 and 45 days
    pred_rul = max(0.0, min(45.0, pred_rul))
    
    # 4. Feature attribution (SHAP)
    # Use classifier feature importances or regressor feature importances depending on state
    # We use failure classifier feature importances for explaining faults
    model_importances = models.failure_classifier.feature_importances_
    attributions = explain_prediction(latest_row[FEATURES].values, model_importances)
    
    # Determine overall status label
    if pred_class_idx > 0:
        status_label = "Critical" if pred_rul < 7 else "Warning"
    else:
        status_label = "Healthy"
        
    return {
        "vehicle_id": vehicle_id,
        "timestamp": latest_row["timestamp"],
        "anomaly_score": round(100 - anomaly_pct, 1), # High anomaly score = high risk
        "failure_class": pred_class,
        "failure_probabilities": {failure_classes[i]: round(float(prob) * 100, 1) for i, prob in enumerate(class_probs)},
        "predicted_rul": round(pred_rul, 1),
        "status": status_label,
        "feature_attributions": attributions,
        "raw_sensor_values": {
            "coolant_temp": float(latest_row["coolant_temp"]),
            "engine_rpm": float(latest_row["engine_rpm"]),
            "oil_pressure": float(latest_row["oil_pressure"]),
            "engine_load": float(latest_row["engine_load"]),
            "vibration": float(latest_row["vibration"]),
            "voltage": float(latest_row["voltage"]),
            "exhaust_temp": float(latest_row["exhaust_temp"])
        }
    }
