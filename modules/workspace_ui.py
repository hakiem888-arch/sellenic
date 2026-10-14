"""Keyword research, competitor radar, rank history and production workflows."""
import json
import re
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from modules.growth_engine import ResearchStore, seo_audit, gap_candidates
from modules.growth_ui import open_seo
from modules.intelligence import (keyword_profile, phrase_clusters, comparable_baseline, lifetime_vph,
                                  age_hours, parse_video_id, rank_observation, ctr_experiment, csv_bytes)
from modules.youtube_client import YouTubeClient, YouTubeError

STATUSES = ['Ide', 'Riset', 'Produksi', 'Siap terbit', 'Terbit']


def client_for(backend):
    keys = getattr(backend, 'API_KEYS', [])
    index = int(st.session_state.get('current_api_index', 0))
    return YouTubeClient(keys[index % len(keys)] if keys else '', st.session_state)


def save_record(kind, ident, payload):
    try:
        ResearchStore().save(kind,ident,payload)
        return True
    except (OSError,sqlite3.Error):
        st.error('Belum tersimpan. Periksa akses folder data dan coba lagi.')
        return False


def delete_record(kind, ident):
    try:
        ResearchStore().delete(kind,ident)
        st.session_state['notice'] = 'Entri berhasil dihapus.'
    except (OSError,sqlite3.Error):
        st.session_state['notice'] = 'Entri belum terhapus. Periksa folder data.'


def plan_from_keyword(keyword):
    st.session_state['planner_seed'] = keyword
    st.session_state['pending_route'] = ('Studio','Kalender konten')


