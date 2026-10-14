"""Streamlit UI pages and components for Nexlev.io-inspired features."""
import json
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

from modules.intelligence import csv_bytes
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
)
from modules.workspace_ui import client_for, resolve_channel


def _session_videos():
    """Collect unique videos discovered in the current session across search, trending, and viral modes."""
    collected = {}
    for key in ('video_results_bundle', 'viral_bundle', 'trending_results_bundle', 'niche_overview_bundle'):
        bundle = st.session_state.get(key, {})
        for row in bundle.get('rows', []):
            if isinstance(row, dict) and row.get('id'):
                collected.setdefault(row['id'], row)
    return list(collected.values())


def render_advanced_feed_filter(rows, scope_prefix='feed'):
    """Render an interactive Advanced Homepage / Feed Filter bar inside Video Search or Trending."""
    with st.expander('Advanced Homepage Filter (Filter Metrik Kreator & Outlier)', expanded=False):
        st.caption('Saring daftar video berdasarkan ukuran subscriber channel, rasio outlier, VPH minimum, durasi, dan pengecualian Shorts.')
        c1, c2, c3, c4 = st.columns(4)
        min_vph = c1.number_input('VPH minimum', min_value=0, value=0, step=25, key=f'{scope_prefix}_adv_min_vph')
        min_ratio = c2.number_input('Rasio Views/Subs min (Outlier)', min_value=0.0, value=0.0, step=0.5, key=f'{scope_prefix}_adv_min_ratio')
        max_subs = c3.number_input('Subscriber maks (0 = semua)', min_value=0, value=0, step=5000, key=f'{scope_prefix}_adv_max_subs')
        min_views = c4.number_input('Views minimum', min_value=0, value=0, step=1000, key=f'{scope_prefix}_adv_min_views')

        d1, d2, d3, d4 = st.columns(4)
        min_dur = d1.number_input('Durasi min (menit)', min_value=0.0, value=0.0, step=1.0, key=f'{scope_prefix}_adv_min_dur')
        max_age = d2.number_input('Usia maks (hari, 0 = semua)', min_value=0, value=0, step=7, key=f'{scope_prefix}_adv_max_age')
        kw_inc = d3.text_input('Wajib memuat kata', key=f'{scope_prefix}_adv_kw_inc', placeholder='opsional')
        exclude_shorts = d4.checkbox('Sembunyikan Shorts (≤3m)', value=False, key=f'{scope_prefix}_adv_no_shorts')

    active = any([min_vph > 0, min_ratio > 0, max_subs > 0, min_views > 0, min_dur > 0, max_age > 0, str(kw_inc).strip(), exclude_shorts])
    if not active:
        return rows

    filtered = apply_advanced_homepage_filter(
        rows,
        min_views=min_views,
        max_subs=max_subs,
        min_vph=min_vph,
        min_outlier_ratio=min_ratio,
        min_duration_minutes=min_dur,
        max_age_days=max_age,
        exclude_shorts=exclude_shorts,
        keyword_include=kw_inc,
    )
    st.caption(f'Filter Advanced aktif: menampilkan **{len(filtered)}** dari **{len(rows)}** video.')
    return filtered


