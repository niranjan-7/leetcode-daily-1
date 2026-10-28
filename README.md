# 🚀 LeetCode Daily Challenge & Streak Bot

An asynchronous, intelligent Discord bot that posts daily LeetCode challenges, provides progressive spoiler-safe hints, tracks individual solving streaks, and sends smart reminders that only notify members who haven't completed today's challenge.

---

## ✨ Features

- **⚡ Asynchronous LeetCode GraphQL Client**: Powered by `aiohttp` with anti-bot headers and resilient query execution.
- **📊 Rich Problem Embeds**: Includes difficulty badges (🟢 Easy, 🟡 Medium, 🔴 Hard), acceptance rate, problem topics, and date.
- **💡 Progressive Hint System**: Reveal hints on demand with Discord spoiler masking (`||hint||`) via `/hint [num]` so other solvers aren't spoiled.
- **🔥 Private Ephemeral Streak Tracking (`Only you can see this`)**:
  - Click the **`Mark Solved ✅`** button on any challenge card or run `/solved`.
  - Your completion confirmation, updated streak, and 4-problem bonus practice track are displayed in a **100% private ephemeral message** (`Only you can see this • Dismiss message`) so your solutions and stats never clutter the public channel.
  - Clicking the **`✅`** emoji reaction also quietly logs completion in SQLite without sending any public channel messages.
  - Automatically advances streaks, logs personal bests, and tracks total solved problems.
- **🎉 Public Milestone Celebrations**:
  - While regular daily solves remain completely private, major landmark streaks trigger a public celebration in the channel tagging the solver!
  - Celebrates landmark streaks: **7 Days** (1 Week), **28 Days** (4 Weeks), **56 Days** (8 Weeks), and all monthly multiples (**30, 60, 90, 100, 180, 365 Days**).
- **👑 Weekly Sunday Champion Spotlight (11:00 AM IST)**:
  - Every Sunday at 11:00 AM IST, the bot crowns and showcases the server's #1 streak leader with stats and achievements.
- **🛡️ 60-Day Data Retention Policy**:
  - If a member uses `/leave`, their solved history and streak data are preserved for 60 days (2 months).
  - Rejoining via `/join` or `/solved` within 60 days restores full history seamlessly; after 60 days of inactivity, expired records are permanently pruned.
- **💬 Dynamic Rotating Phrases & Quotes**:
  - Dynamic rotational phrases and quotes across morning announcements, midday check-ins, evening reminders, solves, and 100% team sweeps.
  - Motivational quotes are exclusively reserved for announcements and check-ins, keeping `/daily` problem specifications clean and focused.
- **⏰ 3-Stage Smart Reminders with Cascading Exemptions (IST)**:
  - **8:00 AM IST**: Daily challenge announcement (only pings enrolled participants).
  - **1:00 PM IST**: Midday check-in (**only pings members who haven't completed yet**; members who solved earlier are completely exempt from pings).
  - **8:30 PM IST**: Evening reminder (**only pings members who STILL haven't completed**; anyone who solved at or after 1:00 PM is also exempt!).
  - If 100% of participants have finished, posts a celebration message with **zero pings**.
- **🎯 Dynamic Trigger Command (`/trigger`)**:
  - **Between 5:30 AM and 8:00 AM IST**: Posts the official daily announcement early and automatically skips the scheduled 8:00 AM post to prevent duplicates.
  - **After 8:00 AM IST**: Evaluates the live completion status and sends an on-demand check-in pinging **only** pending members.
  - Does not alter or cancel the independent 1:00 PM or 8:30 PM scheduled check-ins.
- **📚 Curated Bonus Practice Track (2 Easy, 1 Medium, 1 Hard)**:
  - Dynamically queries LeetCode for 4 similar free practice problems matching today's primary topic.
  - Cached daily in SQLite (`bonus_problems`) for zero latency.
  - Delivered privately to the solver upon completing the daily challenge.
  - Highlighted in check-in and trigger posts tagging **only completed solvers** near the practice challenge set.
- **👥 Dynamic Participant Enrollment**:
  - Automatically registers new members who click `Mark Solved ✅`, react `✅`, or run `/solved`.
  - Manual enrollment via `/join` and `/leave`.
- **🏆 Server Leaderboard**: Top 10 streak leaders with `/leaderboard`.

---

## 🛠️ Commands & Usage

The bot supports native Discord **Slash Commands**, traditional **Prefix Commands** (`!`, `\`, `/`), and **plain text words** in chat:

| Command | Type | Description |
| :--- | :--- | :--- |
| `/daily` | Public | View today's active LeetCode daily challenge embed. |
| `/practice` | Public | View today's curated 4 similar practice problems (2 Easy, 1 Medium, 1 Hard). |
| `/trigger` | Public | Post daily challenge early (5:30–8:00 AM, skips 8 AM post) OR on-demand check-in pinging only pending members (after 8 AM). |
| `/hint [num]` | Ephemeral | Reveal a spoiler-masked hint privately (`Only you can see this`). |
| `/solved` | Ephemeral | Mark today's problem as solved privately with streak & bonus problems (`Only you can see this`). |
| `Mark Solved ✅` | Button | Persistent interactive button on challenge cards to log completion privately. |
| `/streak [@user]` | Public | View your or another member's current streak, highest streak, and total solves. |
| `/leaderboard` | Public | View the server's top 10 streak leaderboard. |
| `/participants` | Public | View all currently enrolled participants and live `✅ Solved` / `⏳ Pending` status. |
| `/join` | Public | Enroll as an active participant for daily announcements and smart reminders. |
| `/leave` | Ephemeral | Opt out of daily reminder pings. |
| `/help` | Public | View the interactive guide and schedule. |
| `/ping` | Ephemeral | Check bot latency and status. |

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
