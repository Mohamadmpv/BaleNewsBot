import feedparser
import requests
from bs4 import BeautifulSoup
import time
import os
from datetime import datetime, timedelta
from baleRobot import BaleClient

# 🔴 توکن ربات خود را اینجا بگذارید
TOKEN = "905647704:TQ92LJotFVjKZHX4-F0VYc1XQZ6sSV0D9e0"
client = BaleClient(TOKEN)

# ==========================================
# تابع قوی برای خواندن متن از سایت‌های ایرانی
# ==========================================
def get_news_summary(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        summary = ""
        
        # مخصوص ایسنا
        isna_div = soup.find('div', class_='news-text') or soup.find('div', itemprop='articleBody')
        if isna_div:
            summary = isna_div.get_text(strip=True)
            
        # مخصوص مهر و سایر خبرگزاری‌ها
        if not summary:
            paragraphs = soup.find_all('p')
            for p in paragraphs:
                text = p.get_text(strip=True)
                if len(text) > 60 and "کلیک" not in text and "خبرگزاری" not in text:
                    summary += text + " "
                    if len(summary) > 800: break

        if not summary:
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and 'content' in meta_desc.attrs:
                summary = meta_desc['content']
                
        return summary.strip()
    except Exception as e:
        print(f"خطا در خواندن متن {url}: {e}")
        return ""

# ==========================================
# خواندن از شناسنامه قانون (بهینه‌شده)
# ==========================================
def get_shenasnameh_news():
    news_list = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get("https://shenasname.ir", headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                title = link.get_text(strip=True)
                
                # بررسی همه لینک‌ها با فیلتر کلمات کلیدی
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
# خواندن از خبرگزاری‌ها
# ==========================================
RSS_FEEDS = ["https://www.mehrnews.com/rss", "https://www.isna.ir/rss", "https://www.ilna.ir/feeds/"]
KEYWORDS_MUST = ["حقوق", "دستمزد", "معیشت", "کالابرگ", "یارانه", "بازنشسته", "استخدام", "قانون", "بخشنامه", "قیمت", "وام", "بیمه", "آزمون", "قرارداد"]

# کلمات ممنوعه (بهینه‌شده برای حذف خبرها حقوق بشری)
KEYWORDS_IGNORE = [
    "حقوق بشر", "سیاسی", "سیاست", "زندان", "دادگاه", "کروبی", "انتخابات", 
    "فوتبال", "ورزش", "سفر", "دیدار", "تشییع", "بین‌الملل"
]

def get_news_from_rss(limit=5):
    all_news = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                title = entry.title
                if any(bad in title for bad in KEYWORDS_IGNORE): continue
                if any(good in title for good in KEYWORDS_MUST):
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

SENT_NEWS_LINKS = set()
KNOWN_USERS = set()

# ذخیره و بازیابی حافظه
SENT_NEWS_FILE = "sent_news.txt"
if os.path.exists(SENT_NEWS_FILE):
    with open(SENT_NEWS_FILE, "r", encoding="utf-8") as f:
        SENT_NEWS_LINKS = set(line.strip() for line in f if line.strip())

def get_all_news(limit=5):
    final_news = []
    
    shenas_news = get_shenasnameh_news()
    for n in shenas_news:
        if n['link'] not in SENT_NEWS_LINKS:
            print(f"در حال خواندن متن: {n['title']}")
            n['summary'] = get_news_summary(n['link'])
            final_news.append(n)
    
    if len(final_news) < limit:
        rss_news = get_news_from_rss(limit=limit - len(final_news))
        for r in rss_news:
            print(f"در حال خواندن متن: {r['title']}")
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
last_update_id = 0
last_auto_time = time.time()

while True:
    try:
        updates = client.get_updates(offset=last_update_id + 1, timeout=5)
        for update in updates:
            last_update_id = update.update_id
            message = update.message
            
            if not message or not message.text: continue
            KNOWN_USERS.add(message.chat.id)
            
            if message.text == "/start":
                client.send_message(message.chat.id, "👋 سلام! در حال آماده‌سازی ۵ خبر اول...")
                send_news(message.chat.id, 5)

        if time.time() - last_auto_time > 1800:
            print("⏰ ارسال خودکار...")
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
            last_auto_time = time.time()
            
    except Exception as e:
        time.sleep(2)

# ذخیره حافظه (برای اینکه گیت‌هاب خبرهای تکراری نفرستد)
with open(SENT_NEWS_FILE, "w", encoding="utf-8") as f:
    for link in SENT_NEWS_LINKS: f.write(link + "\n")
