"""Quiet, task-oriented presentation for the original Niche Hunter services.

All remote work is explicit. UI state is scoped to the result set or video.
The supplied backend mapping keeps the original calculations in app.py.
"""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from types import SimpleNamespace
import re
import time
import urllib.parse

import matplotlib.pyplot as plt
import pandas as pd
import requests
import streamlit as st
from modules.growth_ui import seo_page, research_page, evaluation_page, open_seo, save_watch
from modules.growth_engine import ResearchStore, safe_video
from modules.intelligence import csv_bytes
from modules.workspace_ui import keyword_page, rank_page, competitor_page, planner_page, experiment_page, bulk_page
from modules.nexlev_engine import (
    check_monetization_status,
    render_channel_screenshot,
    render_video_performance_screenshot,
    sort_channel_videos,
)
from modules.nexlev_ui import (
    ad_placer_page,
    monetization_transcript_page,
    niche_overview_page,
    profit_combined_page,
    render_advanced_feed_filter,
    screenshot_studio_page,
    similar_channels_page,
    similar_thumbnail_page,
    thumbnail_compressor_page,
)
import sqlite3


def clean_label(value):
    return re.sub(r"^[^A-Za-z0-9]+", "", str(value)).strip()


def select(label, options, name, default=0, **kwargs):
    options = list(options)
    prefs = st.session_state.setdefault("ui_preferences", {})
    key = "field_" + name
    if key in st.session_state and st.session_state[key] not in options:
        st.session_state[key] = options[default]
    if key not in st.session_state:
        saved = prefs.get(name, options[default])
        st.session_state[key] = saved if saved in options else options[default]
    value = st.selectbox(label, options, key=key, **kwargs)
    prefs[name] = value
    return value


def text_input(label, name, **kwargs):
    prefs = st.session_state.setdefault("ui_preferences", {})
    key = "field_" + name
    if key not in st.session_state:
        st.session_state[key] = prefs.get(name, "")
    value = st.text_input(label, key=key, **kwargs)
    prefs[name] = value
    return value


def amount(label, name, minimum=5, maximum=50, default=12):
    prefs = st.session_state.setdefault("ui_preferences", {})
    key = "field_" + name
    if key not in st.session_state:
        st.session_state[key] = prefs.get(name, default)
    value = st.slider(label, minimum, maximum, key=key)
    prefs[name] = value
    return value


def route(section, page, channel_id=None):
    st.session_state["pending_route"] = (section, page)
    if channel_id:
        st.session_state["selected_channel"] = channel_id


def compare_add(channel_id):
    queue = st.session_state.setdefault("compare_list", [])
    if channel_id not in queue:
        if len(queue) >= 4:
            st.session_state["notice"] = "Daftar berisi 4 channel. Hapus salah satu sebelum menambahkan channel baru."
        else:
            queue.append(channel_id)
    route("Channel", "Perbandingan")


def compare_remove(channel_id):
    queue = st.session_state.setdefault("compare_list", [])
    if channel_id in queue:
        queue.remove(channel_id)


def apply_suggestion(query):
    st.session_state.setdefault("ui_preferences", {})["video_query"] = query
    st.session_state["field_video_query"] = query
    st.session_state["query_suggestions"] = []


def result_id(*values):
    return sha256(repr(values).encode()).hexdigest()[:16]


def run_ai(label, key, callback):
    cache = st.session_state.setdefault("ai_answers", {})
    if st.button(label if key not in cache else "Buat ulang analisis", key="ai_" + key):
        with st.spinner("Menyiapkan analisis..."):
            cache[key] = callback()
    if key in cache:
        answer = cache[key]
        if isinstance(answer, dict):
            st.json(answer)
        else:
            st.markdown(str(answer))
        st.caption("Hasil AI perlu ditinjau bersama data sumber. Tersimpan selama sesi ini.")


def empty_state(title, detail):
    st.markdown(
        f'<div class="empty-state"><h3>{escape(title)}</h3><p>{escape(detail)}</p></div>',
        unsafe_allow_html=True,
    )


def save_result(key, rows, **context):
    # Context belongs to the submitted query, not to the currently edited form.
    if rows:
        try:
            ResearchStore().save('history', str(time.time_ns()), {'mode': key, 'query': context.get('query',''), 'context': context.get('context',''), 'jumlah':len(rows), 'videos':[safe_video(r) for r in rows[:50] if r.get('id') and r.get('title') and r.get('link')]})
        except (OSError, sqlite3.Error):
            st.warning('Riwayat belum tersimpan. Hasil tetap tersedia selama sesi.')
    st.session_state[key] = {"rows": rows, "at": datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
                             "revision": time.time_ns(), **context}
    st.session_state["field_" + key + "_page"] = 1


def result_header(bundle, filename):
    a, b = st.columns([4, 1])
    with a:
        st.subheader(f"{len(bundle['rows'])} hasil")
        st.caption(f"{bundle.get('query', '')} | {bundle.get('context', '')} | {bundle['at']}")
    with b:
        st.download_button("Unduh CSV", csv_bytes(bundle["rows"]),
                           filename, "text/csv", key="csv_" + filename, use_container_width=True)


