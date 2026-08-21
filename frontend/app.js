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
      } else if (data.type === 'chat_message') {
        appendChatMessage(data.message);
      } else if (data.type === 'pc_note_update') {
        const pc = pcs.find(p => p.id === data.pc_id);
        if (pc && data.metadata) {
          pc.notes = data.metadata.notes;
          if (data.metadata.friendlyName) pc.friendlyName = data.metadata.friendlyName;
          if (data.metadata.room) pc.room = data.metadata.room;
          renderGrid();
        }
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

      <div class="space-y-1.5 text-xs text-slate-300 mb-3">
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

      <div class="pt-2 border-t border-slate-700/50 flex items-center justify-between">
        <span class="text-[11px] text-slate-400 font-mono">${pc.ip || ''}</span>
        <button onclick="event.stopPropagation(); showPCLocationOnKroki('${pc.id}')" class="px-2.5 py-1 text-[11px] font-bold rounded-lg bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 hover:bg-cyan-500/40 transition-all flex items-center gap-1 shadow-sm">
          📍 Konumu Göster
        </button>
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

  const notesInput = document.getElementById("modal-notes-input");
  if (notesInput) notesInput.value = pc.notes || "";

  document.getElementById("detail-modal").classList.remove("hidden");
  document.getElementById("detail-modal").classList.add("flex");
}

function closeModal() {
  document.getElementById("detail-modal").classList.add("hidden");
  document.getElementById("detail-modal").classList.remove("flex");
}

const KROKI_MAP = {
  'KD-PACS-01': 'Kadın Doğum PACS Oda 1 PC 1',
  'KD-PACS-02': 'Kadın Doğum PACS Oda 1 PC 2',
  'KD-PACS-03': 'Kadın Doğum PACS Oda 1 PC 3',
  'Cassiopeia-β': 'KVC PACS Oda 1 PC 1',
  'Cassiopeia-α': 'KVC PACS Oda 1 PC 2',
  'Aquila-α': 'Kadın Doğum Toplantı Odası PC 1',
  'Perseus-β': 'Nöroloji PACS Oda 1 PC 1',
  'Perseus-α': 'Nöroloji PACS Oda 1 PC 2',
  'Perseus-γ': 'Nöroloji PACS Oda 1 PC 3',
  'ws-pe-01': 'Nöroloji PACS Oda 1 PC 1',
  'ws-pe-02': 'Nöroloji PACS Oda 1 PC 2',
  'ws-pe-03': 'Nöroloji PACS Oda 1 PC 3',
  'ws-y-01': 'Genel PACS Oda 1 PC 1',
  'ws-y-02': 'Genel PACS Oda 1 PC 2',
  'ws-y-03': 'Genel PACS Oda 1 PC 3',
  'ws-y-04': 'Genel PACS Oda 1 PC 4',
  'ws-y-05': 'Genel PACS Oda 1 PC 5',
  'ws-y-06': 'Genel PACS Oda 1 PC 6',
  'ws-y-07': 'Genel PACS Oda 1 PC 7',
  'ws-y-08': 'Genel PACS Oda 1 PC 8',
  'ws-p-01': 'Genel PACS Oda 2 PC 1',
  'ws-p-02': 'Genel PACS Oda 2 PC 2',
  'ws-p-03': 'Genel PACS Oda 2 PC 3',
  'ws-p-04': 'Genel PACS Oda 2 PC 4',
  'ws-p-05': 'Genel PACS Oda 2 PC 5',
  'ws-p-06': 'Genel PACS Oda 2 PC 6',
  'ws-p-07': 'Genel PACS Oda 2 PC 7',
  'ws-p-08': 'Genel PACS Oda 2 PC 8',
  'ws-t-01': 'Genel PACS Oda 3 PC 1',
  'ws-t-02': 'Genel PACS Oda 3 PC 2',
  'ws-t-03': 'Genel PACS Oda 3 PC 3',
  'ws-t-04': 'Genel PACS Oda 3 PC 4',
  'ws-t-05': 'Genel PACS Oda 3 PC 5',
  'ws-t-06': 'Genel PACS Oda 3 PC 6',
  'ws-t-07': 'Genel PACS Oda 3 PC 7',
  'ws-t-08': 'Genel PACS Oda 3 PC 8',
  'ws-t-09': 'Genel PACS Oda 3 PC 9',
  'ws-t-10': 'Genel PACS Oda 3 PC 10',
  'ws-t-11': 'Genel PACS Oda 3 PC 11',
  'ws-b-01': 'Genel PACS Oda 4 PC 1',
  'ws-b-02': 'Genel PACS Oda 4 PC 2',
  'ws-b-03': 'Genel PACS Oda 4 PC 3',
  'ws-b-04': 'Genel PACS Oda 4 PC 4',
  'ws-b-05': 'Genel PACS Oda 4 PC 5',
  'ws-b-06': 'Genel PACS Oda 4 PC 6',
  'ws-b-07': 'Genel PACS Oda 4 PC 7',
  'ws-b-08': 'Genel PACS Oda 4 PC 8',
  'ws-b-09': 'Genel PACS Oda 4 PC 9',
  'ws-b-10': 'Genel PACS Oda 4 PC 10',
  'ws-pi-01': 'Genel PACS Oda 5 PC 1',
  'e092e2c2-5348-4724-9a00-5d37a4486176': 'Genel PACS Oda 6 PC 1',
};

