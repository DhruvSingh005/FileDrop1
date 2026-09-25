import os
import random
import string
from io import BytesIO
import qrcode
import base64
from flask import Flask, render_template, redirect, url_for, request, session, jsonify
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback_secret_key_change_in_production')

# === SUPABASE CONFIGURATION ===
url: str = "https://qzpgqlfujfyjfstfxqgj.supabase.co"
key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF6cGdxbGZ1amZ5amZzdGZ4cWdqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5MDI1NTMwNiwiZXhwIjoyMTA1ODMxMzA2fQ.oXQEYfAMORqJJ2dbjoerq_UOFbohGFm5BqpG9RqN3sU"
supabase: Client = create_client(url, key)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/create')
def create_room():
    room_code = ''.join(random.choices(string.ascii_uppercase, k=5))
    presenter_key = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))

    # Insert into Supabase
    supabase.table('rooms').insert({
        'room_code': room_code, 
        'presenter_key': presenter_key
    }).execute()

    session['presenter_key'] = presenter_key
    return redirect(url_for('room', code=room_code))

@app.route('/room/<code>')
def room(code):
    # Check if room exists and get presenter key
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

    # Fetch files for this room (fetch all data and keep it as a dictionary)
    files_response = supabase.table('files').select('*').eq('room_code', code).execute()
    room_files = files_response.data
    
    return render_template('room.html', room_code=code, files=room_files, is_presenter=is_presenter, qr_base64=qr_base64)

@app.route('/join', methods=['GET', 'POST'])
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

@app.route('/upload/<code>', methods=['POST'])
def upload_file(code):
    if 'file' not in request.files:
        return 'No file part'
    file = request.files['file']
    if file.filename == '':
        return 'No selected file'
    
    # Check if room exists
    room_check = supabase.table('rooms').select('room_code').eq('room_code', code).execute()
    if len(room_check.data) > 0:
        file_bytes = file.read()
        file_path = f"{code}/{file.filename}"
        
        # Upload to Supabase Storage bucket
        supabase.storage.from_("filedrop").upload(file_path, file_bytes)
        
        # Get the public URL
        public_url = supabase.storage.from_("filedrop").get_public_url(file_path)

        # Save metadata to Supabase DB
        supabase.table('files').insert({
            'room_code': code,
            'filename': file.filename,
            'file_url': public_url,
            'storage_path': file_path
        }).execute()

        return redirect(url_for('room', code=code))

    return "Error uploading file. Room not found."

@app.route('/delete_file/<code>', methods=['POST'])
def delete_file(code):
    room_check = supabase.table('rooms').select('presenter_key').eq('room_code', code).execute()
    if len(room_check.data) == 0:
        return "Room not found."
    
    room_data = room_check.data[0]
    is_presenter = (session.get('presenter_key') == room_data['presenter_key'])
    
    if is_presenter:
        filename = request.form['filename']
        
        # Get storage path
        file_data = supabase.table('files').select('storage_path').eq('room_code', code).eq('filename', filename).execute()
        
        if len(file_data.data) > 0:
            storage_path = file_data.data[0]['storage_path']
            
            # Delete from Storage
            supabase.storage.from_("filedrop").remove([storage_path])
            
            # Delete from DB
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
        # 1. Get all file paths for this room
        files_response = supabase.table('files').select('storage_path').eq('room_code', code).execute()
        storage_paths = [row['storage_path'] for row in files_response.data]
        
        # 2. Delete all files physically from Supabase Storage
        if storage_paths:
            supabase.storage.from_("filedrop").remove(storage_paths)
            
        # 3. Delete file metadata from the database
        supabase.table('files').delete().eq('room_code', code).execute()
        
        # 4. Delete the room itself
        supabase.table('rooms').delete().eq('room_code', code).execute()
        
        # Redirect the presenter back to the home page
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
        
    # Tell the frontend the room no longer exists
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
        
        # Fetch all file data, keeping the dictionary structure
        files_response = supabase.table('files').select('*').eq('room_code', code).execute()
        files_list = files_response.data
        
        return render_template('presenter_view.html', room_code=code, files=files_list, is_presenter=is_presenter)
        
    return "Room not found."