import streamlit as st
import pandas as pd
import time
import json
import os
import requests
from ledger_web3.ledger import verify_ledger 

try: from gtts import gTTS; GTTS_ENABLED = True
except ImportError: print("WARNING: gTTS not found. Voice alerts disabled."); GTTS_ENABLED = False

st.set_page_config(page_title="GRIDLOCK AI", page_icon="⚡", layout="wide")
LIVE_STATUS_FILE = "live_status.json"
LEDGER_FILE = "web3_ledger.json"
FEEDBACK_LOG = "user_feedback_data.csv"
VOICE_ALERT_FILE = "alert.mp3"
BACKEND_URL_FEEDBACK = "http://127.0.0.1:8000/feedback_dashboard" 
BACKEND_URL_RETRAIN = "http://127.0.0.1:8000/retrain" 

if "public_webhook_url" not in st.session_state: st.session_state.public_webhook_url = ""
if 'chart_data' not in st.session_state: st.session_state.chart_data = pd.DataFrame(columns=["timestamp", "Power"])
if 'anomaly_in_progress' not in st.session_state: st.session_state.anomaly_in_progress = False
if 'anomaly_data_payload' not in st.session_state: st.session_state.anomaly_data_payload = None
if 'anomaly_trigger_score' not in st.session_state: st.session_state.anomaly_trigger_score = 0.75
if 'feedback_given' not in st.session_state: st.session_state.feedback_given = None 
if 'voice_played' not in st.session_state: st.session_state.voice_played = False
if 'current_anomaly_threshold' not in st.session_state: st.session_state.current_anomaly_threshold = 0.75 
if 'threshold_override_time' not in st.session_state: st.session_state.threshold_override_time = 0 
if 'suggested_cause' not in st.session_state: st.session_state.suggested_cause = None 
if 'retraining_status' not in st.session_state: st.session_state.retraining_status = "" 

@st.cache_resource
def generate_voice_alert():
    if not GTTS_ENABLED: return None
    try:
        if not os.path.exists(VOICE_ALERT_FILE):
            tts = gTTS("Warning, grid anomaly detected. Please check the system.", lang='en', tld='com')
            tts.save(VOICE_ALERT_FILE)
        return open(VOICE_ALERT_FILE, 'rb').read()
    except Exception as e: print(f"Error generating voice: {e}"); return None

def play_voice_alert(audio_bytes):
    if audio_bytes and GTTS_ENABLED: st.audio(audio_bytes, format='audio/mp3', autoplay=True)

@st.cache_data(ttl=1)
def get_live_data():
    if not os.path.exists(LIVE_STATUS_FILE): return None
    try:
        with open(LIVE_STATUS_FILE, "r") as f: return json.load(f)
    except: return None

@st.cache_data(ttl=5)
def load_ledger_file():
    if os.path.exists(LEDGER_FILE):
        try: return pd.read_json(LEDGER_FILE)
        except: return pd.DataFrame()
    return pd.DataFrame()

@st.cache_data(ttl=5)
def load_feedback_file():
    if os.path.exists(FEEDBACK_LOG):
        try: return pd.read_csv(FEEDBACK_LOG)
        except: return pd.DataFrame()
    return pd.DataFrame()

def submit_feedback_to_backend(data, response):
    """Sends feedback to backend, logs locally, clears caches."""
    log_payload = data.copy() if data else {}
    log_payload['Label'] = 0 if response == "normal" else 1
    file_exists = os.path.isfile(FEEDBACK_LOG)
    try:
        with open(FEEDBACK_LOG, "a") as f:
            if not file_exists: f.write("voltage,current,power,power_factor,suggested_cause,Label\n")
            f.write(f"{log_payload.get('voltage','N/A')},{log_payload.get('current','N/A')},{log_payload.get('power','N/A')},{log_payload.get('power_factor','N/A')},{log_payload.get('suggested_cause','N/A')},{log_payload.get('Label')}\n")
        load_feedback_file.clear()
    except Exception as e: print(f"Error writing local feedback log: {e}")

    if response == "theft" and data:
        try:
            payload = {"data": data, "response": response}
            requests.post(BACKEND_URL_FEEDBACK, json=payload)
            load_ledger_file.clear()
        except Exception as e:
            st.error(f"Error submitting feedback to backend: {e}")

def trigger_retraining():
    """Sends a request to the backend to start retraining."""
    try:
        response = requests.post(BACKEND_URL_RETRAIN)
        if response.status_code == 200:
            st.session_state.retraining_status = "⏳ Retraining started in background..."
            load_feedback_file.clear() 
        else:
            st.session_state.retraining_status = f"❌ Error starting retraining: {response.text}"
    except Exception as e:
        st.session_state.retraining_status = f"❌ Connection error during retraining request: {e}"

with st.sidebar:
    st.header("Public Proof")
    st.session_state.public_webhook_url = st.text_input("Webhook URL", value=st.session_state.public_webhook_url)
    if st.session_state.public_webhook_url.startswith("https://webhook.site"):
        st.link_button("View Public Proof", st.session_state.public_webhook_url, use_container_width=True)
    else: st.warning("Get URL from webhook.site")

    st.divider()
    st.header("AI Management")
    if st.button("🧠 Retrain AI with Latest Feedback", use_container_width=True):
        trigger_retraining()
    if st.session_state.retraining_status:
        st.info(st.session_state.retraining_status)


st.title("⚡ GRIDLOCK AI")
col_live, col_feedback = st.columns([2, 1])
with col_live: st.subheader("Live Grid Status"); live_placeholder = st.empty()
with col_feedback: st.subheader("Anomaly Response"); feedback_placeholder = st.empty()
st.subheader("Live Power Chart"); chart_placeholder = st.empty()

