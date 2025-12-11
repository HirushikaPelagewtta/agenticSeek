import requests
import json
import time
import os

# --- CONFIGURATION ---
API_URL = "http://127.0.0.1:8000/chat"

# Create folder if it doesn't exist
os.makedirs("benchmarks/browser", exist_ok=True)

# TASKS from "The Internet" Sandbox
TASKS = [
    {
        "id": "nav_1",
        "name": "Navigation Check",
        "prompt": (
            "Go to 'https://the-internet.herokuapp.com/'. "
            "What is the large welcome text at the very top of the page? "
            "It should be the first line of text."
        ),
        "expected_keywords": ["Welcome to the-internet"]
    },
    {
        "id": "login_2",
        "name": "Login Test",
        "prompt": (
            "Go to 'https://the-internet.herokuapp.com/login'. "
            "Log into the secure area using username 'tomsmith' and password 'SuperSecretPassword!'. "
            "Click the Login button. After logging in, tell me the text of the green success message."
        ),
        "expected_keywords": ["You logged into a secure area", "secure area!"]
    },
    {
        "id": "table_3",
        "name": "Reading Tables",
        "prompt": (
            "Go to 'https://the-internet.herokuapp.com/tables'. "
            "Look at 'Example 1'. What is the 'Due' amount for the person with Last Name 'Bach'?"
        ),
        "expected_keywords": ["$51.00", "51.00", "51"]
    },
    {
        "id": "dropdown_4",
        "name": "Select Dropdown",
        "prompt": (
            "Go to 'https://the-internet.herokuapp.com/dropdown'. "
            "Select 'Option 2' from the dropdown list. "
            "After selecting it, confirm which option is currently selected."
        ),
        "expected_keywords": ["Option 2"]
    },
    {
        "id": "checkbox_5",
        "name": "Toggle Checkboxes",
        "prompt": (
            "Go to 'https://the-internet.herokuapp.com/checkboxes'. "
            "Ensure BOTH 'checkbox 1' and 'checkbox 2' are checked. "
            "Reply with 'Done' when both are checked."
        ),
        "expected_keywords": ["Done", "checked"]
    }
]

print(f"Starting Web Benchmark on {len(TASKS)} tasks...")
results = []

for i, task in enumerate(TASKS):
    print(f"\nTask {i+1}: {task['name']}")
    
    # 1. CONSTRUCT PROMPT
    # We use a strong system prompt to ensure the Router picks the BrowserAgent
    full_prompt = (
            "You are an automated browser agent.\n"
            f"TASK: {task['prompt']}\n"
            "RULES:\n"
            "1. Use your Browser tool to navigate and interact.\n"
            "2. If you need to click or type, do so.\n"
            "3. CRITICAL: Output ONLY the requested text/value. Do not write 'Findings' or 'Analysis'.\n"
            "4. If asking for a heading, return JUST the heading text.\n"
            "YOUR ANSWER:"
        )

    # 2. SEND REQUEST
    # We use 'new_session: True' to clear memory between tasks.
    # We DO NOT use 'benchmark_mode' because that would force CasualAgent (which has no tools).
    payload = {"prompt": full_prompt, "new_session": True}
    
    start = time.time()
    status = "FAIL"
    agent_ans = ""

    try:
        resp = requests.post(API_URL, json=payload, timeout=300)
        
        if resp.status_code == 200:
            data = resp.json()
            agent_ans = str(data.get("response", ""))
            
            # 3. SCORING
            found_key = False
            for key in task['expected_keywords']:
                if key.lower() in agent_ans.lower():
                    found_key = True
                    break
            
            if found_key:
                status = "PASS"
            else:
                status = "WRONG_ANSWER"
        else:
            status = f"HTTP {resp.status_code}"

    except Exception as e:
        status = "ERROR"
        agent_ans = str(e)

    duration = time.time() - start
    print(f"  -> {status} ({duration:.2f}s)")
    if status != "PASS":
        print(f"     [EXPECTED]: One of {task['expected_keywords']}")
        print(f"     [AGENT]:    {agent_ans[:200]}...") 
        
    results.append({"id": task['id'], "status": status})

passed = sum(1 for r in results if r['status'] == 'PASS')
print(f"\nFinal Score: {passed}/{len(results)}")