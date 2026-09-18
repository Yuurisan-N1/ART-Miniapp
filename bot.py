import os
import sys
import json
import time
import signal
import asyncio
import aiohttp

from urllib.parse import parse_qs, unquote, urlencode

from utils.banner import show_banner

RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"

MY_PROJECT = "ART Miniapp"
BASE_URL = "https://art.tamimdev.dev"
REF_CODE = "6004380466"

CALL_ATTEMPTS = 3
CALL_RETRY_SECONDS = 4
ROUND_PAUSE_SECONDS = 1
ACTION_PAUSE_SECONDS = 2
ADS_RATE_LIMIT_RETRIES = 3
AD_UNVERIFIED_LIMIT = 3
BUSY_STATUS = (429, 500, 502, 503, 504)

BANNED_CODES = (
    91, 93, 124, 35, 33, 64, 36, 37, 94, 38, 42, 40, 41,
    45, 44, 58, 59, 39, 34, 96, 126, 43, 61, 60, 62, 63, 47, 92,
)
BANNED_CHARS = tuple(chr(code) for code in BANNED_CODES)

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/152.0.0.0 Mobile Safari/537.36"
)


def log_green(msg):
    print(f"{GREEN}{BOLD}{msg}{RESET}")


def log_yellow(msg):
    print(f"{YELLOW}{BOLD}{msg}{RESET}")


def log_red(msg):
    print(f"{RED}{BOLD}{msg}{RESET}")


def signal_handler(sig, frame):
    print()
    log_red("Script stopped by user")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def clean_text(value, fallback):
    if value is None:
        return str(fallback)
    text = str(value)
    for symbol in BANNED_CHARS:
        text = text.replace(symbol, " ")
    text = "".join(char for char in text if ord(char) < 128)
    text = " ".join(text.split())
    return text if text else str(fallback)


def unit_word(value, singular, plural):
    try:
        return singular if int(float(value)) == 1 else plural
    except Exception:
        return plural


def display_name(user, account):
    for value in (
        user.get("firstName"),
        user.get("lastName"),
        account.get("firstName"),
        account.get("username"),
        user.get("username"),
    ):
        name = clean_text(value, "")
        if name:
            return name
    return "Unknown"


def format_duration(seconds):
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    rest = total % 60
    if hours:
        return f"{hours} {unit_word(hours, 'hour', 'hours')} {minutes} {unit_word(minutes, 'minute', 'minutes')}"
    if minutes:
        return f"{minutes} {unit_word(minutes, 'minute', 'minutes')} {rest} {unit_word(rest, 'second', 'seconds')}"
    return f"{rest} {unit_word(rest, 'second', 'seconds')}"


def load_config():
    defaults = {"settings": {"sleep_seconds": 900, "buy_miner": True}}
    if not os.path.exists("config.json"):
        return defaults
    try:
        with open("config.json") as handle:
            return json.load(handle)
    except Exception:
        return defaults


def config_flag(config, key, fallback):
    value = config.get("settings", {}).get(key, fallback)
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("true", "yes", "on", "1"):
        return True
    if text in ("false", "no", "off", "0"):
        return False
    return fallback


def load_lines(filename, required):
    if not os.path.exists(filename):
        if required:
            log_red(f"File {clean_text(filename, 'data.txt')} was not found")
            sys.exit(1)
        return []
    lines = [line.strip() for line in open(filename).readlines() if line.strip()]
    if required and not lines:
        log_red("File data.txt is empty and holds no initData string")
        sys.exit(1)
    return lines


def parse_credential(line):
    value = line.strip()
    wallet = ""
    if "|" in value:
        value, wallet = value.rsplit("|", 1)
        wallet = wallet.strip()
    return parse_init_data(value), wallet


