from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, current_user, login_user, logout_user, login_required
from functools import wraps
from config import Config
import os

app = Flask(__name__)
app.config.from_object(Config)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret')
mysql = MySQL(app)

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Mock user class
class User(UserMixin):
    def __init__(self, id, role):
        self.id = id
        self.role = role

# Mock user loader function
@login_manager.user_loader
def load_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, role_id FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    
    if user:
        return User(id=user['id'], role=user['role_id'])
    return None

def requires_role(role_name):
    def wrapper(f):
        @wraps(f)
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
    try:
        cur.execute("SELECT role_name FROM roles WHERE id = %s", (session['role'],))
        role = cur.fetchone()
    finally:
        cur.close()

    # Pass the role to the template (handle case where role is None)
    return render_template('index.html', user_role=role['role_name'] if role else None)

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

    user_id = session['user_id']
    user_role = session.get('role_id', 1)  # Default to 'voter' role if not specified
    cur = mysql.connection.cursor()

    # Check if the user has already voted in the current election
    if request.method == 'POST':
        selected_election_id = request.form.get('electionIdFilter')
    else:  # GET method
        selected_election_id = request.args.get('electionIdFilter')

    if selected_election_id:
        selected_election_id = int(selected_election_id)
    else:
        selected_election_id = None  # Use None to indicate all elections

    # Determine if the user has voted in the selected election
    if selected_election_id:
        cur.execute("SELECT 1 FROM votes WHERE user_id = %s AND election_id = %s LIMIT 1", (user_id, selected_election_id))
    else:
        cur.execute("SELECT 1 FROM votes WHERE user_id = %s LIMIT 1", (user_id,))
    result = cur.fetchone()
    has_voted = result is not None

    # Fetch all positions
    cur.execute("SELECT * FROM positions")
    positions = cur.fetchall()

    # Fetch existing elections
    cur.execute("SELECT * FROM elections")
    elections = cur.fetchall()

    # Initialize candidates_by_position dictionary
    candidates_by_position = {}

    for position in positions:
        if selected_election_id:
            # Fetch candidates based on the selected election ID and position
            cur.execute("""
                SELECT candidates.*, positions.name AS position_name, elections.name AS election_name
                FROM candidates
                LEFT JOIN positions ON candidates.position_id = positions.id
                LEFT JOIN elections ON candidates.election_id = elections.id
                WHERE candidates.position_id = %s AND candidates.election_id = %s
            """, (position['id'], selected_election_id))
        else:
            # Fetch candidates for all elections excluding already voted ones
            cur.execute("""
                SELECT candidates.*, positions.name AS position_name, elections.name AS election_name
                FROM candidates
                LEFT JOIN positions ON candidates.position_id = positions.id
                LEFT JOIN elections ON candidates.election_id = elections.id
                WHERE candidates.position_id = %s AND candidates.id NOT IN (
                    SELECT candidate_id FROM votes WHERE user_id = %s
                )
            """, (position['id'], user_id))
        
        candidates = cur.fetchall()
        candidates_by_position[position['name']] = candidates

    cur.close()

    return render_template('vote.html', candidates_by_position=candidates_by_position, elections=elections, selected_election_id=selected_election_id, has_voted=has_voted, user_role=user_role)

@app.route('/submit_vote', methods=['POST'])
def submit_vote():
    if 'user_id' not in session:
        flash('You must be logged in to vote.', 'danger')
        return redirect(url_for('login'))

    user_id = session['user_id']
    election_id = request.form.get('election_id')
    votes = []

    # Debugging: Print form data
    print(f"Form Data: {request.form}")

    for position in request.form.getlist('positions'):
        candidate_id = request.form.get(position)
        print(f"Position: {position}, Candidate ID: {candidate_id}")  # Debugging statement
        if candidate_id:
            votes.append((user_id, candidate_id, election_id))

    if votes:
        cur = mysql.connection.cursor()
        try:
            # Record votes in the database
            cur.executemany("INSERT INTO votes (user_id, candidate_id, election_id) VALUES (%s, %s, %s)", votes)
            mysql.connection.commit()
            flash('Your vote has been recorded!', 'success')
        except Exception as e:
            mysql.connection.rollback()
            flash(f'An error occurred: {e}', 'danger')
            print(f"Error: {e}")  # Debugging statement
        finally:
            cur.close()
    else:
        flash('Please select a candidate for each position.', 'danger')
        return redirect(url_for('vote'))

    return redirect(url_for('index'))

@app.route('/vote_results')
def vote_results():
    user_role = session.get('role_id', 1)  # Default to 'voter' role if not specified
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT 
            candidates.name AS candidate_name, 
            COALESCE(COUNT(votes.candidate_id), 0) AS votes, 
            elections.name AS election_name, 
            positions.name AS position_name
        FROM candidates
        LEFT JOIN votes ON votes.candidate_id = candidates.id
        LEFT JOIN elections ON candidates.election_id = elections.id
        LEFT JOIN positions ON candidates.position_id = positions.id
        GROUP BY candidates.id, candidates.name, elections.name, positions.name
        ORDER BY votes DESC
    """)
    vote_results = cur.fetchall()
    cur.close()
    return render_template('vote_results.html', vote_results=vote_results, user_role=user_role)

# Dashboard Page
@app.route('/dashboard', methods=['GET', 'POST'], endpoint='dashboard')
@login_required
@requires_role('admin')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT users.id, users.username, users.email, users.role_id, roles.role_name 
        FROM users 
        JOIN roles ON users.role_id = roles.id
    """)
    users = cur.fetchall()

    # Query to count total logins
    cur.execute("SELECT COUNT(*) as total_logins FROM login_logs")
    total_logins = cur.fetchone()['total_logins']

    # Query to count total users
    cur.execute("SELECT COUNT(*) as total_users FROM users")
    total_users = cur.fetchone()['total_users']

    # Query to count total admins
    cur.execute("SELECT COUNT(*) as total_admins FROM users WHERE role_id = (SELECT id FROM roles WHERE role_name = 'admin')")
    total_admins = cur.fetchone()['total_admins']

    # Query to count total votes cast
    cur.execute("SELECT COUNT(*) as total_votes FROM votes")
    total_votes = cur.fetchone()['total_votes']

    cur.close()
    
    return render_template('dashboard.html', users=users, user_role=current_user.role, 
                           total_logins=total_logins, total_users=total_users, 
                           total_admins=total_admins, total_votes=total_votes)

