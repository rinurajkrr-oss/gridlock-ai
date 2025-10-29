import uvicorn
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import joblib
import numpy as np
import time
import json
import os
import requests 
from ledger_web3.ledger import add_to_ledger 

PUBLIC_WEBHOOK_URL = "https://webhook.site/f6e88887-23de-4e00-8973-b72a9de4fc72" 

LIVE_STATUS_FILE = "live_status.json"
FEEDBACK_LOG = "user_feedback_data.csv"
MODEL_PATH = "ai_model/gridlock_model.pkl"
SCALER_PATH = "ai_model/scaler.pkl"

app = FastAPI(
    title="GRIDLOCK AI API (v2.1)",
    description="Real-time AI Anomaly Detection with Web3 Proof and Adaptive Learning.",
    version="2.1.0"
)

try:
    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    print("--- ✅ AI Model and Scaler loaded successfully ---")
except FileNotFoundError:
    print(f"--- 💥 CRITICAL ERROR 💥 ---")
    print(f"Could not find model at: {MODEL_PATH} or {SCALER_PATH}")
    model = None
    scaler = None
except Exception as e:
    print(f"--- 💥 CRITICAL ERROR 💥 ---")
    print(f"Error loading model: {e}")
    model = None
    scaler = None

if not PUBLIC_WEBHOOK_URL.startswith("https"):
    print("--- 💥 WARNING 💥 ---")
    print("PUBLIC_WEBHOOK_URL is not set. Un-tamperable proof will not be posted.")
    print("Get your URL from https://webhook.site and paste it at the top of this file.")
    print("-------------------------")

class SensorReading(BaseModel):
    voltage: float
    current: float
    power: float
    power_factor: float

class FeedbackData(BaseModel):
    data: dict
    response: str  

def send_email_alert(anomaly_data, anomaly_id):
    """Simulates sending an interactive email alert."""
    print("\n--- 📧 SIMULATING EMAIL ALERT 📧 ---")
    print(f"TO: admin@gridlock.com")
    print(f"SUBJECT: GRIDLOCK AI: ANOMALY DETECTED!")
    print(f"BODY:")
    print(f"An anomaly was detected with score: {anomaly_data['anomaly_score']:.4f}")
    print(f"Data: {anomaly_data['payload']}")
    print("\nWas this you? (Click a link to help the AI learn)")
    print(f"  --> This was me (Normal): http://127.0.0.1:8000/feedback?id={anomaly_id}&response=normal")
    print(f"  --> This was NOT me (Theft): http://127.0.0.1:8000/feedback?id={anomaly_id}&response=theft")
    print("--------------------------------------\n")

def post_to_public_ledger(public_hash, timestamp):
    """Sends the un-tamperable proof to the public webhook."""
    if not PUBLIC_WEBHOOK_URL.startswith("https"):
        return  

    try:
        proof_payload = {
            "proof_type": "GRIDLOCK_ANOMALY_HASH",
            "timestamp": timestamp,
            "hash": public_hash
        }
        requests.post(PUBLIC_WEBHOOK_URL, json=proof_payload, timeout=3)
        print(f"--- 🌎 Public proof posted to Webhook ---")
    except Exception as e:
        print(f"--- 💥 ERROR 💥 ---")
        print(f"Could not post public proof to webhook: {e}")

def log_user_feedback(data_payload, response_type):
    """Logs the user's feedback to a CSV file for future AI retraining."""
    print(f"--- 🤖 ADAPTIVE AI 🤖 ---")
    print(f"Logging user feedback: This was '{response_type}'")
    
    data_payload['Label'] = 0 if response_type == "normal" else 1
    
    file_exists = os.path.isfile(FEEDBACK_LOG)
    
    try:
        with open(FEEDBACK_LOG, "a") as f:
            if not file_exists:
                f.write("voltage,current,power,power_factor,Label\n")
            
            f.write(f"{data_payload['voltage']},{data_payload['current']},{data_payload['power']},{data_payload['power_factor']},{data_payload['Label']}\n")
        
        print(f"--- ✅ New training data saved to {FEEDBACK_LOG} ---")
        return True
    except Exception as e:
        print(f"--- 💥 ERROR 💥 ---")
        print(f"Could not write to feedback log: {e}")
        return False

