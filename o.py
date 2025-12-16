import asyncio
from datetime import datetime
from dotenv import load_dotenv
from eth_account import Account
from colorama import Fore, Style, init
import pyfiglet
import aiohttp
import os
import sys
import json
import random
from faker import Faker
from web3 import Web3

BASE_URL = "https://campapi.diamante.io/api/v1"

init(autoreset=False)

BOLD = Style.BRIGHT
RESET = Style.RESET_ALL
GREEN = Fore.GREEN + BOLD
YELLOW = Fore.YELLOW + BOLD
RED = Fore.RED + BOLD

ASCII_BANNER = pyfiglet.figlet_format("Yuurisandesu", font="standard")
INFO_TOGGLE = 0

def set_title():
    sys.stdout.write("\x1b]2;Diamante Testnet by : 佐賀県産 (YUURI)\x1b\\")
    sys.stdout.flush()

def render_screen():
    os.system("cls" if os.name == "nt" else "clear")
    print(Fore.CYAN + Style.BRIGHT + ASCII_BANNER + RESET)
    print(Fore.MAGENTA + Style.BRIGHT + "Welcome to Yuuri Diamante Testnet" + RESET)
    print(GREEN + "Ready to hack the world" + RESET)
    print(YELLOW + BOLD + "Current time " + datetime.now().strftime("%d/%m/%Y %H:%M:%S") + RESET)
    print()

def banner():
    render_screen()

def log_info(message):
    global INFO_TOGGLE
    if INFO_TOGGLE == 0:
        color = GREEN
        INFO_TOGGLE = 1
    else:
        color = YELLOW
        INFO_TOGGLE = 0
    line = color + "INFO " + message + RESET
    print(line)

def log_warn(message):
    line = YELLOW + "WARN " + message + RESET
    print(line)

def log_error(message):
    line = RED + "ERROR " + message + RESET
    print(line)

def load_private_keys():
    load_dotenv()
    items = []
    for key, value in os.environ.items():
        if key.startswith("PRIVATEKEY_") and value:
            try:
                index = int(key.split("_", 1)[1])
            except ValueError:
                index = 0
            items.append((index, value.strip()))
    items.sort(key=lambda pair: pair[0])
    keys = [value for _, value in items]
    return keys

async def build_session():
    access_header = os.getenv("ACCESS_HEADER_TOKEN", "key")
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "ja,en-US;q=0.9,en;q=0.8",
        "access-token": access_header,
        "cache-control": "no-cache",
        "origin": "https://campaign.diamante.io",
        "pragma": "no-cache",
        "referer": "https://campaign.diamante.io/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
    }
    session = aiohttp.ClientSession(headers=headers)
    return session

async def refresh_session(session):
    access_header = os.getenv("ACCESS_HEADER_TOKEN", "key")
    session.headers["access-token"] = access_header

async def send_request(session, method, url, **kwargs):
    attempt = 0
    while True:
        attempt += 1
        try:
            if method == "GET":
                async with session.get(url, timeout=30, **kwargs) as resp:
                    status = resp.status
                    text = await resp.text()
                    data = json.loads(text) if text else {}
            else:
                async with session.post(url, timeout=30, **kwargs) as resp:
                    status = resp.status
                    text = await resp.text()
                    data = json.loads(text) if text else {}
        except Exception:
            log_error("Network error")
            return None

        if status == 429:
            wait_time = 5 * attempt
            log_warn(f"Rate limit - wait {wait_time}s")
            await asyncio.sleep(wait_time)
            continue
        if status in (401, 403):
            log_error("Token invalid")
            return None
        if status != 200:
            return None
        return data

def generate_device_payload(address, index):
    base_lat = 35.6895
    base_lng = 139.6917
    jitter_lat = (random.random() - 0.5) * 0.02
    jitter_lng = (random.random() - 0.5) * 0.02
    latitude = base_lat + jitter_lat + index * 0.0003
    longitude = base_lng + jitter_lng - index * 0.0003
    device_id = "DEVJP" + str(1000 + index)
    payload = {
        "address": address,
        "deviceId": device_id,
        "deviceSource": "web_app",
        "deviceType": "Windows",
        "browser": "Edge",
        "ipAddress": "153.127.0.1",
        "latitude": latitude,
        "longitude": longitude,
        "countryCode": "JP",
        "country": "Japan",
        "continent": "Asia",
        "continentCode": "AS",
        "region": "Tokyo",
        "regionCode": "Unknown",
        "city": "Tokyo",
    }
    return payload

async def connect_wallet(session, address, index):
    payload = generate_device_payload(address, index)
    log_info("Connect wallet request started for address")
    data = await send_request(session, "POST", BASE_URL + "/user/connect-wallet", json=payload)
    if not data or not data.get("success"):
        log_error("Connect wallet failed")
        return None, None
    user_data = data.get("data") or {}
    user_id = user_data.get("userId")
    testnet_address = user_data.get("testnetWalletAddress")
    if not user_id:
        log_error("No userId returned")
        return None, None
    log_info("User id acquired for current wallet")
    return user_id, testnet_address