def parse_init_data(line):
    value = line.strip()
    if "tgWebAppData=" in value:
        value = value.split("tgWebAppData=", 1)[1]
        value = value.split("&tgWebAppVersion")[0].split("&tgWebAppPlatform")[0]
        value = unquote(value)
    fields = parse_qs(value, keep_blank_values=True)
    raw_user = (fields.get("user") or [""])[0]
    if not raw_user:
        return None
    try:
        profile = json.loads(raw_user)
    except Exception:
        try:
            profile = json.loads(unquote(raw_user))
        except Exception:
            return None
    if not isinstance(profile, dict) or not profile.get("id"):
        return None
    return {
        "initData": value,
        "id": str(profile.get("id")),
        "username": str(profile.get("username") or ""),
        "firstName": str(profile.get("first_name") or ""),
        "lastName": str(profile.get("last_name") or ""),
        "startParam": str((fields.get("start_param") or [""])[0]),
    }


def normalize_proxy(proxy_line):
    if not proxy_line:
        return None
    value = proxy_line.strip()
    if "://" in value:
        return value
    parts = value.split(":")
    if len(parts) == 4:
        host, port, user, password = parts
        return f"http://{user}:{password}@{host}:{port}"
    if len(parts) == 3:
        host, port, user = parts
        return f"http://{user}@{host}:{port}"
    return f"http://{value}"


def mask_proxy(proxy_url):
    try:
        value = proxy_url.split("://")[-1]
        after_at = value.split("@")[-1]
        host_part = after_at.split(":")[0]
        port_part = after_at.split(":")[1] if ":" in after_at else ""
        octets = host_part.split(".")
        if len(octets) == 4:
            masked_host = f"{octets[0]}*****{octets[3]}"
        elif len(host_part) > 4:
            masked_host = f"{host_part[:2]}*****{host_part[-2:]}"
        else:
            masked_host = "***"
        suffix = f":{port_part}" if port_part else ""
        return f"http://user:pass@{masked_host}{suffix}"
    except Exception:
        return "http://user:pass@***:***"


def build_headers(init_data):
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "origin": BASE_URL,
        "referer": BASE_URL + "/",
        "user-agent": USER_AGENT,
        "X-Telegram-Init-Data": init_data,
    }


def error_message(payload):
    if isinstance(payload, dict):
        message = payload.get("message") or payload.get("error")
        if message:
            return str(message)
    return ""


def payload_flag(payload, key):
    return isinstance(payload, dict) and bool(payload.get(key))


def busy_error(status, payload):
    if status in BUSY_STATUS:
        return True
    message = error_message(payload).lower()
    return "busy" in message or "timeout" in message


async def api_call(session, method, path, headers, body=None, proxy=None):
    url = f"{BASE_URL}{path}"
    last_status = 0
    last_payload = None
    attempts = CALL_ATTEMPTS if method == "POST" else 2
    for attempt in range(1, attempts + 1):
        try:
            request = session.request(
                method,
                url,
                headers=headers,
                json=body,
                proxy=proxy,
                timeout=aiohttp.ClientTimeout(total=30),
            )
            async with request as response:
                last_status = response.status
                text = await response.text()
                try:
                    last_payload = json.loads(text)
                except Exception:
                    last_payload = None
                if response.status < 400 or not busy_error(response.status, last_payload):
                    return last_status, last_payload
        except Exception:
            last_status = 0
            last_payload = None
        if attempt < attempts:
            await asyncio.sleep(CALL_RETRY_SECONDS * attempt)
    return last_status, last_payload


def read_user(payload):
    if isinstance(payload, dict) and isinstance(payload.get("user"), dict):
        return payload["user"]
    return {}


def read_settings(payload):
    if isinstance(payload, dict) and isinstance(payload.get("settings"), dict):
        return payload["settings"]
    return {}


def read_mining(payload):
    if isinstance(payload, dict) and isinstance(payload.get("miningState"), dict):
        return payload["miningState"]
    return {}


async def fetch_json(session, headers, path, proxy):
    status, payload = await api_call(session, "GET", path, headers, None, proxy)
    if status == 200 and isinstance(payload, dict):
        return payload
    return {}


async def fresh_user(session, headers, user_id, proxy):
    return read_user(await fetch_json(session, headers, f"/api/user/{user_id}", proxy))


async def load_account(session, headers, account, proxy):
    referral = account["startParam"] if account["startParam"].isdigit() else REF_CODE
    params = {"username": account["username"], "firstName": account["firstName"], "referredBy": referral}
    clean_params = {key: value for key, value in params.items() if value}
    query = "?" + urlencode(clean_params) if clean_params else ""
    status, payload = await api_call(session, "GET", f"/api/user/{account['id']}{query}", headers, None, proxy)
    if status == 200:
        return payload
    return None


