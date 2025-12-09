import requests
import json
import time
import re
import os

# --- CONFIGURATION ---
API_URL = "http://127.0.0.1:8000/chat"
TASK_FILE = "task.json"  # Make sure this file exists!
MAX_TASKS = 10           # How many questions to run (set to -1 for all)

def normalize_text(text):
    """
    Simple cleaner to make matching easier.
    Removes punctuation and converts to lowercase.
    """
    if not isinstance(text, str): return str(text)
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text) # Remove punctuation
    return text.strip()

def robust_answer_extraction(full_response):
    """
    Attempts to pull the final answer from the Agent's reasoning.
    1. Looks for 'Answer: X'
    2. Looks for the last line.
    3. Fallback: returns the whole text.
    """
    # 1. Clean Markdown code blocks if any
    text = re.sub(r'```[a-zA-Z]*', '', full_response)
    text = text.replace('```', '')
    
    # 2. explicit "Answer:" pattern
    # Matches "Answer: <content>" at the end of the string or line
    match = re.search(r'(?:Answer|Result):\s*(.*)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # 3. Fallback: Return the last non-empty line (common for CoT)
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if lines:
        return lines[-1]
        
    return text.strip()

# --- LOAD DATA ---
if not os.path.exists(TASK_FILE):
    print(f"ERROR: File '{TASK_FILE}' not found.")
    print("Please download a BIG-bench task.json (e.g. date_understanding) first.")
    exit()

print(f"Loading {TASK_FILE}...")
with open(TASK_FILE, 'r', encoding='utf-8') as f:
    task_data = json.load(f)

examples = task_data.get('examples', [])
print(f"Found {len(examples)} examples. Starting API Benchmark on {MAX_TASKS}...")

results = []

# --- MAIN LOOP ---
for i, example in enumerate(examples):
    if MAX_TASKS > 0 and i >= MAX_TASKS: break
    
    print(f"\nTask {i+1}")

    # 1. PREPARE PROMPT
    # BIG-bench inputs are usually just text questions.
    input_text = example['input']
    
    # We allow string or list of strings for targets
    raw_targets = example['target']
    if isinstance(raw_targets, str):
        valid_targets = [raw_targets]
    else:
        valid_targets = raw_targets

    # Construct the Prompt
    full_prompt = (
        "You are a helpful logic agent.\n"
        "GOAL: Answer the following question concisely.\n"
        "RULES:\n"
        "1. Think step-by-step if needed.\n"
        "2. Your FINAL line must be the direct answer.\n"
        f"QUESTION: {input_text}\n"
        "YOUR ANSWER:"
    )

    # 2. SEND REQUEST
    start = time.time()
    status = "FAIL"
    agent_output = ""

        # ...
    payload = {
        "prompt": full_prompt,
        "new_session": True  # <--- TELLS SERVER TO WIPE MEMORY
    }

    try:
        resp = requests.post(API_URL, json=payload, timeout=600)
# ...
    
        if resp.status_code == 200:
            data = resp.json()
            # Handle different API response formats (adjust key if needed)
            raw_output = str(data.get("response", ""))
            
            # 3. EXTRACTION
            agent_answer = robust_answer_extraction(raw_output)
            
            # 4. SCORING (Soft Match)
            # We check if the expected answer appears in the agent's cleaned output
            is_correct = False
            clean_agent = normalize_text(agent_answer)
            
            for t in valid_targets:
                clean_target = normalize_text(t)
                # Check for exact match OR if target is contained in answer
                if clean_target in clean_agent:
                    is_correct = True
                    break
            
            if is_correct:
                status = "PASS"
            else:
                status = "WRONG_ANSWER"
        else:
            status = f"HTTP_ERROR_{resp.status_code}"
            raw_output = resp.text

    except requests.exceptions.Timeout:
        status = "TIMEOUT"
    except Exception as e:
        status = f"ERROR: {str(e)}"

    duration = time.time() - start
    print(f"  -> {status} ({duration:.2f}s)")
    
    if status != "PASS":
        print(f"     [EXPECTED]: {valid_targets}")
        print(f"     [AGENT]:    {agent_answer}")

    results.append({"id": i, "status": status})

# --- FINAL REPORT ---
passed = sum(1 for r in results if r['status'] == 'PASS')
print("\n" + "="*30)
print(f"Final Score: {passed}/{len(results)} ({(passed/len(results))*100:.1f}%)")
print("="*30)