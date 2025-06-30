// atualizar.js

const admin = require("firebase-admin");
const fs = require("fs");
const path = require("path");
const axios = require("axios");
const net = require("net");

// Inicializa o Admin SDK
admin.initializeApp();
const db = admin.firestore();

// Função para coletar via socket OTServ
async function collectSocket(ip, port, timeout = 3000) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    let resolved = false;
    const timer = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        socket.destroy();
        resolve({ jogadores: 0, origem: "socket", obs: "timeout" });
      }
    }, timeout);

    socket.connect(port, ip, () => {
      // Handshake OTProtocol (versão 12) para obter informações
      const protocol = 12;
      const buf = Buffer.alloc(3);
      buf.writeUInt8(0x0a, 0); // código de handshake
      buf.writeUInt16LE(protocol, 1);
      socket.write(buf);
    });

    socket.on("data", (data) => {
      if (!resolved) {
        clearTimeout(timer);
        resolved = true;
        const players = data.readUInt8(5);
        resolve({ jogadores: players, origem: "socket", obs: "" });
      }
      socket.destroy();
    });

    socket.on("error", (err) => {
      if (!resolved) {
        clearTimeout(timer);
        resolved = true;
        resolve({ jogadores: 0, origem: "socket", obs: err.message });
      }
    });
  });
}

(async () => {
  try {
    console.log("🏁 Iniciando atualização de rankings…");
    const filePath = path.join(
      __dirname,
      "functions",
      "servidores_otserv_socket.txt",
    );
    const lines = fs
      .readFileSync(filePath, "utf-8")
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);

    const resultados = [];
    for (const line of lines) {
      const [nome, ip, portStr] = line.split(",");
      const port = parseInt(portStr, 10) || 7171;
      let result = await collectSocket(ip, port);

      // Se falhou via socket, tenta fallback HTTP
      if (result.obs) {
        try {
          const url = `http://${ip}:${port}/`;
          const res = await axios.get(url, { timeout: 5000 });
          const match = res.data.match(/Online Players:\s*(\d+)/i);
          const players = match ? parseInt(match[1], 10) : 0;
          result = { jogadores: players, origem: "HTML", obs: "" };
        } catch (e) {
          result = { jogadores: 0, origem: "HTML", obs: e.message };
        }
      }

      resultados.push({
        nome,
        versao: "",
        jogadores: result.jogadores,
        origem: result.origem,
        obs: result.obs,
      });
    }

    await db.collection("rankings").doc("latest").set({
      updatedAt: admin.firestore.FieldValue.serverTimestamp(),
      servidores: resultados,
    });

    console.log("✅ Rankings gravados em Firestore.");
  } catch (e) {
    console.error("❌ Erro ao atualizar rankings:", e);
  }
})();
