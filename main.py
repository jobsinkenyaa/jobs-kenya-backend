#!/usr/bin/env python3
"""
================================================================
  🇰🇪 JOBS OPPORTUNITIES IN KENYA — BACKEND SERVER
  Runs on Railway.app
  - Scrapes 6 Kenyan job sites every hour
  - Serves scraped jobs via REST API
  - Your website fetches from this API
================================================================
"""

import os
import json
import time
import threading
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import re
import schedule
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Allow your Netlify site to fetch from this API

# ── CONFIG ─────────────────────────────────────────────────────
ADMIN_SECRET = os.getenv('ADMIN_SECRET', 'jobskenya-secret-2025')
PORT         = int(os.getenv('PORT', 5001))
OUTPUT_FILE  = 'scraped_jobs.json'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}

# ── HELPERS ─────────────────────────────────────────────────────
def get_page(url, retries=3):
    for attempt in range(retries):
        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            if res.status_code == 200:
                return BeautifulSoup(res.content, 'html.parser')
            print(f'  [!] HTTP {res.status_code} for {url}')
        except Exception as e:
            print(f'  [!] Attempt {attempt+1} failed: {e}')
            time.sleep(2)
    return None

def clean(t):
    return ' '.join((t or '').strip().split())

def extract_county(text):
    counties = ['Nairobi','Mombasa','Kisumu','Nakuru','Eldoret','Kiambu',
                'Machakos','Nyeri','Meru','Kakamega','Kisii','Kilifi',
                'Embu','Garissa','Bungoma','Siaya','Migori','Kajiado',
                'Laikipia','Kericho','Nandi','Bomet','Baringo','Kwale',
                'Kitui','Makueni','Turkana','Homa Bay','Nyamira','Mandera',
                'Wajir','Marsabit','Narok','Vihiga','Lamu','Thika']
    t = (text or '').lower()
    for c in counties:
        if c.lower() in t:
            return c
    if 'remote' in t or 'online' in t:
        return 'Remote'
    return 'Nairobi'

def detect_type(text):
    t = (text or '').lower()
    if any(w in t for w in ['intern','attachment','graduate trainee']): return 'Internship'
    if any(w in t for w in ['part-time','part time','casual']): return 'Part-Time'
    if any(w in t for w in ['government','county','ministry','public service','psc','civil service']): return 'Government'
    if any(w in t for w in ['ngo','unicef','undp','wfp','unhcr','oxfam','red cross','non-profit','foundation']): return 'NGO'
    if any(w in t for w in ['remote','work from home','wfh']): return 'Remote'
    if any(w in t for w in ['contract','consultant','temporary','freelance']): return 'Contract'
    return 'Full-Time'

def detect_sector(text):
    t = (text or '').lower()
    if any(w in t for w in ['software','developer','ict','data','cyber','system','network','tech']): return 'ICT & Technology'
    if any(w in t for w in ['nurse','doctor','medical','health','clinical','pharmacy','lab']): return 'Health & Medicine'
    if any(w in t for w in ['finance','account','audit','tax','banking','economist']): return 'Finance & Banking'
    if any(w in t for w in ['engineer','civil','mechanical','electrical','construction']): return 'Engineering'
    if any(w in t for w in ['teach','tutor','lecturer','school','education','training']): return 'Education'
    if any(w in t for w in ['farm','agri','crop','livestock','food','rural']): return 'Agriculture'
    if any(w in t for w in ['market','sales','brand','advertis','digital']): return 'Marketing & Sales'
    if any(w in t for w in ['ngo','humanitarian','relief','development','programme']): return 'NGO / Non-Profit'
    if any(w in t for w in ['legal','lawyer','advocate','court','compliance']): return 'Legal'
    if any(w in t for w in ['driver','transport','logistics','supply','fleet']): return 'Transport & Logistics'
    if any(w in t for w in ['hotel','hospitality','tour','chef','cook','restaurant']): return 'Hospitality & Tourism'
    return 'General'

