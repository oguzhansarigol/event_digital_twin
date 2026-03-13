/**
 * map.js — SVG-based 2D venue map renderer.
 * Draws the venue layout (zones, paths, gates, exits)
 * and animates visitor dots in real time.
 */

const SVG_NS = "http://www.w3.org/2000/svg";

// Color maps
const ZONE_COLORS = {
    entertainment: { fill: "rgba(142, 68, 173, 0.25)", stroke: "#8E44AD" },
    service:       { fill: "rgba(39, 174, 96, 0.20)",  stroke: "#27AE60" },
    restricted:    { fill: "rgba(255, 215, 0, 0.20)",  stroke: "#FFD700" },
};

const VISITOR_COLORS = {
    normal:         "#4A90D9",
    vip:            "#FFD700",
    staff:          "#27AE60",
    security_staff: "#8E44AD",
    medical_staff:  "#E74C3C",
};

const STATE_OVERRIDE_COLORS = {
    queuing:    "#F39C12",
    evacuating: "#E74C3C",
    leaving:    "#95A5A6",
};

const GATE_COLOR = "#4A90D9";
const EXIT_COLOR = "#E74C3C";
const INTERSECTION_COLOR = "#2d4050";

/**
 * VenueMap class — manages SVG rendering.
 */
class VenueMap {
    constructor(svgElement) {
        this.svg = svgElement;
        this.venueData = null;
        this.nodesById = {};
        this.visitorElements = {};  // visitor_id -> SVG circle
        this.zoneRects = {};       // zone_id -> SVG rect
        this.pathLines = {};       // "from-to" -> SVG line
        this.gateMarkers = {};     // gate_id -> SVG group

        // SVG layer groups (draw order)
        this.layerPaths = this._createGroup("layer-paths");
        this.layerZones = this._createGroup("layer-zones");
        this.layerNodes = this._createGroup("layer-nodes");
        this.layerVisitors = this._createGroup("layer-visitors");
        this.layerLabels = this._createGroup("layer-labels");
    }

    _createGroup(id) {
        const g = document.createElementNS(SVG_NS, "g");
        g.setAttribute("id", id);
        this.svg.appendChild(g);
        return g;
    }

    _createSVG(tag, attrs) {
        const el = document.createElementNS(SVG_NS, tag);
        for (const [k, v] of Object.entries(attrs)) {
            el.setAttribute(k, v);
        }
        return el;
    }

    /**
     * Initialize the map with venue data from the API.
     */
    init(venueData) {
        this.venueData = venueData;
        this.nodesById = {};
        for (const node of venueData.nodes) {
            this.nodesById[node.id] = node;
        }
        this._drawBackground();
        this._drawPaths();
        this._drawZones();
        this._drawNodes();
        this._drawLabels();
    }

    _drawBackground() {
        // Venue border
        const border = this._createSVG("rect", {
            x: 5, y: 5,
            width: this.venueData.width - 10,
            height: this.venueData.height - 10,
            fill: "none",
            stroke: "#1a3d4d",
            "stroke-width": 2,
            rx: 10, ry: 10,
            "stroke-dasharray": "8,4"
        });
        this.layerPaths.appendChild(border);
    }

    _drawPaths() {
        for (const edge of this.venueData.edges) {
            const from = this.nodesById[edge.from];
            const to = this.nodesById[edge.to];
            if (!from || !to) continue;

            const line = this._createSVG("line", {
                x1: from.x, y1: from.y,
                x2: to.x,   y2: to.y,
                class: "path-line",
                "stroke-width": Math.max(1, (edge.width || 2) * 0.8),
            });
            const key = [edge.from, edge.to].sort().join("-");
            this.pathLines[key] = line;
            this.layerPaths.appendChild(line);
        }
    }

