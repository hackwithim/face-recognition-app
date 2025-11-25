/**
 * Face Recognition System - Main JavaScript Application
 * Contains common utilities and functions used across the application
 */

// Global configuration
const CONFIG = {
    API_BASE_URL: '/api',
    WEBSOCKET_URL: 'ws://localhost:5000/ws',
    VIDEO_REFRESH_RATE: 30, // FPS
    RECOGNITION_THRESHOLD: 70, // Minimum confidence for recognition
    MAX_CAPTURE_IMAGES: 20,
    CAPTURE_INTERVAL: 500 // ms between captures
};

// Global state management
const AppState = {
    isAuthenticated: false,
    currentUser: null,
    cameraActive: false,
    recognitionActive: false,
    captureSession: null
};

/**
 * Authentication utilities
 */
class AuthManager {
    static getToken() {
        return localStorage.getItem('access_token');
    }
    
    static setToken(token) {
        localStorage.setItem('access_token', token);
        AppState.isAuthenticated = true;
    }
    
    static removeToken() {
        localStorage.removeItem('access_token');
        AppState.isAuthenticated = false;
        AppState.currentUser = null;
    }
    
    static isAuthenticated() {
        return !!this.getToken();
    }
    
    static async login(username, password) {
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.setToken(data.access_token);
                AppState.currentUser = data.admin;
                return { success: true, user: data.admin };
            } else {
                return { success: false, error: data.error };
            }
        } catch (error) {
            console.error('Login error:', error);
            return { success: false, error: 'Network error' };
        }
    }
    
    static logout() {
        this.removeToken();
        window.location.href = '/admin';
    }
}

/**
 * API utilities
 */
