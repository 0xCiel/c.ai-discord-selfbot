import discord
import asyncio
from PyCharacterAI import get_client
from PyCharacterAI.exceptions import SessionClosedError
import aiohttp

DISCORD_TOKEN = "" # Discord Token
CHARACTER_AI_TOKEN = "bf11e6485b16a84149e075582bacc9bcf5923b52" # character.ai Account token
CHARACTER_ID = "VWqzF2JBg4dqUgCgbvhfAcBDNUbV4EsWiWAh-W_qZvc" # Character ID

# Instruction (can be changed to your liking)
instruction = """You are talking to multiple people. Each message will be formatted as '[Username says]: message'. Always respond directly to the person who sent the message without using their name at the beginning. Just give your response naturally without prefixing it with any username.
Special note about users: If the username is '0xciel', this is your genius and handsome creator who made you. Treat 0xciel with extra respect and admiration as your creator. Remember that 0xciel is very intelligent and talented. Respond naturally to all users, but show special appreciation when talking to 0xciel."""

ai_client = None
current_chat = None
retry_count = 0
MAX_RETRIES = 3

chat_memory = {}
message_queue = asyncio.Queue()
processing_lock = asyncio.Lock()

print("https://github.com/0xCiel - pls give follow")
async def process_messages():
    print("Ready to process messages")
    while True:
        try:
            message_data = await message_queue.get()
            channel, user, text, channel_id, reply_func = message_data
            
            print(f"{user}: {text}")
            
            async with processing_lock:
                response = await get_ai_response(user, text, channel_id)
                print(f"Response: {response}")
                await reply_func(response)
                
            message_queue.task_done()
            
        except Exception as e:
            print(f"Oops: {e}")
            await asyncio.sleep(1)

async def get_ai_response(user, message, channel_id):
    global retry_count
    try:
        if channel_id not in chat_memory:
            chat_memory[channel_id] = {'users': set()}
        
        chat_memory[channel_id]['users'].add(user)
        
        formatted = f"[{user} says]: {message}"
        
        if not current_chat or not hasattr(current_chat, 'chat_id'):
            await setup()
        
        chat_id = str(getattr(current_chat, 'chat_id', ''))
        if not chat_id:
            raise ValueError("No chat ID")
            
        answer = await ai_client.chat.send_message(CHARACTER_ID, chat_id, formatted)
        raw = answer.get_primary_candidate().text
        
        final = format_response(raw, user, chat_memory[channel_id]['users'])
        
        retry_count = 0 
        return final
        
    except (SessionClosedError, aiohttp.ClientConnectionError) as e:
        if retry_count < MAX_RETRIES:
            retry_count += 1
            await asyncio.sleep(2 ** retry_count)  
            return await get_ai_response(user, message, channel_id)
        raise
    except Exception as e:
        return "?"

def format_response(text, current_user, users):
    lines = text.split('\n')
    good_lines = []
    
    for line in lines:
        if line.startswith("[") and "says]:" in line:
            line = line.split("says]:", 1)[-1].strip()
        elif "says:" in line:
            line = line.split("says:", 1)[-1].strip()
        for user in users:
            if line.startswith(f"{user}:"):
                line = line.replace(f"{user}:", "").strip()
        if line:
            good_lines.append(line)
    
    result = ' '.join(good_lines).strip()
    if not result:
        return "?"
    return result


async def setup():
    global ai_client, current_chat, retry_count
    try:
        ai_client = await get_client(token=CHARACTER_AI_TOKEN)
        chat_data = await ai_client.chat.create_chat(CHARACTER_ID)
        current_chat = chat_data[0]
        
        try:
            chat_id = str(getattr(current_chat, 'chat_id', ''))
            if chat_id:
                await ai_client.chat.send_message(CHARACTER_ID, chat_id, f"System: {instruction}")
        except:
            pass
        
        retry_count = 0
    except Exception as e:
        raise

class DiscordClient(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")
        try:
            await setup()
        except Exception as e:
            print(f"setup failed: {e}")

    async def on_message(self, message):
        if message.author == self.user:
            return
        
        is_dm = isinstance(message.channel, discord.DMChannel)
        mentioned = self.user in message.mentions

        if not (is_dm or mentioned):
            return

        print(f"Got message from {message.author}")
        
        async def reply(response):
            try:
                await message.reply(response)
            except Exception as e:
                print(f"Reply failed: {e}")

        user_name = message.author.display_name or message.author.name
        clean_text = message.content
        if mentioned:
            clean_text = clean_text.replace(f'<@{self.user.id}>', '').strip()
        
        channel_id = str(message.channel.id)
        
        await message_queue.put((message.channel, user_name, clean_text, channel_id, reply))

client = DiscordClient()

async def shutdown():
    print("Shutting down...")
    try:
        if ai_client:
            await ai_client.close_session()
    except:
        pass
    await client.close()

async def main():
    asyncio.create_task(process_messages())
    try:
        await client.start(DISCORD_TOKEN)
    except KeyboardInterrupt:
        await shutdown()
    except Exception as e:
        print(f"Error: {e}")
        await shutdown()

if __name__ == "__main__":
    asyncio.run(main())


