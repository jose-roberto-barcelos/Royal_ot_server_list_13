<!DOCTYPE html>
<html lang="pt-br">
  <head>
    <meta charset="UTF-8" />
    <title>Contato | Royal OtServlist</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />

    <!-- Google Font -->
    <link
      href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600&display=swap"
      rel="stylesheet"
    />

    <!-- Seu CSS -->
    <link rel="stylesheet" href="styles.css" />
  </head>

  <body class="fundo-contato">
    <div class="background"></div>
    <video autoplay muted loop class="fog">
      <source src="./Neblina.webm" type="video/webm" />
    </video>

    <!-- === Cabeçalho copiado do regras.html === -->
    <header class="site-header">
      <div class="titulo-container">
        <img
          src="./tituloprincipal.png"
          alt="Royal OtServlist"
          class="titulo-imagem"
        />
      </div>
      <div class="brasao-centro">
        <a href="destaque.html">
          <img src="./brasao-novo.png" alt="Brasão" class="header-brasao" />
        </a>
      </div>
      <div class="bloco-direita">
        <div class="botoes-acesso">
          <!-- login e logout são links diretos -->
          <a href="login.html" class="btn-imagem login-btn">
            <img src="./icon-login.png" alt="Login" width="24" height="24" />
          </a>
          <a href="register.html" class="btn-imagem registrar-btn">
            <img
              src="./icon-registrar.png"
              alt="Registrar"
              width="24"
              height="24"
            />
          </a>
        </div>
        <nav class="nav-links">
          <div class="nav-esquerda">
            <a href="top.html">Top Streamers/Youtube</a>
            <a href="servicos.html">Serviços & Portfólio</a>
          </div>
          <div class="nav-direita">
            <a href="index.html">Início</a>
            <a href="regras.html">Regras/ban</a>
            <a href="sobre.html">Sobre</a>
            <a href="contato.html">Contato</a>
          </div>
        </nav>
      </div>
    </header>
    <!-- ========================================== -->

    <main class="formulario-centro espaco-pos-header">
      <div class="info-contato">
        <h2>Fale com a gente</h2>
        <p><strong>Email:</strong> contato@royalotservlist.com</p>
        <p>
          <strong>Instagram:</strong>
          <a
            href="https://instagram.com/royalotservlist"
            target="_blank"
            >@royalotservlist</a
          >
        </p>
      </div>

      <form id="contato-form">
        <h1>Envie uma mensagem</h1>
        <input type="text" name="nome" placeholder="Seu nome" required />
        <input type="email" name="email" placeholder="Seu e-mail" required />
        <textarea
          name="mensagem"
          placeholder="Sua mensagem"
          rows="6"
          required
        ></textarea>
        <button type="submit">Enviar</button>
      </form>
    </main>

    <!-- Script de envio de formulário (compat ou modular, conforme você já tinha) -->
    <script>
      // Exemplo compat -- mantenha o que já funcionava pra você
      const db = firebase.firestore();
      document
        .getElementById("contato-form")
        .addEventListener("submit", async (e) => {
          e.preventDefault();
          const form = e.target;
          const data = {
            nome: form.nome.value,
            email: form.email.value,
            mensagem: form.mensagem.value,
            criadoEm: firebase.firestore.FieldValue.serverTimestamp(),
          };
          try {
            await db.collection("contatos").add(data);
            alert("Mensagem enviada com sucesso!");
            form.reset();
          } catch (err) {
            console.error(err);
            alert("Erro ao enviar. Veja o console.");
          }
        });
    </script>
  </body>
</html>
