
from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime
import os
from werkzeug.utils import secure_filename


#Configure upload folder
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  #Needed for flash messages
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # Limit upload size to 5MB

#Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
              filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


#DATABASE SETUP
def get_db_connection():
    """Create and return a database connection"""
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row  #Allows accessing columns by name
    return conn

def init_db():
    """Initialize database tables"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        #Job Postings Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS job_postings (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,          
                job_type TEXT NOT NULL,           
                salary TEXT,
                posted_date TEXT DEFAULT CURRENT_TIMESTAMP,
                deadline TEXT,
                approved BOOLEAN DEFAULT 1      
            )
        ''')

       
        standard_job_types = ['Full-time', 'Part-time', 'Internship', 'Contract', 'Temporary', 'Volunteer', 'Remote']
        standard_categories = ['Technology', 'Healthcare', 'Business', 'Education', 'Arts', 'Science', 'Government']

        
        #Feedback Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                message TEXT NOT NULL,
                email TEXT,
                submission_date TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        #Applications Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                student_name TEXT NOT NULL,
                student_email TEXT NOT NULL,
                resume_filename TEXT,
                cover_letter TEXT,
                submission_date TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES job_postings(id)
            )
        ''')

        #Recommendation Requests Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recommendation_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                student_email TEXT NOT NULL,
                teacher_name TEXT NOT NULL,
                teacher_email TEXT NOT NULL,
                deadline TEXT NOT NULL,
                purpose TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

#Initialize the database when app starts
init_db()

#========================
# ROUTES FOR HTML SCREENS
#========================

#Home Page
@app.route('/')
def home():
    """Render the home page"""
    return render_template('home.html')

#Job Listings Page
@app.route('/jobs')
def jobs():
    """Enhanced job listings with search and filters"""
    try:
        conn = get_db_connection()
        
        # Get filter parameters from URL
        search = request.args.get('search', '')
        job_type = request.args.get('type', 'all')
        category = request.args.get('category', 'all')
        
        # Base query
        query = '''
            SELECT * FROM job_postings 
            WHERE approved = 1
        '''
        params = []
        
        # Add filters
        if search:
            query += ' AND (title LIKE ? OR company LIKE ? OR description LIKE ?)'
            params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
        
        if job_type != 'all':
            query += ' AND job_type = ?'
            params.append(job_type)
            
        if category != 'all':
            query += ' AND category = ?'
            params.append(category)
        
        query += ' ORDER BY posted_date DESC'
        
        # Execute query
        jobs = conn.execute(query, params).fetchall()
        
        # Get distinct filters for dropdowns
        categories = conn.execute('SELECT DISTINCT category FROM job_postings').fetchall()
        job_types = conn.execute('SELECT DISTINCT job_type FROM job_postings').fetchall()
        
        return render_template(
            'jobs.html',
            jobs=jobs,
            categories=categories,
            job_types=job_types,
            current_search=search,
            current_type=job_type,
            current_category=category
        )
        
    except sqlite3.Error as e:
        flash('Error loading jobs', 'error')
        return render_template('jobs.html', jobs=[])
    finally:
        conn.close()


#Feedback Page
@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    """Handle feedback form"""
    if request.method == 'POST':
        try:
            conn = get_db_connection()
            conn.execute('''
                INSERT INTO feedback (type, message, email)
                VALUES (?, ?, ?)
            ''', (
                request.form['type'],
                request.form['message'],
                request.form.get('email', '')
            ))
            conn.commit()
            flash('Thank you for your feedback!', 'success')
            return redirect(url_for('feedback'))
        except sqlite3.Error as e:
            flash('Error submitting feedback', 'error')
            return render_template('feedback.html')
        finally:
            if conn:
                conn.close()
    
    return render_template('feedback.html')


@app.route('/applications')
def applications():
    """Show all submitted applications"""
    conn = get_db_connection()
    try:
        # Get all applications with job details
        apps = conn.execute('''
            SELECT applications.*, job_postings.title, job_postings.company
            FROM applications
            JOIN job_postings ON applications.job_id = job_postings.id
        ''').fetchall()
        return render_template('applications.html', applications=apps)
    finally:
        conn.close()

@app.route('/recommendations', methods=['GET', 'POST'])
def recommendations():
    conn = get_db_connection()
    
    if request.method == 'POST':
        # Get form data
        data = {
            'student_name': request.form['student_name'],
            'student_email': request.form['student_email'],
            'teacher_name': request.form['teacher_name'],
            'teacher_email': request.form['teacher_email'],
            'deadline': request.form['deadline'],
            'purpose': request.form['purpose']
        }
        
        # Insert into database
        conn.execute('''
            INSERT INTO recommendation_requests 
            (student_name, student_email, teacher_name, teacher_email, deadline, purpose)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', tuple(data.values()))
        
        conn.commit()
        flash('Recommendation request submitted!', 'success')
        return redirect(url_for('recommendations'))
    
    # GET request - show existing requests
    requests = conn.execute('SELECT * FROM recommendation_requests ORDER BY created_at DESC').fetchall()
    conn.close()
    
    return render_template('recommendations.html', requests=requests)


if __name__ == '__main__':
        # Wipe and recreate database if corrupted
    # import os
    # if os.path.exists('database.db'):
    #     os.remove('database.db')
    
    # Initialize fresh database
    init_db()
    # print("✅ Database successfully reset!")
    app.run(debug=True)
