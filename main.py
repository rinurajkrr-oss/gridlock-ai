import uvicorn
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
import joblib
import numpy as np
import pandas as pd 
import time
import json
import os
import requests
from ledger_web3.ledger import add_to_ledger
import smtplib
from email.message import EmailMessage
from datetime import datetime

from sklearn.model_selection import train_test_split 
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

PUBLIC_WEBHOOK_URL = "https://webhook.site/f6e88887-23de-4e00-8973-b72a9de4fc72" 

LIVE_STATUS_FILE = "live_status.json"
FEEDBACK_LOG = "user_feedback_data.csv"
MODEL_PATH = "ai_model/gridlock_model.pkl"
SCALER_PATH = "ai_model/scaler.pkl"
ORIGINAL_DATASET = "gridlock_dataset.csv" 

SENDER_EMAIL = "nithila.ramasamy2024@vitstudent.ac.in" 
SENDER_PASSWORD = "najl kxra onia alvd" 
RECEIVER_EMAIL = "gridlockai.alerts@gmail.com" 
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

HIGH_CURRENT_THRESHOLD = 15.0; LOW_PF_THRESHOLD = 0.70; VOLTAGE_SAG_THRESHOLD = 210.0

app = FastAPI(
    title="GRIDLOCK AI API (v2.12 - Retraining)",
    description="Real-time AI Anomaly Detection with Retraining, Cause Suggestion, Web3 Proof, Adaptive Learning, and Email Alerts.",
    version="2.12.0"
)

model = None
scaler = None

def load_models():
    """Loads model and scaler from files into global variables."""
    global model, scaler
    try:
        model = joblib.load(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)
        print("--- ✅ AI Model and Scaler loaded successfully ---")
        return True
    except FileNotFoundError:
        print(f"--- 💥 CRITICAL ERROR: Could not find model at: {MODEL_PATH} or {SCALER_PATH} ---")
        model = None; scaler = None; return False
    except Exception as e:
        print(f"--- 💥 CRITICAL ERROR: Error loading model: {e} ---")
        model = None; scaler = None; return False

models_loaded = load_models() 

if not PUBLIC_WEBHOOK_URL.startswith("https"): print("--- 💥 WARNING: PUBLIC_WEBHOOK_URL is not set. ---")

class SensorReading(BaseModel): voltage: float; current: float; power: float; power_factor: float
class FeedbackData(BaseModel): data: dict; response: str

def send_real_email(subject, body, to_email):
     if not SENDER_EMAIL or not SENDER_PASSWORD or SENDER_EMAIL == "your_gmail_address@gmail.com":
        print("--- 📧 Email not configured. Skipping send_real_email. ---")
        return False
     try:
        msg = EmailMessage(); msg["From"] = SENDER_EMAIL; msg["To"] = to_email; msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.starttls(); smtp.login(SENDER_EMAIL, SENDER_PASSWORD); smtp.send_message(msg)
        print(f"--- 📧 REAL Email sent successfully to {to_email} ---")
        return True
     except Exception as e:
        print(f"--- 💥 ERROR: Failed to send REAL email: {e} ---"); return False

def post_to_public_ledger(public_hash, timestamp):
    if not PUBLIC_WEBHOOK_URL.startswith("https"): return
    try:
        payload = {"proof_type": "GRIDLOCK_ANOMALY_HASH", "timestamp": timestamp, "hash": public_hash}
        requests.post(PUBLIC_WEBHOOK_URL, json=payload, timeout=3)
        print(f"--- 🌎 Public proof posted to Webhook ---")
    except Exception as e: print(f"--- 💥 ERROR: Could not post public proof: {e} ---")


def log_user_feedback(data_payload, response_type):
    print(f"--- ✅ Logging Feedback: '{response_type}' ---")
    suggested_cause = data_payload.get('suggested_cause', 'N/A')
    log_payload = {
        'voltage': data_payload.get('voltage', 'N/A'),
        'current': data_payload.get('current', 'N/A'),
        'power': data_payload.get('power', 'N/A'),
        'power_factor': data_payload.get('power_factor', 'N/A')
    }
    log_payload['Label'] = 0 if response_type == "normal" else 1
    file_exists = os.path.isfile(FEEDBACK_LOG)
    try:
        with open(FEEDBACK_LOG, "a") as f:
            if not file_exists:
                f.write("voltage,current,power,power_factor,suggested_cause,Label\n")
            f.write(f"{log_payload['voltage']},{log_payload['current']},{log_payload['power']},{log_payload['power_factor']},{suggested_cause},{log_payload['Label']}\n")
        print(f"--- Feedback saved to {FEEDBACK_LOG} ---"); return True
    except Exception as e: print(f"--- 💥 ERROR: Could not write feedback log: {e} ---"); return False


