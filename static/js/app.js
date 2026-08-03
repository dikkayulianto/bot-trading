// State Variables
let currentConfig = null;
let displayedLogsCount = 0;
let lastChartSymbol = "";
let isScrolledToBottom = true;

// On Page Load
document.addEventListener("DOMContentLoaded", () => {
    // Initial fetches
    fetchConfig();
    fetchStatus();
    fetchLogs();

    // Start periodic update loops
    setInterval(fetchStatus, 2000);
    setInterval(fetchLogs, 2000);

    // Monitor log console scrolling to check if user scrolled up
    const logConsole = document.getElementById("log-console");
    logConsole.addEventListener("scroll", () => {
        // Allow a 10px threshold
        isScrolledToBottom = (logConsole.scrollHeight - logConsole.clientHeight - logConsole.scrollTop) < 10;
    });
});

// Show floating notification
function showNotification(message, type = "success") {
    const el = document.getElementById("notification");
    el.innerText = message;
    el.className = `notification show ${type}`;
    
    setTimeout(() => {
        el.className = "notification";
    }, 4000);
}

// Fetch bot configurations
async function fetchConfig() {
    try {
        const response = await fetch("/api/config");
        const data = await response.json();
        currentConfig = data;

        // Populate Form Fields
        document.getElementById("symbols").value = data.symbols.join(", ");
        document.getElementById("timeframe").value = data.timeframe;
        document.getElementById("lot_size").value = data.lot_size;
        document.getElementById("sl_pips").value = data.sl_pips;
        document.getElementById("tp_pips").value = data.tp_pips;
        document.getElementById("magic_number").value = data.magic_number;
        document.getElementById("ema_fast").value = data.ema_fast;
        document.getElementById("ema_slow").value = data.ema_slow;
        document.getElementById("rsi_period").value = data.rsi_period;
        document.getElementById("rsi_overbought").value = data.rsi_overbought;
        document.getElementById("rsi_oversold").value = data.rsi_oversold;
        document.getElementById("loop_interval_seconds").value = data.loop_interval_seconds;

        // Update Chart Dropdown Option list
        updateChartDropdownOptions(data.symbols);
        
        // Initialize TradingView chart with the first symbol if not loaded yet
        if (data.symbols.length > 0 && !lastChartSymbol) {
            loadTradingViewChart(data.symbols[0]);
        }
    } catch (error) {
        console.error("Error fetching config:", error);
        showNotification("Gagal memuat konfigurasi dari server.", "error");
    }
}

// Update TradingView Chart dropdown options
function updateChartDropdownOptions(symbols) {
    const select = document.getElementById("chart-symbol-select");
    const currentSelected = select.value;
    
    select.innerHTML = "";
    symbols.forEach(symbol => {
        const option = document.createElement("option");
        option.value = symbol;
        option.text = symbol;
        select.appendChild(option);
    });

    if (symbols.includes(currentSelected)) {
        select.value = currentSelected;
    } else if (symbols.length > 0) {
        select.value = symbols[0];
    }
}

// Load TradingView Chart widget
function loadTradingViewChart(symbol) {
    if (symbol === lastChartSymbol) return;
    lastChartSymbol = symbol;
    
    // Map standard Forex pairs (e.g. EURUSD) to FX:EURUSD
    let formattedSymbol = symbol;
    if (!symbol.includes(":")) {
        formattedSymbol = "FX:" + symbol;
    }

    try {
        new TradingView.widget({
            "autosize": true,
            "symbol": formattedSymbol,
            "interval": "5",
            "timezone": "Etc/UTC",
            "theme": "dark",
            "style": "1",
            "locale": "en",
            "enable_publishing": false,
            "hide_side_toolbar": false,
            "allow_symbol_change": true,
            "container_id": "tradingview_chart"
        });
    } catch (e) {
        console.error("TradingView widget failed to load:", e);
    }
}

// Chart Selection Dropdown Handler
function updateChartFromDropdown() {
    const select = document.getElementById("chart-symbol-select");
    loadTradingViewChart(select.value);
}

