import subprocess
import json
import arckit
import time

# 1. SETUP
# Load the 'training' set (400 tasks) which is public and standard for testing
print("Loading ARC Dataset...")
train_set, eval_set = arckit.load_data()
tasks = train_set  # Choose 'train_set' or 'eval_set'

# Configuration
MAX_TASKS = 5  # Start small! ARC is hard and slow.
AGENT_CMD = "agenticseek" # Your CLI command

results = []

print(f"Starting Benchmark on {MAX_TASKS} ARC tasks...")

for i, task in enumerate(tasks):
    if i >= MAX_TASKS: break
    
    task_id = task.id
    print(f"\nrunning Task {i+1}/{MAX_TASKS} (ID: {task_id})")

    # 2. CONSTRUCT PROMPT
    # We build a string with all training examples
    prompt = "You are solving an ARC reasoning task. Find the pattern in the examples and apply it to the TEST INPUT.\n\n"
    
    # Add Training Examples (The "Few-Shot" learning)
    for t_in, t_out in task.train:
        prompt += f"EXAMPLE INPUT:\n{json.dumps(t_in.tolist())}\n"
        prompt += f"EXAMPLE OUTPUT:\n{json.dumps(t_out.tolist())}\n\n"
    
    # Add the Test Input (The actual question)
    # Note: ARC tasks can have multiple test pairs, usually just 1. We take the first.
    test_input = task.test[0][0]
    expected_output = task.test[0][1]
    
    prompt += f"TEST INPUT:\n{json.dumps(test_input.tolist())}\n"
    prompt += "Provide ONLY the output grid as a JSON list of lists. No text."

    # 3. RUN AGENT
    start_time = time.time()
    try:
        # Calls your CLI agent
        process = subprocess.run(
            [AGENT_CMD, prompt],
            capture_output=True,
            text=True,
            timeout=60 # Give it time to think
        )
        raw_output = process.stdout.strip()
    except Exception as e:
        raw_output = str(e)

    duration = time.time() - start_time

    # 4. PARSE & GRADE
    status = "FAIL"
    try:
        # We try to find the JSON array in the agent's response
        # This is a simple heuristic; you might need regex if your agent is chatty
        start_idx = raw_output.find("[[")
        end_idx = raw_output.rfind("]]") + 2
        clean_json = raw_output[start_idx:end_idx]
        
        agent_grid = json.loads(clean_json)
        
        # EXACT MATCH CHECK
        if agent_grid == expected_output.tolist():
            status = "PASS"
    except:
        status = "PARSE_ERROR"

    print(f"  -> {status} ({duration:.2f}s)")
    
    results.append({
        "id": task_id,
        "status": status,
        "duration": duration,
        "raw_response_preview": raw_output[:100]
    })

# 5. SUMMARY
passed = sum(1 for r in results if r['status'] == 'PASS')
print(f"\nFinal Score: {passed}/{MAX_TASKS} ({(passed/MAX_TASKS)*100:.1f}%)")