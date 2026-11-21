import feedparser
import requests
import time
import os
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from baleRobot import BaleClient

# خواندن توکن از تنظیمات گیت‌هاب برای امنیت
TOKEN = os.environ.get("BALE_TOKEN", "905647704:ivlB2El9803u-a12Uq5tTW87-RLTf5WvQvQ")

# ==========================================
# ۱. لیست سایت‌ها و کلمات کلیدی
# ==========================================
RSS_FEEDS = [
    "https://www.mehrnews.com/rss",
    "https://www.isna.ir/rss",
    "https://www.irna.ir/rss",
    "https://www.ilna.ir/feeds/",
    "https://www.icana.ir/rss"
]
HTML_SOURCES = ["https://shenasname.ir"]

KEYWORDS_CORE = [
    "استخدام", "آزمون استخدامی", "اداره استخدامی", "کارگزینی", "بخشنامه", "تخلفات اداری", 
    "دورکاری", "ساعات کاری", "حقوق", "دستمزد", "معیشت", "کالابرگ", "یارانه", "بنزین", 
    "متناسب‌سازی", "افزایش حقوق", "بازنشستگی", "صندوق بازنشستگی", "تامین اجتماعی", 
    "بیمه", "حق بیمه", "قانون کار", "قانون استخدامی", "بودجه", "سازمان برنامه", 
    "تعطیلی ادارات", "تعطیلی مدارس", "کارمند", "کارگر", "تعطیلات", "تعطیل"
]

KEYWORDS_IGNORE = [
    "کره شمالی", "ترامپ", "بایدن", "آمریکا", "اسرائیل", "جنگ", "زلزله", "اندونزی", 
    "آتش‌سوزی", "قبرس", "باد", "ورزش", "فوتبال", "سیاسی", "انتخابات", "دیوان محاسبات", 
    "بین‌الملل", "خاورمیانه", "روسیه", "چین", "اروپا", "دلار", "فقهی", "مذهبی", "دادگاه"
]

# ==========================================
# ۲. توابع خواندن خبر
# ==========================================
def is_recent(entry):
    published = entry.get('published_parsed') or entry.get('updated_parsed')
    if not published: return True 
    return (datetime.now() - datetime.fromtimestamp(time.mktime(published))) < timedelta(days=3)

def is_related(title):
    if any(bad in title for bad in KEYWORDS_IGNORE): return False
    if any(kw in title for kw in KEYWORDS_CORE): return True
    return False

def get_news_from_html():
    news_list = []
    for url in HTML_SOURCES:
        try:
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                for link in soup.find_all('a', href=True):
                    title = link.get_text(strip=True)
                    href = link['href']
                    if len(title) > 15 and ('/news/' in href or '/mosavabat/' in href or '/bakhshnameh/' in href):
                        if href.startswith('/'): href = url + href
                        if is_related(title):
                            if not any(n['link'] == href for n in news_list):
                                news_list.append({"title": title, "link": href, "source": "شناسنامه قانون"})
        except: pass
    return news_list

def get_news_from_rss():
    news_list = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]: 
                title = entry.title
                if is_related(title):
                    if not is_recent(entry): continue
                    news_list.append({"title": title, "link": entry.link, "source": feed.feed.get('title', 'منبع')})
        except: continue
    return news_list

def get_all_news():
    return get_news_from_html() + get_news_from_rss()

# ==========================================
# ۳. استخراج متن و تصویر
# ==========================================
def get_article_text(url):
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
        if response.status_code != 200: return ""
        soup = BeautifulSoup(response.text, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form']): tag.decompose()
        article = soup.find('article') or soup.find('div', class_=lambda c: c and any(x in str(c).lower() for x in ['content', 'body', 'text', 'news']))
        target = article if article else soup
        paragraphs = target.find_all('p')
        text = "\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)
        return text[:1500]
    except: return ""

def get_article_image(url):
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
        if response.status_code != 200: return None
        soup = BeautifulSoup(response.text, 'html.parser')
        og = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'og:image'})
        if og and og.get('content'): return og['content']
        tw = soup.find('meta', attrs={'name': 'twitter:image'})
        if tw and tw.get('content'): return tw['content']
        for img_tag in soup.find_all('img', src=True):
            src = img_tag['src']
            if src.startswith('data:'): continue
            if src.startswith('//'): return 'https:' + src
            if src.startswith('/'): return url.rsplit('/', 1)[0] + src
            return src
    except: pass
    return None

