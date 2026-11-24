from pathlib import Path

# Pasta atual = via-licitacoes
root = Path(".")

# Estrutura de diretórios
directories = [
    "public/assets/css",
    "public/assets/js",
    "public/assets/img",
    "public/admin",
    "public/app",
    "public/api",

    "src/config",
    "src/core",
    "src/models",
    "src/helpers",

    "storage/logs",
    "storage/pdfs",
]

# Arquivos
files = [
    # Public
    "public/index.php",
    "public/login.php",
    "public/cadastro.php",
    "public/logout.php",

    # Assets
    "public/assets/css/style.css",
    "public/assets/css/dashboard.css",
    "public/assets/js/main.js",
    "public/assets/js/dashboard.js",
    "public/assets/img/logo.png",

    # Admin
    "public/admin/index.php",
    "public/admin/usuarios.php",
    "public/admin/empresas.php",
    "public/admin/licitacoes.php",
    "public/admin/logs.php",
    "public/admin/leads.php",

    # App
    "public/app/index.php",
    "public/app/licitacoes.php",
    "public/app/interesses.php",
    "public/app/regioes.php",
    "public/app/empresa.php",
    "public/app/notificacoes.php",
    "public/app/perfil.php",

    # API
    "public/api/auth.php",
    "public/api/interesses.php",
    "public/api/licitacoes.php",
    "public/api/ingest.php",
    "public/api/notificacoes.php",

    # Source
    "src/config/database.php",
    "src/config/config.php",

    "src/core/Auth.php",
    "src/core/Router.php",
    "src/core/Response.php",
    "src/core/Validator.php",

    "src/models/Usuario.php",
    "src/models/Empresa.php",
    "src/models/Licitacao.php",
    "src/models/Interesse.php",
    "src/models/Notificacao.php",
    "src/models/Log.php",

    "src/helpers/functions.php",

    # Root
    ".htaccess",
    "README.md",
]


def create_structure():
    print("Criando diretórios...")

    for directory in directories:
        path = root / directory
        path.mkdir(parents=True, exist_ok=True)
        print(f"[DIR]  {path}")

    print("\nCriando arquivos...")

    for file in files:
        path = root / file

        # Cria o diretório pai caso ainda não exista
        path.parent.mkdir(parents=True, exist_ok=True)

        # Não sobrescreve arquivos existentes
        if not path.exists():
            path.touch()
            print(f"[FILE] {path}")
        else:
            print(f"[SKIP] {path} já existe")

    print("\nEstrutura criada com sucesso!")


if __name__ == "__main__":
    create_structure()
