import requests
import json
import time
import re
import os

# --- CONFIGURATION ---
API_URL = "http://127.0.0.1:8000/chat"
TASK_FILE = "benchmarks/big-bench/task.json"  # Make sure this file exists!
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
    Ignores known system status messages.
    """
    # 1. Clean up known system noise/artifacts
    # Add any other system messages you see here to ignore them
    noise_phrases = [
        "Agent succeeded with task.",
        "Agent finished.",
        "Task completed."
    ]
    for phrase in noise_phrases:
        full_response = full_response.replace(phrase, "")

    # 2. Clean Markdown code blocks
    text = re.sub(r'```[a-zA-Z]*', '', full_response)
    text = text.replace('```', '')
    
    # 3. Explicit "Answer:" pattern
    # Matches "Answer: <content>" or "YOUR ANSWER: <content>"
    match = re.search(r'(?:Answer|Result):\s*(.*)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # 4. Fallback: Return the last non-empty line
    # Since we removed the "Agent succeeded" line above, 
    # this should now grab the line *before* that (the real answer).
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

# --- MAIN LOOP (Updated) ---
for i, example in enumerate(examples):
    if MAX_TASKS > 0 and i >= MAX_TASKS: break
    
    # 1. DETERMINE CORRECT TARGETS
    valid_targets = []
    if 'target' in example and isinstance(example['target'], str):
        valid_targets.append(example['target'])
    if 'target_scores' in example:
        scores = example['target_scores']
        max_score = max(scores.values())
        valid_targets.extend([k for k, v in scores.items() if v == max_score])
        
        # ALSO: Get ALL options for the prompt (including wrong ones)
        # This helps the agent see what it can choose from
        all_options = list(scores.keys())
    else:
        all_options = valid_targets # Fallback

    print(f"\nTask {i+1}")
    
    # 2. CONSTRUCT PROMPT (The Fix)
    input_text = example['input']
    
    # We create a string like "Options: [Yes, No]"
    options_display = ", ".join(f"'{opt}'" for opt in all_options)
    
    full_prompt = (
        "You are a logical reasoning expert taking a multiple-choice test.\n"
        f"QUESTION: {input_text}\n"
        f"AVAILABLE OPTIONS: [{options_display}]\n"
        "INSTRUCTIONS:\n"
        "1. Analyze the scenario.\n"
        "2. Select the best option from the list above.\n"
        "3. Your FINAL line must be ONLY the exact option text (e.g. 'Yes').\n"
        "YOUR ANSWER:"
    )

    # 3. SEND REQUEST
    start = time.time()
    status = "FAIL"
    payload = {"prompt": full_prompt, "new_session": True}

    try:
        resp = requests.post(API_URL, json=payload, timeout=600)
        
        if resp.status_code == 200:
            data = resp.json()
            raw_output = str(data.get("response", ""))
            
            # 4. EXTRACTION & SCORING
            agent_answer = robust_answer_extraction(raw_output)
            clean_agent = normalize_text(agent_answer)
            
            is_correct = False
            for t in valid_targets:
                clean_target = normalize_text(t)
                # Check for exact word match
                if clean_target == clean_agent: # Strict match is safer now
                    is_correct = True
                    break
                # Fallback: if agent says "Answer: Yes", clean_agent might be "yes"
                elif clean_target in clean_agent.split():
                    is_correct = True
                    break
            
            if is_correct:
                status = "PASS"
            else:
                status = "WRONG_ANSWER"
        else:
            status = f"HTTP_ERROR_{resp.status_code}"
            raw_output = resp.text
            agent_answer = "HTTP Error"

    except requests.exceptions.Timeout:
        status = "TIMEOUT"
        agent_answer = "Timeout"
    except Exception as e:
        status = f"ERROR: {str(e)}"
        agent_answer = f"Exception: {e}"

    duration = time.time() - start
    print(f"  -> {status} ({duration:.2f}s)")
    
    if status != "PASS":
        print(f"     [EXPECTED]: {valid_targets}")
        print(f"     [AGENT]:    '{agent_answer}'") 

    results.append({"id": i, "status": status})

# --- FINAL REPORT ---
passed = sum(1 for r in results if r['status'] == 'PASS')
print("\n" + "="*30)
print(f"Final Score: {passed}/{len(results)} ({(passed/len(results))*100:.1f}%)")
print("="*30)