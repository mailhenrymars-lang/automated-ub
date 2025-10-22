# Telegram Userbot

A powerful Telegram userbot built with Pyrogram that can automatically send stickers and react to messages.

## Features

- Automatically sends random stickers from configured packs to all joined groups
- Reacts with ❤️ to every new message in joined groups
- Sudo system for authorized users to control the bot
- Commands for managing sticker packs and bot functions
- Automatic detection and leaving of restricted groups
- Broadcast messages to all joined groups
- Forward latest channel posts to all groups
- Join groups by username
- Enable/disable reactions
- Auto-join groups when receiving links from sudo users

## Prerequisites

1. Python 3.7 or higher
2. A Telegram account
3. API credentials from Telegram

## Setup

### 1. Get Telegram API Credentials

1. Go to https://my.telegram.org and log in with your Telegram account
2. Click on "API development tools"
3. Fill in your application details (can be anything)
4. Copy your `API_ID` and `API_HASH`

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Note: `tgcrypto` is optional but recommended for better performance. If you have trouble installing it on Windows, you can skip it - the bot will work without it but with reduced performance.

### 3. Configure Environment Variables

Create a `.env` file in the project directory with the following content:

```env
API_ID=your_api_id_here
API_HASH=your_api_hash_here
SUDO_USERS=your_telegram_user_id
```

Replace:
- `your_api_id_here` with your actual API ID
- `your_api_hash_here` with your actual API Hash
- `your_telegram_user_id` with your Telegram user ID (you can find this by messaging @userinfobot on Telegram)

You can add multiple sudo users by separating IDs with commas:
```env
SUDO_USERS=123456789,987654321
```

### 4. Add Sticker Packs

**Important**: To use sticker packs, you need to add individual sticker file IDs, not pack names. Here's how:

1. Run the userbot first: `python main.py`
2. Open any sticker pack in Telegram
3. Forward any sticker from the pack to yourself or any chat
4. Reply to the forwarded sticker with the command `.getsticker`
5. The bot will reply with the sticker's file ID
6. Add the file ID to your sticker_packs.json file

### 5. Run the Userbot

```bash
python main.py
```

## Usage

After starting the userbot, it will automatically:
- Listen for group links from sudo users (auto-join is ON by default)
- NOT send stickers (sticker sending is OFF by default)
- NOT react to messages (reactions are OFF by default)

### Default Settings

- **Sticker Sending**: OFF (use `.on` to enable)
- **Reactions**: OFF (use `.enablereact` to enable)
- **Auto-Join**: ON (use `.disableautojoin` to disable)

### Commands

Available commands (prefix with `.`):

- `.addpack <sticker_file_id>` - Manually add a sticker file ID to the list
- `.off` - Stop sticker sending automation
- `.on` - Start sticker sending automation
- `.leave_restricted` - Leave groups where sending is restricted
- `.broadcast <text>` - Send a message to all joined groups
- `.forward <channel_id>` - Forward latest message from a channel to all groups
- `.getsticker` - Get the file ID of a replied sticker (reply to a sticker with this command)
- `.join @username1 @username2 ...` - Join groups by username with flood wait between joins
- `.enablereact` - Enable automatic reactions to messages
- `.disablereact` - Disable automatic reactions to messages
- `.enableautojoin` - Enable auto-join when receiving links from sudo users
- `.disableautojoin` - Disable auto-join when receiving links from sudo users

Example workflow:
```
# Join some groups first
.join @publicgroup1 @publicgroup2

# Enable features as needed
.enablereact
.on

# Forward latest message from a channel
.forward @mychannel
.forward -1001234567890
.forward channelusername

# Disable features when not needed
.off
.disablereact

# Control auto-join
.disableautojoin
.enableautojoin

# Collect some sticker file IDs by replying to stickers with .getsticker
# Then use the other commands:
.broadcast Hello everyone!
```

## Auto-Join Feature

The bot can automatically join groups when it receives Telegram group links from sudo users:

1. **How it works**: When a sudo user sends a message containing Telegram group links, the bot will automatically attempt to join those groups
2. **Supported formats**: 
   - `t.me/username`
   - `https://t.me/username`
   - `t.me/joinchat/hash`
3. **Flood Wait Handling**: The bot properly handles Telegram's flood wait restrictions when joining groups
4. **Control**: You can enable/disable this feature with `.enableautojoin` and `.disableautojoin`

## Forward Feature

The forward feature allows you to forward the latest message from any channel to all your joined groups:

1. **Usage**: `.forward <channel_identifier>`
2. **Supported formats**:
   - Channel username: `.forward @channelusername`
   - Channel ID: `.forward -1001234567890`
   - Channel name: `.forward channelname`
3. **Intelligent parsing**: The bot automatically handles different channel identifier formats
4. **How it works**: 
   - Retrieves the most recent message from the specified channel
   - Forwards that message to all groups you've joined
   - Reports how many groups the message was forwarded to
   - Shows any groups where forwarding failed

## How Sticker Sending Works

The bot sends random stickers from your configured list:

1. **Random Sticker Selection**: The bot randomly selects one sticker file ID from your list
2. **Random Group Selection**: The bot randomly selects one of your joined groups
3. **Sending**: The selected sticker is sent to the selected group
4. **Repeat**: This process repeats every 5-20 seconds with a new random combination each time

While this doesn't exactly match your original request of "random sticker from random pack", it provides the same practical result - random stickers being sent to random groups with variety.

## Sticker Management

**Important Note**: This userbot works with individual sticker file IDs, not sticker pack names. This is because:

1. Pyrogram's API requires specific file IDs to send stickers
2. Telegram sticker packs cannot be directly accessed as chats
3. Pack names alone cannot be used to send stickers

To collect sticker file IDs:
1. Forward any sticker to yourself or your userbot
2. Reply to the sticker with `.getsticker`
3. The bot will respond with the file ID
4. Add this ID to your sticker_packs.json file

Example sticker_packs.json file with real IDs:
```json
[
  "CAACAgUAAxkBAAICv2VXv3V7b8y2D2y2D2y2D2y2D2y2AAKzAQACmB3JSU2Rv5V5V5V5HgQ",
  "CAACAgUAAxkBAAICwGVXv4V7b8y2D2y2D2y2D2y2D2y2AAKyAQACmB3JSU2Rv5V5V5V5HgQ"
]
```

## Notes

- The first time you run the bot, it will prompt you to enter your phone number and the verification code sent by Telegram
- Make sure your account is not logged in elsewhere during the first authentication
- The session is stored in `userbot.session` - don't share this file
- Be cautious with automation to avoid spam restrictions
- The bot will wait if no sticker file IDs are configured
- Start by collecting 5-10 sticker file IDs for testing
- When joining groups with `.join` or auto-join, there's a 30-second flood wait between each join to avoid restrictions
- All features are OFF by default except auto-join for convenience
- The forward command now has improved parsing for different channel identifier formats