import os
import random
from datetime import datetime
from typing import Optional, List, Dict, Any

import pytz
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from database import (
    init_db,
    record_completion,
    get_user_stats,
    get_top_streaks,
    get_today_completions,
    save_daily_post,
    get_daily_post_date,
    add_participant,
    remove_participant,
    get_active_participants,
    get_challenge_status,
    is_announcement_posted_today,
    get_cached_bonus_problems,
    save_cached_bonus_problems
)
from leetcode import (
    fetch_leetcode_daily,
    create_problem_embed,
    get_random_quote,
    fetch_bonus_practice_problems,
    create_practice_embed
)

# Load environment configuration
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "1550577189467197511"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")

# Schedules in IST
MORNING_HOUR = int(os.getenv("MORNING_HOUR", "8"))
MORNING_MINUTE = int(os.getenv("MORNING_MINUTE", "0"))
AFTERNOON_HOUR = int(os.getenv("AFTERNOON_HOUR", "13"))
AFTERNOON_MINUTE = int(os.getenv("AFTERNOON_MINUTE", "0"))
EVENING_HOUR = int(os.getenv("EVENING_HOUR", "20"))
EVENING_MINUTE = int(os.getenv("EVENING_MINUTE", "30"))

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True


class LeetCodeBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=["!", "\\"], intents=intents, help_command=None)
        self.scheduler = AsyncIOScheduler()
        self.session: Optional[aiohttp.ClientSession] = None

    async def setup_hook(self):
        # 1. Initialize persistent SQLite database & seed participants
        init_db()
        print("SQLite Database initialized with active participants.")

        # 2. Shared aiohttp ClientSession
        self.session = aiohttp.ClientSession()

        # 3. Schedule cron jobs
        tz = pytz.timezone(TIMEZONE)

        # 8:00 AM IST - Morning announcement
        self.scheduler.add_job(
            send_morning_announcement_job,
            "cron",
            hour=MORNING_HOUR,
            minute=MORNING_MINUTE,
            timezone=tz
        )
        print(f"Scheduled 8:00 AM challenge post at {MORNING_HOUR:02d}:{MORNING_MINUTE:02d} {TIMEZONE}.")

        # 1:00 PM IST - Midday check-in (pings only pending participants)
        self.scheduler.add_job(
            send_afternoon_checkin_job,
            "cron",
            hour=AFTERNOON_HOUR,
            minute=AFTERNOON_MINUTE,
            timezone=tz
        )
        print(f"Scheduled 1:00 PM check-in at {AFTERNOON_HOUR:02d}:{AFTERNOON_MINUTE:02d} {TIMEZONE}.")

        # 8:30 PM IST - Evening check-in (pings only pending participants)
        self.scheduler.add_job(
            send_evening_checkin_job,
            "cron",
            hour=EVENING_HOUR,
            minute=EVENING_MINUTE,
            timezone=tz
        )
        print(f"Scheduled 8:30 PM evening reminder at {EVENING_HOUR:02d}:{EVENING_MINUTE:02d} {TIMEZONE}.")

        self.scheduler.start()

        # 4. Sync Application Slash Commands
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} application slash commands with Discord.")
        except Exception as e:
            print(f"Warning: Failed to sync slash commands: {e}")

    async def close(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
        if self.session and not self.session.closed:
            await self.session.close()
        await super().close()


bot = LeetCodeBot()


def get_current_date_str() -> str:
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz).strftime("%Y-%m-%d")


def build_participant_pings(participants: List[Dict[str, Any]]) -> str:
    """Builds Discord mention tags for a list of participant dictionaries."""
    return " ".join([f"<@{p['user_id']}>" for p in participants])


