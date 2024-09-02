import requests
import time
from datetime import datetime, timezone, timedelta
from colorama import Fore, Style, init
import sys

init(autoreset=True)

BASE = "https://fintopio-tg.fintopio.com/api"
AUTH_URL = f"{BASE}/auth/telegram"
CHECKIN_URL = f"{BASE}/daily-checkins"
DIAMOND_STATE_URL = f"{BASE}/clicker/diamond/state"
DIAMOND_COMPLETE_URL = f"{BASE}/clicker/diamond/complete"
FARM_STATE_URL = f"{BASE}/farming/state"
FARM_URL = f"{BASE}/farming/farm"
CLAIM_FARM_URL = f"{BASE}/farming/claim"
BALANCE_URL = f"{BASE}/fast/init"
TASKS_URL = f"{BASE}/hold/tasks"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "priority": "u=1, i",
    "sec-ch-ua": "\"Chromium\";v=\"128\", \"Not;A=Brand\";v=\"24\", \"Microsoft Edge\";v=\"128\", \"Microsoft Edge WebView2\";v=\"128\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "webapp": "true",
    "Referer": "https://fintopio-tg.fintopio.com/?tgWebAppStartParam=reflink-reflink_dr6rbXM5Cz5iM9d7-",
    "Referrer-Policy": "strict-origin-when-cross-origin"
}

# Variabel warna untuk mempersingkat kode
RED, YELLOW, GREEN, CYAN, MAGENTA, RESET = Fore.RED, Fore.YELLOW, Fore.GREEN, Fore.CYAN, Fore.MAGENTA, Style.RESET_ALL

def log(message, level="INFO"):
    colors = {"ERROR": RED, "WARNING": YELLOW, "SUCCESS": GREEN, "INFO": CYAN}
    color = colors.get(level, "")
    print(f"{color}[{level}] {message}{RESET}")

def to_utc(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc)

def read_sessions(file):
    try:
        with open(file, 'r') as f:
            sessions = [line.strip() for line in f if line.strip()]
        log(f"Read {len(sessions)} sessions from {file}", "INFO")
        return sessions
    except FileNotFoundError:
        log(f"File {file} not found.", "ERROR")
        return []

def login(session):
    try:
        url = f"{AUTH_URL}?{session}"
        res = requests.get(url, headers=HEADERS).json()
        token = res.get("token")
        log("Login successful.", "SUCCESS") if token else log("Login failed.", "ERROR")
        return token
    except Exception as e:
        log(f"Error during login: {str(e)}", "ERROR")
        return None

def check_in(token):
    try:
        hdr = {**HEADERS, "authorization": f"Bearer {token}"}
        res = requests.post(CHECKIN_URL, headers=hdr).json()
        if "dailyReward" in res and not res.get("claimed", True):
            log("Daily check-in successful.", "SUCCESS")
        elif any(r.get("status") == "now" for r in res.get("rewards", [])):
            log("Already checked in today.", "WARNING")
        else:
            log("Check-in already done or error.", "WARNING")
        return res
    except Exception as e:
        log(f"Error during daily check-in: {str(e)}", "ERROR")
        return None

def check_balance(token):
    try:
        hdr = {**HEADERS, "authorization": f"Bearer {token}"}
        res = requests.get(BALANCE_URL, headers=hdr)
        if res.status_code == 200:
            try:
                res_data = res.json()
                username = res_data.get("profile", {}).get("telegramUsername", "Unknown")
                balance = res_data.get("balance", {}).get("balance", "0")
                log(f"Account: {GREEN}{username}{RESET}, Balance: {GREEN}{balance} HOLD{RESET}", "INFO")
                return balance
            except ValueError:
                log("Failed to parse JSON response from balance check.", "ERROR")
                return "0"
        else:
            log(f"Failed to fetch balance. Status Code: {res.status_code}", "ERROR")
            return "0"
    except Exception as e:
        log(f"Error during balance check: {str(e)}", "ERROR")
        return "0"

def get_diamond_state(token):
    try:
        hdr = {**HEADERS, "authorization": f"Bearer {token}"}
        return requests.get(DIAMOND_STATE_URL, headers=hdr).json()
    except Exception as e:
        log(f"Error getting diamond state: {str(e)}", "ERROR")
        return {}

