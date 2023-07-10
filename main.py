#!/usr/bin/env python

"""
Discord bot for doing stuff with radarr [etc.]
"""

import logging
import os
from typing import Optional

import discord
from discord.ext import commands
from dotenv import dotenv_values

from radarr import Radarr, radarr_help_text

logger = logging.getLogger(__name__)

ENV_FILE = os.path.join(os.path.dirname(__file__), "config.env")


class Vars:
    def __init__(self):
        self._vars = dotenv_values(ENV_FILE)
        self.radarr_url = self._vars.get('RADARR_URL')
        self.radarr_api_key = self._vars.get('RADARR_API_KEY')
        self.discord_token = self._vars.get('DISCORD_TOKEN')
        self.discord_channel = self._vars.get('DISCORD_CHANNEL', None)
        self.log_level = self._vars.get('LOG_LEVEL', 'INFO').upper()


# Declare the discord bot up front
INTENTS = discord.Intents.default()
INTENTS.message_content = True
BOT = commands.Bot(
    command_prefix='!',
    intents=INTENTS,
    description="Discord bot for doing stuff with radarr [etc.]",
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

    if VARS.discord_channel is not None and ctx.channel.name != VARS.discord_channel:
        logger.info(f"ignoring channel {ctx.channel.name}")
        return

    logger.info("running radarr command: %s", cmd)
    # logger.info(f"ctx = {ctx}")
    # logger.info(f"user = {ctx.author}")
    # logger.info(f"cmd = {cmd}")
    # logger.info(f"args = {args}")

    # Default command is status
    if cmd is None:
        cmd = 'status'

    # Help - list commands
    if cmd == 'help':
        for text in radarr_help_text():
            await ctx.author.send(f"`{text}`")

    # Status - list summary of movies
    elif cmd == 'status':
        for text in RADARR.status(*args):
            await ctx.send(f"`{text}`")

    # List - list all movies
    elif cmd == 'list':
        for text in RADARR.list(*args):
            await ctx.author.send(f"`{text}`")

    # Me - list movies tagged with user
    elif cmd == 'me':
        for text in RADARR.me(ctx.author.name, *args):
            await ctx.author.send(f"`{text}`")

    # Tag
    elif cmd == 'tag':
        text = RADARR.tag(ctx.author.name, *args)
        await ctx.author.send(f"`{text}`")

    # Untag
    elif cmd == 'untag':
        text = RADARR.untag(ctx.author.name, *args)
        await ctx.author.send(f"`{text}`")

    # Search
    elif cmd == 'search':
        for text in RADARR.search(*args):
            await ctx.author.send(f"`{text}`")

    # Add movie
    elif cmd == 'add':
        for text in RADARR.add_movie(ctx.author.name, *args):
            await ctx.author.send(f"`{text}`")

    else:
        await ctx.send(f"`Unknown command {cmd}`")


if __name__ == '__main__':
    VARS = Vars()
    logging.basicConfig(level=VARS.log_level)
    RADARR = Radarr(VARS.radarr_url, VARS.radarr_api_key)
    BOT.run(VARS.discord_token)
