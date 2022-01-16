import discord
from discord.ext import commands

import os
from dotenv import load_dotenv
load_dotenv()
TOKEN = os.getenv('TOKEN')

bot = commands.Bot(command_prefix='$', help_command=None)

@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.listening, name="$help"))
    print(f'{bot.user} has logged in.')
    bot.load_extension('cogs.musicAPI')

bot.run(TOKEN)