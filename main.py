import discord
import asyncio
from PyCharacterAI import get_client
from PyCharacterAI.exceptions import SessionClosedError
import aiohttp

DISCORD_TOKEN = "" # DISCORD ACCOUNT TOKEN
CHARACTER_AI_TOKEN = "bf11e6485b16a84149e075582bacc9bcf5923b52" # character.ai Account Token
CHARACTER_ID = "RYdl1drUQGDft0dj7TMOgYVCZIz96gPFSGb8NT3dhCY" # Character ID
client_ai = None
chat = None
retry_count = 0
MAX_RETRIES = 3

async def get_ai_response(message_content):
    global retry_count
    try:
        print(f"Processing message: {message_content[:200]}")
        if not chat or not hasattr(chat, 'chat_id'):
            print("No active chat session found, initializing new one...")
            await initialize_character_ai()
        
        chat_id = str(getattr(chat, 'chat_id', ''))
        if not chat_id:
            raise ValueError("Invalid chat ID")
            
        print("Sending message...")
        answer = await client_ai.chat.send_message(CHARACTER_ID, chat_id, message_content)
        response = answer.get_primary_candidate().text
        print(f"response: {response[:200]}")
        retry_count = 0 
        return response
        
    except (SessionClosedError, aiohttp.ClientConnectionError) as e:
        print(f"Connection error: {str(e)}")
        if retry_count < MAX_RETRIES:
            retry_count += 1
            print(f"Attempting reconnect (attempt {retry_count}/{MAX_RETRIES})...")
            await asyncio.sleep(2 ** retry_count) 
            return await get_ai_response(message_content)
        raise
    except Exception as e:
        print(f"Unexpected error getting AI response: {str(e)}")
        return "I'm having trouble responding right now. Please try again later."

async def initialize_character_ai():
    global client_ai, chat, retry_count
    print("Initializing Character AI connection...")
    try:
        client_ai = await get_client(token=CHARACTER_AI_TOKEN)
        me = await client_ai.account.fetch_me()
        print(f"Connected to Character AI as @{me.username}")
        
        print("Creating new chat session...")
        chat_data = await client_ai.chat.create_chat(CHARACTER_ID)
        chat = chat_data[0]
        greeting_message = chat_data[1]
        print(f"Chat session created: {greeting_message.get_primary_candidate().text[:200]}")
        retry_count = 0
    except Exception as e:
        print(f"Initialization failed: {str(e)}")
        raise

class cClient(discord.Client):
    async def on_ready(self):
        print(f"\nlogged in as {self.user} (ID: {self.user.id})")
        print(f"Connected to {len(self.guilds)} servers:")
        for guild in self.guilds:
            print(f"- {guild.name} (ID: {guild.id})")
        
        try:
            await initialize_character_ai()
            print("Character AI initialized successfully")
        except Exception as e:
            print(f"Failed to initialize Character AI: {str(e)}")

    async def on_message(self, message):
        if message.author == self.user:
            return
        
        is_dm = isinstance(message.channel, discord.DMChannel)
        mentioned = self.user in message.mentions
        channel_info = f"DM" if is_dm else f"#{message.channel.name} in {message.guild.name}"

        if not (is_dm or mentioned):
            return

        print(f"\nNew message in {channel_info} from {message.author}: {message.content[:200]}")
        try:
            async with message.channel.typing():
                print("Generating response...")
                try:
                    response_text = await get_ai_response(message.content)
                    await message.reply(response_text)
                    print("Response sent successfully")
                except Exception as e:
                    print(f"Failed to generate response: {str(e)}")
                    await message.reply("I'm having technical difficulties. Please try again later.")
        except discord.errors.HTTPException as e:
            print(f"Discord HTTP error: {str(e)}")
        except Exception as e:
            print(f"Unexpected error in message handling: {str(e)}")

client = cClient()

async def shutdown():
    print("\nShutdown initiated...")
    try:
        if client_ai:
            print("Closing Character AI session...")
            await client_ai.close_session()
    except Exception as e:
        print(f"Error closing session: {str(e)}")
    
    print("Closing Discord connection...")
    await client.close()
    await asyncio.sleep(1)
    print("Shutdown complete")

async def main():
    try:
        print("Starting...")
        await client.start(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received")
        await shutdown()
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        await shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Critical error: {str(e)}")
