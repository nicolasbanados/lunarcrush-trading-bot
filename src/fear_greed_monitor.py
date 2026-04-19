"""
Fear & Greed Index Monitor
Sends email notification when index goes above threshold (45)
"""

import os
import json
import time
import subprocess
import requests
from datetime import datetime

# Configuration
THRESHOLD = 45
CHECK_INTERVAL_HOURS = 4  # Check every 4 hours
STATE_FILE = "data/fear_greed_state.json"

def get_fear_greed_index():
    """Fetch current Fear & Greed Index from Alternative.me API"""
    try:
        response = requests.get(
            "https://api.alternative.me/fng/",
            timeout=10
        )
        data = response.json()
        if data.get("data"):
            value = int(data["data"][0]["value"])
            classification = data["data"][0]["value_classification"]
            return value, classification
    except Exception as e:
        print(f"Error fetching Fear & Greed: {e}")
    return None, None

def get_replit_auth_token():
    """Get Replit authentication token for email API"""
    hostname = os.environ.get("REPLIT_CONNECTORS_HOSTNAME")
    if not hostname:
        print("REPLIT_CONNECTORS_HOSTNAME not set")
        return None, None
    
    try:
        result = subprocess.run(
            ["replit", "identity", "create", "--audience", f"https://{hostname}"],
            capture_output=True,
            text=True
        )
        token = result.stdout.strip()
        if token:
            return f"Bearer {token}", hostname
    except Exception as e:
        print(f"Error getting auth token: {e}")
    
    return None, None

def send_email(subject: str, text: str):
    """Send email using Replit Mail"""
    auth_token, hostname = get_replit_auth_token()
    if not auth_token:
        print("Could not get auth token for email")
        return False
    
    try:
        response = requests.post(
            f"https://{hostname}/api/v2/mailer/send",
            headers={
                "Content-Type": "application/json",
                "Replit-Authentication": auth_token
            },
            json={
                "subject": subject,
                "text": text
            },
            timeout=30
        )
        
        if response.ok:
            print(f"Email sent successfully: {subject}")
            return True
        else:
            print(f"Email failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def load_state():
    """Load previous state from file"""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {"last_notification": None, "was_above_threshold": False}

def save_state(state):
    """Save state to file"""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def check_and_notify():
    """Main check function"""
    value, classification = get_fear_greed_index()
    
    if value is None:
        print(f"[{datetime.now()}] Could not fetch Fear & Greed Index")
        return
    
    print(f"[{datetime.now()}] Fear & Greed Index: {value} ({classification})")
    
    state = load_state()
    
    # Only send notification when crossing above threshold
    if value > THRESHOLD and not state.get("was_above_threshold", False):
        subject = f"🚀 Trading Bot Alert: Fear & Greed = {value}"
        text = f"""Good news! The Fear & Greed Index has risen above {THRESHOLD}.

Current Value: {value} ({classification})
Threshold: {THRESHOLD}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}

This indicates improving market sentiment. You may consider reactivating your trading bot.

To reactivate:
1. Go to your Replit project
2. Click "Resume" in the dashboard

Remember to close any remaining positions first if needed.

- LCTB Bot"""
        
        if send_email(subject, text):
            state["last_notification"] = datetime.now().isoformat()
            state["was_above_threshold"] = True
            save_state(state)
            print("Notification sent!")
    
    elif value <= THRESHOLD:
        # Reset the flag when below threshold
        if state.get("was_above_threshold", False):
            state["was_above_threshold"] = False
            save_state(state)
            print(f"Index dropped below {THRESHOLD}, reset notification flag")

def run_monitor():
    """Run continuous monitoring"""
    print(f"Starting Fear & Greed Monitor (threshold: {THRESHOLD})")
    print(f"Checking every {CHECK_INTERVAL_HOURS} hours")
    print("-" * 50)
    
    while True:
        check_and_notify()
        time.sleep(CHECK_INTERVAL_HOURS * 3600)

if __name__ == "__main__":
    # Single check mode (for testing)
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        check_and_notify()
    else:
        run_monitor()
