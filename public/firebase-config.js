// public/firebase-config.js
import { initializeApp, getApps, getApp } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-app.js";
import { getAuth }                        from "https://www.gstatic.com/firebasejs/9.6.1/firebase-auth.js";
import { getFirestore }                   from "https://www.gstatic.com/firebasejs/9.6.1/firebase-firestore.js";

const firebaseConfig = {
  apiKey: "AIzaSyBnzTkzA4KsbvUruYobVEsWFP_upCFGvFM",

  authDomain: "royalotservlist.firebaseapp.com",
  projectId: "royalotservlist",
  storageBucket: "royalotservlist.firebasestorage.app",
  messagingSenderId: "795611612401",
  appId: "1:795611612401:web:3f869dcdff2366a0b45550",
  measurementId: "G-LP54JFLRDT"
};

// Inicializa o app apenas uma vez
const app  = !getApps().length ? initializeApp(firebaseConfig) : getApp();
const auth = getAuth(app);
const db   = getFirestore(app);

export { app, auth, db };
