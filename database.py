import os
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

from phrases import check_milestone

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "bot.db")

# Initial seeded participants: shanks (Niranjan), Praveen, VICHU
INITIAL_PARTICIPANTS = [
    (755039308955648080, "shanks"),
    (835900884344766474, "Praveen"),
    (739811756863651851, "VICHU")
]


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                current_streak INTEGER NOT NULL DEFAULT 0,
                highest_streak INTEGER NOT NULL DEFAULT 0,
                total_solved INTEGER NOT NULL DEFAULT 0,
                last_solved_date TEXT
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                challenge_date TEXT NOT NULL,
                solved_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, challenge_date),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_posts (
                message_id INTEGER PRIMARY KEY,
                challenge_date TEXT NOT NULL,
                channel_id INTEGER NOT NULL,
                post_type TEXT NOT NULL DEFAULT 'post',
                posted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_posts_date ON daily_posts(challenge_date);")

        # Ensure post_type column exists if table was created previously
        cursor.execute("PRAGMA table_info(daily_posts)")
        columns = [c["name"] for c in cursor.fetchall()]
        if "post_type" not in columns:
            cursor.execute("ALTER TABLE daily_posts ADD COLUMN post_type TEXT NOT NULL DEFAULT 'post'")

        # Migrate older schema where challenge_date was PRIMARY KEY if present
        cursor.execute("PRAGMA table_info(daily_posts)")
        columns_info = cursor.fetchall()
        pk_col = next((c["name"] for c in columns_info if c["pk"] == 1), None)
        if pk_col == "challenge_date":
            cursor.execute("""
                CREATE TABLE daily_posts_v2 (
                    message_id INTEGER PRIMARY KEY,
                    challenge_date TEXT NOT NULL,
                    channel_id INTEGER NOT NULL,
                    post_type TEXT NOT NULL DEFAULT 'post',
                    posted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                INSERT OR IGNORE INTO daily_posts_v2 (message_id, challenge_date, channel_id, post_type, posted_at)
                SELECT message_id, challenge_date, channel_id, 'announcement', posted_at FROM daily_posts;
            """)
            cursor.execute("DROP TABLE daily_posts;")
            cursor.execute("ALTER TABLE daily_posts_v2 RENAME TO daily_posts;")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_posts_date ON daily_posts(challenge_date);")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS participants (
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                active INTEGER NOT NULL DEFAULT 1,
                left_at TIMESTAMP DEFAULT NULL
            );
            """
        )

        # Migration: ensure left_at column exists in participants if upgrading
        cursor.execute("PRAGMA table_info(participants);")
        part_cols = [row["name"] for row in cursor.fetchall()]
        if "left_at" not in part_cols:
            cursor.execute("ALTER TABLE participants ADD COLUMN left_at TIMESTAMP DEFAULT NULL;")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS bonus_problems (
                challenge_date TEXT PRIMARY KEY,
                topic_name TEXT NOT NULL,
                problems_json TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # Seed initial participants if empty
        cursor.execute("SELECT COUNT(*) as count FROM participants")
        if cursor.fetchone()["count"] == 0:
            for uid, name in INITIAL_PARTICIPANTS:
                cursor.execute(
                    "INSERT OR IGNORE INTO participants (user_id, username, active) VALUES (?, ?, 1)",
                    (uid, name)
                )

        conn.commit()


def add_participant(user_id: int, username: str, db_path: str = DEFAULT_DB_PATH) -> bool:
    """Adds a member to active participants, or reactivates them if previously left."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO participants (user_id, username, active, left_at)
            VALUES (?, ?, 1, NULL)
            ON CONFLICT(user_id) DO UPDATE SET active = 1, left_at = NULL, username = excluded.username
            """,
            (user_id, username)
        )
        conn.commit()
        return True


def remove_participant(user_id: int, db_path: str = DEFAULT_DB_PATH) -> bool:
    """Deactivates a member from participation and marks left_at timestamp (retained for 60 days)."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE participants SET active = 0, left_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()
        return cursor.rowcount > 0


