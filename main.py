#!/usr/bin/env python3
"""
================================================================
  🇰🇪 JOBS OPPORTUNITIES IN KENYA — BACKEND SERVER
  Runs on Railway.app via gunicorn
================================================================
"""

import os, json, time, threading, re, requests, schedule
from datetime import datetime
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

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
    if any(w in t for w in ['government','county','ministry','public service','psc']): return 'Government'
    if any(w in t for w in ['ngo','unicef','undp','wfp','unhcr','oxfam','red cross','non-profit']): return 'NGO'
    if any(w in t for w in ['remote','work from home','wfh']): return 'Remote'
    if any(w in t for w in ['contract','consultant','temporary','freelance']): return 'Contract'
    return 'Full-Time'

def detect_sector(text):
    t = (text or '').lower()
    if any(w in t for w in ['software','developer','ict','data','cyber','tech']): return 'ICT & Technology'
    if any(w in t for w in ['nurse','doctor','medical','health','clinical','pharmacy']): return 'Health & Medicine'
    if any(w in t for w in ['finance','account','audit','tax','banking']): return 'Finance & Banking'
    if any(w in t for w in ['engineer','civil','mechanical','electrical','construction']): return 'Engineering'
    if any(w in t for w in ['teach','tutor','lecturer','school','education']): return 'Education'
    if any(w in t for w in ['farm','agri','crop','livestock','food']): return 'Agriculture'
    if any(w in t for w in ['market','sales','brand','advertis','digital']): return 'Marketing & Sales'
    if any(w in t for w in ['ngo','humanitarian','relief','development']): return 'NGO / Non-Profit'
    if any(w in t for w in ['legal','lawyer','advocate','court','compliance']): return 'Legal'
    if any(w in t for w in ['driver','transport','logistics','supply','fleet']): return 'Transport & Logistics'
    if any(w in t for w in ['hotel','hospitality','tour','chef','cook','restaurant']): return 'Hospitality'
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

def scrape_brightermonday():
    print('\n[1] Scraping BrighterMonday Kenya...')
    jobs, base = [], 'https://www.brightermonday.co.ke'
    for page in range(1, 4):
        soup = get_page(f'{base}/jobs?page={page}')
        if not soup: break
        listings = (soup.find_all('article', class_=re.compile(r'job|listing', re.I)) or
                    soup.find_all('div', class_=re.compile(r'job.?card|listing.?item', re.I)) or
                    soup.select('a[href*="/jobs/"]'))
        for item in listings:
            try:
                title_el    = item.find(['h2','h3','h4'])
                company_el  = item.find(class_=re.compile(r'company|employer', re.I))
                location_el = item.find(class_=re.compile(r'location|place', re.I))
                salary_el   = item.find(class_=re.compile(r'salary|pay|remun', re.I))
                link_el     = item.find('a', href=True) or item
                title   = clean(title_el.get_text())    if title_el    else ''
                if not title or len(title) < 4: continue
                company = clean(company_el.get_text())  if company_el  else 'Not specified'
                location= clean(location_el.get_text()) if location_el else 'Kenya'
                salary  = clean(salary_el.get_text())   if salary_el   else 'Not stated'
                href    = link_el.get('href','') if hasattr(link_el,'get') else ''
                link    = base + href if href.startswith('/') else (href if href.startswith('http') else base)
                jobs.append({
                    'id': f"bm-{len(jobs)}",
                    'title': title, 'company': company,
                    'location': location, 'county': extract_county(location),
                    'type': detect_type(title+' '+company),
                    'sector': detect_sector(title),
                    'salary': salary, 'deadline': '',
                    'link': link, 'apply_email': '', 'description': '',
                    'source': 'BrighterMonday',
                    'scraped_at': datetime.now().isoformat()
                })
            except: continue
        time.sleep(1.5)
    print(f'  ✅ BrighterMonday: {len(jobs)} jobs')
    return jobs


def scrape_myjobinkenya():
    print('\n[2] Scraping MyJobInKenya...')
    jobs, base = [], 'https://www.myjobinkenya.com'
    for page in range(1, 4):
        soup = get_page(f'{base}/jobs/?page={page}')
        if not soup: break
        listings = (soup.find_all('div', class_=re.compile(r'job.?item|listing|job.?post', re.I)) or
                    soup.find_all('article') or
                    soup.find_all('li', class_=re.compile(r'job', re.I)))
        for item in listings:
            try:
                title_el    = item.find(['h2','h3','h4','a'], class_=re.compile(r'title|job.?name', re.I))
                company_el  = item.find(class_=re.compile(r'company|employer|org', re.I))
                location_el = item.find(class_=re.compile(r'location|county|city', re.I))
                deadline_el = item.find(class_=re.compile(r'deadline|date|expir', re.I))
                link_el     = item.find('a', href=True)
                title   = clean(title_el.get_text())    if title_el    else ''
                if not title or len(title) < 4: continue
                company = clean(company_el.get_text())  if company_el  else 'Not specified'
                location= clean(location_el.get_text()) if location_el else 'Kenya'
                deadline= clean(deadline_el.get_text()) if deadline_el else ''
                href    = link_el['href'] if link_el else ''
                link    = base + href if href.startswith('/') else (href or base)
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
        time.sleep(1.5)
    print(f'  ✅ MyJobInKenya: {len(jobs)} jobs')
    return jobs


