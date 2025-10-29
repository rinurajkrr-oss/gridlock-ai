import requests
import json
import time
import random
import threading
import pandas as pd
import os

API_ENDPOINT_URL = "http://127.0.0.1:8000/predict"
SEND_INTERVAL = 3
DATA_FILE = "gridlock_dataset.csv" 
SIMULATION_MODE = "NORMAL" 
normal_data = pd.DataFrame()
theft_data = pd.DataFrame()

def load_data():
    """Loads and splits the dataset into NORMAL and THEFT data."""
    global normal_data, theft_data
    relative_data_file_path = os.path.join(os.path.dirname(__file__), "..", DATA_FILE)
    if not os.path.exists(relative_data_file_path):
        if not os.path.exists(DATA_FILE):
            print(f"--- 💥 CRITICAL ERROR (Simulator) 💥 ---")
            print(f"Data file not found: {DATA_FILE}")
            print(f"Please ensure '{DATA_FILE}' is in your main 'Gridlock ai' folder.")
            return False
        else:
             relative_data_file_path = DATA_FILE
    try:
        df = pd.read_csv(relative_data_file_path)
        normal_data = df[df['Label'] == 0]
        theft_data = df[df['Label'] == 1]
        if len(normal_data) == 0 or len(theft_data) == 0:
            print("Error: Could not find Label 0 (NORMAL) or Label 1 (THEFT) data in the CSV.")
            return False
        print("--- ✅ Data Loaded Successfully (Simulator) ---")
        print(f"Found {len(normal_data)} 'NORMAL' samples.")
        print(f"Found {len(theft_data)} 'THEFT' samples.")
        print("-----------------------------------")
        return True
    except Exception as e:
        print(f"Error loading data: {e}"); return False

def generate_data_point():
    """Picks a random real data sample based on the current mode."""
    global SIMULATION_MODE
    if SIMULATION_MODE == "NORMAL":
        if normal_data.empty: return None
        sample = normal_data.sample(1)
    else:
        if theft_data.empty: return None
        sample = theft_data.sample(1)
    data_packet = {
        "voltage": sample['Voltage'].iloc[0],
        "current": sample['Current'].iloc[0],
        "power": sample['Power'].iloc[0],
        "power_factor": sample['Power_Factor'].iloc[0]
    }
    for key in data_packet:
        data_packet[key] = float(data_packet[key])
    return data_packet

def mode_switcher():
    """Waits for the user to press ENTER to toggle the mode."""
    global SIMULATION_MODE
    while True:
        try:
            input()
            if SIMULATION_MODE == "NORMAL":
                SIMULATION_MODE = "THEFT"
                print("\n*** 🚨 SIMULATION MODE SET TO THEFT (Label 1) 🚨 ***\n")
            else:
                SIMULATION_MODE = "NORMAL"
                print("\n*** ✅ SIMULATION MODE SET TO NORMAL (Label 0) ✅ ***\n")
        except EOFError: break
        except Exception as e: print(f"Error in mode switcher: {e}"); break

if load_data():
    print("--- ⚡ GRIDLOCK AI: High-Fidelity Simulator Started ⚡ ---")
    print(f"Streaming REAL data from {DATA_FILE}")
    print(f"Targeting API: {API_ENDPOINT_URL}")
    print("\n>>> PRESS ENTER AT ANY TIME TO TOGGLE THEFT MODE <<<\n")
    print("Press Ctrl+C to stop.")
    toggle_thread = threading.Thread(target=mode_switcher, daemon=True)
    toggle_thread.start()

    while True:
        try:
            data = generate_data_point()
            if data is None:
                print("Error generating data point."); time.sleep(SEND_INTERVAL); continue

            response = requests.post(API_ENDPOINT_URL, json=data, timeout=5)

            try:
                response_data = response.json()
                anomaly_status = response_data.get('anomaly', 'ERROR') 
                anomaly_score = response_data.get('anomaly_score', 'ERROR')
                if response.status_code == 200 and 'anomaly' in response_data:
                     print(f"Mode: {SIMULATION_MODE} | Sent: {data['voltage']:.1f}V, {data['current']:.1f}A "
                           f"==> Received: Anomaly: {anomaly_status} (Score: {anomaly_score})")
                else:
                    error_detail = response_data.get('detail', response.text[:200]) 
                    print(f"Error: Got status {response.status_code}. Server Response: {error_detail}")

            except json.JSONDecodeError:
                 print(f"Error: Received non-JSON response (Status: {response.status_code}). Server Response: {response.text[:200]}")
  
        except requests.exceptions.ConnectionError:
            print(f"Error: Connection refused. Is the backend server running?")
        except requests.exceptions.Timeout:
            print("Error: The request to the server timed out.")
        except Exception as e:
            print(f"An unexpected error occurred in the main loop: {type(e).__name__} - {e}")

        try:
            time.sleep(SEND_INTERVAL)
        except KeyboardInterrupt:
            print("\n--- 🛑 Simulation stopped by user ---"); break
else:
    print("--- 💥 Script failed to start. Fix data file loading. ---")