def account_view(payload):
    return {
        "user": read_user(payload),
        "settings": read_settings(payload),
        "mining": read_mining(payload),
    }


async def watch_ads(session, headers, view, proxy):
    settings = view["settings"]
    symbol = clean_text(settings.get("tokenSymbol"), "ART")
    user_id = view["user"].get("id")
    status_payload = await fetch_json(session, headers, f"/api/ads/status/{user_id}", proxy)
    if status_payload.get("enabled") is False:
        return 0, 0
    limit = int(status_payload.get("limit") or 0)
    watched = int(status_payload.get("watched") or 0)
    fallback_reward = int(status_payload.get("rewardAtf") or 0)
    balance = int((await fresh_user(session, headers, user_id, proxy)).get("poolWallet") or 0)
    credited = 0
    unverified = 0
    retries = 0
    while watched < limit:
        status, payload = await api_call(session, "POST", "/api/ads/claim", headers, {"userId": user_id}, proxy)
        if not payload_flag(payload, "success"):
            if status == 429:
                retries += 1
                if retries > ADS_RATE_LIMIT_RETRIES:
                    break
                await asyncio.sleep(ACTION_PAUSE_SECONDS * retries)
                continue
            break
        fresh = await fresh_user(session, headers, user_id, proxy)
        fresh_watched = int(fresh.get("adsWatchedCount") or 0)
        gain = int(fresh.get("poolWallet") or 0) - balance
        if fresh_watched <= watched or gain <= 0:
            unverified += 1
            if unverified >= AD_UNVERIFIED_LIMIT:
                break
        else:
            credited += gain
            watched = fresh_watched
            balance += gain
            reward = int(payload.get("reward") or fallback_reward)
            log_green(f"Ad view {clean_text(watched, 0)} of {clean_text(limit, 0)} was verified and earned {clean_text(reward, 0)} {clean_text(symbol, 1)}")
        await asyncio.sleep(ACTION_PAUSE_SECONDS)
    return credited, limit


async def claim_tasks(session, headers, user_id, proxy):
    data = await fetch_json(session, headers, f"/api/tasks/{user_id}", proxy)
    tasks = data.get("tasks") or []
    pending = [task for task in tasks if task.get("isActive") and not task.get("isCompleted")]
    if not pending:
        log_green("Every available account task was already completed")
        return 0
    before = await fresh_user(session, headers, user_id, proxy)
    balance = int(before.get("poolWallet") or 0)
    claimed = 0
    for task in pending:
        task_id = task.get("id")
        if not task_id:
            continue
        status, payload = await api_call(
            session, "POST", "/api/tasks/claim", headers, {"userId": user_id, "taskId": task_id}, proxy
        )
        if payload_flag(payload, "success"):
            claimed += int(payload.get("reward") or 0)
        await asyncio.sleep(ACTION_PAUSE_SECONDS)
    fresh_payload = await fetch_json(session, headers, f"/api/user/{user_id}", proxy)
    gain = int(read_user(fresh_payload).get("poolWallet") or 0) - balance
    earned = gain if gain > 0 else claimed
    if earned > 0:
        symbol = clean_text(read_settings(fresh_payload).get("tokenSymbol"), "ART")
        log_green(f"Every available account task was claimed and {clean_text(earned, 0)} {clean_text(symbol, 1)} was credited")
    return earned


async def mining_view(session, headers, user_id, proxy):
    return account_view(await fetch_json(session, headers, f"/api/user/{user_id}", proxy))


