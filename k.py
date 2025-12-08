import json
import os
import time
import random
from web3 import Web3
from datetime import datetime
from colorama import init

init(autoreset=True)

MAIN_WALLET = "0x94b6cefe36ef5fb68f3e6a04db85219404b74126"
WALLETS_FILE = "wallets.json"

# RPC & ChainId (dari jaringan Maculatus di HP dan log: ChainId 10778) [image:1]
RPC_URL = "https://maculatus-rpc.x1eco.com"
CHAIN_ID = 10778

# sisakan 0.01 X1T buat gas di tiap wallet
GAS_FEE_RESERVE = Web3.to_wei(0.01, 'ether')

BOLD = "\u001B[1m"
GREEN = "\u001B[32m"
RED = "\u001B[31m"
YELLOW = "\u001B[33m"
CYAN = "\u001B[36m"
RESET = "\u001B[0m"

def log_info(msg):
    print(f"{BOLD}{GREEN}[INFO] {msg}{RESET}")

def log_success(msg):
    print(f"{BOLD}{GREEN}✅ {msg}{RESET}")

def log_warning(msg):
    print(f"{BOLD}{YELLOW}⚠️  {msg}{RESET}")

def log_error(msg):
    print(f"{BOLD}{RED}❌ {msg}{RESET}")

def banner():
    os.system("cls" if os.name == "nt" else "clear")
    print(f"{CYAN}{BOLD}{'═' * 50}{RESET}")
    print("     X1 Maculatus Wallet Sweeper")
    print(f"     Main: {MAIN_WALLET}")
    print(f"{CYAN}{BOLD}{'═' * 50}{RESET}")

def init_web3():
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={'timeout': 20}))
        if not w3.is_connected():
            raise Exception("Tidak bisa connect ke RPC")
        cid = w3.eth.chain_id
        latest_block = w3.eth.block_number
        if cid != CHAIN_ID:
            log_warning(f"ChainId RPC ({cid}) != setting script ({CHAIN_ID})")
        log_success(f"Connected RPC: {RPC_URL} | ChainId: {cid} | Block: {latest_block}")
        return w3
    except Exception as e:
        log_error(f"RPC connection failed: {e}")
        return None

def load_wallets():
    if not os.path.exists(WALLETS_FILE):
        log_error(f"File {WALLETS_FILE} tidak ditemukan")
        return []
    try:
        with open(WALLETS_FILE, "r") as f:
            data = json.load(f)
        log_info(f"Loaded {len(data)} wallets dari {WALLETS_FILE}")
        return data
    except Exception as e:
        log_error(f"Gagal load wallets: {e}")
        return []

def get_balance(w3, address):
    try:
        checksum = Web3.to_checksum_address(address)
        return w3.eth.get_balance(checksum)
    except Exception as e:
        log_error(f"Gagal cek saldo {address}: {e}")
        return 0

def send_all_to_main(w3, private_key, address):
    try:
        checksum_from = Web3.to_checksum_address(address)
        checksum_to = Web3.to_checksum_address(MAIN_WALLET)

        balance = get_balance(w3, checksum_from)
        balance_eth = w3.from_wei(balance, "ether")

        if balance <= GAS_FEE_RESERVE:
            log_warning(f"{address}: saldo kurang (saldo {balance_eth} X1T)")
            return False

        amount_to_send = balance - GAS_FEE_RESERVE
        nonce = w3.eth.get_transaction_count(checksum_from)
        gas_price = w3.eth.gas_price

        tx = {
            "nonce": nonce,
            "to": checksum_to,
            "value": amount_to_send,
            "gas": 21000,
            "gasPrice": gas_price,
            "chainId": CHAIN_ID,
        }

        signed = w3.eth.account.sign_transaction(tx, private_key)

        # Kompatibel web3.py lama & baru
        raw_tx = getattr(signed, "rawTransaction", None)
        if raw_tx is None:
            raw_tx = getattr(signed, "raw_transaction", None)

        if raw_tx is None:
            raise Exception("SignedTransaction tidak punya rawTransaction/raw_transaction")

        tx_hash = w3.eth.send_raw_transaction(raw_tx)

        log_success(
            f"{address}: kirim {w3.from_wei(amount_to_send, 'ether')} X1T "
            f"(gas_price {w3.from_wei(gas_price, 'gwei')} gwei)"
        )
        log_info(f"TX hash: {tx_hash.hex()}")
        return True
    except Exception as e:
        log_error(f"Transfer gagal {address}: {e}")
        return False

def main():
    banner()
    w3 = init_web3()
    if not w3:
        return

    wallets = load_wallets()
    if not wallets:
        return

    main_before = get_balance(w3, MAIN_WALLET)
    log_info(f"Saldo main sebelum: {w3.from_wei(main_before, 'ether')} X1T")

    sukses = 0
    total_sent_wei = 0

    for idx, w in enumerate(wallets, 1):
        addr = w.get("address")
        pk = w.get("pk")
        if not addr or not pk:
            continue

        print(f"[{idx}/{len(wallets)}] {addr}")
        bal = get_balance(w3, addr)
        bal_eth = w3.from_wei(bal, "ether")
        log_info(f"Saldo: {bal_eth} X1T")

        if bal > GAS_FEE_RESERVE:
            if send_all_to_main(w3, pk, addr):
                sukses += 1
                total_sent_wei += bal - GAS_FEE_RESERVE
                time.sleep(random.uniform(1.5, 3.5))
        else:
            log_warning("Skip, saldo kurang dari fee")

    main_after = get_balance(w3, MAIN_WALLET)
    total_received = main_after - main_before

    print(f"{GREEN}{BOLD}{'═' * 60}{RESET}")
    log_success(f"SELESAI: {sukses}/{len(wallets)} wallet sukses dikirim")
    log_success(f"Total masuk ke main (real): {w3.from_wei(total_received, 'ether')} X1T")
    log_success(f"Estimasi total dikirim (tanpa gas): {w3.from_wei(total_sent_wei, 'ether')} X1T")
    log_success(f"Saldo main akhir: {w3.from_wei(main_after, 'ether')} X1T")
    print(f"{GREEN}{BOLD}{'═' * 60}{RESET}")

if __name__ == "__main__":
    main()
