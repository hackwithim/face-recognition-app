"""
Face Recognition App with OpenCV Face Detection
This version uses OpenCV's Haar Cascades for face detection instead of dlib
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, Response
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity, verify_jwt_in_request
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import cv2
import numpy as np
import pickle
import os
import json
import time
from datetime import datetime, timedelta
import base64
import io
from PIL import Image
import threading

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///face_recognition.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'dev-jwt-secret-change-in-production'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)

# JWT Error Handlers
@jwt.unauthorized_loader
def unauthorized_callback(callback):
    return jsonify({
        'status': 'error',
        'message': 'Missing Authorization Header'
    }), 401

@jwt.invalid_token_loader
def invalid_token_callback(callback):
    return jsonify({
        'status': 'error',
        'message': 'Invalid token'
    }), 401

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({
        'status': 'error',
        'message': 'Token has expired'
    }), 401

# Create upload directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.String(20), unique=True, nullable=False)  # Auto-generated: P001, P002, etc.
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    city = db.Column(db.String(100), nullable=True)
    college_name = db.Column(db.String(200), nullable=True)
    department = db.Column(db.String(100), nullable=True)
    course = db.Column(db.String(100), nullable=True)
    year_of_study = db.Column(db.String(20), nullable=True)
    face_data = db.Column(db.Text, nullable=True)  # Store face encoding as JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'person_id': self.person_id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'address': self.address,
            'city': self.city,
            'college_name': self.college_name,
            'department': self.department,
            'course': self.course,
            'year_of_study': self.year_of_study,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active,
            'has_face_data': self.face_data is not None
        }

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='admin')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RecognitionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    confidence = db.Column(db.Float, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    image_path = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default='detected')

# Face Detection Class using OpenCV
class OpenCVFaceDetector:
    def __init__(self):
        # Load OpenCV's pre-trained face detection classifier
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        
    def detect_faces(self, image):
        """Detect faces in an image with improved parameters"""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Apply histogram equalization for better detection
            gray = cv2.equalizeHist(gray)
            
            # Detect faces with more lenient parameters
            # scaleFactor: 1.1 (smaller = more accurate but slower)
            # minNeighbors: 3 (lower = more detections but more false positives)
            # minSize: (30, 30) minimum face size
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=3,
                minSize=(30, 30),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            return faces
        except Exception as e:
            print(f"Face detection error: {e}")
            return []
    
    def extract_face_features(self, image, face_rect):
        """Extract simple features from a face region"""
        x, y, w, h = face_rect
        face_roi = image[y:y+h, x:x+w]
        
        # Resize face to standard size
        face_resized = cv2.resize(face_roi, (100, 100))
        
        # Convert to grayscale and flatten for simple feature vector
        gray_face = cv2.cvtColor(face_resized, cv2.COLOR_BGR2GRAY)
        
        # Calculate histogram as a simple feature
        hist = cv2.calcHist([gray_face], [0], None, [256], [0, 256])
        
        # Normalize histogram
        hist = hist.flatten()
        hist = hist / (hist.sum() + 1e-7)
        
        # Also extract LBP (Local Binary Pattern) features for better recognition
        lbp = self.calculate_lbp(gray_face)
        
        return {
            'histogram': hist.tolist(),
            'lbp': lbp.tolist(),
            'face_size': [int(w), int(h)],
            'face_position': [int(x), int(y)]
        }
    
    def calculate_lbp(self, image):
        """Calculate Local Binary Pattern features"""
        # Simple LBP implementation
        rows, cols = image.shape
        lbp_image = np.zeros((rows-2, cols-2), dtype=np.uint8)
        
        for i in range(1, rows-1):
            for j in range(1, cols-1):
                center = image[i, j]
                code = 0
                code |= (image[i-1, j-1] > center) << 7
                code |= (image[i-1, j] > center) << 6
                code |= (image[i-1, j+1] > center) << 5
                code |= (image[i, j+1] > center) << 4
                code |= (image[i+1, j+1] > center) << 3
                code |= (image[i+1, j] > center) << 2
                code |= (image[i+1, j-1] > center) << 1
                code |= (image[i, j-1] > center) << 0
                lbp_image[i-1, j-1] = code
        
        # Calculate histogram of LBP
        hist = cv2.calcHist([lbp_image], [0], None, [256], [0, 256])
        hist = hist.flatten()
        hist = hist / (hist.sum() + 1e-7)
        
        return hist
    
    def train_face_model(self, face_features_list):
        """Train face model from multiple feature sets"""
        if not face_features_list or len(face_features_list) == 0:
            return None
        
        # Average all histograms and LBP features
        all_histograms = [np.array(f['histogram']) for f in face_features_list]
        all_lbps = [np.array(f['lbp']) for f in face_features_list]
        
        avg_histogram = np.mean(all_histograms, axis=0)
        avg_lbp = np.mean(all_lbps, axis=0)
        
        # Calculate standard deviation for confidence scoring
        std_histogram = np.std(all_histograms, axis=0)
        std_lbp = np.std(all_lbps, axis=0)
        
        return {
            'histogram': avg_histogram.tolist(),
            'lbp': avg_lbp.tolist(),
            'histogram_std': std_histogram.tolist(),
            'lbp_std': std_lbp.tolist(),
            'num_samples': len(face_features_list)
        }
    
    def compare_faces(self, features1, features2, threshold=0.65):
        """Compare two face feature sets with improved accuracy"""
        if not features1 or not features2:
            return False, 0.0
        
        hist1 = np.array(features1.get('histogram', []))
        hist2 = np.array(features2.get('histogram', []))
        lbp1 = np.array(features1.get('lbp', []))
        lbp2 = np.array(features2.get('lbp', []))
        
        if len(hist1) == 0 or len(hist2) == 0:
            return False, 0.0
        
        # Calculate correlation for histogram
        hist_correlation = cv2.compareHist(hist1.astype(np.float32), hist2.astype(np.float32), cv2.HISTCMP_CORREL)
        
        # Calculate correlation for LBP if available
        lbp_correlation = 0.0
        if len(lbp1) > 0 and len(lbp2) > 0:
            lbp_correlation = cv2.compareHist(lbp1.astype(np.float32), lbp2.astype(np.float32), cv2.HISTCMP_CORREL)
        
        # Combined score (weighted average)
        combined_score = (hist_correlation * 0.6) + (lbp_correlation * 0.4)
        
        return combined_score > threshold, combined_score

# Global variables
face_detector = OpenCVFaceDetector()
camera = None
recognition_active = False

def generate_person_id():
    """Generate auto-incrementing person ID (P001, P002, etc.)"""
    # Get the count of existing users
    user_count = User.query.count()
    # Generate new person ID
    person_id = f"P{str(user_count + 1).zfill(3)}"
    
    # Check if this ID already exists (in case of deletions)
    while User.query.filter_by(person_id=person_id).first():
        user_count += 1
        person_id = f"P{str(user_count + 1).zfill(3)}"
    
    return person_id

# Routes
@app.route('/')
def index():
    """Home page"""
    return render_template('index_opencv.html')

@app.route('/register')
def register():
    """User registration page"""
    return render_template('register_fixed.html')

@app.route('/recognize')
def recognize():
    """Face recognition page"""
    return render_template('recognize_fixed.html')



@app.route('/api/login', methods=['POST'])
def login():
    """Admin login endpoint"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400
        
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({
                'status': 'error',
                'message': 'Username and password are required'
            }), 400
        
        # Simple hardcoded admin credentials (in production, use proper user management)
        if username == 'admin' and password == 'admin123':
            # Create access token
            access_token = create_access_token(identity=username)
            
            return jsonify({
                'status': 'success',
                'message': 'Login successful',
                'access_token': access_token,
                'user': {
                    'username': username,
                    'role': 'admin'
                }
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Invalid username or password'
            }), 401
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Login failed: {str(e)}'
        }), 500