def scrape_fuzu():
    print('\n[3] Scraping Fuzu Kenya...')
    jobs, base = [], 'https://fuzu.com'
    for page in range(1, 3):
        soup = get_page(f'{base}/kenya/jobs?page={page}')
        if not soup: break
        listings = (soup.find_all('div', class_=re.compile(r'job.?card|job.?item|listing', re.I)) or
                    soup.find_all('article') or
                    soup.select('a[href*="/kenya/jobs/"]'))
        for item in listings:
            try:
                title_el    = item.find(['h2','h3','h4','a'])
                company_el  = item.find(class_=re.compile(r'company|employer|org', re.I))
                location_el = item.find(class_=re.compile(r'location|place|county', re.I))
                link_el     = item.find('a', href=True) or item
                title   = clean(title_el.get_text())    if title_el    else ''
                if not title or len(title) < 4: continue
                company = clean(company_el.get_text())  if company_el  else 'Not specified'
                location= clean(location_el.get_text()) if location_el else 'Kenya'
                href    = link_el.get('href','') if hasattr(link_el,'get') else ''
                link    = base + href if href.startswith('/') else (href if href.startswith('http') else base)
                jobs.append({
                    'id': f"fuzu-{len(jobs)}",
                    'title': title, 'company': company,
                    'location': location, 'county': extract_county(location),
                    'type': detect_type(title+' '+company),
                    'sector': detect_sector(title),
                    'salary': 'Not stated', 'deadline': '',
                    'link': link, 'apply_email': '', 'description': '',
                    'source': 'Fuzu',
                    'scraped_at': datetime.now().isoformat()
                })
            except: continue
        time.sleep(1.5)
    print(f'  ✅ Fuzu: {len(jobs)} jobs')
    return jobs


def scrape_ngo_jobs():
    print('\n[4] Scraping NGO Jobs Kenya...')
    jobs, base = [], 'https://www.ngojobskenya.com'
    for page in range(1, 3):
        soup = get_page(f'{base}/jobs/page/{page}/')
        if not soup: break
        listings = (soup.find_all('article') or
                    soup.find_all('div', class_=re.compile(r'job|post|listing', re.I)))
        for item in listings:
            try:
                title_el    = item.find(['h2','h3','h4'])
                company_el  = item.find(class_=re.compile(r'company|employer|org', re.I))
                location_el = item.find(class_=re.compile(r'location|place', re.I))
                deadline_el = item.find(class_=re.compile(r'deadline|date|closing', re.I))
                link_el     = item.find('a', href=True)
                title   = clean(title_el.get_text())    if title_el    else ''
                if not title or len(title) < 4: continue
                company = clean(company_el.get_text())  if company_el  else 'NGO'
                location= clean(location_el.get_text()) if location_el else 'Kenya'
                deadline= clean(deadline_el.get_text()) if deadline_el else ''
                href    = link_el['href'] if link_el else ''
                link    = href if href.startswith('http') else base + href
                jobs.append({
                    'id': f"ngo-{len(jobs)}",
                    'title': title, 'company': company,
                    'location': location, 'county': extract_county(location),
                    'type': 'NGO', 'sector': 'NGO / Non-Profit',
                    'salary': 'Not stated', 'deadline': deadline,
                    'link': link, 'apply_email': '', 'description': '',
                    'source': 'NGO Jobs Kenya',
                    'scraped_at': datetime.now().isoformat()
                })
            except: continue
        time.sleep(1.5)
    print(f'  ✅ NGO Jobs Kenya: {len(jobs)} jobs')
    return jobs


def scrape_career_point():
    print('\n[5] Scraping Career Point Kenya...')
    jobs, base = [], 'https://www.careerpointkenya.co.ke'
    for page in range(1, 3):
        soup = get_page(f'{base}/jobs/?page={page}')
        if not soup: break
        listings = (soup.find_all('div', class_=re.compile(r'job|listing|post', re.I)) or
                    soup.find_all('article'))
        for item in listings:
            try:
                title_el    = item.find(['h2','h3','h4'])
                company_el  = item.find(class_=re.compile(r'company|employer', re.I))
                location_el = item.find(class_=re.compile(r'location|county', re.I))
                deadline_el = item.find(class_=re.compile(r'deadline|closing|date', re.I))
                link_el     = item.find('a', href=True)
                title   = clean(title_el.get_text())    if title_el    else ''
                if not title or len(title) < 4: continue
                company = clean(company_el.get_text())  if company_el  else 'Not specified'
                location= clean(location_el.get_text()) if location_el else 'Kenya'
                deadline= clean(deadline_el.get_text()) if deadline_el else ''
                href    = link_el['href'] if link_el else ''
                link    = base + href if href.startswith('/') else (href or base)
                jobs.append({
                    'id': f"cp-{len(jobs)}",
                    'title': title, 'company': company,
                    'location': location, 'county': extract_county(location),
                    'type': detect_type(title+' '+company),
                    'sector': detect_sector(title),
                    'salary': 'Not stated', 'deadline': deadline,
                    'link': link, 'apply_email': '', 'description': '',
                    'source': 'Career Point Kenya',
                    'scraped_at': datetime.now().isoformat()
                })
            except: continue
        time.sleep(1.5)
    print(f'  ✅ Career Point Kenya: {len(jobs)} jobs')
    return jobs


