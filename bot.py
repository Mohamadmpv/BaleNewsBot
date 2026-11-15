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
                if len(text) > 60 and "کلیک" not in text and "خبرگزاری" not in text:
                    summary += text + " "
                    if len(summary) > 500: break
        return summary.strip()
    except: return ""

def get_shenasnameh_news():
    news_list = []
    try:
        response = requests.get("https://shenasname.ir", headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                title = link.get_text(strip=True)
                if len(title) > 15 and any(kw in title for kw in ["استخدام", "حقوق", "بخشنامه", "قانون", "بازنشستگی", "قرارداد", "معیشت"]):
                    if href.startswith('/'): href = "https://shenasname.ir" + href
                    if not any(n['link'] == href for n in news_list):
                        news_list.append({"title": title, "link": href, "source": "شناسنامه قانون", "summary": ""})
    except: pass
    return news_list[:5]

RSS_FEEDS = ["https://www.mehrnews.com/rss", "https://www.isna.ir/rss", "https://www.ilna.ir/feeds/", "https://www.khabaronline.ir/rss?kw=حقوق+و+دستمزد"]
KEYWORDS_MUST = ["حقوق و دستمزد", "دستمزد کارگران", "استخدام", "آزمون استخدامی", "کالابرگ", "بازنشستگی", "بخشنامه", "قرارداد کار", "معیشت"]
KEYWORDS_IGNORE = ["حقوق بشر", "سیاسی", "زندان", "دادگاه", "کروبی", "انتخابات", "فوتبال", "ورزش", "سفر", "دیدار", "تشییع"]

# تحلیل‌های آموزشی برای مواقعی که خبر جدیدی نیست
FALLBACK_ANALYSES = [
    {"title": "بررسی شرایط بازنشستگی در تامین اجتماعی", "text": "بر اساس قانون تامین اجتماعی، بیمه‌شدگان با داشتن ۳۰ سال سابقه پرداخت حق بیمه می‌توانند بازنشسته شوند. این قانون شامل حال افرادی که در مشاغل سخت و زیان‌آور کار می‌کنند نیز با شرایط ویژه‌ای می‌شود.", "source": "قانون تامین اجتماعی (ماده ۷۶)"},
    {"title": "حقوق و مزایای مرخصی زایمان", "text": "زنان باردار بر اساس قانون کار، حق استفاده از مرخصی زایمان (۹ ماه) را دارند و در این مدت حقوق آن‌ها باید توسط کارفرما پرداخت شود.", "source": "قانون کار (مواد ۷۶ تا ۷۸)"}
]

def is_recent(entry, days=2):
    published = entry.get('published_parsed') or entry.get('updated_parsed')
    if not published: return False
    news_date = datetime.fromtimestamp(time.mktime(published))
    return (datetime.now() - news_date) < timedelta(days=days)

# تابع اصلی با قابلیت جایگزین (Fallback)
def get_all_news(limit=5):
    final_news = []
    
    # ۱. تلاش برای خواندن از شناسنامه قانون
    shenas_news = get_shenasnameh_news()
    for n in shenas_news:
        if n['link'] not in SENT_NEWS_LINKS:
            n['summary'] = get_news_summary(n['link'])
            final_news.append(n)
            if len(final_news) >= limit: break

    # ۲. اگر خبر جدیدی پیدا نشد، از آرشیو (حتی قدیمی‌تر از ۴۸ ساعت) بیاور
    if len(final_news) == 0:
        print("هیچ خبر جدیدی نبود. جستجو در آرشیو...")
        for n in shenas_news: # از لیست خبرهای سایت
            if n['link'] not in SENT_NEWS_LINKS: # اگر قبلا نفرستادیم
                n['summary'] = get_news_summary(n['link'])
                final_news.append(n)
                if len(final_news) >= limit: break
                
    # ۳. اگر باز هم کم بود، از خبرگزاری‌ها (با فیلتر ۴۸ ساعت) بیاور
    if len(final_news) < limit:
        for feed_url in RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:10]:
                    title = entry.title
                    if any(bad in title for bad in KEYWORDS_IGNORE): continue
                    if any(good in title for good in KEYWORDS_MUST):
                        if not is_recent(entry, days=2): continue # فیلتر ۴۸ ساعت
                        if entry.link in SENT_NEWS_LINKS: continue
                        
                        image_url = None
                        if hasattr(entry, 'media_content') and entry.media_content:
                            image_url = entry.media_content[0].get('url')
                        final_news.append({"title": title, "link": entry.link, "source": feed.feed.get('title', 'منبع'), "image_url": image_url, "summary": ""})
                        if len(final_news) >= limit: break
            except: continue
            if len(final_news) >= limit: break

    # ۴. اگر باز هم کم بود، تحلیل آموزشی اضافه کن
    if len(final_news) < limit:
        for analysis in FALLBACK_ANALYSES:
            if len(final_news) >= limit: break
            final_news.append({"title": analysis["title"], "link": "https://shenasname.ir", "source": analysis["source"], "image_url": None, "summary": analysis["text"]})

    return final_news[:limit]

def send_news(chat_id, count):
    news_list = get_all_news(limit=count)
    for news in news_list:
        caption = f"**{news['title']}**\n\n"
        if news['summary']: 
            caption += f"{news['summary']}\n\n"
        caption += f"🔗 منبع: [{news['source']}]({news['link']})"
        
        try:
            if news.get('image_url'): 
                client.send_photo(chat_id, news['image_url'], caption=caption)
            else: 
                client.send_message(chat_id, caption)
            SENT_NEWS_LINKS.add(news['link'])
            time.sleep(2)
        except: pass

print("🤖 ربات روشن شد...")

SENT_NEWS_FILE = "sent_news.txt"
SENT_NEWS_LINKS = set()
if os.path.exists(SENT_NEWS_FILE):
    with open(SENT_NEWS_FILE, "r", encoding="utf-8") as f:
        SENT_NEWS_LINKS = set(line.strip() for line in f if line.strip())

try:
    updates = client.get_updates(offset=0, timeout=5)
    for update in updates:
        message = update.message
        if not message or not message.text: continue
        
        if message.text == "/start":
            client.send_message(message.chat.id, "👋 سلام! در حال جستجو در آرشیو و منابع خبری...")
            send_news(message.chat.id, 5)
            
except Exception as e:
    print(f"خطا: {e}")

with open(SENT_NEWS_FILE, "w", encoding="utf-8") as f:
    for link in SENT_NEWS_LINKS: f.write(link + "\n")
