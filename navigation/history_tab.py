"""
History Tab - FINAL WORKING VERSION
Auto-refresh after delete + Working refresh button
"""
import gradio as gr
from db.db_manager import db_manager
from datetime import datetime

db = db_manager()

def delete_session(session_id):
    """Simple wrapper - just calls db.delete_session()"""
    try:
        print(f"\n🗑️ Deleting session #{session_id}...")
        
        # Call YOUR db_manager function
        success = db.delete_session(session_id)
        
        if success:
            print(f"✅ Session #{session_id} deleted successfully!\n")
            return f"✅ Session #{session_id} deleted successfully!"
        else:
            print(f"❌ Failed to delete session #{session_id}\n")
            return f"❌ Failed to delete session #{session_id}"
    
    except Exception as e:
        print(f"❌ Error deleting session: {e}\n")
        return f"❌ Error: {e}"

def create_history_tab():
    """Create history tab with delete buttons inside session boxes"""
    with gr.Tab("📜 Data History"):
        gr.HTML("""
        <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    color: white; border-radius: 10px; margin-bottom: 20px;'>
            <h2 style='margin: 0;'>📂 Session History & Analytics</h2>
            <p style='margin: 5px 0 0 0;'>Historical data from completed sessions</p>
        </div>
        """)
        
        # Status message at top
        status_msg = gr.Textbox(label="📋 Status", value="", interactive=False, lines=2)
        
        # Refresh button
        refresh_btn = gr.Button("🔄 Refresh History", variant="primary", size="lg")
        
        # Custom CSS for session boxes AND scrollable container
        gr.HTML("""
        <style>
        .session-box {
            background: rgba(255,255,255,0.05) !important;
            padding: 20px !important;
            border-radius: 10px !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
            margin-bottom: 15px !important;
        }
        
        /* Scrollable history container - STRONGER CSS */
        #history_scrollable_container {
            max-height: 600px !important;
            overflow-y: auto !important;
            overflow-x: hidden !important;
            padding-right: 10px !important;
            display: block !important;
        }
        
        /* Force scrollbar to always show styling */
        #history_scrollable_container > div {
            max-height: none !important;
        }
        
        /* Custom scrollbar */
        #history_scrollable_container::-webkit-scrollbar {
            width: 10px !important;
        }
        
        #history_scrollable_container::-webkit-scrollbar-track {
            background: rgba(255,255,255,0.05) !important;
            border-radius: 10px !important;
        }
        
        #history_scrollable_container::-webkit-scrollbar-thumb {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            border-radius: 10px !important;
        }
        
        #history_scrollable_container::-webkit-scrollbar-thumb:hover {
            background: linear-gradient(135deg, #764ba2 0%, #667eea 100%) !important;
        }
        </style>
        """)
        
        # Get history data
        history_data = db.get_session_history()
        
        # Scrollable container for history
        with gr.Column(elem_id="history_scrollable_container") as history_container:
            
            if not history_data:
                gr.HTML("""
                <div style='text-align: center; color: rgba(255,255,255,0.7); padding: 50px; 
                            background: rgba(255,255,255,0.05); border-radius: 10px;'>
                    📭 No session history available in database.
                </div>
                """)
            else:
                # Header
                gr.HTML(f"""
                <div style='padding: 15px; background: rgba(102, 126, 234, 0.1); border-radius: 10px; margin-bottom: 20px;'>
                    <h3 style='margin: 0; color: #a0c4ff;'>📜 Total Sessions: {len(history_data)}</h3>
                </div>
                """)
                
                # Store all delete buttons and their corresponding columns
                delete_buttons = []
                session_columns = []
                
                # Add each session
                for session in history_data:
                    # Calculate duration
                    duration = "N/A"
                    if session.get('start_time') and session.get('end_time') and session.get('end_time') != 'N/A':
                        try:
                            if isinstance(session['start_time'], str):
                                start_time = datetime.fromisoformat(session['start_time'].replace('Z', '+00:00'))
                            else:
                                start_time = session['start_time']
                            
                            if isinstance(session['end_time'], str):
                                end_time = datetime.fromisoformat(session['end_time'].replace('Z', '+00:00'))
                            else:
                                end_time = session['end_time']
                            
                            duration_delta = end_time - start_time
                            hours, remainder = divmod(duration_delta.seconds, 3600)
                            minutes, _ = divmod(remainder, 60)
                            duration = f"{hours}h {minutes}m"
                        except Exception as e:
                            print(f"⚠️ Error calculating duration: {e}")
                    
                    # Format timestamps
                    start_display = session.get('start_time', 'N/A')
                    end_display = session.get('end_time', 'N/A')
                    if isinstance(start_display, datetime):
                        start_display = start_display.strftime('%Y-%m-%d %H:%M:%S')
                    if isinstance(end_display, datetime):
                        end_display = end_display.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Get statistics
                    avg_people_val = session.get('avg_people_count')
                    avg_people = f"{avg_people_val:.1f}" if avg_people_val else "0.0"
                    max_count = session.get('max_people_count', 0) or 0
                    total_people = session.get('total_people', 0) or 0
                    avg_density_val = session.get('avg_density')
                    avg_density = f"{avg_density_val:.2f}" if avg_density_val else "0.00"
                    avg_mq2_val = (session.get('avg_air_quality') or session.get('avg_mq2') or session.get('mq2_avg'))
                    avg_mq2 = f"{avg_mq2_val:.1f} ppm" if avg_mq2_val else "N/A"
                    total_counts = session.get('total_counts', 0) or 0
                    session_id = session.get('session_id', 'Unknown')
                    
                    # Create a Column with custom styling (session box)
                    with gr.Column(elem_classes="session-box", visible=True) as session_col:
                        # Session header with delete button in same row
                        with gr.Row():
                            gr.HTML(f"""
                            <div style="flex: 1;">
                                <strong style="color: #a0c4ff; font-size: 18px;">📋 Session #{session_id}</strong>
                                <span style="background: #667eea; color: white; padding: 5px 15px; 
                                             border-radius: 20px; font-size: 12px; margin-left: 10px;">✓ Completed</span>
                            </div>
                            """)
                            
                            # Delete button in the same row (INSIDE the box)
                            delete_btn = gr.Button(
                                "🗑️ Delete",
                                variant="stop",
                                size="sm",
                                scale=0,
                                min_width=100
                            )
                            
                            # Store button, session_id, and column for wiring up later
                            delete_buttons.append((delete_btn, session_id, session_col))
                        
                        # Session stats
                        gr.HTML(f"""
                        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; 
                                    color: rgba(255,255,255,0.8); margin-top: 15px;">
                            <div style="background: rgba(102, 126, 234, 0.1); padding: 10px; border-radius: 5px;">
                                <strong>Start Time:</strong><br>{start_display}
                            </div>
                            <div style="background: rgba(102, 126, 234, 0.1); padding: 10px; border-radius: 5px;">
                                <strong>End Time:</strong><br>{end_display}
                            </div>
                            <div style="background: rgba(46, 134, 171, 0.1); padding: 10px; border-radius: 5px;">
                                <strong>Duration:</strong><br>{duration}
                            </div>
                            <div style="background: rgba(46, 134, 171, 0.1); padding: 10px; border-radius: 5px;">
                                <strong>Data Points:</strong><br>{total_counts}
                            </div>
                            <div style="background: rgba(86, 171, 47, 0.1); padding: 10px; border-radius: 5px;">
                                <strong>👥 Avg People/Count:</strong><br>{avg_people}
                            </div>
                            <div style="background: rgba(86, 171, 47, 0.1); padding: 10px; border-radius: 5px;">
                                <strong>📈 Max Count:</strong><br>{max_count}
                            </div>
                            <div style="background: rgba(138, 43, 226, 0.1); padding: 10px; border-radius: 5px;">
                                <strong>📊 Session Total:</strong><br>
                                <span style="color: #a0c4ff; font-weight: bold;">{total_people}</span>
                            </div>
                            <div style="background: rgba(168, 224, 99, 0.1); padding: 10px; border-radius: 5px;">
                                <strong>📊 Avg Density:</strong><br>{avg_density}
                            </div>
                            <div style="background: rgba(255, 152, 0, 0.1); padding: 10px; border-radius: 5px;">
                                <strong>🌡️ MQ2 Quality:</strong><br>{avg_mq2}
                            </div>
                        </div>
                        """)
                        
                        # Store the column
                        session_columns.append(session_col)
                        
                        # Add spacing between sessions
                        gr.HTML("<div style='height: 15px;'></div>")
                
                # NOW wire up all the delete buttons (after all sessions are created)
                for delete_btn, session_id, session_col in delete_buttons:
                    # Use default parameter to capture values correctly
                    delete_btn.click(
                        fn=lambda sid=session_id: delete_session(sid),
                        outputs=[status_msg]
                    ).then(
                        # Hide the session box after successful delete
                        fn=lambda: gr.update(visible=False),
                        outputs=[session_col]
                    )
        
        # Helper function to show refresh message
        def show_refresh_message():
            """Show message that user should manually refresh if needed"""
            history_data = db.get_session_history()
            
            if not history_data:
                return "📭 No sessions in database"
            
            visible_sessions = sum(1 for col in session_columns if col.visible)
            return f"✅ History updated! Showing {visible_sessions} session(s). Deleted sessions are hidden."
        
        # Refresh button - just update message, no page reload
        refresh_btn.click(
            fn=show_refresh_message,
            outputs=[status_msg]
        )
        
        gr.Markdown("""
        ---
        ### 💡 Tips:
        - Deleted sessions **disappear immediately** from the list
        - Click **🔄 Refresh History** to check for new sessions
        - To see newly added sessions, refresh the browser manually (F5)
        
        ### ⚠️ Note:
        - If you have an active session running, don't refresh the browser!
        - The History tab updates automatically when sessions are deleted
        """)
        
        gr.Markdown("""
        ---
        ### 💡 Usage:
        - Click **🗑️ Delete** button inside any session box to remove it
        - Session card will disappear immediately after deletion
        - Click **🔄 Refresh History** to reload the page with updated data
        
        ### ⚠️ Warning:
        - Deletion is **permanent** and cannot be undone
        - This removes: People Count, Crowd Density, Air Quality records
        
        ### 🔄 Refresh:
        - The refresh button reloads the entire page to show the latest data
        - Sessions are automatically hidden after deletion
        """)
        
        return {"status": status_msg}