"""Local, explainable audits and durable personal research. No network calls."""
import json
import os
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

STOP = set('yang dan di ke dari untuk dengan pada adalah ini itu a an the of in to for and or how cara'.split())
FIELDS = ('id', 'title', 'description', 'channel', 'channel_id', 'link', 'tags', 'raw_views', 'views', 'raw_subs', 'duration_seconds', 'vph', 'published_full', 'breakout_score')
RECORD_KINDS = ('watchlist', 'brief', 'history', 'keyword', 'rank_track', 'planner', 'experiment')

def words(text):
    return [w for w in re.findall(r'[^\W_]+', str(text).lower(), re.UNICODE) if w not in STOP and len(w) > 1]

def seo_audit(title, description, tags=None, keyword='', content=''):
    """Internal metadata rubric. Missing content means relevance is unverified."""
    title, description, keyword, content = [str(x or '').strip() for x in (title, description, keyword, content)]
    target = set(words(keyword))
    def coverage(text):
        return len(target & set(words(text))) / len(target) if target else 0
    checks = []
    def check(label, earned, maximum, advice):
        checks.append({'Aspek': label, 'Poin': round(earned, 1), 'Maksimum': maximum, 'Saran': advice})
    check('Judul menjelaskan topik', 15 if len(words(title)) >= 3 else 5 if title else 0, 15,
          'Gunakan judul spesifik yang menjelaskan pokok video.')
    check('Kata kunci pada judul', 25 * coverage(title), 25,
          'Cocokkan maksud pencarian; kesamaan kata saja belum membuktikan relevansi.')
    check('Konteks deskripsi', 15 if len(words(description)) >= 30 else 5 if description else 0, 15,
          'Jelaskan isi, manfaat, dan konteks secara alami; panjang bukan faktor peringkat yang dijamin.')
    check('Kata kunci pada pembuka deskripsi', 15 * coverage(description[:250]), 15,
          'Jelaskan topik utama pada pembuka tanpa mengulang kata kunci berlebihan.')
    check('Dukungan isi video', 25 * coverage(content), 25,
          'Kecocokan leksikal dengan ringkasan/transkrip.' if content else 'Belum terverifikasi. Masukkan ringkasan/transkrip.')
    check('Tag relevan', 5 if target and target & set(words(' '.join(tags or []))) else 0, 5,
          'Tag bersifat pendukung, termasuk variasi ejaan; jumlah tag tidak menambah nilai.')
    warnings = []
    if not target: warnings.append('Kata kunci target belum diisi. Relevansi pencarian belum dinilai.')
    if not content: warnings.append('Isi video belum tersedia. Audit metadata tidak memverifikasi janji judul.')
    blocking = []
    if len(title) > 100: blocking.append('Judul melebihi 100 karakter. Ringkas sebelum diterbitkan.')
    if len(description.encode('utf-8')) > 5000: blocking.append('Deskripsi melebihi batas 5.000 byte API. Ringkas sebelum ekspor ke API.')
    if '<' in title or '>' in title: blocking.append('Hapus karakter < atau > dari judul.')
    if '<' in description or '>' in description: blocking.append('Hapus karakter < atau > dari deskripsi sebelum ekspor ke API.')
    tag_list = [str(t).strip() for t in (tags or []) if str(t).strip()]
    tag_length = sum(len(t) + (2 if ' ' in t else 0) for t in tag_list) + max(0,len(tag_list)-1)
    if tag_length > 500: blocking.append('Tag melebihi 500 karakter termasuk koma dan tanda kutip untuk frasa.')
    if len({t.casefold() for t in tag_list}) < len(tag_list): warnings.append('Ada tag duplikat. Hapus pengulangan yang tidak menambah konteks.')
    if keyword and len(re.findall(re.escape(keyword),title,re.IGNORECASE)) >= 3:
        warnings.append('Kata kunci berulang berlebihan pada judul. Utamakan kalimat alami.')
    if re.search(r'(.)\1{4,}', title): warnings.append('Periksa pengulangan karakter pada judul.')
    warnings.extend(blocking)
    return {'score': round(sum(c['Poin'] for c in checks)), 'checks': checks, 'warnings': warnings,
            'blocking_issues': blocking, 'title_characters': len(title), 'description_bytes': len(description.encode('utf-8')), 'tag_characters': tag_length,
            'basis': 'Rubrik internal berbasis kata, bukan skor YouTube atau prediksi peringkat.'}