def monetization_transcript_page(backend):
    st.title('Monetization Status & Analisis Transkrip')
    st.caption('Periksa indikator kelayakan monetisasi video/channel serta bedah kualitas hook, tempo bicara (WPM), dan struktur transkrip.')

    tab_mon, tab_tr = st.tabs(['Monetization Status Checker', 'Transcript Analysis'])

    with tab_mon:
        session_vids = _session_videos()
        mode = st.radio(
            'Sumber pemeriksaan monetisasi',
            ['Pilih dari video hasil riset sesi ini', 'Input manual / simulasi indikator'],
            horizontal=True,
            key='mon_source_mode'
        )
        target_entity = None
        entity_kind = 'video'

        if mode == 'Pilih dari video hasil riset sesi ini':
            if not session_vids:
                st.info('Belum ada video pada sesi ini. Jalankan Pencarian Video, Trending, atau gunakan mode Input manual di atas.')
            else:
                idx = st.selectbox(
                    'Pilih video untuk diperiksa',
                    range(len(session_vids)),
                    format_func=lambda i: f"{session_vids[i].get('title', 'Video')} — {session_vids[i].get('channel', '')}",
                    key='mon_select_video'
                )
                target_entity = session_vids[idx]
        else:
            with st.form('mon_manual_form'):
                a, b, c = st.columns(3)
                subs = a.number_input('Jumlah subscriber channel', min_value=0, value=1500, step=100)
                views = b.number_input('Views video / total channel', min_value=0, value=25000, step=1000)
                dur = c.number_input('Durasi video (detik)', min_value=0, value=600, step=30)
                d, e = st.columns(2)
                kids = d.checkbox('Konten Made for Kids', value=False)
                lic = e.selectbox('Lisensi', ['youtube', 'creativeCommon'])
                desc = st.text_area('Deskripsi video (untuk deteksi afiliasi/sponsor)', placeholder='Contoh: Beli alat di https://shopee.co.id/... Business inquiries: email@domain.com')
                run_mon = st.form_submit_button('Periksa Status Monetisasi', type='primary')
            if run_mon or 'mon_manual_entity' in st.session_state:
                if run_mon:
                    st.session_state['mon_manual_entity'] = {
                        'title': 'Simulasi Pemeriksaan Monetisasi',
                        'raw_subs': subs,
                        'raw_views': views,
                        'duration_seconds': dur,
                        'made_for_kids': kids,
                        'license': lic,
                        'description': desc,
                    }
                target_entity = st.session_state.get('mon_manual_entity')

        if target_entity:
            res = check_monetization_status(target_entity, kind=entity_kind)
            c1, c2, c3 = st.columns(3)
            c1.metric('Status Indikator', res['status_label'])
            c2.metric('Skor Kesiapan Monetisasi', f"{res['score']}/100")
            c3.metric('Iklan Mid-Roll (≥8m)', 'Memenuhi' if res['midroll_eligible'] else 'Tidak (Pre/Post-Roll)')
            st.dataframe(pd.DataFrame(res['signals']), hide_index=True, use_container_width=True)
            st.caption(res['basis'])

    with tab_tr:
        with st.form('transcript_analysis_form'):
            a, b = st.columns([2, 1])
            kw = a.text_input('Kata kunci target (opsional)', placeholder='Contoh: belajar python', key='tr_keyword')
            dur_sec = b.number_input('Durasi video dalam detik (0 = estimasi otomatis)', min_value=0, value=0, step=30, key='tr_duration')
            text = st.text_area(
                'Teks transkrip (mendukung format biasa maupun bertimestamp 00:00)',
                height=200,
                placeholder='00:00 Mengapa banyak pemula gagal belajar Python? Ini cara paling mudah dan bukti hasilnya.\n00:45 Langkah pertama menyiapkan lingkungan kerja...\n02:10 Kesalahan umum saat menulis fungsi...',
                key='tr_text'
            )
            submit_tr = st.form_submit_button('Analisis Transkrip', type='primary')

        if submit_tr:
            try:
                st.session_state['transcript_analysis_result'] = analyze_transcript(text, kw, dur_sec)
            except ValueError as exc:
                st.warning(str(exc))

        tr_res = st.session_state.get('transcript_analysis_result')
        if tr_res:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric('Skor Hook Pembuka', f"{tr_res['hook_score']}/100")
            m2.metric('Kecepatan Bicara', f"{tr_res['wpm']} WPM")
            m3.metric('Total Kata', f"{tr_res['total_words']:,}")
            m4.metric('Proporsi Kata Filler', f"{tr_res['filler_pct']}%")

            st.info(f"**Evaluasi Tempo:** {tr_res['pace_label']} · **Durasi Estimasi/Aktual:** {tr_res['duration_formatted']}")
            st.write('**Evaluasi Hook (30 Detik / 75 Kata Pertama):**')
            for fb in tr_res['hook_feedback']:
                st.write(f'- {fb}')

            t1, t2, t3 = st.tabs(['Struktur 4 Kuartal', 'Kata Kunci & Frasa', 'Chapter Otomatis'])
            with t1:
                st.dataframe(pd.DataFrame(tr_res['quarters']), hide_index=True, use_container_width=True)
                if tr_res['top_fillers']:
                    st.caption('Kata filler yang sering muncul:')
                    st.dataframe(pd.DataFrame(tr_res['top_fillers']), hide_index=True, use_container_width=True)
            with t2:
                col_a, col_b = st.columns(2)
                with col_a:
                    st.write('**Kata Teratas**')
                    st.dataframe(pd.DataFrame(tr_res['top_keywords']), hide_index=True, use_container_width=True)
                with col_b:
                    st.write('**Frasa 2 Kata Teratas**')
                    if tr_res['top_phrases']:
                        st.dataframe(pd.DataFrame(tr_res['top_phrases']), hide_index=True, use_container_width=True)
                    else:
                        st.caption('Belum ada frasa berulang minimal 2 kali.')
            with t3:
                st.caption(tr_res['chapter_note'])
                if tr_res['chapters']:
                    st.code('\n'.join(tr_res['chapters']), language='text')
                else:
                    st.info('Tambahkan minimal 3 baris timestamp mulai dari 00:00 untuk mengekstrak daftar chapter.')