function updateKrokiColors() {
  Object.keys(KROKI_MAP).forEach(wsId => {
    const el = document.getElementById(wsId);
    if (!el) return;

    const friendly = KROKI_MAP[wsId];
    const pc = pcs.find(p => p.friendlyName === friendly || p.hostname === friendly);

    el.classList.remove('ws-idle', 'ws-active', 'ws-lunch-break', 'ws-offline');

    if (pc) {
      const st = pc.status || 'offline';
      if (st === 'idle') el.classList.add('ws-idle');
      else if (st === 'active') el.classList.add('ws-active');
      else if (st === 'lunch-break') el.classList.add('ws-lunch-break');
      else el.classList.add('ws-offline');

      el.onclick = () => openModal(pc);
    } else {
      el.classList.add('ws-offline');
    }
  });
}

let activeKrokiRoom = "ALL";

function switchKrokiLayout(layoutId) {
  document.querySelectorAll(".kroki-layout-btn").forEach(btn => {
    if (btn.getAttribute("data-layout") === layoutId) {
      btn.className = "kroki-layout-btn active px-3.5 py-2 rounded-xl font-bold bg-cyan-500 text-white shadow transition-all border border-cyan-400/30";
    } else {
      btn.className = "kroki-layout-btn px-3.5 py-2 rounded-xl font-bold bg-slate-800 text-slate-300 hover:bg-slate-700 transition-all border border-slate-700";
    }
  });

  document.querySelectorAll(".kroki-view-wrapper").forEach(wrapper => {
    if (wrapper.id === layoutId) {
      wrapper.classList.remove("hidden");
    } else {
      wrapper.classList.add("hidden");
    }
  });

  updateKrokiColors();
}