def metadata_check(title, description, tags):
    audit = seo_audit(title, description, tags)
    # Discovery has no target keyword or transcript. Score only the observable rubric.
    observed = [c for c in audit['checks'] if c['Aspek'] in ('Judul menjelaskan topik', 'Konteks deskripsi')]
    score = round(sum(c['Poin'] for c in observed) / 30 * 100)
    checks = [f"{c['Aspek']}: {c['Poin']:g}/{c['Maksimum']} poin. {c['Saran']}" for c in observed]
    checks.append('Skor kelengkapan metadata saja. Kata kunci dan isi video perlu diaudit di SEO Studio.')
    return score, checks

def keyword_groups(keyword, rows):
    counts = Counter()
    for row in rows:
        counts.update(set(words(row.get('title', '') + ' ' + row.get('description', '')[:500])))
    return [{'Kata': w, 'Video dalam sampel': n} for w, n in counts.most_common(25) if w not in set(words(keyword))]

def gap_candidates(keyword, rows):
    intents = {'Panduan awal': ('pemula', 'beginner', 'dasar'), 'Langkah praktis': ('tutorial', 'langkah', 'step'),
               'Perbandingan': ('vs', 'versus', 'perbandingan', 'compare'), 'Kesalahan dan solusi': ('kesalahan', 'error', 'solusi', 'mistake'),
               'Biaya dan kebutuhan': ('biaya', 'harga', 'cost', 'budget')}
    return [{'Sudut pembahasan': label, 'Cakupan sampel': sum(bool(set(tokens) & set(words(r.get('title','')+' '+r.get('description','')[:500]))) for r in rows),
             'Ide untuk ditinjau': f'{keyword}: {label.lower()}'} for label, tokens in intents.items()]

def build_brief(keyword, audience, content, angle, title):
    return f'''# Brief produksi\n\nTopik: {keyword}\n\nTarget penonton: {audience or 'Belum ditentukan'}\n\nSudut pembahasan: {angle or 'Belum ditentukan'}\n\nJudul kerja: {title or keyword}\n\n## Dasar isi\n{content or 'Ringkasan/transkrip belum tersedia. Lengkapi sebelum menulis janji judul.'}\n\n## Rencana produksi\n1. Pembuka: jelaskan masalah penonton dan hasil yang benar-benar dibahas.\n2. Konteks: definisikan masalah dan kebutuhan penonton.\n3. Pembahasan: susun langkah/bukti berdasarkan dasar isi di atas.\n4. Contoh: pilih contoh yang dapat diverifikasi.\n5. Penutup: rangkum hasil dan langkah berikutnya.\n\n## Konsep thumbnail\nTampilkan satu fokus visual yang sesuai isi. Pilih teks singkat yang melengkapi judul.\n\n## Pemeriksaan sebelum publikasi\nPeriksa fakta, izin aset, kesesuaian judul, deskripsi, dan chapter. Timestamp hanya dibuat dari transkrip bertimestamp.\n'''

def parse_chapters(text):
    found = []
    for line in str(text).splitlines():
        m = re.match(r'^\s*\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?\s+(.+)', line)
        if not m: continue
        nums = list(map(int, m[1].split(':')))
        if any(n >= 60 for n in nums[1:]): continue
        sec = sum(n * 60 ** i for i, n in enumerate(reversed(nums)))
        found.append((sec, m[1], m[2][:90]))
    if len(found) < 3 or found[0][0] != 0 or any(b[0]-a[0] < 10 for a,b in zip(found,found[1:])):
        return [], 'Perlu minimal tiga chapter, mulai 00:00, berurutan, dan berjarak minimal 10 detik. Periksa durasi chapter terakhir sendiri.'
    return [f'{stamp} {label}' for _, stamp, label in found], 'Draf dari timestamp sumber. Tinjau judul chapter sebelum publikasi.'

