import html
import re
import random
import asyncio
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
                    slug
                }
            }
        }
    }
    """
    payload = {"query": query}

    async def _do_fetch(s: aiohttp.ClientSession):
        max_retries = 5
        last_exc = None
        for attempt in range(1, max_retries + 1):
            try:
                async with s.post(LEETCODE_URL, json=payload, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    return data
            except Exception as e:
                last_exc = e
                if attempt < max_retries:
                    wait_time = min(2 ** attempt + random.uniform(0.5, 1.5), 20)
                    print(f"Warning: LeetCode daily fetch attempt {attempt}/{max_retries} failed ({e}). Retrying in {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
        raise last_exc

    if session is not None:
        data = await _do_fetch(session)
    else:
        async with aiohttp.ClientSession() as new_session:
            data = await _do_fetch(new_session)

    challenge = data["data"]["activeDailyCodingChallengeQuestion"]
    question = challenge["question"]
    topic_tags = question.get("topicTags", [])
    tags = [t["name"] for t in topic_tags]
    tag_slugs = [t.get("slug", "") for t in topic_tags if t.get("slug")]
    raw_hints = question.get("hints", [])
    cleaned_hints = [clean_html_text(h) for h in raw_hints if h]

    return {
        "id": question["questionFrontendId"],
        "title": question["title"],
        "difficulty": question["difficulty"],
        "url": f"https://leetcode.com{challenge['link']}",
        "tags": ", ".join(tags) if tags else "None",
        "primary_tag": tags[0] if tags else "Algorithms",
        "primary_tag_slug": tag_slugs[0] if tag_slugs else "algorithms",
        "ac_rate": round(question.get("acRate", 0), 1),
        "hints": cleaned_hints,
        "date": challenge["date"]
    }


async def fetch_bonus_practice_problems(
    session: aiohttp.ClientSession,
    topic_slug: str,
    topic_name: str,
    exclude_id: str = ""
) -> Dict[str, Any]:
    """
    Fetches a curated 4-problem practice set: 2 Easy, 1 Medium, 1 Hard
    matching the given topic tag, excluding paid-only problems and today's daily problem.
    """
    query = """
    query problemsetQuestionList($categorySlug: String, $limit: Int, $filters: QuestionListFilterInput) {
        problemsetQuestionList: questionList(categorySlug: $categorySlug, limit: $limit, filters: $filters) {
            questions: data {
                questionFrontendId
                title
                titleSlug
                difficulty
                acRate
                isPaidOnly
            }
        }
    }
    """

    async def _query_diff(slug: str, diff_str: str) -> List[Dict[str, Any]]:
        variables = {
            "categorySlug": "algorithms",
            "limit": 20,
            "filters": {"tags": [slug] if slug else [], "difficulty": diff_str}
        }
        for attempt in range(1, 4):
            try:
                async with session.post(
                    LEETCODE_URL,
                    json={"query": query, "variables": variables},
                    headers=HEADERS,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    resp.raise_for_status()
                    res = await resp.json()
                    raw_list = res.get("data", {}).get("problemsetQuestionList", {}).get("questions", [])
                    free = [
                        {
                            "id": q["questionFrontendId"],
                            "title": q["title"],
                            "url": f"https://leetcode.com/problems/{q['titleSlug']}/",
                            "difficulty": q["difficulty"],
                            "ac_rate": round(q.get("acRate", 0), 1)
                        }
                        for q in raw_list
                        if not q.get("isPaidOnly") and str(q.get("questionFrontendId")) != str(exclude_id)
                    ]
                    return free
            except Exception as e:
                if attempt < 3:
                    await asyncio.sleep(2 * attempt)
                else:
                    print(f"Error fetching practice diff {diff_str} after retries: {e}")
        return []

    # 1. Fetch candidates for Easy, Medium, Hard
    easy_candidates = await _query_diff(topic_slug, "EASY")
    if len(easy_candidates) < 2:
        fallback_easy = await _query_diff("", "EASY")
        for q in fallback_easy:
            if q not in easy_candidates and str(q["id"]) != str(exclude_id):
                easy_candidates.append(q)

    med_candidates = await _query_diff(topic_slug, "MEDIUM")
    if not med_candidates:
        fallback_med = await _query_diff("", "MEDIUM")
        for q in fallback_med:
            if str(q["id"]) != str(exclude_id):
                med_candidates.append(q)

    hard_candidates = await _query_diff(topic_slug, "HARD")
    if not hard_candidates:
        fallback_hard = await _query_diff("", "HARD")
        for q in fallback_hard:
            if str(q["id"]) != str(exclude_id):
                hard_candidates.append(q)

    # 2. Randomly sample 2 Easy, 1 Medium, 1 Hard
    selected_easy = random.sample(easy_candidates, min(2, len(easy_candidates))) if easy_candidates else []
    selected_medium = random.sample(med_candidates, min(1, len(med_candidates))) if med_candidates else []
    selected_hard = random.sample(hard_candidates, min(1, len(hard_candidates))) if hard_candidates else []

    return {
        "topic_name": topic_name,
        "easy": selected_easy,
        "medium": selected_medium,
        "hard": selected_hard
    }


def create_practice_embed(practice_data: Dict[str, Any]) -> discord.Embed:
    topic_name = practice_data.get("topic_name", "Algorithms")
    embed = discord.Embed(
        title=f"🎯 Bonus Practice Track: {topic_name}",
        description=(
            f"Conquered today's challenge? Level up your **{topic_name}** skills "
            f"with today's 4 curated practice problems:"
        ),
        color=discord.Color.teal(),
        timestamp=datetime.now(timezone.utc)
    )

    easy_problems = practice_data.get("easy", [])
    if easy_problems:
        lines = [
            f"• [#{p['id']}. {p['title']}]({p['url']}) — 📊 `{p['ac_rate']}%`"
            for p in easy_problems
        ]
        embed.add_field(name="🟢 Easy (2 Challenges)", value="\n".join(lines), inline=False)

    med_problems = practice_data.get("medium", [])
    if med_problems:
        lines = [
            f"• [#{p['id']}. {p['title']}]({p['url']}) — 📊 `{p['ac_rate']}%`"
            for p in med_problems
        ]
        embed.add_field(name="🟡 Medium (1 Challenge)", value="\n".join(lines), inline=False)

    hard_problems = practice_data.get("hard", [])
    if hard_problems:
        lines = [
            f"• [#{p['id']}. {p['title']}]({p['url']}) — 📊 `{p['ac_rate']}%`"
            for p in hard_problems
        ]
        embed.add_field(name="🔴 Hard (1 Challenge)", value="\n".join(lines), inline=False)

    embed.set_footer(text="Solve at your own pace! Consistency is the path to mastery.")
    return embed


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

    embed.set_footer(text="Click 'Mark Solved ✅' below or use /solved to track your streak privately!")
    return embed