def page_items(rows, name, size=6):
    pages = max(1, (len(rows) + size - 1) // size)
    if pages == 1:
        return rows
    page = select("Halaman hasil", range(1, pages + 1), name + "_page",
                  format_func=lambda p: f"{p} dari {pages}")
    st.caption(f"Menampilkan {(page-1)*size+1} sampai {min(page*size, len(rows))} dari {len(rows)} hasil.")
    return rows[(page-1)*size:page*size]


def video_detail(video, backend, scope):
    mon = check_monetization_status(video, kind="video")
    metrics = [("Likes", video.get("likes", 0)), ("Komentar", video.get("comments", 0)),
               ("Engagement", f"{video.get('er', 0)}%"), ("Views / subscriber", video.get("ratio_label", "0x")),
               ("Kelengkapan metadata", f"{video.get('seo_score', 0)}/100"),
               ("Status Monetisasi (Indikator)", mon["status_label"]),
               ("Estimasi pendapatan", video.get("earnings", "Tidak tersedia"))]
    st.dataframe(pd.DataFrame(metrics, columns=["Indikator", "Nilai"]), hide_index=True, use_container_width=True)
    st.caption("Pendapatan perlu asumsi RPM dari pengguna. VPH pencarian adalah rata-rata sejak publikasi, bukan laju real-time.")
    st.write("**Ringkasan deskripsi**")
    for point in video.get("summary", []):
        st.write(point)
    st.write("**Checklist SEO**")
    for check in video.get("seo_checks", []):
        st.write(check)
    if video.get("tags"):
        st.caption("Tag video")
        st.code(", ".join(video["tags"]), language="text")
    c,d = st.columns(2)
    c.button('Optimalkan ide ini',key=f'seo_{scope}_{video["id"]}',on_click=open_seo,args=(video,),use_container_width=True)
    d.button('Simpan watchlist',key=f'watch_{scope}_{video["id"]}',on_click=save_watch,args=(video,),use_container_width=True)
    with st.expander('Simulasi pendapatan berdasarkan asumsi RPM'):
        currency=st.selectbox('Mata uang',['IDR','USD'],key=f'currency_{scope}_{video["id"]}')
        low=st.number_input('Asumsi RPM minimum',min_value=0.0,value=0.0,key=f'rpm_lo_{scope}_{video["id"]}')
        high=st.number_input('Asumsi RPM maksimum',min_value=0.0,value=0.0,key=f'rpm_hi_{scope}_{video["id"]}')
        views=video.get('raw_views',video.get('views',0))
        if high < low: st.warning('RPM maksimum harus minimal sama dengan minimum.')
        elif high > 0: st.write(f'Skenario {currency}: {views/1000*low:,.2f} sampai {views/1000*high:,.2f}')
        st.caption('Asumsi diisi pengguna. Bukan pendapatan terukur dan tidak memperhitungkan seluruh faktor monetisasi.')
    a, b = st.columns(2)
    a.button("Analisis channel", key=f"analyze_{scope}_{video['id']}", on_click=route,
             args=("Channel", "Analisis", video["channel_id"]), use_container_width=True)
    b.button("Bandingkan channel", key=f"compare_{scope}_{video['id']}", on_click=compare_add,
             args=(video["channel_id"],), use_container_width=True)
    run_ai("Analisis Channel DNA", "dna_" + result_id(video["channel_id"], video["id"], video.get("views")),
           lambda: backend.channel_insight({"channel_id": video["channel_id"], "channel": video.get("channel"),
               "title": video.get("title"), "views": video.get("views_fmt"), "tags": video.get("tags")}))
    thumb_key = "thumbnail_" + video["id"]
    if st.button("Siapkan unduhan thumbnail", key="get_" + scope + thumb_key):
        try:
            response = requests.get(video["thumbnail"], timeout=15)
            response.raise_for_status()
            st.session_state[thumb_key] = response.content
        except requests.RequestException:
            st.warning("Thumbnail belum dapat diunduh. Coba lagi.")
    if thumb_key in st.session_state:
        st.download_button("Unduh thumbnail", st.session_state[thumb_key], f"thumb_{video['id']}.jpg",
                           "image/jpeg", key="download_" + scope + thumb_key)


def video_cards(rows, backend, scope, trending=False):
    for row_start in range(0, len(rows), 2):
        columns = st.columns(2, gap="large")
        for col, video in zip(columns, rows[row_start:row_start+2]):
            with col, st.container(border=True):
                if video.get("thumbnail"):
                    st.image(video["thumbnail"], use_container_width=True)
                st.markdown(f"**{video['title']}**")
                st.caption(f"{video.get('channel', '')} | {video.get('subs', '0')} subscriber")
                st.caption(f"{video.get('published_simple', '')} | {video.get('duration', '')}")
                rank = f"Peringkat {video.get('rank', '')} | " if trending else ""
                st.write(f"{rank}{video.get('views_fmt', '0')} views | {video.get('vph_fmt', '0')} VPH")
                st.link_button("Tonton video", video["link"], use_container_width=True)
                with st.expander("Detail, SEO, dan tindakan"):
                    video_detail(video, backend, scope)


def market_analysis(bundle, backend, trending):
    rows = bundle["rows"]
    st.subheader("Pola publikasi sampel")
    st.write(backend.estimate_best_time(rows))
    st.caption("Ini pola waktu publikasi video sampel dalam WIB. Belum membuktikan waktu unggah terbaik untuk channel Anda.")
    st.subheader("Perbandingan VPH")
    st.bar_chart(pd.DataFrame(rows)[["title", "vph"]].set_index("title").head(10))
    tags = Counter(tag for video in rows for tag in video.get("tags", []))
    if tags:
        st.subheader("Tag yang sering muncul")
        st.dataframe(pd.DataFrame(tags.most_common(15), columns=["Tag", "Jumlah"]), hide_index=True, use_container_width=True)
    if not trending:
        st.subheader("Google Trends")
        key = "trends_" + result_id(bundle["query"], bundle.get("region"))
        if st.button("Muat tren kata kunci", key="load_" + key):
            with st.spinner("Mengambil Google Trends..."):
                st.session_state[key] = backend.get_rising_trends(bundle["query"], bundle.get("region"))
        if key in st.session_state:
            trends = st.session_state[key]
            if trends is None:
                st.info("Google Trends belum dapat diambil. Anda dapat membukanya langsung.")
            elif trends:
                st.dataframe(pd.DataFrame(trends), hide_index=True, use_container_width=True)
            else:
                st.caption("Tidak ada rising keyword yang dikembalikan untuk sampel ini.")
        query = urllib.parse.urlencode({"date": "now 7-d", "gprop": "youtube", "q": bundle["query"], "geo": bundle.get("region") or ""})
        st.link_button("Buka Google Trends", "https://trends.google.com/trends/explore?" + query)


def video_search(backend, trending=False):
    scope = "trending" if trending else "video"
    st.title("Trending" if trending else "Pencarian video")
    st.caption("Lihat video populer per wilayah." if trending else "Cari referensi video, lalu buka analisis saat diperlukan.")
    with st.form(scope + "_form", border=False):
        if not trending:
            query = text_input("Kata kunci", "video_query", placeholder="Contoh: ASMR rain, cover musik, tutorial Excel")
        else:
            query = "Trending"
        a, b = st.columns(2)
        with a:
            country = select("Wilayah", backend.COUNTRY_CODES, scope + "_country", default=1, format_func=clean_label)
        with b:
            if trending:
                category = select("Kategori", backend.CATEGORIES, scope + "_category")
            else:
                sort = select("Urutkan berdasarkan", backend.SORT_OPTIONS, "video_sort")
        with st.expander("Filter lanjutan"):
            if not trending:
                a, b = st.columns(2)
                with a:
                    duration = select("Durasi", ["Semua", "Short (<4m)", "Medium (4-20m)", "Long (>20m)"], "video_duration",
                                      help="Short pada filter ini berarti video di bawah 4 menit, bukan klasifikasi YouTube Shorts.")
                    period = select("Waktu publikasi", backend.TIME_FILTERS, "video_period")
                with b:
                    category = select("Kategori", backend.CATEGORIES, "video_category")
                    license_name = select("Lisensi", backend.LICENSE_OPTIONS, "video_license")
            maximum = amount("Jumlah hasil", scope + "_maximum")
        a, b = st.columns([2, 1])
        with a:
            search = st.form_submit_button("Lihat trending" if trending else "Cari video", type="primary", use_container_width=True)
        with b:
            suggest = st.form_submit_button("Saran kata kunci", use_container_width=True) if not trending else False
    if suggest:
        if len(query.strip()) < 2:
            st.warning("Masukkan minimal dua karakter untuk mencari saran.")
        else:
            with st.spinner("Mencari saran..."):
                st.session_state["query_suggestions"] = backend.get_youtube_suggestions(query.strip())
            if not st.session_state["query_suggestions"]:
                st.info("Belum ada saran yang dapat diambil. Kata kunci tetap bisa dicari langsung.")
    if not trending and st.session_state.get("query_suggestions"):
        suggestions = st.session_state["query_suggestions"]
        with st.expander("Saran kata kunci", expanded=True):
            chosen = st.selectbox("Pilih saran", suggestions, key="suggestion_choice")
            st.button("Gunakan kata kunci", on_click=apply_suggestion, args=(chosen,))
    result_key = scope + "_results_bundle"
    if search:
        if not query.strip():
            st.warning("Masukkan kata kunci terlebih dahulu.")
        else:
            with st.spinner("Mengambil video..."):
                region = backend.COUNTRY_CODES[country]
                if trending:
                    rows = backend.get_trending_videos(region, backend.CATEGORIES[category], maximum)
                else:
                    durations = {"Short (<4m)": "short", "Medium (4-20m)": "medium", "Long (>20m)": "long"}
                    rows = backend.search_youtube(query=query.strip(), region_code=region, duration=durations.get(duration, "any"),
                        category_id=backend.CATEGORIES[category], published_after=backend.get_published_after_rfc3339(backend.TIME_FILTERS[period]),
                        license_type=backend.LICENSE_OPTIONS[license_name], sort_order=backend.SORT_OPTIONS[sort], max_results=maximum)
                context = f"{clean_label(country)}, {category}" if trending else f"{clean_label(country)}, {sort}, {period}, {duration}, {category}, {license_name}"
                save_result(result_key, rows, query=query.strip(), context=context, region=region)
    bundle = st.session_state.get(result_key)
    if not bundle:
        empty_state("Mulai dari satu pencarian", "Atur kata kunci atau wilayah, lalu jalankan pencarian. Detail analisis tersedia setelah hasil muncul.")
        return
    if not bundle["rows"]:
        empty_state("Belum ada hasil untuk pencarian ini", "Coba kata kunci yang lebih luas atau longgarkan filter. Periksa pesan API jika ditampilkan.")
        return
    result_header(bundle, "trending.csv" if trending else "data_riset.csv")
    tabs = st.tabs(["Hasil", "Analisis pasar"] + ([] if trending else ["Ide AI"]))
    with tabs[0]:
        filtered_rows = render_advanced_feed_filter(bundle["rows"], scope_prefix=scope)
        if not filtered_rows:
            st.info("Tidak ada video yang memenuhi kriteria Advanced Homepage Filter. Longgarkan filter di atas.")
        else:
            view = st.radio("Tampilan hasil", ["Kartu", "Tabel"], horizontal=True, key=scope + "_view", label_visibility="collapsed")
            if view == "Kartu":
                video_cards(page_items(filtered_rows, result_key), backend, scope, trending)
            else:
                cols = ["title", "channel", "views", "vph", "seo_score", "er", "ratio", "duration", "link"]
                st.dataframe(pd.DataFrame(filtered_rows).reindex(columns=cols), hide_index=True, use_container_width=True)
                selected = select("Detail video", range(len(filtered_rows)), scope + "_table_detail",
                                  format_func=lambda i: filtered_rows[i]["title"])
                video_detail(filtered_rows[selected], backend, scope + "_table")
    with tabs[1]:
        market_analysis(bundle, backend, trending)
    if not trending:
        with tabs[2]:
            st.caption(f"Ide berdasarkan kata kunci: {bundle['query']}")
            run_ai("Buat 5 ide konten", "ideas_" + result_id(bundle["query"]), lambda: backend.generate_ai_ideas(bundle["query"]))


def viral_page(backend):
    st.title("Viral Intelligence")
    st.caption("Cari sinyal awal pada video long-form baru. Skor adalah indikator heuristik, bukan jaminan viral.")
    with st.form("viral_form", border=False):
        query = text_input("Niche atau kata kunci", "viral_query", placeholder="Contoh: teknologi, cooking, football")
        a, b = st.columns(2)
        with a:
            country = select("Wilayah", backend.COUNTRY_CODES, "viral_country", 1, format_func=clean_label)
        with b:
            freshness = select("Rentang publikasi", ["24 Jam", "3 Hari", "7 Hari", "14 Hari", "30 Hari"], "viral_freshness", 2)
        with st.expander("Filter lanjutan"):
            a, b = st.columns(2)
            with a:
                category = select("Kategori", backend.CATEGORIES, "viral_category")
            with b:
                duration = select("Durasi minimum", ["4 Menit+", "8 Menit+", "20 Menit+"], "viral_duration")
            maximum = amount("Jumlah kandidat", "viral_maximum", 10, 50, 30)
        search = st.form_submit_button("Cari kandidat", type="primary", use_container_width=True)
    if search:
        if not query.strip():
            st.warning("Masukkan niche atau kata kunci terlebih dahulu.")
        else:
            with st.spinner("Mengumpulkan kandidat dan baseline channel..."):
                rows = backend.search_viral_longform(query.strip(), backend.COUNTRY_CODES[country], backend.CATEGORIES[category], maximum,
                    freshness_days={"24 Jam": 1, "3 Hari": 3, "7 Hari": 7, "14 Hari": 14, "30 Hari": 30}[freshness],
                    min_duration_seconds={"4 Menit+": 240, "8 Menit+": 480, "20 Menit+": 1200}[duration])
            save_result("viral_bundle", rows, query=query.strip(), context=f"{clean_label(country)}, {freshness}, {duration}")
    bundle = st.session_state.get("viral_bundle")
    if not bundle or not bundle["rows"]:
        empty_state("Temukan kandidat breakout", "Jalankan pencarian untuk menampilkan kandidat, radar, pola konten, dan peluang dari AI.")
        return
    rows = bundle["rows"]
    result_header(bundle, "viral_intelligence_v2.csv")
    top = rows[0]
    a, b, c = st.columns(3)
    a.metric("Kandidat", len(rows))
    b.metric("Skor tertinggi", f"{top.get('breakout_score', 0):.0f}/100")
    c.metric("Velocity kandidat teratas", f"{top.get('velocity_vph', 0):,} VPH")
    tab1, tab2, tab3 = st.tabs(["Kandidat", "Detail dan radar", "Peluang konten"])
    with tab1:
        table = [{"Judul": v["title"], "Channel": v["channel"], "Label": clean_label(v.get("viral_label", "NORMAL")),
                  "Skor": v.get("breakout_score", 0), "Usia (jam)": round(v.get("age_hours", 0), 1),
                  "VPH": v.get("velocity_vph", 0), "Akselerasi": v.get("acceleration", 1),
                  "Kelipatan baseline": v.get("channel_breakout_multiple", 0), "Views/subs": v.get("ratio", 0)} for v in rows]
        st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
        st.caption("Kelipatan baseline membandingkan VPH sejak publikasi kedua sisi. Velocity dapat memakai interval snapshot; keduanya tidak dicampur dalam rasio baseline.")
        with st.expander("Small Channel Breakouts"):
            gems = backend.small_channel_gems(rows)
            if gems:
                st.dataframe(pd.DataFrame(gems).reindex(columns=["title", "channel", "subs", "views_fmt", "velocity_vph", "channel_breakout_multiple", "breakout_score"]), use_container_width=True, hide_index=True)
            else:
                st.caption("Belum ada kandidat yang memenuhi kriteria small-channel breakout.")
    with tab2:
        index = select("Pilih kandidat", range(len(rows)), "viral_candidate", format_func=lambda i: rows[i]["title"])
        chosen = rows[index]
        a, b = st.columns([1, 1.4])
        with a:
            fig = backend.radar_chart(chosen)
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)
        with b:
            st.subheader(chosen["title"])
            st.write(f"{clean_label(chosen.get('viral_label', 'NORMAL'))} | {chosen.get('breakout_score', 0):.0f}/100")
            st.caption(f"{chosen['channel']} | {chosen.get('subs', 0)} subscriber | {chosen.get('duration', '')}")
            st.write(f"Views: {chosen.get('views_fmt', 0)} | Usia: {chosen.get('age_hours', 0):.1f} jam")
            st.write(f"Velocity: {chosen.get('velocity_vph', 0):,} VPH | Akselerasi: {chosen.get('acceleration', 1):.1f}x")
            st.write(f"Baseline: {chosen.get('channel_baseline_vph', 0):,} VPH | Kelipatan: {chosen.get('channel_breakout_multiple', 0):.1f}x")
            for reason in chosen.get("breakout_reasons", []):
                st.write(reason)
            st.caption(f"Snapshot tersedia: {chosen.get('snapshot_count', 0)}. Scan pertama dapat menggunakan rata-rata sejak publikasi.")
            st.caption(chosen.get('baseline_basis', 'Baseline sebanding belum tersedia.'))
            if chosen.get("channel_baseline_samples", 0) < 3:
                st.warning("Sampel baseline channel kurang dari 3 video. Perlakukan skor sebagai sinyal awal.")
            st.caption('Skor heuristik belum dikalibrasi sebagai probabilitas viral. Indikator dapat saling berkorelasi.')
            st.write('Kecukupan data: '+chosen.get('score_evidence','Belum tersedia'))
            if chosen.get('score_components'):
                st.dataframe(pd.DataFrame(chosen['score_components']),hide_index=True,use_container_width=True)
            st.button('Optimalkan ide ini',key='seo_viral_selected',on_click=open_seo,args=(chosen,))
            st.button('Simpan watchlist',key='watch_viral_selected',on_click=save_watch,args=(chosen,))
            st.link_button("Tonton video", chosen["link"])
    with tab3:
        st.caption(f"Referensi terpilih: {chosen['title']}")
        opportunity = backend.build_content_opportunity(chosen, bundle["query"])
        labels = {"topic": "Topik", "hook": "Hook", "angle": "Sudut pandang", "recommended_duration": "Durasi",
                  "title_formula": "Pola judul", "thumbnail": "Thumbnail", "why_now": "Alasan relevansi"}
        st.dataframe(pd.DataFrame([(labels[k], str(v)) for k, v in opportunity.items() if k in labels], columns=["Bagian", "Usulan"]), hide_index=True, use_container_width=True)
        run_ai("Kembangkan peluang dengan AI", "opportunity_" + result_id(bundle["query"], chosen["id"], bundle["revision"]),
               lambda: backend.generate_ai_content_opportunity(chosen, bundle["query"]))
        with st.expander("Pola kandidat unggulan"):
            patterns = backend.analyze_winning_patterns(rows)
            a, b, c = st.columns(3)
            a.metric("Video dalam pola", patterns.get("top_count", 0))
            b.metric("Rerata durasi", f"{patterns.get('avg_duration', 0):.0f} detik")
            c.metric("Rerata skor", patterns.get("avg_score", 0))
            st.write("Kata kunci: " + ", ".join(patterns.get("keywords", [])))
            st.write("Pola judul: " + ", ".join(f"{k} ({v})" for k, v in patterns.get("title_patterns", {}).items()))
        with st.expander("Analisis breakout dengan AI"):
            run_ai("Analisis kandidat dengan AI", "winners_" + result_id(bundle["query"], bundle["revision"], [v["id"] for v in rows]),
                   lambda: backend.generate_ai_winner_analysis(rows, bundle["query"]))


