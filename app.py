import os
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from pymongo import MongoClient
import subprocess
import json

# Import GPIO and sensor libraries
try:
    from gpiozero import DistanceSensor, LED, OutputDevice
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("⚠️ GPIO Zero not available - using simulation mode")

try:
    import adafruit_scd4x
    import board
    import busio
    SCD40_AVAILABLE = True
except ImportError:
    SCD40_AVAILABLE = False
    print("⚠️ SCD40 libraries not available")

try:
    import smbus2
    BH1750_AVAILABLE = True
except ImportError:
    BH1750_AVAILABLE = False
    print("⚠️ BH1750 libraries not available")

# Check if we're running on actual Raspberry Pi hardware
def is_raspberry_pi():
    """Check if running on actual Raspberry Pi hardware"""
    try:
        with open('/proc/cpuinfo', 'r') as f:
            return 'Raspberry Pi' in f.read()
    except:
        return False

# Set simulation mode if not on actual hardware
SIMULATION_MODE = not is_raspberry_pi()
if SIMULATION_MODE:
    print("🖥️ Running in simulation mode (not on actual Raspberry Pi hardware)")
    GPIO_AVAILABLE = False
    SCD40_AVAILABLE = False
    BH1750_AVAILABLE = False

# Import configuration
from config import GPIO_CONFIG, MUSHROOM_CONFIG, SENSOR_CONFIG

# Load environment variables
load_dotenv()

# Constants
DEVICE_ID = "raspberry-pi-01"
SENSOR_READ_INTERVAL = SENSOR_CONFIG['read_interval']
ALERT_THRESHOLDS = MUSHROOM_CONFIG['alert_thresholds']
OPTIMAL_RANGES = MUSHROOM_CONFIG['optimal_ranges']

# Initialize Flask
app = Flask(__name__)
CORS(app)
app.config.update({
    'SECRET_KEY': os.getenv('SECRET_KEY', 'pentaplets'),
    'MONGO_URI': os.getenv('MONGODB_URI'),
    'DASHBOARD_PASSWORD': os.getenv('DASHBOARD_PASSWORD', 'pentaplets')
})

# Initialize SocketIO
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    logger=False,
    engineio_logger=False
)

# ========================
# AUTHENTICATION
# ========================
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'authenticated' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ========================
# BH1750 LIGHT SENSOR CLASS
# ========================
class BH1750:
    """BH1750 Light Sensor Driver"""
    
    # Device I2C address
    DEVICE_ADDRESS = 0x23  # Default address (ADDR pin = LOW)
    # DEVICE_ADDRESS = 0x5C  # Alternative address (ADDR pin = HIGH)
    
    # Measurement modes
    CONTINUOUS_HIGH_RES_MODE = 0x10
    CONTINUOUS_HIGH_RES_MODE_2 = 0x11
    CONTINUOUS_LOW_RES_MODE = 0x13
    ONE_TIME_HIGH_RES_MODE = 0x20
    ONE_TIME_HIGH_RES_MODE_2 = 0x21
    ONE_TIME_LOW_RES_MODE = 0x23
    
    def __init__(self, bus_number=1):
        """Initialize BH1750 sensor"""
        if not BH1750_AVAILABLE:
            self.bus = None
            return
            
        try:
            self.bus = smbus2.SMBus(bus_number)
            self.address = self.DEVICE_ADDRESS
            print(f"✅ BH1750 initialized on I2C bus {bus_number}, address 0x{self.address:02X}")
        except Exception as e:
            print(f"❌ BH1750 initialization failed: {e}")
            self.bus = None
    
    def read_light_level(self):
        """Read light level in lux"""
        if not self.bus:
            return None
            
        try:
            # Send measurement command (one-time high resolution mode)
            self.bus.write_byte(self.address, self.ONE_TIME_HIGH_RES_MODE)
            
            # Wait for measurement (max 180ms)
            time.sleep(0.2)
            
            # Read 2 bytes of data
            data = self.bus.read_i2c_block_data(self.address, 0x00, 2)
            
            # Convert to lux
            light_level = (data[0] << 8 | data[1]) / 1.2
            
            return round(light_level, 1)
            
        except Exception as e:
            print(f"❌ BH1750 read error: {e}")
            return None
    
    def close(self):
        """Close I2C bus"""
        if self.bus:
            self.bus.close()

