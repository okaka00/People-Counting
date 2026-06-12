"""
Dashboard Tab - UPDATED WITH IMPROVED AIR QUALITY + PDF DOWNLOAD
- Density graphs show current counts only (not cumulative)
- Gas Quality Index (0-400 scale) based on MQ2 sensor
- Accurate MQ2 thresholds and status
- PDF report download functionality
"""
import gradio as gr
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
import requests
import os
from app_utils.state import car_state, JETSON_STREAM_URL
from app_utils.email_notifications import send_report_email, alert_tracker

# PDF generation imports
from reportlab.lib.pagesizes import letter # type: ignore
from reportlab.lib import colors # type: ignore
from reportlab.lib.units import inch # type: ignore
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer # type: ignore
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle # type: ignore
from reportlab.lib.enums import TA_CENTER, TA_LEFT # type: ignore

# ========================================
# MQ2 TO GAS QUALITY INDEX CONVERSION
# ========================================

def mq2_to_gas_quality_index(mq2_value):
    """
    MQ2 Scale:
    - 0-300 ppm:     Excellent (0-50 GQI)
    - 300-500 ppm:   Good (50-100 GQI)
    - 500-1000 ppm:  Moderate (100-200 GQI)
    - 1000-2000 ppm: Unhealthy (200-300 GQI)
    - 2000+ ppm:     Dangerous (300-400 GQI)
    """
    if mq2_value < 300:
        return (mq2_value / 300) * 50
    elif mq2_value < 500:
        return 50 + ((mq2_value - 300) / 200) * 50
    elif mq2_value < 1000:
        return 100 + ((mq2_value - 500) / 500) * 100
    elif mq2_value < 2000:
        return 200 + ((mq2_value - 1000) / 1000) * 100
    else:
        return min(300 + ((mq2_value - 2000) / 2000) * 100, 400)

def get_air_quality_status(mq2_value):
   
    if mq2_value < 300:
        return "Excellent"
    elif mq2_value < 500:
        return "Good"
    elif mq2_value < 1000:
        return "Moderate"
    elif mq2_value < 2000:
        return "Unhealthy"
    else:
        return "Dangerous"

def get_status_color(status):
    """Get color for status"""
    color_map = {
        "Excellent": "#4caf50",
        "Good": "#8bc34a",
        "Moderate": "#ff9800",
        "Unhealthy": "#ff5722",
        "Dangerous": "#f44336"
    }
    return color_map.get(status, "#999")

# ========================================
# DASHBOARD UPDATE
# ========================================

def update_dashboard():
    """Update all dashboard statistics and graphs"""
    current_count = car_state["people_count"]
    total_count = car_state["total_people"]
    
    # Use CURRENT counts only for density (not cumulative)
    current_counts = car_state.get("current_density_data", [])
    avg_density = np.mean(current_counts[-10:]) if current_counts else 0
    
    density_fig = create_density_heatmap()
    timeseries_fig = create_timeseries_graph()
    
    update_air_quality()
    air_quality_fig = create_air_quality_gauge()
    
    aq = car_state["air_quality"]
    mq2_val = aq.get('mq2', 0)
    gqi_val = aq.get('gqi', 0)
    status = aq.get('status', 'Unknown')
    status_color = get_status_color(status)
    
    # Format MQ2 display
    if isinstance(mq2_val, (int, float)):
        mq2_display = f"{mq2_val:.0f}"
    else:
        mq2_display = "N/A"
    
    air_quality_text = f"""
    <div class="aq-card">
        <h3 class="aq-title">🌡️ Environmental Metrics</h3>
        <div class="aq-grid">
            <div class="aq-box">
                <div class="aq-label">MQ2 Gas Sensor</div>
                <div class="aq-val">{mq2_display}</div>
                <div class="aq-unit">ppm</div>
            </div>
            <div class="aq-box">
                <div class="aq-label">Gas Quality Index</div>
                <div class="aq-val">{gqi_val:.0f}</div>
                <div class="aq-unit">/ 400</div>
            </div>
            <div class="aq-box">
                <div class="aq-label">Status</div>
                <div class="aq-val" style="color: {status_color};">{status}</div>
                <div class="aq-unit">Air Quality</div>
            </div>
        </div>
    </div>
    """
    
    return (
        current_count,
        total_count,
        f"{avg_density:.2f}",
        density_fig,
        timeseries_fig,
        air_quality_fig,
        air_quality_text
    )

