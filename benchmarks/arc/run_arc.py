import subprocess
import json
import time
import arckit
import numpy as np
import threading
import queue
import os

# --- CONFIGURATION ---
AGENT_CMD = ["uv", "run", "cli.py"]
EXIT_COMMAND = "exit" 
MAX_TASKS = 5
# ---------------------

def numpy_to_list(grid):
    if isinstance(grid, np.ndarray): return grid.tolist()
    return grid

def enqueue_output(out, q):
    """Reads output line by line and puts it in a queue."""
    try:
        for line in iter(out.readline, ''):
            q.put(line)
    except ValueError: pass
    out.close()

print("Loading ARC-AGI-1 Dataset via arckit...")
train_set, eval_set = arckit.load_data("arcagi")

print(f"Starting Benchmark on {MAX_TASKS} tasks...")
results = []

# FORCE PYTHON TO PRINT IMMEDIATELY (No Buffering)
env = os.environ.copy()
env["PYTHONUNBUFFERED"] = "1"

for i, task in enumerate(train_set):
    if i >= MAX_TASKS: break
    
    print(f"\nRunning Task {i+1}/{MAX_TASKS} (ID: {task.id})")

    # 1. FLATTEN THE PROMPT (Crucial Fix!)
    # We replace all newlines with spaces so the agent reads it as ONE command.
    prompt_parts = [
        "You are solving an ARC reasoning task.",
        "Rules: Find the pattern in the examples and apply it to the TEST INPUT.",
        "IMPORTANT: Return ONLY the output grid as a JSON list of lists. Do not use tools or talk."
    ]
    
    for t_in, t_out in task.train:
        prompt_parts.append(f"EXAMPLE INPUT: {json.dumps(numpy_to_list(t_in))}")
        prompt_parts.append(f"EXAMPLE OUTPUT: {json.dumps(numpy_to_list(t_out))}")
    
    test_input = task.test[0][0]
    expected_output = task.test[0][1]
    prompt_parts.append(f"TEST INPUT: {json.dumps(numpy_to_list(test_input))}")
    prompt_parts.append("YOUR OUTPUT:")

    # Join with spaces to create a single-line string
    full_prompt = " ".join(prompt_parts)

    # 2. RUN AGENT
    start_time = time.time()
    
    process = subprocess.Popen(
        AGENT_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, # Hides the DevTools red text
        text=True,
        bufsize=0, # Unbuffered
        env=env    # Pass the unbuffered environment var
    )

    q = queue.Queue()
    t = threading.Thread(target=enqueue_output, args=(process.stdout, q))
    t.daemon = True
    t.start()

    full_output = ""
    agent_ready = False
    
    try:
        while True:
            if process.poll() is not None: break
            if time.time() - start_time > 120: 
                process.kill()
                break

            try:
                line = q.get(timeout=0.1) # Wait briefly for output
                full_output += line
                
                # DETECT READY STATE
                # If your agent says something else, change "ready" below
                if not agent_ready and ("ready" in line.lower() or "help you" in line.lower()):
                    print("  -> Agent is ready. Sending flattened prompt...")
                    
                    # SEND PROMPT (One massive line)
                    process.stdin.write(full_prompt + "\n")
                    process.stdin.flush()
                    agent_ready = True
                    
                    # SEND EXIT (Give it 30 seconds to think before queuing the exit?)
                    # If we send exit immediately, some agents quit before printing.
                    # Hack: Wait a bit or rely on the agent processing input sequentially.
                    # We'll just send it immediately for now, as standard input() blocks.
                    process.stdin.write(EXIT_COMMAND + "\n")
                    process.stdin.flush()

            except queue.Empty:
                continue

    except Exception as e:
        print(f"Error: {e}")

    if process.poll() is None:
        process.kill()

    duration = time.time() - start_time

    # 3. VERIFY RESULTS
    status = "FAIL"
    try:
        # Search for JSON array [[...]]
        start_idx = full_output.find("[[")
        end_idx = full_output.rfind("]]") + 2
        
        if start_idx != -1 and end_idx != -1:
            clean_json = full_output[start_idx:end_idx]
            agent_grid = json.loads(clean_json)
            if agent_grid == numpy_to_list(expected_output):
                status = "PASS"
            else:
                status = "WRONG_ANSWER"
        else:
            status = "NO_JSON_FOUND"
    except json.JSONDecodeError:
        status = "PARSE_ERROR"
    except Exception:
        status = "UNKNOWN_ERROR"

    print(f"  -> {status} ({duration:.2f}s)")
    
    if status != "PASS":
        # Print a snippet of what the agent actually said
        print(f"     [Agent Said]: {full_output.replace(full_prompt, 'PROMPT_HIDDEN')[-300:].replace(chr(10), ' ')}")

    results.append({"id": task.id, "status": status, "duration": duration})

passed = sum(1 for r in results if r['status'] == 'PASS')
print(f"\nFinal Score: {passed}/{MAX_TASKS} ({(passed/MAX_TASKS)*100:.1f}%)")