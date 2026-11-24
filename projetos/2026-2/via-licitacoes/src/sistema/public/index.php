<?php
require_once __DIR__ . '/../src/config/config.php';
require_once __DIR__ . '/../src/core/Auth.php';

// Se já estiver logado, redireciona
if (Auth::logado()) {
    $dest = Auth::isAdmin() ? '/admin/index.php' : '/app/index.php';
    header('Location: ' . BASE_URL . $dest);
    exit;
}
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<link rel="icon" type="image/png" href="<?= BASE_URL ?>/assets/img/favicon.png">
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Via Licitações — Monitoramento Inteligente de Licitações Públicas</title>
<link rel="stylesheet" href="<?= BASE_URL ?>/assets/css/style.css">
</head>
<body>

<!-- ===================== HEADER ===================== -->
<header class="header">
  <div class="container header-inner">
    <a href="<?= BASE_URL ?>/index.php" class="logo">
      <img src="<?= BASE_URL ?>/assets/img/logo.png" alt="Via Licitações">
    </a>
    <nav class="nav">
      <a href="#recursos">Recursos</a>
      <a href="#como-funciona">Como funciona</a>
      <a href="#planos">Planos</a>
      <button class="btn btn-outline" onclick="abrirModalLogin()">Logar na plataforma</button>
    </nav>
  </div>
</header>

<!-- ===================== HERO ===================== -->
<section class="hero">
  <div class="container hero-inner">
    <div class="hero-text">
      <span class="badge">Monitoramento automatizado 24/7</span>
      <h1>Nunca mais perca uma licitação relevante para o seu negócio.</h1>
      <p>
        A Via Licitações centraliza editais de portais federais, estaduais e municipais,
        filtra por palavras-chave e região, e avisa você em tempo real quando surgir uma nova oportunidade.
      </p>
      <div class="hero-actions">
        <a href="#cadastro" class="btn btn-primary">Quero começar agora</a>
        <a href="#como-funciona" class="btn btn-ghost">Como funciona</a>
      </div>
    </div>
    <div class="hero-card">
      <div class="card-mock">
        <div class="mock-line w-60"></div>
        <div class="mock-line w-90"></div>
        <div class="mock-line w-80"></div>
        <div class="mock-line w-70"></div>
        <div class="mock-tag">Nova licitação compatível com seu interesse</div>
      </div>
    </div>
  </div>
</section>

<!-- ===================== RECURSOS ===================== -->
<section id="recursos" class="section">
  <div class="container">
    <h2 class="section-title">Tudo o que sua empresa precisa em um só lugar</h2>
    <div class="grid-3">
      <div class="feature-card">
        <div class="feature-icon">🔎</div>
        <h3>Centralização de editais</h3>
        <p>Reunimos oportunidades de múltiplos portais governamentais em uma única plataforma.</p>
      </div>
      <div class="feature-card">
        <div class="feature-icon">🎯</div>
        <h3>Filtros por palavra-chave e região</h3>
        <p>Cadastre suas palavras-chave de interesse e as regiões onde atua. Nós filtramos por você.</p>
      </div>
      <div class="feature-card">
        <div class="feature-icon">🔔</div>
        <h3>Notificações automáticas</h3>
        <p>Seja avisado sempre que surgir uma nova licitação compatível com seu perfil.</p>
      </div>
      <div class="feature-card">
        <div class="feature-icon">📄</div>
        <h3>Leitura de PDFs</h3>
        <p>Extraímos automaticamente informações dos editais em PDF, mesmo os não estruturados.</p>
      </div>
      <div class="feature-card">
        <div class="feature-icon">⭐</div>
        <h3>Marque seus interesses</h3>
        <p>Organize internamente as licitações que deseja disputar e acompanhe cada uma.</p>
      </div>
      <div class="feature-card">
        <div class="feature-icon">📊</div>
        <h3>Histórico e rastreabilidade</h3>
        <p>Tudo registrado: consultas, notificações e o andamento das oportunidades.</p>
      </div>
    </div>
  </div>
</section>

<!-- ===================== COMO FUNCIONA ===================== -->
<section id="como-funciona" class="section section-alt">
  <div class="container">
    <h2 class="section-title">Como funciona</h2>
    <div class="steps">
      <div class="step"><span>1</span><h4>Cadastre-se</h4><p>Solicite acesso e nosso time entra em contato.</p></div>
      <div class="step"><span>2</span><h4>Configure interesses</h4><p>Informe palavras-chave e regiões de atuação da sua empresa.</p></div>
      <div class="step"><span>3</span><h4>Receba oportunidades</h4><p>Nós monitoramos e avisamos você em tempo real.</p></div>
      <div class="step"><span>4</span><h4>Dispute com vantagem</h4><p>Decida rápido, com informação organizada e confiável.</p></div>
    </div>
  </div>
