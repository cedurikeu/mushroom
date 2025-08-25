#!/usr/bin/env python3
"""
Standalone sensor test script for Raspberry Pi Mushroom Environmental Control System
This script tests each sensor individually to help identify connection issues.
"""

import time
import sys
import os

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from config import GPIO_CONFIG, SENSOR_CONFIG
    print("✅ Config loaded successfully")
except ImportError as e:
    print(f"❌ Config import error: {e}")
    sys.exit(1)

def test_gpio():
    """Test GPIO availability"""
    print("\n🔌 Testing GPIO...")
    try:
        from gpiozero import DistanceSensor, LED, OutputDevice
        print("✅ GPIO Zero library available")
        
        # Test basic GPIO operations
        try:
            # Test LED (should work even without hardware)
            led = LED(17)  # Use a safe GPIO pin
            led.on()
            time.sleep(0.1)
            led.off()
            led.close()
            print("✅ Basic GPIO operations work")
        except Exception as e:
            print(f"⚠️ GPIO operations failed: {e}")
            
    except ImportError:
        print("❌ GPIO Zero not available")
        return False
    return True

def test_i2c():
    """Test I2C bus"""
    print("\n🔗 Testing I2C...")
    try:
        import board
        import busio
        
        # Try to initialize I2C
        i2c = busio.I2C(board.SCL, board.SDA)
        print("✅ I2C bus initialized")
        
        # Scan for devices
        devices = i2c.scan()
        if devices:
            print(f"✅ Found {len(devices)} I2C device(s): {[hex(addr) for addr in devices]}")
        else:
            print("⚠️ No I2C devices found")
            
        return True
    except Exception as e:
        print(f"❌ I2C test failed: {e}")
        return False

def test_scd40():
    """Test SCD40 sensor"""
    print("\n🌡️ Testing SCD40...")
    try:
        import adafruit_scd4x
        import board
        import busio
        
        i2c = busio.I2C(board.SCL, board.SDA)
        scd40 = adafruit_scd4x.SCD4X(i2c)
        
        print("✅ SCD40 sensor initialized")
        print("🔄 Starting periodic measurement...")
        scd40.start_periodic_measurement()
        
        # Wait for first reading
        print("⏳ Waiting for first reading...")
        for i in range(10):  # Wait up to 10 seconds
            if scd40.data_ready:
                temp = scd40.temperature
                humidity = scd40.relative_humidity
                co2 = scd40.CO2
                print(f"✅ SCD40 readings: T={temp:.1f}°C, H={humidity:.1f}%, CO2={co2}ppm")
                return True
            time.sleep(1)
            print(f"  Waiting... ({i+1}/10)")
        
        print("⚠️ SCD40 data not ready after 10 seconds")
        return False
        
    except Exception as e:
        print(f"❌ SCD40 test failed: {e}")
        return False

def test_bh1750():
    """Test BH1750 light sensor"""
    print("\n💡 Testing BH1750...")
    try:
        import smbus2
        
        # Try to access I2C bus
        bus = smbus2.SMBus(1)
        print("✅ I2C bus accessible")
        
        # Try to read from BH1750 address
        try:
            # BH1750 address
            addr = 0x23
            # Try to read a byte
            bus.read_byte(addr)
            print("✅ BH1750 responds to I2C")
            
            # Try to get a reading
            # Send measurement command
            bus.write_byte(addr, 0x20)  # One-time high resolution mode
            time.sleep(0.2)  # Wait for measurement
            
            # Read 2 bytes
            data = bus.read_i2c_block_data(addr, 0x20, 2)
            light_level = (data[0] << 8) + data[1]
            light_lux = light_level / 1.2
            
            print(f"✅ BH1750 reading: {light_lux:.1f} lux")
            return True
            
        except Exception as e:
            print(f"⚠️ BH1750 reading failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ BH1750 test failed: {e}")
        return False

def test_ultrasonic():
    """Test ultrasonic sensor"""
    print("\n💧 Testing Ultrasonic sensor...")
    try:
        from gpiozero import DistanceSensor
        
        # Initialize sensor
        sensor = DistanceSensor(
            echo=GPIO_CONFIG['ULTRASONIC_ECHO_PIN'],
            trigger=GPIO_CONFIG['ULTRASONIC_TRIG_PIN'],
            max_distance=1
        )
        print("✅ Ultrasonic sensor initialized")
        
        # Take a few readings
        for i in range(3):
            try:
                distance = sensor.distance
                distance_cm = distance * 100
                print(f"  Reading {i+1}: {distance_cm:.1f} cm")
                time.sleep(0.5)
            except Exception as e:
                print(f"  Reading {i+1} failed: {e}")
        
        sensor.close()
        return True
        
    except Exception as e:
        print(f"❌ Ultrasonic test failed: {e}")
        return False

def test_mongodb():
    """Test MongoDB connections"""
    print("\n📊 Testing MongoDB...")
    try:
        from pymongo import MongoClient
        
        # Test local MongoDB
        try:
            local_client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=2000)
            local_client.server_info()
            print("✅ Local MongoDB connected")
            local_client.close()
        except Exception as e:
            print(f"❌ Local MongoDB failed: {e}")
        
        # Test Atlas (if MONGODB_URI is set)
        atlas_uri = os.getenv('MONGODB_URI')
        if atlas_uri:
            try:
                atlas_client = MongoClient(atlas_uri, serverSelectionTimeoutMS=5000)
                atlas_client.server_info()
                print("✅ MongoDB Atlas connected")
                atlas_client.close()
            except Exception as e:
                print(f"❌ MongoDB Atlas failed: {e}")
        else:
            print("⚠️ MONGODB_URI not set")
            
    except ImportError:
        print("❌ PyMongo not available")
        return False
    
    return True

def main():
    """Run all tests"""
    print("🧪 Sensor Test Suite")
    print("=" * 50)
    
    results = {}
    
    # Run tests
    results['gpio'] = test_gpio()
    results['i2c'] = test_i2c()
    results['scd40'] = test_scd40()
    results['bh1750'] = test_bh1750()
    results['ultrasonic'] = test_ultrasonic()
    results['mongodb'] = test_mongodb()
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 Test Summary:")
    print("=" * 50)
    
    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test.upper():12} {status}")
    
    passed = sum(results.values())
    total = len(results)
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your sensors should work correctly.")
    else:
        print("⚠️ Some tests failed. Check the connections and try again.")
        print("\n💡 Troubleshooting tips:")
        print("  - Check I2C connections (SCL/SDA pins)")
        print("  - Verify power connections (3.3V and GND)")
        print("  - Check GPIO pin assignments in config.py")
        print("  - Ensure MongoDB is running locally")
        print("  - Check MONGODB_URI environment variable for Atlas")

if __name__ == "__main__":
    main()