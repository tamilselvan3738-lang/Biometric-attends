class AttendanceScanner {
    constructor(videoElementId, actionUrl, redirectUrl, detectFaceUrl = null) {
        this.webcam = new WebcamHandler(videoElementId);
        this.actionUrl = actionUrl;
        this.redirectUrl = redirectUrl;
        this.detectFaceUrl = detectFaceUrl;
        this.statusText = document.getElementById('status-text');
        this.scanBtn = document.getElementById('scan-btn');
        this.faceBox = document.getElementById('face-bounding-box');
        this.isScanning = false;
        this.scanTimer = null;
    }

    async init() {
        try {
            await this.webcam.start();
            this.statusText.textContent = "Camera Ready. Align your face inside the frame.";
            if (this.scanBtn) {
                this.scanBtn.disabled = false;
                this.scanBtn.addEventListener('click', () => this.capture());
            }
            if (this.detectFaceUrl && this.faceBox) {
                this.startTracking();
            }
        } catch (err) {
            this.statusText.textContent = "Error: Webcam access denied or unavailable.";
            this.statusText.classList.add('text-danger');
        }
    }

    startTracking() {
        this.stopTracking();
        this.scanTimer = setInterval(() => this.trackFace(), 500);
    }

    stopTracking() {
        if (this.scanTimer) {
            clearInterval(this.scanTimer);
            this.scanTimer = null;
        }
    }

    async trackFace() {
        if (this.isScanning || !this.webcam.stream) return;
        
        const base64 = this.webcam.snap();
        if (!base64) return;

        try {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            const response = await fetch(this.detectFaceUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ image: base64 })
            });
            const data = await response.json();
            if (data.success && data.bbox && this.faceBox) {
                const videoWidth = 320;
                const videoHeight = 240;
                const video = this.webcam.videoElement;
                const displayWidth = video.clientWidth;
                const displayHeight = video.clientHeight;
                
                const scaleX = displayWidth / videoWidth;
                const scaleY = displayHeight / videoHeight;
                
                // Mirrored coordinate mapping
                const displayX = (videoWidth - data.bbox.x - data.bbox.w) * scaleX;
                const displayY = data.bbox.y * scaleY;
                
                this.faceBox.style.left = displayX + 'px';
                this.faceBox.style.top = displayY + 'px';
                this.faceBox.style.width = (data.bbox.w * scaleX) + 'px';
                this.faceBox.style.height = (data.bbox.h * scaleY) + 'px';
                this.faceBox.style.display = 'block';
            } else if (this.faceBox) {
                this.faceBox.style.display = 'none';
            }
        } catch (err) {
            if (this.faceBox) this.faceBox.style.display = 'none';
        }
    }

    async capture() {
        if (this.isScanning) return;
        this.isScanning = true;
        this.stopTracking();
        if (this.faceBox) this.faceBox.style.display = 'none';
        
        this.scanBtn.disabled = true;

        const images = [];
        for (let i = 1; i <= 5; i++) {
            this.statusText.textContent = `Capturing live clips... (${i}/5)`;
            this.scanBtn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status"></span> Capturing ${i}/5...`;
            
            const base64 = this.webcam.snap();
            if (base64) {
                images.push(base64);
            }
            await new Promise(resolve => setTimeout(resolve, 200));
        }

        if (images.length === 0) {
            this.statusText.textContent = "Error capturing clips. Try again.";
            this.isScanning = false;
            this.scanBtn.innerHTML = 'Capture & Verify';
            this.scanBtn.disabled = false;
            this.startTracking();
            return;
        }

        this.statusText.textContent = "Analyzing live clips end-to-end...";
        this.scanBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span> Processing...';

        try {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            const response = await fetch(this.actionUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ images: images })
            });

            const data = await response.json();
            if (data.success) {
                this.statusText.textContent = "Verification Success! " + data.message;
                this.statusText.className = "webcam-status-text text-success fw-bold";
                setTimeout(() => {
                    window.location.href = this.redirectUrl;
                }, 1500);
            } else {
                this.statusText.textContent = "Failed: " + data.message;
                this.statusText.className = "webcam-status-text text-danger fw-bold";
                this.isScanning = false;
                this.scanBtn.innerHTML = 'Capture & Verify';
                this.scanBtn.disabled = false;
                this.startTracking();
            }
        } catch (err) {
            console.error(err);
            this.statusText.textContent = "Server communication failure.";
            this.statusText.className = "webcam-status-text text-danger fw-bold";
            this.isScanning = false;
            this.scanBtn.innerHTML = 'Capture & Verify';
            this.scanBtn.disabled = false;
            this.startTracking();
        }
    }

    destroy() {
        this.stopTracking();
        this.webcam.stop();
    }
}
