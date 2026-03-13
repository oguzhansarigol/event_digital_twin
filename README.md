# Event Digital Twin

Etkinlik mekanları için gerçek zamanlı 2D kitle simülasyon platformu. Ziyaretçi akışını, kapı kuyruklarını, bölge yoğunluklarını ve acil tahliye senaryolarını analiz etmek amacıyla tasarlanmıştır.

## Genel Bakış

Event Digital Twin, bir etkinlik alanındaki insan hareketini ayrık olay simülasyonu (discrete-event simulation) yöntemiyle modeller. SimPy tabanlı simülasyon motoru, her ziyaretçiyi bağımsız bir ajan olarak ele alır; kapılarda kuyruk oluşturur, bölgeler arasında NetworkX graf routing ile rota hesaplar ve yoğunluk eşiklerine göre uyarı üretir. Tüm bu veriler WebSocket üzerinden tarayıcıya anlık olarak aktarılır.

## Özellikler

- **Ziyaretçi Ajanları** — Normal, VIP ve Personel türlerinde, her birinin yürüyüş hızı ve sabır eşiği farklı olan bağımsız ajan modeli
- **Kapı & Kuyruk Yönetimi** — Kapasite ve servis süresi tanımlanabilen kapılar; sabır aşıldığında otomatik kapı geçişi
- **Yoğunluk Analizi** — Bölge bazlı doluluk takibi, dört kademeli yoğunluk eşiği (düşük / orta / yüksek / kritik) ve otomatik uyarılar
- **Graf Tabanlı Rotalama** — NetworkX ile oluşturulan mekan grafı, anlık tıkanıklık verisiyle ağırlıklandırılır
- **Acil Tahliye Modu** — Belirli bir simülasyon zamanında veya manuel tetikle tüm ziyaretçileri tahliye rotasına yönlendirir
- **Metrik & Öneri Motoru** — Bekleme süreleri, throughput ve bölge doluluk verileri toplanır; simülasyon sonunda iyileştirme önerileri sunulur
- **Gerçek Zamanlı Frontend** — WebSocket ile beslenen 2D harita görünümü, canlı grafikler ve kontrol paneli
- **REST API** — WebSocket'e ek olarak başlatma, adım atlama, acil durum ve metrik sorgulama uç noktaları

## Hazır Senaryolar

| Senaryo | Açıklama |
|---|---|
| Normal Event Flow | Tüm kapılar açık, Poisson varış dağılımı, 300 ziyaretçi |
| Peak Hour Congestion | Kısa sürede yüksek yoğunluk, kapasite stres testi, 500 ziyaretçi |
| Gate Failure | Gate B kapalı; kalan 3 kapı üzerindeki trafik dağılımı gözlemlenir |
| Security Delay | Tüm kapılarda işlem süresi 3 katına çıkarılır; kuyruk birikimi test edilir |
| Emergency Evacuation | 200. saniyede acil durum tetiklenir, tüm alan tahliye edilir |

## Teknoloji Yığını

- **Backend:** Python, FastAPI, uvicorn
- **Simülasyon:** SimPy (discrete-event), NetworkX (graph routing), NumPy, pandas
- **Gerçek Zamanlı İletişim:** WebSocket (native FastAPI + websockets)
- **Frontend:** Vanilla JS, HTML/CSS, Jinja2 şablonları
- **Veri Doğrulama:** Pydantic v2

## Kurulum

**Gereksinim:** Python 3.10+

```bash
# Bağımlılıkları yükle
pip install -r requirements.txt

# Uygulamayı başlat
uvicorn app.main:app --reload
```

Sunucu başladıktan sonra tarayıcıdan `http://localhost:8000` adresine gidin.

## API Uç Noktaları

### WebSocket

```
ws://localhost:8000/ws/simulation
```

İstemciden gönderilecek mesajlar:

```json
{"action": "start", "params": {"scenario_id": "normal_flow", "total_visitors": 300}}
{"action": "emergency"}
{"action": "speed", "value": 10}
{"action": "reset"}
{"action": "stop"}
```

### REST

| Method | Endpoint | Açıklama |
|---|---|---|
| GET | `/api/venue` | Mekan yapılandırması |
| GET | `/api/scenarios` | Senaryo listesi |
| POST | `/api/simulation/start` | Simülasyon başlat |
| POST | `/api/simulation/step` | Tek adım ilerlet |
| POST | `/api/simulation/emergency` | Acil tahliye tetikle |
| GET | `/api/simulation/metrics` | Anlık metrikler |
| GET | `/api/simulation/recommendations` | Öneri listesi |
| POST | `/api/simulation/reset` | Simülasyonu sıfırla |
| GET | `/health` | Sağlık kontrolü |

## Proje Yapısı

```
event_digital_twin/
├── app/
│   ├── api/            # FastAPI route'ları ve WebSocket handler
│   ├── core/           # Konfigürasyon ve sabitler
│   ├── data/           # venue.json ve scenarios.json
│   ├── models/         # Domain modelleri ve Pydantic şemaları
│   ├── services/       # SimulationService katmanı
│   ├── simulation/     # Simülasyon çekirdeği
│   │   ├── engine.py       # Ana motor
│   │   ├── agents.py       # Ziyaretçi ajanları
│   │   ├── routing.py      # Graf & rota hesaplama
│   │   ├── queues.py       # Kapı & kuyruk yönetimi
│   │   ├── density.py      # Yoğunluk analizi
│   │   ├── metrics.py      # Metrik toplama
│   │   ├── evacuation.py   # Acil tahliye
│   │   ├── recommendations.py  # Öneri motoru
│   │   ├── arrivals.py     # Varış örüntüleri
│   │   └── scenarios.py    # Senaryo yönetimi
│   ├── static/         # CSS ve JavaScript
│   ├── templates/      # Jinja2 HTML şablonları
│   └── main.py         # Uygulama giriş noktası
└── requirements.txt
```

## Lisans

Bu proje [LICENSE](LICENSE) dosyasında belirtilen koşullar altında dağıtılmaktadır.
