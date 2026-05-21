from flask import Flask, render_template
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import os
import cv2
import numpy as np
import random
import string
import base64
from functools import wraps
from PIL import Image, ImageDraw, ImageFont
import io

app = Flask(__name__)
CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:5500", "*"])

# Config
app.config['SECRET_KEY'] = 'helmet_detection_secret_2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///helmet_detection.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DETECTED_FOLDER'] = 'detected'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DETECTED_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# ─── Models ─────────────────────────────────────────────────────────────────

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    vehicle_number = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Challan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    challan_number = db.Column(db.String(20), unique=True, nullable=False)
    vehicle_number = db.Column(db.String(20), nullable=False)
    violation = db.Column(db.String(200), default="Not wearing helmet")
    location = db.Column(db.String(200), nullable=True)
    fine_amount = db.Column(db.Float, default=500.0)
    status = db.Column(db.String(20), default="Unpaid")  # Unpaid / Paid
    detected_image = db.Column(db.Text, nullable=True)   # base64 image
    detected_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    camera_id = db.Column(db.String(50), nullable=True)
    confidence = db.Column(db.Float, nullable=True)


# ─── Helpers ────────────────────────────────────────────────────────────────

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'Token missing'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'error': 'Invalid token'}), 401
        except Exception as e:
            return jsonify({'error': 'Invalid token', 'details': str(e)}), 401
        return f(current_user, *args, **kwargs)
    return decorated


def generate_challan_number():
    return 'CH' + datetime.datetime.now().strftime('%Y%m%d') + ''.join(
        random.choices(string.digits, k=6))


def simulate_detection(image_data=None):
    """
    Simulates YOLO-based helmet detection.
    In production, replace with actual YOLOv8 model inference.
    Returns: dict with detections
    """
    # Simulate detection result
    detected = random.choice([True, True, True, False])  # 75% detection rate
    confidence = round(random.uniform(0.82, 0.99), 2)
    return {
        'helmet_detected': not detected,
        'no_helmet_detected': detected,
        'confidence': confidence,
        'bounding_boxes': [
            {'x': 120, 'y': 80, 'w': 160, 'h': 140, 'label': 'No Helmet', 'conf': confidence}
        ] if detected else []
    }


def draw_detection_on_image(image_b64, vehicle_number, confidence, location):
    """Draw bounding boxes and challan info on the detected image."""
    try:
        if image_b64:
            img_data = base64.b64decode(image_b64.split(',')[-1])
            img = Image.open(io.BytesIO(img_data)).convert('RGB')
        else:
            # Create a synthetic road scene image
            img = Image.new('RGB', (640, 480), color=(80, 80, 80))
            draw = ImageDraw.Draw(img)
            # Draw road
            draw.rectangle([0, 280, 640, 480], fill=(60, 60, 60))
            draw.rectangle([290, 0, 350, 480], fill=(200, 180, 0), outline=None)
            # Draw bike silhouette
            draw.ellipse([180, 280, 260, 360], fill=(40, 40, 40))
            draw.ellipse([380, 280, 460, 360], fill=(40, 40, 40))
            draw.rectangle([200, 220, 440, 310], fill=(30, 30, 80))
            # Draw person (no helmet - red head)
            draw.ellipse([295, 150, 345, 200], fill=(255, 60, 60), outline=(255, 0, 0), width=3)
            draw.rectangle([295, 195, 345, 280], fill=(20, 60, 150))

        draw = ImageDraw.Draw(img)

        # Red bounding box around head (no helmet zone)
        draw.rectangle([280, 140, 360, 210], outline=(255, 0, 0), width=4)
        draw.text((285, 120), f"NO HELMET {confidence:.0%}", fill=(255, 0, 0))

        # Info bar at bottom
        draw.rectangle([0, img.height - 80, img.width, img.height], fill=(0, 0, 0, 200))
        draw.text((10, img.height - 75), f"Vehicle: {vehicle_number}", fill=(255, 255, 0))
        draw.text((10, img.height - 55), f"Location: {location}", fill=(255, 255, 255))
        draw.text((10, img.height - 35), f"Confidence: {confidence:.1%} | CHALLAN ISSUED", fill=(255, 80, 80))

        # Watermark
        draw.text((img.width - 200, 10), "TRAFFIC ENFORCEMENT AI", fill=(255, 255, 0))

        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=85)
        return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        print(f"Image processing error: {e}")
        return None


