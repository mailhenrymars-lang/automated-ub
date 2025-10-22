import asyncio
import json
import logging
import os
import random
import re
from typing import List, Dict, Optional, Union, Sequence
from urllib.parse import urlparse

import pyrogram
from pyrogram import filters, enums
from pyrogram.types import Message, Dialog
from pyrogram.errors import FloodWait, ChatWriteForbidden, PeerIdInvalid
from pyrogram.enums import ParseMode
# Import Client properly
from pyrogram.client import Client
# Import MessageHandler properly
from pyrogram.handlers.message_handler import MessageHandler

from config import API_ID, API_HASH, SESSION_NAME, SUDO_USERS, MIN_DELAY, MAX_DELAY

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# File to store sticker pack names
STICKER_PACKS_FILE = "sticker_packs.json"

# Global variables
automation_enabled = False  # Default: Sticker sending OFF
reactions_enabled = False   # Default: Reactions OFF
AUTO_JOIN_ENABLED = True    # Default: Auto-join ON
JOIN_FLOOD_WAIT = 30        # Flood wait time for joining groups (seconds)


def load_sticker_packs() -> List[str]:
    """Load sticker file IDs from JSON file."""
    try:
        if os.path.exists(STICKER_PACKS_FILE):
            with open(STICKER_PACKS_FILE, "r") as f:
                return json.load(f)
        else:
            # Create file with empty list if it doesn't exist
            with open(STICKER_PACKS_FILE, "w") as f:
                json.dump([], f)
            return []
    except Exception as e:
        logger.error(f"Error loading sticker packs: {e}")
        return []


