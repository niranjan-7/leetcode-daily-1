# 🚀 LeetCode Daily Challenge & Streak Bot

An asynchronous, intelligent Discord bot that posts daily LeetCode challenges, provides progressive spoiler-safe hints, tracks individual solving streaks, and sends smart reminders that only notify members who haven't completed today's challenge.

---

## ✨ Features

- **⚡ Asynchronous LeetCode GraphQL Client**: Powered by `aiohttp` with anti-bot headers and resilient query execution.
- **📊 Rich Problem Embeds**: Includes difficulty badges (🟢 Easy, 🟡 Medium, 🔴 Hard), acceptance rate, problem topics, and date.
- **💡 Progressive Hint System**: Reveal hints on demand with Discord spoiler masking (`||hint||`) via `/hint [num]` so other solvers aren't spoiled.
- **🔥 Automatic Streak Tracking (SQLite)**:
  - Mark completion by simply clicking the **`✅`** reaction on the daily announcement post, OR
  - Run `/solved` in any channel.
  - Automatically calculates current streaks, personal best streaks, and total solved count.
- **⏰ 3-Stage Smart Reminders (IST)**:
  - **8:00 AM IST**: Daily challenge announcement (only pings enrolled participants).
  - **1:00 PM IST**: Midday check-in (**only pings members who haven't completed yet**; completed members are exempt).
  - **8:30 PM IST**: Evening reminder (**only pings members who haven't completed yet** before midnight reset).
- **👥 Dynamic Participant Enrollment**:
  - Automatically registers new members who react `✅` or run `/solved`.
  - Manual enrollment via `/join` and `/leave`.
- **🏆 Server Leaderboard**: Top 10 streak leaders with `/leaderboard`.

---

## 🛠️ Slash Commands

| Command | Description |
| :--- | :--- |
| `/daily` | View today's active LeetCode daily challenge embed. |
| `/hint [num]` | Reveal a spoiler-masked hint privately for today's challenge. |
| `/solved` | Manually mark today's problem as solved and view your streak. |
| `/streak [@user]` | View your or another member's current streak, highest streak, and total solves. |
| `/leaderboard` | View the server's top 10 streak leaderboard. |
| `/participants` | View all currently enrolled participants and today's completion status. |
| `/join` | Enroll as an active participant for daily announcements and smart reminders. |
| `/leave` | Opt out of daily reminder pings. |
| `/help` | View the interactive guide and schedule. |
| `/ping` | Check bot latency and status. |

---

## 🚀 Setup & Installation

### 1. Clone the repository
```bash
git clone https://github.com/niranjan-7/leetcode-daily-1.git
cd leetcode-daily-1
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
Create a `.env` file from `.env.example`:
```bash
cp .env.example .env
```
Fill in your configuration:
```env
DISCORD_TOKEN=your_bot_token_here
CHANNEL_ID=your_channel_id_here
TIMEZONE=Asia/Kolkata
MORNING_HOUR=8
MORNING_MINUTE=0
AFTERNOON_HOUR=13
AFTERNOON_MINUTE=0
EVENING_HOUR=20
EVENING_MINUTE=30
```

### 4. Discord Developer Portal Settings
Make sure **Privileged Gateway Intents** are enabled:
- **Server Members Intent**: `ON`
- **Message Content Intent**: `ON`

### 5. Run the bot
```bash
python main.py
```
Or manage it with PM2:
```bash
pm2 start main.py --name leetcode-bot --interpreter python3
```
