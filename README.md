# StudyPilot 2 — monochrome, personal accounts and Python AI

The redesigned UI uses the supplied mobile reference's sampled colors: charcoal `#1f1f1d`, warm white `#f5f4f2`, and gray `#eaeaea`. Text size is adjustable from 85% to 150% using **Aa** in the header or **Settings → Reading & display**. Typography uses relative units; large-text mode also reflows dense layouts.

## Two distinct deployment modes

**Current Sites demo:** public browser-only demo. Notes, quizzes and preferences are saved on that browser. It uses labeled extractive recall generation. It does not have a live Python service, account login, or live LLM connection.

**Full-stack package:** React frontend + FastAPI served together by the included Dockerfile. This activates account registration/login, individual SQLite records, server-saved preferences, and real AI calls. It requires a Python-capable host and a configured model-provider API key. Do not describe the Sites demo as the deployed full-stack system.

## Implemented functionality

- Email/password StudyPilot registration, login, 7-day sessions, logout and expired-session handling.
- Scrypt password hashing; HttpOnly/SameSite cookies, secure cookies on HTTPS, hashed session tokens, origin checks and authorization on every private route.
- Individual notes, study kits, quiz history and performance. Server-side preferences save planner tasks, flashcard marks, focus time and font size to each account.
- PDF/DOCX/TXT extraction, summary points, flashcards, quizzes, weak-topic revision and changed retest prompts.
- OpenAI-compatible AI API integration with validated JSON and source-evidence quotations. REQUIRE_AI=true refuses generation if the key is missing, instead of silently generating demo content.
- Configurable account/global AI rate limits, login throttling and a 100-document-per-account limit.

These are StudyPilot credentials, not Google/college account credentials. Email verification and password recovery are not implemented; the registration screen discloses this. This is a small public-demo architecture, not an audited large-scale account service.

## Deploy the complete Python app on Render

The source contains `Dockerfile`, `.dockerignore` and `render.yaml`. Render builds the frontend and serves it from FastAPI at the same HTTPS origin. This avoids third-party-cookie problems.

1. Put this source in a Git repository accessible to your Render account.
2. Create a Render Blueprint from that repository using `render.yaml`.
3. Enter `AI_API_KEY` in Render's secure environment configuration. Do not paste the key into chat, source code or frontend configuration.
4. Set `AI_MODEL` and `AI_BASE_URL` for your provider. Defaults use an OpenAI-compatible endpoint.
5. Deploy and open the returned Render URL. Create a StudyPilot account, upload notes and complete a quiz.

The blueprint selects a **paid starter web service with a 1 GB persistent disk**. Review Render's current pricing before creating resources. The disk stores `/var/data/studypilot.db`; without persistent storage, redeployment can lose accounts and notes. No Render service has been provisioned by this source package alone.

Render sets RENDER_EXTERNAL_URL; the API allows that origin automatically. For a custom domain, also set ALLOWED_ORIGINS to its exact HTTPS origin. Keep COOKIE_SECURE=true for public hosting. Restrict proxy trust at the hosting boundary; the service relies on the host's trusted client-IP handling for IP throttles. Run one API worker with this SQLite configuration. Use database backups and migrate to managed PostgreSQL for multiple instances.

Official references:
- https://render.com/docs/docker
- https://render.com/docs/disks
- https://render.com/docs/blueprint-spec
- https://render.com/docs/configure-environment-variables

## Windows local full-stack development

Tested with Python 3.12 and Node.js 22+.

