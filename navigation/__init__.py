"""
Tabs package initialization
"""
from .dashboard_tab import create_dashboard_tab
from .control_tab import create_control_tab
from .history_tab import create_history_tab

__all__ = ['create_dashboard_tab', 'create_control_tab', 'create_history_tab']