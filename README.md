# Calorie Counter

A Telegram bot for personalised calorie, protein, fat, and carb tracking — log your meals in one message and see your progress toward daily goals.

---

## Product Context

### End Users
People who track their daily nutrition intake.

### Problem
People want to track daily nutrition, but existing apps are cluttered, push premium paywalls, use generic norms, and require too many taps to log a meal. For users with eating disorders, calorie-focused interfaces can be triggering.

### Our Solution
Our bot solves this: one message `200/30/15/45` logs calories, protein, fat, and carbs instantly, and shows progress toward a personalised daily norm calculated from the user's body, activity, and goals.

### Stakeholders
- End-users seeking a quick, stress-free way to log daily nutrition
- Fitness enthusiasts wanting personalised norms tailored to their body and goals

---

## Project Plan

### Version 1: Core Tracker
**Features:**
- Personalised daily norm calculation (gender, weight, height, age, activity level, goal)
- One-message food logging (calories/protein/fat/carbs)
- Daily summary with progress tracking (surplus/deficit vs. target)
- Backend (PostgreSQL) + Telegram client

**Outcome:** A working MVP that delivers the core value: log intake, instantly view progress toward personalized goals.

### Version 2: Analytics & Refinement
**Features:**
- Interactive calendar with daily navigation and history view
- Weekly/monthly statistics with consolidated totals
- Advanced logging options (per-100g auto-calculation, entry correction/deletion)
- Deployment hardening, edge-case handling, and integration of TA feedback

**Outcome:** A production-ready app with a complete tracking lifecycle, historical analytics, and a polished UX for sustained use.

---

## Features

### Implemented
- **Personalised norm calculation** — gender, weight, height, age, activity level, and goal
- **One-message food logging** — enter `200/30/15/45` to log calories, protein, fat, and carbs
- **Per-100g auto-calculation** — enter `100/20/30/40 150` to calculate macros for any portion weight
- **Daily summary** — view your progress toward personalised targets
- **Interactive calendar** — navigate between days and view historical data
- **Weekly and monthly statistics** — consolidated totals with norm comparison
- **Entry correction and deletion** — remove or adjust any logged meal
- **Negative value protection** — values never drop below zero
- **Reply keyboard navigation** — all main actions accessible via bottom-panel buttons

### Not Yet Implemented
- Meal presets (save frequent meals for 1-tap logging)
- Data export (CSV/JSON download)
- Natural language input
- Web dashboard companion
- Push notifications and reminders

---

## Usage

1. Open Telegram and search for **@kbzhyshka_bot**
2. Send `/start` to begin
3. Complete the onboarding: select gender, enter weight (kg), height (cm), age, activity level, and goal
4. The bot calculates your personalised daily norm
5. Log meals by tapping **➕ Add** → select type → enter data in the required format
6. View your daily summary, calendar, or weekly/monthly statistics using the bottom-panel buttons

---

## Deployment

### Target OS
Ubuntu 24.04

### Prerequisites
The following must be installed on the VM:

```bash
# Python 3.10+
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# PostgreSQL client libraries (for psycopg2)
sudo apt install -y libpq-dev python3-dev

# Git
sudo apt install -y git
```

### Step-by-Step Deployment

**1. Clone the repository:**
```bash
git clone https://github.com/kaftanovaa/se-toolkit-hackathon.git
cd se-toolkit-hackathon
```

**2. Create and activate a virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```

**4. Create a `.env` file:**
```bash
cp .env.example .env
```

Edit `.env` and add your values:
```
BOT_TOKEN=your_telegram_bot_token_here
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

**5. Obtain a Telegram Bot Token:**
- Open Telegram and message **@BotFather**
- Send `/newbot` and follow the prompts
- Copy the token and paste it into `BOT_TOKEN` in `.env`

**6. Set up PostgreSQL database:**
```bash
# Install PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE DATABASE calorie_counter;
CREATE USER counter_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE calorie_counter TO counter_user;
\q

# Update DATABASE_URL in .env
DATABASE_URL=postgresql://counter_user:your_password@localhost:5432/calorie_counter
```

**7. Run the bot:**
```bash
python3 main.py
```

**8. (Optional) Run as a systemd service for persistence:**
```bash
sudo nano /etc/systemd/system/calorie-counter.service
```

Paste the following:
```ini
[Unit]
Description=Calorie Counter Telegram Bot
After=network.target postgresql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/se-toolkit-hackathon
ExecStart=/home/ubuntu/se-toolkit-hackathon/venv/bin/python3 /home/ubuntu/se-toolkit-hackathon/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable calorie-counter
sudo systemctl start calorie-counter
sudo systemctl status calorie-counter
```

---

## Project Structure

```
se-toolkit-hackathon/
├── main.py           # Bot logic and handlers
├── config.py         # Environment variable loading
├── database.py       # PostgreSQL operations
├── keyboards.py      # Reply and inline keyboard layouts
├── requirements.txt  # Python dependencies
├── LICENSE           # MIT License
├── README.md         # This file
├── .env.example      # Environment template
└── .gitignore        # Ignored files
```

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
