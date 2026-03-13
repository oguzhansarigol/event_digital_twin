"""
Zone density and congestion analysis.
Calculates occupancy, density scores, and detects hotspots.
"""
from __future__ import annotations

from typing import Optional

from app.core.config import (
    DENSITY_LOW_THRESHOLD,
    DENSITY_MEDIUM_THRESHOLD,
    DENSITY_HIGH_THRESHOLD,
    DENSITY_CRITICAL_THRESHOLD,
)


class DensityAnalyzer:
    """
    Analyzes zone density and edge congestion in real time.
    """

    def __init__(self, zones_config: dict):
        """
        Args:
            zones_config: dict mapping zone_id -> {"capacity": int, "zone_type": str}
        """
        self.zones_config = zones_config
        self.zone_occupancy: dict[str, set[int]] = {
            zid: set() for zid in zones_config
        }
        self.edge_usage: dict[tuple[str, str], int] = {}

    def add_visitor_to_zone(self, zone_id: str, visitor_id: int) -> None:
        """Record a visitor entering a zone."""
        if zone_id in self.zone_occupancy:
            self.zone_occupancy[zone_id].add(visitor_id)

    def remove_visitor_from_zone(self, zone_id: str, visitor_id: int) -> None:
        """Record a visitor leaving a zone."""
        if zone_id in self.zone_occupancy:
            self.zone_occupancy[zone_id].discard(visitor_id)

    def get_zone_density(self, zone_id: str) -> float:
        """
        Get current density (0.0 to 1.0+) for a zone.
        Values > 1.0 indicate overcrowding.
        """
        if zone_id not in self.zones_config:
            return 0.0
        capacity = self.zones_config[zone_id].get("capacity", 100)
        occupancy = len(self.zone_occupancy.get(zone_id, set()))
        return occupancy / max(capacity, 1)

    def get_zone_occupancy(self, zone_id: str) -> int:
        """Get current occupancy count for a zone."""
        return len(self.zone_occupancy.get(zone_id, set()))

    def get_all_densities(self) -> dict[str, float]:
        """Get density for all zones."""
        return {zid: self.get_zone_density(zid) for zid in self.zones_config}

    def get_all_occupancies(self) -> dict[str, int]:
        """Get occupancy for all zones."""
        return {zid: self.get_zone_occupancy(zid) for zid in self.zones_config}

    def get_density_level(self, zone_id: str) -> str:
        """
        Classify density level.
        Returns: "low", "medium", "high", or "critical"
        """
        density = self.get_zone_density(zone_id)
        if density >= DENSITY_CRITICAL_THRESHOLD:
            return "critical"
        elif density >= DENSITY_HIGH_THRESHOLD:
            return "high"
        elif density >= DENSITY_MEDIUM_THRESHOLD:
            return "medium"
        else:
            return "low"

    def detect_hotspots(self) -> list[dict]:
        """
        Detect zones with high or critical density.
        Returns list of hotspot dicts: {"zone_id", "density", "level", "occupancy", "capacity"}
        """
        hotspots = []
        for zone_id in self.zones_config:
            density = self.get_zone_density(zone_id)
            level = self.get_density_level(zone_id)
            if level in ("high", "critical"):
                capacity = self.zones_config[zone_id].get("capacity", 100)
                hotspots.append({
                    "zone_id": zone_id,
                    "density": round(density, 3),
                    "level": level,
                    "occupancy": self.get_zone_occupancy(zone_id),
                    "capacity": capacity,
                })
        return hotspots

    # ── Edge congestion ──────────────────────────────────

    def increment_edge(self, from_id: str, to_id: str) -> None:
        """Record a visitor traversing an edge."""
        key = tuple(sorted([from_id, to_id]))
        self.edge_usage[key] = self.edge_usage.get(key, 0) + 1

    def decrement_edge(self, from_id: str, to_id: str) -> None:
        """Record a visitor finishing edge traversal."""
        key = tuple(sorted([from_id, to_id]))
        current = self.edge_usage.get(key, 0)
        self.edge_usage[key] = max(0, current - 1)

    def get_edge_congestion(
        self,
        from_id: str,
        to_id: str,
        max_capacity: float = 20.0,
    ) -> float:
        """Get congestion score (0-1) for an edge."""
        key = tuple(sorted([from_id, to_id]))
        count = self.edge_usage.get(key, 0)
        return min(1.0, count / max_capacity)

    def get_congested_edges(self, threshold: float = 0.5) -> list[dict]:
        """Find edges with congestion above threshold."""
        congested = []
        for (u, v), count in self.edge_usage.items():
            congestion = min(1.0, count / 20.0)
            if congestion >= threshold:
                congested.append({
                    "from": u,
                    "to": v,
                    "visitors": count,
                    "congestion": round(congestion, 3),
                })
        return congested

    def generate_alerts(self) -> list[str]:
        """Generate alert messages for current conditions."""
        alerts = []

        # Zone alerts
        for zone_id in self.zones_config:
            level = self.get_density_level(zone_id)
            density = self.get_zone_density(zone_id)
            if level == "critical":
                alerts.append(
                    f"🔴 CRITICAL: {zone_id} density at {density:.0%} — overcrowded!"
                )
            elif level == "high":
                alerts.append(
                    f"🟠 WARNING: {zone_id} density at {density:.0%} — approaching capacity"
                )

        # Edge alerts
        for edge_info in self.get_congested_edges(threshold=0.7):
            alerts.append(
                f"🟡 Corridor {edge_info['from']}↔{edge_info['to']} congested "
                f"({edge_info['visitors']} visitors)"
            )

        return alerts
