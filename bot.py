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
# ۱. تابع خواندن متن (با تایم‌اوت ۵ ثانیه)
# ==========================================
def get_news_summary(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        summary = ""
        isna_div = soup.find('div', class_='news-text') or soup.find('div', itemprop='articleBody')
        if isna_div:
            summary = isna_div.get_text(strip=True)
            
        if not summary:
            for p in soup.find_all('p'):
                text = p.get_text(strip=True)
                if len(text) > 80 and "کلیک" not in text and "خبرگزاری" not in text:
                    summary += text + " "
                    if len(summary) > 400: break

        if not summary:
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and 'content' in meta_desc.attrs:
                summary = meta_desc['content']
                
        return summary.strip()
    except:
        return ""

# ==========================================
# ۲. خواندن از شناسنامه قانون
# ==========================================
def get_shenasnameh_news():
    news_list = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get("https://shenasname.ir", headers=headers, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                title = link.get_text(strip=True)
                
                if len(title) > 15 and any(kw in title for kw in ["استخدام", "حقوق", "بخشنامه", "قانون", "بازنشستگی", "قرارداد", "معیشت"]):
                    if href.startswith('/'): href = "https://shenasname.ir" + href
                    if not any(n['link'] == href for n in news_list):
                        news_list.append({
                            "title": title, "link": href,
                            "source": "شناسنامه قانون",
                            "image_url": None, "summary": ""
                        })
    except: pass
    return news_list[:5]

# ==========================================
# ۳. خواندن از خبرگزاری‌ها
# ==========================================
RSS_FEEDS = [
    "https://www.mehrnews.com/rss", 
    "https://www.isna.ir/rss", 
    "https://www.ilna.ir/feeds/",
    "https://www.khabaronline.ir/rss?kw=حقوق+و+دستمزد"
]

KEYWORDS_MUST = ["حقوق و دستمزد", "دستمزد کارگران", "استخدام", "آزمون استخدامی", "کالابرگ", "بازنشستگی", "بخشنامه", "قرارداد کار", "معیشت"]
KEYWORDS_IGNORE = ["حقوق بشر", "سیاسی", "زندان", "دادگاه", "کروبی", "انتخابات", "فوتبال", "ورزش", "سفر", "دیدار", "تشییع"]

def is_recent(entry):
    published = entry.get('published_parsed') or entry.get('updated_parsed')
    if not published: return False
    news_date = datetime.fromtimestamp(time.mktime(published))
    return (datetime.now() - news_date) < timedelta(days=2)

def get_news_from_rss(limit=5):
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
                    all_news.append({
                        "title": title, "link": entry.link,
                        "source": feed.feed.get('title', 'منبع'),
                        "image_url": image_url, "summary": ""
                    })
        except: continue
    return all_news[:limit]

# ==========================================
# ۴. حافظه‌ها
# ==========================================
SENT_NEWS_FILE = "sent_news.txt"
USERS_FILE = "users.txt"

SENT_NEWS_LINKS = set()
if os.path.exists(SENT_NEWS_FILE):
    with open(SENT_NEWS_FILE, "r", encoding="utf-8") as f:
        SENT_NEWS_LINKS = set(line.strip() for line in f if line.strip())

KNOWN_USERS = set()
if os.path.exists(USERS_FILE):
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        KNOWN_USERS = set(line.strip() for line in f if line.strip())

def get_all_news(limit=5):
    final_news = []
    
    shenas_news = get_shenasnameh_news()
    for n in shenas_news:
        if n['link'] not in SENT_NEWS_LINKS:
            print(f"خواندن متن: {n['title']}")
            n['summary'] = get_news_summary(n['link'])
            final_news.append(n)
    
    if len(final_news) < limit:
        rss_news = get_news_from_rss(limit=limit - len(final_news))
        for r in rss_news:
            if r['link'] not in SENT_NEWS_LINKS:
                print(f"خواندن متن: {r['title']}")
                r['summary'] = get_news_summary(r['link'])
                final_news.append(r)
        
    return final_news[:limit]

def send_news(chat_id, count):
    news_list = get_all_news(limit=count)
    if not news_list:
        print("خبر جدیدی پیدا نشد.")
        return
    for news in news_list:
        caption = f"**{news['title']}**\n\n"
        if news['summary']: 
            caption += f"{news['summary']}\n\n"
        caption += f"🔗 منبع: [{news['source']}]({news['link']})"
        
        try:
            if news['image_url']: 
                client.send_photo(chat_id, news['image_url'], caption=caption)
            else: 
                client.send_message(chat_id, caption)
            SENT_NEWS_LINKS.add(news['link'])
            time.sleep(2)
        except: pass

print("🤖 ربات روشن شد...")

# ==========================================
# ۵. بخش دریافت پیام‌های جدید (با پیام خوش‌آمدگویی جدید)
# ==========================================
try:
    # در هر اجرا، از صفر پیام‌ها را می‌خوانیم تا پیام‌های جدید از دست نروند
    updates = client.get_updates(offset=0, timeout=5)
    
    max_update_id = 0
    for update in updates:
        if update.update_id > max_update_id:
            max_update_id = update.update_id
            
        message = update.message
        if not message or not message.text: continue
        
        # ذخیره کاربر جدید
        KNOWN_USERS.add(str(message.chat.id))
        
        if message.text == "/start":
            welcome_text = (
                "👋 سلام! به ربات خبری خوش آمدید.\n\n"
                "من اخبار مهم استخدامی، حقوق و دستمزد، کالابرگ و بخشنامه‌ها را برایتان می‌فرستم.\n\n"
                "⏰ **زمان‌بندی ارسال:**\n"
                "• اگر سیستم شخصی من روشن باشد، به محض دریافت خبر جدید، آن را برایتان ارسال می‌کنم.\n"
                "• اگر سیستم شخصی خاموش باشد، ربات روی سرور گیت‌هاب فعال می‌شود و **هر یک ساعت** یک‌بار اخبار جدید را برایتان می‌فرستد.\n\n"
                "⏳ در حال آماده‌سازی ۵ خبر اول..."
            )
            client.send_message(message.chat.id, welcome_text)
            send_news(message.chat.id, 5)
            
    # ذخیره آخرین آیدی
    if max_update_id > 0:
        with open("last_id.txt", "w") as f:
            f.write(str(max_update_id))
            
except Exception as e:
    print(f"خطا در دریافت پیام‌ها: {e}")

# ==========================================
# ۶. بخش ارسال خودکار به همه کاربران (برای گیت‌هاب)
# ==========================================
print(f"در حال ارسال خودکار به {len(KNOWN_USERS)} کاربر...")
auto_news = get_all_news(limit=3)
if auto_news:
    for user_id in KNOWN_USERS:
        for news in auto_news:
            caption = f"**{news['title']}**\n\n"
            if news['summary']: caption += f"{news['summary']}\n\n"
            caption += f"🔗 منبع: [{news['source']}]({news['link']})"
            try:
                if news['image_url']: client.send_photo(user_id, news['image_url'], caption=caption)
                else: client.send_message(user_id, caption)
                time.sleep(2)
            except: pass

# ==========================================
# ۷. ذخیره نهایی حافظه‌ها
# ==========================================
with open(SENT_NEWS_FILE, "w", encoding="utf-8") as f:
    for link in SENT_NEWS_LINKS: f.write(link + "\n")

with open(USERS_FILE, "w", encoding="utf-8") as f:
    for user in KNOWN_USERS: f.write(user + "\n")
