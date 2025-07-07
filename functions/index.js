<!doctype html>
<html lang="pt-br">
  <head>
    <meta charset="UTF-8" />
    <title>Royal OtServlist</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />

    <!-- Google Font -->
    <link
      href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600&display=swap"
      rel="stylesheet"
    />
    <!-- Seu CSS -->
    <link rel="stylesheet" href="styles.css" />

    <style>
      .tibia-oficial-banner {
        background-color: rgba(0, 0, 0, 0.6);
        padding: 8px 16px;
        border: 1px solid rgba(255, 204, 102, 0.3);
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        font-family: "Cinzel", serif;
        color: #ffe97f;
        text-shadow:
          0 0 4px #000,
          0 0 6px #ffd700;
        font-size: 0.95rem;
        margin: 0 auto 8px auto;
        width: fit-content;
        max-width: 100%;
      }
      .tibia-oficial-banner .icon-tibia {
        width: 20px;
        height: 20px;
        filter: drop-shadow(1px 1px 1px #000);
      }
    </style>
  </head>

  <body class="fundo-inicio">
    <div class="background"></div>
    <video autoplay muted loop class="fog">
      <source src="./Neblina.webm" type="video/webm" />
    </video>

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
        <!-- dropdown de idioma já existente -->
        <select
          id="language-select"
          style="margin-right: 16px; font-size: 0.9rem; padding: 4px"
        >
          <option value="pt">PT</option>
          <option value="en">EN</option>
          <option value="es">ES</option>
          <option value="pl">PL</option>
        </select>

        <!-- botões login / registrar -->
        <div class="botoes-acesso">
          <button type="button" class="btn-imagem login-btn">
            <img src="./icon-login.png" alt="Login" width="24" height="24" />
          </button>
          <button type="button" class="btn-imagem registrar-btn">
            <img
              src="./icon-registrar.png"
              alt="Registrar"
              width="24"
              height="24"
            />
          </button>
        </div>

        <nav class="nav-links">
          <div class="nav-esquerda">
            <a href="top.html">Top Streamers/Youtube</a>
            <a href="servicos.html">Serviços & Portfólio</a>
          </div>
          <div class="nav-direita">
            <a href="/">Início</a>
            <a href="regras.html">Regras/ban</a>
            <a href="sobre.html">Sobre</a>
            <a href="contato.html">Contato</a>
          </div>
        </nav>

        <!-- PLAYER MINIMALISTA -->
        <div class="radio-player">
          <button id="btn-playpause">►</button>
          <input
            type="range"
            id="slider-volume"
            min="0"
            max="1"
            step="0.01"
            value="1"
          />
        </div>
      </div>
    </header>

    <section class="ranking aba ativa espaco-pos-header" id="inicio">
      <div class="titulo-epico">
        <img
          src="./espada-esquerda.png"
          alt="Espada Esquerda"
          class="espada-decorativa esquerda"
        />
        <h1 class="titulo-ranking">Ranking de Servidores</h1>
        <img
          src="./espada-direita.png"
          alt="Espada Direita"
          class="espada-decorativa direita"
        />
      </div>

      <div class="filtros-ranking" style="margin-bottom: 20px">
        <input
          type="text"
          id="filtro-nome"
          placeholder="🔍 Buscar servidor..."
        />
        <select id="filtro-versao">
          <option value="">Todas as versões</option>
        </select>
        <select id="filtro-origem">
          <option value="">Todas as origens</option>
          <option value="Socket">Socket</option>
          <option value="HTML">HTML</option>
          <option value="Erro">Erro</option>
        </select>
      </div>

      <div class="tibia-oficial-banner">
        <span class="texto-tibia-oficial">
          <strong>Tibia Oficial:</strong> 13.258 jogadores online
        </span>
      </div>

      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th onclick="ordenarPor('Servidor')">Servidor ⬍</th>
              <th onclick="ordenarPor('Versão')">Versão ⬍</th>
              <th onclick="ordenarPor('Jogadores Online')">
                Jogadores Online ⬍
              </th>
              <th>Origem</th>
              <th>Observação</th>
            </tr>
          </thead>
          <tbody id="tabela-servidores"></tbody>
        </table>
      </div>
    </section>

    <!-- seu script principal -->
    <script type="module" src="./script.js"></script>
  </body>
</html>
