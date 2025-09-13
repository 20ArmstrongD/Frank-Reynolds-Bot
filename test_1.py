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


# Slash command for talking to the bot and triggering it
@bot.tree.command(name='AskGronk', description="Talk to Gronk, he can probably help")
async def AskGronk(interaction: discord.Interaction, message: str):

    await interaction.response.defer(thinking=True)  # Acknowledge within 3 seconds

    try:
        # Call OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": message}],
            max_tokens=4096,
            temperature=0.9,
            stop=["Mantis Toboggan, M.D.:"],
        )

        if response.choices:
            reply = response.choices[0].message.content
        else:
            reply = "No response from OpenAI."

        user_name = interaction.user.display_name 
        server_location = interaction.guild.name
        channel_location = interaction.channel.name

        # Log to database
        db_logger.log_message(user_name, message, reply, server_location, channel_location)

        # Send the response back to Discord
        await interaction.followup.send(reply)

        print(f"user: {user_name}")
        print(f"bot: {reply}")
        print(f"Server: {server_location}, Channel: {channel_location}")
    except Exception as e:
        print(f"Error: {e}")
        await interaction.followup.send("There was an error processing your request.")


# Logging into Discord 
@bot.event
async def on_ready():
    
    try:
        await bot.tree.sync()  # Sync slash commands
        print(f'Logged in as {bot.user}')
        print(f' slash commands registered')
    except Exception as e:
        print(f"Error syncing commands: {e}")

# Main function to run the bot
async def main():
    async with bot:
        await bot.start(os.getenv('DISCORD_TOKEN'))

# Execute the main function with asyncio
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("Bot shutting down.")