@app.route('/grant_admin/<int:user_id>', methods=['POST'])
@requires_role('admin')
def grant_admin(user_id):
    cur = mysql.connection.cursor()
    cur.execute("UPDATE users SET role_id = (SELECT id FROM roles WHERE role_name = 'admin') WHERE id = %s", (user_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': 'Admin privileges granted successfully'}), 200

@app.route('/remove_admin/<int:user_id>', methods=['POST'])
@requires_role('admin')
def remove_admin(user_id):
    cur = mysql.connection.cursor()
    cur.execute("UPDATE users SET role_id = (SELECT id FROM roles WHERE role_name = 'voter') WHERE id = %s", (user_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': 'Admin privileges revoked successfully'}), 200

@app.route('/delete_user/<int:user_id>', methods=['DELETE'])
@requires_role('admin')
def delete_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': 'User deleted successfully'}), 200

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
            login_user(User(id=user['id'], role=user['role_id']))  # Log in the user
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
    logout_user()  # Log out the user
    if user_id:
        log_activity(user_id, "User logged out")  # Log the logout activity
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

    # Fetch existing elections
    cur.execute("SELECT * FROM elections")
    elections = cur.fetchall()

    # Fetch existing positions
    cur.execute("SELECT * FROM positions")
    positions = cur.fetchall()

    selected_election_id = request.form.get('electionIdFilter')

    # Fetch candidates and their associated elections and positions, ordered by position and name
    if selected_election_id:
        cur.execute("""
            SELECT candidates.*, elections.name AS election_name, positions.name AS position_name
            FROM candidates 
            LEFT JOIN elections ON candidates.election_id = elections.id
            LEFT JOIN positions ON candidates.position_id = positions.id
            WHERE elections.id = %s
            ORDER BY positions.name, candidates.name
        """, (selected_election_id,))
    else:
        cur.execute("""
            SELECT candidates.*, elections.name AS election_name, positions.name AS position_name
            FROM candidates 
            LEFT JOIN elections ON candidates.election_id = elections.id
            LEFT JOIN positions ON candidates.position_id = positions.id
            ORDER BY positions.name, candidates.name
        """)

    candidates = cur.fetchall()
    cur.close()
    
    return render_template('admin.html', candidates=candidates, elections=elections, positions=positions, selected_election_id=selected_election_id)

# Edit Candidate Route
@app.route('/edit_candidate/<int:candidate_id>', methods=['PUT'])
@requires_role('admin')
def edit_candidate(candidate_id):
    data = request.get_json()
    candidate_name = data.get('candidateName')
    candidate_position = data.get('candidatePosition')
    election_id = data.get('electionId')
    image_url = data.get('imageUrl', None)  # Get the image URL if provided

    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            UPDATE candidates 
            SET name = %s, position = %s, election_id = %s, image_url = %s
            WHERE id = %s
        """, (candidate_name, candidate_position, election_id, image_url, candidate_id))
        mysql.connection.commit()
        cur.close()

        return jsonify({'message': 'Candidate updated successfully'}), 200
    except Exception as e:
        mysql.connection.rollback()
        print(f"Error updating candidate: {e}")
        return jsonify({'error': 'An error occurred while updating the candidate'}), 500

@app.route('/add_candidate', methods=['POST'])
@requires_role('admin')
def add_candidate():
    candidate_name = request.form['candidateName']
    candidate_position = request.form['candidatePosition']
    image_url = request.form.get('imageUrl', None)  # Get the image URL if provided
    election_id = request.form.get('electionId')
    existing_election_id = request.form.get('existingElectionId')

    try:
        cur = mysql.connection.cursor()

        # Determine the election ID to use
        if election_id:
            assigned_election_id = election_id
        elif existing_election_id:
            assigned_election_id = existing_election_id
        else:
            assigned_election_id = None

        # Insert the new candidate
        cur.execute("INSERT INTO candidates (name, position, election_id, image_url) VALUES (%s, %s, %s, %s)", 
                    (candidate_name, candidate_position, assigned_election_id, image_url))
        mysql.connection.commit()
        cur.close()

        flash('Candidate added successfully!', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'An error occurred: {e}', 'danger')

    return redirect(url_for('admin'))


@app.route('/delete_candidate/<int:candidate_id>', methods=['DELETE'])
@requires_role('admin')
def delete_candidate(candidate_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM candidates WHERE id = %s", (candidate_id,))
        mysql.connection.commit()
        cur.close()
        return jsonify({'message': 'Candidate deleted successfully'}), 200
    except Exception as e:
        mysql.connection.rollback()
        print(f"Error deleting candidate: {e}")
        return jsonify({'error': 'An error occurred while deleting the candidate'}), 500

# -------------------------------
# Run the Application
# -------------------------------
if __name__ == '__main__':
    app.run(debug=True)