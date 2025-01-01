from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
import os

app = Flask(__name__)
app.config.from_object(Config)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret')
mysql = MySQL(app)

def requires_role(role_name):
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
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO activity_logs (user_id, action) VALUES (%s, %s)", (user_id, action))
    mysql.connection.commit()
    cur.close()

@app.before_request
def check_db_connection():
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
    
    # Fetch the user's role from the database
    cur = mysql.connection.cursor()
    cur.execute("SELECT role_name FROM roles WHERE id = %s", (session['role'],))
    role = cur.fetchone()
    cur.close()

    return render_template('index.html', user_role=role['role_name'])

# About Page
@app.route('/about')
def about():
    if 'username' in session:
        return render_template('about.html')
    return redirect(url_for('login'))

@app.route('/vote', methods=['GET', 'POST'])
def vote():
    if 'user_id' not in session:
        flash('You must be logged in to vote.', 'danger')
        return redirect(url_for('login'))

    # Fetch all elections
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name FROM elections")
    elections = cur.fetchall()

    candidates = []
    if request.method == 'POST':
        election_id = request.form.get('election_id')
        # Fetch candidates based on the selected election ID
        cur.execute("SELECT * FROM candidates WHERE election_id = %s", (election_id,))
        candidates = cur.fetchall()
        cur.close()
        return render_template('vote.html', elections=elections, candidates=candidates, selected_election_id=election_id)

    cur.close()
    return render_template('vote.html', elections=elections, candidates=candidates)

@app.route('/submit_vote', methods=['POST'])
def submit_vote():
    candidate_id = request.form['candidate_id']
    election_id = request.form['election_id']
    user_id = session['user_id']  # Assuming you have the user ID in the session
    print(f"Candidate ID: {candidate_id}, Election ID: {election_id}, User ID: {user_id}")
    
    # Insert the vote into the database
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO votes (candidate_id, user_id) VALUES (%s, %s, %s)", (candidate_id, election_id, user_id))    
    mysql.connection.commit()
    cur.close()

    flash('Your vote has been recorded successfully!', 'success')
    return redirect(url_for('index'))