# ========================
# DATABASE SERVICE
# ========================
class DatabaseService:
    def __init__(self):
        self.local_mongo_client = None
        self.local_mongo_db = None
        self.atlas_mongo_client = None
        self.atlas_mongo_db = None
        self.using_atlas = False
        self.offline_queue = []
        self.setup_databases()
        
    def setup_databases(self):
        """Setup local MongoDB and try to connect to Atlas"""
        # Setup local MongoDB
        self.setup_local_mongodb()
        
        # Try to connect to Atlas
        self.connect_atlas()
        
    def setup_local_mongodb(self):
        """Setup local MongoDB database"""
        try:
            # Connect to local MongoDB (default port 27017)
            self.local_mongo_client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=2000)
            self.local_mongo_db = self.local_mongo_client.sensor_db
            
            # Test connection
            self.local_mongo_client.server_info()
            print("✅ Local MongoDB connected")
            
            # Create indexes for better performance
            self.local_mongo_db.readings.create_index([("device_id", 1), ("server_timestamp", -1)])
            self.local_mongo_db.readings.create_index([("server_timestamp", -1)])
            
        except Exception as e:
            print(f"❌ Local MongoDB setup failed: {e}")
            print("💡 Make sure MongoDB is installed and running locally")
            print("🎭 Using in-memory storage for simulation")
            self.local_mongo_client = None
            self.local_mongo_db = None
            # Use in-memory storage for simulation
            self.simulation_data = []
            
    def connect_atlas(self):
        """Connect to MongoDB Atlas"""
        try:
            if app.config['MONGO_URI']:
                self.atlas_mongo_client = MongoClient(app.config['MONGO_URI'], serverSelectionTimeoutMS=5000)
                self.atlas_mongo_db = self.atlas_mongo_client.sensor_db
                
                # Test connection
                self.atlas_mongo_client.server_info()
                self.using_atlas = True
                print("✅ MongoDB Atlas connected")
                
                # Sync any offline data
                self.sync_offline_data()
                return True
        except Exception as e:
            print(f"⚠️ MongoDB Atlas connection failed: {e}")
            print("📱 Operating in offline mode with local MongoDB")
            self.using_atlas = False
            self.atlas_mongo_client = None
            self.atlas_mongo_db = None
            return False
            
    def sync_offline_data(self):
        """Sync offline data to Atlas when connection is restored"""
        if not self.atlas_mongo_db or not self.local_mongo_db:
            return
            
        try:
            # Get unsynced data from local MongoDB
            unsynced_data = list(self.local_mongo_db.readings.find({
                'synced_to_atlas': {'$ne': True}
            }))
            
            if unsynced_data:
                print(f"🔄 Syncing {len(unsynced_data)} offline records to Atlas...")
                
                # Insert into Atlas
                for doc in unsynced_data:
                    # Remove local MongoDB specific fields
                    doc.pop('_id', None)
                    doc.pop('synced_to_atlas', None)
                    
                    # Insert into Atlas
                    self.atlas_mongo_db.readings.insert_one(doc)
                
                # Mark as synced in local MongoDB
                self.local_mongo_db.readings.update_many(
                    {'synced_to_atlas': {'$ne': True}},
                    {'$set': {'synced_to_atlas': True}}
                )
                
                print(f"✅ Synced {len(unsynced_data)} records to Atlas")
                
        except Exception as e:
            print(f"❌ Sync error: {e}")

    def save_reading(self, data):
        """Save reading to local MongoDB and optionally to Atlas"""
        try:
            # Add timestamp
            data['server_timestamp'] = datetime.utcnow()
            data['device_id'] = DEVICE_ID
            
            # Save to local MongoDB
            if self.local_mongo_db:
                # Mark as not synced initially
                data['synced_to_atlas'] = False
                result = self.local_mongo_db.readings.insert_one(data)
                print(f"📦 Saved to local MongoDB: {result.inserted_id}")
                
                # Try to save to Atlas if available
                if self.using_atlas and self.atlas_mongo_db:
                    try:
                        # Remove local MongoDB specific fields
                        atlas_data = data.copy()
                        atlas_data.pop('_id', None)
                        atlas_data.pop('synced_to_atlas', None)
                        
                        self.atlas_mongo_db.readings.insert_one(atlas_data)
                        
                        # Mark as synced in local MongoDB
                        self.local_mongo_db.readings.update_one(
                            {'_id': result.inserted_id},
                            {'$set': {'synced_to_atlas': True}}
                        )
                        print(f"📦 Also saved to Atlas")
                        
                    except Exception as e:
                        print(f"⚠️ Atlas save failed, keeping local only: {e}")
                
                return str(result.inserted_id)
            else:
                # Use in-memory storage for simulation
                if hasattr(self, 'simulation_data'):
                    data['_id'] = len(self.simulation_data) + 1
                    self.simulation_data.append(data)
                    print(f"📦 Saved to simulation storage: {data['_id']}")
                    return str(data['_id'])
                else:
                    print("❌ No storage available")
                    return None
                
        except Exception as e:
            print(f"❌ Save error: {e}")
            return None

    def get_latest_readings(self, limit=10):
        """Get latest readings from local MongoDB or simulation storage"""
        try:
            if self.local_mongo_db:
                cursor = self.local_mongo_db.readings.find({
                    'device_id': DEVICE_ID
                }).sort('server_timestamp', -1).limit(limit)
                
                readings = []
                for doc in cursor:
                    doc['_id'] = str(doc['_id'])
                    if isinstance(doc.get('server_timestamp'), datetime):
                        doc['server_timestamp'] = doc['server_timestamp'].isoformat()
                    readings.append(doc)
                
                print(f"📊 Retrieved {len(readings)} readings from local MongoDB")
                return readings
            elif hasattr(self, 'simulation_data'):
                # Return from simulation storage
                readings = sorted(self.simulation_data, key=lambda x: x['server_timestamp'], reverse=True)[:limit]
                for doc in readings:
                    doc['_id'] = str(doc['_id'])
                    if isinstance(doc.get('server_timestamp'), datetime):
                        doc['server_timestamp'] = doc['server_timestamp'].isoformat()
                print(f"📊 Retrieved {len(readings)} readings from simulation storage")
                return readings
            else:
                print("❌ No storage available")
                return []
                
        except Exception as e:
            print(f"❌ Read error: {e}")
            return []

    def get_historical_data(self, hours=24, limit=500):
        """Get historical data from local MongoDB"""
        try:
            time_threshold = datetime.utcnow() - timedelta(hours=hours)
            
            if self.local_mongo_db:
                cursor = self.local_mongo_db.readings.find({
                    'server_timestamp': {'$gte': time_threshold},
                    'device_id': DEVICE_ID
                }).sort('server_timestamp', -1).limit(limit)
                
                readings = []
                for doc in cursor:
                    doc['_id'] = str(doc['_id'])
                    if isinstance(doc.get('server_timestamp'), datetime):
                        doc['server_timestamp'] = doc['server_timestamp'].isoformat()
                    readings.append(doc)
                
                return readings
            else:
                return []
                
        except Exception as e:
            print(f"❌ Historical read error: {e}")
            return []

    def get_database_status(self):
        """Get current database status"""
        if hasattr(self, 'simulation_data'):
            db_type = 'Simulation Storage'
        elif self.using_atlas:
            db_type = 'MongoDB Atlas'
        else:
            db_type = 'Local MongoDB'
            
        return {
            'local_mongodb': self.local_mongo_db is not None or hasattr(self, 'simulation_data'),
            'atlas_connected': self.using_atlas,
            'database_type': db_type,
            'offline_mode': not self.using_atlas
        }