# ── RUN ALL ──────────────────────────────────────────────────────
def run_all():
    print('\n' + '='*55)
    print('  🇰🇪 JOBS KENYA — Scraping started')
    print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('='*55)

    all_jobs = []
    for name, fn in [
        ('BrighterMonday',     scrape_brightermonday),
        ('MyJobInKenya',       scrape_myjobinkenya),
        ('Fuzu',               scrape_fuzu),
        ('NGO Jobs Kenya',     scrape_ngo_jobs),
        ('Career Point Kenya', scrape_career_point),
    ]:
        try:
            all_jobs.extend(fn())
        except Exception as e:
            print(f'  ❌ {name} failed: {e}')

    before   = len(all_jobs)
    all_jobs = deduplicate(all_jobs)
    all_jobs.sort(key=lambda j: j.get('scraped_at',''), reverse=True)
    print(f'\n  🧹 {before} → {len(all_jobs)} unique jobs')

    output = {
        'total':      len(all_jobs),
        'scraped_at': datetime.now().isoformat(),
        'jobs':       all_jobs
    }
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'  ✅ Done! {len(all_jobs)} jobs saved.\n')
    return all_jobs


# ── SCHEDULER ───────────────────────────────────────────────────
def start_scheduler():
    schedule.every(1).hours.do(run_all)
    while True:
        schedule.run_pending()
        time.sleep(60)


# ── API ROUTES ──────────────────────────────────────────────────
@app.route('/')
def home():
    return jsonify({
        'status':  'running',
        'service': '🇰🇪 Jobs Kenya Scraper API',
        'endpoints': {
            'GET /jobs':    'Get scraped jobs (optional: ?county=Nairobi&type=NGO&q=accountant&limit=50)',
            'GET /status':  'Check scraper status',
            'POST /scrape': 'Manually trigger scrape (X-Admin-Token header required)',
        }
    })

@app.route('/jobs')
def get_jobs():
    try:
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        jobs    = data.get('jobs', [])
        county  = request.args.get('county','').lower()
        sector  = request.args.get('sector','').lower()
        jtype   = request.args.get('type','').lower()
        keyword = request.args.get('q','').lower()
        limit   = min(int(request.args.get('limit', 50)), 200)

        if county:  jobs = [j for j in jobs if county  in j.get('county','').lower()]
        if sector:  jobs = [j for j in jobs if sector  in j.get('sector','').lower()]
        if jtype:   jobs = [j for j in jobs if jtype   in j.get('type','').lower()]
        if keyword: jobs = [j for j in jobs if keyword in (j.get('title','')+' '+j.get('company','')).lower()]

        return jsonify({'total': len(jobs), 'scraped_at': data.get('scraped_at'), 'jobs': jobs[:limit]})
    except FileNotFoundError:
        return jsonify({'total': 0, 'jobs': [], 'message': 'Scraper running for first time...'})

@app.route('/status')
def status():
    try:
        with open(OUTPUT_FILE, 'r') as f:
            data = json.load(f)
        return jsonify({'status': 'ok', 'total_jobs': data.get('total', 0), 'last_run': data.get('scraped_at')})
    except:
        return jsonify({'status': 'no_data', 'total_jobs': 0, 'last_run': None})

@app.route('/scrape', methods=['POST'])
def manual_scrape():
    token = request.headers.get('X-Admin-Token','')
    if token != ADMIN_SECRET:
        return jsonify({'error': 'Unauthorized'}), 401
    thread = threading.Thread(target=run_all, daemon=True)
    thread.start()
    return jsonify({'success': True, 'message': 'Scrape started in background — check /status in 5 minutes'})


# ── STARTUP — works with both gunicorn AND direct python ─────────
# This runs when gunicorn imports the module (not just __main__)
_started = False
def startup():
    global _started
    if _started:
        return
    _started = True
    print('\n🇰🇪 Jobs Kenya Backend — Starting scraper thread...')
    # First scrape in background
    t1 = threading.Thread(target=run_all, daemon=True)
    t1.start()
    # Hourly scheduler in background
    t2 = threading.Thread(target=start_scheduler, daemon=True)
    t2.start()

# Runs when gunicorn imports this file
startup()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