def channel_cards(rows, scope):
    for start in range(0, len(rows), 2):
        for col, channel in zip(st.columns(2, gap="large"), rows[start:start+2]):
            with col, st.container(border=True):
                a, b = st.columns([1, 4])
                with a:
                    if channel.get("thumb"):
                        st.image(channel["thumb"], width=56)
                with b:
                    st.markdown(f"**{channel['title']}**")
                    st.caption(channel.get("custom_url", ""))
                st.write(f"{channel.get('subs', 0)} subscriber | {channel.get('videos', 0)} video")
                with st.expander("Statistik channel"):
                    st.write(f"Total views: {channel.get('total_views', 0)}")
                    st.write(f"Rerata views: {channel.get('avg_views', 0)}")
                    st.caption("Rerata views direktori hanya dihitung oleh mesin asli jika filter VPH atau urutan pertumbuhan dipakai. Nilai 0 dapat berarti belum dihitung.")
                    st.write(f"Dibuat: {channel.get('published_at_str', '')} | Usia: {channel.get('age', '')}")
                    st.link_button("Buka di YouTube", "https://youtube.com/channel/" + channel["id"])
                a, b = st.columns(2)
                a.button("Analisis", key=f"channel_{scope}_{channel['id']}", on_click=route, args=("Channel", "Analisis", channel["id"]), use_container_width=True)
                b.button("Bandingkan", key=f"add_{scope}_{channel['id']}", on_click=compare_add, args=(channel["id"],), use_container_width=True)


