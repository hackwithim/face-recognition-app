# 🚀 Deployment Guide

This guide covers different deployment options for the Face Recognition App.

## 📋 Prerequisites

- Python 3.8+
- Git
- Camera/Webcam access
- Modern web browser

## 🏠 Local Development

### Quick Start
```bash
git clone https://github.com/kashinathgaikwad/face-recognition-app.git
cd face-recognition-app
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app_opencv_face_detection.py
```

Access at: http://localhost:5000

## 🌐 Production Deployment

### Using Gunicorn (Recommended)

1. **Install Gunicorn**
```bash
pip install gunicorn
```

2. **Create Gunicorn config**
```python
# gunicorn.conf.py
bind = "0.0.0.0:5000"
workers = 4
worker_class = "sync"
timeout = 120
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
```

3. **Run with Gunicorn**
```bash
gunicorn -c gunicorn.conf.py app_opencv_face_detection:app
```

### Environment Variables

Create `.env` file:
```env
# Database
DATABASE_URL=sqlite:///face_recognition.db

# Security
SECRET_KEY=your-super-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here

# Flask
FLASK_ENV=production
FLASK_DEBUG=False

# Camera
DEFAULT_CAMERA_INDEX=0
FACE_RECOGNITION_TOLERANCE=0.6

# Upload
MAX_CONTENT_LENGTH=16777216
UPLOAD_FOLDER=static/uploads

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
```

### Security Checklist

- [ ] Change default admin credentials
- [ ] Use strong SECRET_KEY and JWT_SECRET_KEY
- [ ] Enable HTTPS in production
- [ ] Set FLASK_ENV=production
- [ ] Configure proper file permissions
- [ ] Set up regular database backups
- [ ] Configure firewall rules
- [ ] Use reverse proxy (Nginx/Apache)

## 🐳 Docker Deployment

### Dockerfile
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p instance logs static/uploads

# Expose port
EXPOSE 5000

# Run application
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app_opencv_face_detection:app"]
```

### Docker Compose
```yaml
version: '3.8'

services:
  face-recognition-app:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./instance:/app/instance
      - ./logs:/app/logs
      - ./static/uploads:/app/static/uploads
    environment:
      - FLASK_ENV=production
      - SECRET_KEY=your-secret-key
      - JWT_SECRET_KEY=your-jwt-secret
    restart: unless-stopped
```

### Build and Run
```bash
docker-compose up -d
```

## ☁️ Cloud Deployment

### Heroku

1. **Create Procfile**
```
web: gunicorn app_opencv_face_detection:app
```

2. **Deploy**
```bash
heroku create your-app-name
git push heroku main
```

### AWS EC2

1. **Launch EC2 instance** (Ubuntu 20.04 LTS)
2. **Install dependencies**
```bash
sudo apt update
sudo apt install python3-pip python3-venv git
```

3. **Clone and setup**
```bash
git clone https://github.com/kashinathgaikwad/face-recognition-app.git
cd face-recognition-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

4. **Configure systemd service**
```ini
# /etc/systemd/system/face-recognition.service
[Unit]
Description=Face Recognition App
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/face-recognition-app
Environment=PATH=/home/ubuntu/face-recognition-app/venv/bin
ExecStart=/home/ubuntu/face-recognition-app/venv/bin/gunicorn -c gunicorn.conf.py app_opencv_face_detection:app
Restart=always

[Install]
WantedBy=multi-user.target
```

5. **Start service**
```bash
sudo systemctl enable face-recognition
sudo systemctl start face-recognition
```

### DigitalOcean Droplet

Similar to AWS EC2, but with DigitalOcean's one-click apps:
1. Create Ubuntu droplet
2. Follow EC2 instructions above
3. Configure domain and SSL

## 🔒 SSL/HTTPS Setup

### Using Certbot (Let's Encrypt)

1. **Install Certbot**
```bash
sudo apt install certbot python3-certbot-nginx
```

2. **Get certificate**
```bash
sudo certbot --nginx -d yourdomain.com
```

3. **Auto-renewal**
```bash
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

## 🔧 Nginx Configuration

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /video_feed {
        proxy_pass http://127.0.0.1:5000;
        proxy_buffering off;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 📊 Monitoring

### Health Check Endpoint
Add to your app:
```python
@app.route('/health')
def health_check():
    return {'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}
```

### Log Monitoring
```bash
# View logs
tail -f logs/app.log

# Rotate logs
sudo logrotate -f /etc/logrotate.d/face-recognition
```

## 🔄 Updates and Maintenance

### Update Process
```bash
# Backup database
cp instance/face_recognition.db instance/face_recognition.db.backup

# Pull updates
git pull origin main

# Update dependencies
pip install -r requirements.txt

# Restart service
sudo systemctl restart face-recognition
```

### Database Backup
```bash
# Create backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
cp instance/face_recognition.db backups/face_recognition_$DATE.db

# Add to crontab for daily backups
0 2 * * * /path/to/backup-script.sh
```

## 🐛 Troubleshooting

### Common Issues

**Camera not accessible:**
- Check camera permissions
- Verify camera device exists
- Test with different camera backends

**Database locked:**
- Check file permissions
- Ensure only one app instance
- Restart the application

**High memory usage:**
- Monitor camera feed connections
- Implement connection limits
- Use process monitoring

### Performance Tuning

**Optimize camera settings:**
```python
# In app configuration
CAMERA_SETTINGS = {
    'resolution': (640, 480),
    'fps': 15,
    'buffer_size': 1
}
```

**Database optimization:**
```python
# Add indexes for better performance
CREATE INDEX idx_user_email ON user(email);
CREATE INDEX idx_recognition_timestamp ON recognition_logs(timestamp);
```

## 📞 Support

For deployment issues:
- **Developer:** Kashinath Gaikwad
- **Email:** kashinathgaikwad844@gmail.com
- **GitHub Issues:** [Report deployment issues](https://github.com/kashinathgaikwad/face-recognition-app/issues)

---

**Note:** Always test deployments in a staging environment before production!