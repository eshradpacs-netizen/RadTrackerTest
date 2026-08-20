/**
 * Radiology PC Tracker v1 - Frontend Real-Time WebSocket & Telegram Mini App Client
 */

let pcs = [];
let activeRoom = 'ALL';
let searchQuery = '';
let socket = null;
let selectedPc = null;

// Initialize Telegram WebApp SDK if available
const tgApp = window.Telegram?.WebApp;
if (tgApp) {
  try {
    tgApp.ready();
    tgApp.expand();
  } catch (e) {
    console.log("Telegram WebApp initialization warning:", e);
  }
}

// WebSocket Connection Setup
function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws`;
  
  socket = new WebSocket(wsUrl);

  socket.onopen = () => {
    console.log("Connected to Real-Time WebSockets Engine.");
    document.getElementById("ws-indicator").className = "flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
    document.getElementById("ws-indicator").innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-400 pulse-dot"></span> Canlı (0ms)`;
  };

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'init' || data.type === 'status_update') {
        pcs = data.computers || [];
        renderAll();
      }
    } catch (e) {
      console.error("Error parsing WS message:", e);
    }
  };

  socket.onclose = () => {
    console.warn("WebSocket disconnected. Reconnecting in 3s...");
    document.getElementById("ws-indicator").className = "flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20";
    document.getElementById("ws-indicator").innerHTML = `<span class="w-2 h-2 rounded-full bg-amber-400"></span> Bağlanıyor...`;
    setTimeout(connectWebSocket, 3000);
  };

  socket.onerror = (err) => {
    console.error("WebSocket error:", err);
    socket.close();
  };
}

// Render Summary Statistics Counter
function renderStats() {
  let active = 0, idle = 0, lunch = 0, offline = 0, suspicious = 0;
  pcs.forEach(p => {
    const st = p.status || 'offline';
    if (st === 'active') active++;
    else if (st === 'idle' || st === 'probably-idle') idle++;
    else if (st === 'lunch-break') lunch++;
    else if (st === 'suspicious') suspicious++;
    else offline++;
  });

  document.getElementById("stat-active").innerText = active;
  document.getElementById("stat-idle").innerText = idle;
  document.getElementById("stat-lunch").innerText = lunch;
  document.getElementById("stat-offline").innerText = offline;
  document.getElementById("stat-suspicious").innerText = suspicious;
}

