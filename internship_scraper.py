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
            'negarprh/Canadian-Tech-Internships-2026?tab=readme-ov-file',
            'lucianlavric/CanadaTechInternships-Summer2026',
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
    
    def extract_job_info(self, line):
        """Extract company, role, and date from markdown table line"""
        # Remove markdown table separators
        parts = [p.strip() for p in line.split('|') if p.strip()]
        
        info = {
            'company': 'Unknown',
            'role': 'Unknown',
            'date_posted': 'Unknown',
            'link': ''
        }
        
        # Try to extract company name (usually has a link)
        for part in parts:
            if '[' in part and ']' in part and 'http' in part:
                # Extract text between [ and ]
                company_match = part.split('[')[1].split(']')[0] if '[' in part else ''
                if company_match and not any(x in company_match.lower() for x in ['apply', 'link', 'posting']):
                    info['company'] = company_match
                    break
        
        # Try to extract role (look for common role keywords)
        for part in parts:
            if any(keyword in part.lower() for keyword in ['intern', 'engineer', 'developer', 'software', 'swe', 'co-op']):
                info['role'] = part.replace('[', '').replace(']', '').split('(')[0].strip()
                break
        
        # Try to extract date (look for date formats)
        for part in parts:
            if any(month in part for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']) or '/' in part or '-' in part:
                info['date_posted'] = part.strip()
                break
        
        # Extract first link found
        if 'http' in line:
            link_start = line.find('http')
            link_end = line.find(')', link_start)
            if link_end == -1:
                link_end = line.find(' ', link_start)
            if link_end == -1:
                link_end = len(line)
            info['link'] = line[link_start:link_end].strip()
        
        return info
    
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
                    job_info = self.extract_job_info(line)
                    new_postings.append({
                        'repo': repo_name,
                        'company': job_info['company'],
                        'role': job_info['role'],
                        'date_posted': job_info['date_posted'],
                        'link': job_info['link'],
                        'raw_content': line.strip(),
                        'id': posting_id,
                        'found_date': datetime.now().strftime('%Y-%m-%d')
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
        msg['Subject'] = f'🇨🇦 {len(postings)} New Canadian SWE Internships - {datetime.now().strftime("%b %d, %Y")}'
        msg['From'] = self.email_sender
        msg['To'] = self.email_receiver
        
        # Create simple HTML email body
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
            <h2>🇨🇦 {len(postings)} New Canadian Internship Posting(s)</h2>
            <p>Found on {datetime.now().strftime("%B %d, %Y")}</p>
            <hr>
        """
        
        for i, posting in enumerate(postings, 1):
            html_content += f"""
            <div style="margin: 20px 0; padding: 15px; background-color: #f5f5f5; border-radius: 5px;">
                <p style="margin: 5px 0;"><strong>#{i}</strong></p>
                <p style="margin: 5px 0;"><strong>Company:</strong> {posting['company']}</p>
                <p style="margin: 5px 0;"><strong>Role:</strong> {posting['role']}</p>
                <p style="margin: 5px 0;"><strong>Posted:</strong> {posting['date_posted']}</p>
                <p style="margin: 5px 0;"><strong>Apply:</strong> <a href="{posting['link']}">{posting['link'][:60]}...</a></p>
                <p style="margin: 5px 0; font-size: 12px; color: #666;">Source: {posting['repo']}</p>
            </div>
            """
        
        html_content += """
            <hr>
            <p style="color: #666; font-size: 12px;">Good luck with your applications!</p>
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
        
        try:
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
        except Exception as e:
            print(f"❌ Error during scraping: {e}")
            import traceback
            traceback.print_exc()
            # Don't raise - allow the run to complete
            return 0

def main():
    print("Starting internship scraper...")
    print(f"Python version: {__import__('sys').version}")
    
    # Check environment variables
    required_vars = ['EMAIL_SENDER', 'EMAIL_PASSWORD', 'EMAIL_RECEIVER']
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        print(f"❌ Missing required environment variables: {', '.join(missing)}")
        print("Please set these in GitHub Secrets")
        return
    
    print("✅ All required environment variables are set")
    
    try:
        scraper = InternshipScraper()
        count = scraper.run()
        print(f"\n✅ Scraper completed successfully. Found {count} new postings.\n")
    except Exception as e:
        print(f"\n❌ Fatal error running scraper: {e}\n")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