def complete_diamond(token, diamond_num):
    try:
        hdr = {**HEADERS, "authorization": f"Bearer {token}", "content-type": "application/json"}
        res = requests.post(DIAMOND_COMPLETE_URL, headers=hdr, json={"diamondNumber": diamond_num})
        if res.status_code == 200:
            log("Diamond completed successfully.", "SUCCESS")
            try:
                return res.json()
            except ValueError:
                log("Failed to parse JSON response from complete_diamond.", "ERROR")
                return {}
        else:
            log(f"Failed to complete diamond. Status Code: {res.status_code}", "ERROR")
            return {}
    except Exception as e:
        log(f"Error during diamond completion: {str(e)}", "ERROR")
        return {}

def get_farming_state(token):
    try:
        hdr = {**HEADERS, "authorization": f"Bearer {token}"}
        res = requests.get(FARM_STATE_URL, headers=hdr)
        if res.status_code == 200:
            try:
                res_data = res.json()
                state = res_data.get("state", "")
                farmed_amount = res_data.get("farmed", 0)
                finish_timestamp = res_data.get("timings", {}).get("finish", 0)
                left_time = res_data.get("timings", {}).get("left", 0)
                
                if state == "farmed":
                    log(f"Farming completed. Farmed amount: {GREEN}{farmed_amount}{RESET}", "INFO")
                    return "farmed", res_data
                elif state == "farming" and left_time > 0:
                    current_time = datetime.now(timezone.utc).timestamp() * 1000
                    if current_time > finish_timestamp:
                        log("Farming should have completed. Time to claim reward.", "INFO")
                        return "farmed", res_data
                    else:
                        log(f"Farming is in progress. Time left: {YELLOW}{timedelta(milliseconds=left_time)}{RESET}", "INFO")
                        return "farming", res_data
                else:
                    log("Farming state is idling or unknown.", "WARNING")
                    return "idling", res_data
            except ValueError:
                log("Failed to parse JSON response from check farming state.", "ERROR")
                return "error", {}
        else:
            log(f"Failed to check farming state. Status Code: {res.status_code}", "ERROR")
            return "error", {}
    except Exception as e:
        log(f"Error checking farming state: {str(e)}", "ERROR")
        return "error", {}

def claim_farming(token):
    try:
        hdr = {**HEADERS, "authorization": f"Bearer {token}"}
        log("Attempting to claim farming reward...", "INFO")
        time.sleep(2)
        res = requests.post(CLAIM_FARM_URL, headers=hdr)
        if res.status_code == 200:
            try:
                res_json = res.json()
                if res_json.get("state") == "idling":
                    log(f"Farming reward claimed successfully at: {GREEN}{datetime.now(timezone.utc)} UTC{RESET}", "SUCCESS")
                    return True
                else:
                    log(f"Failed to claim farming reward. Status: {res_json.get('state')}", "ERROR")
                    return False
            except ValueError:
                log(f"Failed to parse JSON response from claim_farming. Response text: {res.text}", "ERROR")
                return False
        else:
            log(f"Failed to claim farming reward. Status Code: {res.status_code}, Response: {res.text}", "ERROR")
            return False
    except Exception as e:
        log(f"Error claiming farming reward: {str(e)}", "ERROR")
        return False

def start_farming(token):
    try:
        hdr = {**HEADERS, "authorization": f"Bearer {token}"}
        log("Starting new farming session...", "INFO")
        time.sleep(2)
        res = requests.post(FARM_URL, headers=hdr)
        if res.status_code == 200:
            try:
                res_data = res.json()
                finish = res_data.get("timings", {}).get("finish")
                if finish:
                    finish_time = to_utc(finish / 1000)
                    log(f"Farming started at: {CYAN}{datetime.now(timezone.utc)} UTC{RESET}", "INFO")
                    log(f"Farming will finish at: {YELLOW}{finish_time} UTC{RESET}", "INFO")
                    return True
                else:
                    log("No finish time available in farming response.", "WARNING")
            except ValueError:
                log("Failed to parse JSON response from start_farming.", "ERROR")
                return False
        else:
            log(f"Failed to start farming. Status Code: {res.status_code}", "ERROR")
        return False
    except Exception as e:
        log(f"Error during farming: {str(e)}", "ERROR")
        return False

def manage_farming(token):
    try:
        log("Checking farming state...", "INFO")
        state, state_data = get_farming_state(token)
        time.sleep(2)
        
        if state == "farmed":
            log("Farming is completed. Attempting to claim the reward...", "INFO")
            if claim_farming(token):
                time.sleep(5)
                start_farming(token)
            else:
                log("Failed to claim farming reward, skipping farming start.", "ERROR")
        
        elif state == "farming":
            left_time = state_data.get("timings", {}).get("left", 0)
            log(f"Farming is still in progress. Time left: {YELLOW}{timedelta(milliseconds=left_time)}{RESET}", "INFO")
            log("Skipping waiting for farming to complete and moving to next process...", "INFO")
        
        elif state == "idling":
            start_farming(token)
        
        else:
            log("Unknown farming state or error occurred.", "ERROR")
    
    except Exception as e:
        log(f"Error in farming management: {str(e)}", "ERROR")