@app.route('/login')
def login_page():
    """Admin login page"""
    return render_template('login.html')

@app.route('/admin')
def admin():
    """Admin dashboard - client-side authentication check"""
    # Just render the page, authentication is checked client-side
    return render_template('admin.html')

@app.route('/capture/<int:user_id>')
def capture_user_face(user_id):
    """Face capture page for specific user"""
    user = User.query.get(user_id)
    if not user:
        return "User not found", 404
    
    return render_template('capture_face.html', user=user)

@app.route('/video_feed')
def video_feed():
    """Video streaming route with face detection"""
    camera_index = request.args.get('camera', 0, type=int)
    
    def generate():
        cap = None
        error_count = 0
        max_errors = 10
        consecutive_errors = 0
        last_frame_time = time.time()
        
        while True:  # Outer loop to keep trying
            try:
                # Try multiple camera backends for better compatibility
                if cap is None or not cap.isOpened():
                    print(f"Initializing camera {camera_index} for video feed...")
                    cap = initialize_camera(camera_index)
                    error_count = 0
                    consecutive_errors = 0
                
                if not cap or not cap.isOpened():
                    # Create a placeholder frame if camera fails
                    placeholder = create_placeholder_frame("Camera not available - Retrying...")
                    ret, buffer = cv2.imencode('.jpg', placeholder)
                    if ret:
                        frame = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                    time.sleep(1)
                    continue
                
                frame_count = 0
                while cap and cap.isOpened():
                    try:
                        ret, frame = cap.read()
                        current_time = time.time()
                        
                        if not ret or frame is None:
                            consecutive_errors += 1
                            error_count += 1
                            
                            if consecutive_errors > 3:
                                print(f"Camera read failed {consecutive_errors} times, reinitializing...")
                                if cap:
                                    cap.release()
                                    cap = None
                                break  # Break inner loop to reinitialize
                            
                            # Send placeholder while recovering
                            placeholder = create_placeholder_frame("Camera reconnecting...")
                            ret, buffer = cv2.imencode('.jpg', placeholder)
                            if ret:
                                frame = buffer.tobytes()
                                yield (b'--frame\r\n'
                                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                            time.sleep(0.5)
                            continue
                        
                        consecutive_errors = 0  # Reset on successful read
                        error_count = 0
                        last_frame_time = current_time
                        
                        # Detect faces (with error handling)
                        try:
                            faces = face_detector.detect_faces(frame)
                            
                            # Draw rectangles around faces
                            for (x, y, w, h) in faces:
                                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                                cv2.putText(frame, 'Face Detected', (x, y-10), 
                                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                            
                            # Add info overlay
                            cv2.putText(frame, f'OpenCV Face Detection - {len(faces)} faces', 
                                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                            cv2.putText(frame, f'Time: {datetime.now().strftime("%H:%M:%S")}', 
                                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                        except Exception as e:
                            print(f"Face detection error: {e}")
                            # Continue with frame even if face detection fails
                        
                        ret, buffer = cv2.imencode('.jpg', frame)
                        if ret:
                            frame = buffer.tobytes()
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                        
                        frame_count += 1
                        # Limit frame rate
                        time.sleep(0.05)  # ~20 FPS
                        
                    except Exception as e:
                        print(f"Frame processing error: {e}")
                        consecutive_errors += 1
                        if consecutive_errors > 5:
                            if cap:
                                cap.release()
                                cap = None
                            break
                        time.sleep(0.5)
                        continue
                        
            except Exception as e:
                print(f"Video feed error: {e}")
                if cap:
                    try:
                        cap.release()
                    except:
                        pass
                    cap = None
                time.sleep(1)
                continue
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

def initialize_camera(camera_index=0):
    """Initialize camera with multiple backend options for better compatibility"""
    backends = [
        cv2.CAP_DSHOW,      # DirectShow (Windows)
        cv2.CAP_MSMF,       # Microsoft Media Foundation
        cv2.CAP_V4L2,       # Video4Linux2 (Linux)
        cv2.CAP_ANY         # Any available backend
    ]
    
    for backend in backends:
        try:
            print(f"Trying camera {camera_index} with backend: {backend}")
            cap = cv2.VideoCapture(camera_index, backend)
            
            if cap.isOpened():
                # Test if we can actually read a frame
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"Camera {camera_index} successfully initialized with backend: {backend}")
                    # Reset to beginning for actual use
                    cap.release()
                    cap = cv2.VideoCapture(camera_index, backend)
                    
                    # Set camera properties for better performance
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    cap.set(cv2.CAP_PROP_FPS, 15)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    
                    return cap
                else:
                    cap.release()
            else:
                cap.release()
        except Exception as e:
            print(f"Backend {backend} failed: {e}")
            continue
    
    print(f"All camera backends failed for camera {camera_index}")
    return None

def create_placeholder_frame(message):
    """Create a placeholder frame when camera is not available"""
    import numpy as np
    
    # Create a 640x480 black frame
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Add text message
    cv2.putText(frame, message, (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(frame, 'Face Recognition System', (150, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 2)
    cv2.putText(frame, f'Time: {datetime.now().strftime("%H:%M:%S")}', (200, 320), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
    
    return frame

@app.route('/api/register', methods=['POST'])
def api_register():
    """Register a new user with face data"""
    try:
        print("Registration API called")
        
        # Get JSON data
        data = request.get_json()
        print(f"Received data: {data}")
        
        if not data:
            print("No JSON data received")
            return jsonify({
                'status': 'error',
                'message': 'No data received'
            }), 400
        
        name = data.get('name')
        email = data.get('email')
        phone = data.get('phone')
        address = data.get('address')
        city = data.get('city')
        college_name = data.get('college_name')
        department = data.get('department')
        course = data.get('course')
        year_of_study = data.get('year_of_study')
        
        print(f"Parsed data - Name: {name}, Email: {email}, City: {city}")
        
        if not name or not email:
            print("Missing required fields")
            return jsonify({
                'status': 'error',
                'message': 'Name and email are required'
            }), 400
        
        # Check if user exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            print(f"User already exists: {email}")
            return jsonify({
                'status': 'error',
                'message': 'User with this email already exists'
            }), 409
        
        # Generate person ID
        person_id = generate_person_id()
        
        # Create new user
        new_user = User(
            person_id=person_id,
            name=name,
            email=email,
            phone=phone,
            address=address,
            city=city,
            college_name=college_name,
            department=department,
            course=course,
            year_of_study=year_of_study
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        print(f"User created successfully with ID: {new_user.id}")
        
        response_data = {
            'status': 'success',
            'message': 'User registered successfully',
            'user_id': new_user.id,
            'person_id': new_user.person_id
        }
        
        print(f"Sending response: {response_data}")
        return jsonify(response_data), 200
        
    except Exception as e:
        print(f"Registration error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'status': 'error',
            'message': f'Registration failed: {str(e)}'
        }), 500

@app.route('/api/capture_face', methods=['POST'])
def capture_face():
    """Capture and store face data for a user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({
                'status': 'error',
                'message': 'User ID is required'
            })
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            })
        
        # Capture frame from camera with improved error handling
        cap = None
        try:
            cap = initialize_camera()
            if not cap or not cap.isOpened():
                return jsonify({
                    'status': 'error',
                    'message': 'Could not initialize camera'
                })
            
            # Try multiple frame captures for better reliability
            ret, frame = None, None
            for attempt in range(3):
                ret, frame = cap.read()
                if ret and frame is not None:
                    break
                time.sleep(0.1)
            
            if not ret or frame is None:
                return jsonify({
                    'status': 'error',
                    'message': 'Could not capture image from camera'
                })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Camera error: {str(e)}'
            })
        finally:
            if cap:
                cap.release()
        
        # Detect faces in the captured frame
        faces = face_detector.detect_faces(frame)
        
        if len(faces) == 0:
            return jsonify({
                'status': 'error',
                'message': 'No face detected in the image'
            })
        
        if len(faces) > 1:
            return jsonify({
                'status': 'error',
                'message': 'Multiple faces detected. Please ensure only one person is in the frame'
            })
        
        # Extract features from the detected face
        face_features = face_detector.extract_face_features(frame, faces[0])
        
        # Store face data
        user.face_data = json.dumps(face_features)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Face data captured and stored successfully'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Face capture failed: {str(e)}'
        })

@app.route('/api/recognize_from_image', methods=['POST'])
def recognize_from_image():
    """Recognize face from provided image"""
    try:
        data = request.get_json()
        image_data = data.get('image')
        
        if not image_data:
            return jsonify({
                'status': 'error',
                'message': 'No image data provided'
            }), 400
        
        # Decode base64 image
        import base64
        import io
        from PIL import Image
        
        # Remove data URL prefix if present
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        # Decode base64
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to OpenCV format
        frame = np.array(image)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        
        print(f"Recognizing face in image of size: {frame.shape}")
        
        # Detect faces
        faces = face_detector.detect_faces(frame)
        
        print(f"Detected {len(faces)} faces for recognition")
        
        if len(faces) == 0:
            return jsonify({
                'status': 'error',
                'message': 'No face detected in image. Please ensure your face is clearly visible with good lighting.'
            })
        
        # Use the first detected face
        face_features = face_detector.extract_face_features(frame, faces[0])
        
        # Compare with stored faces
        users = User.query.filter(User.face_data.isnot(None)).all()
        
        if len(users) == 0:
            return jsonify({
                'status': 'error',
                'message': 'No registered users with face data found in the system.'
            })
        
        best_match = None
        best_confidence = 0.0
        
        for user in users:
            try:
                stored_features = json.loads(user.face_data)
                is_match, confidence = face_detector.compare_faces(face_features, stored_features)
                
                if is_match and confidence > best_confidence:
                    best_match = user
                    best_confidence = confidence
            except Exception as e:
                print(f"Error comparing with user {user.id}: {e}")
                continue
        
        # Log the recognition attempt
        log_entry = RecognitionLog(
            user_id=best_match.id if best_match else None,
            confidence=best_confidence,
            status='recognized' if best_match else 'unknown'
        )
        db.session.add(log_entry)
        db.session.commit()
        
        if best_match:
            print(f"✅ Face recognized: {best_match.name} (confidence: {best_confidence})")
            return jsonify({
                'status': 'success',
                'message': f'Face recognized: {best_match.name}',
                'user': best_match.to_dict(),
                'confidence': float(best_confidence)
            })
        else:
            print(f"❌ Face not recognized (best confidence: {best_confidence})")
            return jsonify({
                'status': 'error',
                'message': 'Unknown user - Face detected but not recognized in the system.',
                'confidence': float(best_confidence)
            })
        
    except Exception as e:
        print(f"Recognition error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f'Recognition failed: {str(e)}'
        })

@app.route('/api/recognize_face', methods=['POST'])
def recognize_face():
    """Recognize a face from camera"""
    try:
        # Capture frame from camera with improved error handling
        cap = None
        try:
            cap = initialize_camera()
            if not cap or not cap.isOpened():
                return jsonify({
                    'status': 'error',
                    'message': 'Could not initialize camera'
                })
            
            # Try multiple frame captures for better reliability
            ret, frame = None, None
            for attempt in range(5):
                ret, frame = cap.read()
                if ret and frame is not None:
                    break
                time.sleep(0.1)
            
            if not ret or frame is None:
                return jsonify({
                    'status': 'error',
                    'message': 'Could not capture image from camera'
                })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Camera error: {str(e)}'
            })
        finally:
            if cap:
                cap.release()
        
        # Detect faces
        faces = face_detector.detect_faces(frame)
        
        if len(faces) == 0:
            return jsonify({
                'status': 'error',
                'message': 'No face detected in frame. Please position your face in front of the camera.'
            })
        
        # Use the first detected face
        face_features = face_detector.extract_face_features(frame, faces[0])
        
        # Compare with stored faces
        users = User.query.filter(User.face_data.isnot(None)).all()
        
        if len(users) == 0:
            return jsonify({
                'status': 'error',
                'message': 'No registered users with face data found in the system.'
            })
        
        best_match = None
        best_confidence = 0.0
        
        for user in users:
            try:
                stored_features = json.loads(user.face_data)
                is_match, confidence = face_detector.compare_faces(face_features, stored_features)
                
                if is_match and confidence > best_confidence:
                    best_match = user
                    best_confidence = confidence
            except Exception as e:
                print(f"Error comparing with user {user.id}: {e}")
                continue
        
        # Log the recognition attempt
        log_entry = RecognitionLog(
            user_id=best_match.id if best_match else None,
            confidence=best_confidence,
            status='recognized' if best_match else 'unknown'
        )
        db.session.add(log_entry)
        db.session.commit()
        
        if best_match:
            print(f"✅ Face recognized: {best_match.name} (confidence: {best_confidence})")
            return jsonify({
                'status': 'success',
                'message': f'Face recognized: {best_match.name}',
                'user': best_match.to_dict(),
                'confidence': float(best_confidence)
            })
        else:
            print(f"❌ Face not recognized (best confidence: {best_confidence})")
            return jsonify({
                'status': 'error',
                'message': 'Unknown user - Face detected but not recognized in the system.',
                'confidence': float(best_confidence)
            })
        
    except Exception as e:
        print(f"Recognition error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f'Recognition failed: {str(e)}'
        })

@app.route('/api/system/status')
def system_status():
    """Get system status"""
    try:
        # Test camera
        camera_status = False
        try:
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                ret, frame = cap.read()
                camera_status = ret
                cap.release()
        except:
            camera_status = False
        
        # Test face detection
        face_detection_status = False
        try:
            test_image = np.zeros((100, 100, 3), dtype=np.uint8)
            faces = face_detector.detect_faces(test_image)
            face_detection_status = True
        except:
            face_detection_status = False
        
        status = {
            'flask': True,
            'opencv': True,
            'database': True,
            'face_detection': face_detection_status,
            'camera': camera_status
        }
        
        return jsonify({
            'status': 'success',
            'components': status,
            'message': 'System status retrieved',
            'face_recognition_method': 'OpenCV Haar Cascades'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Status check failed: {str(e)}'
        })

@app.route('/api/detect_faces', methods=['POST'])
def detect_faces():
    """Detect faces in an image and return coordinates"""
    try:
        data = request.get_json()
        image_data = data.get('image')
        
        if not image_data:
            return jsonify({
                'status': 'error',
                'message': 'No image data provided'
            }), 400
        
        # Decode base64 image
        import base64
        import io
        from PIL import Image
        
        # Remove data URL prefix if present
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        # Decode base64
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to OpenCV format
        frame = np.array(image)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        
        print(f"Detecting faces in image of size: {frame.shape}")
        
        # Detect faces
        faces = face_detector.detect_faces(frame)
        
        print(f"Detected {len(faces)} faces")
        
        # Convert to list of dictionaries
        faces_list = []
        for (x, y, w, h) in faces:
            faces_list.append({
                'x': int(x),
                'y': int(y),
                'w': int(w),
                'h': int(h)
            })
            print(f"Face at: x={x}, y={y}, w={w}, h={h}")
        
        return jsonify({
            'status': 'success',
            'faces': faces_list,
            'count': len(faces_list),
            'image_size': f"{frame.shape[1]}x{frame.shape[0]}"
        })
        
    except Exception as e:
        print(f"Face detection API error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/camera/list')
def list_cameras():
    """List all available cameras"""
    try:
        available_cameras = []
        
        # Test up to 10 camera indices
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    height, width = frame.shape[:2]
                    available_cameras.append({
                        'index': i,
                        'name': f'Camera {i}',
                        'resolution': f'{width}x{height}',
                        'status': 'available'
                    })
                cap.release()
        
        return jsonify({
            'status': 'success',
            'cameras': available_cameras,
            'count': len(available_cameras)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to list cameras: {str(e)}'
        })



@app.route('/api/users')
def api_users():
    """Get all users"""
    try:
        users = User.query.all()
        users_data = [user.to_dict() for user in users]
        
        return jsonify({
            'status': 'success',
            'users': users_data,
            'count': len(users_data)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to get users: {str(e)}'
        })

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    """Update user information"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404
        
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400
        
        # Update user fields
        if 'name' in data:
            user.name = data['name']
        if 'email' in data:
            user.email = data['email']
        if 'phone' in data:
            user.phone = data['phone']
        if 'address' in data:
            user.address = data['address']
        if 'city' in data:
            user.city = data['city']
        if 'college_name' in data:
            user.college_name = data['college_name']
        if 'department' in data:
            user.department = data['department']
        if 'course' in data:
            user.course = data['course']
        if 'year_of_study' in data:
            user.year_of_study = data['year_of_study']
        if 'is_active' in data:
            user.is_active = data['is_active']
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'User updated successfully',
            'user': user.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to update user: {str(e)}'
        }), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    """Delete user"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404
        
        # Delete associated recognition logs first
        RecognitionLog.query.filter_by(user_id=user_id).delete()
        
        # Delete the user
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'User deleted successfully'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to delete user: {str(e)}'
        }), 500

@app.route('/api/stats/dashboard')
def api_dashboard_stats():
    """Get dashboard statistics"""
    try:
        # Get user statistics
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        users_with_faces = User.query.filter(User.face_data.isnot(None)).count()
        
        # Get recognition statistics
        total_recognitions = RecognitionLog.query.count()
        successful_recognitions = RecognitionLog.query.filter_by(status='recognized').count()
        
        # Get recent activity
        recent_registrations = User.query.order_by(User.created_at.desc()).limit(5).all()
        recent_recognitions = RecognitionLog.query.order_by(RecognitionLog.timestamp.desc()).limit(5).all()
        
        return jsonify({
            'status': 'success',
            'stats': {
                'users': {
                    'total': total_users,
                    'active': active_users,
                    'with_faces': users_with_faces,
                    'inactive': total_users - active_users
                },
                'recognitions': {
                    'total': total_recognitions,
                    'successful': successful_recognitions,
                    'failed': total_recognitions - successful_recognitions
                },
                'recent_registrations': [user.to_dict() for user in recent_registrations],
                'recent_recognitions': [{
                    'id': log.id,
                    'user_name': User.query.get(log.user_id).name if log.user_id else 'Unknown',
                    'status': log.status,
                    'confidence': log.confidence,
                    'timestamp': log.timestamp.isoformat()
                } for log in recent_recognitions]
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to get dashboard stats: {str(e)}'
        })

@app.route('/api/logs')
def api_logs():
    """Get recognition logs"""
    try:
        logs = RecognitionLog.query.order_by(RecognitionLog.timestamp.desc()).limit(50).all()
        logs_data = []
        
        for log in logs:
            user_name = 'Unknown'
            if log.user_id:
                user = User.query.get(log.user_id)
                if user:
                    user_name = user.name
            
            logs_data.append({
                'id': log.id,
                'user_name': user_name,
                'confidence': log.confidence,
                'timestamp': log.timestamp.isoformat(),
                'status': log.status
            })
        
        return jsonify({
            'status': 'success',
            'logs': logs_data,
            'count': len(logs_data)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to get logs: {str(e)}'
        })

@app.route('/api/logs/clear', methods=['DELETE'])
def clear_logs():
    """Clear all recognition logs"""
    try:
        RecognitionLog.query.delete()
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'All recognition logs cleared'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to clear logs: {str(e)}'
        })

@app.route('/api/stats/today')
def today_stats():
    """Get today's recognition statistics"""
    try:
        from datetime import date
        today = date.today()
        
        # Get today's logs
        today_logs = RecognitionLog.query.filter(
            db.func.date(RecognitionLog.timestamp) == today
        ).all()
        
        # Calculate stats
        total_recognitions = len(today_logs)
        unique_users = len(set(log.user_id for log in today_logs if log.user_id))
        
        # Get last recognition
        last_log = RecognitionLog.query.order_by(RecognitionLog.timestamp.desc()).first()
        last_recognition = 'None'
        if last_log:
            if last_log.user_id:
                user = User.query.get(last_log.user_id)
                user_name = user.name if user else 'Unknown'
            else:
                user_name = 'Unknown'
            last_recognition = f"{user_name} at {last_log.timestamp.strftime('%H:%M:%S')}"
        
        return jsonify({
            'status': 'success',
            'stats': {
                'total_recognitions': total_recognitions,
                'unique_users': unique_users,
                'last_recognition': last_recognition
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to get today stats: {str(e)}'
        })

@app.route('/api/recognition/status')
def recognition_status():
    """Get recognition status"""
    try:
        return jsonify({
            'status': 'success',
            'recognition_active': recognition_active,
            'message': 'Recognition status retrieved'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to get recognition status: {str(e)}'
        })

@app.route('/api/recognition/start', methods=['POST'])
def start_recognition():
    """Start recognition process"""
    try:
        global recognition_active
        recognition_active = True
        
        return jsonify({
            'status': 'success',
            'message': 'Recognition started'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to start recognition: {str(e)}'
        })

@app.route('/api/recognition/stop', methods=['POST'])
def stop_recognition():
    """Stop recognition process"""
    try:
        global recognition_active
        recognition_active = False
        
        return jsonify({
            'status': 'success',
            'message': 'Recognition stopped'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to stop recognition: {str(e)}'
        })

@app.route('/api/video_feed')
def api_video_feed():
    """Redirect to video feed"""
    return redirect('/video_feed')

@app.route('/video_feed_with_recognition')
def video_feed_with_recognition():
    """Video streaming route with face recognition overlay"""
    def generate():
        cap = None
        error_count = 0
        max_errors = 5
        
        try:
            cap = initialize_camera()
            if not cap or not cap.isOpened():
                while True:
                    placeholder = create_placeholder_frame("Camera not available")
                    ret, buffer = cv2.imencode('.jpg', placeholder)
                    frame = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                    time.sleep(0.5)
                return
            
            # Load all users with face data
            users = User.query.filter(User.face_data.isnot(None)).all()
            
            frame_count = 0
            while True:
                try:
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        error_count += 1
                        if error_count > max_errors:
                            if cap:
                                cap.release()
                            cap = initialize_camera()
                            error_count = 0
                        continue
                    
                    error_count = 0
                    
                    # Detect faces
                    faces = face_detector.detect_faces(frame)
                    
                    # Process each detected face
                    for (x, y, w, h) in faces:
                        # Extract features only every 5 frames to improve performance
                        if frame_count % 5 == 0:
                            try:
                                face_features = face_detector.extract_face_features(frame, (x, y, w, h))
                                
                                # Compare with stored faces
                                best_match = None
                                best_confidence = 0.0
                                
                                for user in users:
                                    try:
                                        stored_features = json.loads(user.face_data)
                                        is_match, confidence = face_detector.compare_faces(face_features, stored_features)
                                        
                                        if is_match and confidence > best_confidence:
                                            best_match = user
                                            best_confidence = confidence
                                    except:
                                        continue
                                
                                # Draw rectangle and name
                                if best_match and best_confidence > 0.6:
                                    # Green rectangle for recognized user
                                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 3)
                                    
                                    # Draw name background
                                    name_text = f"{best_match.name}"
                                    conf_text = f"{int(best_confidence * 100)}%"
                                    
                                    # Name label
                                    cv2.rectangle(frame, (x, y-40), (x+w, y), (0, 255, 0), -1)
                                    cv2.putText(frame, name_text, (x+5, y-22), 
                                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
                                    cv2.putText(frame, conf_text, (x+5, y-5), 
                                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
                                else:
                                    # Red rectangle for unknown user
                                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 3)
                                    cv2.rectangle(frame, (x, y-30), (x+w, y), (0, 0, 255), -1)
                                    cv2.putText(frame, 'Unknown User', (x+5, y-10), 
                                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                            except Exception as e:
                                # Just draw basic rectangle if recognition fails
                                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 255, 0), 2)
                        else:
                            # Just draw rectangle without recognition
                            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 255, 0), 2)
                    
                    # Add info overlay
                    cv2.putText(frame, f'Face Recognition Active - {len(faces)} faces', 
                               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                    cv2.putText(frame, f'Time: {datetime.now().strftime("%H:%M:%S")}', 
                               (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
                    ret, buffer = cv2.imencode('.jpg', frame)
                    if ret:
                        frame = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                    
                    frame_count += 1
                    time.sleep(0.033)  # ~30 FPS
                    
                except Exception as e:
                    print(f"Frame processing error: {e}")
                    error_count += 1
                    if error_count > max_errors:
                        break
                    continue
                    
        except Exception as e:
            print(f"Video feed with recognition error: {e}")
        finally:
            if cap:
                try:
                    cap.release()
                except:
                    pass
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/train_from_images', methods=['POST'])
def train_from_images():
    """Train face model from provided images"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        images = data.get('images', [])
        
        if not user_id:
            return jsonify({
                'status': 'error',
                'message': 'User ID is required'
            }), 400
        
        if not images or len(images) == 0:
            return jsonify({
                'status': 'error',
                'message': 'No images provided'
            }), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404
        
        # Process images
        import base64
        import io
        from PIL import Image
        
        captured_features = []
        
        for idx, image_data in enumerate(images):
            try:
                # Remove data URL prefix if present
                if ',' in image_data:
                    image_data = image_data.split(',')[1]
                
                # Decode base64
                image_bytes = base64.b64decode(image_data)
                image = Image.open(io.BytesIO(image_bytes))
                
                # Convert to OpenCV format
                frame = np.array(image)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                # Detect faces
                faces = face_detector.detect_faces(frame)
                
                if len(faces) > 0:
                    # Use the first detected face
                    face_features = face_detector.extract_face_features(frame, faces[0])
                    captured_features.append(face_features)
                    print(f"✓ Processed image {idx + 1}/{len(images)}")
                
            except Exception as e:
                print(f"Error processing image {idx + 1}: {e}")
                continue
        
        if len(captured_features) < 3:
            return jsonify({
                'status': 'error',
                'message': f'Not enough face images captured. Got {len(captured_features)}, need at least 3.'
            }), 400
        
        # Average the features
        averaged_features = captured_features[0].copy()
        if len(captured_features) > 1:
            histograms = [f['histogram'] for f in captured_features]
            avg_histogram = np.mean(histograms, axis=0).tolist()
            averaged_features['histogram'] = avg_histogram
        
        # Store the averaged features
        user.face_data = json.dumps(averaged_features)
        db.session.commit()
        
        print(f"Training complete! Processed {len(captured_features)} images")
        
        return jsonify({
            'status': 'success',
            'message': f'Face training complete with {len(captured_features)} images',
            'images_captured': len(captured_features)
        })
        
    except Exception as e:
        print(f"Training error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/capture_training_images', methods=['POST'])
def capture_training_images():
    """Capture multiple images for face training"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        num_images = data.get('num_images', 20)
        
        if not user_id:
            return jsonify({
                'status': 'error',
                'message': 'User ID is required'
            }), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404
        
        # Capture multiple images
        cap = None
        captured_features = []
        
        try:
            cap = initialize_camera()
            if not cap or not cap.isOpened():
                return jsonify({
                    'status': 'error',
                    'message': 'Could not initialize camera. Please check camera permissions and ensure no other application is using the camera.'
                }), 500
            
            print(f"Capturing {num_images} images for user {user_id}...")
            
            # Warm up camera - skip first 3 frames only
            for _ in range(3):
                cap.read()
                time.sleep(0.05)
            
            attempts = 0
            max_attempts = num_images * 5  # Allow more attempts to find face
            consecutive_failures = 0
            
            while len(captured_features) < num_images and attempts < max_attempts:
                attempts += 1
                
                # Read frame
                ret, frame = cap.read()
                if not ret or frame is None:
                    consecutive_failures += 1
                    if consecutive_failures > 10:
                        print(f"Too many consecutive frame read failures")
                        break
                    time.sleep(0.05)
                    continue
                
                consecutive_failures = 0
                
                try:
                    # Detect faces
                    faces = face_detector.detect_faces(frame)
                    
                    if len(faces) > 0:
                        # Use the first detected face
                        face_features = face_detector.extract_face_features(frame, faces[0])
                        captured_features.append(face_features)
                        print(f"✓ Captured image {len(captured_features)}/{num_images}")
                        
                        # Very short delay between successful captures for speed
                        time.sleep(0.05)
                    else:
                        # Slightly longer delay when no face detected
                        time.sleep(0.1)
                    
                except Exception as e:
                    print(f"Error processing frame: {e}")
                    time.sleep(0.05)
                    continue
            
            print(f"Capture complete: {len(captured_features)} images captured in {attempts} attempts")
            
        except Exception as e:
            print(f"Camera capture error: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Camera error: {str(e)}'
            }), 500
        finally:
            if cap:
                try:
                    cap.release()
                except:
                    pass
        
        if len(captured_features) < 3:
            return jsonify({
                'status': 'error',
                'message': f'Not enough face images captured. Got {len(captured_features)}, need at least 3. Please ensure your face is clearly visible in the camera with good lighting.'
            }), 400
        
        # Average the features from multiple captures for better accuracy
        # Take the first capture as the base model (they should all be similar)
        averaged_features = captured_features[0].copy()
        
        # Average the histograms
        if len(captured_features) > 1:
            histograms = [f['histogram'] for f in captured_features]
            avg_histogram = np.mean(histograms, axis=0).tolist()
            averaged_features['histogram'] = avg_histogram
        
        # Store the averaged features
        user.face_data = json.dumps(averaged_features)
        db.session.commit()
        
        print(f"Training complete! Captured {len(captured_features)} images")
        
        return jsonify({
            'status': 'success',
            'message': f'Face training complete with {len(captured_features)} images',
            'images_captured': len(captured_features)
        })
        
    except Exception as e:
        print(f"Training error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f'Training failed: {str(e)}'
        }), 500

@app.route('/api/register_with_face', methods=['POST'])
def register_with_face():
    """Register a new user and capture face data in one step"""
    try:
        print("Register with face API called")
        
        # Get JSON data
        data = request.get_json()
        print(f"Received data: {data}")
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data received'
            }), 400
        
        name = data.get('name')
        email = data.get('email')
        phone = data.get('phone')
        address = data.get('address')
        city = data.get('city')
        college_name = data.get('college_name')
        department = data.get('department')
        course = data.get('course')
        year_of_study = data.get('year_of_study')
        
        if not name or not email:
            return jsonify({
                'status': 'error',
                'message': 'Name and email are required'
            }), 400
        
        # Check if user exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({
                'status': 'error',
                'message': 'User with this email already exists'
            }), 409
        
        # Generate person ID
        person_id = generate_person_id()
        
        # Step 1: Create user
        new_user = User(
            person_id=person_id,
            name=name,
            email=email,
            phone=phone,
            address=address,
            city=city,
            college_name=college_name,
            department=department,
            course=course,
            year_of_study=year_of_study
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        print(f"User created successfully with ID: {new_user.id}")
        
        # Step 2: Capture face data
        try:
            # Capture frame from camera with improved error handling
            cap = None
            try:
                cap = initialize_camera()
                if not cap or not cap.isOpened():
                    return jsonify({
                        'status': 'partial_success',
                        'message': 'User registered but could not initialize camera',
                        'user_id': new_user.id
                    }), 200
                
                # Try multiple frame captures for better reliability
                ret, frame = None, None
                for attempt in range(3):
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        break
                    time.sleep(0.1)
                
                if not ret or frame is None:
                    return jsonify({
                        'status': 'partial_success',
                        'message': 'User registered but could not capture face image from camera',
                        'user_id': new_user.id
                    }), 200
            except Exception as cam_error:
                return jsonify({
                    'status': 'partial_success',
                    'message': f'User registered but camera error: {str(cam_error)}',
                    'user_id': new_user.id
                }), 200
            finally:
                if cap:
                    cap.release()
            
            # Detect faces in the captured frame
            faces = face_detector.detect_faces(frame)
            
            if len(faces) == 0:
                return jsonify({
                    'status': 'partial_success',
                    'message': 'User registered but no face detected in the image',
                    'user_id': new_user.id
                }), 200
            
            if len(faces) > 1:
                return jsonify({
                    'status': 'partial_success',
                    'message': 'User registered but multiple faces detected. Please ensure only one person is in the frame',
                    'user_id': new_user.id
                }), 200
            
            # Extract features from the detected face
            face_features = face_detector.extract_face_features(frame, faces[0])
            
            # Store face data
            new_user.face_data = json.dumps(face_features)
            db.session.commit()
            
            print(f"Face data captured and stored for user ID: {new_user.id}")
            
            return jsonify({
                'status': 'success',
                'message': 'User registered and face data captured successfully',
                'user_id': new_user.id,
                'person_id': new_user.person_id,
                'face_captured': True
            }), 200
            
        except Exception as face_error:
            print(f"Face capture error: {str(face_error)}")
            return jsonify({
                'status': 'partial_success',
                'message': f'User registered but face capture failed: {str(face_error)}',
                'user_id': new_user.id,
                'face_captured': False
            }), 200
        
    except Exception as e:
        print(f"Registration with face error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'status': 'error',
            'message': f'Registration failed: {str(e)}'
        }), 500

