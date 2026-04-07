# Attendance & Turnstile System

Локальная desktop-программа на Python для регистрации сотрудников и мини-симуляции турникета с распознаванием лиц.

## Структура

```bash
attendance_system/
├── app.py
├── database.py
├── face_utils.py
├── gui.py
├── models.py
├── photos/
├── logs/
│   └── unknown/
├── attendance.db
└── requirements.txt
```

## Что исправлено

- убрана нестабильная логика с `cv2.imshow()` в фоновых потоках;
- добавлено live-preview камеры прямо в Tkinter;
- исправлены абсолютные пути к БД и папкам;
- улучшено определение камеры для macOS M2 и Windows;
- сохранены snapshot-ы в `logs/` и `logs/unknown/`;
- оставлена anti-duplicate логика на 30 секунд;
- улучшены сообщения об ошибках;
- добавлены автообновление логов, face boxes, name labels, beep.

## Установка

### 1. Создайте виртуальное окружение

```bash
python -m venv .venv
source .venv/bin/activate
```

На Windows:

```bash
.venv\Scripts\activate
```

### 2. Установите зависимости

```bash
pip install -r requirements.txt
```

### 3. Если `face_recognition` / `dlib` не ставится

#### macOS Apple Silicon (M1/M2)

Обычно помогают:

```bash
brew install cmake
xcode-select --install
pip install dlib
pip install face_recognition
```

#### Windows

- установите CMake;
- установите Microsoft C++ Build Tools;
- затем снова выполните `pip install -r requirements.txt`.

## Запуск

```bash
python app.py
```

## Как зарегистрировать сотрудника

1. Введите **Full Name**.
2. Введите **Employee Code**.
3. Нажмите **Open Camera for Register**.
4. Подведите лицо к камере.
5. Когда найдено ровно одно лицо, нажмите **Capture & Save**.
6. Фото сохранится в `photos/`, encoding — в SQLite.

## Как использовать турникет

1. Нажмите **Open Turnstile**.
2. Камера откроется с live-preview.
3. Встаньте перед камерой один.
4. Нажмите **Scan Current Frame**.
5. Если лицо известно — будет `Access Granted`, лог сохранится в БД и snapshot уйдёт в `logs/`.
6. Если лицо неизвестно — будет `Unknown Person`, snapshot уйдёт в `logs/unknown/`.

## Примечания

- приложение работает полностью локально и офлайн;
- база создаётся автоматически;
- папки `photos/`, `logs/`, `logs/unknown/` создаются автоматически;
- при повторном проходе того же сотрудника в течение 30 секунд новый лог не создаётся.
