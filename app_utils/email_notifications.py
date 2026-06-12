"""
Email notification system using Gmail SMTP
FREE: Unlimited emails through your Gmail account
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from threading import Thread
import time

# ========================================
# GMAIL SMTP CONFIGURATION
# ========================================

# Your Gmail credentials
GMAIL_ADDRESS = "maslinda.ayen@gmail.com"  # ← Change this to your Gmail
GMAIL_APP_PASSWORD = "cdzy lhta dodd djat"  # ← Change this to your App Password

# Gmail SMTP settings (DO NOT CHANGE)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Sender information
SENDER_NAME = "Robotics Car Alert System"

# Alert thresholds
HIGH_DENSITY_THRESHOLD = 50
CRITICAL_DENSITY_THRESHOLD = 100
MQ2_WARNING_THRESHOLD = 300
MQ2_CRITICAL_THRESHOLD = 400  # ← CHANGED: Added critical air threshold


# ========================================
# ALERT TRACKER - UPDATED FOR 4 ALERT TYPES
# ========================================

class AlertTracker:
    """Track alerts to prevent spam - Updated for 4 alert types"""
    def __init__(self):
        # Track last alert time for each type
        self.last_alerts = {
            "critical": 0,          # 100+ people + MQ2 >= 300
            "high": 0,              # 50+ people + MQ2 >= 300
            "air_quality": 0,       # MQ2 >= 300 (any crowd) - NEW
            "critical_air": 0       # MQ2 >= 400 (any crowd) - NEW
        }
        
        # Cooldown periods (in seconds)
        self.cooldown = {
            "critical": 300,        # 5 minutes
            "high": 600,            # 10 minutes
            "air_quality": 600,     # 10 minutes - NEW
            "critical_air": 300     # 5 minutes - NEW
        }
        
        # Alert counts for statistics
        self.alert_counts = {
            "critical": 0,
            "high": 0,
            "air_quality": 0,       # NEW
            "critical_air": 0       # NEW
        }
        
        # Keep old attributes for backward compatibility
        self.last_high_alert = 0
        self.last_critical_alert = 0
        self.high_alert_count = 0
        self.critical_alert_count = 0
    
    def should_send_alert(self, alert_type):
        """Check if enough time has passed since last alert"""
        current_time = time.time()
        
        # Get last alert time
        last_alert_time = self.last_alerts.get(alert_type, 0)
        cooldown_seconds = self.cooldown.get(alert_type, 600)
        
        # Check if cooldown period has passed
        if current_time - last_alert_time >= cooldown_seconds:
            # Update last alert time
            self.last_alerts[alert_type] = current_time
            
            # Increment alert count
            if alert_type in self.alert_counts:
                self.alert_counts[alert_type] += 1
            
            # Update old attributes for backward compatibility
            if alert_type == "high":
                self.last_high_alert = current_time
                self.high_alert_count += 1
            elif alert_type == "critical":
                self.last_critical_alert = current_time
                self.critical_alert_count += 1
            
            return True
        
        # Still in cooldown
        remaining = int(cooldown_seconds - (current_time - last_alert_time))
        print(f"⏳ Alert cooldown: {remaining}s remaining for {alert_type}")
        return False
    
    def reset(self):
        """Reset alert tracker for new session"""
        self.last_alerts = {
            "critical": 0,
            "high": 0,
            "air_quality": 0,
            "critical_air": 0
        }
        self.alert_counts = {
            "critical": 0,
            "high": 0,
            "air_quality": 0,
            "critical_air": 0
        }
        # Reset old attributes
        self.last_high_alert = 0
        self.last_critical_alert = 0
        self.high_alert_count = 0
        self.critical_alert_count = 0
    
    def get_stats(self):
        """Get alert statistics"""
        return {
            "high_alert_count": self.alert_counts["high"],
            "critical_alert_count": self.alert_counts["critical"],
            "air_quality_alert_count": self.alert_counts["air_quality"],       # NEW
            "critical_air_alert_count": self.alert_counts["critical_air"],     # NEW
            "total_alerts": sum(self.alert_counts.values())                    # NEW
        }

# Global alert tracker instance
alert_tracker = AlertTracker()

# ========================================
# GMAIL SMTP FUNCTIONS
# ========================================

def send_email_smtp(to_email, subject, html_body):
    """Send email using Gmail SMTP"""
    try:
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{SENDER_NAME} <{GMAIL_ADDRESS}>"
        message["To"] = to_email
        
        # Attach HTML body
        html_part = MIMEText(html_body, "html")
        message.attach(html_part)
        
        # Connect to Gmail SMTP server
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Secure the connection
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(message)
        
        print(f"✅ Email sent to {to_email}")
        return True
        
    except smtplib.SMTPAuthenticationError:
        print("❌ Authentication failed! Check your Gmail address and App Password")
        print("   Make sure you're using an App Password, not your regular Gmail password")
        return False
    except smtplib.SMTPException as e:
        print(f"❌ SMTP error: {e}")
        return False
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False

def send_email_async(to_email, subject, html_body):
    """Send email in background thread"""
    thread = Thread(target=send_email_smtp, args=(to_email, subject, html_body))
    thread.daemon = True
    thread.start()

# ========================================
# EMAIL TEMPLATES
# ========================================

def test_email(to_email):
    """Send welcome test email"""
    subject = "✅ Welcome - Monitoring System Ready"
    
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center;">
            <h1 style="margin: 0;">🤖 Welcome!</h1>
            <p style="margin: 10px 0 0 0;">Your email notifications are active</p>
        </div>
        <div style="padding: 30px; background: #f5f5f5;">
            <h2 style="color: #667eea;">✅ System Ready</h2>
            <p>Your email address has been successfully registered for monitoring alerts.</p>
            
            <h3 style="color: #667eea;">🌡️ Smart Alert System</h3>
            <p>You will receive email alerts when:</p>
            <ul>
                <li><strong>Critical:</strong> 100+ people + Poor air quality</li>
                <li><strong>High:</strong> 50+ people + Poor air quality</li>
                <li><strong>Air Quality Warning:</strong> Poor air detected (any crowd)</li>
                <li><strong>Critical Air:</strong> Dangerous air levels (any crowd)</li>
            </ul>
            
            <h3 style="color: #667eea;">📊 Report Features</h3>
            <ul>
                <li>Download reports from Dashboard</li>
                <li>Email reports directly to your inbox</li>
            </ul>
            
            <div style="background: white; padding: 20px; border-radius: 10px; margin-top: 20px;">
                <p style="margin: 0; color: #666;">If you did not register for this service, please ignore this email.</p>
            </div>
        </div>
        <div style="text-align: center; padding: 20px; color: #666; font-size: 12px;">
            <p>© 2024 Robotics Car Monitoring System</p>
            <p>Sent via Gmail SMTP</p>
        </div>
    </div>
    """
    
    # Send in background thread
    send_email_async(to_email, subject, html_body)
    return True

