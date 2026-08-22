function formatMessageTime(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
}

// Check for Magic Link Token in URL (?magic_token=...)
async function checkMagicLoginToken() {
  const urlParams = new URLSearchParams(window.location.search);
  const magicToken = urlParams.get('magic_token');
  if (magicToken) {
    try {
      const resp = await fetch("/api/verify-magic-token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: magicToken })
      });
      const data = await resp.json();
      if (resp.ok && data.success) {
        const docName = localStorage.getItem("radtracker_doctor_name") || "";
        persistAuthSession(data.token, data.email, docName);
        // Clean URL parameter
        window.history.replaceState({}, document.title, window.location.pathname);
        checkAuthStatus();
        if (typeof showToast === 'function') {
          showToast("✅ E-posta ile giriş başarılı! Hoş geldiniz.");
        }
      }
    } catch (e) {
      console.error("Magic token verification error:", e);
    }
  }
}

/**
 * Radiology PC Tracker v1 - Frontend Real-Time Client
 */

// Global State Variables (Top-Level)
var pcs = [];
var activeRoom = 'ALL';
var activeStatusFilter = 'ALL';
var searchQuery = '';
var socket = null;
var selectedPc = null;

const ROOM_TO_KROKI_LAYOUT = {
  'GENEL_PACS': 'kroki-pacs-raporlama',
  'Genel PACS Oda 1': 'kroki-pacs-raporlama',
  'Genel PACS Oda 2': 'kroki-pacs-raporlama',
  'Genel PACS Oda 3': 'kroki-pacs-raporlama',
  'Genel PACS Oda 4': 'kroki-pacs-raporlama',
  'Genel PACS Oda 5': 'kroki-pacs-raporlama',
  'Toplantı Odası': 'kroki-pacs-raporlama',
  'Nöroloji PACS Odası': 'kroki-noroloji',
  'KVC PACS Odası': 'kroki-cassiopeia',
  'Kadın Doğum PACS Odası': 'kroki-kadin-dogum-pacs',
  'Kadın Doğum Toplantı Odası': 'kroki-kadin-dogum',
  'Onkoloji PACS Odası': 'kroki-onkoloji',
  'FTR PACS Odası': 'kroki-ftr'
};

// Unified View Switchers
function showGridView() {
  const krokiCont = document.getElementById("kroki-container");
  const pcGridCont = document.getElementById("pc-grid-container");
  if (krokiCont) {
    krokiCont.classList.add("hidden");
    krokiCont.removeAttribute("style");
  }
  if (pcGridCont) {
    pcGridCont.classList.remove("hidden");
    pcGridCont.removeAttribute("style");
  }
}

function showKrokiView(layoutId = 'kroki-pacs-raporlama') {
  const krokiCont = document.getElementById("kroki-container");
  const pcGridCont = document.getElementById("pc-grid-container");
  if (pcGridCont) {
    pcGridCont.classList.add("hidden");
    pcGridCont.removeAttribute("style");
  }
  if (krokiCont) {
    krokiCont.classList.remove("hidden");
    krokiCont.removeAttribute("style");
  }
  switchKrokiLayout(layoutId);
}

// Global Bulletproof Status Filter Handler
window.filterByStatus = function(statusName) {
  if (activeStatusFilter === statusName) {
    // Toggle off: return to all
    activeStatusFilter = "ALL";
    document.querySelectorAll(".stat-filter-card").forEach(c => {
      c.classList.remove("ring-2", "ring-cyan-400", "bg-cyan-500/20", "active-filter");
    });
  } else {
    // Toggle on: filter by selected status
    activeStatusFilter = statusName;
    document.querySelectorAll(".stat-filter-card").forEach(c => {
      if (c.getAttribute("data-status-filter") === statusName) {
        c.classList.add("ring-2", "ring-cyan-400", "bg-cyan-500/20", "active-filter");
      } else {
        c.classList.remove("ring-2", "ring-cyan-400", "bg-cyan-500/20", "active-filter");
      }
    });
  }

  // Highlight 'Tüm Odalar' tab
  document.querySelectorAll(".room-tab").forEach(t => {
    if (t.getAttribute("data-room") === "ALL") {
      t.classList.remove("bg-slate-800", "text-slate-300");
      t.classList.add("bg-cyan-500", "text-white", "active");
    } else {
      t.classList.remove("bg-cyan-500", "text-white", "active");
      t.classList.add("bg-slate-800", "text-slate-300");
    }
  });
  activeRoom = "ALL";

  showGridView();
  renderGrid();
};

window.clearStatusFilter = function() {
  activeStatusFilter = "ALL";
  document.querySelectorAll(".stat-filter-card").forEach(c => {
    c.classList.remove("ring-2", "ring-cyan-400", "bg-cyan-500/20", "active-filter");
  });
  showGridView();
  renderGrid();
};

async function fetchComputers() {
  try {
    const res = await fetch('/api/computers');
    if (res.ok) {
      const data = await res.json();
      pcs = Array.isArray(data) ? data : (data.computers || []);
      renderAll();
    }
  } catch (err) {
    console.error("fetchComputers error:", err);
  }
}


