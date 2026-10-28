import random
from typing import Optional, Dict, Any, List

# ==========================================
# 1. MORNING ANNOUNCEMENT (8:00 AM IST)
# ==========================================

MORNING_TITLES: List[str] = [
    "🚀 Daily LeetCode Challenge is Live!",
    "⚡ Today's Challenge Just Dropped!",
    "🧠 Time to Sharpen the Blade — Today's Problem is Here!",
    "☕ Grab Your Coffee — Daily Problem Unlocked!",
    "🔥 Fresh Algorithm Incoming — Let's Conquer It!",
    "🎯 The Daily Arena is Open!",
    "☀️ Morning Algorithmic Awakening!",
    "🏆 New Day, New Problem — Keep the Streak Alive!",
    "💡 Algorithm of the Day is Ready!",
    "🏁 Ready, Set, Code — Today's Challenge Awaits!"
]

MORNING_QUOTES: List[str] = [
    "The secret of getting ahead is getting started. Tackle today's problem with clarity!",
    "Small daily improvements over time lead to stunning algorithmic mastery.",
    "Do something today that your future self will thank you for.",
    "Mastery is not about doing 1,000 problems once, but understanding the core patterns deeply.",
    "Wake up with determination, go to bed with satisfaction and a green tick.",
    "Every hard problem is just a series of easy problems chained together.",
    "An algorithm a day keeps unemployment away.",
    "Consistency beats talent when talent doesn't stay consistent.",
    "The grind you put in this morning pays compounding dividends tomorrow.",
    "Code with clarity, test with rigor, optimize with patience.",
    "The obstacle is the way. Every tricky edge-case is a lesson in disguise.",
    "You don't have to be great to start, but you have to start to be great."
]

# ==========================================
# 2. MIDDAY CHECK-IN (1:00 PM IST)
# ==========================================

MIDDAY_TITLES: List[str] = [
    "⏰ 1:00 PM Midday Check-In!",
    "☀️ Afternoon Algorithmic Pulse!",
    "⏳ Half the Day is Behind Us — Challenge Waiting!",
    "⚡ Post-Lunch Coding Fuel — Lock in Your Green Tick!",
    "🎯 Lunch Break Algorithm Sprint!",
    "🔥 Midday Momentum Check — Who's Ready?",
    "💡 Take 20 Minutes This Afternoon to Solve It!",
    "🏹 Halfway Through the Day — Aim for That Solve!"
]

MIDDAY_QUOTES: List[str] = [
    "Half the day has passed, but the problem is patiently waiting. Take 20 minutes and knock it out!",
    "Midday persistence separates the dreamers from the achievers.",
    "Your streak is a monument to your discipline. Keep adding bricks.",
    "A 20-minute focused coding session now frees up your entire evening.",
    "Progress over perfection. Break down the inputs, trace the edges, and ship the code.",
    "The best time to solve today's challenge was this morning. The second best time is right now.",
    "Energy flows where attention goes. Focus on today's logic and lock it down.",
    "Don't wait for motivation — discipline is what gets the submission accepted.",
    "One solved challenge now means an evening free of reminder pings!",
    "Step away from the screen for 2 minutes, think through the brute force, then optimize."
]

# ==========================================
# 3. EVENING REMINDER (8:30 PM IST)
# ==========================================

EVENING_TITLES: List[str] = [
    "🌙 8:30 PM Evening Reminder — Reset Approaching!",
    "⏳ Final Call: The Clock is Ticking!",
    "🔥 Protect Your Streak — Night Reminder!",
    "🚨 ~3.5 Hours Remaining — Don't Break the Chain!",
    "💪 Late-Night Grit: 20 Minutes to Save Your Streak!",
    "🌙 The Midnight Reset is Coming — Lock It In!",
    "⚡ Final Stretch: Don't Let Today Slip Away!"
]

