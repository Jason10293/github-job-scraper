import requests
import smtplib
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

class InternshipScraper:
    def __init__(self):
        # Configuration from environment variables
        self.github_token = os.getenv('GITHUB_TOKEN', '')
        self.email_sender = os.getenv('EMAIL_SENDER')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.email_receiver = os.getenv('EMAIL_RECEIVER')
        
        # Validate environment variables
        if not all([self.email_sender, self.email_password, self.email_receiver]):
            raise ValueError("Missing required environment variables")
        
        # Popular repos for Canadian internships
        self.repos_to_check = [
            'negarprh/Canadian-Tech-Internships-2026',
            'lucianlavric/CanadaTechInternships-Summer2026',
            'SimplifyJobs/Summer2026-Internships'
        ]
        
        self.cache_file = 'seen_postings.json'
        self.seen_postings = self.load_cache()
        
    def load_cache(self):
        """Load previously seen postings from cache file"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_cache(self):
        """Save seen postings to cache file"""
        with open(self.cache_file, 'w') as f:
            json.dump(self.seen_postings, f, indent=2)
    
    def get_github_commits(self, repo):
        """Fetch recent commits from a GitHub repository"""
        url = f'https://api.github.com/repos/{repo}/commits'
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
        
        # Get commits from last 24 hours
        since = (datetime.now() - timedelta(days=1)).isoformat()
        params = {'since': since, 'per_page': 10}
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
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
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching README from {repo}: {e}")
            return ""
    
    def parse_internships(self, content, repo_name):
        """Parse internship postings from README content"""
        new_postings = []
        lines = content.split('\n')
        
        for line in lines:
            # Look for lines containing Canada and common job indicators
            if ('canada' in line.lower() or '🇨🇦' in line) and ('http' in line or '[' in line):
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
            else:
                print(f"No recent commits in {repo}")
        
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
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    border-radius: 10px;
                    margin-bottom: 30px;
                }}
                .posting {{ 
                    margin: 20px 0; 
                    padding: 15px; 
                    border-left: 4px solid #667eea;
                    background-color: #f8f9fa;
                    border-radius: 5px;
                    transition: transform 0.2s;
                }}
                .repo {{ 
                    color: #6c757d; 
                    font-size: 13px; 
                    margin-bottom: 8px;
                    font-weight: 600;
                }}
                .content {{
                    color: #212529;
                    font-size: 14px;
                }}
                h1 {{ 
                    margin: 0;
                    font-size: 28px;
                }}
                .count {{
                    background: rgba(255,255,255,0.2);
                    padding: 5px 15px;
                    border-radius: 20px;
                    display: inline-block;
                    margin-top: 10px;
                }}
                .footer {{
                    margin-top: 40px;
                    padding: 20px;
                    background: #f8f9fa;
                    border-radius: 10px;
                    text-align: center;
                    color: #6c757d;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🇨🇦 New Internship Opportunities</h1>
                <div class="count">{len(postings)} new posting(s) found</div>
            </div>
        """
        
        for posting in postings:
            html_content += f"""
            <div class="posting">
                <div class="repo">📁 {posting['repo']}</div>
                <div class="content">{posting['content']}</div>
            </div>
            """
        
        html_content += """
            <div class="footer">
                <p>🚀 Good luck with your applications!</p>
                <p style="font-size: 12px; margin-top: 10px;">
                    This is an automated notification from your internship scraper.
                </p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(html_content, 'html'))
        
        # Send email
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(self.email_sender, self.email_password)
                server.send_message(msg)
            print(f"✅ Email sent successfully with {len(postings)} postings")
        except Exception as e:
            print(f"❌ Error sending email: {e}")
            raise
    
    def run(self):
        """Main execution - runs once"""
        print(f"\n{'='*60}")
        print(f"🔍 Running internship scraper at {datetime.now()}")
        print(f"{'='*60}\n")
        
        new_postings = self.scrape_all_repos()
        
        print(f"\n{'='*60}")
        if new_postings:
            print(f"✨ Found {len(new_postings)} new postings!")
            print(f"{'='*60}\n")
            self.send_email(new_postings)
        else:
            print(f"📭 No new postings found today")
            print(f"{'='*60}\n")
        
        return len(new_postings)

def main():
    try:
        scraper = InternshipScraper()
        count = scraper.run()
        print(f"\n✅ Scraper completed successfully. Found {count} new postings.\n")
    except Exception as e:
        print(f"\n❌ Error running scraper: {e}\n")
        raise

if __name__ == "__main__":
    main()