def keyword_page(backend):
    st.title('Keyword Lab')
    st.caption('Bandingkan hingga 5 kata kunci, temukan frasa dan sudut konten, lalu simpan ke rencana produksi.')
    with st.form('keyword_lab'):
        seeds = st.text_area('Kata kunci, satu per baris', placeholder='belajar python\npython untuk pemula', key='lab_seeds')
        a,b,c = st.columns(3)
        region = a.selectbox('Wilayah pencarian',['ID','US','MY','GB','AU'],key='lab_region')
        days = b.selectbox('Usia publikasi maksimum',[30,90,365,0],format_func=lambda x: f'{x} hari' if x else 'Semua usia')
        own_subs = c.number_input('Subscriber channel Anda (opsional)',min_value=0,value=0,step=100)
        format_label = st.selectbox('Durasi sampel',['Semua','4–20 menit','Lebih dari 20 menit','Kurang dari 4 menit'])
        run = st.form_submit_button('Bandingkan kata kunci',type='primary')
    st.caption('Satu pencarian per kata kunci, maksimal 25 video. Skor adalah proksi sampel, bukan volume pencarian atau peluang ranking.')
    if run:
        keywords = list(dict.fromkeys(x.strip().casefold() for x in seeds.splitlines() if x.strip()))
        if not 1 <= len(keywords) <= 5 or any(len(x)>120 for x in keywords):
            st.warning('Isi 1–5 kata kunci, maksimal 120 karakter per baris.')
        else:
            bundles, errors = [], []
            try:
                client = client_for(backend)
                for keyword in keywords:
                    params = dict(q=keyword,part='snippet',type='video',order='relevance',regionCode=region,maxResults=25)
                    if days: params['publishedAfter']=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
                    if format_label != 'Semua': params['videoDuration']={'4–20 menit':'medium','Lebih dari 20 menit':'long','Kurang dari 4 menit':'short'}[format_label]
                    try:
                        result = client.fetch('search',**params)
                        ids = [x['id']['videoId'] for x in result.get('items',[]) if x.get('id',{}).get('videoId')]
                        videos = client.fetch('videos',id=','.join(ids),part='snippet,statistics,contentDetails').get('items',[]) if ids else []
                        rows = backend.process_video_response(videos,client,region) if videos else []
                        bundles.append({'profile':keyword_profile(keyword,rows,own_subs or None),'rows':rows})
                    except YouTubeError as exc:
                        errors.append(str(exc)); break
                st.session_state['keyword_lab_result']={'bundles':bundles,'context':f'{region} · {days or "semua"} hari · {format_label}',
                    'at':datetime.now(timezone.utc).isoformat(),'errors':errors}
            except YouTubeError as exc:
                st.error(str(exc))
    result = st.session_state.get('keyword_lab_result')
    if not result:
        st.info('Masukkan topik yang ingin dibandingkan. Hasil akan muncul setelah pencarian.')
        return
    st.caption(result['context']+' · '+result['at'])
    for error in result['errors']: st.warning(error)
    bundles=result['bundles']
    if not bundles: return
    table=[{'Keyword':p['keyword'],'Sampel':p['sample_size'],'Median VPH':p['median_vph'],
            'Cakupan judul (%)':p['title_coverage_pct'],'Dominasi channel (%)':p['top_channel_share_pct'],
            'Peluang sampel':p['opportunity'],'Peluang personal':p['personal_opportunity'],'Bukti':p['confidence']}
           for p in (b['profile'] for b in bundles)]
    st.dataframe(pd.DataFrame(table),hide_index=True,use_container_width=True)
    st.download_button('Unduh perbandingan keyword',csv_bytes(table),'keyword-lab.csv','text/csv')
    selected=st.selectbox('Detail kata kunci',range(len(bundles)),format_func=lambda i:bundles[i]['profile']['keyword'])
    bundle=bundles[selected];p=bundle['profile'];rows=bundle['rows']
    a,b=st.columns(2)
    if a.button('Simpan riset keyword'):
        ident=sha256((p['keyword']+result['context']).encode()).hexdigest()[:24]
        if save_record('keyword',ident,{'profile':p,'context':result['context'],'at':result['at']}): st.success('Riset keyword tersimpan.')
    b.button('Jadikan rencana konten',on_click=plan_from_keyword,args=(p['keyword'],))
    tabs=st.tabs(['Rumus dan bukti','Frasa dan celah','Video referensi'])
    with tabs[0]:
        st.dataframe(pd.DataFrame(p['components']),hide_index=True,use_container_width=True)
        st.write('Momentum: log10(1 + median VPH) / 4, dibatasi 100. Ruang judul: 100 − persentase judul yang memuat semua kata target. Keragaman: 100 − pangsa channel terbesar. Publikasi baru: persentase video berusia ≤30 hari.')
        st.caption('Skor personal = 80% skor sampel + 20% proporsi channel dengan subscriber ≤2× channel Anda. Ukuran channel bukan jaminan daya saing. Subscriber tersembunyi tidak dianggap nol.')
        st.caption('Minimal 5 video dengan tanggal/views valid dan 2 channel untuk menampilkan skor. Semua sampel tetap eksploratif; proksi ini belum dikalibrasi terhadap hasil publikasi. Filter usia/durasi memengaruhi skor.')
    with tabs[1]:
        st.dataframe(pd.DataFrame(phrase_clusters(p['keyword'],rows)),hide_index=True,use_container_width=True)
        st.dataframe(pd.DataFrame(gap_candidates(p['keyword'],rows)).sort_values('Cakupan sampel'),hide_index=True,use_container_width=True)
        st.caption('Frekuensi frasa pada judul dan kategori yang jarang muncul dalam sampel; verifikasi isi video sebelum menyimpulkan adanya celah.')
    with tabs[2]:
        for row in rows[:10]:
            st.write(row['title'])
            st.caption(f"{row.get('channel','')} · {row.get('views_fmt','')} views")
            st.button('Buka di SEO Studio',key='lab_seo_'+row['id'],on_click=open_seo,args=(row,))
    with st.expander('Riset keyword tersimpan'):
        for entry in ResearchStore().list('keyword'):
            payload=entry['payload']
            st.write(payload.get('profile',{}).get('keyword',entry['id']))
            st.caption(payload.get('context',''))
            st.button('Hapus riset keyword',key='del_kw_'+entry['id'],on_click=delete_record,args=('keyword',entry['id']))


