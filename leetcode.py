import html
import re
import random
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import aiohttp
import discord

LEETCODE_URL = "https://leetcode.com/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://leetcode.com"
}

MOTIVATIONAL_QUOTES = [
    "Consistency beats talent when talent doesn’t work hard. Let’s crack today’s problem!",
    "One problem a day keeps the unemployment away. Let’s get it!",
    "Small daily improvements over time lead to stunning results. Let's solve this together!",
    "Don't practice until you get it right. Practice until you can't get it wrong. Time to code!",
    "Discipline is choosing between what you want now and what you want most. Let's grind!",
    "Code is like humor. When you have to explain it, it’s bad. Keep it clean today!",
    "First, solve the problem. Then, write the code.",
    "Experience is the name everyone gives to their mistakes. Debug and move forward!",
    "Every expert was once a beginner who refused to quit.",
    "Make it work, make it right, make it fast.",
    "It’s not a bug, it’s an undocumented feature waiting for you to conquer it.",
    "The only way to learn a new programming language or paradigm is by writing programs in it.",
    "Simplicity is prerequisite for reliability.",
    "A clean algorithmic solution is a thing of pure beauty.",
    "Don’t count the days, make the daily streaks count.",
    "You don’t have to be great to start, but you have to start to be great.",
    "Today's effort is tomorrow's offer letter.",
    "Master the basics, and the complex problems solve themselves.",
    "The secret of getting ahead is getting started.",
    "Strive for progress, not perfection.",
    "Your future self will thank you for solving this today.",
    "Data structures are your tools; logic is your craft.",
    "Push yourself, because no one else is going to do it for you.",
    "Big journeys begin with small steps. Submit that first solution!",
    "Failure is simply the opportunity to begin again, this time more intelligently.",
    "One acceptance a day builds the muscle memory you need for the interview room.",
    "Hard work beats luck every single time.",
    "Focus on the process, and the rating points will follow.",
    "Don't wish it were easier; wish you were better prepared. Let's practice!",
    "An optimized algorithm is music to a developer's ears.",
    "Great coders aren't born; they are forged in the fires of edge cases.",
    "Clear your mind, open your IDE, and let's get solving.",
    "A year from now, you'll wish you had started today.",
    "The grind you put in today pays dividends tomorrow.",
    "Stay hungry, stay coding.",
    "Every Runtime Error is just a stepping stone to an Accepted submission.",
    "Think twice, code once.",
    "Action is the foundational key to all success.",
    "Turn caffeine into clean code.",
    "Complexity is the enemy of execution. Simplify your logic.",
    "Success is the sum of small efforts repeated day in and day out.",
    "Edge cases define true mastery.",
    "The best view comes after the hardest climb. Tackle that hard problem!",
    "Don't stop when you're tired. Stop when you're done.",
    "Keep calm and submit code.",
    "Brute force first, optimize second.",
    "The master has failed more times than the beginner has even tried.",
    "Your keyboard is your instrument; make music with your logic.",
    "Solve problems, don't just memorize solutions.",
    "Dedication is doing it even when you don't feel like it.",
    "A bug solved today is wisdom earned forever.",
    "Dream big, code clean, stay humble.",
    "Opportunities don't happen; you create them through prep.",
    "Every LeetCode green checkmark is a win for the team.",
    "Sharpen your algorithmic axe before you start chopping.",
    "Believe in the power of compound daily practice.",
    "Good programmers write code that humans can understand.",
    "Doubt kills more dreams than failure ever will. Believe in your logic!",
    "The best way to predict the future is to invent it.",
    "Stay consistent, stay sharp.",
    "A day without solving is a missed opportunity to grow.",
    "Focus on understanding the patterns, not just passing test cases.",
    "Your only limit is your willingness to sit down and debug.",
    "Success doesn't come to you, you go to it.",
    "Level up your problem-solving one challenge at a time.",
    "Work hard in silence; let your offers make the noise.",
    "The mind once stretched by a new problem never returns to its original dimensions.",
    "Keep coding, keep improving, keep showing up.",
    "One line of clean code at a time.",
    "Don't fear the Hard difficulty; it's just multiple Medium concepts glued together.",
    "The struggle you're in today is developing the strength you need for tomorrow.",
    "Code with clarity, test with rigor.",
    "Success starts with self-discipline.",
    "Treat every edge case like a VIP guest.",
    "There are no shortcuts to any place worth going.",
    "Great algorithms come from persistent debugging.",
    "Be stronger than your excuses.",
    "Small daily wins lead to massive career leaps.",
    "Stay curious, keep breaking down the problem.",
    "Consistency is the DNA of mastery.",
    "Turn 'I can't solve this' into 'I haven't solved this yet.'",
    "Don't let a Time Limit Exceeded error break your spirit; optimize and conquer!",
    "Great things never come from comfort zones.",
    "Keep your focus sharp and your functions pure.",
    "Patience, persistence, and problem-solving.",
    "Push through the confusion; clarity lives on the other side.",
    "You are capable of solving more than you think.",
    "Embrace the challenge today, reap the reward tomorrow.",
    "Your streak is your proof of dedication.",
    "Think outside the box, but keep your time complexity reasonable.",
    "Great engineering begins with foundational understanding.",
    "Build momentum daily.",
    "Never underestimate the power of showing up every single day.",
    "Coding is thinking, not typing.",
    "Conquer the problem before it conquers your schedule.",
    "Keep your head down and build your skills.",
    "Winners never quit, and quitters never code.",
    "Let's show today's daily problem who's boss!",
    "Together we code, together we grow. Let's solve it!"
]