# Initialize DB service
db_service = DatabaseService()

# ========================
# GPIO CONTROL SERVICE
# ========================
class GPIOControlService:
    def __init__(self):
        self.fogger_active = False
        self.fan_speed = 0
        self.heater_active = False
        self.lights_active = False
        self.setup_gpio()
        
    def setup_gpio(self):
        """Initialize GPIO pins using GPIO Zero"""
        if not GPIO_AVAILABLE or SIMULATION_MODE:
            print("🎭 GPIO simulation mode - no actual hardware control")
            # Create dummy devices for simulation
            self.fogger = type('DummyDevice', (), {'on': lambda *args: print("🌫️ Fogger ON (simulated)"), 'off': lambda *args: print("🌫️ Fogger OFF (simulated)")})()
            self.fan = type('DummyDevice', (), {'on': lambda *args: print("🌬️ Fan ON (simulated)"), 'off': lambda *args: print("🌬️ Fan OFF (simulated)")})()
            self.heater = type('DummyDevice', (), {'on': lambda *args: print("🔥 Heater ON (simulated)"), 'off': lambda *args: print("🔥 Heater OFF (simulated)")})()
            self.lights = type('DummyDevice', (), {'on': lambda *args: print("💡 Lights ON (simulated)"), 'off': lambda *args: print("💡 Lights OFF (simulated)")})()
            
            # Dummy LEDs
            self.status_led_green = type('DummyLED', (), {'on': lambda *args: None, 'off': lambda *args: None})()
            self.status_led_red = type('DummyLED', (), {'on': lambda *args: None, 'off': lambda *args: None})()
            self.status_led_blue = type('DummyLED', (), {'on': lambda *args: None, 'off': lambda *args: None})()
            
            # Set status LED to green (system OK)
            self.status_led_green.on()
            self.status_led_red.off()
            self.status_led_blue.off()
            
            print("✅ GPIO simulation devices initialized")
            return
            
        try:
            # Setup control devices using GPIO Zero
            self.fogger = OutputDevice(GPIO_CONFIG['FOGGER_PIN'])
            self.fan = OutputDevice(GPIO_CONFIG['FAN_PIN'])
            self.heater = OutputDevice(GPIO_CONFIG['HEATER_PIN'])
            self.lights = OutputDevice(GPIO_CONFIG['LED_LIGHTS_PIN'])
            
            # Setup status LEDs
            self.status_led_green = LED(GPIO_CONFIG['STATUS_LED_GREEN'])
            self.status_led_red = LED(GPIO_CONFIG['STATUS_LED_RED'])
            self.status_led_blue = LED(GPIO_CONFIG['STATUS_LED_BLUE'])
            
            # Initialize all outputs to OFF
            self.fogger.off()
            self.fan.off()
            self.heater.off()
            self.lights.off()
            
            # Set status LED to green (system OK)
            self.status_led_green.on()
            self.status_led_red.off()
            self.status_led_blue.off()
            
            print("✅ GPIO Zero devices initialized successfully")
        except Exception as e:
            print(f"❌ GPIO setup error: {e}")
    
    def control_fogger(self, activate=True, duration=None):
        """Control the fogger"""
        if not GPIO_AVAILABLE or SIMULATION_MODE:
            self.fogger_active = activate
            print(f"🌫️ Fogger {'activated' if activate else 'deactivated'} (simulation)")
            return
            
        try:
            if activate:
                self.fogger.on()
                self.fogger_active = True
                print("🌫️ Fogger activated")
                
                if duration:
                    # Auto-turn off after duration
                    threading.Timer(duration, self.control_fogger, [False]).start()
            else:
                self.fogger.off()
                self.fogger_active = False
                print("🌫️ Fogger deactivated")
        except Exception as e:
            print(f"❌ Fogger control error: {e}")
    
    def control_fan(self, speed_percent=0):
        """Control exhaust fan speed (0-100%)"""
        if not GPIO_AVAILABLE or SIMULATION_MODE:
            self.fan_speed = speed_percent
            print(f"🌬️ Fan speed set to {speed_percent}% (simulation)")
            return
            
        try:
            if speed_percent > 0:
                self.fan.on()
            else:
                self.fan.off()
            
            self.fan_speed = speed_percent
            print(f"🌬️ Fan speed set to {speed_percent}%")
        except Exception as e:
            print(f"❌ Fan control error: {e}")
    
    def control_lights(self, activate=True):
        """Control LED grow lights"""
        if not GPIO_AVAILABLE or SIMULATION_MODE:
            self.lights_active = activate
            print(f"💡 Lights {'activated' if activate else 'deactivated'} (simulation)")
            return
            
        try:
            if activate:
                self.lights.on()
            else:
                self.lights.off()
            self.lights_active = activate
            print(f"💡 Lights {'activated' if activate else 'deactivated'}")
        except Exception as e:
            print(f"❌ Light control error: {e}")
    
    def get_control_status(self):
        """Get current control status"""
        return {
            'fogger_active': self.fogger_active,
            'fan_speed': self.fan_speed,
            'heater_active': self.heater_active,
            'lights_active': self.lights_active
        }