function showPCLocationOnKroki(pcId) {
  const pc = pcs.find(p => p.id === pcId || p.hostname === pcId || p.friendlyName === pcId);
  if (!pc) {
    console.warn("PC not found for location show:", pcId);
    return;
  }

  closeModal();

  // 1. Activate Kroki View Mode
  document.getElementById("pc-grid-container")?.classList.add("hidden");
  document.getElementById("kroki-container")?.classList.remove("hidden");
  
  const viewCardBtn = document.getElementById("view-card-btn");
  const viewKrokiBtn = document.getElementById("view-kroki-btn");
  if (viewKrokiBtn) viewKrokiBtn.className = "px-3 py-2 text-xs font-bold rounded-xl bg-cyan-500 text-white shadow transition-all";
  if (viewCardBtn) viewCardBtn.className = "px-3 py-2 text-xs font-bold rounded-xl bg-slate-800 text-slate-300 hover:bg-slate-700 transition-all border border-slate-700";

  document.querySelectorAll(".room-tab").forEach(t => {
    t.classList.remove("bg-cyan-500", "text-white", "active");
    t.classList.add("bg-slate-800", "text-slate-300");
  });
  const krokiTab = document.querySelector('.room-tab[data-room="KROKI"]');
  if (krokiTab) {
    krokiTab.classList.remove("bg-slate-800", "text-slate-300");
    krokiTab.classList.add("bg-cyan-500", "text-white", "active");
  }

  // 2. Exact Target Kroki Room Layout Matching
  let targetLayout = "kroki-pacs-raporlama";
  const name = (pc.friendlyName || "").toLowerCase();
  const room = (pc.room || "").toLowerCase();

  if (name.includes("kvc") || room.includes("kvc")) {
    targetLayout = "kroki-cassiopeia";
  } else if (name.includes("kadın doğum toplantı") || room.includes("toplantı")) {
    targetLayout = "kroki-kadin-dogum";
  } else if (name.includes("kadın doğum pacs") || (room.includes("kadın doğum") && room.includes("pacs"))) {
    targetLayout = "kroki-kadin-dogum-pacs";
  } else if (name.includes("onkoloji") || room.includes("onkoloji")) {
    targetLayout = "kroki-onkoloji";
  } else if (name.includes("ftr") || room.includes("ftr")) {
    targetLayout = "kroki-ftr";
  } else {
    targetLayout = "kroki-pacs-raporlama";
  }

  switchKrokiLayout(targetLayout);

  // Clear previous active sonar highlights
  document.querySelectorAll('.ws-aktif').forEach(el => el.classList.remove('ws-aktif'));

  // 3. Find Workstation Element across layouts
  let wsEl = document.getElementById(pc.id) || document.getElementById(pc.friendlyName);

  if (!wsEl) {
    for (const [wsId, fn] of Object.entries(KROKI_MAP)) {
      if (fn.toLowerCase() === (pc.friendlyName || "").toLowerCase() || 
          fn.toLowerCase() === (pc.hostname || "").toLowerCase() || 
          wsId === pc.id) {
        wsEl = document.getElementById(wsId);
        if (wsEl) break;
      }
    }
  }

  // Fallback: search by title attribute
  if (!wsEl && pc.friendlyName) {
    wsEl = document.querySelector(`.ws[title*="${pc.friendlyName}"]`) || 
           document.querySelector(`[title*="${pc.friendlyName}"]`);
  }

  if (wsEl) {
    wsEl.classList.add('ws-aktif');
    setTimeout(() => {
      wsEl.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
    }, 150);
  } else {
    console.warn("Could not find workstation DOM element for PC:", pc);
  }
}

function renderAll() {
  renderStats();
  renderGrid();
  updateKrokiColors();
}

// Auth & Verification Modal Handlers
let pendingEmail = "";

function checkAuthStatus() {
  const token = localStorage.getItem("radtracker_token");
  const email = localStorage.getItem("radtracker_email");
  const mainContent = document.getElementById("main-content");
  const authContainer = document.getElementById("auth-container");
  const authBtn = document.getElementById("auth-btn");
  
  if (token && email) {
    document.getElementById("user-banner")?.classList.remove("hidden");
    if (document.getElementById("user-email-label")) {
      document.getElementById("user-email-label").innerText = `Doğrulanmış Hekim (${email})`;
    }
    if (document.getElementById("auth-btn-label")) {
      document.getElementById("auth-btn-label").innerText = email.split('@')[0];
    }
    if (authBtn) authBtn.classList.remove("hidden");
    if (mainContent) mainContent.classList.remove("hidden");
    if (authContainer) authContainer.classList.add("hidden");
  } else {
    document.getElementById("user-banner")?.classList.add("hidden");
    if (authBtn) authBtn.classList.add("hidden");
    if (mainContent) mainContent.classList.add("hidden");
    if (authContainer) authContainer.classList.remove("hidden");
  }
}

function openAuthModal() {
  const authContainer = document.getElementById("auth-container");
  if (authContainer) {
    authContainer.classList.remove("hidden");
    document.getElementById("seamless-email")?.focus();
  }
}

