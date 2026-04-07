# Calorie Counter

A Telegram bot for personalised calorie, protein, fat, and carb tracking — log your meals in one message and see your progress toward daily goals.

---

## Demo

![Personal Norm Calculation](demo_norm.png)
*Personalised daily norm calculated from user's body, activity level, and goal.*

![Main Menu](demo_main.png)
*Main menu with quick-access buttons for daily tracking, calendar, and statistics.*

![Daily Summary](demo_today.png)
*Daily summary showing progress toward personalised calorie and macronutrient targets.*

![Interactive Calendar](demo_calendar.png)
*Navigate through months and view any day's nutrition data with surplus/deficit indicators.*

![Weekly Statistics](demo_week.png)
*Consolidated weekly totals compared against personalised norms for each macronutrient.*

![Monthly Statistics](demo_month.png)
*Monthly overview with aggregated values and overall progress toward targets.*

---

## Product Context

### End Users
People who track their daily nutrition intake.

### Problem
People want to track daily nutrition, but existing apps are cluttered, push premium paywalls, use generic norms, and require too many taps to log a meal.
### Our Solution
Our bot solves this: one message `200/30/15/45` logs calories, protein, fat, and carbs instantly, and shows progress toward a personalised daily norm calculated from the user's body, activity, and goals.

---

## Features

### Implemented
- Personalised daily norm calculation (gender, weight, height, age, activity level, goal)
- One-message food logging (calories/protein/fat/carbs)
- Per-100g auto-calculation for portion-weighted entries
- Daily summary with progress tracking (surplus/deficit vs. target)
- Interactive calendar with daily navigation and history view
- Weekly and monthly statistics with consolidated totals
- Entry correction and deletion
- Negative value protection (values never drop below zero)
- Reply keyboard navigation for all main actions

### Not Yet Implemented
- Meal presets (save frequent meals for 1-tap logging)
- Data export (CSV/JSON download)
- Natural language input (e.g., "I ate an apple and chicken breast")
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

### What Should Be Installed on the VM
- Python 3.10+
- pip and python3-venv
- PostgreSQL server
- Git

### Step-by-Step Deployment Instructions

**1. Clone the repository:**
```bash
git clone https://github.com/kaftanovaa/se-toolkit-hackathon.git
cd se-toolkit-hackathon
```

**2. Install system dependencies:**
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv libpq-dev python3-dev postgresql postgresql-contrib
```

**3. Create and activate a virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**4. Install Python dependencies:**
```bash
pip install -r requirements.txt
```

**5. Set up the environment file:**
```bash
cp .env.example .env
```

Edit `.env` with your values:
```
BOT_TOKEN=your_telegram_bot_token_here
DATABASE_URL=postgresql://user:password@localhost:5432/calorie_counter
```

**6. Obtain a Telegram Bot Token:**
- Open Telegram and message **@BotFather**
- Send `/newbot` and follow the prompts
- Copy the token into `BOT_TOKEN` in `.env`

**7. Set up PostgreSQL:**
```bash
sudo -u postgres psql -c "CREATE DATABASE calorie_counter;"
sudo -u postgres psql -c "CREATE USER counter_user WITH PASSWORD 'your_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE calorie_counter TO counter_user;"
```

**8. Run the bot:**
```bash
python3 main.py
```

**9. (Optional) Run as a systemd service:**
```bash
sudo nano /etc/systemd/system/calorie-counter.service
```

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

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable calorie-counter
sudo systemctl start calorie-counter
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
└── .env.example      # Environment template
```

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