def rank_page(backend):
    st.title('Rank Tracker')
    st.caption('Simpan posisi video dalam 50 hasil API YouTube. Riwayat bertambah saat Anda menjalankan pemeriksaan.')
    db=ResearchStore()
    with st.form('rank_add'):
        keyword=st.text_input('Keyword yang dipantau',key='rank_keyword')
        video=st.text_input('URL atau ID video',key='rank_video')
        a,b=st.columns(2)
        region=a.selectbox('Wilayah',['ID','US','MY','GB','AU'],key='rank_region')
        language=b.selectbox('Bahasa relevansi',['id','en','ms'],key='rank_language')
        add=st.form_submit_button('Tambahkan pelacakan')
    if add:
        try:
            video_id=parse_video_id(video)
            if not keyword.strip() or len(keyword)>120: raise ValueError('Isi keyword maksimal 120 karakter.')
            ident=sha256(json.dumps([keyword.strip().casefold(),video_id,region,language]).encode()).hexdigest()[:24]
            old={e['id']:e['payload'] for e in db.list('rank_track')}
            if ident in old: st.info('Video dan keyword ini sudah dipantau pada wilayah/bahasa yang sama.')
            elif len(old)>=20: st.warning('Maksimal 20 pelacakan. Hapus salah satu untuk menambah.')
            elif save_record('rank_track',ident,{'keyword':keyword.strip(),'video_id':video_id,'region':region,'language':language,'observations':[]}): st.success('Pelacakan tersimpan.')
        except ValueError as exc: st.warning(str(exc))
    entries=db.list('rank_track')
    if not entries: st.info('Tambahkan video dan kata kunci untuk mulai memantau.'); return
    picked=st.multiselect('Pelacakan untuk diperiksa (maksimal 5)',[e['id'] for e in entries],
        default=[e['id'] for e in entries[:5]],format_func=lambda ident: next(e['payload']['keyword']+' · '+e['payload']['video_id'] for e in entries if e['id']==ident))
    if st.button('Periksa posisi sekarang',type='primary'):
        if not 1<=len(picked)<=5: st.warning('Pilih 1–5 pelacakan.')
        else:
            try:
                client=client_for(backend); fetched={};count=0
                for entry in entries:
                    if entry['id'] not in picked: continue
                    p=entry['payload'];signature=(p['keyword'],p['region'],p['language'])
                    if signature not in fetched:
                        fetched[signature]=client.fetch('search',force=True,q=p['keyword'],regionCode=p['region'],relevanceLanguage=p['language'],type='video',order='relevance',part='snippet',maxResults=50)
                    observation=rank_observation(p['video_id'],fetched[signature].get('items',[]))
                    db.append_rank(entry['id'],{**observation,'at':datetime.now(timezone.utc).isoformat()});count+=1
                st.success(f'{count} pelacakan diperbarui.')
            except (YouTubeError,ValueError,sqlite3.Error) as exc: st.warning('Pemeriksaan terhenti. Hasil yang berhasil tetap disimpan. '+str(exc))
            entries=db.list('rank_track')
    export=[]
    for entry in entries:
        p=entry['payload'];obs=p.get('observations',[]);last=obs[-1] if obs else {}
        with st.expander(p['keyword']+' · '+p['video_id'],expanded=len(entries)==1):
            st.write(f"Wilayah {p['region']} · bahasa {p['language']}")
            position=last.get('position')
            st.metric('Posisi API terakhir',str(position) if position is not None else 'Tidak ditemukan' if obs else 'Belum diperiksa')
            if obs:
                st.caption(f"{last['at']} · {last.get('checked',0)} hasil diperiksa")
                frame=pd.DataFrame(obs)
                st.dataframe(frame,hide_index=True,use_container_width=True)
                if len(obs)>=2: st.line_chart(frame.set_index('at')[['position']])
            st.button('Hapus pelacakan',key='del_rank_'+entry['id'],on_click=delete_record,args=('rank_track',entry['id']))
            export.extend({'keyword':p['keyword'],'video_id':p['video_id'],'region':p['region'],'language':p['language'],**o} for o in obs)
    if export: st.download_button('Unduh riwayat posisi',csv_bytes(export),'rank-history.csv','text/csv')
    st.caption('API tidak mewakili hasil personal setiap penonton. Tidak ditemukan berarti di luar sampel yang diperiksa, bukan otomatis peringkat 51. Tidak ada pemantauan latar belakang; maksimal 100 pengukuran terakhir per pelacakan.')


