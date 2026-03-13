/**
 * charts.js — Chart.js based real-time charts for simulation metrics.
 */

const CHART_COLORS = [
    "#4A90D9", "#27AE60", "#F39C12", "#E74C3C",
    "#8E44AD", "#FFD700", "#1ABC9C", "#E67E22",
];

const CHART_OPTIONS_BASE = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 150 },
    plugins: {
        legend: {
            position: "bottom",
            labels: {
                color: "#8899a6",
                font: { size: 10 },
                boxWidth: 12,
                padding: 8,
            },
        },
    },
    scales: {
        x: {
            ticks: { color: "#8899a6", font: { size: 9 }, maxTicksLimit: 10 },
            grid: { color: "rgba(255,255,255,0.05)" },
        },
        y: {
            ticks: { color: "#8899a6", font: { size: 9 } },
            grid: { color: "rgba(255,255,255,0.05)" },
            beginAtZero: true,
        },
    },
};

/**
 * SimulationCharts class — manages all Chart.js instances.
 */
class SimulationCharts {
    constructor() {
        this.queueChart = null;
        this.densityChart = null;
        this.throughputChart = null;

        // Data buffers
        this.queueData = [];
        this.densityData = [];
        this.throughputData = [];

        this.maxPoints = 120;
        this.gateIds = [];
        this.zoneIds = [];
    }

    /**
     * Initialize charts with gate and zone IDs.
     */
    init(gateIds, zoneIds) {
        this.gateIds = gateIds;
        this.zoneIds = zoneIds;
        this._initQueueChart();
        this._initDensityChart();
        this._initThroughputChart();
    }

    _initQueueChart() {
        const ctx = document.getElementById("queueChart");
        if (!ctx) return;

        const datasets = this.gateIds.map((gid, i) => ({
            label: gid.replace("_", " ").toUpperCase(),
            data: [],
            borderColor: CHART_COLORS[i % CHART_COLORS.length],
            backgroundColor: CHART_COLORS[i % CHART_COLORS.length] + "33",
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
            fill: false,
        }));

        this.queueChart = new Chart(ctx, {
            type: "line",
            data: { labels: [], datasets },
            options: {
                ...CHART_OPTIONS_BASE,
                plugins: {
                    ...CHART_OPTIONS_BASE.plugins,
                    title: { display: false },
                },
            },
        });
    }

    _initDensityChart() {
        const ctx = document.getElementById("densityChart");
        if (!ctx) return;

        const datasets = this.zoneIds.map((zid, i) => ({
            label: zid.replace("_", " "),
            data: [],
            borderColor: CHART_COLORS[i % CHART_COLORS.length],
            backgroundColor: CHART_COLORS[i % CHART_COLORS.length] + "33",
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
            fill: false,
        }));

        this.densityChart = new Chart(ctx, {
            type: "line",
            data: { labels: [], datasets },
            options: {
                ...CHART_OPTIONS_BASE,
                scales: {
                    ...CHART_OPTIONS_BASE.scales,
                    y: {
                        ...CHART_OPTIONS_BASE.scales.y,
                        max: 1.2,
                        ticks: {
                            ...CHART_OPTIONS_BASE.scales.y.ticks,
                            callback: (v) => (v * 100).toFixed(0) + "%",
                        },
                    },
                },
            },
        });
    }

    _initThroughputChart() {
        const ctx = document.getElementById("throughputChart");
        if (!ctx) return;

        const datasets = this.gateIds.map((gid, i) => ({
            label: gid.replace("_", " ").toUpperCase(),
            data: [],
            backgroundColor: CHART_COLORS[i % CHART_COLORS.length] + "CC",
            borderColor: CHART_COLORS[i % CHART_COLORS.length],
            borderWidth: 1,
        }));

        this.throughputChart = new Chart(ctx, {
            type: "bar",
            data: { labels: this.gateIds.map(g => g.replace("_", " ").toUpperCase()), datasets: [{
                label: "İşlenen Ziyaretçi",
                data: this.gateIds.map(() => 0),
                backgroundColor: this.gateIds.map((_, i) => CHART_COLORS[i % CHART_COLORS.length] + "CC"),
                borderColor: this.gateIds.map((_, i) => CHART_COLORS[i % CHART_COLORS.length]),
                borderWidth: 1,
            }]},
            options: {
                ...CHART_OPTIONS_BASE,
                plugins: {
                    ...CHART_OPTIONS_BASE.plugins,
                    legend: { display: false },
                },
            },
        });
    }

    /**
     * Add a data point from the simulation state.
     */
    addDataPoint(chartPoint) {
        if (!chartPoint || chartPoint.time === undefined) return;

        const time = chartPoint.time;
        const timeLabel = time.toFixed(0) + "s";

        // Queue chart
        if (this.queueChart) {
            this.queueChart.data.labels.push(timeLabel);
            this.gateIds.forEach((gid, i) => {
                const val = (chartPoint.gate_queues || {})[gid] || 0;
                this.queueChart.data.datasets[i].data.push(val);
            });

            // Trim to max points
            if (this.queueChart.data.labels.length > this.maxPoints) {
                this.queueChart.data.labels.shift();
                this.queueChart.data.datasets.forEach(ds => ds.data.shift());
            }
            this.queueChart.update("none");
        }

        // Density chart
        if (this.densityChart) {
            this.densityChart.data.labels.push(timeLabel);
            this.zoneIds.forEach((zid, i) => {
                const val = (chartPoint.zone_densities || {})[zid] || 0;
                this.densityChart.data.datasets[i].data.push(val);
            });

            if (this.densityChart.data.labels.length > this.maxPoints) {
                this.densityChart.data.labels.shift();
                this.densityChart.data.datasets.forEach(ds => ds.data.shift());
            }
            this.densityChart.update("none");
        }

        // Throughput chart (bar — just update values)
        if (this.throughputChart) {
            const throughputValues = this.gateIds.map(
                gid => (chartPoint.gate_throughput || {})[gid] || 0
            );
            this.throughputChart.data.datasets[0].data = throughputValues;
            this.throughputChart.update("none");
        }
    }

    /**
     * Reset all charts.
     */
    reset() {
        if (this.queueChart) {
            this.queueChart.data.labels = [];
            this.queueChart.data.datasets.forEach(ds => ds.data = []);
            this.queueChart.update();
        }
        if (this.densityChart) {
            this.densityChart.data.labels = [];
            this.densityChart.data.datasets.forEach(ds => ds.data = []);
            this.densityChart.update();
        }
        if (this.throughputChart) {
            this.throughputChart.data.datasets[0].data = this.gateIds.map(() => 0);
            this.throughputChart.update();
        }
        this.queueData = [];
        this.densityData = [];
        this.throughputData = [];
    }

    /**
     * Destroy chart instances.
     */
    destroy() {
        if (this.queueChart) this.queueChart.destroy();
        if (this.densityChart) this.densityChart.destroy();
        if (this.throughputChart) this.throughputChart.destroy();
    }
}

// Export
window.SimulationCharts = SimulationCharts;
