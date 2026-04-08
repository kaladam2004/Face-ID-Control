"""Main entry point for the Face ID Attendance + Access Control System."""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Add current directory to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.database import init_db
from core.engine import FaceRecognitionEngine


def main() -> None:
    """Main application entry point."""
    print("🚀 Starting Face ID Attendance + Access Control System")

    # Initialize database
    init_db()
    print("✅ Database initialized")

    # Initialize engine
    engine = FaceRecognitionEngine()

    # Initialize cameras
    camera_results = engine.initialize_cameras()
    active_cameras = [cam_id for cam_id, success in camera_results.items() if success]

    if not active_cameras:
        print("❌ No cameras available. Check configuration and try again.")
        return

    print(f"✅ Cameras initialized: {active_cameras}")

    try:
        print("🎥 Starting live monitoring... Press Ctrl+C to stop")

        while True:
            for camera_id in active_cameras:
                result = engine.process_camera_frame(camera_id)

                if result:
                    status = result.get("status", "unknown")
                    message = result.get("message", "")

                    if status == "granted":
                        print(f"🟢 {message}")
                    elif status == "denied":
                        print(f"🟡 {message}")
                    elif status == "unknown":
                        print(f"🔴 {message}")
                    elif status == "duplicate":
                        print(f"🔵 {message}")
                    elif status in ["no_face", "multiple_faces"]:
                        pass  # Skip verbose logging for these
                    else:
                        print(f"⚠️  {message}")

            # Small delay to prevent CPU hogging
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        engine.shutdown()
        print("👋 System shutdown complete")


if __name__ == "__main__":
    main()