class ResearchStore:
    def __init__(self, path=None):
        self.path = Path(path or os.environ.get('NICHE_HUNTER_DATA_DIR', 'data'))
        self.path.mkdir(parents=True, exist_ok=True)
        self.db = self.path / 'research.sqlite3'
        with self.connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, payload TEXT, updated TEXT, PRIMARY KEY(kind,id))')
    def connect(self):
        return sqlite3.connect(self.db, timeout=10)
    def save(self, kind, ident, payload):
        with self.connect() as c:
            c.execute('INSERT OR REPLACE INTO records VALUES(?,?,?,?)', (kind, str(ident), json.dumps(payload, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))
            if kind == 'history':
                c.execute("DELETE FROM records WHERE kind='history' AND id NOT IN (SELECT id FROM records WHERE kind='history' ORDER BY updated DESC LIMIT 30)")
    def list(self, kind):
        with self.connect() as c:
            return [{'id': r[0], 'payload': json.loads(r[1]), 'updated': r[2]} for r in c.execute('SELECT id,payload,updated FROM records WHERE kind=? ORDER BY updated DESC', (kind,))]
    def delete(self, kind, ident):
        with self.connect() as c:
            deleted = c.execute('DELETE FROM records WHERE kind=? AND id=?', (kind, str(ident))).rowcount
        return bool(deleted)
    def export(self):
        return json.dumps({'schema': 2, **{kind:self.list(kind) for kind in RECORD_KINDS}}, ensure_ascii=False, indent=2)
    def restore(self, value):
        if not isinstance(value, dict) or value.get('schema') not in (1,2): raise ValueError('Format cadangan tidak didukung.')
        pending = []
        for kind in RECORD_KINDS:
            rows = value.get(kind, [])
            if not isinstance(rows, list) or len(rows) > 1000: raise ValueError('Daftar cadangan tidak valid atau terlalu besar.')
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get('payload'), dict) or not isinstance(row.get('id'), str):
                    raise ValueError('Entri cadangan tidak valid.')
                if not row['id'] or len(row['id']) > 256: raise ValueError('ID cadangan tidak valid.')
                payload = row['payload']
                if kind == 'rank_track':
                    from modules.intelligence import parse_video_id
                    parse_video_id(payload.get('video_id',''))
                    observations = payload.get('observations',[])
                    if not isinstance(observations,list) or len(observations)>100 or any(not isinstance(o,dict) for o in observations):
                        raise ValueError('Riwayat posisi tidak valid.')
                if kind == 'planner' and payload.get('status') not in ('Ide','Riset','Produksi','Siap terbit','Terbit'):
                    raise ValueError('Status kalender tidak valid.')
                if kind == 'planner':
                    from datetime import date
                    try: date.fromisoformat(payload.get('due',''))
                    except (ValueError,TypeError): raise ValueError('Tanggal kalender tidak valid.')
                    if not isinstance(payload.get('title'),str) or not payload['title'].strip() or payload.get('priority') not in ('Tinggi','Sedang','Rendah'):
                        raise ValueError('Rencana konten tidak valid.')
                if kind == 'rank_track' and (not isinstance(payload.get('keyword'),str) or not re.fullmatch(r'[A-Z]{2}',payload.get('region','')) or not re.fullmatch(r'[a-z]{2}',payload.get('language',''))):
                    raise ValueError('Wilayah, bahasa, atau keyword pelacakan tidak valid.')
                pending.append((kind,row['id'],json.dumps(payload,ensure_ascii=False),datetime.now(timezone.utc).isoformat()))
        with self.connect() as c:
            c.executemany('INSERT OR REPLACE INTO records VALUES(?,?,?,?)', pending)
            c.execute("DELETE FROM records WHERE kind='history' AND id NOT IN (SELECT id FROM records WHERE kind='history' ORDER BY updated DESC LIMIT 30)")
        return len(pending)

    def append_rank(self, ident, observation):
        """Read-modify-write under one lock; keep the latest 100 successful measurements."""
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute("SELECT payload FROM records WHERE kind='rank_track' AND id=?",(ident,)).fetchone()
            if row is None: raise ValueError('Pelacakan sudah dihapus.')
            payload = json.loads(row[0])
            payload['observations'] = (payload.get('observations',[]) + [observation])[-100:]
            c.execute("UPDATE records SET payload=?,updated=? WHERE kind='rank_track' AND id=?",
                      (json.dumps(payload,ensure_ascii=False),datetime.now(timezone.utc).isoformat(),ident))

def safe_video(video):
    return {k: video[k] for k in FIELDS if k in video}
