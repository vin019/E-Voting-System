from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
import os

# Initialize the Flask app
app = Flask(__name__)
app.config.from_object(Config)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret')
mysql = MySQL(app)

# -------------------------------
# Utility Functions
# -------------------------------

def requires_role(role_name):
    """
    Decorator to enforce role-based access control.
    """
    def wrapper(f):
        def decorated_function(*args, **kwargs):
            if 'role' not in session:
                flash('Please log in first.', 'danger')
                return redirect(url_for('login'))

            cur = mysql.connection.cursor()
            cur.execute("SELECT role_name FROM roles WHERE id = %s", (session['role'],))
            role = cur.fetchone()
            cur.close()

            if not role or role['role_name'] != role_name:
                flash('Access denied: insufficient permissions.', 'danger')
                return redirect(url_for('index'))

            return f(*args, **kwargs)

        decorated_function.__name__ = f.__name__
        return decorated_function
    return wrapper


def log_activity(user_id, action):
    """
    Log user activity in the database.
    """
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO activity_logs (user_id, action) VALUES (%s, %s)", (user_id, action))
    mysql.connection.commit()
    cur.close()


@app.before_request
def check_db_connection():
    """
    Ensure database connection is active before processing requests.
    """
    cur = mysql.connection.cursor()
    cur.execute("SELECT 1")
    cur.close()
    print("Successfully connected to the database!")


# -------------------------------
# Routes
# -------------------------------

# Home Route
@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')


# About Page
@app.route('/about')
def about():
    if 'username' in session:
        return render_template('about.html')
    return redirect(url_for('login'))


# Vote Page
@app.route('/vote')
def vote():
    if 'username' in session:
        return render_template('vote.html')
    return redirect(url_for('login'))


# Dashboard Page
@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('dashboard.html')
    return redirect(url_for('login'))


# -------------------------------
# Authentication Routes
# -------------------------------

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user['password'], password):
            session['username'] = username
            session['role'] = user['role_id']
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')


# Register Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, email))
        existing_user = cur.fetchone()

        if existing_user:
            flash('Username or email already exists!', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        cur.execute(
            "INSERT INTO users (username, password, email, role_id) VALUES (%s, %s, %s, %s)",
            (username, hashed_password, email, 1)  # Default role is 'voter'
        )
        mysql.connection.commit()
        cur.close()

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# Logout Route
@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    session.clear()
    if user_id:
        log_activity(user_id, "User logged out")
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))


# -------------------------------
# Admin Routes
# -------------------------------

# Admin Dashboard
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users")
    users = cur.fetchall()
    cur.close()
    return render_template('admin.html', users=users)


# Grant Admin Privileges
@app.route('/grant_admin/<int:user_id>', methods=['POST'])
@requires_role('admin')
def grant_admin(user_id):
    cur = mysql.connection.cursor()
    cur.execute("UPDATE users SET role_id = (SELECT id FROM roles WHERE role_name = 'admin') WHERE id = %s", (user_id,))
    mysql.connection.commit()
    cur.close()
    log_activity(session.get('user_id'), "Granted admin privileges")
    flash('Admin privileges granted.', 'success')
    return redirect(url_for('admin'))


# -------------------------------
# Run the Application
# -------------------------------
if __name__ == '__main__':
    app.run(debug=True)
