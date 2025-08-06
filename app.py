from flask import Flask, render_template, request, send_from_directory, redirect, url_for, flash, jsonify
import yt_dlp
import os
import re
from werkzeug.utils import secure_filename
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, error, TIT2, TPE1, TALB
from urllib.parse import urlparse, parse_qs
from threading import Lock

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui_32_caracteres_ou_mais'
app.config['UPLOAD_FOLDER'] = 'static/downloads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

download_progress = {
    'progress': 0,
    'status': 'idle',
    'filename': None,
    'error': None
}
progress_lock = Lock()

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def clean_text(text):
    return re.sub(r'[\\/*?:"<>|]', '', str(text))

def sanitize_filename(title):
    return secure_filename(clean_text(title))[:100]

def is_valid_youtube_url(url):
    patterns = [
        r'(https?://)?(www\.)?youtube\.com/watch\?v=',
        r'(https?://)?youtu\.be/',
        r'(https?://)?(www\.)?youtube\.com/embed/',
        r'(https?://)?(www\.)?youtube\.com/shorts/'
    ]
    return any(re.search(pattern, url) for pattern in patterns)

def extract_video_id(url):
    if 'youtu.be' in url:
        return url.split('/')[-1].split('?')[0]
    elif 'youtube.com' in url:
        params = parse_qs(urlparse(url).query)
        return params.get('v', [None])[0]
    return None

def update_progress(status, progress=None, filename=None, error=None):
    global download_progress
    with progress_lock:
        download_progress['status'] = status
        if progress is not None:
            download_progress['progress'] = progress
        if filename is not None:
            download_progress['filename'] = filename
        if error is not None:
            download_progress['error'] = error

def download_audio(youtube_url, quality='192'):
    try:
        update_progress('downloading', progress=0)
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                percent = d.get('_percent_str', '0%').strip('%')
                if percent == 'NA':
                    if '_total_bytes_str' in d and '_downloaded_bytes_str' in d:
                        try:
                            total = float(d['_total_bytes_str'].replace(',', ''))
                            downloaded = float(d['_downloaded_bytes_str'].replace(',', ''))
                            percent = (downloaded / total) * 100
                        except:
                            percent = 0
                try:
                    update_progress('downloading', progress=float(percent))
                except ValueError:
                    update_progress('downloading', progress=0)

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(app.config['UPLOAD_FOLDER'], '%(title)s.%(ext)s'),
            'writethumbnail': True,
            'quiet': True,
            'noplaylist': True,
            'progress_hooks': [progress_hook],
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': quality,
                },
                {
                    'key': 'FFmpegMetadata',
                    'add_metadata': True,
                },
                {
                    'key': 'EmbedThumbnail',
                    'already_have_thumbnail': False,
                }
            ],
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            if 'entries' in info:  # Isso é uma playlist
                raise Exception("URL parece ser uma playlist. Use um link de vídeo específico.")
            
            filename = ydl.prepare_filename(info)
            base_filename = os.path.splitext(filename)[0]
            final_mp3 = base_filename + '.mp3'
            
            if not os.path.exists(final_mp3):
                raise Exception("Arquivo MP3 não foi criado corretamente")
            
            enhance_metadata(final_mp3, info.get('title'), info.get('uploader'))
            
            update_progress('complete', progress=100, filename=os.path.basename(final_mp3))
            return os.path.basename(final_mp3)
            
    except Exception as e:
        update_progress('error', error=str(e))
        raise e

def enhance_metadata(mp3_file, title, artist):
    try:
        audio = MP3(mp3_file, ID3=ID3)
        try:
            audio.add_tags()
        except error:
            pass
        audio.tags.add(TIT2(encoding=3, text=clean_text(title)))
        audio.tags.add(TPE1(encoding=3, text=clean_text(artist)))
        audio.tags.add(TALB(encoding=3, text="YouTube Download"))
        audio.save(v2_version=3)
    except Exception as e:
        print(f"Warning metadata: {str(e)}")

@app.route('/progress')
def progress():
    global download_progress
    with progress_lock:
        return jsonify(download_progress)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        youtube_url = request.form.get('youtube_url', '').strip()
        quality = request.form.get('quality', '192')
        
        if not youtube_url:
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'error': 'Por favor, insira uma URL do YouTube'}), 400
            flash('Por favor, insira uma URL do YouTube', 'error')
            return redirect(url_for('index'))
            
        if not is_valid_youtube_url(youtube_url):
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'error': 'URL do YouTube inválida'}), 400
            flash('URL do YouTube inválida. Use formatos válidos', 'error')
            return redirect(url_for('index'))
        
        try:
            filename = download_audio(youtube_url, quality)
            if filename:
                if request.headers.get('Accept') == 'application/json':
                    return jsonify({'success': True, 'filename': filename})
                flash(f'Download completo: {filename}', 'success')
                flash(f'<a href="/downloads/{filename}" class="alert-link">Clique aqui para baixar</a>', 'success')
            else:
                if request.headers.get('Accept') == 'application/json':
                    return jsonify({'success': False, 'error': 'Falha no download'}), 500
                flash('Falha no download. Tente novamente.', 'error')
        except Exception as e:
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'error': str(e)}), 500
            flash(f'Erro: {str(e)}', 'error')
        
        if request.headers.get('Accept') == 'application/json':
            return jsonify({'success': False, 'error': 'Unknown error'}), 500
        return redirect(url_for('index'))
    
    update_progress('idle', progress=0, filename=None, error=None)
    return render_template('index.html')

@app.route('/downloads/<filename>')
def download_file(filename):
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        filename,
        as_attachment=True,
        mimetype='audio/mpeg'
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)