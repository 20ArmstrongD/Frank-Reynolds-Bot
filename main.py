import discord
import openai
import db_logger
from discord.ext import commands
from dotenv import load_dotenv
import os
import asyncio

# Load environment variables
load_dotenv(dotenv_path='environmental/.env')

# Establish OpenAI credentials
openai.api_key = os.getenv('OPENAI_KEY')
openai.organization = os.getenv('OPENAI_ORG')

# Setting up intents 
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)

# To send long messages in chunks
async def send_long_message(channel, content):
    for i in range(0, len(content), 2000):
        await channel.send(content[i:i + 2000])

# Global variable to track the bot's state
is_online = False

# Slash command for talking to the bot and triggering it
@bot.tree.command(name='chat', description="Talk to Dr. Toboggan, he can help")
async def chat(interaction: discord.Interaction, message: str):
    global is_online
    if not is_online:
        await interaction.response.send_message("The bot is currently restarting, please try again later.")
        return

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": message}],
            max_tokens=300,
            temperature=0.7,
            stop=["Mantis Toboggan, M.D.:"],
        )

        print(f"OpenAI Response: {response}")

        if response.choices:
            reply = response.choices[0].message.content
        else:
            reply = "No response from OpenAI."

        user_name = interaction.user.nick if interaction.user.nick else interaction.user.name
        server_location = interaction.guild.name
        channel_location = interaction.channel.name

        db_logger.log_message(user_name, message, reply, server_location, channel_location)

        await interaction.response.send_message(reply)

        print(f"user: {user_name}")
        print(f"bot: {reply}")
        print(f"Server: {server_location}, Channel: {channel_location}")
        print(f"Full OpenAI Response: {response}")

    except commands.CommandOnCooldown:
        await interaction.response.send_message("Please wait before using this command again.")
    except Exception as e:
        print(f"Error: {e}")
        await interaction.response.send_message("There was an error processing your request.")

# Command to check the bot's status
@bot.tree.command(name='status', description="Check if the bot is online or offline")
async def status(interaction: discord.Interaction):
    global is_online
    if is_online:
        await interaction.response.send_message("The bot is currently online and ready to assist!")
    else:
        await interaction.response.send_message("The bot is currently offline. Please try again later.")

# Logging into Discord 
@bot.event
async def on_ready():
    global is_online
    is_online = True  # Set the bot state to online when it is ready
    await bot.tree.sync()
    print(f'Logged in as {bot.user}')
    print(f'/chat slash command registered')

@bot.event
async def on_disconnect():
    global is_online
    is_online = False  # Set the bot state to offline when it disconnects

# Main function to run the bot
async def main():
    async with bot:
        await bot.start(os.getenv('DISCORD_TOKEN'))

# Execute the main function with asyncio
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("Bot shutting down.")