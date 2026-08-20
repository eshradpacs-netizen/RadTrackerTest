# Proje Spesifikasyonu: Bulut Tabanlı Radyoloji Bilgisayar ve Asistan Takip Sistemi

## 1. Proje Genel Bakış ve Amaç
Mevcut Google E-Tablolar (Google Sheets) tabanlı bilgisayar takip sisteminin yavaşlığını, kilitlenme sorunlarını ve anlık takip eksikliğini ortadan kaldırmak; 60 kayıtlı asistanın güvenli e-posta doğrulaması ile giriş yapabildiği, bilgisayarların anlık (real-time) durumunu (Boş/Dolu) sıfır gecikmeyle gösteren bulut tabanlı modern bir web uygulaması geliştirmek.

---

## 2. Teknoloji Yığını (Tech Stack)
* **Backend:** Python 3.10+ & FastAPI (Yüksek performans, asenkron yapı, harika WebSocket desteği)
* **Veritabanı (İlişkisel):** PostgreSQL (Supabase veya Neon - Kullanıcı yönetimi, e-posta doğrulama ve kayıtlar için)
* **Veritabanı (Önbellek & Anlık Durum):** Redis (Bilgisayarların "heartbeat" verileri ve anlık "dolu/boş" durumları için in-memory hız ve TTL yönetimi)
* **Kimlik Doğrulama (Auth):** JWT (JSON Web Token) + E-posta Doğrulama (SMTP üzerinden aktivasyon)
* **Frontend:** HTML5, Tailwind CSS, Vanilla JavaScript (Karmaşık framework yükü olmadan saf WebSocket istemcisi)
* **Ajan (PC Client):** Python (Arka planda çalışan, merkeze periyodik kalp atışı gönderen hafif servis)

---

## 3. Veritabanı Şeması (PostgreSQL)

### `users` Tablosu
| Kolon Adı | Veri Tipi | Açıklama |
| :--- | :--- | :--- |
| `id` | UUID / Serial | Benzersiz kullanıcı ID |
| `email` | VARCHAR (Unique) | Asistanın hastane /kurum mail adresi |
| `password_hash` | VARCHAR | Argon2 veya Bcrypt ile şifrelenmiş parola |
| `is_verified` | BOOLEAN | E-posta doğrulama durumu (Varsayılan: `False`) |
| `verification_token` | VARCHAR | Mail doğrulama için geçici token |
| `created_at` | TIMESTAMP | Kayıt oluşturulma zamanı |

---

## 4. Mimari ve Akış Senaryoları

### A. E-Posta Doğrulamalı Kayıt ve Giriş Akışı
1. **Kayıt (`/api/register`):** Kullanıcı mail ve şifre ile kaydolur. Sistem `is_verified = False` olarak kullanıcıyı oluşturur ve mailine doğrulama linki atar.
2. **Doğrulama (`/api/verify`):** Kullanıcı mailindeki linke tıklar, hesabı aktifleşir (`is_verified = True`). Onaysız hesaplar sisteme giremez.
3. **Giriş (`/api/login`):** Doğrulanmış kullanıcı giriş yapar, sunucu bir **JWT Token** üretir ve tarayıcıya döner. Tüm korumalı isteklere bu token eklenir.

### B. Bilgisayar Durum Takibi (Heartbeat & TTL Mantığı)
1. Hastanedeki bilgisayarlarda çalışan ajanlar her 10 saniyede bir FastAPI sunucusuna `/api/heartbeat` isteği atar.
2. İstek gövdesi: `{"pc_id": "rad-pc-01", "status": "bos", "current_user": "ahmet@hastane.com"}`
3. Sunucu bu veriyi **Redis** içine kaydeder ve Redis anahtarına **20 saniye TTL (Time-to-Live)** tanımlar.
4. Eğer bilgisayar kapanır veya ağı koparsa, 20 saniye içinde Redis'teki verisi otomatik silinir ve sistem arayüzünde otomatik olarak **"Çevrimdışı / Kullanılamaz"** durumuna geçer.

### C. Gerçek Zamanlı Arayüz (WebSockets)
* Tarayıcıdaki web paneli sunucuya WebSocket (`/ws`) ile bağlanır.
* Herhangi bir bilgisayarın durumu değiştiğinde (veya yeni bir heartbeat geldiğinde), FastAPI sunucusu bağlı olan tüm istemcilere (asistanların açık panellerine) anlık olarak güncel JSON listesini iter. Sayfa yenilemeye gerek kalmadan kutucuklar anında renk değiştirir (Yeşil: Boş, Kırmızı: Dolu).

---

## 5. Proje Dosya Yapısı (Directory Structure)

```text
radiology-pc-tracker/
│
├── backend/
│   ├── main.py              # FastAPI ana uygulama ve WebSocket router
│   ├── database.py          # PostgreSQL & Redis bağlantı ayarları
│   ├── models.py            # SQLAlchemy veritabanı modelleri
│   ├── schemas.py           # Pydantic veri doğrulama şemaları
│   ├── auth.py              # JWT ve şifreleme fonksiyonları
│   └── requirements.txt     # Python bağımlılıkları
│
├── agent/
│   └── pc_agent.py          # Bilgisayarlara kurulacak arka plan ajan scripti
│
├── frontend/
│   ├── index.html           # Ana takip paneli (Dashboard)
│   ├── login.html           # Giriş ve kayıt ekranı
│   └── script.js            # WebSocket ve UI dinamikleri
│
└── README.md                # Proje dokümantasyonu