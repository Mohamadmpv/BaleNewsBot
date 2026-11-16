import feedparser
import requests
from bs4 import BeautifulSoup
import time
import os
from datetime import datetime, timedelta
from baleRobot import BaleClient

# 🔴 توکن ربات خود را اینجا بگذارید
TOKEN = "905647704:Ml_O1U8Oxbi07Spn_vacNhEftkeZ2UtDO-Y"
client = BaleClient(TOKEN)

# ==========================================
# ۱. توابع خواندن خبر (مثل کد سیستم)
# ==========================================
def get_news_summary(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        summary = ""
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if len(text) > 50 and "کلیک" not in text:
                summary += text + " "
                if len(summary.split()) >= 100: break
        return summary.strip()
    except: return ""

def get_shenasnameh_news():
    news_list = []
    try:
        response = requests.get("https://shenasname.ir", headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                title = link.get_text(strip=True)
                if len(title) > 15 and any(kw in title for kw in ["استخدام", "حقوق", "بخشنامه", "قانون"]):
                    href = link['href']
                    if href.startswith('/'): href = "https://shenasname.ir" + href
                    news_list.append({"title": title, "link": href, "source": "شناسنامه قانون", "image_url": None, "summary": ""})
    except: pass
    return news_list

RSS_FEEDS = ["https://www.mehrnews.com/rss", "https://www.isna.ir/rss", "https://www.ilna.ir/feeds/"]
KEYWORDS_MUST = ["حقوق", "دستمزد", "استخدام", "کالابرگ", "بازنشستگی", "بخشنامه", "قرارداد", "معیشت"]
KEYWORDS_IGNORE = ["حقوق بشر", "سیاسی", "زندان", "دادگاه", "کروبی", "انتخابات", "فوتبال", "ورزش"]

def is_recent(entry):
    published = entry.get('published_parsed') or entry.get('updated_parsed')
    if not published: return False
    news_date = datetime.fromtimestamp(time.mktime(published))
    return (datetime.now() - news_date) < timedelta(days=3) # فیلتر ۳ روزه

def get_news_from_rss():
    all_news = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                title = entry.title
                if any(bad in title for bad in KEYWORDS_IGNORE): continue
                if any(good in title for good in KEYWORDS_MUST):
                    if not is_recent(entry): continue
                    image_url = entry.media_content[0].get('url') if hasattr(entry, 'media_content') else None
                    all_news.append({"title": title, "link": entry.link, "source": feed.feed.get('title', 'منبع'), "image_url": image_url, "summary": ""})
        except: continue
    return all_news

# ==========================================
# ۲. خواندن حافظه‌ها
# ==========================================
SENT_NEWS_FILE = "sent_news.txt"
LAST_ID_FILE = "last_id.txt"
USERS_FILE = "users.txt"

SENT_NEWS_LINKS = set()
if os.path.exists(SENT_NEWS_FILE):
    with open(SENT_NEWS_FILE, "r") as f: SENT_NEWS_LINKS = set(l.strip() for l in f)

LAST_ID = 0
if os.path.exists(LAST_ID_FILE):
    with open(LAST_ID_FILE, "r") as f: LAST_ID = int(f.read())

USERS = set()
if os.path.exists(USERS_FILE):
    with open(USERS_FILE, "r") as f: USERS = set(l.strip() for l in f)

# ==========================================
# ۳. جمع‌آوری خبر
# ==========================================
def get_all_news(limit=3):
    final_news = []
    for r in get_news_from_rss():
        if r['link'] not in SENT_NEWS_LINKS:
            summary = get_news_summary(r['link'])
            if len(summary.split()) >= 100:
                r['summary'] = summary
                final_news.append(r)
            if len(final_news) >= limit: break
    if len(final_news) < limit:
        for n in get_shenasnameh_news():
            if n['link'] not in SENT_NEWS_LINKS:
                summary = get_news_summary(n['link'])
                if len(summary.split()) >= 100:
                    n['summary'] = summary
                    final_news.append(n)
                if len(final_news) >= limit: break
    return final_news

# ==========================================
# ۴. پاسخ به پیام‌های جدید (فقط اگر سیستم خاموش باشد)
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
                    if news.get('image_url'): client.send_photo(message.chat.id, news['image_url'], caption=caption)
                    else: client.send_message(message.chat.id, caption)
                    SENT_NEWS_LINKS.add(news['link'])
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
                if news.get('image_url'): client.send_photo(user_id, news['image_url'], caption=caption)
                else: client.send_message(user_id, caption)
                time.sleep(2)
            except: pass

# ==========================================
# ۶. ذخیره حافظه
# ==========================================
with open(LAST_ID_FILE, "w") as f: f.write(str(LAST_ID))
with open(SENT_NEWS_FILE, "w") as f:
    for link in SENT_NEWS_LINKS: f.write(link + "\n")
with open(USERS_FILE, "w") as f:
    for u in USERS: f.write(u + "\n")
