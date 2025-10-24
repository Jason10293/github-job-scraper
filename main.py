import requests
import smtplib
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import schedule
import time

class InternshipScraper:
    def __init__(self):
        # Configuration - Set these as environment variables or update directly
        self.github_token = os.getenv('GITHUB_TOKEN', '')  # Optional but recommended
        self.email_sender = os.getenv('EMAIL_SENDER', 'your_email@gmail.com')
        self.email_password = os.getenv('EMAIL_PASSWORD', 'your_app_password')
        self.email_receiver = os.getenv('EMAIL_RECEIVER', 'your_email@gmail.com')
        
        # Popular repos that aggregate internship postings
        self.repos_to_check = [
            'jenndryden/Canadian-Tech-Internships-Summer-2025',
            'SimplifyJobs/Summer2025-Internships',
            'pittcsc/Summer2025-Internships',
            'ReaVNaiL/New-Grad-2025'
        ]
        
        self.cache_file = 'seen_postings.json'
        self.seen_postings = self.load_cache()
        
    def load_cache(self):
        """Load previously seen postings from cache file"""
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_cache(self):
        """Save seen postings to cache file"""
        with open(self.cache_file, 'w') as f:
            json.dump(self.seen_postings, f)
    
    def get_github_commits(self, repo):
        """Fetch recent commits from a GitHub repository"""
        url = f'https://api.github.com/repos/{repo}/commits'
        headers = {}
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
        
        # Get commits from last 24 hours
        since = (datetime.now() - timedelta(days=1)).isoformat()
        params = {'since': since, 'per_page': 10}
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching commits from {repo}: {e}")
            return []
    
    def get_readme_content(self, repo):
        """Fetch README content from a GitHub repository"""
        url = f'https://api.github.com/repos/{repo}/readme'
        headers = {'Accept': 'application/vnd.github.v3.raw'}
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching README from {repo}: {e}")
            return ""
    
    def parse_internships(self, content, repo_name):
        """Parse internship postings from README content"""
        new_postings = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            # Look for lines containing Canada and common job indicators
            if 'canada' in line.lower() or '🇨🇦' in line:
                # Check if this line contains links (typical in job tables)
                if 'http' in line or '[' in line:
                    # Create a unique ID for this posting
                    posting_id = f"{repo_name}_{hash(line)}"
                    
                    # Check if we've seen this posting before
                    if posting_id not in self.seen_postings:
                        new_postings.append({
                            'repo': repo_name,
                            'content': line.strip(),
                            'id': posting_id,
                            'date': datetime.now().isoformat()
                        })
                        self.seen_postings[posting_id] = datetime.now().isoformat()
        
        return new_postings
    
    def scrape_all_repos(self):
        """Scrape all configured repositories for new postings"""
        all_new_postings = []
        
        for repo in self.repos_to_check:
            print(f"Checking {repo}...")
            
            # Check for recent commits
            commits = self.get_github_commits(repo)
            if commits:
                print(f"Found {len(commits)} recent commits in {repo}")
                
                # Get current README content
                content = self.get_readme_content(repo)
                if content:
                    new_postings = self.parse_internships(content, repo)
                    all_new_postings.extend(new_postings)
                    print(f"Found {len(new_postings)} new Canadian postings")
        
        self.save_cache()
        return all_new_postings
    
    def send_email(self, postings):
        """Send email with new job postings"""
        if not postings:
            print("No new postings to send")
            return
        
        # Create email
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'🇨🇦 {len(postings)} New Canadian SWE Internship Postings - {datetime.now().strftime("%B %d, %Y")}'
        msg['From'] = self.email_sender
        msg['To'] = self.email_receiver
        
        # Create email body
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .posting {{ 
                    margin: 15px 0; 
                    padding: 10px; 
                    border-left: 3px solid #4CAF50;
                    background-color: #f9f9f9;
                }}
                .repo {{ color: #666; font-size: 12px; }}
                h2 {{ color: #333; }}
            </style>
        </head>
        <body>
            <h2>New Canadian Software Engineering Internship Postings</h2>
            <p>Found {len(postings)} new posting(s) in the last 24 hours:</p>
        """
        
        for posting in postings:
            html_content += f"""
            <div class="posting">
                <div class="repo">From: {posting['repo']}</div>
                <div>{posting['content']}</div>
            </div>
            """
        
        html_content += """
            <p>Good luck with your applications! 🚀</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(html_content, 'html'))
        
        # Send email
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(self.email_sender, self.email_password)
                server.send_message(msg)
            print(f"Email sent successfully with {len(postings)} postings")
        except Exception as e:
            print(f"Error sending email: {e}")
    
    def daily_job(self):
        """Main job that runs daily"""
        print(f"\n{'='*50}")
        print(f"Running daily scrape at {datetime.now()}")
        print(f"{'='*50}")
        
        new_postings = self.scrape_all_repos()
        
        if new_postings:
            self.send_email(new_postings)
        else:
            print("No new postings found today")

def main():
    scraper = InternshipScraper()
    
    # Schedule the job to run every day at 9 AM
    schedule.every().day.at("09:00").do(scraper.daily_job)
    
    # Run once immediately on startup (optional - comment out if not desired)
    print("Running initial scrape...")
    scraper.daily_job()
    
    print("\nScheduler started. Will check for new postings daily at 9:00 AM")
    print("Press Ctrl+C to stop\n")
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()