def prune_expired_inactive_participants(days: int = 60, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Finds participants who left more than `days` ago (default 60 days / 2 months)
    and permanently removes their records from completions, users, and participants.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT user_id, username, left_at
            FROM participants
            WHERE active = 0 AND left_at IS NOT NULL AND left_at <= datetime('now', '-{days} days')
            """
        )
        expired_users = [dict(row) for row in cursor.fetchall()]

        for u in expired_users:
            uid = u["user_id"]
            cursor.execute("DELETE FROM completions WHERE user_id = ?", (uid,))
            cursor.execute("DELETE FROM users WHERE user_id = ?", (uid,))
            cursor.execute("DELETE FROM participants WHERE user_id = ?", (uid,))

        conn.commit()
        return expired_users


def get_active_participants(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Returns all currently active participants."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, username, joined_at FROM participants WHERE active = 1 ORDER BY username ASC"
        )
        return [dict(row) for row in cursor.fetchall()]


def get_challenge_status(challenge_date: str, db_path: str = DEFAULT_DB_PATH) -> Dict[str, List[Dict[str, Any]]]:
    """
    Separates active participants into:
    - 'completed': those who have logged completion for this date
    - 'pending': those who have NOT completed yet
    """
    active = get_active_participants(db_path)
    today_completions = get_today_completions(challenge_date, db_path)
    solved_user_ids = {c["user_id"] for c in today_completions}

    completed = []
    pending = []

    for p in active:
        if p["user_id"] in solved_user_ids:
            completed.append(p)
        else:
            pending.append(p)

    return {
        "completed": completed,
        "pending": pending
    }


def record_completion(
    user_id: int,
    username: str,
    challenge_date: str,
    db_path: str = DEFAULT_DB_PATH
) -> Dict[str, Any]:
    """
    Records problem completion for a user on a given challenge date.
    Calculates streak increments or resets.
    Also automatically enrolls/reactivates the user in participants.
    """
    # Ensure user is an active participant
    add_participant(user_id, username, db_path)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Check if already completed
        cursor.execute(
            "SELECT id FROM completions WHERE user_id = ? AND challenge_date = ?",
            (user_id, challenge_date)
        )
        if cursor.fetchone():
            cursor.execute("SELECT current_streak, highest_streak, total_solved FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
            return {
                "success": False,
                "reason": "already_solved",
                "current_streak": user["current_streak"] if user else 1,
                "highest_streak": user["highest_streak"] if user else 1,
                "total_solved": user["total_solved"] if user else 1,
            }

        # Check existing user
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()

        target_date = date.fromisoformat(challenge_date)
        yesterday_str = (target_date - timedelta(days=1)).isoformat()

        if user is None:
            current_streak = 1
            highest_streak = 1
            total_solved = 1
            cursor.execute(
                """
                INSERT INTO users (user_id, username, current_streak, highest_streak, total_solved, last_solved_date)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, username, current_streak, highest_streak, total_solved, challenge_date)
            )
        else:
            last_date_str = user["last_solved_date"]
            if last_date_str == yesterday_str:
                current_streak = user["current_streak"] + 1
            else:
                # Broken streak or past date jump
                current_streak = 1

            highest_streak = max(user["highest_streak"], current_streak)
            total_solved = user["total_solved"] + 1

            cursor.execute(
                """
                UPDATE users
                SET username = ?,
                    current_streak = ?,
                    highest_streak = ?,
                    total_solved = ?,
                    last_solved_date = ?
                WHERE user_id = ?
                """,
                (username, current_streak, highest_streak, total_solved, challenge_date, user_id)
            )

        cursor.execute(
            "INSERT INTO completions (user_id, challenge_date) VALUES (?, ?)",
            (user_id, challenge_date)
        )
        conn.commit()

        milestone = check_milestone(current_streak)
        return {
            "success": True,
            "reason": "completed",
            "current_streak": current_streak,
            "highest_streak": highest_streak,
            "total_solved": total_solved,
            "milestone": milestone
        }


def get_user_stats(user_id: int, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def get_top_streaks(limit: int = 10, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT username, current_streak, highest_streak, total_solved
            FROM users
            ORDER BY current_streak DESC, total_solved DESC
            LIMIT ?
            """,
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]


def get_today_completions(challenge_date: str, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT u.user_id, u.username, c.solved_at
            FROM completions c
            JOIN users u ON c.user_id = u.user_id
            WHERE c.challenge_date = ?
            ORDER BY c.solved_at ASC
            """,
            (challenge_date,)
        )
        return [dict(row) for row in cursor.fetchall()]


def save_daily_post(
    challenge_date: str,
    message_id: int,
    channel_id: int,
    post_type: str = "post",
    db_path: str = DEFAULT_DB_PATH
) -> None:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO daily_posts (message_id, challenge_date, channel_id, post_type, posted_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (message_id, challenge_date, channel_id, post_type)
        )
        conn.commit()


def is_announcement_posted_today(challenge_date: str, db_path: str = DEFAULT_DB_PATH) -> bool:
    """Returns True if the primary challenge announcement was already posted for challenge_date."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as count FROM daily_posts WHERE challenge_date = ? AND post_type = 'announcement'",
            (challenge_date,)
        )
        return cursor.fetchone()["count"] > 0


def get_daily_post_date(message_id: int, db_path: str = DEFAULT_DB_PATH) -> Optional[str]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT challenge_date FROM daily_posts WHERE message_id = ?",
            (message_id,)
        )
        row = cursor.fetchone()
        if row:
            return row["challenge_date"]
        return None


def get_cached_bonus_problems(challenge_date: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieves cached 4-problem bonus set for a given challenge date if available."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT topic_name, problems_json FROM bonus_problems WHERE challenge_date = ?",
            (challenge_date,)
        )
        row = cursor.fetchone()
        if row:
            import json
            data = json.loads(row["problems_json"])
            data["topic_name"] = row["topic_name"]
            return data
        return None


def save_cached_bonus_problems(
    challenge_date: str,
    topic_name: str,
    problems_data: Dict[str, Any],
    db_path: str = DEFAULT_DB_PATH
) -> None:
    """Caches the 4-problem bonus set for a given challenge date."""
    import json
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO bonus_problems (challenge_date, topic_name, problems_json, created_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (challenge_date, topic_name, json.dumps(problems_data))
        )
        conn.commit()
