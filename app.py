from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

mysql = MySQL(app)

# Home route
@app.route('/')
def index():
    return redirect(url_for('login'))

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Check credentials
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cur.fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['username'] = username
            return redirect(url_for('vote'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        # Check if username or email already exists
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, email))
        existing_user = cur.fetchone()
        
        if existing_user:
            flash('Username or email already exists!', 'danger')
            return redirect(url_for('register'))
        
        # Hash the password for security
        hashed_password = generate_password_hash(password)

        # Insert new user into the database
        cur.execute("INSERT INTO users (username, password, email) VALUES (%s, %s, %s)", 
                    (username, hashed_password, email))
        mysql.connection.commit()

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# Voting page
@app.route('/vote', methods=['GET', 'POST'])
def vote():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        candidate = request.form['candidate']
        voter = session['username']
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM votes WHERE voter=%s", [voter])
        result = cur.fetchone()

        if result:
            flash('You have already voted!', 'danger')
        else:
            cur.execute("INSERT INTO votes (voter, candidate) VALUES (%s, %s)", (voter, candidate))
            mysql.connection.commit()
            flash('Your vote has been recorded', 'success')

    return render_template('vote.html')

@app.route('/header')
def header():
    return render_template('header.html')

# Logout
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
