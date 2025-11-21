# Quick Start Guide
## Multi-Camera Intrusion Detection System with PyQt6 GUI

This guide will help you get the system running with your **3 Logitech C270 webcams**.

---

## 📋 Prerequisites

### Hardware
✅ You have **3 Logitech C270 webcams** connected:
- Bus 003 Device 002: Webcam C270
- Bus 003 Device 003: Webcam C270
- Bus 009 Device 005: Webcam C270

### Software
- Python 3.9+ installed
- CUDA-capable GPU (recommended, optional)
- Ubuntu/Linux system

---

## 🚀 Installation

### 1. Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y \
    python3-dev \
    python3-pip \
    libopencv-dev \
    python3-opencv \
    portaudio19-dev \
    python3-pyqt6
```

### 2. Run Setup Script

```bash
cd /path/to/Multi-Camera-Intrusion-Detection-System
bash setup.sh
```

This will:
- Create a virtual environment
- Install all Python dependencies
- Create necessary directories
- Check for CUDA support

### 3. Activate Virtual Environment

```bash
source venv/bin/activate
```

---

## 🎥 Running the Application

### Default Mode (PyQt6 GUI - Recommended)

```bash
python main.py
```

This will:
1. Auto-detect your 3 Logitech C270 webcams
2. Initialize YOLOv8 detection engine (downloads model on first run)
3. Launch the professional PyQt6 GUI
4. Start real-time monitoring

### Alternative: Basic OpenCV Mode

```bash
python main.py --no-gui
```

This shows simple OpenCV windows with detection/tracking overlay (no fancy GUI).

---

## 🖥️ Using the GUI

### Main Interface

The GUI has 5 main tabs:

#### 1. 🎥 **Live Monitoring** (Default View)
- **Camera Grid**: See all 3 cameras in 2x2 layout
- **Real-time Detection**: Green boxes around detected persons
- **Track IDs**: Unique ID for each person
- **Trajectories**: Purple lines showing movement paths
- **Threat Indicator**: Color-coded threat level (Green/Yellow/Orange/Red)
- **Statistics**: Active tracks, persons detected, violations
- **Recent Events**: Live event log

**Controls:**
- Confidence slider: Adjust detection sensitivity
- Layout dropdown: Change camera grid layout
- Show Confidence: Toggle confidence scores
- Show Trajectories: Toggle movement trails

#### 2. 👥 **Person Database**
- **Add Persons**: Register authorized personnel
- **Search**: Find persons by name, email, phone
- **Filter**: By authorization level
- **Color Coding**:
  - 🟢 Green = Authorized
  - 🔵 Blue = Visitor
  - 🔴 Red = Blacklist
  - ⚪ Gray = Unknown

**Actions:**
- ➕ Add Person: Click to register new person
- 👁️ View Details: See full person information
- ✏️ Edit: Modify person details
- 🗑️ Delete: Remove person from database

#### 3. 🚨 **Alerts & Incidents**
- **Event Table**: All security events
- **Filters**: By severity (Critical/High/Medium/Low) and status
- **Event Details**: Full information panel
- **Actions**:
  - ✓ Acknowledge: Mark event as seen
  - ✓ Resolve: Close the incident
  - ⚠️ False Positive: Mark incorrect alerts
  - 🎥 View Video: Watch event recording

#### 4. 📊 **Analytics**
- **Statistics Cards**: Total detections, persons, events
- **Time Range**: Today, Last 7 Days, Last 30 Days, All Time
- **Camera Performance**: FPS, uptime, detections per camera
- **Top Persons**: Most frequently seen individuals
- **Event Breakdown**: Distribution by event type

#### 5. ⚙️ **Settings**
Configure all system parameters:
- **Camera**: Resolution, FPS, buffer size
- **Detection**: Model (YOLOv8n/s/m/l/x), confidence, device (CUDA/CPU)
- **Tracking**: Max age, min hits, IOU threshold
- **Alerts**: Email (SMTP), SMS (Twilio)
- **Recording**: Mode, codec (H.264/H.265), quality, duration

**💾 Remember to click "Save Settings" and restart the system!**

---

## 🛠️ Toolbar Actions

- **▶️ Start System**: Begin monitoring
- **⏸️ Stop System**: Pause monitoring
- **📸 Screenshot**: Capture current view
- **⏺️ Start Recording**: Manual recording control
- **🚨 Emergency Alert**: Trigger immediate alert to all channels

---

## ⌨️ Keyboard Shortcuts

- `F11`: Toggle fullscreen mode
- `Ctrl+Q`: Quit application
- `q`: Quit (when in OpenCV windows)
- `s`: Show statistics (console mode)

---

## 📊 System Status Indicators

**Top Right Corner:**
- **Time**: Current date and time
- **CPU**: CPU usage percentage
- **RAM**: Memory usage percentage

**Bottom Status Bar:**
- **📷 Cameras**: Active cameras / Total cameras
- **🔍 Detections**: Total persons detected
- **🎯 Active Tracks**: Currently tracked persons
- **⚡ FPS**: Detection engine performance

---

## 🎯 First-Time Setup Checklist

### 1. **Verify Cameras Detected**
- Launch the application
- Check status bar shows "📷 Cameras: 3/3"
- If not, check USB connections

### 2. **Download YOLO Model** (First Run Only)
The system will automatically download YOLOv8n.pt (~6MB) on first run.
This may take 1-2 minutes depending on your internet connection.

### 3. **Configure Detection Settings**
1. Go to **Settings** tab
2. Set **Device** to:
   - `cuda` if you have NVIDIA GPU
   - `cpu` if no GPU
3. Click **💾 Save Settings**

### 4. **Register Authorized Persons** (Optional)
1. Go to **Person Database** tab
2. Click **➕ Add Person**
3. Fill in details:
   - Name (required)
   - Authorization Level: "Authorized"
   - Email, Phone (optional)
   - Photo (optional but recommended)
4. Click **Save**

### 5. **Test the System**
1. Start the system (▶️ button in toolbar)
2. Walk in front of cameras
3. Watch for green bounding boxes
4. Check **Live Monitoring** tab shows detections

---

## 🔧 Configuration File

Located at: `config/config.yaml`

### Key Settings to Adjust:

```yaml
# Use your 3 cameras
cameras:
  camera_configs:
    - id: 0
      name: "Front Entrance"
      resolution: [1280, 720]
      fps: 30
      enabled: true
    - id: 1
      name: "Parking Lot"
      resolution: [1280, 720]
      fps: 25
      enabled: true
    - id: 2
      name: "Back Door"
      resolution: [1280, 720]
      fps: 25
      enabled: true