    _drawZones() {
        for (const node of this.venueData.nodes) {
            if (node.type !== "zone") continue;

            const w = node.width || 100;
            const h = node.height || 60;
            const zoneType = node.zone_type || "service";
            const colors = ZONE_COLORS[zoneType] || ZONE_COLORS.service;

            const rect = this._createSVG("rect", {
                x: node.x - w / 2,
                y: node.y - h / 2,
                width: w,
                height: h,
                fill: colors.fill,
                stroke: colors.stroke,
                class: "zone-rect",
            });
            this.zoneRects[node.zone_id || node.id] = rect;
            this.layerZones.appendChild(rect);
        }
    }

    _drawNodes() {
        for (const node of this.venueData.nodes) {
            if (node.type === "entry_gate") {
                this._drawGate(node);
            } else if (node.type === "emergency_exit") {
                this._drawExit(node);
            } else if (node.type === "intersection") {
                const dot = this._createSVG("circle", {
                    cx: node.x, cy: node.y, r: 3,
                    fill: INTERSECTION_COLOR,
                    opacity: 0.5,
                });
                this.layerNodes.appendChild(dot);
            }
        }
    }

    _drawGate(node) {
        const g = document.createElementNS(SVG_NS, "g");
        g.setAttribute("class", "gate-marker");

        // Gate icon (rectangle with border)
        const rect = this._createSVG("rect", {
            x: node.x - 18, y: node.y - 10,
            width: 36, height: 20,
            fill: "rgba(74, 144, 217, 0.3)",
            stroke: GATE_COLOR,
            "stroke-width": 2,
            rx: 4, ry: 4,
        });
        g.appendChild(rect);

        // Queue count label
        const countText = this._createSVG("text", {
            x: node.x, y: node.y + 4,
            "text-anchor": "middle",
            fill: GATE_COLOR,
            "font-size": "10px",
            "font-weight": "bold",
        });
        countText.textContent = "0";
        g.appendChild(countText);

        this.gateMarkers[node.id] = { group: g, countText, rect };
        this.layerNodes.appendChild(g);
    }

    _drawExit(node) {
        // Emergency exit marker
        const marker = this._createSVG("polygon", {
            points: this._trianglePoints(node.x, node.y, 12),
            fill: "rgba(231, 76, 60, 0.3)",
            stroke: EXIT_COLOR,
            "stroke-width": 1.5,
        });
        this.layerNodes.appendChild(marker);
    }

    _trianglePoints(cx, cy, size) {
        const h = size * Math.sqrt(3) / 2;
        return `${cx},${cy - h * 0.7} ${cx - size / 2},${cy + h * 0.3} ${cx + size / 2},${cy + h * 0.3}`;
    }

    _drawLabels() {
        for (const node of this.venueData.nodes) {
            if (!node.label) continue;

            let yOffset = 0;
            let fontSize = "9px";
            let cssClass = "node-label";

            if (node.type === "zone") {
                yOffset = 3;
                fontSize = "11px";
                cssClass = "zone-label";
            } else if (node.type === "entry_gate") {
                yOffset = -16;
                fontSize = "10px";
            } else if (node.type === "emergency_exit") {
                yOffset = 16;
                fontSize = "8px";
            }

            const text = this._createSVG("text", {
                x: node.x,
                y: node.y + yOffset,
                class: cssClass,
                "font-size": fontSize,
            });
            text.textContent = node.label;
            this.layerLabels.appendChild(text);
        }
    }

    /**
     * Update the map with current simulation state.
     */
    updateState(state) {
        this._updateVisitors(state.visitors || []);
        this._updateGates(state.gates || {});
        this._updateZoneDensities(state.zones || {});
        this._updateEdgeCongestion(state);
    }