// Format Last Seen relative time
function formatLastSeen(isoStr) {
  if (!isoStr) return "Henüz Sinyal Yok";
  try {
    const d = new Date(isoStr);
    const diffSec = Math.round((new Date() - d) / 1000);
    if (diffSec < 15) return "Anlık (Canlı)";
    if (diffSec < 60) return `${diffSec} sn önce`;
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)} dk önce`;
    return d.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
  } catch (e) {
    return isoStr;
  }
}

// Render PC Cards Grid
function renderGrid() {
  const grid = document.getElementById("pc-grid");
  grid.innerHTML = "";

  const filtered = pcs.filter(p => {
    const matchRoom = (activeRoom === 'ALL') || (p.room === activeRoom);
    const q = searchQuery.toLowerCase();
    const matchQuery = !q || 
      (p.friendlyName && p.friendlyName.toLowerCase().includes(q)) ||
      (p.hostname && p.hostname.toLowerCase().includes(q)) ||
      (p.username && p.username.toLowerCase().includes(q)) ||
      (p.ip && p.ip.includes(q));
    return matchRoom && matchQuery;
  });

  if (filtered.length === 0) {
    grid.innerHTML = `
      <div class="col-span-full py-12 text-center text-slate-500">
        <p class="text-3xl mb-2">🔍</p>
        <p class="text-sm font-medium">Aramaya uygun bilgisayar bulunamadı.</p>
      </div>
    `;
    return;
  }

  const statusConfig = {
    'active': { title: 'Dolu (Aktif)', badgeClass: 'status-active', icon: '🔴' },
    'idle': { title: 'Boşta (Kullanılabilir)', badgeClass: 'status-idle', icon: '🟢' },
    'probably-idle': { title: 'Muhtemelen Boş', badgeClass: 'status-probably-idle', icon: '🟡' },
    'lunch-break': { title: 'Öğle Arası', badgeClass: 'status-lunch-break', icon: '🍱' },
    'offline': { title: 'Çevrimdışı / Kapalı', badgeClass: 'status-offline', icon: '⚪' },
    'suspicious': { title: 'Şüpheli Aktivite', badgeClass: 'status-suspicious', icon: '⚠️' }
  };

  filtered.forEach(pc => {
    const st = pc.status || 'offline';
    const cfg = statusConfig[st] || statusConfig['offline'];
    const card = document.createElement("div");
    card.className = `glass-card rounded-2xl p-4 border transition-all duration-200 hover:scale-[1.02] cursor-pointer ${cfg.badgeClass}`;
    
    card.innerHTML = `
      <div class="flex items-start justify-between mb-3">
        <div>
          <span class="text-xs font-semibold px-2 py-0.5 rounded-md bg-slate-800/80 text-slate-300 border border-slate-700/50">${pc.room || 'Genel'}</span>
          <h3 class="text-base font-bold text-white mt-1">${pc.friendlyName || pc.hostname}</h3>
        </div>
        <span class="text-2xl">${cfg.icon}</span>
      </div>

      <div class="space-y-1.5 text-xs text-slate-300">
        <div class="flex items-center justify-between">
          <span class="text-slate-400">Durum:</span>
          <span class="font-semibold">${cfg.title}</span>
        </div>
        <div class="flex items-center justify-between">
          <span class="text-slate-400">Kullanıcı:</span>
          <span class="font-medium text-slate-100">${pc.username && pc.username !== 'unknown' ? pc.username : 'Belirtilmedi'}</span>
        </div>
        <div class="flex items-center justify-between">
          <span class="text-slate-400">Son İletişim:</span>
          <span class="font-mono text-slate-400">${formatLastSeen(pc.lastSeen)}</span>
        </div>
      </div>
    `;

    card.addEventListener("click", () => openModal(pc));
    grid.appendChild(card);
  });
}

// Open Detail Modal
function openModal(pc) {
  selectedPc = pc;
  if (tgApp?.HapticFeedback) {
    tgApp.HapticFeedback.impactOccurred('light');
  }

  document.getElementById("modal-title").innerText = pc.friendlyName || pc.hostname;
  document.getElementById("modal-room").innerText = `${pc.room || 'Genel'} Odası`;
  document.getElementById("modal-user").innerText = pc.username && pc.username !== 'unknown' ? pc.username : 'Belirtilmedi';
  document.getElementById("modal-hostname").innerText = pc.hostname || 'Bilinmiyor';
  document.getElementById("modal-ip").innerText = pc.ip || 'Bilinmiyor';
  document.getElementById("modal-idle").innerText = `${pc.idleTimeSeconds || 0} saniye`;
  document.getElementById("modal-lastseen").innerText = formatLastSeen(pc.lastSeen);

  const statusIcons = { 'active': '🔴', 'idle': '🟢', 'lunch-break': '🍱', 'offline': '⚪', 'suspicious': '⚠️' };
  document.getElementById("modal-status-icon").innerText = statusIcons[pc.status] || '⚪';

  document.getElementById("detail-modal").classList.remove("hidden");
  document.getElementById("detail-modal").classList.add("flex");
}

function closeModal() {
  document.getElementById("detail-modal").classList.add("hidden");
  document.getElementById("detail-modal").classList.remove("flex");
}

function renderAll() {
  renderStats();
  renderGrid();
}

// Auth & Verification Modal Handlers
let pendingEmail = "";

function checkAuthStatus() {
  const token = localStorage.getItem("radtracker_token");
  const email = localStorage.getItem("radtracker_email");
  const mainContent = document.getElementById("main-content");
  const authContainer = document.getElementById("auth-container");
  
  if (token && email) {
    document.getElementById("user-banner")?.classList.remove("hidden");
    if (document.getElementById("user-email-label")) {
      document.getElementById("user-email-label").innerText = `Doğrulanmış Hekim (${email})`;
    }
    if (document.getElementById("auth-btn-label")) {
      document.getElementById("auth-btn-label").innerText = email.split('@')[0];
    }
    if (mainContent) mainContent.classList.remove("hidden");
    if (authContainer) authContainer.classList.add("hidden");
  } else {
    document.getElementById("user-banner")?.classList.add("hidden");
    if (document.getElementById("auth-btn-label")) {
      document.getElementById("auth-btn-label").innerText = "Giriş Yap";
    }
    if (mainContent) mainContent.classList.add("hidden");
    if (authContainer) authContainer.classList.remove("hidden");
  }
}

function openAuthModal() {
  const modal = document.getElementById("auth-modal");
  if (modal) {
    modal.classList.remove("hidden");
    modal.classList.add("flex");
  }
}

function closeAuthModal() {
  const modal = document.getElementById("auth-modal");
  if (modal) {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  }
  const errBox = document.getElementById("auth-error");
  if (errBox) errBox.classList.add("hidden");
}

function showAuthError(msg) {
  const errBox = document.getElementById("auth-error");
  if (errBox) {
    errBox.innerText = msg;
    errBox.classList.remove("hidden");
  }
}

// Event Listeners
document.addEventListener("DOMContentLoaded", () => {
  connectWebSocket();
  checkAuthStatus();

  // Search input
  document.getElementById("search-input")?.addEventListener("input", (e) => {
    searchQuery = e.target.value;
    renderGrid();
  });

  // Room tab filter
  document.querySelectorAll(".room-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".room-tab").forEach(t => {
        t.classList.remove("bg-cyan-500", "text-white", "active");
        t.classList.add("bg-slate-800", "text-slate-300");
      });
      tab.classList.remove("bg-slate-800", "text-slate-300");
      tab.classList.add("bg-cyan-500", "text-white", "active");
      activeRoom = tab.getAttribute("data-room");
      renderGrid();
    });
  });

  // Modals close buttons
  document.getElementById("modal-close")?.addEventListener("click", closeModal);
  document.getElementById("auth-modal-close")?.addEventListener("click", closeAuthModal);
  document.getElementById("auth-btn")?.addEventListener("click", openAuthModal);

  document.getElementById("logout-btn")?.addEventListener("click", () => {
    localStorage.removeItem("radtracker_token");
    localStorage.removeItem("radtracker_email");
    checkAuthStatus();
  });

  // Helper to extract Telegram WebApp User
  function getTgUserData() {
    const tgUser = tgApp?.initDataUnsafe?.user || {};
    return {
      telegram_id: tgUser.id ? String(tgUser.id) : "",
      telegram_username: tgUser.username ? String(tgUser.username) : ""
    };
  }

  // Seamless Auth Submit (0-click passwordless verification)
  document.getElementById("form-seamless")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("seamless-email").value;
    const tgData = getTgUserData();

    try {
      const resp = await fetch("/api/seamless-auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password: "seamless", ...tgData })
      });
      const data = await resp.json();
      if (resp.ok && data.success) {
        localStorage.setItem("radtracker_token", data.token);
        localStorage.setItem("radtracker_email", data.email);
        checkAuthStatus();
        closeAuthModal();
      } else {
        showAuthError(data.detail || "Giriş başarısız.");
      }
    } catch (err) {
      showAuthError("Bağlantı hatası oluştu.");
    }
  });

  // Subscribe button
  document.getElementById("modal-subscribe-btn").addEventListener("click", () => {
    if (tgApp?.sendData && selectedPc) {
      tgApp.sendData(JSON.stringify({ action: "subscribe", pc_id: selectedPc.id }));
      alert(`${selectedPc.friendlyName || selectedPc.hostname} için Telegram bildirimi aktifleştirildi!`);
    } else {
      alert("Telegram Bot sohbetinden /takip " + (selectedPc?.friendlyName || selectedPc?.hostname) + " yazarak bildirim alabilirsiniz.");
    }
    closeModal();
  });
});
