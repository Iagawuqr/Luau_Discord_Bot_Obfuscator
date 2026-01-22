# Lua Obfuscator Discord Bot

## Overview
A Discord bot that obfuscates Lua scripts. Users can send Lua files to the bot with the `!obfuscate` command, and the bot will return an obfuscated version of the script.

## Project Structure
```
.
├── bot.py              # Main Discord bot logic
├── keep_alive.py       # Flask web server for keep-alive functionality
├── obfuscate.lua       # Lua obfuscation logic
├── module.lua          # Obfuscation module
├── bin/                # Luvit binary for running Lua
├── uploads/            # Temporary storage for uploaded files
├── obfuscated/         # Output directory for obfuscated files
└── requirements.txt    # Python dependencies
```

## How It Works
1. Users send a `.lua` or `.txt` file with the `!obfuscate` command in Discord
2. The bot downloads the file and processes it through the Lua obfuscator
3. The obfuscated result is sent back to the user

## Configuration
- **DISCORD_TOKEN**: Required environment secret for Discord bot authentication
- Flask server runs on port 5000 to keep the bot alive

## Running the Bot
The bot is started via `python bot.py` which:
1. Starts the Flask keep-alive server on port 5000
2. Connects to Discord using the bot token
3. Listens for `!obfuscate` commands

## Dependencies
- discord.py 1.7.3
- Flask 3.x
- requests
- Luvit (Lua runtime in bin/)
