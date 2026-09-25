import os
import random
import string
from io import BytesIO
import qrcode
import base64
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, redirect, url_for, request, session, jsonify
from dotenv import load_dotenv
from supabase import create_client, Client
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback_secret_key_change_in_production')

# === SECURITY: INITIALIZE RATE LIMITER ===
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# === SUPABASE CONFIGURATION ===
url: str = "https://qzpgqlfujfyjfstfxqgj.supabase.co"
key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF6cGdxbGZ1amZ5amZzdGZ4cWdqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5MDI1NTMwNiwiZXhwIjoyMTA1ODMxMzA2fQ.oXQEYfAMORqJJ2dbjoerq_UOFbohGFm5BqpG9RqN3sU"
supabase: Client = create_client(url, key)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/create')
# Apply a specific rate limit to prevent spamming room creations
@limiter.limit("10 per hour") 
def create_room():
    room_code = ''.join(random.choices(string.ascii_uppercase, k=5))
    presenter_key = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))

    supabase.table('rooms').insert({
        'room_code': room_code, 
        'presenter_key': presenter_key
    }).execute()

    session['presenter_key'] = presenter_key
    return redirect(url_for('room', code=room_code))

@app.route('/room/<code>')
def room(code):
    response = supabase.table('rooms').select('presenter_key').eq('room_code', code).execute()
    
    if len(response.data) > 0:
        room_data = response.data[0]
        is_presenter = (session.get('presenter_key') == room_data['presenter_key'])
    else:
        return "Room not found."

    host = request.host
    qr_url = f"http://{host}/join?code={code}"
    qr_img = qrcode.make(qr_url)
    buffer = BytesIO()
    qr_img.save(buffer, 'PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    files_response = supabase.table('files').select('*').eq('room_code', code).execute()
    room_files = files_response.data
    
    return render_template('room.html', room_code=code, files=room_files, is_presenter=is_presenter, qr_base64=qr_base64)

@app.route('/join', methods=['GET', 'POST'])
# === SECURITY: BRUTE FORCE PROTECTION ===
# Allows a maximum of 5 room code guesses per minute per IP address
@limiter.limit("5 per minute")
def join_room():
    if request.method == 'POST':
        code = request.form['code'].upper()
        response = supabase.table('rooms').select('room_code').eq('room_code', code).execute()
        if len(response.data) > 0:
            return redirect(url_for('room', code=code))
        else:
            return render_template('join.html', error_message="Invalid room code. Please try again.")
    
    code = request.args.get('code')
    if code:
        response = supabase.table('rooms').select('room_code').eq('room_code', code).execute()
        if len(response.data) > 0:
            return redirect(url_for('room', code=code))

    return render_template('join.html', error_message="")

# Handle rate limit exceeded errors gracefully
@app.errorhandler(429)
def ratelimit_handler(e):
    return render_template('join.html', error_message="Security trigger: Too many attempts. Please wait 60 seconds and try again."), 429

@app.route('/save_file_record/<code>', methods=['POST'])
def save_file_record(code):
    room_check = supabase.table('rooms').select('room_code').eq('room_code', code).execute()
    if len(room_check.data) > 0:
        data = request.json
        filename = data.get('filename')
        
        if not filename:
            return jsonify({"error": "Filename missing"}), 400
            
        file_path = f"{code}/{filename}"
        public_url = supabase.storage.from_("filedrop").get_public_url(file_path)

        supabase.table('files').insert({
            'room_code': code,
            'filename': filename,
            'file_url': public_url,
            'storage_path': file_path
        }).execute()

        return jsonify({"status": "success", "file_url": public_url})

    return jsonify({"error": "Room not found"}), 404

@app.route('/delete_file/<code>', methods=['POST'])
def delete_file(code):
    room_check = supabase.table('rooms').select('presenter_key').eq('room_code', code).execute()
    if len(room_check.data) == 0:
        return "Room not found."
    
    room_data = room_check.data[0]
    is_presenter = (session.get('presenter_key') == room_data['presenter_key'])
    
    if is_presenter:
        filename = request.form['filename']
        file_data = supabase.table('files').select('storage_path').eq('room_code', code).eq('filename', filename).execute()
        
        if len(file_data.data) > 0:
            storage_path = file_data.data[0]['storage_path']
            supabase.storage.from_("filedrop").remove([storage_path])
            supabase.table('files').delete().eq('room_code', code).eq('filename', filename).execute()
        
        return redirect(url_for('room', code=code))
    
    return "Unauthorized access."

@app.route('/close_room/<code>', methods=['POST'])
def close_room(code):
    room_check = supabase.table('rooms').select('presenter_key').eq('room_code', code).execute()
    if len(room_check.data) == 0:
        return "Room not found."
    
    room_data = room_check.data[0]
    is_presenter = (session.get('presenter_key') == room_data['presenter_key'])
    
    if is_presenter:
        files_response = supabase.table('files').select('storage_path').eq('room_code', code).execute()
        storage_paths = [row['storage_path'] for row in files_response.data]
        
        if storage_paths:
            supabase.storage.from_("filedrop").remove(storage_paths)
            
        supabase.table('files').delete().eq('room_code', code).execute()
        supabase.table('rooms').delete().eq('room_code', code).execute()
        
        return redirect(url_for('home'))
        
    return "Unauthorized access."

@app.route('/files/<code>')
def get_files(code):
    room_check = supabase.table('rooms').select('presenter_key').eq('room_code', code).execute()
    
    if len(room_check.data) > 0:
        room_data = room_check.data[0]
        is_presenter = (session.get('presenter_key') == room_data['presenter_key'])
        
        files_response = supabase.table('files').select('filename, file_url').eq('room_code', code).execute()
        return jsonify({'room_exists': True, 'files': files_response.data, 'is_presenter': is_presenter})
        
    return jsonify({'room_exists': False, 'files': [], 'is_presenter': False})

@app.route('/download_file')
def download_file_route():
    room_code = request.args.get('room_code')
    filename = request.args.get('filename')
    
    if not room_code or not filename:
        return "File not found.", 404
    
    file_data = supabase.table('files').select('file_url').eq('room_code', room_code).eq('filename', filename).execute()
    
    if len(file_data.data) > 0:
        return redirect(file_data.data[0]['file_url'])
    
    return "File not found.", 404

@app.route('/presenter/<code>')
def presenter_view(code):
    room_check = supabase.table('rooms').select('presenter_key').eq('room_code', code).execute()
    
    if len(room_check.data) > 0:
        room_data = room_check.data[0]
        is_presenter = (session.get('presenter_key') == room_data['presenter_key'])
        
        files_response = supabase.table('files').select('*').eq('room_code', code).execute()
        files_list = files_response.data
        
        return render_template('presenter_view.html', room_code=code, files=files_list, is_presenter=is_presenter)
        
    return "Room not found."

@app.route('/cleanup-old-rooms-secret-task')
def cleanup_old_rooms():
    try:
        time_threshold = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
        old_rooms = supabase.table('rooms').select('room_code').lt('created_at', time_threshold).execute()
        
        deleted_count = 0
        for room in old_rooms.data:
            code = room['room_code']
            
            files_response = supabase.table('files').select('storage_path').eq('room_code', code).execute()
            storage_paths = [row['storage_path'] for row in files_response.data]
            
            if storage_paths:
                supabase.storage.from_("filedrop").remove(storage_paths)
                
            supabase.table('files').delete().eq('room_code', code).execute()
            supabase.table('rooms').delete().eq('room_code', code).execute()
            
            deleted_count += 1
            
        return jsonify({"status": "success", "rooms_deleted": deleted_count})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})