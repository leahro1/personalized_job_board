import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sqlite3
import schedule
import time
from bs4 import BeautifulSoup

# Email details
email_user = 'customjobfeed@gmail.com'
email_password = 'tehhif-Daxfir-3qivji'
recipient_email = 'leahro1@gmail.com'

# API key for email SMTP (using Gmail here, but you can modify as needed)
smtp_server = 'smtp.gmail.com'
smtp_port = 587

# Load companies from the 'companies.txt' file
def load_companies_from_file(file_path):
    with open(file_path, 'r') as file:
        companies = [line.strip() for line in file.readlines() if not line.startswith('#')]
    return companies

# Detect the job board provider
def detect_job_board_provider(url):
    response = requests.get(url)
    if 'boards.greenhouse.io' in response.text:
        return 'greenhouse'
    if 'jobs.lever.co' in response.text:
        return 'lever'
    if 'workday.com' in response.text:
        return 'workday'
    if 'notion.so' in response.text or 'Notion' in response.text:
        return 'notion'
    if 'boards.ashbyhq.com' in response.text:
        return 'ashbyhq'
    return 'unknown'

# Fetch jobs from Greenhouse
def fetch_jobs_from_greenhouse(company_slug):
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs"
    response = requests.get(api_url)
    if response.status_code == 200:
        data = response.json()
        return [{'title': job['title'], 'url': job['absolute_url']} for job in data['jobs']]
    else:
        return []

# Fetch jobs from Lever
def fetch_jobs_from_lever(company_slug):
    api_url = f"https://api.lever.co/v0/postings/{company_slug}"
    response = requests.get(api_url)
    if response.status_code == 200:
        data = response.json()
        return [{'title': job['text'], 'url': job['hostedUrl']} for job in data]
    else:
        return []

# Fetch jobs from Notion
def fetch_jobs_from_notion(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    jobs = []
    job_elements = soup.find_all('div', class_='notion-block')
    for job in job_elements:
        title = job.text.strip()
        if title:
            jobs.append({'title': title, 'url': url})
    return jobs
    
# Fetch jobs from Ash by HQ
def fetch_jobs_from_ashbyhq(company_slug):
    api_url = f"https://boards.ashbyhq.com/api/job-board/{company_slug}/jobs"
    response = requests.get(api_url)
    if response.status_code == 200:
        data = response.json()
        jobs = [{'title': job['title'], 'url': job['url']} for job in data['jobs']]
        return jobs
    else:
        return [] 

# Store jobs in SQLite database
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
            pass  # Ignore duplicate jobs
    conn.commit()
    conn.close()

# Check if a job already exists in the database
def job_exists_in_db(job_url):
    conn = sqlite3.connect('jobs.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE url=?", (job_url,))
    job = cursor.fetchone()
    conn.close()
    return job is not None

# Send email with new jobs
def send_email(subject, body):
    msg = MIMEMultipart()
    msg['From'] = email_user
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_user, email_password)
        server.sendmail(email_user, recipient_email, msg.as_string())
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {str(e)}")

# Dynamic slug detection from URL
def extract_company_slug(url):
    if 'greenhouse.io' in url:
        return url.split('/')[-1]  # Assume last part is the slug for Greenhouse
    if 'lever.co' in url:
        return url.split('/')[-1]  # Assume last part is the slug for Lever
    if 'ashbyhq.com' in url:
        return url.split('/')[-1]  # Assume last part is the slug for AshbyHQ
    return None

# Keywords/titles to search for
job_keywords = ['Product Marketing', 'Marketing', 'Growth', 'Strategy']  # Add more keywords here

# Filter jobs based on title keywords
def filter_jobs_by_keyword(jobs, keywords):
    return [job for job in jobs if any(keyword.lower() in job['title'].lower() for keyword in keywords)]

# Fetch jobs and email new ones
def job_search_and_notify():
    companies = load_companies_from_file('companies.txt')
    email_body = "Here are the latest job listings:\n\n"
    
    for company_url in companies:
        provider = detect_job_board_provider(company_url)
        company_slug = extract_company_slug(company_url)

        if provider == 'greenhouse':
            jobs = fetch_jobs_from_greenhouse(company_slug)
        elif provider == 'lever':
            jobs = fetch_jobs_from_lever(company_slug)
        elif provider == 'notion':
            jobs = fetch_jobs_from_notion(company_url)
        elif provider == 'ashbyhq':
            jobs = fetch_jobs_from_ashbyhq(company_slug)
        else:
            email_body += f"\nCould not detect job board provider for {company_url}.\n"
            continue

        # Filter jobs by keywords before processing
        filtered_jobs = filter_jobs_by_keyword(jobs, job_keywords)

        new_jobs = [job for job in filtered_jobs if not job_exists_in_db(job['url'])]
        if new_jobs:
            for job in new_jobs:
                email_body += f"{job['title']} - {job['url']}\n"
            store_jobs_in_db(new_jobs)

    if email_body.strip():
        send_email("Daily Job Listings", email_body)

# Schedule and run the job
schedule.every().day.at("08:00").do(job_search_and_notify)

# Keep the script running
while True:
    schedule.run_pending()
    time.sleep(60)