def deduplicate(jobs):
    seen, unique = set(), []
    for j in jobs:
        key = f"{j.get('title','').lower()}|{j.get('company','').lower()}"
        if key not in seen:
            seen.add(key)
            unique.append(j)
    return unique


# ── SCRAPERS ────────────────────────────────────────────────────

def scrape_myjobinkenya():
    print('\n[1] Scraping MyJobInKenya...')
    jobs, base = [], 'https://www.myjobinkenya.com'
    for page in range(1, 4):
        soup = get_page(f'{base}/jobs/?page={page}')
        if not soup: break
        listings = (soup.find_all('div', class_=re.compile(r'job[-_]?item|listing|job[-_]?post', re.I))
                    or soup.find_all('article')
                    or soup.find_all('li', class_=re.compile(r'job', re.I)))
        for item in listings:
            try:
                title_el    = item.find(['h2','h3','h4','a'], class_=re.compile(r'title|job[-_]?name', re.I))
                company_el  = item.find(class_=re.compile(r'company|employer|org', re.I))
                location_el = item.find(class_=re.compile(r'location|county|city', re.I))
                deadline_el = item.find(class_=re.compile(r'deadline|date|expir', re.I))
                link_el     = item.find('a', href=True)
                title       = clean(title_el.get_text())    if title_el    else ''
                if not title: continue
                company     = clean(company_el.get_text())  if company_el  else 'Not specified'
                location    = clean(location_el.get_text()) if location_el else 'Kenya'
                deadline    = clean(deadline_el.get_text()) if deadline_el else ''
                href        = link_el['href'] if link_el else ''
                link        = base + href if href.startswith('/') else href or base
                jobs.append({
                    'id': f"myjob-{len(jobs)}",
                    'title': title, 'company': company,
                    'location': location, 'county': extract_county(location),
                    'type': detect_type(title+' '+company),
                    'sector': detect_sector(title),
                    'salary': 'Not stated', 'deadline': deadline,
                    'link': link, 'apply_email': '', 'description': '',
                    'source': 'MyJobInKenya',
                    'scraped_at': datetime.now().isoformat()
                })
            except: continue
        time.sleep(1)
    print(f'  ✅ MyJobInKenya: {len(jobs)} jobs')
    return jobs


def scrape_brightermonday():
    print('\n[2] Scraping BrighterMonday Kenya...')
    jobs, base = [], 'https://www.brightermonday.co.ke'
    for page in range(1, 4):
        soup = get_page(f'{base}/jobs?page={page}')
        if not soup: break
        listings = (soup.find_all('article', class_=re.compile(r'job|listing', re.I))
                    or soup.find_all('div', class_=re.compile(r'job[-_]?card|listing[-_]?item', re.I)))
        for item in listings:
            try:
                title_el    = item.find(['h2','h3','h4'])
                company_el  = item.find(class_=re.compile(r'company|employer', re.I))
                location_el = item.find(class_=re.compile(r'location|place', re.I))
                salary_el   = item.find(class_=re.compile(r'salary|pay|remun', re.I))
                link_el     = item.find('a', href=True)
                title       = clean(title_el.get_text())    if title_el    else ''
                if not title: continue
                company     = clean(company_el.get_text())  if company_el  else 'Not specified'
                location    = clean(location_el.get_text()) if location_el else 'Kenya'
                salary      = clean(salary_el.get_text())   if salary_el   else 'Not stated'
                href        = link_el['href'] if link_el else ''
                link        = base + href if href.startswith('/') else href or base

                # Try to get full job description from detail page
                desc, email = '', ''
                if link and link != base:
                    detail = get_page(link)
                    if detail:
                        desc_el = detail.find(class_=re.compile(r'description|detail|content|body', re.I))
                        desc    = clean(desc_el.get_text()) if desc_el else ''
                        # Extract email from description
                        emails  = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', desc)
                        email   = emails[0] if emails else ''
                    time.sleep(0.5)

                jobs.append({
                    'id': f"bm-{len(jobs)}",
                    'title': title, 'company': company,
                    'location': location, 'county': extract_county(location),
                    'type': detect_type(title+' '+company),
                    'sector': detect_sector(title),
                    'salary': salary, 'deadline': '',
                    'link': link, 'apply_email': email,
                    'description': desc[:2000],  # Limit description size
                    'source': 'BrighterMonday',
                    'scraped_at': datetime.now().isoformat()
                })
            except: continue
        time.sleep(1)
    print(f'  ✅ BrighterMonday: {len(jobs)} jobs')
    return jobs


