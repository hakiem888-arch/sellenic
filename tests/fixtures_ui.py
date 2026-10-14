"""Synthetic data used only in isolated UI tests. Never imported by app.py."""
import ast
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
import copy
import math
import re
import statistics
import streamlit as st

APP = Path(__file__).resolve().parents[1] / 'app.py'
source = ast.parse(APP.read_text())
constants = {'COUNTRY_CODES','CATEGORIES','SORT_OPTIONS','TIME_FILTERS','LICENSE_OPTIONS'}
functions = {'normalize_score','radar_chart','extract_keywords','build_content_opportunity','analyze_winning_patterns','small_channel_gems','normalize_artist_comparison','get_published_after_rfc3339','format_number','parse_yt_date','estimate_best_time'}
import matplotlib.pyplot as plt
ns = dict(globals())
for node in source.body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in node.targets):
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(APP), 'exec'), ns)
    elif isinstance(node, ast.FunctionDef) and node.name in functions:
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(APP), 'exec'), ns)

VIDEOS = []
for i in range(1, 14):
    VIDEOS.append(dict(id=f'sample{i}', channel_id=f'channel{i}', title=f'Data simulasi {i}: ide konten untuk pengujian',
        channel=f'Channel simulasi {i}', thumbnail='', published_full='2026-10-08T08:00:00Z',
        published_simple='08 Okt 2026', duration='8:20', duration_seconds=500, duration_iso='PT8M20S',
        summary=['Ringkasan sintetis untuk menguji tampilan.'], tags=['simulasi', 'pengujian'], keywords=['simulasi'],
        description='Data simulasi untuk pengujian UI.', views=10000*i, raw_views=10000*i, views_fmt=f'{10*i}K',
        subs='2K', raw_subs=2000, likes='100', raw_likes=100, comments='10', raw_comments=10,
        vph=400*i, vph_fmt=f'{400*i:,}', earnings='Rp 100Rb', er=1.1, ratio=5*i, ratio_label=f'{5*i}x',
        is_gem=True, seo_score=80, seo_checks=['Judul tersedia', 'Deskripsi tersedia'], link=f'https://example.com/sample{i}',
        rank=i, velocity_vph=400*i, acceleration=2.0, age_hours=18, breakout_score=80-i,
        viral_label='BREAKOUT', channel_baseline_vph=100, channel_breakout_multiple=4.0,
        channel_baseline_samples=5, snapshot_count=2, breakout_reasons=['Data uji'], previous_vph=200))
CHANNELS = [dict(id=f'channel{i}', title=f'Channel simulasi {i}', thumb='', custom_url=f'@simulasi{i}',
                subs='2K', videos='100', total_views='1M', avg_views='10K', published_at_str='01 Jan 2024', age='2 THN') for i in range(1,7)]


def record(name, value):
    calls=st.session_state.setdefault('test_calls', {})
    calls.setdefault(name, []).append(value)


def search_youtube(**kwargs):
    record('search', kwargs)
    return copy.deepcopy(VIDEOS)


def trending(*args):
    record('trending', args)
    return [{**copy.deepcopy(v), 'title': 'Trending simulasi '+str(i)} for i,v in enumerate(VIDEOS[:3])]


def channels(*args, **kwargs):
    record('channels', (args, kwargs))
    return copy.deepcopy(CHANNELS[:kwargs.get('max_results', 6)])


def deep(channel_id):
    record('deep', channel_id)
    return dict(title='Channel '+channel_id, thumb='', custom_url='@'+channel_id, subs='2K', total_views='1M',
                video_count='100', avg_recent_views='10K', favorite_upload_hour='08:00 WIB', top_seo_tags=[('simulasi', 5)],
                recent_videos=[dict(title='Video uji '+str(i), views='10K', raw_views=10000, date='08 Okt 2026', thumb='') for i in range(5)])


def dna(data):
    record('dna', data['channel_id'])
    return 'Analisis khusus '+data['channel_id']


def artist(name, *args):
    record('artist', name)
    return dict(artist=name, youtube_interest_score=50, videos_found=10, recent_videos=8, total_views=100000,
                median_views=5000, avg_vph=100, engagement_rate=2, longform_count=8, shorts_like_count=2,
                search_results_estimate=1000, error='')


def normalize(rows):
    return rows


def viral(*args, **kwargs):
    record('viral', (args, kwargs))
    return copy.deepcopy(VIDEOS)


def ideas(query):
    record('ideas', query)
    return 'Ide simulasi untuk '+query

SERVICES = {**ns, 'API_KEYS':['TEST_ONLY'], 'GEMINI_API_KEY':'', 'search_youtube':search_youtube,
    'get_trending_videos':trending, 'search_youtube_channels':channels, 'analyze_channel_deep':deep,
    'search_viral_longform':viral, 'channel_insight':dna, 'generate_ai_ideas':ideas,
    'get_youtube_suggestions':lambda q:[q+' fokus',q+' detail'], 'get_rising_trends':lambda *args:[],
    'get_artist_search_demand':artist, 'normalize_artist_comparison':normalize,
    'generate_ai_content_opportunity':lambda *args:'Peluang uji', 'generate_ai_winner_analysis':lambda *args:'Analisis uji'}