def resolve_channel(client, value):
    value=value.strip()
    if value.startswith('https://'):
        url=urlparse(value)
        if url.hostname not in ('youtube.com','www.youtube.com'): raise ValueError('Gunakan URL channel YouTube.')
        value=url.path.removeprefix('/channel/').strip('/')
    if re.fullmatch(r'UC[\w-]{22}',value): return value
    if value.startswith('@') and 2<=len(value)<=101:
        items=client.fetch('channels',forHandle=value,part='id').get('items',[])
        if items:return items[0]['id']
    raise ValueError('Gunakan ID channel UC… atau @handle yang valid.')


def competitor_page(backend):
    st.title('Radar kompetitor')
    st.caption('Bandingkan unggahan terbaru hingga 4 channel dan temukan video yang melampaui baseline sebanding.')
    with st.form('radar_form'):
        identifiers=st.text_area('ID channel atau @handle, satu per baris',key='radar_channels')
        days=st.selectbox('Rentang usia video',[7,30,90,365],index=1)
        duration=st.selectbox('Kelompok durasi',['Semua','Lebih dari 3 menit','Maksimal 3 menit'])
        go=st.form_submit_button('Analisis kompetitor',type='primary')
    if go:
        values=list(dict.fromkeys(x.strip() for x in identifiers.splitlines() if x.strip()))
        if not 1<=len(values)<=4:st.warning('Isi 1–4 channel.')
        else:
            try:
                client=client_for(backend); all_rows=[]; summaries=[];seen=set()
                for value in values:
                    cid=resolve_channel(client,value)
                    if cid in seen:continue
                    seen.add(cid)
                    source=client.recent_uploads(cid,50)
                    rows=backend.process_video_response(source,client,'ID')
                    rows=[r for r in rows if age_hours(r) is not None and age_hours(r)<=days*24]
                    if duration=='Lebih dari 3 menit': rows=[r for r in rows if r.get('duration_seconds',0)>180]
                    elif duration=='Maksimal 3 menit':rows=[r for r in rows if 0<r.get('duration_seconds',0)<=180]
                    for row in rows:
                        base=comparable_baseline(row,rows)
                        row['comparable_multiple']=base['multiple'];row['peer_count']=base['sample_size']
                    rates=[v for row in rows if (v:=lifetime_vph(row)) is not None]
                    summaries.append({'Channel':rows[0]['channel'] if rows else value,'Channel ID':cid,'Video dalam sampel':len(rows),
                        'Median VPH sejak publikasi':round(float(pd.Series(rates,dtype=float).median()),2) if rates else None,
                        'Views sampel':sum(r['raw_views'] for r in rows),'Outlier ≥3×':sum((r['comparable_multiple'] or 0)>=3 for r in rows)})
                    all_rows.extend(rows)
                st.session_state['radar_result']={'summary':summaries,'rows':all_rows,'context':f'{days} hari · {duration}','at':datetime.now(timezone.utc).isoformat()}
            except (YouTubeError,ValueError) as exc: st.warning(str(exc))
    result=st.session_state.get('radar_result')
    if not result:return
    st.caption(result['context']+' · '+result['at'])
    st.dataframe(pd.DataFrame(result['summary']),hide_index=True,use_container_width=True)
    table=[{'Judul':r['title'],'Channel':r['channel'],'Views':r['raw_views'],'VPH sejak publikasi':round(lifetime_vph(r),2),
            'Kelipatan sebanding':r['comparable_multiple'],'Video pembanding':r['peer_count'],'URL':r['link']}
           for r in sorted(result['rows'],key=lambda r:r['comparable_multiple'] or -1,reverse=True)]
    st.dataframe(pd.DataFrame(table),hide_index=True,use_container_width=True)
    st.download_button('Unduh radar kompetitor',csv_bytes(table),'radar-kompetitor.csv','text/csv')
    st.caption('Maksimal 50 unggahan terbaru per channel. Ini sampel, bukan total analitik channel. Baseline mengecualikan video target, memakai kelompok durasi sama dan usia 0,5–2×, minimal 3 pembanding. VPH dihitung sejak publikasi untuk kedua sisi. Durasi ≤3 menit belum memastikan video adalah Shorts.')