function closeAuthModal() {
  const authContainer = document.getElementById("auth-container");
  if (authContainer) {
    authContainer.classList.add("hidden");
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

  // View mode switcher (Kart vs Kroki Planı)
  document.getElementById("view-card-btn")?.addEventListener("click", () => {
    document.getElementById("pc-grid-container")?.classList.remove("hidden");
    document.getElementById("kroki-container")?.classList.add("hidden");
    document.getElementById("view-card-btn").className = "px-3 py-2 text-xs font-bold rounded-xl bg-cyan-500 text-white shadow transition-all";
    document.getElementById("view-kroki-btn").className = "px-3 py-2 text-xs font-bold rounded-xl bg-slate-800 text-slate-300 hover:bg-slate-700 transition-all border border-slate-700";
  });

  document.getElementById("view-kroki-btn")?.addEventListener("click", () => {
    document.getElementById("kroki-container")?.classList.remove("hidden");
    document.getElementById("pc-grid-container")?.classList.add("hidden");
    document.getElementById("view-kroki-btn").className = "px-3 py-2 text-xs font-bold rounded-xl bg-cyan-500 text-white shadow transition-all";
    document.getElementById("view-card-btn").className = "px-3 py-2 text-xs font-bold rounded-xl bg-slate-800 text-slate-300 hover:bg-slate-700 transition-all border border-slate-700";
    updateKrokiColors();
  });

  // Kroki Layout Switcher Buttons
  document.querySelectorAll(".kroki-layout-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const layoutId = btn.getAttribute("data-layout");
      switchKrokiLayout(layoutId);
    });
  });

  // Search input
  document.getElementById("search-input")?.addEventListener("input", (e) => {
    searchQuery = e.target.value;
    renderGrid();
  });

  // Room tab filter & Kroki toggle
  document.querySelectorAll(".room-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".room-tab").forEach(t => {
        t.classList.remove("bg-cyan-500", "text-white", "active");
        t.classList.add("bg-slate-800", "text-slate-300");
      });
      tab.classList.remove("bg-slate-800", "text-slate-300");
      tab.classList.add("bg-cyan-500", "text-white", "active");

      const targetRoom = tab.getAttribute("data-room");
      if (targetRoom === "KROKI") {
        document.getElementById("pc-grid-container")?.classList.add("hidden");
        document.getElementById("kroki-container")?.classList.remove("hidden");
        updateKrokiColors();
      } else {
        document.getElementById("kroki-container")?.classList.add("hidden");
        document.getElementById("pc-grid-container")?.classList.remove("hidden");
        activeRoom = targetRoom;
        renderGrid();
      }
    });
  });

  // Modals close & locate buttons
  document.getElementById("modal-close")?.addEventListener("click", closeModal);
  document.getElementById("modal-locate-btn")?.addEventListener("click", () => {
    if (selectedPc) showPCLocationOnKroki(selectedPc.id);
  });
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

  let currentAuthEmail = "";

  // Step 1: Send Telegram Code
  document.getElementById("form-send-code")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const emailInput = document.getElementById("auth-email");
    const email = emailInput ? emailInput.value.trim() : "";
    const tgData = getTgUserData();
    const errBox = document.getElementById("auth-error");
    if (errBox) errBox.classList.add("hidden");

    if (!email) return;

    const btn = document.getElementById("btn-send-code");
    if (btn) {
      btn.disabled = true;
      btn.innerText = "⏳ Telegram'a Kod Gönderiliyor...";
    }

    try {
      const resp = await fetch("/api/send-telegram-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, ...tgData })
      });
      const data = await resp.json();

      if (resp.ok && data.success) {
        currentAuthEmail = email;
        document.getElementById("form-send-code")?.classList.add("hidden");
        document.getElementById("form-verify-code")?.classList.remove("hidden");
        const subtitle = document.getElementById("auth-subtitle");
        if (subtitle) subtitle.innerText = `${email} adresine 6 haneli Telegram doğrulama kodu gönderildi.`;
        document.getElementById("auth-code")?.focus();
      } else {
        showAuthError(data.detail || "Kod gönderilemedi.");
      }
    } catch (err) {
      showAuthError("Bağlantı hatası oluştu. Lütfen tekrar deneyin.");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerText = "🔑 Telegram'a Doğrulama Kodu Gönder";
      }
    }
  });

  // Step 2: Verify 6-Digit OTP Code
  document.getElementById("form-verify-code")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const codeInput = document.getElementById("auth-code");
    const code = codeInput ? codeInput.value.trim() : "";
    const tgData = getTgUserData();
    const errBox = document.getElementById("auth-error");
    if (errBox) errBox.classList.add("hidden");

    if (!code || !currentAuthEmail) return;

    const btn = document.getElementById("btn-verify-code");
    if (btn) {
      btn.disabled = true;
      btn.innerText = "⏳ Kod Doğrulanıyor...";
    }

    try {
      const resp = await fetch("/api/verify-telegram-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: currentAuthEmail, code, ...tgData })
      });
      const data = await resp.json();

      if (resp.ok && data.success) {
        localStorage.setItem("radtracker_token", data.token);
        localStorage.setItem("radtracker_email", data.email);
        checkAuthStatus();
        closeAuthModal();
      } else {
        showAuthError(data.detail || "Kod doğrulama başarısız.");
      }
    } catch (err) {
      showAuthError("Bağlantı hatası oluştu.");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerText = "🔓 Kodu Doğrula & Canlı Paneli Aç";
      }
    }
  });

  // Back to Email Step
  document.getElementById("btn-back-to-email")?.addEventListener("click", () => {
    document.getElementById("form-verify-code")?.classList.add("hidden");
    document.getElementById("form-send-code")?.classList.remove("hidden");
    const subtitle = document.getElementById("auth-subtitle");
    if (subtitle) subtitle.innerText = "Canlı takip panelini açmak için yetkili e-posta adresinizi giriniz.";
    const errBox = document.getElementById("auth-error");
    if (errBox) errBox.classList.add("hidden");
  });

  // Save PC Note
  document.getElementById("modal-save-note-btn")?.addEventListener("click", async () => {
    if (!selectedPc) return;
    const notesInput = document.getElementById("modal-notes-input");
    const notes = notesInput ? notesInput.value : "";
    const author = localStorage.getItem("radtracker_email") || "Hekim";

    try {
      const resp = await fetch("/api/pc/notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pc_id: selectedPc.id, notes, author })
      });
      const data = await resp.json();
      if (data.success) {
        alert("Bilgisayar notu kaydedildi ve tüm hekimlere yayınlandı!");
      }
    } catch (e) {
      alert("Not kaydedilirken hata oluştu.");
    }
  });

  // Chat Toggle Drawer
  document.getElementById("chat-toggle-btn")?.addEventListener("click", () => {
    const drawer = document.getElementById("chat-drawer");
    if (drawer) {
      drawer.classList.toggle("hidden");
      drawer.classList.toggle("flex");
      if (!drawer.classList.contains("hidden")) {
        loadChatHistory();
      }
    }
  });

  document.getElementById("chat-close-btn")?.addEventListener("click", () => {
    const drawer = document.getElementById("chat-drawer");
    if (drawer) {
      drawer.classList.add("hidden");
      drawer.classList.remove("flex");
    }
  });

  // Send Chat Message
  document.getElementById("chat-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("chat-input");
    if (!input) return;
    const text = input.value.trim();
    const email = localStorage.getItem("radtracker_email") || "anonymous@hastane.com";

    if (!text) return;
    input.value = "";

    try {
      await fetch("/api/chat/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, text })
      });
    } catch (e) {
      console.error("Error sending chat message:", e);
    }
  });

  // Subscribe button
  document.getElementById("modal-subscribe-btn")?.addEventListener("click", () => {
    if (tgApp?.sendData && selectedPc) {
      tgApp.sendData(JSON.stringify({ action: "subscribe", pc_id: selectedPc.id }));
      alert(`${selectedPc.friendlyName || selectedPc.hostname} için Telegram bildirimi aktifleştirildi!`);
    } else {
      alert("Telegram Bot sohbetinden /takip " + (selectedPc?.friendlyName || selectedPc?.hostname) + " yazarak bildirim alabilirsiniz.");
    }
    closeModal();
  });
});

