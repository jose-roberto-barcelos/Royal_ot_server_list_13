console.log("✔ script.js carregado");

// 1) URL raw do CSV no GitHub
const CSV_URL =
  "https://raw.githubusercontent.com/jose-roberto-barcelos/Royal_ot_server_list_13/main/ranking_final.csv";

// Armazena os dados
let serversData = [];

// Carrega e processa o CSV
async function carregarRanking() {
  console.log("▶ iniciar carregarRanking");
  try {
    const res = await fetch(`${CSV_URL}?t=${Date.now()}`, {
      cache: "no-store",
    });
    console.log("Fetch CSV status:", res.status);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const text = await res.text();
    const linhas = text.trim().split("\n");
    console.log("Linhas totais (incluindo cabeçalho):", linhas.length);

    // Timestamp
    if (linhas[0].startsWith("# Gerado em:")) {
      const utc = linhas.shift().replace("# Gerado em:", "").trim();
      console.log("Timestamp UTC original:", utc);
      mostrarTimestamp(utc);
    }

    // Converte em objetos
    serversData = linhas.slice(1).map((line) => {
      const [servidor, jogadores, versao, origem, obs] = line.split(",");
      return { servidor, jogadores, versao, origem, obs };
    });
    console.log("serversData carregado:", serversData.length);

    // Preenche filtros e mostra tabela
    popularFiltroVersao(serversData);
    aplicarFiltros();
  } catch (err) {
    console.error("Erro ao buscar CSV:", err);
  }
}

// Exibe o timestamp já formatado
function mostrarTimestamp(utcString) {
  const dt = new Date(utcString + " UTC");
  const local = dt.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
  console.log("Timestamp local convertido:", local);
  const container = document.querySelector(".table-container");
  container.querySelectorAll(".info-update").forEach((el) => el.remove());
  const div = document.createElement("div");
  div.textContent = `Última coleta: ${local}`;
  div.classList.add("info-update");
  container.prepend(div);
}

// Popula o select de versões
function popularFiltroVersao(data) {
  const sel = document.getElementById("filtro-versao");
  sel.querySelectorAll("option:not(:first-child)").forEach((o) => o.remove());
  const versoes = [
    ...new Set(data.map((s) => s.versao).filter((v) => v)),
  ].sort();
  versoes.forEach((v) => {
    const o = document.createElement("option");
    o.value = v;
    o.textContent = v;
    sel.appendChild(o);
  });
}

// Aplica filtros
function aplicarFiltros() {
  const nomeF = document.getElementById("filtro-nome").value.toLowerCase();
  const verF = document.getElementById("filtro-versao").value;
  const oriF = document.getElementById("filtro-origem").value;

  const filtrados = serversData.filter((s) => {
    return (
      s.servidor.toLowerCase().includes(nomeF) &&
      (!verF || s.versao === verF) &&
      (!oriF || s.origem === oriF)
    );
  });
  renderTable(filtrados);
}

// Renderiza a tabela
function renderTable(data) {
  const tb = document.getElementById("tabela-servidores");
  tb.innerHTML = "";
  data.forEach((s) => {
    const tr = document.createElement("tr");
    [s.servidor, s.versao, s.jogadores, s.origem, s.obs].forEach((txt) => {
      const td = document.createElement("td");
      td.textContent = txt;
      tr.appendChild(td);
    });
    tb.appendChild(tr);
  });
}

// Ordenação ao clicar no header
let currentSort = { col: null, asc: true };
window.ordenarPor = function (column) {
  const mapKey = {
    Servidor: "servidor",
    Versão: "versao",
    "Jogadores Online": "jogadores",
  };
  const key = mapKey[column];
  if (!key) return;
  if (currentSort.col === column) currentSort.asc = !currentSort.asc;
  else {
    currentSort.col = column;
    currentSort.asc = true;
  }
  const sorted = [...serversData].sort((a, b) => {
    let va = key === "jogadores" ? +a[key] : a[key],
      vb = key === "jogadores" ? +b[key] : b[key];
    return currentSort.asc
      ? va > vb
        ? 1
        : va < vb
          ? -1
          : 0
      : va < vb
        ? 1
        : va > vb
          ? -1
          : 0;
  });
  renderTable(sorted);
};

// Liga eventos e inicia tudo
window.addEventListener("DOMContentLoaded", () => {
  document
    .getElementById("filtro-nome")
    .addEventListener("input", aplicarFiltros);
  document
    .getElementById("filtro-versao")
    .addEventListener("change", aplicarFiltros);
  document
    .getElementById("filtro-origem")
    .addEventListener("change", aplicarFiltros);
  carregarRanking();
});
