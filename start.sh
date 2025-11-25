#!/bin/bash
# Startup script for Face Recognition App

echo "Starting Face Recognition App..."

# Check if gunicorn is available
if command -v gunicorn &> /dev/null; then
    echo "Using gunicorn..."
    gunicorn app_opencv_face_detection:app --bind 0.0.0.0:${PORT:-5000} --workers 2 --timeout 120
else
    echo "Gunicorn not found, using Python directly..."
    python app_opencv_face_detection.py
fi