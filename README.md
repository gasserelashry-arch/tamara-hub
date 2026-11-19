# Tamara Hub — Public Permanent Link

One HTTPS URL for every agent. When you unlock AI Update Agent and save, all open browsers on that same link pick up the update within ~15 seconds. You never redistribute a ZIP or a new file.

## Quick start (local)

1. Copy `.env.example` to `.env` and set a strong `ADMIN_PASS`.
2. Or create `admin_pass.txt` with a single line containing the password.
3. Run `Start_Tamara_Hub_Server.bat` (Windows) or `Start_Tamara_Hub_Server.command` (Mac).
4. Open `http://localhost:8080`.

## Public link right now (any network)

1. Run `Start_Public_Tunnel.bat` (starts the hub + Cloudflare public HTTPS tunnel).
2. Copy the `https://….trycloudflare.com` URL printed in the tunnel window.
3. Share that URL once with agents. Admin saves sync live on the same link.
4. For a URL that never changes and stays up 24/7 without your PC, use Render below.
5. See `PUBLIC_LINK.txt` for the last verified public URL from this machine.

## Deploy to Render (public link for all agents)

1. Push this folder to a GitHub repository (private is fine).
2. In [Render](https://render.com): **New → Blueprint** and connect that repo (uses `render.yaml`).
   - Or **New → Web Service**, runtime Python, build `pip install -r requirements.txt`, start `python tamara_hub_server.py`.
3. Set environment variable **`ADMIN_PASS`** to your new strong password (required).
4. Optional but recommended on the free plan: set `GITHUB_TOKEN`, `GITHUB_REPO`, and `GITHUB_PATH` so admin saves survive service sleep/restarts.
5. After deploy, copy the public URL, e.g. `https://tamara-hub.onrender.com`.
6. Share **that one link** with agents once.

### Admin workflow after deploy

1. Open the same public URL.
2. Unlock **AI Update Agent** with `ADMIN_PASS`.
3. Edit SOPs / macros and confirm save.
4. Agents already on the link auto-refresh via `/api/version` — no new file, no new link.

### Free-tier note

Render free web services can sleep when idle (first open may take ~30–60s). Without GitHub persistence, filesystem changes can reset on restart. Use the optional `GITHUB_*` env vars or a paid persistent disk for durable storage.

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Health check |
| GET | `/api/version` | Current revision for agent polling |
| GET | `/api/hub-data` | Full CMS + macros payload |
| POST | `/api/auth` | `{ "password": "..." }` admin unlock |
| POST | `/api/save-hub` | `{ password, cmsData, masterMacros, reason }` live push |

## Security

- Admin password lives only in server env (`ADMIN_PASS`), not in `index.html`.
- Rotate away any password that was previously shared in documents or chat.
- Do not commit `.env`, `admin_pass.txt`, or `hub_store.json`.
