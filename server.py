import sys
import os

# --- CRITICAL WINDOWS FIX ---
# This forces the console to accept emojis (like 🎯) without crashing.
# Must be the very first thing the script does.
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    # Python < 3.7 or weird environments might not support this
    pass

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


# $env:PYTHONIOENCODING = "utf-8"
# python server.py

# 1. INITIALIZATION
print("--- SERVER STARTUP ---")
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

# Load all agents
all_agents = [
    CasualAgent(name=config["MAIN"]["agent_name"], prompt_path=f"prompts/{personality_folder}/casual_agent.txt", provider=provider, verbose=False),
    CoderAgent(name="coder", prompt_path=f"prompts/{personality_folder}/coder_agent.txt", provider=provider, verbose=False),
    FileAgent(name="File Agent", prompt_path=f"prompts/{personality_folder}/file_agent.txt", provider=provider, verbose=False),
    BrowserAgent(name="Browser", prompt_path=f"prompts/{personality_folder}/browser_agent.txt", provider=provider, verbose=False, browser=browser),
    PlannerAgent(name="Planner", prompt_path=f"prompts/{personality_folder}/planner_agent.txt", provider=provider, verbose=False, browser=browser),
]

# Standard Interaction (All agents)
global_interaction = Interaction(all_agents, tts_enabled=False, stt_enabled=False, recover_last_session=False, langs=languages)

print("--- SERVER READY ---")

app = FastAPI()

class Query(BaseModel):
    prompt: str
    new_session: bool = False
    benchmark_mode: bool = False 

@app.post("/chat")
async def chat(query: Query):
    global global_interaction
    
    try:
        # --- BENCHMARK MODE: FORCE CASUAL AGENT (For HumanEval) ---
        if query.benchmark_mode:
            print(">>> BENCHMARK MODE: Using CasualAgent ONLY <<<")
            casual_only = [all_agents[0]] 
            global_interaction = Interaction(
                casual_only, tts_enabled=False, stt_enabled=False, recover_last_session=False, langs=languages
            )
        # --- STANDARD RESET ---
        elif query.new_session:
            print(">>> RESETTING MEMORY (Standard Mode) <<<")
            global_interaction = Interaction(
                all_agents, tts_enabled=False, stt_enabled=False, recover_last_session=False, langs=languages
            )

        global_interaction.set_query(query.prompt)
        success = await global_interaction.think()
        
        if success:
            response_text = str(global_interaction.last_answer)
            
            # --- UNIVERSAL BLOCK UNPACKER (Fixes GAIA & ARC & HumanEval) ---
            try:
                blocks = global_interaction.get_last_blocks_result()
                if blocks:
                    print(f"DEBUG: Found {len(blocks)} internal blocks.")
                    for block in blocks:
                        # 1. Append Source Code
                        code_content = block.get('code', '')
                        if code_content:
                            response_text += f"\n\n```python\n{code_content}\n```"
                        
                        # 2. Append Execution Output
                        output_content = str(block.get('output', ''))
                        if output_content:
                            # Safe printing for debug logs (replaces errors with ?)
                            safe_output = output_content.encode('utf-8', 'replace').decode('utf-8')
                            print(f"DEBUG: Appending output: {safe_output[:50]}...")
                            response_text += f"\n\nOUTPUT:\n{output_content}"
            except Exception as e:
                print(f"DEBUG: Block extraction warning: {e}")
            # ---------------------------------------------------------------
            
            return {"response": response_text}
        else:
            return {"response": "Error: Agent declined to answer."}

    except Exception as e:
        print(f"Server Error: {e}")
        return {"response": f"SERVER_EXCEPTION: {str(e)}"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)