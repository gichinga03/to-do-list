from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from  bson.objectid import ObjectId
from apscheduler.jobstores.base import JobLookupError





# Initializing the Flask application
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

uri = "mongodb+srv://gichinga03:Gichinga2003@cluster0.kialttn.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(uri, server_api=ServerApi('1'))

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

# MongoDB connection
client = MongoClient(uri)
db = client['to_do_list']
users_registration = db.registration
tasks_collection = db.tasks

# Scheduler setup
scheduler = BackgroundScheduler()
scheduler.start()

def add_task_to_database_and_schedule(user_id, task, due_date):
    task_doc = {
        'user_id': user_id,
        'task': task,
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
        args=[task]
    )

# Dummy function to print task (replace with actual task handling logic)
def print_task(task):
    print(f"Executing task: {task}")

# Routes
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/edit_task/<task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    return render_template('edit_task.html')



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
            'password': password
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
            return redirect(url_for('welcome'))
        else:
            flash('Invalid username or password')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/welcome')
def welcome():
    if 'username' in session:
        user_id = session['user_id']
        user_tasks = list(tasks_collection.find({'user_id': user_id}))
        return render_template('welcome.html', tasks=user_tasks)
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
        due_date = datetime.strptime(request.form['due_date'], '%Y-%m-%dT%H:%M')
        add_task_to_database_and_schedule(user_id, task, due_date)
        flash('Task added and scheduled successfully!', 'success')
        return redirect(url_for('welcome'))

    return render_template('tasks.html')


def update_task_in_database_and_scheduler(task_id, user_id, new_task, new_due_date):
    # Update the task in the database
    tasks_collection.update_one(
        {'_id': ObjectId(task_id)},
        {'$set': {'task': new_task, 'due_date': new_due_date}}
    )
    # Remove the old job from the scheduler
    scheduler.remove_job(str(task_id))



@app.route('/delete/<task_id>', methods=['POST'])
def delete_task(task_id):
    user_id = session.get('user_id')  # Use get to avoid KeyError if 'user_id' is not in session
    try:
        result = tasks_collection.delete_one({'_id': ObjectId(task_id)})
        scheduler.remove_job(task_id)
        flash('Task successfully deleted!', 'success')
    except JobLookupError:
        flash('Error: Task not found in scheduler', 'error')
    except Exception as e:
        flash(f'Error deleting task: {str(e)}', 'error')

    return redirect(url_for('welcome'))






if __name__ == '__main__':
    app.run(debug=True)
