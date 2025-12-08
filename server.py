import sys
import os

# --- FIX WINDOWS UNICODE CRASH ---
# This forces the console to accept arrows (→) and emojis without crashing.
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# server.py
import configparser
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import re

# --- IMPORTS (Matches your cli.py) ---
from sources.llm_provider import Provider
from sources.interaction import Interaction
from sources.agents import Agent, CoderAgent, CasualAgent, FileAgent, PlannerAgent, BrowserAgent, McpAgent
from sources.browser import Browser, create_driver

# 1. INITIALIZATION (Global Scope - Runs Once)
print("--- SERVER STARTUP: INITIALIZING AGENTS ---")
config = configparser.ConfigParser()
config.read('config.ini')

# Force these to False for the server to make it faster/quieter
stealth_mode = config.getboolean('BROWSER', 'stealth_mode')
personality_folder = "jarvis" if config.getboolean('MAIN', 'jarvis_personality') else "base"
languages = config["MAIN"]["languages"].split(' ')

provider = Provider(
    provider_name=config["MAIN"]["provider_name"],
    model=config["MAIN"]["provider_model"],
    server_address=config["MAIN"]["provider_server_address"],
    is_local=config.getboolean('MAIN', 'is_local')
)

print("Launching Browser (This happens only once)...")
# We load the browser here so it stays open forever
browser = Browser(
    create_driver(headless=config.getboolean('BROWSER', 'headless_browser'), stealth_mode=stealth_mode, lang=languages[0]),
    anticaptcha_manual_install=stealth_mode
)

agents = [
    CasualAgent(name=config["MAIN"]["agent_name"], prompt_path=f"prompts/{personality_folder}/casual_agent.txt", provider=provider, verbose=False),
    CoderAgent(name="coder", prompt_path=f"prompts/{personality_folder}/coder_agent.txt", provider=provider, verbose=False),
    FileAgent(name="File Agent", prompt_path=f"prompts/{personality_folder}/file_agent.txt", provider=provider, verbose=False),
    BrowserAgent(name="Browser", prompt_path=f"prompts/{personality_folder}/browser_agent.txt", provider=provider, verbose=False, browser=browser),
    PlannerAgent(name="Planner", prompt_path=f"prompts/{personality_folder}/planner_agent.txt", provider=provider, verbose=False, browser=browser),
]

# Initialize Interaction with TTS/STT DISABLED for speed
interaction = Interaction(
    agents,
    tts_enabled=False, 
    stt_enabled=False,
    recover_last_session=False,
    langs=languages
)

print("--- AGENTS READY. WAITING FOR REQUESTS ---")

app = FastAPI()

class Query(BaseModel):
    prompt: str

@app.post("/chat")
async def chat(query: Query):
    try:
        interaction.set_query(query.prompt)
        success = await interaction.think()
        
        if success:
            # 1. Get the text response
            response_text = str(interaction.last_answer)
            
            # 2. SAFETY NET: Check internal blocks if text doesn't look like a grid
            # Regex looks for [[number..., ...]] pattern
            grid_pattern = r"\[\s*\[\s*\d+.*\]\s*\]"
            
            if not re.search(grid_pattern, response_text, re.DOTALL):
                print(f"DEBUG: Grid not found in speech. Checking code blocks...")
                try:
                    blocks = interaction.get_last_blocks_result()
                    # Print blocks to console so we can see what's happening
                    print(f"DEBUG: Found {len(blocks)} blocks.") 
                    
                    for block in reversed(blocks):
                        output = str(block.get('output', ''))
                        # Try to find a grid in the code output
                        match = re.search(grid_pattern, output, re.DOTALL)
                        if match:
                            found_grid = match.group(0)
                            print(f"DEBUG: Recovered grid from code output!")
                            # Append only the grid to the response
                            response_text += "\n" + found_grid
                            break
                except Exception as e:
                    print(f"DEBUG: Safety net failed: {e}")

            return {"response": response_text}
        else:
            return {"response": "Error: Agent declined to answer."}

    except Exception as e:
        print(f"Server Error: {e}")
        return {"response": f"SERVER_EXCEPTION: {str(e)}"}
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)