# ========================
# SENSOR SERVICE
# ========================
class SensorService:
    def __init__(self):
        self.current_data = {
            'temperature': 22.0,  # Default realistic values
            'humidity': 65.0,
            'co2': 400,
            'light_intensity': 500,
            'water_level': 75.0,
            'timestamp': datetime.utcnow().isoformat(),
            'device_id': DEVICE_ID
        }
        self.scd40 = None
        self.bh1750 = None
        self.water_sensor = None
        self.setup_sensors()
        
    def setup_sensors(self):
        """Initialize sensors"""
        try:
            print("\n🔧 Initializing sensors...")
            
            # I2C setup for SCD40 sensor (pins 3=SDA, 5=SCL)
            if SCD40_AVAILABLE:
                try:
                    print("  🔄 Setting up SCD40...")
                    i2c = busio.I2C(board.SCL, board.SDA)
                    self.scd40 = adafruit_scd4x.SCD4X(i2c)
                    print("  🔄 Starting SCD40 periodic measurement...")
                    self.scd40.start_periodic_measurement()
                    print("  ✅ SCD40 sensor initialized")
                except Exception as e:
                    print(f"  ❌ SCD40 setup failed: {e}")
                    self.scd40 = None
            else:
                print("  ⚠️ SCD40 libraries not available")
            
            # BH1750 light sensor (I2C)
            if BH1750_AVAILABLE:
                try:
                    print("  🔄 Setting up BH1750...")
                    self.bh1750 = BH1750(bus_number=1)
                    if self.bh1750.bus is None:
                        print("  ❌ BH1750 setup failed - bus is None")
                        self.bh1750 = None
                    else:
                        print("  ✅ BH1750 sensor initialized")
                except Exception as e:
                    print(f"  ❌ BH1750 setup failed: {e}")
                    self.bh1750 = None
            else:
                print("  ⚠️ BH1750 libraries not available")
            
            # Setup ultrasonic sensor using GPIO Zero
            if GPIO_AVAILABLE:
                try:
                    print("  🔄 Setting up Ultrasonic sensor...")
                    self.water_sensor = DistanceSensor(
                        echo=GPIO_CONFIG['ULTRASONIC_ECHO_PIN'], 
                        trigger=GPIO_CONFIG['ULTRASONIC_TRIG_PIN'],
                        max_distance=1  # 1 meter max range
                    )
                    print("  ✅ Ultrasonic sensor initialized")
                except Exception as e:
                    print(f"  ❌ Ultrasonic sensor setup failed: {e}")
                    self.water_sensor = None
            else:
                print("  ⚠️ GPIO libraries not available")
            
            # Summary
            print("\n📊 Sensor Status:")
            print(f"  - SCD40: {'✅' if self.scd40 else '❌'}")
            print(f"  - BH1750: {'✅' if self.bh1750 else '❌'}")
            print(f"  - Ultrasonic: {'✅' if self.water_sensor else '❌'}")
            
            if not any([self.scd40, self.bh1750, self.water_sensor]):
                print("⚠️ No sensors available - using simulation mode")
            else:
                print("✅ At least one sensor is available")
            
        except Exception as e:
            print(f"❌ Sensor setup error: {e}")
    
    def read_ultrasonic_distance(self):
        """Read distance from ultrasonic sensor in cm using GPIO Zero"""
        if not self.water_sensor:
            return None
            
        try:
            # GPIO Zero DistanceSensor returns distance in meters
            distance_m = self.water_sensor.distance
            distance_cm = distance_m * 100  # Convert to centimeters
            return round(distance_cm, 2)
        except Exception as e:
            print(f"❌ Ultrasonic sensor error: {e}")
            return None
    
    def calculate_water_level_percentage(self, distance_cm):
        """Convert ultrasonic distance to water level percentage"""
        if distance_cm is None:
            return 75.0  # Default value if sensor fails
        
        reservoir_config = SENSOR_CONFIG['reservoir_config']
        sensor_height = reservoir_config['sensor_height_cm']
        max_depth = reservoir_config['max_depth_cm']
        min_depth = reservoir_config['min_depth_cm']
        
        # Calculate water depth
        water_depth = sensor_height - distance_cm
        
        # Clamp to valid range
        water_depth = max(0, min(max_depth, water_depth))
        
        # Convert to percentage (0% = empty, 100% = full)
        if water_depth <= min_depth:
            return 0.0
        else:
            percentage = ((water_depth - min_depth) / (max_depth - min_depth)) * 100
            return round(percentage, 1)
    
    def read_sensors(self):
        """Read data from actual GPIO sensors or generate simulated data"""
        data = self.current_data.copy()
        
        if SIMULATION_MODE:
            # Generate simulated sensor data
            import random
            import math
            
            # Simulate realistic sensor readings with some variation
            base_time = time.time()
            
            # Temperature: 18-24°C with daily cycle
            temp_variation = math.sin(base_time / 86400) * 2  # Daily cycle
            data['temperature'] = round(21 + temp_variation + random.uniform(-0.5, 0.5), 1)
            
            # Humidity: 70-95% with some variation
            humidity_variation = math.sin(base_time / 43200) * 5  # 12-hour cycle
            data['humidity'] = round(82.5 + humidity_variation + random.uniform(-2, 2), 1)
            
            # CO2: 400-1200 ppm with gradual changes
            co2_variation = math.sin(base_time / 3600) * 200  # Hourly cycle
            data['co2'] = int(800 + co2_variation + random.uniform(-50, 50))
            
            # Light: 200-800 lux with day/night cycle
            current_hour = datetime.now().hour
            if 6 <= current_hour <= 18:  # Daytime
                light_variation = math.sin((current_hour - 6) * math.pi / 12) * 300
                data['light_intensity'] = int(500 + light_variation + random.uniform(-50, 50))
            else:  # Nighttime
                data['light_intensity'] = int(random.uniform(0, 50))
            
            # Water level: 60-90% with gradual decrease
            water_variation = math.sin(base_time / 7200) * 10  # 2-hour cycle
            data['water_level'] = round(75 + water_variation + random.uniform(-2, 2), 1)
            
            # Update timestamp
            data['timestamp'] = datetime.utcnow().isoformat()
            
            print(f"🎭 Simulation mode: T={data['temperature']}°C, H={data['humidity']}%, CO2={data['co2']}ppm, Light={data['light_intensity']}, Water={data['water_level']}%")
            return data
        
        # Real sensor reading code
        try:
            # Read SCD40 (temperature, humidity, CO2)
            if hasattr(self, 'scd40') and self.scd40:
                try:
                    # Wait a bit for data to be ready
                    if self.scd40.data_ready:
                        temp = self.scd40.temperature
                        humidity = self.scd40.relative_humidity
                        co2 = self.scd40.CO2
                        
                        if temp is not None and humidity is not None and co2 is not None:
                            data['temperature'] = round(temp + SENSOR_CONFIG['calibration_offsets']['temperature'], 1)
                            data['humidity'] = round(humidity + SENSOR_CONFIG['calibration_offsets']['humidity'], 1)
                            data['co2'] = int(co2 + SENSOR_CONFIG['calibration_offsets']['co2'])
                            print(f"📡 SCD40 readings: T={temp:.1f}°C, H={humidity:.1f}%, CO2={co2}ppm")
                        else:
                            print("⚠️ SCD40 returned None values, using defaults")
                    else:
                        print("⏳ SCD40 data not ready yet, using previous values")
                except Exception as e:
                    print(f"❌ SCD40 reading error: {e}")
            else:
                print("❌ SCD40 sensor not available")
            
            # Read BH1750 light sensor
            if self.bh1750:
                try:
                    light_lux = self.bh1750.read_light_level()
                    if light_lux is not None:
                        data['light_intensity'] = int(light_lux + SENSOR_CONFIG['calibration_offsets']['light_intensity'])
                        print(f"💡 BH1750 light reading: {light_lux:.1f} lux")
                    else:
                        print("⚠️ BH1750 reading failed")
                except Exception as e:
                    print(f"❌ BH1750 reading error: {e}")
            else:
                print("❌ BH1750 not available")
            
            # Read water level via ultrasonic sensor
            try:
                distance = self.read_ultrasonic_distance()
                if distance is not None:
                    water_level = self.calculate_water_level_percentage(distance)
                    data['water_level'] = water_level + SENSOR_CONFIG['calibration_offsets']['water_level']
                    print(f"💧 Water level: {distance:.1f}cm distance = {water_level:.1f}%")
                else:
                    print("⚠️ Ultrasonic sensor returned None, using default water level")
            except Exception as e:
                print(f"❌ Water level reading error: {e}")
            
            # Update timestamp
            data['timestamp'] = datetime.utcnow().isoformat()
            
            # Log final data
            print(f"📊 Final sensor data: T={data['temperature']}°C, H={data['humidity']}%, CO2={data['co2']}ppm, Light={data['light_intensity']}, Water={data['water_level']}%")
            
        except Exception as e:
            print(f"❌ Sensor reading error: {e}")
        
        return data
    
    def get_sensor_data(self):
        """Get current sensor data"""
        return self.read_sensors()

