import requests
import json
import time
import os

# --- CONFIGURATION ---
API_URL = "http://127.0.0.1:8000/chat"
DATA_FILE = "HumanEval.jsonl"
MAX_TASKS = 5  # Start small!

def extract_code_block(response_text):
    """
    Extracts python code from ```python ... ``` blocks.
    If no block is found, returns the raw text.
    """
    if "```python" in response_text:
        return response_text.split("```python")[1].split("```")[0].strip()
    if "```" in response_text:
        return response_text.split("```")[1].split("```")[0].strip()
    return response_text.strip()

def run_test_safe(code, entry_point, test_code):
    """
    Executes the combined code + test in a sandbox (try/except block).
    Returns: (Pass/Fail, Error Message)
    """
    # Combine the agent's code with the official test case
    full_script = f"""
{code}

{test_code}

check({entry_point})
"""
    try:
        # Define a local scope so definitions don't leak between tasks
        local_scope = {}
        exec(full_script, {}, local_scope)
        return True, "Tests Passed"
    except Exception as e:
        return False, str(e)

# --- LOAD DATA ---
if not os.path.exists(DATA_FILE):
    print(f"ERROR: Please download {DATA_FILE} from OpenAI's repository first.")
    exit()

print(f"Loading {DATA_FILE}...")
tasks = []
with open(DATA_FILE, 'r', encoding='utf-8') as f:
    for line in f:
        tasks.append(json.loads(line))

print(f"Found {len(tasks)} tasks. Running first {MAX_TASKS}...")

results = []

for i, task in enumerate(tasks):
    if i >= MAX_TASKS: break
    
    task_id = task['task_id']
    prompt_func = task['prompt']  # Contains function signature + docstring
    entry_point = task['entry_point']
    test_code = task['test']      # Hidden unit tests
    
    print(f"\nTask {task_id}")

    # 1. CONSTRUCT PROMPT
    # We ask the agent to complete the function based on the docstring
    full_prompt = (
        "You are an expert Python programmer.\n"
        "GOAL: Complete the following function.\n"
        "RULES:\n"
        "1. Return ONLY the function code.\n"
        "2. Do not import extra libraries unless necessary.\n"
        f"CODE:\n{prompt_func}"
    )

    # 2. SEND TO AGENT
    start = time.time()
    payload = {"prompt": full_prompt, "new_session": True}
    
    try:
        resp = requests.post(API_URL, json=payload, timeout=600)
        raw_response = resp.json().get("response", "")
        
        # 3. EXTRACT CODE
        generated_code = extract_code_block(raw_response)
        
        # 4. EXECUTE AND TEST
        # We must append the imports provided by the benchmark (usually in 'prompt')
        # But usually the 'prompt' variable has the imports + signature.
        # We combine the Agent's completion with the original prompt to ensure imports/signatures exist.
        
        # Strategy: The agent usually outputs the WHOLE function or just the body.
        # If agent outputs whole function (def ...), use that.
        # If agent outputs just body, we might need to prepend signature.
        # For simplicity, let's assume your CoderAgent outputs the full valid function.
        
        passed, message = run_test_safe(generated_code, entry_point, test_code)
        
        status = "PASS" if passed else "FAIL"
        
    except Exception as e:
        status = "ERROR"
        message = str(e)
        generated_code = ""

    duration = time.time() - start
    print(f"  -> {status} ({duration:.2f}s) - {message}")
    
    if status != "PASS":
        print(f"     [AGENT CODE START]\n{generated_code[:100]}...\n     [AGENT CODE END]")

    results.append({"id": task_id, "status": status})

passed_count = sum(1 for r in results if r['status'] == 'PASS')
print(f"\nFinal Score: {passed_count}/{len(results)}")