async def perform_transfer(session, user_id, to_address, amount, failure_streak):
    payload = {"toAddress": to_address, "amount": amount, "userId": user_id}
    log_info(f"Transfer {amount} to {to_address}")
    data = await send_request(session, "POST", BASE_URL + "/transaction/transfer", json=payload)
    if not data:
        failure_streak += 1
        log_warn("Transfer request failed - wait 60s")
        if failure_streak >= 2:
            await refresh_session(session)
            failure_streak = 0
        await asyncio.sleep(60)
        return False, failure_streak
    if not data.get("success"):
        msg = data.get("message", "Unknown")
        log_error(f"Transfer failed: {msg}")
        failure_streak += 1
        if failure_streak >= 2:
            await refresh_session(session)
            failure_streak = 0
        await asyncio.sleep(60)
        return False, failure_streak
    log_info("Transfer success")
    return True, 0

async def check_faucet_balance(session, user_id):
    log_info("Faucet balance request started")
    data = await send_request(session, "GET", BASE_URL + "/transaction/get-balance/" + user_id)
    if data and data.get("success"):
        balance = data.get("data", {}).get("balance")
        log_info(f"Current faucet balance {balance}")
    else:
        log_warn("Failed to get balance")

async def check_leaderboard(session, user_id):
    log_info("Leaderboard request started")
    data = await send_request(session, "GET", BASE_URL + "/leaderboard/user/" + user_id)
    if data and data.get("success"):
        entry = (data.get("data", {}).get("data") or [{}])[0]
        rank = entry.get("rank")
        xp = entry.get("totalXP")
        tx = entry.get("transactionCount")
        log_info(f"Leaderboard: Rank {rank}  XP {xp}  TX {tx}")
    else:
        log_warn("Failed to get leaderboard")

async def claim_mystery_box(session, user_id):
    log_info("Trying to claim mystery box")
    data = await send_request(session, "GET", BASE_URL + "/mystery/claim/" + user_id)
    if data and data.get("success"):
        reward = data.get("data", {}).get("mysteryReward")
        desc = data.get("data", {}).get("description")
        log_info(f"Mystery box claimed! Reward: {reward} - {desc}")
    else:
        log_warn("No mystery box eligible")

async def main():
    set_title()
    banner()
    private_keys = load_private_keys()
    if not private_keys:
        log_error("No private key found in .env")
        return
    wallet_entries = []
    for position, pk in enumerate(private_keys, start=1):
        try:
            acc = Account.from_key(pk)
        except:
            log_error("Invalid private key")
            continue
        wallet_entries.append((position, pk, acc.address))
    if not wallet_entries:
        return

    session = await build_session()
    try:
        log_info(f"Total wallet count {len(wallet_entries)}")
        faker = Faker()
        referral = "RO5-BL18"
        fixed = "0x222306e34a54455aa10c215b26aaad3d6037dbf8"

        while True:
            for pos, pk_main, addr_main in wallet_entries:
                failure_streak = 0
                log_info(f"Processing wallet {pos}")

                user_id_main, _ = await connect_wallet(session, addr_main, pos)
                if not user_id_main:
                    continue

                await check_faucet_balance(session, user_id_main)
                await check_leaderboard(session, user_id_main)

                while True:
                    new_acc = Account.create()
                    new_addr = new_acc.address
                    log_info(f"New address generated: {new_addr}")

                    user_id_new, _ = await connect_wallet(session, new_addr, random.randint(1,10000))
                    if not user_id_new:
                        await asyncio.sleep(10)
                        continue

                    twit = faker.user_name()
                    reg_payload = {
                        "userId": user_id_new,
                        "walletAddress": new_addr,
                        "socialHandle": twit,
                        "referralCode": referral,
                    }
                    reg = await send_request(session, "POST", BASE_URL + "/auth/register", json=reg_payload)
                    if not reg or not reg.get("success"):
                        log_error("Register failed - retrying with new wallet")
                        await asyncio.sleep(10)
                        continue
                    log_info("Register success")
                    break

                fund = await send_request(session, "GET", BASE_URL + "/transaction/fund-wallet/" + user_id_new)
                amount_back = 1
                if fund and fund.get("success"):
                    log_info("Fund success")
                    amount_back = 51
                else:
                    log_info("Fund failed (normal)")

                user_id_new, testnet_addr = await connect_wallet(session, new_addr, random.randint(1,10000))
                if not testnet_addr:
                    log_error("Failed get testnet address")
                    continue

                await connect_wallet(session, addr_main, pos)

                success, failure_streak = await perform_transfer(session, user_id_main, testnet_addr, 1.001, failure_streak)
                if not success:
                    continue

                await claim_mystery_box(session, user_id_new)

                log_info("Waiting 60 seconds before send back")
                await asyncio.sleep(60)

                send_back_attempts = 0
                while send_back_attempts < 3:
                    user_id_new, _ = await connect_wallet(session, new_addr, random.randint(1,10000))
                    if not user_id_new:
                        send_back_attempts += 1
                        log_warn(f"Connect failed for send back - attempt {send_back_attempts}/3")
                        await asyncio.sleep(30)
                        continue

                    success, failure_streak = await perform_transfer(session, user_id_new, fixed, amount_back, failure_streak)
                    if success:
                        break
                    send_back_attempts += 1
                    log_warn(f"Send back failed - attempt {send_back_attempts}/3")
                    await asyncio.sleep(60)

                if send_back_attempts >= 3:
                    log_error("Send back failed after 3 attempts - skipping this cycle")

                log_info("Cycle complete - wait 60s")
                await asyncio.sleep(60)
    finally:
        await session.close()

if __name__ == "__main__":
    asyncio.run(main())
