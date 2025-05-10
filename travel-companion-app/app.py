
from flask import Flask, render_template, request, redirect, session, url_for
from flask_pymongo import PyMongo
from bson import ObjectId
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

# MongoDB connection
app.config["MONGO_URI"] = "mongodb://localhost:27017/travelCompanionDB"
mongo = PyMongo(app)

# File upload config
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def home():
    return render_template("home.html")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = {
            "name": request.form['name'],
            "email": request.form['email'],
            "password": request.form['password'],
            "style": "",
            "emergency": "",
            "bio": "",
            "profile_pic": "default.jpg"
        }
        result = mongo.db.users.insert_one(user)
        session['user_id'] = str(result.inserted_id)
        session['user_name'] = user['name']
        return redirect('/dashboard')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = mongo.db.users.find_one({'email': email})
        if user and user['password'] == password:
            session['user_id'] = str(user['_id'])
            session['user_name'] = user['name']
            return redirect('/dashboard')
        else:
            return render_template('login.html', error="Invalid email or password")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        return render_template('dashboard.html', user_name=session['user_name'])
    else:
        return redirect('/login')

@app.route('/plan')
def plan():
    if 'user_id' in session:
        return "<h2>Trip planner coming soon...</h2>"
    else:
        return redirect('/login')

@app.route('/sos')
def sos():
    if 'user_id' in session:
        return "<h2>SOS panel coming soon...</h2>"
    else:
        return redirect('/login')

@app.route('/companions')
def companions():
    if 'user_id' in session:
        return "<h2>Companion matcher coming soon...</h2>"
    else:
        return redirect('/login')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = ObjectId(session['user_id'])
    user = mongo.db.users.find_one({'_id': user_id})

    if request.method == 'POST':
        updated_data = {
            'name': request.form['name'],
            'style': request.form['style'],
            'emergency': request.form['emergency'],
            'bio': request.form['bio']
        }

        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename:
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                updated_data['profile_pic'] = filename

        mongo.db.users.update_one({'_id': user_id}, {'$set': updated_data})
        session['user_name'] = updated_data['name']
        return redirect('/profile')

    return render_template('profile.html', user=user)

if __name__ == '__main__':
    app.run(debug=True)