# ========================================
# DENSITY VISUALIZATIONS
# ========================================

def create_density_heatmap():
    """
    Create density heatmap showing people distribution
    Uses CURRENT counts only (not cumulative totals)
    """
    # Get current counts (not cumulative)
    current_counts = car_state.get("current_density_data", [])
    
    if current_counts:
        data = current_counts[-20:]  # Last 20 current counts
        x = list(range(len(data)))
        y = [1] * len(data)
        z = [[d] for d in data]
    else:
        x = list(range(10))
        y = [1]
        z = [[0] * 10]
    
    fig = go.Figure(data=go.Heatmap(
        z=z, x=x, y=y,
        colorscale='YlOrRd',
        colorbar=dict(title="Count")
    ))
    
    fig.update_layout(
        title="People Count Heatmap (Current Counts - Recent History)",
        xaxis_title="Time Interval",
        yaxis_title="",
        height=300,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color="white"),
    )
    
    return fig

def create_timeseries_graph():
    """
    Create time series graph of people count
    Shows CURRENT counts over time (not cumulative)
    """
    # Initialize current_density_data if not exists
    if "current_density_data" not in car_state:
        car_state["current_density_data"] = []
    
    # Add current count (not cumulative)
    current_count = car_state["people_count"]
    car_state["current_density_data"].append(current_count)
    
    # Keep only last 100 data points
    if len(car_state["current_density_data"]) > 100:
        car_state["current_density_data"].pop(0)
    
    # Get recent data points (current counts only)
    data_points = car_state["current_density_data"][-20:]
    times = [datetime.now() - timedelta(seconds=i*2) for i in range(len(data_points))]
    times.reverse()
    
    df = pd.DataFrame({
        'Time': times,
        'People Count': data_points
    })
    
    fig = px.line(df, x='Time', y='People Count', 
                  title='People Count Over Time (Current Counts - Live)',
                  markers=True)
    
    fig.update_layout(
        height=400,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color="white"),
    )
    fig.update_traces(line_color='#2E86AB', line_width=3)
    
    return fig

# ========================================
# AIR QUALITY - UPDATED
# ========================================

def update_air_quality():
    """Fetch MQ2 sensor data from Jetson Flask API - IMPROVED"""
    try:
        response = requests.get(f"http://{JETSON_STREAM_URL}:8000/sensor/latest", timeout=1)
        data = response.json()
        mq2_value = data.get("mq2", 0)
        
        # Convert to number if needed
        if isinstance(mq2_value, str):
            try:
                mq2_value = float(mq2_value) if mq2_value != "N/A" else 0
            except:
                mq2_value = 0
        
        # Calculate Gas Quality Index from MQ2
        gqi = mq2_to_gas_quality_index(mq2_value)
        status = get_air_quality_status(mq2_value)
        
        car_state["air_quality"] = {
            "mq2": mq2_value,
            "gqi": gqi,  # Gas Quality Index (0-400)
            "status": status
        }
    except Exception as e:
        print(f"⚠️ Could not fetch sensor data: {e}")
        car_state["air_quality"] = {
            "mq2": "N/A",
            "gqi": 0,
            "status": "Unknown"
        }

