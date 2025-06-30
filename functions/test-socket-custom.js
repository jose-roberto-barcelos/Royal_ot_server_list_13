// test-socket-custom.js
const net = require("net");
const dns = require("dns").promises;

// Dois domínios de teste
const DOMAINS = ["ambrussouls.com", "arenaot.com.br"];
const VERSIONS = [15,14,13,12,10,8,7,6,3];
const TIMEOUT = 2000; // 2 segundos

(async () => {
  for (const domain of DOMAINS) {
    let ip;
    try {
      // declara ip aqui
      const lookup = await dns.lookup(domain, { family: 4 });
      ip = lookup.address;
      console.log(`\n🔍 ${domain} → ${ip}`);
    } catch {
      console.log(`\n❌ ${domain} → DNS fail`);
      continue;
    }

    for (const v of VERSIONS) {
      await new Promise(resolve => {
        const socket = new net.Socket();
        let done = false;

        const timer = setTimeout(() => {
          if (!done) {
            done = true;
            console.log(`  v${v}: ⏱ timeout`);
            socket.destroy();
            resolve();
          }
        }, TIMEOUT);

        socket.connect(7171, ip, () => {
          const buf = Buffer.alloc(3);
          buf.writeUInt8(0x0A, 0);
          buf.writeUInt16LE(v, 1);
          socket.write(buf);
        });

        socket.on("data", data => {
          if (!done) {
            clearTimeout(timer);
            done = true;
            const players = data.readUInt8(5);
            console.log(`  v${v}: ✅ ${players} players`);
            socket.destroy();
            resolve();
          }
        });

        socket.on("error", err => {
          if (!done) {
            clearTimeout(timer);
            done = true;
            console.log(`  v${v}: ❌ ${err.message}`);
            resolve();
          }
        });
      });
    }
  }
})();
