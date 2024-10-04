from flask import Flask, request, render_template
import requests
from bs4 import BeautifulSoup
import sqlite3

app = Flask(__name__)

# Detect the job board provider
def detect_job_board_provider(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    if 'boards.greenhouse.io' in response.text or soup.find_all('iframe', src=lambda x: x and 'greenhouse' in x):
        return 'greenhouse'
    if 'jobs.lever.co' in response.text or soup.find_all('iframe', src=lambda x: x and 'lever' in x):
        return 'lever'
    if 'workday.com' in response.text or 'workday' in response.text:
        return 'workday'
    if 'notion.so' in response.text or 'Notion' in response.text:
        return 'notion'
    
    scripts = soup.find_all('script')
    for script in scripts:
        if 'greenhouse' in str(script):
            return 'greenhouse'
        if 'lever' in str(script):
            return 'lever'
        if 'workday' in str(script):
            return 'workday'
        if 'notion' in str(script):
            return 'notion'
    
    return 'unknown'

# Scraping logic for Greenhouse
def fetch_jobs_from_greenhouse(company_slug):
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs"
    response = requests.get(api_url)
    if response.status_code == 200:
        data = response.json()
        jobs = [{'title': job['title'], 'url': job['absolute_url']} for job in data['jobs']]
        return jobs
    else:
        return []

# Scraping logic for Lever
def fetch_jobs_from_lever(company_slug):
    api_url = f"https://api.lever.co/v0/postings/{company_slug}"
    response = requests.get(api_url)
    if response.status_code == 200:
        data = response.json()
        jobs = [{'title': job['text'], 'url': job['hostedUrl']} for job in data]
        return jobs
    else:
        return []

# Scraping logic for Notion
def fetch_jobs_from_notion(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    jobs = []
    
    # Notion job pages typically have specific div elements with text content
    job_elements = soup.find_all('div', class_='notion-block')
    
    for job in job_elements:
        title = job.text.strip()
        if title:
            jobs.append({'title': title, 'url': url})
    
    return jobs

# Store jobs in the database
def store_jobs_in_db(jobs):
    conn = sqlite3.connect('jobs.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        url TEXT UNIQUE
    )
    ''')
    for job in jobs:
        try:
            cursor.execute("INSERT INTO jobs (title, url) VALUES (?, ?)", (job['title'], job['url']))
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        url = request.form['url']
        provider = detect_job_board_provider(url)
        if provider == 'greenhouse':
            company_slug = "company_slug_here"  # Replace with dynamic slug detection
            jobs = fetch_jobs_from_greenhouse(company_slug)
        elif provider == 'lever':
            company_slug = "company_slug_here"  # Replace with dynamic slug detection
            jobs = fetch_jobs_from_lever(company_slug)
        elif provider == 'notion':
            jobs = fetch_jobs_from_notion(url)
        else:
            jobs = []
        
        store_jobs_in_db(jobs)
        return render_template('index.html', jobs=jobs, provider=provider)
    return render_template('index.html', jobs=None, provider=None)

if __name__ == "__main__":
    app.run(debug=True)