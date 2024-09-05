import discord
import openai
import db_logger
from discord.ext import commands
from dotenv import load_dotenv
import os

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
    # Split the message into chunks of 2000 characters or less
    for i in range(0, len(content), 2000):
        await channel.send(content[i:i + 2000])

# Slash command for talking to the bot and triggering it
@bot.tree.command(name='chat', description="Talk to Dr. Toboggan, he can help")
async def chat(interaction: discord.Interaction, message: str):
    try:
        # Parameters for response body using the correct API
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": message}],  # Use message directly
            max_tokens=300,
            temperature=0.7,
            stop=["Mantis Toboggan, M.D.:"],  # Adjust as necessary
        )
        
        # Debug log the entire response to inspect its structure
        print(f"OpenAI Response: {response}")

        # OpenAI response
        if response.choices:  # Check if there are choices
            reply = response.choices[0].message.content
        else:
            reply = "No response from OpenAI."

        # Get the user's nickname or fallback to username
        user_name = interaction.user.nick if interaction.user.nick else interaction.user.name
        
        # Get server and channel location
        server_location = interaction.guild.name  # Get the server name
        channel_location = interaction.channel.name  # Get the channel name

        # Log message and response data to the database using the nickname
        db_logger.log_message(user_name, message, reply, server_location, channel_location)

        # Send the AI response directly to the user who invoked the command
        await interaction.response.send_message(reply)  # Respond to the user only

        # # Send the entire OpenAI response to the Discord channel
        # await send_long_message(interaction.channel, f"Full OpenAI Response: {response}")  # Send full response

        # Console log statements for debug purposes
        print(f"user: {user_name}")
        print(f"bot: {reply}")
        print(f"Server: {server_location}, Channel: {channel_location}")
        print(f"Full OpenAI Response: {response}")

    except commands.CommandOnCooldown:
        await interaction.response.send_message("Please wait before using this command again.")
    except Exception as e: 
        print(f"Error: {e}")
        await interaction.response.send_message("There was an error processing your request.")

# Logging into Discord 
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Logged in as {bot.user}')
    print(f'/chat slash command registered')

bot.run(os.getenv('DISCORD_TOKEN'))
