from flask import Flask, redirect, render_template, url_for, request, session
from database import db
import bcrypt

app = Flask(__name__)
app.secret_key = 'notes@26'

@app.route('/')
def base():
    return redirect(url_for('login'))

@app.route('/login', methods=['POST', 'GET'])
def login():
    info = request.args.get('info')
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        cursor = db.cursor()
        cursor.execute("select * from users where email = %s", (email,))
        user = cursor.fetchone()

        if user:
            if bcrypt.checkpw(password.encode('utf-8'),
                              user[3].encode('utf-8')):
                session['id'] = user[0]
                session['username'] = user[1]
                return redirect(url_for('dashboard', username=user[1]))
            return redirect(url_for('login', info='Incorrect Password'))
        return redirect(url_for('login', info='Email is not registered'))        

    return render_template('login.html', info=info)

@app.route('/register', methods=['GET', 'POST'])
def register():
    info = request.args.get('info')
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        hashed_password = bcrypt.hashpw(password.encode('utf-8'),
                                        bcrypt.gensalt()).decode('utf-8')
        cursor = db.cursor()
        cursor.execute("select * from users where email = %s", (email,))
        user = cursor.fetchone()

        if user:
            return redirect(url_for('register', info="Email is already exist"))
        cursor.execute("insert into users(username,email,password) value(%s,%s,%s)", (username, email, hashed_password))
        db.commit()
        return redirect(url_for('login')) 

    return render_template('register.html', info=info)

@app.route('/dashboard/<username>')
def dashboard(username):
    if 'id' not in session:
        return redirect(url_for('login', info='Please login to continue'))
    cursor = db.cursor(dictionary=True)
    cursor.execute('select * from notes where user_id = %s order by created_at desc', (session['id'],))
    notes = cursor.fetchall()
    return render_template('dashboard.html', notes=notes)

@app.route('/createnote', methods=['POST'])
def createnote():
    if 'id' not in session:
        return redirect(url_for('login'))
    note = request.form.get('note')
    cursor = db.cursor()
    cursor.execute('insert into notes(user_id,content) value(%s,%s)', (session['id'], note))
    db.commit()
    return redirect(url_for('dashboard', username=session.get('username', '')))

@app.route('/editnote/<note_id>', methods=['GET', 'POST'])
def editnote(note_id):
    if 'id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        edit_note = request.form.get('notes')
        cursor = db.cursor()
        cursor.execute("Update notes set content = %s where user_id = %s and id = %s", (edit_note, session['id'], note_id))
        db.commit()
        return redirect(url_for('dashboard', username=session.get('username', '')))
    cursor = db.cursor(dictionary=True)
    cursor.execute('select * from notes where user_id = %s and id = %s', (session['id'], note_id))
    note = cursor.fetchone()
    return render_template('edit.html', note=note)

@app.route('/deletenote/<note_id>')
def deletenote(note_id):
    if 'id' not in session:
        return redirect(url_for('login'))
    cursor = db.cursor()
    cursor.execute('delete from notes where user_id = %s and id = %s', (session['id'], note_id))
    db.commit()
    return redirect(url_for('dashboard', username=session.get('username', '')))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == "__main__":
    import socket
    port = 5000
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(('127.0.0.1', 5000)) == 0:
            port = 5001
    print(f"Starting NotesApp on http://127.0.0.1:{port}")
    app.run(debug=True, port=port)