#!/usr/bin/env python

"""
Discord bot for doing stuff with *arrs
"""

import logging
import os
from typing import Optional

import discord
from discord.ext import commands
from dotenv import load_dotenv

from radarr import Radarr

logger = logging.getLogger(__name__)

ENV_FILE = os.path.join(os.path.dirname(__file__), "config.env")


class Vars:
    def __init__(self):
        self.radarr_url = os.getenv('RADARR_URL')
        self.radarr_api_key = os.getenv('RADARR_API_KEY')
        self.discord_token = os.getenv('DISCORD_TOKEN')


# Declare the discord bot up front
INTENTS = discord.Intents.default()
INTENTS.message_content = True
BOT = commands.Bot(
    command_prefix='!',
    intents=INTENTS,
    description="Discord bot for doing stuff with *arrs",
    help_command=None
)


@BOT.event
async def on_ready():
    """count connect guilds (servers) on startup"""
    guild_count = 0

    for guild in BOT.guilds:
        print(f"- {guild.id} (name: {guild.name})")
        guild_count = guild_count + 1

    print(f"- In {guild_count} guilds")


@BOT.command()
async def radarr(ctx: commands.Context, cmd: Optional[str] = None, *args):
    """radarr command"""

    logger.info("running radarr command")
    # logger.info(f"ctx = {ctx}")
    # logger.info(f"user = {ctx.author}")
    # logger.info(f"cmd = {cmd}")
    # logger.info(f"args = {args}")

    # Default command is status
    if cmd is None:
        cmd = 'status'

    # Commands

    # Help - list commands
    if cmd == 'help':
        help_message = \
"""!radarr [ status | list | me | tag <id> | untag <id> ]
    status - show status of radarr
    list [search terms] - list all movies in radarr
    me [search times] - show movies tagged with your discord username
    tag <id> - tag a movie with your discord username
    untag <id> - untag a movie with your discord username
      
If search terms are provided then the #10 matches are shown."""

        await ctx.author.send(f"`{help_message}`")

    # Status - list summary of movies
    elif cmd == 'status':
        text = RADARR.status()
        await ctx.send(f"`{text}`")

    # List - list all movies
    elif cmd == 'list':
        for text in RADARR.list(*args):
            await ctx.author.send(f"`{text}`")

    # Me - list movies tagged with user
    elif cmd == 'me':
        text = RADARR.me(ctx.author.name, *args)
        await ctx.author.send(f"`{text}`")

    # Tag
    elif cmd == 'tag':
        text = RADARR.tag(ctx.author.name, *args)
        await ctx.send(f"`{text}`")

    # Untag
    elif cmd == 'untag':
        text = RADARR.untag(ctx.author.name, *args)
        await ctx.send(f"`{text}`")

    else:
        await ctx.send(f"`Unknown command {cmd}`")


if __name__ == '__main__':
    load_dotenv(ENV_FILE)
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    logging.basicConfig(level=log_level)
    VARS = Vars()
    RADARR = Radarr(VARS.radarr_url, VARS.radarr_api_key)
    BOT.run(VARS.discord_token)