// Save configuration from UI to JSON file
async function saveConfig() {
    const symbolsVal = document.getElementById("symbols").value;
    const timeframeVal = document.getElementById("timeframe").value;
    const lotSizeVal = document.getElementById("lot_size").value;
    const slPipsVal = document.getElementById("sl_pips").value;
    const tpPipsVal = document.getElementById("tp_pips").value;
    const magicNumVal = document.getElementById("magic_number").value;
    const emaFastVal = document.getElementById("ema_fast").value;
    const emaSlowVal = document.getElementById("ema_slow").value;
    const rsiPeriodVal = document.getElementById("rsi_period").value;
    const rsiOverboughtVal = document.getElementById("rsi_overbought").value;
    const rsiOversoldVal = document.getElementById("rsi_oversold").value;
    const intervalVal = document.getElementById("loop_interval_seconds").value;

    const payload = {
        symbols: symbolsVal,
        timeframe: timeframeVal,
        lot_size: lotSizeVal,
        sl_pips: slPipsVal,
        tp_pips: tpPipsVal,
        magic_number: magicNumVal,
        ema_fast: emaFastVal,
        ema_slow: emaSlowVal,
        rsi_period: rsiPeriodVal,
        rsi_overbought: rsiOverboughtVal,
        rsi_oversold: rsiOversoldVal,
        loop_interval_seconds: intervalVal
    };

    try {
        const response = await fetch("/api/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const result = await response.json();

        if (response.ok && result.status === "success") {
            showNotification("Pengaturan berhasil disimpan!");
            fetchConfig(); // Reload layout
        } else {
            showNotification("Gagal menyimpan: " + result.message, "error");
        }
    } catch (error) {
        console.error("Error saving config:", error);
        showNotification("Terjadi kesalahan saat menyimpan pengaturan.", "error");
    }
}

// Fetch bot status, MT5 connection, account statistics, and open positions
async function fetchStatus() {
    try {
        const response = await fetch("/api/status");
        const status = await response.json();

        // Update Bot running state badges
        const botBadge = document.getElementById("bot-status-badge");
        const btnStart = document.getElementById("btn-start");
        const btnStop = document.getElementById("btn-stop");

        if (status.bot_running) {
            botBadge.className = "badge badge-running";
            botBadge.querySelector(".status-text").innerText = "RUNNING";
            btnStart.disabled = true;
            btnStop.disabled = false;
        } else {
            botBadge.className = "badge badge-stopped";
            botBadge.querySelector(".status-text").innerText = "STOPPED";
            btnStart.disabled = false;
            btnStop.disabled = true;
        }

        // Update MT5 Connection state badge
        const mt5Badge = document.getElementById("mt5-status-badge");
        if (status.mt5_connected) {
            mt5Badge.className = "badge badge-online";
            mt5Badge.querySelector(".status-text").innerText = "CONNECTED";
        } else {
            mt5Badge.className = "badge badge-offline";
            mt5Badge.querySelector(".status-text").innerText = "DISCONNECTED";
        }

        // Update Account Info
        if (status.account) {
            document.getElementById("account-server").innerText = status.account.server;
            document.getElementById("stat-login").innerText = status.account.login;
            document.getElementById("stat-balance").innerText = `${formatCurrency(status.account.balance)} ${status.account.currency}`;
            document.getElementById("stat-equity").innerText = `${formatCurrency(status.account.equity)} ${status.account.currency}`;

            const profitEl = document.getElementById("stat-profit");
            const profit = status.account.profit;
            profitEl.innerText = `${profit >= 0 ? "+" : ""}${formatCurrency(profit)} ${status.account.currency}`;
            
            if (profit > 0) {
                profitEl.className = "stat-val profit-positive";
            } else if (profit < 0) {
                profitEl.className = "stat-val profit-negative";
            } else {
                profitEl.className = "stat-val";
            }
        } else {
            document.getElementById("account-server").innerText = "-";
            document.getElementById("stat-login").innerText = "-";
            document.getElementById("stat-balance").innerText = "$0.00";
            document.getElementById("stat-equity").innerText = "$0.00";
            document.getElementById("stat-profit").innerText = "$0.00";
            document.getElementById("stat-profit").className = "stat-val";
        }

        // Update Open Positions Table
        const tbody = document.getElementById("positions-table-body");
        tbody.innerHTML = "";

        if (status.positions && status.positions.length > 0) {
            status.positions.forEach(pos => {
                const tr = document.createElement("tr");
                const profitClass = pos.profit > 0 ? "profit-positive" : (pos.profit < 0 ? "profit-negative" : "");
                
                tr.innerHTML = `
                    <td>${pos.ticket}</td>
                    <td><strong>${pos.symbol}</strong></td>
                    <td class="${pos.type === 'BUY' ? 'profit-positive' : 'profit-negative'}"><strong>${pos.type}</strong></td>
                    <td>${pos.volume.toFixed(2)}</td>
                    <td>${pos.price_open.toFixed(5)}</td>
                    <td>${pos.price_current.toFixed(5)}</td>
                    <td>${pos.sl > 0 ? pos.sl.toFixed(5) : '-'}</td>
                    <td>${pos.tp > 0 ? pos.tp.toFixed(5) : '-'}</td>
                    <td class="${profitClass}"><strong>$${pos.profit.toFixed(2)}</strong></td>
                `;
                tbody.appendChild(tr);
            });
        } else {
            tbody.innerHTML = `<tr><td colspan="9" class="empty-table-text">Tidak ada posisi terbuka saat ini.</td></tr>`;
        }

    } catch (error) {
        console.error("Error fetching status:", error);
    }
}

// Fetch in-memory logs and stream to console log element
async function fetchLogs() {
    try {
        const response = await fetch("/api/logs");
        const logs = await response.json();

        const logConsole = document.getElementById("log-console");
        
        // Clear if logs count decreased (indicates reset)
        if (logs.length < displayedLogsCount) {
            logConsole.innerHTML = "";
            displayedLogsCount = 0;
        }

        // Add new logs
        for (let i = displayedLogsCount; i < logs.length; i++) {
            const line = logs[i];
            const div = document.createElement("div");
            
            // Determine log class
            let typeClass = "info";
            if (line.includes(" - WARNING - ")) typeClass = "warning";
            else if (line.includes(" - ERROR - ")) typeClass = "error";
            
            div.className = `log-line ${typeClass}`;
            div.innerText = line;
            logConsole.appendChild(div);
        }

        displayedLogsCount = logs.length;

        // Auto Scroll to bottom if user is already at the bottom
        if (isScrolledToBottom && logs.length > 0) {
            logConsole.scrollTop = logConsole.scrollHeight;
        }

    } catch (error) {
        console.error("Error fetching logs:", error);
    }
}

// Start the trading bot process
async function startBot() {
    try {
        const response = await fetch("/api/start", { method: "POST" });
        const result = await response.json();
        
        if (response.ok && result.status === "success") {
            showNotification("Mempersiapkan bot trading...");
            fetchStatus();
        } else {
            showNotification("Gagal menjalankan bot: " + result.message, "error");
        }
    } catch (error) {
        console.error("Error starting bot:", error);
        showNotification("Terjadi kesalahan saat memulai bot.", "error");
    }
}

// Stop the trading bot process
async function stopBot() {
    try {
        const response = await fetch("/api/stop", { method: "POST" });
        const result = await response.json();
        
        if (response.ok && result.status === "success") {
            showNotification("Menghentikan bot trading...", "warning");
            fetchStatus();
        } else {
            showNotification("Gagal menghentikan: " + result.message, "error");
        }
    } catch (error) {
        console.error("Error stopping bot:", error);
        showNotification("Terjadi kesalahan saat menghentikan bot.", "error");
    }
}

// Helper to format currency values
function formatCurrency(val) {
    if (val === null || val === undefined) return "0.00";
    return val.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// Clear the log terminal UI visually
function clearLogsUI() {
    document.getElementById("log-console").innerHTML = "";
    displayedLogsCount = 0;
}
