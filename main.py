#!/usr/bin/env python3
"""
🇰🇪 Jobs Kenya Backend — Railway deployment
"""
import os, json, time, threading, re, requests, schedule
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

ADMIN_SECRET = os.getenv('ADMIN_SECRET', 'jobskenya-secret-2025')
PORT         = int(os.getenv('PORT', 8080))
OUTPUT_FILE  = '/tmp/scraped_jobs.json'  # /tmp works on Railway

# ── HELPERS ─────────────────────────────────────────────────────
def clean(t):
    return ' '.join((t or '').strip().split())

def extract_county(text):
    counties = ['Nairobi','Mombasa','Kisumu','Nakuru','Eldoret','Kiambu',
                'Machakos','Nyeri','Meru','Kakamega','Kisii','Kilifi',
                'Embu','Garissa','Bungoma','Kajiado','Kericho','Turkana',
                'Homa Bay','Nyamira','Narok','Vihiga','Thika','Lamu']
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
    if any(w in t for w in ['government','county','ministry','public service']): return 'Government'
    if any(w in t for w in ['ngo','unicef','undp','wfp','unhcr','oxfam','non-profit']): return 'NGO'
    if any(w in t for w in ['remote','work from home','wfh']): return 'Remote'
    if any(w in t for w in ['contract','consultant','temporary','freelance']): return 'Contract'
    return 'Full-Time'

def detect_sector(text):
    t = (text or '').lower()
    if any(w in t for w in ['software','developer','ict','data','cyber','tech','systems']): return 'ICT & Technology'
    if any(w in t for w in ['nurse','doctor','medical','health','clinical','pharmacy']): return 'Health & Medicine'
    if any(w in t for w in ['finance','account','audit','tax','banking']): return 'Finance & Banking'
    if any(w in t for w in ['engineer','civil','mechanical','electrical']): return 'Engineering'
    if any(w in t for w in ['teach','tutor','lecturer','school','education']): return 'Education'
    if any(w in t for w in ['farm','agri','crop','livestock','food']): return 'Agriculture'
    if any(w in t for w in ['market','sales','brand','advertis']): return 'Marketing & Sales'
    if any(w in t for w in ['ngo','humanitarian','relief','programme officer']): return 'NGO / Non-Profit'
    if any(w in t for w in ['legal','lawyer','advocate','compliance']): return 'Legal'
    if any(w in t for w in ['driver','transport','logistics','supply']): return 'Transport & Logistics'
    return 'General'

def extract_email(text):
    emails = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text or '')
    bad = ['noreply','no-reply','donotreply','example','sentry','test@']
    return next((e for e in emails if not any(b in e.lower() for b in bad)), '')

def strip_html(text):
    return re.sub(r'<[^>]+>', ' ', text or '').strip()

def deduplicate(jobs):
    seen, unique = set(), []
    for j in jobs:
        key = f"{j.get('title','').lower()[:40]}|{j.get('company','').lower()[:25]}"
        if key not in seen:
            seen.add(key)
            unique.append(j)
    return unique


# ════════════════════════════════════════════════════════════════
#  SOURCE 1: ReliefWeb API — best NGO/UN jobs, always works
# ════════════════════════════════════════════════════════════════
def scrape_reliefweb():
    print('  [ReliefWeb] Fetching NGO/UN jobs...')
    jobs = []
    try:
        url = 'https://api.reliefweb.int/v1/jobs?appname=jobskenya&filter[field]=country.name&filter[value]=Kenya&limit=50&fields[include][]=title&fields[include][]=body&fields[include][]=source&fields[include][]=date&fields[include][]=url&fields[include][]=career_categories&fields[include][]=type'
        res = requests.get(url, timeout=20)
        if not res.ok:
            print(f'  [ReliefWeb] HTTP {res.status_code}')
            return []
        data = res.json().get('data', [])
        for item in data:
            try:
                f       = item.get('fields', {})
                title   = clean(f.get('title', ''))
                if not title: continue
                company = f.get('source', [{}])[0].get('name', 'NGO') if f.get('source') else 'NGO'
                body    = clean(strip_html(f.get('body', '')))
                email   = extract_email(body)
                link    = f.get('url', '')
                date    = f.get('date', {}).get('created', datetime.now().isoformat())
                jobs.append({
                    'id':          f"rw-{item.get('id',len(jobs))}",
                    'title':       title,
                    'company':     company,
                    'location':    'Kenya',
                    'county':      extract_county(title + ' ' + body),
                    'type':        detect_type(title + ' ' + body),
                    'sector':      detect_sector(title),
                    'salary':      'Not stated',
                    'deadline':    '',
                    'link':        link,
                    'apply_email': email,
                    'description': body[:2000],
                    'source':      'ReliefWeb',
                    'scraped_at':  date,
                })
            except: continue
        print(f'  [ReliefWeb] ✅ {len(jobs)} jobs')
    except Exception as e:
        print(f'  [ReliefWeb] ❌ {e}')
    return jobs


