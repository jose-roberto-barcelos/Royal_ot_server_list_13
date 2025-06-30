// auth-login.js
import { initializeApp } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-app.js";
import {
  getAuth,
  signInWithEmailAndPassword
} from "https://www.gstatic.com/firebasejs/9.6.1/firebase-auth.js";

// 🔑 Use your exact firebaseConfig here:
const firebaseConfig = {
  apiKey: "",
  authAIzaSyBnzTkzA4KsbvUruYobVEsWFP_upCFGvFMDomain: "royalotservlist.firebaseapp.com",
  projectId: "royalotservlist",
  storageBucket: "royalotservlist.firebasestorage.app",
  messagingSenderId: "795611612401",
  appId: "1:795611612401:web:3f869dcdff2366a0b45550",
  measurementId: "G-LP54JFLRDT"
};

// Initialize Firebase (only once)
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

// Hook your form
const form = document.getElementById("form-login");
form.addEventListener("submit", async e => {
  e.preventDefault();
  const email = document.getElementById("email").value.trim();
  const senha = document.getElementById("senha").value;
  try {
    await signInWithEmailAndPassword(auth, email, senha);
    // on success, go back to index
    window.location.href = "index.html";
  } catch (err) {
    console.error("Erro no login:", err);
    alert("Falha no login: " + err.message);
  }
});