EVENING_QUOTES: List[str] = [
    "Only ~3.5 hours remaining! Don't let days of hard work vanish before midnight.",
    "It's not over until the green Accepted message appears. You've got this!",
    "Discipline is choosing between what you want now and what you want most.",
    "20 minutes of focus tonight saves weeks of streak regret tomorrow.",
    "When fatigue sets in, character steps up. Finish strong tonight!",
    "You've solved harder problems than this. Write the base case and power through.",
    "Champions find a way to get it done, no matter how busy the day was.",
    "Don't break the chain. Keep the flame burning bright before midnight!"
]

# ==========================================
# 4. ON-DEMAND TRIGGER CHECK-IN
# ==========================================

TRIGGER_QUOTES: List[str] = [
    "Consistency isn't about perfection; it's about refusing to give up.",
    "Stay focused, stay humble, and keep building that problem-solving intuition.",
    "Great coders aren't born; they are forged one daily challenge at a time.",
    "The code you write today is the foundation for the interview you'll ace tomorrow."
]

# ==========================================
# 5. PRIVATE SOLVED CELEBRATIONS (EPHEMERAL)
# ==========================================

SOLVED_TITLES: List[str] = [
    "Challenge Crushed! 🏆",
    "Flawless Execution! 🎯",
    "Problem Conquered! ⚡",
    "Another One in the Books! 🔥",
    "Algorithmic Victory! 🚀",
    "Green Tick Secured! ✨",
    "Submission Accepted! 💎",
    "Logic On Point! 🧠"
]

SOLVED_SUBTITLES: List[str] = [
    "Your logic was sharp and your execution clean!",
    "Another green tick etched into your streak history.",
    "Consistency is the true superpower. Great job today!",
    "Zero pings for you for the rest of the day — enjoy the peace of mind!",
    "One day closer to algorithmic mastery. Keep grinding!",
    "Brute force avoided, optimal logic deployed. High five!",
    "Streak defended with honor! Time to level up with bonus practice below."
]

# ==========================================
# 6. 100% SERVER SWEEP CELEBRATION
# ==========================================

SERVER_SWEEP_TITLES: List[str] = [
    "🌟 Server Sweep: 100% Completed Today!",
    "🚀 Flawless Victory: Every Participant Checked In!",
    "🔥 Zero Slackers: The Entire Server Conquered Today's Problem!",
    "🛡️ All Streaks Intact: Perfect Team Performance Today!",
    "👑 Clean Sheet: 100% of Active Solvers Finished!"
]

SERVER_SWEEP_DESCRIPTIONS: List[str] = [
    "Every single participant logged their solution today! All streaks are guarded and safe.",
    "Total dominance today team! Zero reminder pings needed tonight.",
    "The server is on fire! 100% completion rate across all active members.",
    "Flawless algorithmic discipline today! Keep this collective momentum rolling."
]

# ==========================================
# 7. SUNDAY 11:00 AM CHAMPION SHOWCASE
# ==========================================

SUNDAY_CHAMPION_TITLES: List[str] = [
    "👑 Weekly LeetCode Champion — Sunday Showcase!",
    "🏆 Server Champion Spotlight — Week in Review!",
    "🔥 Supreme Streaker: Sunday Leaderboard Coronation!",
    "🌟 Hall of Fame: This Week's Algorithm Ruler!",
    "🎖️ Weekly Podium: Crowning Our LeetCode Leader!"
]

SUNDAY_CHAMPION_DESCRIPTIONS: List[str] = [
    "Consistency creates champions! Let's recognize our #1 problem solver this week:",
    "A full week of algorithmic grit! Bow down to this week's reigning leaderboard leader:",
    "Seven days of discipline, zero excuses. Here is our server champion for the week:",
    "Leading from the front! Here is who holds the crown heading into the new week:"
]

# ==========================================
# 8. MILESTONE DEFINITIONS
# ==========================================

