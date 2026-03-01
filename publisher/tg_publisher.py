"""Telegram channel publisher."""

from typing import Optional

from aiogram import Bot
from loguru import logger


class TelegramPublisher:
    """Publishes content to Telegram channels."""
    
    MAX_MESSAGE_LENGTH = 4096
    MAX_CAPTION_LENGTH = 1024
    
    async def publish(
        self,
        bot: Bot,
        channel_id: str,
        text: str,
        image_url: Optional[str] = None,
    ) -> bool:
        """
        Publish content to a Telegram channel.
        
        Args:
            bot: Aiogram Bot instance
            channel_id: Channel ID (e.g., @mychannel or -100123456789)
            text: Message text (supports Markdown)
            image_url: Optional image URL to attach
        
        Returns:
            True if published successfully, False otherwise
        """
        try:
            if image_url:
                return await self._publish_with_photo(bot, channel_id, text, image_url)
            else:
                return await self._publish_text_only(bot, channel_id, text)
        except Exception as e:
            logger.error(f"Failed to publish to Telegram channel {channel_id}: {e}")
            return False
    
    async def _publish_with_photo(
        self, bot: Bot, channel_id: str, text: str, image_url: str
    ) -> bool:
        """Publish message with photo."""
        try:
            # Telegram captions have a shorter limit
            if len(text) <= self.MAX_CAPTION_LENGTH:
                await bot.send_photo(
                    chat_id=channel_id,
                    photo=image_url,
                    caption=text,
                    parse_mode="Markdown",
                )
                logger.info(f"Published photo with caption to {channel_id}")
                return True
            else:
                # Send photo first, then text in chunks
                await bot.send_photo(
                    chat_id=channel_id,
                    photo=image_url,
                )
                logger.info(f"Published photo to {channel_id}")
                return await self._publish_text_only(bot, channel_id, text)
        except Exception as e:
            logger.error(f"Failed to publish photo: {e}")
            return False
    
    async def _publish_text_only(self, bot: Bot, channel_id: str, text: str) -> bool:
        """Publish text-only message, splitting if necessary."""
        try:
            if len(text) <= self.MAX_MESSAGE_LENGTH:
                await bot.send_message(
                    chat_id=channel_id,
                    text=text,
                    parse_mode="Markdown",
                )
                logger.info(f"Published message to {channel_id}")
                return True
            else:
                # Split into chunks
                chunks = self._split_text(text)
                for i, chunk in enumerate(chunks):
                    await bot.send_message(
                        chat_id=channel_id,
                        text=chunk,
                        parse_mode="Markdown",
                    )
                    logger.info(f"Published message chunk {i+1}/{len(chunks)} to {channel_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to publish text message: {e}")
            return False
    
    def _split_text(self, text: str) -> list[str]:
        """
        Split text into chunks respecting Telegram's message length limit.
        
        Tries to split at paragraph boundaries to maintain readability.
        """
        chunks = []
        
        # Try to split by double newlines (paragraphs)
        paragraphs = text.split("\n\n")
        current_chunk = ""
        
        for para in paragraphs:
            # If adding this paragraph exceeds limit, save current chunk and start new one
            if len(current_chunk) + len(para) + 2 > self.MAX_MESSAGE_LENGTH:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
        
        # Add remaining text
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # Final safety check: if any chunk is still too long, split by length
        final_chunks = []
        for chunk in chunks:
            if len(chunk) <= self.MAX_MESSAGE_LENGTH:
                final_chunks.append(chunk)
            else:
                # Hard split by character count
                for i in range(0, len(chunk), self.MAX_MESSAGE_LENGTH):
                    final_chunks.append(chunk[i:i + self.MAX_MESSAGE_LENGTH])
        
        return final_chunks
