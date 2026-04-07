"""Tkinter GUI for the Attendance / Mini-Turnstile app."""

from __future__ import annotations

import platform
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

import cv2
from PIL import Image, ImageTk

import database as db
import face_utils as fu
import models
from auto_mode import AutoAttendanceEngine

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
FONT_MONO = ("Menlo" if platform.system() == "Darwin" else "Consolas", 10)


def beep(success: bool = True) -> None:
    try:
        if platform.system() == "Windows":
            import winsound

            winsound.Beep(1100 if success else 450, 180 if success else 280)
        elif platform.system() == "Darwin":
            sound = "Glass" if success else "Basso"
            import os

            os.system(f"afplay /System/Library/Sounds/{sound}.aiff >/dev/null 2>&1 &")
        else:
            print("\a", end="")
    except Exception:
        pass


class CameraWindow(tk.Toplevel):
    def __init__(self, parent, title: str, mode: str, app: "AttendanceApp"):
        super().__init__(parent)
        self.app = app
        self.mode = mode
        self.cap = fu.open_camera()
        self.current_frame = None
        self.preview_job = None
        self.analysis_tick = 0
        self.last_faces = []
        self.known_encodings = []
        self.known_meta = []

        self.title(title)
        self.geometry("1000x720")
        self.configure(bg=C["bg"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.close)

        if mode == "turnstile":
            self.known_encodings, self.known_meta = models.load_known_faces()

        self._build()

        if self.cap is None or not self.cap.isOpened():
            self.info_var.set("❌ Камера кушода нашуд. Camera permission-ро санҷед.")
            self.capture_btn.config(state="disabled")
            return

        self.update_preview()

    def _build(self) -> None:
        header = tk.Frame(self, bg=C["panel"], height=64)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="LIVE CAMERA PREVIEW",
            bg=C["panel"],
            fg=C["accent"],
            font=FONT_TITLE,
        ).pack(side="left", padx=18, pady=14)

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=16, pady=16)

        left = tk.Frame(body, bg=C["panel_2"], highlightthickness=1, highlightbackground=C["border"])
        left.pack(side="left", fill="both", expand=True)

        self.preview_label = tk.Label(left, bg="#000000")
        self.preview_label.pack(fill="both", expand=True, padx=10, pady=10)

        right = tk.Frame(body, width=290, bg=C["panel"], highlightthickness=1, highlightbackground=C["border"])
        right.pack(side="right", fill="y", padx=(14, 0))
        right.pack_propagate(False)

        title_text = "REGISTER" if self.mode == "register" else "TURNSTILE"
        tk.Label(right, text=title_text, bg=C["panel"], fg=C["text"], font=("Helvetica", 16, "bold")).pack(
            anchor="w", padx=16, pady=(16, 10)
        )

        instruction = (
            "• Чеҳраро ба марказ биёред\n"
            "• Дар кадр танҳо 1 нафар бошад\n"
            "• Нурро беҳтар кунед\n"
            "• Capture/Scan-ро пахш кунед"
        )
        tk.Label(
            right,
            text=instruction,
            justify="left",
            bg=C["panel"],
            fg=C["muted"],
            font=FONT_BODY,
        ).pack(anchor="w", padx=16)

        tk.Frame(right, height=14, bg=C["panel"]).pack()

        self.info_var = tk.StringVar(value="Камера омода мешавад...")
        info = tk.Label(
            right,
            textvariable=self.info_var,
            justify="left",
            wraplength=250,
            bg=C["panel_2"],
            fg=C["text"],
            font=FONT_BODY,
            padx=12,
            pady=12,
        )
        info.pack(fill="x", padx=16)

        self.capture_btn = tk.Button(
            right,
            text="📷 Capture & Save" if self.mode == "register" else "🚪 Scan Current Frame",
            command=self.capture,
            bg=C["accent"] if self.mode == "register" else C["success"],
            fg=C["white"],
            bd=0,
            relief="flat",
            font=("Helvetica", 11, "bold"),
            padx=12,
            pady=12,
            cursor="hand2",
        )
        self.capture_btn.pack(fill="x", padx=16, pady=(16, 8))

        tk.Button(
            right,
            text="✖ Close",
            command=self.close,
            bg=C["border"],
            fg=C["white"],
            bd=0,
            relief="flat",
            font=("Helvetica", 10, "bold"),
            padx=12,
            pady=10,
            cursor="hand2",
        ).pack(fill="x", padx=16)

        tk.Frame(right, height=16, bg=C["panel"]).pack()
        tk.Label(right, text="Hints", bg=C["panel"], fg=C["accent"], font=FONT_LABEL).pack(anchor="w", padx=16)
        tk.Label(
            right,
            text=(
                f"Confidence threshold: {fu.CONFIDENCE_THRESHOLD:.0%}\n"
                f"Employees in DB: {db.count_employees()}\n"
                f"Anti-duplicate: {models.ANTI_DUPLICATE_SECONDS} sec"
            ),
            justify="left",
            bg=C["panel"],
            fg=C["muted"],
            font=FONT_BODY,
        ).pack(anchor="w", padx=16, pady=(6, 0))

    def update_preview(self) -> None:
        if self.cap is None or not self.cap.isOpened():
            return

        ok, frame = self.cap.read()
        if not ok:
            self.info_var.set("❌ Аз камера frame хонда нашуд.")
            self.preview_job = self.after(120, self.update_preview)
            return

        self.current_frame = frame.copy()
        self.analysis_tick += 1

        try:
            if self.analysis_tick % 4 == 0:
                self.last_faces = fu.extract_faces(frame) if fu.face_engine_available() else []
        except Exception as exc:
            self.last_faces = []
            self.info_var.set(f"⚠ Detection error: {exc}")

        if self.mode == "turnstile":
            display = fu.annotate_frame(frame, self.last_faces, self.known_encodings, self.known_meta)
            if self.last_faces:
                self.info_var.set(f"Дар preview {len(self.last_faces)} рӯй ёфт шуд.")
            else:
                self.info_var.set("Рӯйро ба камера нигоҳ доред.")
        else:
            display = fu.annotate_frame(frame, self.last_faces)
            if len(self.last_faces) == 1:
                self.info_var.set("✅ 1 рӯй ёфт шуд. Ҳозир Capture & Save-ро пахш кунед.")
            elif len(self.last_faces) > 1:
                self.info_var.set("⚠ Зиёда аз як рӯй дар кадр ҳаст.")
            else:
                self.info_var.set("Рӯйро ба камера наздиктар кунед.")

        rgb = fu.bgr_to_rgb_image(display)
        image = Image.fromarray(rgb)
        image.thumbnail((680, 520))
        photo = ImageTk.PhotoImage(image=image)
        self.preview_label.configure(image=photo)
        self.preview_label.image = photo

        self.preview_job = self.after(30, self.update_preview)

    def capture(self) -> None:
        if self.current_frame is None:
            messagebox.showerror("Camera", "Frame аз камера дастрас нест.", parent=self)
            return

        if self.mode == "register":
            self._capture_register()
        else:
            self._capture_turnstile()

    def _capture_register(self) -> None:
        result = models.register_employee(
            self.app.var_name.get(),
            self.app.var_code.get(),
            self.current_frame,
        )
        self.app.handle_register_result(result)
        if result["success"]:
            beep(True)
            self.close()
        else:
            beep(False)
            self.info_var.set(result["message"])

    def _capture_turnstile(self) -> None:
        result = models.process_turnstile_frame(self.current_frame)
        self.app.handle_turnstile_result(result)
        if result["status"] in {"granted", "denied", "duplicate"}:
            self.close()

    def close(self) -> None:
        if self.preview_job is not None:
            self.after_cancel(self.preview_job)
            self.preview_job = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.grab_release()
        self.destroy()


class AttendanceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Attendance / Mini-Turnstile System")
        self.geometry("1220x760")
        self.minsize(1100, 700)
        self.configure(bg=C["bg"])

        # Initialize auto-attendance engine
        self.auto_engine = AutoAttendanceEngine(callback=self.handle_auto_result)
        self.auto_mode_active = False

        db.init_db()
        self._build_ui()
        self.refresh_logs()
        self.after(3000, self.auto_refresh_logs)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self) -> None:
        self._build_header()

        main = tk.Frame(self, bg=C["bg"])
        main.pack(fill="both", expand=True, padx=16, pady=14)

        self._build_register_panel(main)
        self._build_turnstile_panel(main)
        self._build_logs_panel(main)
        self._build_footer()

    def _build_header(self) -> None:
        hdr = tk.Frame(self, bg="#141A24", height=68)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="🔐 Attendance & Turnstile System", bg="#141A24", fg=C["accent"], font=FONT_TITLE).pack(
            side="left", padx=20, pady=14
        )
        tk.Label(
            hdr,
            text="Offline • SQLite3 • Face Recognition • macOS M2 / Windows Ready",
            bg="#141A24",
            fg=C["muted"],
            font=FONT_SUB,
        ).pack(side="right", padx=20)

    def _make_panel(self, parent, title: str, width: int | None = None) -> tk.Frame:
        panel = tk.Frame(parent, bg=C["panel"], highlightthickness=1, highlightbackground=C["border"])
        if width:
            panel.configure(width=width)
            panel.pack_propagate(False)
        title_bar = tk.Frame(panel, bg=C["border"], height=38)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        tk.Label(title_bar, text=f"  {title}", bg=C["border"], fg=C["accent"], font=FONT_LABEL).pack(
            side="left", pady=9
        )
        return panel

    def _build_register_panel(self, parent) -> None:
        panel = self._make_panel(parent, "REGISTER EMPLOYEE", 300)
        panel.pack(side="left", fill="y", padx=(0, 12))

        self.var_name = tk.StringVar()
        self.var_code = tk.StringVar()

        self._label(panel, "Full Name")
        self._entry(panel, self.var_name)
        self._label(panel, "Employee Code")
        self._entry(panel, self.var_code)

        tk.Label(
            panel,
            text=(
                "1) Ному насабро ворид кунед\n"
                "2) Employee Code нависед\n"
                "3) Камераро кушоед\n"
                "4) Вақте 1 face муайян шуд, Capture пахш кунед"
            ),
            justify="left",
            bg=C["panel"],
            fg=C["muted"],
            font=FONT_BODY,
        ).pack(anchor="w", padx=16, pady=(16, 10))

        self._button(panel, "📷 Open Camera for Register", C["accent"], self.open_register_camera)

        self.lbl_reg_status = tk.Label(
            panel,
            text="",
            wraplength=250,
            justify="left",
            bg=C["panel_2"],
            fg=C["text"],
            font=FONT_BODY,
            padx=12,
            pady=12,
        )
        self.lbl_reg_status.pack(fill="x", padx=16, pady=14)

    def _build_turnstile_panel(self, parent) -> None:
        panel = self._make_panel(parent, "TURNSTILE CONTROL", 370)
        panel.pack(side="left", fill="y", padx=(0, 12))

        btn_frame = tk.Frame(panel, bg=C["panel"])
        btn_frame.pack(fill="x", padx=16, pady=(12, 0))
        self._button(btn_frame, "🚪 Manual Scan", C["success"], self.open_turnstile_camera, pack_side="left")
        
        self.auto_btn = tk.Button(
            btn_frame,
            text="🤖 AUTO MODE OFF",
            command=self.toggle_auto_mode,
            bg=C["border"],
            fg=C["white"],
            bd=0,
            relief="flat",
            cursor="hand2",
            font=("Helvetica", 10, "bold"),
            padx=10,
            pady=11,
        )
        self.auto_btn.pack(side="left", padx=(6, 0), fill="x", expand=True)

        result_box = tk.Frame(panel, bg=C["panel_2"], highlightthickness=1, highlightbackground=C["border"])
        result_box.pack(fill="x", padx=16, pady=16)

        self.lbl_access = tk.Label(result_box, text="— READY —", bg=C["panel_2"], fg=C["muted"], font=("Helvetica", 16, "bold"))
        self.lbl_access.pack(pady=(18, 8))
        self.lbl_person = tk.Label(result_box, text="", bg=C["panel_2"], fg=C["text"], font=("Helvetica", 13, "bold"))
        self.lbl_person.pack()
        self.lbl_time = tk.Label(result_box, text="", bg=C["panel_2"], fg=C["muted"], font=FONT_BODY)
        self.lbl_time.pack(pady=(6, 0))
        self.lbl_conf = tk.Label(result_box, text="", bg=C["panel_2"], fg=C["muted"], font=FONT_BODY)
        self.lbl_conf.pack(pady=(2, 16))

        tk.Label(panel, text="Recent Events", bg=C["panel"], fg=C["accent"], font=FONT_LABEL).pack(anchor="w", padx=16)
        self.event_feed = tk.Text(
            panel,
            height=10,
            bg=C["panel_2"],
            fg=C["text"],
            bd=0,
            relief="flat",
            font=FONT_MONO,
            state="disabled",
            wrap="word",
            insertbackground=C["white"],
        )
        self.event_feed.pack(fill="both", expand=True, padx=16, pady=(8, 16))

    def _build_logs_panel(self, parent) -> None:
        panel = self._make_panel(parent, "LOGS VIEWER")
        panel.pack(side="left", fill="both", expand=True)

        stats = tk.Frame(panel, bg=C["panel"])
        stats.pack(fill="x", padx=16, pady=14)
        self.stats_var = tk.StringVar(value="Employees: 0 | Logs: 0")
        tk.Label(stats, textvariable=self.stats_var, bg=C["panel"], fg=C["muted"], font=FONT_BODY).pack(side="left")
        self._button(stats, "↻ Refresh", C["border"], self.refresh_logs, small=True, pack_side="right")

        table_wrap = tk.Frame(panel, bg=C["panel"])
        table_wrap.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Dark.Treeview",
            background=C["panel_2"],
            foreground=C["text"],
            fieldbackground=C["panel_2"],
            rowheight=28,
            borderwidth=0,
            font=FONT_BODY,
        )
        style.configure(
            "Dark.Treeview.Heading",
            background=C["border"],
            foreground=C["accent"],
            relief="flat",
            font=FONT_LABEL,
        )
        style.map("Dark.Treeview", background=[("selected", C["accent"])], foreground=[("selected", C["white"])])

        columns = ("name", "event", "time", "confidence")
        self.tree = ttk.Treeview(table_wrap, columns=columns, show="headings", style="Dark.Treeview")
        headings = {
            "name": "Full Name",
            "event": "Event",
            "time": "Time",
            "confidence": "Confidence",
        }
        widths = {"name": 180, "event": 90, "time": 180, "confidence": 110}
        for key in columns:
            self.tree.heading(key, text=headings[key])
            self.tree.column(key, width=widths[key], anchor="center")

        vsb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_footer(self) -> None:
        bar = tk.Frame(self, bg=C["border"], height=28)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self.status_var = tk.StringVar(value="System ready")
        tk.Label(bar, textvariable=self.status_var, bg=C["border"], fg=C["muted"], font=FONT_BODY).pack(
            side="left", padx=12, pady=5
        )

    def _label(self, parent, text: str) -> None:
        tk.Label(parent, text=text, bg=C["panel"], fg=C["muted"], font=FONT_LABEL).pack(anchor="w", padx=16, pady=(16, 4))

    def _entry(self, parent, variable: tk.StringVar) -> None:
        entry = tk.Entry(
            parent,
            textvariable=variable,
            bg=C["panel_2"],
            fg=C["white"],
            insertbackground=C["white"],
            relief="flat",
            bd=0,
            font=FONT_BODY,
        )
        entry.pack(fill="x", padx=16, ipady=10)

    def _button(self, parent, text: str, color: str, command, small: bool = False, pack_side: str | None = None) -> None:
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=color,
            fg=C["white"],
            bd=0,
            relief="flat",
            cursor="hand2",
            font=("Helvetica", 10 if small else 11, "bold"),
            padx=10,
            pady=7 if small else 11,
        )
        if pack_side:
            button.pack(side=pack_side)
        else:
            button.pack(fill="x", padx=16, pady=(4, 0))

    def open_register_camera(self) -> None:
        if not self.var_name.get().strip() or not self.var_code.get().strip():
            self.handle_register_result({"success": False, "message": "Аввал Full Name ва Employee Code-ро пур кунед."})
            return
        self.status_var.set("Opening register camera...")
        CameraWindow(self, "Register Employee", "register", self)

    def open_turnstile_camera(self) -> None:
        self.status_var.set("Opening turnstile camera...")
        CameraWindow(self, "Open Turnstile", "turnstile", self)

    def handle_register_result(self, result: dict) -> None:
        color = C["success"] if result.get("success") else C["danger"]
        self.lbl_reg_status.configure(text=result.get("message", ""), fg=color)
        self.status_var.set(result.get("message", ""))
        if result.get("success"):
            self.var_name.set("")
            self.var_code.set("")
            self.append_event(result["message"], C["success"])
            self.refresh_logs()
        else:
            self.append_event(result.get("message", "Register failed"), C["danger"])

    def handle_turnstile_result(self, result: dict) -> None:
        status = result.get("status")
        self.status_var.set(result.get("message", ""))

        if status == "granted":
            self.lbl_access.configure(text="✅ ACCESS GRANTED", fg=C["success"])
            self.lbl_person.configure(text=result.get("full_name", ""), fg=C["white"])
            self.lbl_time.configure(text=result.get("event_time", ""), fg=C["muted"])
            self.lbl_conf.configure(text=f"Confidence: {result.get('confidence', 0.0):.0%}", fg=C["muted"])
            self.append_event(f"✅ {result.get('full_name', '')} — IN", C["success"])
            beep(True)
        elif status == "denied":
            self.lbl_access.configure(text="🚫 ACCESS DENIED", fg=C["danger"])
            self.lbl_person.configure(text="Unknown Person", fg=C["danger"])
            self.lbl_time.configure(text=result.get("event_time", ""), fg=C["muted"])
            self.lbl_conf.configure(text=f"Confidence: {result.get('confidence', 0.0):.0%}", fg=C["muted"])
            self.append_event("🚫 Unknown Person", C["danger"])
            beep(False)
        elif status == "duplicate":
            self.lbl_access.configure(text="⚠ ALREADY LOGGED", fg=C["warning"])
            self.lbl_person.configure(text=result.get("full_name", ""), fg=C["warning"])
            self.lbl_time.configure(text=result.get("event_time", ""), fg=C["muted"])
            self.lbl_conf.configure(text=f"Confidence: {result.get('confidence', 0.0):.0%}", fg=C["muted"])
            self.append_event(f"⚠ Duplicate: {result.get('full_name', '')}", C["warning"])
            beep(False)
        elif status == "no_face":
            self.lbl_access.configure(text="👀 NO FACE", fg=C["warning"])
            self.lbl_person.configure(text="", fg=C["text"])
            self.lbl_time.configure(text=result.get("event_time", ""), fg=C["muted"])
            self.lbl_conf.configure(text="", fg=C["muted"])
            self.append_event("👀 No face detected", C["warning"])
            beep(False)
        elif status == "multiple_faces":
            self.lbl_access.configure(text="⚠ MULTIPLE FACES", fg=C["warning"])
            self.lbl_person.configure(text="", fg=C["text"])
            self.lbl_time.configure(text=result.get("event_time", ""), fg=C["muted"])
            self.lbl_conf.configure(text="", fg=C["muted"])
            self.append_event("⚠ Multiple faces in frame", C["warning"])
            beep(False)
        else:
            self.lbl_access.configure(text="❌ ERROR", fg=C["danger"])
            self.lbl_person.configure(text=result.get("message", ""), fg=C["danger"])
            self.lbl_time.configure(text=result.get("event_time", ""), fg=C["muted"])
            self.lbl_conf.configure(text="", fg=C["muted"])
            self.append_event(result.get("message", "Error"), C["danger"])
            beep(False)

        self.refresh_logs()

    def append_event(self, text: str, color: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.event_feed.configure(state="normal")
        self.event_feed.insert("1.0", f"[{timestamp}] {text}\n")
        self.event_feed.tag_add(timestamp, "1.0", f"1.0+{len(f'[{timestamp}] {text}')}c")
        self.event_feed.tag_config(timestamp, foreground=color)
        self.event_feed.configure(state="disabled")

    def refresh_logs(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        logs = db.get_recent_logs(limit=100)
        for row in logs:
            confidence = row["confidence"]
            conf_text = f"{confidence:.0%}" if confidence is not None else "—"
            self.tree.insert("", "end", values=(row["full_name"], row["event_type"], row["event_time"], conf_text))

        self.stats_var.set(f"Employees: {db.count_employees()} | Logs: {len(logs)}")

    def auto_refresh_logs(self) -> None:
        self.refresh_logs()
        self.after(3000, self.auto_refresh_logs)
    def toggle_auto_mode(self) -> None:
        """Toggle automatic attendance mode on/off."""
        if self.auto_mode_active:
            # Stop auto mode
            self.auto_engine.stop()
            self.auto_mode_active = False
            self.auto_btn.configure(text="🤖 AUTO MODE OFF", bg=C["border"])
            self.status_var.set("Auto mode STOPPED")
        else:
            # Start auto mode
            if self.auto_engine.start():
                self.auto_mode_active = True
                self.auto_btn.configure(text="🤖 AUTO MODE ON", bg=C["success"])
                self.status_var.set("Auto mode RUNNING - Scanning for faces...")
            else:
                self.auto_mode_active = False
                self.status_var.set("Failed to start auto mode")

    def handle_auto_result(self, result: dict) -> None:
        """Handle results from auto-attendance engine."""
        status = result.get("status")

        if status == "error":
            self.lbl_access.configure(text="❌ ERROR", fg=C["danger"])
            self.lbl_person.configure(text=result.get("message", ""), fg=C["danger"])
            self.append_event(f"❌ {result.get('message', 'Error')}", C["danger"])
            if self.auto_mode_active:
                self.toggle_auto_mode()  # Stop on error
            beep(False)

        elif status == "started":
            self.lbl_access.configure(text="🎥 SCANNING", fg=C["success"])
            self.lbl_person.configure(text="Auto mode started", fg=C["success"])
            self.append_event("🎥 Auto mode STARTED", C["success"])
            beep(True)

        elif status == "stopped":
            self.lbl_access.configure(text="⏸ AUTO MODE OFF", fg=C["muted"])
            self.lbl_person.configure(text="", fg=C["text"])
            self.append_event("⏸ Auto mode STOPPED", C["muted"])
            beep(False)

        elif status == "scanning":
            # Just update status, don't log every frame
            self.lbl_access.configure(text="🎥 SCANNING", fg=C["success"])
            msg = result.get("message", "Scanning...")
            self.lbl_person.configure(text=msg, fg=C["success"])

        elif status == "recognized":
            self.lbl_access.configure(text="✅ RECOGNIZED", fg=C["success"])
            self.lbl_person.configure(text=result.get("full_name", ""), fg=C["white"])
            self.lbl_time.configure(text=result.get("event_time", ""), fg=C["muted"])
            self.lbl_conf.configure(text=f"Confidence: {result.get('confidence', 0.0):.0%}", fg=C["muted"])
            self.append_event(f"✅ {result.get('full_name', '')} — IN", C["success"])
            beep(True)

        elif status == "unknown":
            self.lbl_access.configure(text="🚫 UNKNOWN", fg=C["danger"])
            self.lbl_person.configure(text="Unknown Person", fg=C["danger"])
            self.lbl_time.configure(text=result.get("event_time", ""), fg=C["muted"])
            self.lbl_conf.configure(text=f"Confidence: {result.get('confidence', 0.0):.0%}", fg=C["muted"])
            self.append_event("🚫 Unknown Person", C["danger"])
            beep(False)

        self.refresh_logs()

    def on_close(self) -> None:
        """Handle window close - stop auto mode if running."""
        if self.auto_mode_active:
            self.auto_engine.stop()
        self.destroy()