def scrape_fuzu():
    print('\n[3] Scraping Fuzu Kenya...')
    jobs, base = [], 'https://fuzu.com'
    for page in range(1, 3):
        soup = get_page(f'{base}/kenya/jobs?page={page}')
        if not soup: break
        listings = (soup.find_all('div', class_=re.compile(r'job[-_]?card|job[-_]?item|listing', re.I))
                    or soup.find_all('article'))
        for item in listings:
            try:
                title_el    = item.find(['h2','h3','h4','a'])
                company_el  = item.find(class_=re.compile(r'company|employer|org', re.I))
                location_el = item.find(class_=re.compile(r'location|place|county', re.I))
                link_el     = item.find('a', href=True)
                title       = clean(title_el.get_text()) if title_el else ''
                if not title: continue
                company     = clean(company_el.get_text())  if company_el  else 'Not specified'
                location    = clean(location_el.get_text()) if location_el else 'Kenya'
                href        = link_el['href'] if link_el else ''
                link        = base + href if href.startswith('/') else href or base
                jobs.append({
                    'id': f"fuzu-{len(jobs)}",
                    'title': title, 'company': company,
                    'location': location, 'county': extract_county(location),
                    'type': detect_type(title+' '+company),
                    'sector': detect_sector(title),
                    'salary': 'Not stated', 'deadline': '',
                    'link': link, 'apply_email': '',
                    'description': '',
                    'source': 'Fuzu',
                    'scraped_at': datetime.now().isoformat()
                })
            except: continue
        time.sleep(1)
    print(f'  ✅ Fuzu: {len(jobs)} jobs')
    return jobs


def scrape_public_service():
    print('\n[4] Scraping Public Service Commission...')
    jobs, base = [], 'https://www.publicservice.go.ke'
    soup = get_page(f'{base}/index.php/job-opportunities')
    if not soup:
        print('  ⚠️  PSC not reachable')
        return []
    listings = (soup.find_all('div', class_=re.compile(r'job|vacancy|opportunit', re.I))
                or soup.find_all('tr') or soup.find_all('li'))
    for item in listings:
        try:
            title_el = item.find(['h2','h3','h4','a','td'])
            link_el  = item.find('a', href=True)
            title    = clean(title_el.get_text()) if title_el else ''
            if not title or len(title) < 5: continue
            href = link_el['href'] if link_el else ''
            link = base + href if href.startswith('/') else href or base
            jobs.append({
                'id': f"psc-{len(jobs)}",
                'title': title, 'company': 'Public Service Commission Kenya',
                'location': 'Kenya', 'county': 'Nairobi',
                'type': 'Government', 'sector': 'Government / Civil Service',
                'salary': 'Government Scale', 'deadline': '',
                'link': link, 'apply_email': 'info@publicservice.go.ke',
                'description': '',
                'source': 'Public Service Commission',
                'scraped_at': datetime.now().isoformat()
            })
        except: continue
    print(f'  ✅ Public Service Commission: {len(jobs)} jobs')
    return jobs


