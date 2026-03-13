"""
NetworkX-based venue graph construction and route finding.
"""
from __future__ import annotations

import math
from typing import Optional

import networkx as nx

from app.core.constants import NODE_EMERGENCY_EXIT, NODE_ENTRY_GATE, NODE_ZONE


def build_graph(venue_data: dict) -> nx.Graph:
    """
    Build a NetworkX undirected graph from venue JSON data.
    Edge weights are Euclidean distances computed from node coordinates.
    """
    G = nx.Graph()
    nodes_by_id: dict[str, dict] = {}

    # Add nodes
    for node in venue_data["nodes"]:
        nid = node["id"]
        nodes_by_id[nid] = node
        G.add_node(
            nid,
            x=node["x"],
            y=node["y"],
            node_type=node["type"],
            label=node.get("label", ""),
            zone_id=node.get("zone_id"),
            capacity=node.get("capacity"),
        )

    # Add edges with Euclidean distance as weight
    for edge in venue_data["edges"]:
        from_id = edge["from"]
        to_id = edge["to"]
        if from_id not in nodes_by_id or to_id not in nodes_by_id:
            continue
        n1 = nodes_by_id[from_id]
        n2 = nodes_by_id[to_id]
        dist = math.sqrt((n1["x"] - n2["x"]) ** 2 + (n1["y"] - n2["y"]) ** 2)
        G.add_edge(
            from_id,
            to_id,
            weight=dist,
            base_weight=dist,
            width=edge.get("width", 2),
            congestion=0.0,
        )

    return G


def find_shortest_path(
    graph: nx.Graph,
    source: str,
    target: str,
    weight: str = "weight",
) -> list[str]:
    """Find shortest path between two nodes using Dijkstra."""
    try:
        return nx.shortest_path(graph, source, target, weight=weight)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []


def find_nearest_exit(
    graph: nx.Graph,
    source: str,
    exit_types: tuple[str, ...] = (NODE_EMERGENCY_EXIT, NODE_ENTRY_GATE),
) -> Optional[str]:
    """
    Find the nearest exit node (emergency exit or entry gate) from source.
    Returns the exit node id, or None if unreachable.
    """
    best_exit = None
    best_dist = float("inf")

    exit_nodes = [
        n for n, d in graph.nodes(data=True)
        if d.get("node_type") in exit_types
    ]

    for exit_node in exit_nodes:
        try:
            dist = nx.shortest_path_length(graph, source, exit_node, weight="weight")
            if dist < best_dist:
                best_dist = dist
                best_exit = exit_node
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue

    return best_exit


def find_congestion_aware_path(
    graph: nx.Graph,
    source: str,
    target: str,
    congestion_weight: float = 2.0,
) -> list[str]:
    """
    Find path that balances distance and congestion.
    Uses a combined weight: base_weight + congestion * congestion_weight.
    """
    # Temporarily set combined weights
    for u, v, data in graph.edges(data=True):
        data["combined_weight"] = (
            data.get("base_weight", data["weight"])
            + data.get("congestion", 0.0) * congestion_weight
        )

    path = find_shortest_path(graph, source, target, weight="combined_weight")
    return path if path else find_shortest_path(graph, source, target, weight="weight")


def update_edge_congestion(
    graph: nx.Graph,
    edge_visitor_counts: dict[tuple[str, str], int],
    max_capacity_per_edge: float = 20.0,
) -> None:
    """
    Update congestion scores on edges based on current visitor counts.
    """
    for (u, v), count in edge_visitor_counts.items():
        if graph.has_edge(u, v):
            congestion = min(1.0, count / max_capacity_per_edge)
            graph[u][v]["congestion"] = congestion


def get_zone_nodes(graph: nx.Graph) -> list[str]:
    """Return list of node IDs that are zones."""
    return [
        n for n, d in graph.nodes(data=True)
        if d.get("node_type") == NODE_ZONE
    ]


def get_exit_nodes(graph: nx.Graph) -> list[str]:
    """Return list of node IDs that are exits (emergency + gates)."""
    return [
        n for n, d in graph.nodes(data=True)
        if d.get("node_type") in (NODE_EMERGENCY_EXIT, NODE_ENTRY_GATE)
    ]


def get_gate_nodes(graph: nx.Graph) -> list[str]:
    """Return list of node IDs that are entry gates."""
    return [
        n for n, d in graph.nodes(data=True)
        if d.get("node_type") == NODE_ENTRY_GATE
    ]
