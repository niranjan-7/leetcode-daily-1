import os
import random
import asyncio
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
    save_cached_bonus_problems,
    prune_expired_inactive_participants
)
from leetcode import (
    fetch_leetcode_daily,
    create_problem_embed,
    fetch_bonus_practice_problems,
    create_practice_embed
)
from phrases import (
    get_morning_title,
    get_morning_quote,
    get_midday_title,
    get_midday_quote,
    get_evening_title,
    get_evening_quote,
    get_trigger_quote,
    get_solved_title,
    get_solved_subtitle,
    get_server_sweep_title,
    get_server_sweep_desc,
    get_sunday_champion_title,
    get_sunday_champion_desc,
    check_milestone
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
        super().__init__(command_prefix=["!", "\\", "/"], intents=intents, help_command=None)
        self.scheduler = AsyncIOScheduler()
        self.session: Optional[aiohttp.ClientSession] = None

    async def setup_hook(self):
        # 1. Initialize persistent SQLite database & seed participants
        init_db()
        print("SQLite Database initialized with active participants.")

        # 1b. Register persistent views
        self.add_view(SolvedButtonView())

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

        # Sunday 11:00 AM IST - Weekly Champion Spotlight
        self.scheduler.add_job(
            send_sunday_champion_job,
            "cron",
            day_of_week="sun",
            hour=11,
            minute=0,
            timezone=tz
        )
        print(f"Scheduled Sunday 11:00 AM weekly champion celebration.")

        # Daily 00:05 IST - Expired Inactive Participants Pruning (> 60 days)
        self.scheduler.add_job(
            prune_expired_participants_job,
            "cron",
            hour=0,
            minute=5,
            timezone=tz
        )
        print("Scheduled daily midnight pruning of inactive participants (>60 days).")

        # Watchdog: Every 15 minutes, catch up on missed morning announcement (e.g. if phone was asleep/offline at 8:00 AM)
        self.scheduler.add_job(
            check_and_recover_announcement_job,
            "interval",
            minutes=15,
            timezone=tz
        )
        print("Scheduled 15-minute announcement watchdog for auto-recovery.")

        self.scheduler.start()

        # 4. Sync Application Slash Commands (Global)
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} global application slash commands with Discord.")
        except Exception as e:
            print(f"Warning: Failed to sync global slash commands: {e}")

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


