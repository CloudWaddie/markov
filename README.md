# Markov

A Discord bot that uses [markovify](https://github.com/jsvine/markovify) to mimic any user's writing style.

## How it works

- Silently collects messages in real time and stores them in a local SQLite database
- When a user doesn't have enough stored messages, it scrapes recent channel history as a fallback
- Builds a Markov chain model from a user's messages and generates new sentences that sound like them

## Commands

| Command | Description |
|---|---|
| `/mimic @user` | Generate a sentence mimicking the target user |
| `/mimic @user count:3` | Generate multiple sentences (1-5) |

## Setup

1. Create a bot application in the [Discord Developer Portal](https://discord.com/developers/applications)
2. Enable the **Message Content** and **Server Members** privileged intents
3. Clone this repo and install dependencies:

```bash
git clone https://github.com/CloudWaddie/markov.git
cd markov
pip install -r requirements.txt
```

4. Copy `.env.example` to `.env` and add your bot token:

```bash
cp .env.example .env
```

5. Run the bot:

```bash
python bot.py
```

Slash commands sync globally on startup, which can take up to an hour. For instant testing in a single server, change the `setup_hook` in `bot.py` to sync to your guild:

```python
await self.tree.sync(guild=discord.Object(id=YOUR_GUILD_ID))
```

## Requirements

- Python 3.10+
- `discord.py >= 2.3`
- `markovify`
- `python-dotenv`
