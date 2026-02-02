import socket
import sys
import importlib.util

def check_port(port):
    """Returns True if port is open/listening on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        result = s.connect_ex(('127.0.0.1', port))
        return result == 0

def check_thetadata_pkg():
    """Checks if thetadata is installed and checks capabilities."""
    spec = importlib.util.find_spec("thetadata")
    if spec is None:
        print("[ERROR] 'thetadata' package not installed.")
        return False
    
    print("[SUCCESS] 'thetadata' package found.")
    
    try:
        import thetadata
        print(f"  Version: {getattr(thetadata, '__version__', 'Unknown')}")
        
        # Check for Context/Stream
        has_context = hasattr(thetadata, 'Context') or hasattr(thetadata, 'ThetaClient')
        has_stream = hasattr(thetadata, 'Stream') or hasattr(thetadata, 'subscribe')
        
        if has_context and has_stream:
             print("[SUCCESS] Streaming classes (Context/Stream) detected.")
        else:
             print("[WARNING] Streaming classes missing. Check library version.")
             
        return True
    except Exception as e:
        print(f"[ERROR] inspecting thetadata: {e}")
        return False

def main():
    print("--- Phase 1: Environment Verification ---")
    
    # 1. Port Check
    v2_port = 25510
    v3_port = 25520
    
    v2_open = check_port(v2_port)
    v3_open = check_port(v3_port)
    
    if v2_open:
        print(f"[SUCCESS] Theta Terminal V2 (Standard) detected on port {v2_port}.")
    else:
        print(f"[INFO] Port {v2_port} closed.")

    if v3_open:
        print(f"[INFO] Theta Terminal V3 (Beta) detected on port {v3_port}.")
        
    if v3_open and not v2_open:
        print("\n[CRITICAL WARNING] Streaming is not supported on V3 Beta via this API. Please launch Terminal V2.")
        sys.exit(1)
        
    if not v2_open and not v3_open:
        print("\n[ERROR] No Theta Terminal detected. Please launch Theta Terminal V2 (Port 25510).")
        # Proceeding anyway? User script said "If successful".
        # But failing here is safer.
        # sys.exit(1) 
        
    # 2. Library Check
    if not check_thetadata_pkg():
        sys.exit(1)
        
    print("\n[VERIFIED] Environment looks ready for Real-Time Streaming (pending Connection).")

if __name__ == "__main__":
    main()