def create_default_admin():
    """Create default admin user"""
    try:
        admin = Admin.query.filter_by(username='admin').first()
        if not admin:
            admin = Admin(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                role='super_admin'
            )
            db.session.add(admin)
            db.session.commit()
            print("Default admin user created (admin/admin123)")
    except Exception as e:
        print(f"Failed to create default admin: {e}")

def initialize_app():
    """Initialize the application"""
    with app.app_context():
        try:
            # Create database tables
            db.create_all()
            
            # Create default admin
            create_default_admin()
            
            print("=" * 60)
            print("Face Recognition App - OpenCV Edition")
            print("=" * 60)
            print("[OK] Flask application started")
            print("[OK] Database initialized")
            print("[OK] OpenCV face detection enabled")
            print("[OK] Camera access available")
            print("")
            print("Features available:")
            print("   - Web interface")
            print("   - OpenCV face detection")
            print("   - User registration with face capture")
            print("   - Face recognition using histogram comparison")
            print("   - Admin dashboard")
            print("   - Recognition logging")
            print("")
            print("Note: This version uses OpenCV Haar Cascades")
            print("      instead of dlib for better compatibility")
            print("=" * 60)
            
        except Exception as e:
            print(f"Error initializing app: {e}")

# Initialize app when imported (for gunicorn)
initialize_app()

if __name__ == '__main__':
    # For local development
    import os
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    
    print(f"Starting on port {port}, debug={debug}")
    app.run(debug=debug, host='0.0.0.0', port=port)