# Initialize services
sensor_service = SensorService()
gpio_control = GPIOControlService()

# ========================
# WEB ROUTES
# ========================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        if password == app.config['DASHBOARD_PASSWORD']:
            session['authenticated'] = True
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login'))

@app.route('/')
@require_auth
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/current')
@require_auth
def get_current():
    return jsonify(sensor_service.current_data)

@app.route('/api/latest')
@require_auth
def get_latest():
    readings = db_service.get_latest_readings(limit=10)
    return jsonify(readings)

@app.route('/api/history')
@require_auth
def get_history():
    hours = request.args.get('hours', 24, type=int)
    readings = db_service.get_historical_data(hours)
    return jsonify(readings)

@app.route('/api/status')
@require_auth
def get_status():
    control_status = gpio_control.get_control_status()
    db_status = db_service.get_database_status()
    return jsonify({
        'database': db_status['database_type'],
        'connected': db_status['local_mongodb'],
        'atlas_connected': db_status['atlas_connected'],
        'offline_mode': db_status['offline_mode'],
        'device_id': DEVICE_ID,
        'controls': control_status
    })

@app.route('/api/test-sensors')
@require_auth
def test_sensors():
    """Test endpoint to get current sensor readings with detailed info"""
    try:
        # Get current sensor data
        sensor_data = sensor_service.get_sensor_data()
        
        # Get sensor availability status
        sensor_status = {
            'scd40_available': sensor_service.scd40 is not None,
            'bh1750_available': sensor_service.bh1750 is not None,
            'water_sensor_available': sensor_service.water_sensor is not None,
            'gpio_available': GPIO_AVAILABLE,
            'scd40_available_lib': SCD40_AVAILABLE,
            'bh1750_available_lib': BH1750_AVAILABLE
        }
        
        return jsonify({
            'success': True,
            'sensor_data': sensor_data,
            'sensor_status': sensor_status,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        })

