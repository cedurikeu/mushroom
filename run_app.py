#!/usr/bin/env python3
"""
Simple runner for the Mushroom Environmental Control System
This script handles the app startup with proper error handling
"""
import sys
import os

def main():
    try:
        print("🍄 Starting Mushroom Environmental Control System...")
        print("📦 Loading dependencies...")
        
        # Import and run the main app
        from app import main as app_main
        app_main()
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("💡 Make sure all dependencies are installed:")
        print("   pip3 install -r requirements.txt --break-system-packages")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Application stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()