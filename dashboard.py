import streamlit as st
import pandas as pd
import time
import json
import os
import requests
from ledger_web3.ledger import verify_ledger

try:
    from gtts import gTTS
    GTTS_ENABLED = True
except ImportError:
    print("WARNING: gTTS library not found. Voice alerts will be disabled.")
    GTTS_ENABLED = False

st.set_page_config(
    page_title="GRIDLOCK AI Dashboard",
    page_icon="⚡",
    layout="wide"
)

LIVE_STATUS_FILE = "live_status.json"
LEDGER_FILE = "web3_ledger.json"
FEEDBACK_LOG = "user_feedback_data.csv" 
VOICE_ALERT_FILE = "alert.mp3"
BACKEND_URL = "http://127.0.0.1:8000/feedback_dashboard" 

if "public_webhook_url" not in st.session_state:
    st.session_state.public_webhook_url = ""
if 'chart_data' not in st.session_state:
    st.session_state.chart_data = pd.DataFrame(columns=["timestamp", "Power"])
if 'anomaly_in_progress' not in st.session_state:
    st.session_state.anomaly_in_progress = False
if 'anomaly_data_payload' not in st.session_state:
    st.session_state.anomaly_data_payload = None
if 'anomaly_trigger_score' not in st.session_state: 
    st.session_state.anomaly_trigger_score = 0.75
if 'feedback_given' not in st.session_state:
    st.session_state.feedback_given = None 
if 'voice_played' not in st.session_state:
    st.session_state.voice_played = False
if 'current_anomaly_threshold' not in st.session_state: 
    st.session_state.current_anomaly_threshold = 0.75
if 'threshold_override_time' not in st.session_state:
    st.session_state.threshold_override_time = 0

@st.cache_resource
def generate_voice_alert():
    if not GTTS_ENABLED: return None
    try:
        if not os.path.exists(VOICE_ALERT_FILE):
            tts = gTTS("Warning, grid anomaly detected. Please check the system.", lang='en', tld='com')
            tts.save(VOICE_ALERT_FILE)
        return open(VOICE_ALERT_FILE, 'rb').read()
    except Exception as e:
        print(f"Error generating voice alert: {e}")
        return None

def play_voice_alert(audio_bytes):
    if audio_bytes and GTTS_ENABLED:
        st.audio(audio_bytes, format='audio/mp3', autoplay=True)

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
    """Only sends feedback to backend if it's confirmed theft."""
    if response == "theft":
        try:
            payload = {"data": data, "response": response}
            requests.post(BACKEND_URL, json=payload)
            load_ledger_file.clear() 
            load_feedback_file.clear() 
        except Exception as e:
            st.error(f"Error submitting feedback to backend: {e}")

with st.sidebar:
    st.header("Public Proof")
    st.session_state.public_webhook_url = st.text_input(
        "Enter Public Webhook URL", value=st.session_state.public_webhook_url
    )
    if st.session_state.public_webhook_url.startswith("https://webhook.site"):
        st.link_button("View Public, Un-tamperable Proof", st.session_state.public_webhook_url, use_container_width=True)
    else:
        st.warning("Get URL from webhook.site")

st.title("⚡ GRIDLOCK AI")

col_live, col_feedback = st.columns([2, 1])
with col_live:
    st.subheader("Live Grid Status")
    live_placeholder = st.empty()
with col_feedback:
    st.subheader("Anomaly Response")
    feedback_placeholder = st.empty()

st.subheader("Live Power Chart")
chart_placeholder = st.empty()

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

    if time.time() > st.session_state.threshold_override_time:
        st.session_state.current_anomaly_threshold = 0.75 

    is_anomaly = bool(score > st.session_state.current_anomaly_threshold)

    with live_placeholder.container():
        c1, c2, c3 = st.columns(3)
        c1.metric("Voltage (V)", f"{live_data['payload']['voltage']:.2f}")
        c2.metric("Current (A)", f"{live_data['payload']['current']:.2f}")
        c3.metric("Power (W)", f"{live_data['payload']['power']:.2f}")

        if is_anomaly:
            status_color = "red"
            status_text = f"**STATUS: 🚨 ANOMALY DETECTED!** (Score: {score:.3f} > {st.session_state.current_anomaly_threshold:.2f})"
            st.error(status_text)

            if not st.session_state.anomaly_in_progress:
                st.session_state.anomaly_in_progress = True
                st.session_state.anomaly_data_payload = live_data['payload']
                st.session_state.anomaly_trigger_score = score 
                st.session_state.feedback_given = None
                st.session_state.voice_played = False
        else:
            status_color = "green"
            status_text = f"**STATUS: ✅ SYSTEM NORMAL** (Score: {score:.3f} <= {st.session_state.current_anomaly_threshold:.2f})"
            st.success(status_text)
            if st.session_state.anomaly_in_progress:
                st.session_state.anomaly_in_progress = False
                st.session_state.anomaly_data_payload = None
                st.session_state.feedback_given = None 
                st.session_state.threshold_override_time = 0 

else:
   
    chart_placeholder.info("Waiting for live data feed...")
    with live_placeholder.container():
        st.info("Awaiting live data feed...")
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
            play_voice_alert(audio_bytes)
            st.session_state.voice_played = True

        @st.dialog("Anomaly Detected!")
        def show_anomaly_dialog():
            st.warning("**An anomaly was detected! Was this you?**")
            st.write(f"Trigger Score: {st.session_state.anomaly_trigger_score:.3f}")
            st.write(f"Data: V={st.session_state.anomaly_data_payload['voltage']:.1f}, A={st.session_state.anomaly_data_payload['current']:.1f}, W={st.session_state.anomaly_data_payload['power']:.1f}")

            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("Yes, this was me (Adapt)", use_container_width=True):
                    st.session_state.current_anomaly_threshold = 0.99
                    st.session_state.threshold_override_time = time.time() + 30 
                    st.session_state.feedback_given = "adapted"
                    submit_feedback_to_backend(st.session_state.anomaly_data_payload, "normal")
                    st.rerun()

            with col_no:
                if st.button("No, this was NOT me (Confirm Theft!)", type="primary", use_container_width=True):
                    st.session_state.feedback_given = "theft_confirmed"
                    submit_feedback_to_backend(st.session_state.anomaly_data_payload, "theft")
                    st.rerun()

        show_anomaly_dialog()

else:
    feedback_placeholder.info("Awaiting anomaly detection...")
    run_loop = True

st.divider()
col_ledger, col_adaptive = st.columns(2)

with col_ledger:
    st.subheader("Local Tamper-Proof Ledger")
    if st.button("Manually Verify Local Ledger Integrity"):
        if verify_ledger(): st.success("✅ HASH CHAIN VERIFIED")
        else: st.error("🚨 TAMPERING DETECTED!")

    ledger_df = load_ledger_file()
    if not ledger_df.empty: st.dataframe(ledger_df.iloc[::-1], use_container_width=True, height=300)
    else: st.info("No confirmed theft events logged yet.")

with col_adaptive:
    st.subheader("User Feedback Log (For AI Retraining)")
    feedback_df = load_feedback_file()
    if not feedback_df.empty: st.dataframe(feedback_df.iloc[::-1], use_container_width=True, height=300)
    else: st.info("No user feedback logged yet.")

if run_loop:
    time.sleep(3)
    st.rerun()
