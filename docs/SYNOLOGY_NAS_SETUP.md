# Grand Agent On NAS

Grand Agent can run as a private web console on a Synology NAS or any Linux box with Python 3.11+ and Node 22+. The public repository does not include admin passwords, provider keys, Codex data, MiniMax tokens, or local NAS paths.

## First Install

```bash
git clone https://github.com/bobthecomputer/vibe-coding-platform.git grand-agent
cd grand-agent
python -m pip install -e .
npm ci
python scripts/nas_setup.py
python scripts/run_web_backend.py --host 0.0.0.0 --port 47880
```

The setup script builds `web/dist` and creates an ignored local admin file under `.agent_control/`. The generated admin password is written to `.agent_control/grand_agent_admin_password.txt` on that machine only.

## Synology Task Scheduler

In DSM:

1. Open Control Panel -> Task Scheduler.
2. Create -> Triggered Task -> User-defined script.
3. Run as the NAS user that owns the checkout.
4. Use this script, adjusted to your checkout path:

```bash
cd /volume1/docker/grand-agent
python scripts/run_web_backend.py --host 0.0.0.0 --port 47880
```

For HTTPS, put Synology Login Portal or Reverse Proxy in front of `http://127.0.0.1:47880`.

## Reset Admin Password

```bash
python scripts/nas_setup.py --skip-npm --reset-admin-password
```

This rewrites the ignored local admin config and password file.

## Provider Secrets

Use environment variables in the NAS task, a local shell profile, or the in-app provider form after login:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `OPENROUTER_API_KEY`
- `MINIMAX_API_KEY`
- `MINIMAX_OAUTH_TOKEN`
- `TELEGRAM_BOT_TOKEN`

The web backend returns presence only. It does not send raw provider keys to the browser or write them into Git.

## Public Static Hosting

GitHub Pages and Vercel can serve the static shell, but full machine control requires the NAS backend. Use NAS hosting for private operations; use Vercel/GitHub Pages only for public preview or screenshots.
