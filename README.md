# MT5 Forex Algo Trading Bot with Web Dashboard UI

Bot Trading Forex otomatis berbasis Python yang terintegrasi langsung dengan terminal **MetaTrader 5 (MT5)** di Windows. Dilengkapi dengan antarmuka **Web Dashboard UI** yang modern untuk memantau status akun, posisi terbuka, log aktivitas real-time, grafik TradingView, serta mengubah parameter trading secara dinamis.

---

## Fitur Utama
* **Multi-Currency Support**: Memantau dan melakukan perdagangan pada beberapa pasangan mata uang sekaligus (default: `EURUSD`, `GBPUSD`, `USDJPY`, `AUDUSD`).
* **Web Dashboard Control**: Menjalankan (*Start*) dan menghentikan (*Stop*) bot secara real-time hanya dengan satu klik di browser.
* **Pengaturan Dinamis (Hot-Reload)**: Mengubah lot size, target Take Profit (TP), Stop Loss (SL), parameter EMA, dan RSI langsung dari form UI tanpa perlu mematikan program.
* **Strategi Crossover EMA + RSI**:
  * **Sinyal BUY**: Terjadi persilangan EMA Crossover ke atas (Fast EMA memotong ke atas Slow EMA) pada *closed candle* dan RSI berada di bawah area *overbought* (jenuh beli).
  * **Sinyal SELL**: Terjadi persilangan EMA Crossover ke bawah (Fast EMA memotong ke bawah Slow EMA) pada *closed candle* dan RSI berada di atas area *oversold* (jenuh jual).
* **Manajemen Posisi Otomatis**: Secara otomatis mendeteksi dan menutup posisi berlawanan jika tren berbalik arah.
* **Pembersihan Log Terintegrasi**: Log aktivitas server Werkzeug (Flask HTTP Request) telah difilter agar konsol log di web dashboard bersih dan hanya menampilkan log analisis trading.

---

## Prasyarat Sistem
1. **Sistem Operasi**: Windows (wajib, karena pustaka `MetaTrader5` di Python hanya mendukung Windows).
2. **Python**: Versi 3.8 ke atas (disarankan Python 3.10+ atau 3.14).
3. **MetaTrader 5**: Terminal desktop MT5 terinstal dan terhubung ke akun trading (disarankan **Akun Demo** untuk pengujian).

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

3. **Mulai Bot**:
   * Di dashboard web, klik tombol **`⚡ START BOT`**.
   * Status bot pada badge akan berubah menjadi **`RUNNING`** dan log analisis pasar akan mulai tampil di kotak **Konsol Log Aktivitas**.
   * Jika ingin mengubah parameter trading (seperti Lot size atau target TP/SL), cukup ubah nilainya pada form **Pengaturan Parameter** lalu klik tombol **`💾 Simpan`**. Bot akan otomatis membaca pengaturan baru pada siklus cek berikutnya.

4. **Hentikan Bot**:
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
├── config.json             # File penyimpanan parameter trading dinamis
├── requirements.txt        # Daftar pustaka Python yang dibutuhkan
└── README.md               # Dokumentasi petunjuk penggunaan
```

---

## Penafian Risiko (Risk Disclaimer)
Trading Forex melibatkan risiko finansial yang sangat tinggi dan dapat mengakibatkan kerugian modal yang signifikan. Bot trading ini dirancang untuk tujuan pembelajaran dan simulasi. **Selalu uji bot ini terlebih dahulu di Akun Demo (Paper Trading) selama beberapa minggu sebelum mempertimbangkan penggunaan dengan uang riil.** Penulis tidak bertanggung jawab atas segala kerugian finansial yang timbul dari penggunaan perangkat lunak ini.