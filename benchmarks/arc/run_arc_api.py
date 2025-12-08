import requests
import json
import time
import arckit
import numpy as np
import ast
import re

# CONFIG
API_URL = "http://127.0.0.1:8000/chat"
MAX_TASKS = 5

def numpy_to_list(grid):
    if isinstance(grid, np.ndarray): return grid.tolist()
    return grid

def robust_grid_extraction(text):
    """
    Tries to find a grid [[...]] in text using multiple methods.
    Returns the grid (list of lists) or None.
    """
    if not text: return None
    
    # 1. Clean Markdown (remove ```json ... ```)
    text = re.sub(r'```[a-zA-Z]*', '', text)
    text = text.replace('```', '')
    
    # 2. Regex Search for [[...]] pattern (Dotall matches newlines)
    # We look for outer brackets containing at least one inner bracket
    pattern = r"\[\s*\[.*?\]\s*\]"
    matches = re.findall(pattern, text, re.DOTALL)
    
    for match in reversed(matches): # Check latest match first
        # Try JSON parser (strict)
        try:
            return json.loads(match)
        except:
            pass
        
        # Try Python Evaluator (flexible - handles single quotes, etc)
        try:
            return ast.literal_eval(match)
        except:
            pass
            
    return None

print("Loading ARC-AGI-1 Dataset...")
train_set, eval_set = arckit.load_data("arcagi")

results = []
print(f"Starting API Benchmark on {MAX_TASKS} tasks...")

for i, task in enumerate(train_set):
    if i >= MAX_TASKS: break
    
    print(f"\nTask {i+1} (ID: {task.id})")

    # 1. PREPARE PROMPT (Updated to prevent loops)
    prompt_parts = [
        "You are an ARC Solver.",
        "GOAL: Write Python code to calculate the output grid for the TEST INPUT.",
        "RULES:",
        "1. Write the code.",
        "2. Run the code.",
        "3. CRITICAL: Copy the resulting grid from your code output and paste it here.",
        "4. If your code fails twice, STOP and print your best guess grid manually.",
        "5. Format: [[1, 0], [0, 1]]",
        "TEST INPUT:"
    ]
    for t_in, t_out in task.train:
        prompt_parts.append(f"IN: {json.dumps(numpy_to_list(t_in))} OUT: {json.dumps(numpy_to_list(t_out))}")
    
    test_input = task.test[0][0]
    prompt_parts.append(f"TEST IN: {json.dumps(numpy_to_list(test_input))}")
    prompt_parts.append("YOUR OUTPUT:")
    full_prompt = " ".join(prompt_parts)

    # 2. SEND REQUEST
    start = time.time()
    status = "FAIL"
    raw_output = ""

    try:
        # 600s Timeout
        resp = requests.post(API_URL, json={"prompt": full_prompt}, timeout=600)
        
        if resp.status_code == 200:
            data = resp.json()
            raw_output = str(data.get("response", ""))
            
            # 3. EXTRACTION
            agent_grid = robust_grid_extraction(raw_output)
            
            if agent_grid:
                # Validate it's actually a list of lists
                if isinstance(agent_grid, list) and len(agent_grid) > 0 and isinstance(agent_grid[0], list):
                    expected = numpy_to_list(task.test[0][1])
                    if agent_grid == expected:
                        status = "PASS"
                    else:
                        status = "WRONG_ANSWER"
                else:
                    status = "PARSE_ERROR (Invalid Structure)"
            else:
                status = "NO_JSON_FOUND"
        else:
            status = f"HTTP_ERROR_{resp.status_code}"
            raw_output = resp.text

    except requests.exceptions.Timeout:
        status = "TIMEOUT"
    except Exception as e:
        status = f"ERROR: {str(e)}"

    duration = time.time() - start
    print(f"  -> {status} ({duration:.2f}s)")
    
    # DEBUG: Print output if we missed the JSON
    if status in ["NO_JSON_FOUND", "PARSE_ERROR"]:
        print("     [AGENT OUTPUT SNIPPET] >>>")
        print("     " + raw_output.replace('\n', ' ')[:300] + "...")
        print("     <<<")

    results.append({"id": task.id, "status": status})

passed = sum(1 for r in results if r['status'] == 'PASS')
print(f"\nFinal Score: {passed}/{MAX_TASKS}")