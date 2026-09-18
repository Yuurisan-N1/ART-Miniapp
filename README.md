<div align="center">

<img width="100%" alt="header" src="https://capsule-render.vercel.app/api?type=waving&height=210&text=ART%20Miniapp%20Bot&fontAlign=50&fontAlignY=36&fontSize=56&desc=Auto%20Ads%20%7C%20Auto%20Tasks%20%7C%20Auto%20Mining%20%7C%20Auto%20Miner%20Upgrade%20%7C%20Referral%20Claim&descAlign=50&descAlignY=58"/>

<img alt="typing" src="https://readme-typing-svg.demolab.com?font=Inter&size=18&duration=3000&pause=650&center=true&vCenter=true&width=900&lines=Auto+Watch+Ads+%7C+Verified+Per+View+Reward;Auto+Social+Tasks+%7C+Claim+ART+Per+Task;Auto+Mining+%7C+Claim+and+Restart+Session;Auto+Miner+Upgrade+%7C+Buy+Next+Level+When+Affordable;Auto+Referral+Claim+%7C+Collect+Pending+Bonus;TON+Wallet+Linking+%7C+Per+Account+in+data.txt;Proxy+Support+%7C+One+Proxy+Per+Account;Multi-Account+%7C+Sequential+Processing+Per+Cycle"/>

<p>
  <img alt="python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white"/>
  <img alt="platform" src="https://img.shields.io/badge/Platform-ART%20Miniapp-111111"/>
  <img alt="multi-account" src="https://img.shields.io/badge/Multi--Account-Supported-111111"/>
  <img alt="proxy" src="https://img.shields.io/badge/Proxy-Supported-111111"/>
  <img alt="author" src="https://img.shields.io/badge/by-Yuurisandesu-111111"/>
</p>

<p>
  <b>ART Miniapp Bot</b> is a full automation bot for the ART Telegram Miniapp.<br/>
  It handles the complete daily cycle: authenticating each account, linking a TON payout wallet per account when provided, watching all available daily ads with per-view balance verification, claiming all pending social tasks, claiming any accumulated mining reward and restarting the mining session, upgrading to the next miner level when the balance covers the cost, and collecting any pending referral bonus, all running across multiple accounts with proxy support and a live countdown between cycles.<br/>
  Built and distributed by <b>Yuurisandesu</b>.
</p>

</div>

---

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Bot](#running-the-bot)
- [Features](#features)
- [File Structure](#file-structure)
- [Disclaimer](#disclaimer)

---

## Requirements

- Python `3.12`
- Git

---

## Installation

**Clone the repository:**

```bash
git clone https://github.com/Yuurisan-N1/ART-Miniapp.git
cd ART-Miniapp
```

**Install dependencies:**

```bash
pip install aiohttp
```

---

## Configuration

### 1. Accounts (data.txt)

Fill `data.txt` with Telegram WebApp `initData` for each account, one per line. To link a TON payout wallet for an account, append a pipe character followed by the wallet address on the same line:

```
user=%7B%22id%22...&hash=abc123
user=%7B%22id%22...&hash=def456|UQDxxxYourTONWalletAddressHere
```

The wallet address after the pipe is optional. If omitted, the wallet linking step is skipped for that account.

> `initData` can be obtained from the browser DevTools when opening ART on Telegram Web.

### 2. Proxy (proxy.txt) - Optional

Fill `proxy.txt` with proxies, one per line. Proxies are assigned to accounts by index (first proxy to first account, second proxy to second account, and so on). If the number of proxies is fewer than the number of accounts, proxies wrap around cyclically. If `proxy.txt` is missing or empty, the bot runs without a proxy.

```
http://user:pass@ip:port
http://user:pass@ip:port
```

Supported formats: `http://user:pass@host:port` or `host:port:user:pass`

### 3. Bot Settings (config.json)

`sleep_seconds` controls how many seconds the bot waits between cycles. `buy_miner` controls whether the bot automatically purchases the next miner level upgrade when the balance is sufficient. If `config.json` is missing, the bot falls back to `3600` seconds and miner purchases enabled.

```json
{
  "settings": {
    "sleep_seconds": 3600,
    "buy_miner": true
  }
}
```

---

## Running the Bot

```bash
python bot.py
```

Press `Ctrl+C` at any time to stop the bot cleanly.

---

## Features

### TON Wallet Linking
If a TON wallet address is provided alongside the `initData` in `data.txt` using the pipe separator, the bot sends a connect request for that account before any other action. If the wallet is already linked and matches, the step is skipped silently. A success or failure is logged depending on the result.

### Auto Watch Ads
The bot fetches the ad status for each account to determine the daily ad limit and how many have already been watched. It then sends claim requests one by one until the limit is reached, verifying each view by checking that the watched count and pool balance both increased after each claim. Ad views that cannot be verified against the balance are skipped after a short series of retries. Each verified view and its ART reward are logged individually.

### Auto Social Tasks
The bot fetches the full task list for each account and filters for active tasks that have not yet been completed. A claim request is sent for each pending task and the total ART earned across all tasks is logged after the run finishes. If every task is already completed, that result is logged and the step is skipped.

### Auto Mining
The bot checks the current mining state for each account. If a session is still running with time remaining, the remaining duration is logged and the claim step is skipped. If the session has finished, a claim request is sent and the reward credited to the pool wallet is logged. Regardless of whether a reward was claimed, the bot then starts a new mining session. Mining requires a linked TON payout wallet; accounts without one are logged and skipped for this step.

### Auto Miner Upgrade
If `buy_miner` is enabled in `config.json`, the bot fetches the miner catalog and looks for the next level above the highest level the account currently has unlocked. If the pool wallet balance covers the cost of that level, a purchase request is sent and the result is logged. If the balance is insufficient or no higher level exists in the catalog, the step is skipped without logging.

### Auto Referral Claim
The bot checks the pending referral bonus balance for each account. If any amount is available, a claim request is sent and the ART reward is logged on success. If there is no pending referral balance, this step is skipped silently.

### Withdrawal Status
After all actions complete, the bot reports the withdrawal status for each account. If no TON wallet is linked, a reminder is logged. If the combined pool and holding balance meets or exceeds the minimum withdrawal threshold, the bot logs that a withdrawal can be requested. If the balance has not reached the threshold yet, the remaining amount needed is logged instead.

### Proxy Support
Each account can be assigned its own proxy via `proxy.txt`. If a proxy is configured for the current account, it is shown in masked form before processing begins. Proxy assignment uses a round-robin fallback if there are fewer proxies than accounts. Both `http://user:pass@host:port` and `host:port:user:pass` formats are supported.

### Multi Account
All accounts in `data.txt` are processed sequentially within every cycle. Account index and username are logged at the start of each account. A blank line separates each account output in the terminal for readability.

### Auto Countdown
After all accounts complete a cycle, the bot displays a live `HH:MM:SS` countdown in the terminal until the next cycle starts, then re-shows the banner before beginning again.

---

## File Structure

```text
ART-Miniapp/
├── bot.py          # Main bot, full daily cycle automation
├── config.json     # Sleep duration and miner purchase toggle
├── data.txt        # Account initData and optional TON wallet, one per line
├── proxy.txt       # Proxies, one per line (optional)
├── LICENSE         # License file
└── utils/
    ├── banner.py   # Banner display on startup
    └── __init__.py
```

---

## Disclaimer

This tool is built for educational and technical exploration purposes. Use it wisely and at your own responsibility.

---

<div align="center">
<img width="100%" alt="footer" src="https://capsule-render.vercel.app/api?type=waving&height=120&section=footer"/>
</div>