def directory_page(backend):
    st.title("Direktori channel")
    st.caption("Cari channel dalam niche yang ingin Anda pelajari.")
    with st.form("directory_form", border=False):
        query = text_input("Niche atau nama channel", "directory_query", placeholder="Contoh: cover musik")
        with st.expander("Filter lanjutan"):
            a, b = st.columns(2)
            with a:
                subs = select("Subscriber", ["Semua", "0-1K", "1K-10K", "10K-100K", "100K-1M", "> 1M"], "directory_subs")
                age = select("Usia channel", ["Semua", "Kurang dari 1 Tahun", "1-3 Tahun", "Lebih dari 3 Tahun"], "directory_age")
            with b:
                vph = select("VPH (perkiraan mesin lama)", ["Semua", "> 100", "> 500", "> 1000", "> 5000"], "directory_vph",
                             help="Metode VPH direktori masih perlu diperbaiki. Jangan gunakan sebagai satu-satunya dasar memilih channel.")
                sort = select("Urutkan berdasarkan", ["Banyak Ditonton (Teratas)", "Subscriber Terbanyak", "Video Terbanyak", "Channel Terbaru", "Tumbuh Tercepat"], "directory_sort")
        search = st.form_submit_button("Cari channel", type="primary", use_container_width=True)
    if search:
        if not query.strip():
            st.warning("Masukkan niche atau nama channel terlebih dahulu.")
        else:
            with st.spinner("Mencari channel..."):
                rows = backend.search_youtube_channels(query.strip(), max_results=20, sort_by=sort, subs_filter=subs, age_filter=age, vph_filter=vph)
            save_result("directory_bundle", rows, query=query.strip(), context=f"{sort}, subscriber {subs}, usia {age}, VPH {vph}")
    bundle = st.session_state.get("directory_bundle")
    if not bundle or not bundle["rows"]:
        empty_state("Temukan channel referensi", "Hasil pencarian dapat dianalisis satu per satu atau ditambahkan ke perbandingan.")
        return
    result_header(bundle, "direktori_channel.csv")
    channel_cards(page_items(bundle["rows"], "directory_bundle"), "directory")


