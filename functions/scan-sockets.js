// scan-sockets.js
const net = require("net");
const dns = require("dns").promises;
const fs  = require("fs");
const path = require("path");

// Versões a testar
const VERSIONS = [15,14,13,12,10,8,7,6,3];
const TIMEOUT = 2000; // ms

// Lê todos os domínios do seu arquivo
const domains = fs.readFileSync(
  path.join(__dirname, "servidores_otserv_socket.txt"),
  "utf-8"
).split(/\r?\n/).map(l => l.trim()).filter(Boolean);

(async () => {
  console.log("Domínio,Versão,Jogadores (socket)");
  for (const domain of domains) {
    let ip;
    try {
      ({ address: ip } = await dns.lookup(domain, { family: 4 }));
    } catch {
      continue; // pular DNS fail
    }
    for (const v of VERSIONS) {
      const result = await new Promise(res => {
        const s = new net.Socket();
        let done = false;
        const timer = setTimeout(() => {
          if (!done) { done = true; s.destroy(); res(null); }
        }, TIMEOUT);
        s.connect(7171, ip, () => {
          const buf = Buffer.alloc(3);
          buf.writeUInt8(0x0A, 0);
          buf.writeUInt16LE(v, 1);
          s.write(buf);
        });
        s.on("data", data => {
          if (!done) {
            clearTimeout(timer);
            done = true;
            const players = data.readUInt8(5);
            res({ domain, version: v, players });
          }
          s.destroy();
        });
        s.on("error", () => {
          if (!done) { clearTimeout(timer); done = true; res(null); }
        });
      });
      if (result) {
        console.log(`${result.domain},v${result.version},${result.players}`);
        break; // achou versão válida, vai pro próximo domínio
      }
    }
  }
  process.exit(0);
})();