def similar_thumbnail_page(backend):
    st.title('Similar Thumbnail Search')
    st.caption('Bandingkan kemiripan visual thumbnail (komposisi struktur, palet warna, kecerahan, dan kontras) terhadap video di niche Anda.')

    session_vids = [v for v in _session_videos() if v.get('thumbnail')]
    col1, col2 = st.columns(2)
    with col1:
        uploaded = st.file_uploader('Unggah thumbnail referensi (PNG/JPG/WebP)', type=['png', 'jpg', 'jpeg', 'webp'], key='sim_thumb_upload')
    with col2:
        quick_query = st.text_input('Atau cari kandidat video niche baru (opsional)', placeholder='Contoh: gadget review indonesia', key='sim_thumb_query')
        if st.button('Ambil sampel thumbnail dari pencarian', key='sim_thumb_fetch'):
            if not str(quick_query).strip():
                st.warning('Masukkan kata kunci pencarian terlebih dahulu.')
            else:
                with st.spinner('Mengambil sampel video...'):
                    rows = backend.search_youtube(query=str(quick_query).strip(), max_results=12)
                    st.session_state['video_results_bundle'] = {
                        'rows': rows,
                        'query': str(quick_query).strip(),
                        'context': 'Sampel Similar Thumbnail',
                        'at': datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M UTC'),
                        'revision': 1,
                    }
                    session_vids = [v for v in _session_videos() if v.get('thumbnail')]

    ref_bytes = None
    if uploaded is not None:
        ref_bytes = uploaded.getvalue()
        st.image(ref_bytes, caption='Thumbnail Referensi Anda', width=280)
    elif session_vids:
        ref_idx = st.selectbox(
            'Atau gunakan salah satu thumbnail dari sesi riset sebagai referensi',
            range(len(session_vids)),
            format_func=lambda i: session_vids[i].get('title', f'Video {i+1}'),
            key='sim_thumb_ref_select'
        )
        if st.button('Bandingkan Kemiripan Visual Sekarang', type='primary', key='sim_thumb_run_session'):
            cand_records = []
            with st.spinner('Mengunduh dan menghitung tanda tangan visual thumbnail...'):
                for v in session_vids[:15]:
                    try:
                        resp = requests.get(v['thumbnail'], timeout=10)
                        if resp.ok:
                            cand_records.append({'video': v, 'image_bytes': resp.content})
                    except requests.RequestException:
                        continue
            if cand_records:
                ref_b = next((c['image_bytes'] for c in cand_records if c['video'].get('id') == session_vids[ref_idx].get('id')), cand_records[0]['image_bytes'])
                st.session_state['sim_thumb_result'] = rank_similar_thumbnails(ref_b, cand_records)
            else:
                st.warning('Thumbnail kandidat belum dapat diunduh.')

    if uploaded is not None and session_vids and st.button('Cari Thumbnail yang Mirip dengan Unggahan Saya', type='primary', key='sim_thumb_run_upload'):
        cand_records = []
        with st.spinner('Menganalisis kemiripan visual terhadap sampel video...'):
            for v in session_vids[:15]:
                try:
                    resp = requests.get(v['thumbnail'], timeout=10)
                    if resp.ok:
                        cand_records.append({'video': v, 'image_bytes': resp.content})
                except requests.RequestException:
                    continue
        if cand_records:
            st.session_state['sim_thumb_result'] = rank_similar_thumbnails(ref_bytes, cand_records)

    res = st.session_state.get('sim_thumb_result')
    if not res:
        if not session_vids and uploaded is None:
            st.info('Unggah gambar thumbnail Anda atau jalankan pencarian video terlebih dahulu untuk membandingkan tren visual thumbnail.')
        return

    sig = res['reference_signature']
    st.caption(f"Tanda tangan visual referensi — Warna dominan: `{sig['dominant_hex']}` · Kecerahan: `{sig['brightness']}` · Kontras: `{sig['contrast']}`")
    ranked = res.get('results', [])
    if not ranked:
        st.info('Belum ada kandidat thumbnail yang dapat dibandingkan.')
        return

    table = [{
        'Judul Video': r['title'],
        'Channel': r['channel'],
        'Kemiripan Total (%)': r['similarity_pct'],
        'Kemiripan Komposisi (%)': r['structure_similarity_pct'],
        'Kemiripan Warna (%)': r['color_similarity_pct'],
        'Warna Dominan': r['dominant_hex'],
        'Views': r['views_fmt'],
        'VPH': r['vph'],
    } for r in ranked]
    st.dataframe(pd.DataFrame(table), hide_index=True, use_container_width=True)