def channel_data(channel_id, backend, refresh=False):
    cache = st.session_state.setdefault("channel_details", {})
    entry = cache.get(channel_id)
    if refresh or entry is None or time.time() - entry[0] > 900:
        with st.spinner("Mengambil data channel..."):
            data = backend.analyze_channel_deep(channel_id)
        if data:
            cache[channel_id] = (time.time(), data)
            return data
        return None
    return entry[1]


def channel_tags(data):
    tags = data.get("top_seo_tags", [])
    if tags:
        st.dataframe(pd.DataFrame(tags, columns=["Tag", "Frekuensi"]), hide_index=True, use_container_width=True)
        st.caption("Salin tag")
        st.code(", ".join(tag for tag, _ in tags), language="text")
    else:
        st.caption("Tidak ada tag yang tersedia pada sampel video.")


def analysis_page(backend):
    st.title("Analisis channel")
    st.caption("Tinjau performa, pola publikasi, dan tag dari satu channel.")
    with st.form("channel_search_form", border=False):
        query = text_input("Nama channel", "channel_query", placeholder="Masukkan nama channel")
        search = st.form_submit_button("Cari channel", type="primary")
    if search:
        if not query.strip():
            st.warning("Masukkan nama channel terlebih dahulu.")
        else:
            st.session_state["selected_channel"] = None
            with st.spinner("Mencari channel..."):
                st.session_state["channel_choices"] = backend.search_youtube_channels(query.strip(), max_results=5)
            if not st.session_state["channel_choices"]:
                st.info("Channel belum ditemukan. Coba nama lain.")
    channel_id = st.session_state.get("selected_channel")
    if not channel_id:
        choices = st.session_state.get("channel_choices", [])
        if choices:
            channel_cards(choices, "choices")
        else:
            empty_state("Pilih channel untuk dianalisis", "Cari nama channel di atas atau gunakan tombol Analisis dari hasil pencarian.")
        return
    sample = st.selectbox('Jumlah video sampel', [5,15,30,50], key='channel_sample_size')
    cache_entry = st.session_state.get('channel_details',{}).get(channel_id)
    changed = bool(cache_entry and cache_entry[1].get('sample_limit',5) != sample)
    a, b, c = st.columns(3)
    refresh = a.button("Perbarui data", key="refresh_channel") or changed
    b.button("Tambahkan ke perbandingan", on_click=compare_add, args=(channel_id,), key="compare_current")
    if c.button("Tutup analisis"):
        st.session_state["selected_channel"] = None
        st.rerun()
    data = channel_data(channel_id, backend, refresh)
    if not data:
        return
    a, b = st.columns([1, 8])
    with a:
        if data.get("thumb"):
            st.image(data["thumb"], width=72)
    with b:
        st.subheader(data["title"])
        st.caption(data.get("custom_url", ""))
    a, b, c = st.columns(3)
    a.metric("Subscriber", data["subs"])
    b.metric("Total views", data["total_views"])
    c.metric("Total video", data["video_count"])
    st.link_button("Buka channel di YouTube", "https://youtube.com/channel/" + channel_id)
    st.caption("Data disimpan selama sesi maksimal 15 menit sebelum diambil ulang. Gunakan Perbarui data untuk mengambil data terbaru.")
    tab1, tab2, tab3 = st.tabs(["Performa dan video", "Tag SEO", "Monetisasi & Screenshot"])
    with tab1:
        st.write(f"Rerata views ({len(data.get('recent_videos', []))} video sampel): **{data['avg_recent_views']}**")
        if data.get('median_recent_views'):
            st.write(f"Median views: **{data['median_recent_views']}**")
        st.caption('Sampel video terbaru memiliki usia berbeda. Views belum dinormalisasi terhadap umur video.')
        st.write(f"Pola jam publikasi: **{data['favorite_upload_hour']}**")
        st.caption("Pola publikasi bukan bukti jam terbaik untuk mendapatkan views.")
        sort_mode = st.selectbox(
            "Videos Sort by Popularity (Urutkan sampel video)",
            ["Terbaru", "Terpopuler (Views Tertinggi)", "VPH Tertinggi", "Outlier Score Tertinggi", "Terlama"],
            key="channel_video_sort"
        )
        videos_to_show = sort_channel_videos(data.get("recent_videos", []), sort_by=sort_mode)
        for video in videos_to_show:
            with st.container(border=True):
                a, b = st.columns([1, 4])
                with a:
                    if video.get("thumb"):
                        st.image(video["thumb"], use_container_width=True)
                with b:
                    st.write(video["title"])
                    extra = f" | {video.get('vph_calculated', 0):,.0f} VPH | Outlier {video.get('outlier_multiple', 1.0)}x" if "outlier_multiple" in video else ""
                    st.caption(f"{video['date']} | {video['views']} views{extra}")
    with tab2:
        channel_tags(data)
    with tab3:
        mon = check_monetization_status(data, kind="channel")
        st.write(f"**Status Indikator Monetisasi Channel:** {mon['status_label']} ({mon['score']}/100)")
        st.dataframe(pd.DataFrame(mon["signals"]), hide_index=True, use_container_width=True)
        st.caption(mon["basis"])
        ch_png = render_channel_screenshot(data, hide_sensitive=False)
        st.download_button("Unduh Channel Page Screenshot (PNG)", ch_png, f"channel_{channel_id}.png", "image/png", key="dl_ch_ss_" + channel_id)