def planner_page(backend):
    st.title('Kalender konten')
    st.caption('Ubah riset menjadi jadwal, prioritas, dan status produksi. Data tersimpan pada instalasi ini.')
    seed=st.session_state.pop('planner_seed',None)
    if seed is not None: st.session_state['plan_new_title']=seed;st.session_state['plan_new_keyword']=seed
    with st.form('planner_new',clear_on_submit=True):
        title=st.text_input('Judul atau ide konten',key='plan_new_title')
        keyword=st.text_input('Keyword utama',key='plan_new_keyword')
        a,b,c=st.columns(3)
        due=a.date_input('Tanggal target (WIB)',value=datetime.now(timezone(timedelta(hours=7))).date())
        priority=b.selectbox('Prioritas',['Tinggi','Sedang','Rendah'],index=1)
        status=c.selectbox('Status awal',STATUSES)
        note=st.text_area('Brief, referensi, atau catatan')
        add=st.form_submit_button('Simpan rencana',type='primary')
    if add:
        if not title.strip():st.warning('Isi judul atau ide konten.')
        elif save_record('planner',uuid.uuid4().hex,{'title':title.strip(),'keyword':keyword.strip(),'due':due.isoformat(),'priority':priority,'status':status,'note':note}):st.success('Rencana konten tersimpan.')
    entries=ResearchStore().list('planner')
    if not entries:st.info('Belum ada rencana konten. Tambahkan di atas atau kirim dari Keyword Lab.');return
    summary=CounterStatuses(entries)
    columns=st.columns(5)
    for col,status in zip(columns,STATUSES):col.metric(status,summary[status])
    active=st.multiselect('Tampilkan status',STATUSES,default=STATUSES)
    rows=[{'ID':e['id'],**e['payload']} for e in entries if e['payload'].get('status') in active]
    rows.sort(key=lambda p:p.get('due',''))
    st.dataframe(pd.DataFrame(rows).drop(columns=['ID'],errors='ignore'),hide_index=True,use_container_width=True)
    st.download_button('Unduh kalender CSV',csv_bytes(rows),'kalender-konten.csv','text/csv')
    selected=st.selectbox('Edit rencana',[e['id'] for e in entries],format_func=lambda x:next(e['payload']['title'] for e in entries if e['id']==x))
    p=next(e['payload'] for e in entries if e['id']==selected)
    with st.form('edit_plan_'+selected):
        title=st.text_input('Judul',value=p['title'])
        keyword=st.text_input('Keyword',value=p.get('keyword',''))
        a,b,c=st.columns(3)
        due=a.date_input('Tanggal',value=date.fromisoformat(p['due']))
        status=b.selectbox('Status',STATUSES,index=STATUSES.index(p['status']))
        priority=c.selectbox('Prioritas produksi',['Tinggi','Sedang','Rendah'],index=['Tinggi','Sedang','Rendah'].index(p.get('priority','Sedang')))
        note=st.text_area('Catatan',value=p.get('note',''))
        update=st.form_submit_button('Perbarui rencana')
    if update:
        if not title.strip():st.warning('Judul tidak boleh kosong.')
        elif save_record('planner',selected,{'title':title.strip(),'keyword':keyword,'due':due.isoformat(),'status':status,'priority':priority,'note':note}):st.rerun()
    a,b=st.columns(2)
    a.button('Optimalkan rencana di SEO Studio',on_click=open_seo,args=({'title':p['title'],'description':p.get('note',''),'keyword':p.get('keyword','')},))
    b.button('Hapus rencana',on_click=delete_record,args=('planner',selected))