def similar_channels_page(backend):
    st.title('Similar Channels Finder')
    st.caption('Temukan channel serupa berdasarkan kemiripan topik, tag SEO, ukuran subscriber, dan kecepatan penayangan.')

    selected_cid = st.session_state.get('selected_channel')
    cached_details = st.session_state.get('channel_details', {})
    default_input = selected_cid or ''

    with st.form('similar_channels_form'):
        query_or_id = st.text_input(
            'ID Channel (UC...), @handle, atau topik channel referensi',
            value=default_input,
            placeholder='Contoh: UC... atau @nama_channel atau topik spesifik',
            key='sim_ch_input'
        )
        subs_tier = st.selectbox('Filter rentang subscriber kandidat', ['Semua', '0-1K', '1K-10K', '10K-100K', '100K-1M', '> 1M'], key='sim_ch_subs')
        run = st.form_submit_button('Temukan Channel Serupa', type='primary')

    if run:
        val = str(query_or_id or '').strip()
        if not val:
            st.warning('Masukkan ID channel, @handle, atau topik referensi terlebih dahulu.')
        else:
            ref_data = None
            if val in cached_details:
                ref_data = cached_details[val][1]
                ref_data['id'] = val
            elif val.startswith('UC') or val.startswith('@'):
                try:
                    client = client_for(backend)
                    cid = resolve_channel(client, val)
                    ref_data = backend.analyze_channel_deep(cid)
                    if ref_data:
                        ref_data['id'] = cid
                except Exception:
                    ref_data = None

            if ref_data is None:
                ref_data = {'id': '', 'title': val, 'raw_subs': 10000, 'raw_total_views': 500000, 'raw_videos': 50,
                            'top_seo_tags': [(val, 5)], 'recent_videos': [{'title': val}]}

            queries = extract_channel_dna_queries(ref_data, max_queries=2)
            candidates = []
            with st.spinner(f"Mencari channel serupa untuk topik: {', '.join(queries)}..."):
                for q in queries:
                    found = backend.search_youtube_channels(q, max_results=15, subs_filter=subs_tier)
                    for item in found:
                        item['matched_query'] = q
                        candidates.append(item)
            ranked = score_similar_channels(ref_data, candidates)
            st.session_state['similar_channels_result'] = {
                'reference': ref_data,
                'queries': queries,
                'results': ranked,
            }

    bundle = st.session_state.get('similar_channels_result')
    if not bundle:
        st.info('Masukkan channel referensi untuk menemukan kompetitor dan channel sejenis di niche yang sama.')
        return

    ref = bundle['reference']
    st.caption(f"Referensi: **{ref.get('title', '-')}** · Kata kunci DNA yang diekstrak: `{', '.join(bundle['queries'])}`")
    results = bundle.get('results', [])
    if not results:
        st.info('Belum ditemukan channel kandidat yang cocok dengan filter tersebut.')
        return

    table = [{
        'Channel': r['title'],
        'Handle': r.get('custom_url', ''),
        'Kemiripan (%)': r['similarity_score'],
        'Subscriber': r.get('subs', '0'),
        'Total Views': r.get('total_views', '0'),
        'Video': r.get('videos', '0'),
        'Alasan Kecocokan': r['match_reasons'],
    } for r in results]
    st.dataframe(pd.DataFrame(table), hide_index=True, use_container_width=True)
    st.download_button('Unduh Daftar Similar Channels (CSV)', csv_bytes(table), 'similar-channels.csv', 'text/csv')


def niche_overview_page(backend):
    st.title('Niche Finder & Niche Overview')
    st.caption('Evaluasi potensi niche secara menyeluruh: skor peluang niche, tingkat tembus channel kecil (small-channel breakout), kesiapan iklan mid-roll, dan ekspor data.')

    with st.form('niche_overview_form'):
        query = st.text_input('Nama Niche atau Sub-Niche', placeholder='Contoh: sejarah kuno, stoikisme, eksperimen sains', key='niche_ov_query')
        a, b, c = st.columns(3)
        country_label = a.selectbox('Wilayah', list(backend.COUNTRY_CODES.keys()), index=1, key='niche_ov_country')
        days = b.selectbox('Rentang usia publikasi sampel', [7, 30, 90, 365, 0], index=1, format_func=lambda d: f'{d} hari terakhir' if d else 'Semua waktu', key='niche_ov_days')
        own_subs = c.number_input('Subscriber Anda (opsional)', min_value=0, value=0, step=500, key='niche_ov_subs')
        d1, d2 = st.columns(2)
        rpm_lo = d1.number_input('Asumsi RPM Bawah (USD)', min_value=0.1, value=1.5, step=0.5, key='niche_ov_rpm_lo')
        rpm_hi = d2.number_input('Asumsi RPM Atas (USD)', min_value=0.1, value=4.0, step=0.5, key='niche_ov_rpm_hi')
        run = st.form_submit_button('Analisis Niche Overview', type='primary')

    if run:
        if not str(query or '').strip():
            st.warning('Masukkan nama niche yang ingin dianalisis.')
        else:
            region = backend.COUNTRY_CODES[country_label]
            pub_after = backend.get_published_after_rfc3339(days) if days else None
            with st.spinner('Mengumpulkan sampel video dan menghitung indikator Niche Overview...'):
                rows = backend.search_youtube(
                    query=str(query).strip(),
                    region_code=region,
                    published_after=pub_after,
                    sort_order='relevance',
                    max_results=30
                )
            overview = compute_niche_overview(
                str(query).strip(),
                rows,
                own_subscribers=own_subs or None,
                rpm_low=min(rpm_lo, rpm_hi),
                rpm_high=max(rpm_lo, rpm_hi),
            )
            st.session_state['niche_overview_bundle'] = {'overview': overview, 'rows': rows}

    bundle = st.session_state.get('niche_overview_bundle')
    if not bundle:
        st.info('Jalankan analisis niche di atas untuk melihat kartu skor Niche Overview, daftar channel teratas, outlier video, dan opsi ekspor.')
        return

    ov = bundle['overview']
    rows = bundle['rows']
    if not rows:
        st.warning('Tidak ada video yang ditemukan untuk kueri tersebut.')
        return

    s = ov['summary']
    m1, m2, m3, m4 = st.columns(4)
    m1.metric('Niche Score', f"{ov['niche_score']}/100")
    m2.metric('Median VPH', f"{s['median_vph']:,}")
    m3.metric('Small-Channel Gems', f"{s['small_channel_gems_count']} ({s['small_channel_win_pct']}%)")
    m4.metric('Layak Mid-Roll (≥8m)', f"{s['midroll_eligible_pct']}%")

    st.info(f"**Kesimpulan Niche ({ov['niche']}):** {ov['verdict']} · **Estimasi Pendapatan Median Video:** {s['median_video_est_revenue_usd']} (pada asumsi RPM {s['estimated_rpm_range_usd']})")

    dl_col1, dl_col2 = st.columns(2)
    dl_col1.download_button(
        'Ekspor Video Niche Overview (CSV)',
        csv_bytes(rows),
        f"niche-overview-{ov['niche'].replace(' ', '-')}.csv",
        'text/csv',
        use_container_width=True
    )
    dl_col2.download_button(
        'Ekspor Ringkasan Niche (JSON)',
        json.dumps(ov, ensure_ascii=False, indent=2),
        f"niche-overview-{ov['niche'].replace(' ', '-')}.json",
        'application/json',
        use_container_width=True
    )

    t1, t2, t3, t4 = st.tabs(['Komponen Skor', 'Outlier & Small Gems', 'Top Channel di Sampel', 'Peluang Sub-Niche'])
    with t1:
        st.dataframe(pd.DataFrame(ov['components']), hide_index=True, use_container_width=True)
    with t2:
        out_table = [{
            'Judul': v.get('title', ''),
            'Channel': v.get('channel', ''),
            'Subscriber': v.get('subs', '0'),
            'Views': v.get('views_fmt', '0'),
            'VPH': v.get('vph', 0),
            'Rasio Views/Subs': v.get('ratio_label', '0x'),
            'Durasi': v.get('duration', ''),
            'URL': v.get('link', ''),
        } for v in ov['outlier_videos']]
        st.dataframe(pd.DataFrame(out_table), hide_index=True, use_container_width=True)
    with t3:
        st.dataframe(pd.DataFrame(ov['top_channels']), hide_index=True, use_container_width=True)
    with t4:
        st.dataframe(pd.DataFrame(ov['sub_niches']), hide_index=True, use_container_width=True)


