import discord
# Modern OpenAI SDK import:
from openai import OpenAI
import db_logger
from discord.ext import commands
from dotenv import load_dotenv
import os
import asyncio
from datetime import datetime, timedelta, timezone

# Load environment variables
load_dotenv(dotenv_path='environmental/.env')

# ---- OpenAI client (v1+) ----
# Looks for OPENAI_KEY first, then OPENAI_API_KEY as a fallback
client = OpenAI(
    api_key=os.getenv('OPENAI_KEY') or os.getenv('OPENAI_API_KEY'),
    organization=os.getenv('OPENAI_ORG')  # optional
)

# Choose your model centrally (env override supported)
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)

# ================= Conversation memory with TTL =================
SYSTEM_PROMPT = (
    "You are Gronk, a helpful Discord assistant. "
    "Be concise, clear, and friendly. Use markdown when helpful."
)

MAX_TURNS = 12                          # keep last ~12 user/assistant turns
CONVO_TTL = timedelta(hours=2)          # flush after 2 hours of inactivity
CLEANUP_PERIOD = 300                    # seconds (5 min)

# convos[root_id] = {"history": [...], "last_active": datetime, "channel_id": int}
convos = {}
# map any bot message id in a convo back to its root id
msg_to_root = {}

def utcnow():
    return datetime.now(timezone.utc)

def trim_history(history, max_turns=MAX_TURNS):
    """Keep system + last N user/assistant turns."""
    sys = [m for m in history if m["role"] == "system"][:1]
    rest = [m for m in history if m["role"] != "system"][-2*max_turns:]
    return sys + rest

def is_expired(root_id):
    meta = convos.get(root_id)
    if not meta:
        return True
    return utcnow() - meta["last_active"] > CONVO_TTL

def touch(root_id):
    if root_id in convos:
        convos[root_id]["last_active"] = utcnow()

async def cleanup_conversations_task():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            now = utcnow()
            to_delete = []
            for root_id, meta in list(convos.items()):
                if now - meta["last_active"] > CONVO_TTL:
                    to_delete.append(root_id)

            # Purge expired convos
            for root_id in to_delete:
                del convos[root_id]
                # remove any msg_to_root entries that map to this root
                for mid in [k for k, v in list(msg_to_root.items()) if v == root_id]:
                    del msg_to_root[mid]
        except Exception as e:
            print(f"[cleanup] error: {e}")

        await asyncio.sleep(CLEANUP_PERIOD)

async def send_long_message(channel, content):
    # Discord hard limit ~2000 chars
    for i in range(0, len(content), 2000):
        await channel.send(content[i:i + 2000])

# ---- LLM helper using modern client ----
def llm_reply(history):
    """
    history: list of {"role": "system"|"user"|"assistant", "content": "..."}
    returns: string reply
    """
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=trim_history(history),
        temperature=0.9,
        max_tokens=1024,
    )
    return resp.choices[0].message.content if resp.choices else "No response from OpenAI."

# ================== Slash command: start a new conversation ==================
@bot.tree.command(name='askgronk', description="Talk to Gronk, he can probably help")
async def AskGronk(interaction: discord.Interaction, message: str):
    await interaction.response.defer(thinking=True)
    try:
        # New conversation history
        history = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ]

        reply = llm_reply(history)

        # Log
        user_name = interaction.user.display_name
        server_location = interaction.guild.name
        channel_location = interaction.channel.name
        db_logger.log_message(user_name, message, reply, server_location, channel_location)

        # Send + capture the bot's message id as the root of this conversation
        if len(reply) > 2000:
            sent_msg = await interaction.followup.send(reply[:2000])
            await send_long_message(interaction.channel, reply[2000:])
        else:
            sent_msg = await interaction.followup.send(reply)

        root_id = sent_msg.id

        history.append({"role": "assistant", "content": reply})
        convos[root_id] = {
            "history": trim_history(history),
            "last_active": utcnow(),
            "channel_id": interaction.channel.id,
        }
        msg_to_root[root_id] = root_id

        print(f"user: {user_name}\nbot: {reply[:120]}...\nServer: {server_location}, Channel: {channel_location}")

    except Exception as e:
        print(f"Error: {e}")
        try:
            await interaction.followup.send("There was an error processing your request.")
        except Exception:
            pass

# ================== Reply-to-continue handler with TTL ==================
@bot.event
async def on_message(message: discord.Message):
    # Ignore bots
    if message.author.bot:
        return

    # If user replies to a bot message, continue that conversation (if not expired)
    if message.reference and (message.reference.resolved or message.reference.message_id):
        try:
            ref = message.reference.resolved
            if not ref:
                ref = await message.channel.fetch_message(message.reference.message_id)
        except Exception:
            ref = None

        if ref and ref.author.id == bot.user.id:
            # Identify the root conversation id for this referenced bot message
            root_id = msg_to_root.get(ref.id, ref.id)

            # Start fresh if expired or missing; else continue
            if is_expired(root_id):
                # Fresh history using the referenced bot content as the prior assistant turn
                history = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "assistant", "content": ref.content},
                    {"role": "user", "content": message.content},
                ]
            else:
                # Continue existing history
                meta = convos[root_id]
                history = meta["history"] + [{"role": "user", "content": message.content}]

            try:
                reply = llm_reply(history)
            except Exception as e:
                print(f"OpenAI error: {e}")
                await message.reply("Sorry, I hit an error talking to OpenAI.")
                return

            # Send reply (split if needed)
            if len(reply) > 2000:
                sent = await message.reply(reply[:2000])
                await send_long_message(message.channel, reply[2000:])
            else:
                sent = await message.reply(reply)

            # Update memory (fresh or continued)
            history.append({"role": "assistant", "content": reply})
            convos[root_id] = {
                "history": trim_history(history),
                "last_active": utcnow(),
                "channel_id": message.channel.id,
            }
            # Any bot message in this convo maps back to the same root
            msg_to_root[sent.id] = root_id
            msg_to_root[ref.id] = root_id

            # Log this turn (best-effort)
            try:
                db_logger.log_message(
                    message.author.display_name,
                    message.content,
                    reply,
                    message.guild.name if message.guild else "DM",
                    getattr(message.channel, "name", "DM"),
                )
            except Exception as e:
                print(f"DB log error: {e}")

            return  # don't fall through to command processing

    # Allow normal commands to work
    await bot.process_commands(message)

# ================== Bot lifecycle ==================
@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print(f'Logged in as {bot.user}')
        print('slash commands registered')
    except Exception as e:
        print(f"Error syncing commands: {e}")

    # Start cleanup loop once
    if not hasattr(bot, "_cleanup_task"):
        bot._cleanup_task = asyncio.create_task(cleanup_conversations_task())

async def main():
    async with bot:
        await bot.start(os.getenv('DISCORD_TOKEN'))

try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("Bot shutting down.")
