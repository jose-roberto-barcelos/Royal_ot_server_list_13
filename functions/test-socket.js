// test-socket.js
const net = require("net");
const dns = require("dns").promises;

// Troque aqui por um servidor que você sabe suportar OTProtocol (por exemplo: "ambrussouls.com").
const DOMAIN = "ambrussouls.com"; 
// Versões que estamos testando:
const VERSIONS = [15,14,13,12,10,8,7,6,3];
// Timeout para cada tentativa:
const TIMEOUT = 2000;

(async () => {
  let ip;
  try {
    ({ address: ip } = await dns.lookup(DOMAIN, { family: 4 }));
  } catch (e) {
    return console.error("❌ DNS lookup falhou:", e.message);
  }
  console.log(`🔍 Testando ${DOMAIN} (${ip})\n`);
  for (const v of VERSIONS) {
    await new Promise((resolve) => {
      const socket = new net.Socket();
      let done = false;
      // Se demorar demais...
      const timer = setTimeout(() => {
        if (!done) {
          done = true;
          console.log(`v${v}: ⏱ timeout`);
          socket.destroy();
          resolve();
        }
      }, TIMEOUT);
      socket.connect(7171, ip, () => {
        // Monta o buffer [0x0A, versão (LE)]
        const buf = Buffer.alloc(3);
        buf.writeUInt8(0x0A, 0);
        buf.writeUInt16LE(v, 1);
        socket.write(buf);
      });
      socket.on("data", (data) => {
        if (!done) {
          clearTimeout(timer);
          done = true;
          console.log(`v${v}: ✅ recebeu ${data.length} bytes →`, data);
          socket.destroy();
          resolve();
        }
      });
      socket.on("error", (err) => {
        if (!done) {
          clearTimeout(timer);
          done = true;
          console.log(`v${v}: ❌ erro →`, err.message);
          resolve();
        }
      });
    });
  }
})();
