# Biometric Attendance System

A modern Django-based web application with computer vision features. It uses HTML5 Webcam streams and OpenCV face recognition matching algorithms to register arrival and departure shifts for staff.

---

## 🌟 Key Features

### 👤 Super Admin Controls
- Add, modify, or disable Administrative accounts.
- Set global system configuration parameters (daily lateness thresholds, face match ratios, etc.).
- Update corporate profiles and logos.
- Review global attendance analytics.

### 💼 Administrator Controls
- Manage employee directory profiles and documents.
- Process pending leave request submissions.
- Review biometric registration logs and daily attendance sheets.
- Publish company-wide announcements.

### 🧑‍💼 Employee Portal
- Enroll biometric face templates using web cameras.
- Clock In and Clock Out using biometric facial recognition.
- Apply for leave applications and monitor approvals.
- View personal attendance histories.
- Download monthly performance logs (as CSV).

---

## 📦 Tech Stack
- **Backend Framework**: Django 4.2 & Django REST Framework (DRF)
- **Computer Vision**: OpenCV (Haar Cascades for detection, Pearson Correlation Coefficient for similarity matching)
- **Database**: SQLite (built-in file database)
- **Frontend Layer**: Bootstrap 5, HTML5 Canvas/Webcam API, Vanilla CSS (Glassmorphism layout)

---

## ⚙️ Installation & Development Setup

### 1. Requirements
Ensure you have **Python 3.10+** and a standard web camera.

### 2. Setup environment
```powershell
# Clone or copy project, navigate to root directory, and run:
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Generate Database & Superuser
```powershell
python manage.py migrate
# A default user is pre-seeded with username 'admin' and password 'admin123'
```

### 4. Run Application
```powershell
python manage.py runserver
```
Visit `http://127.0.0.1:8000/` and sign in.
