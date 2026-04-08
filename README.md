# Face ID Attendance + Access Control System

A professional face recognition attendance system with role-based access control and turnstile integration.

## Features

- **Real-time Face Recognition**: Detect and recognize employees from live camera feeds
- **Multi-Camera Support**: USB webcams and RTSP IP cameras (Hikvision, etc.)
- **Role-Based Access Control**: Different access rules for teachers, security, staff, etc.
- **Automated Attendance Logging**: Save attendance with timestamps and snapshots
- **Turnstile Integration**: Control physical access with relay/serial/HTTP APIs
- **Anti-Spoofing**: Liveness detection to prevent photo/video attacks
- **Duplicate Prevention**: Prevent multiple entries within timeout period
- **Unknown Face Handling**: Log unrecognized faces for security

## Project Structure

```
project/
│
├── main.py                 # Main entry point (console mode)
├── app.py                  # GUI entry point
├── .env                    # Configuration file
├── requirements.txt        # Python dependencies
│
├── core/                   # Core modules
│   ├── __init__.py
│   ├── config.py           # Configuration management
│   ├── database.py         # Database operations
│   ├── camera.py           # Camera management
│   ├── recognition.py      # Face recognition utilities
│   ├── attendance.py       # Attendance logging
│   ├── access_control.py   # Role-based access rules
│   ├── liveness.py         # Anti-spoofing (placeholder)
│   ├── turnstile.py        # Turnstile control
│   └── engine.py           # Main processing engine
│
├── gui.py                  # Tkinter GUI
├── photos/                 # Employee photos
├── logs/                   # Attendance snapshots
│   └── unknown/           # Unknown face snapshots
├── data/                   # Database files
│   └── attendance.db
```

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Configure cameras in `.env` file:
```bash
# Camera URLs (0 for webcam, rtsp:// for IP cameras)
CAMERA_1_URL=0
CAMERA_2_URL=rtsp://username:password@192.168.1.100:554/Streaming/Channels/101

# Other settings
DB_PATH=data/attendance.db
CONFIDENCE_THRESHOLD=0.50
DUPLICATE_TIMEOUT=30
TURNSTILE_MODE=SIMULATE
```

3. Initialize database:
```bash
python -c "from core.database import init_db; init_db()"
```

## Adding Employees to Database

### Option 1: Single Employee Registration

Use the `add_employee.py` script to register new employees one by one:

```bash
python add_employee.py
```

The script will:
1. Ask for employee details (name, code, role, department)
2. Open camera for face capture
3. Process the face and save to database
4. Store photo in `photos/` directory

### Option 2: Bulk Interactive Registration

For registering multiple employees quickly with camera:

```bash
python bulk_register.py interactive
```

This will:
1. Open camera once for all employees
2. Allow you to register multiple employees in sequence
3. Press SPACE to capture photo for each employee
4. Press ESC to skip photo (use dummy image)
5. Type 'done' when finished

### Option 3: Bulk Registration from CSV

Create a CSV file with employee data and register all at once:

```bash
# First, create a sample CSV file
python bulk_register.py sample

# Edit the employees_sample.csv file with your data
# Then register all employees
python bulk_register.py csv employees_sample.csv
```

CSV format:
```csv
full_name,employee_code,role,department
Алиев Ахмад,T001,teacher,Mathematics
Каримова Фатима,S001,security,
```

**Note:** CSV registration creates employees without photos. Use the interactive method to add photos later.

### Option 4: Web Registration (Browser Camera)

Run the new web registration app:

```bash
python3 web_register.py
```

If port 5000 is already in use, start on a different port:

```bash
python3 web_register.py 5001
```

Open browser at:

```
http://localhost:5000/register
```

or if using port 5001:

```
http://localhost:5001/register
```

На странице заполните поля, нажмите «Сделать фото», затем «Добавить сотрудника».

### Manual Registration (Alternative)

You can also register employees programmatically:

```python
from models import register_employee
import cv2

# Capture frame from camera
cap = cv2.VideoCapture(0)
ret, frame = cap.read()
cap.release()

# Register employee
result = register_employee(
    full_name="John Doe",
    employee_code="EMP001",
    role="teacher",
    department="Mathematics",
    frame=frame
)

if result["success"]:
    print("Employee registered successfully!")
else:
    print(f"Error: {result['message']}")
```

## Database Schema

### Employees Table
- `id`: Primary key
- `employee_code`: Unique employee identifier
- `full_name`: Employee name
- `role`: Role (teacher, security, reception, staff)
- `department`: Optional department
- `face_encoding`: Serialized face encoding
- `photo_path`: Path to photo
- `is_active`: Active status
- `created_at`: Registration timestamp

### Attendance Logs Table
- `id`: Primary key
- `employee_id`: Foreign key to employees
- `employee_code`: Employee code
- `full_name`: Employee name
- `role`: Employee role
- `confidence`: Recognition confidence
- `camera_ip`: Camera identifier
- `snapshot_path`: Attendance photo path
- `status`: GRANTED/DENIED/UNKNOWN
- `event_type`: ENTRY/EXIT
- `created_at`: Event timestamp

### Unknown Logs Table
- `id`: Primary key
- `camera_ip`: Camera identifier
- `snapshot_path`: Unknown face photo
- `created_at`: Detection timestamp

## Access Control Rules

- **Security**: 24/7 access
- **Teacher**: School hours (07:00-16:00)
- **Assistant**: Work hours (08:00-18:00)
- **Reception**: Work hours (08:00-18:00)
- **Staff**: Work hours (08:00-18:00)

## Turnstile Integration

Configure `TURNSTILE_MODE` in `.env`:

- `SIMULATE`: Print messages (default)
- `RELAY`: GPIO control (Raspberry Pi)
- `SERIAL`: Serial port control
- `HTTP`: HTTP API calls

## Anti-Spoofing

The system includes a placeholder for liveness detection. To implement:

1. Replace `core/liveness.py` with actual detection logic
2. Use techniques like:
   - Blink detection
   - Head movement analysis
   - Texture analysis
   - Frequency domain analysis

## Performance Optimization

- Frame skipping (process every N frames)
- Frame resizing before processing
- Efficient encoding storage
- Duplicate entry prevention

## Security Considerations

- Store face encodings securely
- Implement proper access logging
- Regular backup of database
- Monitor unknown face detections
- Update liveness detection regularly

## Development

The system is modular and extensible:

- Add new camera types in `core/camera.py`
- Customize access rules in `core/access_control.py`
- Extend database schema as needed
- Add new roles and permissions
- Integrate with existing HR systems

## License

This project is for educational and professional use. Ensure compliance with local privacy laws and regulations.