def create_air_quality_gauge():
    """Create gauge chart for Gas Quality Index (0-400 scale)"""
    aq = car_state["air_quality"]
    
    # Get Gas Quality Index
    if isinstance(aq.get("gqi"), (int, float)):
        gqi = aq["gqi"]
    else:
        gqi = 0
    
    # Get MQ2 value and status for display
    mq2_value = aq.get("mq2", "N/A")
    if isinstance(mq2_value, (int, float)):
        mq2_display = f"{mq2_value:.0f}"
    else:
        mq2_display = "N/A"
    
    status = aq.get("status", "Unknown")
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=gqi,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': f"Gas Quality Index<br><sub>MQ2: {mq2_display} ppm | {status}</sub>"},
        gauge={
            'axis': {'range': [None, 400]},  # ← 400 maximum!
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 50], 'color': "lightgreen"},      # Excellent
                {'range': [50, 100], 'color': "yellow"},        # Good
                {'range': [100, 200], 'color': "orange"},       # Moderate
                {'range': [200, 300], 'color': "orangered"},    # Unhealthy
                {'range': [300, 400], 'color': "darkred"}       # Dangerous
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 300  # Critical threshold at 300 GQI (2000 ppm)
            }
        }
    ))
    
    fig.update_layout(
        height=300,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color="white"),
    )
    return fig

# ========================================
# HTML REPORT GENERATION
# ========================================