# Dashboard Page
@app.route('/dashboard', methods=['GET', 'POST'])
@requires_role('admin')
def dashboard():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT users.id, users.username, users.email, roles.role_name 
        FROM users 
        JOIN roles ON users.role_id = roles.id
    """)
    users = cur.fetchall()

    # Query to count total logins
    cur.execute("SELECT COUNT(*) as total_logins FROM login_logs")
    total_logins = cur.fetchone()['total_logins']
    cur.close()
    
    # Fetch the user_id's role from the database
    cur = mysql.connection.cursor()
    cur.execute("SELECT role_name FROM roles WHERE id = %s", (session['role'],))
    role = cur.fetchone()
    cur.close()

    return render_template('dashboard.html', users=users, user_role=role['role_name'], total_logins=total_logins)

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
            session['user_id'] = user['id']  # Store user_id in session
            flash('Login successful!', 'success')

            # Log the login event
            log_login(user['id'])

            return redirect(url_for('index'))
        
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')

def log_login(user_id):
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO login_logs (user_id) VALUES (%s)", (user_id,))
    mysql.connection.commit()
    cur.close()

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
        log_activity(user_id, "User  logged out")  # Log the logout activity
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

# -------------------------------
# Admin Routes
# -------------------------------

# Admin Dashboard
@app.route('/admin', methods=['GET', 'POST'])
@requires_role('admin')
def admin():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM candidates")  # Fetch all candidates from the database
    candidates = cur.fetchall()

    # Fetch existing elections
    cur.execute("SELECT * FROM elections")
    elections = cur.fetchall()
    
    cur.execute("""
        SELECT candidates.*, elections.name AS election_name 
        FROM candidates 
        LEFT JOIN elections ON candidates.election_id = elections.id
    """)
    candidates = cur.fetchall()
    
    cur.execute("SELECT * FROM elections")
    elections = cur.fetchall()

    cur.close()
    
    return render_template('admin.html', candidates=candidates, elections=elections)

# Grant Admin Privileges
@app.route('/grant_admin/<int:user_id>', methods=['POST'])
@requires_role('admin')
def grant_admin(user_id):
    cur = mysql.connection.cursor()
    # Update the user's role to admin
    cur.execute("UPDATE users SET role_id = (SELECT id FROM roles WHERE role_name = 'admin') WHERE id = %s", (user_id,))
    mysql.connection.commit()
    cur.close()
    
    flash('Admin privileges granted successfully.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/remove_admin/<int:user_id>', methods=['POST'])
@requires_role('admin')
def remove_admin(user_id):
    cur = mysql.connection.cursor()
    # Update the user's role to a regular user (assuming role_id 1 is for regular users)
    cur.execute("UPDATE users SET role_id = (SELECT id FROM roles WHERE role_name = 'voter') WHERE id = %s", (user_id,))
    mysql.connection.commit()
    cur.close()
    
    flash('Admin privileges removed successfully.', 'success')
    return redirect(url_for('dashboard'))


# Edit Candidate Route
@app.route('/edit_candidate', methods=['POST'])
@requires_role('admin')
def edit_candidate():
    candidate_id = request.form 
    ['candidateId']
    candidate_name = request.form['candidateName']
    candidate_position = request.form['candidatePosition']

    # Basic validation
    if not candidate_name or not candidate_position:
        flash('Error: All fields are required.', 'danger')
        return redirect(url_for('admin'))

    # Update the candidate in the database
    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE candidates 
        SET name = %s, position = %s 
        WHERE id = %s
    """, (candidate_name, candidate_position, candidate_id))
    mysql.connection.commit()
    cur.close()

    flash('Candidate updated successfully!', 'success')
    return redirect(url_for('admin'))

@app.route('/add_candidate', methods=['POST'])
@requires_role('admin')
def add_candidate():
    candidate_name = request.form['candidateName']
    candidate_position = request.form['candidatePosition']
    new_election_id = request.form['electionId']  # New election ID
    existing_election_id = request.form['existingElectionId']  # Existing election ID

    # Determine which election ID to use
    selected_election_id = existing_election_id if existing_election_id else new_election_id

    # Validate input data
    if not candidate_name or not candidate_position:
        flash('Candidate name and position are required!', 'danger')
        return redirect(url_for('admin'))

    if not selected_election_id:
        flash('Please select an existing election ID or enter a new one!', 'danger')
        return redirect(url_for('admin'))

    # Insert the new candidate into the database
    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO candidates (name, position, election_id) 
            VALUES (%s, %s, %s)
        """, (candidate_name, candidate_position, selected_election_id))
        mysql.connection.commit()
        cur.close()
        flash('Candidate added successfully!', 'success')
    except Exception as e:
        mysql.connection.rollback()  # Rollback in case of error
        print(f'Error adding candidate: {str(e)}')  # Log the error
        flash(f'Error adding candidate: {str(e)}', 'danger')
        return redirect(url_for('admin'))

    return redirect(url_for('admin'))

@app.route('/delete_candidate/<int:candidate_id>', methods=['POST'])
def delete_candidate(candidate_id):
    try:
        cur = mysql.connection.cursor()
        # Delete the candidate from the database
        cur.execute("DELETE FROM candidates WHERE id = %s", (candidate_id,))
        mysql.connection.commit()
        cur.close()
        flash('Candidate deleted successfully!', 'success')
    except Exception as e:
        mysql.connection.rollback()
        print(f"Error deleting candidate: {e}")
        flash('An error occurred while deleting the candidate.', 'danger')
        print(f"Deleting candidate with ID: {candidate_id}")
    return redirect(url_for('admin_page'))

# -------------------------------
# Run the Application
# -------------------------------
if __name__ == '__main__':
    app.run(debug=True)
