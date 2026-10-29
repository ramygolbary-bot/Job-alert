import os, re, json, time
import requests
from bs4 import BeautifulSoup

TOKEN = os.environ["TELEGRAM_TOKEN"].strip()
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"].strip()
SEEN_FILE = "seen.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept-Language": "he-IL,he;q=0.9,en;q=0.8"}

KEYWORDS = ["מנהל פרויקט בכיר", "מנהל תוכניות", "מנהל תוכנית", "ראש צוות ניהול פרויקטים", "ניהול מצוינות תפעולית", "Senior Project Manager", "Program Manager", "Operational Excellence Manager", "PMO", "Head of PMO", "Operations Manager", "NPI Manager"]
SITE_KEYWORDS = ["מנהל פרויקט בכיר", "מנהל תוכניות", "ראש צוות ניהול פרויקטים", "מצוינות תפעולית", "PMO", "מנהל תפעול", "NPI", "Program Manager"]

SOURCES = [
    {"name": "Drushim", "url": "https://www.drushim.co.il/jobs/search/{kw}/", "id": r"/job/(\d+)/"},
    {"name": "AllJobs", "url": "https://www.alljobs.co.il/SearchResultsGuest.aspx?page=1&position=&type=&freeText={kw}&city=&region=", "id": r"JobID=(\d+)"},
    {"name": "JobMaster", "url": "https://www.jobmaster.co.il/jobs/?q={kw}", "id": r"checknum\.asp\?key=(\d+)"},
    {"name": "JobNet", "url": "https://www.jobnet.co.il/jobs?q={kw}", "id": r"positionid=(\d+)"},
    {"name": "Applied Materials", "anchor": True, "id": r"/job/rehovot/[^/]+/95/(\d+)",
     "urls": ["https://jobs.appliedmaterials.com/employment/rehovot-project-program-management-jobs/95/8338064/294640-294904-293725/4",
              "https://jobs.appliedmaterials.com/search-jobs/Rehovot"]},
    {"name": "Stratasys", "anchor": True, "id": r"/job/[^/]*(?:Rehovot|Kiryat)[^/]*/(\d+)",
     "urls": ["https://careers.stratasys.com/go/Manufacturing-&-Operations/8909100/",
              "https://careers.stratasys.com/go/Manufacturing-&-Operations/8909100/25/",
              "https://careers.stratasys.com/go/Corporate-Functions/8909200/",
              "https://careers.stratasys.com/search/?q=manager&locationsearch=Israel"]},
]

LOCATIONS = [c + ", Israel" for c in ["Kiryat Gat", "Ashdod", "Yavne", "Gedera", "Rehovot", "Ness Ziona", "Rishon LeZion", "Lod", "Ramla", "Modiin", "Shoham", "Bat Yam", "Holon", "Beit Shemesh"]]

ALLOWED_LOCATIONS = [x.lower() for x in [
    "Kiryat Gat", "Ashdod", "Yavne", "Gedera", "Rehovot", "Ness Ziona", "Rishon", "Lod", "Ramla", "Modiin", "Modi'in", "Shoham", "Bat Yam", "Holon", "Beit Shemesh",
    "Gan Yavne", "Beer Yaakov", "Be'er Ya'akov", "Mazkeret Batya", "Kiryat Malachi", "Ekron", "Kfar Chabad", "Tzrifin", "Beer Tuvia", "Shfela", "Lachish",
    "קריית גת", "קרית גת", "אשדוד", "יבנה", "גדרה", "רחובות", "נס ציונה", "ראשון", "לוד", "רמלה", "מודיעין", "שוהם", "בת ים", "חולון", "בית שמש",
    "גן יבנה", "באר יעקב", "מזכרת בתיה", "קריית מלאכי", "קרית מלאכי", "עקרון", "כפר חב", "צריפין", "באר טוביה", "שפלה", "לכיש"]]

# --- סינון לפי שם התפקיד ---
TITLE_YES = re.compile(r"project manager|program manager|programme manager|project lead|program lead|\bpmo\b|head of project|head of program|operations manager|operational excellence|\bnpi\b|new product intro|head of operations|director of operations|project management|program management|מנהל(ת)? (פרו?י?יקט|תוכני|תפעול|מצוינות)|ראש צוות (ניהול )?פרו?י?יקט|ניהול פרו?י?יקט|ניהול תוכני|מצוינות תפעולית|ניהול תפעול|מנהל/ת (פרו?י?יקט|תוכני|תפעול)", re.I)
TITLE_NO = re.compile(r"engineer|developer|mechanic|technician|devops|\bdj\b|sales|account manager|buyer|procurement|purchas|maintenance|recruit|מהנדס|טכנאי|מפתח|אחזקה|תחזוקה|קניין|קונה|רכש|מכירות|גיוס", re.I)

EXCLUDE = ["בניין", "נדל\"ן", "קבלן", "אתר בנייה", "construction", "real estate", "קניין", "קונה", "buyer"]

def title_ok(t):
    return bool(TITLE_YES.search(t)) and not TITLE_NO.search(t)

def load_seen():
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False)

def tg(text):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": "true"}, timeout=20)
    except Exception as e:
        print("telegram error", e)
    time.sleep(0.5)

