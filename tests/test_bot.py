import unittest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import discord

# Import functions from bot.py
# This requires bot.py to not run on import
from bot import is_quality_message, MarkovBot

class TestBot(unittest.IsolatedAsyncioTestCase):

    def test_emoji_only_is_quality_message(self):
        # Current behavior: this will return False because it gets filtered out by emoji check.
        # Desired behavior: emoji checks are removed, so if there are enough emojis/words, it should return True.
        # E.g., "😊 😊 😊 😊" has 4 words/emojis.
        self.assertTrue(is_quality_message("😊 😊 😊 😊"))

    def test_message_with_words_and_emojis(self):
        self.assertTrue(is_quality_message("This is a test 😊"))

    def test_message_with_only_custom_emojis(self):
        # <:emoji:12345> style custom emojis
        self.assertTrue(is_quality_message("<:emoji:12345> <:emoji:12345> <:emoji:12345> <:emoji:12345>"))

    @patch("discord.Client.user", new_callable=PropertyMock)
    @patch("discord.Client.change_presence", new_callable=AsyncMock)
    async def test_on_ready_sets_online_status(self, mock_change_presence, mock_user_prop):
        mock_user = MagicMock()
        mock_user.id = 12345
        mock_user.__str__.return_value = "TestBot#0000"
        mock_user_prop.return_value = mock_user

        bot_instance = MarkovBot()
        await bot_instance.on_ready()
        mock_change_presence.assert_called_once_with(status=discord.Status.online)

    @patch("bot.is_opted_out")
    @patch("bot.message_count")
    @patch("bot.get_messages")
    async def test_handle_reply_mimic_uses_typing(self, mock_get_messages, mock_message_count, mock_is_opted_out):
        mock_is_opted_out.return_value = False
        mock_message_count.return_value = 50
        mock_get_messages.return_value = ["hello world style message", "another test message here"]

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

    def test_generate_sentences_strict_overlap(self):
        from bot import generate_sentences
        # Corpus designed so that it can generate a novel sentence "x y e f z w" (6 words).
        # This sentence overlaps with "x y e f g h i j" by 4 words (66.6%) and "a b c d e f z w" by 4 words (66.6%).
        # Under default 0.70 max_overlap_ratio, this is allowed and it will generate a sentence.
        # Under our new stricter 0.55 ratio, this should be rejected, returning []
        corpus = [
            "a b c d e f g h i j",
            "x y e f g h i j",
            "a b c d e f z w"
        ]
        results = generate_sentences(corpus, 100) # request many times to ensure it runs
        self.assertEqual(results, [])



if __name__ == "__main__":
    unittest.main()
