import configparser
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import re

# --- IMPORTS ---
from sources.llm_provider import Provider
from sources.interaction import Interaction
from sources.agents import Agent, CoderAgent, CasualAgent, FileAgent, PlannerAgent, BrowserAgent, McpAgent
from sources.browser import Browser, create_driver

# 1. INITIALIZATION (Global Scope - Runs Once)
print("--- SERVER STARTUP: INITIALIZING AGENTS ---")
config = configparser.ConfigParser()
config.read('config.ini')

stealth_mode = config.getboolean('BROWSER', 'stealth_mode')
personality_folder = "jarvis" if config.getboolean('MAIN', 'jarvis_personality') else "base"
languages = config["MAIN"]["languages"].split(' ')

provider = Provider(
    provider_name=config["MAIN"]["provider_name"],
    model=config["MAIN"]["provider_model"],
    server_address=config["MAIN"]["provider_server_address"],
    is_local=config.getboolean('MAIN', 'is_local')
)

print("Launching Browser...")
browser = Browser(
    create_driver(headless=config.getboolean('BROWSER', 'headless_browser'), stealth_mode=stealth_mode, lang=languages[0]),
    anticaptcha_manual_install=stealth_mode
)

# Agents are heavy (prompts), so we load them once and keep them globally
agents = [
    CasualAgent(name=config["MAIN"]["agent_name"], prompt_path=f"prompts/{personality_folder}/casual_agent.txt", provider=provider, verbose=False),
    CoderAgent(name="coder", prompt_path=f"prompts/{personality_folder}/coder_agent.txt", provider=provider, verbose=False),
    FileAgent(name="File Agent", prompt_path=f"prompts/{personality_folder}/file_agent.txt", provider=provider, verbose=False),
    BrowserAgent(name="Browser", prompt_path=f"prompts/{personality_folder}/browser_agent.txt", provider=provider, verbose=False, browser=browser),
    PlannerAgent(name="Planner", prompt_path=f"prompts/{personality_folder}/planner_agent.txt", provider=provider, verbose=False, browser=browser),
]

# Create a global interaction holder
global_interaction = Interaction(agents, tts_enabled=False, stt_enabled=False, recover_last_session=False, langs=languages)

print("--- AGENTS READY. WAITING FOR REQUESTS ---")

app = FastAPI()

class Query(BaseModel):
    prompt: str
    new_session: bool = False  # <--- NEW PARAMETER

@app.post("/chat")
async def chat(query: Query):
    global global_interaction
    
    try:
        # --- MEMORY RESET LOGIC ---
        if query.new_session:
            print(">>> RESETTING MEMORY for new task <<<")
            # We re-initialize the interaction object to wipe history
            global_interaction = Interaction(
                agents, 
                tts_enabled=False, 
                stt_enabled=False, 
                recover_last_session=False, 
                langs=languages
            )
        # --------------------------

        global_interaction.set_query(query.prompt)
        success = await global_interaction.think()
        
        if success:
            response_text = str(global_interaction.last_answer)
            
            print("\n" + "="*40)
            print(f"RAW AGENT OUTPUT ({len(response_text)} chars):")
            print(response_text)
            print("="*40 + "\n")
            # --------------------------------
            # --- ARC SPECIFIC LOGIC (Runs for ARC, fails silently for BIG-bench) ---
            grid_pattern = r"\[\s*\[\s*\d+.*\]\s*\]"
            
            # Only run the heavy regex/block check if we suspect a grid is missing
            # and if the user didn't ask a purely text question
            if not re.search(grid_pattern, response_text, re.DOTALL):
                try:
                    blocks = global_interaction.get_last_blocks_result()
                    for block in reversed(blocks):
                        output = str(block.get('output', ''))
                        match = re.search(grid_pattern, output, re.DOTALL)
                        if match:
                            found_grid = match.group(0)
                            print(f"DEBUG: Recovered grid from code output!")
                            response_text += "\n" + found_grid
                            break
                except Exception:
                    pass 
            # -----------------------------------------------------------------------

            return {"response": response_text}
        else:
            return {"response": "Error: Agent declined to answer."}

    except Exception as e:
        print(f"Server Error: {e}")
        return {"response": f"SERVER_EXCEPTION: {str(e)}"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)