def save_sticker_packs(packs: List[str]) -> None:
    """Save sticker file IDs to JSON file."""
    try:
        with open(STICKER_PACKS_FILE, "w") as f:
            json.dump(packs, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving sticker packs: {e}")


async def get_joined_groups(client: Client) -> List[int]:
    """Get list of joined group chat IDs."""
    groups = []
    try:
        # Collect all dialogs first
        dialogs = []
        async for dialog in client.get_dialogs(): # type: ignore
            dialogs.append(dialog)
        
        # Process collected dialogs
        for dialog in dialogs:
            if dialog.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                # Check if we can send messages in this group
                try:
                    await client.get_chat_member(dialog.chat.id, "me")
                    groups.append(dialog.chat.id)
                except Exception as e:
                    logger.warning(f"Cannot access group {dialog.chat.id}: {e}")
    except Exception as e:
        logger.error(f"Error getting dialogs: {e}")
    return groups


async def send_random_sticker(client: Client) -> None:
    """Send a random sticker from configured stickers to a random group."""
    global automation_enabled
    
    while True:
        try:
            if not automation_enabled:
                await asyncio.sleep(5)
                continue
                
            sticker_file_ids = load_sticker_packs()
            if not sticker_file_ids:
                logger.info("No sticker file IDs configured. Waiting...")
                await asyncio.sleep(60)
                continue
            
            # Get joined groups
            groups = await get_joined_groups(client)
            if not groups:
                logger.info("Not joined to any groups. Waiting...")
                await asyncio.sleep(60)
                continue
            
            # Select random group and sticker
            group_id = random.choice(groups)
            sticker_file_id = random.choice(sticker_file_ids)
            
            logger.info(f"Selected sticker ID: ...{sticker_file_id[-10:]} for group: {group_id}")
            
            # Send sticker using file ID
            try:
                logger.info(f"Sending sticker to group {group_id}")
                await client.send_sticker(group_id, sticker_file_id)
                logger.info(f"Sent sticker to group {group_id}")
            except ChatWriteForbidden:
                logger.warning(f"Cannot send messages to group {group_id}. Leaving...")
                try:
                    await client.leave_chat(group_id)
                except Exception as e:
                    logger.error(f"Failed to leave group {group_id}: {e}")
            except Exception as e:
                logger.error(f"Error sending sticker to group {group_id}: {e}")
                logger.error(f"Exception type: {type(e).__name__}")
            
            # Random delay before next sticker
            delay = random.randint(MIN_DELAY, MAX_DELAY)
            logger.info(f"Waiting {delay} seconds before next sticker")
            await asyncio.sleep(delay)
            
        except FloodWait as e:
            logger.warning(f"Flood wait for {e.value} seconds")
            # Ensure we're working with a numeric value
            try:
                delay_value = int(str(e.value))
                await asyncio.sleep(delay_value)
            except (ValueError, TypeError):
                await asyncio.sleep(60)  # Default to 60 seconds if conversion fails
        except Exception as e:
            logger.error(f"Error in sticker sending loop: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            await asyncio.sleep(10)


async def react_to_messages(client: Client, message: Message) -> None:
    """React to new messages with a heart emoji."""
    global automation_enabled, reactions_enabled
    
    if not automation_enabled or not reactions_enabled:
        return
        
    try:
        # Don't react to service messages or own messages
        if message.service or (message.from_user and message.from_user.is_self):
            return
            
        # React with heart emoji
        await message.react("❤️")
        logger.info(f"Reacted to message {message.id} in chat {message.chat.id}")
    except Exception as e:
        logger.error(f"Error reacting to message: {e}")


async def auto_join_groups(client: Client, message: Message) -> None:
    """Automatically join groups when receiving links from sudo users."""
    global AUTO_JOIN_ENABLED, automation_enabled, reactions_enabled
    
    # Skip command messages
    text = message.text or message.caption or ""
    if text.startswith("."):
        # Allow command messages to be processed by command handlers
        return
    
    # Log all incoming messages for debugging
    logger.info(f"Received message from user {message.from_user.id if message.from_user else 'Unknown'}: {message.text}")
    
    if not AUTO_JOIN_ENABLED:
        return
        
    # Check if message is from a sudo user
    if message.from_user and message.from_user.id in SUDO_USERS:
        # Check if message contains a Telegram group link
        # Matches t.me/username, https://t.me/username, t.me/joinchat/hash, etc.
        link_pattern = r'(?:https?://)?(?:www\.)?t\.me/(?:joinchat/)?([a-zA-Z0-9_-]+)'
        matches = re.findall(link_pattern, text)
        
        if matches:
            joined_count = 0
            for match in matches:
                try:
                    logger.info(f"Attempting to auto-join group: {match}")
                    # Try to join the chat
                    await client.join_chat(match)
                    joined_count += 1
                    logger.info(f"Auto-joined group: {match}")
                    
                    # Send confirmation to sudo user
                    await message.reply_text(f"✅ Auto-joined group: @{match}")
                    
                    # Delay between joins to avoid flooding
                    if len(matches) > 1 and match != matches[-1]:
                        logger.info(f"Waiting {JOIN_FLOOD_WAIT} seconds before joining next group (flood wait)")
                        await asyncio.sleep(JOIN_FLOOD_WAIT)
                        
                except FloodWait as e:
                    logger.warning(f"Flood wait for joining group {match}: {e.value} seconds")
                    # Wait for the specified flood wait time
                    try:
                        wait_time = int(str(e.value))
                        await asyncio.sleep(wait_time)
                        # Try to join again after flood wait
                        await client.join_chat(match)
                        joined_count += 1
                        logger.info(f"Auto-joined group after flood wait: {match}")
                        await message.reply_text(f"✅ Auto-joined group after flood wait: @{match}")
                    except Exception as flood_e:
                        logger.error(f"Error joining group {match} after flood wait: {flood_e}")
                        await message.reply_text(f"❌ Error joining @{match} after flood wait: {flood_e}")
                except Exception as e:
                    logger.error(f"Error auto-joining group {match}: {e}")
                    await message.reply_text(f"❌ Error joining @{match}: {e}")
            
            if joined_count > 0:
                await message.reply_text(f"Auto-join completed. Joined {joined_count}/{len(matches)} groups.")


async def get_sticker_id_handler(client: Client, message: Message) -> None:
    """Get the file ID of a replied sticker."""
    try:
        # Check if the message is a reply and has a sticker
        if not message.reply_to_message or not message.reply_to_message.sticker:
            await message.reply_text("Please reply to a sticker with this command.")
            return
            
        sticker_file_id = message.reply_to_message.sticker.file_id
        await message.reply_text(f"Sticker file ID:\n<code>{sticker_file_id}</code>", parse_mode=ParseMode.HTML)
        logger.info(f"Provided sticker file ID: {sticker_file_id}")
    except Exception as e:
        logger.error(f"Error getting sticker ID: {e}")
        await message.reply_text("Error getting sticker ID.")


async def join_groups_handler(client: Client, message: Message) -> None:
    """Join groups by username with delay."""
    try:
        if len(message.command) < 2:
            await message.reply_text("Usage: .join @username1 @username2 ...")
            return
            
        usernames = message.command[1:]
        joined_count = 0
        
        for username in usernames:
            try:
                # Remove @ if present
                if username.startswith("@"):
                    username = username[1:]
                
                logger.info(f"Attempting to join group: {username}")
                # Join the chat
                await client.join_chat(username)
                joined_count += 1
                logger.info(f"Joined group: {username}")
                await message.reply_text(f"Joined @{username}")
                
                # Delay between joins to avoid flooding
                if len(usernames) > 1 and username != usernames[-1]:
                    logger.info(f"Waiting {JOIN_FLOOD_WAIT} seconds before joining next group (flood wait)")
                    await asyncio.sleep(JOIN_FLOOD_WAIT)
                    
            except FloodWait as e:
                logger.warning(f"Flood wait for joining group {username}: {e.value} seconds")
                # Wait for the specified flood wait time
                try:
                    wait_time = int(str(e.value))
                    await asyncio.sleep(wait_time)
                    # Try to join again after flood wait
                    await client.join_chat(username)
                    joined_count += 1
                    logger.info(f"Joined group after flood wait: {username}")
                    await message.reply_text(f"Joined @{username} after flood wait")
                except Exception as flood_e:
                    logger.error(f"Error joining group {username} after flood wait: {flood_e}")
                    await message.reply_text(f"Error joining @{username} after flood wait: {flood_e}")
            except Exception as e:
                logger.error(f"Error joining group {username}: {e}")
                await message.reply_text(f"Error joining @{username}: {e}")
        
        await message.reply_text(f"Join process completed. Joined {joined_count}/{len(usernames)} groups.")
        
    except Exception as e:
        logger.error(f"Error in join_groups_handler: {e}")
        await message.reply_text("Error processing join request.")


async def enable_reactions_handler(client: Client, message: Message) -> None:
    """Enable reactions."""
    global reactions_enabled
    reactions_enabled = True
    await message.reply_text("Reactions enabled.")
    logger.info("Reactions enabled by sudo user.")


async def disable_reactions_handler(client: Client, message: Message) -> None:
    """Disable reactions."""
    global reactions_enabled
    reactions_enabled = False
    await message.reply_text("Reactions disabled.")
    logger.info("Reactions disabled by sudo user.")


async def enable_autojoin_handler(client: Client, message: Message) -> None:
    """Enable auto-join functionality."""
    global AUTO_JOIN_ENABLED
    AUTO_JOIN_ENABLED = True
    await message.reply_text("Auto-join enabled.")
    logger.info("Auto-join enabled by sudo user.")


async def disable_autojoin_handler(client: Client, message: Message) -> None:
    """Disable auto-join feature."""
    global AUTO_JOIN_ENABLED
    AUTO_JOIN_ENABLED = False
    await message.reply_text("Auto-join disabled.")
    logger.info("Auto-join disabled by sudo user.")


async def ping_handler(client: Client, message: Message) -> None:
    """Ping command to check if bot is alive."""
    try:
        logger.info(f"Ping command received from user {message.from_user.id if message.from_user else 'Unknown'}")
        import time
        start_time = time.time()
        await client.get_me()  # Simple API call to check if bot is responsive
        end_time = time.time()
        latency = round((end_time - start_time) * 1000, 2)
        await message.reply_text(f"🏓 Pong! Bot is alive.\nLatency: {latency}ms")
        logger.info(f"Ping command executed. Latency: {latency}ms")
    except Exception as e:
        logger.error(f"Error in ping command: {e}")
        await message.reply_text("Error executing ping command.")


# Convert SUDO_USERS to a list for filters.user
SUDO_USERS_LIST: List[Union[int, str]] = list(SUDO_USERS) if SUDO_USERS else []


def create_command_handler(command: str, handler_func):
    """Create a command handler with proper sudo user filtering."""
    logger.info(f"Registering command handler for: {command}")
    logger.info(f"SUDO_USERS: {SUDO_USERS}")
    logger.info(f"SUDO_USERS_LIST for filter: {SUDO_USERS_LIST}")
    handler = MessageHandler(
        handler_func,
        filters.command(command, prefixes=".") & filters.user(users=list(SUDO_USERS_LIST))
    )
    logger.info(f"Created handler for command: {command}")
    return handler


async def add_pack_handler(client: Client, message: Message) -> None:
    """Add a new sticker file ID to the list."""
    try:
        if len(message.command) < 2:
            await message.reply_text("Usage: .addpack <sticker_file_id>")
            return
            
        sticker_file_id = message.command[1]
        
        sticker_packs = load_sticker_packs()
        
        # Check if sticker is already in the list
        if sticker_file_id in sticker_packs:
            await message.reply_text("This sticker is already in the list.")
            return
            
        # Add the sticker file ID
        sticker_packs.append(sticker_file_id)
        save_sticker_packs(sticker_packs)
        
        await message.reply_text(f"Added sticker with ID: ...{sticker_file_id[-10:]}")
        logger.info(f"Added sticker file ID: {sticker_file_id}")
    except Exception as e:
        logger.error(f"Error adding sticker: {e}")
        await message.reply_text("Error adding sticker.")


async def stop_automation_handler(client: Client, message: Message) -> None:
    """Stop all automation."""
    global automation_enabled
    automation_enabled = False
    await message.reply_text("Automation stopped.")
    logger.info("Automation stopped by sudo user.")


async def start_automation_handler(client: Client, message: Message) -> None:
    """Resume automation."""
    global automation_enabled
    logger.info(f"Received .on command from user {message.from_user.id if message.from_user else 'Unknown'}")
    logger.info(f"SUDO_USERS: {SUDO_USERS}")
    logger.info(f"SUDO_USERS_LIST: {SUDO_USERS_LIST}")
    logger.info(f"Message text: {message.text}")
    logger.info(f"Message command: {message.command if hasattr(message, 'command') else 'No command attribute'}")
    automation_enabled = True
    await message.reply_text("Automation started.")
    logger.info("Automation started by sudo user.")


async def leave_restricted_handler(client: Client, message: Message) -> None:
    """Leave groups where sending messages is restricted."""
    try:
        left_count = 0
        groups = await get_joined_groups(client)
        
        for group_id in groups:
            try:
                # Try to send a test message
                await client.send_chat_action(group_id, enums.ChatAction.TYPING)
            except ChatWriteForbidden:
                # Leave the group if we can't send messages
                try:
                    await client.leave_chat(group_id)
                    logger.info(f"Left restricted group: {group_id}")
                    left_count += 1
                except Exception as e:
                    logger.error(f"Failed to leave group {group_id}: {e}")
            except Exception as e:
                logger.warning(f"Error checking group {group_id}: {e}")
        
        await message.reply_text(f"Left {left_count} restricted groups.")
    except Exception as e:
        logger.error(f"Error in leave_restricted: {e}")
        await message.reply_text("Error processing request.")


async def broadcast_handler(client: Client, message: Message) -> None:
    """Broadcast a message to all joined groups."""
    try:
        if len(message.command) < 2:
            await message.reply_text("Usage: .broadcast <text>")
            return
            
        text = " ".join(message.command[1:])
        groups = await get_joined_groups(client)
        sent_count = 0
        
        for group_id in groups:
            try:
                await client.send_message(group_id, text)
                sent_count += 1
                logger.info(f"Broadcast message to group: {group_id}")
            except Exception as e:
                logger.error(f"Failed to send message to group {group_id}: {e}")
        
        await message.reply_text(f"Broadcast sent to {sent_count}/{len(groups)} groups.")
    except Exception as e:
        logger.error(f"Error in broadcast: {e}")
        await message.reply_text("Error broadcasting message.")


async def forward_latest_handler(client: Client, message: Message) -> None:
    """Forward the latest message from a channel to all joined groups."""
    try:
        if len(message.command) < 2:
            await message.reply_text("Usage: .forward <channel_id>\nExamples:\n.forward @channelusername\n.forward -1001234567890\n.forward channelname")
            return
            
        channel_id = message.command[1]
        
        # Handle different channel ID formats
        # If it's a username without @, add @
        if not channel_id.startswith("@") and not channel_id.startswith("-"):
            # Check if it's a numeric ID (negative numbers starting with -100)
            if not (channel_id.startswith("-100") and channel_id[1:].isdigit()):
                # For non-numeric IDs, add @ prefix
                if len(channel_id) >= 1 and channel_id.isalnum():
                    channel_id = "@" + channel_id
        
        # Get the latest message from the channel
        latest_message = None
        try:
            # Get the latest message from the channel
            async for msg in client.get_chat_history(channel_id, limit=1): # type: ignore
                latest_message = msg
                break  # Only get the first (latest) message
        except Exception as e:
            logger.error(f"Error getting chat history from {channel_id}: {e}")
            await message.reply_text(f"Error retrieving message from channel {channel_id}: {str(e)}")
            return
        
        # Check if we got a message
        if not latest_message:
            await message.reply_text(f"Could not retrieve message from channel {channel_id} or channel is empty.")
            return
            
        # Get joined groups
        groups = await get_joined_groups(client)
        if not groups:
            await message.reply_text("No joined groups found to forward to.")
            return
            
        # Forward the message to all groups
        forwarded_count = 0
        failed_groups = []
        
        for group_id in groups:
            try:
                await latest_message.forward(group_id)
                forwarded_count += 1
                logger.info(f"Forwarded message to group: {group_id}")
            except Exception as e:
                logger.error(f"Failed to forward message to group {group_id}: {e}")
                failed_groups.append(str(group_id))
        
        response_text = f"Message forwarded to {forwarded_count}/{len(groups)} groups."
        if failed_groups:
            response_text += f"\nFailed groups: {', '.join(failed_groups[:5])}"  # Show first 5 failures
            if len(failed_groups) > 5:
                response_text += f" and {len(failed_groups) - 5} more..."
                
        await message.reply_text(response_text)
        
    except PeerIdInvalid:
        await message.reply_text("Invalid channel ID. Please check the channel username or ID.\nExamples:\n.forward @channelusername\n.forward -1001234567890\n.forward channelname")
    except Exception as e:
        logger.error(f"Error in forward: {e}")
        await message.reply_text(f"Error forwarding message: {str(e)}")


async def share_post_link_handler(client: Client, message: Message) -> None:
    """Share a post with its link to all joined groups."""
    try:
        if len(message.command) < 2:
            await message.reply_text("Usage: .share <channel_id>\nExamples:\n.share @channelusername\n.share -1001234567890\n.share channelname\n\nFor specific posts: .s https://t.me/channel/123")
            return
            
        channel_id = message.command[1]
        
        # Handle different channel ID formats
        # If it's a username without @, add @
        if not channel_id.startswith("@") and not channel_id.startswith("-"):
            # Check if it's a numeric ID (negative numbers starting with -100)
            if not (channel_id.startswith("-100") and channel_id[1:].isdigit()):
                # For non-numeric IDs, add @ prefix
                if len(channel_id) >= 1 and channel_id.isalnum():
                    channel_id = "@" + channel_id
        
        # Get the latest message from the channel
        latest_message = None
        try:
            # Get the latest message from the channel
            async for msg in client.get_chat_history(channel_id, limit=1): # type: ignore
                latest_message = msg
                break  # Only get the first (latest) message
        except Exception as e:
            logger.error(f"Error getting chat history from {channel_id}: {e}")
            await message.reply_text(f"Error retrieving message from channel {channel_id}: {str(e)}")
            return
        
        # Check if we got a message
        if not latest_message:
            await message.reply_text(f"Could not retrieve message from channel {channel_id} or channel is empty.")
            return
            
        # Get the message link
        try:
            message_link = f"https://t.me/{channel_id.lstrip('@')}/{latest_message.id}"
            if channel_id.startswith("-100"):  # Supergroup/channel with ID
                # Extract the actual channel username or use the ID format
                chat_info = await client.get_chat(channel_id)
                # Check if chat_info has username attribute and it's not None
                username = getattr(chat_info, 'username', None)
                if username:
                    message_link = f"https://t.me/{username}/{latest_message.id}"
                else:
                    # For private channels, we might need to use the message ID differently
                    # Check if chat_info is of a type that has an id attribute
                    chat_id = getattr(chat_info, 'id', None)
                    if chat_id:
                        clean_id = str(chat_id).lstrip('-100') if str(chat_id).startswith('-100') else str(chat_id)
                        message_link = f"https://t.me/c/{clean_id}/{latest_message.id}"
        except Exception as e:
            logger.warning(f"Could not generate message link: {e}")
            message_link = "Link not available"
        
        # Create the share text with the message link
        share_text = f"Check out this post:\n\n{message_link}"
        
        # Add message content if available
        if latest_message.text:
            # Truncate text if it's too long
            content = latest_message.text[:200] + "..." if len(latest_message.text) > 200 else latest_message.text
            share_text = f"Check out this post:\n\n{content}\n\n{message_link}"
        elif latest_message.caption:
            # For media with captions
            caption = latest_message.caption[:200] + "..." if len(latest_message.caption) > 200 else latest_message.caption
            share_text = f"Check out this post:\n\n{caption}\n\n{message_link}"
            
        # Get joined groups
        groups = await get_joined_groups(client)
        if not groups:
            await message.reply_text("No joined groups found to share to.")
            return
            
        # Share the post link to all groups
        shared_count = 0
        failed_groups = []
        
        for group_id in groups:
            try:
                await client.send_message(group_id, share_text)
            except Exception as e:
                logger.error(f"Failed to share post link to group {group_id}: {e}")
                failed_groups.append(str(group_id))
            else:
                shared_count += 1
                logger.info(f"Shared post link to group: {group_id}")
        
        response_text = f"Post shared to {shared_count}/{len(groups)} groups."
        if failed_groups:
            response_text += f"\nFailed groups: {', '.join(failed_groups[:5])}"  # Show first 5 failures
            if len(failed_groups) > 5:
                response_text += f" and {len(failed_groups) - 5} more..."
                
        await message.reply_text(response_text)
        
    except PeerIdInvalid:
        await message.reply_text("Invalid channel ID. Please check the channel username or ID.\nExamples:\n.share @channelusername\n.share -1001234567890\n.share channelname")
    except Exception as e:
        logger.error(f"Error in share post: {e}")
        await message.reply_text(f"Error sharing post: {str(e)}")


async def share_post_by_link_handler(client: Client, message: Message) -> None:
    """Forward a specific post to all joined groups."""
    try:
        logger.info(f"share_post_by_link_handler called with command: {message.command}")
        logger.info(f"Command received from user: {message.from_user.id if message.from_user else 'Unknown'}")
        if len(message.command) < 2:
            await message.reply_text("Usage: .sharelink or .s <message_link>\nExample: .s https://t.me/globalcryptogang/2354")
            return
        
        # Parse the message link
        message_link = message.command[1]
        logger.info(f"Parsing message link: {message_link}")
        
        # Validate and parse the link
        # Expected format: https://t.me/channel_name/message_id or https://t.me/c/channel_id/message_id
        link_pattern = r'https?://t\.me/(?:c/)?([^/]+)/(\d+)'
        match = re.match(link_pattern, message_link)
        
        if not match:
            await message.reply_text("Invalid message link format. Please use: https://t.me/channel_name/message_id")
            return
        
        channel_identifier = match.group(1)
        message_id = int(match.group(2))
        logger.info(f"Parsed channel_identifier: {channel_identifier}, message_id: {message_id}")
        
        # Determine if it's a username or channel ID
        if channel_identifier.isdigit():
            # It's a private channel ID (without -100 prefix)
            channel_id = f"-100{channel_identifier}"
        else:
            # It's a public channel username
            channel_id = f"@{channel_identifier}"
        logger.info(f"Determined channel_id: {channel_id}")
        
        # Get the specific message
        try:
            target_message = await client.get_messages(channel_id, message_id)
            # Handle the case where get_messages might return a list
            if isinstance(target_message, list):
                target_message = target_message[0] if target_message else None
        except Exception as e:
            logger.error(f"Error getting message {message_id} from {channel_id}: {e}")
            await message.reply_text(f"Error retrieving message: {str(e)}")
            return
        
        if not target_message:
            await message.reply_text("Could not retrieve the specified message.")
            return
        
        # Get joined groups
        groups = await get_joined_groups(client)
        if not groups:
            await message.reply_text("No joined groups found to forward to.")
            return
        
        # Forward the message to all groups
        forwarded_count = 0
        failed_groups = []
        
        for group_id in groups:
            try:
                await target_message.forward(group_id)
                forwarded_count += 1
                logger.info(f"Forwarded message to group: {group_id}")
            except Exception as e:
                logger.error(f"Failed to forward message to group {group_id}: {e}")
                failed_groups.append(str(group_id))
        
        response_text = f"Message forwarded to {forwarded_count}/{len(groups)} groups."
        if failed_groups:
            response_text += f"\nFailed groups: {', '.join(failed_groups[:5])}"  # Show first 5 failures
            if len(failed_groups) > 5:
                response_text += f" and {len(failed_groups) - 5} more..."
                
        await message.reply_text(response_text)
        
    except Exception as e:
        logger.error(f"Error in share post by link: {e}")
        await message.reply_text(f"Error forwarding post: {str(e)}")


async def main():
    """Main function to run the userbot."""
    # Validate API credentials
    if not API_ID or not API_HASH:
        logger.error("API_ID and API_HASH must be set in the .env file")
        return
    
    # Create the Pyrogram client
    app = Client(
        SESSION_NAME,
        api_id=API_ID,
        api_hash=API_HASH,
        workers=20  # Increase workers for better performance
    )
    
    # Register the message handler for reactions
    app.add_handler(MessageHandler(
        react_to_messages,
        filters.group & ~filters.service
    ))
    
    # Register command handlers FIRST to ensure they are processed before auto_join_groups
    logger.info(f"Registered SUDO_USERS: {SUDO_USERS}")
    logger.info(f"Registered SUDO_USERS_LIST: {SUDO_USERS_LIST}")
    
    # Register command handlers
    logger.info("Registering command handlers...")
    app.add_handler(create_command_handler("addpack", add_pack_handler))
    app.add_handler(create_command_handler("off", stop_automation_handler))
    app.add_handler(create_command_handler("on", start_automation_handler))
    app.add_handler(create_command_handler("leave_restricted", leave_restricted_handler))
    app.add_handler(create_command_handler("broadcast", broadcast_handler))
    app.add_handler(create_command_handler("forward", forward_latest_handler))
    app.add_handler(create_command_handler("share", share_post_link_handler))  # Share latest post
    app.add_handler(create_command_handler("sharelink", share_post_by_link_handler))  # Share specific post by link
    app.add_handler(create_command_handler("s", share_post_by_link_handler))  # Short alias for sharelink
    app.add_handler(create_command_handler("getsticker", get_sticker_id_handler))
    app.add_handler(create_command_handler("join", join_groups_handler))
    app.add_handler(create_command_handler("enablereact", enable_reactions_handler))
    app.add_handler(create_command_handler("disablereact", disable_reactions_handler))
    app.add_handler(create_command_handler("enableautojoin", enable_autojoin_handler))
    app.add_handler(create_command_handler("disableautojoin", disable_autojoin_handler))
    app.add_handler(create_command_handler("ping", ping_handler))
    logger.info("All command handlers registered.")
    
    # Register the message handler for auto-joining groups (AFTER command handlers)
    app.add_handler(MessageHandler(
        auto_join_groups,
        (filters.text | filters.caption) & filters.user(users=list(SUDO_USERS_LIST))
    ))
    
    logger.info("Starting userbot...")
    await app.start()
    
    # Get userbot info
    me = await app.get_me()
    logger.info(f"Userbot started as @{me.username} ({me.first_name})")
    
    # Start the sticker sending loop in the background
    asyncio.create_task(send_random_sticker(app))
    
    logger.info("Userbot is now running. Press Ctrl+C to stop.")
    logger.info("Default settings - Sticker sending: OFF, Reactions: OFF, Auto-join: ON")
    
    # Keep the bot running
    try:
        while True:
            await asyncio.sleep(30)
    except KeyboardInterrupt:
        logger.info("Stopping userbot...")
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())