# ─── Auth Routes ─────────────────────────────────────────────────────────────

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not all(k in data for k in ['name', 'email', 'password']):
        return jsonify({'error': 'Missing required fields'}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 409

    user = User(
        name=data['name'],
        email=data['email'],
        vehicle_number=data.get('vehicle_number', '').upper()
    )
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': 'Registered successfully', 'user_id': user.id}), 201


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data.get('email')).first()
    if not user or not user.check_password(data.get('password', '')):
        return jsonify({'error': 'Invalid credentials'}), 401

    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm='HS256')

    return jsonify({
        'token': token,
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'vehicle_number': user.vehicle_number
        }
    })


@app.route('/api/me', methods=['GET'])
@token_required
def get_me(current_user):
    return jsonify({
        'id': current_user.id,
        'name': current_user.name,
        'email': current_user.email,
        'vehicle_number': current_user.vehicle_number
    })


# ─── Challan Routes ──────────────────────────────────────────────────────────

@app.route('/api/challans/check', methods=['GET'])
def check_challan_public():
    """Public route: check challan by vehicle number"""
    vehicle_number = request.args.get('vehicle_number', '').upper().strip()
    if not vehicle_number:
        return jsonify({'error': 'Vehicle number required'}), 400

    challans = Challan.query.filter_by(vehicle_number=vehicle_number).order_by(
        Challan.detected_at.desc()).all()

    return jsonify({
        'vehicle_number': vehicle_number,
        'total_challans': len(challans),
        'total_fine': sum(c.fine_amount for c in challans if c.status == 'Unpaid'),
        'challans': [{
            'challan_number': c.challan_number,
            'violation': c.violation,
            'location': c.location,
            'fine_amount': c.fine_amount,
            'status': c.status,
            'detected_at': c.detected_at.isoformat(),
            'detected_image': c.detected_image,
            'confidence': c.confidence
        } for c in challans]
    })


@app.route('/api/challans', methods=['GET'])
@token_required
def get_my_challans(current_user):
    vehicle_number = current_user.vehicle_number
    if not vehicle_number:
        return jsonify({'challans': [], 'message': 'No vehicle registered'})

    challans = Challan.query.filter_by(vehicle_number=vehicle_number.upper()).order_by(
        Challan.detected_at.desc()).all()

    return jsonify({
        'vehicle_number': vehicle_number,
        'total_challans': len(challans),
        'challans': [{
            'id': c.id,
            'challan_number': c.challan_number,
            'violation': c.violation,
            'location': c.location,
            'fine_amount': c.fine_amount,
            'status': c.status,
            'detected_at': c.detected_at.isoformat(),
            'detected_image': c.detected_image,
            'confidence': c.confidence,
            'camera_id': c.camera_id
        } for c in challans]
    })


@app.route('/api/challans/<int:challan_id>/pay', methods=['POST'])
@token_required
def pay_challan(current_user, challan_id):
    challan = Challan.query.get_or_404(challan_id)
    if challan.vehicle_number != current_user.vehicle_number:
        return jsonify({'error': 'Unauthorized'}), 403
    challan.status = 'Paid'
    db.session.commit()
    return jsonify({'message': 'Challan paid successfully'})


# ─── Detection Route ─────────────────────────────────────────────────────────

@app.route('/api/detect', methods=['POST'])
def detect_helmet():
    """
    Receives image/video frame and runs helmet detection.
    In production, integrate YOLOv8 model here.
    """
    data = request.get_json()
    image_b64 = data.get('image')
    vehicle_number = data.get('vehicle_number', '').upper()
    camera_id = data.get('camera_id', 'CAM-001')
    location = data.get('location', 'MG Road, Bangalore')

    if not vehicle_number:
        return jsonify({'error': 'Vehicle number required'}), 400

    # Run detection (simulated - replace with YOLOv8 in production)
    result = simulate_detection(image_b64)

    response = {
        'vehicle_number': vehicle_number,
        'helmet_detected': result['helmet_detected'],
        'no_helmet_detected': result['no_helmet_detected'],
        'confidence': result['confidence'],
        'challan_issued': False,
        'challan': None
    }

    if result['no_helmet_detected']:
        # Draw bounding box on image
        annotated_image = draw_detection_on_image(
            image_b64, vehicle_number, result['confidence'], location)

        # Create challan
        challan = Challan(
            challan_number=generate_challan_number(),
            vehicle_number=vehicle_number,
            violation="Not wearing helmet while riding",
            location=location,
            fine_amount=500.0,
            status='Unpaid',
            detected_image=annotated_image,
            camera_id=camera_id,
            confidence=result['confidence']
        )
        db.session.add(challan)
        db.session.commit()

        response['challan_issued'] = True
        response['challan'] = {
            'challan_number': challan.challan_number,
            'fine_amount': challan.fine_amount,
            'detected_image': annotated_image
        }

    return jsonify(response)