def dynamic_countdown(seconds):
    try:
        while seconds > 0:
            time_left = timedelta(seconds=seconds)
            print(f"\r[INFO] Next action in: {YELLOW}{time_left}{RESET}", end="")
            sys.stdout.flush()
            time.sleep(1)
            seconds -= 1
        print()
    except KeyboardInterrupt:
        log("Countdown interrupted by user.", "WARNING")

def fetch_tasks(token):
    hdr = {**HEADERS, "authorization": f"Bearer {token}"}
    res = requests.get(TASKS_URL, headers=hdr).json()
    if "tasks" in res:
        tasks = res["tasks"]
        log(f"Found {len(tasks)} available tasks.", "INFO")
        return tasks
    else:
        log("Failed to fetch tasks or no tasks available.", "WARNING")
        return []

def execute_task(token, task):
    task_id = task["id"]
    status = task.get("status")

    if status == "verified":
        log(f"Task {task_id} is verified, claiming reward...", "INFO")
        time.sleep(5)
        return claim_task(token, task_id)
    elif status == "available":
        log(f"Task {task_id} is available, starting task...", "INFO")
        time.sleep(5)
        if not start_task(token, task_id):
            log(f"Failed to start task {task_id}.", "ERROR")
            return False
        time.sleep(5)
        return verify_task(token, task_id) and claim_task(token, task_id)
    elif status == "in-progress":
        log(f"Task {task_id} status is 'in-progress', waiting for the next iteration.", "WARNING")
        return False
    else:
        log(f"Task {task_id} status is '{status}', no action taken.", "WARNING")
        return False

def start_task(token, task_id):
    hdr = {**HEADERS, "authorization": f"Bearer {token}"}
    start_url = f"{TASKS_URL}/{task_id}/start"
    res = requests.post(start_url, headers=hdr).json()
    if res.get("status") == "in-progress":
        log(f"Task {task_id} started successfully.", "SUCCESS")
        return True
    return False

def verify_task(token, task_id):
    hdr = {**HEADERS, "authorization": f"Bearer {token}"}
    verify_url = f"{TASKS_URL}/{task_id}/verify"
    res = requests.post(verify_url, headers=hdr).json()
    if res.get("status") == "completed":
        log(f"Task {task_id} verified successfully.", "SUCCESS")
        return True
    else:
        log(f"Failed to verify task {task_id}.", "ERROR")
        return False

def claim_task(token, task_id):
    hdr = {**HEADERS, "authorization": f"Bearer {token}"}
    claim_url = f"{TASKS_URL}/{task_id}/claim"
    res = requests.post(claim_url, headers=hdr).json()
    if res.get("status") == "completed":
        log(f"Task {task_id} reward claimed successfully.", "SUCCESS")
        return True
    else:
        log(f"Failed to claim reward for task {task_id}.", "ERROR")
        return False

def dynamic_countdown(seconds):
    while seconds > 0:
        time_left = timedelta(seconds=seconds)
        print(f"\r[INFO] Next action in: {Fore.YELLOW}{time_left}{Style.RESET_ALL}", end="")
        sys.stdout.flush()
        time.sleep(1)
        seconds -= 1
    print()