def thumbnail_compressor_page(backend):
    st.title('Thumbnail Compressor')
    st.caption('Kompres ukuran file thumbnail secara otomatis agar di bawah batas 2 MB YouTube tanpa mengorbankan ketajaman resolusi HD (1280×720).')

    uploaded = st.file_uploader('Unggah file thumbnail (PNG, JPG, WebP)', type=['png', 'jpg', 'jpeg', 'webp'], key='compressor_upload')
    c1, c2, c3 = st.columns(3)
    target_kb = c1.selectbox(
        'Batas ukuran maksimum',
        [1950, 1000, 500, 250],
        format_func=lambda kb: f'{kb} KB (~1.95 MB Standar YouTube)' if kb == 1950 else f'{kb} KB',
        key='compressor_target_kb'
    )
    res_choice = c2.selectbox('Resolusi target', ['1280x720 (HD Standar YouTube)', '1920x1080 (Full HD)', 'Pertahankan ukuran asli'], key='compressor_res')
    fmt_choice = c3.selectbox('Format keluaran', ['JPEG', 'WEBP', 'PNG'], key='compressor_fmt')

    res_map = {
        '1280x720 (HD Standar YouTube)': (1280, 720),
        '1920x1080 (Full HD)': (1920, 1080),
        'Pertahankan ukuran asli': None,
    }

    if uploaded is not None:
        raw_bytes = uploaded.getvalue()
        result = compress_thumbnail(
            raw_bytes,
            max_bytes=target_kb * 1024,
            target_resolution=res_map[res_choice],
            output_format=fmt_choice,
        )
        m1, m2, m3, m4 = st.columns(4)
        m1.metric('Ukuran Awal', f"{result['original_bytes'] / 1024:,.1f} KB")
        m2.metric('Ukuran Akhir', f"{result['compressed_bytes'] / 1024:,.1f} KB")
        m3.metric('Penghematan', f"{result['reduction_pct']}%")
        m4.metric('Status <2MB YouTube', 'Aman (<2 MB)' if result['under_youtube_limit'] else 'Melebihi 2 MB')

        st.image(result['data'], caption=f"Pratinjau Hasil ({result['final_size'][0]}×{result['final_size'][1]} px · {result['format']})", width=480)
        ext = 'jpg' if result['format'] == 'JPEG' else result['format'].lower()
        st.download_button(
            f"Unduh Thumbnail Terkompresi (.{ext})",
            result['data'],
            f"thumbnail-compressed.{ext}",
            f"image/{result['format'].lower()}",
            type='primary'
        )
    else:
        st.info('Unggah gambar thumbnail Anda di atas untuk mengompresi ukuran file secara instan.')