# ==========================================
# ۴. حافظه و ارسال
# ==========================================
SENT_FILE = "sent.txt"
USERS_FILE = "users.txt"
SENT = set()
if os.path.exists(SENT_FILE):
    with open(SENT_FILE, "r") as f: SENT = set(l.strip() for l in f)

def load_users():
    if not os.path.exists(USERS_FILE): return []
    with open(USERS_FILE, "r") as f:
        return [line.strip() for line in f if line.strip().isdigit()]

def build_caption(n, body):
    if body:
        caption = f"🔴 **خبر** | 📰 {n['source']}\n━━━━━━━━━━━━━━━━━━━━\n**{n['title']}**\n\n{body}\n\n🔗 [مشاهده اصل خبر]({n['link']})"
    else:
        caption = f"🔴 **خبر** | 📰 {n['source']}\n━━━━━━━━━━━━━━━━━━━━\n**{n['title']}**\n\n🔗 [مشاهده اصل خبر]({n['link']})"
    if len(caption) > 4000: caption = caption[:3950] + "...\n\n🔗 [ادامه در منبع]"
    return caption

def send_news(client, chat_id, limit=5, ignore_memory=False):
    news_list = get_all_news()
    count = 0
    for n in news_list:
        if count >= limit: break
        if ignore_memory or (n['link'] not in SENT):
            body = get_article_text(n['link'])
            image = get_article_image(n['link'])
            caption = build_caption(n, body)
            
            success = False
            if image:
                try:
                    client.send_photo(chat_id, photo=image, caption=caption)
                    success = True
                except Exception as e:
                    print(f"⚠️ عکس ارسال نشد، ارسال متن...")
            
            if not success:
                try:
                    client.send_message(chat_id, caption)
                    success = True
                except Exception as e:
                    print(f"❌ خطا در ارسال متن: {e}")

            if success:
                SENT.add(n['link'])
                with open(SENT_FILE, "a") as f: f.write(n['link'] + "\n")
                count += 1
                time.sleep(2)

# ==========================================
# ۵. حلقه اصلی (مخصوص گیت‌هاب - اجرای کوتاه)
# ==========================================
def main():
    print("🤖 ربات روشن شد...")
    client = BaleClient(TOKEN)
    if hasattr(client, 'connect'):
        client.connect()
    print("✅ اتصال به بله برقرار شد.")

    # خواندن آخرین وضعیت برای اینکه پیام‌های تکراری پردازش نشوند
    offset_file = "offset.txt"
    last_id = 0
    if os.path.exists(offset_file):
        try:
            with open(offset_file, "r") as f:
                last_id = int(f.read().strip())
        except: pass

    # ۱. بررسی پیام‌های جدید (مثلا /start)
    try:
        updates = client.get_updates(offset=last_id + 1, timeout=2)
        for update in updates:
            last_id = update.update_id
            msg = update.message
            if not msg or not msg.text: continue

            if msg.text == "/start":
                uid = str(msg.chat.id)
                users = load_users()
                if uid not in users:
                    with open(USERS_FILE, "a") as f: f.write(uid + "\n")
                    print(f"✅ کاربر جدید: {uid}")

                client.send_message(msg.chat.id, "👋 سلام! به ربات حرفه‌ای خبری خوش آمدید.\n\n📰 من اخبار مهم استخدامی، حقوق، معیشت، کالابرگ و بخشنامه‌ها را از منابع معتبر برای شما ارسال می‌کنم.")
                send_news(client, msg.chat.id, limit=10, ignore_memory=True)
    except Exception as e:
        print(f"خطا در دریافت پیام‌ها: {e}")

    # ذخیره وضعیت آپدیت‌ها
    with open(offset_file, "w") as f:
        f.write(str(last_id))

    # ۲. ارسال خودکار به همه کاربران
    users = load_users()
    print(f"⏰ ارسال خودکار به {len(users)} کاربر (فقط اخبار جدید)...")
    for uid in users:
        send_news(client, uid, limit=3, ignore_memory=False)

    # ذخیره لینک‌های ارسال شده
    with open(SENT_FILE, "w") as f:
        for link in SENT: f.write(link + "\n")
    
    print("پایان اجرا.")

if __name__ == "__main__":
    main()