async def get_or_fetch_bonus_problems(problem: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves cached 4-problem bonus set or fetches and caches it if not yet generated."""
    date_str = problem.get("date", get_current_date_str())
    cached = get_cached_bonus_problems(date_str)
    if cached:
        return cached

    primary_slug = problem.get("primary_tag_slug", "algorithms")
    primary_name = problem.get("primary_tag", "Algorithms")
    exclude_id = problem.get("id", "")

    practice_data = await fetch_bonus_practice_problems(
        bot.session,
        primary_slug,
        primary_name,
        exclude_id=exclude_id
    )
    save_cached_bonus_problems(date_str, primary_name, practice_data)
    return practice_data


# ==========================================
# SCHEDULED JOBS
# ==========================================

async def send_morning_announcement_job():
    """8:00 AM IST: Posts the daily problem and pings all active participants."""
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print(f"Error: Channel {CHANNEL_ID} not found.")
        return
    try:
        today_date = get_current_date_str()
        if is_announcement_posted_today(today_date):
            print(f"8:00 AM scheduled post skipped: daily challenge for {today_date} was already announced earlier.")
            return

        problem = await fetch_leetcode_daily(bot.session)
        embed = create_problem_embed(problem)
        quote = get_random_quote()

        active = get_active_participants()
        pings = build_participant_pings(active) if active else ""

        message_content = f"{pings} 🚀 **Daily LeetCode Challenge is Live!**\n> *\"{quote}\"*"
        msg = await channel.send(content=message_content, embed=embed)
        await msg.add_reaction("✅")

        # Save to database with post_type='announcement'
        save_daily_post(problem["date"], msg.id, channel.id, post_type="announcement")
        print(f"8:00 AM Daily challenge '{problem['title']}' posted (msg_id: {msg.id}).")
    except Exception as e:
        print(f"Failed to post 8:00 AM daily problem: {e}")
        await channel.send(f"⚠️ Failed to fetch today's problem: {e}")


async def send_afternoon_checkin_job():
    """1:00 PM IST: Checks who completed, pings pending members, and tags completed solvers with bonus practice problems."""
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return
    try:
        today_date = get_current_date_str()
        status = get_challenge_status(today_date)
        completed = status["completed"]
        pending = status["pending"]

        problem = await fetch_leetcode_daily(bot.session)
        practice_data = await get_or_fetch_bonus_problems(problem)
        practice_embed = create_practice_embed(practice_data)

        # Case 1: 100% Completed
        if not pending:
            completed_pings = build_participant_pings(completed)
            embed = discord.Embed(
                title="🎉 1:00 PM Check-In: All Done!",
                description=(
                    f"Incredible! All participants have already completed today's problem: "
                    f"**[{problem['title']}]({problem['url']})**! 🚀\n\n"
                    f"No pending reminders needed. Enjoy your bonus practice challenges below!"
                ),
                color=discord.Color.green()
            )
            content = f"{completed_pings} 🌟 **100% Completed!** All participants conquered today's challenge!"
            await channel.send(content=content, embeds=[embed, practice_embed])
            print(f"1:00 PM check-in: 100% completed ({len(completed)} solvers).")
            return

        # Case 2: Mixed or Pending
        pending_pings = build_participant_pings(pending)
        embed = discord.Embed(
            title="⏰ 1:00 PM Midday Check-In",
            description=(
                f"Today's problem: **[{problem['title']}]({problem['url']})** ({problem['difficulty']})\n\n"
                f"Half the day has passed! Don't let your streak slip away."
            ),
            color=discord.Color.gold()
        )

        if completed:
            completed_names = ", ".join([f"`{c['username']}`" for c in completed])
            embed.add_field(name="Completed Already 🏅 (Safe from pings)", value=completed_names, inline=False)

        pending_names = ", ".join([f"`{p['username']}`" for p in pending])
        embed.add_field(name="Still Pending ⏳", value=pending_names, inline=False)
        embed.set_footer(text="React with ✅ on this post or use /solved to continue your streak and prevent 8:30 PM pings!")

        if completed:
            completed_pings = build_participant_pings(completed)
            content = (
                f"{pending_pings} ⏰ **1:00 PM Check-In!** Today's LeetCode challenge is waiting for you.\n\n"
                f"{completed_pings} 🎯 **Next Level Practice:** You already conquered today's challenge! "
                f"Level up with today's 4 bonus challenges below:"
            )
            embeds = [embed, practice_embed]
        else:
            content = f"{pending_pings} ⏰ **1:00 PM Check-In!** Today's LeetCode challenge is waiting for you."
            embeds = [embed]

        msg = await channel.send(content=content, embeds=embeds)
        await msg.add_reaction("✅")
        save_daily_post(today_date, msg.id, channel.id, post_type="checkin")
        print(f"1:00 PM check-in posted: {len(pending)} pending, {len(completed)} completed (msg_id: {msg.id}).")
    except Exception as e:
        print(f"Failed to send 1:00 PM check-in: {e}")


async def send_evening_checkin_job():
    """8:30 PM IST: Evening reminder pinging remaining pending members and tagging completed solvers."""
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return
    try:
        today_date = get_current_date_str()
        status = get_challenge_status(today_date)
        completed = status["completed"]
        pending = status["pending"]

        problem = await fetch_leetcode_daily(bot.session)
        practice_data = await get_or_fetch_bonus_problems(problem)
        practice_embed = create_practice_embed(practice_data)

        # Case 1: 100% Completed
        if not pending:
            completed_pings = build_participant_pings(completed)
            embed = discord.Embed(
                title="🌟 8:30 PM Final Check-In: 100% Completed!",
                description=(
                    f"Every participant conquered today's challenge: "
                    f"**[{problem['title']}]({problem['url']})**!\n\n"
                    f"All streaks are safe and accounted for. Great job team! 🔥"
                ),
                color=discord.Color.green()
            )
            content = f"{completed_pings} 🌟 **100% Completed!** Every participant kept their streak intact today!"
            await channel.send(content=content, embeds=[embed, practice_embed])
            print("8:30 PM check-in: 100% completed.")
            return

        # Case 2: Mixed or Pending
        pending_pings = build_participant_pings(pending)
        embed = discord.Embed(
            title="🌙 8:30 PM Evening Reminder — Reset Approaching!",
            description=(
                f"**[{problem['title']}]({problem['url']})** ({problem['difficulty']})\n\n"
                f"Only ~3.5 hours remaining before midnight! Take 20 minutes to solve it and keep your streak alive! 💪"
            ),
            color=discord.Color.red()
        )

        if completed:
            completed_names = ", ".join([f"`{c['username']}`" for c in completed])
            embed.add_field(name="Completed 🏅", value=completed_names, inline=False)

        pending_names = ", ".join([f"`{p['username']}`" for p in pending])
        embed.add_field(name="Action Required ⚠️", value=pending_names, inline=False)
        embed.set_footer(text="React with ✅ on this post or run /solved now to save your streak!")

        if completed:
            completed_pings = build_participant_pings(completed)
            content = (
                f"{pending_pings} 🌙 **8:30 PM Reminder!** Keep your daily streak alive before the reset!\n\n"
                f"{completed_pings} 🎯 **Bonus Practice:** High-five for finishing today's challenge! "
                f"Check out today's bonus problem track below:"
            )
            embeds = [embed, practice_embed]
        else:
            content = f"{pending_pings} 🌙 **8:30 PM Reminder!** Keep your daily streak alive before the reset!"
            embeds = [embed]

        msg = await channel.send(content=content, embeds=embeds)
        await msg.add_reaction("✅")
        save_daily_post(today_date, msg.id, channel.id, post_type="checkin")
        print(f"8:30 PM reminder posted: {len(pending)} pending, {len(completed)} completed (msg_id: {msg.id}).")
    except Exception as e:
        print(f"Failed to send 8:30 PM reminder: {e}")


# ==========================================
# DISCORD EVENTS
# ==========================================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    # Ignore reactions from the bot itself
    if payload.user_id == bot.user.id:
        return

    # Check if the reaction is the completion checkmark
    if str(payload.emoji) != "✅":
        return

    # Check if the reacted message is a daily announcement
    challenge_date = get_daily_post_date(payload.message_id)
    if not challenge_date:
        return

    # Resolve member/username
    guild = bot.get_guild(payload.guild_id) if payload.guild_id else None
    member = payload.member
    if not member and guild:
        member = guild.get_member(payload.user_id)
    username = member.display_name if member else f"User-{payload.user_id}"

    result = record_completion(payload.user_id, username, challenge_date)

    channel = bot.get_channel(payload.channel_id)
    if channel:
        if result["success"]:
            try:
                problem = await fetch_leetcode_daily(bot.session)
                practice_data = await get_or_fetch_bonus_problems(problem)
                practice_embed = create_practice_embed(practice_data)
                await channel.send(
                    f"🔥 **{username}** completed challenge `{challenge_date}`! Current streak: **{result['current_streak']} days**! 🎉\n"
                    f"Here is your personal 4-problem practice set on **{practice_data['topic_name']}** to keep grinding:",
                    embed=practice_embed,
                    delete_after=180
                )
            except Exception as e:
                print(f"Error sending reaction practice set: {e}")
                await channel.send(
                    f"🔥 **{username}** completed challenge `{challenge_date}`! Current streak: **{result['current_streak']} days**! 🎉",
                    delete_after=20
                )


# ==========================================
# MANUAL TRIGGER LOGIC
# ==========================================

async def execute_trigger(
    channel: discord.TextChannel,
    invoker_mention: str,
    interaction: Optional[discord.Interaction] = None
) -> None:
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today_date = now.strftime("%Y-%m-%d")
    now_minutes = now.hour * 60 + now.minute

    # 1. Before 5:30 AM IST (330 minutes)
    if now_minutes < 330:
        msg = (
            "⏳ Today's new LeetCode daily problem resets at **5:30 AM IST** (00:00 UTC).\n"
            "Please use `/trigger` after 5:30 AM IST to fetch today's brand-new problem!"
        )
        if interaction:
            await interaction.followup.send(msg)
        else:
            await channel.send(msg)
        return

    already_announced = is_announcement_posted_today(today_date)

    # 2. Before 8:00 AM IST (480 minutes) and NOT yet announced today:
    # Post the official announcement early and mark it so 8:00 AM scheduled post skips!
    if now_minutes < 480 and not already_announced:
        problem = await fetch_leetcode_daily(bot.session)
        embed = create_problem_embed(problem)
        quote = get_random_quote()

        active = get_active_participants()
        pings = build_participant_pings(active) if active else ""

        message_content = (
            f"{pings} 🚀 **Daily LeetCode Challenge is Live!** (Triggered early by {invoker_mention})\n"
            f"> *\"{quote}\"*"
        )
        msg = await channel.send(content=message_content, embed=embed)
        await msg.add_reaction("✅")
        save_daily_post(problem["date"], msg.id, channel.id, post_type="announcement")

        if interaction:
            await interaction.followup.send(
                "✅ Posted today's challenge announcement early! The 8:00 AM scheduled post will be automatically skipped.",
                ephemeral=True
            )
        print(f"Manual trigger posted announcement for {today_date} early (msg_id: {msg.id}).")
        return

    # 3. Post-Announcement Trigger (after 8:00 AM IST or if already announced):
    # Runs an on-demand check-in: pings ONLY members who have NOT completed today's problem!
    status = get_challenge_status(today_date)
    completed = status["completed"]
    pending = status["pending"]
    problem = await fetch_leetcode_daily(bot.session)
    practice_data = await get_or_fetch_bonus_problems(problem)
    practice_embed = create_practice_embed(practice_data)

    if not pending:
        completed_pings = build_participant_pings(completed)
        embed = discord.Embed(
            title="🌟 On-Demand Status: 100% Completed!",
            description=(
                f"Triggered by {invoker_mention}.\n\n"
                f"All active participants have completed today's challenge: "
                f"**[{problem['title']}]({problem['url']})**! 🚀\n\n"
                f"Zero pings needed. Everyone's streak is intact! 🔥"
            ),
            color=discord.Color.green()
        )
        content = f"{completed_pings} 🌟 **100% Completed!** Here is today's bonus practice track:"
        if interaction:
            await interaction.followup.send(content=content, embeds=[embed, practice_embed])
        else:
            await channel.send(content=content, embeds=[embed, practice_embed])
        return

    pending_pings = build_participant_pings(pending)
    embed = discord.Embed(
        title="⏰ LeetCode Check-In (On-Demand)",
        description=(
            f"Triggered by {invoker_mention}.\n\n"
            f"Today's problem: **[{problem['title']}]({problem['url']})** ({problem['difficulty']})\n"
            f"Here is the live completion status:"
        ),
        color=discord.Color.gold()
    )

    if completed:
        completed_names = ", ".join([f"`{c['username']}`" for c in completed])
        embed.add_field(name="Completed Already 🏅 (Safe from pings)", value=completed_names, inline=False)

    pending_names = ", ".join([f"`{p['username']}`" for p in pending])
    embed.add_field(name="Still Pending ⏳", value=pending_names, inline=False)
    embed.set_footer(text="React with ✅ on this post or use /solved to continue your streak and prevent reminders!")

    if completed:
        completed_pings = build_participant_pings(completed)
        content = (
            f"{pending_pings} ⏰ **LeetCode Check-In!** Today's problem is still waiting for you.\n\n"
            f"{completed_pings} 🎯 **Next Level Practice:** You already conquered today's challenge! "
            f"Try today's 4 bonus challenges below:"
        )
        embeds = [embed, practice_embed]
    else:
        content = f"{pending_pings} ⏰ **LeetCode Check-In!** Today's problem is still waiting for you."
        embeds = [embed]

    msg = await channel.send(content=content, embeds=embeds)
    await msg.add_reaction("✅")
    save_daily_post(today_date, msg.id, channel.id, post_type="checkin")

    if interaction:
        await interaction.followup.send("✅ Check-in dispatched! Pinged pending members and tagged completed solvers.", ephemeral=True)
    print(f"On-demand check-in trigger dispatched: {len(pending)} pending, {len(completed)} completed.")


# ==========================================
# SLASH COMMANDS
# ==========================================

def build_help_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🚀 LeetCode Daily Bot — Guide & Help",
        description=(
            "Welcome! This bot manages daily LeetCode challenges, provides spoiler-safe hints, "
            "and automatically tracks your streaks while respecting your time with smart check-in pings.\n"
        ),
        color=discord.Color.from_rgb(255, 161, 22)
    )

    embed.add_field(
        name="⏰ Daily Automated Schedule (IST)",
        value=(
            f"• **8:00 AM** (`{MORNING_HOUR:02d}:{MORNING_MINUTE:02d}`) — Daily challenge announcement (pings active participants)\n"
            f"• **1:00 PM** (`{AFTERNOON_HOUR:02d}:{AFTERNOON_MINUTE:02d}`) — Midday check-in (**only pings members who haven't completed**)\n"
            f"• **8:30 PM** (`{EVENING_HOUR:02d}:{EVENING_MINUTE:02d}`) — Evening reminder (**only pings members who haven't completed**)"
        ),
        inline=False
    )

    embed.add_field(
        name="🔥 How Streak Tracking & Smart Pings Work",
        value=(
            "1. **Any Post Reaction**: Click the **✅** reaction on **any** post (8:00 AM announcement, 1:00 PM check-in, or 8:30 PM reminder) OR run `/solved` to continue your streak!\n"
            "2. **Cascading Smart Exemptions**:\n"
            "   • Solve before 1:00 PM ➔ **Zero pings** at 1:00 PM & 8:30 PM.\n"
            "   • Solve at or after 1:00 PM ➔ **Zero pings** at 8:30 PM.\n"
            "   • Only members who still haven't solved get pinged in reminders!\n"
            "3. **Automatic Participation**: Reacting ✅ on any post or using `/solved` automatically enrolls you as an active participant."
        ),
        inline=False
    )

    embed.add_field(
        name="⚡ Available Commands",
        value=(
            "• `/daily` — View today's active challenge & stats\n"
            "• `/practice` — View today's 4 similar practice problems (2 Easy, 1 Medium, 1 Hard)\n"
            "• `/trigger` — Smart trigger: posts challenge early (5:30–8:00 AM, skips 8 AM cron) OR on-demand check-in pinging only pending members (after 8 AM)\n"
            "• `/hint [num]` — Reveal progressive hints privately with spoiler tags (`||hint||`)\n"
            "• `/solved` — Mark today's challenge as solved & update streak\n"
            "• `/streak [@user]` — View personal or another member's streak stats\n"
            "• `/leaderboard` — View the top streak leaders in the server\n"
            "• `/participants` — View currently enrolled active participants\n"
            "• `/join` / `/leave` — Enroll into or opt out of daily challenge pings\n"
            "• `/help` — Display this guide\n"
            "• `/ping` — Check bot response latency"
        ),
        inline=False
    )

    embed.set_footer(text="Consistency beats talent. Keep your streak alive!")
    return embed


@bot.tree.command(name="trigger", description="Post daily challenge early (before 8 AM) or run on-demand check-in (after 8 AM)")
async def slash_trigger(interaction: discord.Interaction):
    await interaction.response.defer()
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        channel = bot.get_channel(CHANNEL_ID)
    await execute_trigger(channel, interaction.user.mention, interaction=interaction)


@bot.tree.command(name="daily", description="Fetch today's active LeetCode daily challenge")
async def slash_daily(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        problem = await fetch_leetcode_daily(bot.session)
        embed = create_problem_embed(problem)
        quote = get_random_quote()
        await interaction.followup.send(content=f"> *\"{quote}\"*", embed=embed)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Error fetching today's daily problem: {e}", ephemeral=True)


@bot.tree.command(name="practice", description="View today's curated 4 similar practice problems (2 Easy, 1 Medium, 1 Hard)")
async def slash_practice(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        problem = await fetch_leetcode_daily(bot.session)
        practice_data = await get_or_fetch_bonus_problems(problem)
        embed = create_practice_embed(practice_data)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Error fetching practice problems: {e}", ephemeral=True)


@bot.tree.command(name="hint", description="Reveal a spoiler-safe hint for today's challenge")
@app_commands.describe(number="Which hint number to view (e.g. 1, 2)")
async def slash_hint(interaction: discord.Interaction, number: Optional[int] = 1):
    await interaction.response.defer(ephemeral=True)
    try:
        problem = await fetch_leetcode_daily(bot.session)
        hints = problem.get("hints", [])

        if not hints:
            await interaction.followup.send(f"💡 No hints are available for **{problem['title']}**.", ephemeral=True)
            return

        hint_idx = (number or 1) - 1
        if hint_idx < 0 or hint_idx >= len(hints):
            await interaction.followup.send(
                f"⚠️ Invalid hint number. **{problem['title']}** has {len(hints)} hint(s) available (1 to {len(hints)}).",
                ephemeral=True
            )
            return

        hint_content = hints[hint_idx]
        msg = (
            f"💡 **Hint {hint_idx + 1}/{len(hints)} for {problem['title']}**:\n"
            f"||{hint_content}||\n\n"
            f"*(Click the black spoiler box above to reveal)*"
        )
        await interaction.followup.send(msg, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Error fetching hint: {e}", ephemeral=True)


@bot.tree.command(name="solved", description="Mark today's LeetCode daily challenge as solved and update your streak")
async def slash_solved(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        today_date = get_current_date_str()
        username = interaction.user.display_name
        res = record_completion(interaction.user.id, username, today_date)

        problem = await fetch_leetcode_daily(bot.session)
        practice_data = await get_or_fetch_bonus_problems(problem)
        practice_embed = create_practice_embed(practice_data)

        if not res["success"] and res.get("reason") == "already_solved":
            embed = discord.Embed(
                title="Already Logged! 🎯",
                description=(
                    f"You have already marked today's challenge (`{today_date}`) as completed!\n"
                    f"You are safe from the 1:00 PM and 8:30 PM reminder pings.\n\n"
                    f"🔥 Current Streak: **{res['current_streak']} days**\n"
                    f"🏆 Best Streak: **{res['highest_streak']} days**\n"
                    f"📚 Total Solved: **{res['total_solved']} problems**"
                ),
                color=discord.Color.blue()
            )
            embed.set_footer(text="Here is today's bonus practice track:")
            await interaction.followup.send(embeds=[embed, practice_embed])
            return

        embed = discord.Embed(
            title="Challenge Completed! 🏆",
            description=(
                f"Congratulations {interaction.user.mention}! Your submission for `{today_date}` has been logged.\n"
                f"You will **not** be pinged in today's check-ins.\n\n"
                f"🔥 Current Streak: **{res['current_streak']} days**\n"
                f"🏆 Best Streak: **{res['highest_streak']} days**\n"
                f"📚 Total Solved: **{res['total_solved']} problems**"
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text="Keep the momentum going! Here is your 4-problem bonus practice track:")
        await interaction.followup.send(embeds=[embed, practice_embed])
    except Exception as e:
        await interaction.followup.send(f"⚠️ Error logging completion: {e}", ephemeral=True)


@bot.tree.command(name="streak", description="Check your or another member's LeetCode streak and stats")
@app_commands.describe(member="Member to view streak for (defaults to yourself)")
async def slash_streak(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    target = member or interaction.user
    stats = get_user_stats(target.id)

    if not stats:
        msg = f"ℹ️ **{target.display_name}** has not recorded any solved problems yet! Use `/solved` to begin."
        await interaction.response.send_message(msg, ephemeral=True)
        return

    embed = discord.Embed(
        title=f"📊 LeetCode Stats: {target.display_name}",
        color=discord.Color.purple()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Current Streak", value=f"🔥 **{stats['current_streak']} days**", inline=True)
    embed.add_field(name="Highest Streak", value=f"🏆 **{stats['highest_streak']} days**", inline=True)
    embed.add_field(name="Total Solved", value=f"📚 **{stats['total_solved']} problems**", inline=True)
    embed.add_field(name="Last Solved Date", value=f"📅 `{stats['last_solved_date']}`", inline=False)
    embed.set_footer(text="Consistency is key to mastery!")

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="leaderboard", description="Display the top LeetCode streak leaders in the server")
async def slash_leaderboard(interaction: discord.Interaction):
    leaders = get_top_streaks(limit=10)

    if not leaders:
        await interaction.response.send_message("ℹ️ No streaks recorded yet! Be the first by using `/solved`.", ephemeral=True)
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for idx, user in enumerate(leaders):
        rank_icon = medals[idx] if idx < 3 else f"`#{idx + 1}`"
        lines.append(
            f"{rank_icon} **{user['username']}** — 🔥 **{user['current_streak']} days** (Best: {user['highest_streak']} | Total: {user['total_solved']})"
        )

    embed = discord.Embed(
        title="🏆 LeetCode Streak Leaderboard",
        description="\n".join(lines),
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    embed.set_footer(text="Solve daily to climb the leaderboard!")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="participants", description="View active members participating in daily challenges")
async def slash_participants(interaction: discord.Interaction):
    active = get_active_participants()
    if not active:
        await interaction.response.send_message("ℹ️ No active participants currently registered. Use `/join` to participate!", ephemeral=True)
        return

    today_date = get_current_date_str()
    status = get_challenge_status(today_date)
    completed_ids = {c["user_id"] for c in status["completed"]}

    lines = []
    for p in active:
        done_badge = "✅ Solved" if p["user_id"] in completed_ids else "⏳ Pending"
        lines.append(f"• **{p['username']}** ({done_badge})")

    embed = discord.Embed(
        title=f"👥 Active LeetCode Participants ({len(active)})",
        description="\n".join(lines),
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Status for challenge date: {today_date}")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="join", description="Enroll into daily LeetCode challenge announcements and reminders")
async def slash_join(interaction: discord.Interaction):
    username = interaction.user.display_name
    add_participant(interaction.user.id, username)
    await interaction.response.send_message(
        f"🚀 **{interaction.user.mention}**, you are now enrolled as an active participant! You'll receive daily challenges and smart streak reminders.",
        ephemeral=False
    )


@bot.tree.command(name="leave", description="Opt out of daily LeetCode challenge announcements and reminders")
async def slash_leave(interaction: discord.Interaction):
    remove_participant(interaction.user.id)
    await interaction.response.send_message(
        f"👋 You have been removed from daily reminder pings. You can rejoin anytime with `/join`.",
        ephemeral=True
    )


@bot.tree.command(name="help", description="Learn how to use the LeetCode Daily Bot and track streaks")
async def slash_help(interaction: discord.Interaction):
    embed = build_help_embed()
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="ping", description="Check bot latency and status")
async def slash_ping(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latency: **{latency_ms}ms**", ephemeral=True)


# ==========================================
# BACKWARD COMPATIBLE PREFIX COMMANDS
# ==========================================

@bot.command(name="help")
async def prefix_help(ctx):
    embed = build_help_embed()
    await ctx.send(embed=embed)


@bot.command(name="daily")
async def prefix_daily(ctx):
    try:
        problem = await fetch_leetcode_daily(bot.session)
        embed = create_problem_embed(problem)
        quote = get_random_quote()
        await ctx.send(content=f"> *\"{quote}\"*", embed=embed)
    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")


@bot.command(name="solved")
async def prefix_solved(ctx):
    today_date = get_current_date_str()
    res = record_completion(ctx.author.id, ctx.author.display_name, today_date)
    if not res["success"] and res.get("reason") == "already_solved":
        await ctx.send(f"🎯 {ctx.author.mention}, you already logged today's challenge! Streak: **{res['current_streak']} days**")
    else:
        await ctx.send(f"🏆 {ctx.author.mention} solved today's challenge! Streak: 🔥 **{res['current_streak']} days** (Total: {res['total_solved']})")


@bot.command(name="streak")
async def prefix_streak(ctx, member: Optional[discord.Member] = None):
    target = member or ctx.author
    stats = get_user_stats(target.id)
    if not stats:
        await ctx.send(f"ℹ️ {target.display_name} hasn't logged any solutions yet!")
        return
    await ctx.send(
        f"📊 **{target.display_name}**: Streak: 🔥 **{stats['current_streak']} days** | Best: 🏆 **{stats['highest_streak']}** | Total: 📚 **{stats['total_solved']}**"
    )


@bot.command(name="leaderboard")
async def prefix_leaderboard(ctx):
    leaders = get_top_streaks(limit=10)
    if not leaders:
        await ctx.send("ℹ️ No streaks recorded yet!")
        return
    lines = [f"{idx + 1}. **{u['username']}**: 🔥 {u['current_streak']} days (Total: {u['total_solved']})" for idx, u in enumerate(leaders)]
    await ctx.send("**🏆 LeetCode Streak Leaderboard:**\n" + "\n".join(lines))


@bot.command(name="participants")
async def prefix_participants(ctx):
    active = get_active_participants()
    if not active:
        await ctx.send("ℹ️ No active participants currently registered.")
        return
    lines = [f"• **{p['username']}**" for p in active]
    await ctx.send(f"**👥 Active LeetCode Participants ({len(active)}):**\n" + "\n".join(lines))


@bot.command(name="trigger")
async def prefix_trigger(ctx):
    channel = ctx.channel
    if not isinstance(channel, discord.TextChannel):
        channel = bot.get_channel(CHANNEL_ID)
    await execute_trigger(channel, ctx.author.mention)


@bot.command(name="practice")
async def prefix_practice(ctx):
    try:
        problem = await fetch_leetcode_daily(bot.session)
        practice_data = await get_or_fetch_bonus_problems(problem)
        embed = create_practice_embed(practice_data)
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not found. Please set it in your .env file.")
    else:
        bot.run(DISCORD_TOKEN)
