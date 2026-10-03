import urllib.request
import json
import re
import os

CREDLY_USER = os.environ.get("CREDLY_USER", "siva-subramanian.a44c518c")
README_PATH = os.environ.get("README_PATH", "README.md")

url = f"https://www.credly.com/users/{CREDLY_USER}/badges.json"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

try:
    with urllib.request.urlopen(req) as res:
        data = json.loads(res.read().decode("utf-8"))
except Exception as e:
    print(f"Error fetching Credly data: {e}")
    exit(1)

badges = sorted(data.get("data", []), key=lambda b: b.get("issued_at_date") or "", reverse=True)

if not badges:
    print("No badges found.")
    exit(0)

html_items = []
for b in badges:
    title = b["badge_template"]["name"].replace('"', "&quot;")
    img = b["badge_template"]["image_url"]
    badge_url = f"https://www.credly.com/badges/{b['id']}"
    html_items.append(
        f'<a href="{badge_url}" target="_blank" rel="noopener noreferrer" title="{title}">\n'
        f'  <img src="{img}" width="85" height="85" alt="{title}" />\n'
        f'</a>'
    )

new_badges_section = (
    "<!--START_SECTION:badges-->\n"
    '<p align="center">\n'
    + "\n".join(html_items)
    + "\n</p>\n"
    "<!--END_SECTION:badges-->"
)

if not os.path.exists(README_PATH):
    print(f"README file not found at {README_PATH}")
    exit(1)

with open(README_PATH, "r", encoding="utf-8") as f:
    readme_content = f.read()

updated_readme = re.sub(
    r"<!--START_SECTION:badges-->.*?<!--END_SECTION:badges-->",
    new_badges_section,
    readme_content,
    flags=re.DOTALL,
)

with open(README_PATH, "w", encoding="utf-8") as f:
    f.write(updated_readme)

print(f"Successfully updated {len(badges)} Credly badges in {README_PATH} as 85x85 thumbnails!")
