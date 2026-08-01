import uvicorn
import webbrowser
import threading
import time
import os
import sys

def open_browser():
    """Waits for the FastAPI server to initialize, then opens the browser."""
    # Give the server 3 seconds to complete seed generation and ML training on startup
    time.sleep(3.0)
    print("\n[DriveMind] Launching web browser pointing to http://localhost:8000")
    webbrowser.open("http://localhost:8000")

if __name__ == "__main__":
    # Ensure current directory is on python path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, current_dir)
    
    # Start web browser opening thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    print("[DriveMind] Initializing local Fleet Intelligence servers...")
    print("[DriveMind] Running on http://localhost:8000")
    print("[DriveMind] Press Ctrl+C to terminate.")
    
    # Run FastAPI server
    # We specify app as import string so reloading works if needed, or object
    from backend.app import app
    uvicorn.run(app, host="127.0.0.1", port=8000)
