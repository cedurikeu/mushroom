"""
Database Service for Mushroom Cultivation System
Handles both local MongoDB and Atlas connections
"""

import os
from datetime import datetime, timedelta
from pymongo import MongoClient, errors
import time
from typing import Dict, List, Optional

class DatabaseService:
    def __init__(self):
        self.local_client = None
        self.local_db = None
        self.atlas_client = None
        self.atlas_db = None
        self.using_atlas = False
        
        # Setup databases
        self.setup_local_mongodb()
        self.connect_atlas()
        
    def setup_local_mongodb(self):
        """Setup local MongoDB database"""
        try:
            # Connect to local MongoDB (default port 27017)
            self.local_client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=2000)
            self.local_db = self.local_client.sensor_db
            
            # Test connection
            self.local_client.server_info()
            print("✅ Local MongoDB connected")
            
            # Create indexes for better performance
            self.local_db.readings.create_index([("device_id", 1), ("server_timestamp", -1)])
            self.local_db.readings.create_index([("server_timestamp", -1)])
            
        except Exception as e:
            print(f"❌ Local MongoDB setup failed: {e}")
            print("💡 Make sure MongoDB is installed and running locally")
            self.local_client = None
            self.local_db = None
            
    def connect_atlas(self):
        """Connect to MongoDB Atlas"""
        try:
            atlas_uri = os.getenv('MONGODB_URI')
            if atlas_uri:
                self.atlas_client = MongoClient(atlas_uri, serverSelectionTimeoutMS=5000)
                self.atlas_db = self.atlas_client.sensor_db
                
                # Test connection
                self.atlas_client.server_info()
                self.using_atlas = True
                print("✅ MongoDB Atlas connected")
                
                # Sync any offline data
                self.sync_offline_data()
                return True
        except Exception as e:
            print(f"⚠️ MongoDB Atlas connection failed: {e}")
            print("📱 Operating in offline mode with local MongoDB")
            self.using_atlas = False
            self.atlas_client = None
            self.atlas_db = None
            return False
            
    def sync_offline_data(self):
        """Sync offline data to Atlas when connection is restored"""
        if self.atlas_db is None or self.local_db is None:
            return
            
        try:
            # Get unsynchronized local data (last 24 hours)
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            local_readings = list(self.local_db.readings.find({
                "server_timestamp": {"$gte": cutoff_time}
            }))
            
            if local_readings:
                print(f"🔄 Syncing {len(local_readings)} readings to Atlas...")
                
                # Insert to Atlas (ignore duplicates)
                for reading in local_readings:
                    try:
                        self.atlas_db.readings.insert_one(reading)
                    except errors.DuplicateKeyError:
                        continue  # Skip duplicates
                        
                print("✅ Data synced to Atlas successfully")
        except Exception as e:
            print(f"⚠️ Sync error: {e}")
    
    def save_reading(self, data: Dict) -> bool:
        """Save sensor reading to database"""
        try:
            # Add server timestamp
            reading = {
                **data,
                'server_timestamp': datetime.utcnow()
            }
            
            # Try to save to Atlas first
            saved_to_atlas = False
            if self.using_atlas and self.atlas_db is not None:
                try:
                    self.atlas_db.readings.insert_one(reading.copy())
                    saved_to_atlas = True
                except Exception as e:
                    print(f"❌ Atlas save failed: {e}")
                    # Fall back to local only
                    self.using_atlas = False
            
            # Always save to local MongoDB as backup
            if self.local_db is not None:
                try:
                    self.local_db.readings.insert_one(reading.copy())
                    if not saved_to_atlas:
                        print("💾 Saved to local MongoDB")
                    return True
                except Exception as e:
                    print(f"❌ Local save failed: {e}")
                    return False
            else:
                print("❌ No database available for saving")
                return False
                
        except Exception as e:
            print(f"❌ Save error: {e}")
            return False
    
    def get_latest_readings(self, limit: int = 10) -> List[Dict]:
        """Get latest sensor readings"""
        try:
            # Try Atlas first, then local
            db = self.atlas_db if (self.using_atlas and self.atlas_db is not None) else self.local_db
            
            if db is not None:
                cursor = db.readings.find().sort("server_timestamp", -1).limit(limit)
                readings = []
                for doc in cursor:
                    # Convert ObjectId to string for JSON serialization
                    doc['_id'] = str(doc['_id'])
                    # Convert datetime to ISO string
                    if 'server_timestamp' in doc:
                        doc['server_timestamp'] = doc['server_timestamp'].isoformat()
                    readings.append(doc)
                return readings
            else:
                return []
        except Exception as e:
            print(f"❌ Error getting latest readings: {e}")
            return []
    
    def get_historical_data(self, hours: int = 24) -> List[Dict]:
        """Get historical data for the specified time period"""
        try:
            # Try Atlas first, then local
            db = self.atlas_db if (self.using_atlas and self.atlas_db is not None) else self.local_db
            
            if db is not None:
                cutoff_time = datetime.utcnow() - timedelta(hours=hours)
                cursor = db.readings.find({
                    "server_timestamp": {"$gte": cutoff_time}
                }).sort("server_timestamp", 1)
                
                readings = []
                for doc in cursor:
                    # Convert ObjectId to string for JSON serialization
                    doc['_id'] = str(doc['_id'])
                    # Convert datetime to ISO string
                    if 'server_timestamp' in doc:
                        doc['server_timestamp'] = doc['server_timestamp'].isoformat()
                    readings.append(doc)
                return readings
            else:
                return []
        except Exception as e:
            print(f"❌ Error getting historical data: {e}")
            return []
    
    def get_database_status(self) -> Dict:
        """Get current database connection status"""
        local_connected = self.local_db is not None
        atlas_connected = self.atlas_db is not None and self.using_atlas
        
        return {
            'local_mongodb': local_connected,
            'atlas_connected': atlas_connected,
            'offline_mode': not atlas_connected,
            'database_type': 'MongoDB Atlas' if atlas_connected else 'Local MongoDB' if local_connected else 'None'
        }
    
    def test_connections(self):
        """Test database connections"""
        print("🔍 Testing database connections...")
        
        # Test local MongoDB
        if self.local_db is not None:
            try:
                self.local_client.server_info()
                count = self.local_db.readings.count_documents({})
                print(f"✅ Local MongoDB: Connected ({count} readings)")
            except Exception as e:
                print(f"❌ Local MongoDB: Failed - {e}")
        else:
            print("❌ Local MongoDB: Not configured")
        
        # Test Atlas
        if self.atlas_db is not None:
            try:
                self.atlas_client.server_info()
                count = self.atlas_db.readings.count_documents({})
                print(f"✅ MongoDB Atlas: Connected ({count} readings)")
            except Exception as e:
                print(f"❌ MongoDB Atlas: Failed - {e}")
                self.using_atlas = False
        else:
            print("❌ MongoDB Atlas: Not configured")
    
    def cleanup(self):
        """Clean up database connections"""
        if self.local_client:
            self.local_client.close()
        if self.atlas_client:
            self.atlas_client.close()

# Health monitoring function
def database_health_monitor():
    """Monitor database health and attempt reconnection"""
    while True:
        try:
            time.sleep(60)  # Check every minute
            
            # This would be called from main app with db_service instance
            # db_service.test_connections()
            
        except Exception as e:
            print(f"⚠️ Database health monitor error: {e}")
            time.sleep(10)