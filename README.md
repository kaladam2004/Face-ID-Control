# 🏫 Dahua Attendance System

**Системаи пурраи назорати ҳозиршавӣ барои дастгоҳҳои Dahua Face Access Terminal**

---

## 📋 Имкониятҳо

- ✅ Парсинги event-ҳои Dahua CGI stream (бе RTSP/OpenCV)
- ✅ 2 дастгоҳ — IN (омадан) ва OUT (рафтан) — ҳамзамон
- ✅ Мантиқи дуруст: аввалин IN ва охирин OUT
- ✅ Санҷиши duplicate (configurable timeout)
- ✅ Ҳисоби дермонӣ ва барвақт рафтан
- ✅ Жадвали кории инфиродӣ барои ҳар корманд
- ✅ Ҳисоботи Excel: рӯзона, ҳафтаина, моҳона
- ✅ Telegram bot бо командаҳо ва огоҳиҳои автоматӣ
- ✅ Auto-reconnect ба дастгоҳҳо
- ✅ SQLite база (crash-safe WAL mode)
- ✅ Production-ready: logging, error handling, 24/7

---

## 🗂️ Сохтори лоиҳа

```
dahua_attendance/
├── run_all.py              # 🚀 Нуқтаи оғоз (як команда)
├── manage_employees.py     # 🛠️ CLI барои кормандон
├── start.sh                # 🐚 Bash launcher
├── requirements.txt
├── .env                    # Танзимот (аз .env.example нусха кунед)
├── .env.example
│
├── config/
│   └── settings.py         # Ҳамаи танзимот аз .env
│
├── core/
│   ├── database.py         # DatabaseManager + schema
│   ├── employees.py        # Идоракунии кормандон
│   ├── attendance.py       # Мантиқи асосии ҳозиршавӣ
│   └── event_parser.py     # Парсинги event Dahua
│
├── listeners/
│   └── dahua_listener.py   # CGI stream listener + reconnect
│
├── bot/
│   └── telegram_bot.py     # Telegram bot + notification service
│
├── reports/
│   └── excel_report.py     # Excel ҳисобот (openpyxl)
│
├── utils/
│   ├── logger.py           # Logging setup
│   └── scheduler.py        # Огоҳиҳои автоматӣ
│
├── tests/
│   ├── test_system.py      # Санҷишҳои воҳидӣ
│   └── seed_data.py        # Маълумоти намунавӣ
│
├── data/                   # SQLite база
├── logs/                   # Логҳо
└── exports/                # Excel файлҳо
```

---

## ⚡ Оғоз (Quick Start)

### 1. Насб кардан

```bash
git clone <repo>
cd dahua_attendance
pip install -r requirements.txt
cp .env.example .env
```

### 2. Танзими `.env`

```env
DEVICE_IN_IP=192.168.1.81
DEVICE_OUT_IP=192.168.1.80
DEVICE_IN_PASSWORD=admin123
DEVICE_OUT_PASSWORD=admin123
TELEGRAM_BOT_TOKEN=your_token_from_botfather
TELEGRAM_ADMIN_CHAT_IDS=your_chat_id
TIMEZONE=Asia/Dushanbe
```

> **Telegram Chat ID** — боти `@userinfobot`-ро паём фиристед.

### 3. Иловакунии кормандон

```bash
python manage_employees.py add
```

ё маълумоти намунавӣ:
```bash
python run_all.py --seed
```

### 4. Санҷиш

```bash
python tests/test_system.py
```

### 5. Иҷро

```bash
python run_all.py
```

ё

```bash
bash start.sh
```

---

## 🤖 Telegram Bot командаҳо

| Команда | Тавсиф |
|---------|--------|
| `/today` | Ҳозиршавии имрӯз |
| `/late` | Кӣ имрӯз дер кард |
| `/absent` | Кӣ имрӯз ғоиб |
| `/status` | Ҳолати дастгоҳҳо |
| `/download_daily` | Excel рӯзона |
| `/download_weekly` | Excel ҳафтаина |
| `/download_monthly` | Excel моҳона |

---

## 🛠️ Идоракунии кормандон (CLI)

```bash
# Рӯйхати ҳама кормандон
python manage_employees.py list

# Иловакунии корманди нав
python manage_employees.py add

# Танзими жадвали корӣ
python manage_employees.py set-schedule EMP001

# Барориши ҳисобот
python manage_employees.py report today
python manage_employees.py report weekly
python manage_employees.py report monthly
python manage_employees.py report custom
```

---

## ⚙️ Параметрҳои run_all.py

```bash
python run_all.py                  # Режими стандартӣ
python run_all.py --test-mode      # Бе дастгоҳ (барои тест)
python run_all.py --seed           # Маълумоти намунавӣ
python run_all.py --no-bot         # Бе Telegram bot
python run_all.py --no-listeners   # Бе listener (танҳо bot)
```

---

## 🗃️ Ҷадвалҳои база

| Ҷадвал | Тавсиф |
|--------|--------|
| `employees` | Маълумоти кормандон |
| `schedules` | Жадвали корӣ |
| `raw_events` | Event-ҳои хоми Dahua |
| `daily_attendance` | Ҳозиршавии рӯзона |
| `notifications_log` | Логи огоҳиҳо |
| `system_settings` | Танзимоти система |

---

## 🔒 Мантиқи ҳозиршавӣ

```
IN device (192.168.1.81):   08:01 → 08:03 → 08:05
                            ↓
                        first_in = 08:01 (танҳо аввалин)

OUT device (192.168.1.80):  10:20 → 14:02 → 16:15
                            ↓
                        last_out = 16:15 (танҳо охирин)

Дермонӣ:    first_in (08:12) - work_start (08:00) = 12 дақ
Барвақт:    work_end (16:00) - last_out (15:42) = 18 дақ
```

---

## 📊 Огоҳиҳои автоматии Telegram

| Вақт (пешфарз) | Огоҳӣ |
|----------------|-------|
| `08:15` | Санҷиши дермонӣ |
| `09:00` | Summary-и субҳ |
| `17:00` | Summary-и бегоҳ |
| `23:55` | Ғоибонро сабт кун |

---

## 🔧 Насб ҳамчун systemd service (Linux)

```ini
# /etc/systemd/system/attendance.service
[Unit]
Description=Dahua Attendance System
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/dahua_attendance
ExecStart=/usr/bin/python3 run_all.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable attendance
sudo systemctl start attendance
sudo systemctl status attendance
```

---

## 📦 Вобастагиҳо

```
python-dotenv       # Танзимоти .env
requests            # HTTP барои Dahua CGI
python-telegram-bot # Telegram bot
openpyxl            # Excel
pandas              # Маълумоти ҷадвалӣ
schedule            # Scheduler
pytz                # Timezone
```
