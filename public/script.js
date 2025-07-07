// script.js
console.log("✔ script.js carregado");

// --- 1) Firebase Auth (ESM) ---
import { initializeApp } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-app.js";
import {
  getAuth,
  onAuthStateChanged,
  signOut
} from "https://www.gstatic.com/firebasejs/9.6.1/firebase-auth.js";

const firebaseConfig = {
  apiKey: "AIzaSyBnzTkzA4KsbvUruYobVEsWFP_upCFGvFM",
  authDomain: "royalotservlist.firebaseapp.com",
  projectId: "royalotservlist",
  storageBucket: "royalotservlist.firebasestorage.app",
  messagingSenderId: "795611612401",
  appId: "1:795611612401:web:3f869dcdff2366a0b45550",
  measurementId: "G-LP54JFLRDT"
};
initializeApp(firebaseConfig);
const auth = getAuth();

// --- 2) Traduções (mantive seu objeto) ---
const translations = { /* ... seu objeto translations sem alterações ... */ };

// --- 3) Funções de tradução estática ---
function applyLanguage(lang) {
  // (você pode remover se não quiser traduzir agora)
}

// --- 4) Ranking e filtros ---
const CSV_URL =
  "https://raw.githubusercontent.com/jose-roberto-barcelos/Royal_ot_server_list_13/main/ranking_final.csv";

let serversData = [];
let lastCount = 0;

async function carregarRanking() {
  console.log("▶ iniciar carregarRanking");
  try {
    const res = await fetch(`${CSV_URL}?t=${Date.now()}`, {
      cache: "no-store"
    });
    console.log("Fetch CSV status:", res.status);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const text = await res.text();
    const lines = text.trim().split("\n");

    // Se tiver timestamp, exibe banner
    if (lines[0].startsWith("# Gerado em:")) {
      const utc = lines.shift().replace("# Gerado em:", "").trim();
      mostrarTimestamp(utc);
    }

    // Converte em objetos
    serversData = lines.slice(1).map(line => {
      const [srv, jog, ver, ori, obs] = line.split(",");
      return {
        servidor: srv,
        jogadores: parseInt(jog) || 0,
        versao: ver,
        origem: ori,
        obs: obs
      };
    });

    // Conta o primeiro socket confiável
    const first = serversData.find(s => s.origem === "Socket");
    lastCount = first ? first.jogadores : 0;

    popularFiltroVersao();
    aplicarFiltros();
  } catch (err) {
    console.error("Erro ao buscar CSV:", err);
  }
}

function mostrarTimestamp(utcString) {
  const dt = new Date(`${utcString} UTC`);
  const local = dt.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });

  // Atualiza o banner
  const bannerEl = document.querySelector(".texto-tibia-oficial");
  if (bannerEl) {
    bannerEl.textContent = `Tibia Oficial: ${lastCount} jogadores online`;
  }

  // Exibe última coleta
  const container = document.querySelector(".table-container");
  if (container) {
    container.querySelectorAll(".info-update").forEach(el => el.remove());
    const div = document.createElement("div");
    div.textContent = `Última coleta: ${local}`;
    div.classList.add("info-update");
    container.prepend(div);
  }
}

function popularFiltroVersao() {
  const sel = document.getElementById("filtro-versao");
  if (!sel) return;
  // Limpa opções antigas
  Array.from(sel.options)
    .slice(1)
    .forEach(opt => opt.remove());
  // Adiciona únicas
  const versoes = [
    ...new Set(serversData.map(s => s.versao).filter(v => v))
  ].sort();
  versoes.forEach(v => {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = v;
    sel.appendChild(opt);
  });
}

