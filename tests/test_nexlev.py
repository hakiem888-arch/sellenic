"""Unit tests for all Nexlev.io-inspired features in modules/nexlev_engine.py."""
import io
import unittest
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw

from modules.nexlev_engine import (
    analyze_transcript,
    apply_advanced_homepage_filter,
    calculate_net_profit,
    check_monetization_status,
    combine_channel_analytics,
    compress_thumbnail,
    compute_niche_overview,
    extract_channel_dna_queries,
    generate_midroll_ad_breaks,
    rank_similar_thumbnails,
    render_analytics_screenshot,
    render_channel_screenshot,
    render_video_performance_screenshot,
    score_similar_channels,
    sort_channel_videos,
)


NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


def _make_sample_image(width=1600, height=900, color=(20, 120, 220), accent=(250, 200, 40), fmt='PNG'):
    img = Image.new('RGB', (width, height), color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([100, 100, width // 2, height // 2], fill=accent)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


class NexlevEngineTest(unittest.TestCase):
    def test_monetization_status_video_and_channel(self):
        monetized_video = {
            'title': 'Review Gadget Terbaik 2026',
            'raw_subs': 25000,
            'raw_views': 150000,
            'duration_seconds': 620,
            'made_for_kids': False,
            'description': 'Beli di https://shopee.co.id/produk atau https://tokopedia.com/toko. Business inquiries: sponsor@brand.com',
        }
        res = check_monetization_status(monetized_video, kind='video')
        self.assertTrue(res['ypp_eligible'])
        self.assertTrue(res['midroll_eligible'])
        self.assertGreaterEqual(res['score'], 75)
        self.assertIn('shopee', res['affiliate_markers'])

        kids_video = {
            'title': 'Lagu Anak',
            'raw_subs': 5000,
            'raw_views': 50000,
            'duration_seconds': 180,
            'made_for_kids': True,
            'description': '',
        }
        res_kids = check_monetization_status(kids_video, kind='video')
        self.assertIn('Made for Kids', res_kids['status_label'])
        self.assertFalse(res_kids['midroll_eligible'])

        small_ch = {'title': 'Channel Baru', 'raw_subs': 120, 'raw_total_views': 800, 'raw_videos': 3}
        res_small = check_monetization_status(small_ch, kind='channel')
        self.assertFalse(res_small['ypp_eligible'])

    def test_sort_channel_videos_by_popularity_vph_and_outlier(self):
        vids = [
            {'id': 'v1', 'channel_id': 'c1', 'title': 'Video A', 'raw_views': 5000, 'duration_seconds': 600,
             'published_full': (NOW - timedelta(hours=48)).isoformat()},
            {'id': 'v2', 'channel_id': 'c1', 'title': 'Video B Viral', 'raw_views': 80000, 'duration_seconds': 600,
             'published_full': (NOW - timedelta(hours=24)).isoformat()},
            {'id': 'v3', 'channel_id': 'c1', 'title': 'Video C', 'raw_views': 10000, 'duration_seconds': 600,
             'published_full': (NOW - timedelta(hours=36)).isoformat()},
            {'id': 'v4', 'channel_id': 'c1', 'title': 'Video D', 'raw_views': 8000, 'duration_seconds': 600,
             'published_full': (NOW - timedelta(hours=30)).isoformat()},
        ]
        by_pop = sort_channel_videos(vids, sort_by='Terpopuler (Views Tertinggi)', now=NOW)
        self.assertEqual([v['id'] for v in by_pop], ['v2', 'v3', 'v4', 'v1'])
        self.assertGreater(by_pop[0]['outlier_multiple'], 3.0)

        by_vph = sort_channel_videos(vids, sort_by='VPH Tertinggi', now=NOW)
        self.assertEqual(by_vph[0]['id'], 'v2')

        by_oldest = sort_channel_videos(vids, sort_by='Terlama', now=NOW)
        self.assertEqual(by_oldest[0]['id'], 'v1')

    def test_thumbnail_compressor_reduces_size_and_fits_resolution(self):
        raw_png = _make_sample_image(1920, 1080, fmt='PNG')
        compressed = compress_thumbnail(raw_png, max_bytes=150_000, target_resolution=(1280, 720), output_format='JPEG')
        self.assertLessEqual(compressed['compressed_bytes'], 150_000)
        self.assertTrue(compressed['under_youtube_limit'])
        self.assertEqual(compressed['final_size'], (1280, 720))

    def test_similar_thumbnail_search_ranks_visually_close_higher(self):
        ref_img = _make_sample_image(640, 360, color=(20, 120, 220), accent=(250, 200, 40), fmt='JPEG')
        close_img = _make_sample_image(640, 360, color=(25, 118, 215), accent=(245, 195, 45), fmt='JPEG')
        diff_img = _make_sample_image(640, 360, color=(220, 20, 30), accent=(10, 10, 10), fmt='JPEG')

        candidates = [
            {'video': {'id': 'diff', 'title': 'Different Style', 'views_fmt': '10K', 'vph': 50}, 'image_bytes': diff_img},
            {'video': {'id': 'close', 'title': 'Visually Similar', 'views_fmt': '50K', 'vph': 200}, 'image_bytes': close_img},
        ]
        ranked = rank_similar_thumbnails(ref_img, candidates)
        self.assertEqual(len(ranked['results']), 2)
        self.assertEqual(ranked['results'][0]['video']['id'], 'close')
        self.assertGreater(ranked['results'][0]['similarity_pct'], ranked['results'][1]['similarity_pct'])

    def test_transcript_analysis_evaluates_hook_wpm_and_chapters(self):
        sample_transcript = (
            "00:00 Mengapa 90% pemula gagal belajar Python? Ini rahasia dan cara tercepat membuktikan hasilnya.\n"
            "00:45 Langkah pertama memahami struktur data dasar dalam pemrograman Python untuk pemula.\n"
            "02:15 Kesalahan umum saat membuat perulangan dan fungsi yang sering menghambat belajar Python.\n"
            "04:00 Studi kasus proyek nyata otomatisasi data menggunakan skrip Python sederhana.\n"
        )
        res = analyze_transcript(sample_transcript, target_keyword='belajar python', duration_seconds=270)
        self.assertTrue(res['keyword_in_hook'])
        self.assertGreaterEqual(res['hook_score'], 75)
        self.assertGreater(res['wpm'], 0)
        self.assertEqual(len(res['chapters']), 4)
        self.assertEqual(len(res['quarters']), 4)

    def test_similar_channels_scoring_and_dna_extraction(self):
        ref = {
            'id': 'UC_ref',
            'title': 'Python Coding Lab',
            'raw_subs': 50000,
            'raw_total_views': 5000000,
            'raw_videos': 100,
            'top_seo_tags': [('tutorial python', 10), ('belajar coding', 8)],
            'recent_videos': [{'title': 'Tutorial Python Pemula Lengkap'}],
        }
        queries = extract_channel_dna_queries(ref)
        self.assertTrue(queries)
        candidates = [
            {'id': 'UC_1', 'title': 'Belajar Python ID', 'raw_subs': 45000, 'raw_total_views': 4200000, 'raw_videos': 90, 'matched_query': 'tutorial python'},
            {'id': 'UC_2', 'title': 'Vlog Masak Harian', 'raw_subs': 2000000, 'raw_total_views': 500000000, 'raw_videos': 1500, 'matched_query': ''},
        ]
        ranked = score_similar_channels(ref, candidates)
        self.assertEqual(ranked[0]['id'], 'UC_1')
        self.assertGreater(ranked[0]['similarity_score'], ranked[1]['similarity_score'])

    def test_advanced_homepage_filter(self):
        videos = [
            {'id': '1', 'title': 'Longform Outlier Python', 'raw_views': 50000, 'raw_subs': 5000, 'vph': 300, 'ratio': 10.0,
             'duration_seconds': 600, 'published_full': (NOW - timedelta(days=3)).isoformat()},
            {'id': '2', 'title': 'Short Clip #shorts', 'raw_views': 100000, 'raw_subs': 500000, 'vph': 500, 'ratio': 0.2,
             'duration_seconds': 45, 'published_full': (NOW - timedelta(days=1)).isoformat()},
        ]
        filtered = apply_advanced_homepage_filter(
            videos,
            max_subs=20000,
            min_vph=100,
            min_outlier_ratio=2.0,
            exclude_shorts=True,
            now=NOW
        )
        self.assertEqual([v['id'] for v in filtered], ['1'])

    def test_niche_overview_computation(self):
        rows = [
            {'id': f'v{i}', 'channel': f'Ch {i%3}', 'channel_id': f'c{i%3}', 'title': f'Sejarah Kuno Bagian {i}',
             'description': 'Pembahasan sejarah kuno tutorial langkah', 'raw_views': 30000 * (i + 1),
             'raw_subs': 10000, 'vph': 150 * (i + 1), 'er': 4.2, 'ratio': 3.0 * (i + 1),
             'duration_seconds': 720, 'published_full': (NOW - timedelta(days=5)).isoformat()}
            for i in range(6)
        ]
        ov = compute_niche_overview('sejarah kuno', rows, own_subscribers=15000, now=NOW)
        self.assertIsNotNone(ov['niche_score'])
        self.assertIsNotNone(ov['personal_niche_score'])
        self.assertEqual(ov['summary']['midroll_eligible_pct'], 100.0)
        self.assertGreater(ov['summary']['small_channel_gems_count'], 0)

    def test_automatic_ad_placer_8min_rule_and_timestamp_snapping(self):
        short_res = generate_midroll_ad_breaks(300)
        self.assertFalse(short_res['eligible'])
        self.assertEqual(short_res['placements'], [])

        long_res = generate_midroll_ad_breaks(
            750,
            transcript_text="00:00 Intro\n01:35 Masuk Topik 1\n04:25 Masuk Topik 2\n07:35 Masuk Topik 3\n10:30 Penutup",
            strategy='Seimbang',
            first_ad_seconds=90
        )
        self.assertTrue(long_res['eligible'])
        self.assertGreaterEqual(long_res['ad_count'], 3)
        self.assertEqual(long_res['placements'][0]['Timestamp'], '01:35')

    def test_net_profit_calculator_and_combined_analytics(self):
        profit = calculate_net_profit(
            monthly_views=500_000,
            rpm=4.0,
            videos_per_month=8,
            cost_per_video=50.0,
            monthly_fixed_cost=100.0,
            sponsor_revenue=300.0,
            affiliate_revenue=100.0,
            tax_pct=10.0,
            rev_share_pct=0.0,
            currency='USD'
        )
        self.assertEqual(profit['adsense_gross'], 2000.0)
        self.assertEqual(profit['total_gross_revenue'], 2400.0)
        self.assertEqual(profit['total_expenses'], 500.0)
        self.assertEqual(profit['operating_profit'], 1900.0)
        self.assertEqual(profit['net_profit'], 1710.0)
        self.assertTrue(profit['profitable'])

        combined = combine_channel_analytics([
            {'title': 'Ch A', 'raw_subs': 10000, 'raw_total_views': 1000000, 'raw_videos': 20,
             'recent_videos': [{'title': 'V1', 'raw_views': 100000}]},
            {'title': 'Ch B', 'raw_subs': 25000, 'raw_total_views': 2500000, 'raw_videos': 35,
             'recent_videos': [{'title': 'V2', 'raw_views': 150000}]},
        ], rpm_assumption=3.0, currency='USD')
        self.assertEqual(combined['channel_count'], 2)
        self.assertEqual(combined['combined_subscribers'], 35000)
        self.assertEqual(combined['combined_sample_views'], 250000)
        self.assertEqual(combined['combined_estimated_revenue'], 750.0)

    def test_screenshots_render_valid_png_bytes(self):
        an_png = render_analytics_screenshot('Channel Rahasia', {'Views': '100K', 'Est. Revenue': '$500'}, hide_sensitive=True)
        self.assertTrue(an_png.startswith(b'\x89PNG'))
        ch_png = render_channel_screenshot({'title': 'Channel Uji', 'subs': '10K', 'total_views': '1M', 'video_count': '25'}, hide_sensitive=True)
        self.assertTrue(ch_png.startswith(b'\x89PNG'))
        vid_png = render_video_performance_screenshot({'title': 'Video Uji', 'views_fmt': '50K', 'vph_fmt': '450', 'ratio': 3.2}, hide_sensitive=False)
        self.assertTrue(vid_png.startswith(b'\x89PNG'))


if __name__ == '__main__':
    unittest.main()