/**
 * Radiology PC Tracker v1 - Frontend Real-Time WebSocket & Telegram Mini App Client
 */



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
  let active = 0, idle = 0, probablyIdle = 0, lunch = 0, offline = 0, suspicious = 0;
  pcs.forEach(p => {
    const st = p.status || 'offline';
    if (st === 'active') active++;
    else if (st === 'idle') idle++;
    else if (st === 'probably-idle') probablyIdle++;
    else if (st === 'lunch-break') lunch++;
    else if (st === 'suspicious') suspicious++;
    else offline++;
  });

  if (document.getElementById("stat-active")) document.getElementById("stat-active").innerText = active;
  if (document.getElementById("stat-idle")) document.getElementById("stat-idle").innerText = idle;
  if (document.getElementById("stat-probably-idle")) document.getElementById("stat-probably-idle").innerText = probablyIdle;
  if (document.getElementById("stat-lunch")) document.getElementById("stat-lunch").innerText = lunch;
  if (document.getElementById("stat-offline")) document.getElementById("stat-offline").innerText = offline;
  if (document.getElementById("stat-suspicious")) document.getElementById("stat-suspicious").innerText = suspicious;
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
    // 1. Room Filter
    let matchRoom = false;
    if (activeRoom === 'ALL' || activeRoom === 'KROKI') {
      matchRoom = true;
    } else if (activeRoom === 'GENEL_PACS') {
      matchRoom = p.room && (p.room.startsWith('Genel PACS') || p.room === 'Toplantı Odası');
    } else {
      matchRoom = (p.room === activeRoom);
    }

    // 2. Status Filter
    let matchStatus = true;
    if (activeStatusFilter === 'idle') {
      matchStatus = (p.status === 'idle');
    } else if (activeStatusFilter === 'probably-idle') {
      matchStatus = (p.status === 'probably-idle');
    } else if (activeStatusFilter !== 'ALL') {
      matchStatus = (p.status === activeStatusFilter);
    }

    // 3. Search Query Filter
    const q = searchQuery.toLowerCase().trim();
    const matchQuery = !q || 
      (p.friendlyName && p.friendlyName.toLowerCase().includes(q)) ||
      (p.hostname && p.hostname.toLowerCase().includes(q)) ||
      (p.username && p.username.toLowerCase().includes(q)) ||
      (p.ip && p.ip.includes(q)) ||
      (p.room && p.room.toLowerCase().includes(q));

    return matchRoom && matchStatus && matchQuery;
  });

  if (filtered.length === 0) {
    let filterMsg = "Aramaya uygun bilgisayar bulunamadı.";
    if (activeStatusFilter !== "ALL") {
      const filterNames = {
        'idle': 'Boşta (45+ dk)',
        'probably-idle': 'Muhtemelen Boş (30-45 dk)',
        'active': 'Dolu (Aktif)',
        'lunch-break': 'Öğle Arası',
        'offline': 'Çevrimdışı / Kapalı',
        'suspicious': 'Şüpheli Aktivite'
      };
      filterMsg = `Şu anda "<b>${filterNames[activeStatusFilter] || activeStatusFilter}</b>" durumunda bilgisayar bulunmuyor.`;
    }

    grid.innerHTML = `
      <div class="col-span-full py-10 text-center text-slate-400 glass-card rounded-2xl border border-slate-800 p-6 max-w-md mx-auto">
        <p class="text-3xl mb-2">🔍</p>
        <p class="text-sm font-medium text-slate-300 mb-3">${filterMsg}</p>
        <button onclick="clearStatusFilter()" class="px-4 py-2 text-xs font-bold rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 text-white shadow-lg hover:opacity-90 transition-all">
          ✨ Filtreyi Temizle (Tümünü Göster)
        </button>
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
async function openModal(pc) {
  selectedPc = pc;
  if (tgApp?.HapticFeedback) {
    tgApp.HapticFeedback.impactOccurred('light');
  }

  const titleEl = document.getElementById("modal-title-text");
  if (titleEl) titleEl.innerText = pc.friendlyName || pc.hostname;

  const rName = pc.room || "Genel";
  const roomEl = document.getElementById("modal-room-text");
  if (roomEl) roomEl.innerText = rName.toLowerCase().endsWith("odası") ? rName : `${rName} Odası`;

  const userEl = document.getElementById("modal-user");
  if (userEl) userEl.innerText = pc.username && pc.username !== 'unknown' ? pc.username : 'Belirtilmedi';

  const hostEl = document.getElementById("modal-hostname");
  if (hostEl) hostEl.innerText = pc.hostname || 'Bilinmiyor';

  const ipEl = document.getElementById("modal-ip");
  if (ipEl) ipEl.innerText = pc.ip || 'Bilinmiyor';

  const idleEl = document.getElementById("modal-idle");
  if (idleEl) {
    if (pc.status === 'offline') {
      idleEl.innerText = "Kapalı";
      idleEl.className = "text-sm font-black text-slate-500 block";
    } else if (pc.status === 'active') {
      idleEl.innerText = "Kullanımda (0 dk)";
      idleEl.className = "text-sm font-black text-rose-400 block";
    } else if (pc.status === 'probably-idle') {
      const min = Math.floor((pc.idleTimeSeconds || 0) / 60);
      idleEl.innerText = `${min} Dk Boşta`;
      idleEl.className = "text-sm font-black text-amber-400 block";
    } else {
      const min = Math.floor((pc.idleTimeSeconds || 0) / 60);
      idleEl.innerText = `${min > 0 ? min + ' Dakika' : (pc.idleTimeSeconds||0) + ' Saniye'}`;
      idleEl.className = "text-sm font-black text-emerald-400 block";
    }
  }

  const lastSeenEl = document.getElementById("modal-lastseen");
  if (lastSeenEl) lastSeenEl.innerText = formatLastSeen(pc.lastSeen);

  // Status Badge UI
  const badgeEl = document.getElementById("modal-status-badge");
  const badgeText = document.getElementById("modal-status-text");
  const badgeDot = document.getElementById("modal-status-dot");
  const subscribeBtn = document.getElementById("modal-subscribe-btn");

  if (pc.status === 'idle') {
    if (badgeEl) badgeEl.className = "inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-black tracking-wide bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-lg shadow-emerald-500/20";
    if (badgeText) badgeText.innerText = "🟢 BOŞTA (KULLANILABİLİR)";
    if (badgeDot) badgeDot.className = "w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse";
    if (subscribeBtn) subscribeBtn.classList.add("hidden");
  } else if (pc.status === 'probably-idle') {
    if (badgeEl) badgeEl.className = "inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-black tracking-wide bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-lg shadow-amber-500/20";
    if (badgeText) badgeText.innerText = "🟡 MUHTEMELEN BOŞ (30+ dk)";
    if (badgeDot) badgeDot.className = "w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse";
    if (subscribeBtn) subscribeBtn.classList.add("hidden");
  } else if (pc.status === 'active') {
    if (badgeEl) badgeEl.className = "inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-black tracking-wide bg-rose-500/20 text-rose-300 border border-rose-500/40 shadow-lg shadow-rose-500/20";
    if (badgeText) badgeText.innerText = "🔴 DOLU (AKTİF KULLANIMDA)";
    if (badgeDot) badgeDot.className = "w-2.5 h-2.5 rounded-full bg-rose-500";
    if (subscribeBtn) subscribeBtn.classList.remove("hidden");
  } else if (pc.status === 'lunch-break') {
    if (badgeEl) badgeEl.className = "inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-black tracking-wide bg-orange-500/20 text-orange-300 border border-orange-500/40";
    if (badgeText) badgeText.innerText = "🍱 ÖĞLE ARASI";
    if (badgeDot) badgeDot.className = "w-2.5 h-2.5 rounded-full bg-orange-400";
    if (subscribeBtn) subscribeBtn.classList.remove("hidden");
  } else {
    if (badgeEl) badgeEl.className = "inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-bold tracking-wide bg-slate-800 text-slate-400 border border-slate-700";
    if (badgeText) badgeText.innerText = "⚪ ÇEVRİMDIŞI / KAPALI";
    if (badgeDot) badgeDot.className = "w-2.5 h-2.5 rounded-full bg-slate-500";
    if (subscribeBtn) subscribeBtn.classList.add("hidden");
  }

  // Load Threaded Notes for this PC
  await loadPcNotes(pc.id);

  document.getElementById("detail-modal").classList.remove("hidden");
  document.getElementById("detail-modal").classList.add("flex");
}

async function loadPcNotes(pcId) {
  const feed = document.getElementById("modal-notes-feed");
  const countEl = document.getElementById("modal-notes-count");
  if (!feed) return;

  const myEmail = (localStorage.getItem("radtracker_email") || "").toLowerCase().trim();

  try {
    const res = await fetch(`/api/pc/notes/${encodeURIComponent(pcId)}`);
    const data = await res.json();
    const messages = data.messages || [];

    if (countEl) countEl.innerText = `${messages.length} not`;

    if (messages.length === 0) {
      feed.innerHTML = '<div class="p-3 text-center text-xs text-slate-500 bg-slate-800/30 rounded-xl">Bu masada henüz not bırakılmamış.</div>';
      return;
    }

    feed.innerHTML = "";
    messages.forEach(msg => {
      const isMine = myEmail && msg.author_email && (msg.author_email.toLowerCase() === myEmail);
      const row = document.createElement("div");
      row.className = "p-2.5 rounded-2xl bg-slate-800/80 border border-slate-700/60 flex items-start justify-between gap-2 transition-all";
      
      row.innerHTML = `
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-1.5 mb-0.5">
            <span class="text-[11px] font-bold ${isMine ? 'text-cyan-300' : 'text-amber-300'} truncate">${msg.author_name || msg.author_email}</span>
            <span class="text-[9px] text-slate-500 font-mono">${formatMessageTime(msg.timestamp) || msg.time_str || ''}</span>
          </div>
          <p class="text-xs text-slate-200 break-words leading-relaxed">${msg.text}</p>
        </div>
        ${isMine ? `
          <button onclick="deletePcNote('${pcId}', '${msg.id}')" class="text-slate-500 hover:text-rose-400 text-xs p-1 rounded-lg hover:bg-slate-700/50 transition-colors" title="Kendi notunu sil">
            🗑️
          </button>
        ` : ''}
      `;
      feed.appendChild(row);
    });

    // Scroll to bottom
    feed.scrollTop = feed.scrollHeight;
  } catch (e) {
    feed.innerHTML = '<div class="p-2 text-center text-xs text-red-400">Notlar yüklenemedi.</div>';
  }
}

async function sendPcNote() {
  if (!selectedPc) return;
  const input = document.getElementById("modal-new-note-text");
  const text = input ? input.value.trim() : "";
  if (!text) return;

  const email = (localStorage.getItem("radtracker_email") || "hekim@hastane.com").toLowerCase().trim();
  let authorName = localStorage.getItem("radtracker_doctor_name");
  if (!authorName) {
    authorName = "Dr. " + email.split("@")[0].charAt(0).toUpperCase() + email.split("@")[0].slice(1);
  }
  const btn = document.getElementById("modal-send-note-btn");
  if (btn) btn.disabled = true;

  try {
    const resp = await fetch("/api/pc/notes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pc_id: selectedPc.id,
        notes: text,
        author: email,
        author_name: authorName,
        friendly_name: selectedPc.friendlyName || selectedPc.hostname
      })
    });
    const data = await resp.json();
    if (data.success) {
      if (input) input.value = "";
      await loadPcNotes(selectedPc.id);
      if (typeof showToast === 'function') showToast("📝 Not masaya eklendi!");
    }
  } catch (e) {
    alert("Not gönderilemedi.");
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function deletePcNote(pcId, msgId) {
  const email = localStorage.getItem("radtracker_email") || "";
  try {
    const res = await fetch(`/api/pc/notes/${encodeURIComponent(pcId)}/${encodeURIComponent(msgId)}?email=${encodeURIComponent(email)}`, {
      method: "DELETE"
    });
    const data = await res.json();
    if (data.success) {
      await loadPcNotes(pcId);
      if (typeof showToast === 'function') showToast("🗑️ Not silindi.");
    } else {
      alert(data.detail || "Not silinemedi.");
    }
  } catch (e) {
    alert("Not silinirken hata oluştu.");
  }
}


function closeModal() {
  document.getElementById("detail-modal").classList.add("hidden");
  document.getElementById("detail-modal").classList.remove("flex");
}

const KROKI_MAP = {
  'ws-noroloji-01': 'Nöroloji PACS Oda 1 PC 1',
  'ws-noroloji-02': 'Nöroloji PACS Oda 1 PC 2',
  'ws-noroloji-03': 'Nöroloji PACS Oda 1 PC 3',
  'noroloji-pacs-01-uuid-0001': 'Nöroloji PACS Oda 1 PC 1',
  'noroloji-pacs-01-uuid-0002': 'Nöroloji PACS Oda 1 PC 2',
  'noroloji-pacs-01-uuid-0003': 'Nöroloji PACS Oda 1 PC 3',

  'KD-PACS-01': 'Kadın Doğum PACS Oda 1 PC 1',
  'KD-PACS-02': 'Kadın Doğum PACS Oda 1 PC 2',
  'KD-PACS-03': 'Kadın Doğum PACS Oda 1 PC 3',
  'Cassiopeia-β': 'KVC PACS Oda 1 PC 1',
  'Cassiopeia-α': 'KVC PACS Oda 1 PC 2',
  'Aquila-α': 'Kadın Doğum Toplantı Odası PC 1',
  'Perseus-β': 'Toplantı Odası PC 1',
  'Perseus-α': 'Toplantı Odası PC 2',
  'Perseus-γ': 'Toplantı Odası PC 3',
  'ws-pe-01': 'Toplantı Odası PC 1',
  'ws-pe-02': 'Toplantı Odası PC 2',
  'ws-pe-03': 'Toplantı Odası PC 3',
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
  'e092e2c2-5348-4724-9a00-5d37a4486176': 'Genel PACS Oda 5 PC 1',
  'ws-onkoloji-01': 'Onkoloji PACS Oda 1 PC 1',
  'ws-ftr-01': 'FTR PACS Oda 1 PC 1',
};

function updateKrokiColors() {
  Object.keys(KROKI_MAP).forEach(wsId => {
    const el = document.getElementById(wsId);
    if (!el) return;

    const friendly = KROKI_MAP[wsId];
    const pc = pcs.find(p => p.friendlyName === friendly || p.hostname === friendly || p.id === wsId);
    const st = (pc && pc.status) ? pc.status : 'offline';

    el.classList.remove('ws-idle', 'ws-probably-idle', 'ws-active', 'ws-lunch-break', 'ws-offline');

    // Handle large detailed desk cards (KVC, Nöroloji, Kadın Doğum, Onkoloji, FTR)
    const innerBadge = el.querySelector('[class*="ws-badge"]') || el.querySelector('.w-14') || el.querySelector('.w-12');
    const statusSpan = el.querySelector('span:last-child');

    if (st === 'idle') {
      el.classList.add('ws-idle');
      if (innerBadge) {
        innerBadge.className = "w-14 h-14 text-xl font-black flex items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-400 to-green-600 text-white shadow-lg shadow-emerald-500/50 border border-emerald-300 pointer-events-none";
      }
      if (statusSpan && statusSpan.parentElement && statusSpan.parentElement !== el) {
        statusSpan.className = "text-[10px] text-emerald-400 font-bold block";
        statusSpan.innerText = `${friendly} • 🟢 Boşta`;
      }
    } else if (st === 'probably-idle') {
      el.classList.add('ws-probably-idle');
      if (innerBadge) {
        innerBadge.className = "w-14 h-14 text-xl font-black flex items-center justify-center rounded-2xl bg-gradient-to-br from-amber-400 to-yellow-500 text-slate-950 shadow-lg shadow-amber-400/50 border border-amber-300 pointer-events-none";
      }
      if (statusSpan && statusSpan.parentElement && statusSpan.parentElement !== el) {
        statusSpan.className = "text-[10px] text-amber-400 font-bold block";
        statusSpan.innerText = `${friendly} • 🟡 Muhtemelen Boş`;
      }
    } else if (st === 'active') {
      el.classList.add('ws-active');
      if (innerBadge) {
        innerBadge.className = "w-14 h-14 text-xl font-black flex items-center justify-center rounded-2xl bg-gradient-to-br from-red-500 to-rose-600 text-white shadow-lg shadow-red-500/50 border border-red-400 pointer-events-none";
      }
      if (statusSpan && statusSpan.parentElement && statusSpan.parentElement !== el) {
        statusSpan.className = "text-[10px] text-red-400 font-bold block";
        statusSpan.innerText = `${friendly} • 🔴 Dolu (Aktif)`;
      }
    } else if (st === 'lunch-break') {
      el.classList.add('ws-lunch-break');
      if (innerBadge) {
        innerBadge.className = "w-14 h-14 text-xl font-black flex items-center justify-center rounded-2xl bg-gradient-to-br from-orange-400 to-amber-600 text-white shadow-lg shadow-orange-500/50 border border-orange-300 pointer-events-none";
      }
      if (statusSpan && statusSpan.parentElement && statusSpan.parentElement !== el) {
        statusSpan.className = "text-[10px] text-orange-400 font-bold block";
        statusSpan.innerText = `${friendly} • 🍱 Öğle Arası`;
      }
    } else {
      // OFFLINE / SİNYAL YOK
      el.classList.add('ws-offline');
      if (innerBadge) {
        innerBadge.className = "w-14 h-14 text-xl font-bold flex items-center justify-center rounded-2xl bg-slate-800/90 text-slate-500 border border-slate-700/80 shadow-none pointer-events-none";
      }
      if (statusSpan && statusSpan.parentElement && statusSpan.parentElement !== el) {
        statusSpan.className = "text-[10px] text-slate-500 font-medium block";
        statusSpan.innerText = `${friendly} • ⚪ Çevrimdışı`;
      }
    }

    el.onclick = (e) => {
      e.stopPropagation();
      if (pc) {
        openModal(pc);
      } else {
        openModal({
          id: wsId,
          friendlyName: friendly || wsId,
          hostname: wsId,
          room: 'Radyoloji PACS',
          status: 'offline',
          username: 'Bilinmiyor',
          ip: '-',
          idleTimeSeconds: 0,
          lastSeen: 0
        });
      }
    };
  });
}

let activeKrokiRoom = "ALL";

function switchKrokiLayout(layoutId) {
  if (!layoutId) layoutId = 'kroki-pacs-raporlama';
  
  // Highlight active layout button
  document.querySelectorAll(".kroki-layout-btn").forEach(btn => {
    if (btn.getAttribute("data-layout") === layoutId) {
      btn.className = "kroki-layout-btn active px-4 py-2 rounded-xl font-black bg-cyan-500 text-white shadow-lg shadow-cyan-500/30 transition-all border border-cyan-300 scale-105";
    } else {
      btn.className = "kroki-layout-btn px-3.5 py-2 rounded-xl font-bold bg-slate-800/90 text-slate-300 hover:bg-slate-700 transition-all border border-slate-700";
    }
  });

  // Toggle layout visibility
  document.querySelectorAll(".kroki-view-wrapper").forEach(wrapper => {
    if (wrapper.id === layoutId) {
      wrapper.classList.remove("hidden");
      wrapper.style.display = "block";
    } else {
      wrapper.classList.add("hidden");
      wrapper.style.display = "none";
    }
  });

  // Toggle zoom controls (only needed for main large floor plan)
  const zoomControls = document.getElementById("kroki-zoom-controls");
  if (zoomControls) {
    zoomControls.style.display = (layoutId === 'kroki-pacs-raporlama') ? 'flex' : 'none';
  }

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

  if (name.includes("nöroloji") || room.includes("nöroloji")) {
    targetLayout = "kroki-noroloji";
  } else if (name.includes("kvc") || room.includes("kvc")) {
    targetLayout = "kroki-cassiopeia";
  } else if (name.includes("kadın doğum toplantı") || (room.includes("kadın doğum") && room.includes("toplantı"))) {
    targetLayout = "kroki-kadin-dogum";
  } else if (name.includes("kadın doğum") || room.includes("kadın doğum")) {
    targetLayout = "kroki-kadin-dogum-pacs";
  } else if (name.includes("onkoloji") || room.includes("onkoloji")) {
    targetLayout = "kroki-onkoloji";
  } else if (name.includes("ftr") || room.includes("ftr")) {
    targetLayout = "kroki-ftr";
  } else {
    targetLayout = "kroki-pacs-raporlama";
  }

  switchKrokiLayout(targetLayout);

  // Clear previous highlights & pins & room glows
  document.querySelectorAll('.ws-aktif').forEach(el => el.classList.remove('ws-aktif'));
  document.querySelectorAll('.room-active-glow').forEach(el => el.classList.remove('room-active-glow'));
  document.querySelectorAll('.pc-pin-callout').forEach(el => el.remove());

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

  // 4. Show Notification Banner at Top
  const banner = document.getElementById("kroki-location-banner");
  const bannerText = document.getElementById("kroki-banner-text");
  if (banner && bannerText) {
    bannerText.innerText = `${pc.friendlyName || pc.hostname} (${pc.room || 'Genel'}) krokide işaretlendi!`;
    banner.classList.remove("hidden");
  }

  if (wsEl) {
    // A. Add active sonar class
    wsEl.classList.add('ws-aktif');

    // B. Glow the parent room container if available
    const parentRoom = wsEl.closest('.floor-room') || wsEl.closest('.glass-card');
    if (parentRoom) {
      parentRoom.classList.add('room-active-glow');
    }

    // C. Attach Floating 3D Animated Pin Callout directly on the desk
    const pinEl = document.createElement('div');
    pinEl.className = 'pc-pin-callout';
    pinEl.innerHTML = `
      <div class="pc-pin-badge">
        <span>📍</span>
        <span>${pc.friendlyName || pc.hostname}</span>
      </div>
      <div class="pc-pin-arrow"></div>
    `;
    wsEl.appendChild(pinEl);

    // D. Precise Multi-Axis Center Scrolling (handles mobile & overflow)
    setTimeout(() => {
      wsEl.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
      
      // Also scroll parent horizontal containers
      const scrollContainers = document.querySelectorAll('.overflow-x-auto, #kroki-container');
      scrollContainers.forEach(container => {
        if (container.contains(wsEl)) {
          const wsRect = wsEl.getBoundingClientRect();
          const contRect = container.getBoundingClientRect();
          const offsetLeft = wsEl.offsetLeft - (container.clientWidth / 2) + (wsEl.clientWidth / 2);
          container.scrollTo({ left: offsetLeft, behavior: 'smooth' });
        }
      });
    }, 100);

    // Haptic feedback on Telegram if available
    if (tgApp?.HapticFeedback) {
      tgApp.HapticFeedback.notificationOccurred('success');
    }
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

function getRadCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return decodeURIComponent(parts.pop().split(';').shift());
  return null;
}

function persistAuthSession(token, email, doctorName) {
  if (!token || !email) return;
  try {
    localStorage.setItem("radtracker_token", token);
    localStorage.setItem("radtracker_email", email);
    if (doctorName) localStorage.setItem("radtracker_doctor_name", doctorName);
    
    sessionStorage.setItem("radtracker_token", token);
    sessionStorage.setItem("radtracker_email", email);
    if (doctorName) sessionStorage.setItem("radtracker_doctor_name", doctorName);
  } catch (e) {
    console.warn("Storage write error:", e);
  }

  // 30 Days Persistent Cookie (2592000 seconds)
  const maxAge = 30 * 24 * 60 * 60;
  document.cookie = `radtracker_token=${encodeURIComponent(token)}; max-age=${maxAge}; path=/; SameSite=Lax`;
  document.cookie = `radtracker_email=${encodeURIComponent(email)}; max-age=${maxAge}; path=/; SameSite=Lax`;
  if (doctorName) {
    document.cookie = `radtracker_doctor_name=${encodeURIComponent(doctorName)}; max-age=${maxAge}; path=/; SameSite=Lax`;
  }
}

function clearAuthSession() {
  try {
    clearAuthSession();
    localStorage.removeItem("radtracker_doctor_name");
    sessionStorage.clear();
  } catch (e) {}
  document.cookie = "radtracker_token=; max-age=0; path=/;";
  document.cookie = "radtracker_email=; max-age=0; path=/;";
  document.cookie = "radtracker_doctor_name=; max-age=0; path=/;";
}


function checkAuthStatus() {
  let token = localStorage.getItem("radtracker_token") || sessionStorage.getItem("radtracker_token") || getRadCookie("radtracker_token");
  let email = localStorage.getItem("radtracker_email") || sessionStorage.getItem("radtracker_email") || getRadCookie("radtracker_email");
  let doctorName = localStorage.getItem("radtracker_doctor_name") || sessionStorage.getItem("radtracker_doctor_name") || getRadCookie("radtracker_doctor_name");

  const mainContent = document.getElementById("main-content");
  const authContainer = document.getElementById("auth-container");
  const authBtn = document.getElementById("auth-btn");
  const userBanner = document.getElementById("user-banner");

  if (token && email) {
    // Re-persist to all storage layers so session never drops
    persistAuthSession(token, email, doctorName);

    if (userBanner) userBanner.classList.remove("hidden");
    
    const displayName = doctorName || ("Dr. " + email.split('@')[0].charAt(0).toUpperCase() + email.split('@')[0].slice(1));
    
    if (document.getElementById("user-email-label")) {
      document.getElementById("user-email-label").innerText = `👨‍⚕️ ${displayName} (${email})`;
    }
    if (document.getElementById("auth-btn-label")) {
      document.getElementById("auth-btn-label").innerText = displayName;
    }
    if (authBtn) authBtn.classList.remove("hidden");
    if (mainContent) mainContent.classList.remove("hidden");
    if (authContainer) authContainer.classList.add("hidden");
    
    return true;
  } else {
    if (userBanner) userBanner.classList.add("hidden");
    if (authBtn) authBtn.classList.add("hidden");
    if (mainContent) mainContent.classList.add("hidden");
    if (authContainer) authContainer.classList.remove("hidden");
    
    return false;
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
  fetchComputers();
  // Stat filters handled exclusively by window.filterByStatus

  connectWebSocket();
  checkAuthStatus();

  // View mode switcher (Kart vs Kroki Planı)
  document.getElementById("view-card-btn")?.addEventListener("click", () => {
    showGridView();
    document.getElementById("view-card-btn").className = "px-3 py-2 text-xs font-bold rounded-xl bg-cyan-500 text-white shadow transition-all";
    document.getElementById("view-kroki-btn").className = "px-3 py-2 text-xs font-bold rounded-xl bg-slate-800 text-slate-300 hover:bg-slate-700 transition-all border border-slate-700";
  });

  document.getElementById("view-kroki-btn")?.addEventListener("click", () => {
    showKrokiView();
    document.getElementById("view-kroki-btn").className = "px-3 py-2 text-xs font-bold rounded-xl bg-cyan-500 text-white shadow transition-all";
    document.getElementById("view-card-btn").className = "px-3 py-2 text-xs font-bold rounded-xl bg-slate-800 text-slate-300 hover:bg-slate-700 transition-all border border-slate-700";
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
    if (searchQuery.trim().length > 0) {
      document.getElementById("kroki-container")?.classList.add("hidden");
      document.getElementById("pc-grid-container")?.classList.remove("hidden");
    }
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
      
      // Reset status filter when switching room tabs
      activeStatusFilter = "ALL";
      document.querySelectorAll(".stat-filter-card").forEach(c => {
        c.classList.remove("ring-2", "ring-cyan-400", "bg-cyan-500/20", "active-filter");
      });

      if (targetRoom === "ALL") {
        activeRoom = "ALL";
        showGridView();
        renderGrid();
      } else if (targetRoom === "KROKI" || targetRoom === "GENEL_PACS") {
        activeRoom = "GENEL_PACS";
        showKrokiView('kroki-pacs-raporlama');
      } else if (ROOM_TO_KROKI_LAYOUT[targetRoom]) {
        activeRoom = targetRoom;
        showKrokiView(ROOM_TO_KROKI_LAYOUT[targetRoom]);
      } else {
        activeRoom = targetRoom;
        showGridView();
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
    clearAuthSession();
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
    const nameInput = document.getElementById("auth-name");
    const doctorName = nameInput && nameInput.value.trim() ? nameInput.value.trim() : "";
    if (doctorName) {
      localStorage.setItem("radtracker_doctor_name", doctorName);
    }
    const tgData = getTgUserData();
    const errBox = document.getElementById("auth-error");
    if (errBox) errBox.classList.add("hidden");

    if (!email) return;

    const btn = document.getElementById("btn-send-code");
    if (btn) {
      btn.disabled = true;
      btn.innerText = "⏳ E-Posta Gönderiliyor...";
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
        if (subtitle) subtitle.innerText = `${email} adresine 6 haneli güvenlik kodu ve giriş bağlantısı gönderildi.`;
        
        const authInput = document.getElementById("auth-code");
        if (authInput) {
          authInput.value = ""; // Clean input waiting for user's real email code
          authInput.focus();
        }
      } else {
        showAuthError(data.detail || "Kod gönderilemedi.");
      }
    } catch (err) {
      showAuthError("Bağlantı hatası oluştu. Lütfen tekrar deneyin.");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerText = "🔑 E-Postama Giriş Bağlantısı & Kod Gönder";
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
        const docName = localStorage.getItem("radtracker_doctor_name") || "";
        persistAuthSession(data.token, data.email, docName);
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
  document.getElementById("modal-send-note-btn")?.addEventListener("click", sendPcNote);
  document.getElementById("modal-new-note-text")?.addEventListener("keydown", (e) => { if (e.key === "Enter") sendPcNote(); });
  // legacy save note
  document.getElementById("modal-save-note-btn")?.addEventListener("click", async () => {
    if (!selectedPc) return;
    const notesInput = document.getElementById("modal-notes-input");
    const notes = notesInput ? notesInput.value : "";
    const email = (localStorage.getItem("radtracker_email") || "hekim@hastane.com").toLowerCase().trim();
  let authorName = localStorage.getItem("radtracker_doctor_name");
  if (!authorName) {
    authorName = "Dr. " + email.split("@")[0].charAt(0).toUpperCase() + email.split("@")[0].slice(1);
  }

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

// ============================================================================
// ============================================================================
// Dynamic Admin Whitelist & Multi-Role Management Functions
// ============================================================================

async function openAdminModal() {
  const modal = document.getElementById("admin-modal");
  if (modal) modal.classList.remove("hidden");
  await loadAdminUsers();
}

function closeAdminModal() {
  const modal = document.getElementById("admin-modal");
  if (modal) modal.classList.add("hidden");
  const msg = document.getElementById("admin-msg");
  if (msg) msg.classList.add("hidden");
}

async function loadAdminUsers() {
  const listEl = document.getElementById("admin-email-list");
  const countEl = document.getElementById("admin-user-count");
  if (!listEl) return;

  listEl.innerHTML = '<div class="p-3 text-center text-xs text-slate-500">Yükleniyor...</div>';

  try {
    const res = await fetch("/api/admin/users");
    const data = await res.json();
    if (data.success && data.user_roles) {
      const users = data.user_roles;
      if (countEl) countEl.innerText = users.length;

      if (users.length === 0) {
        listEl.innerHTML = '<div class="p-3 text-center text-xs text-slate-500">Henüz yetkili hekim eklenmemiş.</div>';
        return;
      }

      listEl.innerHTML = "";
      users.forEach(u => {
        const isAdmin = u.role === "admin";
        const row = document.createElement("div");
        row.className = "flex items-center justify-between p-3 rounded-xl bg-slate-800/80 border border-slate-700/60 text-xs gap-2";
        
        row.innerHTML = `
          <div class="flex items-center gap-2 overflow-hidden flex-1 min-w-0">
            <span>${isAdmin ? '👑' : '👨‍⚕️'}</span>
            <span class="font-medium text-slate-200 truncate">${u.email}</span>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full ${isAdmin ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'}">
              ${isAdmin ? 'Yönetici' : 'Hekim'}
            </span>
          </div>

          <div class="flex items-center gap-1.5 flex-shrink-0">
            <button onclick="adminToggleRole('${u.email}', '${isAdmin ? 'doctor' : 'admin'}')" class="px-2 py-1 text-[10px] font-bold rounded-lg ${isAdmin ? 'bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/40 border border-cyan-500/30' : 'bg-amber-500/20 text-amber-300 hover:bg-amber-500/40 border border-amber-500/30'} transition-all">
              ${isAdmin ? '👨‍⚕️ Hekim Yap' : '👑 Yönetici Yap'}
            </button>

            <button onclick="adminRemoveEmail('${u.email}')" class="px-2 py-1 text-[10px] font-bold rounded-lg bg-rose-500/20 hover:bg-rose-500/40 text-rose-300 border border-rose-500/30 transition-all">
              🗑️
            </button>
          </div>
        `;
        listEl.appendChild(row);
      });
    }
  } catch (err) {
    listEl.innerHTML = '<div class="p-3 text-center text-xs text-rose-400">Yetkili listesi yüklenemedi.</div>';
  }
}

async function adminAddEmail() {
  const input = document.getElementById("admin-new-email");
  const roleSelect = document.getElementById("admin-new-role");
  const msg = document.getElementById("admin-msg");
  if (!input) return;

  const email = input.value.trim().toLowerCase();
  const role = roleSelect ? roleSelect.value : "doctor";

  if (!email || !email.includes("@")) {
    if (msg) {
      msg.className = "text-[11px] font-bold text-rose-400";
      msg.innerText = "Geçerli bir e-posta adresi giriniz.";
      msg.classList.remove("hidden");
    }
    return;
  }

  try {
    const res = await fetch("/api/admin/whitelist/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        email: email, 
        role: role, 
        adminEmail: localStorage.getItem("radtracker_email") || "" 
      })
    });
    const data = await res.json();
    if (data.success) {
      input.value = "";
      if (msg) {
        msg.className = "text-[11px] font-bold text-emerald-400";
        msg.innerText = `${email} (${role === 'admin' ? '👑 Yönetici' : '👨‍⚕️ Hekim'}) olarak başarıyla yetkilendirildi!`;
        msg.classList.remove("hidden");
      }
      await loadAdminUsers();
    }
  } catch (err) {
    if (msg) {
      msg.className = "text-[11px] font-bold text-rose-400";
      msg.innerText = "Ekleme sırasında bir hata oluştu.";
      msg.classList.remove("hidden");
    }
  }
}

async function adminToggleRole(email, targetRole) {
  try {
    const res = await fetch("/api/admin/role/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        email: email, 
        role: targetRole, 
        adminEmail: localStorage.getItem("radtracker_email") || "" 
      })
    });
    const data = await res.json();
    if (data.success) {
      await loadAdminUsers();
    }
  } catch (err) {
    alert("Rol güncelleme başarısız oldu.");
  }
}

async function adminRemoveEmail(email) {
  if (!confirm(`${email} kullanıcısının tüm yetkilerini silmek istediğinize emin misiniz?`)) return;

  try {
    const res = await fetch("/api/admin/whitelist/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        email: email, 
        adminEmail: localStorage.getItem("radtracker_email") || "" 
      })
    });
    const data = await res.json();
    if (data.success) {
      await loadAdminUsers();
    }
  } catch (err) {
    alert("Yetki silme başarısız oldu.");
  }
}

// ==========================================================================
// Mobile Kroki Zoom & Touch Drag Engine
// ==========================================================================
let currentKrokiZoom = 0.85;

function setKrokiZoom(scale) {
  currentKrokiZoom = scale;
  const target = document.getElementById('kroki-scale-target');
  if (target) {
    target.style.transform = `scale(${scale})`;
  }
  
  // Update button active state
  document.querySelectorAll('.zoom-btn').forEach(btn => {
    btn.classList.remove('bg-cyan-500', 'text-white', 'shadow');
    btn.classList.add('bg-slate-700', 'text-slate-300');
  });

  const activeBtnId = scale === 0.65 ? 'zoom-btn-65' : (scale === 1.0 ? 'zoom-btn-100' : 'zoom-btn-85');
  const activeBtn = document.getElementById(activeBtnId);
  if (activeBtn) {
    activeBtn.classList.remove('bg-slate-700', 'text-slate-300');
    activeBtn.classList.add('bg-cyan-500', 'text-white', 'shadow');
  }
}

// Auto-detect mobile screen width and set optimal zoom on startup
function autoFitKrokiOnMobile() {
  if (window.innerWidth < 640) {
    setKrokiZoom(0.65);
  } else if (window.innerWidth < 1024) {
    setKrokiZoom(0.85);
  } else {
    setKrokiZoom(1.0);
  }
}

window.addEventListener('resize', () => {
  // Only adjust on initial load or major screen orientation change
});

// Enable Mouse & Touch Drag on Kroki
document.addEventListener('DOMContentLoaded', () => {
  autoFitKrokiOnMobile();
  const slider = document.getElementById('kroki-scroll-area');
  if (!slider) return;

  let isDown = false;
  let startX;
  let scrollLeft;

  slider.addEventListener('mousedown', (e) => {
    isDown = true;
    slider.classList.add('active');
    startX = e.pageX - slider.offsetLeft;
    scrollLeft = slider.scrollLeft;
  });
  slider.addEventListener('mouseleave', () => { isDown = false; });
  slider.addEventListener('mouseup', () => { isDown = false; });
  slider.addEventListener('mousemove', (e) => {
    if (!isDown) return;
    e.preventDefault();
    const x = e.pageX - slider.offsetLeft;
    const walk = (x - startX) * 1.5;
    slider.scrollLeft = scrollLeft - walk;
  });
});
