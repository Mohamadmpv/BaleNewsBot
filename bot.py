import feedparser
import requests
from bs4 import BeautifulSoup
import time
import os
from datetime import datetime, timedelta
from baleRobot import BaleClient

TOKEN = os.environ.get("BALE_TOKEN")
CHANNEL_NAME = os.environ.get("BALE_CHANNEL")

if not TOKEN or not CHANNEL_NAME:
    print("❌ خطا: توکن یا کانال تنظیم نشده است.")
    exit()

client = BaleClient(TOKEN)

RSS_FEEDS = [
    "https://shenasname.ir/page/458?format=feed&type=rss",
    "https://www.mehrnews.com/rss",
    "https://www.isna.ir/rss",
    "https://www.ilna.ir/feeds/",
    "https://www.khabaronline.ir/rss?kw=حقوق+و+دستمزد",
]

KEYWORDS_MUST = [
    "حقوق", "دستمزد", "معیشت", "کالابرگ", "یارانه", "بازنشسته", "بازنشستگی",
    "استخدام", "آزمون", "قانون کار", "قانون استخدامی", "هیات علمی", 
    "تامین اجتماعی", "بیمه", "قیمت", "وام", "اقساط",
    "بخشنامه", "قرارداد کار", "تبدیل وضعیت", "دیوان عدالت", "سازمان اداری"
]

KEYWORDS_IGNORE = ["کروبی", "سیاسی", "زندان", "انتخابات", "فوتبال", "ورزش", "سفر"]

SENT_NEWS_LINKS = set()

def get_news_summary(url):
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        paragraphs = soup.find_all('p')
        summary = ""
        for p in paragraphs:
            text = p.get_text(strip=True)
            if len(text) > 50 and "کلیک" not in text:
                summary += text + " "
                if len(summary) > 600: break
        return summary.strip()
    except:
        return ""

def is_recent(entry):
    published = entry.get('published_parsed') or entry.get('updated_parsed')
    if not published: return False
    news_date = datetime.fromtimestamp(time.mktime(published))
    return (datetime.now() - news_date) < timedelta(days=2)

def get_news(limit=3):
    all_news = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:15]:
                title = entry.title
                if any(bad in title for bad in KEYWORDS_IGNORE): continue
                if any(good in title for good in KEYWORDS_MUST):
                    if entry.link in SENT_NEWS_LINKS: continue
                    if not is_recent(entry): continue
                    
                    image_url = None
                    if hasattr(entry, 'media_content') and entry.media_content:
                        image_url = entry.media_content[0].get('url')
                    elif hasattr(entry, 'links'):
                        for l in entry.links:
                            if 'image' in l.get('type', ''): image_url = l.get('href'); break
                    
                    summary = get_news_summary(entry.link)
                    all_news.append({
                        "title": title, "link": entry.link,
                        "source": feed.feed.get('title', 'منبع'),
                        "image_url": image_url, "summary": summary
                    })
        except: continue
    return all_news[:limit]

print("🤖 در حال جستجو و ارسال اخبار به کانال...")
news_list = get_news(limit=3)

if not news_list:
    print("خبر جدیدی پیدا نشد.")
else:
    for news in news_list:
        caption = f"**{news['title']}**\n\n"
        if news['summary']: caption += f"{news['summary']}\n\n"
        caption += f"🔗 منبع: [{news['source']}]({news['link']})"
        try:
            if news['image_url']: client.send_photo(CHANNEL_NAME, news['image_url'], caption=caption)
            else: client.send_message(CHANNEL_NAME, caption)
            time.sleep(2)
        except Exception as e:
            print(f"خطا در ارسال: {e}")