def CounterStatuses(entries):
    return {status:sum(e['payload'].get('status')==status for e in entries) for status in STATUSES}


def experiment_page(backend):
    st.title('Eksperimen CTR')
    st.caption('Analisis hasil eksperimen yang sudah Anda kumpulkan. Aplikasi ini tidak merotasi thumbnail atau judul di YouTube.')
    with st.expander('Pratinjau judul dan thumbnail A/B'):
        for label,col in zip(['A','B'],st.columns(2)):
            with col:
                title=st.text_input('Judul '+label,key='package_title_'+label)
                uploaded=st.file_uploader('Thumbnail '+label,type=['png','jpg','jpeg','webp'],key='package_thumb_'+label)
                if uploaded:
                    if uploaded.size>5_000_000:st.warning('Thumbnail maksimal 5 MB.')
                    else:
                        try:
                            from PIL import Image, UnidentifiedImageError
                            picture=Image.open(uploaded)
                            if picture.width*picture.height>20_000_000:st.warning('Gunakan gambar maksimal 20 megapiksel.')
                            else:st.image(picture,width=320)
                        except (OSError,ValueError,Image.DecompressionBombError):st.warning('Gambar belum dapat dibuka.')
                st.write(title or 'Judul varian '+label)
                st.caption(f'{len(title)}/100 karakter · Tinjau keterbacaan pada ukuran kecil.')
        st.caption('Pratinjau membantu menilai kemasan secara manual. Bukan heatmap atau prediksi CTR. Gambar tidak disertakan dalam cadangan eksperimen.')
    with st.form('experiment'):
        name=st.text_input('Nama eksperimen',key='experiment_name')
        a,b=st.columns(2)
        ai=a.number_input('Impresi A',min_value=1,value=1000,step=100)
        ac=a.number_input('Klik dari impresi A',min_value=0,value=50,step=1)
        bi=b.number_input('Impresi B',min_value=1,value=1000,step=100)
        bc=b.number_input('Klik dari impresi B',min_value=0,value=60,step=1)
        design=st.selectbox('Desain pengumpulan',['Periode bergantian / observasional','Pembagian acak pada periode yang sama'])
        note=st.text_area('Periode, sumber traffic, dan perubahan yang diuji')
        run=st.form_submit_button('Analisis eksperimen',type='primary')
    st.caption('Angka awal adalah contoh yang dapat diganti. Gunakan klik yang berasal dari impresi tersebut, bukan total views dari seluruh sumber.')
    if run:
        try:st.session_state['ctr_result']={'name':name or 'Eksperimen tanpa nama','design':design,'note':note,
                'input':[ai,ac,bi,bc], 'titles':{k:st.session_state.get('package_title_'+k,'') for k in ['A','B']},
                'result':ctr_experiment(ai,ac,bi,bc),'at':datetime.now(timezone.utc).isoformat()}
        except ValueError as exc:st.warning(str(exc))
    result=st.session_state.get('ctr_result')
    if result:
        r=result['result'];a,b,c=st.columns(3)
        a.metric('CTR A',f"{r['ctr_a']:.2f}%");b.metric('CTR B',f"{r['ctr_b']:.2f}%");c.metric('Selisih B − A',f"{r['difference_pp']:+.2f} pp")
        st.write(r['verdict'])
        st.caption(f"Interval 95% selisih: {r['difference_interval_pp'][0]:+.2f} sampai {r['difference_interval_pp'][1]:+.2f} poin persentase. Desain tercatat: {result['design']}.")
        st.dataframe(pd.DataFrame([{'Varian':v,'CTR (%)':r['ctr_'+v.lower()],'Batas bawah 95%':r['interval_'+v.lower()][0],'Batas atas 95%':r['interval_'+v.lower()][1]} for v in ['A','B']]),hide_index=True,use_container_width=True)
        st.info('Periode bergantian dapat dipengaruhi perubahan penonton dan sumber traffic. Interval mengasumsikan dua sampel binomial independen. Jangan menetapkan pemenang hanya dari CTR; periksa watch time dan kualitas penonton. Tentukan periode uji di awal untuk mengurangi bias berhenti saat hasil terlihat bagus.')
        if st.button('Simpan eksperimen'):
            ident=sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()[:24]
            if save_record('experiment',ident,result):st.success('Eksperimen tersimpan.')
        st.download_button('Unduh hasil eksperimen',json.dumps(result,ensure_ascii=False,indent=2),'eksperimen-ctr.json','application/json')
    for entry in ResearchStore().list('experiment'):
        p=entry['payload']
        with st.expander(p.get('name',entry['id'])):
            st.json(p)
            st.button('Hapus eksperimen',key='del_exp_'+entry['id'],on_click=delete_record,args=('experiment',entry['id']))