# Milestones: 7 days, 28 days, 56 days, and monthly multiples (30, 60, 90, 120, 150, 180, 365...)
MILESTONE_CONFIG: Dict[int, Dict[str, str]] = {
    7: {
        "badge": "🥉",
        "title": "7-Day Streak Conquered! (1 Full Week)",
        "desc": "One solid week of unbroken algorithmic discipline! You've officially built the habit."
    },
    28: {
        "badge": "🥈",
        "title": "28-Day Streak Master! (4 Continuous Weeks)",
        "desc": "Four continuous weeks of daily problem-solving! Your algorithmic intuition is operating at peak levels."
    },
    30: {
        "badge": "🗓️",
        "title": "30-Day Monthly Milestone! (1 Month)",
        "desc": "A full calendar month of non-stop coding! You are in the top tier of consistency."
    },
    56: {
        "badge": "🥇",
        "title": "56-Day Streak Titan! (8 Weeks)",
        "desc": "Eight straight weeks without missing a single day! Pure algorithmic mastery and relentless focus."
    },
    60: {
        "badge": "🗓️",
        "title": "60-Day Streak Legend! (2 Full Months)",
        "desc": "Two full months of dedication! Your persistence is an inspiration to the entire server."
    },
    90: {
        "badge": "💎",
        "title": "90-Day Quarter Milestone! (3 Months)",
        "desc": "Three months of relentless daily problem solving! Interview-ready intuition unlocked."
    },
    100: {
        "badge": "💯",
        "title": "Century Club: 100-Day Streak!",
        "desc": "Triple digits! An elite accomplishment achieved only by the most dedicated engineers."
    },
    180: {
        "badge": "🌟",
        "title": "Half-Year Streak Phenomenon! (6 Months)",
        "desc": "Half a year of daily dedication! Coding has become second nature."
    },
    365: {
        "badge": "👑",
        "title": "365-Day Grandmaster! (1 Full Year)",
        "desc": "A FULL YEAR OF UNBROKEN LEETCODE! Absolute legend status in the server."
    }
}


def get_morning_title() -> str:
    return random.choice(MORNING_TITLES)


def get_morning_quote() -> str:
    return random.choice(MORNING_QUOTES)


def get_midday_title() -> str:
    return random.choice(MIDDAY_TITLES)


def get_midday_quote() -> str:
    return random.choice(MIDDAY_QUOTES)


def get_evening_title() -> str:
    return random.choice(EVENING_TITLES)


def get_evening_quote() -> str:
    return random.choice(EVENING_QUOTES)


def get_trigger_quote() -> str:
    return random.choice(TRIGGER_QUOTES)


def get_solved_title() -> str:
    return random.choice(SOLVED_TITLES)


def get_solved_subtitle() -> str:
    return random.choice(SOLVED_SUBTITLES)


def get_server_sweep_title() -> str:
    return random.choice(SERVER_SWEEP_TITLES)


def get_server_sweep_desc() -> str:
    return random.choice(SERVER_SWEEP_DESCRIPTIONS)


def get_sunday_champion_title() -> str:
    return random.choice(SUNDAY_CHAMPION_TITLES)


def get_sunday_champion_desc() -> str:
    return random.choice(SUNDAY_CHAMPION_DESCRIPTIONS)


def check_milestone(streak: int) -> Optional[Dict[str, str]]:
    """
    Checks if a streak count qualifies for a public milestone celebration.
    Supports specific landmarks (7, 28, 56, 100, 365) and any monthly multiple of 30.
    """
    if streak in MILESTONE_CONFIG:
        return MILESTONE_CONFIG[streak]

    # Dynamic multiples of 30 for higher months (120, 150, 210, etc.)
    if streak > 30 and streak % 30 == 0:
        months = streak // 30
        return {
            "badge": "🗓️",
            "title": f"{streak}-Day Streak! ({months} Months)",
            "desc": f"{months} full months of consistent problem solving! Unbelievable discipline."
        }

    return None
