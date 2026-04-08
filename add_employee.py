#!/usr/bin/env python3
"""Script to add employees to the database using camera."""

from __future__ import annotations

import sys
from pathlib import Path

# Add current directory to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import cv2
from models import register_employee
from core.recognition import open_camera, face_engine_available, get_engine_error


def main():
    """Interactive employee registration."""
    print("👤 EMPLOYEE REGISTRATION")
    print("=" * 50)

    # Check if face recognition is available
    if not face_engine_available():
        print(f"❌ {get_engine_error()}")
        return

    # Get employee details
    print("\nEnter employee information:")
    full_name = input("Full Name: ").strip()
    employee_code = input("Employee Code: ").strip().upper()
    role = input("Role (teacher/security/assistant/reception/staff): ").strip().lower()
    department = input("Department (optional): ").strip() or None

    if not full_name or not employee_code or not role:
        print("❌ Full Name, Employee Code, and Role are required!")
        return

    # Validate role
    valid_roles = ["teacher", "security", "assistant", "reception", "staff"]
    if role not in valid_roles:
        print(f"❌ Invalid role. Must be one of: {', '.join(valid_roles)}")
        return

    print("\n📸 Opening camera for face capture...")
    print("Please look at the camera and press SPACE to capture, or ESC to cancel.")

    # Open camera
    cap = open_camera()
    if cap is None:
        print("❌ Could not open camera!")
        return

    captured_frame = None

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("❌ Failed to read from camera!")
                return

            # Show preview
            cv2.imshow("Employee Registration - Press SPACE to capture", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == 32:  # SPACE key
                captured_frame = frame.copy()
                break
            elif key == 27:  # ESC key
                print("❌ Registration cancelled.")
                return

    finally:
        cap.release()
        cv2.destroyAllWindows()

    # Register employee
    print("\n🔄 Processing registration...")
    result = register_employee(full_name, employee_code, role, department, captured_frame)

    if result["success"]:
        print("✅ SUCCESS!")
        print(f"   Name: {result['message'].split(' ')[-1]}")
        print(f"   Code: {employee_code}")
        print(f"   Photo: {result['photo_path']}")
    else:
        print(f"❌ ERROR: {result['message']}")


if __name__ == "__main__":
    main()