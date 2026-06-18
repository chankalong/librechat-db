# LibreChat MongoDB Export (Railway)

Tools to query and export LibreChat data from MongoDB hosted on **Railway** (`industrious-flow` / production).

LibreChat stores data in the **`test`** database (collections: `users`, `conversations`, `messages`).

---

## Prerequisites

1. **Railway CLI** installed and logged in:

```bash
railway login
```

2. **Link to the MongoDB service** (from this project folder):

```bash
cd librechat-db
railway link
# Choose: industrious-flow → production → MongoDB
```

Verify:

```bash
railway status
# Project: industrious-flow
# Environment: production
# Service: MongoDB
```

3. **Optional:** MongoDB MCP for Cursor (external TCP often blocked — SSH method below is reliable):

```bash
# ~/.mcp-env
export MDB_MCP_CONNECTION_STRING="mongodb://mongo:PASSWORD@HOST:PORT/?directConnection=true&authSource=admin"
export MDB_MCP_READ_ONLY="true"
```

Add to `~/.zshrc`: `[ -f ~/.mcp-env ] && source ~/.mcp-env`

---

## Railway setup walkthrough (step by step)

This guide sets up **two new services** in your existing Railway project (`industrious-flow`):

| Service | Purpose |
|---------|---------|
| `librechat-export-cron` | Runs daily → exports MongoDB → Excel |
| `librechat-export-api` | Always-on HTTP API → Power BI / dashboards fetch CSV/Excel |

Your existing **MongoDB** and **LibreChat** services are not changed.

```
industrious-flow (production)
├── MongoDB              ← already exists
├── LibreChat            ← already exists
├── librechat-export-cron   ← you will add
└── librechat-export-api    ← you will add
```

### Step 0 — Push this repo to GitHub

Railway deploys easiest from GitHub.

```bash
cd librechat-db
git init   # if not already a repo
git add .
git commit -m "Add LibreChat export cron and API"
git remote add origin https://github.com/YOUR_USER/librechat-db.git
git push -u origin main
```

Skip this if the repo is already on GitHub.

---

### Step 1 — Create the export cron service

