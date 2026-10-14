import streamlit as st
from modules.youtube_client import build
from datetime import datetime, timedelta, timezone
import pandas as pd
import requests
import re
import urllib.parse
import json
import sqlite3
import math
import statistics
import os
from pathlib import Path
from modules.growth_engine import metadata_check
from modules.intelligence import comparable_baseline, lifetime_vph, balanced_ids
import matplotlib.pyplot as plt
from collections import Counter
from pytrends.request import TrendReq
from dateutil.relativedelta import relativedelta
from modules.ai_engine import (
    groq_analyze,
    video_insight,
    channel_insight,
    competitor_insight,
    content_strategy
)

# ==========================================
# 1. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(page_title="Niche Hunter", layout="wide", initial_sidebar_state="expanded")

# --- MULTI API KEY SETUP (SUPER PARSER FIX) ---
try:
    raw_keys = st.secrets.get("YOUTUBE_API_KEYS", st.secrets.get("YOUTUBE_API_KEY", ""))
except FileNotFoundError:
    raw_keys = ""
raw_keys = raw_keys or os.environ.get('YOUTUBE_API_KEYS', os.environ.get('YOUTUBE_API_KEY', ''))
if isinstance(raw_keys, (list, tuple)):
    raw_keys = ",".join(str(k) for k in raw_keys)
else:
    raw_keys = str(raw_keys)

# Memaksa membelah string berdasarkan koma, walau nama variabelnya salah
API_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]

if not API_KEYS:
    st.warning("YouTube API belum diatur. SEO Studio, ruang riset, dan impor CSV dapat digunakan tanpa kunci YouTube.")

if 'current_api_index' not in st.session_state:
    st.session_state.current_api_index = 0
if API_KEYS:
    st.session_state.current_api_index %= len(API_KEYS)

try:
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
except FileNotFoundError:
    GEMINI_API_KEY = ""
GEMINI_API_KEY = GEMINI_API_KEY or os.environ.get('GEMINI_API_KEY', '')

# ==========================================
# 2. DATA REFERENSI
# ==========================================
COUNTRY_CODES = {
    "🌍 Global (Semua Negara)": None, "🇮🇩 Indonesia": "ID", "🇺🇸 Amerika Serikat (US)": "US",
    "🇲🇾 Malaysia": "MY", "🇸🇬 Singapura": "SG", "🇯🇵 Jepang": "JP", "🇰🇷 Korea Selatan": "KR",
    "🇬🇧 Inggris (UK)": "GB", "🇦🇺 Australia": "AU", "🇨🇦 Kanada": "CA", "🇸🇦 Arab Saudi": "SA", "🇹🇭 Thailand": "TH"
}

CATEGORIES = {
    "Semua Kategori": None, "Film & Animasi": "1", "Otomotif": "2", "Musik": "10",
    "Hewan & Peliharaan": "15", "Olahraga": "17", "Travel & Acara": "19", "Gaming": "20",
    "Orang & Blog": "22", "Komedi": "23", "Hiburan": "24", "Berita & Politik": "25",
    "How-to & Gaya": "26", "Pendidikan": "27", "Sains & Teknologi": "28"
}

SORT_OPTIONS = {
    "Relevansi": "relevance", "Tanggal Upload (Terbaru)": "date", "Jumlah Views": "viewCount",
    "Rating": "rating", "VPH Tertinggi (Custom)": "vph_custom", "Golden Ratio (Custom)": "ratio_custom",
    "Skor SEO Terbaik (Custom)": "seo_custom"
}

TIME_FILTERS = {
    "Kapan Saja": None, "Hari Ini (24 Jam)": 1, "Minggu Ini": 7, "Bulan Ini": 30, "Tahun Ini": 365
}

LICENSE_OPTIONS = {
    "Semua Lisensi": None, "Creative Commons": "creativeCommon", "Youtube Standar": "youtube"
}

CARD_COLORS = ["#f43f5e", "#fbbf24", "#10b981", "#0ea5e9", "#8b5cf6"]

# ==========================================
# 3. CUSTOM CSS
# ==========================================
# ==========================================
# 4. FUNGSI LOGIKA (BACKEND)
# ==========================================

def parse_yt_date(date_str):
    parsed = datetime.fromisoformat(str(date_str).replace('Z', '+00:00'))
    if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)

def format_number(num):
    if num >= 1000000: return f"{num/1000000:.1f}M"
    if num >= 1000: return f"{num/1000:.1f}K"
    return str(num)

def calculate_channel_age(published_at):
    try:
        pub_date = parse_yt_date(published_at)
        now = datetime.utcnow()
        diff = relativedelta(now, pub_date)
        years_decimal = diff.years + (diff.months / 12.0)
        if years_decimal >= 1: return f"{years_decimal:.1f} THN"
        elif diff.months > 0: return f"{diff.months} BLN"
        else: return f"{diff.days} HR"
    except: return "N/A"

def fetch_channel_recent_avg_views(youtube, channel_id):
    items = youtube.recent_uploads(channel_id, 15)
    samples = [{'raw_views': int(v.get('statistics',{}).get('viewCount',0)),
                'published_full': v.get('snippet',{}).get('publishedAt','')} for v in items]
    rates = [r for v in samples if (r := lifetime_vph(v)) is not None]
    return {'average_views': statistics.mean([v['raw_views'] for v in samples]) if samples else 0,
            'median_vph': statistics.median(rates) if rates else 0}


