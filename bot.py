import requests
import aiohttp
import httpx
import asyncio
import json
import sys
from colorama import Fore, Style, init

init(autoreset=True)

# Base API URL and endpoint constants
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

RED = Fore.RED
YELLOW = Fore.YELLOW
GREEN = Fore.GREEN
CYAN = Fore.CYAN
MAGENTA = Fore.MAGENTA
RESET = Style.RESET_ALL
BLUE = Fore.BLUE

def log(message, level="INFO"):
    colors = {
        "ERROR": RED, 
        "WARNING": YELLOW, 
        "SUCCESS": GREEN, 
        "INFO": CYAN, 
        "DEBUG": Fore.CYAN
    }
    color = colors.get(level, "")
    print(f"{color}[{level}] {message}{RESET}")

def read_sessions(file):
    """Reads session tokens from a specified file."""
    try:
        with open(file, 'r') as f:
            sessions = [line.strip() for line in f if line.strip()]
        log(f"Read {len(sessions)} sessions from {file}", "INFO")
        return sessions
    except FileNotFoundError:
        log(f"File {file} not found.", "ERROR")
        return []

async def api_request(method, url, token=None, json_data=None):
    async with httpx.AsyncClient() as client:
        headers = {**HEADERS}
        if token:
            headers["authorization"] = f"Bearer {token}"
        if json_data is not None:
            headers["Content-Type"] = "application/json"

        try:
            response = await client.request(method, url, headers=headers, json=json_data)
            response.raise_for_status()  # Raise an error for bad responses
            return response.json()
        except httpx.HTTPStatusError as http_err:
            log(f"HTTP error: {http_err}", "ERROR")
        except Exception as err:
            log(f"Error: {err}", "ERROR")
    return None



async def login(session):
    """Logs in to the API using the session token."""
    url = f"{AUTH_URL}?{session}"
    res = await api_request("GET", url)
    token = res.get("token") if res else None
    log("Login successful." if token else "Login failed.", "SUCCESS" if token else "ERROR")
    return token

async def check_in(token):
    """Performs the daily check-in for the user."""
    res = await api_request("POST", CHECKIN_URL, token)
    if res:
        if "dailyReward" in res and not res.get("claimed", True):
            log("Daily check-in successful.", "SUCCESS")
        else:
            log("Already checked in today.", "WARNING")
    else:
        log("Check-in failed or already done.", "WARNING")

async def check_balance(token):
    """Checks the user's account balance."""
    res = await api_request("GET", BALANCE_URL, token)
    if res:
        username = res.get("profile", {}).get("telegramUsername", "Unknown")
        balance = res.get("balance", {}).get("balance", "0")
        log(f"Account: {GREEN}{username}{RESET}, Balance: {GREEN}{balance} HOLD{RESET}", "INFO")
        return balance
    log("Failed to fetch balance.", "ERROR")
    return "0"

