/* global firebaseConfig, firebase */

(function () {
  firebase.initializeApp(firebaseConfig);

  const auth = firebase.auth();
  const db = firebase.firestore();

  // IMPORTANTE:
  // Coloque aqui o SEU e-mail (o mesmo que você usa pra login do site).
  // Só esse e-mail poderá mexer no admin.
  const ADMIN_EMAILS = ["COLOQUE_SEU_EMAIL_AQUI"];

  const elStatus = document.getElementById("adminStatus");
  const btnSair = document.getElementById("btnSair");

  const monthId = document.getElementById("monthId");
  const monthLabel = document.getElementById("monthLabel");
  const monthEndsAt = document.getElementById("monthEndsAt");
  const btnSalvarMes = document.getElementById("btnSalvarMes");

  const bpPersonagem = document.getElementById("bpPersonagem");
  const bpStream = document.getElementById("bpStream");
  const bpVideo = document.getElementById("bpVideo");
  const btnAddBadplay = document.getElementById("btnAddBadplay");
  const badplaysAdminList = document.getElementById("badplaysAdminList");

  const crNome = document.getElementById("crNome");
  const crCanal = document.getElementById("crCanal");
  const btnAddCreator = document.getElementById("btnAddCreator");
  const creatorsAdminList = document.getElementById("creatorsAdminList");

  const otNome = document.getElementById("otNome");
  const otSite = document.getElementById("otSite");
  const otDiscord = document.getElementById("otDiscord");
  const btnAddOt = document.getElementById("btnAddOt");
  const otAdminList = document.getElementById("otAdminList");

  let activeMonthId = null;

  function isAdmin(user) {
    if (!user || !user.email) return false;
    return ADMIN_EMAILS.includes(user.email);
  }

  function status(msg) {
    elStatus.textContent = msg;
  }

  function card(title, sub, onDel) {
    const div = document.createElement("div");
    div.className = "home-card";
    div.innerHTML = `
      <div class="home-card__title">${escapeHtml(title)}</div>
      <div class="home-card__sub">${sub}</div>
      <div class="home-card__actions">
        <button class="home-btn">Excluir</button>
      </div>
    `;
    div.querySelector("button").addEventListener("click", onDel);
    return div;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (m) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[m]));
  }

  async function loadActiveMonth() {
    const snap = await db.collection("config").doc("activeMonth").get();
    if (!snap.exists) {
      status("Sem mês ativo configurado. Preencha acima e clique em salvar.");
      return;
    }
    const d = snap.data();
    activeMonthId = d.monthId;
    monthId.value = d.monthId || "";
    monthLabel.value = d.label || "";
    monthEndsAt.value = (d.endsAt && d.endsAt.toDate) ? d.endsAt.toDate().toISOString().slice(0, 10) : "";
    status(`Mês ativo: ${d.label || d.monthId}`);
  }

  async function renderLists() {
    if (!activeMonthId) return;

    // Badplays
    badplaysAdminList.innerHTML = "";
    const bpSnap = await db.collection("months").doc(activeMonthId).collection("badplays").orderBy("createdAt", "desc").get();
    bpSnap.docs.forEach((doc) => {
      const d = doc.data();
      const sub = `Stream: <a href="${d.streamUrl}" target="_blank" rel="noopener">abrir</a> • Vídeo: <a href="${d.videoUrl}" target="_blank" rel="noopener">ver</a> • Pontos: ${d.score || 0}`;
      badplaysAdminList.appendChild(card(d.personagem || doc.id, sub, async () => {
        await doc.ref.delete();
        await renderLists();
      }));
    });

    // Creators
    creatorsAdminList.innerHTML = "";
    const crSnap = await db.collection("months").doc(activeMonthId).collection("creators").orderBy("createdAt", "desc").get();
    crSnap.docs.forEach((doc) => {
      const d = doc.data();
      const sub = `Canal: <a href="${d.canalUrl}" target="_blank" rel="noopener">abrir</a>`;
      creatorsAdminList.appendChild(card(d.nome || doc.id, sub, async () => {
        await doc.ref.delete();
        await renderLists();
      }));
    });

    // OTs
    otAdminList.innerHTML = "";
    const otSnap = await db.collection("months").doc(activeMonthId).collection("otservers").orderBy("createdAt", "desc").get();
    otSnap.docs.forEach((doc) => {
      const d = doc.data();
      const sub = `Site: <a href="${d.siteUrl}" target="_blank" rel="noopener">abrir</a> • Discord: <a href="${d.discordUrl}" target="_blank" rel="noopener">abrir</a> • Pontos: ${d.score || 0}`;
      otAdminList.appendChild(card(d.nome || doc.id, sub, async () => {
        await doc.ref.delete();
        await renderLists();
      }));
    });
  }

  btnSair.addEventListener("click", async () => {
    await auth.signOut();
    status("Você saiu. Faça login novamente.");
  });

  btnSalvarMes.addEventListener("click", async () => {
    const id = (monthId.value || "").trim();
    const label = (monthLabel.value || "").trim();
    const endStr = (monthEndsAt.value || "").trim();

    if (!id) {
      status("Preencha o monthId (ex: 2025-12).");
      return;
    }

    let endsAt = null;
    if (endStr) {
      const d = new Date(endStr + "T23:59:59");
      endsAt = firebase.firestore.Timestamp.fromDate(d);
    }

    await db.collection("config").doc("activeMonth").set({
      monthId: id,
      label: label || id,
      endsAt: endsAt || null,
      updatedAt: firebase.firestore.FieldValue.serverTimestamp()
    }, { merge: true });

    activeMonthId = id;
    status(`Mês ativo salvo: ${label || id}`);
    await renderLists();
  });

  btnAddBadplay.addEventListener("click", async () => {
    if (!activeMonthId) {
      status("Defina o mês ativo antes.");
      return;
    }
    const personagem = (bpPersonagem.value || "").trim();
    const streamUrl = (bpStream.value || "").trim();
    const videoUrl = (bpVideo.value || "").trim();

    if (!personagem || !streamUrl || !videoUrl) {
      status("Preencha Personagem + Stream + Vídeo.");
      return;
    }

    await db.collection("months").doc(activeMonthId).collection("badplays").add({
      personagem,
      streamUrl,
      videoUrl,
      score: 0,
      createdAt: firebase.firestore.FieldValue.serverTimestamp()
    });

    bpPersonagem.value = "";
    bpStream.value = "";
    bpVideo.value = "";

    status("Jogada adicionada.");
    await renderLists();
  });

  btnAddCreator.addEventListener("click", async () => {
    if (!activeMonthId) {
      status("Defina o mês ativo antes.");
      return;
    }
    const nome = (crNome.value || "").trim();
    const canalUrl = (crCanal.value || "").trim();

    if (!nome || !canalUrl) {
      status("Preencha Nome + Link do canal.");
      return;
    }

    await db.collection("months").doc(activeMonthId).collection("creators").add({
      nome,
      canalUrl,
      score: 0,
      createdAt: firebase.firestore.FieldValue.serverTimestamp()
    });

    crNome.value = "";
    crCanal.value = "";

    status("Criador adicionado.");
    await renderLists();
  });

  btnAddOt.addEventListener("click", async () => {
    if (!activeMonthId) {
      status("Defina o mês ativo antes.");
      return;
    }
    const nome = (otNome.value || "").trim();
    const siteUrl = (otSite.value || "").trim();
    const discordUrl = (otDiscord.value || "").trim();

    if (!nome || !siteUrl || !discordUrl) {
      status("Preencha Nome + Site + Discord.");
      return;
    }

    await db.collection("months").doc(activeMonthId).collection("otservers").add({
      nome,
      siteUrl,
      discordUrl,
      score: 0,
      createdAt: firebase.firestore.FieldValue.serverTimestamp()
    });

    otNome.value = "";
    otSite.value = "";
    otDiscord.value = "";

    status("OTServer adicionado.");
    await renderLists();
  });

  auth.onAuthStateChanged(async (user) => {
    if (!user) {
      status("Faça login para usar o Admin. (seu e-mail precisa estar na lista ADMIN_EMAILS)");
      return;
    }
    if (!isAdmin(user)) {
      status("Você está logado, mas este e-mail não tem permissão no Admin. Ajuste ADMIN_EMAILS no admin.js.");
      return;
    }

    status(`Admin liberado: ${user.email}`);
    await loadActiveMonth();
    await renderLists();
  });
})();
