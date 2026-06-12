"""
Database Manager - Simplified Cumulative Counting
Calculates cumulative totals from existing People_Count data
NO NEW COLUMNS NEEDED!
"""
from datetime import datetime
import json
import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Database Configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'peopleCount'),
    'unix_socket': os.getenv('DB_SOCKET', '/Applications/XAMPP/xamppfiles/var/mysql/mysql.sock'),
    'autocommit': True
}

class db_manager:
    def __init__(self):
        self.connection = None
        self.connect()
    
    def connect(self):
        try:
            self.connection = mysql.connector.connect(**DB_CONFIG)
            if self.connection.is_connected():
                print("✅ Successfully connected to MySQL database")
                return True
        except Error as e:
            print(f"❌ Error connecting to MySQL: {e}")
            self.connection = None
            return False
    
    def start_session(self):
        """Start new session"""
        cursor = self.connection.cursor()
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = "INSERT INTO Session (start_time) VALUES (%s)"
        cursor.execute(sql, (start_time,))
        self.connection.commit()
        session_id = cursor.lastrowid
        cursor.close()
        
        print(f"✅ Started session #{session_id}")
        return session_id

    def stop_session(self, session_id):
        """Stop session and record end time"""
        cursor = self.connection.cursor()
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = "UPDATE Session SET end_time=%s WHERE session_id=%s"
        cursor.execute(sql, (end_time, session_id))
        self.connection.commit()
        cursor.close()
        
        print(f"✅ Stopped session #{session_id}")

    def delete_session(self, session_id):
        """Delete a session and all its related data"""
        try:
            cursor = self.connection.cursor()
            
            # Delete related data first
            cursor.execute("DELETE FROM People_Count WHERE session_id = %s", (session_id,))
            cursor.execute("DELETE FROM Crowd_Density WHERE session_id = %s", (session_id,))
            cursor.execute("DELETE FROM Air_Quality WHERE session_id = %s", (session_id,))
            cursor.execute("DELETE FROM Session WHERE session_id = %s", (session_id,))
            
            session_deleted = cursor.rowcount
            self.connection.commit()
            cursor.close()
            
            if session_deleted > 0:
                print(f"✅ Session #{session_id} deleted successfully")
                return True
            else:
                print(f"⚠️ Session #{session_id} not found")
                return False
                
        except Error as e:
            print(f"❌ Error deleting session #{session_id}: {e}")
            return False

    def save_people_count(self, session_id, people_count):
        """
        Save people count to database
        Strategy: Save large jumps as cumulative markers
        """
        if session_id is None:
            return
        
        cursor = self.connection.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        sql = """
            INSERT INTO People_Count (session_id, timestamp, people_count)
            VALUES (%s, %s, %s)
        """
        cursor.execute(sql, (session_id, timestamp, people_count))
        self.connection.commit()
        cursor.close()

    def save_crowd_density(self, session_id, density_value):
        if session_id is None:
            return
        cursor = self.connection.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = """
            INSERT INTO Crowd_Density (session_id, timestamp, crowd_density)
            VALUES (%s, %s, %s)
        """
        cursor.execute(sql, (session_id, timestamp, density_value))
        self.connection.commit()
        cursor.close()

    def save_air_quality(self, session_id, mq2_value):
        """Save MQ2 sensor reading"""
        if session_id is None:
            return
        cursor = self.connection.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = """
            INSERT INTO Air_Quality (session_id, timestamp, air_quality)
            VALUES (%s, %s, %s)
        """
        cursor.execute(sql, (session_id, timestamp, mq2_value))
        self.connection.commit()
        cursor.close()

    def calculate_cumulative_total(self, session_id):
        """
        Calculate cumulative total for a session using smart logic:
        - Find large jumps in people_count (these are cumulative updates)
        - Last large value is the cumulative total
        """
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            # Get all people counts for this session, ordered by time
            cursor.execute("""
                SELECT people_count, timestamp
                FROM People_Count
                WHERE session_id = %s
                ORDER BY timestamp ASC
            """, (session_id,))
            
            counts = cursor.fetchall()
            cursor.close()
            
            if not counts:
                return 0
            
            # Strategy: Look for the pattern of cumulative updates
            # Cumulative values are typically much larger and appear less frequently
            
            # Get all unique values
            all_values = [c['people_count'] for c in counts]
            
            if len(all_values) == 1:
                # Only one value, that's the total
                return all_values[0]
            
            # Find the maximum value (likely the cumulative total)
            # This works because cumulative grows over time
            max_value = max(all_values)
            
            # Count how many times max value appears
            max_count = all_values.count(max_value)
            
            # If max value appears rarely (< 10% of entries), it's likely cumulative
            if max_count < len(all_values) * 0.1 or max_count <= 3:
                return max_value
            
            # Otherwise, look for the last significant jump
            # Sort values and find last large one
            sorted_values = sorted(set(all_values), reverse=True)
            
            if len(sorted_values) >= 2:
                # If there's a big gap between largest and second largest
                if sorted_values[0] > sorted_values[1] * 1.5:
                    return sorted_values[0]
            
            # Fallback: return max value
            return max_value
            
        except Error as e:
            print(f"⚠️ Error calculating cumulative: {e}")
            return 0

    def get_session_history(self):
        """Get session history with cumulative totals calculated from existing data"""
        if not self.connection or not self.connection.is_connected():
            print("⚠️ Database not connected. Reconnecting...")
            if not self.connect():
                return []
        
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            # Fetch all sessions
            cursor.execute("""
                SELECT session_id, start_time, end_time 
                FROM Session 
                ORDER BY start_time DESC
            """)
            sessions = cursor.fetchall()
            
            history = []
            
            for session in sessions:
                session_id = session['session_id']
                
                # Calculate cumulative total using smart logic
                cumulative_total = self.calculate_cumulative_total(session_id)
                
                # Aggregate data from People_Count (excluding cumulative markers)
                cursor.execute("""
                    SELECT 
                        COUNT(*) AS total_counts,
                        AVG(people_count) AS avg_people_count,
                        MAX(people_count) AS max_people_count
                    FROM People_Count
                    WHERE session_id = %s
                """, (session_id,))
                counts = cursor.fetchone()
                
                # Aggregate data from Crowd_Density
                cursor.execute("""
                    SELECT 
                        AVG(crowd_density) AS avg_density,
                        MAX(crowd_density) AS max_density
                    FROM Crowd_Density
                    WHERE session_id = %s
                """, (session_id,))
                density = cursor.fetchone()
                
                # Aggregate data from Air_Quality
                cursor.execute("""
                    SELECT 
                        AVG(air_quality) AS avg_mq2,
                        MAX(air_quality) AS max_mq2,
                        MIN(air_quality) AS min_mq2
                    FROM Air_Quality
                    WHERE session_id = %s
                """, (session_id,))
                air_quality = cursor.fetchone()
                
                history.append({
                    'session_id': session_id,
                    'start_time': session['start_time'].strftime('%Y-%m-%d %H:%M:%S') if session['start_time'] else 'N/A',
                    'end_time': session['end_time'].strftime('%Y-%m-%d %H:%M:%S') if session['end_time'] else 'N/A',
                    'total_counts': counts['total_counts'] or 0,
                    'avg_people_count': float(counts['avg_people_count'] or 0),
                    'max_people_count': counts['max_people_count'] or 0,
                    'total_people': cumulative_total,  # CUMULATIVE TOTAL!
                    'avg_density': float(density['avg_density'] or 0),
                    'max_density': float(density['max_density'] or 0),
                    'avg_mq2': float(air_quality['avg_mq2'] or 0),
                    'max_mq2': float(air_quality['max_mq2'] or 0),
                    'min_mq2': float(air_quality['min_mq2'] or 0)
                })
            
            cursor.close()
            print(f"✅ Retrieved {len(history)} session records (cumulative totals calculated)")
            return history
            
        except Error as e:
            print(f"❌ Error fetching session history: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def close(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("✅ Database connection closed")