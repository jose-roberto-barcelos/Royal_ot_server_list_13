const functions = require("firebase-functions");
const admin = require("firebase-admin");

admin.initializeApp();
const db = admin.firestore();

function getWeight(context) {
  // anonymous = 1 / logado = 2
  const provider = context?.auth?.token?.firebase?.sign_in_provider;
  return provider === "anonymous" ? 1 : 2;
}

function requireAuth(context) {
  if (!context.auth || !context.auth.uid) {
    throw new functions.https.HttpsError("unauthenticated", "Você precisa estar autenticado (o voto livre usa login anônimo automático).");
  }
}

function requireAppCheck(context) {
  // Quando App Check estiver configurado, context.app existe.
  // Se você ainda não configurou, comente este bloqueio para testar,
  // mas para segurança real deixe ativo.
  if (!context.app) {
    throw new functions.https.HttpsError("failed-precondition", "App Check obrigatório (anti-bot). Configure no Firebase Console.");
  }
}

function cooldownKey(monthId, type, uid) {
  return `${monthId}__${type}__${uid}`;
}

exports.vote = functions.https.onCall(async (data, context) => {
  requireAuth(context);
  requireAppCheck(context);

  const uid = context.auth.uid;
  const monthId = String(data.monthId || "").trim();
  const type = String(data.type || "").trim(); // "badplay" | "duel" | "otserver"
  const targetId = String(data.targetId || "").trim();

  const cooldownHours = Number(data.cooldownHours || 6);

  if (!monthId || !type || !targetId) {
    throw new functions.https.HttpsError("invalid-argument", "Dados inválidos para voto.");
  }

  if (!["badplay", "duel", "otserver"].includes(type)) {
    throw new functions.https.HttpsError("invalid-argument", "Tipo de voto inválido.");
  }

  const weight = getWeight(context);
  const now = admin.firestore.Timestamp.now();

  // alvo
  let targetRef;
  if (type === "badplay") {
    targetRef = db.collection("months").doc(monthId).collection("badplays").doc(targetId);
  } else if (type === "otserver") {
    targetRef = db.collection("months").doc(monthId).collection("otservers").doc(targetId);
  } else {
    // duel: targetId = creatorId (pontua o criador)
    targetRef = db.collection("months").doc(monthId).collection("creators").doc(targetId);
  }

  const cdRef = db.collection("voteCooldowns").doc(cooldownKey(monthId, type, uid));
  const logRef = db.collection("voteLogs").doc(); // histórico (opcional)

  const nextAllowedAt = admin.firestore.Timestamp.fromMillis(
    now.toMillis() + cooldownHours * 60 * 60 * 1000
  );

  // transação: checa cooldown e soma pontos
  await db.runTransaction(async (tx) => {
    const [cdSnap, tSnap] = await Promise.all([tx.get(cdRef), tx.get(targetRef)]);

    if (cdSnap.exists) {
      const cd = cdSnap.data() || {};
      const na = cd.nextAllowedAt;
      if (na && na.toMillis && now.toMillis() < na.toMillis()) {
        const diff = na.toMillis() - now.toMillis();
        throw new functions.https.HttpsError(
          "resource-exhausted",
          `Aguarde ${Math.ceil(diff / 60000)} min para votar novamente (${type}).`
        );
      }
    }

    if (!tSnap.exists) {
      throw new functions.https.HttpsError("not-found", "Alvo do voto não encontrado.");
    }

    const currentScore = Number((tSnap.data() || {}).score || 0);
    tx.update(targetRef, {
      score: currentScore + weight,
      updatedAt: now
    });

    tx.set(cdRef, {
      uid,
      monthId,
      type,
      lastTargetId: targetId,
      weightLast: weight,
      nextAllowedAt,
      updatedAt: now
    }, { merge: true });

    tx.set(logRef, {
      uid,
      monthId,
      type,
      targetId,
      weight,
      createdAt: now
    });
  });

  // Resposta
  const mins = Math.ceil((cooldownHours * 60));
  return {
    ok: true,
    weight,
    nextAllowedIn: `${cooldownHours}h (~${mins} min)`,
    nextAllowedAt: nextAllowedAt.toDate().toISOString()
  };
});
