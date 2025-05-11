from flask import Flask, render_template, request, redirect, session, url_for, jsonify, flash
from flask_pymongo import PyMongo
from bson import ObjectId
from werkzeug.utils import secure_filename
import os
import datetime
import google.generativeai as genai
import markdown
import re
from datetime import datetime

genai.configure(api_key="AIzaSyBUQ2JFGebBIEnOqwt2dA5nUc2nsDSA6Cw")

app = Flask(__name__)
app.secret_key = "supersecretkey"

# MongoDB connection
app.config["MONGO_URI"] = "mongodb://localhost:27017/travelCompanionDB"
mongo = PyMongo(app)

# Upload folder
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Dummy SMS function
def send_sms(phone, message):
    print(f"Sending SMS to {phone}: {message}")

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
            "emergency": request.form['emergency'],
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

@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        return render_template('dashboard.html', user_name=session['user_name'])
    else:
        return redirect('/login')

@app.route('/plan')
def plan():
    if 'user_id' in session:
        return render_template("plan_trip.html")
    return redirect('/login')

@app.route('/preferences')
def preferences():
    if 'user_id' in session:
        return render_template("travel_preferences.html")
    return redirect('/login')

def create_prompt(destination, start_date, end_date, budget, travel_style):
    return f"""
I am planning a trip to {destination} from {start_date} to {end_date}.
My total budget is {budget} INR.
My travel style is {travel_style}.
This trip is for a female traveler, so please keep safety, comfort, and suitability in mind when suggesting activities and locations.

Please create a detailed day-wise itinerary that includes:
- Recommended places to visit each day
- Local food suggestions based on my travel style
- Approximate expenses per day
- Tips or local experiences that match my travel style
- Any safety recommendations or precautions specifically for female travelers

Ensure that the itinerary fits the budget and is realistic for an Indian female traveler.
"""