def generate_report():
    """Generate a detailed HTML report"""
    if not car_state["session_active"]:
        return "<p style='color: #ff6b6b;'>⚠️ No active session to report</p>"
    
    duration = datetime.now() - car_state["session_start_time"]
    hours, remainder = divmod(duration.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    aq = car_state["air_quality"]
    mq2_value = aq.get('mq2', 0)
    gqi_value = aq.get('gqi', 0)
    status = aq.get('status', 'Unknown')
    
    # Format MQ2 display
    if isinstance(mq2_value, (int, float)):
        mq2_display = f"{mq2_value:.0f} ppm"
    else:
        mq2_display = 'N/A'
    
    # Calculate average of CURRENT counts (not cumulative)
    current_counts = car_state.get("current_density_data", [])
    avg_current_density = np.mean(current_counts) if current_counts else 0
    
    report = f"""
    <div class="report-card">
        <div class="report-header">
            <h1 class="report-h1">📊 MONITORING REPORT</h1>
            <p class="report-sub">Robotics Car People Counting System</p>
        </div>
        
        <h2 class="report-section-title">Session Information</h2>
        <table class="report-table">
            <tr>
                <td style="width: 40%;"><strong>Session ID:</strong></td>
                <td>#{car_state['session_id']}</td>
            </tr>
            <tr>
                <td><strong>Start Time:</strong></td>
                <td>{car_state['session_start_time'].strftime('%Y-%m-%d %H:%M:%S')}</td>
            </tr>
            <tr>
                <td><strong>Duration:</strong></td>
                <td>{hours}h {minutes}m {seconds}s</td>
            </tr>
            <tr>
                <td><strong>Report Generated:</strong></td>
                <td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td>
            </tr>
        </table>
        
        <h2 class="report-section-title">People Counting Statistics</h2>
        <div class="report-stat-grid">
            <div class="stat-card grad-purple">
                <div class="stat-label">Current Video/Image</div>
                <div class="stat-val">{car_state['people_count']}</div>
                <div style="font-size: 0.8em; opacity: 0.8;">Latest count</div>
            </div>
            <div class="stat-card grad-blue">
                <div class="stat-label">Session Total (Cumulative)</div>
                <div class="stat-val">{car_state['total_people']}</div>
                <div style="font-size: 0.8em; opacity: 0.8;">All videos/images</div>
            </div>
            <div class="stat-card grad-green">
                <div class="stat-label">Avg Density</div>
                <div class="stat-val">{avg_current_density:.2f}</div>
                <div style="font-size: 0.8em; opacity: 0.8;">Current counts avg</div>
            </div>
        </div>
        
        <h2 class="report-section-title">Environmental Data</h2>
        <table class="report-table">
            <tr>
                <td style="width: 40%;"><strong>MQ2 Gas Sensor:</strong></td>
                <td>{mq2_display}</td>
            </tr>
            <tr>
                <td><strong>Gas Quality Index:</strong></td>
                <td>{gqi_value:.0f} / 400 ({status})</td>
            </tr>
            <tr>
                <td><strong>Alert Status:</strong></td>
                <td>High: {alert_tracker.high_alert_count} | Critical: {alert_tracker.critical_alert_count}</td>
            </tr>
        </table>
        
        <div style="background: rgba(33, 150, 243, 0.2); border-left: 4px solid #2196F3; padding: 15px; margin: 20px 0; border-radius: 8px;">
            <strong style="color: #4fc3f7;">ℹ️ System Information:</strong><br>
            <span style="color: #e0e6ed;">• Detection System: YOLOv5 + DeepSORT</span><br>
            <span style="color: #e0e6ed;">• Air Quality Sensor: MQ2 Gas Sensor</span><br>
            <span style="color: #e0e6ed;">• Gas Quality Index: 0-400 scale</span><br>
            <span style="color: #e0e6ed;">• Data Points Collected: {len(current_counts)}</span><br>
            <span style="color: #e0e6ed;">• Density graphs show current counts (not cumulative totals)</span>
        </div>
        
        <div class="report-footer">
            <p><strong>Robotics Car People Counting System</strong></p>
            <p>© 2024 | Automated Monitoring Report</p>
            <p style="margin-top: 20px;">
                Report ID: Session #{car_state['session_id']}<br>
                Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </p>
        </div>
    </div>
    """
    
    return report

# ========================================
# PDF REPORT GENERATION - NEW!
# ========================================

def generate_pdf_report():
    """Generate PDF report and return filepath for download"""
    if not car_state["session_active"]:
        return None, "❌ No active session to report"
    
    try:
        current_dir = os.getcwd()
        output_dir = os.path.join(current_dir, "reports")
        
        # Create reports directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        session_id = car_state.get("session_id", "unknown")
        filename = f"session_report_{session_id}_{timestamp}.pdf"
        filepath = os.path.join(output_dir, filename)
        
        # Create PDF document
        doc = SimpleDocTemplate(filepath, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#667eea'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#667eea'),
            spaceAfter=12,
            spaceBefore=20
        )
        
        # Title
        story.append(Paragraph("📊 MONITORING REPORT", title_style))
        story.append(Paragraph("Robotics Car People Counting System", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Session Information
        duration = datetime.now() - car_state["session_start_time"]
        hours, remainder = divmod(duration.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        story.append(Paragraph("Session Information", heading_style))
        
        session_data = [
            ['Session ID:', f"#{car_state['session_id']}"],
            ['Start Time:', car_state['session_start_time'].strftime('%Y-%m-%d %H:%M:%S')],
            ['Duration:', f"{hours}h {minutes}m {seconds}s"],
            ['Report Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
        ]
        
        session_table = Table(session_data, colWidths=[2*inch, 4*inch])
        session_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f5')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#667eea')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        story.append(session_table)
        story.append(Spacer(1, 0.3*inch))
        
        # People Counting Statistics
        story.append(Paragraph("People Counting Statistics", heading_style))
        
        current_counts = car_state.get("current_density_data", [])
        avg_current_density = np.mean(current_counts) if current_counts else 0
        max_current = max(current_counts) if current_counts else 0
        
        people_data = [
            ['Current Count (Latest):', str(car_state['people_count'])],
            ['Session Total (Cumulative):', str(car_state['total_people'])],
            ['Average Density:', f"{avg_current_density:.2f}"],
            ['Maximum Count:', str(max_current)],
            ['Data Points Collected:', str(len(current_counts))]
        ]
        
        people_table = Table(people_data, colWidths=[2.5*inch, 3.5*inch])
        people_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f5')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#667eea')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        story.append(people_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Environmental Data
        story.append(Paragraph("Environmental Data", heading_style))
        
        aq = car_state["air_quality"]
        mq2_value = aq.get('mq2', 0)
        gqi_value = aq.get('gqi', 0)
        status = aq.get('status', 'Unknown')
        
        if isinstance(mq2_value, (int, float)):
            mq2_display = f"{mq2_value:.0f} ppm"
        else:
            mq2_display = 'N/A'
        
        # Get alert stats
        alert_stats = alert_tracker.get_stats()
        
        env_data = [
            ['MQ2 Gas Sensor:', mq2_display],
            ['Gas Quality Index:', f"{gqi_value:.0f} / 400"],
            ['Air Quality Status:', status],
            ['High Alerts Sent:', str(alert_stats.get('high_alert_count', 0))],
            ['Critical Alerts Sent:', str(alert_stats.get('critical_alert_count', 0))],
            ['Air Quality Alerts:', str(alert_stats.get('air_quality_alert_count', 0))],
            ['Critical Air Alerts:', str(alert_stats.get('critical_air_alert_count', 0))]
        ]
        
        env_table = Table(env_data, colWidths=[2.5*inch, 3.5*inch])
        env_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f5')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#667eea')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        story.append(env_table)
        story.append(Spacer(1, 0.3*inch))
        
        # System Information
        story.append(Paragraph("System Information", heading_style))
        
        info_text = """
        • Detection System: YOLOv5 + DeepSORT<br/>
        • Air Quality Sensor: MQ2 Gas Sensor<br/>
        • Gas Quality Index: 0-400 scale (0-50: Excellent, 50-100: Good, 100-200: Moderate, 200-300: Unhealthy, 300-400: Dangerous)<br/>
        • Density graphs show current counts (not cumulative totals)
        """
        story.append(Paragraph(info_text, styles['Normal']))
        story.append(Spacer(1, 0.5*inch))
        
        # Footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
        
        story.append(Paragraph("Robotics Car People Counting System", footer_style))
        story.append(Paragraph("© 2024 | Automated Monitoring Report", footer_style))
        story.append(Paragraph(f"Report ID: Session #{car_state['session_id']} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", footer_style))
        
        # Build PDF
        doc.build(story)
        
        print(f"✅ PDF report generated: {filepath}")
        return filepath, f"✅ Report generated: {filename}"
        
    except Exception as e:
        print(f"❌ Error generating PDF: {e}")
        import traceback
        traceback.print_exc()
        return None, f"❌ Failed to generate PDF: {str(e)}"

# ========================================
# EMAIL REPORT
# ========================================

def email_report():
    """Email the report to user"""
    user_email = car_state.get("user_email")
    
    if not user_email or "@" not in user_email:
        return "❌ No email address found. Please start a new session with your email."
    
    if not car_state["session_active"]:
        return "❌ No active session. Start a session first."
    
    # Prepare session data
    duration = datetime.now() - car_state["session_start_time"]
    hours, remainder = divmod(duration.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    session_data = {
        "session_id": car_state.get("session_id", "N/A"),
        "start_time": car_state['session_start_time'].strftime('%Y-%m-%d %H:%M:%S'),
        "end_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "duration": f"{hours}h {minutes}m"
    }
    
    # Use current counts for stats (not cumulative)
    current_counts = car_state.get("current_density_data", [])
    
    # Get MQ2 value
    mq2_value = car_state.get("air_quality", {}).get("mq2", 0)
    if isinstance(mq2_value, (int, float)):
        avg_mq2 = mq2_value
    else:
        avg_mq2 = 0
    
    stats = {
        "total_people": car_state.get("total_people", 0),  # Cumulative
        "avg_count": np.mean(current_counts) if current_counts else 0,  # Avg of current
        "max_count": max(current_counts) if current_counts else 0,  # Max of current
        "data_points": len(current_counts),
        "avg_mq2": avg_mq2,
        "avg_density": np.mean(current_counts) if current_counts else 0,
        **alert_tracker.get_stats()
    }
    
    # Send report email
    print(f"📧 Sending report to {user_email}...")
    success = send_report_email(user_email, session_data, stats)
    
    if success:
        return f"✅ Report sent to {user_email}!\n\nCheck your inbox for the detailed session report."
    else:
        return f"❌ Failed to send report to {user_email}\n\nPlease check your email configuration."

# ========================================
# CREATE DASHBOARD TAB
# ========================================

def create_dashboard_tab():
    """Create and return the dashboard tab component"""
    with gr.Tab("📊 Dashboard"):
        gr.HTML("""
        <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 10px; margin-bottom: 20px;'>
            <h2 style='margin: 0;'>📈 Statistics & Analytics</h2>
            <p style='margin: 5px 0 0 0;'>Real-time data from OpenCV YOLO processor</p>
        </div>
        """)
        
        with gr.Row():
            with gr.Column(scale=1):
                current_people = gr.Number(label="👥 Current Count (Latest Video/Image)", value=0, interactive=False)
            with gr.Column(scale=1):
                total_people = gr.Number(label="📈 Total Count (Session Cumulative)", value=0, interactive=False)
            with gr.Column(scale=1):
                avg_density = gr.Textbox(label="📊 Avg Density (Current Counts)", value="0.00", interactive=False)
        
        gr.HTML("""
        <div style='background: rgba(255, 193, 7, 0.2); border-left: 4px solid #FFC107; padding: 12px; margin: 15px 0; border-radius: 6px;'>
            <strong style='color: #FFD54F;'>ℹ️ Note:</strong>
            <span style='color: #e0e6ed;'>Density graphs show <strong>current counts</strong> from each video/image, not cumulative totals.</span>
        </div>
        """)
        
        with gr.Row():
            with gr.Column():
                density_plot = gr.Plot(label="Density Heatmap (Current Counts)")
            with gr.Column():
                timeseries_plot = gr.Plot(label="Time Series (Current Counts)")
        
        gr.HTML("<h2 style='margin-top: 30px;'>🌍 Environmental Air Quality</h2>")
        
        with gr.Row():
            with gr.Column(scale=2):
                air_quality_gauge = gr.Plot(label="Gas Quality Index (0-400)")
            with gr.Column(scale=1):
                air_quality_text = gr.HTML("")
        
        # UPDATED: Added PDF download button
        with gr.Row():
            refresh_dashboard = gr.Button("🔄 Refresh Dashboard", variant="primary", size="lg", scale=2)
            generate_report_btn = gr.Button("📄 Generate Report (View)", variant="secondary", size="lg", scale=1)
            download_pdf_btn = gr.Button("⬇️ Download PDF", variant="secondary", size="lg", scale=1)
            email_report_btn = gr.Button("📧 Email Report", variant="secondary", size="lg", scale=1)
        
        report_output = gr.HTML(label="Report Preview", visible=True)
        
        # NEW: File download component
        pdf_download = gr.File(label="📄 Download PDF Report", visible=True, interactive=False)
        
        email_status = gr.Textbox(label="Status", visible=True, interactive=False)
        
        # Event handlers
        refresh_dashboard.click(
            fn=update_dashboard,
            inputs=[],
            outputs=[current_people, total_people, avg_density, density_plot, 
                    timeseries_plot, air_quality_gauge, air_quality_text]
        )
        
        generate_report_btn.click(
            fn=generate_report,
            inputs=[],
            outputs=[report_output]
        )
        
        # NEW: PDF download handler
        download_pdf_btn.click(
            fn=generate_pdf_report,
            inputs=[],
            outputs=[pdf_download, email_status]
        )
        
        email_report_btn.click(
            fn=email_report,
            inputs=[],
            outputs=[email_status]
        )
        
        return {
            "current_people": current_people,
            "total_people": total_people,
            "avg_density": avg_density,
            "density_plot": density_plot,
            "timeseries_plot": timeseries_plot,
            "air_quality_gauge": air_quality_gauge,
            "air_quality_text": air_quality_text
        }