// functions/index.js

const { onRequest } = require("firebase-functions/v2/https");
const { onSchedule } = require("firebase-functions/v2/scheduler");
const admin = require("firebase-admin");
const fs = require("fs");
const path = require("path");
const axios = require("axios");
const net = require("net");
const dns = require("dns").promises;

// Inicializa o Firebase Admin SDK
admin.initializeApp();
const db = admin.firestore();

// Configurações de timeout e paralelismo
const TIMEOUT_SOCKET = 2000;  // 2s para handshake socket
const TIMEOUT_HTTP   = 5000;  // 5s para requests HTTP
const CHUNK_SIZE     = 50;    // lotes de 50 servidores
const VERSIONS       = [15,14,13,12,10,8,7,6,3];

// Coleta via socket OTProtocol
async function collectSocket(domain) {
  let ip;
  try {
    ({ address: ip } = await dns.lookup(domain, { family: 4 }));
  } catch {
    return { jogadores: 0, origem: 'socketError', obs: 'DNS fail' };
  }

  for (const v of VERSIONS) {
    const result = await new Promise(resolve => {
      const socket = new net.Socket();
      let done = false;
      const timer = setTimeout(() => {
        if (!done) { done = true; socket.destroy(); resolve(null); }
      }, TIMEOUT_SOCKET);

      socket.connect(7171, ip, () => {
        const buf = Buffer.alloc(3);
        buf.writeUInt8(0x0A, 0);
        buf.writeUInt16LE(v, 1);
        socket.write(buf);
      });

      socket.on('data', data => {
        if (!done) {
          clearTimeout(timer);
          done = true;
          const players = data.readUInt8(5);
          resolve({ jogadores: players, origem: 'socket', obs: `v${v}` });
        }
        socket.destroy();
      });

      socket.on('error', () => {
        if (!done) { clearTimeout(timer); done = true; resolve(null); }
      });
    });

    if (result) return result;
  }

  return { jogadores: 0, origem: 'socketError', obs: 'all versions failed' };
}

// Coleta via HTTP como fallback
async function collectHTTP(domain) {
  try {
    let response = await axios.get(`http://${domain}/`, { timeout: TIMEOUT_HTTP });
    let html = response.data;
    if (!/Online Players|Players online|Jogadores/i.test(html)) {
      response = await axios.get(`https://${domain}/`, { timeout: TIMEOUT_HTTP });
      html = response.data;
    }
    const match = html.match(/(?:Online Players|Players online|Jogadores)\D*?(\d+)/i);
    const count = match ? parseInt(match[1], 10) : 0;
    return { jogadores: count, origem: 'http', obs: '' };
  } catch {
    return { jogadores: 0, origem: 'httpError', obs: 'HTTP fail' };
  }
}

// Função interna que realiza o scraping completo
async function doScrape() {
  const filePath = path.join(__dirname, 'servidores_otserv_socket.txt');
  const domains = fs.readFileSync(filePath, 'utf-8')
    .split(/\r?\n/).map(l => l.trim()).filter(Boolean);

  const results = [];
  for (let i = 0; i < domains.length; i += CHUNK_SIZE) {
    const chunk = domains.slice(i, i + CHUNK_SIZE);
    for (const domain of chunk) {
      let r = await collectSocket(domain);
      if (r.origem !== 'socket') {
        r = await collectHTTP(domain);
      }
      results.push({
        nome: domain,
        versao: r.obs.startsWith('v') ? r.obs : '',
        jogadores: r.jogadores,
        origem: r.origem,
        obs: r.obs
      });
    }
  }

  await db.collection('rankings').doc('latest').set({
    updatedAt: admin.firestore.FieldValue.serverTimestamp(),
    servidores: results
  });
  console.log('Scraping finalizado:', results.length);
}

// Função agendada (Gen2) - executa a cada 5 minutos
exports.scheduledScrape = onSchedule(
  { schedule: 'every 5 minutes', timeZone: 'America/Sao_Paulo' },
  async () => {
    try {
      await doScrape();
    } catch (err) {
      console.error('Erro no scheduledScrape:', err);
    }
  }
);

// Endpoint HTTP para retornar o ranking atualizado
exports.getRanking = onRequest(
  { timeoutSeconds: 60 },
  async (req, res) => {
    try {
      const doc = await db.collection('rankings').doc('latest').get();
      if (!doc.exists) {
        return res.status(404).send('Nenhum ranking disponível.');
      }
      return res.status(200).json(doc.data().servidores || []);
    } catch (err) {
      console.error('Erro no getRanking:', err);
      return res.status(500).send('Erro interno');
    }
  }
);

// Endpoint HTTP manual para forçar scraping sob demanda
// Endpoint HTTP manual para forçar scraping sob demanda
exports.manualScrape = onRequest(
  { timeoutSeconds: 60 },
  (req, res) => {
    // Dispara o scraping em background sem aguardar conclusão
    doScrape().catch(err => console.error('Erro em manualScrape:', err));
    // Responde imediatamente
    return res.status(200).send('Scrape disparado com sucesso!');
  }
);