async def run_mining(session, headers, view, proxy):
    user_id = view["user"].get("id")
    view = await mining_view(session, headers, user_id, proxy)
    settings = view["settings"]
    symbol = clean_text(settings.get("tokenSymbol"), "ART")
    state = view["mining"]
    balance = int(view["user"].get("poolWallet") or 0)
    if not (view["user"].get("tonWalletAddress") or ""):
        log_yellow("Mining was skipped because this account has no linked TON payout wallet")
        return 0
    if state.get("isMining") and int(state.get("remainingSeconds") or 0) > 0:
        log_yellow(f"Mining is still running with {format_duration(state.get('remainingSeconds'))} left")
        return 0

    claimed = 0
    status, payload = await api_call(session, "POST", "/api/user/claim-mining", headers, {"userId": user_id}, proxy)
    if payload_flag(payload, "success"):
        fresh = await mining_view(session, headers, user_id, proxy)
        gain = int(fresh["user"].get("poolWallet") or 0) - balance
        if gain > 0:
            log_green(f"Mining reward of {clean_text(gain, 0)} {clean_text(symbol, 1)} was claimed")
            claimed += gain
            balance += gain
            state = fresh["mining"] or state

    running = await mining_view(session, headers, user_id, proxy)
    if running["mining"].get("isMining"):
        return claimed

    status, payload = await api_call(session, "POST", "/api/user/start-mining", headers, {"userId": user_id}, proxy)
    if payload_flag(payload, "success"):
        after = await mining_view(session, headers, user_id, proxy)
        gain = int(after["user"].get("poolWallet") or 0) - balance
        if gain > 0:
            log_green(f"Mining reward of {clean_text(gain, 0)} {clean_text(symbol, 1)} was claimed")
            claimed += gain
        log_green("Mining session was started for this account")
        return claimed
    message = error_message(payload).lower()
    if "wallet" in message:
        log_yellow("Mining is locked until a TON payout wallet is linked inside the Mini App")
    elif claimed <= 0:
        log_yellow("Mining session could not be started on this run")
    return claimed


async def buy_next_miner(session, headers, view, proxy):
    user_id = view["user"].get("id")
    view = await mining_view(session, headers, user_id, proxy)
    settings = view["settings"]
    symbol = clean_text(settings.get("tokenSymbol"), "ART")
    user = view["user"]
    balance = int(user.get("poolWallet") or 0)
    levels = [int(level) for level in (user.get("unlockedMiners") or [1])]
    next_level = max(levels) + 1
    catalog = await fetch_json(session, headers, "/api/miners", proxy)
    entry = None
    for miner in catalog.get("miners") or []:
        if int(miner.get("level") or 0) == next_level:
            entry = miner
            break
    if not entry:
        return 0
    need = int(entry.get("needAtf") or 0)
    if balance < need:
        return 0
    status, payload = await api_call(
        session, "POST", "/api/user/buy-miner", headers, {"userId": user_id, "level": next_level}, proxy
    )
    if payload_flag(payload, "success"):
        fresh = await fresh_user(session, headers, user_id, proxy)
        if next_level in [int(level) for level in (fresh.get("unlockedMiners") or [])]:
            log_green(f"Miner level {clean_text(next_level, 0)} was unlocked for {clean_text(need, 0)} {clean_text(symbol, 1)}")
            return next_level
    return 0


async def link_wallet(session, headers, view, wallet, proxy):
    user_id = view["user"].get("id")
    current = view["user"].get("tonWalletAddress") or ""
    if not wallet or current == wallet:
        return False
    status, payload = await api_call(
        session, "POST", "/api/user/connect-wallet", headers, {"userId": user_id, "tonAddress": wallet}, proxy
    )
    if payload_flag(payload, "success"):
        fresh = await fresh_user(session, headers, user_id, proxy)
        if (fresh.get("tonWalletAddress") or "") == wallet:
            log_green("Payout wallet was linked for this account")
            return True
    log_yellow("Payout wallet could not be linked on this run")
    return False


async def claim_referral(session, headers, view, proxy):
    settings = view["settings"]
    symbol = clean_text(settings.get("tokenSymbol"), "ART")
    user = view["user"]
    user_id = user.get("id")
    if int(user.get("referralRewardAvailable") or 0) <= 0:
        return 0
    status, payload = await api_call(session, "POST", "/api/referrals/claim-bonus", headers, {"userId": user_id}, proxy)
    if payload_flag(payload, "success"):
        reward = int(payload.get("reward") or payload.get("amount") or 0)
        if reward > 0:
            log_green(f"Referral bonus of {clean_text(reward, 0)} {clean_text(symbol, 1)} was claimed")
            return reward
    return 0