# ════════════════════════════════════════════════════════════════
#  SOURCE 2: Remotive API — remote jobs open to Kenya
# ════════════════════════════════════════════════════════════════
def scrape_remotive():
    print('  [Remotive] Fetching remote jobs...')
    jobs = []
    try:
        res = requests.get('https://remotive.com/api/remote-jobs?limit=50', timeout=20)
        if not res.ok:
            print(f'  [Remotive] HTTP {res.status_code}')
            return []
        for j in res.json().get('jobs', []):
            try:
                title = clean(j.get('title', ''))
                if not title: continue
                desc  = clean(strip_html(j.get('description', '')))
                jobs.append({
                    'id':          f"remotive-{len(jobs)}",
                    'title':       title,
                    'company':     clean(j.get('company_name', '')),
                    'location':    'Remote / Online',
                    'county':      'Remote',
                    'type':        'Remote',
                    'sector':      detect_sector(title + ' ' + j.get('category', '')),
                    'salary':      j.get('salary', '') or 'Not stated',
                    'deadline':    '',
                    'link':        j.get('url', ''),
                    'apply_email': '',
                    'description': desc[:2000],
                    'source':      'Remotive (Remote)',
                    'scraped_at':  j.get('publication_date', datetime.now().isoformat()),
                })
            except: continue
        print(f'  [Remotive] ✅ {len(jobs)} jobs')
    except Exception as e:
        print(f'  [Remotive] ❌ {e}')
    return jobs


# ════════════════════════════════════════════════════════════════
#  SOURCE 3: RSS Feeds — parse XML from Kenyan job sites
# ════════════════════════════════════════════════════════════════
def parse_rss(name, url):
    print(f'  [RSS] Fetching {name}...')
    jobs = []
    try:
        import xml.etree.ElementTree as ET
        res = requests.get(url, timeout=20, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; JobsKenyaBot/1.0)'
        })
        if not res.ok:
            print(f'  [RSS] {name} HTTP {res.status_code}')
            return []

        root = ET.fromstring(res.content)
        ns   = {'atom': 'http://www.w3.org/2005/Atom'}

        # Try RSS format
        items = root.findall('.//item')
        # Try Atom format
        if not items:
            items = root.findall('.//atom:entry', ns) or root.findall('.//entry')

        for item in items[:40]:
            try:
                def get(tag, alt=''):
                    el = item.find(tag) or item.find(f'atom:{tag}', ns)
                    return clean(el.text or '') if el is not None else alt

                title = get('title')
                if not title or len(title) < 4: continue

                desc  = clean(strip_html(get('description') or get('summary') or get('content') or ''))
                link  = get('link') or (item.find('link') or item.find('atom:link', ns) or ET.Element('x')).get('href','')
                date  = get('pubDate') or get('published') or get('updated') or datetime.now().isoformat()
                email = extract_email(desc)

                # Split "Title at Company" or "Title - Company"
                company = name
                for sep in [' at ', ' - ', ' | ']:
                    if sep in title:
                        parts = title.split(sep, 1)
                        title = parts[0].strip()
                        company = parts[1].strip()
                        break

                jobs.append({
                    'id':          f"{name.lower()[:8]}-{len(jobs)}",
                    'title':       title,
                    'company':     company,
                    'location':    extract_county(title + ' ' + desc) + ', Kenya',
                    'county':      extract_county(title + ' ' + desc),
                    'type':        detect_type(title + ' ' + desc),
                    'sector':      detect_sector(title + ' ' + desc),
                    'salary':      'Not stated',
                    'deadline':    '',
                    'link':        link,
                    'apply_email': email,
                    'description': desc[:2000],
                    'source':      name,
                    'scraped_at':  datetime.now().isoformat(),
                })
            except: continue

        print(f'  [RSS] {name}: ✅ {len(jobs)} jobs')
    except Exception as e:
        print(f'  [RSS] {name}: ❌ {e}')
    return jobs


