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
    global normal_data, theft_data
    if not os.path.exists(DATA_FILE):
        print(f"--- 💥 CRITICAL ERROR 💥 ---")
        print(f"Data file not found: {DATA_FILE}")
        print("Please move the CSV file to the main 'Gridlock ai' folder.")
        print("------------------------------")
        return False
    try:
        df = pd.read_csv(DATA_FILE)
        normal_data = df[df['Label'] == 0]
        theft_data = df[df['Label'] == 1]
        
        if len(normal_data) == 0 or len(theft_data) == 0:
            print("Error: Could not find Label 0 or Label 1 data.")
            return False
            
        print("--- ✅ Data Loaded Successfully ---")
        print(f"Found {len(normal_data)} 'NORMAL' samples.")
        print(f"Found {len(theft_data)} 'THEFT' samples.")
        print("-----------------------------------")
        return True
    except Exception as e:
        print(f"Error loading data: {e}")
        return False

def generate_data_point():
    global SIMULATION_MODE
    if SIMULATION_MODE == "NORMAL":
        sample = normal_data.sample(1)
    else:
        sample = theft_data.sample(1)
    
    data_packet = {
        "voltage": sample['Voltage'].iloc[0],
        "current": sample['Current'].iloc[0],
        "power": sample['Power'].iloc[0],
        "power_factor": sample['Power_Factor'].iloc[0]  
    }
    
    return data_packet

def mode_switcher():
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
        except EOFError:
            pass

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
            response = requests.post(API_ENDPOINT_URL, json=data, timeout=3)
            
            if response.status_code == 200:
                response_data = response.json()
                print(f"Mode: {SIMULATION_MODE} | Sent: {data['voltage']:.1f}V, {data['current']:.1f}A "
                      f"==> Received: Anomaly: {response_data['anomaly']} (Score: {response_data['anomaly_score']})")
            else:
                print(f"Error: Got status {response.status_code}. Server says: {response.text}")
                
        except requests.exceptions.ConnectionError:
            print(f"Error: Connection refused. Is the backend server running at {API_ENDPOINT_URL}?")
        except requests.exceptions.Timeout:
            print("Error: The server timed out.")
        except Exception as e:
            print(f"An error occurred: {e}")

        try:
            time.sleep(SEND_INTERVAL)
        except KeyboardInterrupt:
            print("\n--- 🛑 Simulation stopped ---")
            break
else:
    print("Script failed to start. Please fix the data file issue above.")