async def handle_solve_interaction(interaction: discord.Interaction):
    """Processes problem completion and returns a 100% ephemeral response ('Only you can see this')."""
    await interaction.response.defer(ephemeral=True)
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
            await interaction.followup.send(embeds=[embed, practice_embed], ephemeral=True)
            return

        title = get_solved_title()
        subtitle = get_solved_subtitle()
        embed = discord.Embed(
            title=title,
            description=(
                f"{subtitle}\n\n"
                f"Congratulations {interaction.user.mention}! Your submission for `{today_date}` has been logged.\n"
                f"You will **not** be pinged in today's check-ins.\n\n"
                f"🔥 Current Streak: **{res['current_streak']} days**\n"
                f"🏆 Best Streak: **{res['highest_streak']} days**\n"
                f"📚 Total Solved: **{res['total_solved']} problems**"
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text="Keep the momentum going! Here is your 4-problem bonus practice track:")
        await interaction.followup.send(embeds=[embed, practice_embed], ephemeral=True)

        # Check for milestone celebration (7, 28, 56, 30, 60, 90, 100, 180, 365 days...)
        milestone = res.get("milestone")
        if milestone:
            channel = interaction.channel
            if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                channel = bot.get_channel(CHANNEL_ID)
            if channel:
                badge = milestone.get("badge", "🎉")
                m_title = milestone.get("title", f"{res['current_streak']}-Day Streak Milestone!")
                m_desc = milestone.get("desc", "Incredible persistence and dedication!")
                milestone_embed = discord.Embed(
                    title=f"{badge} {m_title}",
                    description=(
                        f"Huge milestone reached! Let's celebrate {interaction.user.mention} for achieving "
                        f"an unbroken streak of **{res['current_streak']} days**! 🔥\n\n"
                        f"{m_desc}\n\n"
                        f"🏆 Highest Streak: **{res['highest_streak']} days** | 📚 Total Solved: **{res['total_solved']} problems**"
                    ),
                    color=discord.Color.gold(),
                    timestamp=datetime.now()
                )
                milestone_embed.set_footer(text="LeetCode Milestone Celebration • Keep the streak alive!")
                await channel.send(
                    content=f"🎉 **MILESTONE ALERT!** Shoutout to {interaction.user.mention} for hitting **{res['current_streak']} days**!",
                    embed=milestone_embed
                )
                print(f"Public milestone celebration posted for {username} ({res['current_streak']} days).")
    except Exception as e:
        await interaction.followup.send(f"⚠️ Error logging completion: {e}", ephemeral=True)


class SolvedButtonView(discord.ui.View):
    """Persistent button view allowing solvers to log completion ephemerally on any challenge or check-in card."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Mark Solved ✅",
        style=discord.ButtonStyle.success,
        custom_id="mark_solved_button_persistent"
    )
    async def on_mark_solved(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_solve_interaction(interaction)


# ==========================================
# SCHEDULED JOBS
# ==========================================

async def send_morning_announcement_job():
    """8:00 AM IST: Posts the daily problem and pings all active participants."""
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print(f"Error: Channel {CHANNEL_ID} not found.")
        return

    today_date = get_current_date_str()
    if is_announcement_posted_today(today_date):
        print(f"Daily challenge for {today_date} was already announced earlier.")
        return

    max_attempts = 10
    for attempt in range(1, max_attempts + 1):
        try:
            problem = await fetch_leetcode_daily(bot.session)
            embed = create_problem_embed(problem)
            title = get_morning_title()
            quote = get_morning_quote()

            active = get_active_participants()
            pings = build_participant_pings(active) if active else ""

            message_content = f"{pings} **{title}**\n> *\"{quote}\"*"
            msg = await channel.send(content=message_content, embed=embed, view=SolvedButtonView())

            # Save to database with post_type='announcement'
            save_daily_post(problem["date"], msg.id, channel.id, post_type="announcement")
            print(f"Daily challenge '{problem['title']}' posted successfully (msg_id: {msg.id}).")
            return
        except Exception as e:
            print(f"Attempt {attempt}/{max_attempts} to post 8:00 AM daily problem failed: {e}")
            if attempt < max_attempts:
                await asyncio.sleep(20)
            else:
                try:
                    await channel.send(f"⚠️ Failed to fetch today's problem after multiple attempts: {e}")
                except Exception:
                    pass


async def send_afternoon_checkin_job():
    """1:00 PM IST: Checks who completed, pings pending members, and tags completed solvers with bonus practice problems."""
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return
    try:
        today_date = get_current_date_str()
        if not is_announcement_posted_today(today_date):
            print(f"1:00 PM check-in detected missing announcement for {today_date}. Posting announcement first...")
            await send_morning_announcement_job()
            return

        status = get_challenge_status(today_date)
        completed = status["completed"]
        pending = status["pending"]

        problem = await fetch_leetcode_daily(bot.session)
        practice_data = await get_or_fetch_bonus_problems(problem)
        practice_embed = create_practice_embed(practice_data)

        # Case 1: 100% Completed
        if not pending:
            completed_pings = build_participant_pings(completed)
            sweep_title = get_server_sweep_title()
            sweep_desc = get_server_sweep_desc()
            embed = discord.Embed(
                title=sweep_title,
                description=(
                    f"{sweep_desc}\n\n"
                    f"Today's problem: **[{problem['title']}]({problem['url']})** 🚀\n"
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
        title = get_midday_title()
        quote = get_midday_quote()
        embed = discord.Embed(
            title=title,
            description=(
                f"Today's problem: **[{problem['title']}]({problem['url']})** ({problem['difficulty']})\n\n"
                f"> *\"{quote}\"*"
            ),
            color=discord.Color.gold()
        )

        if completed:
            completed_names = ", ".join([f"`{c['username']}`" for c in completed])
            embed.add_field(name="Completed Already 🏅 (Safe from pings)", value=completed_names, inline=False)

        pending_names = ", ".join([f"`{p['username']}`" for p in pending])
        embed.add_field(name="Still Pending ⏳", value=pending_names, inline=False)
        embed.set_footer(text="Click 'Mark Solved ✅' below or use /solved to continue your streak privately!")

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

        msg = await channel.send(content=content, embeds=embeds, view=SolvedButtonView())
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
            sweep_title = get_server_sweep_title()
            sweep_desc = get_server_sweep_desc()
            embed = discord.Embed(
                title=sweep_title,
                description=(
                    f"{sweep_desc}\n\n"
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
        title = get_evening_title()
        quote = get_evening_quote()
        embed = discord.Embed(
            title=title,
            description=(
                f"**[{problem['title']}]({problem['url']})** ({problem['difficulty']})\n\n"
                f"> *\"{quote}\"*"
            ),
            color=discord.Color.red()
        )

        if completed:
            completed_names = ", ".join([f"`{c['username']}`" for c in completed])
            embed.add_field(name="Completed 🏅", value=completed_names, inline=False)

        pending_names = ", ".join([f"`{p['username']}`" for p in pending])
        embed.add_field(name="Action Required ⚠️", value=pending_names, inline=False)
        embed.set_footer(text="Click 'Mark Solved ✅' below or use /solved now to save your streak privately!")

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

        msg = await channel.send(content=content, embeds=embeds, view=SolvedButtonView())
        save_daily_post(today_date, msg.id, channel.id, post_type="checkin")
        print(f"8:30 PM reminder posted: {len(pending)} pending, {len(completed)} completed (msg_id: {msg.id}).")
    except Exception as e:
        print(f"Failed to send 8:30 PM reminder: {e}")


async def send_sunday_champion_job():
    """Sunday 11:00 AM IST: Showcases and congratulates the #1 streak champion of the week."""
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return
    try:
        leaders = get_top_streaks(limit=1)
        if not leaders:
            return
        champion = leaders[0]
        streak = champion["current_streak"]
        if streak <= 0:
            return

        title = get_sunday_champion_title()
        desc_intro = get_sunday_champion_desc()

        embed = discord.Embed(
            title=title,
            description=(
                f"{desc_intro}\n\n"
                f"👑 **Weekly Champion:** **{champion['username']}**\n"
                f"🔥 Active Streak: **{champion['current_streak']} days**\n"
                f"🏆 Highest Recorded Streak: **{champion['highest_streak']} days**\n"
                f"📚 Lifetime Problems Solved: **{champion['total_solved']} problems**\n\n"
                f"Give it up for our algorithm champion! Can anyone dethrone them next week?"
            ),
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        embed.set_footer(text="Sunday Weekly Spotlight • LeetCode Daily Arena")
        content = f"🏆👑 **Sunday Algorithmic Champion Spotlight!** All hail **{champion['username']}**!"
        await channel.send(content=content, embed=embed)
        print(f"Sunday champion spotlight posted for {champion['username']} (streak: {streak}).")
    except Exception as e:
        print(f"Failed to post Sunday champion spotlight: {e}")


async def prune_expired_participants_job():
    """Daily midnight maintenance: permanently deletes data for members who left > 60 days ago."""
    try:
        pruned = prune_expired_inactive_participants(days=60)
        if pruned:
            pruned_names = ", ".join([p["username"] for p in pruned])
            print(f"Pruned {len(pruned)} expired participants (> 60 days inactive): {pruned_names}")
    except Exception as e:
        print(f"Error during expired participant pruning: {e}")


async def check_and_recover_announcement_job():
    """Watchdog: Checks between 8:00 AM and 1:00 PM if the announcement was missed due to network/downtime and posts it."""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    now_minutes = now.hour * 60 + now.minute
    # Between 8:00 AM and 1:00 PM (480 to 780 minutes)
    if 480 <= now_minutes < 780:
        today_date = now.strftime("%Y-%m-%d")
        if not is_announcement_posted_today(today_date):
            print(f"Watchdog triggered: Missed 8:00 AM post detected for {today_date}. Recovering now...")
            await send_morning_announcement_job()


# ==========================================
# DISCORD EVENTS
# ==========================================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    # Clear guild-level duplicate commands so Discord shows each command only once (from global sync)
    for guild in bot.guilds:
        try:
            bot.tree.clear_commands(guild=guild)
            await bot.tree.sync(guild=guild)
            print(f"Cleared guild-specific commands for '{guild.name}' ({guild.id}) to eliminate duplicate command listings.")
        except Exception as e:
            print(f"Warning clearing guild commands for '{guild.name}': {e}")

    # Startup catch-up: If it's past 8:00 AM and today's announcement wasn't posted yet (e.g. after restart or downtime)
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    now_minutes = now.hour * 60 + now.minute
    today_date = now.strftime("%Y-%m-%d")
    if now_minutes >= 480 and not is_announcement_posted_today(today_date):
        print(f"Startup catch-up: Daily announcement for {today_date} not posted yet. Posting now...")
        bot.loop.create_task(send_morning_announcement_job())


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Print incoming messages to PM2 logs for monitoring
    print(f"Message from {message.author} in #{message.channel}: {message.content!r}")

    # If the user typed a known command name directly without any prefix (e.g. "participants", "trigger", "daily")
    content_stripped = message.content.strip()
    first_word = content_stripped.lower().split()[0] if content_stripped else ""
    valid_commands = {
        "participants", "trigger", "daily", "practice", "hint",
        "leaderboard", "streak", "help", "solved", "join", "leave", "ping"
    }

    if first_word in valid_commands and not any(content_stripped.startswith(p) for p in ["!", "\\", "/"]):
        message.content = "!" + content_stripped

    await bot.process_commands(message)


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
    print(f"Reaction ✅: Logged completion quietly for {username} ({payload.user_id}) on {challenge_date} (streak: {result['current_streak']}).")


# ==========================================
# MANUAL TRIGGER LOGIC
# ==========================================

async def execute_trigger(
    channel: discord.TextChannel,
    invoker_mention: str,
    interaction: Optional[discord.Interaction] = None
) -> None:
    try:
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
            elif channel:
                await channel.send(msg)
            return

        already_announced = is_announcement_posted_today(today_date)

        # 2. If the announcement has NOT been posted yet today (e.g. before 8:00 AM or first trigger today):
        # Post the official daily announcement card!
        if not already_announced:
            problem = await fetch_leetcode_daily(bot.session)
            embed = create_problem_embed(problem)
            title = get_morning_title()
            quote = get_trigger_quote()

            active = get_active_participants()
            pings = build_participant_pings(active) if active else ""

            message_content = (
                f"{pings} **{title}** (Triggered by {invoker_mention})\n"
                f"> *\"{quote}\"*"
            )
            if interaction:
                msg = await interaction.followup.send(content=message_content, embed=embed, view=SolvedButtonView())
            elif channel:
                msg = await channel.send(content=message_content, embed=embed, view=SolvedButtonView())
            else:
                return

            chan_id = channel.id if channel else CHANNEL_ID
            save_daily_post(problem["date"], msg.id, chan_id, post_type="announcement")
            print(f"Trigger posted daily announcement for {today_date} (msg_id: {msg.id}).")
            return

        # 3. Post-Announcement Trigger (when announcement was already posted today):
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
                msg = await interaction.followup.send(content=content, embeds=[embed, practice_embed], view=SolvedButtonView())
            elif channel:
                msg = await channel.send(content=content, embeds=[embed, practice_embed], view=SolvedButtonView())
            else:
                return

            chan_id = channel.id if channel else CHANNEL_ID
            save_daily_post(today_date, msg.id, chan_id, post_type="checkin")
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
        embed.set_footer(text="Click 'Mark Solved ✅' below or use /solved to continue your streak privately!")

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

        if interaction:
            msg = await interaction.followup.send(content=content, embeds=embeds, view=SolvedButtonView())
        elif channel:
            msg = await channel.send(content=content, embeds=embeds, view=SolvedButtonView())
        else:
            return

        chan_id = channel.id if channel else CHANNEL_ID
        save_daily_post(today_date, msg.id, chan_id, post_type="checkin")
        print(f"On-demand check-in trigger dispatched: {len(pending)} pending, {len(completed)} completed (msg_id: {msg.id}).")
    except Exception as e:
        import traceback
        print(f"Error in execute_trigger: {e}")
        traceback.print_exc()
        err_msg = f"⚠️ An error occurred while executing trigger: `{e}`"
        if interaction:
            await interaction.followup.send(err_msg)
        elif channel:
            await channel.send(err_msg)


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
            f"• **8:30 PM** (`{EVENING_HOUR:02d}:{EVENING_MINUTE:02d}`) — Evening reminder (**only pings members who haven't completed**)\n"
            f"• **Sunday 11:00 AM** — Weekly Champion Spotlight crowning the #1 streak leader!"
        ),
        inline=False
    )

    embed.add_field(
        name="🔥 How Streak Tracking & Smart Pings Work",
        value=(
            "1. **Private Mark Solved**: Click the **Mark Solved ✅** button on any challenge or check-in card OR run `/solved`! Your completion and bonus practice track are 100% private (`Only you can see this`).\n"
            "2. **Quiet Emoji Reaction**: Clicking the **✅** reaction also logs your completion quietly without posting any messages into the channel.\n"
            "3. **Cascading Smart Exemptions**:\n"
            "   • Solve before 1:00 PM ➔ **Zero pings** at 1:00 PM & 8:30 PM.\n"
            "   • Solve at or after 1:00 PM ➔ **Zero pings** at 8:30 PM.\n"
            "   • Only members who still haven't solved get pinged in reminders!\n"
            "4. **Public Milestone Shoutouts**: When you conquer landmark streaks of **7, 28, 56, and monthly marks (30, 60, 90... days)**, the server celebrates your achievement publicly!\n"
            "5. **60-Day Data Retention**: If you `/leave`, your streak history is preserved for 60 days before deletion."
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
            "• `/solved` — Mark today's challenge as solved privately (`Only you can see this`)\n"
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


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    import traceback
    cmd_name = interaction.command.name if interaction.command else "command"
    print(f"Slash command error in /{cmd_name}: {error}")
    traceback.print_exception(type(error), error, error.__traceback__)
    msg = f"⚠️ An error occurred while executing `/{cmd_name}`: {error}"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception as e:
        print(f"Failed to notify interaction error: {e}")


@bot.tree.command(name="trigger", description="Post daily challenge announcement (if not posted yet) or on-demand check-in")
async def slash_trigger(interaction: discord.Interaction):
    await interaction.response.defer()
    channel = interaction.channel
    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        channel = bot.get_channel(CHANNEL_ID)
    await execute_trigger(channel, interaction.user.mention, interaction=interaction)


@bot.tree.command(name="daily", description="Fetch today's active LeetCode daily challenge")
async def slash_daily(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        problem = await fetch_leetcode_daily(bot.session)
        embed = create_problem_embed(problem)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Error fetching today's daily problem: {e}")


@bot.tree.command(name="practice", description="View today's curated 4 similar practice problems (2 Easy, 1 Medium, 1 Hard)")
async def slash_practice(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        problem = await fetch_leetcode_daily(bot.session)
        practice_data = await get_or_fetch_bonus_problems(problem)
        embed = create_practice_embed(practice_data)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Error fetching practice problems: {e}")


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


@bot.tree.command(name="solved", description="Mark today's LeetCode daily challenge as solved privately (Only you can see this)")
async def slash_solved(interaction: discord.Interaction):
    await handle_solve_interaction(interaction)


@bot.tree.command(name="streak", description="Check your or another member's LeetCode streak and stats")
@app_commands.describe(member="Member to view streak for (defaults to yourself)")
async def slash_streak(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    await interaction.response.defer()
    target = member or interaction.user
    stats = get_user_stats(target.id)

    if not stats:
        msg = f"ℹ️ **{target.display_name}** has not recorded any solved problems yet! Use `/solved` to begin."
        await interaction.followup.send(msg)
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

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="leaderboard", description="Display the top LeetCode streak leaders in the server")
async def slash_leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()
    leaders = get_top_streaks(limit=10)

    if not leaders:
        await interaction.followup.send("ℹ️ No streaks recorded yet! Be the first by using `/solved`.")
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
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="participants", description="View active members participating in daily challenges")
async def slash_participants(interaction: discord.Interaction):
    await interaction.response.defer()
    active = get_active_participants()
    if not active:
        await interaction.followup.send("ℹ️ No active participants currently registered. Use `/join` to participate!")
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
    await interaction.followup.send(embed=embed)


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
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")


@bot.command(name="solved")
async def prefix_solved(ctx):
    today_date = get_current_date_str()
    res = record_completion(ctx.author.id, ctx.author.display_name, today_date)

    try:
        await ctx.message.delete()
    except Exception:
        pass

    if not res["success"] and res.get("reason") == "already_solved":
        await ctx.send(
            f"🎯 {ctx.author.mention}, you already logged today's challenge! Current streak: **{res['current_streak']} days**! *(Tip: Use `/solved` or click the **Mark Solved ✅** button on the post for a 100% private popup)*",
            delete_after=6
        )
    else:
        await ctx.send(
            f"🏆 {ctx.author.mention}, marked as solved! Streak: 🔥 **{res['current_streak']} days**! *(Tip: Use `/solved` or click the **Mark Solved ✅** button on the post for a 100% private popup)*",
            delete_after=6
        )

    # Check for milestone celebration
    milestone = res.get("milestone")
    if milestone:
        badge = milestone.get("badge", "🎉")
        m_title = milestone.get("title", f"{res['current_streak']}-Day Streak Milestone!")
        m_desc = milestone.get("desc", "Incredible persistence and dedication!")
        milestone_embed = discord.Embed(
            title=f"{badge} {m_title}",
            description=(
                f"Huge milestone reached! Let's celebrate {ctx.author.mention} for achieving "
                f"an unbroken streak of **{res['current_streak']} days**! 🔥\n\n"
                f"{m_desc}\n\n"
                f"🏆 Highest Streak: **{res['highest_streak']} days** | 📚 Total Solved: **{res['total_solved']} problems**"
            ),
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        milestone_embed.set_footer(text="LeetCode Milestone Celebration • Keep the streak alive!")
        await ctx.send(
            content=f"🎉 **MILESTONE ALERT!** Shoutout to {ctx.author.mention} for hitting **{res['current_streak']} days**!",
            embed=milestone_embed
        )


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
        await ctx.send("ℹ️ No active participants currently registered. Use `/join` or `!join` to participate!")
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
    await ctx.send(embed=embed)


@bot.command(name="trigger")
async def prefix_trigger(ctx):
    channel = ctx.channel
    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
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


@bot.command(name="hint")
async def prefix_hint(ctx, number: Optional[int] = 1):
    try:
        problem = await fetch_leetcode_daily(bot.session)
        hints = problem.get("hints", [])
        if not hints:
            await ctx.send(f"💡 No hints are available for **{problem['title']}**.")
            return

        hint_idx = (number or 1) - 1
        if hint_idx < 0 or hint_idx >= len(hints):
            await ctx.send(f"⚠️ Invalid hint number. **{problem['title']}** has {len(hints)} hint(s) available (1 to {len(hints)}).")
            return

        hint_content = hints[hint_idx]
        msg = (
            f"💡 **Hint {hint_idx + 1}/{len(hints)} for {problem['title']}**:\n"
            f"||{hint_content}||\n\n"
            f"*(Click the black spoiler box above to reveal)*"
        )
        await ctx.send(msg)
    except Exception as e:
        await ctx.send(f"⚠️ Error fetching hint: {e}")


@bot.command(name="join")
async def prefix_join(ctx):
    add_participant(ctx.author.id, ctx.author.display_name)
    await ctx.send(f"🚀 **{ctx.author.mention}**, you are now enrolled as an active participant! You'll receive daily challenges and smart streak reminders.")


@bot.command(name="leave")
async def prefix_leave(ctx):
    remove_participant(ctx.author.id)
    await ctx.send(f"👋 **{ctx.author.mention}**, you have been removed from daily reminder pings. You can rejoin anytime with `/join` or `!join`.")


@bot.command(name="ping")
async def prefix_ping(ctx):
    latency_ms = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! Latency: **{latency_ms}ms**")


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not found. Please set it in your .env file.")
    else:
        bot.run(DISCORD_TOKEN)
