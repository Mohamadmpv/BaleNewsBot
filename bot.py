import feedparser
import requests
from bs4 import BeautifulSoup
import time
import os
from datetime import datetime, timedelta
from baleRobot import BaleClient

# 🔴 توکن ربات
TOKEN = "905647704:Ml_O1U8Oxbi07Spn_vacNhEftkeZ2UtDO-Y"
client = BaleClient(TOKEN)

# ==========================================
# ۱ و ۲. منابع خبری (شناسنامه قانون اولویت اول)
# ==========================================
RSS_FEEDS = [
    "https://www.mehrnews.com/rss",     # مهر
    "https://www.isna.ir/rss",          # ایسنا
    "https://www.irna.ir/rss",          # ایرنا
    "https://www.ilna.ir/feeds/",       # ایلنا
    "https://news.google.com/rss/search?q=site:farsnews.ir+when:2d&hl=fa&gl=IR&ceid=IR:fa" # فارس (از طریق گوگل نیوز)
]

KEYWORDS_MUST = ["حقوق", "دستمزد", "استخدام", "کالابرگ", "بازنشستگی", "بخشنامه", "قرارداد", "معیشت", "سازمان اداری"]
KEYWORDS_IGNORE = ["حقوق بشر", "سیاسی", "زندان", "دادگاه", "کروبی", "انتخابات", "فوتبال", "ورزش", "سفر", "دیدار"]

# ==========================================
# ۳. تابع خواندن متن (حداقل ۱۰۰ کلمه)
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

# ==========================================
# ۶. بررسی تاریخ ۴۸ ساعت
# ==========================================
def is_recent(entry):
    published = entry.get('published_parsed') or entry.get('updated_parsed')
    if not published: return False
    news_date = datetime.fromtimestamp(time.mktime(published))
    return (datetime.now() - news_date) < timedelta(days=2) # ۴۸ ساعت

# ==========================================
# ۱. خواندن از شناسنامه قانون
# ==========================================
def get_shenasnameh_news():
    news_list = []
    try:
        response = requests.get("https://shenasname.ir", headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                title = link.get_text(strip=True)
                if len(title) > 15 and any(kw in title for kw in KEYWORDS_MUST):
                    href = link['href']
                    if href.startswith('/'): href = "https://shenasname.ir" + href
                    news_list.append({"title": title, "link": href, "source": "شناسنامه قانون", "image_url": None, "summary": ""})
    except: pass
    return news_list

# ==========================================
# ۲. خواندن از خبرگزاری‌ها
# ==========================================
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
                    image_url = None
                    if hasattr(entry, 'media_content') and entry.media_content:
                        image_url = entry.media_content[0].get('url')
                    all_news.append({"title": title, "link": entry.link, "source": feed.feed.get('title', 'منبع'), "image_url": image_url, "summary": ""})
        except: continue
    return all_news

# ==========================================
# ۹. حافظه ضد تکرار
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
# ۵. جمع‌آوری ۵ خبر اول
# ==========================================
def get_all_news(limit=5):
    final_news = []
    
    # اولویت اول: شناسنامه قانون
    shenas_news = get_shenasnameh_news()
    for n in shenas_news:
        if n['link'] not in SENT_NEWS_LINKS:
            summary = get_news_summary(n['link'])
            if len(summary.split()) >= 100:
                n['summary'] = summary
                final_news.append(n)
            if len(final_news) >= limit: break
    
    # اگر کم بود، خبرگزاری‌ها
    if len(final_news) < limit:
        rss_news = get_news_from_rss()
        for r in rss_news:
            if r['link'] not in SENT_NEWS_LINKS:
                summary = get_news_summary(r['link'])
                if len(summary.split()) >= 100:
                    r['summary'] = summary
                    final_news.append(r)
                if len(final_news) >= limit: break
                
    return final_news

def send_news(chat_id, count):
    news_list = get_all_news(limit=count)
    if not news_list:
        client.send_message(chat_id, "📭 در حال حاضر خبر جدیدی در ۴۸ ساعت گذشته پیدا نشد.")
        return
        
    for news in news_list:
        caption = f"**{news['title']}**\n\n{news['summary']}\n\n🔗 منبع: [{news['source']}]({news['link']})"
        try:
            if news.get('image_url'): 
                client.send_photo(chat_id, news['image_url'], caption=caption)
            else: 
                client.send_message(chat_id, caption)
            SENT_NEWS_LINKS.add(news['link'])
            time.sleep(2)
        except: pass

# ==========================================
# ۴. پاسخ به پیام‌های جدید (فقط یک‌بار)
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
            send_news(message.chat.id, 5)
except: pass

# ==========================================
# ۸. ارسال خودکار به کاربران (هر ۱ ساعت)
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
# ۹. ذخیره حافظه
# ==========================================
with open(LAST_ID_FILE, "w") as f: f.write(str(LAST_ID))
with open(SENT_NEWS_FILE, "w") as f:
    for link in SENT_NEWS_LINKS: f.write(link + "\n")
with open(USERS_FILE, "w") as f:
    for u in USERS: f.write(u + "\n")
