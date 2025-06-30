// public/script.js

async function fetchRanking() {
  try {
    const res = await fetch("/getRanking"); // GET no mesmo domínio
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const servers = await res.json();
    preencherTabela(servers);
  } catch (err) {
    console.error("Erro ao buscar /getRanking:", err);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  fetchRanking();
  // Se quiser atualizar periodicamente na página:
  // setInterval(fetchRanking, 5 * 60 * 1000);
});

function preencherTabela(servers) {
  const tbody = document.getElementById("tabela-servidores");
  tbody.innerHTML = "";
  servers.forEach((s) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${s.nome}</td>
      <td>${s.versao}</td>
      <td>${s.jogadores}</td>
      <td>${s.origem}</td>
      <td>${s.obs}</td>
    `;
    tbody.appendChild(tr);
  });
}
