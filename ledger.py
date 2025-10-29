import json
import os
import hashlib
from datetime import datetime

LEDGER_FILE = "web3_ledger.json"

def get_last_hash():
    """Helper function to get the hash of the last block in the chain."""
    if not os.path.exists(LEDGER_FILE):
        return "0000000000000000000000000000000000000000000000000000000000000000"
    
    try:
        with open(LEDGER_FILE, "r") as f:
            ledger = json.load(f)
        if not ledger: 
            return "0000000000000000000000000000000000000000000000000000000000000000"
        return ledger[-1]['entry_hash']
    except (json.JSONDecodeError, IndexError, FileNotFoundError):
        return "0000000000000000000000000000000000000000000000000000000000000000"

def add_to_ledger(data_payload):
    """
    Creates a new, hashed entry for the local ledger.
    Returns the new hash so it can be sent to the public.
    """
    if not os.path.exists(LEDGER_FILE):
        ledger = []
    else:
        try:
            with open(LEDGER_FILE, "r") as f:
                ledger = json.load(f)
            if not isinstance(ledger, list):
                ledger = []
        except (json.JSONDecodeError, FileNotFoundError):
            ledger = []

    new_entry = {
        "timestamp": datetime.now().isoformat(),
        "previous_hash": get_last_hash(),
        "payload": data_payload
    }
    
    entry_string = json.dumps(new_entry, sort_keys=True).encode('utf-8')
    entry_hash = hashlib.sha256(entry_string).hexdigest()
    
    new_entry["entry_hash"] = entry_hash
    
    ledger.append(new_entry)
    
    try:
        with open(LEDGER_FILE, "w") as f:
            json.dump(ledger, f, indent=4)
        
        return entry_hash, new_entry["timestamp"]
    except Exception as e:
        print(f"Error writing to ledger file: {e}")
        return None, None

def verify_ledger():
    """
    Verifies the integrity of the entire local hash chain.
    Returns True if valid, False if tampered.
    """
    if not os.path.exists(LEDGER_FILE):
        return True 

    try:
        with open(LEDGER_FILE, "r") as f:
            ledger = json.load(f)
    except Exception:
        return False 

    if not isinstance(ledger, list) or not ledger:
        return True 

    current_previous_hash = "0000000000000000000000000000000000000000000000000000000000000000"

    for entry in ledger:
        if entry['previous_hash'] != current_previous_hash:
            return False 
        
        entry_hash = entry.pop('entry_hash')
        
        entry_string = json.dumps(entry, sort_keys=True).encode('utf-8')
        recalculated_hash = hashlib.sha256(entry_string).hexdigest()
        
        if recalculated_hash != entry_hash:
            return False 
        
        current_previous_hash = entry_hash

    return True