function aplicarFiltros() {
  const nomeF = document
    .getElementById("filtro-nome")
    .value.toLowerCase();
  const verF = document.getElementById("filtro-versao").value;
  const oriF = document.getElementById("filtro-origem").value;
  const tbody = document.getElementById("tabela-servidores");
  if (!tbody) return;

  tbody.innerHTML = "";
  serversData
    .filter(s =>
      s.servidor.toLowerCase().includes(nomeF) &&
      (!verF || s.versao === verF) &&
      (!oriF || s.origem === oriF)
    )
    .forEach(s => {
      const tr = document.createElement("tr");
      [s.servidor, s.versao, s.jogadores, s.origem, s.obs].forEach(txt => {
        const td = document.createElement("td");
        td.textContent = txt;
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
}

// Ordenação
let currentSort = { col: null, asc: true };
window.ordenarPor = column => {
  const mapKey = {
    Servidor: "servidor",
    Versão: "versao",
    "Jogadores Online": "jogadores"
  };
  const key = mapKey[column];
  if (!key) return;

  currentSort.asc = currentSort.col === column ? !currentSort.asc : true;
  currentSort.col = column;

  serversData.sort((a, b) => {
    const va =
      typeof a[key] === "number" ? a[key] : String(a[key]).toLowerCase();
    const vb =
      typeof b[key] === "number" ? b[key] : String(b[key]).toLowerCase();
    if (va < vb) return currentSort.asc ? -1 : 1;
    if (va > vb) return currentSort.asc ? 1 : -1;
    return 0;
  });

  aplicarFiltros();
};

// 5) Inicialização
window.addEventListener("DOMContentLoaded", () => {
  // Auth buttons
  onAuthStateChanged(auth, user => {
    const btn = document.querySelector(".login-btn");
    const ic = btn && btn.querySelector("img");
    const rb = document.querySelector(".registrar-btn");
    if (user) {
      if (ic) { ic.src = "./icon-sair.png"; ic.alt = "Sair"; }
      if (btn) btn.onclick = () => signOut(auth).then(() => location.reload());
      if (rb) rb.onclick = () => (location.href = "register.html?aba=servidor");
    } else {
      if (ic) { ic.src = "./icon-login.png"; ic.alt = "Login"; }
      if (btn) btn.onclick = () => (location.href = "login.html");
      if (rb) rb.onclick = () => (location.href = "register.html");
    }
  });

  // Filtros
  const nomeInput = document.getElementById("filtro-nome");
  const verSelect = document.getElementById("filtro-versao");
  const oriSelect = document.getElementById("filtro-origem");
  if (nomeInput) nomeInput.addEventListener("input", aplicarFiltros);
  if (verSelect) verSelect.addEventListener("change", aplicarFiltros);
  if (oriSelect) oriSelect.addEventListener("change", aplicarFiltros);

  // Carrega ranking
  carregarRanking();
});

// === RADIO PLAYER CUSTOM ===
window.addEventListener("DOMContentLoaded", () => {
  const playlist = [
    "assets/music/track1.mp3",
    "assets/music/track2.mp3",
    "assets/music/track3.mp3"
  ];
  let currentTrack = 0;

  const audio  = document.getElementById("radio-audio");
  const playBtn= document.getElementById("btn-playpause");
  const skipBtn= document.getElementById("btn-skip");
  const slider = document.getElementById("slider-volume");

  // se não encontrou algum elemento, aborta sem quebrar nada
  if (!audio || !playBtn || !skipBtn || !slider) return;

  // carrega a primeira faixa
  audio.src = playlist[currentTrack];

  audio.addEventListener("error", e =>
    console.error("Erro carregando áudio:", e)
  );
  audio.addEventListener("ended", () => {
    playBtn.textContent = "►";
  });

  // play / pause
  playBtn.addEventListener("click", () => {
    if (audio.paused) {
      audio.play().catch(err => console.error("play() falhou:", err));
      playBtn.textContent = "❚❚";
    } else {
      audio.pause();
      playBtn.textContent = "►";
    }
  });

  // pular faixa
  skipBtn.addEventListener("click", () => {
    currentTrack = (currentTrack + 1) % playlist.length;
    audio.src = playlist[currentTrack];
    audio.play().catch(err => console.error("play() falhou:", err));
    playBtn.textContent = "❚❚";
  });

  // volume
  slider.addEventListener("input", () => {
    audio.volume = Number(slider.value);
  });
});
// aplica fade-in staggered nos cards assim que a página carrega
window.addEventListener('DOMContentLoaded', () => {
  const cards = document.querySelectorAll('.streamer-card, .youtuber-card');
  cards.forEach((card, i) => {
    setTimeout(() => {
      card.classList.add('visible');
    }, i * 150); // cada card aparece 150 ms depois do anterior
  });
});

