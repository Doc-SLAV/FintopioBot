
import requests
import time
from colorama import Fore, Style, init
import json
import asyncio
import sys

init(autoreset=True)

BASE = "https://fintopio-tg.fintopio.com/api"
AUTH_URL = f"{BASE}/auth/telegram"
CHECKIN_URL = f"{BASE}/daily-checkins"
BALANCE_URL = f"{BASE}/fast/init"
DIAMOND_STATE_URL = f"{BASE}/clicker/diamond/state"
DIAMOND_COMPLETE_URL = f"{BASE}/clicker/diamond/complete"
FARM_STATE_URL = f"{BASE}/farming/state"
CLAIM_FARM_URL = f"{BASE}/farming/claim"
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
    "Referer": "https://fintopio-tg.fintopio.com/hold",
    "Referrer-Policy": "strict-origin-when-cross-origin"
}

# Color variables for console output
RED, YELLOW, GREEN, CYAN, MAGENTA, RESET, BLUE = Fore.RED, Fore.YELLOW, Fore.GREEN, Fore.CYAN, Fore.MAGENTA, Style.RESET_ALL, Fore.BLUE

def log(message, level="INFO"):
    colors = {"ERROR": RED, "WARNING": YELLOW, "SUCCESS": GREEN, "INFO": CYAN, "DEBUG": BLUE}
    color = colors.get(level, "")
    print(f"{color}[{level}] {message}{RESET}")

def read_sessions(file):
    try:
        with open(file, 'r') as f:
            sessions = [line.strip() for line in f if line.strip()]
        log(f"Read {len(sessions)} sessions from {file}", "INFO")
        return sessions
    except FileNotFoundError:
        log(f"File {file} not found.", "ERROR")
        return []

def api_request(method, url, token=None, json_data=None):
    hdr = {**HEADERS}
    if token:
        hdr["authorization"] = f"Bearer {token}"
    
    try:
        response = requests.request(method, url, headers=hdr, json=json_data)
        response.raise_for_status()  # Raise an error for bad responses
        return response.json()
    except requests.HTTPError as http_err:
        log(f"HTTP error: {http_err}", "ERROR")
    except Exception as err:
        log(f"Error: {err}", "ERROR")
    return None

def login(session):
    url = f"{AUTH_URL}?{session}"
    res = api_request("GET", url)
    token = res.get("token") if res else None
    log("Login successful." if token else "Login failed.", "SUCCESS" if token else "ERROR")
    return token

def check_in(token):
    res = api_request("POST", CHECKIN_URL, token)
    if res and "dailyReward" in res and not res.get("claimed", True):
        log("Daily check-in successful.", "SUCCESS")
    elif res:
        log("Already checked in today.", "WARNING")
    else:
        log("Check-in already done or error.", "WARNING")

def check_balance(token):
    res = api_request("GET", BALANCE_URL, token)
    if res:
        username = res.get("profile", {}).get("telegramUsername", "Unknown")
        balance = res.get("balance", {}).get("balance", "0")
        log(f"Account: {GREEN}{username}{RESET}, Balance: {GREEN}{balance} HOLD{RESET}", "INFO")
        return balance
    log("Failed to fetch balance.", "ERROR")
    return "0"

def get_diamond_state(token):
    try:
        hdr = {**HEADERS, "authorization": f"Bearer {token}"}
        response = requests.get(DIAMOND_STATE_URL, headers=hdr)
        response.raise_for_status()  # Raise an error for bad responses
        
        diamond_data = response.json()  # Get the JSON response

        # Safely extract hold_amount and gem_name
        hold_amount = diamond_data.get("rewards", {}).get("hold", {}).get("amount", "N/A")
        gem_name = diamond_data.get("rewards", {}).get("gem", {}).get("name", "N/A")

        # Log the values correctly after extracting them
        log(f"Diamond state fetched successfully: Hold Amount: {hold_amount} HOLD, Gem Name: {gem_name}", "INFO")
        
        return diamond_data  # Return the whole diamond data for further processing
    except requests.HTTPError as http_err:
        log(f"HTTP error occurred: {http_err}", "ERROR")
    except Exception as e:
        log(f"Error getting diamond state: {str(e)}", "ERROR")
    return {}

def complete_diamond(token, diamond_num):
    try:
        hdr = {**HEADERS, "authorization": f"Bearer {token}", "content-type": "application/json"}
        res = requests.post(DIAMOND_COMPLETE_URL, headers=hdr, json={"diamondNumber": diamond_num})

        log(f"Diamond complete response: {res.status_code} - {res.text}", "DEBUG")

        if res.status_code == 200:
            log("Diamond completed successfully.", "SUCCESS")
            return res.json()  # Safely parse JSON response
        else:
            log(f"Failed to complete diamond. Status Code: {res.status_code}, Response: {res.text}", "ERROR")
            return {}
    except Exception as e:
        log(f"Error during diamond completion: {str(e)}", "ERROR")
        return {}

def format_time(ms):
    """Convert milliseconds to hh:mm:ss format."""
    total_seconds = ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}"

