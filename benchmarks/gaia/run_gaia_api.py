import requests
import json
import time
import os
import re
import pandas as pd  # <--- NEW IMPORT

# --- CONFIGURATION ---
API_URL = "http://127.0.0.1:8000/chat"
# Point to the Level 1 Parquet file you downloaded
METADATA_FILE = "benchmarks/gaia/metadata.level1.parquet" 
CACHE_DIR = "benchmarks/gaia/files"
MAX_TASKS = 5

# Ensure directories exist
os.makedirs(CACHE_DIR, exist_ok=True)

def download_attachment(filename):
    """
    Downloads the specific file required for the task from HuggingFace.
    """
    # Base URL for validation files
    base_url = "https://huggingface.co/datasets/gaia-benchmark/GAIA/resolve/main/2023/validation/"
    target_path = os.path.join(CACHE_DIR, filename)
    
    if os.path.exists(target_path):
        return target_path
        
    print(f"   Downloading {filename}...")
    try:
        # We try to fetch the file. Note: Some files might be in different folders 
        # on the repo, but the flat structure usually works for validation set.
        url = base_url + filename
        r = requests.get(url)
        if r.status_code == 200:
            with open(target_path, 'wb') as f:
                f.write(r.content)
            return target_path
        else:
            print(f"   Failed to download {filename} (Status: {r.status_code})")
    except Exception as e:
        print(f"   Error downloading file: {e}")
    return None

def normalize_answer(text):
    text = str(text).lower()
    text = re.sub(r'[^\w\s.]', '', text) 
    return text.strip()

# --- LOAD TASKS (UPDATED FOR PARQUET) ---
tasks = []
if os.path.exists(METADATA_FILE):
    print(f"Loading tasks from {METADATA_FILE}...")
    
    if METADATA_FILE.endswith(".parquet"):
        # Read Parquet using Pandas
        df = pd.read_parquet(METADATA_FILE)
        # Convert to list of dictionaries (records)
        tasks = df.to_dict(orient='records')
    else:
        # Fallback for JSONL
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                tasks.append(json.loads(line))
else:
    print(f"ERROR: Could not find {METADATA_FILE}")
    print("Please make sure you moved the downloaded parquet file to benchmarks/gaia/")
    exit()

print(f"Found {len(tasks)} GAIA tasks. Running first {MAX_TASKS}...")

results = []

for i, task in enumerate(tasks):
    if i >= MAX_TASKS: break
    
    task_id = task['task_id']
    question = task['Question']
    filename = task.get('file_name', '')
    # Try the standard key (with space), fallback to other common variations just in case
    correct_answer = task.get('Final answer') or task.get('final_answer') or task.get('ground_truth')
    
    # Handle NaN/None in filename
    if pd.isna(filename): filename = ""

    print(f"\nTask {i+1} (ID: {task_id})")
    
    # 1. PREPARE FILE
    file_path_abs = ""
    file_instruction = ""
    
    if filename:
        local_path = download_attachment(filename)
        if local_path:
            file_path_abs = os.path.abspath(local_path)
            # We give the agent the ABSOLUTE path so it can find it easily
            file_instruction = f"\nATTACHED FILE: {file_path_abs}\n(You must use your File tools to read/process this file.)"
        else:
            print("   Skipping task: Could not download file.")
            continue

    # 2. CONSTRUCT PROMPT
    full_prompt = (
        "You are a capable AI assistant with file access tools.\n"
        f"QUESTION: {question}"
        f"{file_instruction}\n"
        "INSTRUCTIONS:\n"
        "1. If a file is provided, YOU MUST READ IT using your tools.\n"
        "2. Solve the problem based on the file content.\n"
        "3. The final line of your response must be ONLY the answer.\n"
        "YOUR ANSWER:"
    )

    # 3. SEND TO AGENT
    # new_session=True ensures fresh memory for each task
    payload = {
        "prompt": full_prompt, 
        "new_session": True
    }
    
    start = time.time()
    status = "FAIL"
    agent_ans = ""
    
    try:
        resp = requests.post(API_URL, json=payload, timeout=600)
        
        if resp.status_code == 200:
            raw_response = str(resp.json().get("response", ""))
            
            # 4. EXTRACTION
            lines = [l.strip() for l in raw_response.split('\n') if l.strip()]
            if lines:
                agent_ans = lines[-1]
            
            # 5. SCORING
            clean_agent = normalize_answer(agent_ans)
            clean_target = normalize_answer(correct_answer)
            
            if clean_target in clean_agent:
                status = "PASS"
            else:
                status = "WRONG_ANSWER"
        else:
            status = f"HTTP {resp.status_code}"
            agent_ans = "API Error"

    except Exception as e:
        status = "ERROR"
        agent_ans = str(e)

    duration = time.time() - start
    print(f"  -> {status} ({duration:.2f}s)")
    if status != "PASS":
        print(f"     [EXPECTED]: {correct_answer}")
        print(f"     [AGENT]:    {agent_ans}")
        
    results.append({"id": task_id, "status": status})

passed = sum(1 for r in results if r['status'] == 'PASS')
print(f"\nFinal Score: {passed}/{len(results)}")