"""
Recommendation engine.
Generates actionable suggestions based on simulation metrics and state.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.simulation.engine import SimulationEngine


def generate_recommendations(engine: "SimulationEngine") -> list[str]:
    """
    Analyze current simulation state and metrics to produce recommendations.
    Returns a list of recommendation strings.
    """
    recs: list[str] = []

    _recommend_gates(engine, recs)
    _recommend_zones(engine, recs)
    _recommend_corridors(engine, recs)
    _recommend_evacuation(engine, recs)
    _recommend_operations(engine, recs)

    return recs


def _recommend_gates(engine: "SimulationEngine", recs: list[str]) -> None:
    """Gate-related recommendations."""
    gate_stats = engine.gate_manager.get_all_stats()

    if not gate_stats:
        return

    # Find best and worst gates
    best_gate = None
    worst_gate = None
    best_wait = float("inf")
    worst_wait = 0.0

    for gid, stats in gate_stats.items():
        avg_w = stats.get("avg_wait_time", 0)
        if stats.get("status") == "closed":
            continue
        if avg_w < best_wait and stats.get("processed", 0) > 0:
            best_wait = avg_w
            best_gate = gid
        if avg_w > worst_wait:
            worst_wait = avg_w
            worst_gate = gid

    if best_gate:
        recs.append(
            f"✅ Önerilen giriş kapısı: {best_gate.upper()} "
            f"(ort. bekleme: {best_wait:.1f}s)"
        )

    if worst_gate and worst_wait > 30:
        recs.append(
            f"⚠️ {worst_gate.upper()} kapısında yüksek bekleme süresi "
            f"({worst_wait:.1f}s). Ek güvenlik şeridi eklemeyi düşünün."
        )

    # Check for severely unbalanced gates
    processed_counts = {
        gid: s.get("processed", 0)
        for gid, s in gate_stats.items()
        if s.get("status") != "closed"
    }
    if processed_counts:
        max_p = max(processed_counts.values())
        min_p = min(processed_counts.values())
        if max_p > 0 and min_p < max_p * 0.3:
            low_gates = [
                gid for gid, p in processed_counts.items()
                if p < max_p * 0.3
            ]
            recs.append(
                f"📊 Kapı kullanım dengesizliği: {', '.join(g.upper() for g in low_gates)} "
                f"düşük kullanımda. Yönlendirmeyi artırın."
            )

    # Queue overflow warning
    for gid, stats in gate_stats.items():
        if stats.get("max_queue_length", 0) > 25:
            recs.append(
                f"🔴 {gid.upper()} kapısında maksimum kuyruk uzunluğu "
                f"{stats['max_queue_length']} kişiye ulaştı. Kapasite artışı gerekli."
            )


def _recommend_zones(engine: "SimulationEngine", recs: list[str]) -> None:
    """Zone density recommendations."""
    hotspots = engine.density_analyzer.detect_hotspots()

    for hs in hotspots:
        zone = hs["zone_id"]
        density = hs["density"]
        level = hs["level"]

        if level == "critical":
            recs.append(
                f"🔴 {zone} bölgesi kritik yoğunlukta ({density:.0%}). "
                f"Giriş kısıtlaması veya yönlendirme bariyeri önerilir."
            )
        elif level == "high":
            recs.append(
                f"🟠 {zone} bölgesinde yüksek yoğunluk ({density:.0%}). "
                f"Alternatif alanlara yönlendirme yapılabilir."
            )


def _recommend_corridors(engine: "SimulationEngine", recs: list[str]) -> None:
    """Corridor congestion recommendations."""
    congested = engine.density_analyzer.get_congested_edges(threshold=0.6)

    for edge in congested:
        if edge["congestion"] > 0.8:
            recs.append(
                f"🟡 {edge['from']}↔{edge['to']} koridoru aşırı yoğun "
                f"({edge['visitors']} kişi). Alternatif güzergah açılabilir."
            )


def _recommend_evacuation(engine: "SimulationEngine", recs: list[str]) -> None:
    """Evacuation-related recommendations."""
    if not engine.emergency_mode:
        return

    evac_time = engine.metrics.evacuation_time
    if evac_time is not None:
        if evac_time > 300:
            recs.append(
                f"🚨 Tahliye süresi çok yüksek ({evac_time:.0f}s). "
                f"Ek acil çıkış veya bariyer değişikliği gerekli."
            )
        elif evac_time > 180:
            recs.append(
                f"⚠️ Tahliye süresi {evac_time:.0f}s. "
                f"Darboğaz noktalarının iyileştirilmesi önerilir."
            )
        else:
            recs.append(
                f"✅ Tahliye süresi kabul edilebilir ({evac_time:.0f}s)."
            )

    still_inside = len(engine.active_visitors)
    if still_inside > 0 and engine.emergency_mode:
        recs.append(
            f"🔴 Hâlâ {still_inside} kişi mekan içinde. "
            f"Tahliye devam ediyor."
        )


def _recommend_operations(engine: "SimulationEngine", recs: list[str]) -> None:
    """General operational recommendations."""
    metrics = engine.metrics

    # Overall wait time assessment
    if metrics.avg_wait_time > 60:
        recs.append(
            f"⏱️ Ortalama bekleme süresi yüksek ({metrics.avg_wait_time:.0f}s). "
            f"Kapı kapasitesini artırmayı veya güvenlik sürecini hızlandırmayı düşünün."
        )

    # Throughput assessment
    if metrics.total_entered > 0:
        active_ratio = metrics.active_count / max(metrics.total_generated, 1)
        if active_ratio > 0.8:
            recs.append(
                "📈 Mekan doluluk oranı yüksek. "
                "Yeni ziyaretçi girişini sınırlandırmayı düşünün."
            )

    if not recs:
        recs.append("✅ Tüm sistemler normal aralıkta çalışıyor.")
