TAMARA HUB - PERMANENT SINGLE-LINK ARCHITECTURE
===============================================

HOW TO UPDATE WITHOUT EVER SENDING A NEW LINK TO AGENTS:

1. PUBLIC INTERNET (RECOMMENDED — ANY AGENT, NO VPN):
   - Deploy this folder once to Render (see README.md).
   - Share the permanent HTTPS URL with agents ONCE (e.g. https://tamara-hub.onrender.com).
   - Unlock AI Update Agent with the ADMIN_PASS you set in Render env vars, then save.
   - Every connected agent browser syncs within ~15 seconds on the exact same link.

2. LOCAL NETWORK / VPN HOSTING (AUTOMATIC LIVE PUSH):
   - Extract this folder once on your host PC.
   - Set ADMIN_PASS (create admin_pass.txt or set the env var), then run
     Start_Tamara_Hub_Server.bat (Windows) or Start_Tamara_Hub_Server.command (Mac).
   - Share http://<YOUR-IP>:8080 with agents on the same network/VPN ONCE.
   - Admin saves write into the live server; agents on that link auto-sync.

3. CLOUD / REMOTE STATIC HOSTING ONLY (NETLIFY / GITHUB PAGES / SHAREPOINT):
   - Static hosts do NOT run the live save API — prefer Render for automatic push.
   - If you must use static hosting: after edits click "Download Updated index.html"
     and replace index.html on the host — the URL never changes, but agents will not
     live-sync until they refresh the new file.

SECURITY:
   - Never put the admin password in shared documents.
   - Set ADMIN_PASS only in the host environment (or local admin_pass.txt, which is gitignored).