def suggest_anomaly_cause(data_payload):
    v = data_payload.get('voltage', 230); i = data_payload.get('current', 0); pf = data_payload.get('power_factor', 1.0)
    if i > HIGH_CURRENT_THRESHOLD:
        return "High Current & Voltage Sag (Possible Short Circuit / Major Fault)" if v < VOLTAGE_SAG_THRESHOLD else "Sustained High Current (Possible Theft or Overload)"
    elif pf < LOW_PF_THRESHOLD: return "Low Power Factor (Possible Industrial Motor Issue / Faulty Appliance)"
    elif v < VOLTAGE_SAG_THRESHOLD: return "Significant Voltage Sag (Possible Grid Fault / Brownout)"
    else: return "Unusual Pattern Detected (Check System)"

def perform_retraining():
    """Loads data, combines, retrains model/scaler, saves, and reloads."""
    global model, scaler 
    print("\n--- 🔄 Starting AI Retraining Process... ---")
    try:
        if not os.path.exists(ORIGINAL_DATASET):
            print(f"--- 💥 ERROR: Original dataset '{ORIGINAL_DATASET}' not found. Cannot retrain. ---")
            return
        df_original = pd.read_csv(ORIGINAL_DATASET)
        print(f"- Loaded {len(df_original)} samples from original dataset.")

        if not os.path.exists(FEEDBACK_LOG):
            print(f"--- ℹ️ INFO: Feedback log '{FEEDBACK_LOG}' not found. Training only on original data. ---")
            df_feedback = pd.DataFrame()
        else:
            df_feedback = pd.read_csv(FEEDBACK_LOG)
            feedback_cols = ['voltage', 'current', 'power', 'power_factor', 'Label']
            df_feedback = df_feedback[feedback_cols]
            print(f"- Loaded {len(df_feedback)} samples from feedback log.")

        df_combined = pd.concat([df_original, df_feedback], ignore_index=True)
        df_combined = df_combined.drop_duplicates()
        print(f"- Combined dataset size: {len(df_combined)} samples.")

        features = ['voltage', 'current', 'power', 'power_factor']
        X = df_combined[features]
        y = df_combined['Label']

        new_scaler = StandardScaler()
        X_scaled = new_scaler.fit_transform(X) 
        print("- Scaler retrained.")

        new_model = RandomForestClassifier(n_estimators=100, random_state=42) 
        new_model.fit(X_scaled, y)
        print("- Model retrained.")

        joblib.dump(new_model, MODEL_PATH)
        joblib.dump(new_scaler, SCALER_PATH)
        print(f"- New model saved to: {MODEL_PATH}")
        print(f"- New scaler saved to: {SCALER_PATH}")

        model = new_model
        scaler = new_scaler
        print("--- ✅ AI Model and Scaler reloaded into memory. ---")
        print("--- ✅ Retraining Complete! ---")

    except Exception as e:
        print(f"--- 💥 ERROR during retraining: {e} ---")

