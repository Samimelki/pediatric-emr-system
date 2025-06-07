#!/usr/bin/env python3
"""
Development server for testing the EMR Flask app without webview.
This allows you to test the web interface in a browser.
"""

import os
import sys
from flask import Flask

# Import the configured app from app.py
from app import app

if __name__ == '__main__':
    print("=" * 60)
    print("EMR Development Server")
    print("=" * 60)
    print("Starting Flask development server...")
    print("The EMR will be available at: http://127.0.0.1:9999")
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    try:
        print("Importing database init...")
        from database import init_db_schema
        print("Creating app context...")
        
        # Initialize database schema
        with app.app_context():
            print("Initializing database schema...")
            init_db_schema()
            print("Database schema initialized.")
        
        print("Starting Flask app...")
        # Run the Flask app in development mode
        app.run(
            debug=True,
            host='127.0.0.1',
            port=9999,
            use_reloader=True
        )
    except Exception as e:
        print(f"Error starting server: {e}")
        import traceback
        traceback.print_exc() 