async def get_diamond_state(token):
    """Fetches the diamond state from the API."""
    try:
        hdr = {**HEADERS, "authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(DIAMOND_STATE_URL, headers=hdr) as response:
                response.raise_for_status()  # Raise an error for bad responses
                diamond_data = await response.json()  # Get the JSON response

                # Safely extract hold_amount and gem_name
                hold_amount = diamond_data.get("rewards", {}).get("hold", {}).get("amount", "N/A")
                gem_name = diamond_data.get("rewards", {}).get("gem", {}).get("name", "N/A")

                # Log the values correctly after extracting them
                log(f"Diamond state fetched successfully: Hold Amount: {hold_amount} HOLD, Gem Name: {gem_name}", "INFO")
                return diamond_data  # Return the whole diamond data for further processing
    except Exception as e:
        log(f"Error getting diamond state: {str(e)}", "ERROR")
    return {}

async def complete_diamond(token, diamond_num):
    """Completes a diamond task."""
    try:
        hdr = {**HEADERS, "authorization": f"Bearer {token}", "content-type": "application/json"}
        res = await api_request("POST", DIAMOND_COMPLETE_URL, token, json={"diamondNumber": diamond_num})
        log(f"Diamond complete response: {res.status_code} - {res.text}", "DEBUG")

        if res:
            log("Diamond completed successfully.", "SUCCESS")
            return res  # Safely parse JSON response
        else:
            log(f"Failed to complete diamond.", "ERROR")
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

async def get_farming_state(token):
    """Checks the current farming state."""
    try:
        res = await api_request("GET", FARM_STATE_URL, token)
        if res:
            state = res.get("state", "")
            farmed_amount = res.get("farmed", 0)
            if state == "farmed":
                log(f"Farming completed. Farmed amount: {GREEN}{farmed_amount}{RESET}", "INFO")
                return "farmed", res
            elif state == "farming":
                left_time = res.get("timings", {}).get("left", 0)
                formatted_time = format_time(left_time)
                log(f"Farming is in progress. Time left: {YELLOW}{formatted_time}{RESET}", "INFO")
                return "farming", res
            else:
                log("Farming state is idling or unknown.", "WARNING")
                return "idling", res
        else:
            log(f"Failed to check farming state.", "ERROR")
            return "error", {}
    except Exception as e:
        log(f"Error checking farming state: {str(e)}", "ERROR")
        return {}

async def claim_farming(token):
    try:
        log(f"Attempting to claim farming rewards with token: {token}", "DEBUG")
        res = await api_request("POST", CLAIM_FARM_URL, token)

        if res:
            if res.get("success"):
                log("Farming reward claimed successfully.", "SUCCESS")
            else:
                log(f"Failed to claim farming rewards: {res.get('message', 'No message provided')}", "ERROR")
        else:
            log("Response was None or invalid.", "ERROR")
    except httpx.HTTPStatusError as http_err:
        log(f"HTTP error: {http_err}", "ERROR")
    except Exception as e:
        log(f"An error occurred during farming rewards management: {str(e)}", "ERROR")

async def execute_task(token, task):
    task_id = task["id"]
    status = task.get("status")

    if status == "available":
        log(f"Executing task {task_id}...", "INFO")
        response = await api_request("POST", f"{TASKS_URL}/{task_id}/execute", token)

        if response:
            log(f"Task {task_id} executed successfully.", "SUCCESS")
        else:
            log(f"Failed to execute task {task_id}.", "ERROR")
    
    elif status == "in-progress":
        log(f"Task {task_id} is already in-progress.", "WARNING")
    
    elif status == "verified":
        log(f"Task {task_id} is already verified and does not require execution.", "INFO")

    else:
        log(f"Task {task_id} has an unknown status: {status}. Please check the API documentation.", "ERROR")


async def fetch_tasks(token):
    res = await api_request("GET", TASKS_URL, token)
    if res and "tasks" in res:
        log(f"Found {len(res['tasks'])} available tasks.", "INFO")
        for task in res['tasks']:
            log(f"Task ID: {task['id']}, Status: {task.get('status')}", "DEBUG")
        return res["tasks"]
    else:
        log("Failed to fetch tasks or no tasks available.", "WARNING")
    return []

async def process_sessions(file, execute_tasks):
    sessions = read_sessions(file)
    if not sessions:
        log("No sessions to process.", "ERROR")
        return

    total_wait_times = []
    for idx, session in enumerate(sessions):
        log(f"Processing session: Token {CYAN}{idx + 1}{RESET}", "INFO")
        token = await login(session)  # Await the login function
        if not token:
            log(f"Skipping session Token {idx + 1} due to login failure.", "WARNING")
            continue

        await check_in(token)
        balance = await check_balance(token)  # Ensure you await here
        log(f"Current balance for Token {idx + 1}: {balance} HOLD", "INFO")

        diamond_state = await get_diamond_state(token)

        if diamond_state and "rewards" in diamond_state:
            hold_amount = diamond_state["rewards"].get("hold", {}).get("amount", "N/A")
            gem_name = diamond_state["rewards"].get("gem", {}).get("name", "N/A")
            log(f"Hold Amount: {hold_amount}, Gem Name: {gem_name}", "INFO")
        else:
            log("No rewards data found in diamond state.", "WARNING")

        log(f"Starting farming check...", "INFO")
        farming_state, farming_data = await get_farming_state(token)

        if farming_state == "farmed":
            await claim_farming(token)
        else:
            log(f"Cannot claim farming rewards yet. Current state: {farming_state}.", "WARNING")

        if execute_tasks:
            tasks = await fetch_tasks(token)
            if tasks:
                for task in tasks:
                    await execute_task(token, task)

    log("All sessions processed.", "SUCCESS")



async def countdown(seconds):
    """Countdown function to wait for the given number of seconds."""
    while seconds:
        mins, secs = divmod(seconds, 60)
        timer = f"{mins:02}:{secs:02}"
        print(timer, end="\r")
        await asyncio.sleep(1)
        seconds -= 1
    print("Time's up!")

async def main():
    """Main function to execute the processing of sessions."""
    # Continuously process sessions and wait
    while True:
        await process_sessions("sessions.txt", execute_tasks)
        await countdown(duration_between_runs)

if __name__ == "__main__":
    try:
        duration_between_runs = 3600  # Duration in seconds (1 hour)
        user_input = input(f"Do you want to execute tasks for all sessions? (y/n): ")
        execute_tasks = user_input.lower() == 'y'

        asyncio.run(main())
    except KeyboardInterrupt:
        log("Script interrupted by user. Exiting gracefully...", "WARNING")