def ad_placer_page(backend):
    st.title('Automatic Ad Placer (Mid-Roll Generator)')
    st.caption('Susun titik penempatan iklan mid-roll secara otomatis untuk video berdurasi minimal 8 menit (480 detik) berdasarkan kurva retensi dan jeda transisi transkrip.')

    with st.form('ad_placer_form'):
        a, b, c = st.columns(3)
        minutes = a.number_input('Durasi Video (Menit)', min_value=1, max_value=300, value=12, step=1, key='ad_min')
        seconds = b.number_input('Detik Tambahan', min_value=0, max_value=59, value=30, step=5, key='ad_sec')
        strategy = c.selectbox('Strategi Kepadatan Iklan', ['Seimbang (Setiap ~3 Menit)', 'Konservatif (Setiap ~4 Menit)', 'Agresif (Setiap ~2 Menit)'], key='ad_strategy')
        first_ad = st.slider('Waktu iklan pertama paling awal (detik)', min_value=60, max_value=180, value=90, step=15, key='ad_first_sec')
        transcript = st.text_area(
            'Transkrip atau Daftar Chapter Bertimestamp (Opsional — agar iklan jatuh tepat di jeda topik)',
            height=150,
            placeholder='00:00 Pembukaan\n01:35 Masuk ke pembahasan pertama\n04:40 Studi kasus kedua\n07:50 Kesalahan yang sering terjadi\n10:45 Kesimpulan',
            key='ad_transcript'
        )
        run = st.form_submit_button('Susun Titik Iklan Mid-Roll Otomatis', type='primary')

    if run:
        total_sec = int(minutes) * 60 + min(59, int(seconds))
        st.session_state['ad_placer_result'] = generate_midroll_ad_breaks(
            total_sec,
            transcript_text=transcript,
            strategy=strategy,
            first_ad_seconds=first_ad,
        )

    res = st.session_state.get('ad_placer_result')
    if not res:
        return

    if not res['eligible']:
        st.warning(res['message'])
        return

    st.success(res['message'])
    st.write('**Daftar Timestamp untuk YouTube Studio (Salin & Tempel):**')
    st.code(res['studio_timestamps'], language='text')
    st.dataframe(pd.DataFrame(res['placements']), hide_index=True, use_container_width=True)
    st.download_button('Unduh Jadwal Mid-Roll (CSV)', csv_bytes(res['placements']), 'midroll-placements.csv', 'text/csv')


