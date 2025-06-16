#!/usr/bin/env python3
"""
Emergency script to kill any stuck EMR processes.
Run this before launching the EMR app if you experience infinite loops.
"""

import subprocess
import sys
import os

def kill_emr_processes():
    """Kill any running EMR processes."""
    try:
        # Find processes with EMR in the name
        result = subprocess.run(['pgrep', '-f', 'EMR'], capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    print(f"Killing EMR process with PID: {pid}")
                    subprocess.run(['kill', '-9', pid])
        else:
            print("No EMR processes found.")
    except Exception as e:
        print(f"Error killing EMR processes: {e}")

    # Also check for Python processes running app.py
    try:
        result = subprocess.run(['pgrep', '-f', 'app.py'], capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    print(f"Killing Python app.py process with PID: {pid}")
                    subprocess.run(['kill', '-9', pid])
        else:
            print("No app.py processes found.")
    except Exception as e:
        print(f"Error killing app.py processes: {e}")

    # Check for processes using port 9999
    try:
        result = subprocess.run(['lsof', '-ti:9999'], capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    print(f"Killing process using port 9999 with PID: {pid}")
                    subprocess.run(['kill', '-9', pid])
        else:
            print("No processes using port 9999.")
    except Exception as e:
        print(f"Error killing port 9999 processes: {e}")

if __name__ == '__main__':
    print("=== EMR Process Killer ===")
    print("This will kill any running EMR processes.")
    print("Use this if EMR got stuck in an infinite loop.")
    print()
    
    kill_emr_processes()
    print()
    print("Done! All EMR processes should be stopped.")
    print("It's now safe to launch EMR again.") 