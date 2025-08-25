#!/usr/bin/env python3
"""
Database Monitor Script
Monitors MongoDB and shows real-time sensor data being saved
"""

import time
from datetime import datetime, timedelta
from pymongo import MongoClient


def monitor_database():
    """Monitor database for new sensor readings"""
    print("📊 Database Monitor - Real-time Sensor Data")
    print("=" * 50)
    print("Monitoring MongoDB for new sensor readings...")
    print("Press Ctrl+C to stop")
    print()

    try:
        # Connect to MongoDB
        client = MongoClient('mongodb://localhost:27017/')
        db = client.sensor_db

        # Get initial count
        initial_count = db.readings.count_documents({})
        print(f"📦 Initial readings in database: {initial_count}")

        # Get latest reading timestamp
        latest = db.readings.find_one({}, sort=[('server_timestamp', -1)])
        if latest:
            last_timestamp = latest.get('server_timestamp')
            print(f"🕐 Last reading: {last_timestamp}")
        else:
            last_timestamp = None
            print("🕐 No previous readings found")

        print("\n" + "=" * 50)
        print("Waiting for new readings...")
        print()

        while True:
            try:
                # Get current count
                current_count = db.readings.count_documents({})

                # Check for new readings
                if current_count > initial_count:
                    print(f"🆕 New readings detected! Total: {current_count}")

                    # Get new readings
                    if last_timestamp:
                        new_readings = list(db.readings.find({
                            'server_timestamp': {'$gt': last_timestamp}
                        }).sort('server_timestamp', -1))
                    else:
                        new_readings = list(db.readings.find().sort('server_timestamp', -1).limit(5))

                    # Display new readings
                    for reading in new_readings:
                        timestamp = reading.get('server_timestamp', 'N/A')
                        if isinstance(timestamp, datetime):
                            timestamp = timestamp.strftime('%H:%M:%S')

                        print(f"\n📊 Reading at {timestamp}:")
                        print(f"   🌡️  Temperature: {reading.get('temperature', 'N/A')}°C")
                        print(f"   💧 Humidity: {reading.get('humidity', 'N/A')}%")
                        print(f"   🌬️  CO2: {reading.get('co2', 'N/A')} ppm")
                        print(f"   💡 Light: {reading.get('light_intensity', 'N/A')} lux")
                        print(f"   💧 Water: {reading.get('water_level', 'N/A')}%")
                        print(f"   📱 Device: {reading.get('device_id', 'N/A')}")

                        # Update last timestamp
                        last_timestamp = reading.get('server_timestamp')

                    initial_count = current_count
                    print("\n" + "-" * 30)

                time.sleep(2)  # Check every 2 seconds

            except KeyboardInterrupt:
                print("\n🛑 Monitoring stopped by user")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(5)

        client.close()

    except Exception as e:
        print(f"❌ Database connection error: {e}")
        print("   Make sure MongoDB is running: sudo systemctl status mongod")


def show_recent_readings(limit=10):
    """Show recent sensor readings"""
    print(f"📊 Recent Sensor Readings (Last {limit})")
    print("=" * 50)

    try:
        # Connect to MongoDB
        client = MongoClient('mongodb://localhost:27017/')
        db = client.sensor_db

        # Get recent readings
        readings = list(db.readings.find().sort('server_timestamp', -1).limit(limit))

        if not readings:
            print("❌ No readings found in database")
            return

        for i, reading in enumerate(readings, 1):
            timestamp = reading.get('server_timestamp', 'N/A')
            if isinstance(timestamp, datetime):
                timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')

            print(f"\n📊 Reading #{i} at {timestamp}:")
            print(f"   🌡️  Temperature: {reading.get('temperature', 'N/A')}°C")
            print(f"   💧 Humidity: {reading.get('humidity', 'N/A')}%")
            print(f"   🌬️  CO2: {reading.get('co2', 'N/A')} ppm")
            print(f"   💡 Light: {reading.get('light_intensity', 'N/A')} lux")
            print(f"   💧 Water: {reading.get('water_level', 'N/A')}%")
            print(f"   📱 Device: {reading.get('device_id', 'N/A')}")

        client.close()

    except Exception as e:
        print(f"❌ Error: {e}")


def show_database_stats():
    """Show database statistics"""
    print("📊 Database Statistics")
    print("=" * 30)

    try:
        # Connect to MongoDB
        client = MongoClient('mongodb://localhost:27017/')
        db = client.sensor_db

        # Get statistics
        total_readings = db.readings.count_documents({})

        # Get date range
        first_reading = db.readings.find_one({}, sort=[('server_timestamp', 1)])
        last_reading = db.readings.find_one({}, sort=[('server_timestamp', -1)])

        print(f"📦 Total readings: {total_readings}")

        if first_reading and last_reading:
            first_time = first_reading.get('server_timestamp')
            last_time = last_reading.get('server_timestamp')

            if isinstance(first_time, datetime) and isinstance(last_time, datetime):
                duration = last_time - first_time
                print(f"📅 Date range: {first_time.strftime('%Y-%m-%d')} to {last_time.strftime('%Y-%m-%d')}")
                print(f"⏱️  Duration: {duration.days} days")

        # Get readings from last 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_count = db.readings.count_documents({
            'server_timestamp': {'$gte': yesterday}
        })
        print(f"📈 Readings in last 24h: {recent_count}")

        # Get average readings per hour
        if recent_count > 0:
            avg_per_hour = recent_count / 24
            print(f"📊 Average readings per hour: {avg_per_hour:.1f}")

        client.close()

    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Main function"""
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "monitor":
            monitor_database()
        elif command == "recent":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            show_recent_readings(limit)
        elif command == "stats":
            show_database_stats()
        else:
            print("❌ Unknown command")
            print("Available commands:")
            print("  python3 monitor_database.py monitor  # Monitor real-time")
            print("  python3 monitor_database.py recent   # Show recent readings")
            print("  python3 monitor_database.py stats    # Show database stats")
    else:
        print("📊 Database Monitor Tool")
        print("=" * 30)
        print("Usage:")
        print("  python3 monitor_database.py monitor  # Monitor real-time sensor data")
        print("  python3 monitor_database.py recent   # Show recent readings")
        print("  python3 monitor_database.py stats    # Show database statistics")
        print()
        print("Examples:")
        print("  python3 monitor_database.py monitor")
        print("  python3 monitor_database.py recent 5")
        print("  python3 monitor_database.py stats")


if __name__ == '__main__':
    main()