def scrape_ngo_jobs():
    print('\n[5] Scraping NGO Jobs Kenya...')
    jobs, base = [], 'https://www.ngojobskenya.com'
    for page in range(1, 3):
        soup = get_page(f'{base}/jobs/page/{page}/')
        if not soup: break
        listings = (soup.find_all('article')
                    or soup.find_all('div', class_=re.compile(r'job|post|listing', re.I)))
        for item in listings:
            try:
                title_el    = item.find(['h2','h3','h4'])
                company_el  = item.find(class_=re.compile(r'company|employer|org', re.I))
                location_el = item.find(class_=re.compile(r'location|place', re.I))
                deadline_el = item.find(class_=re.compile(r'deadline|date|closing', re.I))
                link_el     = item.find('a', href=True)
                title       = clean(title_el.get_text()) if title_el else ''
                if not title: continue
                company     = clean(company_el.get_text())  if company_el  else 'NGO'
                location    = clean(location_el.get_text()) if location_el else 'Kenya'
                deadline    = clean(deadline_el.get_text()) if deadline_el else ''
                href        = link_el['href'] if link_el else ''
                link        = href if href.startswith('http') else base + href
                jobs.append({
                    'id': f"ngo-{len(jobs)}",
                    'title': title, 'company': company,
                    'location': location, 'county': extract_county(location),
                    'type': 'NGO', 'sector': 'NGO / Non-Profit',
                    'salary': 'Not stated', 'deadline': deadline,
                    'link': link, 'apply_email': '',
                    'description': '',
                    'source': 'NGO Jobs Kenya',
                    'scraped_at': datetime.now().isoformat()
                })
            except: continue
        time.sleep(1)
    print(f'  ✅ NGO Jobs Kenya: {len(jobs)} jobs')
    return jobs


def scrape_career_point():
    print('\n[6] Scraping Career Point Kenya...')
    jobs, base = [], 'https://www.careerpointkenya.co.ke'
    for page in range(1, 3):
        soup = get_page(f'{base}/jobs/?page={page}')
        if not soup: break
        listings = (soup.find_all('div', class_=re.compile(r'job|listing|post', re.I))
                    or soup.find_all('article'))
        for item in listings:
            try:
                title_el    = item.find(['h2','h3','h4'])
                company_el  = item.find(class_=re.compile(r'company|employer', re.I))
                location_el = item.find(class_=re.compile(r'location|county', re.I))
                deadline_el = item.find(class_=re.compile(r'deadline|closing|date', re.I))
                link_el     = item.find('a', href=True)
                title       = clean(title_el.get_text()) if title_el else ''
                if not title: continue
                company     = clean(company_el.get_text())  if company_el  else 'Not specified'
                location    = clean(location_el.get_text()) if location_el else 'Kenya'
                deadline    = clean(deadline_el.get_text()) if deadline_el else ''
                href        = link_el['href'] if link_el else ''
                link        = base + href if href.startswith('/') else href or base
                jobs.append({
                    'id': f"cp-{len(jobs)}",
                    'title': title, 'company': company,
                    'location': location, 'county': extract_county(location),
                    'type': detect_type(title+' '+company),
                    'sector': detect_sector(title),
                    'salary': 'Not stated', 'deadline': deadline,
                    'link': link, 'apply_email': '',
                    'description': '',
                    'source': 'Career Point Kenya',
                    'scraped_at': datetime.now().isoformat()
                })
            except: continue
        time.sleep(1)
    print(f'  ✅ Career Point Kenya: {len(jobs)} jobs')
    return jobs


# ── RUN ALL SCRAPERS ────────────────────────────────────────────
def run_all():
    print('\n' + '='*55)
    print('  🇰🇪 JOBS KENYA — Scraping started')
    print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('='*55)

    all_jobs = []
    for name, fn in [
        ('MyJobInKenya',           scrape_myjobinkenya),
        ('BrighterMonday',         scrape_brightermonday),
        ('Fuzu',                   scrape_fuzu),
        ('Public Service',         scrape_public_service),
        ('NGO Jobs Kenya',         scrape_ngo_jobs),
        ('Career Point Kenya',     scrape_career_point),
    ]:
        try:
            all_jobs.extend(fn())
        except Exception as e:
            print(f'  ❌ {name} failed: {e}')

    # Clean up
    before     = len(all_jobs)
    all_jobs   = deduplicate(all_jobs)
    all_jobs.sort(key=lambda j: j.get('scraped_at',''), reverse=True)

    print(f'\n  🧹 {before} → {len(all_jobs)} unique jobs')

    output = {
        'total':      len(all_jobs),
        'scraped_at': datetime.now().isoformat(),
        'jobs':       all_jobs
    }
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'  ✅ {len(all_jobs)} jobs saved!\n')
    return all_jobs