// Chat History Loader & Message Appender
async function loadChatHistory() {
  try {
    const resp = await fetch("/api/chat/messages");
    const data = await resp.json();
    if (data.success && data.messages) {
      const container = document.getElementById("chat-messages-container");
      if (container) {
        container.innerHTML = "";
        data.messages.forEach(appendChatMessage);
      }
    }
  } catch (e) {
    console.error("Error loading chat history:", e);
  }
}

function appendChatMessage(msg) {
  const container = document.getElementById("chat-messages-container");
  if (!container || !msg) return;

  const currentEmail = localStorage.getItem("radtracker_email") || "";
  const isMe = msg.sender_email === currentEmail;

  const msgDiv = document.createElement("div");
  msgDiv.className = `p-2.5 rounded-xl max-w-[85%] ${isMe ? 'bg-cyan-600/30 text-cyan-200 border border-cyan-500/30 ml-auto' : 'bg-slate-800 text-slate-200 border border-slate-700 mr-auto'}`;

  const timeStr = msg.timestamp ? new Date(msg.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Şimdi';
  msgDiv.innerHTML = `
    <div class="flex justify-between items-center gap-2 mb-1 font-semibold text-[11px] ${isMe ? 'text-cyan-300' : 'text-slate-400'}">
      <span>${msg.sender_name || 'Hekim'}</span>
      <span class="text-[10px] text-slate-500 font-normal">${timeStr}</span>
    </div>
    <div class="text-xs break-words">${msg.text || ''}</div>
  `;

  container.appendChild(msgDiv);
  container.scrollTop = container.scrollHeight;
}