def search_youtube_channels(query, max_results=20, sort_by="Banyak Ditonton (Teratas)", subs_filter="Semua", age_filter="Semua", vph_filter="Semua"):
    for attempt in range(min(1, len(API_KEYS))):
        key_idx = (st.session_state.current_api_index + attempt) % len(API_KEYS)
        youtube = build('youtube', 'v3', developerKey=API_KEYS[key_idx])
        try:
            fetch_limit = min(50, max_results * 3) if subs_filter != "Semua" or age_filter != "Semua" else max_results
            res = youtube.search().list(q=query, type='channel', part='snippet', maxResults=fetch_limit).execute()
            ch_ids = [item['snippet']['channelId'] for item in res.get('items', [])]
            
            if not ch_ids: return []
            
            stats_res = youtube.channels().list(id=','.join(ch_ids), part='snippet,statistics,contentDetails').execute()
            channels = []
            
            for item in stats_res.get('items', []):
                raw_subs = int(item['statistics'].get('subscriberCount', 0))
                raw_videos = int(item['statistics'].get('videoCount', 0))
                raw_total_views = int(item['statistics'].get('viewCount', 0))
                published_at = item['snippet']['publishedAt']
                
                if subs_filter == "0-1K" and not (0 <= raw_subs <= 1000): continue
                elif subs_filter == "1K-10K" and not (1000 < raw_subs <= 10000): continue
                elif subs_filter == "10K-100K" and not (10000 < raw_subs <= 100000): continue
                elif subs_filter == "100K-1M" and not (100000 < raw_subs <= 1000000): continue
                elif subs_filter == "> 1M" and raw_subs <= 1000000: continue
                
                pub_date = parse_yt_date(published_at)
                now = datetime.utcnow()
                diff = relativedelta(now, pub_date)
                years_decimal = diff.years + (diff.months / 12.0)
                
                if age_filter == "Kurang dari 1 Tahun" and years_decimal >= 1: continue
                elif age_filter == "1-3 Tahun" and not (1 <= years_decimal <= 3): continue
                elif age_filter == "Lebih dari 3 Tahun" and years_decimal <= 3: continue
                
                if years_decimal > 3: card_color = "#ef4444" 
                elif years_decimal >= 1: card_color = "#facc15" 
                else: card_color = "#10b981" 
                    
                if years_decimal >= 1: age_str = f"{years_decimal:.1f} THN"
                elif diff.months > 0: age_str = f"{diff.months} BLN"
                else: age_str = f"{diff.days} HR"
                
                avg_views_val = "0"
                avg_vph_val = 0
                if vph_filter != "Semua" or sort_by == "Tumbuh Tercepat":
                    recent = fetch_channel_recent_avg_views(youtube, item['id'])
                    avg_views_val = format_number(recent['average_views'])
                    avg_vph_val = recent['median_vph']
                
                    if vph_filter == "> 100" and avg_vph_val <= 100: continue
                    elif vph_filter == "> 500" and avg_vph_val <= 500: continue
                    elif vph_filter == "> 1000" and avg_vph_val <= 1000: continue
                    elif vph_filter == "> 5000" and avg_vph_val <= 5000: continue

                channels.append({
                    'id': item['id'],
                    'title': item['snippet']['title'],
                    'custom_url': item['snippet'].get('customUrl', ''),
                    'thumb': item['snippet']['thumbnails'].get('medium', item['snippet']['thumbnails'].get('default', {}))['url'],
                    'subs': format_number(raw_subs),
                    'raw_subs': raw_subs,
                    'videos': format_number(raw_videos),
                    'raw_videos': raw_videos,
                    'total_views': format_number(raw_total_views),
                    'raw_total_views': raw_total_views,
                    'published_at_str': pub_date.strftime("%d %b %Y"),
                    'pub_date_obj': pub_date,
                    'age': age_str,
                    'card_color': card_color,
                    'avg_views': avg_views_val,
                    'raw_avg_vph': avg_vph_val 
                })
                    
            if sort_by == "Subscriber Terbanyak":
                channels = sorted(channels, key=lambda x: x['raw_subs'], reverse=True)
            elif sort_by == "Video Terbanyak":
                channels = sorted(channels, key=lambda x: x['raw_videos'], reverse=True)
            elif sort_by == "Channel Terbaru":
                channels = sorted(channels, key=lambda x: x['pub_date_obj'], reverse=True)
            elif sort_by == "Tumbuh Tercepat":
                channels = sorted(channels, key=lambda x: x['raw_avg_vph'], reverse=True)
            else:
                channels = sorted(channels, key=lambda x: x['raw_total_views'], reverse=True)
                
            st.session_state.current_api_index = key_idx
            return channels[:max_results]
        
        except Exception as e:
            if "quota" in str(e).lower() or "403" in str(e):
                continue
            else:
                st.error(f"❌ Terjadi kesalahan API YouTube. Detail: {str(e)}")
                return []
            
    st.error("Permintaan YouTube belum berhasil. Periksa kunci, izin API, atau kuota proyek. Kunci tidak diganti otomatis.")
    return []

def get_youtube_suggestions(query):
    if not query or len(query) < 2: return []
    try:
        url = f"https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q={urllib.parse.quote(query)}"
        response = requests.get(url, timeout=3)
        if response.status_code == 200: return json.loads(response.text)[1][:10]
        return []
    except: return []

def estimate_best_time(results):
    if not results: return "Data tidak cukup"
    times = []
    for r in results:
        try:
            dt = parse_yt_date(r['published_full']) + timedelta(hours=7) 
            times.append(dt)
        except: pass
    if not times: return "Data tidak cukup"
    days_indo = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']
    day_counts = Counter([days_indo[t.weekday()] for t in times])
    hour_counts = Counter([t.hour for t in times])
    return f"{day_counts.most_common(1)[0][0]}, pukul {hour_counts.most_common(1)[0][0]:02d}:00 WIB"

def get_rising_trends(query, geo='ID'):
    try:
        pytrend = TrendReq(hl='id-ID', tz=420, retries=3, backoff_factor=1) 
        pytrend.build_payload(kw_list=[query], timeframe='now 7-d', geo=geo if geo else '', gprop='youtube')
        data = pytrend.related_queries()
        if query in data and data[query]['rising'] is not None:
            return data[query]['rising'].head(8).to_dict('records')
        return []
    except Exception: return None 

def generate_ai_ideas(niche_query):
    if not GEMINI_API_KEY: return "⚠️ **Error:** GEMINI_API_KEY belum diisi di Streamlit Secrets."
    prompt = f"""Anda editor ide YouTube independen. Buat 5 usulan ide video untuk niche: "{niche_query}". Jangan menjanjikan viral, mengaku mewakili vidIQ, atau mengarang data permintaan.
    Format wajib: 
    ### Ide [Nomor]
    * **💡 Judul Video:** (Clickbait jujur)
    * **🖼️ Konsep Thumbnail:** (Elemen visual, teks, warna kontras)
    * **🔥 Alasan Menang:** (Kenapa disukai algoritma & penonton)"""
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    try:
        response = requests.post(url, headers={'Content-Type': 'application/json','x-goog-api-key':GEMINI_API_KEY}, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=45)
        response.raise_for_status()
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception: return "Layanan AI belum tersedia. Periksa konfigurasi atau coba lagi nanti."

def calculate_vph(published_at_str, current_views):
    try:
        pub_date = parse_yt_date(published_at_str).replace(tzinfo=timezone.utc)
        hours = (datetime.now(timezone.utc) - pub_date).total_seconds() / 3600
        return int(current_views / max(hours, 1))
    except: return 0

def parse_duration(iso_duration):
    try:
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso_duration)
        if not match: return "0:00"
        h, m, s = [int(v) if v else 0 for v in match.groups()]
        return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"
    except: return "N/A"

def estimate_earnings(views, region_code):
    # Explicit scenarios; public video data does not reveal creator revenue.
    return "Gunakan simulasi RPM pada detail video"


def calculate_er(views, likes, comments): return round(((likes + comments) / views) * 100, 2) if views > 0 else 0

def calculate_seo_score(title, desc, tags):
    return metadata_check(title, desc, tags)


