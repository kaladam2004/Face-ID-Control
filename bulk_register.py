#!/usr/bin/env python3
"""Bulk employee registration script."""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

# Add current directory to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import cv2
import numpy as np
from models import register_employee
from core.recognition import open_camera, face_engine_available, get_engine_error


def bulk_register_from_csv(csv_file: str) -> None:
    """Register employees from CSV file (without photos)."""
    if not Path(csv_file).exists():
        print(f"❌ CSV file '{csv_file}' not found!")
        return

    print(f"📄 Reading employees from {csv_file}...")

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        employees = list(reader)

    print(f"Found {len(employees)} employees to register.")

    for i, emp in enumerate(employees, 1):
        full_name = emp.get('full_name', '').strip()
        employee_code = emp.get('employee_code', '').strip().upper()
        role = emp.get('role', 'staff').strip().lower()
        department = emp.get('department', '').strip() or None

        if not full_name or not employee_code:
            print(f"❌ Row {i}: Missing required fields (full_name, employee_code)")
            continue

        # Create a dummy image for registration (will be updated later)
        dummy_image = np.zeros((480, 640, 3), dtype=np.uint8)

        print(f"🔄 Registering {i}/{len(employees)}: {full_name} ({employee_code})...")

        result = register_employee(full_name, employee_code, role, department, dummy_image, skip_photo=True)

        if result["success"]:
            print(f"✅ {employee_code} registered successfully")
        else:
            print(f"❌ {employee_code}: {result['message']}")

    print("\n📸 Note: Photos need to be captured separately for each employee.")


def interactive_bulk_registration() -> None:
    """Interactive bulk registration with camera."""
    print("👥 BULK EMPLOYEE REGISTRATION")
    print("=" * 50)
    print("Enter employee details. Type 'done' when finished.")
    print()

    # Check if face recognition is available
    if not face_engine_available():
        print(f"❌ {get_engine_error()}")
        return

    # Open camera once for all registrations
    print("📸 Opening camera...")
    cap = open_camera()
    if cap is None:
        print("❌ Could not open camera!")
        return

    registered_count = 0

    try:
        while True:
            print(f"\n{'='*30} Employee #{registered_count + 1} {'='*30}")

            # Get employee details
            full_name = input("Full Name (or 'done' to finish): ").strip()
            if full_name.lower() == 'done':
                break

            employee_code = input("Employee Code: ").strip().upper()
            role = input("Role (teacher/security/assistant/reception/staff): ").strip().lower()
            department = input("Department (optional): ").strip() or None

            if not full_name or not employee_code or not role:
                print("❌ Full Name, Employee Code, and Role are required!")
                continue

            # Validate role
            valid_roles = ["teacher", "security", "assistant", "reception", "staff"]
            if role not in valid_roles:
                print(f"❌ Invalid role. Must be one of: {', '.join(valid_roles)}")
                continue

            print(f"\n📸 Taking photo for {full_name}...")
            print("Look at the camera and press SPACE to capture, or ESC to skip.")

            captured_frame = None

            while True:
                ret, frame = cap.read()
                if not ret:
                    print("❌ Failed to read from camera!")
                    break

                # Show preview
                cv2.imshow(f"Photo for {full_name} - SPACE to capture, ESC to skip", frame)

                key = cv2.waitKey(1) & 0xFF
                if key == 32:  # SPACE key
                    captured_frame = frame.copy()
                    break
                elif key == 27:  # ESC key
                    print("⏭️  Skipping photo capture for this employee.")
                    captured_frame = np.zeros((480, 640, 3), dtype=np.uint8)  # Dummy image
                    break

            cv2.destroyWindow(f"Photo for {full_name} - SPACE to capture, ESC to skip")

            # Register employee
            print(f"🔄 Registering {full_name}...")
            result = register_employee(full_name, employee_code, role, department, captured_frame)

            if result["success"]:
                registered_count += 1
                print(f"✅ SUCCESS! {registered_count} employees registered so far.")
                print(f"   Name: {full_name}")
                print(f"   Code: {employee_code}")
                if 'photo_path' in result and result['photo_path']:
                    print(f"   Photo: {result['photo_path']}")
            else:
                print(f"❌ ERROR: {result['message']}")

            print("\n" + "="*60)

    finally:
        cap.release()
        cv2.destroyAllWindows()

    print(f"\n🎉 Bulk registration completed! {registered_count} employees registered.")


def create_sample_csv() -> None:
    """Create a sample CSV file for bulk registration."""
    sample_file = Path("employees_sample.csv")

    sample_data = [
        ["full_name", "employee_code", "role", "department"],
        ["Алиев Ахмад", "T001", "teacher", "Mathematics"],
        ["Каримова Фатима", "S001", "security", ""],
        ["Рахимов Даврон", "A001", "assistant", "Administration"],
        ["Собирова Нилуфар", "R001", "reception", ""],
        ["Хасанов Бахром", "T002", "teacher", "Physics"]
    ]

    with open(sample_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(sample_data)

    print(f"📄 Sample CSV created: {sample_file}")
    print("Edit this file and use: python bulk_register.py csv employees_sample.csv")


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("🚀 BULK EMPLOYEE REGISTRATION")
        print("=" * 40)
        print("Usage:")
        print("  python bulk_register.py interactive    # Interactive bulk registration")
        print("  python bulk_register.py csv <file.csv> # Register from CSV file")
        print("  python bulk_register.py sample         # Create sample CSV file")
        print()
        print("Examples:")
        print("  python bulk_register.py interactive")
        print("  python bulk_register.py csv employees.csv")
        print("  python bulk_register.py sample")
        return

    command = sys.argv[1].lower()

    if command == "interactive":
        interactive_bulk_registration()
    elif command == "csv":
        if len(sys.argv) < 3:
            print("❌ Please specify CSV file: python bulk_register.py csv <file.csv>")
            return
        bulk_register_from_csv(sys.argv[2])
    elif command == "sample":
        create_sample_csv()
    else:
        print(f"❌ Unknown command: {command}")
        print("Use 'interactive', 'csv', or 'sample'")


if __name__ == "__main__":
    main()