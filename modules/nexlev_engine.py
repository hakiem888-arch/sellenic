"""Nexlev.io-inspired research, monetization, thumbnail, transcript, and productivity engines.

All functions are pure or operate on in-memory data/images without hidden network calls.
"""
import io
import math
import re
import statistics
from collections import Counter
from datetime import datetime, timezone

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image, ImageStat

from modules.growth_engine import gap_candidates, parse_chapters, words
from modules.intelligence import age_hours, comparable_baseline, lifetime_vph, number, unique_videos


AFFILIATE_PATTERNS = (
    'shopee', 'tokopedia', 'lazada', 'tiktokshop', 'amzn.to', 'amazon.com',
    'saweria', 'trakteer', 'sociabuzz', 'patreon', 'ko-fi', 'gumroad',
    'lynkid', 'linktr.ee', 'beacons.ai', 'bit.ly', 's.id', 'wa.me',
    'sponsor', 'endorse', 'business inquiries', 'kerjasama', 'affiliate',
    'diskon', 'kode voucher', 'promo', 'membership', 'gabung channel'
)

FILLER_WORDS = {
    'eee', 'umm', 'ehm', 'anu', 'kayak', 'gitu', 'kan',
    'jadi', 'terus', 'nah', 'oke', 'guys',
    'basically', 'literally', 'actually'
}

HOOK_PROMISE_WORDS = {
    'cara', 'rahasia', 'bukti', 'hasil', 'mengapa', 'kenapa', 'ternyata',
    'jangan', 'kesalahan', 'cepat', 'mudah', 'fakta', 'terbongkar',
    'how', 'why', 'secret', 'result', 'proven', 'mistake', 'never', 'truth'
}

WEAK_INTRO_PHRASES = (
    'halo semuanya', 'halo guys', 'selamat datang kembali', 'kembali lagi di channel',
    'jangan lupa subscribe', 'jangan lupa like', 'sebelum mulai', 'welcome back to my channel'
)


def _parse_int(val, default=0):
    if isinstance(val, (int, float)) and math.isfinite(val):
        return int(val)
    if isinstance(val, str):
        s = val.strip().upper().replace(',', '')
        try:
            if s.endswith('M'):
                return int(float(s[:-1]) * 1_000_000)
            if s.endswith('K'):
                return int(float(s[:-1]) * 1_000)
            return int(float(s))
        except ValueError:
            return default
    return default


