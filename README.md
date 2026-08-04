# MT5 Forex Algo Trading Bot with Web Dashboard UI & Gemini AI Analyst

Bot Trading Forex otomatis berbasis Python yang terintegrasi langsung dengan terminal **MetaTrader 5 (MT5)** di Windows. Dilengkapi dengan antarmuka **Web Dashboard UI** yang modern untuk memantau status akun, posisi terbuka, log aktivitas real-time, grafik TradingView, serta mengubah parameter trading secara dinamis.

Proyek ini telah dikembangkan lebih lanjut untuk mendukung analisis kecerdasan buatan (AI) secara real-time menggunakan model **Gemini AI (Gemini 1.5 Flash - Stable)** untuk menganalisis data pasar dan mengambil keputusan trading secara cerdas.

---

## Fitur Utama
* **Multi-Currency Support**: Memantau dan melakukan perdagangan pada beberapa pasangan mata uang sekaligus (default: `EURUSD`, `GBPUSD`, `USDJPY`, `AUDUSD`).
* **Dua Pilihan Mode Strategi**:
  * **`TECHNICAL` (EMA Crossover + RSI)**:
    * **Sinyal BUY**: Terjadi persilangan EMA Crossover ke atas (Fast EMA memotong ke atas Slow EMA) pada *closed candle* dan RSI berada di bawah area *overbought* (jenuh beli).
    * **Sinyal SELL**: Terjadi persilangan EMA Crossover ke bawah (Fast EMA memotong ke bawah Slow EMA) pada *closed candle* dan RSI berada di atas area *oversold* (jenuh jual).
  * **`AI` (Gemini AI Analyst)**:
    * Menganalisis lilin (candle history), indikator teknikal (EMA, RSI), tren pasar, menetapkan level support & resistance, serta memberikan rekomendasi keputusan (`BUY`, `SELL`, `HOLD`) beserta persentase kepercayaan (*confidence score*).
    * Secara otomatis mengeksekusi deal order di MT5 jika keputusan AI adalah `BUY` atau `SELL` dan skor kepercayaan memenuhi batas minimal kepercayaan (`min_confidence`).
* **Bulk & Parallel AI Analysis**:
  * Tombol **`Analisis Semua Pair`** untuk memicu analisis manual bulk secara simultan/paralel dengan teknologi *staggering* (jeda 3 detik per request untuk menghindari limit kuota API 429).
  * **Tabel Ringkasan Keputusan AI Semua Pair**: Menampilkan hasil rekomendasi, persentase keyakinan, level support & resistance, dan waktu analisis terakhir untuk seluruh pasangan mata uang sekaligus.
* **Web Dashboard Control**: Menjalankan (*Start*) dan menghentikan (*Stop*) bot secara real-time hanya dengan satu klik di browser.
* **Pengaturan Dinamis (Hot-Reload)**: Mengubah lot size, target Take Profit (TP), Stop Loss (SL), parameter EMA, RSI, mode strategi, batas kepercayaan AI, dan Gemini API Key langsung dari form UI tanpa perlu mematikan program.
* **Keamanan API Key**: Kunci API Gemini disimpan secara lokal di `config.json` komputer Anda dan terdaftar di `.gitignore` untuk mencegah risiko kebocoran ke GitHub.
* **Keandalan Threading**: Logika inisialisasi MT5 telah disempurnakan secara *thread-safe* untuk memisahkan koneksi antara thread latar belakang bot dan thread web browser.

---

## Prasyarat Sistem
1. **Sistem Operasi**: Windows (wajib, karena pustaka `MetaTrader5` di Python hanya mendukung Windows).
2. **Python**: Versi 3.8 ke atas (disarankan Python 3.10+ atau 3.14).
3. **MetaTrader 5**: Terminal desktop MT5 terinstal dan terhubung ke akun trading (disarankan **Akun Demo** untuk pengujian).
4. **Gemini API Key**: Kunci API gratis dari Google AI Studio untuk menggunakan fitur AI Analyst.

---

## Langkah Instalasi