Backend PowerShell terminal:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
$env:COOKIE_SECURE = "false"
$env:ALLOWED_ORIGINS = "http://localhost:5173"
$env:REQUIRE_AI = "true"
$env:AI_API_KEY = "your-provider-key"
$env:AI_MODEL = "your-provider-model"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
```

Frontend PowerShell terminal:

```powershell
Set-Content .env.local "VITE_API_URL=http://localhost:8000"
npm ci
npm run dev
```

Open **http://localhost:5173**. Use localhost consistently for both frontend and API; do not mix localhost with 127.0.0.1. Create an account using the on-screen form. Do not enter API keys in the app.

For authentication/workflow testing without an AI key, explicitly set `$env:REQUIRE_AI = "false"` on the backend. Those generated kits will be labeled demo. For the browser-only demo, leave VITE_API_URL empty.

The example env files are references, not automatically loaded by the Python server. Set variables in the terminal or hosting dashboard. Frontend VITE_API_URL is build-time configuration; restart Vite or rebuild when changing it. The Dockerfile sets `VITE_API_URL=same-origin` automatically.

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| AI_API_KEY | Server-side provider secret | Unset |
| AI_BASE_URL | OpenAI-compatible API endpoint | https://api.openai.com/v1 |
| AI_MODEL | Model supporting JSON object responses | gpt-4.1-mini |
| REQUIRE_AI | Reject generation without an AI key | true |
| COOKIE_SECURE | HTTPS-only session cookies | true |
| ALLOW_REGISTRATION | Allow new accounts | true |
| STUDYPILOT_DB | SQLite path | backend/data/studypilot.db |
| ALLOWED_ORIGINS | Exact allowed browser origins, comma-separated | http://localhost:5173 |
| AI_USER_DAILY_LIMIT | Generation requests per account per 24-hour window | 10 |
| AI_GLOBAL_DAILY_LIMIT | Site-wide generation requests per 24-hour window | 100 |
| VITE_API_URL | Browser API origin, same-origin, or blank demo mode | Blank |

A generation request can make up to three model calls for long notes. Each call requests at most 6,000 output tokens. Uploads allow 10 MB and 300,000 characters; AI generation accepts at most 42,000 characters per kit. The request limit is not a dollar budget. Provider-side budget controls remain separate. Failed provider requests consume a request slot to avoid repeated uncontrolled retries.

## Data and migration

The database initializes automatically. Existing v1 tables receive an owner column. Legacy unowned data is intentionally not assigned to new accounts, so registering cannot expose someone else's old notes. No local demo data is imported into user accounts automatically. Back up the database before deployment changes.

The local demo stores data in localStorage; connected mode holds account data in memory and saves it through the API. Session secrets stay in HttpOnly cookies. Signing out removes access to the account workspace. Font size is local in browser-demo mode and server-saved in account mode.

## Validation

```sh
npm run build
node tests/engine.mjs
```

Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

macOS/Linux:

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/python -m pytest backend/tests -q
```

Tests cover document extraction, quiz scoring, weak-topic revision, retests, persistence, deletion, cross-user access denial, logout invalidation, password hashing, preferences isolation, required-AI behavior, generation quotas, CSRF origin rejection and input validation. AI response handling is tested with controlled provider responses; no real AI key was supplied. Browser-based visual QA and a Docker build were not run in this environment.

Manual checks: sign up as account A, upload and quiz, change text size, sign out; create account B and confirm its workspace is empty; sign back into A and confirm notes, scores and font size return. Test a live provider-generated kit and retest after deployment. Check phone/tablet layouts at 85%, 100% and 150% text size.

## API and source

Auth: `/api/auth/register`, `/api/auth/login`, `/api/auth/me`, `/api/auth/logout`.

Documents and learning: `/api/documents/upload`, `/api/documents/text`, `/api/documents`, `/api/documents/{id}/topics`, `/api/study-kit/generate`, `/api/study-kit/{id}`, `/api/quizzes/{id}/submit`, `/api/quizzes/retest`, `/api/revision/generate`, `/api/performance`, `/api/performance/topics`, `/api/recommendations`, `/api/state`, `/api/preferences`, `/api/documents/delete`.

`/api/health` is public and reveals only health/configuration booleans. Private API routes require the session cookie.

Frontend: `src/main.tsx`, `src/Auth.tsx`, `src/engine.ts`, `src/styles.css`.
Backend: `backend/main.py`, `backend/auth.py`, `backend/storage.py`.

Quiz accuracy remains correct answers / total attempted questions × 100. Under five answers is limited evidence. Revision recommendations use initial <40, 40–69, 70–85 and >85 thresholds. These are practice heuristics, not validated mastery measurements. Retest differences are descriptive; topic coverage can differ. Demo questions are recall completions; live AI can generate understanding and application questions when supported by the notes. Source-quote validation reduces unsupported content but does not guarantee semantic correctness.