def comparison_page(backend):
    st.title("Perbandingan channel")
    queue = st.session_state.setdefault("compare_list", [])
    st.caption(f"{len(queue)} dari 4 channel dipilih. Tambahkan channel melalui pencarian atau direktori.")
    if st.session_state.get("notice"):
        st.info(st.session_state.pop("notice"))
    if not queue:
        empty_state("Belum ada channel untuk dibandingkan", "Buka Direktori, cari channel, kemudian pilih Bandingkan.")
        st.button("Buka direktori", on_click=route, args=("Channel", "Direktori"))
        return
    with st.expander("Kelola daftar perbandingan"):
        for channel_id in queue[:]:
            cached = st.session_state.get("channel_details", {}).get(channel_id)
            name = cached[1]["title"] if cached else channel_id
            st.button("Hapus " + name, key="remove_" + channel_id, on_click=compare_remove, args=(channel_id,))
        if st.button("Kosongkan daftar"):
            st.session_state["compare_list"] = []
            st.rerun()
    refresh = st.button("Perbarui data channel", key="refresh_comparison")
    datasets = [(channel_id, channel_data(channel_id, backend, refresh)) for channel_id in queue]
    datasets = [(cid, data) for cid, data in datasets if data]
    if not datasets:
        st.info("Data channel belum tersedia. Periksa pesan API lalu coba Perbarui data.")
        return
    table = [{"Channel": d["title"], "Subscriber": d["subs"], "Total views": d["total_views"], "Video": d["video_count"],
              "Rerata views sampel": d["avg_recent_views"], "Pola jam publikasi (WIB)": d["favorite_upload_hour"]} for _, d in datasets]
    st.dataframe(pd.DataFrame(table), hide_index=True, use_container_width=True)
    st.caption("Rerata views dihitung dari maksimal 5 video terbaru oleh mesin analisis asli.")
    for cid, data in datasets:
        with st.expander(data["title"] + ": tag dan tautan"):
            st.link_button("Buka channel", "https://youtube.com/channel/" + cid)
            channel_tags(data)


