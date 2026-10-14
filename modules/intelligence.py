"""Explainable research metrics. Pure functions; no claims of search volume or CTR prediction."""
import csv
import io
import math
import re
import statistics
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

from modules.growth_engine import words


def number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) and n >= 0 else None
    except (ValueError, TypeError):
        return None


def age_hours(video, now=None):
    try:
        dt = datetime.fromisoformat(str(video.get('published_full', '')).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        hours = (now - dt).total_seconds() / 3600
        return max(hours, 1) if hours >= 0 else None
    except (ValueError, TypeError):
        return None


def lifetime_vph(video, now=None):
    age = age_hours(video, now)
    views = number(video.get('raw_views', video.get('views')))
    return views / age if age is not None and views is not None else None


def duration_group(video):
    duration = number(video.get('duration_seconds'))
    if not duration:
        return 'unknown'
    # Duration alone cannot establish the orientation or official Shorts status.
    return 'short-or-uncertain' if duration <= 180 else 'long'


def unique_videos(rows):
    found = {}
    for row in rows:
        if row.get('id'):
            found.setdefault(row['id'], row)
    return list(found.values())


def comparable_baseline(video, peers, now=None):
    """Leave-one-out, same channel/duration band, age within factor two; >=3 peers."""
    age = age_hours(video, now)
    group = duration_group(video)
    usable = []
    for row in unique_videos(peers):
        other_age = age_hours(row, now)
        if row.get('id') == video.get('id') or row.get('channel_id') != video.get('channel_id'):
            continue
        if age is None or other_age is None or group == 'unknown' or duration_group(row) != group:
            continue
        if age / 2 <= other_age <= age * 2 and lifetime_vph(row, now) is not None:
            usable.append(row)
    rates = [lifetime_vph(r, now) for r in usable]
    median = statistics.median(rates) if rates else None
    current = lifetime_vph(video, now)
    valid = len(usable) >= 3 and median is not None and median > 0 and current is not None
    return {'sample_size': len(usable), 'median_vph': median,
            'median_views': statistics.median([number(r.get('raw_views', r.get('views'))) for r in usable]) if usable else None,
            'multiple': current / median if valid else None,
            'peer_ids': [r['id'] for r in usable],
            'basis': 'VPH sejak publikasi; channel dan kelompok durasi sama; usia 0,5–2×; tanpa video target.'}


def keyword_profile(keyword, rows, own_subscribers=None, now=None):
    target = set(words(keyword))
    rows = unique_videos(rows)
    if not target:
        raise ValueError('Isi kata kunci yang dapat dianalisis.')
    rates = [r for row in rows if (r := lifetime_vph(row, now)) is not None]
    eligible = [row for row in rows if age_hours(row, now) is not None]
    exact = sum(target <= set(words(row.get('title', ''))) for row in rows)
    channels = Counter(r['channel_id'] for r in rows if r.get('channel_id'))
    recent = sum(age_hours(r, now) <= 24 * 30 for r in eligible)
    subs = [n for row in rows if row.get('subscriber_known',True) and (n := number(row.get('raw_subs'))) is not None and n > 0]
    median_rate = statistics.median(rates) if rates else None
    # Fixed transparent heuristic, not normalized against other submitted keywords.
    momentum = min(100, math.log10(1 + median_rate) / 4 * 100) if median_rate is not None else None
    coverage = exact / len(rows) * 100 if rows else None
    concentration = max(channels.values()) / sum(channels.values()) * 100 if channels else None
    freshness = recent / len(eligible) * 100 if eligible else None
    attainable = sum(s <= own_subscribers * 2 for s in subs) / len(subs) * 100 if own_subscribers and subs else None
    components = {'Momentum VPH': (momentum, .40), 'Ruang judul': (100-coverage if coverage is not None else None, .25),
                  'Keragaman channel': (100-concentration if concentration is not None else None, .20),
                  'Publikasi baru': (freshness, .15)}
    evidence_ok = len(rows) >= 5 and len(rates) >= 5 and len(channels) >= 2
    score = round(sum(v*w for v, w in components.values()), 1) if evidence_ok and all(v is not None for v,w in components.values()) else None
    personal = round(score * .8 + attainable * .2, 1) if score is not None and attainable is not None else None
    return {'keyword': keyword, 'sample_size': len(rows), 'valid_rates': len(rates), 'unique_channels': len(channels),
            'median_vph': round(median_rate, 2) if median_rate is not None else None,
            'title_coverage_pct': round(coverage, 1) if coverage is not None else None,
            'top_channel_share_pct': round(concentration, 1) if concentration is not None else None,
            'recent_pct': round(freshness, 1) if freshness is not None else None,
            'opportunity': score, 'personal_opportunity': personal,
            'subscriber_sample': len(subs), 'confidence': 'Sampel eksploratif' if evidence_ok else 'Data belum cukup',
            'components': [{'Komponen': k, 'Nilai': round(v, 1) if v is not None else None, 'Bobot': w}
                           for k, (v,w) in components.items()]}


def phrase_clusters(keyword, rows, limit=25):
    counts = Counter()
    for row in unique_videos(rows):
        tokens = words(row.get('title', ''))
        phrases = {' '.join(tokens[i:i+n]) for n in (2,3) for i in range(len(tokens)-n+1)}
        counts.update(phrases)
    seed = ' '.join(words(keyword))
    return [{'Frasa judul': p, 'Video dalam sampel': count} for p,count in counts.most_common(limit+1) if p != seed][:limit]


def parse_video_id(value):
    value = str(value).strip()
    if re.fullmatch(r'[A-Za-z0-9_-]{11}', value):
        return value
    url = urlparse(value)
    if url.scheme not in ('https', 'http') or url.hostname not in ('youtube.com','www.youtube.com','m.youtube.com','youtu.be'):
        raise ValueError('Masukkan ID video 11 karakter atau URL YouTube yang valid.')
    if url.hostname == 'youtu.be':
        candidate = url.path.strip('/')
    elif url.path == '/watch':
        candidate = parse_qs(url.query).get('v', [''])[0]
    else:
        parts = url.path.strip('/').split('/')
        candidate = parts[1] if len(parts) == 2 and parts[0] in ('shorts','embed','live') else ''
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', candidate):
        raise ValueError('ID video pada URL tidak valid.')
    return candidate


def rank_observation(video_id, search_items, limit=50):
    ids = [item.get('id', {}).get('videoId') for item in search_items]
    ids = list(dict.fromkeys(x for x in ids if x))[:limit]
    return {'position': ids.index(video_id)+1 if video_id in ids else None, 'checked': len(ids),
            'limit': limit, 'status': 'Ditemukan' if video_id in ids else 'Tidak ditemukan dalam sampel'}


def wilson_interval(clicks, impressions, z=1.959963984540054):
    p = clicks / impressions
    denominator = 1 + z*z/impressions
    center = (p + z*z/(2*impressions)) / denominator
    half = z * math.sqrt(p*(1-p)/impressions + z*z/(4*impressions**2)) / denominator
    return max(0,center-half), min(1,center+half)


def ctr_experiment(a_impressions, a_clicks, b_impressions, b_clicks):
    values = [a_impressions, a_clicks, b_impressions, b_clicks]
    if any(isinstance(v,bool) or number(v) is None or int(v) != v for v in values):
        raise ValueError('Impresi dan klik harus bilangan bulat nonnegatif.')
    if min(a_impressions,b_impressions) == 0 or a_clicks > a_impressions or b_clicks > b_impressions:
        raise ValueError('Impresi harus lebih dari nol dan klik tidak boleh melebihi impresi.')
    pa,pb = a_clicks/a_impressions, b_clicks/b_impressions
    la,ua = wilson_interval(a_clicks,a_impressions)
    lb,ub = wilson_interval(b_clicks,b_impressions)
    # Newcombe hybrid score interval for difference of independent binomial proportions.
    low = pb-pa-math.sqrt((pb-lb)**2+(ua-pa)**2)
    high = pb-pa+math.sqrt((ub-pb)**2+(pa-la)**2)
    enough = min(a_clicks,b_clicks,a_impressions-a_clicks,b_impressions-b_clicks) >= 10
    verdict = ('Indikasi CTR B lebih tinggi' if low > 0 else 'Indikasi CTR A lebih tinggi' if high < 0
               else 'Belum ada perbedaan yang jelas') if enough else 'Data masih terbatas'
    return {'ctr_a': pa*100,'ctr_b': pb*100,'interval_a': [la*100,ua*100],'interval_b': [lb*100,ub*100],
            'difference_pp': (pb-pa)*100,'difference_interval_pp': [low*100,high*100],
            'relative_lift_pct': (pb/pa-1)*100 if pa else None, 'verdict': verdict}


def csv_bytes(rows):
    """Neutralize spreadsheet formula injection in user/API-supplied text."""
    out = io.StringIO()
    rows = list(rows)
    if not rows:
        return b''
    writer = csv.DictWriter(out, fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
    writer.writeheader()
    for row in rows:
        safe = {k: ("'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@','\t','\r')) else v) for k,v in row.items()}
        writer.writerow(safe)
    return out.getvalue().encode('utf-8-sig')


def balanced_ids(groups, limit=50):
    output = []
    for i in range(max((len(g) for g in groups), default=0)):
        for group in groups:
            if i < len(group) and group[i] not in output:
                output.append(group[i])
                if len(output) == limit:
                    return output
    return output