# ─── Admin / Stats ───────────────────────────────────────────────────────────

@app.route('/api/stats', methods=['GET'])
def get_stats():
    total = Challan.query.count()
    unpaid = Challan.query.filter_by(status='Unpaid').count()
    total_fine = db.session.query(db.func.sum(Challan.fine_amount)).filter_by(status='Unpaid').scalar() or 0
    return jsonify({
        'total_challans': total,
        'unpaid_challans': unpaid,
        'total_fine_pending': total_fine
    })


# ─── Demo Data Seeder ────────────────────────────────────────────────────────

@app.route('/api/seed', methods=['POST'])
def seed_demo_data():
    """Seed demo challans for testing."""
    vehicles = ['MH12AB1234', 'KA03CD5678', 'DL09EF9012', 'TN07GH3456', 'MH12AB1234']
    locations = [
        'FC Road, Pune', 'MG Road, Bangalore', 'Connaught Place, Delhi',
        'Anna Salai, Chennai', 'Bandra-Worli Sea Link, Mumbai'
    ]
    cameras = ['CAM-001', 'CAM-002', 'CAM-003', 'CAM-004']

    for i in range(10):
        veh = random.choice(vehicles)
        loc = random.choice(locations)
        conf = round(random.uniform(0.82, 0.99), 2)
        img = draw_detection_on_image(None, veh, conf, loc)
        challan = Challan(
            challan_number=generate_challan_number() + str(i),
            vehicle_number=veh,
            violation="Not wearing helmet while riding",
            location=loc,
            fine_amount=500.0,
            status=random.choice(['Unpaid', 'Unpaid', 'Paid']),
            detected_image=img,
            camera_id=random.choice(cameras),
            confidence=conf,
            detected_at=datetime.datetime.utcnow() - datetime.timedelta(hours=random.randint(1, 72))
        )
        db.session.add(challan)

    db.session.commit()
    return jsonify({'message': '10 demo challans created'})


# ─── Run ─────────────────────────────────────────────────────────────────────

with app.app_context():
    db.create_all()

    # Seed demo data for MH12AB1234
    if Challan.query.filter_by(vehicle_number='MH12AB1234').count() == 0:
        demo_challans = [
            Challan(
                challan_number='CH20241201001',
                vehicle_number='MH12AB1234',
                violation='No Helmet Detected',
                location='FC Road, Pune',
                fine_amount=500.0,
                status='Unpaid',
                confidence=0.94,
                detected_at=datetime.datetime.utcnow() - datetime.timedelta(hours=1)
            ),
            Challan(
                challan_number='CH20241130002',
                vehicle_number='MH12AB1234',
                violation='No Helmet Detected',
                location='MG Road, Bangalore',
                fine_amount=500.0,
                status='Paid',
                confidence=0.88,
                detected_at=datetime.datetime.utcnow() - datetime.timedelta(days=1)
            ),
            Challan(
                challan_number='CH20241129003',
                vehicle_number='MH12AB1234',
                violation='No Helmet Detected',
                location='Bandra, Mumbai',
                fine_amount=500.0,
                status='Unpaid',
                confidence=0.96,
                detected_at=datetime.datetime.utcnow() - datetime.timedelta(days=2)
            )
        ]
        for challan in demo_challans:
            db.session.add(challan)
        db.session.commit()
        print("Demo challans seeded for MH12AB1234")

if __name__ == '__main__':
    app.run(debug=True, port=5000)