def artists_page(backend):
    st.title("Perbandingan artis")
    st.caption("Bandingkan sinyal minat dari sampel YouTube. Indeks ini bukan volume pencarian resmi.")
    with st.form("artist_form", border=False):
        a, b = st.columns(2)
        with a:
            artist1 = text_input("Artis 1", "artist_1", placeholder="Nama artis pertama")
        with b:
            artist2 = text_input("Artis 2", "artist_2", placeholder="Nama artis kedua")
        with st.expander("Tambahkan artis (opsional)"):
            artist3 = text_input("Artis 3", "artist_3")
            artist4 = text_input("Artis 4", "artist_4")
            artist5 = text_input("Artis 5", "artist_5")
        with st.expander("Pengaturan perbandingan"):
            a, b = st.columns(2)
            with a:
                country = select("Wilayah", backend.COUNTRY_CODES, "artist_country", 1, format_func=clean_label)
            with b:
                window = select("Rentang publikasi", ["24 Jam", "3 Hari", "7 Hari", "30 Hari"], "artist_window", 2)
        search = st.form_submit_button("Bandingkan artis", type="primary", use_container_width=True)
    if search:
        artists = []
        for name in [artist1, artist2, artist3, artist4, artist5]:
            name = name.strip()
            if name and name.casefold() not in [x.casefold() for x in artists]:
                artists.append(name)
        if len(artists) < 2:
            st.warning("Masukkan minimal dua nama artis yang berbeda.")
        else:
            with st.spinner("Mengumpulkan sampel YouTube..."):
                rows = [backend.get_artist_search_demand(artist, backend.COUNTRY_CODES[country], {"24 Jam": 1, "3 Hari": 3, "7 Hari": 7, "30 Hari": 30}[window], 25) for artist in artists]
            save_result("artist_bundle", backend.normalize_artist_comparison(rows), query=", ".join(artists), context=f"{clean_label(country)}, {window}")
    bundle = st.session_state.get("artist_bundle")
    if not bundle:
        empty_state("Mulai dengan dua artis", "Artis tambahan dan pengaturan tersedia bila diperlukan.")
        return
    valid = [row for row in bundle["rows"] if not row.get("error")]
    failed = [row for row in bundle["rows"] if row.get("error")]
    if failed:
        st.warning(f"{len(failed)} artis belum berhasil diambil. Perbandingan menggunakan data yang tersedia.")
        with st.expander("Detail pengambilan data"):
            for row in failed:
                st.write(f"{row.get('artist', '')}: {row.get('error', '')}")
    if not valid:
        return
    result_header(bundle, "artist_comparison.csv")
    df = pd.DataFrame([{"Artis": r["artist"], "Indeks minat": r.get("youtube_interest_score", 0),
        "Estimasi hasil pencarian": r.get("search_results_estimate", 0), "Video ditemukan": r.get("videos_found", 0),
        "Video baru": r.get("recent_videos", 0), "Total views": r.get("total_views", 0), "Median views": r.get("median_views", 0),
        "Rerata VPH": r.get("avg_vph", 0), "Engagement (%)": r.get("engagement_rate", 0),
        "Long-form": r.get("longform_count", 0), "Shorts-like": r.get("shorts_like_count", 0)} for r in valid])
    tab1, tab2, tab3 = st.tabs(["Ringkasan", "Data lengkap", "Cara membaca"])
    with tab1:
        st.dataframe(df[["Artis", "Indeks minat", "Video ditemukan", "Video baru"]], hide_index=True, use_container_width=True)
        metric = select("Metrik grafik", ["Indeks minat", "Rerata VPH", "Video baru"], "artist_chart")
        st.bar_chart(df.set_index("Artis")[[metric]])
    with tab2:
        st.dataframe(df, hide_index=True, use_container_width=True)
    with tab3:
        st.write("Indeks minat membandingkan artis dalam scan yang sama. Komposisi artis dapat memengaruhi normalisasi skor.")
        st.write("Estimasi hasil pencarian bukan jumlah orang yang mencari. Video baru dan views merujuk pada sampel yang berhasil diambil.")
        st.write("Median views merangkum nilai tengah. Rerata VPH memakai usia publikasi, bukan statistik pencarian resmi.")
        st.write("Long-form dan Shorts-like adalah klasifikasi perkiraan. Google Trends merupakan sumber indeks relatif yang terpisah.")


