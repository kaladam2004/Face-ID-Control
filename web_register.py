#!/usr/bin/env python3
"""Web-based employee registration with browser camera."""

from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv
from flask import Flask, redirect, render_template_string, request, url_for

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.database import init_db
from models import register_employee

app = Flask(__name__)
app.secret_key = "attendance_system_web_secret"

HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Web Employee Registration</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 0; padding: 0; background: #f4f7fb; }
    .container { max-width: 900px; margin: 24px auto; padding: 24px; background: #fff; border-radius: 10px; box-shadow: 0 12px 36px rgba(0,0,0,0.08); }
    h1 { margin-top: 0; }
    .grid { display: grid; gap: 18px; grid-template-columns: 1fr 1fr; }
    label { display: block; margin-bottom: 8px; font-weight: 600; }
    input, select, button, textarea { width: 100%; font-size: 1rem; padding: 10px 12px; border: 1px solid #ccd0db; border-radius: 8px; }
    button { background: #2e7dff; color: #fff; border: none; cursor: pointer; }
    button:hover { background: #245dcc; }
    .video-box { border: 1px solid #ccd0db; border-radius: 10px; overflow: hidden; background: #000; }
    video, canvas { width: 100%; display: block; }
    .status { padding: 14px; margin: 18px 0; border-radius: 10px; }
    .success { background: #e6f4ea; color: #176f3e; }
    .error { background: #fdecea; color: #7f1d1d; }
    .full-width { grid-column: 1 / -1; }
  </style>
</head>
<body>
  <div class="container">
    <h1>Web Employee Registration</h1>
    <p>Сканируйте лицо через браузер, заполните данные и нажмите "Добавить сотрудника".</p>

    {% if status_message %}
    <div class="status {{ 'success' if success else 'error' }}">
      {{ status_message }}
    </div>
    {% endif %}

    <div class="grid">
      <div class="video-box full-width">
        <video id="video" autoplay playsinline></video>
        <canvas id="canvas" style="display:none"></canvas>
      </div>

      <div>
        <label for="full_name">ФИО</label>
        <input id="full_name" name="full_name" type="text" placeholder="Иванов Иван" required />
      </div>
      <div>
        <label for="employee_code">Код сотрудника</label>
        <input id="employee_code" name="employee_code" type="text" placeholder="EMP001" required />
      </div>
      <div>
        <label for="role">Роль</label>
        <select id="role" name="role" required>
          <option value="teacher">teacher</option>
          <option value="security">security</option>
          <option value="assistant">assistant</option>
          <option value="reception">reception</option>
          <option value="staff">staff</option>
        </select>
      </div>
      <div>
        <label for="department">Отдел</label>
        <input id="department" name="department" type="text" placeholder="Mathematics" />
      </div>
      <div class="full-width">
        <button id="captureButton" type="button">Сделать фото</button>
      </div>

      <form id="registerForm" method="POST" action="/register" class="full-width">
        <input type="hidden" id="photo_data" name="photo_data" />
        <input type="hidden" id="form_full_name" name="full_name" />
        <input type="hidden" id="form_employee_code" name="employee_code" />
        <input type="hidden" id="form_role" name="role" />
        <input type="hidden" id="form_department" name="department" />
        <button type="submit">Добавить сотрудника</button>
      </form>
    </div>
  </div>

  <script>
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const captureButton = document.getElementById('captureButton');
    const registerForm = document.getElementById('registerForm');
    const photoInput = document.getElementById('photo_data');
    const formFullName = document.getElementById('form_full_name');
    const formEmployeeCode = document.getElementById('form_employee_code');
    const formRole = document.getElementById('form_role');
    const formDepartment = document.getElementById('form_department');

    const fullNameField = document.getElementById('full_name');
    const employeeCodeField = document.getElementById('employee_code');
    const roleField = document.getElementById('role');
    const departmentField = document.getElementById('department');

    async function initCamera() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        video.srcObject = stream;
      } catch (error) {
        alert('Не удалось получить доступ к камере. Проверьте разрешения браузера.');
      }
    }

    captureButton.addEventListener('click', () => {
      const width = video.videoWidth;
      const height = video.videoHeight;
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext('2d');
      context.drawImage(video, 0, 0, width, height);
      const dataUrl = canvas.toDataURL('image/jpeg');
      photoInput.value = dataUrl;
      alert('Фото сделано. Теперь нажмите "Добавить сотрудника".');
    });

    registerForm.addEventListener('submit', (event) => {
      if (!photoInput.value) {
        event.preventDefault();
        alert('Сначала сделайте фото через кнопку "Сделать фото".');
        return;
      }
      formFullName.value = fullNameField.value;
      formEmployeeCode.value = employeeCodeField.value;
      formRole.value = roleField.value;
      formDepartment.value = departmentField.value;
    });

    initCamera();
  </script>
</body>
</html>
"""


def decode_base64_image(data_url: str):
    match = re.match(r"data:image/(png|jpeg|jpg);base64,(.+)", data_url)
    if not match:
        raise ValueError("Неправильный формат изображения")
    image_data = base64.b64decode(match.group(2))
    nparr = np.frombuffer(image_data, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Не удалось декодировать изображение")
    return frame


@app.route("/")
def index():
    return redirect(url_for("register"))


@app.route("/register", methods=["GET", "POST"])
def register():
    status_message = None
    success = False

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        employee_code = request.form.get("employee_code", "").strip().upper()
        role = request.form.get("role", "").strip().lower()
        department = request.form.get("department", "").strip() or None
        photo_data = request.form.get("photo_data", "")

        if not photo_data:
            status_message = "Сначала сделайте фото сотрудника."
        else:
            try:
                frame = decode_base64_image(photo_data)
                result = register_employee(full_name, employee_code, role, department, frame)
                status_message = result.get("message", "Неизвестная ошибка")
                success = result.get("success", False)
            except Exception as exc:
                status_message = f"Ошибка при обработке фото: {exc}"

    return render_template_string(HTML_TEMPLATE, status_message=status_message, success=success)


def main() -> None:
    init_db()
    load_dotenv()
    port = 5000

    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port '{sys.argv[1]}'. Using default 5000.")
    else:
        import os
        env_port = os.getenv('WEB_REGISTER_PORT')
        if env_port:
            try:
                port = int(env_port)
            except ValueError:
                print(f"Invalid WEB_REGISTER_PORT='{env_port}'. Using default 5000.")

    print(f"Starting web registration on http://localhost:{port}/register")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
