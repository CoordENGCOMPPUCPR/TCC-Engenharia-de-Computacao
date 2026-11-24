<h1> Via Licitações </h1>

<p align="center">
<strong>Sistema Web de Inteligência em Licitações Públicas com Automação RPA</strong>
</p>

<p align="center">
<img src="https://img.shields.io/badge/PHP-Backend-777BB4?style=flat-square&logo=php&logoColor=white">
<img src="https://img.shields.io/badge/Python-RPA-3776AB?style=flat-square&logo=python&logoColor=white">
<img src="https://img.shields.io/badge/MySQL-Database-4479A1?style=flat-square&logo=mysql&logoColor=white">
<img src="https://img.shields.io/badge/JavaScript-Frontend-F7DF1E?style=flat-square&logo=javascript&logoColor=black">
<img src="https://img.shields.io/badge/PUCPR-TCC-orange?style=flat-square">
</p>

<h2>01. Sobre o projeto</h2>

<p>
O <strong>Via Licitações</strong> é uma plataforma de inteligência em licitações públicas desenvolvida para auxiliar empresas na identificação, consulta e gestão de oportunidades em processos de compras e contratações públicas.
</p>

<p>
A solução integra um sistema web desenvolvido em PHP, um banco de dados MySQL e uma automação RPA desenvolvida em Python, responsável pela coleta e processamento de informações de licitações.
</p>

<h2>02. Funcionalidades</h2>

<table>
<tr>
<td width="50%">
<strong>Gestão de usuários</strong><br>
Autenticação, cadastro e gerenciamento de usuários e equipes.
</td>
<td width="50%">
<strong>Gestão de empresas</strong><br>
Cadastro de empresas e atividades econômicas.
</td>
</tr>
<tr>
<td>
<strong>Consulta de licitações</strong><br>
Pesquisa e filtragem por palavras-chave e regiões.
</td>
<td>
<strong>Gestão de oportunidades</strong><br>
Acompanhamento de licitações, comentários e tarefas.
</td>
</tr>
<tr>
<td>
<strong>Automação RPA</strong><br>
Coleta e processamento automatizado de informações.
</td>
<td>
<strong>Administração</strong><br>
Notificações, importações, logs e gerenciamento de dados.
</td>
</tr>
</table>

<h2>03. Arquitetura tecnológica</h2>

<h3>Sistema Web</h3>

<table>
<tr><th>Tecnologia</th><th>Aplicação</th></tr>
<tr><td>PHP</td><td>Backend</td></tr>
<tr><td>HTML5</td><td>Estrutura das interfaces</td></tr>
<tr><td>CSS3</td><td>Estilização</td></tr>
<tr><td>JavaScript</td><td>Interatividade</td></tr>
<tr><td>MySQL</td><td>Banco de dados</td></tr>
<tr><td>PDO</td><td>Comunicação com o banco</td></tr>
<tr><td>XAMPP</td><td>Ambiente local de execução</td></tr>
</table>

<h3>Automação RPA</h3>

<table>
<tr><th>Tecnologia</th><th>Aplicação</th></tr>
<tr><td>Python</td><td>Desenvolvimento da automação</td></tr>
<tr><td>Pandas</td><td>Manipulação de dados</td></tr>
<tr><td>BeautifulSoup</td><td>Análise de HTML</td></tr>
<tr><td>Selenium</td><td>Automação web</td></tr>
<tr><td>WebDriver Manager</td><td>Gerenciamento do ChromeDriver</td></tr>
</table>

<h3>Banco de dados</h3>

<p><strong>Banco:</strong> <code>via_licitacoes</code></p>
<p><strong>SGBD:</strong> MySQL</p>
<p><strong>Estrutura:</strong> 16 tabelas relacionais.</p>

<table>
<tr><th>Domínio</th><th>Tabelas</th></tr>
<tr><td>Empresas e CNAEs</td><td>empresas, cnaes_catalogo, cnaes_interesse</td></tr>
<tr><td>Licitações</td><td>licitacoes, documentos_licitacao, fontes_coleta</td></tr>
<tr><td>Oportunidades</td><td>interesses_licitacoes, interesses_comentarios, interesses_tarefas</td></tr>
<tr><td>Inteligência comercial</td><td>leads</td></tr>
<tr><td>Preferências</td><td>palavras_interesse, regioes_interesse</td></tr>
<tr><td>Usuários e comunicação</td><td>usuarios, notificacoes</td></tr>
<tr><td>Auditoria</td><td>logs_execucao, importacoes</td></tr>
</table>

<h2>04. Estrutura do repositório</h2>

<pre>
via-licitacoes/
│
├── data/
│ ├── datasets/
│ └── exemplos/
│ └── via_licitacoes.sql
│
├── src/
│ ├── sistema/
│ │ ├── public/
│ │ │ ├── admin/
│ │ │ ├── api/
│ │ │ ├── app/
│ │ │ └── assets/
│ │ │ ├── css/
│ │ │ ├── img/
│ │ │ └── js/
│ │ │
│ │ ├── src/
│ │ │ ├── config/
│ │ │ ├── core/
│ │ │ ├── helpers/
│ │ │ └── models/
│ │ │
│ │ ├── .htaccess
│ │ └── README.md
│ │
│ └── automacao/
│ ├── main.py
│ ├── automacao.bat
│ └── requirements.txt
│
├── tests/
│ ├── integracao/
│ └── unitarios/
│
└── README.md
</pre>

<h2>05. Requisitos</h2>