async def report_withdrawal(session, headers, view, proxy):
    settings = view["settings"]
    symbol = clean_text(settings.get("tokenSymbol"), "ART")
    user_id = view["user"].get("id")
    fresh_payload = await fetch_json(session, headers, f"/api/user/{user_id}", proxy)
    fresh = read_user(fresh_payload)
    minimum = int(read_settings(fresh_payload).get("minWithdrawAtf") or settings.get("minWithdrawAtf") or 0)
    balance = int(fresh.get("poolWallet") or 0) + int(fresh.get("holdingWallet") or 0)
    if not (fresh.get("tonWalletAddress") or ""):
        log_yellow("Withdrawal is locked until a TON payout wallet is linked inside the Mini App")
    elif minimum and balance >= minimum:
        log_green(f"Withdrawal of {clean_text(minimum, 0)} {clean_text(symbol, 1)} can be requested now")
    elif minimum:
        log_yellow(f"Withdrawal is still locked until {clean_text(minimum, 0)} {clean_text(symbol, 1)}")
    return minimum


async def process_account(line, proxy, index, buy_miner):
    account, wallet = parse_credential(line)
    if not account:
        log_red(f"Credential line {clean_text(index, 1)} is not a valid Telegram initData string")
        return

    user_id = account["id"]
    headers = build_headers(account["initData"])
    connector = aiohttp.TCPConnector(ssl=False)

    async with aiohttp.ClientSession(connector=connector) as session:
        payload = await load_account(session, headers, account, proxy)
        view = account_view(payload)
        if not view["user"]:
            log_red(f"Sign in failed for account number {clean_text(index, 1)}")
            return

        settings = view["settings"]
        symbol = clean_text(settings.get("tokenSymbol"), "ART")
        name = display_name(view["user"], account)
        log_green(f"Account {clean_text(name, 1)} signed in successfully")

        if wallet:
            await link_wallet(session, headers, view, wallet, proxy)

        if settings.get("adsEnabled") is not False:
            credited, limit = await watch_ads(session, headers, view, proxy)
            if credited <= 0:
                if limit > 0 and int(view["user"].get("adsWatchedCount") or 0) >= limit:
                    log_green("Daily ad quota was already filled for this account")
                else:
                    log_yellow("No ad reward could be verified from the ad network")

        await claim_tasks(session, headers, user_id, proxy)

        await run_mining(session, headers, view, proxy)

        if buy_miner:
            await buy_next_miner(session, headers, view, proxy)

        await claim_referral(session, headers, view, proxy)

        await report_withdrawal(session, headers, view, proxy)


async def main_async(accounts, proxies, sleep_secs, buy_miner):
    cycle = 1
    while True:
        log_yellow(f"Starting automation cycle number {clean_text(cycle, 0)}")
        if not buy_miner:
            log_yellow("Miner purchases are disabled in config.json")

        for index, line in enumerate(accounts):
            if index > 0:
                print()

            proxy_line = proxies[index % len(proxies)] if proxies else None
            proxy_url = normalize_proxy(proxy_line) if proxy_line else None
            if proxy_url:
                log_yellow(f"Using proxy {mask_proxy(proxy_url)}")

            await process_account(line, proxy_url, index + 1, buy_miner)
            await asyncio.sleep(ROUND_PAUSE_SECONDS)

        log_yellow(f"Automation cycle number {clean_text(cycle, 0)} is complete")
        cycle += 1
        countdown(sleep_secs)
        show_banner(MY_PROJECT)


def countdown(seconds):
    for remaining in range(int(seconds), 0, -1):
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        rest = remaining % 60
        print(f"\r{YELLOW}{BOLD}Next cycle starts in {hours:02d}:{minutes:02d}:{rest:02d}{RESET}", end="", flush=True)
        time.sleep(1)
    print()


def main():
    show_banner(MY_PROJECT)

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    config = load_config()
    sleep_secs = config.get("settings", {}).get("sleep_seconds", 900)
    buy_miner = config_flag(config, "buy_miner", True)
    accounts = load_lines("data.txt", True)
    proxies = load_lines("proxy.txt", False)
    asyncio.run(main_async(accounts, proxies, sleep_secs, buy_miner))


if __name__ == "__main__":
    main()