@app.post("/predict")
def predict(data: SensorReading):
    """Main endpoint: Receives data, runs AI, and triggers all alerts."""
    if not model or not scaler:
        raise HTTPException(status_code=503, detail="Model not loaded. Check server logs.")

    try:
        v, i, p, pf = data.voltage, data.current, data.power, data.power_factor
        features = np.array([[v, i, p, pf]])
        features_scaled = scaler.transform(features)
        
        prob_anomaly = model.predict_proba(features_scaled)[0, 1]
        is_anomaly = bool(prob_anomaly > 0.75)
        
        data_payload = {
            "voltage": v, "current": i, "power": p, "power_factor": pf
        }
        
        result = {
            "timestamp": time.time(),
            "payload": data_payload,
            "anomaly_score": round(float(prob_anomaly), 4),
            "anomaly": is_anomaly,
        }
        
        with open(LIVE_STATUS_FILE, "w") as f:
            json.dump(result, f)
            
        if is_anomaly:
            anomaly_id = f"data_{int(time.time())}"
            with open(f"{anomaly_id}.json", "w") as f:
                json.dump(data_payload, f)
                
            send_email_alert(result, anomaly_id)
            

        return result
        
    except Exception as e:
        print(f"Error during prediction: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction error: {e}")

@app.get("/feedback")
def handle_email_feedback(id: str, response: str):
    """Handles the "Yes/No" click from the SIMULATED EMAIL."""
    if response not in ["normal", "theft"]:
        raise HTTPException(status_code=400, detail="Invalid response.")
    
    data_file = f"{id}.json"
    if not os.path.exists(data_file):
        raise HTTPException(status_code=404, detail="Data ID not found or already processed.")
    
    try:
        with open(data_file, "r") as f:
            data_payload = json.load(f)
        
        log_user_feedback(data_payload, response)
        
        if response == "theft":
            print("--- ⚖️ EMAIL CONFIRMED THEFT ⚖️ ---")
            dummy_result = {"timestamp": time.time(), "payload": data_payload, "anomaly_score": "N/A (Email Confirmed)"}
            public_hash, timestamp = add_to_ledger(dummy_result)
            if public_hash:
                post_to_public_ledger(public_hash, timestamp)
        
        os.remove(data_file)
        
        return {"status": "success", "message": f"Feedback '{response}' logged. You can close this tab."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/feedback_dashboard")
async def handle_dashboard_feedback(feedback: FeedbackData):
    """Handles the "Yes/No" click from the Streamlit Dashboard."""
    try:
        data_payload = feedback.data
        response_type = feedback.response
        
        log_user_feedback(data_payload, response_type)
        
        if response_type == "theft":
            print("--- ⚖️ DASHBOARD CONFIRMED THEFT ⚖️ ---")
            dummy_result = {"timestamp": time.time(), "payload": data_payload, "anomaly_score": "N/A (Dashboard Confirmed)"}
            public_hash, timestamp = add_to_ledger(dummy_result)
            if public_hash:
                post_to_public_ledger(public_hash, timestamp)
        
        return {"status": "success", "message": "Feedback logged."}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing feedback: {e}")

if __name__ == "__main__":
    if not model or not scaler:
        print("--- 💥 SERVER CANNOT START 💥 ---")
        print("Model or Scaler failed to load. Please check file paths.")
    else:
        print("--- Server starting... ---")
        print("Go to http://127.0.0.1:8000/docs for API docs.")
        uvicorn.run(app, host="127.0.0.1", port=8000)