# Adjust detection confidence (lower = more detections, more false positives)
detection:
  confidence_threshold: 0.5

# GPU acceleration
detection:
  device: "cuda"  # or "cpu"
  enable_gpu: true
```

---

## 🐛 Troubleshooting

### Problem: No cameras detected

**Solution:**
```bash
# Check USB cameras
lsusb | grep Logitech

# Check OpenCV can access cameras
python -c "import cv2; print([i for i in range(10) if cv2.VideoCapture(i).isOpened()])"
```

### Problem: Low FPS / Slow performance

**Solutions:**
1. Lower camera resolution in Settings
2. Use smaller YOLO model (yolov8n instead of yolov8s)
3. Enable GPU acceleration if available
4. Reduce number of cameras

### Problem: CUDA out of memory

**Solutions:**
1. Use `yolov8n.pt` (smallest model)
2. Enable `half_precision: true` in config
3. Lower camera resolution
4. Set `device: "cpu"` in settings

### Problem: PyQt6 import error

**Solution:**
```bash
# Install PyQt6
pip install PyQt6

# Or use basic mode
python main.py --no-gui
```

### Problem: Database errors

**Solution:**
```bash
# Delete and recreate database
rm database/intrusion_detection.db
python main.py  # Will recreate automatically
```

---

## 📁 Important Directories

- `logs/`: Application logs (check for errors)
- `recordings/`: Video recordings from events
- `snapshots/`: Screenshots of events
- `database/`: SQLite database file
- `backups/`: Database backups
- `exports/`: Exported reports and data

---

## 💡 Tips for Best Results

1. **Good Lighting**: Ensure cameras have adequate lighting
2. **Camera Angles**: Position cameras at eye level or slightly above
3. **Overlap**: Have some overlap between camera views for better tracking
4. **Start Simple**: Begin with default settings, then adjust
5. **Monitor Logs**: Check `logs/` folder if issues occur
6. **Regular Backups**: Use **Tools → Backup Database** menu option

---

## 🎓 Learning the System

### Recommended Workflow:

1. **Day 1**: Run system, observe detections
2. **Day 2**: Register a few test persons
3. **Day 3**: Configure zones (when zone editor is ready)
4. **Day 4**: Set up email alerts
5. **Day 5**: Review analytics and adjust settings

---

## 📞 Getting Help

If you encounter issues:

1. Check `logs/IntrusionDetection.log`
2. Look for ERROR or CRITICAL messages
3. Check GitHub Issues
4. Provide log excerpts when reporting issues

---

## 🚀 Next Steps

Once comfortable with basics:
- Configure alert emails (Settings → Alerts)
- Set up zones and rules (Zone Editor - coming soon)
- Explore behavioral analysis features
- Fine-tune detection thresholds
- Review analytics to understand patterns

---

**Ready to start? Run:**

```bash
source venv/bin/activate
python main.py
```

**Your professional multi-camera intrusion detection system is ready! 🛡️**