@app.route('/debug/sensors')
def debug_sensors():
    """Debug endpoint to check sensor status without authentication"""
    try:
        # Get sensor availability status
        sensor_status = {
            'scd40_available': sensor_service.scd40 is not None,
            'bh1750_available': sensor_service.bh1750 is not None,
            'water_sensor_available': sensor_service.water_sensor is not None,
            'gpio_available': GPIO_AVAILABLE,
            'scd40_available_lib': SCD40_AVAILABLE,
            'bh1750_available_lib': BH1750_AVAILABLE,
            'current_data': sensor_service.current_data
        }
        
        return jsonify({
            'success': True,
            'sensor_status': sensor_status,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        })

@app.route('/debug/read-sensors')
def debug_read_sensors():
    """Debug endpoint to force a sensor reading"""
    try:
        # Force a sensor reading
        sensor_data = sensor_service.read_sensors()
        
        return jsonify({
            'success': True,
            'sensor_data': sensor_data,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        })

@app.route('/api/control/fogger', methods=['POST'])
@require_auth
def control_fogger():
    data = request.get_json()
    activate = data.get('activate', False)
    duration = data.get('duration', MUSHROOM_CONFIG['control_settings']['fogger_duration'])
    
    gpio_control.control_fogger(activate, duration if activate else None)
    
    return jsonify({
        'success': True,
        'fogger_active': gpio_control.fogger_active,
        'message': f"Fogger {'activated' if activate else 'deactivated'}"
    })