def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()

def allowed_location(loc):
    loc = (loc or "").lower()
    return any(x in loc for x in ALLOWED_LOCATIONS)

def excluded(text):
    t = (text or "").lower()
    return any(x.lower() in t for x in EXCLUDE)

def send_job(j):
    lines = ["🆕 " + j["title"]]
    if j.get("company"):
        lines.append("🏢 " + j["company"])
    if j.get("location"):
        lines.append("📍 " + j["location"])
    lines.append("🔎 " + j["source"])
    lines.append("🔗 " + j["url"])
    tg("\n".join(lines))

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
        jobs.append({"id": jid, "title": t.get_text(strip=True), "company": c.get_text(strip=True) if c else "",
                     "location": loc.get_text(strip=True) if loc else "", "url": clean, "source": "LinkedIn"})
    return jobs

def linkedin(keyword, location):
    params = {"keywords": keyword, "location": location, "f_TPR": "r86400", "start": 0}
    codes = []
    for url in ["https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobs/search", "https://www.linkedin.com/jobs/search"]:
        try:
            r = requests.get(url, params=params, headers=UA, timeout=25)
            if r.status_code == 200:
                return parse_linkedin(r.text)
            codes.append(r.status_code)
        except Exception as e:
            codes.append(str(e)[:40])
    raise RuntimeError("linkedin failed: " + ",".join(map(str, codes)))

def scan_source(src):
    jobs, errors = {}, []
    urls = src.get("urls") or [src["url"].format(kw=requests.utils.quote(kw)) for kw in SITE_KEYWORDS]
    base = re.match(r"https?://[^/]+", urls[0]).group(0)
    for url in urls:
        try:
            r = requests.get(url, headers=UA, timeout=25)
            if r.status_code != 200:
                errors.append(str(r.status_code))
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                m = re.search(src["id"], a["href"])
                if not m:
                    continue
                jid = src["name"] + "_" + m.group(1)
                if jid in jobs:
                    continue
                card = a
                for _ in range(6):
                    if card.parent is None:
                        break
                    card = card.parent
                    if len(card.get_text(" ", strip=True)) > 80:
                        break
                if src.get("anchor"):
                    title = norm(a.get_text())
                    text = norm(a.get_text(" ")) + " " + a["href"]
                else:
                    h = card.find(["h1", "h2", "h3", "h4"])
                    title = norm(h.get_text()) if h else ""
                    if not title:
                        cands = [norm(x.get_text()) for x in card.find_all("a", href=True) if re.search(src["id"], x["href"])]
                        title = max(cands, key=len) if cands else norm(a.get_text())
                    text = norm(card.get_text(" "))
                if not title_ok(title) or not allowed_location(text) or excluded(title):
                    continue
                href = a["href"]
                if href.startswith("/"):
                    href = base + href
                jobs[jid] = {"id": jid, "title": title[:120], "company": "", "location": "", "url": href, "source": src["name"]}
        except Exception as e:
            errors.append(str(e)[:40])
        time.sleep(1.5)
    return jobs, errors

def main():
    seen = load_seen()
    now = time.time()

    # LinkedIn
    found, errs, ok = {}, 0, 0
    for kw in KEYWORDS:
        for loc in LOCATIONS:
            try:
                for j in linkedin(kw, loc):
                    found[j["id"]] = j
                ok += 1
            except Exception as e:
                errs += 1
                last = str(e)
            time.sleep(2)
    if ok == 0:
        if now - seen.get("_last_err", 0) > 6 * 3600:
            tg("⚠️ LinkedIn: הסריקה נכשלה. " + last)
            seen["_last_err"] = now
    else:
        good = {k: j for k, j in found.items() if title_ok(j["title"]) and allowed_location(j["location"]) and not excluded(j["title"] + " " + j["company"])}
        if "_init_LinkedIn" not in seen:
            for k in found:
                seen[k] = 1
            seen["_init_LinkedIn"] = 1
            tg(f"✅ LinkedIn פעיל. נסרקו {len(found)} משרות, {len(good)} מתאימות. מעכשיו תקבל רק חדשות.")
        else:
            for k, j in good.items():
                if k not in seen:
                    send_job(j)
            for k in found:
                seen[k] = 1

    # אתרים ישראליים וחברות
    for src in SOURCES:
        name = src["name"]
        jobs, errors = scan_source(src)
        if not jobs and errors and len(errors) >= max(1, len(src.get('urls') or SITE_KEYWORDS) // 2):
            if now - seen.get("_err_" + name, 0) > 6 * 3600:
                tg(f"⚠️ {name}: לא הצלחתי לקרוא ({','.join(errors[:3])})")
                seen["_err_" + name] = now
            continue
        if "_init_" + name not in seen:
            for k in jobs:
                seen[k] = 1
            seen["_init_" + name] = 1
            tg(f"✅ {name} פעיל. נמצאו {len(jobs)} משרות מתאימות. מעכשיו תקבל רק חדשות.")
        else:
            for k, j in jobs.items():
                if k not in seen:
                    send_job(j)
                    seen[k] = 1

    save_seen(seen)
    print(f"linkedin_found={len(found)} ok={ok} errs={errs}")

if __name__ == "__main__":
    main()