@app.post("/predict")
def predict(data: SensorReading):
    global model, scaler 
    if not model or not scaler: raise HTTPException(status_code=503, detail="Model not loaded.")

    try:
        v, i, p, pf = data.voltage, data.current, data.power, data.power_factor
        features = np.array([[v, i, p, pf]])
        features_scaled = scaler.transform(features)
        prob_anomaly = model.predict_proba(features_scaled)[0, 1]
        is_anomaly = bool(prob_anomaly > 0.75)

        data_payload = {"voltage": v, "current": i, "power": p, "power_factor": pf}

        suggested_cause = None
        if is_anomaly:
            suggested_cause = suggest_anomaly_cause(data_payload)

        result = {
            "timestamp": time.time(), "payload": data_payload,
            "anomaly_score": round(float(prob_anomaly), 4), "anomaly": is_anomaly,
            "suggested_cause": suggested_cause
        }

        with open(LIVE_STATUS_FILE, "w") as f: json.dump(result, f)

        if is_anomaly:
            anomaly_id = f"data_{int(time.time())}"
            email_body = f"""
Dear User, An anomaly was detected.
Score: {result['anomaly_score']:.4f}, Suggested Cause: {suggested_cause}
Data: V={v:.1f}, A={i:.1f}, W={p:.1f}, PF={pf:.2f}
Was this you? Click a link:
--> Normal: http://127.0.0.1:8000/feedback?id={anomaly_id}&response=normal
--> Theft: http://127.0.0.1:8000/feedback?id={anomaly_id}&response=theft
- Gridlock AI
"""
            send_real_email("GRIDLOCK AI: ANOMALY DETECTED!", email_body, RECEIVER_EMAIL)

            temp_data_for_feedback = data_payload.copy()
            temp_data_for_feedback['suggested_cause'] = suggested_cause
            with open(f"{anomaly_id}.json", "w") as f: json.dump(temp_data_for_feedback, f)

        return result

    except Exception as e:
        print(f"Error during prediction: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction error: {e}")


@app.get("/feedback")
def handle_email_feedback(id: str, response: str):
    if response not in ["normal", "theft"]: raise HTTPException(status_code=400, detail="Invalid response.")
    data_file = f"{id}.json";
    if not os.path.exists(data_file): raise HTTPException(status_code=404, detail="Data ID not found.")

    try:
        with open(data_file, "r") as f: data_payload_with_cause = json.load(f)
        data_payload = {k: v for k, v in data_payload_with_cause.items() if k != 'suggested_cause'}
        log_user_feedback(data_payload_with_cause, response) 

        if response == "theft":
            print("--- ⚖️ EMAIL CONFIRMED THEFT - Triggering Web3/Follow-up ---")
            dummy_result = {"timestamp": time.time(), "payload": data_payload_with_cause, "anomaly_score": "N/A (Email Confirmed)"}
            public_hash, timestamp = add_to_ledger(dummy_result)
            if public_hash: post_to_public_ledger(public_hash, timestamp)
            follow_up_subject = "ACTION REQUIRED: Gridlock AI Theft/Fault Confirmed"
            follow_up_body = f"""
Dear User, You confirmed the anomaly was NOT you.
Suggested Cause: {data_payload_with_cause.get('suggested_cause', 'N/A')}
Details: V={data_payload.get('voltage', 'N/A'):.1f}V, A={data_payload.get('current', 'N/A'):.1f}A...
RECOMMENDATION: Contact electrician. Evidence secured.
- Gridlock AI Security Team
"""
            send_real_email(follow_up_subject, follow_up_body, RECEIVER_EMAIL)

        os.remove(data_file)
        return {"status": "success", "message": f"Feedback '{response}' logged. Close tab."}
    except Exception as e:
        error_message = f"Error processing feedback: {id}: {str(e)}"; print(f"--- 💥 ERROR: {error_message} ---")
        return {"status": "error", "message": error_message}


@app.post("/feedback_dashboard")
async def handle_dashboard_feedback(feedback: FeedbackData):
     try:
        data_payload = feedback.data 
        response_type = feedback.response
        log_user_feedback(data_payload, response_type) 
        if response_type == "theft":
            print("--- ⚖️ DASHBOARD CONFIRMED THEFT - Triggering Web3 ---")
            dummy_result = {"timestamp": time.time(), "payload": data_payload, "anomaly_score": "N/A (Dashboard Confirmed)"}
            public_hash, timestamp = add_to_ledger(dummy_result)
            if public_hash: post_to_public_ledger(public_hash, timestamp)

        return {"status": "success", "message": "Feedback logged."}

     except Exception as e: raise HTTPException(status_code=500, detail=f"Error processing feedback: {e}")

@app.post("/retrain")
async def trigger_retraining(background_tasks: BackgroundTasks):
    """Triggers the AI retraining process in the background."""
    print("--- Received request to retrain AI model. ---")
    background_tasks.add_task(perform_retraining)
    return {"status": "success", "message": "AI retraining process started in the background."}

if __name__ == "__main__":
    if not models_loaded: print("--- 💥 SERVER CANNOT START: Model/Scaler failed initial load. ---")
    else:
        print("--- Server starting... ---")
        uvicorn.run(app, host="127.0.0.1", port=8000)
