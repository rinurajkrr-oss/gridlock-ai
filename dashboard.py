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
    print("To enable voice, run: pip install gTTS")
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

if "last_anomaly_time" not in st.session_state:
    st.session_state.last_anomaly_time = 0
if "anomaly_data" not in st.session_state:
    st.session_state.anomaly_data = None
if "feedback_given" not in st.session_state:
    st.session_state.feedback_given = None
if "public_webhook_url" not in st.session_state:
    st.session_state.public_webhook_url = ""
if 'chart_data' not in st.session_state:
    st.session_state.chart_data = pd.DataFrame(columns=["timestamp", "Power"])

@st.cache_resource
def generate_voice_alert():
    """Creates and caches the voice alert MP3 file."""
    if not GTTS_ENABLED:
        return None
    try:
        if not os.path.exists(VOICE_ALERT_FILE):
            tts = gTTS("Warning, grid anomaly detected. Please check the system.", lang='en', tld='com')
            tts.save(VOICE_ALERT_FILE)
        
        audio_bytes = open(VOICE_ALERT_FILE, 'rb').read()
        return audio_bytes
    except Exception as e:
        print(f"Error generating voice alert: {e}")
        return None

def play_voice_alert(audio_bytes):
    """Plays the cached voice alert."""
    if audio_bytes and GTTS_ENABLED:
        st.audio(audio_bytes, format='audio/mp3', autoplay=True)

@st.cache_data(ttl=1)
def get_live_data():
    """Reads the latest data from the live status file."""
    if not os.path.exists(LIVE_STATUS_FILE):
        return None
    try:
        with open(LIVE_STATUS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return None 
    except Exception as e:
        print(f"Error reading live data: {e}")
        return None

@st.cache_data(ttl=3) 
def load_ledger_file():
    """Loads the local Web3 ledger."""
    if os.path.exists(LEDGER_FILE):
        try:
            return pd.read_json(LEDGER_FILE)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

@st.cache_data(ttl=3)
def load_feedback_file():
    """Loads the user feedback log for the Adaptive AI."""
    if os.path.exists(FEEDBACK_LOG):
        try:
            return pd.read_csv(FEEDBACK_LOG)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def submit_feedback(data, response):
    """Sends the user's "Yes/No" feedback to the backend."""
    try:
        payload = {"data": data, "response": response}
        requests.post(BACKEND_URL, json=payload)
        st.session_state.feedback_given = response
        st.session_state.anomaly_data = None
        load_ledger_file.clear()
        load_feedback_file.clear()
    except Exception as e:
        st.error(f"Error submitting feedback: {e}")

with st.sidebar:
    st.header("Public Proof")
    st.session_state.public_webhook_url = st.text_input(
        "Enter Public Webhook URL", 
        value=st.session_state.public_webhook_url
    )
    
    if st.session_state.public_webhook_url.startswith("https://webhook.site"):
        st.link_button(
            "Click to view Public, Un-tamperable Proof", 
            st.session_state.public_webhook_url, 
            use_container_width=True
        )
    else:
        st.warning("Get your URL from webhook.site")

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

if live_data:
    df = st.session_state.chart_data
    now = pd.to_datetime(live_data['timestamp'], unit='s')
    
    new_row = pd.DataFrame({
        "timestamp": [now],
        "Power": [live_data['payload']['power']],
    })
    
    df = pd.concat([df, new_row], ignore_index=True).tail(100)
    st.session_state.chart_data = df 
    
    chart_df = df.set_index('timestamp')
    
    chart_placeholder.line_chart(chart_df, y="Power")

    score = live_data.get('anomaly_score', 0)
    is_anomaly = live_data.get('anomaly', False)
    
    with live_placeholder.container():
        c1, c2, c3 = st.columns(3)
        c1.metric("Voltage (V)", f"{live_data['payload']['voltage']:.2f}")
        c2.metric("Current (A)", f"{live_data['payload']['current']:.2f}")
        c3.metric("Power (W)", f"{live_data['payload']['power']:.2f}")

        if is_anomaly:
            st.error(f"**STATUS: 🚨 ANOMALY DETECTED!** (Score: {score:.3f})")
            
            if time.time() - st.session_state.last_anomaly_time > 10: 
                play_voice_alert(audio_bytes)
                st.session_state.last_anomaly_time = time.time()
                st.session_state.anomaly_data = live_data['payload']
                st.session_state.feedback_given = None
        else:
            st.success(f"**STATUS: ✅ SYSTEM NORMAL** (Score: {score:.3f})")
            if st.session_state.anomaly_data:
                st.session_state.anomaly_data = None
                st.session_state.feedback_given = None

    with feedback_placeholder.container():
        if st.session_state.anomaly_data and not st.session_state.feedback_given:
            st.warning("**Anomaly Detected! Was this you?**")
            
            col_yes, col_no = st.columns(2)
            
            with col_yes:
                if st.button("Yes, this was me (New Device)", use_container_width=True):
                    submit_feedback(st.session_state.anomaly_data, "normal")
                    st.rerun() 
                    
            with col_no:
                if st.button("No, this was NOT me (Check System!)", type="primary", use_container_width=True):
                    submit_feedback(st.session_state.anomaly_data, "theft")
                    st.rerun() 

        elif st.session_state.feedback_given == "normal":
            st.success("✅ **AI is Learning...** Feedback logged. The AI will adapt.")
        
        elif st.session_state.feedback_given == "theft":
            st.error("🚨 **THEFT/FAULT CONFIRMED!** Check system and public ledger for proof.")
            
        else:
            st.info("Awaiting anomaly detection...")
else:
    chart_placeholder.info("Waiting for live data feed... Please run the Backend and Simulator.")
    with live_placeholder.container():
        st.info("Awaiting live data feed...")

st.divider()
col_ledger, col_adaptive = st.columns(2)

with col_ledger:
    st.subheader("Local Tamper-Proof Ledger")
    if st.button("Manually Verify Local Ledger Integrity"):
        if verify_ledger():
            st.success("✅ HASH CHAIN VERIFIED: The local ledger is valid.")
        else:
            st.error("🚨 TAMPERING DETECTED: The local ledger hash chain is broken!")
    
    ledger_df = load_ledger_file()
    if not ledger_df.empty:
        st.dataframe(ledger_df.iloc[::-1], use_container_width=True, height=300)
    else:
        st.info("No anomaly events logged yet.")

with col_adaptive:
    st.subheader("Adaptive AI Log")
    feedback_df = load_feedback_file()
    if not feedback_df.empty:
        st.dataframe(feedback_df.iloc[::-1], use_container_width=True, height=300)
    else:
        st.info("No user feedback has been logged yet.")

time.sleep(3)
st.rerun()
