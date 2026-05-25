import os
import re
import sqlite3
from datetime import datetime, timezone

import discord
from discord import app_commands
import markovify
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "markov.db")
MIN_MESSAGES = 50
SCRAPE_LIMIT = 500
MAX_SENTENCES = 5
STATE_SIZE = 2
MIN_WORDS = 4

URL_RE = re.compile(r"https?://\S+")
def is_quality_message(text: str) -> bool:
    stripped = URL_RE.sub("", text).strip()
    if not stripped:
        return False
    if len(stripped.split()) < MIN_WORDS:
        return False
    return True



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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS opted_out (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        )
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


def is_opted_out(conn, guild_id: int, user_id: int) -> bool:
    cursor = conn.execute(
        "SELECT 1 FROM opted_out WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    return cursor.fetchone() is not None


def opt_out(conn, guild_id: int, user_id: int):
    conn.execute(
        "INSERT OR IGNORE INTO opted_out (guild_id, user_id) VALUES (?, ?)",
        (guild_id, user_id),
    )
    conn.execute(
        "DELETE FROM messages WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    conn.commit()


def opt_in(conn, guild_id: int, user_id: int):
    conn.execute(
        "DELETE FROM opted_out WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    conn.commit()


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
        self.tree.add_command(markovme)
        self.tree.add_command(optout)
        await self.tree.sync()

    async def on_ready(self):
        await self.change_presence(status=discord.Status.online)
        print(f"Logged in as {self.user} (ID: {self.user.id})")

    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        if message.reference and self.user in message.mentions:
            await self.handle_reply_mimic(message)
            return

        content = message.content.strip()
        if not content or not is_quality_message(content):
            return
        if is_opted_out(self.db, message.guild.id, message.author.id):
            return
        store_message(self.db, message.guild.id, message.author.id, content)

    async def handle_reply_mimic(self, message: discord.Message):
        try:
            replied = await message.channel.fetch_message(message.reference.message_id)
        except discord.NotFound:
            return

        target = replied.author
        if target.bot:
            await message.reply("I can't mimic bots.")
            return

        if is_opted_out(self.db, message.guild.id, target.id):
            await message.reply(f"**{target.display_name}** has opted out of markov.")
            return

        guild_id = message.guild.id
        stored = message_count(self.db, guild_id, target.id)

        if stored < MIN_MESSAGES:
            scraped = 0
            async for msg in message.channel.history(limit=SCRAPE_LIMIT):
                if msg.author.id == target.id and not msg.author.bot and msg.content.strip() and is_quality_message(msg.content.strip()):
                    store_message(self.db, guild_id, target.id, msg.content.strip())
                    scraped += 1
            stored += scraped

        if stored < 10:
            await message.reply(f"Not enough data for **{target.display_name}**. They need to chat more!")
            return

        corpus = get_messages(self.db, guild_id, target.id)

        try:
            sentences = generate_sentences(corpus, 1)
        except Exception:
            sentences = []

        if not sentences:
            await message.reply(f"Couldn't generate anything for **{target.display_name}**.")
            return

        embed = discord.Embed(
            description=sentences[0],
            color=target.color if target.color != discord.Color.default() else discord.Color.blurple(),
        )
        embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)
        embed.set_footer(text="Generated with markovify")

        await message.reply(embed=embed)


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

    if is_opted_out(bot.db, interaction.guild.id, user.id):
        await interaction.response.send_message(
            f"**{user.display_name}** has opted out of markov.", ephemeral=True
        )
        return

    stored = message_count(bot.db, interaction.guild.id, user.id)

    if stored < MIN_MESSAGES:
        await interaction.response.defer()
        scraped = 0
        async for msg in interaction.channel.history(limit=SCRAPE_LIMIT):
            if msg.author.id == user.id and not msg.author.bot and msg.content.strip() and is_quality_message(msg.content.strip()):
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


@app_commands.command(name="markovme", description="Generate a message mimicking yourself")
@app_commands.describe(count="Number of sentences to generate (1-5, default 1)")
async def markovme(interaction: discord.Interaction, count: int = 1):
    count = max(1, min(count, MAX_SENTENCES))
    user = interaction.user

    if is_opted_out(bot.db, interaction.guild.id, user.id):
        await interaction.response.send_message(
            "You've opted out of markov. Use `/optout` to opt back in first.", ephemeral=True
        )
        return

    stored = message_count(bot.db, interaction.guild.id, user.id)

    if stored < MIN_MESSAGES:
        await interaction.response.defer()
        scraped = 0
        async for msg in interaction.channel.history(limit=SCRAPE_LIMIT):
            if msg.author.id == user.id and not msg.author.bot and msg.content.strip() and is_quality_message(msg.content.strip()):
                store_message(bot.db, interaction.guild.id, user.id, msg.content.strip())
                scraped += 1
        stored += scraped

    if stored < 10:
        msg = "Not enough data to mimic you yet. Keep chatting!"
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)
        return

    corpus = get_messages(bot.db, interaction.guild.id, user.id)

    try:
        sentences = generate_sentences(corpus, count)
    except Exception:
        sentences = []

    if not sentences:
        msg = "Couldn't generate anything. Your messages might be too short or repetitive."
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


@app_commands.command(name="optout", description="Opt out or back in to markov data collection")
async def optout(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    user_id = interaction.user.id

    if is_opted_out(bot.db, guild_id, user_id):
        opt_in(bot.db, guild_id, user_id)
        await interaction.response.send_message(
            "You've opted back in. Your messages will be collected again.", ephemeral=True
        )
    else:
        opt_out(bot.db, guild_id, user_id)
        await interaction.response.send_message(
            "You've opted out. All your stored messages have been deleted and no new ones will be collected.",
            ephemeral=True,
        )


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN not set. Copy .env.example to .env and add your token.")

    bot.run(token)

