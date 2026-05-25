import os
import sqlite3
from datetime import datetime, timezone

import discord
from discord import app_commands
import markovify
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "markov.db"
MIN_MESSAGES = 50
SCRAPE_LIMIT = 500
MAX_SENTENCES = 5
STATE_SIZE = 2


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_guild_user
        ON messages(guild_id, user_id)
    """)
    conn.commit()
    return conn


def store_message(conn, guild_id: int, user_id: int, content: str):
    conn.execute(
        "INSERT INTO messages (guild_id, user_id, content, timestamp) VALUES (?, ?, ?, ?)",
        (guild_id, user_id, content, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def get_messages(conn, guild_id: int, user_id: int) -> list[str]:
    cursor = conn.execute(
        "SELECT content FROM messages WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    return [row[0] for row in cursor.fetchall()]


def message_count(conn, guild_id: int, user_id: int) -> int:
    cursor = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    return cursor.fetchone()[0]


def generate_sentences(corpus: list[str], count: int) -> list[str]:
    text = "\n".join(corpus)
    model = markovify.NewlineText(text, state_size=STATE_SIZE)
    sentences = []
    for _ in range(count * 3):
        sentence = model.make_sentence(tries=100)
        if sentence and sentence not in sentences:
            sentences.append(sentence)
        if len(sentences) >= count:
            break
    return sentences


class MarkovBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.db = init_db()

    async def setup_hook(self):
        self.tree.add_command(mimic)
        await self.tree.sync()

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")

    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        content = message.content.strip()
        if not content:
            return
        store_message(self.db, message.guild.id, message.author.id, content)


bot = MarkovBot()


@app_commands.command(name="mimic", description="Generate a message mimicking a user's style")
@app_commands.describe(
    user="The user to mimic",
    count="Number of sentences to generate (1-5, default 1)",
)
async def mimic(
    interaction: discord.Interaction,
    user: discord.Member,
    count: int = 1,
):
    count = max(1, min(count, MAX_SENTENCES))

    if user.bot:
        await interaction.response.send_message("I can't mimic bots.", ephemeral=True)
        return

    stored = message_count(bot.db, interaction.guild.id, user.id)

    if stored < MIN_MESSAGES:
        await interaction.response.defer()
        scraped = 0
        async for msg in interaction.channel.history(limit=SCRAPE_LIMIT):
            if msg.author.id == user.id and not msg.author.bot and msg.content.strip():
                store_message(bot.db, interaction.guild.id, user.id, msg.content.strip())
                scraped += 1
        stored += scraped

    if stored < 10:
        if not interaction.response.is_done():
            await interaction.response.send_message(
                f"Not enough data for **{user.display_name}**. They need to chat more!",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"Not enough data for **{user.display_name}**. They need to chat more!",
                ephemeral=True,
            )
        return

    corpus = get_messages(bot.db, interaction.guild.id, user.id)

    try:
        sentences = generate_sentences(corpus, count)
    except Exception:
        sentences = []

    if not sentences:
        msg = f"Couldn't generate anything for **{user.display_name}**. Their messages might be too short or repetitive."
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)
        return

    embed = discord.Embed(
        description="\n\n".join(sentences),
        color=user.color if user.color != discord.Color.default() else discord.Color.blurple(),
    )
    embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
    embed.set_footer(text="Generated with markovify")

    if not interaction.response.is_done():
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.followup.send(embed=embed)


token = os.getenv("DISCORD_TOKEN")
if not token:
    raise SystemExit("DISCORD_TOKEN not set. Copy .env.example to .env and add your token.")

bot.run(token)
