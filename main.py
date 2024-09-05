import discord
import openai
from dotenv import load_dotenv
import os


load_dotenv(dotenv_path = 'environmental/.env')

openai.api_key = os.getenv('OPENAI_KEY')

openai.organization = os.getenv('OPENAI_ORG')

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents = intents)

@client.event
async def onMessage(message):
    try:
        if message.author_bot:
            return 
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": message.content}],
            max_tokens=30,
            temperature=0.7,
            stop=["Mantis Toboggan, M.D.:", "BigDon(g)"],
        )

        reply = response.choices[0].message['content']

        print(f"user: {message.content}")
        print(f"bot: {reply}")

        await message.channel.send(reply)