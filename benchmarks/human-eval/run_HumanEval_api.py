import requests
import json
import time
import os
import re

# --- CONFIGURATION ---
API_URL = "http://127.0.0.1:8000/chat"
DATA_FILE = "benchmarks/human-eval/human-eval.jsonl" # Ensure this file is in your folder
MAX_TASKS = 5 

def extract_code_block(response_text):
    """
    Robustly extracts python code.
    """
    # 1. Try finding ```python ... ```
    if "```python" in response_text:
        return response_text.split("```python")[1].split("```")[0].strip()
    
    # 2. Try finding generic ``` ... ```
    if "```" in response_text:
        # Check if there are at least 2 backticks groups
        parts = response_text.split("```")
        if len(parts) >= 3:
            return parts[1].strip()
            
    # 3. Fallback: If the text starts with 'def ', assume the whole text is code
    if response_text.strip().startswith("def "):
        return response_text.strip()
        
    return ""

def run_test_safe(code, entry_point, test_code):
    """
    Executes the combined code + test in a sandbox.
    """
    if not code:
        return False, "No code extracted"

    # Combine the agent's code with the official test case
    full_script = f"""
{code}

{test_code}

check({entry_point})
"""
    try:
        # Define a local scope so definitions don't leak between tasks
        # We also need to mock common imports if the agent forgets them
        local_scope = {
            'List': list,
            'Tuple': tuple,
            'Dict': dict,
            'Optional': None,
            'Any': None,
            'math': __import__('math')
        }
        exec(full_script, {}, local_scope)
        return True, "Tests Passed"
    except Exception as e:
        return False, str(e)

# --- LOAD DATA ---
if not os.path.exists(DATA_FILE):
    # Auto-download if missing
    print(f"Downloading {DATA_FILE}...")
    import urllib.request
    import gzip
    import shutil
    url = "[https://github.com/openai/human-eval/raw/master/data/HumanEval.jsonl.gz](https://github.com/openai/human-eval/raw/master/data/HumanEval.jsonl.gz)"
    urllib.request.urlretrieve(url, "HumanEval.jsonl.gz")
    with gzip.open("HumanEval.jsonl.gz", 'rb') as f_in:
        with open(DATA_FILE, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
            
tasks = []
with open(DATA_FILE, 'r', encoding='utf-8') as f:
    for line in f:
        tasks.append(json.loads(line))

print(f"Found {len(tasks)} tasks. Running first {MAX_TASKS}...")

results = []

for i, task in enumerate(tasks):
    if i >= MAX_TASKS: break
    
    task_id = task['task_id']
    prompt_code = task['prompt']  # Contains signature + docstring
    entry_point = task['entry_point']
    test_code = task['test']
    
    print(f"\nTask {task_id}")

    # 1. CONSTRUCT PROMPT (UPDATED FOR NO TOOLS)
    # We specifically tell it NOT to execute code.
    full_prompt = (
        "You are a Python coding assistant.\n"
        "TASK: Complete the function below based on its docstring.\n"
        "CRITICAL RULES:\n"
        "1. DO NOT RUN THE CODE. DO NOT USE TOOLS.\n"
        "2. Output ONLY the Python function definition wrapped in ```python``` blocks.\n"
        "3. Do not include example usage or tests, just the function.\n"
        f"CODE:\n{prompt_code}"
    )

    # 2. SEND TO AGENT
    start = time.time()
    payload = {
            "prompt": full_prompt, 
            "new_session": True,
            "benchmark_mode": True 
        }
        
    generated_code = ""
    status = "FAIL"
    message = "Unknown"

    try:
        resp = requests.post(API_URL, json=payload, timeout=600)
        
        if resp.status_code == 200:
            raw_response = str(resp.json().get("response", ""))
            
            # 3. EXTRACT CODE
            generated_code = extract_code_block(raw_response)
            
            # 4. DEBUG PRINT (See what the agent actually wrote!)
            # This is crucial if extraction fails again
            if not generated_code:
                print(f"    [DEBUG RAW RESPONSE]: {raw_response[:200]}...")

            # 5. EXECUTE
            passed, message = run_test_safe(generated_code, entry_point, test_code)
            status = "PASS" if passed else "FAIL"
            
        else:
            message = f"HTTP {resp.status_code}"

    except Exception as e:
        status = "ERROR"
        message = str(e)

    duration = time.time() - start
    print(f"  -> {status} ({duration:.2f}s) - {message}")
    
    if status != "PASS":
        # Only print the first few lines of code to save space
        clean_code_preview = generated_code.replace('\n', ' ')[:100]
        print(f"     [EXTRACTED CODE]: {clean_code_preview}...")

    results.append({"id": task_id, "status": status})

passed_count = sum(1 for r in results if r['status'] == 'PASS')
print(f"\nFinal Score: {passed_count}/{len(results)}")