// doScrape.js
const admin = require("firebase-admin");
const axios = require("axios");
const net   = require("net");
const dns   = require("dns").promises;
const fs    = require("fs");
const path  = require("path");

// Init Admin com service account via env var
const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT);
admin.initializeApp({ credential: admin.credential.cert(serviceAccount) });
const db = admin.firestore();

const VERSIONS      = [15,14,13,12,10,8,7,6,3];
const TIMEOUT_SOCKET = 2000;
const TIMEOUT_HTTP   = 5000;

async function collectSocket(domain) { /* idêntico ao seu código */ }
async function collectHTTP(domain)  { /* idêntico ao seu código */ }

(async () => {
  const domains = fs.readFileSync("./functions/servidores_otserv_socket.txt","utf-8")
                    .split(/\r?\n/).filter(Boolean);
  const results = [];
  for (const d of domains) {
    let r = await collectSocket(d);
    if (r.origem !== "socket") r = await collectHTTP(d);
    results.push({ nome:d, versao:r.obs.startsWith("v")?r.obs:"", jogadores:r.jogadores, origem:r.origem, obs:r.obs });
  }
  await db.collection("rankings").doc("latest")
          .set({ updatedAt: admin.firestore.FieldValue.serverTimestamp(), servidores: results });
  console.log("✅ Scrape concluído:", results.length, "servidores");
})();
