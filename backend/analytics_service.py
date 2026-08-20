"""
Radiology PC Tracker v1 - Hourly PC Analytics & Usage Statistics Service
Records hourly PC occupancy rates and provides usage analytics graphs.
"""

import time
import logging
from typing import Dict, Any, List

logger = logging.getLogger("analytics_service")

class AnalyticsService:
    def __init__(self, db_instance, state_manager_instance):
        self.db = db_instance
        self.state_manager = state_manager_instance

    def record_hourly_snapshot(self) -> Dict[str, Any]:
        """Captures an hourly snapshot of PC states across rooms."""
        now = time.localtime()
        hour_label = f"{now.tm_year}-{now.tm_mon:02d}-{now.tm_mday:02d} {now.tm_hour:02d}:00"
        
        all_pcs = self.state_manager.get_all_computers()
        counts = {
            "active": sum(1 for p in all_pcs if p.get("status") == "active"),
            "idle": sum(1 for p in all_pcs if p.get("status") == "idle"),
            "lunch-break": sum(1 for p in all_pcs if p.get("status") == "lunch-break"),
            "offline": sum(1 for p in all_pcs if p.get("status") == "offline"),
            "suspicious": sum(1 for p in all_pcs if p.get("status") == "suspicious"),
            "total": len(all_pcs)
        }

        history = self.db.state.setdefault("hourly_history", [])
        snapshot = {
            "timestamp": time.time(),
            "hour_label": hour_label,
            "counts": counts
        }
        
        history.append(snapshot)
        # Keep last 168 hours (7 days)
        if len(history) > 168:
            self.db.state["hourly_history"] = history[-168:]

        return snapshot

    def get_analytics_summary(self) -> Dict[str, Any]:
        """Returns summary statistics for the dashboard charts."""
        all_pcs = self.state_manager.get_all_computers()
        history = self.db.state.get("hourly_history", [])
        
        # Room utilization breakdown
        rooms = {}
        for pc in all_pcs:
            r = pc.get("room", "Genel")
            if r not in rooms:
                rooms[r] = {"total": 0, "active": 0, "idle": 0, "offline": 0}
            rooms[r]["total"] += 1
            st = pc.get("status", "offline")
            if st in rooms[r]:
                rooms[r][st] += 1

        return {
            "total_computers": len(all_pcs),
            "room_breakdown": rooms,
            "hourly_history": history[-24:] # Last 24 hours
        }
