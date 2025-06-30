import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import {
  getAuth,
  onAuthStateChanged,
  signOut
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

// ✅ Sua config Firebase
const firebaseConfig = {
  apiKey: "",
  authAIzaSyBnzTkzA4KsbvUruYobVEsWFP_upCFGvFMDomain: "royalotservlist.firebaseapp.com",
  projectId: "royalotservlist",
  storageBucket: "royalotservlist.firebasestorage.app",
  messagingSenderId: "795611612401",
  appId: "1:795611612401:web:3f869dcdff2366a0b45550",
  measurementId: "G-LP54JFLRDT"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

// ✅ Muda botão de login para SAIR com seu ícone
onAuthStateChanged(auth, (user) => {
  const loginBtn = document.querySelector(".login-btn");

  if (user) {
    if (loginBtn) {
      loginBtn.innerHTML = `<img src="./icon-sair.png" alt="Sair" />`;
      loginBtn.onclick = () => {
        signOut(auth).then(() => {
          alert("Você saiu com sucesso.");
          window.location.href = "index.html";
        });
      };
    }
  } else {
    // Caso esteja deslogado, mantém botão padrão
    if (loginBtn) {
      loginBtn.innerHTML = `<img src="./icon-login.png" alt="Login" />`;
      loginBtn.onclick = () => {
        window.location.href = "login.html";
      };
    }
  }
});