# ==========================================
# VIRAL INTELLIGENCE V2
# New long-form videos + breakout prediction
# ==========================================
DATA_DIR = Path(os.environ.get("NICHE_HUNTER_DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DB = str(DATA_DIR / "niche_hunter_snapshots.db")
# Preserve existing local snapshot history on first upgrade.
if not Path(SNAPSHOT_DB).exists() and Path("niche_hunter_snapshots.db").exists():
    with sqlite3.connect("niche_hunter_snapshots.db") as old, sqlite3.connect(SNAPSHOT_DB) as new:
        old.backup(new)


def init_snapshot_db():
    conn = sqlite3.connect(SNAPSHOT_DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS video_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id TEXT NOT NULL,
        captured_at TEXT NOT NULL,
        views INTEGER DEFAULT 0,
        likes INTEGER DEFAULT 0,
        comments INTEGER DEFAULT 0,
        subscribers INTEGER DEFAULT 0
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_video_snapshots ON video_snapshots(video_id, captured_at)")
    conn.commit(); conn.close()


init_snapshot_db()


def parse_iso_duration_seconds(iso):
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or '')
    if not m: return 0
    h, mi, sec = [int(x or 0) for x in m.groups()]
    return h * 3600 + mi * 60 + sec


def shorts_confidence(video):
    title = (video.get('title') or '').lower()
    desc = (video.get('description') or '').lower()
    duration = video.get('duration_seconds', 99999)
    score = 0
    if duration <= 60: score += 45
    elif duration <= 180: score += 35
    if '#shorts' in title or '#shorts' in desc: score += 35
    if 'shorts' in title or 'short video' in title or 'vertical' in title: score += 15
    if 'shorts' in desc: score += 10
    return min(score, 100)


def save_video_snapshots(results):
    if not results: return
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(SNAPSHOT_DB)
    for v in results:
        last = conn.execute("SELECT captured_at FROM video_snapshots WHERE video_id=? ORDER BY captured_at DESC LIMIT 1", (v['id'],)).fetchone()
        if last and (datetime.fromisoformat(now) - datetime.fromisoformat(last[0])).total_seconds() < 300:
            continue
        conn.execute(
            "INSERT INTO video_snapshots(video_id,captured_at,views,likes,comments,subscribers) VALUES(?,?,?,?,?,?)",
            (v['id'], now, int(v.get('raw_views', v.get('views', 0))), int(v.get('raw_likes', 0)),
             int(v.get('raw_comments', 0)), int(v.get('raw_subs', 0)))
        )
    conn.commit(); conn.close()


def get_snapshot_history(video_id, limit=6):
    conn = sqlite3.connect(SNAPSHOT_DB)
    rows = conn.execute(
        "SELECT captured_at,views,likes,comments,subscribers FROM video_snapshots "
        "WHERE video_id=? ORDER BY captured_at DESC LIMIT ?", (video_id, limit)
    ).fetchall()
    conn.close()
    return rows


def calculate_v2_velocity_and_acceleration(video):
    """Return interval VPH, acceleration and history confidence.
    First scan falls back to lifetime VPH. Later scans use real snapshot deltas.
    """
    rows = get_snapshot_history(video['id'], 6)
    now = datetime.utcnow()
    current_views = int(video.get('raw_views', video.get('views', 0)))

    if not rows:
        return float(video.get('vph', 0)), 1.0, 0, 0

    latest_time = datetime.fromisoformat(rows[0][0])
    elapsed = max((now - latest_time).total_seconds() / 3600, 0.05)
    if (now - latest_time).total_seconds() < 300:
        return float(video.get("vph", 0)), 1.0, 0, 0
    current_interval_vph = max((current_views - int(rows[0][1])) / elapsed, 0)

    # With only one historical snapshot, we can measure velocity but not true acceleration.
    if len(rows) < 2:
        return current_interval_vph, 1.0, int(video.get('vph', 0)), 1

    prev_time = datetime.fromisoformat(rows[1][0])
    if (latest_time - prev_time).total_seconds() < 300:
        return current_interval_vph, 1.0, 0, 1
    interval_hours = (latest_time - prev_time).total_seconds() / 3600
    previous_interval_vph = max((int(rows[0][1]) - int(rows[1][1])) / interval_hours, 0)
    if previous_interval_vph <= 0:
        acceleration = 3.0 if current_interval_vph > 0 else 1.0
    else:
        acceleration = current_interval_vph / previous_interval_vph
    return current_interval_vph, max(0.1, acceleration), int(previous_interval_vph), len(rows)


def normalize_score(value, low, high):
    if high <= low: return 50
    return max(0, min(100, (value - low) / (high - low) * 100))


def median_safe(values, default=0):
    vals = [float(x) for x in values if x is not None and float(x) >= 0]
    return statistics.median(vals) if vals else default


def fetch_channel_baselines(youtube, channel_ids, max_videos=50, max_channels=20):
    """Use upload playlists, not search quota, and retain evidence for comparable cohorts."""
    baselines = {}
    for channel_id in list(dict.fromkeys(x for x in channel_ids if x))[:max_channels]:
        items = youtube.recent_uploads(channel_id, max_videos)
        rows = []
        for item in items:
            snippet = item.get('snippet', {})
            rows.append({'id':item['id'], 'channel_id':channel_id,
                         'published_full':snippet.get('publishedAt',''),
                         'raw_views':int(item.get('statistics',{}).get('viewCount',0)),
                         'duration_seconds':parse_iso_duration_seconds(item.get('contentDetails',{}).get('duration',''))})
        baselines[channel_id] = {'videos':rows}
    return baselines




# ==========================================
# LEGACY / SHARED YOUTUBE FUNCTIONS
# ==========================================

def get_channel_subs(youtube, channel_ids):
    try:
        result = {}
        # YouTube channel ID filters are safest in batches of 50.
        for start in range(0, len(channel_ids), 50):
            batch = channel_ids[start:start + 50]
            res = youtube.channels().list(id=','.join(batch), part='statistics').execute()
            result.update({
                item['id']: int(item['statistics'].get('subscriberCount', 0))
                for item in res.get('items', [])
                if not item.get('statistics',{}).get('hiddenSubscriberCount',False) and 'subscriberCount' in item.get('statistics',{})
            })
        return result
    except Exception as e:
        if "quota" in str(e).lower() or "403" in str(e): raise e
        return {}

def smart_summarize(text):
    if not text: return ["Tidak ada deskripsi."]
    lines = [l.strip() for l in re.sub(r'http\S+', '', text).split('\n') if len(l.strip()) > 5]
    spam = ['subscribe', 'follow', 'instagram', 'tiktok', 'donasi', 'saweria', 'copyright']
    important = [l for l in lines if len(l) > 15 and not any(s in l.lower() for s in spam)]
    return important[:4] if important else (lines[:3] if lines else ["Deskripsi terlalu pendek."])

def extract_keywords(text):
    words = [w for w in re.findall(r'\w+', text.lower()) if len(w) > 3 and w not in ['yang', 'dan', 'di', 'ke', 'dari', 'ini', 'itu', 'untuk', 'dengan', 'adalah', 'video', 'saya', 'aku', 'the', 'and', 'to', 'of', 'in', 'is', 'for', 'with']]
    return [item[0] for item in Counter(words).most_common(5)]

def analyze_channel_deep(channel_id):
    sample_limit = int(st.session_state.get("channel_sample_size", 5))
    for attempt in range(min(1, len(API_KEYS))):
        key_idx = (st.session_state.current_api_index + attempt) % len(API_KEYS)
        youtube = build('youtube', 'v3', developerKey=API_KEYS[key_idx])
        try:
            ch_data = youtube.channels().list(id=channel_id, part='snippet,statistics,contentDetails').execute()['items'][0]
            uploads_id = ch_data['contentDetails']['relatedPlaylists']['uploads']
            
            pl_res = youtube.playlistItems().list(playlistId=uploads_id, part='snippet', maxResults=max(15, sample_limit)).execute()
            vid_ids = [item['snippet']['resourceId']['videoId'] for item in pl_res.get('items', [])]
            
            recent_videos = []
            all_tags = []
            upload_hours = []
            
            if vid_ids:
                stats = youtube.videos().list(id=','.join(vid_ids), part='snippet,statistics').execute()
                for i, item in enumerate(stats['items']):
                    snippet = item['snippet']
                    views = int(item['statistics'].get('viewCount', 0))
                    try:
                        pub_dt = parse_yt_date(snippet['publishedAt']) + timedelta(hours=7)
                        upload_hours.append(pub_dt.hour)
                    except: pass
                    
                    vid_tags = snippet.get('tags', [])
                    all_tags.extend(vid_tags)
                    
                    if i < sample_limit:
                        vid_id_val = item.get('id', '') if isinstance(item.get('id'), str) else ''
                        recent_videos.append({
                            'id': vid_id_val,
                            'channel_id': channel_id,
                            'title': snippet['title'], 
                            'views': format_number(views),
                            'raw_views': views,
                            'published_full': snippet.get('publishedAt', ''),
                            'vph': calculate_vph(snippet.get('publishedAt', ''), views),
                            'date': parse_yt_date(snippet['publishedAt']).strftime("%d %b %Y"), 
                            'thumb': snippet['thumbnails'].get('medium', snippet['thumbnails'].get('default', {}))['url'],
                            'link': f"https://youtu.be/{vid_id_val}" if vid_id_val else ""
                        })
            
            best_hour_str = "Tidak diketahui"
            if upload_hours:
                most_common_hour = Counter(upload_hours).most_common(1)[0][0]
                best_hour_str = f"Pukul {most_common_hour:02d}:00 WIB"
                
            top_tags = Counter(all_tags).most_common(15)
            avg_views_calc = sum([v['raw_views'] for v in recent_videos]) / len(recent_videos) if recent_videos else 0

            st.session_state.current_api_index = key_idx
            return {
                'id': channel_id,
                'title': ch_data['snippet']['title'], 
                'description': ch_data['snippet'].get('description', ''),
                'thumb': ch_data['snippet']['thumbnails']['medium']['url'],
                'custom_url': ch_data['snippet'].get('customUrl', ''), 
                'subs': format_number(int(ch_data['statistics'].get('subscriberCount', 0))),
                'raw_subs': int(ch_data['statistics'].get('subscriberCount', 0)),
                'total_views': format_number(int(ch_data['statistics'].get('viewCount', 0))), 
                'raw_total_views': int(ch_data['statistics'].get('viewCount', 0)),
                'video_count': format_number(int(ch_data['statistics'].get('videoCount', 0))),
                'raw_videos': int(ch_data['statistics'].get('videoCount', 0)),
                'avg_recent_views': format_number(avg_views_calc),
                'median_recent_views': format_number(statistics.median([v['raw_views'] for v in recent_videos]) if recent_videos else 0),
                'sample_limit': sample_limit,
                'recent_videos': recent_videos,
                'favorite_upload_hour': best_hour_str,
                'top_seo_tags': top_tags
            }
        except Exception as e:
            if "quota" in str(e).lower() or "403" in str(e):
                continue
            else:
                st.error(f"❌ Gagal membedah channel. Detail: {str(e)}")
                return None
    st.error("Permintaan YouTube belum berhasil. Periksa kunci, izin API, atau kuota proyek.")
    return None

def process_video_response(items, youtube, region_code):
    channel_ids = list(set([item['snippet']['channelId'] for item in items]))
    subs_map = get_channel_subs(youtube, channel_ids)
    results = []
    
    for i, item in enumerate(items):
        try:
            stats = item.get('statistics', {})
            snippet = item.get('snippet', {})
            content = item.get('contentDetails', {})
            views = int(stats.get('viewCount', 0))
            likes = int(stats.get('likeCount', 0))
            comments = int(stats.get('commentCount', 0))
            subs = subs_map.get(snippet.get('channelId', ''), 0)
            
            thumbnails = snippet.get('thumbnails', {})
            best_thumb = thumbnails.get('maxres') or thumbnails.get('high') or thumbnails.get('medium') or thumbnails.get('default') or {}
            
            desc = snippet.get('description', '')
            tags = snippet.get('tags', [])
            seo_score, seo_checks = calculate_seo_score(snippet.get('title', ''), desc, tags)
            video_id = item['id'] if isinstance(item['id'], str) else item['id'].get('videoId', '')

            results.append({
                'rank': i + 1, 'id': video_id, 'channel_id': snippet.get('channelId', ''),
                'title': snippet.get('title', 'Untitled'), 'thumbnail': best_thumb.get('url', ''),
                'channel': snippet.get('channelTitle', 'Unknown'), 
                'published_full': snippet.get('publishedAt', ''),
                'published_simple': parse_yt_date(snippet['publishedAt']).strftime("%d %b %Y"),
                'duration': parse_duration(content.get('duration', 'PT0S')), 'duration_iso': content.get('duration','PT0S'), 'duration_seconds': parse_iso_duration_seconds(content.get('duration','PT0S')), 'description': desc,
                'summary': smart_summarize(desc), 'keywords': extract_keywords(desc + " " + snippet.get('title', '')),
                'views': views, 'raw_views': views, 'views_fmt': format_number(views), 'likes': format_number(likes), 'raw_likes': likes, 'comments': format_number(comments), 'raw_comments': comments, 'raw_subs': subs,
                'vph': calculate_vph(snippet.get('publishedAt', ''), views), 'vph_fmt': f"{calculate_vph(snippet.get('publishedAt', ''), views):,.0f}", 
                'earnings': estimate_earnings(views, region_code), 'er': calculate_er(views, likes, comments), 
                'subs': format_number(subs), 'ratio': (views/subs if subs > 0 else 0), 'ratio_label': f"{(views/subs if subs>0 else 0):.1f}x", 
                'is_gem': (views/subs if subs > 0 else 0) > 1.5, 'tags': tags, 'seo_score': seo_score, 'seo_checks': seo_checks,
                'subscriber_known': snippet.get('channelId', '') in subs_map,
                'link': f"https://youtu.be/{video_id}"
            })
        except: continue 
    return results

def search_youtube(query, region_code='ID', duration='any', category_id=None, published_after=None, license_type=None, sort_order='relevance', max_results=12):
    for attempt in range(min(1, len(API_KEYS))):
        key_idx = (st.session_state.current_api_index + attempt) % len(API_KEYS)
        youtube = build('youtube', 'v3', developerKey=API_KEYS[key_idx])
        try:
            api_order = 'viewCount' if sort_order in ['vph_custom', 'ratio_custom', 'seo_custom'] else sort_order
            params = {'q': query, 'part': 'snippet', 'type': 'video', 'maxResults': max_results, 'order': api_order}
            
            if region_code: params['regionCode'] = region_code
            if duration != 'any': params['videoDuration'] = duration
            if category_id: params['videoCategoryId'] = category_id
            if published_after: params['publishedAfter'] = published_after
            if license_type: params['videoLicense'] = license_type
            
            search_res = youtube.search().list(**params).execute()
            vid_ids = [item['id']['videoId'] for item in search_res.get('items', []) if 'videoId' in item['id']]
            if not vid_ids: return []

            stats_res = youtube.videos().list(part='snippet,statistics,contentDetails', id=','.join(vid_ids)).execute()
            items_by_id = {item['id']:item for item in stats_res.get('items', [])}
            results = process_video_response([items_by_id[vid] for vid in vid_ids if vid in items_by_id], youtube, region_code)
            
            if sort_order == 'vph_custom': return sorted(results, key=lambda x: x['vph'], reverse=True)
            elif sort_order == 'ratio_custom': return sorted(results, key=lambda x: x['ratio'], reverse=True)
            elif sort_order == 'seo_custom': return sorted(results, key=lambda x: x['seo_score'], reverse=True)
            
            st.session_state.current_api_index = key_idx
            return results
        except Exception as e:
            if "quota" in str(e).lower() or "403" in str(e):
                continue
            else:
                st.error(f"❌ Terjadi kesalahan API YouTube. Detail: {e}")
                return []
    st.error("Permintaan YouTube belum berhasil. Periksa kunci, izin API, atau kuota proyek.")
    return []

def get_trending_videos(region_code='ID', category_id=None, max_results=12):
    for attempt in range(min(1, len(API_KEYS))):
        key_idx = (st.session_state.current_api_index + attempt) % len(API_KEYS)
        youtube = build('youtube', 'v3', developerKey=API_KEYS[key_idx])
        try:
            params = {'part': 'snippet,statistics,contentDetails', 'chart': 'mostPopular', 'regionCode': region_code, 'maxResults': max_results}
            if category_id: params['videoCategoryId'] = category_id
            response = youtube.videos().list(**params).execute()
            
            st.session_state.current_api_index = key_idx
            return process_video_response(response.get('items', []), youtube, region_code)
        except Exception as e:
            if "quota" in str(e).lower() or "403" in str(e):
                continue
            else:
                st.error(f"❌ Error API: {e}")
                return []
    st.error("Permintaan YouTube belum berhasil. Periksa kunci, izin API, atau kuota proyek.")
    return []


def get_published_after_rfc3339(days):
    """Return an RFC3339 UTC timestamp for a freshness window."""
    if not days:
        return None
    return (datetime.utcnow() - timedelta(days=int(days))).isoformat(timespec="seconds") + "Z"

def search_viral_longform(query, region_code='ID', category_id=None, max_results=30,
                          freshness_days=7, min_duration_seconds=240):
    """V2 discovery: fresh + high-performing long-form candidates.
    YouTube API duration buckets are split into medium (4-20m) and long (>20m).
    """
    for attempt in range(min(1, len(API_KEYS))):
        key_idx = (st.session_state.current_api_index + attempt) % len(API_KEYS)
        youtube = build('youtube', 'v3', developerKey=API_KEYS[key_idx])
        try:
            published_after = get_published_after_rfc3339(freshness_days)
            collected = []
            discovery_groups = []
            discovery_source = {}
            # Fresh discovery catches new uploads that have not accumulated huge lifetime views.
            # Breakout discovery catches videos already gaining unusual view volume.
            for duration_bucket in ['medium', 'long']:
                for order in ['date', 'viewCount']:
                    params = {
                        'q': query, 'part': 'snippet', 'type': 'video',
                        'maxResults': min(50, max(10, max_results)),
                        'order': order, 'videoDuration': duration_bucket,
                    }
                    if region_code: params['regionCode'] = region_code
                    if category_id: params['videoCategoryId'] = category_id
                    if published_after: params['publishedAfter'] = published_after
                    res = youtube.search().list(**params).execute()
                    group = []
                    discovery_groups.append(group)
                    for x in res.get('items', []):
                        vid = x.get('id', {}).get('videoId')
                        if vid:
                            collected.append(vid)
                            group.append(vid)
                            source_name = 'Fresh Uploads' if order == 'date' else 'Recent High-Views'
                            discovery_source[vid] = source_name

            ids = balanced_ids(discovery_groups, 50)
            if not ids:
                return []

            stats = youtube.videos().list(
                id=','.join(ids), part='snippet,statistics,contentDetails'
            ).execute()
            raw = process_video_response(stats.get('items', []), youtube, region_code)

            # Hard long-form gate. 4 minutes is the default; no Shorts leakage.
            candidates = []
            cutoff_hours = freshness_days * 24
            for v in raw:
                age_hours = max((datetime.utcnow() - parse_yt_date(v.get('published_full', ''))).total_seconds() / 3600, 0)
                duration = int(v.get('duration_seconds', 0))
                if duration < min_duration_seconds:
                    continue
                if age_hours > cutoff_hours + 1:
                    continue
                if v.get('shorts_confidence', 0) >= 45:
                    continue
                candidates.append(v)

            # Channel baseline requires extra calls, so do it only for discovered channels.
            baseline_candidates = sorted(candidates, key=lambda x: x.get('vph', 0), reverse=True)[:20]
            channel_ids = [v.get('channel_id') for v in baseline_candidates if v.get('channel_id')]
            baselines = fetch_channel_baselines(youtube, channel_ids, max_videos=50, max_channels=20)
            for v in candidates:
                v['discovery_source'] = discovery_source.get(v.get('id'), 'Recent Candidate')
            enrich_viral_longform(candidates, query, baselines)
            save_video_snapshots(candidates)
            st.session_state.current_api_index = key_idx
            return sorted(candidates, key=lambda x: x.get('breakout_score', 0), reverse=True)[:max_results]
        except Exception as e:
            if 'quota' in str(e).lower() or '403' in str(e):
                continue
            st.error(f'❌ Viral Intelligence V2 API error: {e}')
            return []
    st.error('Permintaan YouTube belum berhasil. Periksa kunci, izin API, atau kuota proyek.')
    return []


def calculate_breakout_score(v):
    velocity_score = normalize_score(math.log10(max(v.get('velocity_vph', 0), 1)), 1, 5)
    acceleration_score = normalize_score(math.log10(max(v.get('acceleration', 1), 0.1)), -1, 1)
    baseline_multiple = v.get('channel_breakout_multiple', 0)
    baseline_score = normalize_score(math.log10(max(baseline_multiple, 0.1)), -1, 1.5)
    ratio_score = normalize_score(math.log10(max(v.get('ratio', 0.01), 0.01)), -1, 2)
    er_score = normalize_score(v.get('er', 0), 0, 10)
    freshness_score = max(0, min(100, 100 - (v.get('age_hours', 999) / 168) * 100))
    relevance_score = v.get('query_relevance', 70)

    components = {
        'Kecepatan': (velocity_score, .30), 'Akselerasi': (acceleration_score, .20),
        'Perbandingan baseline': (baseline_score, .15), 'Views/subscriber': (ratio_score, .10),
        'Engagement': (er_score, .10), 'Kebaruan': (freshness_score, .10), 'Relevansi kata': (relevance_score, .05)
    }
    if v.get('snapshot_count', 0) < 2:
        components['Akselerasi'] = (0, .20)
        acceleration_score = 0
    if v.get('channel_baseline_samples', 0) < 3 or baseline_multiple <= 0:
        components['Perbandingan baseline'] = (0, .15)
        baseline_score = 0
    v['score_components'] = [{'Komponen': k, 'Nilai': round(value,1), 'Bobot': weight, 'Kontribusi': round(value*weight,1)} for k,(value,weight) in components.items()]
    v['score_evidence'] = 'Terbatas' if v.get('snapshot_count',0) < 2 or v.get('channel_baseline_samples',0) < 3 else 'Snapshot dan baseline tersedia'
    score = (
        0.30 * velocity_score +
        0.20 * acceleration_score +
        0.15 * baseline_score +
        0.10 * ratio_score +
        0.10 * er_score +
        0.10 * freshness_score +
        0.05 * relevance_score
    )
    return round(max(0, min(100, score)), 1)


def breakout_label(score):
    if score >= 90: return '💥 EXPLOSIVE'
    if score >= 80: return '🚨 BREAKOUT'
    if score >= 70: return '🔥 HOT'
    if score >= 55: return '🚀 RISING'
    if score >= 40: return '📈 EARLY'
    return 'NORMAL'


def enrich_viral_longform(results, query='', baselines=None):
    baselines = baselines or {}
    now = datetime.utcnow()
    q_words = set(re.findall(r'\w+', query.lower()))
    for v in results:
        pub = parse_yt_date(v.get('published_full', ''))
        age_hours = max((now - pub).total_seconds() / 3600, 0.05)
        v['age_hours'] = age_hours
        v['duration_seconds'] = v.get('duration_seconds', parse_iso_duration_seconds(v.get('duration_iso', '')))
        v['shorts_confidence'] = shorts_confidence(v)

        velocity, acceleration, previous_vph, snapshot_count = calculate_v2_velocity_and_acceleration(v)
        v['velocity_vph'] = int(max(0, velocity))
        v['vph'] = v['velocity_vph']
        v['vph_fmt'] = f"{v['velocity_vph']:,}"
        v['previous_vph'] = previous_vph
        v['acceleration'] = round(acceleration, 2)
        v['snapshot_count'] = snapshot_count

        baseline = comparable_baseline(v, baselines.get(v.get('channel_id'), {}).get('videos', []), now)
        baseline_views = float(baseline.get('median_views') or 0)
        baseline_vph = float(baseline.get('median_vph') or 0)
        v['channel_baseline_views'] = int(baseline_views)
        v['channel_baseline_vph'] = int(baseline_vph)
        v['channel_baseline_samples'] = int(baseline.get('sample_size', 0))
        velocity_multiple = baseline.get('multiple') or 0
        views_multiple = v.get('raw_views', 0) / baseline_views if baseline_views > 0 else 0
        v['velocity_baseline_multiple'] = round(velocity_multiple, 2)
        v['views_baseline_multiple'] = round(views_multiple, 2)
        v['channel_breakout_multiple'] = round(velocity_multiple, 2)
        v['baseline_basis'] = baseline['basis']
        v['lifetime_vph'] = round(lifetime_vph(v, now) or 0, 2)

        title_words = set(re.findall(r'\w+', (v.get('title', '') + ' ' + v.get('description', '')).lower()))
        v['query_relevance'] = 100 * len(q_words & title_words) / len(q_words) if q_words else 0
        v['breakout_score'] = calculate_breakout_score(v)
        v['viral_score'] = v['breakout_score']  # backwards-compatible export
        v['viral_label'] = breakout_label(v['breakout_score'])
        v['breakout'] = v['breakout_score'] >= 70

        reasons = []
        if velocity_multiple >= 5: reasons.append(f"VPH sejak publikasi {velocity_multiple:.1f}x median video sebanding")
        elif velocity > 0 and baseline_vph <= 0: reasons.append("channel baseline belum cukup terbentuk")
        if acceleration >= 2: reasons.append(f"velocity naik {acceleration:.1f}x")
        if v.get('ratio', 0) >= 2: reasons.append(f"views {v['ratio']:.1f}x subscriber")
        if age_hours <= 24: reasons.append(f"baru {age_hours:.1f} jam")
        elif age_hours <= 72: reasons.append(f"baru {age_hours/24:.1f} hari")
        if v.get('er', 0) >= 5: reasons.append(f"engagement {v['er']:.1f}%")
        if not reasons: reasons.append("velocity awal sedang dipantau")
        v['breakout_reasons'] = reasons[:4]
    return sorted(results, key=lambda x: x.get('breakout_score', 0), reverse=True)


def search_viral_shorts(query, region_code='ID', category_id=None, max_results=30):
    """Backward-compatible alias. Viral Intelligence now means NEW LONG-FORM."""
    return search_viral_longform(query, region_code, category_id, max_results, freshness_days=7, min_duration_seconds=240)


def analyze_winning_patterns(results):
    if not results: return {}
    top = sorted(results, key=lambda x: x.get('breakout_score', 0), reverse=True)[:20]
    words, title_patterns, durations, scores = Counter(), Counter(), [], []
    for v in top:
        words.update(re.findall(r'\w+', v.get('title', '').lower()))
        durations.append(v.get('duration_seconds', 0)); scores.append(v.get('breakout_score', 0))
        t = v.get('title', '')
        if '?' in t: title_patterns['Question'] += 1
        if any(c.isdigit() for c in t): title_patterns['Number/List'] += 1
        if re.search(r'\b(you|your|how|why|what|cara|ternyata|rahasia|jangan)\b', t, re.I): title_patterns['Curiosity/Promise'] += 1
        if '!' in t: title_patterns['Emotional punctuation'] += 1
    common = [w for w, c in words.most_common(15) if len(w) > 3]
    return {
        'top_count': len(top),
        'avg_duration': round(sum(durations) / len(durations), 1) if durations else 0,
        'avg_score': round(sum(scores) / len(scores), 1) if scores else 0,
        'keywords': common[:10], 'title_patterns': title_patterns, 'top_videos': top
    }


def channel_outliers(results):
    out = []
    for v in results:
        baseline = comparable_baseline(v, results)
        if (baseline['multiple'] or 0) >= 3:
            out.append({**v, 'outlier_multiple': round(baseline['multiple'], 1)})
    return sorted(out, key=lambda x: x['outlier_multiple'], reverse=True)


def small_channel_gems(results):
    return sorted([
        v for v in results
        if v.get('subscriber_known', True) and 0 < int(v.get('raw_subs', 0)) <= 100000 and v.get('channel_breakout_multiple', 0) >= 3
        and v.get('breakout_score', 0) >= 55
    ], key=lambda x: x.get('breakout_score', 0), reverse=True)


def radar_chart(video):
    labels = ['Velocity', 'Acceleration', 'Channel\nBreakout', 'Views/Subs', 'Engagement', 'Freshness']
    values = [
        normalize_score(math.log10(max(video.get('velocity_vph', 0), 1)), 1, 5),
        normalize_score(math.log10(max(video.get('acceleration', 1), 0.1)), -1, 1),
        normalize_score(math.log10(max(video.get('channel_breakout_multiple', 0.1), 0.1)), -1, 1.5),
        normalize_score(math.log10(max(video.get('ratio', 0.01), 0.01)), -1, 2),
        normalize_score(video.get('er', 0), 0, 10),
        max(0, min(100, 100 - (video.get('age_hours', 999) / 168) * 100)),
    ]
    if video.get('snapshot_count',0)<2: values[1]=0
    if video.get('channel_baseline_samples',0)<3: values[2]=0
    angles = [i * 2 * math.pi / len(labels) for i in range(len(labels))]
    values += values[:1]; angles += angles[:1]
    fig, ax = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True))
    ax.plot(angles, values, linewidth=2)
    ax.fill(angles, values, alpha=0.15)
    ax.set_ylim(0, 100); ax.set_yticks([25, 50, 75, 100]); ax.set_yticklabels(['25', '50', '75', '100'])
    ax.set_xticks(angles[:-1]); ax.set_xticklabels(labels)
    ax.set_title(f"Breakout Radar — {video.get('breakout_score', 0):.0f}/100", pad=20, fontweight='bold')
    ax.grid(alpha=0.25)
    return fig


