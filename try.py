from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.base import JobLookupError
from bson.objectid import ObjectId
from datetime import datetime, timedelta

# Initializing the Flask application
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

uri = "mongodb+srv://gichinga03:Gichinga2003@cluster0.kialttn.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(uri)

# MongoDB connection
db = client['to_do_list']
users_registration = db.registration
tasks_collection = db.tasks

# Scheduler setup
scheduler = BackgroundScheduler()
scheduler.start()

def add_task_to_database_and_schedule(user_id, task, task_description, due_date):
    task_doc = {
        'user_id': user_id,
        'task': task,
        'task_description': task_description,
        'due_date': due_date,
        'created_at': datetime.now()
    }
    tasks_collection.insert_one(task_doc)

    # Schedule the task
    scheduler.add_job(
        id=str(task_doc['_id']),
        func=print_task,
        trigger='date',
        run_date=due_date,
        args=[task, task_description]
    )

# Dummy function to print task (replace with actual task handling logic)
def print_task(task, task_description):
    print(f"Task: {task}")
    print(f"Description: {task_description}")

# Routes
@app.route('/')
def index():
    return render_template('index.html')






# Create an admin user
admin_user = {
    'first_name': 'Admin',
    'second_name': 'User',
    'last_name': 'Admin',
    'date_birth': '2000-01-01',
    'email': 'admin@example.com',
    'phone_number': '1234567890',
    'username': 'admin',
    'password': generate_password_hash('admin_password'),
    'is_admin': True
}

# Insert the admin user into the database
users_registration.insert_one(admin_user)






@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name']
        second_name = request.form['second_name']
        last_name = request.form['last_name']
        date_birth = request.form['date_birth']
        email = request.form['email']
        phone_number = request.form['phone']
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        is_admin = 'is_admin' in request.form

        if users_registration.find_one({'username': username}):
            return "User already exists!"

        users_registration.insert_one({
            'first_name': first_name,
            'second_name': second_name,
            'last_name': last_name,
            'date_birth': date_birth,
            'email': email,
            'phone_number': phone_number,
            'username': username,
            'password': password,
            'is_admin': is_admin
        })
        return redirect(url_for('index'))

    return render_template('registration.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = users_registration.find_one({'username': username})

        if user and check_password_hash(user['password'], password):
            session['username'] = user['username']
            session['user_id'] = str(user['_id'])
            session['is_admin'] = user.get('is_admin', False)
            return redirect(url_for('welcome'))
        else:
            flash('Invalid username or password')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/welcome')
def welcome():
    if 'username' in session:
        if session.get('is_admin'):
            return redirect(url_for('admin_dashboard'))
        else:
            user_id = session['user_id']
            tasks = list(tasks_collection.find({'user_id': user_id}))

            now = datetime.now()
            one_hour_from_now = now + timedelta(hours=1)

            classified_tasks = {
                'done': [],
                'urgent': [],
                'not_done': []
            }

            for task in tasks:
                due_date = task['due_date']
                if due_date < now:
                    classified_tasks['done'].append(task)
                elif due_date <= one_hour_from_now:
                    classified_tasks['urgent'].append(task)
                else:
                    classified_tasks['not_done'].append(task)

            # Sort tasks within each category by due date
            for category in classified_tasks:
                classified_tasks[category].sort(key=lambda x: x['due_date'])

            return render_template('welcome.html', tasks=classified_tasks)
    else:
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/tasks', methods=['GET', 'POST'])
def tasks():
    if 'user_id' not in session:
        flash('Please log in first', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    if request.method == 'POST':
        task = request.form['task']
        task_description = request.form['task_description']
        due_date = datetime.strptime(request.form['due_date'], '%Y-%m-%dT%H:%M')
        add_task_to_database_and_schedule(user_id, task, task_description, due_date)
        flash('Task added and scheduled successfully!', 'success')
        return redirect(url_for('welcome'))

    return render_template('tasks.html')

def update_task_in_database_and_scheduler(task_id, user_id, new_task, new_task_description, new_due_date):
    # Update the task in the database
    tasks_collection.update_one(
        {'_id': ObjectId(task_id)},
        {'$set': {
            'task': new_task, 
            'task_description': new_task_description, 
            'due_date': new_due_date
        }}
    )
    # Remove the old job from the scheduler, if it exists
    try:
        scheduler.remove_job(str(task_id))
    except JobLookupError:
        pass  # Handle gracefully if the job does not exist

    # Re-schedule the task with new details
    scheduler.add_job(
        id=str(task_id),
        func=print_task,
        trigger='date',
        run_date=new_due_date,
        args=[new_task, new_task_description]
    )

@app.route('/delete/<task_id>', methods=['POST'])
def delete_task(task_id):
    user_id = session.get('user_id')
    try:
        result = tasks_collection.delete_one({'_id': ObjectId(task_id)})
        scheduler.remove_job(task_id)
        flash('Task successfully deleted!', 'success')
    except JobLookupError:
        flash('Error: Task not found in scheduler', 'error')
    except Exception as e:
        flash(f'Error deleting task: {str(e)}', 'error')

    return redirect(url_for('welcome'))

@app.route('/edit_task', methods=['POST'])
def edit_task():
    if 'user_id' not in session:
        flash('Please log in to edit tasks', 'error')
        return redirect(url_for('login'))

    task_id = request.form.get('task_id')
    task = request.form['task']
    task_description = request.form['task_description']
    due_date_str = request.form['due_date']
    try:
        due_date = datetime.fromisoformat(due_date_str)
        if due_date <= datetime.now():
            flash('Due date must be in the future', 'error')
            return redirect(url_for('tasks'))
    except ValueError:
        flash('Invalid date format', 'error')
        return redirect(url_for('tasks'))

    update_task_in_database_and_scheduler(task_id, session['user_id'], task, task_description, due_date)

    #flash('Task updated successfully', 'success')
    return redirect(url_for('welcome'))



"""

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'username' in session and session.get('is_admin'):
        users = users_registration.find()
        all_tasks = []

        for user in users:
            user_tasks = list(tasks_collection.find({'user_id': str(user['_id'])}))
            for task in user_tasks:
                task['username'] = user['username']
            all_tasks.extend(user_tasks)

        now = datetime.now()
        one_hour_from_now = now + timedelta(hours=1)

        classified_tasks = {
            'done': [],
            'urgent': [],
            'not_done': []
        }

        for task in all_tasks:
            due_date = task['due_date']
            if due_date < now:
                classified_tasks['done'].append(task)
            elif due_date <= one_hour_from_now:
                classified_tasks['urgent'].append(task)
            else:
                classified_tasks['not_done'].append(task)

        # Sort tasks within each category by due date
        for category in classified_tasks:
            classified_tasks[category].sort(key=lambda x: x['due_date'])

        return render_template('admin.html', tasks=classified_tasks)
    else:
        return redirect(url_for('login'))

"""


@app.route('/admin_dashboard')
def admin_dashboard():
    if 'username' in session and session.get('is_admin'):
        users = list(users_registration.find())

        return render_template('admin.html', users=users)
    else:
        return redirect(url_for('login'))
  


@app.route('/user_details/<user_id>')
def view_user_details(user_id):
    if 'username' in session and session.get('is_admin'):
        user = users_registration.find_one({'_id': ObjectId(user_id)})
        tasks = list(tasks_collection.find({'user_id': user_id}))

        return render_template('user_details.html', user=user, tasks=tasks)
    else:
        return redirect(url_for('login'))



if __name__ == '__main__':
    app.run(debug=True)