@app.route('/api/control/fan', methods=['POST'])
@require_auth
def control_fan():
    data = request.get_json()
    speed = data.get('speed', 0)
    
    gpio_control.control_fan(speed)
    
    return jsonify({
        'success': True,
        'fan_speed': gpio_control.fan_speed,
        'message': f"Fan speed set to {speed}%"
    })

@app.route('/api/control/lights', methods=['POST'])
@require_auth
def control_lights():
    data = request.get_json()
    activate = data.get('activate', False)
    
    gpio_control.control_lights(activate)
    
    return jsonify({
        'success': True,
        'lights_active': gpio_control.lights_active,
        'message': f"Lights {'activated' if activate else 'deactivated'}"
    })

# SocketIO Handlers
@socketio.on('connect')
def handle_connect():
    # Always send database status on connection
    db_status = db_service.get_database_status()
    emit('status_update', {
        'database': db_status['database_type'],
        'connected': db_status['local_mongodb'],
        'atlas_connected': db_status['atlas_connected'],
        'offline_mode': db_status['offline_mode']
    })
    
    # Send sensor data only if authenticated
    if 'authenticated' in session:
        emit('sensor_update', sensor_service.current_data)

@socketio.on('request_data')
def handle_data_request():
    if 'authenticated' in session:
        emit('sensor_update', sensor_service.current_data)