class ApiClient {
    static async request(endpoint, options = {}) {
        const token = AuthManager.getToken();
        
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                ...(token && { 'Authorization': `Bearer ${token}` })
            }
        };
        
        const mergedOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers
            }
        };
        
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}${endpoint}`, mergedOptions);
            
            if (response.status === 401) {
                AuthManager.removeToken();
                window.location.href = '/admin';
                return null;
            }
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Request failed');
            }
            
            return data;
        } catch (error) {
            console.error('API Request Error:', error);
            throw error;
        }
    }
    
    static async get(endpoint) {
        return this.request(endpoint);
    }
    
    static async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
    
    static async put(endpoint, data) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }
    
    static async delete(endpoint) {
        return this.request(endpoint, {
            method: 'DELETE'
        });
    }
}

/**
 * Camera management utilities
 */
class CameraManager {
    constructor() {
        this.videoElement = null;
        this.stream = null;
        this.isActive = false;
        this.recognitionInterval = null;
    }
    
    async initialize(videoElementId) {
        try {
            this.videoElement = document.getElementById(videoElementId);
            if (!this.videoElement) {
                throw new Error('Video element not found');
            }
            
            // Request camera access
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: 'user'
                }
            });
            
            this.videoElement.srcObject = this.stream;
            this.isActive = true;
            AppState.cameraActive = true;
            
            return true;
        } catch (error) {
            console.error('Camera initialization error:', error);
            throw new Error('Failed to access camera: ' + error.message);
        }
    }
    
    stop() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        
        if (this.videoElement) {
            this.videoElement.srcObject = null;
        }
        
        if (this.recognitionInterval) {
            clearInterval(this.recognitionInterval);
            this.recognitionInterval = null;
        }
        
        this.isActive = false;
        AppState.cameraActive = false;
        AppState.recognitionActive = false;
    }
    
    captureFrame() {
        if (!this.videoElement || !this.isActive) {
            return null;
        }
        
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        
        canvas.width = this.videoElement.videoWidth;
        canvas.height = this.videoElement.videoHeight;
        
        context.drawImage(this.videoElement, 0, 0);
        
        return canvas.toDataURL('image/jpeg', 0.8);
    }
    
    startRecognition(callback, interval = 1000) {
        if (!this.isActive) {
            throw new Error('Camera not active');
        }
        
        this.recognitionInterval = setInterval(() => {
            const frame = this.captureFrame();
            if (frame && callback) {
                callback(frame);
            }
        }, interval);
        
        AppState.recognitionActive = true;
    }
    
    stopRecognition() {
        if (this.recognitionInterval) {
            clearInterval(this.recognitionInterval);
            this.recognitionInterval = null;
        }
        AppState.recognitionActive = false;
    }
}

/**
 * Face capture session management
 */
class FaceCaptureSession {
    constructor(userId, userName) {
        this.userId = userId;
        this.userName = userName;
        this.capturedImages = [];
        this.maxImages = CONFIG.MAX_CAPTURE_IMAGES;
        this.isActive = false;
        this.camera = new CameraManager();
    }
    
    async start(videoElementId) {
        try {
            await this.camera.initialize(videoElementId);
            
            // Start capture session on server
            await ApiClient.post(`/capture/start/${this.userId}`);
            
            this.isActive = true;
            AppState.captureSession = this;
            
            return true;
        } catch (error) {
            console.error('Capture session start error:', error);
            throw error;
        }
    }
    
    async captureImage() {
        if (!this.isActive || this.capturedImages.length >= this.maxImages) {
            return false;
        }
        
        try {
            // Capture image from server
            const result = await ApiClient.post('/capture/image');
            
            if (result) {
                this.capturedImages.push({
                    timestamp: new Date(),
                    faces_detected: result.faces_detected
                });
                
                return true;
            }
            
            return false;
        } catch (error) {
            console.error('Image capture error:', error);
            throw error;
        }
    }
    
    async complete() {
        try {
            if (this.capturedImages.length === 0) {
                throw new Error('No images captured');
            }
            
            // Complete training on server
            const result = await ApiClient.post('/capture/complete');
            
            this.stop();
            return result;
        } catch (error) {
            console.error('Capture completion error:', error);
            throw error;
        }
    }
    
    stop() {
        this.camera.stop();
        this.isActive = false;
        AppState.captureSession = null;
    }
    
    getProgress() {
        return {
            captured: this.capturedImages.length,
            total: this.maxImages,
            percentage: Math.round((this.capturedImages.length / this.maxImages) * 100)
        };
    }
}

/**
 * Recognition system management
 */
class RecognitionSystem {
    constructor() {
        this.camera = new CameraManager();
        this.isActive = false;
        this.recognitionCallback = null;
    }
    
    async start(videoElementId, callback) {
        try {
            await this.camera.initialize(videoElementId);
            
            // Start recognition on server
            await ApiClient.post('/recognition/start');
            
            this.recognitionCallback = callback;
            this.isActive = true;
            
            // Start local recognition loop for UI updates
            this.camera.startRecognition(this.handleRecognition.bind(this), 1000);
            
            return true;
        } catch (error) {
            console.error('Recognition start error:', error);
            throw error;
        }
    }
    
    async stop() {
        try {
            // Stop recognition on server
            await ApiClient.post('/recognition/stop');
            
            this.camera.stop();
            this.isActive = false;
            this.recognitionCallback = null;
            
        } catch (error) {
            console.error('Recognition stop error:', error);
        }
    }
    
    handleRecognition(frame) {
        if (this.recognitionCallback) {
            this.recognitionCallback(frame);
        }
    }
    
    async getStatus() {
        try {
            return await ApiClient.get('/recognition/status');
        } catch (error) {
            console.error('Status check error:', error);
            return null;
        }
    }
}

/**
 * UI utilities
 */
class UIUtils {
    static showAlert(message, type = 'info', duration = 5000) {
        const alertContainer = document.getElementById('alertContainer');
        if (!alertContainer) return;
        
        const alertId = 'alert-' + Date.now();
        const iconMap = {
            'success': 'check-circle',
            'danger': 'exclamation-triangle',
            'warning': 'exclamation-circle',
            'info': 'info-circle'
        };
        
        const alertHtml = `
            <div class="alert alert-${type} alert-dismissible fade show" id="${alertId}" role="alert">
                <i class="fas fa-${iconMap[type] || 'info-circle'} me-2"></i>
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        alertContainer.insertAdjacentHTML('beforeend', alertHtml);
        
        if (duration > 0) {
            setTimeout(() => {
                const alert = document.getElementById(alertId);
                if (alert) {
                    const bsAlert = new bootstrap.Alert(alert);
                    bsAlert.close();
                }
            }, duration);
        }
    }
    
    static showLoading(text = 'Processing...', subtext = 'Please wait...') {
        const modal = document.getElementById('loadingModal');
        if (modal) {
            document.getElementById('loadingText').textContent = text;
            document.getElementById('loadingSubtext').textContent = subtext;
            const bsModal = new bootstrap.Modal(modal);
            bsModal.show();
        }
    }
    
    static hideLoading() {
        const modal = document.getElementById('loadingModal');
        if (modal) {
            const bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) {
                bsModal.hide();
            }
        }
    }
    
    static formatDateTime(dateString) {
        const date = new Date(dateString);
        return date.toLocaleString();
    }
    
    static formatConfidence(confidence) {
        return confidence.toFixed(1) + '%';
    }
    
    static getConfidenceClass(confidence) {
        if (confidence >= 80) return 'confidence-high';
        if (confidence >= 60) return 'confidence-medium';
        return 'confidence-low';
    }
    
    static updateProgress(elementId, current, total) {
        const element = document.getElementById(elementId);
        if (element) {
            const percentage = Math.round((current / total) * 100);
            element.style.width = percentage + '%';
            element.setAttribute('aria-valuenow', current);
            element.setAttribute('aria-valuemax', total);
            element.textContent = `${current}/${total} (${percentage}%)`;
        }
    }
    
    static createUserAvatar(name, size = 40) {
        return `
            <div class="user-avatar" style="width: ${size}px; height: ${size}px; font-size: ${size * 0.4}px;">
                ${name.charAt(0).toUpperCase()}
            </div>
        `;
    }
}

