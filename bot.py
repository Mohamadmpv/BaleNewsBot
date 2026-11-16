import feedparser
import requests
from bs4 import BeautifulSoup
import time
import os
from datetime import datetime, timedelta
from baleRobot import BaleClient

TOKEN = "905647704:Ml_O1U8Oxbi07Spn_vacNhEftkeZ2UtDO-Y"
client = BaleClient(TOKEN)

# ==========================================
# ۱. توابع خواندن خبر
# ==========================================
def get_summary_and_image(url):
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        text = ""
        for p in soup.find_all('p'):
            t = p.get_text(strip=True)
            if len(t) > 40 and "کلیک" not in t and "شناسنامه قانون" not in t:
                text += t + " "
                if len(text.split()) >= 100: break
        image_url = None
        img = soup.find('img', class_='wp-post-image') or soup.find('img', class_='attachment-post-thumbnail')
        if img and img.get('src'): image_url = img['src']
        return text.strip(), image_url
    except: return "", None

def get_shenasnameh_news():
    news_list = []
    try:
        response = requests.get("https://shenasname.ir", headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                title = link.get_text(strip=True)
                href = link['href']
                if len(title) > 15 and ('/news/' in href or '/mosavabat/' in href or '/bakhshnameh/' in href):
                    if href.startswith('/'): href = "https://shenasname.ir" + href
                    if any(bad in title for bad in ["حقوق بشر", "سیاسی", "ورزش", "فوتبال"]): continue
                    if not any(n['link'] == href for n in news_list):
                        news_list.append({"title": title, "link": href, "source": "شناسنامه قانون", "image": None, "summary": ""})
                        if len(news_list) >= 5: break
    except: pass
    return news_list

def get_kargozini_news():
    news_list = []
    try:
        response = requests.get("https://kaargozini.ir", headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for heading in soup.find_all(['h2', 'h3']):
                link = heading.find('a')
                if link and link.get('href'):
                    title = link.get_text(strip=True)
                    href = link['href']
                    if len(title) > 15 and any(kw in title for kw in ["استخدام", "حقوق", "بخشنامه", "قانون", "بازنشستگی", "دستمزد"]):
                        if not href.startswith('http'): href = "https://kaargozini.ir" + href
                        if not any(n['link'] == href for n in news_list):
                            news_list.append({"title": title, "link": href, "source": "کارگزینی", "image": None, "summary": ""})
                            if len(news_list) >= 5: break
    except: pass
    return news_list

def get_rss_news():
    news_list = []
    feeds = ["https://www.mehrnews.com/rss", "https://www.isna.ir/rss", "https://www.irna.ir/rss", "https://www.ilna.ir/feeds/"]
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                title = entry.title
                if any(bad in title for bad in ["حقوق بشر", "سیاسی", "ورزش", "فوتبال"]): continue
                if any(good in title for good in ["حقوق", "استخدام", "بازنشستگی", "کالابرگ", "بخشنامه"]):
                    image = entry.media_content[0].get('url') if hasattr(entry, 'media_content') else None
                    news_list.append({"title": title, "link": entry.link, "source": feed.feed.get('title', 'منبع'), "image": image, "summary": ""})
        except: continue
    return news_list

# ==========================================
# ۲. حافظه
# ==========================================
SENT_FILE = "sent.txt"
LAST_ID_FILE = "last_id.txt"
USERS_FILE = "users.txt"

SENT = set()
if os.path.exists(SENT_FILE):
    with open(SENT_FILE, "r") as f: SENT = set(l.strip() for l in f)

LAST_ID = 0
if os.path.exists(LAST_ID_FILE):
    with open(LAST_ID_FILE, "r") as f: LAST_ID = int(f.read())

USERS = set()
if os.path.exists(USERS_FILE):
    with open(USERS_FILE, "r") as f: USERS = set(l.strip() for l in f)

# ==========================================
# ۳. جمع‌آوری خبر
# ==========================================
def get_all_news(limit=5):
    final = []
    for n in get_shenasnameh_news():
        if len(final) >= limit: break
        if n['link'] not in SENT:
            summary, image = get_summary_and_image(n['link'])
            if len(summary.split()) >= 100:
                n['summary'] = summary
                n['image'] = image
                final.append(n)
    if len(final) < limit:
        for n in get_kargozini_news():
            if len(final) >= limit: break
            if n['link'] not in SENT:
                summary, image = get_summary_and_image(n['link'])
                if len(summary.split()) >= 100:
                    n['summary'] = summary
                    n['image'] = image
                    final.append(n)
    if len(final) < limit:
        for r in get_rss_news():
            if len(final) >= limit: break
            if r['link'] not in SENT:
                summary, image = get_summary_and_image(r['link'])
                if len(summary.split()) >= 100:
                    r['summary'] = summary
                    r['image'] = image
                    final.append(r)
    return final

# ==========================================
# ۴. پاسخ به پیام‌های جدید (استارت)
# ==========================================
try:
    updates = client.get_updates(offset=LAST_ID + 1, timeout=5)
    for update in updates:
        LAST_ID = update.update_id
        message = update.message
        if not message or not message.text: continue
        USERS.add(str(message.chat.id))
        if message.text == "/start":
            client.send_message(message.chat.id, "👋 سلام! در حال آماده‌سازی ۵ خبر اول...")
            news_list = get_all_news(limit=5)
            for news in news_list:
                caption = f"**{news['title']}**\n\n{news['summary']}\n\n🔗 منبع: [{news['source']}]({news['link']})"
                try:
                    if news.get('image'): client.send_photo(message.chat.id, news['image'], caption=caption)
                    else: client.send_message(message.chat.id, caption)
                    SENT.add(news['link'])
                    time.sleep(2)
                except: pass
except: pass

# ==========================================
# ۵. ارسال خودکار به کاربران (هر ۱ ساعت)
# ==========================================
print(f"در حال ارسال خودکار به {len(USERS)} کاربر...")
auto_news = get_all_news(limit=3)
if auto_news:
    for user_id in USERS:
        for news in auto_news:
            caption = f"**{news['title']}**\n\n{news['summary']}\n\n🔗 منبع: [{news['source']}]({news['link']})"
            try:
                if news.get('image'): client.send_photo(user_id, news['image'], caption=caption)
                else: client.send_message(user_id, caption)
                time.sleep(2)
            except: pass

# ==========================================
# ۶. ذخیره حافظه
# ==========================================
with open(LAST_ID_FILE, "w") as f: f.write(str(LAST_ID))
with open(SENT_FILE, "w") as f:
    for link in SENT: f.write(link + "\n")
with open(USERS_FILE, "w") as f:
    for u in USERS: f.write(u + "\n")
