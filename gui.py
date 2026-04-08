"""Tkinter GUI for the Face ID Attendance + Access Control System."""

from __future__ import annotations

import platform
import tkinter as tk
from tkinter import messagebox

from core.database import init_db
from core.engine import FaceRecognitionEngine

C = {
    "bg": "#0F1117",
    "panel": "#171B26",
    "panel_2": "#10141D",
    "border": "#2B3245",
    "accent": "#4F8EF7",
    "success": "#22C55E",
    "danger": "#EF4444",
    "warning": "#F59E0B",
    "text": "#E5E7EB",
    "muted": "#94A3B8",
    "white": "#FFFFFF",
}

FONT_TITLE = ("Helvetica", 22, "bold")
FONT_SUB = ("Helvetica", 11)
FONT_LABEL = ("Helvetica", 10, "bold")
FONT_BODY = ("Helvetica", 10)


class LiveMonitoringWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.engine = FaceRecognitionEngine()
        self.camera_results = self.engine.initialize_cameras()
        self.active_cameras = [cam_id for cam_id, success in self.camera_results.items() if success]
        self.current_camera = self.active_cameras[0] if self.active_cameras else None
        self.monitoring = False

        self.title("Live Face Recognition Monitoring")
        self.geometry("1200x800")
        self.configure(bg=C["bg"])
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.close)

        if not self.active_cameras:
            messagebox.showerror("Error", "No cameras available. Check .env configuration.")
            self.destroy()
            return

        self._build()
        self._start_monitoring()

    def _build(self) -> None:
        # Header
        header = tk.Frame(self, bg=C["panel"], height=64)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="LIVE FACE RECOGNITION MONITORING",
            bg=C["panel"],
            fg=C["accent"],
            font=FONT_TITLE,
        ).pack(side="left", padx=18, pady=14)

        # Status bar
        self.status_var = tk.StringVar(value="Initializing...")
        status_bar = tk.Frame(self, bg=C["panel_2"], height=30)
        status_bar.pack(fill="x")
        status_bar.pack_propagate(False)
        tk.Label(
            status_bar,
            textvariable=self.status_var,
            bg=C["panel_2"],
            fg=C["text"],
            font=FONT_BODY,
        ).pack(side="left", padx=18)

        # Video display area
        self.video_frame = tk.Frame(self, bg=C["bg"])
        self.video_frame.pack(fill="both", expand=True, padx=18, pady=18)

        self.video_label = tk.Label(
            self.video_frame,
            bg=C["panel_2"],
            text="Loading camera feed...",
            font=FONT_SUB
        )
        self.video_label.pack(fill="both", expand=True)

        # Control buttons
        button_frame = tk.Frame(self, bg=C["bg"], height=50)
        button_frame.pack(fill="x", pady=(0, 18), padx=18)
        button_frame.pack_propagate(False)

        self.stop_btn = tk.Button(
            button_frame,
            text="⏹ Stop Monitoring",
            command=self._stop_monitoring,
            bg=C["danger"],
            fg=C["white"],
            font=FONT_LABEL,
            relief="flat",
            padx=20,
            pady=8,
        )
        self.stop_btn.pack(side="right")

    def _start_monitoring(self) -> None:
        self.monitoring = True
        self.status_var.set(f"Monitoring active - Camera: {self.current_camera}")
        self._update_preview()

    def _stop_monitoring(self) -> None:
        self.monitoring = False
        self.status_var.set("Monitoring stopped")
        self.stop_btn.config(state="disabled")

    def _update_preview(self) -> None:
        if not self.monitoring:
            return

        try:
            # Get annotated frame
            success, frame, error_result = self.engine.get_annotated_frame(self.current_camera)

            if success and frame is not None:
                # For now, just show text status since PIL conversion is complex
                # In a full implementation, convert frame to PIL Image and display
                self.video_label.config(text="Camera feed active\n(Visual display requires PIL)")

                # Process recognition
                result = self.engine.process_camera_frame(self.current_camera)
                if result:
                    self._handle_recognition_result(result)

            elif error_result:
                self.status_var.set(f"Error: {error_result.get('message', 'Unknown error')}")

        except Exception as e:
            self.status_var.set(f"Preview error: {e}")

        # Schedule next update
        if self.monitoring:
            self.after(500, self._update_preview)  # 2 FPS for demo

    def _handle_recognition_result(self, result: dict) -> None:
        status = result.get("status")
        message = result.get("message", "")

        if status == "granted":
            self.status_var.set(f"✅ {message}")
        elif status == "denied":
            self.status_var.set(f"⚠️ {message}")
        elif status == "unknown":
            self.status_var.set(f"🚫 {message}")
        elif status == "duplicate":
            self.status_var.set(f"🔄 {message}")

    def close(self) -> None:
        self._stop_monitoring()
        self.engine.shutdown()
        self.destroy()


class AttendanceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Face ID Attendance + Access Control System")
        self.geometry("1000x700")
        self.configure(bg=C["bg"])
        self.resizable(True, True)

        init_db()
        self._build()

    def _build(self) -> None:
        # Header
        header = tk.Frame(self, bg=C["panel"], height=80)
        header.pack(fill="x")
        header.pack_propagate(False)

        title_label = tk.Label(
            header,
            text="FACE ID ATTENDANCE SYSTEM",
            bg=C["panel"],
            fg=C["accent"],
            font=FONT_TITLE,
        )
        title_label.pack(pady=20)

        # Main content
        content = tk.Frame(self, bg=C["bg"])
        content.pack(fill="both", expand=True, padx=40, pady=40)

        # Welcome message
        welcome_frame = tk.Frame(content, bg=C["panel"], padx=30, pady=30)
        welcome_frame.pack(fill="x", pady=(0, 30))

        tk.Label(
            welcome_frame,
            text="Welcome to the Professional Face Recognition Attendance System",
            bg=C["panel"],
            fg=C["text"],
            font=FONT_SUB,
            wraplength=600,
            justify="center",
        ).pack(pady=(0, 20))

        tk.Label(
            welcome_frame,
            text="This system provides real-time face recognition, role-based access control,\n"
                 "and automated attendance logging with turnstile integration.",
            bg=C["panel"],
            fg=C["muted"],
            font=FONT_BODY,
            justify="center",
        ).pack()

        # Action buttons
        button_frame = tk.Frame(content, bg=C["bg"])
        button_frame.pack(pady=30)

        # Live monitoring button
        monitor_btn = tk.Button(
            button_frame,
            text="🎥 Start Live Monitoring",
            command=self._open_live_monitoring,
            bg=C["accent"],
            fg=C["white"],
            font=FONT_LABEL,
            relief="flat",
            padx=30,
            pady=15,
        )
        monitor_btn.pack(side="left", padx=10)

        # Register employee button (placeholder)
        register_btn = tk.Button(
            button_frame,
            text="👤 Register Employee",
            command=self._register_employee,
            bg=C["warning"],
            fg=C["white"],
            font=FONT_LABEL,
            relief="flat",
            padx=30,
            pady=15,
        )
        register_btn.pack(side="left", padx=10)

        # View logs button (placeholder)
        logs_btn = tk.Button(
            button_frame,
            text="📊 View Attendance Logs",
            command=self._view_logs,
            bg=C["success"],
            fg=C["white"],
            font=FONT_LABEL,
            relief="flat",
            padx=30,
            pady=15,
        )
        logs_btn.pack(side="left", padx=10)

    def _open_live_monitoring(self) -> None:
        LiveMonitoringWindow(self)

    def _register_employee(self) -> None:
        messagebox.showinfo("Info", "Employee registration feature - use the original GUI or implement separately!")

    def _view_logs(self) -> None:
        messagebox.showinfo("Info", "Attendance logs viewer - check database directly or implement viewer!")