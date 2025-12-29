/* global firebaseConfig, firebase */

(function () {
  // ========= CONFIG EDITÁVEL =========
  // 1) Coloque sua chave do reCAPTCHA v3 (App Check) aqui:
  //    Firebase Console > App Check > Web app > reCAPTCHA v3
  const APP_CHECK_RECAPTCHA_V3_SITE_KEY = "COLOQUE_SUA_SITE_KEY_AQUI";

  // 2) Cooldown em horas (você pediu 6h)
  const COOLDOWN_HOURS = 6;

  // ========= INIT FIREBASE =========
  firebase.initializeApp(firebaseConfig);

  const auth = firebase.auth();
  const db = firebase.firestore();
  const fn = firebase.functions();

  // App Check (anti-bot)
  try {
    if (APP_CHECK_RECAPTCHA_V3_SITE_KEY && APP_CHECK_RECAPTCHA_V3_SITE_KEY.includes("COLOQUE_") === false) {
      firebase.appCheck().activate(APP_CHECK_RECAPTCHA_V3_SITE_KEY, true);
    }
  } catch (e) {
    // Se não configurar a key, só perde uma camada de segurança (o site ainda funciona).
  }

  // ========= UI =========
  const elStatus = document.getElementById("statusTopo");
  const elMesTag = document.getElementById("mesAtualTag");
  const elFechaTag = document.getElementById("fechaEmTag");

  const elTopBadplays = document.getElementById("badplaysTop3");
  const elListaBadplays = document.getElementById("badplaysLista");
  const btnVerTodosBad = document.getElementById("btnVerTodosBadplays");

  const elOtTop = document.getElementById("otTop3");
  const elOtLista = document.getElementById("otLista");
  const btnVerTodosOts = document.getElementById("btnVerTodosOts");

  const btnMenu = document.getElementById("btnMenu");
  const sideMenu = document.getElementById("sideMenu");

  const btnLogin = document.getElementById("btnLogin");
  const btnPainel = document.getElementById("btnPainel");

  // Duel
  const duelAName = document.getElementById("duelAName");
  const duelBName = document.getElementById("duelBName");
  const duelALink = document.getElementById("duelALink");
  const duelBLink = document.getElementById("duelBLink");
  const btnVotarA = document.getElementById("btnVotarA");
  const btnVotarB = document.getElementById("btnVotarB");
  const btnTrocarDuelo = document.getElementById("btnTrocarDuelo");

  // ========= HELPERS =========
  function toast(msg) {
    elStatus.textContent = msg;
  }

  function fmtDate(d) {
    try {
      return new Date(d).toLocaleDateString("pt-BR");
    } catch {
      return "—";
    }
  }

  function remainingToText(ms) {
    const totalMin = Math.max(0, Math.ceil(ms / 60000));
    const h = Math.floor(totalMin / 60);
    const m = totalMin % 60;
    if (h <= 0) return `${m} min`;
    return `${h}h ${m}m`;
  }

  function weightLabel(user) {
    if (!user) return "Voto livre: +1 • Logado: +2";
    return user.isAnonymous ? "Voto livre: +1 • Logado: +2" : "Você está logado: seu voto vale +2";
  }

  // ========= STATE =========
  let activeMonthId = null;

  // Duel pool (em memória, pra trocar duelo sem travar)
  let creatorsPool = [];
  let currentDuelA = null;
  let currentDuelB = null;

  // ========= MENU =========
  btnMenu.addEventListener("click", () => {
    sideMenu.style.display = (sideMenu.style.display === "block") ? "none" : "block";
  });
  document.addEventListener("click", (e) => {
    if (!sideMenu.contains(e.target) && e.target !== btnMenu) {
      sideMenu.style.display = "none";
    }
  });

  // ========= AUTH (voto livre, mas com identidade) =========
  // Para voto livre com segurança: fazemos login anônimo automático.
  async function ensureAuth() {
    if (auth.currentUser) return auth.currentUser;
    await auth.signInAnonymously();
    return auth.currentUser;
  }

  auth.onAuthStateChanged((user) => {
    // Ajusta botões do topo
    if (user && !user.isAnonymous) {
      btnLogin.style.display = "none";
      btnPainel.style.display = "inline-flex";
    } else {
      btnLogin.style.display = "inline-flex";
      btnPainel.style.display = "none";
    }

    const pesoTag = document.getElementById("pesoVotoTag");
    if (pesoTag) pesoTag.textContent = weightLabel(user);
  });

  // ========= LOAD ACTIVE MONTH =========
  async function loadActiveMonth() {
    // Doc simples: config/activeMonth
    // { monthId: "2025-12", label: "Dezembro 2025", endsAt: Timestamp }
    const snap = await db.collection("config").doc("activeMonth").get();

    if (!snap.exists) {
      // fallback pro mês atual
      const now = new Date();
      const id = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
      activeMonthId = id;
      elMesTag.textContent = id;
      elFechaTag.textContent = "Sem configuração";
      toast("Configure o mês em /admin.html (config/activeMonth).");
      return;
    }

    const data = snap.data();
    activeMonthId = data.monthId;
    elMesTag.textContent = data.label || data.monthId || "—";

    let endsAt = null;
    if (data.endsAt && data.endsAt.toDate) endsAt = data.endsAt.toDate();
    elFechaTag.textContent = endsAt ? `Fecha em: ${fmtDate(endsAt)}` : "—";
  }

  // ========= RENDER CARDS =========
  function makeBadplayCard(doc) {
    const d = doc.data();
    const personagem = d.personagem || "—";
    const streamUrl = d.streamUrl || "#";
    const videoUrl = d.videoUrl || "#";
    const score = Number(d.score || 0);

    const div = document.createElement("div");
    div.className = "home-card";
    div.innerHTML = `
      <div class="home-card__title">${escapeHtml(personagem)}</div>
      <div class="home-card__sub">
        Stream: <a href="${escapeAttr(streamUrl)}" target="_blank" rel="noopener">abrir</a>
        • Vídeo: <a href="${escapeAttr(videoUrl)}" target="_blank" rel="noopener">ver jogada</a>
      </div>
      <div class="home-card__score"><b>Pontos:</b> ${score}</div>
      <div class="home-card__actions">
        <button class="home-btn" data-vote="badplay" data-id="${doc.id}">Votar</button>
        <a class="home-btn home-btn--ghost" href="${escapeAttr(videoUrl)}" target="_blank" rel="noopener">Ver</a>
      </div>
    `;
    return div;
  }

  function makeOtCard(doc) {
    const d = doc.data();
    const nome = d.nome || "—";
    const siteUrl = d.siteUrl || "#";
    const discordUrl = d.discordUrl || "#";
    const score = Number(d.score || 0);

    const div = document.createElement("div");
    div.className = "home-card";
    div.innerHTML = `
      <div class="home-card__title">${escapeHtml(nome)}</div>
      <div class="home-card__sub">
        <a href="${escapeAttr(siteUrl)}" target="_blank" rel="noopener">Site</a>
        • <a href="${escapeAttr(discordUrl)}" target="_blank" rel="noopener">Discord</a>
      </div>
      <div class="home-card__score"><b>Pontos:</b> ${score}</div>
      <div class="home-card__actions">
        <button class="home-btn" data-vote="otserver" data-id="${doc.id}">Votar</button>
        <a class="home-btn home-btn--ghost" href="${escapeAttr(siteUrl)}" target="_blank" rel="noopener">Visitar</a>
      </div>
    `;
    return div;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (m) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[m]));
  }
  function escapeAttr(s) {
    return String(s).replace(/"/g, "&quot;");
  }

  // ========= LOAD BLOCKS =========
  async function loadBadplays() {
    elTopBadplays.innerHTML = "";
    elListaBadplays.innerHTML = "";

    const q = db.collection("months").doc(activeMonthId).collection("badplays").orderBy("score", "desc");
    const snap = await q.get();

    const docs = snap.docs || [];
    const top3 = docs.slice(0, 3);

    if (top3.length === 0) {
      elTopBadplays.innerHTML = `<div class="home-card"><div class="home-card__title">Nenhuma jogada cadastrada</div><div class="home-card__sub">Cadastre em /admin.html</div></div>`;
      return;
    }

    top3.forEach((doc) => elTopBadplays.appendChild(makeBadplayCard(doc)));

    docs.forEach((doc) => elListaBadplays.appendChild(makeBadplayCard(doc)));
  }

  async function loadOtservers() {
    elOtTop.innerHTML = "";
    elOtLista.innerHTML = "";

    const q = db.collection("months").doc(activeMonthId).collection("otservers").orderBy("score", "desc");
    const snap = await q.get();

    const docs = snap.docs || [];
    const top3 = docs.slice(0, 3);

    if (top3.length === 0) {
      elOtTop.innerHTML = `<div class="home-card"><div class="home-card__title">Nenhum OTServer cadastrado</div><div class="home-card__sub">Cadastre em /admin.html</div></div>`;
      return;
    }

    top3.forEach((doc) => elOtTop.appendChild(makeOtCard(doc)));
    docs.forEach((doc) => elOtLista.appendChild(makeOtCard(doc)));
  }

  async function loadCreatorsPool() {
    const snap = await db.collection("months").doc(activeMonthId).collection("creators").get();
    creatorsPool = (snap.docs || []).map(d => ({ id: d.id, ...d.data() }))
      .filter(c => c && c.nome && c.canalUrl);

    if (creatorsPool.length < 2) {
      duelAName.textContent = "Sem criadores suficientes";
      duelBName.textContent = "Cadastre em /admin.html";
      duelALink.href = "#";
      duelBLink.href = "#";
      btnVotarA.disabled = true;
      btnVotarB.disabled = true;
      btnTrocarDuelo.disabled = true;
      return;
    }

    btnVotarA.disabled = false;
    btnVotarB.disabled = false;
    btnTrocarDuelo.disabled = false;

    pickNewDuel();
  }

  function pickNewDuel() {
    if (creatorsPool.length < 2) return;

    // sorteia dois diferentes
    const a = creatorsPool[Math.floor(Math.random() * creatorsPool.length)];
    let b = creatorsPool[Math.floor(Math.random() * creatorsPool.length)];
    let guard = 0;
    while (b.id === a.id && guard < 10) {
      b = creatorsPool[Math.floor(Math.random() * creatorsPool.length)];
      guard++;
    }

    currentDuelA = a;
    currentDuelB = b;

    duelAName.textContent = a.nome;
    duelBName.textContent = b.nome;
    duelALink.href = a.canalUrl;
    duelBLink.href = b.canalUrl;
  }

  // ========= VOTE (via Cloud Function) =========
  async function vote(type, targetId) {
    await ensureAuth();

    toast("Registrando voto...");

    const callable = fn.httpsCallable("vote");
    try {
      const res = await callable({
        monthId: activeMonthId,
        type,
        targetId,
        cooldownHours: COOLDOWN_HOURS
      });

      const data = res.data || {};
      if (data && data.ok) {
        toast(`Voto computado! (+${data.weight}) • Próximo em ${data.nextAllowedIn || "6h"}`);
        // recarrega placares
        if (type === "badplay") await loadBadplays();
        if (type === "otserver") await loadOtservers();
        if (type === "duel") pickNewDuel();
        return;
      }

      toast("Não foi possível votar.");
    } catch (err) {
      const msg = (err && err.message) ? err.message : String(err);
      toast(msg.replace("functions.", "").replace("FirebaseError: ", ""));
    }
  }

  // ========= EVENTS =========
  btnVerTodosBad.addEventListener("click", () => {
    const showing = elListaBadplays.style.display !== "none";
    elListaBadplays.style.display = showing ? "none" : "grid";
    btnVerTodosBad.textContent = showing ? "Ver todos do mês" : "Esconder lista";
  });

  btnVerTodosOts.addEventListener("click", () => {
    const showing = elOtLista.style.display !== "none";
    elOtLista.style.display = showing ? "none" : "grid";
    btnVerTodosOts.textContent = showing ? "Ver todos" : "Esconder lista";
  });

  btnTrocarDuelo.addEventListener("click", () => pickNewDuel());
  btnVotarA.addEventListener("click", () => {
    if (!currentDuelA) return;
    vote("duel", currentDuelA.id);
  });
  btnVotarB.addEventListener("click", () => {
    if (!currentDuelB) return;
    vote("duel", currentDuelB.id);
  });

  document.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-vote]");
    if (!btn) return;
    const type = btn.getAttribute("data-vote");
    const id = btn.getAttribute("data-id");
    vote(type, id);
  });

  // ========= START =========
  (async function start() {
    toast("Entrando...");
    await ensureAuth();
    toast("Carregando mês...");
    await loadActiveMonth();

    if (!activeMonthId) return;

    toast("Carregando placares...");
    await loadBadplays();
    await loadCreatorsPool();
    await loadOtservers();

    toast("Pronto. Vote livre (+1) • Logado (+2) • Cooldown 6h.");
  })();
})();
