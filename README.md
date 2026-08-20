# 🚀 Radiology PC Tracker v1 (Telegram-DB & Fast Real-Time Edition)

Modern, 0-gecikmeli (real-time WebSockets), **Telegram-as-a-Database (Telegram-DB)** mimarili Radyoloji Bilgisayar ve Asistan Takip Sistemi.

---

### ✨ Öne Çıkan Özellikler

1. **📲 %100 Telegram Entegrasyonu:**
   * **Telegram Mini App (Canlı Takip Paneli):** Telegram sohbetinden çıkmadan açılan tam ekran canlı renkli panel.
   * **Anlık Telegram Komutları:** `/bos` (Boş PC'ler), `/durum` (Özet), `/odalar` (Takımyıldızlar), `/takip` (PC boşalınca bildirim).
2. **💾 Telegram-as-a-Database (Telegram-DB):**
   * Sıfır dış veritabanı maliyeti! Tüm kullanıcı kayıtları, izin verilen e-postalar ve loglar gizli bir Telegram kanalındaki mesajlarda bulut üzerinde sınırsız ve ücretsiz saklanır.
   * Google Sheets'teki 10 milyon hücre kısıtlaması, donma ve yavaşlama tamamen tarihe karıştı!
3. **⚡ Sıfır Gecikme (Real-Time WebSockets):**
   * Bilgisayar durumları (Aktif, Boşta, Öğle Arası, Çevrimdışı, Şüpheli) tüm açık ekranlara **milisaniyeler içinde (0ms)** yansır.
4. **🧩 45 Bilgisayarlık Master Matris Koruması:**
   * Tüm 45 adet radyoloji bilgisayarının UUID, Makine Adı, Görünen Adı (Cassiopeia, Orion, Andromeda, Lyra, Vega, Cygnus, Perseus, Sirius, Aquila) ve Odaları hazır tanımlıdır.

---

### 📂 Proje Dizin Yapısı

```text
radiology-pc-tracker-v1/
├── backend/
│   ├── main.py              # FastAPI sunucusu, REST API & WebSockets (/ws)
│   ├── telegram_db.py       # Telegram-as-a-Database motoru
│   ├── state_manager.py     # In-Memory PC durumu ve 20s TTL temizlik motoru
│   ├── telegram_bot.py      # Telegram Bot komutları & Push bildirimleri
│   ├── master_mapping.py    # 45 PC Master Eşleşme Matrisi
│   ├── auth.py              # Şifreleme, 6 haneli kod ve JWT token motoru
│   └── requirements.txt     # Python bağımlılıkları
│
├── frontend/
│   ├── miniapp.html         # Telegram Mini App & Web Dashboard
│   ├── index.html           # Ana Dashboard görünümü
│   ├── styles.css           # Tailwind CSS & Canlı rozet stilleri
│   └── app.js               # WebSockets istemcisi & Telegram WebApp entegrasyonu
│
├── agent/
│   ├── agent.ps1            # Hastane PC'leri için sessiz Windows PowerShell Ajanı
│   └── pc_agent.py          # Python Ajan alternatifi
│
└── README.md                # Kurulum ve canlıya alma rehberi
```

---

### 🚀 1. Yerel Çalıştırma (Local Development)

```bash
cd radiology-pc-tracker-v1/backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```
* **Web Arayüzü:** `http://localhost:8000`
* **API Dokümantasyonu:** `http://localhost:8000/docs`

---

### ☁️ 2. Ücretsiz Buluta Alma Rehberi (Koyeb / Render / Railway)

1. **Telegram Bot Token Alma:**
   * Telegram'da `@BotFather` ile görüşüp `/newbot` komutuyla yeni bir bot oluşturun ve `TELEGRAM_BOT_TOKEN` değerini alın.
2. **Koyeb / Render Üzerinde 1-Tıkla Yayınlama:**
   * Reponuzu GitHub'a yükleyin.
   * Koyeb / Render paneline girip Python Web Service olarak ekleyin.
   * Çalıştırma Komutu (Start Command): `python -m uvicorn main:app --host 0.0.0.0 --port 8000`
   * Çevre Değişkenleri (Environment Variables):
     * `TELEGRAM_BOT_TOKEN`: `@BotFather`'dan alınan bot tokenı.
     * `TELEGRAM_CHAT_ID`: Telegram DB kanalınızın ID'si.
     * `TELEGRAM_MINI_APP_URL`: Yayınladığınız uygulamanın `miniapp.html` adresi (Örn: `https://radtracker.koyeb.app/miniapp.html`).

3. **Telegram Mini App Menü Butonunu Ekleme:**
   * BotFather sohbetine girin: `/setmenubutton`
   * Botunuzu seçin ve Web App URL adresi olarak `https://radtracker.koyeb.app/miniapp.html` girin!

---

### 💻 3. Hastane Bilgisayarlarına Ajan Kurulumu

Hastanedeki 45 bilgisayardan herhangi birinde arka planda başlatmak için:

```powershell
powershell -ExecutionPolicy Bypass -File .\agent.ps1 -ServerUrl "https://radtracker.koyeb.app"
```

Ajan arka planda sessizce çalışacak ve her 10 saniyede bir merkeze sinyal göndererek Telegram Mini App ve sohbet botunu besleyecektir!
