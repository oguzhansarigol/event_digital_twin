/**
 * app.js — Main application controller.
 * Manages WebSocket connection, UI controls, and state updates.
 */

(function () {
    "use strict";

    // ── DOM References ─────────────────────────────────
    const $  = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const dom = {
        status:         $("#simStatus"),
        scenarioSelect: $("#scenarioSelect"),
        scenarioDesc:   $("#scenarioDesc"),
        visitorCount:   $("#visitorCount"),
        arrivalPattern: $("#arrivalPattern"),
        speedSlider:    $("#speedSlider"),
        speedValue:     $("#speedValue"),
        simDuration:    $("#simDuration"),
        btnStart:       $("#btnStart"),
        btnReset:       $("#btnReset"),
        btnEmergency:   $("#btnEmergency"),
        metricTime:     $("#metricTime"),
        metricEntered:  $("#metricEntered"),
        metricActive:   $("#metricActive"),
        metricExited:   $("#metricExited"),
        metricAvgWait:  $("#metricAvgWait"),
        metricMaxWait:  $("#metricMaxWait"),
        metricEvacTime: $("#metricEvacTime"),
        gateStats:      $("#gateStats"),
        alertsList:     $("#alertsList"),
        recommendationsList: $("#recommendationsList"),
    };

    // ── State ──────────────────────────────────────────
    let ws = null;
    let venueData = null;
    let scenarios = [];
    let venueMap = null;
    let charts = null;
    let isRunning = false;
    let frameCounter = 0;

    // ── Initialize ─────────────────────────────────────
    async function init() {
        venueMap = new VenueMap($("#venueMap"));
        charts = new SimulationCharts();

        try {
            // Load venue data
            const venueResp = await fetch("/api/venue/");
            venueData = await venueResp.json();
            venueMap.init(venueData);

            // Load scenarios
            const scenResp = await fetch("/api/scenarios/");
            const scenData = await scenResp.json();
            scenarios = scenData.scenarios || [];
            populateScenarios();

            // Initialize charts with gate and zone IDs
            const gateIds = Object.keys(venueData.gates || {});
            const zoneIds = Object.keys(venueData.zones || {});
            charts.init(gateIds, zoneIds);

        } catch (e) {
            console.error("Initialization error:", e);
            setStatus("error", "Yükleme hatası");
        }

        // Event listeners
        dom.btnStart.addEventListener("click", startSimulation);
        dom.btnReset.addEventListener("click", resetSimulation);
        dom.btnEmergency.addEventListener("click", triggerEmergency);
        dom.speedSlider.addEventListener("input", onSpeedChange);
        dom.scenarioSelect.addEventListener("change", onScenarioChange);
    }

    // ── Scenario UI ────────────────────────────────────
    function populateScenarios() {
        dom.scenarioSelect.innerHTML = "";
        for (const s of scenarios) {
            const opt = document.createElement("option");
            opt.value = s.id;
            opt.textContent = s.name;
            dom.scenarioSelect.appendChild(opt);
        }
        onScenarioChange();
    }

    function onScenarioChange() {
        const sid = dom.scenarioSelect.value;
        const scenario = scenarios.find(s => s.id === sid);
        if (scenario) {
            dom.scenarioDesc.textContent = scenario.description || "";
            dom.visitorCount.value = scenario.default_visitors || 300;
            dom.arrivalPattern.value = scenario.default_arrival || "poisson";
            dom.simDuration.value = scenario.default_duration || 600;
        }
    }

    function onSpeedChange() {
        const speed = dom.speedSlider.value;
        dom.speedValue.textContent = speed;
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: "speed", value: parseFloat(speed) }));
        }
    }

    // ── WebSocket ──────────────────────────────────────
    function connectWebSocket() {
        const protocol = location.protocol === "https:" ? "wss:" : "ws:";
        const url = `${protocol}//${location.host}/ws/simulation`;

        ws = new WebSocket(url);

        ws.onopen = () => {
            console.log("WebSocket connected");
            sendStartCommand();
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleMessage(data);
            } catch (e) {
                console.error("Message parse error:", e);
            }
        };

        ws.onclose = () => {
            console.log("WebSocket closed");
            if (isRunning) {
                setStatus("idle", "BAĞLANTI KESİLDİ");
                isRunning = false;
                updateButtonStates();
            }
        };

        ws.onerror = (e) => {
            console.error("WebSocket error:", e);
        };
    }

    function sendStartCommand() {
        const params = {
            scenario_id: dom.scenarioSelect.value,
            total_visitors: parseInt(dom.visitorCount.value) || 300,
            arrival_pattern: dom.arrivalPattern.value,
            speed_multiplier: parseFloat(dom.speedSlider.value) || 5,
            duration: parseFloat(dom.simDuration.value) || 600,
        };

        // Check scenario for emergency_at
        const scenario = scenarios.find(s => s.id === params.scenario_id);
        if (scenario && scenario.emergency_at) {
            params.emergency_at = scenario.emergency_at;
        }

        ws.send(JSON.stringify({ action: "start", params }));
    }

    // ── Message handling ───────────────────────────────
    function handleMessage(data) {
        const type = data.type;

        if (type === "state") {
            onStateUpdate(data);
        } else if (type === "complete") {
            onSimulationComplete(data);
        } else if (type === "emergency") {
            setStatus("emergency", "ACİL TAHLİYE");
        } else if (type === "reset") {
            onReset();
        } else if (type === "error") {
            console.error("Server error:", data.message);
            setStatus("idle", "HATA");
        }
    }

    function onStateUpdate(state) {
        frameCounter++;

        // Update map
        venueMap.updateState(state);

        // Update metrics
        updateMetrics(state);

        // Update gate stats
        updateGateStats(state.gates || {});

        // Update alerts
        updateAlerts(state.alerts || []);

        // Update charts (every 4th frame for performance)
        if (frameCounter % 4 === 0 && state.chart_point) {
            charts.addDataPoint(state.chart_point);
        }

        // Status
        if (state.emergency_mode) {
            setStatus("emergency", "ACİL TAHLİYE");
        } else if (state.is_complete) {
            onSimulationComplete(state);
        } else {
            setStatus("running", "ÇALIŞIYOR");
        }
    }

    function onSimulationComplete(data) {
        isRunning = false;
        setStatus("complete", "TAMAMLANDI");
        updateButtonStates();

        // Show recommendations
        if (data.recommendations) {
            updateRecommendations(data.recommendations);
        }

        // Show final metrics
        if (data.metrics) {
            updateMetricValues(data.metrics);
        }
    }

    function onReset() {
        isRunning = false;
        venueMap.reset();
        charts.reset();
        resetMetrics();
        setStatus("idle", "IDLE");
        updateButtonStates();
        dom.alertsList.innerHTML = '<li class="no-alerts">Henüz uyarı yok</li>';
        dom.recommendationsList.innerHTML =
            "<li>Simülasyon başlatıldıktan sonra öneriler burada görüntülenecektir.</li>";
    }

    // ── UI Updates ─────────────────────────────────────
    function updateMetrics(state) {
        if (!state) return;
        dom.metricTime.textContent = (state.time || 0).toFixed(1) + "s";

        const m = state.metrics || {};
        updateMetricValues(m);
    }

    function updateMetricValues(m) {
        dom.metricEntered.textContent = m.total_entered || 0;
        dom.metricActive.textContent = m.active_count || 0;
        dom.metricExited.textContent = m.total_exited || 0;
        dom.metricAvgWait.textContent = (m.avg_wait_time || 0).toFixed(1) + "s";
        dom.metricMaxWait.textContent = (m.max_wait_time || 0).toFixed(1) + "s";
        dom.metricEvacTime.textContent =
            m.evacuation_time != null ? m.evacuation_time.toFixed(1) + "s" : "—";
    }

    function resetMetrics() {
        dom.metricTime.textContent = "0.0s";
        dom.metricEntered.textContent = "0";
        dom.metricActive.textContent = "0";
        dom.metricExited.textContent = "0";
        dom.metricAvgWait.textContent = "0.0s";
        dom.metricMaxWait.textContent = "0.0s";
        dom.metricEvacTime.textContent = "—";
    }

    function updateGateStats(gates) {
        let html = "";
        for (const [gid, stats] of Object.entries(gates)) {
            const queueLen = stats.queue_length || 0;
            const processed = stats.processed || 0;
            const status = stats.status || "open";
            const utilization = stats.utilization || 0;

            // Bar width (max at 30 visitors)
            const barPct = Math.min(100, (queueLen / 30) * 100);
            let barClass = "low";
            if (queueLen > 20) barClass = "high";
            else if (queueLen > 10) barClass = "medium";

            html += `
                <div class="gate-row">
                    <span class="gate-name">${gid.replace("_", " ").toUpperCase()}</span>
                    <div class="gate-bar-container">
                        <div class="gate-bar ${barClass}" style="width:${barPct}%"></div>
                    </div>
                    <span class="gate-count">${queueLen}</span>
                    <span class="gate-status ${status}">${status}</span>
                </div>
            `;
        }
        dom.gateStats.innerHTML = html;
    }

    function updateAlerts(alerts) {
        if (!alerts || alerts.length === 0) {
            dom.alertsList.innerHTML = '<li class="no-alerts">Uyarı yok ✅</li>';
            return;
        }
        dom.alertsList.innerHTML = alerts
            .map(a => `<li>${a}</li>`)
            .join("");
    }

    function updateRecommendations(recs) {
        if (!recs || recs.length === 0) return;
        dom.recommendationsList.innerHTML = recs
            .map(r => `<li>${r}</li>`)
            .join("");
    }

    function setStatus(cls, text) {
        dom.status.className = `status-badge status-${cls}`;
        dom.status.textContent = text;
    }

    function updateButtonStates() {
        dom.btnStart.disabled = isRunning;
        dom.btnReset.disabled = !isRunning && !dom.btnReset.dataset.wasRunning;
        dom.btnEmergency.disabled = !isRunning;

        if (isRunning) {
            dom.btnStart.textContent = "⏸ Çalışıyor...";
            dom.btnReset.disabled = false;
            dom.btnReset.dataset.wasRunning = "true";
        } else {
            dom.btnStart.textContent = "▶ Başlat";
        }
    }

    // ── Actions ────────────────────────────────────────
    function startSimulation() {
        if (isRunning) return;
        isRunning = true;
        frameCounter = 0;

        // Reset charts
        charts.destroy();
        const gateIds = Object.keys(venueData.gates || {});
        const zoneIds = Object.keys(venueData.zones || {});
        charts = new SimulationCharts();
        charts.init(gateIds, zoneIds);

        venueMap.clearVisitors();
        resetMetrics();
        updateButtonStates();

        connectWebSocket();
    }

    function resetSimulation() {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: "reset" }));
            ws.close();
        }
        onReset();
    }

    function triggerEmergency() {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: "emergency" }));
        }
    }

    // ── Boot ───────────────────────────────────────────
    document.addEventListener("DOMContentLoaded", init);
})();