def send_alert_email(to_email, people_count, unique_ids, mq2_value, alert_level):
    """Send alert email - UPDATED to support 4 alert types"""
    
    # Determine alert styling based on type
    if alert_level == "critical":
        alert_emoji = "🚨"
        alert_title = "CRITICAL ALERT"
        alert_color = "#d32f2f"
        bg_color = "#ffebee"
        description = "High crowd density with poor air quality detected simultaneously."
    elif alert_level == "high":
        alert_emoji = "⚠️"
        alert_title = "HIGH ALERT"
        alert_color = "#f57c00"
        bg_color = "#fff3e0"
        description = "Elevated crowd density with poor air quality detected."
    elif alert_level == "air_quality":
        alert_emoji = "🌡️"
        alert_title = "AIR QUALITY WARNING"
        alert_color = "#ff9800"
        bg_color = "#fff3e0"
        description = "Poor air quality detected. Ventilation recommended."
    elif alert_level == "critical_air":
        alert_emoji = "🚨🌡️"
        alert_title = "CRITICAL AIR QUALITY"
        alert_color = "#d32f2f"
        bg_color = "#ffebee"
        description = "DANGEROUS air quality levels detected! Immediate action required."
    else:
        alert_emoji = "⚠️"
        alert_title = "ALERT"
        alert_color = "#f57c00"
        bg_color = "#fff3e0"
        description = "Alert condition detected."
    
    # Determine MQ2 status
    if mq2_value >= MQ2_CRITICAL_THRESHOLD:
        mq2_status = "🔴 CRITICAL"
        mq2_color = "#d32f2f"
    elif mq2_value >= MQ2_WARNING_THRESHOLD:
        mq2_status = "⚠️ WARNING"
        mq2_color = "#f57c00"
    else:
        mq2_status = "✅ NORMAL"
        mq2_color = "#4caf50"
    
    subject = f"{alert_emoji} {alert_title} - MQ2: {mq2_value}, People: {people_count}"
    
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: {alert_color}; color: white; padding: 30px; text-align: center;">
            <h1 style="margin: 0; font-size: 32px;">{alert_emoji} {alert_title}</h1>
            <p style="margin: 10px 0 0 0; font-size: 18px;">{description}</p>
        </div>
        
        <div style="padding: 30px; background: #f5f5f5;">
            <div style="background: {bg_color}; padding: 20px; border-radius: 10px; border-left: 5px solid {alert_color};">
                <h2 style="margin: 0; color: {alert_color};">{alert_emoji} {alert_title}</h2>
                <p style="margin: 10px 0 0 0;">{description}</p>
            </div>
            
            <h3 style="color: #667eea; margin-top: 30px;">🌡️ Air Quality (MQ2 Sensor)</h3>
            <table style="width: 100%; background: white; border-radius: 10px; padding: 20px;">
                <tr>
                    <td style="padding: 10px;"><strong>MQ2 Reading:</strong></td>
                    <td style="padding: 10px; text-align: right; font-size: 24px; color: {mq2_color};"><strong>{mq2_value} ppm</strong></td>
                </tr>
                <tr>
                    <td style="padding: 10px;"><strong>Status:</strong></td>
                    <td style="padding: 10px; text-align: right; color: {mq2_color};">{mq2_status}</td>
                </tr>
            </table>
            
            <h3 style="color: #667eea; margin-top: 30px;">👥 Crowd Statistics</h3>
            <table style="width: 100%; background: white; border-radius: 10px; padding: 20px;">
                <tr>
                    <td style="padding: 10px;"><strong>Current People:</strong></td>
                    <td style="padding: 10px; text-align: right; font-size: 24px; color: #667eea;"><strong>{people_count}</strong></td>
                </tr>
                <tr>
                    <td style="padding: 10px;"><strong>Unique People:</strong></td>
                    <td style="padding: 10px; text-align: right; font-size: 20px;">{unique_ids}</td>
                </tr>
                <tr>
                    <td style="padding: 10px;"><strong>Time:</strong></td>
                    <td style="padding: 10px; text-align: right;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td>
                </tr>
            </table>
            
            <div style="background: #e3f2fd; padding: 20px; border-radius: 10px; margin-top: 30px;">
                <h3 style="margin: 0; color: #1976d2;">⚠️ Recommended Actions</h3>
                <ul style="margin: 10px 0; padding-left: 20px;">"""
    
    # Add specific recommendations based on alert type
    if alert_level == "critical":
        html_body += """
                    <li>Implement crowd control measures immediately</li>
                    <li>Improve ventilation if indoors</li>
                    <li>Monitor air quality continuously</li>
                    <li>Consider evacuation if conditions worsen</li>"""
    elif alert_level == "high":
        html_body += """
                    <li>Monitor crowd levels closely</li>
                    <li>Improve ventilation</li>
                    <li>Check air quality regularly</li>"""
    elif alert_level == "air_quality":
        html_body += """
                    <li>Open windows/doors for ventilation</li>
                    <li>Turn on ventilation systems</li>
                    <li>Monitor MQ2 levels closely</li>
                    <li>Identify source of poor air quality</li>"""
    elif alert_level == "critical_air":
        html_body += """
                    <li><strong>STOP all activities</strong></li>
                    <li><strong>Maximum ventilation immediately</strong></li>
                    <li><strong>Consider immediate evacuation</strong></li>
                    <li><strong>Contact safety personnel</strong></li>"""
    
    html_body += """
                </ul>
            </div>
        </div>
        
        <div style="text-align: center; padding: 20px; color: #666; font-size: 12px;">
            <p style="margin: 5px 0;">Alert generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p style="margin: 5px 0;">© 2024 Robotics Car Monitoring System</p>
            <p style="margin: 5px 0;">Sent via Gmail SMTP</p>
        </div>
    </div>
    """
    
    # Send in background thread
    send_email_async(to_email, subject, html_body)
    return True

def send_report_email(to_email, session_data, stats):
    """Send session report email"""
    subject = f"📊 Session Report - {session_data.get('session_id', 'N/A')}"
    
    # Get alert counts with fallback
    high_alerts = stats.get('high_alert_count', 0)
    critical_alerts = stats.get('critical_alert_count', 0)
    air_quality_alerts = stats.get('air_quality_alert_count', 0)
    critical_air_alerts = stats.get('critical_air_alert_count', 0)
    
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center;">
            <h1 style="margin: 0;">📊 Session Report</h1>
            <p style="margin: 10px 0 0 0;">Robotics Car Monitoring System</p>
        </div>
        
        <div style="padding: 30px; background: #f5f5f5;">
            <h2 style="color: #667eea;">Session Information</h2>
            <table style="width: 100%; background: white; border-radius: 10px; padding: 20px;">
                <tr>
                    <td style="padding: 10px;"><strong>Session ID:</strong></td>
                    <td style="padding: 10px;">{session_data.get('session_id', 'N/A')}</td>
                </tr>
                <tr>
                    <td style="padding: 10px;"><strong>Start Time:</strong></td>
                    <td style="padding: 10px;">{session_data.get('start_time', 'N/A')}</td>
                </tr>
                <tr>
                    <td style="padding: 10px;"><strong>End Time:</strong></td>
                    <td style="padding: 10px;">{session_data.get('end_time', 'N/A')}</td>
                </tr>
                <tr>
                    <td style="padding: 10px;"><strong>Duration:</strong></td>
                    <td style="padding: 10px;">{session_data.get('duration', 'N/A')}</td>
                </tr>
            </table>
            
            <h2 style="color: #667eea; margin-top: 30px;">Statistics</h2>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                <div style="background: white; padding: 20px; border-radius: 10px; text-align: center;">
                    <div style="color: #666; font-size: 14px;">Total People</div>
                    <div style="font-size: 32px; font-weight: bold; color: #667eea;">{stats.get('total_people', 0)}</div>
                </div>
                <div style="background: white; padding: 20px; border-radius: 10px; text-align: center;">
                    <div style="color: #666; font-size: 14px;">Max Count</div>
                    <div style="font-size: 32px; font-weight: bold; color: #2E86AB;">{stats.get('max_count', 0)}</div>
                </div>
                <div style="background: white; padding: 20px; border-radius: 10px; text-align: center;">
                    <div style="color: #666; font-size: 14px;">Avg MQ2</div>
                    <div style="font-size: 32px; font-weight: bold; color: #f57c00;">{stats.get('avg_mq2', 0)}</div>
                </div>
                <div style="background: white; padding: 20px; border-radius: 10px; text-align: center;">
                    <div style="color: #666; font-size: 14px;">Data Points</div>
                    <div style="font-size: 32px; font-weight: bold; color: #56AB2F;">{stats.get('data_points', 0)}</div>
                </div>
            </div>
            
            <h2 style="color: #667eea; margin-top: 30px;">Alert History</h2>
            <table style="width: 100%; background: white; border-radius: 10px; padding: 20px;">
                <tr>
                    <td style="padding: 10px;"><strong>🚨 Critical Alerts:</strong></td>
                    <td style="padding: 10px; text-align: right;">{critical_alerts}</td>
                </tr>
                <tr>
                    <td style="padding: 10px;"><strong>⚠️ High Alerts:</strong></td>
                    <td style="padding: 10px; text-align: right;">{high_alerts}</td>
                </tr>
                <tr>
                    <td style="padding: 10px;"><strong>🌡️ Air Quality Alerts:</strong></td>
                    <td style="padding: 10px; text-align: right;">{air_quality_alerts}</td>
                </tr>
                <tr>
                    <td style="padding: 10px;"><strong>🚨🌡️ Critical Air Alerts:</strong></td>
                    <td style="padding: 10px; text-align: right;">{critical_air_alerts}</td>
                </tr>
            </table>
        </div>
        
        <div style="text-align: center; padding: 20px; color: #666; font-size: 12px;">
            <p style="margin: 5px 0;">Report generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p style="margin: 5px 0;">© 2024 Robotics Car Monitoring System</p>
            <p style="margin: 5px 0;">Sent via Gmail SMTP</p>
        </div>
    </div>
    """
    
    # Send in background thread
    send_email_async(to_email, subject, html_body)
    return True

# ========================================
# TESTING FUNCTIONS
# ========================================

def test_connection():
    """Test Gmail SMTP connection"""
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        print("✅ Gmail SMTP connection successful!")
        return True
    except smtplib.SMTPAuthenticationError:
        print("❌ Authentication failed!")
        print("   Check your Gmail address and App Password")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False