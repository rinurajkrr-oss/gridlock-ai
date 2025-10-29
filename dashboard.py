import streamlit as st
import pandas as pd
import time
import json
from datetime import datetime

st.set_page_config(
    page_title="GRIDLOCK AI Dashboard",
    page_icon="⚡",
    layout="wide"
)

LIVE_STATUS_FILE = "live_status.json" 
CHART_HISTORY_LENGTH = 100 

if 'data_history' not in st.session_state:
    st.session_state.data_history = []

def get_live_data():
    """Reads the latest prediction data from the JSON file."""
    try:
        with open(LIVE_STATUS_FILE, "r") as f:
            data = json.load(f)
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {"status": "Waiting for data...", "anomaly": False, "anomaly_score": 0, "power": 0, "current": 0, "timestamp": 0}

st.title("⚡ GRIDLOCK AI: Zero-Tolerance Security Dashboard")
st.markdown("### Real-time Grid Monitoring & Anomaly Detection")

col1, col2, col3 = st.columns(3)
with col1:
    status_placeholder = st.empty()
with col2:
    score_placeholder = st.empty()
with col3:
    power_placeholder = st.empty()

chart_placeholder = st.empty()

while True:
    data = get_live_data()
    
    is_new_data = (len(st.session_state.data_history) == 0 or 
                   st.session_state.data_history[-1]['timestamp'] != data['timestamp'])

    if is_new_data and 'power' in data:
        st.session_state.data_history.append(data)
        
        if len(st.session_state.data_history) > CHART_HISTORY_LENGTH:
            st.session_state.data_history.pop(0) 

    if data['anomaly']:
        status_placeholder.error("🚨 ANOMALY DETECTED!", icon="🚨")
    else:
        status_placeholder.success("✅ SYSTEM NORMAL", icon="✅")

    score_placeholder.metric(
        label="Anomaly Score",
        value=f"{data.get('anomaly_score', 0) * 100:.1f}%",
        delta=f"{data.get('anomaly_score', 0) - 0.5:.1f}%",
        delta_color="inverse"
    )
    
    power_placeholder.metric(
        label="Live Power",
        value=f"{data.get('power', 0):.2f} W",
        delta=f"{data.get('current', 0):.2f} A"
    )

    if len(st.session_state.data_history) > 0:
        chart_df = pd.DataFrame(st.session_state.data_history)
        
        chart_df['datetime'] = pd.to_datetime(chart_df['timestamp'], unit='s')
        chart_df = chart_df.set_index('datetime')
        
        columns_to_plot = ['power', 'anomaly_score']
        
        chart_placeholder.line_chart(chart_df[columns_to_plot])

    time.sleep(1)