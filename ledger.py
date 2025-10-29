import json
import hashlib
import os
from datetime import datetime

LEDGER_FILE = "web3_ledger.json"

def get_last_entry():
    """
    Reads the ledger file and returns the very last entry.
    If the file is empty or missing, returns a "Genesis" (first) entry.
    """
    if not os.path.exists(LEDGER_FILE):
        return {
            "entry_hash": "0000000000000000000000000000000000000000000000000000000000000000" 
        }
    
    try:
        with open(LEDGER_FILE, "r") as f:
            ledger = json.load(f)
            if not ledger: 
                raise IndexError
            return ledger[-1] 
    except (json.JSONDecodeError, IndexError, FileNotFoundError):
        return {
            "entry_hash": "0000000000000000000000000000000000000000000000000000000000000000"
        }

def hash_data(data_string):
    """
    Helper function to create a SHA-256 hash
    """
    return hashlib.sha256(data_string.encode('utf-8')).hexdigest()

def add_to_ledger(anomaly_data):
    """
    The main function. Called by the backend when an anomaly is found.
    """
    last_entry = get_last_entry()
    previous_hash = last_entry['entry_hash']

    new_entry_data = {
        "timestamp": anomaly_data['timestamp'],
        "voltage": anomaly_data['voltage'],
        "current": anomaly_data['current'],
        "power": anomaly_data['power'],
        "anomaly_score": anomaly_data['anomaly_score'],
        "previous_hash": previous_hash
    }
    
    entry_string = json.dumps(new_entry_data, sort_keys=True)
    entry_hash = hash_data(entry_string)
    
    new_entry_data['entry_hash'] = entry_hash

    ledger = []
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, "r") as f:
                ledger = json.load(f)
        except json.JSONDecodeError:
            ledger = [] 

    ledger.append(new_entry_data)
    
    with open(LEDGER_FILE, "w") as f:
        json.dump(ledger, f, indent=4)
        
    print(f"--- 🔐 Web3 Ledger Entry Added (Hash: {entry_hash[:6]}...) ---")