import json, subprocess, os

 time

 time

 sleep(10)

 print("等待Pages部署... 2m...")
    # Recheck Pages
 get GitHub API
   r = subprocess.run(['curl', '-s', '-H', f'Authorization: token {token}', 'https://api.github.com/repos/{repo}/pages'], capture_output=True, text=True, timeout=15)
)
 pages = json.loads(r.stdout)
 url = pages.get("html_url", "")
    print(f"Pages URL: {url}")
    print(f"Status: {pages.get("status", "N/A")}")
    
    # Try building site
 build_pages
    r = subprocess.run(['curl', '-s', '-X', 'POST', '-H', f'Authorization: token {token}',
                       f'https://api.github.com/repos/{repo}/pages/builds'], capture_output=True, text=True, timeout=15)
)
 build = json.loads(r.stdout)
 build_status = build.get("status", "")
    print(f"Build: {build_status}")