<table>
<tr><th>Sistema Web</th><th>Automação RPA</th></tr>
<tr>
<td>
<ul>
<li>Windows ou compatível</li>
<li>XAMPP</li>
<li>Apache</li>
<li>PHP com PDO MySQL</li>
<li>MySQL ou MariaDB</li>
<li>Navegador moderno</li>
</ul>
</td>
<td>
<ul>
<li>Python 3</li>
<li>Google Chrome</li>
<li>requirements.txt</li>
<li>Conexão com a internet</li>
</ul>
</td>
</tr>
</table>

<h2>06. Instalação do sistema web</h2>

<h3>1. Preparar o ambiente</h3>

<p>Instale o <a href="https://www.apachefriends.org/">XAMPP</a> e inicie Apache e MySQL.</p>

<h3>2. Configurar os arquivos</h3>

<p>Copie o conteúdo de <code>src/sistema/</code> para:</p>

<pre>C:\xampp\htdocs\via-licitacoes</pre>

<h3>3. Criar o banco de dados</h3>

<p>Acesse o phpMyAdmin:</p>

<p><a href="http://localhost/phpmyadmin">http://localhost/phpmyadmin</a></p>

<ol>
<li>Crie o banco <code>via_licitacoes</code>.</li>
<li>Selecione o banco criado.</li>
<li>Acesse a opção Importar.</li>
<li>Selecione <code>data/exemplos/via_licitacoes.sql</code>.</li>
<li>Execute a importação.</li>
</ol>

<h3>4. Configurar a conexão</h3>

<p>Arquivo: <code>src/config/database.php</code></p>

<p>Configure host, banco de dados, usuário, senha e charset conforme o ambiente.</p>

<h3>5. Configurar a aplicação</h3>

<p>Arquivo: <code>src/config/config.php</code></p>

<p>Verifique ambiente, depuração, URL base, caminhos físicos e fuso horário.</p>

<h3>6. Executar o sistema</h3>

<p>Acesse:</p>

<p><a href="http://localhost/via-licitacoes/public">http://localhost/via-licitacoes/public</a></p>

<p>Utilize uma conta previamente configurada no banco de dados. O repositório não disponibiliza credenciais administrativas.</p>

<h2>07. Instalação da automação RPA</h2>

<p>Abra o PowerShell na pasta da automação:</p>

<pre>cd C:\PUCPR-TCC\TCC-Engenharia-de-Computacao\projetos\2026-2\via-licitacoes\src\automacao</pre>

<p><strong>Criação do ambiente virtual:</strong></p>

<pre>python -m venv .venv</pre>

<p><strong>Ativação:</strong></p>

<pre>.\.venv\Scripts\Activate.ps1</pre>

<p><strong>Instalação das dependências:</strong></p>

<pre>pip install -r requirements.txt</pre>

<p><strong>Execução:</strong></p>

<pre>python main.py</pre>

<p>Também está disponível o arquivo <code>automacao.bat</code> para inicialização em ambiente Windows.</p>

<h2>08. Integração dos componentes</h2>

<p>O funcionamento da solução contempla o seguinte fluxo:</p>

<p align="center">
<strong>Automação Python</strong><br>
↓<br>
Coleta e processamento de licitações<br>
↓<br>
<strong>Banco de dados MySQL</strong><br>
↓<br>
<strong>Sistema Web PHP</strong><br>
↓<br>
Consulta e gerenciamento de oportunidades
</p>

<p>A comunicação entre os componentes utiliza os mecanismos de integração definidos na implementação do sistema.</p>

<h2>09. Segurança</h2>

<ul>
<li>Não versionar senhas, tokens ou credenciais.</li>
<li>Proteger dados pessoais e comerciais.</li>
<li>Utilizar configurações externas para informações sensíveis.</li>
<li>Não utilizar contas de demonstração em produção.</li>
<li>Desabilitar a exibição de erros em produção.</li>
<li>Restringir o acesso a diretórios internos e arquivos de configuração.</li>
</ul>

<h2>10. Testes</h2>

<pre>
tests/
├── integracao/
└── unitarios/
</pre>

<ul>
<li><strong>Unitários:</strong> validação de funcionalidades isoladas.</li>
<li><strong>Integração:</strong> verificação da comunicação entre sistema web, banco de dados e automação.</li>
</ul>

<h2>11. Organização acadêmica</h2>

<table>
<tr><td><strong>Projeto</strong></td><td>Via Licitações</td></tr>
<tr><td><strong>Curso</strong></td><td>Engenharia de Computação</td></tr>
<tr><td><strong>Instituição</strong></td><td>Pontifícia Universidade Católica do Paraná (PUCPR)</td></tr>
<tr><td><strong>Disciplina</strong></td><td>Projeto Final de Curso – IOPT</td></tr>
<tr><td><strong>Etapa</strong></td><td>4º Bimestre – Implementação Final</td></tr>
<tr><td><strong>Período</strong></td><td>2026/2</td></tr>
<tr><td><strong>Versão sugerida</strong></td><td>v1.0.0-final</td></tr>
</table>

<p>A documentação acadêmica formal, relatórios, apresentações e materiais de defesa devem ser submetidos pelo ambiente institucional Canvas, conforme as orientações da coordenação.</p>

<p>Este repositório destina-se ao versionamento e compartilhamento dos códigos-fonte e materiais técnicos necessários à execução do software.</p>

<h2>12. Licença</h2>

<p>Consulte o arquivo <code>LICENSE</code> na raiz do repositório para conhecer os termos de utilização e distribuição aplicáveis ao projeto.</p>

<p align="center">
<strong>VIA LICITAÇÕES</strong><br>
Sistema de Inteligência em Licitações Públicas<br><br>
Trabalho de Conclusão de Curso<br>
Engenharia de Computação — PUCPR<br>
2026/2
</p>