def profit_combined_page(backend):
    st.title('Net Profit Calculator & Combined Analytics')
    st.caption('Hitung laba bersih produksi channel (AdSense + Sponsor dikurangi biaya tim, tools, dan pajak) serta gabungkan analitik lintas channel dalam satu dasbor.')

    tab_profit, tab_combined = st.tabs(['Net Profit Calculator', 'Combined Analytics (Multi-Channel)'])

    with tab_profit:
        with st.form('net_profit_form'):
            c1, c2, c3 = st.columns(3)
            currency = c1.selectbox('Mata Uang', ['USD', 'IDR'], key='np_currency')
            monthly_views = c2.number_input('Estimasi / Aktual Views Bulanan', min_value=0, value=250_000, step=10_000, key='np_views')
            rpm = c3.number_input('RPM Rata-rata (per 1.000 views)', min_value=0.0, value=3.0, step=0.25, key='np_rpm')

            c4, c5, c6 = st.columns(3)
            vids_mo = c4.number_input('Jumlah Upload Video / Bulan', min_value=0, value=8, step=1, key='np_vids')
            cost_vid = c5.number_input('Biaya Produksi per Video (Script/VO/Editor/Thumb)', min_value=0.0, value=35.0, step=5.0, key='np_cost_vid')
            fixed_cost = c6.number_input('Biaya Langganan Tools / Tetap Bulanan', min_value=0.0, value=50.0, step=10.0, key='np_fixed')

            c7, c8, c9, c10 = st.columns(4)
            sponsor = c7.number_input('Pendapatan Sponsor Bulanan', min_value=0.0, value=0.0, step=50.0, key='np_sponsor')
            affiliate = c8.number_input('Pendapatan Afiliasi Bulanan', min_value=0.0, value=0.0, step=25.0, key='np_affiliate')
            rev_share = c9.number_input('Bagi Hasil Tim / Agensi (%)', min_value=0.0, max_value=100.0, value=0.0, step=5.0, key='np_revshare')
            tax = c10.number_input('Estimasi Pajak (%)', min_value=0.0, max_value=100.0, value=0.0, step=2.5, key='np_tax')

            calc = st.form_submit_button('Hitung Net Profit Channel', type='primary')

        if calc:
            try:
                st.session_state['net_profit_result'] = calculate_net_profit(
                    monthly_views=monthly_views,
                    rpm=rpm,
                    videos_per_month=vids_mo,
                    cost_per_video=cost_vid,
                    monthly_fixed_cost=fixed_cost,
                    sponsor_revenue=sponsor,
                    affiliate_revenue=affiliate,
                    tax_pct=min(40.0, float(tax)),
                    rev_share_pct=min(40.0, float(rev_share)),
                    currency=currency,
                )
            except ValueError as exc:
                st.warning(str(exc))

        np_res = st.session_state.get('net_profit_result')
        if np_res:
            cur = np_res['currency']
            k1, k2, k3, k4 = st.columns(4)
            k1.metric('Pendapatan Kotor (Gross)', f"{cur} {np_res['total_gross_revenue']:,.2f}")
            k2.metric('Total Biaya Produksi', f"{cur} {np_res['total_expenses']:,.2f}")
            k3.metric('Laba Bersih (Net Profit)', f"{cur} {np_res['net_profit']:,.2f}")
            k4.metric('Margin Laba Bersih', f"{np_res['profit_margin_pct']}%")

            breakdown = [
                {'Komponen': 'Gross AdSense Revenue', 'Nilai': f"{cur} {np_res['adsense_gross']:,.2f}"},
                {'Komponen': 'Sponsor + Afiliasi', 'Nilai': f"{cur} {(np_res['sponsor_revenue'] + np_res['affiliate_revenue']):,.2f}"},
                {'Komponen': f"Biaya Produksi ({np_res['videos_per_month']} video)", 'Nilai': f"- {cur} {np_res['video_production_cost']:,.2f}"},
                {'Komponen': 'Biaya Tools & Operasional Tetap', 'Nilai': f"- {cur} {np_res['monthly_fixed_cost']:,.2f}"},
                {'Komponen': 'Bagi Hasil & Pajak', 'Nilai': f"- {cur} {(np_res['rev_share_amount'] + np_res['tax_amount']):,.2f}"},
                {'Komponen': 'Laba Bersih per Video', 'Nilai': f"{cur} {np_res['profit_per_video']:,.2f}"},
                {'Komponen': 'Titik Impas (Break-Even Views Bulanan)', 'Nilai': f"{np_res['break_even_views']:,} views ({np_res['break_even_views_per_video']:,} views/video)"},
            ]
            if np_res['roi_pct'] is not None:
                breakdown.append({'Komponen': 'Return on Investment (ROI)', 'Nilai': f"{np_res['roi_pct']}%"})
            st.dataframe(pd.DataFrame(breakdown), hide_index=True, use_container_width=True)

    with tab_combined:
        st.write('Gabungkan analitik dari beberapa channel (dari daftar perbandingan/analisis sesi ini atau input multi-channel).')
        cached_channels = st.session_state.get('channel_details', {})

        with st.form('combined_analytics_form'):
            ch_lines = st.text_area(
                'Masukkan daftar channel dengan format: Nama Channel, Subscriber, Total Views, Jumlah Video, Views Bulan Ini (satu channel per baris)',
                value='Channel Faceless A, 25000, 3500000, 60, 180000\nChannel Faceless B, 12000, 1400000, 42, 95000',
                height=110,
                key='comb_manual_lines'
            )
            a, b = st.columns(2)
            comb_rpm = a.number_input('Asumsi RPM Gabungan', min_value=0.1, value=2.5, step=0.25, key='comb_rpm')
            comb_cur = b.selectbox('Mata Uang Estimasi', ['USD', 'IDR'], key='comb_cur')
            include_session = st.checkbox('Sertakan juga channel yang sudah dianalisis pada sesi ini', value=True, key='comb_inc_session')
            run_comb = st.form_submit_button('Gabungkan Analitik Channel', type='primary')

        if run_comb:
            entries = []
            if include_session:
                for cid, (_, ch_data) in cached_channels.items():
                    entries.append(ch_data)
            for line in str(ch_lines or '').splitlines():
                parts = [p.strip() for p in line.split(',') if p.strip()]
                if len(parts) >= 4:
                    entries.append({
                        'title': parts[0],
                        'raw_subs': parts[1],
                        'raw_total_views': parts[2],
                        'raw_videos': parts[3],
                        'recent_videos': [{'title': f"Katalog {parts[0]}", 'raw_views': parts[4] if len(parts) >= 5 else parts[2], 'date': 'Periode aktif'}],
                    })
            if not entries:
                entries.append({'title': 'Channel Faceless Default', 'raw_subs': 10000, 'raw_total_views': 500000, 'raw_videos': 25})
            st.session_state['combined_analytics_result'] = combine_channel_analytics(entries, rpm_assumption=comb_rpm, currency=comb_cur)

        comb_res = st.session_state.get('combined_analytics_result')
        if comb_res:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric('Total Channel', comb_res['channel_count'])
            c2.metric('Total Subscriber Gabungan', f"{comb_res['combined_subscribers']:,}")
            c3.metric('Total Views Sampel/Periode', f"{comb_res['combined_sample_views']:,}")
            c4.metric(f"Estimasi Gross ({comb_res['currency']})", f"{comb_res['currency']} {comb_res['combined_estimated_revenue']:,.2f}")

            st.dataframe(pd.DataFrame(comb_res['channels_table']), hide_index=True, use_container_width=True)
            st.download_button(
                'Unduh Combined Analytics (CSV)',
                csv_bytes(comb_res['channels_table']),
                'combined-analytics.csv',
                'text/csv'
            )