def get_farming_state(token):
    try:
        hdr = {**HEADERS, "authorization": f"Bearer {token}"}
        res = requests.get(FARM_STATE_URL, headers=hdr)
        if res.status_code == 200:
            res_data = res.json()
            state = res_data.get("state", "")
            farmed_amount = res_data.get("farmed", 0)
            if state == "farmed":
                log(f"Farming completed. Farmed amount: {GREEN}{farmed_amount}{RESET}", "INFO")
                return "farmed", res_data
            elif state == "farming":
                left_time = res_data.get("timings", {}).get("left", 0)
                formatted_time = format_time(left_time)
                log(f"Farming is in progress. Time left: {YELLOW}{formatted_time}{RESET}", "INFO")
                return "farming", res_data
            else:
                log("Farming state is idling or unknown.", "WARNING")
                return "idling", res_data
        else:
            log(f"Failed to check farming state. Status Code: {res.status_code}", "ERROR")
            return "error", {}
    except Exception as e:
        log(f"Already claimed Gem.", "WARNING")
        return {}

def claim_farming(token):
    try:
        hdr = {**HEADERS, "authorization": f"Bearer {token}"}
        res = requests.post(CLAIM_FARM_URL, headers=hdr)

        if res.status_code == 200:
            log("Farming reward claimed successfully.", "SUCCESS")
        else:
            log("Already claimed Farm.", "INFO")
    except Exception as e:
        log("Farming rewards management failed.", "INFO")


def execute_task(token, task):
    task_id = task["id"]
    status = task.get("status")
    
    if status == "available":
        log(f"Executing task {task_id}...", "INFO")
        # Assuming there's an endpoint to execute the task
        response = api_request("POST", f"{TASKS_URL}/{task_id}/execute", token)
        
        if response:
            log(f"Task {task_id} executed successfully.", "SUCCESS")
        else:
            log(f"Failed to execute task {task_id}.", "ERROR")
    
    elif status == "in-progress":
        log(f"Task {task_id} is already in-progress.", "WARNING")
    else:
        log(f"Task {task_id} status is unknown.", "ERROR")

def fetch_tasks(token):
    res = api_request("GET", TASKS_URL, token)
    if res and "tasks" in res:
        log(f"Found {len(res['tasks'])} available tasks.", "INFO")
        for task in res['tasks']:
            log(f"Task ID: {task['id']}, Status: {task.get('status')}", "DEBUG")
        return res["tasks"]
    log("Failed to fetch tasks or no tasks available.", "WARNING")
    return []


def process_sessions(file, execute_tasks):
    try:
        sessions = read_sessions(file)
        if not sessions:
            return
        
        for idx, session in enumerate(sessions):
            log(f"Processing session: Token {CYAN}{idx + 1}{RESET}", "INFO")
            
            token = login(session)
            if not token:
                continue
            
            try:
                # Process the session: Check in, balance, diamond state, farming, and tasks
                check_in(token)
                
                # Fetch diamond state within the session context
                diamond_state = get_diamond_state(token)

                # Safely access rewards
                if diamond_state and "rewards" in diamond_state:
                    hold_amount = diamond_state["rewards"].get("hold", {}).get("amount", "N/A")
                    gem_name = diamond_state["rewards"].get("gem", {}).get("name", "N/A")
                    log(f"Hold Amount: {hold_amount}, Gem Name: {gem_name}", "INFO")
                else:
                    log("No rewards data found in diamond state.", "WARNING")

                log(f"Starting farming check...", "INFO")
                claim_farming(token)
                
                if execute_tasks:
                    tasks = fetch_tasks(token)
                    if tasks:
                        for task in tasks:
                            execute_task(token, task)
            
            except Exception as session_error:
                log(f"Error while processing session Token {CYAN}{idx + 1}{RESET}: {session_error}", "ERROR")

        log("All sessions processed.", "SUCCESS")

    except KeyboardInterrupt:
        log("Process interrupted by user. Exiting session processing.", "WARNING")
        sys.exit(0)  # Exit the entire script immediately

    except Exception as e:
        log(f"Unexpected error occurred: {str(e)}", "ERROR")

async def countdown(t):
    try:
        for i in range(t, 0, -1):
            minute, seconds = divmod(i, 60)
            hour, minute = divmod(minute, 60)
            seconds = str(seconds).zfill(2)
            minute = str(minute).zfill(2)
            hour = str(hour).zfill(2)

            # Use sys.stdout.write to display countdown on same line
            sys.stdout.write(f"Waiting for {hour}:{minute}:{seconds} remaining...\r")
            sys.stdout.flush()  # Ensure the output is written immediately

            # Asynchronous sleep
            await asyncio.sleep(1)
        log("Countdown complete! Proceeding with next session.", "SUCCESS")

    except KeyboardInterrupt:
        log("Countdown interrupted by user.", "WARNING")
        sys.exit(0)


if __name__ == "__main__":
    try:
        duration_between_runs = 3600  # Duration in seconds (1 hour)
        user_input = input(f"Do you want to execute tasks for all sessions? (y/n): ")
        execute_tasks = user_input.lower() == 'y'

        # Continuously process sessions and wait
        while True:
            process_sessions("sessions.txt", execute_tasks)
            
            # Run the countdown function asynchronously
            asyncio.run(countdown(duration_between_runs))

    except KeyboardInterrupt:
        log("Script interrupted by user. Exiting gracefully...", "WARNING")