def build_content_opportunity(video, query=''):
    duration = int(video.get('duration_seconds', 0))
    minutes = duration / 60 if duration else 0
    keywords = extract_keywords(video.get('title', '') + ' ' + video.get('description', ''))[:6]
    angle = 'angle yang sama dengan diferensiasi lebih kuat'
    if '?' in video.get('title', ''): angle = 'ubah menjadi format problem → experiment → result'
    elif any(c.isdigit() for c in video.get('title', '')): angle = 'ubah menjadi list dengan hasil yang bisa dibuktikan'
    elif any(w in video.get('title', '').lower() for w in ['how', 'cara', 'tutorial']): angle = 'buat versi lebih spesifik untuk pemula dengan hasil akhir yang jelas'
    return {
        'topic': ', '.join(keywords) or query,
        'recommended_duration': f"{max(6, round(minutes))}-{max(10, round(minutes + 5))} menit" if minutes else '8-15 menit',
        'hook': f"Mulai dari masalah/hasil paling kuat terkait {keywords[0] if keywords else query}, bukan intro panjang.",
        'angle': angle,
        'title_formula': f"{keywords[0].title() if keywords else query.title()}: [hasil/temuan utama] yang tidak banyak orang tahu",
        'thumbnail': '1 objek/hasil utama + ekspresi/kontras visual kuat + 2-4 kata besar; hindari menyalin thumbnail asli.',
        'why_now': f"Video referensi masih fresh ({video.get('age_hours', 0):.1f} jam) dan memiliki breakout score {video.get('breakout_score', 0):.0f}/100.",
    }