# ── SCHEDULER (runs every hour in background) ───────────────────
def start_scheduler():
    schedule.every(1).hours.do(run_all)
    print('  ⏰ Scheduler running — scraping every hour')
    while True:
        schedule.run_pending()
        time.sleep(60)


# ── API ROUTES ──────────────────────────────────────────────────

@app.route('/')
def home():
    return jsonify({
        'status':  'running',
        'service': '🇰🇪 Jobs Opportunities in Kenya — Scraper API',
        'endpoints': {
            'GET  /jobs':           'Get all scraped jobs (with optional filters)',
            'GET  /status':         'Check scraper status',
            'POST /scrape':         'Manually trigger a scrape (requires admin token)',
        }
    })

@app.route('/jobs')
def get_jobs():
    """Return scraped jobs with optional filters"""
    try:
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        jobs = data.get('jobs', [])

        # Filters
        county  = request.args.get('county','').lower()
        sector  = request.args.get('sector','').lower()
        jtype   = request.args.get('type','').lower()
        keyword = request.args.get('q','').lower()
        limit   = min(int(request.args.get('limit', 50)), 200)

        if county:  jobs = [j for j in jobs if county  in j.get('county','').lower()]
        if sector:  jobs = [j for j in jobs if sector  in j.get('sector','').lower()]
        if jtype:   jobs = [j for j in jobs if jtype   in j.get('type','').lower()]
        if keyword: jobs = [j for j in jobs if keyword in (j.get('title','')+j.get('company','')).lower()]

        return jsonify({
            'total':       len(jobs),
            'returned':    min(len(jobs), limit),
            'scraped_at':  data.get('scraped_at'),
            'jobs':        jobs[:limit]
        })
    except FileNotFoundError:
        return jsonify({'total': 0, 'jobs': [], 'message': 'Scraper has not run yet. Starting now...'})

@app.route('/status')
def status():
    """Check when scraper last ran and how many jobs it found"""
    try:
        with open(OUTPUT_FILE, 'r') as f:
            data = json.load(f)
        return jsonify({
            'status':     'ok',
            'total_jobs': data.get('total', 0),
            'last_run':   data.get('scraped_at'),
            'message':    'Scraper is running every hour'
        })
    except:
        return jsonify({'status': 'no_data', 'total_jobs': 0, 'last_run': None})

@app.route('/scrape', methods=['POST'])
def manual_scrape():
    """Manually trigger a scrape — requires admin token in header"""
    token = request.headers.get('X-Admin-Token','')
    if token != ADMIN_SECRET:
        return jsonify({'error': 'Unauthorized — send X-Admin-Token header'}), 401
    # Run in background so API doesn't time out
    thread = threading.Thread(target=run_all)
    thread.daemon = True
    thread.start()
    return jsonify({'success': True, 'message': 'Scrape started in background'})


# ── STARTUP ─────────────────────────────────────────────────────
if __name__ == '__main__':
    print('\n🇰🇪 Jobs Kenya Backend Starting...')

    # Run first scrape immediately in background
    scrape_thread = threading.Thread(target=run_all)
    scrape_thread.daemon = True
    scrape_thread.start()

    # Start hourly scheduler in background
    scheduler_thread = threading.Thread(target=start_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()

    # Start Flask API
    print(f'  🌐 API running on port {PORT}')
    app.run(host='0.0.0.0', port=PORT, debug=False)
