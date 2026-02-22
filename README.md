# 🇰🇪 Jobs Kenya — Backend Deployment Guide

## Files in this folder:
- `main.py` — The main server (scraper + API)
- `requirements.txt` — Python packages needed
- `Procfile` — Tells Railway how to start the server
- `railway.json` — Railway configuration

---

## STEP-BY-STEP DEPLOYMENT TO RAILWAY

### Step 1 — Create a GitHub account (if you don't have one)
Go to github.com → Sign Up → Free account

### Step 2 — Create a new GitHub repository
1. Click the "+" icon top right → "New repository"
2. Name it: `jobs-kenya-backend`
3. Set to **Public**
4. Click "Create repository"

### Step 3 — Upload these files to GitHub
1. In your new repo, click "Add file" → "Upload files"
2. Upload ALL 4 files:
   - main.py
   - requirements.txt
   - Procfile
   - railway.json
3. Click "Commit changes"

### Step 4 — Create Railway account
1. Go to railway.app
2. Click "Login" → "Login with GitHub"
3. Authorize Railway to access your GitHub

### Step 5 — Deploy to Railway
1. In Railway dashboard → click "New Project"
2. Click "Deploy from GitHub repo"
3. Select "jobs-kenya-backend"
4. Railway will automatically detect it's a Python app and deploy it

### Step 6 — Set environment variable
1. In Railway → click your project → "Variables"
2. Add: `ADMIN_SECRET` = `jobskenya-admin-2025` (choose your own secret)
3. Click "Save"

### Step 7 — Get your API URL
1. In Railway → click your project → "Settings" → "Domains"
2. Click "Generate Domain"
3. You'll get a URL like: `https://jobs-kenya-backend.up.railway.app`
4. **Copy this URL** — you need it for the next step

### Step 8 — Connect to your website
Replace the URL in your index.html where it says:
`YOUR_RAILWAY_URL`
with your actual Railway URL

### Step 9 — Test it works
Open your browser and go to:
`https://your-railway-url.up.railway.app/status`

You should see:
```json
{
  "status": "ok",
  "total_jobs": 150,
  "last_run": "2025-01-15T10:30:00"
}
```

---

## API ENDPOINTS

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info |
| `/jobs` | GET | Get all scraped jobs |
| `/jobs?county=Nairobi` | GET | Filter by county |
| `/jobs?type=NGO` | GET | Filter by job type |
| `/jobs?q=accountant` | GET | Search by keyword |
| `/status` | GET | Check scraper status |
| `/scrape` | POST | Trigger manual scrape |

---

## COSTS
Railway free tier gives you $5/month of credit which is enough to run this backend 24/7.
No credit card required to start.

---

## TROUBLESHOOTING
- If deployment fails → check the "Logs" tab in Railway for error messages
- If `/status` shows `no_data` → wait 5 minutes for first scrape to complete
- If jobs are 0 → some job sites may have changed their HTML structure