def process_sessions(file, execute_tasks, retry=False):
    sessions = read_sessions(file)
    if not sessions:
        log("No sessions to process.", "ERROR")
        return
    
    total_wait_times = []
    for idx, session in enumerate(sessions):
        log(f"Processing session: Token {Fore.CYAN}{idx + 1}{Style.RESET_ALL}", "INFO")
        token = login(session)
        if not token:
            log(f"Skipping session Token {idx + 1} due to login failure.", "WARNING")
            continue

        check_in(token)
        balance = check_balance(token)
        log(f"Current balance for Token {Fore.CYAN}{idx + 1}{Style.RESET_ALL}: {Fore.GREEN}{balance} HOLD{Style.RESET_ALL}", "INFO")
        state = get_diamond_state(token)
        
        if state.get("state") == "available":
            diamond_num = state.get("diamondNumber")
            log(f"Diamond {Fore.MAGENTA}{diamond_num}{Style.RESET_ALL} available for Token {idx + 1}, completing...", "INFO")
            complete_res = complete_diamond(token, diamond_num)
            log("Complete response received.", "INFO")
            log("Starting farming...", "INFO")
            farm_wait_time = farm(token)
            if farm_wait_time:
                total_wait_times.append(farm_wait_time)
        else:
            log(f"Diamond not available for Token {idx + 1}, moving to next session.", "WARNING")
            next_at = state.get("timings", {}).get("nextAt")
            if next_at:
                next_time = to_utc(next_at / 1000)
                log(f"Next diamond check for Token {idx + 1} at: {Fore.YELLOW}{next_time} UTC{Style.RESET_ALL}", "INFO")
                wait_time = (next_at / 1000) - time.time()
                if wait_time > 0:
                    total_wait_times.append(wait_time)

        if execute_tasks:
            tasks = fetch_tasks(token)
            if tasks:
                for task in tasks:
                    log(f"Processing task {task['id']} for Token {idx + 1}...", "INFO")
                    execute_task(token, task)

    if total_wait_times:
        next_wait_time = max(0, min(total_wait_times))
        next_wait_time_human = to_utc(time.time() + next_wait_time)
        log(f"All sessions processed. Next action in {Fore.YELLOW}{next_wait_time:.2f} seconds{Style.RESET_ALL}, at {Fore.YELLOW}{next_wait_time_human} UTC{Style.RESET_ALL}.", "INFO")
        dynamic_countdown(int(next_wait_time))
        process_sessions(file, execute_tasks, retry=True)
    elif retry:
        log("Retrying to process tasks that were in-progress.", "INFO")
        process_sessions(file, execute_tasks, retry=False)
    else:
        log("All sessions processed. No further actions required.", "SUCCESS")

def process_sessions(file, execute_tasks, retry=False):
    try:
        sessions = read_sessions(file)
        if not sessions:
            log("No sessions to process.", "ERROR")
            return
        
        total_wait_times = []
        for idx, session in enumerate(sessions):
            log(f"Processing session: Token {CYAN}{idx + 1}{RESET}", "INFO")
            token = login(session)
            if not token:
                log(f"Skipping session Token {idx + 1} due to login failure.", "WARNING")
                continue

            check_in(token)
            balance = check_balance(token)
            log(f"Current balance for Token {CYAN}{idx + 1}{RESET}: {GREEN}{balance} HOLD{RESET}", "INFO")
            state = get_diamond_state(token)
            
            if state.get("state") == "available":
                diamond_num = state.get("diamondNumber")
                log(f"Diamond {MAGENTA}{diamond_num}{RESET} available for Token {idx + 1}, completing...", "INFO")
                complete_res = complete_diamond(token, diamond_num)
                log("Complete response received.", "INFO")
            
            log("Starting farming check...", "INFO")
            manage_farming(token)
            
            next_at = state.get("timings", {}).get("nextAt")
            if next_at:
                next_time = to_utc(next_at / 1000)
                log(f"Next diamond check for Token {idx + 1} at: {YELLOW}{next_time} UTC{RESET}", "INFO")
                wait_time = (next_at / 1000) - time.time()
                if wait_time > 0:
                    total_wait_times.append(wait_time)

            if execute_tasks:
                tasks = fetch_tasks(token)
                if tasks:
                    for task in tasks:
                        log(f"Processing task {task['id']} for Token {idx + 1}...", "INFO")
                        execute_task(token, task)

        if total_wait_times:
            next_wait_time = max(0, min(total_wait_times))
            next_wait_time_human = to_utc(time.time() + next_wait_time)
            log(f"All sessions processed. Next action in {YELLOW}{next_wait_time:.2f} seconds{RESET}, at {YELLOW}{next_wait_time_human} UTC{RESET}.", "INFO")
            dynamic_countdown(int(next_wait_time))
            process_sessions(file, execute_tasks, retry=True)
        elif retry:
            log("Retrying to process tasks that were in-progress.", "INFO")
            process_sessions(file, execute_tasks, retry=False)
        else:
            log("All sessions processed. No further actions required.", "SUCCESS")
    except KeyboardInterrupt:
        log("Process interrupted by user.", "WARNING")
    except Exception as e:
        log(f"Unexpected error occurred: {str(e)}", "ERROR")

if __name__ == "__main__":
    try:
        user_input = input(f"{CYAN}Do you want to execute tasks for all sessions? (y/n): {RESET}")
        execute_tasks = user_input.lower() == 'y'
        process_sessions("sessions.txt", execute_tasks)
    except KeyboardInterrupt:
        log("Script interrupted by user. Exiting gracefully...", "WARNING")
