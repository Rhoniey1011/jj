import json
import os
import sys
import asyncio
import random
import aiohttp
import pyfiglet
from datetime import datetime
from web3 import Web3
from eth_account import Account
from colorama import init, Fore, Style
from fake_useragent import UserAgent

init(autoreset=False)

FAUCET_URL = "https://app.avon.xyz/api/faucet"
WALLETS_FILE = "wallets.json"
PROXY_FILE = "proxy.txt"

BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"

UA_FALLBACK = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

HEADERS_STATIC = {
    "accept": "application/json, text/plain, */*",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "origin": "https://app.avon.xyz",
    "referer": "https://app.avon.xyz/",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "content-type": "application/json"
}

ua_provider = UserAgent()


def log_green(text):
    print(f"{BOLD}{GREEN}{text}{RESET}")


def log_yellow(text):
    print(f"{BOLD}{YELLOW}{text}{RESET}")


def log_red(text):
    print(f"{BOLD}{RED}{text}{RESET}")


def banner():
    os.system("cls" if os.name == "nt" else "clear")
    ascii_art = pyfiglet.figlet_format("Yuurisandesu", font="standard")
    print(Fore.CYAN + Style.BRIGHT + ascii_art + RESET)
    print(Fore.MAGENTA + Style.BRIGHT + "Welcome to Yuuri, Avon Faucet" + RESET)
    log_green("Ready to hack the word?")
    print(f"{YELLOW}{BOLD}Current time {datetime.now().strftime('%d %m %Y %H:%M:%S')}{RESET}\n")


def set_title():
    sys.stdout.write("\x1b]2;Avon Faucet by : 佐賀県産 (YUURI)\x1b\\")
    sys.stdout.flush()


def get_user_agent():
    try:
        value = ua_provider.random
        if not value:
            return UA_FALLBACK
        return value
    except Exception:
        return UA_FALLBACK


def build_headers():
    headers = dict(HEADERS_STATIC)
    headers["user-agent"] = get_user_agent()
    sec_ua_candidates = [
        "\"Chromium\";v=\"124\", \"Not A Brand\";v=\"99\"",
        "\"Google Chrome\";v=\"124\", \"Chromium\";v=\"124\", \"Not A Brand\";v=\"99\"",
        "\"Microsoft Edge\";v=\"124\", \"Chromium\";v=\"124\", \"Not A Brand\";v=\"99\""
    ]
    platform_candidates = ["\"Windows\"", "\"macOS\"", "\"Linux\"", "\"Android\""]
    mobile_flag_candidates = ["?0", "?1"]
    language_candidates = [
        "en US,en;q=0.9",
        "en GB,en;q=0.9",
        "en US,en;q=0.8,id;q=0.7"
    ]
    headers["sec-ch-ua"] = random.choice(sec_ua_candidates)
    headers["sec-ch-ua-platform"] = random.choice(platform_candidates)
    headers["sec-ch-ua-mobile"] = random.choice(mobile_flag_candidates)
    headers["accept-language"] = random.choice(language_candidates)
    return headers


def load_proxies():
    proxies = []
    if not os.path.exists(PROXY_FILE):
        log_yellow("Proxy file not found so requests will be executed without proxy")
        return proxies
    try:
        with open(PROXY_FILE, "r") as file:
            for line in file:
                stripped = line.strip()
                if not stripped:
                    continue
                value = stripped
                if not value.startswith("http://") and not value.startswith("https://") and not value.startswith("socks5://"):
                    value = "http://" + value
                proxies.append(value)
    except Exception:
        log_red("Proxy file read error")
        return []
    if proxies:
        log_green(f"Proxy entry count detected {len(proxies)}")
    else:
        log_yellow("Proxy file did not contain valid proxy entry")
    return proxies


def create_wallet():
    account = Account.create()
    address = Web3.to_checksum_address(account.address)
    private_key_raw = account.key.hex()
    if private_key_raw.startswith("0x") or private_key_raw.startswith("0X"):
        private_key = private_key_raw
    else:
        private_key = "0x" + private_key_raw
    return address, private_key


async def save_wallet(address, private_key, file_lock):
    async with file_lock:
        data = []
        if os.path.exists(WALLETS_FILE):
            try:
                with open(WALLETS_FILE, "r") as file:
                    data = json.load(file)
            except Exception:
                data = []
        entry = {"address": address, "pk": private_key}
        data.append(entry)
        with open(WALLETS_FILE, "w") as file:
            json.dump(data, file, indent=2)


async def request_faucet(session, address, proxy_value):
    headers = build_headers()
    payload = {"address": address}
    try:
        if proxy_value:
            async with session.post(FAUCET_URL, headers=headers, json=payload, proxy=proxy_value) as response:
                status = response.status
        else:
            async with session.post(FAUCET_URL, headers=headers, json=payload) as response:
                status = response.status
        if status != 200:
            log_red(f"Faucet request failed with status code {status}")
            return False
        log_green("Faucet request completed successfully")
        return True
    except Exception:
        log_red("Faucet request network error")
        return False


async def claim_cycle(cycle_number, session, file_lock, proxy_value):
    if proxy_value:
        log_green(f"Claim cycle index {cycle_number} started using proxy configuration")
    else:
        log_green(f"Claim cycle index {cycle_number} started without proxy")
    log_green("Wallet creation process started")
    address, private_key = create_wallet()
    log_green(f"Wallet address value {address}")
    success = await request_faucet(session, address, proxy_value)
    if not success:
        log_red("Faucet claim did not succeed for current cycle")
        return
    await save_wallet(address, private_key, file_lock)
    log_green("Wallet data saved in file")
    log_green(f"Claim cycle index {cycle_number} completed")


async def run_claims(claim_count):
    timeout = aiohttp.ClientTimeout(total=None)
    file_lock = asyncio.Lock()
    proxies = load_proxies()
    async with aiohttp.ClientSession(timeout=timeout) as session:
        concurrency_limit = 50
        semaphore = asyncio.Semaphore(concurrency_limit)
        tasks = []

        async def sem_task(cycle_number, proxy_value):
            async with semaphore:
                await claim_cycle(cycle_number, session, file_lock, proxy_value)

        for i in range(1, claim_count + 1):
            if proxies:
                proxy_value = proxies[(i - 1) % len(proxies)]
            else:
                proxy_value = None
            tasks.append(asyncio.create_task(sem_task(i, proxy_value)))
        if tasks:
            await asyncio.gather(*tasks)


def main():
    set_title()
    banner()
    try:
        raw_count = input(f"{YELLOW}{BOLD}Enter claim count then press enter {RESET}")
        claim_count = int(raw_count.strip())
    except Exception:
        log_red("Claim count input value is not valid integer")
        return
    if claim_count <= 0:
        log_yellow("Claim count value is zero or negative")
        return
    log_green(f"Claim batch started with total cycle {claim_count}")
    asyncio.run(run_claims(claim_count))
    log_green("Claim batch execution completed")


if __name__ == "__main__":
    main()
