# 🔍 Face Recognition Web Application

A comprehensive web-based face recognition system built with Flask, OpenCV, and modern web technologies. Features real-time face detection, user registration with face training, and a complete admin dashboard.

![Face Recognition App](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.3+-green.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-4.8+-red.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## ✨ Features

### 🎯 Core Functionality
- **Real-time Face Recognition**: Live camera feed with instant face detection and recognition
- **User Registration**: Easy user onboarding with face capture and model training
- **Recognition Logging**: Detailed logs of all recognition events with timestamps
- **Admin Dashboard**: Comprehensive management interface with statistics

### � ️ Security & Authentication
- **JWT Authentication**: Secure admin access with token-based authentication
- **Role-based Access**: Admin authentication system
- **Secure Data Storage**: Face encodings stored securely in database

### 📊 Analytics & Reporting
- **Real-time Statistics**: Live dashboard with recognition metrics
- **User Management**: Complete CRUD operations for users
- **Recognition History**: Detailed logs with confidence scores

### � Modeirn UI/UX
- **Responsive Design**: Mobile-friendly interface using Bootstrap 5
- **Real-time Updates**: Live camera feeds and instant recognition feedback
- **Intuitive Interface**: Easy-to-use forms and navigation

## 🏗️ Architecture

### Backend Components
- **Flask Application**: Main web server and API endpoints
- **SQLAlchemy ORM**: Database management with SQLite
- **Face Recognition Engine**: OpenCV Haar Cascades integration
- **Camera Management**: Multi-camera support with streaming capabilities

### Frontend Components
- **Bootstrap 5**: Modern responsive UI framework
- **JavaScript ES6+**: Modern client-side functionality
- **Real-time Video**: Camera access and video streaming

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Webcam or camera device
- Modern web browser

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/hackwithim/face-recognition-app.git
cd face-recognition-app
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Run the application**
```bash
python app_opencv_face_detection.py
```

5. **Access the application**
- Open your browser to: http://localhost:5000
- Admin login: `admin` / `admin123`

## � Usage Guide

### 👤 User Registration
1. Navigate to **Register User** page
2. Fill in personal information (Name and Email required)
3. Click **"Register with Face Capture"**
4. System automatically captures face images and trains model
5. Receive auto-generated Person ID (P001, P002, etc.)

### 📹 Face Recognition
1. Go to **Recognition** page
2. Allow camera access when prompted
3. Click **"Recognize Once"** to identify faces
4. System displays:
   - User name and details if recognized
   - "Unknown User" if not in database
   - Confidence percentage

### 📊 Admin Dashboard
1. Login with admin credentials
2. View all registered users
3. See system statistics
4. Manage user accounts
5. View recognition logs

## 🔧 Configuration

### Environment Variables
Create a `.env` file in the root directory:
```env
DATABASE_URL=sqlite:///face_recognition.db
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-here
FLASK_ENV=development
```

### Camera Settings
The app automatically detects and uses the best available camera backend:
- DirectShow (Windows)
- Microsoft Media Foundation
- Video4Linux2 (Linux)

## 📁 Project Structure

```
face-recognition-app/
├── app_opencv_face_detection.py    # Main Flask application
├── requirements.txt                # Python dependencies
├── .env                           # Environment variables
├── .gitignore                     # Git ignore rules
├── README.md                      # This file
├── templates/                     # HTML templates
│   ├── base.html                 # Base template
│   ├── index_opencv.html         # Home page
│   ├── register_fixed.html       # Registration page
│   ├── recognize_fixed.html      # Recognition page
│   ├── admin.html                # Admin dashboard
│   └── capture_face.html         # Face capture page
├── static/                       # Static files (CSS, JS, images)
├── instance/                     # Database files (auto-created)
└── logs/                         # Application logs (auto-created)
```

## 🔌 API Endpoints

### Authentication
- `POST /api/login` - Admin login

### User Management
- `GET /api/users` - List all users
- `POST /api/register` - Register new user
- `PUT /api/users/{id}` - Update user
- `DELETE /api/users/{id}` - Delete user

### Face Recognition
- `POST /api/recognize_face` - Recognize face from camera
- `GET /api/recognition/status` - Get recognition status

### System
- `GET /api/system/status` - Get system status
- `GET /api/stats/dashboard` - Get dashboard statistics

## 🐛 Troubleshooting

### Common Issues

**Camera not working:**
- Check camera permissions in browser
- Ensure camera is not used by other applications
- Try refreshing the page

**Face recognition accuracy issues:**
- Ensure good lighting conditions
- Capture face images with clear frontal view
- Register with multiple angles if needed

**Database connection errors:**
- Check if SQLite database file exists in `instance/` folder
- Ensure proper file permissions

## 📈 Performance Tips

- Use good lighting for better face detection
- Position face directly in front of camera
- Ensure stable internet connection for web interface
- Close other applications using the camera

## 🔒 Security Notes

- Change default admin credentials in production
- Use HTTPS in production environment
- Implement proper backup strategy for database
- Regular security updates for dependencies

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👨‍💻 Developer

**Kashinath Gaikwad**
- Email: kashinathgaikwad844@gmail.com
- GitHub: [@hackwithim](https://github.com/hackwithim)

## 🙏 Acknowledgments

- [OpenCV](https://opencv.org/) - Computer vision library
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [Bootstrap](https://getbootstrap.com/) - UI framework

## 📞 Support

For support and questions:
- **Developer:** Kashinath Gaikwad
- **Email:** kashinathgaikwad844@gmail.com
- **GitHub Issues:** Create an issue for bugs and feature requests
- **Documentation:** Check the troubleshooting section

---

**⚠️ Important Note**: This application processes biometric data. Ensure compliance with local privacy laws and regulations before deployment in production environments.

## 🎯 Demo Credentials

- **Admin Username:** `admin`
- **Admin Password:** `admin123`

**Happy Face Recognition!** 🎉