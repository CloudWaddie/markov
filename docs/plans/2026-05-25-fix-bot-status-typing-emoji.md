# Bot Fixes: Online Status, Typing Indicators, and Emoji Check Removal Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure the Discord bot shows as online when running, uses typing indicators before replying/processing messages, and removes all emoji filters from quality message checks.

**Architecture:** 
1. Protect the entry point of `bot.py` with `if __name__ == "__main__":` so the bot can be imported for testing.
2. In `bot.py`, call `await self.change_presence(status=discord.Status.online)` inside the `on_ready` callback to ensure it sets its online status immediately upon connecting.
3. Wrap message generation and processing blocks in `async with channel.typing():` to show the typing indicator while generating responses.
4. Remove emoji patterns and emoji checking logic from `is_quality_message`.
5. Create a test suite (`tests/test_bot.py`) using Python's built-in `unittest` and `unittest.mock` to test these changes.

**Tech Stack:** Python 3, discord.py, unittest (built-in)

---

### Task 1: Wrap bot.run in main block and set up test suite structure

**Files:**
- Modify: [bot.py](file:///C:/Users/Edward/markov/bot.py)
- Create: [tests/test_bot.py](file:///C:/Users/Edward/markov/tests/test_bot.py)

**Step 1: Write the failing test**
Create `tests/test_bot.py` to test quality messages containing emojis:
```python
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import discord

# Import functions from bot.py
# This requires bot.py to not run on import
from bot import is_quality_message, MarkovBot

class TestBot(unittest.TestCase):
    def test_emoji_only_is_quality_message(self):
        # Current behavior: this will return False because it gets filtered out by emoji check.
        # Desired behavior: emoji checks are removed, so if there are enough emojis/words, it should return True.
        # Let's write a test that checks a string of emojis.
        # E.g., "😊 😊 😊 😊" has 4 words/emojis.
        self.assertTrue(is_quality_message("😊 😊 😊 😊"))
```

**Step 2: Run test to verify it fails**
Run: `python -m unittest tests/test_bot.py`
Expected: Fail (assertion error, returns False instead of True) or error if bot.py runs on import.

**Step 3: Write minimal implementation to wrap bot.run**
Modify the bottom of `bot.py` to wrap the execution:
```python
if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN not set. Copy .env.example to .env and add your token.")
    bot.run(token)
```

**Step 4: Run test to verify it fails on emoji check (not import error)**
Run: `python -m unittest tests/test_bot.py`
Expected: Fail (returns False instead of True for `"😊 😊 😊 😊"`)

**Step 5: Commit**
```bash
git add bot.py tests/test_bot.py
git commit -m "test: set up test structure and verify emoji test fails"
```

---

### Task 2: Remove Emoji Checks from Quality Message Check

**Files:**
- Modify: [bot.py](file:///C:/Users/Edward/markov/bot.py)

**Step 1: Write additional tests verifying emoji checks are removed**
Update `tests/test_bot.py`:
```python
    def test_message_with_words_and_emojis(self):
        self.assertTrue(is_quality_message("This is a test 😊"))

    def test_message_with_only_custom_emojis(self):
        # <a:test:12345> style custom emojis
        self.assertTrue(is_quality_message("<:emoji:12345> <:emoji:12345> <:emoji:12345> <:emoji:12345>"))
```

**Step 2: Run tests to verify they fail**
Run: `python -m unittest tests/test_bot.py`
Expected: Fail

**Step 3: Modify `is_quality_message` and remove regex patterns**
In `bot.py`:
- Remove `EMOJI_ONLY_RE`, `CUSTOM_EMOJI_RE`, and `UNICODE_EMOJI_RANGES`.
- Update `is_quality_message` to only filter URLs and check length:
```python
def is_quality_message(text: str) -> bool:
    stripped = URL_RE.sub("", text).strip()
    if not stripped:
        return False
    if len(stripped.split()) < MIN_WORDS:
        return False
    return True
```

**Step 4: Run tests to verify they pass**
Run: `python -m unittest tests/test_bot.py`
Expected: Pass

**Step 5: Commit**
```bash
git add bot.py tests/test_bot.py
git commit -m "feat: remove emoji checks from is_quality_message"
```

---

### Task 3: Set Bot Status to Online

**Files:**
- Modify: [bot.py](file:///C:/Users/Edward/markov/bot.py)
- Modify: [tests/test_bot.py](file:///C:/Users/Edward/markov/tests/test_bot.py)

**Step 1: Write test for status update**
Add a test in `tests/test_bot.py`:
```python
    @patch("discord.Client.change_presence", new_callable=AsyncMock)
    async def test_on_ready_sets_online_status(self, mock_change_presence):
        # We need to run this asynchronously using unittest.IsolatedAsyncioTestCase if supported, 
        # or manually run the async coroutine using asyncio.run
        bot_instance = MarkovBot()
        await bot_instance.on_ready()
        mock_change_presence.assert_called_once_with(status=discord.Status.online)
```
*Note: We will change `TestBot` to inherit from `unittest.IsolatedAsyncioTestCase` to easily test async functions.*

**Step 2: Run test to verify it fails**
Run: `python -m unittest tests/test_bot.py`
Expected: Fail (assertion error, `change_presence` not called)

**Step 3: Implement online presence in `on_ready`**
Modify `on_ready` in `bot.py`:
```python
    async def on_ready(self):
        await self.change_presence(status=discord.Status.online)
        print(f"Logged in as {self.user} (ID: {self.user.id})")
```

**Step 4: Run tests to verify they pass**
Run: `python -m unittest tests/test_bot.py`
Expected: Pass

**Step 5: Commit**
```bash
git add bot.py tests/test_bot.py
git commit -m "feat: set bot presence to online in on_ready"
```

---

### Task 4: Add Typing Indicators

**Files:**
- Modify: [bot.py](file:///C:/Users/Edward/markov/bot.py)
- Modify: [tests/test_bot.py](file:///C:/Users/Edward/markov/tests/test_bot.py)

**Step 1: Write tests for typing indicators in message handling and slash commands**
Add tests verifying that `typing()` is used when scraping/processing in `handle_reply_mimic`, `mimic`, and `markovme`.
We can mock channel typing:
```python
    @patch("bot.is_opted_out", return_callable=MagicMock(return_value=False))
    @patch("bot.message_count", return_callable=MagicMock(return_value=50))
    @patch("bot.get_messages", return_callable=MagicMock(return_value=["hello world style message", "another test message here"]))
    async def test_handle_reply_mimic_uses_typing(self, mock_get_messages, mock_message_count, mock_is_opted_out):
        bot_instance = MarkovBot()
        
        # Mock message and channel
        mock_msg = AsyncMock(spec=discord.Message)
        mock_msg.guild = MagicMock(spec=discord.Guild)
        mock_msg.guild.id = 123
        mock_msg.author = MagicMock(spec=discord.Member)
        mock_msg.author.id = 456
        mock_msg.author.bot = False
        mock_msg.mentions = [bot_instance.user]
        mock_msg.reference = MagicMock()
        mock_msg.reference.message_id = 789
        
        mock_replied = AsyncMock(spec=discord.Message)
        mock_replied.author = MagicMock(spec=discord.Member)
        mock_replied.author.bot = False
        mock_replied.author.id = 456
        mock_replied.author.display_name = "TargetUser"
        mock_replied.author.color = discord.Color.default()
        mock_replied.author.display_avatar.url = "http://example.com/avatar.png"
        
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_channel.fetch_message.return_value = mock_replied
        
        # Setup typing context manager mock
        typing_mock = AsyncMock()
        mock_channel.typing.return_value = typing_mock
        mock_msg.channel = mock_channel
        
        await bot_instance.handle_reply_mimic(mock_msg)
        
        # Verify typing was entered
        mock_channel.typing.assert_called_once()
        typing_mock.__aenter__.assert_called_once()
```

**Step 2: Run test to verify it fails**
Run: `python -m unittest tests/test_bot.py`
Expected: Fail

**Step 3: Modify `bot.py` to wrap with `typing()`**
Update `handle_reply_mimic`, `mimic`, and `markovme` with `async with channel.typing():` (or `interaction.channel.typing()` if channel is available).

**Step 4: Run tests to verify they pass**
Run: `python -m unittest tests/test_bot.py`
Expected: Pass

**Step 5: Commit**
```bash
git add bot.py tests/test_bot.py
git commit -m "feat: add typing indicators for responses"
```
