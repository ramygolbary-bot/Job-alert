import os, json, time, re
from urllib.parse import quote, urljoin
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

SITE_KEYWORDS = [
    "מנהל פרויקט בכיר",
    "מנהל תוכניות",
    "ראש צוות ניהול פרויקטים",
    "מצוינות תפעולית",
    "PMO",
    "מנהל תפעול",
    "NPI",
    "Program Manager",
]

SOURCES = [
    {
        "name": "Drushim",
        "url": "https://www.drushim.co.il/jobs/search/{kw}/",
        "re": r"/job/(\d+)/",
    },
    {
        "name": "AllJobs",
        "url": "https://www.alljobs.co.il/SearchResultsGuest.aspx?page=1&position=&type=&freetxt={kw}&city=&region=",
        "re": r"JobID=(\d+)",
    },
    {
        "name": "JobMaster",
        "url": "https://www.jobmaster.co.il/jobs/?q={kw}",
        "re": r"checknum\.asp\?key=(\d+)",
    },
    {
        "name": "JobNet",
        "url": "https://www.jobnet.co.il/jobs?q={kw}",
        "re": r"positionid=(\d+)",
    },
]

TITLE_WORDS = [
    "מנהל פרויקט", "מנהלת פרויקט", "מנהל פרוייקט", "מנהל תוכני", "מנהלת תוכני",
    "ראש צוות", "מצוינות", "pmo", "project manager",
    "program manager", "operations", "תפעול", "npi",
    "operational excellence",
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
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": "true"},
            timeout=30,
        )
        r.raise_for_status()
        time.sleep(0.5)
        return True
    except Exception as e:
        print("telegram failed:", e)
        return False


def norm(text):
    return text.lower().replace("'", "").replace("’", "")


def blocked_location(job):
    loc = norm(job["location"])
    return not any(x in loc for x in ALLOWED_LOCATIONS)


def excluded(job):
    text = (job["title"] + " " + job["company"]).lower()
    return any(x.lower() in text for x in EXCLUDE)


def send_job(j, source):
    company = f"\n🏢 {j['company']}" if j["company"] else ""
    tg(f"🆕 {j['title']}{company}\n📍 {j['location']}\n🔎 {source}\n🔗 {j['url']}")


# ---------------- LinkedIn ----------------

def parse_linkedin(html):
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
            return parse_linkedin(r.text)
    raise RuntimeError("LinkedIn status " + "/".join(statuses))


# ---------------- Israeli job sites ----------------

def scan_source(src):
    link_re = re.compile(src["re"])
    name = src["name"]

    def ids_in(el):
        ids = set()
        for a in el.find_all("a", href=True):
            m = link_re.search(a["href"])
            if m:
                ids.add(m.group(1))
        return ids

    jobs, errors = {}, []
    for kw in SITE_KEYWORDS:
        url = src["url"].format(kw=quote(kw))
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code != 200:
                raise RuntimeError(f"{name} status {r.status_code}")
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                m = link_re.search(a["href"])
                if not m:
                    continue
                jid = f"{name}-{m.group(1)}"
                if jid in jobs:
                    continue
                card = a
                for _ in range(12):
                    parent = card.parent
                    if parent is None or len(ids_in(parent)) != 1:
                        break
                    card = parent
                text = card.get_text(" ", strip=True)
                h = card.find(["h1", "h2", "h3", "h4"])
                title = h.get_text(" ", strip=True) if h else ""
                if not title:
                    texts = [
                        x.get_text(" ", strip=True)
                        for x in card.find_all("a", href=True)
                        if link_re.search(x["href"])
                    ]
                    texts = [x for x in texts if x and "הגשת" not in x]
                    title = max(texts, key=len) if texts else ""
                if not title:
                    continue
                if not any(w in title.lower() for w in TITLE_WORDS):
                    continue
                city = next((c for c in ALLOWED_LOCATIONS if c in norm(text)), None)
                if not city:
                    continue
                jobs[jid] = {
                    "id": jid,
                    "title": title,
                    "company": "",
                    "location": city,
                    "url": urljoin(url, a["href"]),
                }
        except Exception as e:
            errors.append(str(e))
        time.sleep(2)
    return jobs, errors


def main():
    seen = load_seen()
    first_run = len(seen) == 0
    now = int(time.time())

    # ---- LinkedIn ----
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
        if now - seen.get("_last_err", 0) > 6 * 3600:
            tg("⚠️ LinkedIn נכשל בכל הבקשות. " + errors[0])
            seen["_last_err"] = now
        print("linkedin all failed:", errors[0])
    else:
        new = [
            j for jid, j in found.items()
            if jid not in seen and not blocked_location(j) and not excluded(j)
        ]
        for jid in found:
            seen[jid] = now
        if first_run:
            tg(f"✅ LinkedIn פעיל. נסרקו {len(found)} משרות קיימות. מעכשיו תקבל רק חדשות.")
        else:
            for j in new:
                send_job(j, "LinkedIn")
        print(f"linkedin found={len(found)} new={len(new)} errors={len(errors)}")

    # ---- Israeli sites ----
    for src in SOURCES:
        name = src["name"]
        jobs, errs = scan_source(src)
        init_key = "_init_" + name
        err_key = "_err_" + name
        if not jobs:
            if now - seen.get(err_key, 0) > 6 * 3600:
                reason = errs[0] if errs else "לא נמצאו משרות באזור"
                tg(f"⚠️ {name}: {reason}")
                seen[err_key] = now
            print(name, "empty", errs[:1])
            continue
        new = [j for jid, j in jobs.items() if jid not in seen and not excluded(j)]
        for jid in jobs:
            seen[jid] = now
        if init_key not in seen:
            seen[init_key] = now
            tg(f"✅ {name} פעיל. נסרקו {len(jobs)} משרות באזור. מעכשיו תקבל רק חדשות.")
        else:
            for j in new:
                send_job(j, name)
        print(f"{name} found={len(jobs)} new={len(new)} errors={len(errs)}")

    save_seen(seen)


if __name__ == "__main__":
    main()
