# Production Deployment Guide
## Multi-Camera Intrusion Detection System v1.1.0

This guide covers production deployment, configuration, security hardening, and operational procedures.

---

## 📋 **Table of Contents**

1. [Prerequisites](#prerequisites)
2. [Hardware Requirements](#hardware-requirements)
3. [Software Requirements](#software-requirements)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Security Hardening](#security-hardening)
7. [Database Setup](#database-setup)
8. [User Management](#user-management)
9. [Camera Configuration](#camera-configuration)
10. [Alert Setup](#alert-setup)
11. [System Startup](#system-startup)
12. [Monitoring & Maintenance](#monitoring--maintenance)
13. [Backup & Recovery](#backup--recovery)
14. [Troubleshooting](#troubleshooting)
15. [Performance Tuning](#performance-tuning)

---

## 🔧 **Prerequisites**

### Operating System
- **Recommended**: Ubuntu 20.04 LTS or Ubuntu 22.04 LTS
- **Supported**: Debian 11+, Fedora 35+, Windows 10/11
- **Architecture**: x86_64 (AMD64)

### User Permissions
```bash
# Create dedicated system user (recommended)
sudo adduser --system --group intrusion-detection
sudo usermod -aG video intrusion-detection  # Camera access
sudo usermod -aG audio intrusion-detection  # Audio alerts (optional)
```

### System Updates
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y \
    python3.10 \
    python3.10-dev \
    python3-pip \
    git \
    build-essential \
    cmake \
    pkg-config \
    libopencv-dev \
    libssl-dev \
    libpq-dev \
    postgresql-client \
    ffmpeg \
    v4l-utils
```

---

## 💻 **Hardware Requirements**

### Minimum Requirements (3 cameras @ 720p)
- **CPU**: Intel Core i5-8th gen or AMD Ryzen 5 3000 series
- **RAM**: 8 GB
- **Storage**: 100 GB SSD (500 GB for recordings)
- **GPU**: Optional, CPU-only mode supported
- **Network**: 100 Mbps Ethernet (for IP cameras)

### Recommended Requirements (3 cameras @ 1080p)
- **CPU**: Intel Core i7-10th gen or AMD Ryzen 7 4000 series
- **RAM**: 16 GB
- **Storage**: 256 GB SSD + 2 TB HDD (recordings)
- **GPU**: NVIDIA RTX 3060 (6 GB VRAM) or better
- **Network**: 1 Gbps Ethernet

### High-Performance Setup (10+ cameras @ 1080p)
- **CPU**: Intel Core i9-12th gen or AMD Ryzen 9 5000 series
- **RAM**: 32 GB DDR4
- **Storage**: 512 GB NVMe SSD + 8 TB HDD RAID
- **GPU**: NVIDIA RTX 4070 Ti (12 GB VRAM) or better
- **Network**: 10 Gbps Ethernet

---

## 📦 **Software Requirements**

### Python Environment
```bash
# Install Python 3.10
sudo apt install -y python3.10 python3.10-venv python3.10-dev

# Verify installation
python3.10 --version  # Should output 3.10.x
```

### NVIDIA GPU Support (Optional)
```bash
# Install NVIDIA drivers
sudo apt install -y nvidia-driver-525

# Install CUDA Toolkit 12.0
wget https://developer.download.nvidia.com/compute/cuda/12.0.0/local_installers/cuda_12.0.0_525.60.13_linux.run
sudo sh cuda_12.0.0_525.60.13_linux.run

# Add to PATH
echo 'export PATH=/usr/local/cuda-12.0/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.0/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc

# Verify installation
nvidia-smi
nvcc --version
```

### PostgreSQL Database (Production)
```bash
# Install PostgreSQL 14
sudo apt install -y postgresql-14 postgresql-contrib

# Start service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql <<EOF
CREATE DATABASE intrusion_detection;
CREATE USER iduser WITH ENCRYPTED PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE intrusion_detection TO iduser;
\q
EOF
```

---

## 🚀 **Installation**

### 1. Clone Repository
```bash
# Clone from GitHub
git clone https://github.com/Sherin-SEF-AI/Multi-Camera-Intrusion-Detection-System.git
cd Multi-Camera-Intrusion-Detection-System

# Or use provided release archive
tar -xzf intrusion-detection-v1.1.0.tar.gz
cd intrusion-detection-v1.1.0
```

### 2. Create Virtual Environment
```bash
# Create virtual environment
python3.10 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate  # Windows
```

### 3. Install Dependencies
```bash
# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install requirements (CPU-only)
pip install -r requirements.txt

# OR install with GPU support
pip install -r requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### 4. Download AI Models
```bash
# Create models directory
mkdir -p app/models

# YOLOv8 models will auto-download on first run
# Alternatively, pre-download:
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt -O app/models/yolov8n.pt
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8s.pt -O app/models/yolov8s.pt
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8m.pt -O app/models/yolov8m.pt
```

---

## ⚙️ **Configuration**

### 1. Copy Configuration Template
```bash
cp config/config.yaml config/config.prod.yaml
```

### 2. Edit Production Configuration
```yaml
# config/config.prod.yaml

app:
  name: "Production Intrusion Detection System"
  version: "1.1.0"
  debug: false  # IMPORTANT: Set to false in production
  log_level: "INFO"

cameras:
  auto_detect: true
  num_cameras: 3
  default_resolution: [1920, 1080]  # 1080p
  default_fps: 30

detection:
  model: "yolov8m.pt"  # Medium model for balance
  confidence_threshold: 0.5
  device: "cuda"  # Use GPU if available
  enable_gpu: true
  half_precision: true  # FP16 for faster inference

database:
  type: "postgresql"  # Use PostgreSQL in production
  postgresql:
    host: "localhost"
    port: 5432
    database: "intrusion_detection"
    user: "iduser"
    password: "your_secure_password"  # Use environment variable

authentication:
  session_timeout: 1800  # 30 minutes
  max_login_attempts: 5
  lockout_duration: 900  # 15 minutes
  password_min_length: 12  # Stronger passwords in production
  require_strong_password: true

audit_logging:
  enabled: true
  log_to_database: true
  log_to_file: true
  retention_days: 365  # 1 year for compliance

alerts:
  email:
    enabled: true
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    use_tls: true
    sender_email: "alerts@yourcompany.com"
    sender_password: "${SMTP_PASSWORD}"  # Use environment variable
    recipients:
      - "security@yourcompany.com"
      - "admin@yourcompany.com"

recording:
  enabled: true
  mode: "event_triggered"
  codec: "h264"
  quality: "high"
  retention_days: 30
  max_storage_gb: 500
```

### 3. Environment Variables
```bash
# Create .env file
cat > .env <<EOF
# Database
DB_PASSWORD=your_secure_database_password

# Email Alerts
SMTP_PASSWORD=your_smtp_password

# Twilio SMS (optional)
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token

# Security
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
EOF

# Secure permissions
chmod 600 .env
```

---

## 🔒 **Security Hardening**

### 1. Create Admin User
```bash
# Run initial setup script
python3 scripts/create_admin.py

# Or manually via Python
python3 <<EOF
from app.database.database_manager import DatabaseManager
from app.security.auth_manager import AuthenticationManager
from app.database.models import UserRole

config = {'database': {'url': 'postgresql://iduser:password@localhost/intrusion_detection'}}
db = DatabaseManager(config)
db.initialize()

auth = AuthenticationManager(db, config)
user = auth.create_user(
    username="admin",
    password="YourSecurePassword123!",
    email="admin@yourcompany.com",
    full_name="System Administrator",
    role=UserRole.ADMIN
)
print(f"Admin user created: {user.username}")
EOF
```

### 2. File Permissions
```bash
# Set proper ownership
sudo chown -R intrusion-detection:intrusion-detection /opt/intrusion-detection

# Secure configuration files
chmod 600 config/config.prod.yaml
chmod 600 .env

# Secure database directory
chmod 700 database/
```

### 3. Firewall Configuration
```bash
# Allow only necessary ports
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp  # SSH (restrict to specific IPs)
sudo ufw allow from 192.168.1.0/24 to any port 8000  # GUI access (internal network only)
sudo ufw enable
```

### 4. SSL/TLS Configuration (if using web interface)
```bash
# Generate self-signed certificate (for testing)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Or use Let's Encrypt (for production)
sudo apt install certbot
sudo certbot certonly --standalone -d intrusion.yourcompany.com
```

---

## 🗄️ **Database Setup**

### 1. Initialize Database
```bash
# Run database initialization
python3 -c "
from app.database.database_manager import DatabaseManager
from app.utils.config_loader import ConfigLoader

config = ConfigLoader('config/config.prod.yaml')
db = DatabaseManager(config.get_all())
db.initialize()
print('Database initialized successfully')
"
```

### 2. Create Indexes (Performance)
```sql
-- Connect to database
psql -U iduser -d intrusion_detection

-- Create indexes
CREATE INDEX idx_events_timestamp ON events(timestamp);
CREATE INDEX idx_events_severity ON events(severity);
CREATE INDEX idx_detections_timestamp ON detections(timestamp);
CREATE INDEX idx_tracks_camera_id ON tracks(camera_id);
CREATE INDEX idx_system_logs_timestamp ON system_logs(created_at);
CREATE INDEX idx_system_logs_level ON system_logs(level);

-- Analyze tables
ANALYZE;
```

### 3. Database Backup Script
```bash
# Create backup script
cat > scripts/backup_database.sh <<'EOF'
#!/bin/bash
BACKUP_DIR="/var/backups/intrusion-detection"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup database
pg_dump -U iduser intrusion_detection | gzip > "$BACKUP_DIR/db_backup_$DATE.sql.gz"

# Keep only last 30 days
find $BACKUP_DIR -name "db_backup_*.sql.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR/db_backup_$DATE.sql.gz"
EOF

chmod +x scripts/backup_database.sh

# Add to crontab (daily at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/intrusion-detection/scripts/backup_database.sh") | crontab -
```

---

## 👥 **User Management**

### Create Additional Users
```python
# scripts/create_users.py
from app.database.database_manager import DatabaseManager
from app.security.auth_manager import AuthenticationManager
from app.database.models import UserRole
from app.utils.config_loader import ConfigLoader

config = ConfigLoader('config/config.prod.yaml')
db = DatabaseManager(config.get_all())
db.initialize()

auth = AuthenticationManager(db, config.get_all())

# Create operator user
operator = auth.create_user(
    username="operator1",
    password="SecureOperator123!",
    email="operator1@yourcompany.com",
    full_name="Security Operator",
    role=UserRole.OPERATOR
)

# Create viewer user
viewer = auth.create_user(
    username="viewer1",
    password="SecureViewer123!",
    email="viewer1@yourcompany.com",
    full_name="Security Viewer",
    role=UserRole.VIEWER
)

print("Users created successfully")
```

Run script:
```bash
python3 scripts/create_users.py
```

---

## 📷 **Camera Configuration**

### 1. List Available Cameras
```bash
# List USB cameras
v4l2-ctl --list-devices

# Test camera
ffplay /dev/video0
```

### 2. Configure Cameras in config.yaml
```yaml
cameras:
  camera_configs:
    - id: 0
      name: "Main Entrance"
      resolution: [1920, 1080]
      fps: 30
      enabled: true
    - id: 1
      name: "Parking Lot"
      resolution: [1920, 1080]
      fps: 25
      enabled: true
    - id: 2
      name: "Back Door"
      resolution: [1280, 720]
      fps: 30
      enabled: true
```

### 3. Camera Permissions
```bash
# Add user to video group
sudo usermod -aG video $USER

# Or for service user
sudo usermod -aG video intrusion-detection
```

---

## 🚨 **Alert Setup**

### Email Configuration (Gmail)
```yaml
alerts:
  email:
    enabled: true
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    use_tls: true
    sender_email: "your-email@gmail.com"
    sender_password: "${SMTP_PASSWORD}"  # App-specific password
    recipients:
      - "security@yourcompany.com"
```

**Gmail App Password**: https://myaccount.google.com/apppasswords

### SMS Configuration (Twilio)
```yaml
alerts:
  sms:
    enabled: true
    account_sid: "${TWILIO_ACCOUNT_SID}"
    auth_token: "${TWILIO_AUTH_TOKEN}"
    from_number: "+1234567890"
    to_numbers:
      - "+1987654321"
      - "+1555555555"
```

### Webhook Configuration (Slack, Discord, etc.)
```yaml
alerts:
  webhook:
    enabled: true
    url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    method: "POST"
    headers:
      Content-Type: "application/json"
```

---

## 🏃 **System Startup**

### 1. Manual Start
```bash
# Activate virtual environment
source venv/bin/activate

# Start with production config
python3 main.py --config config/config.prod.yaml
```

### 2. Systemd Service (Recommended)
```bash
# Create service file
sudo cat > /etc/systemd/system/intrusion-detection.service <<EOF
[Unit]
Description=Multi-Camera Intrusion Detection System
After=network.target postgresql.service

[Service]
Type=simple
User=intrusion-detection
Group=intrusion-detection
WorkingDirectory=/opt/intrusion-detection
Environment="PATH=/opt/intrusion-detection/venv/bin"
EnvironmentFile=/opt/intrusion-detection/.env
ExecStart=/opt/intrusion-detection/venv/bin/python3 main.py --config config/config.prod.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable intrusion-detection
sudo systemctl start intrusion-detection

# Check status
sudo systemctl status intrusion-detection
```

### 3. View Logs
```bash
# Service logs
sudo journalctl -u intrusion-detection -f

# Application logs
tail -f logs/intrusion_detection.log
```

---

## 📊 **Monitoring & Maintenance**

### Health Check Script
```bash
# scripts/health_check.sh
#!/bin/bash

# Check service status
if ! systemctl is-active --quiet intrusion-detection; then
    echo "ERROR: Service is not running"
    exit 1
fi

# Check database connection
psql -U iduser -d intrusion_detection -c "SELECT 1" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "ERROR: Database connection failed"
    exit 1
fi

# Check disk space
DISK_USAGE=$(df -h /var/recordings | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 90 ]; then
    echo "WARNING: Disk usage is ${DISK_USAGE}%"
fi

echo "System health: OK"
```

### Monitoring Metrics
```python
# scripts/get_metrics.py
from app.database.database_manager import DatabaseManager
from app.utils.config_loader import ConfigLoader
from datetime import datetime, timedelta

config = ConfigLoader('config/config.prod.yaml')
db = DatabaseManager(config.get_all())

# Get statistics for last 24 hours
with db.session_scope() as session:
    yesterday = datetime.now() - timedelta(hours=24)

    # Count detections
    detections = session.query(Detection).filter(
        Detection.timestamp >= yesterday
    ).count()

    # Count events
    events = session.query(Event).filter(
        Event.timestamp >= yesterday
    ).count()

    # Count critical events
    critical = session.query(Event).filter(
        Event.timestamp >= yesterday,
        Event.severity == Severity.CRITICAL
    ).count()

    print(f"Detections (24h): {detections}")
    print(f"Events (24h): {events}")
    print(f"Critical Events (24h): {critical}")
```

---

## 💾 **Backup & Recovery**

### Automated Backup
```bash
# Full system backup script
cat > scripts/full_backup.sh <<'EOF'
#!/bin/bash
BACKUP_DIR="/var/backups/intrusion-detection"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Database backup
pg_dump -U iduser intrusion_detection | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

# Configuration backup
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" config/

# Models backup
tar -czf "$BACKUP_DIR/models_$DATE.tar.gz" app/models/

echo "Backup completed: $DATE"
EOF

chmod +x scripts/full_backup.sh
```

### Restore Procedure
```bash
# Restore database
gunzip -c db_20240101_020000.sql.gz | psql -U iduser intrusion_detection

# Restore configuration
tar -xzf config_20240101_020000.tar.gz

# Restore models
tar -xzf models_20240101_020000.tar.gz

# Restart service
sudo systemctl restart intrusion-detection
```

---

## 🔍 **Troubleshooting**

### Common Issues

#### 1. Camera Not Detected
```bash
# Check camera permissions
ls -l /dev/video*

# Test camera
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --all

# Check user permissions
groups $USER  # Should include 'video'
```

#### 2. GPU Not Detected
```bash
# Check NVIDIA driver
nvidia-smi

# Check CUDA
nvcc --version

# Test PyTorch CUDA
python3 -c "import torch; print(torch.cuda.is_available())"
```

#### 3. Database Connection Failed
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Test connection
psql -U iduser -d intrusion_detection

# Check logs
sudo tail -f /var/log/postgresql/postgresql-14-main.log
```

#### 4. High CPU Usage
```bash
# Check system resources
top -p $(pgrep -f "python3 main.py")

# Reduce detection interval in config
detection:
  detection_interval: 3  # Process every 3rd frame

# Reduce resolution
cameras:
  default_resolution: [1280, 720]  # 720p instead of 1080p
```

---

## ⚡ **Performance Tuning**

### 1. GPU Optimization
```yaml
detection:
  device: "cuda"
  enable_gpu: true
  half_precision: true  # FP16 for 2x speed
  batch_size: 4  # Process multiple frames at once
```

### 2. CPU Optimization
```yaml
performance:
  max_threads: 12  # Set to CPU core count
  detection_interval: 2  # Skip some frames
```

### 3. Database Optimization
```sql
-- Increase shared buffers (PostgreSQL)
ALTER SYSTEM SET shared_buffers = '4GB';
ALTER SYSTEM SET effective_cache_size = '12GB';
ALTER SYSTEM SET work_mem = '64MB';

-- Restart PostgreSQL
sudo systemctl restart postgresql
```

### 4. Storage Optimization
```yaml
recording:
  codec: "h265"  # Better compression than h264
  quality: "medium"  # Balance quality vs size
  retention_days: 14  # Keep 2 weeks only
```

---

## 📞 **Support**

For issues and support:
- **GitHub Issues**: https://github.com/Sherin-SEF-AI/Multi-Camera-Intrusion-Detection-System/issues
- **Documentation**: See README.md and QUICKSTART.md
- **Email**: support@yourcompany.com

---

**System Version**: 1.1.0
**Last Updated**: 2024
**Deployment Status**: Production-Ready ✅
