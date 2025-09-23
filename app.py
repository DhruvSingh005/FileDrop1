import os
import random
import string
from io import BytesIO
import qrcode
import base64
from flask import Flask, render_template, redirect, url_for, request, session, Response, g, send_from_directory
import sys
import sqlite3
import socket

# === DATABASE & FILE STORAGE CONFIGURATION ===
DATABASE = 'filedrop.db'
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                room_code TEXT PRIMARY KEY,
                presenter_key TEXT
            )
        ''')
        db.commit()

# Create a Flask application instance
app = Flask(__name__)
app.secret_key = 'your_very_secret_key_here'

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# --- ROUTES ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/create')
def create_room():
    db = get_db()
    cursor = db.cursor()
    room_code = ''.join(random.choices(string.ascii_uppercase, k=5))
    presenter_key = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))

    cursor.execute('INSERT INTO rooms (room_code, presenter_key) VALUES (?, ?)', (room_code, presenter_key))
    db.commit()

    room_folder = os.path.join(UPLOAD_FOLDER, room_code)
    if not os.path.exists(room_folder):
        os.makedirs(room_folder)
    
    session['presenter_key'] = presenter_key
    return redirect(url_for('room', code=room_code))

@app.route('/room/<code>')
def room(code):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT presenter_key FROM rooms WHERE room_code = ?', (code,))
    room_data = cursor.fetchone()
    
    if room_data:
        is_presenter = (session.get('presenter_key') == room_data[0])
    else:
        return "Room not found."

    host = request.host
    qr_url = f"http://{host}/join?code={code}"
    qr_img = qrcode.make(qr_url)
    buffer = BytesIO()
    qr_img.save(buffer, 'PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    room_files = list(os.listdir(os.path.join(UPLOAD_FOLDER, code))) if os.path.exists(os.path.join(UPLOAD_FOLDER, code)) else []
    
    return render_template('room.html', room_code=code, files=room_files, is_presenter=is_presenter, qr_base64=qr_base64)

@app.route('/join', methods=['GET', 'POST'])
def join_room():
    db = get_db()
    cursor = db.cursor()
    if request.method == 'POST':
        code = request.form['code'].upper()
        cursor.execute('SELECT room_code FROM rooms WHERE room_code = ?', (code,))
        if cursor.fetchone():
            return redirect(url_for('room', code=code))
        else:
            return render_template('join.html', error_message="Invalid room code. Please try again.")
    
    code = request.args.get('code')
    if code:
        cursor.execute('SELECT room_code FROM rooms WHERE room_code = ?', (code,))
        if cursor.fetchone():
            return redirect(url_for('room', code=code))

    return render_template('join.html', error_message="")

@app.route('/upload/<code>', methods=['POST'])
def upload_file(code):
    if 'file' not in request.files:
        return 'No file part'
    file = request.files['file']
    if file.filename == '':
        return 'No selected file'
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT room_code FROM rooms WHERE room_code = ?', (code,))
    if cursor.fetchone():
        room_folder = os.path.join(UPLOAD_FOLDER, code)
        if not os.path.exists(room_folder):
            os.makedirs(room_folder)
        filepath = os.path.join(room_folder, file.filename)
        file.save(filepath)
        return redirect(url_for('room', code=code))

    return "Error uploading file."

@app.route('/delete_file/<code>', methods=['POST'])
def delete_file(code):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT presenter_key FROM rooms WHERE room_code = ?', (code,))
    room_data = cursor.fetchone()

    is_presenter = (session.get('presenter_key') == room_data[0]) if room_data else False
    
    if room_data and is_presenter:
        filename = request.form['filename']
        filepath = os.path.join(UPLOAD_FOLDER, code, filename)
        
        if os.path.exists(filepath):
            os.remove(filepath)
        
        return redirect(url_for('room', code=code))
    
    return "Unauthorized access."

@app.route('/files/<code>')
def get_files(code):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT presenter_key FROM rooms WHERE room_code = ?', (code,))
    room_data = cursor.fetchone()
    
    is_presenter = (session.get('presenter_key') == room_data[0]) if room_data else False
    
    if room_data:
        files_list = list(os.listdir(os.path.join(UPLOAD_FOLDER, code))) if os.path.exists(os.path.join(UPLOAD_FOLDER, code)) else []
        files_dict_list = [{'filename': filename} for filename in files_list]
        return {'files': files_dict_list, 'is_presenter': is_presenter}
    return {'files': [], 'is_presenter': False}

@app.route('/download_file')
def download_file_route():
    room_code = request.args.get('room_code')
    filename = request.args.get('filename')
    
    if not room_code or not filename:
        return "File not found.", 404
    
    filepath = os.path.join(UPLOAD_FOLDER, room_code, filename)
    if os.path.exists(filepath):
        return send_from_directory(os.path.join(os.getcwd(), UPLOAD_FOLDER, room_code), filename, as_attachment=True)
    
    return "File not found.", 404

@app.route('/presenter/<code>')
def presenter_view(code):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT presenter_key FROM rooms WHERE room_code = ?', (code,))
    room_data = cursor.fetchone()
    
    is_presenter = (session.get('presenter_key') == room_data[0]) if room_data else False
    
    if room_data:
        files_list = list(os.listdir(os.path.join(UPLOAD_FOLDER, code))) if os.path.exists(os.path.join(UPLOAD_FOLDER, code)) else []
        return render_template('presenter_view.html', room_code=code, files=files_list, is_presenter=is_presenter)
    return "Room not found."


if __name__ == '__main__':
    init_db()
    try:
        app.run(host='0.0.0.0', port=8080)
    except Exception as e:
        print("An error occurred during startup:", e, file=sys.stderr)