1. Open [Railway dashboard](https://railway.com) → project **industrious-flow** → environment **production**.
2. Click **+ New** → **GitHub Repo** → select your `librechat-db` repo.
3. Railway creates a service. Rename it to **`librechat-export-cron`** (Settings → name).

#### 1a. Build settings

Open the cron service → **Settings** → **Build**:

| Setting | Value |
|---------|--------|
| Root directory | `/` (repo root) |
| Dockerfile path | `cloud/Dockerfile` |

Railway reads `railway.json` at the repo root, which sets the cron schedule.

#### 1b. Deploy settings

**Settings** → **Deploy**:

| Setting | Value |
|---------|--------|
| Custom start command | `/app/export-daily.sh` |
| Cron schedule | `0 3 * * *` (3:00 AM UTC daily) |
| Restart policy | **Never** (cron jobs should exit when done) |

> If Cron schedule is not visible in the UI, it is already in `railway.json` and will apply on deploy.

#### 1c. Environment variables

**Variables** tab → add:

| Variable | Value | How |
|----------|--------|-----|
| `MONGO_PRIVATE_URL` | `${{MongoDB.MONGO_PRIVATE_URL}}` | Click **Reference** → pick **MongoDB** service → `MONGO_PRIVATE_URL` |
| `MONGO_DB_NAME` | `test` | Type manually |

To reference MongoDB vars: in the value field, type `${{` and Railway shows a picker. Select your MongoDB service (may be named `MongoDB`).

#### 1d. Add a volume (keeps Excel files)

**Settings** → **Volumes** → **Add volume**:

| Mount path | Size |
|------------|------|
| `/data/export` | 1 GB (enough) |

Without a volume, exported files are lost when the container stops.

#### 1e. First deploy and test

Click **Deploy** (or push to GitHub to trigger deploy).

Watch **Deployments** → **View logs**. A successful run ends with:

```
=== Done ===
Saved: /data/export/YYYY-MM-DD/excel/librechat-combined.xlsx
```

**Run manually before waiting for cron:**

**Settings** → **Deploy** → click **Deploy** again, or from your Mac:

```bash
railway link          # pick librechat-export-cron
railway ssh -- /app/export-daily.sh
```

> **Note:** `railway run` runs on your **Mac**, not in the container — `/app/export-daily.sh` only exists inside the deployed image.

If SSH fails (cron container already stopped), click **Redeploy** in the Railway dashboard.

First run may take **5–15 minutes** (~46k messages in batches).

---

### Step 2 — (Recommended) Add S3 storage for the API

Railway volumes attach to **one service only**. The API service cannot read the cron service’s volume. Use **S3-compatible storage** (AWS S3 or Cloudflare R2) as a shared bridge.

#### Option A — Cloudflare R2 (free tier, simple)

1. Cloudflare dashboard → **R2** → **Create bucket** (e.g. `librechat-exports`).
2. **Manage R2 API tokens** → create token with read/write.
3. Note: **Endpoint URL**, **Access Key ID**, **Secret Access Key**, **Bucket name**.

#### Option B — AWS S3

Create a bucket and IAM user with `s3:PutObject` + `s3:GetObject` on that bucket.

#### Add S3 vars to the cron service

On **`librechat-export-cron`** → **Variables**:

| Variable | Example |
|----------|---------|
| `S3_BUCKET` | `librechat-exports` |
| `S3_PREFIX` | `exports/` |
| `S3_ENDPOINT` | `https://ACCOUNT_ID.r2.cloudflarestorage.com` (R2 only; omit for AWS) |
| `AWS_ACCESS_KEY_ID` | your access key |
| `AWS_SECRET_ACCESS_KEY` | your secret key |

Redeploy the cron service. After the next export, check the bucket for `exports/librechat-combined-YYYY-MM-DD.xlsx`.

> **Skip S3** if you only need files on the cron volume and will download manually from Railway — but then the API in Step 3 cannot serve files unless you also upload to S3.

#### Option C — Vercel Blob (recommended for Next.js / Vercel)

Upload Excel to **Vercel Blob** after each export — easy to use from a Next.js app, Power BI, or any HTTP client. No Railway volume download needed.

1. [Vercel dashboard](https://vercel.com) → your Next.js project → **Storage** → **Blob** → **Create store**
2. Connect the store to your project (Vercel adds `BLOB_READ_WRITE_TOKEN` to the project)
3. Copy the token: Project → **Settings** → **Environment Variables** → `BLOB_READ_WRITE_TOKEN`
4. On **`librechat-export-cron`** (Railway) → **Variables** → add:

| Variable | Value |
|----------|--------|
| `BLOB_READ_WRITE_TOKEN` | paste token from Vercel |
| `BLOB_PREFIX` | `librechat-exports` (optional folder) |
| `BLOB_ACCESS` | `public` (default) or `private` |

5. Push latest code and **Redeploy** the cron service

After export, deploy logs show:

```
Uploading to Vercel Blob...
  url: https://xxxx.public.blob.vercel-storage.com/librechat-exports/librechat-combined-latest.xlsx
  downloadUrl: https://xxxx.public.blob.vercel-storage.com/.../librechat-combined-latest.xlsx?download=1
```

**Use in Next.js:**

```tsx
// Public blob — direct link
<a href="https://YOUR-STORE.public.blob.vercel-storage.com/librechat-exports/librechat-combined-latest.xlsx">
  Download latest export
</a>
```

**Use in Power BI:** Get data → Web → paste the `downloadUrl` from logs.

**Private blobs:** set `BLOB_ACCESS=private` on the cron service. The blob URL is **not** publicly accessible — use one of the auth options below.

---

## Private Vercel Blob + authenticated download

Private blobs cannot be opened by URL alone. A **server** with `BLOB_READ_WRITE_TOKEN` must fetch the file, after checking your auth.

### Option A — Next.js API on Vercel (if your dashboard is Next.js)

1. Cron: `BLOB_ACCESS=private` (already uploads to Blob)
2. Use the **`librechat-db-nextjs`** project (already has API routes)
3. Deploy to Vercel + connect the same Blob store
4. Set `EXPORT_API_KEY` on Vercel

See [`librechat-db-nextjs/SETUP.md`](../librechat-db-nextjs/SETUP.md) for full steps.

**Download (authenticated):**

```bash
curl -L -H "X-API-Key: YOUR_EXPORT_API_KEY" \
  "https://your-nextjs-app.vercel.app/api/exports/latest" \
  -o librechat-combined.xlsx
```

**Power BI:** Get data → Web → Advanced → URL above + `X-API-Key` header.

Replace `EXPORT_API_KEY` check with **NextAuth session** in `librechat-db-nextjs/src/lib/auth.ts` if only logged-in users should download.

**Full setup:** [`librechat-db-nextjs/SETUP.md`](../librechat-db-nextjs/SETUP.md)

### Architecture

```
Cron (Railway)  ──upload──▶  Vercel Blob (private)
                                    │
                     BLOB_READ_WRITE_TOKEN (server only)
                                    │
                                    ▼
                         librechat-db-nextjs (Vercel)
                         EXPORT_API_KEY / session auth
                                    │
                         Power BI / curl / dashboard
```

**Full Next.js + Vercel setup:** see the sibling repo [`librechat-db-nextjs`](../librechat-db-nextjs/SETUP.md) (or `SETUP.md` in that project).

**Never** put `BLOB_READ_WRITE_TOKEN` in browser code or public env vars (`NEXT_PUBLIC_*`).

---

### Step 3 — Download API (Next.js on Vercel)

Use the sibling repo **`librechat-db-nextjs`** — it serves private Blob files with `EXPORT_API_KEY`.

See [`librechat-db-nextjs/SETUP.md`](../librechat-db-nextjs/SETUP.md) for deploy steps.

### Step 4 — Connect Power BI

1. Power BI Desktop → **Get data** → **Web** → **Advanced**
2. URL: `https://YOUR-APP.vercel.app/api/v1/export/latest.xlsx`
3. Header: `X-API-Key` = your `EXPORT_API_KEY`
4. Schedule refresh after the daily cron (e.g. 4:00 AM UTC)

---

### Step 5 — Daily operation checklist

| What | When |
|------|------|
| Cron exports MongoDB → Excel | 3:00 AM UTC |
| File uploaded to Vercel Blob | End of each cron run |
| Next.js API serves latest file | Anytime (with API key) |
| Power BI refresh | After cron |

---

### Troubleshooting Railway deploy

| Problem | Fix |
|---------|-----|
| Build fails | Check Dockerfile path is `cloud/Dockerfile`, repo root is `/` |
| `Set MONGO_URI or MONGO_PRIVATE_URL` | Add `${{MongoDB.MONGO_PRIVATE_URL}}` on cron service |
| Cron runs but 0 messages | Confirm `MONGO_DB_NAME=test` |
| Next.js `404 Export not found` | Run cron once; check Blob store in Vercel |
| Export timeout | Normal for first run (~5–15 min) |
| MongoDB service name differs | When referencing vars, pick your MongoDB service in Railway |

---

## Quick start (full export → Excel)

Run these commands in order:

```bash
# 1. Export users + conversations (and messages if small enough)
./railway-export.sh ./export

# 2. Export messages in batches (recommended — large collection)
./railway-export-messages.sh ./export

# 3. Verify file count matches database
python3 verify-export.py

# 4. Generate one combined Excel file
python3 json-to-excel.py
```

**Output:** `export/excel/librechat-combined.xlsx`  
One sheet, one row per message, with user + conversation + message joined.

Open it:

```bash
open export/excel/librechat-combined.xlsx
```

> **Tip:** Step 2 is safe to re-run — it resumes from where it left off and exits immediately if the export is already complete.

---

## Scripts reference

### `railway-mongo.sh` — run MongoDB queries

Run any `mongosh` expression inside the Railway container:

```bash
./railway-mongo.sh 'db.adminCommand({ping:1})'

./railway-mongo.sh 'db.getSiblingDB("test").getCollectionNames()'

./railway-mongo.sh 'db.getSiblingDB("test").users.countDocuments()'

./railway-mongo.sh 'db.getSiblingDB("test").users.find({}, {email:1, name:1}).limit(5).forEach(printjson)'
```

### `railway-export.sh` — export JSON

Exports three files to `./export/` (or a custom folder):

| File | Collection |
|------|------------|
| `users.json` | User accounts |
| `conversations.json` | Chat threads |
| `messages.json` | All messages |

```bash
./railway-export.sh ./export
```

> **Note:** For `messages`, prefer `railway-export-messages.sh` instead — a single SSH export often hangs or truncates on large collections (~46k+ documents). JSON files may also start with a mongoexport log line (`connected to: mongodb://localhost/`). Downstream scripts skip non-JSON lines automatically.

### `railway-export-messages.sh` — batched messages export

**Use this for messages.** Exports `messages.json` in batches of 5,000 via `railway ssh`.

Features:

- Sorts by `_id` for stable `--skip` / `--limit` pagination
- Validates each batch as valid JSON before appending
- **Auto-resumes** from the existing file (counts valid JSON lines only)
- Compares file count vs database count on start and finish
- Exits immediately if already complete (no extra batch / hang)
- Shows mongoexport stderr when a batch fails

```bash
./railway-export-messages.sh ./export
```

Start fresh (overwrite existing file):

```bash
FORCE_RESTART=1 ./railway-export-messages.sh ./export
```

### `verify-export.py` — check export completeness

Compares valid JSON lines in `export/messages.json` against the live database count:

```bash
python3 verify-export.py
```

Example output:

```
File (valid JSON): 46112
Database:          46112
OK — export includes all messages
```

If messages are missing, re-run `./railway-export-messages.sh ./export`.

### `json-to-excel.py` — combined Excel

Reads JSON from `./export/` and writes:

```
export/excel/librechat-combined.xlsx
```

**Columns in the combined sheet:**

| Column | Description |
|--------|-------------|
| `user_name`, `user_email`, `user_role` | Message author |
| `conversation_title`, `conversation_endpoint`, `conversation_model` | Chat info |
| `sender`, `message_text`, `is_user_message` | Message content |
| `token_count`, `message_created_at` | Metadata |

Requires Python 3 + `openpyxl`:

```bash
pip3 install openpyxl
python3 json-to-excel.py
```

### `test-mongodb.sh` — test external TCP connection

Only needed if you want Compass / Cursor MCP from your Mac (often blocked):

```bash
./test-mongodb.sh
```

---

## Interactive shell (alternative)

```bash
railway ssh
```

Inside the container:

```bash
mongosh -u "$MONGOUSER" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin
```

```javascript
use test
show collections
db.users.find().limit(5)
db.conversations.find().sort({ updatedAt: -1 }).limit(5)
```

---

## Railway networking notes

| URL | Use |
|-----|-----|
| `MONGO_PRIVATE_URL` | App-to-app inside Railway only |
| `MONGO_URL` (TCP proxy) | External access from your Mac |

TCP proxy **must** point to internal port **`27017`** (not 5432).

If external access fails, use **`railway ssh`** — it always works when the DB is healthy.

---

## Daily cloud export (Railway Cron)

Yes — you can run this automatically in the cloud without your Mac. The recommended setup is a **Railway Cron service** in the same project as MongoDB.

```mermaid
flowchart LR
  subgraph railway [Railway project]
    Cron[Export Cron service]
    Mongo[(MongoDB)]
    Vol[(Volume /data/export)]
    Cron -->|MONGO_PRIVATE_URL| Mongo
    Cron --> Vol
  end
  Vol -->|optional| S3[(S3 / R2)]
  Vol -->|optional| You[Download from Railway]
```

### Why this works better than your Mac

| | Mac (SSH scripts) | Cloud cron |
|--|-------------------|------------|
| Connection | `railway ssh` | `MONGO_PRIVATE_URL` (internal network) |
| Schedule | Manual | Daily cron (e.g. 3:00 AM UTC) |
| Reliability | Depends on your laptop | Runs on Railway |
| Output | Local `./export/` | Persistent volume or S3 |

### One-time setup

1. **Create a new service** in Railway project `industrious-flow`:
   - Deploy from this repo (GitHub or `railway up`)
   - Service name suggestion: `librechat-export-cron`

2. **Set environment variables** on the cron service:

| Variable | Value |
|----------|--------|
| `MONGO_PRIVATE_URL` | `${{MongoDB.MONGO_PRIVATE_URL}}` (reference from MongoDB service) |
| `MONGO_DB_NAME` | `test` |

Optional S3 upload (Cloudflare R2, AWS S3, etc.):

| Variable | Value |
|----------|--------|
| `S3_BUCKET` | your bucket name |
| `S3_PREFIX` | `exports/` |
| `S3_ENDPOINT` | R2 endpoint URL (omit for AWS) |
| `AWS_ACCESS_KEY_ID` | access key |
| `AWS_SECRET_ACCESS_KEY` | secret key |

3. **Add a volume** mounted at `/data/export` (Railway → service → Volumes). Exports are kept here:
   - `librechat-combined-YYYY-MM-DD.xlsx` — dated file each run
   - `librechat-combined-latest.xlsx` — symlink to newest
   - `YYYY-MM-DD/` — JSON + Excel for that day

4. **Cron schedule** is in `railway.json` (default **3:00 AM UTC daily**):

```json
"cronSchedule": "0 3 * * *"
```

Change the schedule in Railway UI or edit `railway.json` and redeploy.

5. **Deploy** — Railway builds `cloud/Dockerfile`, runs `/app/export-daily.sh`, then stops until the next cron tick.

### Test before enabling cron

Run the service once manually (Railway → Deploy → Run, or temporarily remove `cronSchedule`):

```bash
railway link          # pick librechat-export-cron
railway ssh -- /app/export-daily.sh
```

If the cron container is not running, use **Redeploy** in the Railway dashboard instead.

Check logs for `=== Done ===` and download the Excel from the volume or S3.

### Other cloud options

| Platform | Works? | Notes |
|----------|--------|-------|
| **Railway Cron** | ✅ Best | Same project, private Mongo URL, volume storage |
| **GitHub Actions cron** | ⚠️ Possible | Needs Railway token + SSH; slower, more fragile |
| **Vercel / serverless** | ❌ Poor fit | 46k+ messages exceeds time/memory limits |
| **Your Mac + cron** | ⚠️ | Laptop must be on; SSH can drop |

### Cloud files

| Path | Purpose |
|------|---------|
| `cloud/Dockerfile` | Cron container (Python + pymongo) |
| `cloud/export-daily.sh` | Main job: export → Excel → Blob upload |
| `cloud/export_collections.py` | MongoDB → JSON (pymongo) |
| `cloud/upload-vercel-blob.py` | Upload Excel to Vercel Blob |
| `cloud/test-mongo.sh` | Pre-flight MongoDB connection check |
| `cloud/requirements.txt` | Python dependencies |
| `railway.json` | Cron schedule + Docker build config |

Download API lives in **`librechat-db-nextjs`**, not in this repo.

---

## Export API (Power BI / dashboards)

Use **`librechat-db-nextjs`** on Vercel to serve private Blob files with `EXPORT_API_KEY`.

See [`librechat-db-nextjs/SETUP.md`](../librechat-db-nextjs/SETUP.md) and [`librechat-db-nextjs/README.md`](../librechat-db-nextjs/README.md).

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `railway: Unauthorized` | Run `railway login` |
| Wrong service linked | Run `railway link` and pick MongoDB |
| `SyntaxError` in `railway-mongo.sh` | Update script; use latest version in this repo |
| `messages.json` truncated or incomplete | Run `./railway-export-messages.sh ./export` (resumes automatically), then `python3 verify-export.py` |
| Batch failed at `skip=…` with mongoexport parse error | Fixed in current script (`--sort='{"_id":1}'` must have no spaces). Pull latest and re-run |
| Script says "Export already complete" but Excel row count looks low | Run `python3 verify-export.py`. If missing, re-run `./railway-export-messages.sh ./export` |
| `./test-mongodb.sh` TCP fail | Use SSH export instead; or try mobile hotspot / redeploy MongoDB on Railway |
| Railway Database UI spinner | Known Railway issue — use `railway ssh` or these scripts |
| `json.decoder.JSONDecodeError` in Excel step | Truncated line in export (interrupted batch). Run `./railway-export-messages.sh ./export`, then `python3 json-to-excel.py` again (invalid lines are skipped with a warning) |
| `env: bash\r: No such file or directory` | Windows CRLF line endings in scripts. Run `sed -i '' 's/\r$//' *.sh` |

---

## Security

- **`export/`** and **`export/excel/`** are in `.gitignore` — do not commit user/chat data
- Password hashes are **not** included in Excel exports
- Rotate MongoDB password if credentials were exposed in screenshots or chat

---

## Typical workflow (next time)

```bash
cd librechat-db
railway status                         # confirm linked to MongoDB
./railway-export.sh ./export           # users + conversations
./railway-export-messages.sh ./export  # messages (batched, resumable)
python3 verify-export.py               # confirm all messages exported
python3 json-to-excel.py                 # one combined Excel
open export/excel/librechat-combined.xlsx
```

For a quick check without exporting everything:

```bash
./railway-mongo.sh 'db.getSiblingDB("test").users.countDocuments()'
./railway-mongo.sh 'db.getSiblingDB("test").conversations.countDocuments()'
./railway-mongo.sh 'db.getSiblingDB("test").messages.countDocuments()'
```