/**
 * Form validation utilities
 */
class FormValidator {
    static validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }
    
    static validateRequired(value) {
        return value && value.trim().length > 0;
    }
    
    static validateForm(formData, rules) {
        const errors = {};
        
        for (const [field, rule] of Object.entries(rules)) {
            const value = formData[field];
            
            if (rule.required && !this.validateRequired(value)) {
                errors[field] = `${rule.label || field} is required`;
                continue;
            }
            
            if (value && rule.email && !this.validateEmail(value)) {
                errors[field] = `${rule.label || field} must be a valid email`;
                continue;
            }
            
            if (value && rule.minLength && value.length < rule.minLength) {
                errors[field] = `${rule.label || field} must be at least ${rule.minLength} characters`;
                continue;
            }
            
            if (value && rule.maxLength && value.length > rule.maxLength) {
                errors[field] = `${rule.label || field} must be no more than ${rule.maxLength} characters`;
                continue;
            }
        }
        
        return {
            isValid: Object.keys(errors).length === 0,
            errors
        };
    }
    
    static displayErrors(errors, formId) {
        // Clear previous errors
        const form = document.getElementById(formId);
        if (!form) return;
        
        form.querySelectorAll('.is-invalid').forEach(el => {
            el.classList.remove('is-invalid');
        });
        
        form.querySelectorAll('.invalid-feedback').forEach(el => {
            el.remove();
        });
        
        // Display new errors
        for (const [field, message] of Object.entries(errors)) {
            const input = form.querySelector(`[name="${field}"]`);
            if (input) {
                input.classList.add('is-invalid');
                
                const feedback = document.createElement('div');
                feedback.className = 'invalid-feedback';
                feedback.textContent = message;
                
                input.parentNode.appendChild(feedback);
            }
        }
    }
}

/**
 * WebSocket manager for real-time updates
 */
class WebSocketManager {
    constructor() {
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.handlers = {};
    }
    
    connect() {
        try {
            this.socket = new WebSocket(CONFIG.WEBSOCKET_URL);
            
            this.socket.onopen = () => {
                console.log('WebSocket connected');
                this.reconnectAttempts = 0;
                this.emit('connected');
            };
            
            this.socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.emit(data.type, data.payload);
                } catch (error) {
                    console.error('WebSocket message parse error:', error);
                }
            };
            
            this.socket.onclose = () => {
                console.log('WebSocket disconnected');
                this.emit('disconnected');
                this.attemptReconnect();
            };
            
            this.socket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.emit('error', error);
            };
            
        } catch (error) {
            console.error('WebSocket connection error:', error);
        }
    }
    
    disconnect() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
    }
    
    send(type, payload) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({ type, payload }));
        }
    }
    
    on(event, handler) {
        if (!this.handlers[event]) {
            this.handlers[event] = [];
        }
        this.handlers[event].push(handler);
    }
    
    off(event, handler) {
        if (this.handlers[event]) {
            this.handlers[event] = this.handlers[event].filter(h => h !== handler);
        }
    }
    
    emit(event, data) {
        if (this.handlers[event]) {
            this.handlers[event].forEach(handler => handler(data));
        }
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            
            setTimeout(() => {
                this.connect();
            }, this.reconnectDelay * this.reconnectAttempts);
        }
    }
}

// Global instances
window.AuthManager = AuthManager;
window.ApiClient = ApiClient;
window.CameraManager = CameraManager;
window.FaceCaptureSession = FaceCaptureSession;
window.RecognitionSystem = RecognitionSystem;
window.UIUtils = UIUtils;
window.FormValidator = FormValidator;
window.WebSocketManager = WebSocketManager;

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    // Check authentication status
    if (AuthManager.isAuthenticated()) {
        AppState.isAuthenticated = true;
    }
    
    // Initialize tooltips and popovers
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    console.log('Face Recognition System initialized');
});