def clean_html_text(text: str) -> str:
    """Strips HTML tags and unescapes HTML entities for clean Discord text."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", text)
    return html.unescape(clean).strip()


async def fetch_leetcode_daily(session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Any]:
    """
    Fetches the active LeetCode daily coding challenge asynchronously.
    """
    query = """
    query questionOfToday {
        activeDailyCodingChallengeQuestion {
            date
            link
            question {
                questionFrontendId
                title
                difficulty
                acRate
                hints
                topicTags {
                    name
                }
            }
        }
    }
    """
    payload = {"query": query}

    async def _do_fetch(s: aiohttp.ClientSession):
        async with s.post(LEETCODE_URL, json=payload, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data

    if session is not None:
        data = await _do_fetch(session)
    else:
        async with aiohttp.ClientSession() as new_session:
            data = await _do_fetch(new_session)

    challenge = data["data"]["activeDailyCodingChallengeQuestion"]
    question = challenge["question"]
    tags = [t["name"] for t in question.get("topicTags", [])]
    raw_hints = question.get("hints", [])
    cleaned_hints = [clean_html_text(h) for h in raw_hints if h]

    return {
        "id": question["questionFrontendId"],
        "title": question["title"],
        "difficulty": question["difficulty"],
        "url": f"https://leetcode.com{challenge['link']}",
        "tags": ", ".join(tags) if tags else "None",
        "ac_rate": round(question.get("acRate", 0), 1),
        "hints": cleaned_hints,
        "date": challenge["date"]
    }


def get_random_quote() -> str:
    return random.choice(MOTIVATIONAL_QUOTES)


def create_problem_embed(problem: Dict[str, Any]) -> discord.Embed:
    diff_styles = {
        "Easy": {"color": discord.Color.green(), "emoji": "🟢"},
        "Medium": {"color": discord.Color.gold(), "emoji": "🟡"},
        "Hard": {"color": discord.Color.red(), "emoji": "🔴"}
    }
    style = diff_styles.get(problem["difficulty"], {"color": discord.Color.blue(), "emoji": "⚪"})

    embed = discord.Embed(
        title=f"{style['emoji']} LeetCode Daily: #{problem['id']} - {problem['title']}",
        url=problem["url"],
        description="Today's challenge is ready! Grab your coffee and let's conquer it.",
        color=style["color"],
        timestamp=datetime.now(timezone.utc)
    )

    embed.add_field(
        name="Difficulty",
        value=f"{style['emoji']} **{problem['difficulty']}**",
        inline=True
    )
    embed.add_field(
        name="Acceptance",
        value=f"📊 **{problem['ac_rate']}%**",
        inline=True
    )
    embed.add_field(
        name="Date",
        value=f"📅 `{problem['date']}`",
        inline=True
    )
    embed.add_field(
        name="Topics",
        value=f"🏷️ {problem['tags']}",
        inline=False
    )

    hint_count = len(problem["hints"])
    hint_text = f"💡 **{hint_count} hint{'s' if hint_count != 1 else ''} available** (Use `/hint` to reveal)" if hint_count > 0 else "💡 No hints available"
    embed.add_field(
        name="Hints",
        value=hint_text,
        inline=False
    )

    embed.set_footer(text="React with ✅ or use /solved to track your daily streak!")
    return embed