# ========================
# BACKGROUND TASKS
# ========================
def sensor_monitor():
    """Background task to read sensor data and save to database"""
    while True:
        try:
            # Get sensor data
            sensor_data = sensor_service.get_sensor_data()
            
            # Auto-control based on conditions
            auto_control_environment(sensor_data)
            
            # Save to database (local MongoDB with Atlas sync)
            db_service.save_reading(sensor_data)
            
            # Emit real-time update to connected clients
            control_status = gpio_control.get_control_status()
            update_data = {
                **sensor_data,
                'controls': control_status
            }
            socketio.emit('sensor_update', update_data)
            
            # Also emit database status update periodically
            db_status = db_service.get_database_status()
            socketio.emit('status_update', {
                'database': db_status['database_type'],
                'connected': db_status['local_mongodb'],
                'atlas_connected': db_status['atlas_connected'],
                'offline_mode': db_status['offline_mode']
            })
            
            # Log current values
            print(f"📊 T: {sensor_data['temperature']}°C, H: {sensor_data['humidity']}%, CO2: {sensor_data['co2']}ppm, Light: {sensor_data['light_intensity']} lux, Water: {sensor_data['water_level']}%")
            
            time.sleep(SENSOR_READ_INTERVAL)
            
        except Exception as e:
            print(f"⚠️ Sensor monitor error: {e}")
            time.sleep(5)

def auto_control_environment(sensor_data):
    """Automatically control environment based on sensor readings"""
    try:
        temp = sensor_data['temperature']
        humidity = sensor_data['humidity']
        water_level = sensor_data.get('water_level', 50.0)
        
        # Check water level first - disable fogger if water is too low
        if water_level < 15:
            if gpio_control.fogger_active:
                gpio_control.control_fogger(False)
                print("🚨 Low water level detected - Fogger disabled!")
        
        # Auto-fogger control based on humidity (only if water level is sufficient)
        humidity_min = OPTIMAL_RANGES['humidity']['min']
        humidity_max = OPTIMAL_RANGES['humidity']['max']
        if (humidity < humidity_min - 5 and not gpio_control.fogger_active and water_level > 20):
            gpio_control.control_fogger(True, MUSHROOM_CONFIG['control_settings']['fogger_duration'])
        
        # Auto-fan control based on humidity (too high)
        if humidity > humidity_max + 5 and gpio_control.fan_speed < 50:
            gpio_control.control_fan(50)
        elif humidity <= humidity_max and gpio_control.fan_speed > 0:
            gpio_control.control_fan(0)
        
        # Auto-light control based on time
        current_hour = datetime.now().hour
        light_schedule = MUSHROOM_CONFIG['control_settings']['light_schedule']
        should_lights_be_on = (light_schedule['on_hour'] <= current_hour < light_schedule['off_hour'])
        
        if should_lights_be_on != gpio_control.lights_active:
            gpio_control.control_lights(should_lights_be_on)
            
    except Exception as e:
        print(f"⚠️ Auto-control error: {e}")

def database_health_monitor():
    """Monitor database connections and sync with Atlas when available"""
    while True:
        try:
            # Try to reconnect to Atlas if not connected
            if not db_service.using_atlas:
                if db_service.connect_atlas():
                    print("🔄 Reconnected to MongoDB Atlas")
                    
            time.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            print(f"⚠️ Database monitor error: {e}")
            time.sleep(30)

# ========================
# MAIN APPLICATION
# ========================
def main():
    print("🍄 Starting Environmental Control System")
    db_status = db_service.get_database_status()
    print(f"📊 Database: {db_status['database_type']}")
    if db_status['offline_mode']:
        print("📱 Operating in offline mode")
    else:
        print("☁️ Connected to MongoDB Atlas")
    print(f"🔌 GPIO: {'Available' if GPIO_AVAILABLE else 'Not Available'}")
    
    # Start background threads
    threading.Thread(target=sensor_monitor, daemon=True).start()
    threading.Thread(target=database_health_monitor, daemon=True).start()
    
    # Auto-open browser
    def open_browser():
        time.sleep(2)  # Wait for server to start
        webbrowser.open('http://localhost:8080')
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Start web server
    try:
        print("🌐 Web server running at http://localhost:8080")
        print("🔐 Default password: admin123 (change in .env file)")
        print("🌍 Opening browser automatically...")
        socketio.run(app, host='0.0.0.0', port=8080, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print("🛑 Server stopped")
        print("🧹 GPIO Zero will automatically cleanup")
    except Exception as e:
        print(f"❌ Server error: {e}")
        print("🧹 GPIO Zero will automatically cleanup")

if __name__ == '__main__':
    main()