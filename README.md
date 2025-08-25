# 🍄 Mushroom Environmental Control System

A comprehensive web-based environmental monitoring and control system for automated mushroom cultivation using Raspberry Pi.

## Features

### 🌡️ Environmental Monitoring
- **Temperature & Humidity**: DHT22 sensor for precise readings
- **CO2 Levels**: MQ-135 or similar sensor for air quality monitoring
- **Light Intensity**: Photoresistor for grow light management
- **Real-time Dashboard**: Live updates via WebSocket

### 🎛️ Automated Controls
- **Fogger System**: Automatic misting based on humidity levels
- **Exhaust Fan**: Air circulation control
- **LED Grow Lights**: Automated lighting schedule
- **Manual Override**: Web-based control interface

### 📊 Data Management
- **Dual Database Support**: MongoDB Atlas (cloud) with SQLite fallback
- **Automatic Failover**: Seamless switching when WiFi is lost
- **Historical Data**: Charts and tables for trend analysis
- **Data Export**: Easy access to sensor readings

### 🍄 Mushroom-Specific Features
- **Growth Phase Tracking**: Inoculation → Colonization → Pinning → Fruiting
- **Phase-Specific Controls**: Automated adjustments per growth stage
- **Health Status Monitoring**: Real-time condition assessment
- **Optimal Range Alerts**: Visual indicators for environmental conditions

## Hardware Requirements

### Raspberry Pi Setup
- Raspberry Pi 4 (recommended) or Pi 3B+
- MicroSD card (32GB+)
- Power supply (5V 3A)

### Sensors
- **DHT22**: Temperature and humidity sensor
- **MCP3008**: 8-channel ADC for analog sensors
- **Photoresistor**: Light intensity measurement
- **MQ-135**: CO2/air quality sensor (or similar)

### Control Hardware
- **Relay Module**: For fogger, fan, and light control
- **12V Fogger/Mister**: Ultrasonic or similar
- **Exhaust Fan**: 12V computer fan or similar
- **LED Grow Lights**: Full spectrum recommended
- **Status LEDs**: Visual system status indicators

### GPIO Pin Configuration
```python
GPIO_CONFIG = {
    # Sensors
    'DHT22_PIN': 4,              # Temperature & Humidity
    'LIGHT_SENSOR_PIN': 0,       # ADC Channel 0
    'CO2_SENSOR_PIN': 1,         # ADC Channel 1
    
    # Controls
    'FOGGER_PIN': 18,            # Fogger relay
    'FAN_PIN': 19,               # Fan control
    'LED_LIGHTS_PIN': 21,        # Grow lights
    
    # Status LEDs
    'STATUS_LED_GREEN': 26,      # System OK
    'STATUS_LED_RED': 16,        # Error
    'STATUS_LED_BLUE': 13,       # WiFi Connected
}
```

## Installation

### 1. System Prerequisites
```bash
# Update Raspberry Pi OS
sudo apt update && sudo apt upgrade -y

# Install Python dependencies
sudo apt install python3-pip python3-venv git -y

# Install system libraries for GPIO
sudo apt install python3-dev python3-gpiozero -y
```

### 2. Clone Repository
```bash
git clone <your-repo-url>
cd mushroom-control-system
```

### 3. Python Environment
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt
```

### 4. Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

Update `.env` with your MongoDB Atlas connection string and other settings.

### 5. Hardware Connections
Connect sensors and control devices according to the GPIO configuration in `config.py`.

## Usage

### Starting the System
```bash
# Activate virtual environment
source venv/bin/activate

# Run the application
python app.py
```

The system will:
1. Initialize GPIO pins and sensors
2. Connect to databases (MongoDB → SQLite fallback)
3. Start the web server on port 5000
4. Automatically open browser to `http://localhost:5000`

### Web Interface
- **Login**: Default password is `admin123` (change in .env)
- **Dashboard**: Real-time sensor readings and controls
- **Controls**: Manual override for fogger, fan, and lights
- **Phase Management**: Set current mushroom growth phase
- **Historical Data**: Charts and tables of past readings

### Remote Access
To access from other devices on your network:
```bash
# Find your Pi's IP address
hostname -I

# Access via browser at: http://YOUR_PI_IP:5000
```

## Mushroom Growth Phases

### 1. Inoculation (14 days)
- Temperature: 20-22°C
- Humidity: 60-70%
- Light: Not needed
- Focus: Sterile conditions

### 2. Colonization (21 days)
- Temperature: 22-24°C
- Humidity: 70-80%
- Light: Not needed
- Focus: Mycelium growth

### 3. Pin Formation (7 days)
- Temperature: 18-20°C
- Humidity: 85-95%
- Light: Required (12 hours/day)
- Focus: Trigger fruiting

### 4. Fruiting (14 days)
- Temperature: 18-22°C
- Humidity: 80-90%
- Light: Required (12 hours/day)
- Focus: Mushroom development

## Automatic Controls

The system automatically manages:

### Humidity Control
- **Fogger**: Activates when humidity drops below optimal range
- **Fan**: Activates when humidity exceeds optimal range
- **Duration**: Configurable misting cycles

### Light Management
- **Schedule**: 6 AM - 6 PM during light-required phases
- **Intensity**: Full spectrum LED grow lights
- **Phase-based**: Only active during pinning and fruiting

### Temperature Regulation
- **Monitoring**: Continuous temperature tracking
- **Alerts**: Visual warnings for out-of-range conditions
- **Future**: Heating element control (configurable)

## Database Configuration

### MongoDB Atlas (Primary)
- Cloud-based storage
- Automatic scaling
- Global accessibility
- Requires internet connection

### SQLite (Fallback)
- Local storage in `sensor_data.db`
- No internet required
- Automatic failover
- Data sync when reconnected

## API Endpoints

### Sensor Data
- `GET /api/current` - Current sensor readings
- `GET /api/latest` - Recent readings (last 10)
- `GET /api/history` - Historical data
- `GET /api/status` - System status

### Controls
- `POST /api/control/fogger` - Control fogger
- `POST /api/control/fan` - Control fan speed
- `POST /api/control/lights` - Control grow lights
- `POST /api/phase` - Set mushroom growth phase

## Troubleshooting

### GPIO Issues
```bash
# Check GPIO permissions
sudo usermod -a -G gpio $USER

# Restart after group change
sudo reboot
```

### Sensor Readings
- Verify wiring connections
- Check sensor power (3.3V/5V)
- Review GPIO pin assignments
- Monitor system logs

### Database Connection
- Verify MongoDB URI in .env
- Check internet connectivity
- SQLite fallback should work offline
- Monitor connection status in dashboard

### Web Access
- Ensure port 5000 is open
- Check firewall settings
- Verify Pi's IP address
- Try localhost:5000 directly on Pi

## Development

### Running in Simulation Mode
If GPIO libraries aren't available, the system runs in simulation mode with realistic sensor data.

### Custom Sensors
Extend the `SensorService` class in `app.py` to add new sensors.

### Custom Controls
Add new control functions in `GPIOControlService` class.

## Safety Considerations

- **Electrical Safety**: Use proper relays for high-voltage devices
- **Moisture Protection**: Protect electronics from humidity
- **Ventilation**: Ensure adequate air circulation
- **Fire Safety**: Monitor heating elements and electrical connections
- **Food Safety**: Use food-grade materials for growing containers

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

For issues, questions, or contributions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review system logs for error details