1. **Clone Repositori**:
   Buka terminal (CMD / PowerShell / Git Bash) dan jalankan perintah berikut:
   ```bash
   git clone https://github.com/dikkayulianto/bot-trading.git
   cd bot-trading
   ```

2. **Instal Dependensi**:
   Instal semua pustaka Python yang dibutuhkan menggunakan `pip`:
   ```bash
   pip install -r requirements.txt
   ```

---

## Konfigurasi MetaTrader 5 (Penting)

Sebelum menjalankan bot, Anda harus mengaktifkan izin trading otomatis pada aplikasi MetaTrader 5 Anda:
1. Buka aplikasi **MetaTrader 5**.
2. Masuk ke menu **Tools** -> **Options** (atau tekan `Ctrl + O`).
3. Pilih tab **Expert Advisors**.
4. Centang opsi berikut:
   * **`[✓] Allow algorithmic trading`**
   * **`[✓] Allow DLL imports`** (wajib untuk komunikasi API Python).
5. Klik **OK**.
6. Klik tombol **"Algo Trading"** pada toolbar atas aplikasi MT5 hingga berwarna **Hijau** (Aktif).
7. Pastikan akun trading Anda sudah terhubung (status di pojok kanan bawah tidak menunjukkan `0/0 Kb`).

---

## Cara Penggunaan

1. **Jalankan Server Dashboard**:
   Jalankan file `app.py` menggunakan Python:
   ```bash
   python app.py
   ```
   *Catatan: Jika Python Anda memiliki beberapa instalasi, gunakan path penuh ke interpreter Python yang sesuai.*

2. **Buka Dashboard di Browser**:
   Buka browser Anda dan akses alamat lokal berikut:
   👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

3. **Masukkan Pengaturan**:
   * Buka panel **Pengaturan Parameter**.
   * Masukkan **Gemini API Key** Anda (jika ingin menggunakan mode AI).
   * Pilih **Mode Strategi** (`TECHNICAL` atau `AI`).
   * Tentukan parameter lainnya seperti Lot Size, SL, TP, dan Min Confidence (%), lalu klik **`💾 Simpan`**.

4. **Mulai Bot**:
   * Klik tombol **`⚡ START BOT`**.
   * Status bot pada badge akan berubah menjadi **`RUNNING`** dan log analisis pasar akan mulai tampil di kotak **Konsol Log Aktivitas**.
   * Jika ingin memicu analisis Gemini AI manual untuk seluruh pair sekaligus, klik tombol **`🔄 Analisis Semua Pair`**.

5. **Hentikan Bot**:
   Klik tombol **`🛑 STOP BOT`** di halaman web dashboard untuk menghentikan loop trading dan memutuskan koneksi ke MT5 dengan aman.

---

## Struktur Proyek
```
bot-trading/
│
├── static/
│   ├── css/
│   │   └── style.css       # Desain tema gelap premium (Glassmorphism)
│   └── js/
│       └── app.js          # Logika frontend (polling API, chart TradingView)
│
├── templates/
│   └── index.html          # Halaman utama Web Dashboard UI
│
├── app.py                  # Backend server Flask (REST API & Web Server)
├── bot.py                  # Loop utama bot trading MT5 (Background Thread)
├── strategy.py             # Logika indikator teknis (EMA & RSI)
├── config.json             # File penyimpanan parameter trading dinamis (Ter-ignore di git)
├── latest_ai_analysis.json # Hasil analisis Gemini AI terperinci (Ter-ignore di git)
├── requirements.txt        # Daftar pustaka Python yang dibutuhkan
└── README.md               # Dokumentasi petunjuk penggunaan
```

---

## Penafian Risiko (Risk Disclaimer)
Trading Forex melibatkan risiko finansial yang sangat tinggi dan dapat mengakibatkan kerugian modal yang signifikan. Bot trading ini dirancang untuk tujuan pembelajaran dan simulasi. **Selalu uji bot ini terlebih dahulu di Akun Demo (Paper Trading) sebelum mempertimbangkan penggunaan dengan uang riil.** Penulis tidak bertanggung jawab atas segala kerugian finansial yang timbul dari penggunaan perangkat lunak ini.