def select_active_api_key():
    """Keep the widget-owned value separate from backend session state."""
    st.session_state['current_api_index'] = st.session_state['youtube_api_selector']


def render_app(services):
    backend = SimpleNamespace(**services)
    if st.session_state.get('notice'):
        st.info(st.session_state.pop('notice'))
    stylesheet = Path(__file__).with_name("simple_ui.css").read_text(encoding="utf-8")
    st.markdown("<style>" + stylesheet + "</style>", unsafe_allow_html=True)
    prefs = st.session_state.setdefault("ui_preferences", {})
    pending = st.session_state.pop("pending_route", None)
    if pending:
        section, page = pending
        prefs["section"] = section
        prefs[section + "_page"] = page
        st.session_state["nav_section"] = section
        st.session_state["nav_" + section] = page
    st.session_state.setdefault("nav_section", prefs.get("section", "Video"))
    with st.sidebar:
        st.markdown('<div class="brand"><span class="brand-mark">N</span><div><strong>Niche Hunter</strong><small>Ruang riset pribadi</small></div></div>', unsafe_allow_html=True)
        section = st.radio("Ruang kerja", ["Video", "Channel", "Artis", "Riset", "Studio"], key="nav_section")
        prefs["section"] = section
        queue = st.session_state.get("compare_list", [])
        st.caption(f"Perbandingan: {len(queue)}/4 channel")
        with st.expander("Pengaturan dan bantuan"):
            st.caption(f'YouTube: {len(backend.API_KEYS)} kunci tersedia')
            if len(backend.API_KEYS)>1:
                choices = range(len(backend.API_KEYS))
                if st.session_state.get('youtube_api_selector') not in choices:
                    st.session_state['youtube_api_selector'] = int(st.session_state.get('current_api_index',0)) % len(backend.API_KEYS)
                st.selectbox('Kunci YouTube aktif',choices,format_func=lambda i:f'Kunci {i+1}',
                             key='youtube_api_selector',on_change=select_active_api_key)
            usage=st.session_state.get('youtube_usage',{})
            st.caption(f"Panggilan API sesi: {usage.get('calls',0)} · pencarian: {usage.get('search',0)} · cache: {usage.get('cache_hits',0)}")
            st.caption('Cache 5 menit. Angka di atas menghitung panggilan sesi ini, bukan saldo kuota proyek. Kunci tidak diputar otomatis saat kuota habis.')
            st.caption("Gemini: " + ("tersedia" if backend.GEMINI_API_KEY else "belum diatur"))
            try:
                groq = bool(st.secrets.get("GROQ_API_KEY", ""))
            except FileNotFoundError:
                groq = False
            st.caption("Groq: " + ("tersedia" if groq else "belum diatur"))
            st.write("Gunakan filter lanjutan untuk mempersempit pencarian. Semua fitur tersedia di ruang kerja yang sesuai.")
            st.caption("Hasil dan jawaban AI tersimpan selama sesi browser. CSV dapat diunduh untuk disimpan.")
    options = {
        "Video": ["Pencarian", "Trending", "Viral Intelligence", "Monetization & Transkrip", "Similar Thumbnail"],
        "Channel": ["Direktori", "Analisis", "Perbandingan", "Similar Channels"],
        "Artis": ["Perbandingan artis"],
        "Riset": ["Keyword Lab", "Radar kompetitor", "Rank Tracker", "Niche Finder & Overview"],
        "Studio": [
            "SEO Studio", "Ruang riset", "Evaluasi channel", "Kalender konten",
            "Eksperimen CTR", "Audit massal", "Thumbnail Compressor",
            "Automatic Ad Placer", "Net Profit & Combined", "Screenshot Studio"
        ]
    }[section]
    key = "nav_" + section
    if key not in st.session_state:
        st.session_state[key] = prefs.get(section + "_page", options[0])
    page = st.radio("Mode " + section.lower(), options, key=key, horizontal=True, label_visibility="collapsed") if len(options) > 1 else options[0]
    prefs[section + "_page"] = page
    if section == "Video":
        if page == "Viral Intelligence":
            viral_page(backend)
        elif page == "Monetization & Transkrip":
            monetization_transcript_page(backend)
        elif page == "Similar Thumbnail":
            similar_thumbnail_page(backend)
        else:
            video_search(backend, trending=page == "Trending")
    elif section == "Channel":
        {"Direktori": directory_page, "Analisis": analysis_page, "Perbandingan": comparison_page, "Similar Channels": similar_channels_page}[page](backend)
    elif section == 'Artis':
        artists_page(backend)
    elif section == 'Riset':
        {'Keyword Lab':keyword_page,'Radar kompetitor':competitor_page,'Rank Tracker':rank_page,'Niche Finder & Overview':niche_overview_page}[page](backend)
    else:
        {'SEO Studio':seo_page,'Ruang riset':research_page,'Evaluasi channel':evaluation_page,
         'Kalender konten':planner_page,'Eksperimen CTR':experiment_page,'Audit massal':bulk_page,
         'Thumbnail Compressor':thumbnail_compressor_page,'Automatic Ad Placer':ad_placer_page,
         'Net Profit & Combined':profit_combined_page,'Screenshot Studio':screenshot_studio_page}[page](backend)