audio_bytes = generate_voice_alert()
live_data = get_live_data()
run_loop = True

if live_data:
    df_chart = st.session_state.chart_data
    now = pd.to_datetime(live_data['timestamp'], unit='s')
    new_row = pd.DataFrame({"timestamp": [now], "Power": [live_data['payload']['power']]})
    df_chart = pd.concat([df_chart, new_row], ignore_index=True).tail(100)
    st.session_state.chart_data = df_chart
    chart_df_indexed = df_chart.set_index('timestamp')
    chart_placeholder.line_chart(chart_df_indexed, y="Power")

    score = live_data.get('anomaly_score', 0)
    if time.time() > st.session_state.threshold_override_time: st.session_state.current_anomaly_threshold = 0.75 
    is_anomaly = bool(score > st.session_state.current_anomaly_threshold)
    suggested_cause = live_data.get('suggested_cause', None) 

    with live_placeholder.container():
        c1, c2, c3 = st.columns(3)
        c1.metric("V", f"{live_data['payload']['voltage']:.2f}")
        c2.metric("A", f"{live_data['payload']['current']:.2f}")
        c3.metric("W", f"{live_data['payload']['power']:.2f}")

        if is_anomaly:
            status_text = f"**STATUS: 🚨 ANOMALY!** (Score: {score:.3f} > {st.session_state.current_anomaly_threshold:.2f})"
            st.error(status_text)
            if not st.session_state.anomaly_in_progress: 
                st.session_state.anomaly_in_progress = True
                st.session_state.anomaly_data_payload = live_data['payload'] 
                st.session_state.anomaly_trigger_score = score
                st.session_state.suggested_cause = suggested_cause 
                st.session_state.feedback_given = None 
                st.session_state.voice_played = False 
        else:
            status_text = f"**STATUS: ✅ NORMAL** (Score: {score:.3f} <= {st.session_state.current_anomaly_threshold:.2f})"
            st.success(status_text)
            if st.session_state.anomaly_in_progress and st.session_state.feedback_given != "theft_confirmed": 
                st.session_state.anomaly_in_progress = False
                st.session_state.anomaly_data_payload = None
                st.session_state.feedback_given = None
                st.session_state.suggested_cause = None

else:
    chart_placeholder.info("Waiting for live data feed...")
    with live_placeholder.container(): st.info("Waiting for live data feed...")
    run_loop = True

if st.session_state.anomaly_in_progress:

    if st.session_state.feedback_given:
        if st.session_state.feedback_given == "adapted":
            feedback_placeholder.success(f"""
                ✅ **AI ADAPTED (Simulated)**
                Feedback logged.
                Previous Threshold: 0.75
                New Temporary Threshold: 0.99
                *(Resets after 30s or normal data)*
            """)
            run_loop = True 

        elif st.session_state.feedback_given == "theft_confirmed":
            feedback_placeholder.error("🚨 **THEFT/FAULT CONFIRMED!** System Halted. Check ledger for proof.")
            run_loop = False

    else:
        run_loop = False 

        if not st.session_state.voice_played:
            play_voice_alert(audio_bytes); st.session_state.voice_played = True

        @st.dialog("Anomaly Detected!")
        def show_anomaly_dialog():
            st.warning("**An anomaly was detected! Was this you?**")
            st.write(f"Trigger Score: {st.session_state.anomaly_trigger_score:.3f}")
            if st.session_state.suggested_cause:
                st.info(f"Suggested Cause: {st.session_state.suggested_cause}")
            st.write(f"Data: V={st.session_state.anomaly_data_payload.get('voltage','N/A'):.1f}, A={st.session_state.anomaly_data_payload.get('current','N/A'):.1f}, W={st.session_state.anomaly_data_payload.get('power','N/A'):.1f}")


            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("Yes, this was me (Adapt)", use_container_width=True):
                    st.session_state.current_anomaly_threshold = 0.99
                    st.session_state.threshold_override_time = time.time() + 30 
                    st.session_state.feedback_given = "adapted"
                    payload_to_log = st.session_state.anomaly_data_payload.copy() if st.session_state.anomaly_data_payload else {}
                    payload_to_log['suggested_cause'] = st.session_state.suggested_cause
                    submit_feedback_to_backend(payload_to_log, "normal")
                    st.rerun() 

            with col_no:
                if st.button("No, this was NOT me (Confirm Theft!)", type="primary", use_container_width=True):
                    st.session_state.feedback_given = "theft_confirmed"
                    payload_to_send = st.session_state.anomaly_data_payload.copy() if st.session_state.anomaly_data_payload else {}
                    payload_to_send['suggested_cause'] = st.session_state.suggested_cause
                    submit_feedback_to_backend(payload_to_send, "theft") 
                    st.rerun() 

        if st.session_state.anomaly_data_payload:
             show_anomaly_dialog()
        else: 
             st.session_state.anomaly_in_progress = False
             run_loop = True

else:
    feedback_placeholder.info("Awaiting anomaly detection...")
    run_loop = True

st.divider()
col_ledger, col_adaptive = st.columns(2)
with col_ledger:
    st.subheader("Local Tamper-Proof Ledger")
    if st.button("Verify Local Ledger"):
        if verify_ledger(): st.success("✅ VALID")
        else: st.error("🚨 TAMPERED!")
    ledger_df = load_ledger_file()
    if not ledger_df.empty: st.dataframe(ledger_df.iloc[::-1], height=300, use_container_width=True)
    else: st.info("No confirmed theft events.")

with col_adaptive:
    st.subheader("User Feedback Log")
    feedback_df = load_feedback_file()
    if not feedback_df.empty: st.dataframe(feedback_df.iloc[::-1], height=300, use_container_width=True)
    else: st.info("No user feedback logged.")

if run_loop:
    time.sleep(3)
    st.rerun()