def _format_mmss(seconds):
    seconds = max(0, int(round(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"


# ==============================================================================
# 1. MONETIZATION STATUS CHECKER (Video & Channel)
# ==============================================================================
def check_monetization_status(entity, kind='video'):
    """Evaluate public monetization eligibility & commercial indicators for a video or channel."""
    if not isinstance(entity, dict):
        raise ValueError('Data video atau channel tidak valid.')
    subs = _parse_int(entity.get('raw_subs', entity.get('subs', 0)))
    views = _parse_int(entity.get('raw_views', entity.get('raw_total_views', entity.get('views', entity.get('total_views', 0)))))
    video_count = _parse_int(entity.get('raw_videos', entity.get('video_count', entity.get('videos', 1))))
    duration_sec = _parse_int(entity.get('duration_seconds', 0))
    made_for_kids = bool(entity.get('made_for_kids', False))
    license_type = str(entity.get('license', 'youtube') or 'youtube')
    description = str(entity.get('description', '') or '')
    title = str(entity.get('title', '') or '')
    combined_text = (title + '\n' + description).lower()

    found_markers = [marker for marker in AFFILIATE_PATTERNS if marker in combined_text]
    urls = re.findall(r'https?://[^\s<>"]+', description)

    signals = []
    score = 0

    if subs >= 1000:
        score += 45
        signals.append({
            'Indikator': 'Ambang Subscriber YPP (≥1.000)',
            'Status': 'Memenuhi',
            'Detail': f'{subs:,} subscriber (memenuhi syarat bagi hasil iklan YouTube Partner Program).'
        })
    elif subs >= 500:
        score += 25
        signals.append({
            'Indikator': 'Ambang Subscriber YPP Awal (≥500)',
            'Status': 'Tahap Awal',
            'Detail': f'{subs:,} subscriber (memenuhi tingkat fan funding/membership, belum 1.000 subscriber).'
        })
    else:
        signals.append({
            'Indikator': 'Ambang Subscriber YPP',
            'Status': 'Belum Memenuhi / Tersembunyi',
            'Detail': f'{subs:,} subscriber teramati (di bawah ambang 1.000 subscriber YPP standar).'
        })

    view_threshold = 100_000 if kind == 'channel' else 4_000
    if views >= view_threshold:
        score += 25
        signals.append({
            'Indikator': 'Volume Penayangan Publik',
            'Status': 'Kuat',
            'Detail': f'{views:,} views menunjukkan akumulasi jam tayang publik yang aktif.'
        })
    elif views >= 1_000:
        score += 12
        signals.append({
            'Indikator': 'Volume Penayangan Publik',
            'Status': 'Sedang',
            'Detail': f'{views:,} views tercatat pada sampel publik.'
        })
    else:
        signals.append({
            'Indikator': 'Volume Penayangan Publik',
            'Status': 'Rendah',
            'Detail': f'{views:,} views (masih membangun jam tayang publik).'
        })

    if found_markers or len(urls) >= 2:
        score += 20
        markers_str = ', '.join(found_markers[:5]) if found_markers else f'{len(urls)} tautan eksternal'
        signals.append({
            'Indikator': 'Jejak Monetisasi Eksternal / Afiliasi',
            'Status': 'Terdeteksi',
            'Detail': f'Indikator komersial ditemukan: {markers_str}.'
        })
    else:
        signals.append({
            'Indikator': 'Jejak Monetisasi Eksternal / Afiliasi',
            'Status': 'Tidak Terdeteksi',
            'Detail': 'Tidak ditemukan tautan afiliasi, sponsor, atau donasi pada deskripsi yang diperiksa.'
        })

    if kind == 'video':
        if duration_sec >= 480:
            score += 10
            signals.append({
                'Indikator': 'Kelayakan Mid-Roll Ads (≥8 Menit)',
                'Status': 'Memenuhi (Mid-Roll Aktif)',
                'Detail': f'Durasi {_format_mmss(duration_sec)} memungkinkan penempatan iklan mid-roll.'
            })
        elif duration_sec > 60:
            score += 6
            signals.append({
                'Indikator': 'Kelayakan Format Iklan',
                'Status': 'Pre/Post-Roll Standar',
                'Detail': f'Durasi {_format_mmss(duration_sec)} (<8 menit; hanya iklan sebelum/sesudah video).'
            })
        elif duration_sec > 0:
            score += 4
            signals.append({
                'Indikator': 'Kelayakan Format Iklan',
                'Status': 'Shorts Feed Pool',
                'Detail': f'Durasi {_format_mmss(duration_sec)} (≤60 detik; mengikuti skema bagi hasil Shorts).'
            })
    else:
        if video_count >= 15:
            score += 10
            signals.append({
                'Indikator': 'Konsistensi Katalog Video',
                'Status': 'Aktif',
                'Detail': f'{video_count:,} video publik mendukung akumulasi jam tayang.'
            })

    if made_for_kids:
        score = max(10, score - 25)
        signals.append({
            'Indikator': 'Status Made for Kids',
            'Status': 'Iklan Terbatas',
            'Detail': 'Konten anak-anak menonaktifkan iklan terpersonalisasi, komentar, dan info card.'
        })
    if license_type == 'creativeCommon':
        signals.append({
            'Indikator': 'Lisensi Video',
            'Status': 'Creative Commons',
            'Detail': 'Mengizinkan penggunaan ulang; periksa keaslian konten untuk kelayakan YPP.'
        })

    score = min(100, max(0, score))
    if made_for_kids and subs >= 1000:
        label = 'Monetisasi Terbatas (Made for Kids)'
    elif subs >= 1000 and score >= 65:
        label = 'Berpotensi Kuat Dimonetisasi (YPP Eligible)'
    elif subs >= 1000 or found_markers:
        label = 'Indikasi Monetisasi Aktif / Afiliasi'
    elif subs >= 500:
        label = 'Tahap Awal YPP (Fan Funding / 500+ Subs)'
    else:
        label = 'Di Bawah Ambang YPP / Belum Terverifikasi'

    return {
        'status_label': label,
        'ypp_eligible': subs >= 1000,
        'early_ypp_eligible': subs >= 500,
        'midroll_eligible': duration_sec >= 480 if kind == 'video' else None,
        'made_for_kids': made_for_kids,
        'score': score,
        'subscribers': subs,
        'views': views,
        'affiliate_markers': found_markers,
        'external_links_count': len(urls),
        'signals': signals,
        'basis': 'Heuristik indikator publik (ambang subscriber YPP, volume views, durasi iklan mid-roll, dan tautan komersial). YouTube Data API publik tidak mengekspos status kontrak AdSense internal.'
    }


# ==============================================================================
# 2. VIDEOS SORT BY POPULARITY (Channel Video Sorter & Outlier Enricher)
# ==============================================================================
def sort_channel_videos(videos, sort_by='Terpopuler (Views Tertinggi)', now=None):
    """Enrich channel videos with VPH, Outlier score vs channel median, and sort."""
    if not videos:
        return []
    now = now or datetime.now(timezone.utc)
    raw_views_list = [_parse_int(v.get('raw_views', v.get('views', 0))) for v in videos]
    median_views = statistics.median(raw_views_list) if raw_views_list else 0

    enriched = []
    for v in videos:
        item = dict(v)
        rv = _parse_int(item.get('raw_views', item.get('views', 0)))
        item['raw_views'] = rv
        vph_val = lifetime_vph(item, now)
        if vph_val is None:
            vph_val = float(item.get('vph', 0) or 0)
        item['vph_calculated'] = round(vph_val, 2)
        base = comparable_baseline(item, videos, now)
        if base.get('multiple') is not None:
            outlier_mult = round(base['multiple'], 2)
        elif median_views > 0:
            outlier_mult = round(rv / median_views, 2)
        else:
            outlier_mult = 1.0
        item['outlier_multiple'] = outlier_mult
        enriched.append(item)

    key_map = {
        'Terpopuler (Views Tertinggi)': lambda x: (x['raw_views'], x['vph_calculated']),
        'popularity': lambda x: (x['raw_views'], x['vph_calculated']),
        'VPH Tertinggi': lambda x: (x['vph_calculated'], x['raw_views']),
        'vph': lambda x: (x['vph_calculated'], x['raw_views']),
        'Outlier Score Tertinggi': lambda x: (x['outlier_multiple'], x['raw_views']),
        'outlier': lambda x: (x['outlier_multiple'], x['raw_views']),
        'Terbaru': lambda x: str(x.get('published_full', x.get('date', ''))),
        'newest': lambda x: str(x.get('published_full', x.get('date', ''))),
        'Terlama': lambda x: str(x.get('published_full', x.get('date', ''))),
        'oldest': lambda x: str(x.get('published_full', x.get('date', ''))),
    }
    reverse = sort_by not in ('Terlama', 'oldest')
    sorter = key_map.get(sort_by, key_map['Terpopuler (Views Tertinggi)'])
    return sorted(enriched, key=sorter, reverse=reverse)


# ==============================================================================
# 3. THUMBNAIL COMPRESSOR (Auto-compress under YouTube 2MB limit without losing HD)
# ==============================================================================
def compress_thumbnail(image_bytes, max_bytes=2_000_000, target_resolution=(1280, 720), output_format='JPEG'):
    """Compress a thumbnail image to stay strictly below max_bytes (default <2MB YouTube limit)."""
    if not image_bytes:
        raise ValueError('Data gambar kosong.')
    max_bytes = max(20_000, int(max_bytes))
    output_format = output_format.upper()
    if output_format not in ('JPEG', 'WEBP', 'PNG'):
        raise ValueError('Format keluaran harus JPEG, WEBP, atau PNG.')

    img = Image.open(io.BytesIO(image_bytes))
    orig_w, orig_h = img.size

    if target_resolution and (orig_w > target_resolution[0] or orig_h > target_resolution[1]):
        img = img.copy()
        img.thumbnail(target_resolution, Image.Resampling.LANCZOS)

    if output_format in ('JPEG', 'WEBP') and img.mode in ('RGBA', 'LA', 'P'):
        bg = Image.new('RGB', img.size, (15, 23, 42))
        rgba = img.convert('RGBA')
        bg.paste(rgba, mask=rgba.split()[3])
        working = bg
    elif output_format == 'JPEG':
        working = img.convert('RGB')
    else:
        working = img.copy()

    best_bytes = None
    best_quality = 95

    if output_format == 'PNG':
        buf = io.BytesIO()
        working.save(buf, format='PNG', optimize=True)
        candidate = buf.getvalue()
        if len(candidate) <= max_bytes:
            best_bytes = candidate
            best_quality = 100
        else:
            for colors in (256, 128, 64):
                q_img = working.quantize(colors=colors)
                buf = io.BytesIO()
                q_img.save(buf, format='PNG', optimize=True)
                candidate = buf.getvalue()
                if len(candidate) <= max_bytes:
                    best_bytes = candidate
                    best_quality = colors
                    break
            if best_bytes is None:
                output_format = 'JPEG'
                working = working.convert('RGB')

    if best_bytes is None:
        for q in range(95, 19, -5):
            buf = io.BytesIO()
            save_kwargs = {'format': output_format, 'quality': q, 'optimize': True}
            if output_format == 'JPEG':
                save_kwargs['progressive'] = True
            working.save(buf, **save_kwargs)
            candidate = buf.getvalue()
            best_bytes = candidate
            best_quality = q
            if len(candidate) <= max_bytes:
                break

        scale = 0.9
        while len(best_bytes) > max_bytes and scale >= 0.4:
            scaled_w = max(320, int(working.width * scale))
            scaled_h = max(180, int(working.height * scale))
            resized = working.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            resized.save(buf, format=output_format, quality=75, optimize=True)
            best_bytes = buf.getvalue()
            working = resized
            scale -= 0.15

    orig_len = len(image_bytes)
    comp_len = len(best_bytes)
    reduction = round((1 - comp_len / orig_len) * 100, 1) if orig_len > 0 else 0.0

    return {
        'data': best_bytes,
        'original_bytes': orig_len,
        'compressed_bytes': comp_len,
        'reduction_pct': reduction,
        'original_size': (orig_w, orig_h),
        'final_size': working.size,
        'quality': best_quality,
        'format': output_format,
        'under_youtube_limit': comp_len <= 2_097_152,
        'under_target': comp_len <= max_bytes,
    }


# ==============================================================================
# 4. SIMILAR THUMBNAIL SEARCH (Visual Perceptual Hash + Color Histogram)
# ==============================================================================
def thumbnail_signature(image_bytes):
    """Extract perceptual average hash, color histogram, and luminance stats."""
    img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    stat = ImageStat.Stat(img)
    r_mean, g_mean, b_mean = stat.mean
    r_std, g_std, b_std = stat.stddev
    brightness = round(0.299 * r_mean + 0.587 * g_mean + 0.114 * b_mean, 1)
    contrast = round((r_std + g_std + b_std) / 3.0, 1)

    gray_8 = img.convert('L').resize((8, 8), Image.Resampling.LANCZOS)
    pixels = list(gray_8.getdata())
    avg_px = sum(pixels) / 64.0
    ahash_bits = [1 if px >= avg_px else 0 for px in pixels]

    small_rgb = img.resize((32, 32), Image.Resampling.LANCZOS)
    hist_raw = small_rgb.histogram()
    bins_24 = []
    for ch in range(3):
        ch_slice = hist_raw[ch * 256:(ch + 1) * 256]
        for b in range(8):
            bins_24.append(sum(ch_slice[b * 32:(b + 1) * 32]) / 1024.0)

    dominant_hex = f"#{int(r_mean):02x}{int(g_mean):02x}{int(b_mean):02x}"
    return {
        'ahash': ahash_bits,
        'hist24': bins_24,
        'brightness': brightness,
        'contrast': contrast,
        'dominant_hex': dominant_hex,
        'size': img.size,
    }


def thumbnail_similarity(sig_a, sig_b):
    """Compute visual similarity score (0-100) between two thumbnail signatures."""
    hamming = sum(a != b for a, b in zip(sig_a['ahash'], sig_b['ahash']))
    hash_sim = max(0.0, (64 - hamming) / 64.0) * 100.0

    l1_diff = sum(abs(a - b) for a, b in zip(sig_a['hist24'], sig_b['hist24']))
    color_sim = max(0.0, (1.0 - l1_diff / 6.0)) * 100.0

    bright_diff = abs(sig_a['brightness'] - sig_b['brightness']) / 255.0
    contrast_diff = abs(sig_a['contrast'] - sig_b['contrast']) / 128.0
    tone_sim = max(0.0, (1.0 - (bright_diff * 0.6 + min(1.0, contrast_diff) * 0.4))) * 100.0

    overall = round(0.45 * hash_sim + 0.35 * color_sim + 0.20 * tone_sim, 1)
    return {
        'similarity_pct': overall,
        'structure_similarity_pct': round(hash_sim, 1),
        'color_similarity_pct': round(color_sim, 1),
        'tone_similarity_pct': round(tone_sim, 1),
    }


def rank_similar_thumbnails(reference_bytes, candidates):
    """Rank candidate videos [{'video': dict, 'image_bytes': bytes}] by visual similarity."""
    ref_sig = thumbnail_signature(reference_bytes)
    ranked = []
    for item in candidates:
        img_bytes = item.get('image_bytes')
        if not img_bytes:
            continue
        try:
            cand_sig = thumbnail_signature(img_bytes)
            sim = thumbnail_similarity(ref_sig, cand_sig)
            video = item.get('video', {})
            ranked.append({
                'video': video,
                'title': video.get('title', 'Untitled'),
                'channel': video.get('channel', ''),
                'views_fmt': video.get('views_fmt', str(video.get('views', 0))),
                'vph': video.get('vph', 0),
                'thumbnail': video.get('thumbnail', ''),
                'link': video.get('link', ''),
                'dominant_hex': cand_sig['dominant_hex'],
                'brightness': cand_sig['brightness'],
                'contrast': cand_sig['contrast'],
                **sim,
            })
        except Exception:
            continue
    return {
        'reference_signature': ref_sig,
        'results': sorted(ranked, key=lambda x: x['similarity_pct'], reverse=True),
    }


# ==============================================================================
# 5. TRANSCRIPT ANALYSIS (Hook, Pacing WPM, Structure, Phrases, Chapters)
# ==============================================================================
def analyze_transcript(transcript_text, target_keyword='', duration_seconds=0):
    """Comprehensive transcript analysis: hook score, speaking rate (WPM), structure, filler words, and chapters."""
    text = str(transcript_text or '').strip()
    if not text:
        raise ValueError('Masukkan teks transkrip untuk dianalisis.')

    clean_lines = [re.sub(r'^\s*\[?\d{1,2}:\d{2}(?::\d{2})?\]?\s*', '', line).strip()
                   for line in text.splitlines() if line.strip()]
    clean_text = ' '.join(clean_lines)
    all_tokens = re.findall(r'[^\W_]+', clean_text.lower(), re.UNICODE)
    total_words = len(all_tokens)
    if total_words == 0:
        raise ValueError('Transkrip tidak mengandung kata yang dapat dianalisis.')

    sentences = [s.strip() for s in re.split(r'[.!?]+', clean_text) if s.strip()]
    sentence_count = max(1, len(sentences))

    inferred_duration = _parse_int(duration_seconds)
    if inferred_duration <= 0:
        stamps = re.findall(r'\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b', text)
        max_sec = 0
        for h_or_m, m_or_s, s_opt in stamps:
            if s_opt:
                sec = int(h_or_m) * 3600 + int(m_or_s) * 60 + int(s_opt)
            else:
                sec = int(h_or_m) * 60 + int(m_or_s)
            if sec > max_sec:
                max_sec = sec
        inferred_duration = max_sec + 30 if max_sec > 0 else int(round(total_words / 140.0 * 60))

    minutes = max(inferred_duration / 60.0, 0.25)
    wpm = round(total_words / minutes, 1)
    if 125 <= wpm <= 165:
        pace_label = 'Ideal (125–165 kata/menit)'
    elif wpm < 125:
        pace_label = 'Lambat (<125 kata/menit — berisiko menurunkan retensi awal)'
    else:
        pace_label = 'Cepat (>165 kata/menit — cocok untuk konten padat/Shorts, beri jeda visual)'

    hook_tokens = all_tokens[:75]
    hook_text = ' '.join(clean_text.split()[:75])
    hook_lower = hook_text.lower()
    target_tokens = set(words(target_keyword))
    keyword_in_hook = bool(target_tokens and (target_tokens & set(hook_tokens)))
    promise_hits = sorted(set(hook_tokens) & HOOK_PROMISE_WORDS)
    has_question = '?' in ' '.join(clean_lines[:3]) or any(w in hook_tokens for w in ('apakah', 'mengapa', 'kenapa', 'bagaimana', 'pernahkah', 'why', 'how', 'what'))
    weak_intro_hits = [p for p in WEAK_INTRO_PHRASES if p in hook_lower]

    hook_score = 50
    hook_feedback = []
    if keyword_in_hook:
        hook_score += 20
        hook_feedback.append('Kata kunci utama muncul di 30 detik pertama.')
    elif target_keyword:
        hook_score -= 10
        hook_feedback.append('Kata kunci target belum terdengar di 75 kata pertama.')

    if promise_hits:
        hook_score += 15
        hook_feedback.append(f'Mengandung kata pemicu rasa ingin tahu/hasil: {", ".join(promise_hits[:4])}.')
    else:
        hook_feedback.append('Tambahkan janji hasil atau masalah spesifik di kalimat pembuka.')

    if has_question:
        hook_score += 15
        hook_feedback.append('Menggunakan pertanyaan pembuka (open loop) untuk menahan penonton.')

    if weak_intro_hits:
        hook_score -= 20
        hook_feedback.append(f'Hindari basa-basi pembuka yang terlalu panjang ({", ".join(weak_intro_hits)}).')

    hook_score = max(0, min(100, hook_score))

    quarter_size = max(1, math.ceil(total_words / 4))
    quarters = []
    labels = ['0–25% (Hook & Setup)', '25–50% (Pengembangan Inti)', '50–75% (Pendalaman & Bukti)', '75–100% (Klimaks & Penutup)']
    for idx, q_label in enumerate(labels):
        chunk = all_tokens[idx * quarter_size:(idx + 1) * quarter_size]
        if not chunk:
            continue
        top_chunk = [w for w, _ in Counter(w for w in chunk if w not in FILLER_WORDS and len(w) > 3).most_common(4)]
        quarters.append({
            'Segmen': q_label,
            'Jumlah Kata': len(chunk),
            'Fokus Kata': ', '.join(top_chunk) or '-'
        })

    filler_counts = Counter(w for w in all_tokens if w in FILLER_WORDS)
    filler_total = sum(filler_counts.values())
    filler_pct = round(filler_total / total_words * 100, 1)

    meaningful = [w for w in words(clean_text) if w not in FILLER_WORDS]
    top_keywords = [{'Kata': k, 'Frekuensi': v} for k, v in Counter(meaningful).most_common(15)]
    phrases_2 = Counter(' '.join(meaningful[i:i + 2]) for i in range(max(0, len(meaningful) - 1)))
    top_phrases = [{'Frasa': k, 'Frekuensi': v} for k, v in phrases_2.most_common(12) if v >= 2]

    chapters, chapter_note = parse_chapters(text)

    return {
        'total_words': total_words,
        'unique_words': len(set(all_tokens)),
        'sentence_count': sentence_count,
        'avg_words_per_sentence': round(total_words / sentence_count, 1),
        'duration_seconds': inferred_duration,
        'duration_formatted': _format_mmss(inferred_duration),
        'wpm': wpm,
        'pace_label': pace_label,
        'hook_score': hook_score,
        'hook_excerpt': hook_text,
        'hook_feedback': hook_feedback,
        'keyword_in_hook': keyword_in_hook,
        'filler_count': filler_total,
        'filler_pct': filler_pct,
        'top_fillers': [{'Kata Filler': k, 'Jumlah': v} for k, v in filler_counts.most_common(8)],
        'top_keywords': top_keywords,
        'top_phrases': top_phrases,
        'quarters': quarters,
        'chapters': chapters,
        'chapter_note': chapter_note,
    }


# ==============================================================================
# 6. SIMILAR CHANNELS FINDER
# ==============================================================================
def extract_channel_dna_queries(channel_data, max_queries=3):
    """Extract search queries representing a reference channel's core niche & topics."""
    tags = [t[0] if isinstance(t, (list, tuple)) else str(t) for t in channel_data.get('top_seo_tags', [])]
    titles = [v.get('title', '') for v in channel_data.get('recent_videos', [])]
    token_counts = Counter(words(' '.join(tags[:10]) + ' ' + ' '.join(titles)))
    top_words = [w for w, _ in token_counts.most_common(8) if len(w) > 2]

    queries = []
    if tags:
        queries.append(tags[0])
    if len(top_words) >= 2:
        queries.append(' '.join(top_words[:2]))
    if len(top_words) >= 4:
        queries.append(' '.join(top_words[2:4]))
    if not queries and channel_data.get('title'):
        queries.append(channel_data['title'])
    return list(dict.fromkeys(q.strip() for q in queries if q.strip()))[:max_queries]


def score_similar_channels(reference_channel, candidates):
    """Score and rank candidate channels by similarity to a reference channel."""
    ref_id = reference_channel.get('id', '')
    ref_subs = max(1, _parse_int(reference_channel.get('raw_subs', reference_channel.get('subs', 0))))
    ref_views = max(1, _parse_int(reference_channel.get('raw_total_views', reference_channel.get('total_views', 0))))
    ref_videos = max(1, _parse_int(reference_channel.get('raw_videos', reference_channel.get('video_count', reference_channel.get('videos', 1)))))
    ref_avg_views = ref_views / ref_videos

    ref_tags = [t[0] if isinstance(t, (list, tuple)) else str(t) for t in reference_channel.get('top_seo_tags', [])]
    ref_titles = [v.get('title', '') for v in reference_channel.get('recent_videos', [])]
    ref_tokens = set(words(reference_channel.get('title', '') + ' ' + ' '.join(ref_tags) + ' ' + ' '.join(ref_titles)))

    ranked = []
    seen = {ref_id} if ref_id else set()
    for ch in candidates:
        cid = ch.get('id', '')
        if not cid or cid in seen:
            continue
        seen.add(cid)

        c_subs = max(1, _parse_int(ch.get('raw_subs', ch.get('subs', 0))))
        c_views = max(1, _parse_int(ch.get('raw_total_views', ch.get('total_views', 0))))
        c_videos = max(1, _parse_int(ch.get('raw_videos', ch.get('videos', 1))))
        c_avg_views = _parse_int(ch.get('avg_views', 0)) or (c_views / c_videos)

        c_tokens = set(words(ch.get('title', '') + ' ' + str(ch.get('custom_url', '')) + ' ' + str(ch.get('matched_query', ''))))
        overlap = len(ref_tokens & c_tokens) / max(1, min(len(ref_tokens), max(3, len(c_tokens)))) if ref_tokens else 0.5
        topic_score = min(100.0, overlap * 100.0 + (25.0 if ch.get('matched_query') else 0.0))

        sub_dist = abs(math.log10(ref_subs) - math.log10(c_subs))
        sub_score = max(0.0, 100.0 - sub_dist * 35.0)

        view_dist = abs(math.log10(max(1, ref_avg_views)) - math.log10(max(1, c_avg_views)))
        view_score = max(0.0, 100.0 - view_dist * 35.0)

        vid_dist = abs(math.log10(ref_videos) - math.log10(c_videos))
        vid_score = max(0.0, 100.0 - vid_dist * 40.0)

        total_sim = round(0.45 * topic_score + 0.25 * sub_score + 0.15 * view_score + 0.15 * vid_score, 1)
        reasons = []
        if ch.get('matched_query'):
            reasons.append(f"Topik: {ch['matched_query']}")
        if sub_score >= 70:
            reasons.append('Ukuran subscriber sebanding')
        if view_score >= 70:
            reasons.append('Rerata views/video sebanding')
        if not reasons:
            reasons.append('Kandidat dalam topik pencarian yang sama')

        ranked.append({
            **ch,
            'similarity_score': total_sim,
            'topic_score': round(topic_score, 1),
            'subscriber_similarity': round(sub_score, 1),
            'match_reasons': ' · '.join(reasons),
        })

    return sorted(ranked, key=lambda x: x['similarity_score'], reverse=True)


# ==============================================================================
# 7. ADVANCED HOMEPAGE / FEED FILTER
# ==============================================================================
def apply_advanced_homepage_filter(
    videos,
    min_views=0,
    max_views=0,
    min_subs=0,
    max_subs=0,
    min_vph=0,
    min_outlier_ratio=0.0,
    min_duration_minutes=0.0,
    max_duration_minutes=0.0,
    max_age_days=0,
    exclude_shorts=False,
    keyword_include='',
    keyword_exclude='',
    now=None
):
    """Filter a video feed by granular subscriber, VPH, outlier ratio, duration, age, and keyword criteria."""
    now = now or datetime.now(timezone.utc)
    inc_words = [w.strip().lower() for w in str(keyword_include or '').split(',') if w.strip()]
    exc_words = [w.strip().lower() for w in str(keyword_exclude or '').split(',') if w.strip()]

    filtered = []
    for v in videos:
        views = _parse_int(v.get('raw_views', v.get('views', 0)))
        subs = _parse_int(v.get('raw_subs', v.get('subs', 0)))
        vph = float(v.get('vph', v.get('velocity_vph', 0)) or 0)
        ratio = float(v.get('ratio', v.get('channel_breakout_multiple', 0)) or 0)
        dur_sec = _parse_int(v.get('duration_seconds', 0))
        dur_min = dur_sec / 60.0
        age_h = age_hours(v, now)

        if min_views > 0 and views < min_views:
            continue
        if max_views > 0 and views > max_views:
            continue
        if min_subs > 0 and subs < min_subs:
            continue
        if max_subs > 0 and subs > max_subs:
            continue
        if min_vph > 0 and vph < min_vph:
            continue
        if min_outlier_ratio > 0 and ratio < min_outlier_ratio:
            continue
        if min_duration_minutes > 0 and dur_min < min_duration_minutes:
            continue
        if max_duration_minutes > 0 and dur_min > max_duration_minutes:
            continue
        if max_age_days > 0 and age_h is not None and age_h > max_age_days * 24:
            continue
        if exclude_shorts and (0 < dur_sec <= 180 or '#shorts' in (v.get('title', '') + ' ' + v.get('description', '')).lower()):
            continue

        haystack = (str(v.get('title', '')) + ' ' + str(v.get('channel', '')) + ' ' + str(v.get('description', ''))).lower()
        if inc_words and not all(w in haystack for w in inc_words):
            continue
        if exc_words and any(w in haystack for w in exc_words):
            continue

        filtered.append(v)
    return filtered


# ==============================================================================
# 8. NICHE OVERVIEW & NICHE FINDER
# ==============================================================================
def compute_niche_overview(niche_query, videos, own_subscribers=None, rpm_low=1.5, rpm_high=4.0, now=None):
    """Generate a holistic Niche Overview scorecard, sub-niche ideas, and exportable dataset."""
    rows = unique_videos(videos)
    now = now or datetime.now(timezone.utc)
    if not rows:
        return {
            'niche': niche_query,
            'sample_size': 0,
            'niche_score': None,
            'verdict': 'Data belum tersedia',
            'summary': {},
            'top_channels': [],
            'outlier_videos': [],
            'sub_niches': [],
        }

    views_list = [_parse_int(r.get('raw_views', r.get('views', 0))) for r in rows]
    subs_list = [_parse_int(r.get('raw_subs', r.get('subs', 0))) for r in rows if r.get('subscriber_known', True)]
    vph_list = [r_vph for r in rows if (r_vph := lifetime_vph(r, now)) is not None]
    if not vph_list:
        vph_list = [float(r.get('vph', 0) or 0) for r in rows]
    er_list = [float(r.get('er', 0) or 0) for r in rows]
    ratios = [float(r.get('ratio', 0) or 0) for r in rows]
    durations = [_parse_int(r.get('duration_seconds', 0)) for r in rows]

    total_views = sum(views_list)
    median_views = statistics.median(views_list) if views_list else 0
    avg_views = statistics.mean(views_list) if views_list else 0
    median_vph = statistics.median(vph_list) if vph_list else 0
    median_subs = statistics.median(subs_list) if subs_list else 0
    avg_er = statistics.mean(er_list) if er_list else 0

    small_gems = [
        r for r in rows
        if 0 < _parse_int(r.get('raw_subs', r.get('subs', 0))) <= 50_000
        and (float(r.get('ratio', 0) or 0) >= 1.5 or _parse_int(r.get('raw_views', r.get('views', 0))) >= median_views)
    ]
    outlier_videos = sorted(rows, key=lambda x: (float(x.get('ratio', 0) or 0), _parse_int(x.get('raw_views', 0))), reverse=True)
    midroll_ready_pct = sum(1 for d in durations if d >= 480) / len(rows) * 100.0
    fresh_30d_pct = sum(1 for r in rows if (ah := age_hours(r, now)) is not None and ah <= 24 * 30) / len(rows) * 100.0
    small_channel_win_pct = len(small_gems) / len(rows) * 100.0

    channels_counter = Counter(r.get('channel') or r.get('channel_id') for r in rows if r.get('channel') or r.get('channel_id'))
    diversity_pct = max(0.0, 100.0 - (max(channels_counter.values()) / len(rows) * 100.0)) if channels_counter else 50.0

    demand_score = min(100.0, math.log10(1 + max(0, median_vph)) / 3.5 * 100.0)
    breakout_accessibility = min(100.0, small_channel_win_pct * 2.2 + (sum(1 for rt in ratios if rt >= 1.5) / len(rows) * 50.0))
    monetization_fit = min(100.0, midroll_ready_pct * 0.7 + min(30.0, avg_er * 6.0))
    competition_openness = round(0.6 * diversity_pct + 0.4 * fresh_30d_pct, 1)

    niche_score = round(
        0.35 * demand_score +
        0.30 * breakout_accessibility +
        0.20 * competition_openness +
        0.15 * monetization_fit,
        1
    )

    if own_subscribers and own_subscribers > 0 and subs_list:
        attainable_pct = sum(1 for s in subs_list if s <= own_subscribers * 2) / len(subs_list) * 100.0
        personal_niche_score = round(0.8 * niche_score + 0.2 * attainable_pct, 1)
    else:
        personal_niche_score = None

    if niche_score >= 75:
        verdict = 'Peluang Tinggi (High Momentum & Ramah Channel Kecil)'
    elif niche_score >= 55:
        verdict = 'Peluang Menengah (Potensial dengan Diferensiasi Angle)'
    else:
        verdict = 'Kompetitif / Momentum Terbatas (Perlu Sub-Niche Lebih Spesifik)'

    ch_groups = {}
    for r in rows:
        cid = r.get('channel_id') or r.get('channel', 'Unknown')
        entry = ch_groups.setdefault(cid, {
            'Channel': r.get('channel', cid),
            'Channel ID': r.get('channel_id', ''),
            'Subscriber': _parse_int(r.get('raw_subs', r.get('subs', 0))),
            'Video di Sampel': 0,
            'Total Views Sampel': 0,
            'Max VPH': 0,
        })
        entry['Video di Sampel'] += 1
        entry['Total Views Sampel'] += _parse_int(r.get('raw_views', r.get('views', 0)))
        entry['Max VPH'] = max(entry['Max VPH'], int(float(r.get('vph', 0) or 0)))

    top_channels = sorted(ch_groups.values(), key=lambda x: x['Total Views Sampel'], reverse=True)[:10]

    return {
        'niche': niche_query,
        'sample_size': len(rows),
        'niche_score': niche_score,
        'personal_niche_score': personal_niche_score,
        'verdict': verdict,
        'summary': {
            'total_sample_views': total_views,
            'median_views': int(median_views),
            'average_views': int(avg_views),
            'median_vph': round(median_vph, 1),
            'median_subscribers': int(median_subs),
            'avg_engagement_pct': round(avg_er, 2),
            'small_channel_gems_count': len(small_gems),
            'small_channel_win_pct': round(small_channel_win_pct, 1),
            'midroll_eligible_pct': round(midroll_ready_pct, 1),
            'fresh_30d_pct': round(fresh_30d_pct, 1),
            'estimated_rpm_range_usd': f"${rpm_low:.2f} – ${rpm_high:.2f}",
            'median_video_est_revenue_usd': f"${median_views / 1000 * rpm_low:,.2f} – ${median_views / 1000 * rpm_high:,.2f}",
        },
        'components': [
            {'Komponen': 'Momentum & Permintaan (VPH)', 'Skor': round(demand_score, 1), 'Bobot': '35%'},
            {'Komponen': 'Aksesibilitas Channel Kecil / Outlier', 'Skor': round(breakout_accessibility, 1), 'Bobot': '30%'},
            {'Komponen': 'Keragaman Channel & Kesegaran', 'Skor': round(competition_openness, 1), 'Bobot': '20%'},
            {'Komponen': 'Kesiapan Monetisasi (Mid-Roll & Engagement)', 'Skor': round(monetization_fit, 1), 'Bobot': '15%'},
        ],
        'top_channels': top_channels,
        'outlier_videos': outlier_videos[:10],
        'small_channel_gems': small_gems[:10],
        'sub_niches': gap_candidates(niche_query, rows),
    }


# ==============================================================================
# 9. AUTOMATIC AD PLACER (Mid-Roll Ad Timestamp Generator)
# ==============================================================================
def generate_midroll_ad_breaks(duration_seconds, transcript_text='', strategy='Seimbang', first_ad_seconds=90):
    """Automatically place mid-roll ads for videos >= 8 minutes (480s), snapping to natural pauses when available."""
    duration_seconds = _parse_int(duration_seconds)
    if duration_seconds <= 0:
        raise ValueError('Durasi video harus lebih dari 0 detik.')

    if duration_seconds < 480:
        return {
            'eligible': False,
            'duration_seconds': duration_seconds,
            'duration_formatted': _format_mmss(duration_seconds),
            'strategy': strategy,
            'placements': [],
            'studio_timestamps': '',
            'message': f'Durasi video {_format_mmss(duration_seconds)} masih di bawah 8 menit (480 detik). YouTube hanya mengizinkan iklan mid-roll pada video berdurasi minimal 08:00.',
        }

    interval_map = {
        'Konservatif (Setiap ~4 Menit)': 240,
        'Konservatif': 240,
        'Seimbang (Setiap ~3 Menit)': 180,
        'Seimbang': 180,
        'Agresif (Setiap ~2 Menit)': 120,
        'Agresif': 120,
    }
    step = interval_map.get(strategy, 180)
    first_ad = max(60, min(180, int(first_ad_seconds)))
    end_guard = max(first_ad + 30, duration_seconds - 45)

    natural_points = []
    for line in str(transcript_text or '').splitlines():
        m = re.match(r'^\s*\[?(\d{1,2}):(\d{2})(?::(\d{2}))?\]?\s*(.*)', line)
        if not m:
            continue
        if m.group(3) is not None:
            sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
        else:
            sec = int(m.group(1)) * 60 + int(m.group(2))
        label = (m.group(4) or 'Transisi bagian').strip()[:70]
        if first_ad - 20 <= sec <= end_guard:
            natural_points.append((sec, label))
    natural_points.sort(key=lambda x: x[0])

    placements = []
    target_t = first_ad
    last_placed = -999
    idx = 1

    while target_t <= end_guard:
        chosen_sec = target_t
        chosen_reason = 'Interval retensi optimal'
        for np_sec, np_label in natural_points:
            if abs(np_sec - target_t) <= 25 and np_sec - last_placed >= max(90, step - 30):
                chosen_sec = np_sec
                chosen_reason = f'Jeda transisi alami: "{np_label}"' if np_label else 'Jeda timestamp transkrip'
                break

        if chosen_sec - last_placed >= 60 and chosen_sec <= end_guard:
            placements.append({
                'Slot': f'Mid-Roll #{idx}',
                'Detik': chosen_sec,
                'Timestamp': _format_mmss(chosen_sec),
                'Jarak dari Sebelumnya': _format_mmss(chosen_sec - (0 if last_placed < 0 else last_placed)),
                'Alasan Penempatan': chosen_reason,
            })
            last_placed = chosen_sec
            idx += 1
        target_t = max(target_t + step, last_placed + step)

    return {
        'eligible': True,
        'duration_seconds': duration_seconds,
        'duration_formatted': _format_mmss(duration_seconds),
        'strategy': strategy,
        'interval_seconds': step,
        'ad_count': len(placements),
        'placements': placements,
        'studio_timestamps': ', '.join(p['Timestamp'] for p in placements),
        'message': f'{len(placements)} titik mid-roll berhasil disusun untuk durasi {_format_mmss(duration_seconds)}.',
    }


# ==============================================================================
# 10. NET PROFIT CALCULATOR (Channel & Faceless Production Economics)
# ==============================================================================
def calculate_net_profit(
    monthly_views,
    rpm,
    videos_per_month=4,
    cost_per_video=0.0,
    monthly_fixed_cost=0.0,
    sponsor_revenue=0.0,
    affiliate_revenue=0.0,
    tax_pct=0.0,
    rev_share_pct=0.0,
    currency='USD'
):
    """Calculate channel net profit, margins, ROI, and break-even views inside analytics."""
    vals = [monthly_views, rpm, videos_per_month, cost_per_video, monthly_fixed_cost, sponsor_revenue, affiliate_revenue, tax_pct, rev_share_pct]
    if any(number(v) is None for v in vals):
        raise ValueError('Semua nilai input harus berupa angka nonnegatif.')
    if tax_pct > 100 or rev_share_pct > 100 or (tax_pct + rev_share_pct) > 100:
        raise ValueError('Persentase pajak dan bagi hasil tidak boleh melebihi 100%.')

    monthly_views = float(monthly_views)
    rpm = float(rpm)
    videos_per_month = max(0, int(videos_per_month))
    cost_per_video = float(cost_per_video)
    monthly_fixed_cost = float(monthly_fixed_cost)
    sponsor_revenue = float(sponsor_revenue)
    affiliate_revenue = float(affiliate_revenue)

    adsense_gross = (monthly_views / 1000.0) * rpm
    total_gross = adsense_gross + sponsor_revenue + affiliate_revenue
    video_production_total = videos_per_month * cost_per_video
    total_expenses = video_production_total + monthly_fixed_cost
    operating_profit = total_gross - total_expenses

    rev_share_amount = max(0.0, operating_profit) * (rev_share_pct / 100.0)
    taxable_income = max(0.0, operating_profit - rev_share_amount)
    tax_amount = taxable_income * (tax_pct / 100.0)
    net_profit = operating_profit - rev_share_amount - tax_amount

    profit_margin_pct = round((net_profit / total_gross) * 100.0, 2) if total_gross > 0 else 0.0
    roi_pct = round((net_profit / total_expenses) * 100.0, 2) if total_expenses > 0 else None
    remaining_cost_for_ads = max(0.0, total_expenses - sponsor_revenue - affiliate_revenue)
    break_even_views = int(math.ceil((remaining_cost_for_ads / rpm) * 1000.0)) if rpm > 0 else 0
    break_even_per_video = int(math.ceil(break_even_views / max(1, videos_per_month)))

    return {
        'currency': currency,
        'monthly_views': int(monthly_views),
        'rpm': round(rpm, 2),
        'videos_per_month': videos_per_month,
        'adsense_gross': round(adsense_gross, 2),
        'sponsor_revenue': round(sponsor_revenue, 2),
        'affiliate_revenue': round(affiliate_revenue, 2),
        'total_gross_revenue': round(total_gross, 2),
        'video_production_cost': round(video_production_total, 2),
        'monthly_fixed_cost': round(monthly_fixed_cost, 2),
        'total_expenses': round(total_expenses, 2),
        'operating_profit': round(operating_profit, 2),
        'rev_share_amount': round(rev_share_amount, 2),
        'tax_amount': round(tax_amount, 2),
        'net_profit': round(net_profit, 2),
        'profit_per_video': round(net_profit / max(1, videos_per_month), 2),
        'profit_margin_pct': profit_margin_pct,
        'roi_pct': roi_pct,
        'break_even_views': break_even_views,
        'break_even_views_per_video': break_even_per_video,
        'profitable': net_profit > 0,
    }


# ==============================================================================
# 11. COMBINED ANALYTICS (Multi-Channel Dashboard Aggregator)
# ==============================================================================
def combine_channel_analytics(channel_entries, rpm_assumption=2.5, currency='USD'):
    """Combine multiple channel analytics (public API datasets or normalized CSV reports) into one dashboard."""
    if not channel_entries:
        raise ValueError('Tambahkan minimal satu channel atau laporan untuk digabungkan.')

    rows = []
    all_videos = []
    total_subs = 0
    total_views = 0
    total_videos = 0
    sample_views_sum = 0

    for entry in channel_entries:
        title = entry.get('title', entry.get('name', 'Channel'))
        subs = _parse_int(entry.get('raw_subs', entry.get('subs', 0)))
        views = _parse_int(entry.get('raw_total_views', entry.get('total_views', entry.get('views_sum', 0))))
        vcount = _parse_int(entry.get('raw_videos', entry.get('video_count', entry.get('videos_count', 0))))
        recent = entry.get('recent_videos', [])
        sample_views = sum(_parse_int(v.get('raw_views', v.get('views', 0))) for v in recent) or views
        est_rev = (sample_views / 1000.0) * float(rpm_assumption)

        total_subs += subs
        total_views += views
        total_videos += vcount
        sample_views_sum += sample_views

        rows.append({
            'Channel': title,
            'Subscriber': subs,
            'Total Views Channel': views,
            'Jumlah Video': vcount,
            'Views Sampel / Periode': sample_views,
            f'Estimasi Gross ({currency})': round(est_rev, 2),
        })
        for v in recent:
            all_videos.append({
                'Channel': title,
                'Judul Video': v.get('title', 'Untitled'),
                'Views': _parse_int(v.get('raw_views', v.get('views', 0))),
                'Tanggal': v.get('date', v.get('published_simple', '-')),
            })

    for r in rows:
        r['Pangsa Views Sampel (%)'] = round(r['Views Sampel / Periode'] / sample_views_sum * 100.0, 1) if sample_views_sum > 0 else 0.0

    all_videos.sort(key=lambda x: x['Views'], reverse=True)
    return {
        'channel_count': len(rows),
        'combined_subscribers': total_subs,
        'combined_total_views': total_views,
        'combined_video_count': total_videos,
        'combined_sample_views': sample_views_sum,
        'combined_estimated_revenue': round((sample_views_sum / 1000.0) * float(rpm_assumption), 2),
        'currency': currency,
        'rpm_assumption': rpm_assumption,
        'channels_table': rows,
        'top_videos': all_videos[:25],
    }


# ==============================================================================
# 12. SCREENSHOT GENERATOR SUITE (Analytics, Channel Page, Video Performance Card)
# ==============================================================================
def _mask_text(text, mask=True, keep_prefix=0):
    text = str(text or '')
    if not mask:
        return text
    if keep_prefix > 0 and len(text) > keep_prefix:
        return text[:keep_prefix] + ' ••••••'
    return '•••••••• (Disembunyikan)'


def render_analytics_screenshot(
    channel_name,
    metrics_dict,
    series_values=None,
    hide_sensitive=True,
    hide_channel_name=True,
    hide_revenue=True,
    subtitle='Ringkasan Analitik Channel (28 Hari / Sampel)'
):
    """Render a clean dark-mode Channel Analytics Screenshot PNG with optional sensitive-data masking."""
    fig = plt.figure(figsize=(10, 5.6), dpi=150)
    fig.patch.set_facecolor('#0f172a')
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor('#0f172a')
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    display_name = _mask_text(channel_name, hide_channel_name or hide_sensitive)
    ax.text(5, 91, 'CHANNEL ANALYTICS SNAPSHOT', color='#38bdf8', fontsize=10, fontweight='bold')
    ax.text(5, 84, display_name, color='#f8fafc', fontsize=18, fontweight='bold')
    ax.text(5, 79, subtitle, color='#94a3b8', fontsize=10)
    badge_text = 'PRIVACY MODE: ON' if (hide_sensitive or hide_channel_name or hide_revenue) else 'PUBLIC VIEW'
    badge_color = '#10b981' if (hide_sensitive or hide_channel_name or hide_revenue) else '#64748b'
    ax.text(95, 88, badge_text, color=badge_color, fontsize=9, fontweight='bold', ha='right',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#1e293b', edgecolor=badge_color, lw=1))

    items = list(metrics_dict.items())[:4]
    card_w = 21
    for idx, (label, val) in enumerate(items):
        x0 = 5 + idx * 23
        is_rev = any(k in label.lower() for k in ('revenue', 'pendapatan', 'profit', 'rpm', 'gross'))
        shown_val = '••••••' if (is_rev and (hide_revenue or hide_sensitive)) else str(val)
        rect = plt.Rectangle((x0, 52), card_w, 21, facecolor='#1e293b', edgecolor='#334155', linewidth=1.2)
        ax.add_patch(rect)
        ax.text(x0 + 2, 67, str(label)[:22], color='#94a3b8', fontsize=9)
        ax.text(x0 + 2, 57, shown_val[:16], color='#f8fafc', fontsize=15, fontweight='bold')

    chart_ax = fig.add_axes([0.06, 0.10, 0.88, 0.34])
    chart_ax.set_facecolor('#1e293b')
    vals = [float(x) for x in (series_values or [120, 180, 160, 240, 310, 290, 420]) if number(x) is not None]
    if len(vals) < 2:
        vals = [100, 150, 210, 190, 280]
    xs = list(range(1, len(vals) + 1))
    chart_ax.plot(xs, vals, color='#38bdf8', linewidth=2.5, marker='o')
    chart_ax.fill_between(xs, vals, color='#38bdf8', alpha=0.18)
    chart_ax.set_title('Tren Penayangan Video Sampel', color='#cbd5e1', fontsize=10, loc='left', pad=8)
    chart_ax.tick_params(colors='#94a3b8', labelsize=8)
    for spine in chart_ax.spines.values():
        spine.set_color('#334155')
    if hide_sensitive:
        chart_ax.set_yticklabels([])

    buf = io.BytesIO()
    fig.savefig(buf, format='png', facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


def render_channel_screenshot(channel_data, hide_sensitive=False):
    """Render a clean Channel Page Screenshot summary card as PNG bytes."""
    fig = plt.figure(figsize=(10, 5.4), dpi=150)
    fig.patch.set_facecolor('#0f172a')
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor('#0f172a')
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    title = _mask_text(channel_data.get('title', 'Channel YouTube'), hide_sensitive)
    handle = _mask_text(channel_data.get('custom_url', '@channel'), hide_sensitive)
    subs = '••••' if hide_sensitive else str(channel_data.get('subs', '0'))
    t_views = str(channel_data.get('total_views', '0'))
    v_count = str(channel_data.get('video_count', channel_data.get('videos', '0')))
    avg_v = str(channel_data.get('avg_recent_views', channel_data.get('avg_views', '0')))
    mon = check_monetization_status(channel_data, kind='channel')

    banner = plt.Rectangle((4, 72), 92, 22, facecolor='#1e293b', edgecolor='#334155', linewidth=1.2)
    ax.add_patch(banner)
    ax.text(7, 87, 'CHANNEL PAGE OVERVIEW', color='#10b981', fontsize=9, fontweight='bold')
    ax.text(7, 80, title[:38], color='#f8fafc', fontsize=17, fontweight='bold')
    ax.text(7, 74.5, f"{handle}  ·  Status: {mon['status_label']}", color='#94a3b8', fontsize=9.5)

    stats = [
        ('Subscriber', subs),
        ('Total Views', t_views),
        ('Total Video', v_count),
        ('Rerata Views Terbaru', avg_v),
    ]
    for idx, (lbl, val) in enumerate(stats):
        x0 = 4 + idx * 23.5
        rect = plt.Rectangle((x0, 48), 21.5, 19, facecolor='#1e293b', edgecolor='#334155', linewidth=1)
        ax.add_patch(rect)
        ax.text(x0 + 2, 61, lbl, color='#94a3b8', fontsize=9)
        ax.text(x0 + 2, 52, str(val)[:15], color='#f8fafc', fontsize=14, fontweight='bold')

    ax.text(4, 41, 'Video Unggulan / Terbaru:', color='#cbd5e1', fontsize=10.5, fontweight='bold')
    recent = channel_data.get('recent_videos', [])[:3]
    if not recent:
        ax.text(4, 33, 'Belum ada daftar video yang dimuat pada sampel.', color='#64748b', fontsize=9.5)
    for i, vid in enumerate(recent):
        y0 = 30 - i * 10
        v_title = _mask_text(vid.get('title', 'Video'), hide_sensitive, keep_prefix=12)
        v_views = vid.get('views', vid.get('views_fmt', '0'))
        row_box = plt.Rectangle((4, y0 - 3), 92, 8, facecolor='#1e293b', edgecolor='#334155', linewidth=0.8)
        ax.add_patch(row_box)
        ax.text(6, y0, f"#{i+1}  {v_title[:58]}", color='#f1f5f9', fontsize=9.5)
        ax.text(94, y0, f"{v_views} views", color='#38bdf8', fontsize=9.5, fontweight='bold', ha='right')

    buf = io.BytesIO()
    fig.savefig(buf, format='png', facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


def render_video_performance_screenshot(video_data, hide_sensitive=False):
    """Render a YouTube Studio / Nexlev-style Latest Video Performance Card as PNG bytes."""
    fig = plt.figure(figsize=(8.5, 5.2), dpi=150)
    fig.patch.set_facecolor('#0f172a')
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor('#0f172a')
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    card = plt.Rectangle((4, 6), 92, 88, facecolor='#1e293b', edgecolor='#334155', linewidth=1.5)
    ax.add_patch(card)

    title = _mask_text(video_data.get('title', 'Judul Video'), hide_sensitive, keep_prefix=10)
    channel = _mask_text(video_data.get('channel', 'Channel'), hide_sensitive)
    views_fmt = str(video_data.get('views_fmt', video_data.get('views', '0')))
    vph_fmt = str(video_data.get('vph_fmt', video_data.get('vph', '0')))
    ratio_lbl = str(video_data.get('ratio_label', f"{float(video_data.get('ratio', 0) or 0):.1f}x"))
    er_val = f"{float(video_data.get('er', 0) or 0):.2f}%"
    outlier = float(video_data.get('channel_breakout_multiple', video_data.get('outlier_multiple', video_data.get('ratio', 1.0))) or 1.0)

    ax.text(8, 86, 'VIDEO PERFORMANCE CARD', color='#38bdf8', fontsize=10, fontweight='bold')
    badge = f"OUTLIER {outlier:.1f}x" if outlier >= 1.5 else 'STANDARD PACE'
    badge_col = '#10b981' if outlier >= 1.5 else '#f59e0b'
    ax.text(92, 86, badge, color=badge_col, fontsize=9.5, fontweight='bold', ha='right',
            bbox=dict(boxstyle='round,pad=0.35', facecolor='#0f172a', edgecolor=badge_col, lw=1))

    ax.text(8, 77, title[:52], color='#f8fafc', fontsize=14.5, fontweight='bold')
    ax.text(8, 71, f"Channel: {channel[:35]}  ·  Durasi: {video_data.get('duration', '-')}", color='#94a3b8', fontsize=9.5)

    rows = [
        ('Penayangan (Views)', views_fmt, '#f8fafc'),
        ('Kecepatan (Views Per Hour)', f"{vph_fmt} VPH", '#38bdf8'),
        ('Outlier / Views vs Subscriber', ratio_lbl, '#10b981'),
        ('Engagement Rate (Likes+Komentar)', er_val, '#fbbf24'),
        ('Skor Kelengkapan Metadata', f"{video_data.get('seo_score', 0)}/100", '#cbd5e1'),
    ]
    for idx, (label, value, col) in enumerate(rows):
        y = 58 - idx * 10
        ax.plot([8, 92], [y - 3, y - 3], color='#334155', linewidth=0.7)
        ax.text(8, y, label, color='#cbd5e1', fontsize=10.5)
        ax.text(92, y, value, color=col, fontsize=11.5, fontweight='bold', ha='right')

    buf = io.BytesIO()
    fig.savefig(buf, format='png', facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()