@app.route('/generate')
def generate_itinerary():
    destination = request.args.get('destination', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    budget = request.args.get('budget', '')
    styles = request.args.getlist('styles')
    travel_style = ', '.join(styles)

    # Generate prompt
    prompt = create_prompt(destination, start_date, end_date, budget, travel_style)

    # Call Gemini
    model = genai.GenerativeModel('models/gemini-2.0-flash')
    response = model.generate_content(prompt)
    raw_text = response.text

    # ✅ Split into blocks at each **Day X:** line
    blocks = re.split(r"\*\*(Day\s+\d+:.*?)\*\*", raw_text)

    # Group blocks like: [Day Title, Content]
    daywise_blocks = []
    for i in range(1, len(blocks), 2):
        title = blocks[i]
        content = blocks[i + 1] if i + 1 < len(blocks) else ""
        html_content = markdown.markdown(content)
        daywise_blocks.append({"title": title, "content": html_content})

    # ✅ Send everything to template
    return render_template(
        "itinerary_result.html",
        blocks=daywise_blocks,
        destination=destination,
        start_date=start_date,
        end_date=end_date,
        budget=budget,
        styles=styles
    )

    
@app.route('/lock-itinerary', methods=['POST'])
def lock_itinerary():
    if 'user_id' not in session:
        return redirect('/login')  # Redirect if not logged in

    locked_data = {
        'user_id': ObjectId(session['user_id']),
        'destination': request.form['destination'],
        'start_date': request.form['start_date'],
        'end_date': request.form['end_date'],
        'budget': request.form['budget'],
        'styles': request.form.getlist('styles'),
        'status': 'confirmed'
    }

    mongo.db.locked_itineraries.insert_one(locked_data)

    return render_template("lock_confirmation.html", destination=locked_data['destination'])



# @app.route('/safety')
# def safety():
#     if 'user_id' in session:
#         return render_template('safety.html')
#     else:
#         return redirect('/login')

# @app.route('/sos', methods=['POST'])
# def activate_sos():
#     if 'user_id' in session:
#         user = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
#         emergency_number = user.get('emergency', "")
#         location = request.form.get('location')

#         if emergency_number:
#             send_sms(emergency_number, f"🚨 SOS Alert from {user['name']}! Location: {location}")
#             mongo.db.sos_alerts.insert_one({
#                 'user_id': user['_id'],
#                 'name': user['name'],
#                 'location': location,
#                 'timestamp': datetime.datetime.now()
#             })
#             flash("🚨 SOS alert sent successfully.")
#         else:
#             flash("❌ No emergency contact found in your profile.")

#         return redirect('/safety')
#     flash("❌ You must be logged in to send an SOS.")
#     return redirect('/login')

@app.route('/companions/discover')
def show_discover_companions():
    if 'user_id' not in session:
        return redirect('/login')

    current_user_id = str(session['user_id'])
    user_object_id = ObjectId(current_user_id)

    current_itinerary = mongo.db.locked_itineraries.find_one({"user_id": user_object_id})
    if not current_itinerary:
        return render_template("discover_companions.html", companions=[], matches=[])

    companions = []
    matches = []

    listings = mongo.db.locked_itineraries.find({"status": "confirmed"})
    for entry in listings:
        if entry['user_id'] == user_object_id:
            continue

        user_data = mongo.db.users.find_one({"_id": entry['user_id']})
        if not user_data:
            continue

        card = {
            "user_id": str(entry['user_id']),
            "name": user_data.get("name", "Unknown"),
            "profile_pic": user_data.get("profile_pic", "default.jpg"),
            "bio": user_data.get("bio", ""),
            "destination": entry.get("destination", ""),
            "start_date": entry.get("start_date", ""),
            "end_date": entry.get("end_date", ""),
            "styles": entry.get("styles", []),
            "budget": entry.get("budget", "")
        }

        # Match check: Destination & overlapping dates
        entry_start = datetime.strptime(entry['start_date'], "%Y-%m-%d")
        entry_end = datetime.strptime(entry['end_date'], "%Y-%m-%d")
        current_start = datetime.strptime(current_itinerary['start_date'], "%Y-%m-%d")
        current_end = datetime.strptime(current_itinerary['end_date'], "%Y-%m-%d")

        if entry['destination'].lower() == current_itinerary['destination'].lower() and (
            entry_start <= current_end and entry_end >= current_start):
            matches.append(card)
        else:
            companions.append(card)

    return render_template("discover_companions.html", companions=companions, matches=matches)


@app.route('/send_match_request', methods=['POST'])
def send_match_request():
    if 'user_id' not in session:
        return redirect('/login')

    companion_name = request.form.get("companion_id")
    # Find that user’s ObjectId
    companion_user = mongo.db.users.find_one({"name": companion_name})

    if not companion_user:
        return redirect('/companions/discover')

    # Check if already sent
    existing = mongo.db.match_requests.find_one({
        "from_user": session['user_id'],
        "to_user": str(companion_user['_id'])
    })
    if existing:
        return redirect('/companions/discover')

    mongo.db.match_requests.insert_one({
        "from_user": session['user_id'],
        "to_user": str(companion_user['_id']),
        "timestamp": datetime.datetime.utcnow(),
        "status": "pending"
    })
    return redirect("/companions/discover")


@app.route('/companions/matches')
def show_matches():
    if 'user_id' not in session:
        return redirect('/login')

    my_id = session['user_id']
    requests = mongo.db.match_requests.find({"from_user": my_id})
    matches = []

    for req in requests:
        to_user_id = req['to_user']
        itinerary = mongo.db.locked_itineraries.find_one({"user_id": ObjectId(to_user_id)})
        profile = mongo.db.users.find_one({"_id": ObjectId(to_user_id)})

        if profile and itinerary:
            matches.append({
                "user_id": str(profile['_id']),  # ✅ Required for /chat/<id>
                "name": profile['name'],
                "profile_pic": profile.get("profile_pic", "default.jpg"),
                "bio": profile.get("bio", ""),
                "destination": itinerary["destination"],
                "start_date": itinerary["start_date"],
                "end_date": itinerary["end_date"],
                "styles": itinerary["styles"],
                "budget": itinerary["budget"]
            })

    return render_template("your_matches.html", matches=matches)


@app.route('/chat/<receiver_id>', methods=['GET', 'POST'])
def chat(receiver_id):
    if 'user_id' not in session:
        return redirect('/login')

    from_user_id = ObjectId(session['user_id'])

    try:
        to_user_id = ObjectId(receiver_id)
    except:
        return "Invalid user ID"

    if request.method == 'POST':
        message = request.form.get('message')
        if message:
            mongo.db.messages.insert_one({
                'from': from_user_id,
                'to': to_user_id,
                'message': message,
                'timestamp': datetime.utcnow()
            })
            return redirect(f'/chat/{receiver_id}')

    messages = list(mongo.db.messages.find({
        '$or': [
            {'from': from_user_id, 'to': to_user_id},
            {'from': to_user_id, 'to': from_user_id}
        ]
    }).sort('timestamp'))

    companion = mongo.db.users.find_one({'_id': to_user_id})

    return render_template(
        "chat_room.html",
        companion=companion,
        messages=messages,
        receiver_id=receiver_id
    )

@app.route('/send_message', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return redirect('/login')

    sender_id = session['user_id']
    receiver_id = request.form.get('receiver_id')
    message = request.form.get('message')

    if message and receiver_id:
        mongo.db.messages.insert_one({
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "message": message,
            "timestamp": datetime.datetime.utcnow()
        })

    return redirect(f'/chat/{receiver_id}')


if __name__ == '__main__':
    app.run(debug=True)
# venv/Scripts/Activate