# GPIO Configuration for Raspberry Pi Mushroom Environmental Control System

# GPIO Pin Assignments
GPIO_CONFIG = {
    # SCD40 Sensor Pins (Physical pins)
    # Pin 1: 3.3V Power
    # Pin 3: SDA (GPIO 2)  
    # Pin 5: SCL (GPIO 3)
    # Pin 9: Ground
    'SCD40_SDA_PIN': 2,          # SCD40 I2C SDA pin (Physical pin 3)
    'SCD40_SCL_PIN': 3,          # SCD40 I2C SCL pin (Physical pin 5)
    
    # Other Sensor Pins
    'LIGHT_SENSOR_PIN': 0,       # Light intensity (MCP3008 ADC Channel 0)
    'ULTRASONIC_TRIG_PIN': 23,   # Ultrasonic trigger pin for water level
    'ULTRASONIC_ECHO_PIN': 24,   # Ultrasonic echo pin for water level
    
    # Control Pins
    'FOGGER_PIN': 18,            # Fogger relay control
    'FAN_PIN': 19,               # Exhaust fan control
    'HEATER_PIN': 20,            # Heating element control
    'LED_LIGHTS_PIN': 21,        # LED grow lights control
    
    # Status LED Pins
    'STATUS_LED_GREEN': 26,      # System OK
    'STATUS_LED_RED': 16,        # System Error
    'STATUS_LED_BLUE': 13,       # WiFi Connected
    
    # SPI Configuration for MCP3008 ADC
    'SPI_CLK': 11,
    'SPI_MISO': 9,
    'SPI_MOSI': 10,
    'SPI_CS': 8
}

# Sensor Thresholds and Optimal Ranges for Mushroom Growing
MUSHROOM_CONFIG = {
    'optimal_ranges': {
        'temperature': {'min': 18, 'max': 24},      # Celsius
        'humidity': {'min': 80, 'max': 95},         # Percentage
        'co2': {'min': 800, 'max': 1200},           # PPM
        'light_intensity': {'min': 200, 'max': 800}, # Lux equivalent
        'water_level': {'min': 20, 'max': 100}     # Percentage of reservoir
    },
    'alert_thresholds': {
        'temperature': {'critical_low': 15, 'critical_high': 28},
        'humidity': {'critical_low': 70, 'critical_high': 98},
        'co2': {'critical_low': 600, 'critical_high': 1500},
        'light_intensity': {'critical_low': 100, 'critical_high': 1000},
        'water_level': {'critical_low': 15, 'critical_high': 100}  # Low water alert at 15%
    },
    'control_settings': {
        'fogger_duration': 30,      # seconds
        'fogger_interval': 300,     # seconds (5 minutes)
        'fan_speed_levels': [0, 50, 75, 100],  # PWM percentage
        'light_schedule': {
            'on_hour': 6,           # 6 AM
            'off_hour': 18          # 6 PM
        }
    }
}

# Mushroom Growth Phases
GROWTH_PHASES = {
    'inoculation': {
        'name': 'Inoculation',
        'duration_days': 14,
        'temp_range': (20, 22),
        'humidity_range': (60, 70),
        'light_needed': False
    },
    'colonization': {
        'name': 'Colonization',
        'duration_days': 21,
        'temp_range': (22, 24),
        'humidity_range': (70, 80),
        'light_needed': False
    },
    'pinning': {
        'name': 'Pin Formation',
        'duration_days': 7,
        'temp_range': (18, 20),
        'humidity_range': (85, 95),
        'light_needed': True
    },
    'fruiting': {
        'name': 'Fruiting',
        'duration_days': 14,
        'temp_range': (18, 22),
        'humidity_range': (80, 90),
        'light_needed': True
    }
}

# Database Configuration
DATABASE_CONFIG = {
    'mongodb_timeout': 5000,     # milliseconds
    'sqlite_file': 'sensor_data.db',
    'backup_interval': 3600,     # seconds (1 hour)
    'data_retention_days': 30
}

# Network Configuration
NETWORK_CONFIG = {
    'flask_host': '0.0.0.0',
    'flask_port': 5000,
    'socket_ping_timeout': 60,
    'socket_ping_interval': 25,
    'wifi_check_interval': 30    # seconds
}

# Sensor Reading Configuration
SENSOR_CONFIG = {
    'read_interval': 10,         # seconds
    'averaging_samples': 3,      # number of readings to average
    'retry_attempts': 3,
    'calibration_offsets': {
        'temperature': 0.0,
        'humidity': 0.0,
        'co2': 0,
        'light_intensity': 0,
        'water_level': 0.0
    },
    # Water reservoir configuration
    'reservoir_config': {
        'max_depth_cm': 30,          # Maximum depth of reservoir in cm
        'min_depth_cm': 5,           # Minimum usable depth in cm
        'sensor_height_cm': 35       # Height of ultrasonic sensor above bottom
    }
}