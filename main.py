import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import numpy as np
import time
import json 

app = FastAPI(
    title="Gridlock AI Anomaly Detection API",
    description="Detects electricity theft from real-time sensor data.",
    version="1.0.0"
)

LIVE_STATUS_FILE = "live_status.json"

class SensorReading(BaseModel):
    voltage: float
    current: float
    power: float
    power_factor: float 

try:
    model_path = r"ai_model/gridlock_model.pkl"
    scaler_path = r"ai_model/scaler.pkl"
    
    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    print("--- AI Model and Scaler loaded successfully ---")
except Exception as e:
    print(f"--- 💥 CRITICAL ERROR 💥 --- Could not load models: {e}")
    model = None
    scaler = None

@app.post("/predict")
def predict(data: SensorReading):
    if not model or not scaler:
        raise HTTPException(status_code=503, detail="Model not loaded. Check server logs.")

    try:
        v, i, p, pf = data.voltage, data.current, data.power, data.power_factor
        features = np.array([[v, i, p, pf]])
        features_scaled = scaler.transform(features)
        prob_anomaly = model.predict_proba(features_scaled)[0, 1]
        is_anomaly = bool(prob_anomaly > 0.75)
        
        result = {
            "timestamp": time.time(),
            "voltage": v,
            "current": i,
            "power": p,
            "power_factor": pf,
            "anomaly_score": round(float(prob_anomaly), 4),
            "anomaly": is_anomaly,
        }

        try:
            with open(LIVE_STATUS_FILE, "w") as f:
                json.dump(result, f)
        except Exception as e:
            print(f"Error writing to {LIVE_STATUS_FILE}: {e}")

        return result

    except Exception as e:
        print(f"Error during prediction: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction error: {e}")

if __name__ == "__main__":
    try:
        with open(LIVE_STATUS_FILE, "w") as f:
            json.dump({"status": "Server is starting..."}, f)
    except:
        pass
        
    print("Starting server... Go to http://127.0.0.1:8000/docs for API docs.")