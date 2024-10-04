import requests
from bs4 import BeautifulSoup
import sqlite3
import smtplib
from email.mime.text import MIMEText
import time
import schedule

# API Key for sending email (replace with your credentials)
email_user = 'customjobfeed@gmail.com'
email_password = 'tehhif-Daxfir-3qivji'
recipient_email = 'leahro1@gmail.com'

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
    
    return 'unknown'

# Scrape logic for Greenhouse
def fetch_jobs_from_greenhouse(company_slug):
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs"
    response = requests.get(api_url)
    if response.status_code == 200:
        data = response.json()
        jobs = [{'title': job['title'], 'url': job['absolute_url']} for job in data['jobs']]
        return jobs
    else:
        return []

# Scrape logic for Lever
def fetch_jobs_from_lever(company_slug):
    api_url = f"https://api.lever.co/v0/postings/{company_slug}"
    response = requests.get(api_url)
    if response.status_code == 200:
        data = response.json()
        jobs = [{'title': job['text'], 'url': job['hostedUrl']} for job in data]
        return jobs
    else:
        return []

# Scrape logic for Notion
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

# Send email with job listings
def send_email(subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = email_user
    msg['To'] = recipient_email

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(email_user, email_password)
        server.sendmail(email_user, recipient_email, msg.as_string())
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {str(e)}")

# Main function to scrape and send new jobs
def scrape_and_notify():
    companies = ['company1_url', 'company2_url']  # List of URLs to scrape
    email_body = ""
    flagged_companies = []

    for url in companies:
        provider = detect_job_board_provider(url)
        if provider == 'unknown':
            flagged_companies.append(url)  # Flag the company for troubleshooting
            continue
        
        if provider == 'greenhouse':
            company_slug = "company_slug_here"  # Replace with dynamic slug
            jobs = fetch_jobs_from_greenhouse(company_slug)
        elif provider == 'lever':
            company_slug = "company_slug_here"  # Replace with dynamic slug
            jobs = fetch_jobs_from_lever(company_slug)
        elif provider == 'notion':
            jobs = fetch_jobs_from_notion(url)
        else:
            jobs = []

        store_jobs_in_db(jobs)
        
        if jobs:
            job_list = "\n".join([f"{job['title']}: {job['url']}" for job in jobs])
            email_body += f"\nJobs from {url}:\n{job_list}\n"

    # Include flagged companies in the email body
    if flagged_companies:
        flagged_list = "\n".join(flagged_companies)
        email_body += f"\nThe following companies could not be detected:\n{flagged_list}\n"

    if email_body:
        send_email("Daily Job Listings", email_body)

# Schedule the job to run daily
schedule.every().day.at("08:00").do(scrape_and_notify)

while True:
    schedule.run_pending()
    time.sleep(60)