def screenshot_studio_page(backend):
    st.title('Screenshot Studio (Analytics, Channel & Video Cards)')
    st.caption('Buat gambar tangkapan layar (PNG) berkualitas tinggi untuk laporan analitik channel (dengan opsi sembunyikan data sensitif), profil channel, maupun kartu performa video terbaru.')

    tab_an, tab_ch, tab_vid = st.tabs([
        'Screenshot Analytics (Hide Sensitive Data)',
        'Channel Page Screenshot',
        'Video Performance Screenshot'
    ])

    with tab_an:
        c1, c2, c3 = st.columns(3)
        hide_sens = c1.checkbox('Mode Privasi (Sembunyikan angka sensitif)', value=True, key='ss_hide_sens')
        hide_name = c2.checkbox('Sembunyikan nama channel', value=True, key='ss_hide_name')
        hide_rev = c3.checkbox('Sembunyikan pendapatan (Revenue)', value=True, key='ss_hide_rev')

        owner_rep = st.session_state.get('owner_report', {}).get('frame')
        if owner_rep is not None and not owner_rep.empty:
            metrics = {
                'Views Periode': f"{owner_rep['views'].sum():,.0f}",
                'Median Views': f"{owner_rep['views'].median():,.0f}",
                'Median CTR': f"{owner_rep['ctr'].median():.2f}%" if 'ctr' in owner_rep else 'N/A',
                'Est. Revenue': f"${owner_rep['views'].sum() / 1000 * 2.5:,.2f}",
            }
            series = list(owner_rep['views'].head(10))
            ch_title = 'Laporan Evaluasi Channel'
        else:
            metrics = {
                'Total Views (28d)': '482.9K',
                'Watch Time (Hours)': '31.4K',
                'Subscribers': '+1,840',
                'Est. Revenue': '$1,420.50',
            }
            series = [12000, 15400, 14200, 19800, 24500, 28100, 34900]
            ch_title = st.text_input('Nama Channel pada Kartu', value='My Faceless Channel', key='ss_an_ch_name')

        png_bytes = render_analytics_screenshot(
            ch_title,
            metrics,
            series_values=series,
            hide_sensitive=hide_sens,
            hide_channel_name=hide_name,
            hide_revenue=hide_rev,
        )
        st.image(png_bytes, caption='Pratinjau Screenshot Analytics', use_container_width=True)
        st.download_button('Unduh Screenshot Analytics (PNG)', png_bytes, 'analytics-screenshot.png', 'image/png', type='primary')

    with tab_ch:
        hide_ch_sens = st.checkbox('Sembunyikan identitas & jumlah subscriber', value=False, key='ss_ch_hide')
        cached = st.session_state.get('channel_details', {})
        if cached:
            cid = st.selectbox('Pilih channel yang sudah dianalisis', list(cached.keys()), format_func=lambda k: cached[k][1].get('title', k), key='ss_ch_pick')
            ch_data = cached[cid][1]
        else:
            ch_data = {
                'title': 'Contoh Channel Riset',
                'custom_url': '@contohchannel',
                'subs': '45.2K',
                'raw_subs': 45200,
                'total_views': '8.4M',
                'raw_total_views': 8400000,
                'video_count': '124',
                'avg_recent_views': '68.5K',
                'recent_videos': [
                    {'title': 'Mengapa Strategi Konten Ini Berhasil Tembus 500K Views', 'views': '512K'},
                    {'title': 'Cara Riset Niche YouTube Menggunakan Data Outlier', 'views': '184K'},
                    {'title': 'Panduan Optimasi Kecepatan Penayangan (VPH)', 'views': '92K'},
                ]
            }
        ch_png = render_channel_screenshot(ch_data, hide_sensitive=hide_ch_sens)
        st.image(ch_png, caption='Pratinjau Channel Page Screenshot', use_container_width=True)
        st.download_button('Unduh Channel Page Screenshot (PNG)', ch_png, 'channel-page-screenshot.png', 'image/png', type='primary')

    with tab_vid:
        hide_vid_sens = st.checkbox('Sembunyikan judul & nama channel pada kartu video', value=False, key='ss_vid_hide')
        vids = _session_videos()
        if vids:
            v_idx = st.selectbox('Pilih video dari hasil riset sesi ini', range(len(vids)), format_func=lambda i: vids[i].get('title', f'Video {i+1}'), key='ss_vid_pick')
            v_data = vids[v_idx]
        else:
            v_data = {
                'title': 'Rahasia Riset Niche YouTube dengan Outlier & VPH Tinggi',
                'channel': 'Creator Lab ID',
                'duration': '12:45',
                'views_fmt': '148.5K',
                'vph_fmt': '1,240',
                'ratio_label': '6.4x',
                'ratio': 6.4,
                'er': 4.85,
                'seo_score': 92,
            }
        vid_png = render_video_performance_screenshot(v_data, hide_sensitive=hide_vid_sens)
        st.image(vid_png, caption='Pratinjau Video Performance Screenshot', use_container_width=True)
        st.download_button('Unduh Video Performance Screenshot (PNG)', vid_png, 'video-performance-screenshot.png', 'image/png', type='primary')
