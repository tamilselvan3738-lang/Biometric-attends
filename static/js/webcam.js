class WebcamHandler {
    constructor(videoElementId, canvasElementId = null) {
        this.videoElement = document.getElementById(videoElementId);
        this.canvasElement = canvasElementId ? document.getElementById(canvasElementId) : document.createElement('canvas');
        this.stream = null;
    }

    async start() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error("Webcam access not supported by this browser.");
        }

        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480, facingMode: "user" },
                audio: false
            });
            this.videoElement.srcObject = this.stream;
            await this.videoElement.play();
            return true;
        } catch (err) {
            console.error("Error accessing webcam: ", err);
            throw err;
        }
    }

    stop() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.videoElement.srcObject = null;
            this.stream = null;
        }
    }

    snap() {
        if (!this.stream) return null;
        
        // Downscale snap frame for fast network transport and low CPU latency
        const width = 320;
        const height = 240;
        
        this.canvasElement.width = width;
        this.canvasElement.height = height;
        
        const ctx = this.canvasElement.getContext('2d');
        // Mirror the canvas image to match the video mirror effect
        ctx.translate(width, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(this.videoElement, 0, 0, width, height);
        
        // Return base64 string
        return this.canvasElement.toDataURL('image/jpeg', 0.85);
    }
}