def generate_ai_content_opportunity(video, query):
    if not GEMINI_API_KEY:
        return build_content_opportunity(video, query)
    compact = {
        'query': query, 'title': video.get('title'), 'duration': video.get('duration'),
        'views': video.get('raw_views'), 'velocity_vph': video.get('velocity_vph'),
        'acceleration': video.get('acceleration'), 'channel_breakout_multiple': video.get('channel_breakout_multiple'),
        'ratio': video.get('ratio'), 'engagement': video.get('er'), 'keywords': video.get('keywords', [])
    }
    prompt = f"""Buat content opportunity dari video YouTube yang sedang breakout. Jangan menyalin video.
Data: {json.dumps(compact, ensure_ascii=False)}
Berikan singkat: 1) topic gap, 2) hook original, 3) angle berbeda, 4) title formula, 5) thumbnail concept, 6) recommended duration, 7) why-now. Jangan mengarang fakta di luar data."""
    url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent'
    try:
        r = requests.post(url, headers={'Content-Type': 'application/json','x-goog-api-key':GEMINI_API_KEY}, json={'contents': [{'parts': [{'text': prompt}]}]}, timeout=60)
        r.raise_for_status()
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception:
        return build_content_opportunity(video, query)


def generate_ai_winner_analysis(results, query):
    if not results: return 'Tidak ada data.'
    if not GEMINI_API_KEY: return '⚠️ GEMINI_API_KEY belum diisi.'
    top = sorted(results, key=lambda x: x.get('breakout_score', 0), reverse=True)[:12]
    compact = [{
        'title': v['title'], 'views': v['views'], 'velocity_vph': v.get('velocity_vph', 0),
        'acceleration': v.get('acceleration', 1), 'channel_multiple': v.get('channel_breakout_multiple', 0),
        'ratio': round(v.get('ratio', 0), 1), 'er': v.get('er', 0),
        'duration': v.get('duration'), 'score': v.get('breakout_score', 0)
    } for v in top]
    prompt = f"""Analisis kandidat long-form baru untuk niche '{query}'. Jangan mengarang data. Temukan pola velocity, acceleration, channel baseline, durasi, judul, engagement, dan content opportunity. Berikan: Why breakout, winning formula, 5 content opportunities, red flags. Data: {json.dumps(compact, ensure_ascii=False)}"""
    url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent'
    try:
        r = requests.post(url, headers={'Content-Type': 'application/json','x-goog-api-key':GEMINI_API_KEY}, json={'contents': [{'parts': [{'text': prompt}]}]}, timeout=60); r.raise_for_status()
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception: return 'Layanan AI belum tersedia. Periksa konfigurasi atau coba lagi nanti.'