    _updateVisitors(visitors) {
        const currentIds = new Set();

        for (const v of visitors) {
            currentIds.add(v.id);

            let circle = this.visitorElements[v.id];
            if (!circle) {
                circle = this._createSVG("circle", {
                    r: 3,
                    class: "visitor-dot",
                    opacity: 0.85,
                });
                this.layerVisitors.appendChild(circle);
                this.visitorElements[v.id] = circle;
            }

            circle.setAttribute("cx", v.x);
            circle.setAttribute("cy", v.y);

            // Color based on state override or visitor type
            const color = STATE_OVERRIDE_COLORS[v.state]
                || VISITOR_COLORS[v.vtype]
                || "#4A90D9";
            circle.setAttribute("fill", color);

            // Size based on state
            const r = v.state === "evacuating" ? 4 : 3;
            circle.setAttribute("r", r);
        }

        // Remove exited visitors
        for (const [id, circle] of Object.entries(this.visitorElements)) {
            if (!currentIds.has(Number(id))) {
                circle.remove();
                delete this.visitorElements[id];
            }
        }
    }

    _updateGates(gates) {
        for (const [gateId, stats] of Object.entries(gates)) {
            const marker = this.gateMarkers[gateId];
            if (!marker) continue;

            const queueLen = stats.queue_length || 0;
            marker.countText.textContent = queueLen;

            // Color based on queue length
            let fillColor = "rgba(74, 144, 217, 0.3)";
            let strokeColor = GATE_COLOR;
            if (stats.status === "closed") {
                fillColor = "rgba(231, 76, 60, 0.3)";
                strokeColor = EXIT_COLOR;
            } else if (queueLen > 20) {
                fillColor = "rgba(231, 76, 60, 0.4)";
                strokeColor = "#E74C3C";
            } else if (queueLen > 10) {
                fillColor = "rgba(243, 156, 18, 0.4)";
                strokeColor = "#F39C12";
            }
            marker.rect.setAttribute("fill", fillColor);
            marker.rect.setAttribute("stroke", strokeColor);
        }
    }

    _updateZoneDensities(zones) {
        for (const [zoneId, zoneData] of Object.entries(zones)) {
            const rect = this.zoneRects[zoneId];
            if (!rect) continue;

            const density = zoneData.density || 0;
            const node = Object.values(this.nodesById).find(n => n.zone_id === zoneId);
            const zoneType = node?.zone_type || "service";
            const baseColors = ZONE_COLORS[zoneType] || ZONE_COLORS.service;

            // Shift toward red as density increases
            if (density > 0.8) {
                rect.setAttribute("fill", "rgba(231, 76, 60, 0.4)");
                rect.setAttribute("stroke", "#E74C3C");
            } else if (density > 0.6) {
                rect.setAttribute("fill", "rgba(243, 156, 18, 0.35)");
                rect.setAttribute("stroke", "#F39C12");
            } else {
                rect.setAttribute("fill", baseColors.fill);
                rect.setAttribute("stroke", baseColors.stroke);
            }

        }
    }

    _updateEdgeCongestion(state) {
        // Reset all path lines
        for (const line of Object.values(this.pathLines)) {
            line.setAttribute("stroke", "#2d4050");
            line.setAttribute("stroke-width", "2");
        }

        // If chart_point has congestion data, highlight congested edges
        const chartPoint = state.chart_point;
        if (!chartPoint) return;
    }

    /**
     * Clear all visitor dots from the map.
     */
    clearVisitors() {
        for (const circle of Object.values(this.visitorElements)) {
            circle.remove();
        }
        this.visitorElements = {};
    }

    /**
     * Reset map to initial state.
     */
    reset() {
        this.clearVisitors();

        // Reset gate markers
        for (const marker of Object.values(this.gateMarkers)) {
            marker.countText.textContent = "0";
            marker.rect.setAttribute("fill", "rgba(74, 144, 217, 0.3)");
            marker.rect.setAttribute("stroke", GATE_COLOR);
        }

        // Reset zone colors
        for (const [zoneId, rect] of Object.entries(this.zoneRects)) {
            const node = Object.values(this.nodesById).find(n => n.zone_id === zoneId);
            const zoneType = node?.zone_type || "service";
            const colors = ZONE_COLORS[zoneType] || ZONE_COLORS.service;
            rect.setAttribute("fill", colors.fill);
            rect.setAttribute("stroke", colors.stroke);
        }
    }
}

// Export for use in app.js
window.VenueMap = VenueMap;
