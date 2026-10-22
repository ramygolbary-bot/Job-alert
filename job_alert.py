import os, json, time, re
import requests
from bs4 import BeautifulSoup

TOKEN = os.environ["TELEGRAM_TOKEN"].strip()
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"].strip()
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
    "PMO",
    "Head of PMO",
    "Operations Manager",
    "NPI Manager",
]

LOCATIONS = [
    "Kiryat Gat, Israel", "Ashdod, Israel", "Yavne, Israel",
    "Gedera, Israel", "Rehovot, Israel", "Ness Ziona, Israel",
    "Rishon LeZion, Israel", "Lod, Israel", "Ramla, Israel",
    "Modiin, Israel", "Shoham, Israel", "Bat Yam, Israel",
    "Holon, Israel", "Beit Shemesh, Israel",
]

ALLOWED_LOCATIONS = [
    "kiryat gat", "קריית גת", "קרית גת",
    "ashdod", "אשדוד",
    "yavne", "יבנה", "gan yavne", "גן יבנה",
    "gedera", "גדרה",
    "rehovot", "רחובות",
    "ness ziona", "נס ציונה",
    "rishon", "ראשון",
    "lod", "לוד",
    "ramla", "רמלה",
    "modiin", "מודיעין",
    "shoham", "שוהם",
    "bat yam", "בת ים",
    "holon", "חולון",
    "beer yaakov", "באר יעקב",
    "mazkeret batya", "מזכרת בתיה",
    "kiryat malakhi", "kiryat malachi", "קריית מלאכי",
    "beit shemesh", "בית שמש",
    "ekron", "עקרון",
    "kfar chabad", "כפר חב\"ד",
    "tzrifin", "צריפין",
    "beer tuvia", "באר טוביה",
    "shfela", "שפלה",
]

EXCLUDE = [
    "בניין", "נדל\"ן", "קבלן", "אתר בנייה",
    "construction", "real estate",
    "קניין", "קונה", "buyer",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,he;q=0.8",
}

URLS = [
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobs/search",
    "https://www.linkedin.com/jobs/search",
]


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


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


def parse(html):
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    for card in soup.find_all(["li", "div"]):
        a = card.find("a", class_="base-card__full-link")
        t = card.find("h3", class_="base-search-card__title")
        if not a or not t:
            continue
        c = card.find("h4", class_="base-search-card__subtitle")
        loc = card.find("span", class_="job-search-card__location")
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


def linkedin(keyword, location):
    params = {"keywords": keyword, "location": location, "f_TPR": "r86400", "start": 0}
    statuses = []
    for url in URLS:
        r = requests.get(url, params=params, headers=HEADERS, timeout=30)
        statuses.append(f"{r.status_code}")
        if r.status_code == 200:
            return parse(r.text)
    raise RuntimeError("LinkedIn status " + "/".join(statuses))


def blocked_location(job):
    loc = job["location"].lower().replace("'", "").replace("’", "")
    return not any(x in loc for x in ALLOWED_LOCATIONS)


def main():
    seen = load_seen()
    first_run = len(seen) == 0
    found, errors = {}, []
    for kw in KEYWORDS:
        for loc in LOCATIONS:
            try:
                for j in linkedin(kw, loc):
                    found[j["id"]] = j
            except Exception as e:
                errors.append(str(e))
            time.sleep(2)

    total = len(KEYWORDS) * len(LOCATIONS)
    if errors and len(errors) >= total and not found:
        if time.time() - seen.get("_last_err", 0) > 6 * 3600:
            tg("⚠️ הסריקה נכשלה בכל הבקשות. " + errors[0])
            seen["_last_err"] = int(time.time())
            save_seen(seen)
        print("all failed:", errors[0])
        return

    new = [
        j for jid, j in found.items()
        if jid not in seen
        and not blocked_location(j)
        and not any(x.lower() in (j["title"] + j["company"]).lower() for x in EXCLUDE)
    ]

    for jid in found:
        seen[jid] = int(time.time())

    if first_run:
        tg(f"✅ ההתראות פעילות. נסרקו {len(found)} משרות קיימות. מעכשיו תקבל רק חדשות.")
    else:
        for j in new:
            tg(f"🆕 {j['title']}\n🏢 {j['company']}\n📍 {j['location']}\n🔗 {j['url']}")

    save_seen(seen)
    print(f"found={len(found)} new={len(new)} errors={len(errors)}")


if __name__ == "__main__":
    main()
