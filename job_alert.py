import os, json, time, re
import requests
from bs4 import BeautifulSoup

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
SEEN_FILE = "seen.json"

KEYWORDS = [
    "מנהל פרויקט בכיר",
    "מנהל תוכניות",
    "מנהל תוכנית",
    "ראש צוות ניהול פרויקטים",
    "ניהול מצוינות תפעולית",
    "Senior Project Manager",
    "Program Manager",
    "Operational Excellence Manager",
]

LOCATIONS = ["Kiryat Gat, Israel", "Rehovot, Israel", "Holon, Israel"]
DISTANCE_KM = 25

EXCLUDE = ["בניין", "נדל\"ן", "קבלן", "אתר בנייה", "construction", "real estate"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "he,en;q=0.8",
}


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, encoding="utf-8") as f:
            return json.load(f)
    return None


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=0)


def tg(text):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": "true"},
        timeout=30,
    )
    r.raise_for_status()


def linkedin(keyword, location):
    url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobs/search"
    params = {
        "keywords": keyword,
        "location": location,
        "distance": int(DISTANCE_KM * 0.62),
        "f_TPR": "r86400",
        "start": 0,
    }
    r = requests.get(url, params=params, headers=HEADERS, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"LinkedIn {r.status_code}")
    soup = BeautifulSoup(r.text, "html.parser")
    jobs = []
    for li in soup.find_all("li"):
        a = li.find("a", class_="base-card__full-link")
        t = li.find("h3", class_="base-search-card__title")
        if not a or not t:
            continue
        c = li.find("h4", class_="base-search-card__subtitle")
        loc = li.find("span", class_="job-search-card__location")
        clean = a["href"].split("?")[0]
        m = re.search(r"(\d{6,})", clean)
        jid = "li-" + (m.group(1) if m else clean)
        jobs.append({
            "id": jid,
            "title": t.get_text(strip=True),
            "company": c.get_text(strip=True) if c else "",
            "location": loc.get_text(strip=True) if loc else "",
            "url": clean,
        })
    return jobs


def main():
    seen = load_seen()
    first_run = seen is None
    seen = seen or {}
    found, errors = {}, []
    for kw in KEYWORDS:
        for loc in LOCATIONS:
            try:
                for j in linkedin(kw, loc):
                    found[j["id"]] = j
            except Exception as e:
                errors.append(str(e))
            time.sleep(2)

    new = [
        j for jid, j in found.items()
        if jid not in seen
        and not any(x.lower() in (j["title"] + j["company"]).lower() for x in EXCLUDE)
    ]

    for jid in found:
        seen[jid] = int(time.time())

    if first_run:
        tg(f"✅ ההתראות פעילות. נסרקו {len(found)} משרות קיימות. מעכשיו תקבל רק חדשות.")
    else:
        for j in new:
            tg(f"🆕 {j['title']}\n🏢 {j['company']}\n📍 {j['location']}\n🔗 {j['url']}")

    if errors and len(errors) >= len(KEYWORDS) * len(LOCATIONS):
        tg("⚠️ הסריקה נכשלה: " + errors[0])

    save_seen(seen)
    print(f"found={len(found)} new={len(new)} errors={len(errors)}")


if __name__ == "__main__":
    main()