</section>

<!-- ===================== PLANOS ===================== -->
<section id="planos" class="section">
  <div class="container">
    <h2 class="section-title">Planos para todos os tamanhos de empresa</h2>
    <p class="section-subtitle">Fale com nosso time e descubra o plano ideal para o seu negócio.</p>
    <div class="grid-3">
      <div class="plan-card">
        <h3>Essencial</h3>
        <p class="plan-desc">Para quem está começando a disputar licitações.</p>
        <ul>
          <li>✔ Monitoramento de 1 palavra-chave</li>
          <li>✔ 1 região de interesse</li>
          <li>✔ Alertas por e-mail</li>
        </ul>
        <a href="#cadastro" class="btn btn-outline">Solicitar contato</a>
      </div>
      <div class="plan-card destaque">
        <span class="tag-popular">Mais procurado</span>
        <h3>Profissional</h3>
        <p class="plan-desc">Para empresas que já disputam com frequência.</p>
        <ul>
          <li>✔ Até 5 palavras-chave monitoradas</li>
          <li>✔ Múltiplas regiões</li>
          <li>✔ Histórico completo</li>
          <li>✔ Marcação de interesses</li>
        </ul>
        <a href="#cadastro" class="btn btn-primary">Solicitar contato</a>
      </div>
      <div class="plan-card">
        <h3>Corporativo</h3>
        <p class="plan-desc">Para operações robustas e multiunidade.</p>
        <ul>
          <li>✔ Palavras-chave ilimitadas</li>
          <li>✔ Suporte dedicado</li>
          <li>✔ Integrações personalizadas</li>
        </ul>
        <a href="#cadastro" class="btn btn-outline">Falar com especialista</a>
      </div>
    </div>
  </div>
</section>

<!-- ===================== CADASTRO (LEAD) ===================== -->
<section id="cadastro" class="section section-alt">
  <div class="container form-wrapper">
    <div class="form-info">
      <h2>Pronto para crescer com licitações?</h2>
      <p>Preencha o formulário e nosso time entrará em contato para ativar seu acesso à plataforma.</p>
    </div>
    <form id="formCadastro" class="form-card">
      <h3>Cadastre-se</h3>
      <div class="form-group">
        <label>Nome completo *</label>
        <input type="text" name="nome" required maxlength="150">
      </div>
      <div class="form-group">
        <label>E-mail *</label>
        <input type="email" name="email" required maxlength="150">
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>Telefone *</label>
          <input type="text" name="telefone" required maxlength="20" placeholder="(00) 00000-0000">
        </div>
        <div class="form-group">
          <label>CNPJ da empresa *</label>
          <input type="text" name="cnpj" required maxlength="18" placeholder="00.000.000/0000-00">
        </div>
      </div>
      <button type="submit" class="btn btn-primary btn-block">Enviar cadastro</button>
      <p class="form-hint">Ao enviar, você concorda em ser contatado pela equipe Via Licitações.</p>
      <div id="formFeedback" class="form-feedback"></div>
    </form>
  </div>
</section>

<!-- ===================== FOOTER ===================== -->
<footer class="footer">
  <div class="container footer-inner">
    <img src="<?= BASE_URL ?>/assets/img/logo.png" alt="Via Licitações" class="footer-logo">
    <p>© <?= date('Y') ?> Via Licitações. Todos os direitos reservados.</p>
  </div>
</footer>

<!-- ===================== MODAL LOGIN ===================== -->
<div id="modalLogin" class="modal" aria-hidden="true">
  <div class="modal-backdrop" onclick="fecharModalLogin()"></div>
  <div class="modal-content">
    <button class="modal-close" onclick="fecharModalLogin()" aria-label="Fechar">×</button>
    <h3>Entrar na plataforma</h3>
    <p class="modal-sub">Acesse com seu e-mail e senha.</p>
    <form id="formLogin">
      <div class="form-group">
        <label>E-mail</label>
        <input type="email" name="email" required autocomplete="username">
      </div>
      <div class="form-group">
        <label>Senha</label>
        <input type="password" name="senha" required autocomplete="current-password">
      </div>
      <button type="submit" class="btn btn-primary btn-block">Entrar</button>
      <div id="loginFeedback" class="form-feedback"></div>
    </form>
  </div>
</div>

<script>
  const BASE_URL = "<?= BASE_URL ?>";
</script>
<script src="<?= BASE_URL ?>/assets/js/main.js"></script>

</body>
</html>