def bulk_page(backend):
    st.title('Audit metadata massal')
    st.caption('Prioritaskan perbaikan hingga 200 video dari CSV. Hasil berupa rekomendasi dan tidak menulis ke channel YouTube.')
    st.download_button('Unduh template CSV',csv_bytes([{'title':'Judul video','description':'Deskripsi video','keyword':'Topik utama','tags':'tag satu,tag dua','content':'Ringkasan isi yang benar-benar dibahas'}]),'template-audit.csv','text/csv')
    upload=st.file_uploader('CSV metadata (maksimal 2 MB)',type=['csv'],key='bulk_file')
    if upload is None:return
    if upload.size>2_000_000:st.error('File melebihi 2 MB.');return
    try:
        frame=pd.read_csv(upload,dtype=str,keep_default_na=False,nrows=201)
        if len(frame)>200:raise ValueError('Maksimal 200 video per audit.')
        if not {'title','keyword'} <= set(frame.columns):raise ValueError('Kolom title dan keyword wajib tersedia.')
        st.dataframe(frame.head(10),hide_index=True,use_container_width=True)
        if st.button('Audit semua baris',type='primary'):
            rows=[]
            for record in frame.to_dict('records'):
                result=seo_audit(record['title'],record.get('description',''),record.get('tags','').split(','),record['keyword'],record.get('content',''))
                rows.append({'title':record['title'],'keyword':record['keyword'],'score':result['score'],
                    'priority':'Perbaiki batas metadata' if result['blocking_issues'] else 'Lengkapi isi' if not record.get('content') else 'Tinjau relevansi' if result['score']<70 else 'Tinjau manual',
                    'issues':' | '.join(result['warnings']),'next_actions':' | '.join(c['Saran'] for c in result['checks'] if c['Poin']<c['Maksimum'])})
            st.session_state['bulk_result']={'digest':sha256(upload.getvalue()).hexdigest(),'rows':rows}
        result=st.session_state.get('bulk_result',{})
        if result.get('digest')==sha256(upload.getvalue()).hexdigest():
            st.dataframe(pd.DataFrame(result['rows']),hide_index=True,use_container_width=True)
            st.download_button('Unduh hasil audit massal',csv_bytes(result['rows']),'audit-metadata.csv','text/csv')
    except (ValueError,pd.errors.ParserError,UnicodeDecodeError) as exc:st.warning(str(exc))