def get_artist_search_demand(artist, region_code='ID', freshness_days=7, max_results=50):
    """Low-quota YouTube audience-interest proxy.

    Important: YouTube Data API does NOT expose official query search volume.
    This function therefore measures search-result presence + recent content
    activity/performance, not the number of people who searched the artist.

    Quota strategy: one search.list + one videos.list per artist.
    The previous implementation made three search.list calls per artist,
    which could exhaust the daily quota very quickly.
    """
    artist = (artist or '').strip()
    if not artist:
        return None

    published_after = get_published_after_rfc3339(freshness_days)
    last_error = None

    for attempt in range(min(1, len(API_KEYS))):
        key_idx = (st.session_state.current_api_index + attempt) % len(API_KEYS)
        youtube = build('youtube', 'v3', developerKey=API_KEYS[key_idx])
        try:
            params = {
                'q': artist,
                'part': 'snippet',
                'type': 'video',
                'order': 'relevance',
                'maxResults': min(50, max(10, max_results)),
            }
            if region_code:
                params['regionCode'] = region_code
            if published_after:
                params['publishedAfter'] = published_after

            res = youtube.search().list(**params).execute()
            items = res.get('items', [])
            result_estimate = int(res.get('pageInfo', {}).get('totalResults', 0) or 0)

            ids = []
            discovery = {}
            for item in items:
                vid = item.get('id', {}).get('videoId')
                if vid:
                    ids.append(vid)
                    discovery[vid] = 'relevance'

            ids = list(dict.fromkeys(ids))[:50]
            if not ids:
                st.session_state.current_api_index = key_idx
                return {
                    'artist': artist,
                    'search_results_estimate': result_estimate,
                    'videos_found': 0,
                    'recent_videos': 0,
                    'total_views': 0,
                    'avg_views': 0,
                    'median_views': 0,
                    'avg_vph': 0,
                    'engagement_rate': 0,
                    'longform_count': 0,
                    'shorts_like_count': 0,
                    'freshness_presence': 0,
                    'freshness_days': freshness_days,
                    'error': None,
                }

            stats = youtube.videos().list(
                id=','.join(ids),
                part='snippet,statistics,contentDetails'
            ).execute()

            videos = []
            now = datetime.utcnow()
            for v in stats.get('items', []):
                sn = v.get('snippet', {})
                stt = v.get('statistics', {})
                cd = v.get('contentDetails', {})
                published = sn.get('publishedAt', '')
                try:
                    dt = parse_yt_date(published)
                    age_h = max((now - dt).total_seconds() / 3600, 0.1)
                except Exception:
                    age_h = 999999

                views = int(stt.get('viewCount', 0) or 0)
                likes = int(stt.get('likeCount', 0) or 0)
                comments = int(stt.get('commentCount', 0) or 0)
                duration_s = parse_iso_duration_seconds(cd.get('duration', 'PT0S'))
                videos.append({
                    'id': v.get('id'),
                    'views': views,
                    'likes': likes,
                    'comments': comments,
                    'age_h': age_h,
                    'duration_s': duration_s,
                    'vph': views / max(age_h, 1),
                    'source': discovery.get(v.get('id'), 'relevance')
                })

            views = [v['views'] for v in videos]
            vphs = [v['vph'] for v in videos]
            engagements = [((v['likes'] + v['comments']) / max(v['views'], 1)) * 100 for v in videos]
            recent = [v for v in videos if v['age_h'] <= 24 * min(freshness_days, 7)]
            longform = [v for v in videos if v['duration_s'] >= 240 and v['duration_s'] > 0]
            shorts_like = [v for v in videos if 0 < v['duration_s'] <= 60]

            freshness_presence = len(recent) / max(len(videos), 1) * 100
            avg_views = statistics.mean(views) if views else 0
            median_views = statistics.median(views) if views else 0
            avg_vph = statistics.mean(vphs) if vphs else 0
            er = statistics.mean(engagements) if engagements else 0

            st.session_state.current_api_index = key_idx
            return {
                'artist': artist,
                'search_results_estimate': result_estimate,
                'videos_found': len(videos),
                'recent_videos': len(recent),
                'total_views': sum(views),
                'avg_views': avg_views,
                'median_views': median_views,
                'avg_vph': avg_vph,
                'engagement_rate': er,
                'longform_count': len(longform),
                'shorts_like_count': len(shorts_like),
                'freshness_presence': freshness_presence,
                'freshness_days': freshness_days,
                'error': None,
            }
        except Exception as e:
            last_error = str(e)
            low = last_error.lower()
            if 'quota' in low or '403' in low or 'daily limit' in low or 'exceeded' in low:
                continue
            return {
                'artist': artist,
                'error': last_error,
                'search_results_estimate': 0,
                'videos_found': 0,
                'recent_videos': 0,
            }

    return {
        'artist': artist,
        'error': last_error or 'Periksa kunci, izin API, atau kuota proyek.',
        'search_results_estimate': 0,
        'videos_found': 0,
        'recent_videos': 0,
    }

def normalize_artist_comparison(rows):
    valid = [r for r in rows if not r.get('error')]
    if not valid:
        return rows
    metrics = ['recent_videos', 'total_views', 'median_views', 'avg_vph', 'engagement_rate', 'longform_count']
    for r in valid:
        components = []
        for key in metrics:
            vals = [float(x.get(key, 0) or 0) for x in valid]
            lo, hi = min(vals), max(vals)
            value = float(r.get(key, 0) or 0)
            if hi == lo:
                score = 50.0
            else:
                score = (value - lo) / (hi - lo) * 100
            components.append(score)
        # Search-result estimate is deliberately shown as context, not treated as search volume.
        r['youtube_interest_score'] = round(
            components[0] * 0.20 + components[1] * 0.20 + components[2] * 0.15 +
            components[3] * 0.20 + components[4] * 0.10 + components[5] * 0.15, 1
        )
    return sorted(rows, key=lambda x: x.get('youtube_interest_score', -1), reverse=True)



from modules.simple_ui import render_app

render_app(globals())