RSS_SOURCES = [
    ('NGO Jobs Kenya',     'https://www.ngojobskenya.com/feed/'),
    ('Career Point Kenya', 'https://www.careerpointkenya.co.ke/feed/'),
    ('Jobs in Kenya',      'https://www.jobsinkenya.co.ke/feed/'),
    ('UN Jobs Nairobi',    'https://unjobs.org/duty_stations/nairobi/rss'),
    ('BrighterMonday',     'https://www.brightermonday.co.ke/rss/jobs'),
]


# ════════════════════════════════════════════════════════════════
#  RUN ALL SOURCES
# ════════════════════════════════════════════════════════════════
def run_all():
    print('\n' + '='*55)
    print('  🇰🇪 JOBS KENYA — Scraping started')
    print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('='*55)

    all_jobs = []

    # ReliefWeb API
    try: all_jobs.extend(scrape_reliefweb())
    except Exception as e: print(f'  ❌ ReliefWeb: {e}')

    # Remotive API
    try: all_jobs.extend(scrape_remotive())
    except Exception as e: print(f'  ❌ Remotive: {e}')

    # RSS feeds
    for name, url in RSS_SOURCES:
        try: all_jobs.extend(parse_rss(name, url))
        except Exception as e: print(f'  ❌ RSS {name}: {e}')
        time.sleep(1)

    # Deduplicate and sort
    before   = len(all_jobs)
    all_jobs = deduplicate(all_jobs)
    all_jobs.sort(key=lambda j: j.get('scraped_at', ''), reverse=True)
    print(f'\n  🧹 {before} → {len(all_jobs)} unique jobs')

    output = {
        'total':      len(all_jobs),
        'scraped_at': datetime.now().isoformat(),
        'jobs':       all_jobs
    }
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'  ✅ {len(all_jobs)} jobs saved to {OUTPUT_FILE}')
    print('='*55 + '\n')
    return all_jobs


def start_scheduler():
    schedule.every(2).hours.do(run_all)
    while True:
        schedule.run_pending()
        time.sleep(60)


# ── API ROUTES ──────────────────────────────────────────────────
@app.route('/')
def home():
    return jsonify({'status': 'running', 'service': '🇰🇪 Jobs Kenya API'})

@app.route('/jobs')
def get_jobs():
    try:
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        jobs    = data.get('jobs', [])
        county  = request.args.get('county', '').lower()
        jtype   = request.args.get('type', '').lower()
        keyword = request.args.get('q', '').lower()
        limit   = min(int(request.args.get('limit', 80)), 200)

        if county:  jobs = [j for j in jobs if county  in j.get('county', '').lower()]
        if jtype:   jobs = [j for j in jobs if jtype   in j.get('type', '').lower()]
        if keyword: jobs = [j for j in jobs if keyword in (j.get('title','') + ' ' + j.get('company','')).lower()]

        return jsonify({'total': len(jobs), 'scraped_at': data.get('scraped_at'), 'jobs': jobs[:limit]})
    except FileNotFoundError:
        return jsonify({'total': 0, 'jobs': [], 'message': 'First scrape in progress...'})

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
    token = request.headers.get('X-Admin-Token', '')
    if token != ADMIN_SECRET:
        return jsonify({'error': 'Unauthorized'}), 401
    threading.Thread(target=run_all, daemon=True).start()
    return jsonify({'success': True, 'message': 'Scrape started — check /status in 3 minutes'})


# ── STARTUP ─────────────────────────────────────────────────────
_started = False
def startup():
    global _started
    if _started: return
    _started = True
    print('🇰🇪 Jobs Kenya — startup() called, launching scraper thread...')
    threading.Thread(target=run_all, daemon=True).start()
    threading.Thread(target=start_scheduler, daemon=True).start()

startup()  # Called at import time — works with gunicorn

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
