import os
import random
from datetime import datetime, timezone
import discord
from discord.ext import commands
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

CHANNEL_ID = 1550577189467197511
LEETCODE_URL = "https://leetcode.com/graphql"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
scheduler = AsyncIOScheduler()

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
    "Write code as if the person maintaining it is a violent psychopath who knows where you live.",
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
    "Think outside the box, but keep your time complexity inside $O(n \\log n)$.",
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

def fetch_leetcode_daily():
    query = """
    query questionOfToday {
        activeDailyCodingChallengeQuestion {
            date
            link
            question {
                questionFrontendId
                title
                difficulty
                topicTags {
                    name
                }
            }
        }
    }
    """
    response = requests.post(LEETCODE_URL, json={"query": query}, timeout=10)
    response.raise_for_status()
    data = response.json()
    challenge = data["data"]["activeDailyCodingChallengeQuestion"]

    question = challenge["question"]
    tags = [t["name"] for t in question["topicTags"]]

    return {
        "id": question["questionFrontendId"],
        "title": question["title"],
        "difficulty": question["difficulty"],
        "url": f"https://leetcode.com{challenge['link']}",
        "tags": ", ".join(tags) if tags else "None",
        "date": challenge["date"]
    }

def create_problem_embed(problem: dict) -> discord.Embed:
    colors = {
        "Easy": discord.Color.green(),
        "Medium": discord.Color.gold(),
        "Hard": discord.Color.red()
    }
    color = colors.get(problem["difficulty"], discord.Color.blue())

    embed = discord.Embed(
        title=f"LeetCode Daily: {problem['id']}. {problem['title']}",
        url=problem["url"],
        description="Today's problem is ready! Grab a coffee and solve it together.",
        color=color,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="Difficulty", value=problem["difficulty"], inline=True)
    embed.add_field(name="Date", value=problem["date"], inline=True)
    embed.add_field(name="Topics", value=problem["tags"], inline=False)
    embed.set_footer(text="Keep the streak going!")
    return embed

async def send_daily_problem():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print(f"Error: Channel {CHANNEL_ID} not found.")
        return
    try:
        problem = fetch_leetcode_daily()
        embed = create_problem_embed(problem)
        quote = random.choice(MOTIVATIONAL_QUOTES)
        
        message_content = f"@everyone 🚀 **Daily LeetCode Challenge is Live!**\n> *\"{quote}\"*"
        await channel.send(content=message_content, embed=embed)
        print("Daily problem successfully posted to Discord.")
    except Exception as e:
        print(f"Failed to send problem: {e}")
        await channel.send(f"⚠️ Failed to fetch today's problem: {e}")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    
    if not scheduler.running:
        # Scheduled every day at 1:00 PM IST (13:00)
        scheduler.add_job(send_daily_problem, 'cron', hour=13, minute=0, timezone='Asia/Kolkata')
        scheduler.start()
        print("Scheduler active: Configured for daily 1:00 PM IST posts.")

@bot.event
async def on_message(message):
    if not message.author.bot:
        print(f"Message from {message.author} in #{message.channel}: '{message.content}'")
    await bot.process_commands(message)

@bot.command(name="daily")
async def manual_daily(ctx):
    print("Manual command '!daily' triggered.")
    try:
        problem = fetch_leetcode_daily()
        embed = create_problem_embed(problem)
        quote = random.choice(MOTIVATIONAL_QUOTES)
        await ctx.send(content=f"> *\"{quote}\"*", embed=embed)
    except Exception as e:
        print(f"Error handling !daily: {e}")
        await ctx.send(f"⚠️ Error: {e}")

@bot.event
async def on_command_error(ctx, error):
    print(f"Command Error: {error}")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not found. Ensure it is set in your environment variables or .env file.")
    else:
        bot.run(DISCORD_TOKEN)