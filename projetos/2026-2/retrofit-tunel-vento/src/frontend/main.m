function varargout = main()
% =========================================================================
% DAS WIND TUNNEL v10.0 - SCADA DE AQUISIÇÃO E PROCESSAMENTO
% Túnel de Vento Subssônico Didático Italia Didacta PN 20 DNT
% Escola Politécnica PUCPR — Engenharia de Computação (TCC)
% Autor: Vinícius Matheus Sary de Lima
%
% PONTO DE ENTRADA PRINCIPAL (MAIN ENTRY POINT)
% Execução direta em alto desempenho compilado via MATLAB JIT
% =========================================================================

    fprintf('\n=================================================================\n');
    fprintf('  DAS WIND TUNNEL SCADA v10.0 — SISTEMA DE AQUISIÇÃO E CONTROLE   \n');
    fprintf('  Bancada: Italia Didacta PN 20 DNT | Escola Politécnica PUCPR   \n');
    fprintf('  Autor: Vinícius Matheus Sary de Lima                          \n');
    fprintf('=================================================================\n');
    fprintf('  [+] Inicializando Interface Fullscreen de Alta Performance...\n\n');

    try
        appInstance = app_v10();
        if nargout > 0
            varargout{1} = appInstance;
        end
        fprintf('  [OK] Sistema SCADA v10.0 iniciado com sucesso (60+ FPS)!\n\n');
    catch ME
        fprintf('  [ERRO] Falha na inicialização: %s\n', ME.message);
        rethrow(ME);
    end
end
