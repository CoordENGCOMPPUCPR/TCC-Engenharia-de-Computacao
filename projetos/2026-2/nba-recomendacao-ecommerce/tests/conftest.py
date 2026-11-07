"""Configuração compartilhada do pytest."""


def pytest_configure(config):
    # Testes de caixa branca: projetados a partir da estrutura interna do código (ramos,
    # exceções, funções privadas, estado interno). Para listá-los: pytest -m caixa_branca
    config.addinivalue_line(
        "markers",
        "caixa_branca: teste projetado a partir da estrutura interna do código",
    )
