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




if __name__ == "__main__":
    unittest.main()

