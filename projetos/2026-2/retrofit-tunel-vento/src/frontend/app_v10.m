classdef app_v10 < matlab.apps.AppBase

    % =========================================================================
    % DAS WIND TUNNEL v10.0 - SISTEMA SCADA DE AQUISIÇÃO E CONTROLE
    % Túnel de Vento Italia Didacta PN 20 DNT | PUCPR | Vinícius Matheus Sary de Lima
    % Focado no Escopo Didático de Graduação, Instrumentação Real & Persistência Segura
    % =========================================================================

    properties (Access = public)
        UIFigure            matlab.ui.Figure
        TabGroup            matlab.ui.container.TabGroup
        TitleLabel          matlab.ui.control.Label
        StartButton         matlab.ui.control.Button
        DemoButton          matlab.ui.control.Button
        StopButton          matlab.ui.control.Button
        TaraButton          matlab.ui.control.Button
        ExportButton        matlab.ui.control.Button
        ExitButton          matlab.ui.control.Button
        StatusLabel         matlab.ui.control.Label
        StatusLamp          matlab.ui.control.Lamp

        % --- TAB 1: TELA SINÓTICA ---
        TabSinotica
        AxesSinotica
        LampRPM
        LampTorque
        LampLift
        LampDrag
        LampHinge
        LampPitot
        LampVenturi
        SinRPMVal
        SinTorqueVal
        SinLiftVal
        SinDragVal
        SinHingeVal
        SinVelVal
        SinFlowVal
        SinTempoVal
        SinAmostrasVal
        SinModoVal
        
        % Painéis de Operação (Simulação vs. Leitura Real)
        PanelControlesSimulacao
        LabelAvisoSimulacao
        SliderRPM
        SliderAlpha
        SliderRPMValLabel
        SliderAlphaValLabel
        BtnPresetZero
        PanelAvisoHardware
        LabelAvisoHardware
        LabelControleRPM
        LabelControleAlpha
        SinCardPanels
        SinStatusPanel

        % --- TAB 2: FORÇAS AERODINÂMICAS (BALANÇA 514QD) ---
        TabForcas
        GaugeLift
        GaugeDrag
        GaugeHinge
        LabelTitleLift
        LabelTitleDrag
        LabelTitleHinge
        LabelLiftVal
        LabelDragVal
        LabelHingeVal
        PanelCardLift
        PanelCardDrag
        PanelCardHinge
        AxesForcasUnificado
        AxesLift
        AxesDrag
        AxesHinge
        PanelBalanca
        LabelResumoLift
        LabelResumoDrag
        LabelResumoHinge
        LabelNotaDidaticaForcas

        % Barra de Filtros Interativos (Estilo PowerBI)
        PanelFiltroForcas
        CbPlotLift
        CbPlotDrag
        CbPlotHinge
        BtnPlotTodas
        BtnPlotNenhuma

        % --- TAB 3: MANOMETRIA & PRESSÕES DIFERENCIAIS (TUBO EM U) ---
        TabFluidos
        PanelGaugePitot
        PanelGaugeVenturi
        PanelManometrosU
        PanelPlotsPressao
        GaugePitot
        GaugeVenturi
        LabelTitleGaugePitot
        LabelTitleGaugeVenturi
        LabelPitotVal
        LabelVenturiVal
        AxesManometroPitot
        AxesManometroVenturi
        LabelManoPitotTitle
        LabelManoPitotVal
        LabelManoPitotLevels
        LabelManoVenturiTitle
        LabelManoVenturiVal
        LabelManoVenturiLevels
        AxesPitot
        AxesVenturi

        % --- TAB 4: DATA LOGGER & HISTÓRICO ---
        TabLogger
        AxesLogger
        LogCanalDropdown
        ClearLogButton
        LogStatMin
        LogStatMean
        LogStatMax
        LogStatStd

        % --- TAB 5: ENSAIO DE VENTILADORES (MÁQUINAS DE FLUXO) ---
        TabVentilador
        LabelVentTitle
        LabelVentSub
        PanelVentCards
        CardVentRPMVal
        CardVentRPMSub
        CardVentTorqueVal
        CardVentTorqueSub
        CardVentPitotVal
        CardVentPitotSub
        CardVentVenturiVal
        CardVentVenturiSub
        AxesVentilador

        % --- TAB 6: CONFIGURAÇÕES & TEORIA ---
        TabConfig
        CfgTempField
        CfgPatmField
        CfgRhoField
        CfgAreaField
        CfgChordField
        CfgDVenturiField
        CfgdVenturiField
        CfgKRPMField
        CfgOffsetRPMField
        CfgKTorqueField
        CfgKLiftField
        CfgKDragField
        CfgKHingeField
        CfgAlphaField
        CfgTaxaLogDropdown
        CfgTaxaLogInfoLabel
        CfgTaraPitotField
        CfgTaraVenturiField
        CfgAplicarButton
        CfgInfoLabel
        BtnManualOperacao
        
        % Switches de Habilitação de Canais (Configurações & Bancada)
        SwCanalRPM          matlab.ui.control.Switch
        SwCanalTorque       matlab.ui.control.Switch
        SwCanalLift         matlab.ui.control.Switch
        SwCanalDrag         matlab.ui.control.Switch
        SwCanalHinge        matlab.ui.control.Switch
        SwCanalPitot        matlab.ui.control.Switch
        SwCanalVenturi      matlab.ui.control.Switch
        BtnPresetTodos      matlab.ui.control.Button
        BtnPresetBancada    matlab.ui.control.Button
        BtnPresetForcas     matlab.ui.control.Button
        BtnRestaurarPadrao  matlab.ui.control.Button
    end

    properties (Access = private)
        % Objeto DAQ e Timer Desacoplado de IHM
        dq
        dqCtr
        TimerPrincipal      timer
        sistemaAtivo        logical = false
        modoDemo            logical = true
        HeaderPanel         matlab.ui.container.Panel
        FooterPanel         matlab.ui.container.Panel
        frameOcupado        logical = false
        
        % Otimização de Memória: Buffer Central Pré-Alocado
        dados_buffer        double  = zeros(50000, 13)
        tempo_buffer        double  = zeros(50000, 1)
        buffer_idx          double  = 0
        dados_finais        double  = []
        tempo_final         double  = []
        
        % Temporização e Contadores
        tempo_inicio        uint64
        ultimo_tic          uint64
        tempo_decorrido     double  = 0.0
        tick_count          double  = 0
        
        % Dinâmica do Simulador Sintético
        simCurrentRPM       double  = 0.0
        simTargetRPM        double  = 0.0

        % Elementos Visuais Dinâmicos da Tela Sinótica
        AirfoilPatch
        AirfoilTextAlpha
        AirfoilBaseX
        AirfoilBaseY
        AirfoilCenterX      = 6.05
        AirfoilCenterY      = 3.5

        % Animação Visual Dinâmica em Tempo Real
        rotor_angle         double  = 0.0
        RotorBladesPlot
        RotorHubPlot
        WindParticlesPlot
        wind_phase          double  = 0.0
        wind_x              double  = [linspace(0.5, 9.5, 10), linspace(0.9, 9.9, 10), linspace(0.3, 9.3, 10), linspace(0.7, 9.7, 10), linspace(0.2, 9.2, 10), linspace(0.8, 9.8, 10)];
        wind_y_base         double  = [repmat(2.4, 1, 10), repmat(2.8, 1, 10), repmat(3.2, 1, 10), repmat(3.8, 1, 10), repmat(4.2, 1, 10), repmat(4.6, 1, 10)];
        LiftVectorLine
        LiftVectorHead
        LiftVectorText
        DragVectorLine
        DragVectorHead
        DragVectorText

        % Elementos Visuais Dinâmicos dos Manômetros Virtuais em U
        ManometroPitotPatchL
        ManometroPitotPatchR
        ManometroPitotMeniscoL
        ManometroPitotMeniscoR
        txtCotaPitot
        ManometroVenturiPatchL
        ManometroVenturiPatchR
        ManometroVenturiMeniscoL
        ManometroVenturiMeniscoR
        txtCotaVenturi

        % Linhas Animadas (animatedline - Alta Performance)
        aLineLift
        aLineDrag
        aLineHinge
        aLinePitot
        aLineVenturi
        aLineLogger
        aLineVentPitot
        aLineVentVenturi
        aLineVentTorque
        ultimo_idx_forcas      double = 0
        ultimo_idx_fluidos     double = 0
        ultimo_idx_ventilador  double = 0

        % Sinais Filtrados em Tempo Real (Filtro EMA)
        count_anterior      = 0
        rpm_suavizado       = 0
        torque_suavizado    = 0
        lift_suavizado      = 0
        drag_suavizado      = 0
        hinge_suavizado     = 0
        pitot_suavizado     = 0
        venturi_suavizado   = 0

        % Parâmetros Físicos & Calibração
        alpha               = 0.08
        rho_ar              = 1.103
        area_ref            = 0.0144
        comprimento_ref     = 0.120
        D_venturi           = 0.050
        d_venturi           = 0.025
        JANELA_TEMPO        = 20
        angulo_ataque       = 0.0
        RPM_MAX_FISICO      = 5000
        pulsos_por_volta    = 4

        % Offsets de Tara & Fatores de Escala K
        tara_torque         = 0.0
        tara_lift           = 0.0
        tara_drag           = 0.0
        tara_hinge          = 0.0
        tara_pitot          = 0.8
        tara_venturi        = 0.8
        tensao_suavizada_torque  = 0.0
        tensao_suavizada_lift    = 0.0
        tensao_suavizada_drag    = 0.0
        tensao_suavizada_hinge   = 0.0
        tensao_suavizada_pitot   = 0.8
        tensao_suavizada_venturi = 0.8
        taxa_log_hz         = 1000
        tempo_hardware_base = 0
        fator_escala_rpm    = 0.9489
        offset_rpm          = 23.5
        fator_escala_torque = 1.0
        fator_escala_lift   = 1.0
        fator_escala_drag   = 1.0
        fator_escala_hinge  = 1.0
        pressao_offset      = 0.8
        pressao_escala      = 390.625

        % Habilitação Individual de Canais (Bancada & Testes)
        habilitarCanalRPM       logical = true
        habilitarCanalTorque    logical = true
        habilitarCanalLift      logical = true
        habilitarCanalDrag      logical = true
        habilitarCanalHinge     logical = true
        habilitarCanalPitot     logical = true
        habilitarCanalVenturi   logical = true

        % Modos Legados de Bancada (mantidos para compatibilidade)
        modoBancadaApenasLift    = false
        modoBancadaApenasRPM     = false
        modoBancadaRPMTorque     = false
        % Buffer de Medição Estabilizada para Tacômetro (Precisão +/- 1 RPM com Filtro Mediano)
        TAMANHO_JANELA_RPM       = 40
        buffer_rpm_counts        = zeros(1, 40)
        buffer_rpm_recents       = zeros(1, 5)
        count_unwrapped          = 0
        rpm_estavel_display      = 0
        rpm_display_valor        = 0.0
        rpm_display_tick         = 0
    end

    methods (Access = private)

        % =================================================================
        % 1. SIMULADOR FÍSICO REALISTA (MODO DEMO / SEM HARDWARE)
        % Baseado na Aerodinâmica Não-Linear do Perfil NACA 0012
        % =================================================================
        function dados = gerarDadosSinteticos(app, dt)
            if nargin < 2 || dt <= 0
                dt = 0.040;
            end

            % Inércia do motor CA e ventilador (Resposta de 1ª ordem contínua)
            if app.simTargetRPM <= 0
                app.simCurrentRPM = app.simCurrentRPM + (0 - app.simCurrentRPM) * 0.08;
                if app.simCurrentRPM < 0.5
                    app.simCurrentRPM = 0.0;
                end
            else
                app.simCurrentRPM = app.simCurrentRPM + (app.simTargetRPM - app.simCurrentRPM) * 0.08;
                if abs(app.simTargetRPM - app.simCurrentRPM) < 0.5
                    app.simCurrentRPM = app.simTargetRPM;
                end
            end

            rpm = app.simCurrentRPM;
            noise_rpm = (rand() - 0.5) * 8.0 * (rpm > 10);
            rpm_sintetico = max(0, rpm + noise_rpm);

            % Velocidade do ar no duto de ensaio: correlação experimental v = 0.0094 * RPM
            v_ar = 0.0094 * rpm_sintetico;
            q_din = 0.5 * app.rho_ar * (v_ar^2);

            % Modelo de Forças Aerodinâmicas NACA 0012
            alpha_deg = app.angulo_ataque;
            alpha_rad = (alpha_deg * pi) / 180;
            
            % Sustentação Não-Linear com Estol Suave a ~16°
            if abs(alpha_deg) <= 15.0
                cl = 2 * pi * 0.88 * sin(alpha_rad);
            elseif alpha_deg > 15.0
                cl = 1.35 * exp(-0.15 * (alpha_deg - 15.0)) * cos(alpha_rad);
            else
                cl = -1.35 * exp(-0.15 * (abs(alpha_deg) - 15.0)) * cos(alpha_rad);
            end
            
            % Arrasto Parabólico com Aumento Pós-Estol
            cd0 = 0.008;
            cd = cd0 + (cl^2) / (pi * 0.85 * 3.5);
            if abs(alpha_deg) > 15.0
                cd = cd + 0.06 * (abs(alpha_deg) - 15.0)^1.4;
            end
            
            % Cálculo das Forças Físicas em Newtons
            lift_force  = cl * q_din * app.area_ref + (rand() - 0.5) * 0.08;
            drag_force  = cd * q_din * app.area_ref + (rand() - 0.5) * 0.04;

            % Momento de Dobradiça (Hinge Moment) em N.m
            % Na balança mecânica 3D do túnel, o pivô de fixação fica recuado em relação ao
            % Centro Aerodinâmico (25% corda), gerando braço de alavanca mecânico (d_x ~ 28 mm):
            % M = -(x_pivot - x_ac) * Lift + M_stall
            d_x = 0.028; % Braço mecânico efetivo (28 mm)
            if abs(alpha_deg) <= 15.0
                % Regime linear pré-estol: momento estabilizador restaurador proporcional à sustentação
                hinge_mom = -d_x * lift_force - 0.015 * q_din * app.area_ref * sin(alpha_rad);
            else
                % Regime pós-estol: recuo do centro de pressão gera momento picante acentuado
                extra_stall = 0.06 * sign(alpha_deg) * (abs(alpha_deg) - 15.0)^1.2;
                hinge_mom = -d_x * lift_force - extra_stall * q_din * app.area_ref;
            end
            if v_ar > 0.5
                hinge_mom = hinge_mom + (rand() - 0.5) * 0.004;
            else
                hinge_mom = 0.0;
            end

            % Dinâmica de Pressões Diferenciais
            dP_pitot   = q_din + (rand() - 0.5) * 2.0;
            if dP_pitot < 0, dP_pitot = 0; end
            
            % Equação da Continuidade / Perda de Carga no Venturi
            ratio_venturi = (app.D_venturi / app.d_venturi)^2;
            dP_venturi = q_din * (ratio_venturi^2 - 1) * 0.25 + (rand() - 0.5) * 3.0;
            if dP_venturi < 0, dP_venturi = 0; end

            % Torque do Motor no Eixo (Potência Mecânica)
            omega = (2 * pi * rpm_sintetico) / 60.0;
            if omega > 1.0
                torque = 0.00008 * (rpm_sintetico^1.8) + (rand() - 0.5) * 0.02;
            else
                torque = 0.0;
            end

            % Conversão para Grandezas Condicionadas
            dados = { ...
                rpm_sintetico, ...
                torque / max(app.fator_escala_torque, 1e-4), ...
                lift_force / max(app.fator_escala_lift, 1e-4), ...
                drag_force / max(app.fator_escala_drag, 1e-4), ...
                hinge_mom / max(app.fator_escala_hinge, 1e-4), ...
                (dP_pitot / app.pressao_escala) + app.tara_pitot, ...
                (dP_venturi / app.pressao_escala) + app.tara_venturi};
        end

        % =================================================================
        % 2. INGESTÃO DE SINAIS, FILTRAGEM EMA & PERSISTÊNCIA EM BUFFER
        % =================================================================
        function processarFrame(app, dados, dt, renderAgora, gravarBuffer)
            if nargin < 4
                renderAgora = true;
            end
            if nargin < 5
                gravarBuffer = true;
            end
            try
                app.tick_count = app.tick_count + 1;

                % --- CANAL 1: Tacômetro Indutivo RPM (Janela 2.0s + Filtro Mediano Anti-Jitter) ---
                if app.modoDemo
                    app.rpm_suavizado = dados{1};
                else
                    count_atual = dados{1};
                    
                    if app.count_anterior == 0
                        % Inicialização na primeira leitura de pulsos
                        app.count_anterior = count_atual;
                        app.count_unwrapped = 0;
                        app.buffer_rpm_counts = repmat(0, 1, app.TAMANHO_JANELA_RPM);
                        app.buffer_rpm_recents = zeros(1, 5);
                        app.rpm_suavizado = 0;
                        app.rpm_estavel_display = 0;
                    else
                        % Diferencial acumulado com proteção de rollover 32-bit
                        delta_pulsos = count_atual - app.count_anterior;
                        if delta_pulsos < 0
                            delta_pulsos = delta_pulsos + 2^32;
                        end
                        app.count_anterior = count_atual;
                        app.count_unwrapped = app.count_unwrapped + delta_pulsos;
                        
                        % Janela móvel circular de 2.0 s (40 blocos a 20 Hz)
                        app.buffer_rpm_counts = [app.buffer_rpm_counts(2:end), app.count_unwrapped];
                        
                        delta_count_janela = app.buffer_rpm_counts(end) - app.buffer_rpm_counts(1);
                        dt_janela = (app.TAMANHO_JANELA_RPM - 1) * 0.050; % Base de tempo física exata de hardware
                        
                        if delta_count_janela <= 0
                            rpm_raw = 0.0;
                        else
                            rpm_raw = (delta_count_janela / (app.pulsos_por_volta * dt_janela)) * 60.0;
                        end
                        rpm_raw = min(max(rpm_raw, 0.0), app.RPM_MAX_FISICO);
                        
                        % Filtro Mediano Móvel (5 amostras): elimina ruídos e atrasos transitórios de USB
                        app.buffer_rpm_recents = [app.buffer_rpm_recents(2:end), rpm_raw];
                        rpm_med = median(app.buffer_rpm_recents);
                        
                        % Estabilização e Deadband de Display
                        if rpm_med < 5.0
                            app.rpm_estavel_display = 0;
                            app.rpm_suavizado = 0;
                        else
                            if abs(rpm_med - app.rpm_estavel_display) >= 2.0
                                app.rpm_estavel_display = round(rpm_med);
                            end
                            app.rpm_suavizado = app.rpm_estavel_display;
                        end
                    end
                end

                % Filtragem EMA adaptativa contínua condicionada aos canais ativos nas configurações
                f_alpha = app.alpha;
                if app.modoDemo, f_alpha = 0.12; end % Resposta ágil e estável na simulação

                % Suavização contínua das tensões brutas de entrada (referência para calibração de Tara precisa)
                app.tensao_suavizada_torque  = f_alpha * dados{2} + (1 - f_alpha) * app.tensao_suavizada_torque;
                app.tensao_suavizada_lift    = f_alpha * dados{3} + (1 - f_alpha) * app.tensao_suavizada_lift;
                app.tensao_suavizada_drag    = f_alpha * dados{4} + (1 - f_alpha) * app.tensao_suavizada_drag;
                app.tensao_suavizada_hinge   = f_alpha * dados{5} + (1 - f_alpha) * app.tensao_suavizada_hinge;
                app.tensao_suavizada_pitot   = f_alpha * dados{6} + (1 - f_alpha) * app.tensao_suavizada_pitot;
                app.tensao_suavizada_venturi = f_alpha * dados{7} + (1 - f_alpha) * app.tensao_suavizada_venturi;

                % CH1 (RPM): já foi computado acima; se desativado, zera
                if ~app.habilitarCanalRPM
                    app.rpm_suavizado = 0;
                end

                % CH2: Torque
                if app.habilitarCanalTorque
                    tc = (dados{2} - app.tara_torque) * app.fator_escala_torque;
                    app.torque_suavizado = f_alpha * tc + (1 - f_alpha) * app.torque_suavizado;
                else
                    app.torque_suavizado = 0;
                end

                % CH3: Lift
                if app.habilitarCanalLift
                    lc = (dados{3} - app.tara_lift) * app.fator_escala_lift;
                    app.lift_suavizado = f_alpha * lc + (1 - f_alpha) * app.lift_suavizado;
                else
                    app.lift_suavizado = 0;
                end

                % CH4: Drag
                if app.habilitarCanalDrag
                    dc = (dados{4} - app.tara_drag) * app.fator_escala_drag;
                    app.drag_suavizado = f_alpha * dc + (1 - f_alpha) * app.drag_suavizado;
                else
                    app.drag_suavizado = 0;
                end

                % CH5: Hinge
                if app.habilitarCanalHinge
                    hc = (dados{5} - app.tara_hinge) * app.fator_escala_hinge;
                    app.hinge_suavizado = f_alpha * hc + (1 - f_alpha) * app.hinge_suavizado;
                else
                    app.hinge_suavizado = 0;
                end

                % CH6: Pitot (com tara dinâmica independente do Auto Tran 600D)
                if app.habilitarCanalPitot
                    p_p = max(0, (dados{6} - app.tara_pitot) * app.pressao_escala);
                    app.pitot_suavizado = f_alpha * p_p + (1 - f_alpha) * app.pitot_suavizado;
                else
                    app.pitot_suavizado = 0;
                end

                % CH7: Venturi (com tara dinâmica independente do Auto Tran 600D)
                if app.habilitarCanalVenturi
                    p_v = max(0, (dados{7} - app.tara_venturi) * app.pressao_escala);
                    app.venturi_suavizado = f_alpha * p_v + (1 - f_alpha) * app.venturi_suavizado;
                else
                    app.venturi_suavizado = 0;
                end

                % Filtro de Banda Morta (Deadband Industrial)
                if app.rpm_suavizado < 1.0; app.rpm_suavizado = 0; end
                if abs(app.torque_suavizado) < 0.002; app.torque_suavizado = 0; end
                if abs(app.lift_suavizado) < 0.005; app.lift_suavizado = 0; end
                if abs(app.drag_suavizado) < 0.002; app.drag_suavizado = 0; end
                if abs(app.hinge_suavizado) < 0.001; app.hinge_suavizado = 0; end
                if app.pitot_suavizado < 0.2; app.pitot_suavizado = 0; end
                if app.venturi_suavizado < 0.3; app.venturi_suavizado = 0; end

                % Grandezas Fluidodinâmicas e Mecânicas Medidas
                if app.pitot_suavizado > 0.1
                    vel_ms = sqrt(2 * app.pitot_suavizado / max(app.rho_ar, 0.001));
                else
                    vel_ms = 0.0;
                end
                if vel_ms < 0.05; vel_ms = 0.0; end
                
                Q_m3s = app.area_ref * vel_ms;
                omega = (2 * pi * app.rpm_suavizado) / 60.0;
                power_w = max(0, app.torque_suavizado * omega);

                lift_kgf    = app.lift_suavizado / 9.80665;
                drag_kgf    = app.drag_suavizado / 9.80665;
                pitot_mmh2o   = app.pitot_suavizado   * 0.10197;
                venturi_mmh2o = app.venturi_suavizado * 0.10197;

                if app.sistemaAtivo
                    t_now = toc(app.tempo_inicio);
                    app.tempo_decorrido = t_now;
                else
                    t_now = app.tempo_decorrido;
                end

                % Armazenamento em Buffer Central Pré-Alocado O(1) (Apenas em Demo ou quando gravarBuffer for ativo)
                if app.sistemaAtivo && gravarBuffer
                    app.buffer_idx = app.buffer_idx + 1;
                    if app.buffer_idx > size(app.dados_buffer, 1)
                        app.dados_buffer = [app.dados_buffer; zeros(50000, 13)];
                        app.tempo_buffer = [app.tempo_buffer; zeros(50000, 1)];
                    end
                    app.dados_buffer(app.buffer_idx, :) = [ ...
                        app.rpm_suavizado, app.torque_suavizado, app.lift_suavizado, ...
                        app.drag_suavizado, app.hinge_suavizado, app.pitot_suavizado, ...
                        app.venturi_suavizado, vel_ms, power_w, lift_kgf, drag_kgf, pitot_mmh2o, venturi_mmh2o];
                    app.tempo_buffer(app.buffer_idx) = t_now;
                end
                n_pts = app.buffer_idx;

                % Séries Temporais Otimizadas: Alimenta APENAS a aba ativa com catch-up instantâneo (Zero overhead offscreen)
                if app.sistemaAtivo
                    selTab = app.TabGroup.SelectedTab;
                    if selTab == app.TabForcas
                        if app.ultimo_idx_forcas < app.buffer_idx
                            idx_novos = (app.ultimo_idx_forcas + 1) : app.buffer_idx;
                            addpoints(app.aLineLift,    app.tempo_buffer(idx_novos), app.dados_buffer(idx_novos, 3));
                            addpoints(app.aLineDrag,    app.tempo_buffer(idx_novos), app.dados_buffer(idx_novos, 4));
                            addpoints(app.aLineHinge,   app.tempo_buffer(idx_novos), app.dados_buffer(idx_novos, 5));
                            app.ultimo_idx_forcas = app.buffer_idx;
                        end
                    elseif selTab == app.TabFluidos
                        if app.ultimo_idx_fluidos < app.buffer_idx
                            idx_novos = (app.ultimo_idx_fluidos + 1) : app.buffer_idx;
                            addpoints(app.aLinePitot,   app.tempo_buffer(idx_novos), app.dados_buffer(idx_novos, 12));
                            addpoints(app.aLineVenturi, app.tempo_buffer(idx_novos), app.dados_buffer(idx_novos, 13));
                            app.ultimo_idx_fluidos = app.buffer_idx;
                        end
                    elseif selTab == app.TabVentilador
                        if app.ultimo_idx_ventilador < app.buffer_idx
                            idx_novos = (app.ultimo_idx_ventilador + 1) : app.buffer_idx;
                            addpoints(app.aLineVentPitot,   app.tempo_buffer(idx_novos), app.dados_buffer(idx_novos, 12));
                            addpoints(app.aLineVentVenturi, app.tempo_buffer(idx_novos), app.dados_buffer(idx_novos, 13));
                            addpoints(app.aLineVentTorque,  app.tempo_buffer(idx_novos), app.dados_buffer(idx_novos, 2));
                            app.ultimo_idx_ventilador = app.buffer_idx;
                        end
                    end
                end

                if renderAgora
                    app.atualizarAbaRender(vel_ms, Q_m3s, power_w, t_now, n_pts, dt);
                end

                % Atualização Decimada do Rodapé
                if mod(app.tick_count, 5) == 0
                    modo_txt = sprintf('HW (NI USB-6211 | %d Hz)', app.taxa_log_hz); 
                    if app.modoDemo, modo_txt = 'DEMO'; end
                    app.StatusLabel.Text = sprintf('[%s] RPM: %.0f | v: %.1f m/s | L: %.2f N | D: %.2f N | P: %.1f W | t: %.1f s | buffer: %d pts', ...
                        modo_txt, app.rpm_suavizado, vel_ms, app.lift_suavizado, app.drag_suavizado, power_w, t_now, n_pts);
                end

            catch ME
                app.StatusLabel.Text = ['ERRO NO FRAME: ' ME.message];
                app.StatusLabel.FontColor = [0.8, 0.1, 0.1];
                app.StatusLamp.Color = [0.9, 0.1, 0.1];
            end
        end

        % =================================================================
        % 4. PROCESSAMENTO DO BUFFER EM LOTE (AQUISIÇÃO ASSÍNCRONA DA DAQ)
        % =================================================================
        function processarBlocoAmostras(app, bloco_matriz, dt_bloco)
            % bloco_matriz: matriz 50 x 8 amostrada a 1000 Hz
            N = size(bloco_matriz, 1);
            if N == 0, return; end
            
            % Média do bloco analógico para os canais 2 a 7
            medias = num2cell(mean(bloco_matriz(:, 2:7), 1));
            
            % Processa frame único decimado para IHM a 20 Hz
            dados_frame = [{bloco_matriz(end, 1)}, medias];
            app.processarFrame(dados_frame, dt_bloco, true, true);
        end

        % =================================================================
        % 5. RENDERIZAÇÃO ESTÁVEL DO ESTADO ATUAL (STANDBY/PAUSADO)
        % =================================================================
        
        % =================================================================
        % 4. CALLBACK DO TIMER DE INTERFACE (25 Hz - DESACOPLADO)
        % =================================================================
        function callbackTimerDemo(app, ~, ~)
            % Trava de Reentrância: Impede acúmulo de eventos na fila gráfica
            if app.frameOcupado, return; end
            app.frameOcupado = true;
            try
                dt = toc(app.ultimo_tic); 
                app.ultimo_tic = tic;
                if dt <= 0 || dt > 0.1, dt = 0.040; end

                if app.modoDemo
                    dados = app.gerarDadosSinteticos(dt);
                    app.processarFrame(dados, dt, true, true);
                else
                    app.renderizarEstadoAtual(dt);
                end
                drawnow nocallbacks;
            catch
            end
            app.frameOcupado = false;
        end

        % =================================================================
        % 5. CALLBACK SCANS AVAILABLE (PRODUTOR DE HARDWARE NI USB-6211 @ 1000 Hz)
        % =================================================================
        function processarBlocoDAQ(app, src, ~)
            try
                [dados_bloco, tempo_bloco] = read(src, src.ScansAvailableFcnCount, "OutputFormat", "Matrix");
                
                if length(tempo_bloco) > 1
                    dt_bloco = tempo_bloco(end) - tempo_bloco(1) + (1 / src.Rate);
                else
                    dt_bloco = 50 / src.Rate;
                end
                
                t_vec = app.extrairSegundosHardware(tempo_bloco);
                
                % Leitura rápida e robusta do acumulador de pulsos do tacômetro (ctr0)
                if ~isempty(app.dqCtr)
                    try
                        val_ctr = read(app.dqCtr);
                        cnt_fim = val_ctr{1, 1};
                    catch
                        cnt_fim = app.count_anterior;
                    end
                else
                    cnt_fim = app.count_anterior;
                end
                
                % Médias dos 6 canais analógicos da sessão (Torque, Lift, Drag, Hinge, Pitot, Venturi)
                medias = mean(dados_bloco, 1);
                
                % Atualiza estado suavizado e IHM a 20 Hz de forma fluida (sem gravar buffer aqui)
                dados_frame = {cnt_fim, medias(1), medias(2), medias(3), medias(4), medias(5), medias(6)};
                app.processarFrame(dados_frame, dt_bloco, false, false);
                
                % Gravação no Buffer do Logger conforme a taxa configurada (20, 100 ou 1000 Hz)
                if app.taxa_log_hz == 1000
                    app.gravarLoteRaw(dados_bloco, t_vec);
                elseif app.taxa_log_hz == 100
                    sub_dados = zeros(5, 6);
                    sub_t = zeros(5, 1);
                    for k = 1:5
                        idx_k = (k-1)*10 + 1 : k*10;
                        sub_dados(k, :) = mean(dados_bloco(idx_k, :), 1);
                        sub_t(k) = t_vec(idx_k(1));
                    end
                    app.gravarLoteRaw(sub_dados, sub_t);
                else
                    app.gravarLoteRaw(medias, t_vec(1));
                end
                
            catch ME
                if contains(ME.message, '-88709') || contains(lower(ME.message), 'device') || contains(lower(ME.message), 'removed') || contains(lower(ME.message), 'aborted')
                    app.tratarErroHardware(src, struct('Error', ME));
                else
                    app.StatusLabel.Text = ['ERRO DAQ NI: ' ME.message];
                    app.StatusLabel.FontColor = [0.8 0.1 0.1];
                    app.StatusLamp.Color = [0.9 0.1 0.1];
                end
            end
        end

        function tratarErroHardware(app, ~, ~)
            % Trava de Reentrância: Impede múltiplos alertas simultâneos
            if ~app.sistemaAtivo
                return;
            end
            app.sistemaAtivo = false;
            
            % Para o temporizador de atualização gráfica da interface
            if ~isempty(app.TimerPrincipal) && isvalid(app.TimerPrincipal)
                try, stop(app.TimerPrincipal); catch, end
            end
            
            % Desvincula callbacks assíncronos da DAQ para não reentrar no fluxo
            if ~isempty(app.dq)
                try, app.dq.ScansAvailableFcn = []; catch, end
                try, app.dq.ErrorOccurredFcn = []; catch, end
            end
            
            % Congela o tempo final decorrido do ensaio
            if app.buffer_idx > 0 && ~isempty(app.tempo_buffer)
                app.dados_finais    = app.dados_buffer(1:app.buffer_idx, :);
                app.tempo_final     = app.tempo_buffer(1:app.buffer_idx);
                app.tempo_decorrido = app.tempo_final(end);
            else
                if ~isempty(app.tempo_inicio)
                    app.tempo_decorrido = toc(app.tempo_inicio);
                else
                    app.tempo_decorrido = 0;
                end
            end
            
            % Restaura os controles da interface para o estado pronto
            app.StartButton.Enable   = 'on';
            app.DemoButton.Enable    = 'on';
            app.StopButton.Enable    = 'off';
            app.TaraButton.Enable    = 'off';
            app.ExportButton.Visible = 'on';
            
            % Atualiza indicadores visuais de hardware desconectado
            app.StatusLabel.Text   = 'Hardware Desconectado (USB removido). Reconecte o cabo USB, aguarde alguns instantes para a inicialização e reinicie a leitura.';
            app.StatusLabel.FontColor = [0.85, 0.1, 0.1];
            app.StatusLamp.Color   = [0.9, 0.1, 0.1];
            app.SinModoVal.Text    = '  CABO USB DESCONECTADO  ';
            app.SinModoVal.FontColor = [0.85, 0.1, 0.1];
            
            % Agenda liberação assíncrona da sessão DAQ (0,3 s) fora da pilha de eventos do driver,
            % permitindo que o listener interno do MATLAB (processHardwareStop) conclua sem warnings
            tLimpeza = timer('ExecutionMode', 'singleShot', 'StartDelay', 0.3, ...
                'TimerFcn', @(~,~) app.limparSessaoAposErroHardware(), ...
                'StopFcn', @(t,~) delete(t));
            start(tLimpeza);
            
            % Exibe caixa de diálogo informativa detalhada ao operador
            uialert(app.UIFigure, ...
                ['A comunicação com a placa de aquisição de dados (NI USB-6211) foi interrompida porque o dispositivo foi desconectado do barramento USB (Status Code: -88709).' newline newline ...
                 'A sessão de leitura foi finalizada com segurança.' newline newline ...
                 'Para retomar os ensaios:' newline ...
                 '1. Reconecte o cabo USB ao computador;' newline ...
                 '2. Aguarde alguns instantes para que a placa inicialize e seja reconhecida pelo sistema operacional;' newline ...
                 '3. Clique no botão "Iniciar Leitura (HW)".'], ...
                'Hardware Desconectado', 'Icon', 'warning');
        end

        function limparSessaoAposErroHardware(app)
            % Se um novo ensaio já foi iniciado pelo operador, não interfere
            if app.sistemaAtivo
                return;
            end
            if ~isempty(app.dq)
                try, stop(app.dq); catch, end
                try, flush(app.dq); catch, end
                try, delete(app.dq); catch, end
                app.dq = [];
            end
            if ~isempty(app.dqCtr)
                try, stop(app.dqCtr); catch, end
                try, flush(app.dqCtr); catch, end
                try, delete(app.dqCtr); catch, end
                app.dqCtr = [];
            end
            try, daqreset; catch, end
        end

        function t_sec = extrairSegundosHardware(app, tempo_bloco)
            if isempty(tempo_bloco)
                t_sec = toc(app.tempo_inicio);
                return;
            end
            
            if isduration(tempo_bloco)
                t_raw = seconds(tempo_bloco);
            elseif isdatetime(tempo_bloco)
                t_raw = posixtime(tempo_bloco);
            elseif isnumeric(tempo_bloco)
                t_raw = double(tempo_bloco);
            else
                t_raw = toc(app.tempo_inicio);
            end
            
            if app.tempo_hardware_base == 0
                app.tempo_hardware_base = t_raw(1);
            end
            t_sec = t_raw - app.tempo_hardware_base;
        end

        function gravarLoteRaw(app, dados_matriz, t_vec)
            if ~app.sistemaAtivo, return; end
            N = size(dados_matriz, 1);
            if N == 0, return; end
            
            % Expansão dinâmica segura do buffer pré-alocado
            if app.buffer_idx + N > size(app.dados_buffer, 1)
                exp_bloco = max(100000, N);
                app.dados_buffer = [app.dados_buffer; zeros(exp_bloco, 13)];
                app.tempo_buffer = [app.tempo_buffer; zeros(exp_bloco, 1)];
            end
            
            % Cálculos físicos instantâneos para os N pontos
            tc = (dados_matriz(:, 1) - app.tara_torque) * app.fator_escala_torque;
            lc = (dados_matriz(:, 2) - app.tara_lift)   * app.fator_escala_lift;
            dc = (dados_matriz(:, 3) - app.tara_drag)   * app.fator_escala_drag;
            hc = (dados_matriz(:, 4) - app.tara_hinge)  * app.fator_escala_hinge;
            pp = max(0, (dados_matriz(:, 5) - app.tara_pitot)   * app.pressao_escala);
            pv = max(0, (dados_matriz(:, 6) - app.tara_venturi) * app.pressao_escala);
            
            % Filtro de canais habilitados
            if ~app.habilitarCanalTorque,  tc = zeros(N, 1); end
            if ~app.habilitarCanalLift,    lc = zeros(N, 1); end
            if ~app.habilitarCanalDrag,    dc = zeros(N, 1); end
            if ~app.habilitarCanalHinge,   hc = zeros(N, 1); end
            if ~app.habilitarCanalPitot,   pp = zeros(N, 1); end
            if ~app.habilitarCanalVenturi, pv = zeros(N, 1); end
            
            % Suavização contínua EMA e Banda Morta idêntica ao manômetro e mostradores
            f_a = app.alpha;
            for k = 1:N
                if app.habilitarCanalTorque
                    app.torque_suavizado = f_a * tc(k) + (1 - f_a) * app.torque_suavizado;
                else
                    app.torque_suavizado = 0;
                end
                if app.habilitarCanalLift
                    app.lift_suavizado = f_a * lc(k) + (1 - f_a) * app.lift_suavizado;
                else
                    app.lift_suavizado = 0;
                end
                if app.habilitarCanalDrag
                    app.drag_suavizado = f_a * dc(k) + (1 - f_a) * app.drag_suavizado;
                else
                    app.drag_suavizado = 0;
                end
                if app.habilitarCanalHinge
                    app.hinge_suavizado = f_a * hc(k) + (1 - f_a) * app.hinge_suavizado;
                else
                    app.hinge_suavizado = 0;
                end
                if app.habilitarCanalPitot
                    app.pitot_suavizado = f_a * pp(k) + (1 - f_a) * app.pitot_suavizado;
                else
                    app.pitot_suavizado = 0;
                end
                if app.habilitarCanalVenturi
                    app.venturi_suavizado = f_a * pv(k) + (1 - f_a) * app.venturi_suavizado;
                else
                    app.venturi_suavizado = 0;
                end

                % Banda morta para zerar completamente oscilações e ruído em repouso
                if abs(app.torque_suavizado) < 0.002; app.torque_suavizado = 0; end
                if abs(app.lift_suavizado)   < 0.005; app.lift_suavizado   = 0; end
                if abs(app.drag_suavizado)   < 0.002; app.drag_suavizado   = 0; end
                if abs(app.hinge_suavizado)  < 0.001; app.hinge_suavizado  = 0; end
                if app.pitot_suavizado       < 0.2;   app.pitot_suavizado   = 0; end
                if app.venturi_suavizado     < 0.3;   app.venturi_suavizado = 0; end

                tc(k) = app.torque_suavizado;
                lc(k) = app.lift_suavizado;
                dc(k) = app.drag_suavizado;
                hc(k) = app.hinge_suavizado;
                pp(k) = app.pitot_suavizado;
                pv(k) = app.venturi_suavizado;
            end
            
            vel = zeros(N, 1);
            mask_p = (pp > 0.1);
            if any(mask_p)
                vel(mask_p) = sqrt(2 .* pp(mask_p) ./ max(app.rho_ar, 0.001));
            end
            vel(vel < 0.05) = 0;
            
            omega = (2 * pi * app.rpm_suavizado) / 60.0;
            pot = max(0, tc .* omega);
            rpm_col = repmat(app.rpm_suavizado, N, 1);
            l_kgf = lc ./ 9.80665;
            d_kgf = dc ./ 9.80665;
            p_mmh2o  = pp .* 0.10197;
            pv_mmh2o = pv .* 0.10197;
            
            idx_range = app.buffer_idx + (1:N);
            app.dados_buffer(idx_range, :) = [rpm_col, tc, lc, dc, hc, pp, pv, vel, pot, l_kgf, d_kgf, p_mmh2o, pv_mmh2o];
            app.tempo_buffer(idx_range) = t_vec;
            app.buffer_idx = app.buffer_idx + N;
        end

        function renderizarEstadoAtual(app, dt)
            if app.buffer_idx == 0
                vel_ms = 0; Q_m3s = 0; power_w = 0;
            else
                vel_ms  = app.dados_buffer(app.buffer_idx, 8);
                power_w = app.dados_buffer(app.buffer_idx, 9);
                Q_m3s   = app.area_ref * vel_ms;
            end
            t_now = app.tempo_decorrido;
            n_pts = app.buffer_idx;
            app.atualizarAbaRender(vel_ms, Q_m3s, power_w, t_now, n_pts, dt);
        end

        % =================================================================
        % 6. RENDERIZAÇÃO DA ABA ATIVA
        % =================================================================
        function atualizarAbaRender(app, vel_ms, Q_m3s, power_w, t_now, n_pts, dt)
            selTab = app.TabGroup.SelectedTab;
            if app.sistemaAtivo
                tmin = max(0, t_now - app.JANELA_TEMPO);
                tmax = max(tmin + 1, t_now);
            else
                % Quando o sistema está parado/concluído, exibe o ensaio completo e NUNCA avança para o futuro
                t_final = max(1.0, app.tempo_decorrido);
                tmin = 0;
                tmax = max(5.0, t_final);
            end

            if selTab == app.TabSinotica
                app.atualizarSinotico(vel_ms, Q_m3s, power_w, t_now, n_pts, dt);

            elseif selTab == app.TabForcas
                % Rolagem contínua e estável do Gráfico Unificado da Balança 514QD
                if ~isempty(app.AxesForcasUnificado) && isvalid(app.AxesForcasUnificado)
                    app.AxesForcasUnificado.XLim = [tmin tmax];
                    yyaxis(app.AxesForcasUnificado, 'left');
                    val_max_forcas = max([app.lift_suavizado, app.drag_suavizado, 5.0]);
                    val_min_forcas = min([app.lift_suavizado, app.drag_suavizado, -1.0]);
                    app.AxesForcasUnificado.YLim = [min(-1.0, floor(val_min_forcas - 0.5)), max(5.0, ceil(val_max_forcas + 0.5))];

                    if app.CbPlotHinge.Value
                        yyaxis(app.AxesForcasUnificado, 'right');
                        val_max_h = max([abs(app.hinge_suavizado), 0.5]);
                        app.AxesForcasUnificado.YLim = [-val_max_h, val_max_h];
                        yyaxis(app.AxesForcasUnificado, 'left');
                    end
                end
                if ~isempty(app.AxesLift) && isvalid(app.AxesLift) && app.AxesLift ~= app.AxesForcasUnificado
                    app.AxesLift.XLim = [tmin tmax];
                end

                % 1. Célula de Sustentação (Lift)
                if app.habilitarCanalLift
                    app.GaugeLift.Value   = min(max(app.lift_suavizado, -50.0), 50.0);
                    app.LabelLiftVal.Text = sprintf('%.4f N', app.lift_suavizado);
                else
                    app.GaugeLift.Value   = 0;
                    app.LabelLiftVal.Text = 'DESATIVADO';
                end

                % 2. Célula de Arrasto (Drag)
                if app.habilitarCanalDrag
                    app.GaugeDrag.Value   = min(max(app.drag_suavizado, -50.0), 50.0);
                    app.LabelDragVal.Text = sprintf('%.4f N', app.drag_suavizado);
                else
                    app.GaugeDrag.Value   = 0;
                    app.LabelDragVal.Text = 'DESATIVADO';
                end

                % 3. Célula de Momento de Dobradiça (Hinge - M_z)
                if app.habilitarCanalHinge
                    app.GaugeHinge.Value   = min(max(app.hinge_suavizado, -1.0), 1.0);
                    app.LabelHingeVal.Text = sprintf('%.4f N.m', app.hinge_suavizado);
                    if ~isempty(app.LabelResumoHinge) && isvalid(app.LabelResumoHinge)
                        app.LabelResumoHinge.Text = sprintf('Momento Hinge (M_z): %.4f N.m', app.hinge_suavizado);
                    end
                else
                    app.GaugeHinge.Value   = 0;
                    app.LabelHingeVal.Text = 'DESATIVADO';
                    if ~isempty(app.LabelResumoHinge) && isvalid(app.LabelResumoHinge)
                        app.LabelResumoHinge.Text = 'Momento Hinge (M_z): [DESATIVADO]';
                    end
                end

            elseif selTab == app.TabFluidos
                app.AxesPitot.XLim   = [tmin tmax];
                app.AxesVenturi.XLim = [tmin tmax];

                dh_pitot_mm   = app.pitot_suavizado   * 0.10197;
                dh_venturi_mm = app.venturi_suavizado * 0.10197;

                % Escalas definidas e estáveis nos gráficos de pressão (máximo padrão de 15 mmH2O)
                val_max_p1 = max(dh_pitot_mm, 15.0);
                app.AxesPitot.YLim = [-1.0, max(15.0, ceil(val_max_p1 + 1.0))];

                val_max_p2 = max(dh_venturi_mm, 15.0);
                app.AxesVenturi.YLim = [-1.0, max(15.0, ceil(val_max_p2 + 1.0))];

                % 1. Canal 1 (Manômetro em U)
                if ~isempty(app.GaugePitot) && isvalid(app.GaugePitot)
                    if app.habilitarCanalPitot
                        app.GaugePitot.Value = min(max(dh_pitot_mm, 0), 125);
                    else
                        app.GaugePitot.Value = 0;
                    end
                end
                if ~isempty(app.LabelPitotVal) && isvalid(app.LabelPitotVal)
                    if app.habilitarCanalPitot
                        app.LabelPitotVal.Text = sprintf('%.2f mmH_2O  (%.1f Pa)', dh_pitot_mm, app.pitot_suavizado);
                    else
                        app.LabelPitotVal.Text = 'DESATIVADO (CFG)';
                    end
                end

                % Atualização Física da Coluna Líquida Canal 1 (Escala Alta 0 a 100 mmH2O)
                escMaxP = 100.0;
                desloc_p = min(max((dh_pitot_mm / escMaxP) * 6.5, -6.5), 6.5);
                yL_p = 8.0 - desloc_p;
                yR_p = 8.0 + desloc_p;
                if ~isempty(app.ManometroPitotPatchL) && isvalid(app.ManometroPitotPatchL)
                    app.ManometroPitotPatchL.YData   = [0 0 yL_p yL_p];
                    app.ManometroPitotMeniscoL.YData = [yL_p yL_p];
                    app.ManometroPitotPatchR.YData   = [0 0 yR_p yR_p];
                    app.ManometroPitotMeniscoR.YData = [yR_p yR_p];
                    app.txtCotaPitot.String          = sprintf('\\Delta h = %.1f mmH_2O', dh_pitot_mm);
                    app.txtCotaPitot.Position        = [0, max(yL_p, yR_p) + 0.8, 0];
                end
                if ~isempty(app.LabelManoPitotVal) && isvalid(app.LabelManoPitotVal)
                    app.LabelManoPitotVal.Text = sprintf(['' char(916) 'h = %.2f mmH_2O  (%.1f Pa)'], dh_pitot_mm, app.pitot_suavizado);
                    app.LabelManoPitotLevels.Text = sprintf('Coluna Alta: %.1f mm  |  Coluna Baixa: %.1f mm', 50.0 + dh_pitot_mm/2.0, 50.0 - dh_pitot_mm/2.0);
                end

                % 2. Canal 2 (Manômetro em U)
                if ~isempty(app.GaugeVenturi) && isvalid(app.GaugeVenturi)
                    if app.habilitarCanalVenturi
                        app.GaugeVenturi.Value = min(max(dh_venturi_mm, 0), 250);
                    else
                        app.GaugeVenturi.Value = 0;
                    end
                end
                if ~isempty(app.LabelVenturiVal) && isvalid(app.LabelVenturiVal)
                    if app.habilitarCanalVenturi
                        app.LabelVenturiVal.Text = sprintf('%.2f mmH_2O  (%.1f Pa)', dh_venturi_mm, app.venturi_suavizado);
                    else
                        app.LabelVenturiVal.Text = 'DESATIVADO (CFG)';
                    end
                end

                % Atualização Física da Coluna Líquida Canal 2 (Escala Alta 0 a 200 mmH2O)
                escMaxV = 200.0;
                desloc_v = min(max((dh_venturi_mm / escMaxV) * 6.5, -6.5), 6.5);
                yL_v = 8.0 - desloc_v;
                yR_v = 8.0 + desloc_v;
                if ~isempty(app.ManometroVenturiPatchL) && isvalid(app.ManometroVenturiPatchL)
                    app.ManometroVenturiPatchL.YData   = [0 0 yL_v yL_v];
                    app.ManometroVenturiMeniscoL.YData = [yL_v yL_v];
                    app.ManometroVenturiPatchR.YData   = [0 0 yR_v yR_v];
                    app.ManometroVenturiMeniscoR.YData = [yR_v yR_v];
                    app.txtCotaVenturi.String          = sprintf('\\Delta h = %.1f mmH_2O', dh_venturi_mm);
                    app.txtCotaVenturi.Position        = [0, max(yL_v, yR_v) + 0.8, 0];
                end
                if ~isempty(app.LabelManoVenturiVal) && isvalid(app.LabelManoVenturiVal)
                    app.LabelManoVenturiVal.Text = sprintf(['' char(916) 'h = %.2f mmH_2O  (%.1f Pa)'], dh_venturi_mm, app.venturi_suavizado);
                    app.LabelManoVenturiLevels.Text = sprintf('Coluna Alta: %.1f mm  |  Coluna Baixa: %.1f mm', 100.0 + dh_venturi_mm/2.0, 100.0 - dh_venturi_mm/2.0);
                end

            elseif selTab == app.TabLogger
                app.atualizarGraficoLogger();

            elseif selTab == app.TabVentilador
                app.atualizarVentilador(power_w, tmin, tmax);
            end
        end

        function atualizarVentilador(app, power_w, tmin, tmax)
            if ~isempty(app.AxesVentilador) && isvalid(app.AxesVentilador)
                app.AxesVentilador.XLim = [tmin tmax];
            end

            % 1. Rotação do Motor N (RPM)
            if app.habilitarCanalRPM
                app.CardVentRPMVal.Text = sprintf('%.0f RPM', app.rpm_suavizado);
                app.CardVentRPMSub.Text = sprintf('Freq: %.1f Hz | Sensor Indutivo', app.rpm_suavizado / 60.0);
            else
                app.CardVentRPMVal.Text = 'DESATIVADO';
                app.CardVentRPMSub.Text = 'Canal Desabilitado';
            end

            % 2. Torque no Eixo Teixo (N.m)
            if app.habilitarCanalTorque
                app.CardVentTorqueVal.Text = sprintf('%.4f N·m', app.torque_suavizado);
                pot_cv = power_w / 735.499;
                app.CardVentTorqueSub.Text = sprintf('Potência no Eixo: %.1f W (%.3f cv)', power_w, pot_cv);
            else
                app.CardVentTorqueVal.Text = 'DESATIVADO';
                app.CardVentTorqueSub.Text = 'Canal Desabilitado';
            end

            % 3. Pressão Estática ΔPest (mmH2O / Pa)
            dh_pitot_mm = app.pitot_suavizado * 0.10197;
            if app.habilitarCanalPitot
                app.CardVentPitotVal.Text = sprintf('%.2f mmH2O', dh_pitot_mm);
                app.CardVentPitotSub.Text = sprintf('%.1f Pa | Transdutor AutoTran', app.pitot_suavizado);
            else
                app.CardVentPitotVal.Text = 'DESATIVADO';
                app.CardVentPitotSub.Text = 'Canal Desabilitado';
            end

            % 4. Pressão no Venturi ΔPventuri (mmH2O / Pa)
            dh_venturi_mm = app.venturi_suavizado * 0.10197;
            if app.habilitarCanalVenturi
                app.CardVentVenturiVal.Text = sprintf('%.2f mmH2O', dh_venturi_mm);
                app.CardVentVenturiSub.Text = sprintf('%.1f Pa | Transdutor AutoTran', app.venturi_suavizado);
            else
                app.CardVentVenturiVal.Text = 'DESATIVADO';
                app.CardVentVenturiSub.Text = 'Canal Desabilitado';
            end
        end

        % =================================================================
        function sincronizarLinhasComBuffer(app)
            n_pts = app.buffer_idx;
            if n_pts == 0, return; end

            if n_pts > 5000
                step = ceil(n_pts / 4000);
                idx_pts = 1:step:n_pts;
                if idx_pts(end) ~= n_pts, idx_pts = [idx_pts, n_pts]; end
            else
                idx_pts = 1:n_pts;
            end

            t_hist = app.tempo_buffer(idx_pts);
            
            % Eixo Esquerdo: Sustentação e Arrasto
            if ~isempty(app.AxesForcasUnificado) && isvalid(app.AxesForcasUnificado)
                yyaxis(app.AxesForcasUnificado, 'left');
                clearpoints(app.aLineLift);
                addpoints(app.aLineLift, t_hist, app.dados_buffer(idx_pts, 3));

                clearpoints(app.aLineDrag);
                addpoints(app.aLineDrag, t_hist, app.dados_buffer(idx_pts, 4));

                % Eixo Direito: Momento de Dobradiça (Hinge)
                yyaxis(app.AxesForcasUnificado, 'right');
                clearpoints(app.aLineHinge);
                addpoints(app.aLineHinge, t_hist, app.dados_buffer(idx_pts, 5));
                yyaxis(app.AxesForcasUnificado, 'left');
            end

            clearpoints(app.aLinePitot);
            addpoints(app.aLinePitot, t_hist, app.dados_buffer(idx_pts, 6) * 0.10197);

            clearpoints(app.aLineVenturi);
            addpoints(app.aLineVenturi, t_hist, app.dados_buffer(idx_pts, 7) * 0.10197);

            if ~isempty(app.AxesVentilador) && isvalid(app.AxesVentilador)
                yyaxis(app.AxesVentilador, 'left');
                clearpoints(app.aLineVentPitot);
                addpoints(app.aLineVentPitot, t_hist, app.dados_buffer(idx_pts, 6) * 0.10197);
                clearpoints(app.aLineVentVenturi);
                addpoints(app.aLineVentVenturi, t_hist, app.dados_buffer(idx_pts, 7) * 0.10197);
                yyaxis(app.AxesVentilador, 'right');
                clearpoints(app.aLineVentTorque);
                addpoints(app.aLineVentTorque, t_hist, app.dados_buffer(idx_pts, 2));
                yyaxis(app.AxesVentilador, 'left');
            end

            app.ultimo_idx_forcas      = app.buffer_idx;
            app.ultimo_idx_fluidos     = app.buffer_idx;
            app.ultimo_idx_ventilador  = app.buffer_idx;

            % Garante que ao mudar de aba ou parar, os gráficos exibam a série completa
            if ~app.sistemaAtivo
                t_final = max([1.0, app.tempo_decorrido, t_hist(end)]);
                if ~isempty(app.AxesForcasUnificado) && isvalid(app.AxesForcasUnificado)
                    app.AxesForcasUnificado.XLim = [0, max(5.0, t_final)];
                    yyaxis(app.AxesForcasUnificado, 'left');
                    v_l = app.dados_buffer(idx_pts, 3);
                    v_d = app.dados_buffer(idx_pts, 4);
                    min_f = min([min(v_l), min(v_d), -1.0]);
                    max_f = max([max(v_l), max(v_d), 5.0]);
                    app.AxesForcasUnificado.YLim = [min(-1.0, floor(min_f - 0.5)), max(5.0, ceil(max_f + 0.5))];
                    if app.CbPlotHinge.Value
                        yyaxis(app.AxesForcasUnificado, 'right');
                        v_h = app.dados_buffer(idx_pts, 5);
                        max_h = max([max(abs(v_h)), 0.5]);
                        app.AxesForcasUnificado.YLim = [-max_h, max_h];
                        yyaxis(app.AxesForcasUnificado, 'left');
                    end
                end
                if ~isempty(app.AxesPitot) && isvalid(app.AxesPitot)
                    v_p = app.dados_buffer(idx_pts, 6) * 0.10197;
                    max_p = max([max(v_p), 15.0]);
                    app.AxesPitot.YLim = [-1.0, max(15.0, ceil(max_p + 1.0))];
                end
                if ~isempty(app.AxesVenturi) && isvalid(app.AxesVenturi)
                    v_v = app.dados_buffer(idx_pts, 7) * 0.10197;
                    max_v = max([max(v_v), 15.0]);
                    app.AxesVenturi.YLim = [-1.0, max(15.0, ceil(max_v + 1.0))];
                end
                if ~isempty(app.AxesVentilador) && isvalid(app.AxesVentilador)
                    app.AxesVentilador.XLim = [0, max(5.0, t_final)];
                end
            end
        end

        function atualizarGraficoLogger(app)
            n_pts = app.buffer_idx;
            if n_pts == 0, return; end

            col = app.LogCanalDropdown.Value;
            if ischar(col) || isstring(col)
                col = 3;
            end
            
            if n_pts > 5000
                step = ceil(n_pts / 4000);
                idx_pts = 1:step:n_pts;
            else
                idx_pts = 1:n_pts;
            end

            t_hist = app.tempo_buffer(idx_pts);
            y_hist = app.dados_buffer(idx_pts, col);

            clearpoints(app.aLineLogger);
            addpoints(app.aLineLogger, t_hist, y_hist);

            if app.sistemaAtivo
                t_now = t_hist(end);
                tmin = max(0, t_now - 30);
                tmax = max(tmin + 1, t_now);
            else
                tmin = 0;
                tmax = max(5.0, app.tempo_decorrido);
            end
            app.AxesLogger.XLim = [tmin tmax];

            app.LogStatMin.Text  = sprintf('%.4f', min(y_hist));
            app.LogStatMean.Text = sprintf('%.4f', mean(y_hist));
            app.LogStatMax.Text  = sprintf('%.4f', max(y_hist));
            app.LogStatStd.Text  = sprintf('%.4f', std(y_hist));
        end

        % =================================================================
        % 8. CALLBACK DE MUDANÇA DE ABA
        % =================================================================
        function TabGroupSelectionChanged(app, ~)
            if app.sistemaAtivo
                t_now = toc(app.tempo_inicio);
                app.tempo_decorrido = t_now;
            else
                t_now = app.tempo_decorrido;
            end
            
            % Catch-up instantâneo dos pontos gravados no buffer ao entrar na aba selecionada
            selTab = app.TabGroup.SelectedTab;
            if selTab == app.TabForcas
                if app.ultimo_idx_forcas < app.buffer_idx
                    idx_novos = (app.ultimo_idx_forcas + 1) : app.buffer_idx;
                    addpoints(app.aLineLift,    app.tempo_buffer(idx_novos), app.dados_buffer(idx_novos, 3));
                    addpoints(app.aLineDrag,    app.tempo_buffer(idx_novos), app.dados_buffer(idx_novos, 4));
                    addpoints(app.aLineHinge,   app.tempo_buffer(idx_novos), app.dados_buffer(idx_novos, 5));
                    app.ultimo_idx_forcas = app.buffer_idx;
                end
            elseif selTab == app.TabFluidos
                if app.ultimo_idx_fluidos < app.buffer_idx
                    idx_novos = (app.ultimo_idx_fluidos + 1) : app.buffer_idx;
                    addpoints(app.aLinePitot,   app.tempo_buffer(idx_novos), app.dados_buffer(idx_novos, 12));
                    addpoints(app.aLineVenturi, app.tempo_buffer(idx_novos), app.dados_buffer(idx_novos, 13));
                    app.ultimo_idx_fluidos = app.buffer_idx;
                end
            elseif selTab == app.TabLogger
                app.atualizarGraficoLogger();
            elseif selTab == app.TabVentilador
                if app.ultimo_idx_ventilador < app.buffer_idx
                    idx_novos = (app.ultimo_idx_ventilador + 1) : app.buffer_idx;
                    addpoints(app.aLineVentPitot,   app.tempo_buffer(idx_novos), app.dados_buffer(idx_novos, 12));
                    addpoints(app.aLineVentVenturi, app.tempo_buffer(idx_novos), app.dados_buffer(idx_novos, 13));
                    addpoints(app.aLineVentTorque,  app.tempo_buffer(idx_novos), app.dados_buffer(idx_novos, 2));
                    app.ultimo_idx_ventilador = app.buffer_idx;
                end
            end
            n_pts = app.buffer_idx;

            if app.habilitarCanalPitot && app.pitot_suavizado > 0.1
                vel_ms = sqrt(2 * app.pitot_suavizado / max(app.rho_ar, 0.001));
            else
                vel_ms = 0;
            end
            Q_m3s = app.area_ref * vel_ms;
            omega = (2 * pi * app.rpm_suavizado) / 60.0;
            power_w = max(0, app.torque_suavizado * omega);

            app.atualizarAbaRender(vel_ms, Q_m3s, power_w, t_now, n_pts, 0.04);
        end

        % =================================================================
        % 9. ATUALIZAÇÃO DA TELA SINÓTICA (ABA 1) - ANIMAÇÃO GEOMÉTRICA REAL
        % =================================================================
        function atualizarSinotico(app, vel, Q, power_w, t_now, n_pts, dt)
            cON  = [0.15 0.75 0.25];
            cOFF = [0.70 0.75 0.80];
            cDIS = [0.82 0.82 0.82];
            txtDIS = [0.55 0.55 0.55];

            % 1. RPM (Tacômetro)
            if app.habilitarCanalRPM
                app.SinRPMVal.Text      = sprintf('%.0f RPM  (%.1f Hz)', app.rpm_suavizado, app.rpm_suavizado / 60.0);
                app.SinRPMVal.FontColor = [0.10, 0.55, 0.20];
                if app.rpm_suavizado > 1; app.LampRPM.Color = cON; else; app.LampRPM.Color = cOFF; end
            else
                app.SinRPMVal.Text      = 'DESATIVADO (CFG)';
                app.SinRPMVal.FontColor = txtDIS;
                app.LampRPM.Color       = cDIS;
            end

            % 2. Torque Motor
            if app.habilitarCanalTorque
                app.SinTorqueVal.Text   = sprintf('%.4f N.m  (P: %.2f W)', app.torque_suavizado, power_w);
                app.SinTorqueVal.FontColor = [0.10, 0.55, 0.20];
                if abs(app.torque_suavizado) > 0.005; app.LampTorque.Color = cON; else; app.LampTorque.Color = cOFF; end
            else
                app.SinTorqueVal.Text   = 'DESATIVADO (CFG)';
                app.SinTorqueVal.FontColor = txtDIS;
                app.LampTorque.Color    = cDIS;
            end

            % 3. Sustentação (Lift)
            if app.habilitarCanalLift
                lift_kg = app.lift_suavizado / 9.80665;
                app.SinLiftVal.Text     = sprintf('%.4f N  (%.3f kgf)', app.lift_suavizado, lift_kg);
                app.SinLiftVal.FontColor = [0.10, 0.55, 0.20];
                if abs(app.lift_suavizado) > 0.010; app.LampLift.Color = cON; else; app.LampLift.Color = cOFF; end
            else
                app.SinLiftVal.Text     = 'DESATIVADO (CFG)';
                app.SinLiftVal.FontColor = txtDIS;
                app.LampLift.Color      = cDIS;
            end

            % 4. Arrasto (Drag)
            if app.habilitarCanalDrag
                drag_kg = app.drag_suavizado / 9.80665;
                app.SinDragVal.Text     = sprintf('%.4f N  (%.3f kgf)', app.drag_suavizado, drag_kg);
                app.SinDragVal.FontColor = [0.10, 0.55, 0.20];
                if abs(app.drag_suavizado) > 0.010; app.LampDrag.Color = cON; else; app.LampDrag.Color = cOFF; end
            else
                app.SinDragVal.Text     = 'DESATIVADO (CFG)';
                app.SinDragVal.FontColor = txtDIS;
                app.LampDrag.Color      = cDIS;
            end

            % 5. Momento de Articulação (Hinge)
            if app.habilitarCanalHinge
                app.SinHingeVal.Text    = sprintf('%.4f N.m', app.hinge_suavizado);
                app.SinHingeVal.FontColor = [0.10, 0.55, 0.20];
                if abs(app.hinge_suavizado) > 0.005; app.LampHinge.Color = cON; else; app.LampHinge.Color = cOFF; end
            else
                app.SinHingeVal.Text    = 'DESATIVADO (CFG)';
                app.SinHingeVal.FontColor = txtDIS;
                app.LampHinge.Color     = cDIS;
            end

            % 6. Pressão do Transdutor 1
            if app.habilitarCanalPitot
                app.SinVelVal.Text      = sprintf('%.1f Pa  (%.2f mmH2O)', app.pitot_suavizado, app.pitot_suavizado * 0.10197);
                app.SinVelVal.FontColor = [0.10, 0.55, 0.20];
                if app.pitot_suavizado > 0.5; app.LampPitot.Color = cON; else; app.LampPitot.Color = cOFF; end
            else
                app.SinVelVal.Text      = 'DESATIVADO (CFG)';
                app.SinVelVal.FontColor = txtDIS;
                app.LampPitot.Color     = cDIS;
            end

            % 7. Pressão do Transdutor 2
            if app.habilitarCanalVenturi
                app.SinFlowVal.Text     = sprintf('%.1f Pa  (%.2f mmH2O)', app.venturi_suavizado, app.venturi_suavizado * 0.10197);
                app.SinFlowVal.FontColor = [0.10, 0.55, 0.20];
                if app.venturi_suavizado > 0.5; app.LampVenturi.Color = cON; else; app.LampVenturi.Color = cOFF; end
            else
                app.SinFlowVal.Text     = 'DESATIVADO (CFG)';
                app.SinFlowVal.FontColor = txtDIS;
                app.LampVenturi.Color   = cDIS;
            end

            app.SinTempoVal.Text    = sprintf('%.1f s', t_now);
            app.SinAmostrasVal.Text = sprintf('%d pts', n_pts);

            % Indicador de Modo de Operação / Bancada
            canais_status = [app.habilitarCanalRPM, app.habilitarCanalTorque, app.habilitarCanalLift, ...
                             app.habilitarCanalDrag, app.habilitarCanalHinge, app.habilitarCanalPitot, app.habilitarCanalVenturi];
            n_ativos = sum(canais_status);

            if app.modoDemo
                if n_ativos == 7
                    app.SinModoVal.Text = '  SIMULAÇÃO VIRTUAL (TESTES DE DESENVOLVIMENTO)  ';
                else
                    app.SinModoVal.Text = sprintf('  SIMULAÇÃO VIRTUAL (%d/7 CANAIS ATIVOS)  ', n_ativos);
                end
                app.SinModoVal.FontColor = [0.1, 0.4, 0.8];
            else
                if n_ativos == 7
                    app.SinModoVal.Text = '  DAQ HW: TODOS OS CANAIS ATIVOS  ';
                    app.SinModoVal.FontColor = [0.05, 0.60, 0.20];
                elseif n_ativos == 0
                    app.SinModoVal.Text = '  TODOS OS CANAIS DESATIVADOS  ';
                    app.SinModoVal.FontColor = [0.70, 0.20, 0.20];
                else
                    app.SinModoVal.Text = sprintf('  BANCADA HW: %d/7 CANAIS ATIVOS  ', n_ativos);
                    app.SinModoVal.FontColor = [0.85, 0.45, 0.05];
                end
            end

            % 1. ANIMAÇÃO DO ROTOR GIRATÓRIO (Anti-Aliasing Estroboscópico Tri-pá Estrito)
            % O avanço angular por frame é calibrado para variar entre 2.5° e 22.0° por frame
            % Como 22.0° << 60° (limite de Nyquist para 3 pás simétricas de 120°),
            % a hélice gira com extrema fluidez e NUNCA aparenta congelar ou girar para trás.
            if app.rpm_suavizado > 15
                d_theta = 0.045 + 0.340 * min(1.0, app.rpm_suavizado / 3500.0);
                app.rotor_angle = mod(app.rotor_angle + d_theta, 2*pi);
            end
            xc_r = 1.1; yc_r = 3.5; R_r = 0.62;
            th = app.rotor_angle;
            th1 = th; th2 = th + (2*pi/3); th3 = th + (4*pi/3);

            app.RotorBladesPlot.XData = [xc_r, xc_r + R_r*cos(th1), NaN, xc_r, xc_r + R_r*cos(th2), NaN, xc_r, xc_r + R_r*cos(th3)];
            app.RotorBladesPlot.YData = [yc_r, yc_r + R_r*sin(th1), NaN, yc_r, yc_r + R_r*sin(th2), NaN, yc_r, yc_r + R_r*sin(th3)];

            % 2. ANIMAÇÃO FLUIDA DE LINHAS DE CORRENTE / FILETES DE VENTO
            if (app.rpm_suavizado > 15 || (app.modoDemo && vel > 0.1)) && isvalid(app.WindParticlesPlot)
                % Avanço perceptual contínuo calibrado por Nyquist espacial (0.015 a 0.14 u/frame)
                dx_adv = 0.015 + 0.135 * min(1.0, vel / 30.0);
                x_min = 3.40; x_max = 9.60;
                x_span = x_max - x_min;
                n_streaks = 8;
                spacing = x_span / n_streaks;
                streak_len = 0.32;

                app.wind_phase = mod(app.wind_phase + dx_adv, spacing);
                alpha_rad = (app.angulo_ataque * pi) / 180.0;

                y_levels = [2.52, 2.88, 3.22, 3.78, 4.12, 4.48];
                n_levels = 6;
                total_streaks = n_levels * n_streaks;

                X_data = NaN(1, 3 * total_streaks);
                Y_data = NaN(1, 3 * total_streaks);

                idx = 1;
                for i = 1:n_levels
                    y_b = y_levels(i);
                    for k = 0:(n_streaks - 1)
                        x1 = x_min + mod(k * spacing + app.wind_phase, x_span);
                        x2 = min(x_max, x1 + streak_len);

                        % Ponto 1 (Início do traço)
                        xm1 = x1;
                        def_a1 = -0.38 * sin(alpha_rad) * sin(pi * max(0, min(1, (xm1 - 4.6)/3.2)));
                        dist_c1 = exp(-((xm1 - 6.05)/0.85)^2);
                        if y_b > 3.5; def_b1 = 0.22 * dist_c1; else; def_b1 = -0.22 * dist_c1; end
                        y1 = y_b + def_a1 + def_b1;
                        if xm1 >= 8.0 && xm1 <= 9.8
                            y1 = 3.50 + (y1 - 3.50) * (1.0 - 0.42 * exp(-((xm1 - 9.0)/0.65)^2));
                        end

                        % Ponto 2 (Fim do traço)
                        xm2 = x2;
                        def_a2 = -0.38 * sin(alpha_rad) * sin(pi * max(0, min(1, (xm2 - 4.6)/3.2)));
                        dist_c2 = exp(-((xm2 - 6.05)/0.85)^2);
                        if y_b > 3.5; def_b2 = 0.22 * dist_c2; else; def_b2 = -0.22 * dist_c2; end
                        y2 = y_b + def_a2 + def_b2;
                        if xm2 >= 8.0 && xm2 <= 9.8
                            y2 = 3.50 + (y2 - 3.50) * (1.0 - 0.42 * exp(-((xm2 - 9.0)/0.65)^2));
                        end

                        X_data(idx)   = x1;
                        X_data(idx+1) = x2;
                        Y_data(idx)   = y1;
                        Y_data(idx+1) = y2;
                        idx = idx + 3;
                    end
                end
                app.WindParticlesPlot.XData = X_data;
                app.WindParticlesPlot.YData = Y_data;
                app.WindParticlesPlot.Visible = 'on';
            else
                if isvalid(app.WindParticlesPlot)
                    app.WindParticlesPlot.Visible = 'off';
                end
            end

            % 3. VETORES DINÂMICOS DE FORÇA NO AEROFÓLIO (LIFT & DRAG)
            xc_a = app.AirfoilCenterX; yc_a = app.AirfoilCenterY;
            
            if abs(app.lift_suavizado) >= 0.05
                L_scale = max(-2.8, min(2.8, app.lift_suavizado * 0.100));
                y_lift_tip = yc_a + L_scale;
                app.LiftVectorLine.XData = [xc_a, xc_a];
                app.LiftVectorLine.YData = [yc_a, y_lift_tip];
                app.LiftVectorHead.XData = xc_a;
                app.LiftVectorHead.YData = y_lift_tip;
                if L_scale >= 0
                    app.LiftVectorHead.Marker = '^';
                    app.LiftVectorText.Position = [xc_a + 0.15, y_lift_tip + 0.25, 0];
                else
                    app.LiftVectorHead.Marker = 'v';
                    app.LiftVectorText.Position = [xc_a + 0.15, y_lift_tip - 0.25, 0];
                end
                app.LiftVectorText.String = sprintf('Lift = %.2f N', app.lift_suavizado);
                app.LiftVectorLine.Visible = 'on';
                app.LiftVectorHead.Visible = 'on';
                app.LiftVectorText.Visible = 'on';
            else
                app.LiftVectorLine.Visible = 'off';
                app.LiftVectorHead.Visible = 'off';
                app.LiftVectorText.Visible = 'off';
            end
            
            if abs(app.drag_suavizado) >= 0.05
                D_scale = max(0.0, min(3.2, app.drag_suavizado * 0.250));
                x_drag_tip = xc_a + D_scale;
                app.DragVectorLine.XData = [xc_a, x_drag_tip];
                app.DragVectorLine.YData = [yc_a, yc_a];
                app.DragVectorHead.XData = x_drag_tip;
                app.DragVectorHead.YData = yc_a;
                app.DragVectorText.Position = [x_drag_tip + 0.15, yc_a - 0.20, 0];
                app.DragVectorText.String = sprintf('Drag = %.2f N', app.drag_suavizado);
                app.DragVectorLine.Visible = 'on';
                app.DragVectorHead.Visible = 'on';
                app.DragVectorText.Visible = 'on';
            else
                app.DragVectorLine.Visible = 'off';
                app.DragVectorHead.Visible = 'off';
                app.DragVectorText.Visible = 'off';
            end

            % Lâmpadas P&ID
            app.LampRPM.Color     = app.obterCorLamp(app.rpm_suavizado, 10, 3500);
            app.LampTorque.Color  = app.obterCorLamp(app.torque_suavizado, 0.05, 4.0);
            app.LampLift.Color    = app.obterCorLamp(abs(app.lift_suavizado), 0.1, 45);
            app.LampDrag.Color    = app.obterCorLamp(app.drag_suavizado, 0.05, 20);
            app.LampHinge.Color   = app.obterCorLamp(abs(app.hinge_suavizado), 0.02, 2);
            app.LampPitot.Color   = app.obterCorLamp(app.pitot_suavizado, 5, 1200);
            app.LampVenturi.Color = app.obterCorLamp(app.venturi_suavizado, 5, 1200);
        end

        % =================================================================
        % 10. ATUALIZAÇÃO DO PERFIL ALAR DINÂMICO
        % =================================================================
        function atualizarDesenhoAirfoil(app)
            if isempty(app.AirfoilPatch) || ~isvalid(app.AirfoilPatch), return; end
            theta = (-app.angulo_ataque * pi) / 180;
            xc = app.AirfoilCenterX;
            yc = app.AirfoilCenterY;
            
            xr = xc + (app.AirfoilBaseX - xc) * cos(theta) - (app.AirfoilBaseY - yc) * sin(theta);
            yr = yc + (app.AirfoilBaseX - xc) * sin(theta) + (app.AirfoilBaseY - yc) * cos(theta);
            
            app.AirfoilPatch.XData = xr;
            app.AirfoilPatch.YData = yr;
            app.AirfoilTextAlpha.String = sprintf('α = %.1f°', app.angulo_ataque);
        end

        function cor = obterCorLamp(~, val, vmin, vmax)
            if val < vmin
                cor = [0.70, 0.75, 0.80];
            elseif val > vmax * 0.90
                cor = [0.85, 0.15, 0.15];
            elseif val > vmax * 0.70
                cor = [0.90, 0.65, 0.05];
            else
                cor = [0.10, 0.65, 0.25];
            end
        end

        % =================================================================
        % 11. INICIALIZAÇÃO ROBUSTA DA PLACA NI USB-6211
        % =================================================================
        function sucesso = iniciarHardware(app)
            sucesso = false;
            d = uiprogressdlg(app.UIFigure, 'Title', 'Inicializando Hardware', 'Message', 'Buscando placa National Instruments (NI-DAQmx)...', 'Cancelable', 'off');
            try
                daqreset;
                d.Value = 0.2;
                devices = daqlist("ni");
                if ~isempty(devices)
                    if istable(devices)
                        devID = string(devices.DeviceID(1));
                        modelo = string(devices.Model(1));
                    elseif isstruct(devices)
                        devID = string(devices(1).ID);
                        modelo = string(devices(1).Model);
                    else
                        devID = "Dev1";
                        modelo = "NI USB-6211";
                    end
                else
                    % Fallback direto para Dev1 caso daqlist retorne vazio
                    devID = "Dev1";
                    modelo = "NI USB-6211";
                end
                
                if isempty(devID) || devID == ""
                    devID = "Dev1";
                end
                
                d.Value = 0.5;
                d.Message = sprintf('Placa detectada: %s (%s). Configurando canais...', devID, modelo);
                
                % -------------------------------------------------------------
                % 1. Sessão Analógica (6 canais @ 1000 Hz Contínuo em Background)
                % Mantém NumberOfInputChannelGroups = 1, eliminando completamente
                % o bug interno do MATLAB R2025b no listener handleMultipleDataSources
                % -------------------------------------------------------------
                if ~isempty(app.dq)
                    try, app.dq.ScansAvailableFcn = []; catch, end
                    try, stop(app.dq); catch, end
                    try, delete(app.dq); catch, end
                    app.dq = [];
                end
                if ~isempty(app.dqCtr)
                    try, stop(app.dqCtr); catch, end
                    try, delete(app.dqCtr); catch, end
                    app.dqCtr = [];
                end

                app.dq = daq("ni");
                app.dq.Rate = 1000;
                
                % CH1-CH4: Células de Carga em modo Diferencial (Alto CMRR)
                addinput(app.dq, devID, "ai5", "Voltage"); % CH1 analógico: Torque (Transmissor DY510)
                addinput(app.dq, devID, "ai0", "Voltage"); % CH2 analógico: Lift (AD8226 1 na PCB)
                addinput(app.dq, devID, "ai1", "Voltage"); % CH3 analógico: Drag (AD8226 2 na PCB)
                addinput(app.dq, devID, "ai2", "Voltage"); % CH4 analógico: Hinge (AD8226 3 na PCB)
                
                for ch = 1:4
                    app.dq.Channels(ch).TerminalConfig = "Differential";
                end
                
                % CH5-CH6: Transdutores AutoTran (Single-Ended / RSE na PCB)
                addinput(app.dq, devID, "ai4", "Voltage"); % CH5 analógico: Pressão 1 (AD8210 1 na PCB)
                addinput(app.dq, devID, "ai3", "Voltage"); % CH6 analógico: Pressão 2 (AD8210 2 na PCB)
                for ch = 5:6
                    app.dq.Channels(ch).TerminalConfig = "SingleEnded";
                end
                
                % -------------------------------------------------------------
                % 2. Sessão Dedicada para o Tacômetro de Borda PFI0 / ctr0
                % -------------------------------------------------------------
                try
                    app.dqCtr = daq("ni");
                    addinput(app.dqCtr, devID, "ctr0", "EdgeCount");
                    val_init = read(app.dqCtr);
                    app.count_anterior = val_init{1, 1};
                catch
                    app.dqCtr = [];
                end
                
                % Aquisição Contínua em Background dos Sinais Analógicos (50 amostras = 20 Hz)
                app.dq.ScansAvailableFcnCount = 50;
                app.dq.ScansAvailableFcn = @(src, event) app.processarBlocoDAQ(src, event);
                app.dq.ErrorOccurredFcn = @(src, event) app.tratarErroHardware(src, event);
                
                d.Value = 1.0;
                d.Message = 'Canais configurados com sucesso! Iniciando ensaio...';
                pause(0.2);
                close(d);
                
                app.StatusLabel.Text = sprintf('Hardware %s Conectado (Amostragem: 1000 Hz | Logger: %d Hz).', devID, app.taxa_log_hz);
                app.StatusLabel.FontColor = [0.05, 0.55, 0.20];
                sucesso = true;
            catch ME
                if isvalid(d), close(d); end
                uialert(app.UIFigure, ['Não foi possível conectar com a placa de aquisição de dados. Verifique o cabo USB e a alimentação do túnel.' newline newline 'Detalhe Técnico: ' ME.message], 'Hardware Não Detectado', 'Icon', 'warning');
                app.dq = [];
                sucesso = false;
            end
        end

        % =================================================================
        % 12. CONTROLE OPERACIONAL DO SISTEMA
        % =================================================================
        function iniciarSistema(app, demo)
            app.modoDemo = demo;
            app.sistemaAtivo = true;
            app.buffer_idx = 0;
            app.ultimo_idx_forcas = 0;
            app.ultimo_idx_fluidos = 0;
            app.ultimo_idx_ventilador = 0;
            app.tempo_decorrido = 0.0;
            
            clearpoints(app.aLineLift);
            clearpoints(app.aLineDrag);
            clearpoints(app.aLineHinge);
            clearpoints(app.aLinePitot);
            clearpoints(app.aLineVenturi);
            clearpoints(app.aLineLogger);
            if ~isempty(app.aLineVentPitot) && isvalid(app.aLineVentPitot), clearpoints(app.aLineVentPitot); end
            if ~isempty(app.aLineVentVenturi) && isvalid(app.aLineVentVenturi), clearpoints(app.aLineVentVenturi); end
            if ~isempty(app.aLineVentTorque) && isvalid(app.aLineVentTorque), clearpoints(app.aLineVentTorque); end

            % Redefine escalas padrão estáveis (sem zoom microscópico em ruído 10^-3)
            if ~isempty(app.AxesForcasUnificado) && isvalid(app.AxesForcasUnificado)
                yyaxis(app.AxesForcasUnificado, 'left');
                app.AxesForcasUnificado.YLim = [-1.0, 5.0];
                yyaxis(app.AxesForcasUnificado, 'right');
                app.AxesForcasUnificado.YLim = [-0.5, 0.5];
                yyaxis(app.AxesForcasUnificado, 'left');
            end
            if ~isempty(app.AxesPitot) && isvalid(app.AxesPitot)
                app.AxesPitot.YLim = [-1.0, 15.0];
            end
            if ~isempty(app.AxesVenturi) && isvalid(app.AxesVenturi)
                app.AxesVenturi.YLim = [-1.0, 15.0];
            end

            app.tempo_inicio = tic;
            app.ultimo_tic = tic;
            app.tick_count = 0;
            app.tempo_hardware_base = 0;
            app.tensao_suavizada_torque  = 0.0;
            app.tensao_suavizada_lift    = 0.0;
            app.tensao_suavizada_drag    = 0.0;
            app.tensao_suavizada_hinge   = 0.0;
            app.tensao_suavizada_pitot   = app.tara_pitot;
            app.tensao_suavizada_venturi = app.tara_venturi;
            app.buffer_rpm_counts        = zeros(1, app.TAMANHO_JANELA_RPM);
            app.buffer_rpm_recents       = zeros(1, 5);
            app.count_anterior           = 0;
            app.count_unwrapped          = 0;
            app.rpm_estavel_display      = 0;

            app.StartButton.Enable = 'off';
            app.DemoButton.Enable  = 'off';
            app.StopButton.Enable  = 'on';
            app.ExportButton.Visible = 'off';
            app.StatusLamp.Color   = [0.1, 0.8, 0.2];

            if ~demo
                app.TaraButton.Enable = 'on'; % Tara habilitada apenas em leitura de hardware real
                sucesso = app.iniciarHardware();
                if sucesso && ~isempty(app.dq) && ~isempty(app.dq.Channels)
                    try
                        start(app.dq, "Continuous");
                        start(app.TimerPrincipal);
                        app.PanelControlesSimulacao.Visible = 'off';
                        app.PanelAvisoHardware.Visible      = 'off';
                    catch ME_daq_start
                        app.pararSistema();
                        uialert(app.UIFigure, ...
                            sprintf('Não foi possível iniciar a placa NI USB-6211:\n\n%s\n\nPossíveis causas:\n1. Outra janela do MATLAB ou software (ex: NI MAX) está com a placa aberta;\n2. A placa ficou reservada por uma sessão anterior (rode "daqreset" no Command Window do MATLAB).', ME_daq_start.message), ...
                            'Aviso de Hardware (DAQ)', 'Icon', 'warning');
                    end
                else
                    app.pararSistema();
                end
            else
                app.TaraButton.Enable = 'off'; % Na simulação virtual não se aplica tara mecânica
                app.PanelControlesSimulacao.Visible = 'on';
                app.PanelAvisoHardware.Visible      = 'off';
                app.StatusLabel.Text = 'Modo Simulação Ativo (Valores Sintéticos de Desenvolvimento) — Operação Virtual para Testes de Bancada.';
                app.StatusLabel.FontColor = [0.85, 0.40, 0.05];
                start(app.TimerPrincipal);
            end
        end

        function pararSistema(app)
            app.sistemaAtivo = false;
            if ~isempty(app.TimerPrincipal) && isvalid(app.TimerPrincipal)
                stop(app.TimerPrincipal);
            end

            if ~isempty(app.dq)
                try, app.dq.ScansAvailableFcn = []; catch, end
                try, app.dq.ErrorOccurredFcn = []; catch, end
                try, stop(app.dq); catch, end
                try, flush(app.dq); catch, end
                try, delete(app.dq); catch, end
                app.dq = [];
            end
            if ~isempty(app.dqCtr)
                try, stop(app.dqCtr); catch, end
                try, flush(app.dqCtr); catch, end
                try, delete(app.dqCtr); catch, end
                app.dqCtr = [];
            end

            % Congela o tempo final decorrido do ensaio para nunca avançar para o futuro vazio
            if app.buffer_idx > 0 && ~isempty(app.tempo_buffer)
                app.dados_finais    = app.dados_buffer(1:app.buffer_idx, :);
                app.tempo_final     = app.tempo_buffer(1:app.buffer_idx);
                app.tempo_decorrido = app.tempo_final(end);
            else
                if ~isempty(app.tempo_inicio)
                    app.tempo_decorrido = toc(app.tempo_inicio);
                else
                    app.tempo_decorrido = 0;
                end
            end

            app.StartButton.Enable = 'on';
            app.DemoButton.Enable  = 'on';
            app.StopButton.Enable  = 'off';
            app.TaraButton.Enable  = 'off';
            app.ExportButton.Visible = 'on';
            app.StatusLamp.Color   = [0.85, 0.2, 0.2];
            app.StatusLabel.Text   = sprintf('Ensaio Finalizado com Sucesso. Total de Amostras: %d (Duração: %.2f s).', app.buffer_idx, app.tempo_decorrido);
            app.StatusLabel.FontColor = [0.2, 0.2, 0.2];
            app.SinModoVal.Text    = '  SISTEMA PARADO  ';
            app.SinModoVal.FontColor = [0.4, 0.4, 0.4];

            % Oculta painéis de aviso e controles de simulação em repouso
            app.PanelControlesSimulacao.Visible = 'off';
            app.PanelAvisoHardware.Visible      = 'off';

            % Sincroniza todas as linhas e exibe o ensaio completo registrado
            app.sincronizarLinhasComBuffer();
            app.TabGroupSelectionChanged();
        end

        function executarTara(app)
            % Calibração de Tara/Zero Global (Células de Carga e Transdutores de Pressão Auto Tran 600D)
            if ~app.sistemaAtivo || app.modoDemo, return; end
            
            if app.habilitarCanalTorque
                app.tara_torque = app.tensao_suavizada_torque;
                app.torque_suavizado = 0;
            end
            if app.habilitarCanalLift
                app.tara_lift   = app.tensao_suavizada_lift;
                app.lift_suavizado   = 0;
            end
            if app.habilitarCanalDrag
                app.tara_drag   = app.tensao_suavizada_drag;
                app.drag_suavizado   = 0;
            end
            if app.habilitarCanalHinge
                app.tara_hinge  = app.tensao_suavizada_hinge;
                app.hinge_suavizado  = 0;
            end

            % Calibração de Zero dos Transdutores de Pressão Auto Tran 600D (Pitot e Venturi)
            if app.habilitarCanalPitot
                app.tara_pitot = app.tensao_suavizada_pitot;
                app.pitot_suavizado = 0;
                if ~isempty(app.CfgTaraPitotField) && isvalid(app.CfgTaraPitotField)
                    app.CfgTaraPitotField.Value = app.tara_pitot;
                end
            end
            if app.habilitarCanalVenturi
                app.tara_venturi = app.tensao_suavizada_venturi;
                app.venturi_suavizado = 0;
                if ~isempty(app.CfgTaraVenturiField) && isvalid(app.CfgTaraVenturiField)
                    app.CfgTaraVenturiField.Value = app.tara_venturi;
                end
            end

            app.StatusLabel.Text = sprintf('Tara/Zero Concluída: Pitot = %.4f V | Venturi = %.4f V | Células Zeradas.', app.tara_pitot, app.tara_venturi);
            app.StatusLabel.FontColor = [0.05, 0.55, 0.20];
        end

        function exportarDadosExcel(app)
            if app.buffer_idx == 0
                uialert(app.UIFigure, 'Nenhum dado registrado para exportar. Execute um ensaio primeiro.', 'Aviso', 'Icon', 'warning');
                return;
            end

            [file, path] = uiputfile({'*.csv', 'Arquivo CSV (*.csv)'; '*.xlsx', 'Planilha Excel (*.xlsx)'}, 'Salvar Dados do Ensaio', sprintf('Ensaio_TunelVento_%s.csv', datestr(now, 'yyyymmdd_HHMMSS')));
            if isequal(file, 0), return; end
            
            fullPath = fullfile(path, file);
            
            nomesColunas = {'Tempo_s', 'RPM', 'Torque_Nm', 'Lift_N', 'Drag_N', ...
                            'Hinge_Nm', 'Pitot_Pa', 'Venturi_Pa', 'Velocidade_ms', ...
                            'Potencia_W', 'Lift_kgf', 'Drag_kgf', 'Pitot_mmH2O', 'Venturi_mmH2O'};
            
            % Arredondamento estrito para 4 casas decimais em todas as grandezas exportadas
            dados_export = round([app.tempo_buffer(1:app.buffer_idx), app.dados_buffer(1:app.buffer_idx, :)], 4);
            tabelaExport = array2table(dados_export, 'VariableNames', nomesColunas);
            
            try
                if app.buffer_idx > 1048000 && endsWith(lower(fullPath), '.xlsx')
                    fullPath = regexprep(fullPath, '\.xlsx$', '.csv', 'ignorecase');
                    writetable(tabelaExport, fullPath);
                    uialert(app.UIFigure, sprintf('Ensaio possui %d amostras (> 1 milhão). Arquivo salvo em formato CSV:\n%s', app.buffer_idx, fullPath), 'Sucesso (CSV)', 'Icon', 'success');
                else
                    writetable(tabelaExport, fullPath);
                    uialert(app.UIFigure, sprintf('Dados exportados com sucesso! (%d amostras salvas a %d Hz)\nArquivo:\n%s', app.buffer_idx, app.taxa_log_hz, fullPath), 'Sucesso', 'Icon', 'success');
                end
            catch ME
                uialert(app.UIFigure, ['Falha ao exportar arquivo: ' ME.message], 'Erro de Exportação', 'Icon', 'error');
            end
        end

        function TaxaLogDropdownChanged(app, ~)
            if isempty(app.CfgTaxaLogDropdown) || ~isvalid(app.CfgTaxaLogDropdown), return; end
            app.taxa_log_hz = app.CfgTaxaLogDropdown.Value;
            if ~isempty(app.CfgTaxaLogInfoLabel) && isvalid(app.CfgTaxaLogInfoLabel)
                switch app.taxa_log_hz
                    case 20
                        app.CfgTaxaLogInfoLabel.Text = '📊 ~0.11 MB/min (~6.7 MB/h) | Leve (.xlsx)';
                        app.CfgTaxaLogInfoLabel.FontColor = [0.10 0.55 0.20];
                    case 100
                        app.CfgTaxaLogInfoLabel.Text = '📊 ~0.55 MB/min (~33 MB/h) | Moderado (.xlsx)';
                        app.CfgTaxaLogInfoLabel.FontColor = [0.10 0.40 0.75];
                    case 1000
                        app.CfgTaxaLogInfoLabel.Text = '⚠️ ~5.4 MB/min (~326 MB/h) | >17 min: use .csv';
                        app.CfgTaxaLogInfoLabel.FontColor = [0.80 0.40 0.05];
                end
            end
        end

        function abrirManualOperacao(app, ~, ~)
            try
                alvo = '';

                % 1. Busca relativa ao arquivo da própria classe app_v9 (funciona no MATLAB e compilado)
                appFile = which('app_v10');
                if ~isempty(appFile)
                    p1 = fullfile(fileparts(appFile), 'docs', 'Manual_do_Usuario_Tunel_Vento.pdf');
                    if exist(p1, 'file') == 2, alvo = p1; end
                end

                % 2. Se for aplicação compilada (.exe), busca recursiva em todo o ctfroot
                if isempty(alvo) && isdeployed
                    try
                        res = dir(fullfile(ctfroot, '**', 'Manual_do_Usuario_Tunel_Vento.pdf'));
                        if ~isempty(res)
                            alvo = fullfile(res(1).folder, res(1).name);
                        end
                    catch
                    end
                end

                % 3. Busca no diretório atual (pwd) ou caminhos relativos padrão
                if isempty(alvo)
                    candidatos = { ...
                        fullfile(pwd, 'docs', 'Manual_do_Usuario_Tunel_Vento.pdf'), ...
                        fullfile(fileparts(mfilename('fullpath')), 'docs', 'Manual_do_Usuario_Tunel_Vento.pdf'), ...
                        fullfile(pwd, 'Manual_do_Usuario_Tunel_Vento.pdf') ...
                    };
                    for i = 1:numel(candidatos)
                        if exist(candidatos{i}, 'file') == 2
                            alvo = candidatos{i};
                            break;
                        end
                    end
                end

                % 4. Fallback genérico: procura qualquer outro arquivo .pdf existente
                if isempty(alvo)
                    if isdeployed
                        resAny = dir(fullfile(ctfroot, '**', '*.pdf'));
                    else
                        resAny = dir(fullfile(pwd, 'docs', '*.pdf'));
                    end
                    if ~isempty(resAny)
                        alvo = fullfile(resAny(1).folder, resAny(1).name);
                    end
                end

                if isempty(alvo) || exist(alvo, 'file') ~= 2
                    uialert(app.UIFigure, ...
                        'O arquivo "Manual_do_Usuario_Tunel_Vento.pdf" não foi encontrado na pasta docs.', ...
                        'Documentação Não Encontrada', 'Icon', 'warning');
                    return;
                end

                % Abre diretamente no leitor padrão de PDF do Windows (Adobe Acrobat, Edge, Chrome, etc.)
                if ispc
                    winopen(alvo);
                else
                    open(alvo);
                end
            catch ME
                uialert(app.UIFigure, ['Erro ao abrir documentação: ' ME.message], 'Erro', 'Icon', 'error');
            end
        end

        function checkExit(app, ~, ~)
            if app.sistemaAtivo
                if app.modoDemo
                    tipoOp = 'Simulação Virtual (Demo)';
                else
                    tipoOp = 'Aquisição Real de Hardware (HW)';
                end
                selection = uiconfirm(app.UIFigure, ...
                    sprintf('O sistema está em operação ativa (%s)!\n\nDeseja interromper o ensaio e fechar o aplicativo agora?', tipoOp), ...
                    'Encerrar Sistema em Operação', 'Icon', 'warning', ...
                    'Options', {'Parar e Sair', 'Cancelar'}, 'DefaultOption', 2, 'CancelOption', 2);
                if ~strcmp(selection, 'Parar e Sair')
                    return;
                end
                app.pararSistema();
            else
                selection = uiconfirm(app.UIFigure, 'Deseja realmente encerrar o sistema e fechar o aplicativo?', ...
                    'Confirmar Saída', 'Icon', 'question', 'Options', {'Sim', 'Não'}, 'DefaultOption', 2, 'CancelOption', 2);
                if ~strcmp(selection, 'Sim')
                    return;
                end
            end
            
            % Encerramento limpo e liberação total de periféricos e threads
            delete(app);
        end

        % =================================================================
        % 13. CALLBACKS DA INTERFACE GRÁFICA
        % =================================================================
        function StartButtonPushed(app, ~)
            app.iniciarSistema(false);
        end

        function DemoButtonPushed(app, ~)
            app.iniciarSistema(true);
        end

        function StopButtonPushed(app, ~)
            app.pararSistema();
        end

        function TaraButtonPushed(app, ~)
            app.executarTara();
        end

        function ExportButtonPushed(app, ~)
            app.exportarDadosExcel();
        end

        function SliderRPMValueChanged(app, ~)
            app.simTargetRPM = app.SliderRPM.Value;
            app.SliderRPMValLabel.Text = sprintf('%.0f RPM', app.SliderRPM.Value);
        end

        function SliderAlphaValueChanged(app, ~)
            app.angulo_ataque = app.SliderAlpha.Value;
            app.SliderAlphaValLabel.Text = sprintf('%.1f°', app.angulo_ataque);
            app.atualizarDesenhoAirfoil();
        end

        function SetTestPreset(app, ~, ~)
            % Zera simultaneamente a rotação do ventilador e o ângulo de ataque
            app.SliderRPM.Value = 0;
            app.SliderRPMValueChanged([]);
            
            app.SliderAlpha.Value = 0.0;
            app.SliderAlphaValueChanged([]);
        end



        function LogCanalDropdownValueChanged(app, ~)
            app.atualizarGraficoLogger();
        end

        function ClearLogButtonPushed(app, ~)
            clearpoints(app.aLineLogger);
            app.LogStatMin.Text  = '---';
            app.LogStatMean.Text = '---';
            app.LogStatMax.Text  = '---';
            app.LogStatStd.Text  = '---';
        end

            end

    methods (Access = public)
        function RestaurarPadroesPushed(app, ~)
            if ~isempty(app.CfgKRPMField) && isvalid(app.CfgKRPMField)
                app.CfgKRPMField.Value = 1.0;
            end
            if ~isempty(app.CfgOffsetRPMField) && isvalid(app.CfgOffsetRPMField)
                app.CfgOffsetRPMField.Value = 0.0;
            end
            if ~isempty(app.CfgKTorqueField) && isvalid(app.CfgKTorqueField)
                app.CfgKTorqueField.Value = 1.0;
            end
            if ~isempty(app.CfgKLiftField) && isvalid(app.CfgKLiftField)
                app.CfgKLiftField.Value = 1.0;
            end
            if ~isempty(app.CfgKDragField) && isvalid(app.CfgKDragField)
                app.CfgKDragField.Value = 1.0;
            end
            if ~isempty(app.CfgKHingeField) && isvalid(app.CfgKHingeField)
                app.CfgKHingeField.Value = 1.0;
            end
            if ~isempty(app.CfgTaraPitotField) && isvalid(app.CfgTaraPitotField)
                app.CfgTaraPitotField.Value = 0.800;
            end
            if ~isempty(app.CfgTaraVenturiField) && isvalid(app.CfgTaraVenturiField)
                app.CfgTaraVenturiField.Value = 0.800;
            end
            if ~isempty(app.CfgAlphaField) && isvalid(app.CfgAlphaField)
                app.CfgAlphaField.Value = 0.08;
            end
            app.AplicarConfigPushed([]);
            if ~isempty(app.CfgInfoLabel) && isvalid(app.CfgInfoLabel)
                app.CfgInfoLabel.Text = 'Valores padrão de calibração restaurados e aplicados com sucesso!';
                app.CfgInfoLabel.FontColor = [0.10 0.40 0.75];
            end
        end

        function AplicarConfigPushed(app, ~)
            if ~isempty(app.CfgKRPMField) && isvalid(app.CfgKRPMField)
                app.fator_escala_rpm    = app.CfgKRPMField.Value;
            end
            if ~isempty(app.CfgOffsetRPMField) && isvalid(app.CfgOffsetRPMField)
                app.offset_rpm          = app.CfgOffsetRPMField.Value;
            end
            if ~isempty(app.CfgKTorqueField) && isvalid(app.CfgKTorqueField)
                app.fator_escala_torque = app.CfgKTorqueField.Value;
            end
            if ~isempty(app.CfgKLiftField) && isvalid(app.CfgKLiftField)
                app.fator_escala_lift   = app.CfgKLiftField.Value;
            end
            if ~isempty(app.CfgKDragField) && isvalid(app.CfgKDragField)
                app.fator_escala_drag   = app.CfgKDragField.Value;
            end
            if ~isempty(app.CfgKHingeField) && isvalid(app.CfgKHingeField)
                app.fator_escala_hinge  = app.CfgKHingeField.Value;
            end
            if ~isempty(app.CfgAlphaField) && isvalid(app.CfgAlphaField)
                app.alpha               = app.CfgAlphaField.Value;
            end
            if ~isempty(app.CfgTaraPitotField) && isvalid(app.CfgTaraPitotField)
                app.tara_pitot          = app.CfgTaraPitotField.Value;
            end
            if ~isempty(app.CfgTaraVenturiField) && isvalid(app.CfgTaraVenturiField)
                app.tara_venturi        = app.CfgTaraVenturiField.Value;
            end

            % Parâmetros físicos e fluidodinâmicos fixos (hardcoded para simulação e ensaios)
            app.rho_ar          = 1.103;
            app.area_ref        = 0.0144;
            app.comprimento_ref = 0.120;
            app.D_venturi       = 0.050;
            app.d_venturi       = 0.025;
            app.taxa_log_hz     = 1000;

            try
                sCfg.rho_ar = app.rho_ar;
                sCfg.tara_pitot = app.tara_pitot;
                sCfg.tara_venturi = app.tara_venturi;
                sCfg.tara_torque = app.tara_torque;
                sCfg.tara_lift = app.tara_lift;
                sCfg.tara_drag = app.tara_drag;
                sCfg.tara_hinge = app.tara_hinge;
                sCfg.taxa_log_hz = app.taxa_log_hz;
                sCfg.area_ref = app.area_ref;
                sCfg.comprimento_ref = app.comprimento_ref;
                sCfg.D_venturi = app.D_venturi;
                sCfg.d_venturi = app.d_venturi;
                sCfg.fator_escala_rpm = app.fator_escala_rpm;
                sCfg.offset_rpm = app.offset_rpm;
                sCfg.fator_escala_torque = app.fator_escala_torque;
                sCfg.fator_escala_lift = app.fator_escala_lift;
                sCfg.fator_escala_drag = app.fator_escala_drag;
                sCfg.fator_escala_hinge = app.fator_escala_hinge;
                sCfg.alpha = app.alpha;
                sCfg.habilitarCanalRPM = app.habilitarCanalRPM;
                sCfg.habilitarCanalTorque = app.habilitarCanalTorque;
                sCfg.habilitarCanalLift = app.habilitarCanalLift;
                sCfg.habilitarCanalDrag = app.habilitarCanalDrag;
                sCfg.habilitarCanalHinge = app.habilitarCanalHinge;
                sCfg.habilitarCanalPitot = app.habilitarCanalPitot;
                sCfg.habilitarCanalVenturi = app.habilitarCanalVenturi;
                save('config_tunel.mat', '-struct', 'sCfg');
                if ~isempty(app.CfgInfoLabel) && isvalid(app.CfgInfoLabel)
                    app.CfgInfoLabel.Text = sprintf('Configurações salvas e aplicadas com sucesso! (Salvo em %s)', datestr(now, 'HH:MM:SS'));
                    app.CfgInfoLabel.FontColor = [0.05 0.55 0.20];
                end
            catch ME
                if ~isempty(app.CfgInfoLabel) && isvalid(app.CfgInfoLabel)
                    app.CfgInfoLabel.Text = ['Erro ao salvar configurações: ' ME.message];
                    app.CfgInfoLabel.FontColor = [0.8 0.1 0.1];
                end
            end
        end

        % =================================================================
            end

    methods (Access = public)
        % -------------------------------------------------------------
        % 8.1. FILTRO DE FORÇAS INTERATIVO DO GRÁFICO (ESTILO POWERBI)
        % -------------------------------------------------------------
        function ForcasPlotFilterChanged(app, ~)
            if isempty(app.AxesForcasUnificado) || ~isvalid(app.AxesForcasUnificado), return; end
            
            % 1. Visibilidade da Sustentação L
            if app.CbPlotLift.Value
                app.aLineLift.Visible = 'on';
            else
                app.aLineLift.Visible = 'off';
            end
            
            % 2. Visibilidade do Arrasto D
            if app.CbPlotDrag.Value
                app.aLineDrag.Visible = 'on';
            else
                app.aLineDrag.Visible = 'off';
            end
            
            % 3. Visibilidade do Momento Hinge M_z
            if app.CbPlotHinge.Value
                app.aLineHinge.Visible = 'on';
                yyaxis(app.AxesForcasUnificado, 'right');
                app.AxesForcasUnificado.YColor = [0.45 0.20 0.65];
                ylabel(app.AxesForcasUnificado, 'Momento de Dobradiça Hinge M_z [N.m]', 'FontWeight', 'bold', 'FontSize', 11.5);
                val_max_h = max([abs(app.hinge_suavizado), 0.5]);
                app.AxesForcasUnificado.YLim = [-val_max_h, val_max_h];
            else
                app.aLineHinge.Visible = 'off';
                yyaxis(app.AxesForcasUnificado, 'right');
                app.AxesForcasUnificado.YColor = [0.85 0.85 0.85];
                ylabel(app.AxesForcasUnificado, '');
                app.AxesForcasUnificado.YLim = [-0.5, 0.5];
            end
            
            % Atualiza a legenda dinamicamente mostrando apenas as forças ativas
            vis_lines = [];
            if app.CbPlotLift.Value,  vis_lines = [vis_lines, app.aLineLift]; end
            if app.CbPlotDrag.Value,  vis_lines = [vis_lines, app.aLineDrag]; end
            if app.CbPlotHinge.Value, vis_lines = [vis_lines, app.aLineHinge]; end
            
            if ~isempty(vis_lines)
                legend(app.AxesForcasUnificado, vis_lines, 'Location', 'northwest', 'FontSize', 10.5, 'FontWeight', 'bold');
            else
                legend(app.AxesForcasUnificado, 'off');
            end
            
            % Retorna o foco principal para o eixo esquerdo
            yyaxis(app.AxesForcasUnificado, 'left');
            if ~app.CbPlotLift.Value && ~app.CbPlotDrag.Value
                app.AxesForcasUnificado.YColor = [0.85 0.85 0.85];
                ylabel(app.AxesForcasUnificado, '');
            else
                app.AxesForcasUnificado.YColor = [0.10 0.30 0.50];
                ylabel(app.AxesForcasUnificado, 'Forças Aerodinâmicas: Lift & Drag [N]', 'FontWeight', 'bold', 'FontSize', 11.5);
            end
            val_max_forcas = max([app.lift_suavizado, app.drag_suavizado, 5.0]);
            val_min_forcas = min([app.lift_suavizado, app.drag_suavizado, -1.0]);
            app.AxesForcasUnificado.YLim = [min(-1.0, floor(val_min_forcas - 0.5)), max(5.0, ceil(val_max_forcas + 0.5))];
        end

        function BtnPlotTodasPushed(app, ~)
            app.CbPlotLift.Value = true;
            app.CbPlotDrag.Value = true;
            app.CbPlotHinge.Value = true;
            app.ForcasPlotFilterChanged();
        end

        function BtnPlotNenhumaPushed(app, ~)
            app.CbPlotLift.Value = false;
            app.CbPlotDrag.Value = false;
            app.CbPlotHinge.Value = false;
            app.ForcasPlotFilterChanged();
        end

        % =================================================================
        % 14. GERENCIAMENTO DINÂMICO DE RESOLUÇÃO E REDIMENSIONAMENTO (PÚBLICO)
        % =================================================================
        function redimensionarInterface(app)
            if isempty(app.UIFigure) || ~isvalid(app.UIFigure), return; end
            pos = app.UIFigure.Position;
            W = pos(3); H = pos(4);
            if W < 800 || H < 500, return; end
            
            % 1. Header Superior Full-Width
            if ~isempty(app.HeaderPanel) && isvalid(app.HeaderPanel)
                app.HeaderPanel.Position = [0, H - 65, W, 65];
                if ~isempty(app.TitleLabel) && isvalid(app.TitleLabel)
                    app.TitleLabel.Position  = [20, 16, min(750, max(400, W - 780)), 32];
                end
                if ~isempty(app.ExitButton) && isvalid(app.ExitButton)
                    app.ExitButton.Position   = [W - 48,  16, 36,  32];
                    app.TaraButton.Position   = [W - 160, 16, 100, 32];
                    app.StopButton.Position   = [W - 295, 16, 125, 32];
                    app.StartButton.Position  = [W - 460, 16, 155, 32];
                    if ~isempty(app.DemoButton) && isvalid(app.DemoButton)
                        app.DemoButton.Position = [W - 615, 16, 145, 32];
                        app.DemoButton.Visible = 'off';
                    end
                    app.ExportButton.Position = [W - 595, 16, 125, 32];
                end
            end
            
            % 2. Footer / Status Bar Full-Width
            if ~isempty(app.FooterPanel) && isvalid(app.FooterPanel)
                app.FooterPanel.Position = [0, 0, W, 36];
                if ~isempty(app.StatusLabel) && isvalid(app.StatusLabel)
                    app.StatusLabel.Position = [42, 8, max(200, W - 60), 20];
                end
            end
            
            % 3. TabGroup Central Full-Width e Full-Height
            if ~isempty(app.TabGroup) && isvalid(app.TabGroup)
                tabW = W - 16;
                tabH = max(300, H - 105);
                app.TabGroup.Position = [8, 38, tabW, tabH];
                
                % Altura util interna da aba (descontando a barra superior do uitabgroup de ~28 px)
                innerH = tabH - 28;
                Y_top = innerH - 14;   % Topo alinhado com a Sinotica (sem corte e sem folga excessiva)    % Topo colado na barra de abas (respiro mínimo de 4px, igual à Sinótica)
                Y_bottom = 10;         % Base inferior limpa
                H_content = Y_top - Y_bottom; % Altura total útil para componentes
                
                % ---------------------------------------------------------
                % ABA 1: TELA SINOTICA (Sem cortes de escala ou limites)
                % ---------------------------------------------------------
                W_card = min(380, max(290, tabW * 0.23));
                diaW = max(500, tabW - W_card - 45);
                diaH = max(240, innerH - 144);
                h_ctrl = 112;

                if ~isempty(app.AxesSinotica) && isvalid(app.AxesSinotica)
                    app.AxesSinotica.Position = [20, 130, diaW, diaH];
                end
                
                if ~isempty(app.PanelControlesSimulacao) && isvalid(app.PanelControlesSimulacao)
                    app.PanelControlesSimulacao.Position = [20, 10, diaW, h_ctrl];
                    if ~isempty(app.LabelAvisoSimulacao) && isvalid(app.LabelAvisoSimulacao)
                        app.LabelAvisoSimulacao.Position = [12, 86, diaW - 24, 18];
                    end
                    w_col = (diaW - 50) / 3;
                    X1 = 15;
                    X2 = 25 + w_col;
                    X3 = 35 + 2 * w_col;
                    if ~isempty(app.LabelControleRPM) && isvalid(app.LabelControleRPM)
                        app.LabelControleRPM.Position = [X1, 62, 180, 20];
                    end
                    if ~isempty(app.SliderRPM) && isvalid(app.SliderRPM)
                        w_sl1 = max(110, w_col - 95);
                        app.SliderRPM.Position = [X1, 38, w_sl1, 3];
                        app.SliderRPMValLabel.Position = [X1 + w_sl1 + 8, 30, 85, 24];
                    end
                    if ~isempty(app.LabelControleAlpha) && isvalid(app.LabelControleAlpha)
                        app.LabelControleAlpha.Position = [X2, 62, 210, 20];
                    end
                    if ~isempty(app.SliderAlpha) && isvalid(app.SliderAlpha)
                        w_sl2 = max(110, w_col - 85);
                        app.SliderAlpha.Position = [X2, 38, w_sl2, 3];
                        app.SliderAlphaValLabel.Position = [X2 + w_sl2 + 8, 30, 75, 24];
                    end
                    if ~isempty(app.BtnPresetZero) && isvalid(app.BtnPresetZero)
                        w_btn = min(220, max(140, w_col - 30));
                        x_btn = X3 + (w_col - 10 - w_btn) / 2;
                        app.BtnPresetZero.Position = [x_btn, 22, w_btn, 48];
                    end
                end
                if ~isempty(app.PanelAvisoHardware) && isvalid(app.PanelAvisoHardware)
                    app.PanelAvisoHardware.Position = [20, 10, diaW, h_ctrl];
                    if ~isempty(app.LabelAvisoHardware) && isvalid(app.LabelAvisoHardware)
                        app.LabelAvisoHardware.Position = [15, 25, diaW - 30, 62];
                    end
                end

                % Telemetria Lateral Direita (Cards com Fontes Grandes e Imponentes)
                xR = diaW + 30;
                W_card_eff = tabW - xR - 15;
                if ~isempty(app.SinStatusPanel) && isvalid(app.SinStatusPanel)
                    app.SinStatusPanel.Position = [xR, 10, W_card_eff, 72];
                end
                if ~isempty(app.SinCardPanels) && iscell(app.SinCardPanels)
                    H_cards = (innerH - 10) - 88;
                    h_step = floor(H_cards / 7);
                    h_box = max(52, h_step - 5);
                    for k = 1:min(7, length(app.SinCardPanels))
                        p_card = app.SinCardPanels{k};
                        if ~isempty(p_card) && isvalid(p_card)
                            y_box = 88 + (7 - k) * h_step;
                            p_card.Position = [xR, y_box, W_card_eff, h_box];
                            ch = p_card.Children;
                            for cidx = 1:length(ch)
                                child = ch(cidx);
                                if isa(child, 'matlab.ui.control.Lamp')
                                    child.Position = [12, h_box - 22, 14, 14];
                                elseif isa(child, 'matlab.ui.control.Label')
                                    if strcmp(child.HorizontalAlignment, 'right')
                                        child.Position = [12, 4, W_card_eff - 24, h_box - 26];
                                        child.FontSize = 16;
                                    else
                                        child.Position = [34, h_box - 24, W_card_eff - 45, 18];
                                    end
                                end
                            end
                        end
                    end
                end

                % ---------------------------------------------------------
                % ABA 2: FORÇAS AERODINÂMICAS (GRÁFICO EXPANDIDO + FILTRO POWERBI)
                % ---------------------------------------------------------
                w_kpi = min(400, max(320, floor(tabW * 0.22)));
                h_card_f = floor((H_content - 16) / 3);
                
                % Dimensoes do gauge com folga generosa da linha de titulo
                sz_g = min(w_kpi - 40, h_card_f - 86);
                gx = floor((w_kpi - sz_g) / 2);
                gy = 44 + floor((h_card_f - 80 - sz_g) / 2);
                
                % Card 1: Lift (topo perfeitamente alinhado abaixo das abas)
                if ~isempty(app.PanelCardLift) && isvalid(app.PanelCardLift)
                    app.PanelCardLift.Position = [12, Y_bottom + 2*(h_card_f + 8), w_kpi, h_card_f];
                    if ~isempty(app.GaugeLift) && isvalid(app.GaugeLift)
                        app.GaugeLift.Position = [gx, gy, sz_g, sz_g];
                    end
                    if ~isempty(app.LabelTitleLift) && isvalid(app.LabelTitleLift)
                        app.LabelTitleLift.Position = [10, 26, w_kpi - 20, 16];
                    end
                    if ~isempty(app.LabelLiftVal) && isvalid(app.LabelLiftVal)
                        app.LabelLiftVal.Position = [10, 4, w_kpi - 20, 24];
                    end
                end
                % Card 2: Drag (meio)
                if ~isempty(app.PanelCardDrag) && isvalid(app.PanelCardDrag)
                    app.PanelCardDrag.Position = [12, Y_bottom + h_card_f + 8, w_kpi, h_card_f];
                    if ~isempty(app.GaugeDrag) && isvalid(app.GaugeDrag)
                        app.GaugeDrag.Position = [gx, gy, sz_g, sz_g];
                    end
                    if ~isempty(app.LabelTitleDrag) && isvalid(app.LabelTitleDrag)
                        app.LabelTitleDrag.Position = [10, 26, w_kpi - 20, 16];
                    end
                    if ~isempty(app.LabelDragVal) && isvalid(app.LabelDragVal)
                        app.LabelDragVal.Position = [10, 4, w_kpi - 20, 24];
                    end
                end
                % Card 3: Hinge (base)
                if ~isempty(app.PanelCardHinge) && isvalid(app.PanelCardHinge)
                    app.PanelCardHinge.Position = [12, Y_bottom, w_kpi, h_card_f];
                    if ~isempty(app.GaugeHinge) && isvalid(app.GaugeHinge)
                        app.GaugeHinge.Position = [gx, gy, sz_g, sz_g];
                    end
                    if ~isempty(app.LabelTitleHinge) && isvalid(app.LabelTitleHinge)
                        app.LabelTitleHinge.Position = [10, 26, w_kpi - 20, 16];
                    end
                    if ~isempty(app.LabelHingeVal) && isvalid(app.LabelHingeVal)
                        app.LabelHingeVal.Position = [10, 4, w_kpi - 20, 24];
                    end
                end

                % Coluna Direita: Barra de Filtros PowerBI + Grafico Unificado Expandido
                x_forcas_r = w_kpi + 24;
                w_forcas_r = tabW - x_forcas_r - 16;
                h_bar_filtro = 32;
                y_bar_filtro = Y_top - h_bar_filtro;

                if ~isempty(app.PanelFiltroForcas) && isvalid(app.PanelFiltroForcas)
                    app.PanelFiltroForcas.Position = [x_forcas_r, y_bar_filtro, w_forcas_r, h_bar_filtro];
                    if ~isempty(app.BtnPlotNenhuma) && isvalid(app.BtnPlotNenhuma)
                        app.BtnPlotNenhuma.Position = [w_forcas_r - 72, 4, 62, 24];
                    end
                    if ~isempty(app.BtnPlotTodas) && isvalid(app.BtnPlotTodas)
                        app.BtnPlotTodas.Position = [w_forcas_r - 140, 4, 62, 24];
                    end
                end

                y_plot_uni = Y_bottom;
                h_plot_uni = y_bar_filtro - y_plot_uni - 6;

                if ~isempty(app.AxesForcasUnificado) && isvalid(app.AxesForcasUnificado)
                    app.AxesForcasUnificado.Position = [x_forcas_r, y_plot_uni, w_forcas_r, h_plot_uni];
                end
                if ~isempty(app.AxesLift) && isvalid(app.AxesLift) && app.AxesLift ~= app.AxesForcasUnificado
                    app.AxesLift.Position = [x_forcas_r, y_plot_uni, w_forcas_r, h_plot_uni];
                end

                % ---------------------------------------------------------
                % ABA 3: PRESSÕES & MANOMETRIA (50/50: MANÔMETROS EM U E GRÁFICOS)
                % ---------------------------------------------------------
                w_half = floor((tabW - 32) / 2);
                w_mano_col = w_half;
                x_mano = 10;
                x_plots = x_mano + w_mano_col + 12;
                w_plots_col = tabW - x_plots - 10;

                % Metade Esquerda: Manômetros em U de Coluna Líquida
                if ~isempty(app.PanelManometrosU) && isvalid(app.PanelManometrosU)
                    app.PanelManometrosU.Position = [x_mano, Y_bottom, w_mano_col, H_content];
                    w_each_m = floor((w_mano_col - 24) / 2);
                    
                    if ~isempty(app.LabelManoPitotTitle) && isvalid(app.LabelManoPitotTitle)
                        app.LabelManoPitotTitle.Position = [12, H_content - 20, w_each_m, 1];
                    end
                    if ~isempty(app.LabelManoPitotVal) && isvalid(app.LabelManoPitotVal)
                        app.LabelManoPitotVal.Position = [12, H_content - 66, w_each_m, 28];
                    end
                    if ~isempty(app.LabelManoPitotLevels) && isvalid(app.LabelManoPitotLevels)
                        app.LabelManoPitotLevels.Position = [12, H_content - 96, w_each_m, 24];
                    end
                    
                    if ~isempty(app.LabelManoVenturiTitle) && isvalid(app.LabelManoVenturiTitle)
                        app.LabelManoVenturiTitle.Position = [12 + w_each_m, H_content - 20, w_each_m, 1];
                    end
                    if ~isempty(app.LabelManoVenturiVal) && isvalid(app.LabelManoVenturiVal)
                        app.LabelManoVenturiVal.Position = [12 + w_each_m, H_content - 66, w_each_m, 28];
                    end
                    if ~isempty(app.LabelManoVenturiLevels) && isvalid(app.LabelManoVenturiLevels)
                        app.LabelManoVenturiLevels.Position = [12 + w_each_m, H_content - 96, w_each_m, 24];
                    end
                    
                    % Ajuste proporcional das coordenadas dos eixos (Aspecto 17:28 sem distorção nem corte)
                    h_ax_avail = H_content - 114;
                    w_ax_avail = w_each_m - 20;
                    w_ax = min(w_ax_avail, floor(h_ax_avail * (17 / 28)));
                    h_ax = floor(w_ax * (28 / 17));
                    x_ax1 = 12 + floor((w_each_m - w_ax) / 2);
                    x_ax2 = 12 + w_each_m + floor((w_each_m - w_ax) / 2);
                    y_ax = 8 + floor((h_ax_avail - h_ax) / 2);
                    
                    if ~isempty(app.AxesManometroPitot) && isvalid(app.AxesManometroPitot)
                        app.AxesManometroPitot.Position = [x_ax1, y_ax, w_ax, h_ax];
                    end
                    if ~isempty(app.AxesManometroVenturi) && isvalid(app.AxesManometroVenturi)
                        app.AxesManometroVenturi.Position = [x_ax2, y_ax, w_ax, h_ax];
                    end
                end

                % Metade Direita: Gráficos Temporais Empilhados
                h_p_box = floor((H_content - 12) / 2);
                if ~isempty(app.AxesPitot) && isvalid(app.AxesPitot)
                    app.AxesPitot.Position = [x_plots, Y_bottom + h_p_box + 12, w_plots_col, h_p_box];
                end
                if ~isempty(app.AxesVenturi) && isvalid(app.AxesVenturi)
                    app.AxesVenturi.Position = [x_plots, Y_bottom, w_plots_col, h_p_box];
                end

                % ---------------------------------------------------------
                % ABA 5: ENSAIO DE VENTILADORES (MÁQUINAS DE FLUXO)
                % ---------------------------------------------------------
                y_top_v  = tabH - 90;
                y_sub_v  = tabH - 114;
                h_card_v = 88;
                y_card_v = tabH - 128 - h_card_v;
                w_gap_v  = 14;
                w_card_v = floor((tabW - 40 - 3 * w_gap_v) / 4);

                if ~isempty(app.LabelVentTitle) && isvalid(app.LabelVentTitle)
                    app.LabelVentTitle.Position = [20, y_top_v, tabW - 40, 24];
                end
                if ~isempty(app.LabelVentSub) && isvalid(app.LabelVentSub)
                    app.LabelVentSub.Position = [20, y_sub_v, tabW - 40, 18];
                end
                if ~isempty(app.PanelVentCards) && iscell(app.PanelVentCards)
                    for k_c = 1:min(4, length(app.PanelVentCards))
                        p_c = app.PanelVentCards{k_c};
                        if ~isempty(p_c) && isvalid(p_c)
                            p_c.Position = [20 + (k_c - 1) * (w_card_v + w_gap_v), y_card_v, w_card_v, h_card_v];
                        end
                    end
                end
                if ~isempty(app.AxesVentilador) && isvalid(app.AxesVentilador)
                    y_ax_v = 15;
                    h_ax_v = max(120, y_card_v - y_ax_v - 12);
                    app.AxesVentilador.Position = [20, y_ax_v, tabW - 40, h_ax_v];
                end
            end
        end
    end

    methods (Access = private)
        % 15. CONSTRUÇÃO COMPLETA DA INTERFACE (TEMA CLARO ACADÊMICO FULLSCREEN)
        % =================================================================
        function createComponents(app)
            % Paleta de Cores Acadêmica (Scientific Publication Light Theme)
            BG        = [0.96 0.97 0.98];
            PNL       = [1.00 1.00 1.00];
            BORDER    = [0.85 0.88 0.92];
            HEADER_BG = [0.12 0.14 0.18];
            TEXT_DARK = [0.20 0.22 0.26];
            TEXT_MUT  = [0.45 0.50 0.58];
            GRN       = [0.10 0.65 0.30];
            ORG       = [0.88 0.45 0.08];
            RED       = [0.85 0.20 0.20];
            TEL       = [0.10 0.55 0.60];
            PRP       = [0.45 0.20 0.65];
            C_LIFT    = [0.00 0.45 0.74];
            C_DRAG    = [0.85 0.33 0.10];
            C_LD      = [0.10 0.60 0.25];
            C_PIT     = [0.00 0.55 0.65];
            C_VEL     = [0.45 0.20 0.65];

            % Resolução Nativa do Monitor
            scr = get(0, 'ScreenSize');
            scrW = max(1366, scr(3));
            scrH = max(768, scr(4));

            % Janela Principal em Modo Tela Cheia
            app.UIFigure = uifigure('Visible', 'off');
            app.UIFigure.AutoResizeChildren = 'off';
            app.UIFigure.Position = [1 1 scrW scrH];
            app.UIFigure.Name = 'DAS Wind Tunnel - SCADA Interface | Italia Didacta PN 20 DNT';
            app.UIFigure.Color = BG;
            app.UIFigure.WindowState = 'fullscreen';
            app.UIFigure.SizeChangedFcn = @(s, e) app.redimensionarInterface();
            app.UIFigure.CloseRequestFcn = @(s, e) app.checkExit();

            % --- Header Superior Escuro Full-Width ---
            app.HeaderPanel = uipanel(app.UIFigure, 'BackgroundColor', HEADER_BG, 'BorderType', 'none', 'Position', [0 scrH-65 scrW 65]);
            
            app.TitleLabel = uilabel(app.HeaderPanel);
            app.TitleLabel.Text = 'DAS WIND TUNNEL  |  Bancada Italia Didacta PN 20 DNT  |  Escola Politécnica PUCPR';
            app.TitleLabel.FontSize = 14;
            app.TitleLabel.FontName = 'Segoe UI';
            app.TitleLabel.FontWeight = 'bold';
            app.TitleLabel.FontColor = [0.95 0.95 0.95];
            app.TitleLabel.Position = [20 16 min(750, max(400, scrW-780)) 32];

            % Botões de Ação do Header (Alinhados à Direita)
            app.ExportButton = uibutton(app.HeaderPanel, 'push');
            app.ExportButton.Text = 'Exportar Dados';
            app.ExportButton.BackgroundColor = TEL;
            app.ExportButton.FontColor = [1 1 1];
            app.ExportButton.FontName = 'Segoe UI';
            app.ExportButton.FontWeight = 'bold';
            app.ExportButton.Position = [scrW - 595, 16, 125, 32];
            app.ExportButton.ButtonPushedFcn = createCallbackFcn(app, @ExportButtonPushed, true);

            app.DemoButton = uibutton(app.HeaderPanel, 'push');
            app.DemoButton.Text = 'Simulação (Demo)';
            app.DemoButton.BackgroundColor = ORG;
            app.DemoButton.FontColor = [1 1 1];
            app.DemoButton.FontName = 'Segoe UI';
            app.DemoButton.FontWeight = 'bold';
            app.DemoButton.Position = [scrW - 615, 16, 145, 32];
            app.DemoButton.Visible = 'off';
            app.DemoButton.ButtonPushedFcn = createCallbackFcn(app, @DemoButtonPushed, true);

            app.StartButton = uibutton(app.HeaderPanel, 'push');
            app.StartButton.Text = 'Iniciar Leitura (HW)';
            app.StartButton.BackgroundColor = GRN;
            app.StartButton.FontColor = [1 1 1];
            app.StartButton.FontName = 'Segoe UI';
            app.StartButton.FontWeight = 'bold';
            app.StartButton.Position = [scrW - 460, 16, 155, 32];
            app.StartButton.ButtonPushedFcn = createCallbackFcn(app, @StartButtonPushed, true);

            app.StopButton = uibutton(app.HeaderPanel, 'push');
            app.StopButton.Text = 'Parar Sistema';
            app.StopButton.BackgroundColor = RED;
            app.StopButton.FontColor = [1 1 1];
            app.StopButton.FontName = 'Segoe UI';
            app.StopButton.FontWeight = 'bold';
            app.StopButton.Position = [scrW - 295, 16, 125, 32];
            app.StopButton.Enable = 'off';
            app.StopButton.ButtonPushedFcn = createCallbackFcn(app, @StopButtonPushed, true);

            app.TaraButton = uibutton(app.HeaderPanel, 'push');
            app.TaraButton.Text = 'Tara / Zero';
            app.TaraButton.BackgroundColor = PRP;
            app.TaraButton.FontColor = [1 1 1];
            app.TaraButton.FontName = 'Segoe UI';
            app.TaraButton.FontWeight = 'bold';
            app.TaraButton.Tooltip = 'Calibração de Tara/Zero (Habilitado apenas durante a Leitura de Hardware Real)';
            app.TaraButton.Position = [scrW - 160, 16, 100, 32];
            app.TaraButton.Enable = 'off';
            app.TaraButton.ButtonPushedFcn = createCallbackFcn(app, @TaraButtonPushed, true);

            % Botão de Fechar Aplicação no Canto Superior Direito
            app.ExitButton = uibutton(app.HeaderPanel, 'push');
            app.ExitButton.Text = '✕';
            app.ExitButton.BackgroundColor = [0.20 0.24 0.32];
            app.ExitButton.FontColor = [0.9 0.4 0.4];
            app.ExitButton.FontName = 'Segoe UI';
            app.ExitButton.FontWeight = 'bold';
            app.ExitButton.FontSize = 14;
            app.ExitButton.Position = [scrW - 48, 16, 36, 32];
            app.ExitButton.ButtonPushedFcn = createCallbackFcn(app, @checkExit, true);

            % --- Rodapé / Status Bar Full-Width ---
            app.FooterPanel = uipanel(app.UIFigure, 'BackgroundColor', PNL, 'BorderColor', BORDER, 'Position', [0 0 scrW 36]);

            app.StatusLamp = uilamp(app.FooterPanel);
            app.StatusLamp.Position = [16 10 16 16];
            app.StatusLamp.Color = [0.85 0.20 0.20];

            app.StatusLabel = uilabel(app.FooterPanel);
            app.StatusLabel.Text = 'Sistema Pronto — Clique em [Iniciar Leitura (HW)] para iniciar a amostragem da bancada.';
            app.StatusLabel.FontSize = 11;
            app.StatusLabel.FontName = 'Segoe UI';
            app.StatusLabel.FontColor = TEXT_DARK;
            app.StatusLabel.Position = [42 8 scrW - 60 20];

            % --- Container Central de Abas Full-Width e Full-Height ---
            tabW = scrW - 16;
            tabH = scrH - 105;
            innerH = tabH - 38;
            app.TabGroup = uitabgroup(app.UIFigure, 'Position', [8 38 tabW tabH]);
            app.TabGroup.SelectionChangedFcn = createCallbackFcn(app, @TabGroupSelectionChanged, true);

            % =============================================================
            % TAB 1: TELA SINÓTICA (EXPANDIDA E RESPONSIVA)
            % =============================================================
            app.TabSinotica = uitab(app.TabGroup, 'Title', 'Tela Sinótica', 'BackgroundColor', BG);

            W_card = min(360, max(280, tabW * 0.23));
            diaW = max(500, tabW - W_card - 45);
            diaH = max(240, innerH - 105);

            app.AxesSinotica = uiaxes(app.TabSinotica, 'Position', [20 92 diaW diaH], 'Color', [1 1 1], 'XColor', 'none', 'YColor', 'none');
            app.AxesSinotica.Toolbar.Visible = 'off';
            disableDefaultInteractivity(app.AxesSinotica);
            app.AxesSinotica.XLim = [0 10.1];
            app.AxesSinotica.YLim = [0 6.4];
            app.AxesSinotica.DataAspectRatio = [1 1 1];
            hold(app.AxesSinotica, 'on');

            % --- BANCADA ESTRUTURAL METÁLICA (CHASSIS INFERIOR) ---
            plot(app.AxesSinotica, [0.3 9.8], [0.55 0.55], 'Color', [0.65 0.70 0.78], 'LineWidth', 2.5);
            plot(app.AxesSinotica, [0.3 9.8], [0.51 0.51], 'Color', [0.80 0.84 0.90], 'LineWidth', 1);
            for xp = [0.85, 3.0, 6.05, 9.0]
                plot(app.AxesSinotica, [xp xp], [0.20 0.51], 'Color', [0.65 0.70 0.78], 'LineWidth', 2.5);
            end

            % --- 1. MOTOR-INSUFLADOR: MOTOR NA BASE INFERIOR + TRANSMISSÃO + ROTOR ---
            % Coluna Mecânica de Transmissão (Mancal de Rolamentos e Acoplamento)
            fill(app.AxesSinotica, [0.98 1.22 1.22 0.98], [1.50 1.50 3.50 3.50], [0.88 0.90 0.94], 'EdgeColor', [0.45 0.50 0.58], 'LineWidth', 1.5);
            text(app.AxesSinotica, 1.10, 2.50, 'Eixo', 'Color', [0.40 0.45 0.55], 'FontSize', 7, 'Rotation', 90, 'HorizontalAlignment', 'center', 'FontWeight', 'bold');

            % Carcaça Aerodinâmica do Insuflador (Duto 100% Livre e Desobstruído)
            fill(app.AxesSinotica, [0.3 1.9 1.9 0.3], [1.8 1.8 5.2 5.2], [0.98 0.94 0.94], 'EdgeColor', [0.80 0.25 0.25], 'LineWidth', 2);

            % Rotor Tri-pá Giratório Industrial
            xc_r = 1.1; yc_r = 3.5; R_r = 0.62;
            th1 = 0; th2 = 2*pi/3; th3 = 4*pi/3;
            bx = [xc_r, xc_r + R_r*cos(th1), NaN, xc_r, xc_r + R_r*cos(th2), NaN, xc_r, xc_r + R_r*cos(th3)];
            by = [yc_r, yc_r + R_r*sin(th1), NaN, yc_r, yc_r + R_r*sin(th2), NaN, yc_r, yc_r + R_r*sin(th3)];
            
            app.RotorBladesPlot = plot(app.AxesSinotica, bx, by, 'Color', [0.30 0.35 0.42], 'LineWidth', 11);
            app.RotorHubPlot = plot(app.AxesSinotica, xc_r, yc_r, 'o', 'MarkerSize', 22, 'MarkerFaceColor', [0.22 0.26 0.32], 'MarkerEdgeColor', [0.10 0.15 0.20], 'LineWidth', 2);
            text(app.AxesSinotica, xc_r, yc_r, 'FAN', 'Color', [0.90 0.95 1.00], 'FontSize', 7, 'HorizontalAlignment', 'center', 'FontWeight', 'bold');
            
            text(app.AxesSinotica, 1.1, 5.6, '1. Ventilador', 'Color', [0.70 0.15 0.15], 'FontSize', 9.5, 'HorizontalAlignment', 'center', 'FontWeight', 'bold');

            % Motor Elétrico na Base Inferior Externa
            fill(app.AxesSinotica, [0.65 1.55 1.55 0.65], [0.65 0.65 1.50 1.50], [0.28 0.45 0.65], 'EdgeColor', [0.15 0.25 0.40], 'LineWidth', 1.5);
            for y_fin = [0.85, 1.05, 1.25]
                plot(app.AxesSinotica, [0.65 1.55], [y_fin y_fin], 'Color', [0.45 0.60 0.80], 'LineWidth', 1.2);
            end
            fill(app.AxesSinotica, [0.58 0.65 0.65 0.58], [0.75 0.75 1.40 1.40], [0.22 0.35 0.52], 'EdgeColor', [0.15 0.25 0.40], 'LineWidth', 1.2); % Grade traseira
            fill(app.AxesSinotica, [0.95 1.25 1.25 0.95], [1.50 1.50 1.68 1.68], [0.22 0.35 0.52], 'EdgeColor', [0.15 0.25 0.40], 'LineWidth', 1.2); % Caixa de bornes
            fill(app.AxesSinotica, [0.72 0.88 0.88 0.72], [0.55 0.55 0.65 0.65], [0.35 0.40 0.45], 'EdgeColor', 'none'); % Sapata fixação
            fill(app.AxesSinotica, [1.32 1.48 1.48 1.32], [0.55 0.55 0.65 0.65], [0.35 0.40 0.45], 'EdgeColor', 'none'); % Sapata fixação
            text(app.AxesSinotica, 1.10, 1.08, 'Motor', 'Color', [1 1 1], 'FontSize', 8, 'HorizontalAlignment', 'center', 'FontWeight', 'bold');

            % --- 2. CONDICIONADOR: BOCAL DE CONTRAÇÃO, FAVO DE MEL E TELAS ---
            fill(app.AxesSinotica, [2.1 3.9 3.9 2.1], [1.8 2.5 4.5 5.2], [0.90 0.94 0.98], 'EdgeColor', [0.25 0.45 0.70], 'LineWidth', 2);
            text(app.AxesSinotica, 3.0, 5.6, '2. Condicionador', 'Color', [0.15 0.35 0.65], 'FontSize', 9.5, 'HorizontalAlignment', 'center', 'FontWeight', 'bold');

            % Tela de Assentamento 1 (Montante - contida rigorosamente no duto)
            plot(app.AxesSinotica, [2.50 2.50], [2.00 5.00], 'Color', [0.30 0.50 0.70], 'LineWidth', 1.8, 'LineStyle', '--');

            % Bloco Estrutural do Favo de Mel (Honeycomb - alinhador de filetes)
            fill(app.AxesSinotica, [2.80 3.20 3.20 2.80], [2.12 2.27 4.73 4.88], [0.84 0.90 0.96], 'EdgeColor', [0.25 0.45 0.70], 'LineWidth', 1.5);
            for y_cell = [2.5, 2.9, 3.3, 3.7, 4.1, 4.5]
                plot(app.AxesSinotica, [2.80 3.20], [y_cell y_cell], 'Color', [0.40 0.60 0.80], 'LineWidth', 1);
            end
            plot(app.AxesSinotica, [2.93 2.93], [2.17 4.83], 'Color', [0.40 0.60 0.80], 'LineWidth', 1, 'LineStyle', ':');
            plot(app.AxesSinotica, [3.07 3.07], [2.22 4.78], 'Color', [0.40 0.60 0.80], 'LineWidth', 1, 'LineStyle', ':');

            % Tela de Assentamento 2 (Jusante - contida rigorosamente no duto)
            plot(app.AxesSinotica, [3.50 3.50], [2.38 4.62], 'Color', [0.30 0.50 0.70], 'LineWidth', 1.8, 'LineStyle', '--');

            % --- 3. CÂMARA DE TESTES ---
            fill(app.AxesSinotica, [4.2 7.9 7.9 4.2], [2.2 2.2 4.8 4.8], [0.96 0.98 1.00], 'EdgeColor', [0.15 0.45 0.85], 'LineWidth', 2);
            text(app.AxesSinotica, 6.05, 5.6, '3. Câmara de Testes', 'Color', [0.10 0.35 0.75], 'FontSize', 9.5, 'HorizontalAlignment', 'center', 'FontWeight', 'bold');

            % Filetes de Escoamento Aerodinâmico Suaves (Streamlines de Referência)
            xs_stream = linspace(4.2, 7.9, 40);
            plot(app.AxesSinotica, xs_stream, 4.30 * ones(size(xs_stream)), 'Color', [0.60 0.78 0.94], 'LineStyle', ':', 'LineWidth', 1);
            plot(app.AxesSinotica, xs_stream, 2.70 * ones(size(xs_stream)), 'Color', [0.60 0.78 0.94], 'LineStyle', ':', 'LineWidth', 1);

            % Módulo de Instrumentação da Balança (Montagem Externa)
            fill(app.AxesSinotica, [5.50 6.60 6.60 5.50], [1.35 1.35 1.85 1.85], [0.92 0.88 0.96], 'EdgeColor', [0.45 0.20 0.65], 'LineWidth', 1.5);
            text(app.AxesSinotica, 6.05, 1.60, 'Balança Aerodinâmica', 'Color', [0.45 0.20 0.65], 'FontSize', 7.5, 'HorizontalAlignment', 'center', 'FontWeight', 'bold');
            plot(app.AxesSinotica, [6.05 6.05], [1.85 2.20], 'Color', [0.45 0.20 0.65], 'LineWidth', 1.5, 'LineStyle', ':');

            % Partículas de Vento (Desabilitadas temporariamente)
            app.WindParticlesPlot = plot(app.AxesSinotica, NaN, NaN, '-', 'Color', [0.15 0.55 0.95], 'LineWidth', 2.0, 'Visible', 'off');

            % Geometria Base do Perfil Alar NACA 0012 (Polinômio Aerodinâmico Autêntico)
            chord = 1.6;
            x_raw = linspace(0, 1, 40);
            y_raw = 5 * 0.12 * (0.2969*sqrt(x_raw) - 0.1260*x_raw - 0.3516*x_raw.^2 + 0.2843*x_raw.^3 - 0.1015*x_raw.^4);
            x_naca = [x_raw, fliplr(x_raw)] * chord;
            y_naca = [y_raw, -fliplr(y_raw)] * chord;

            app.AirfoilBaseX = x_naca - (chord * 0.25) + app.AirfoilCenterX;
            app.AirfoilBaseY = y_naca + app.AirfoilCenterY;
            app.AirfoilPatch = fill(app.AxesSinotica, app.AirfoilBaseX, app.AirfoilBaseY, [0.20 0.50 0.85], 'EdgeColor', [0.05 0.25 0.55], 'LineWidth', 2);
            plot(app.AxesSinotica, app.AirfoilCenterX, app.AirfoilCenterY, 'o', 'MarkerSize', 8, 'MarkerFaceColor', [0.85 0.20 0.20], 'MarkerEdgeColor', [1 1 1], 'LineWidth', 1.5);
            
            app.AirfoilTextAlpha = text(app.AxesSinotica, app.AirfoilCenterX, 2.45, '', 'Visible', 'off');

            % Vetores de Força Aerodinâmica
            app.LiftVectorLine = plot(app.AxesSinotica, [app.AirfoilCenterX, app.AirfoilCenterX], [app.AirfoilCenterY, app.AirfoilCenterY], '-', 'Color', C_LIFT, 'LineWidth', 3, 'Visible', 'off');
            app.LiftVectorHead = plot(app.AxesSinotica, app.AirfoilCenterX, app.AirfoilCenterY, '^', 'MarkerSize', 8, 'MarkerFaceColor', C_LIFT, 'MarkerEdgeColor', C_LIFT, 'Visible', 'off');
            app.LiftVectorText = text(app.AxesSinotica, app.AirfoilCenterX + 0.15, app.AirfoilCenterY + 0.5, 'Lift', 'Color', C_LIFT, 'FontSize', 9, 'FontWeight', 'bold', 'Visible', 'off');

            app.DragVectorLine = plot(app.AxesSinotica, [app.AirfoilCenterX, app.AirfoilCenterX], [app.AirfoilCenterY, app.AirfoilCenterY], '-', 'Color', C_DRAG, 'LineWidth', 3, 'Visible', 'off');
            app.DragVectorHead = plot(app.AxesSinotica, app.AirfoilCenterX, app.AirfoilCenterY, '>', 'MarkerSize', 8, 'MarkerFaceColor', C_DRAG, 'MarkerEdgeColor', C_DRAG, 'Visible', 'off');
            app.DragVectorText = text(app.AxesSinotica, app.AirfoilCenterX + 0.5, app.AirfoilCenterY - 0.20, 'Drag', 'Color', C_DRAG, 'FontSize', 9, 'FontWeight', 'bold', 'Visible', 'off');

            % --- 4. PRESSÕES ---
            fill(app.AxesSinotica, [8.2 9.0 9.0 8.2], [2.2 2.8 4.2 4.8], [0.90 0.96 0.92], 'EdgeColor', [0.15 0.55 0.25], 'LineWidth', 2);
            fill(app.AxesSinotica, [9.0 9.8 9.8 9.0], [2.8 2.2 4.8 4.2], [0.90 0.96 0.92], 'EdgeColor', [0.15 0.55 0.25], 'LineWidth', 2);
            text(app.AxesSinotica, 9.0, 5.6, '4. Pressões', 'Color', [0.10 0.50 0.20], 'FontSize', 9.5, 'HorizontalAlignment', 'center', 'FontWeight', 'bold');
            
            % Tomada de Pressão Estática na Garganta (Anel Piezométrico)
            plot(app.AxesSinotica, [9.0 9.0], [4.2 4.65], '-', 'Color', [0.10 0.50 0.20], 'LineWidth', 2.5);
            plot(app.AxesSinotica, 9.0, 4.2, 'o', 'MarkerSize', 4, 'MarkerFaceColor', [0.10 0.50 0.20], 'MarkerEdgeColor', [0.10 0.50 0.20]);
            plot(app.AxesSinotica, [8.86 9.14], [4.65 4.65], '-', 'Color', [0.10 0.40 0.15], 'LineWidth', 3.5);
            text(app.AxesSinotica, 9.0, 4.90, 'Tomada de Pressão', 'Color', [0.10 0.50 0.20], 'FontSize', 8, 'HorizontalAlignment', 'center', 'FontWeight', 'bold');

            % Setas do Sentido do Escoamento
            for xs = [1.85, 3.95, 7.95]
                plot(app.AxesSinotica, [xs xs+0.25], [3.5 3.5], '->', 'Color', [0.15 0.45 0.85], 'LineWidth', 2);
            end

            % --- Painel Inferior: Deck de Controles de Simulação (Oculto em Repouso, Ativado Apenas em Simulação) ---
            app.PanelControlesSimulacao = uipanel(app.TabSinotica);
            app.PanelControlesSimulacao.BackgroundColor = PNL;
            app.PanelControlesSimulacao.BorderColor = [0.90 0.65 0.25];
            app.PanelControlesSimulacao.BorderType = 'line';
            app.PanelControlesSimulacao.Position = [20 10 diaW 112];
            app.PanelControlesSimulacao.Visible = 'off';

            % Banner de Aviso de Simulação
            app.LabelAvisoSimulacao = uilabel(app.PanelControlesSimulacao);
            app.LabelAvisoSimulacao.Text = '⚠️ AVISO OPERACIONAL: Modo de Simulação Virtual para validação de desenvolvimento. Valores sintéticos NÃO devem ser utilizados para relatórios acadêmicos.';
            app.LabelAvisoSimulacao.FontSize = 10.5;
            app.LabelAvisoSimulacao.FontWeight = 'bold';
            app.LabelAvisoSimulacao.FontName = 'Segoe UI';
            app.LabelAvisoSimulacao.FontColor = [0.85 0.40 0.05];
            app.LabelAvisoSimulacao.Position = [12 86 diaW - 24 18];

            w_col = (diaW - 50) / 3;
            X1 = 15;
            X2 = 25 + w_col;
            X3 = 35 + 2 * w_col;

            % Coluna 1: Inversor do Motor
            app.LabelControleRPM = uilabel(app.PanelControlesSimulacao, 'Text', 'Inversor Motor (RPM):', 'FontSize', 11.5, 'FontColor', TEXT_DARK, 'FontWeight', 'bold', 'Position', [X1 62 180 20]);
            app.SliderRPM = uislider(app.PanelControlesSimulacao);
            app.SliderRPM.Limits = [0 3500];
            w_sl1 = max(110, w_col - 95);
            app.SliderRPM.Position = [X1 38 w_sl1 3];
            app.SliderRPM.ValueChangedFcn = createCallbackFcn(app, @SliderRPMValueChanged, true);

            app.SliderRPMValLabel = uilabel(app.PanelControlesSimulacao, 'Text', '0 RPM', 'FontSize', 13, 'FontWeight', 'bold', 'FontColor', [0.05 0.55 0.20], 'Position', [X1 + w_sl1 + 8, 30, 85, 24]);

            % Coluna 2: Ângulo de Ataque
            app.LabelControleAlpha = uilabel(app.PanelControlesSimulacao, 'Text', ['Angulo de Ataque ' char(945) ' (-15' char(176) ' a +25' char(176) '):'], 'FontSize', 11.5, 'FontColor', TEXT_DARK, 'FontWeight', 'bold', 'Position', [X2 62 210 20]);
            app.SliderAlpha = uislider(app.PanelControlesSimulacao);
            app.SliderAlpha.Limits = [-15 25];
            w_sl2 = max(110, w_col - 85);
            app.SliderAlpha.Position = [X2 38 w_sl2 3];
            app.SliderAlpha.ValueChangedFcn = createCallbackFcn(app, @SliderAlphaValueChanged, true);

            app.SliderAlphaValLabel = uilabel(app.PanelControlesSimulacao, 'Text', '0.0°', 'FontSize', 13, 'FontWeight', 'bold', 'FontColor', [0.15 0.35 0.75], 'Position', [X2 + w_sl2 + 8, 30, 75, 24]);

            % Coluna 3: Botão de Zeramento Geral
            w_btn = min(220, max(140, w_col - 30));
            x_btn = X3 + (w_col - 10 - w_btn) / 2;
            app.BtnPresetZero = uibutton(app.PanelControlesSimulacao, 'push');
            app.BtnPresetZero.Text = 'Zerar (0 RPM | 0.0°)';
            app.BtnPresetZero.FontSize = 12;
            app.BtnPresetZero.FontWeight = 'bold';
            app.BtnPresetZero.BackgroundColor = [0.93 0.95 0.98];
            app.BtnPresetZero.FontColor = [0.15 0.20 0.35];
            app.BtnPresetZero.Tooltip = 'Retorna a simulação ao repouso: Zera simultaneamente a rotação (0 RPM) e o ângulo de ataque (0.0°)';
            app.BtnPresetZero.Position = [x_btn 22 w_btn 48];
            app.BtnPresetZero.ButtonPushedFcn = createCallbackFcn(app, @(s,e) SetTestPreset(app, 0, 0), true);

            % --- Painel Inferior: Aviso de Operação Real em Bancada ---
            app.PanelAvisoHardware = uipanel(app.TabSinotica);
            app.PanelAvisoHardware.BackgroundColor = [1.00 0.98 0.92];
            app.PanelAvisoHardware.BorderColor = [0.85 0.60 0.20];
            app.PanelAvisoHardware.BorderType = 'line';
            app.PanelAvisoHardware.Position = [20 10 diaW 112];
            app.PanelAvisoHardware.Visible = 'off';

            app.LabelAvisoHardware = uilabel(app.PanelAvisoHardware);
            app.LabelAvisoHardware.Text = 'Aviso Operacional: No modo real de bancada, a rotação é comandada no inversor de frequência físico do túnel e o ângulo de ataque α é ajustado no transferidor mecânico.';
            app.LabelAvisoHardware.FontSize = 11.5;
            app.LabelAvisoHardware.FontWeight = 'bold';
            app.LabelAvisoHardware.FontName = 'Segoe UI';
            app.LabelAvisoHardware.FontColor = [0.65 0.35 0.05];
            app.LabelAvisoHardware.Position = [15 25 diaW - 30 62];

            % --- Painel de Telemetria Lateral Direita (Cards Responsivos Autocontidos) ---
            xR = diaW + 30;
            W_card_eff = tabW - xR - 15;
            nomes = {'ROTAÇÃO DO VENTILADOR', 'TORQUE NO EIXO', 'SUSTENTAÇÃO (LIFT)', ...
                     'ARRASTO (DRAG)', 'MOMENTO (HINGE)', 'PRESSÃO TRANSDUTOR 1', 'PRESSÃO TRANSDUTOR 2'};
            cores = {[0.05 0.55 0.20], [0.85 0.40 0.05], [0.00 0.45 0.75], [0.85 0.33 0.10], [0.45 0.20 0.65], [0.00 0.55 0.65], [0.10 0.55 0.35]};
            textos_padrao = {'0 RPM  (0.0 Hz)', ...
                             '0.0000 N.m  (P: 0.00 W)', ...
                             '0.0000 N  (0.000 kgf)', ...
                             '0.0000 N  (0.000 kgf)', ...
                             '0.0000 N.m', ...
                             '0.0 Pa  (0.00 mmH2O)', ...
                             '0.0 Pa  (0.00 mmH2O)'};
            
            lp = {}; vp = {};
            app.SinCardPanels = cell(1, 7);
            H_cards = (innerH - 10) - 84;
            h_step = floor(H_cards / 7);
            h_box = max(45, h_step - 5);
            
            for i = 1:7
                y_box = 84 + (7 - i) * h_step;
                pn = uipanel(app.TabSinotica);
                pn.BackgroundColor = PNL;
                pn.BorderType = 'line';
                pn.BorderColor = BORDER;
                pn.Position = [xR, y_box, W_card_eff, h_box];
                app.SinCardPanels{i} = pn;

                uilabel(pn, 'Text', nomes{i}, 'FontSize', 11.5, 'FontWeight', 'bold', 'FontName', 'Segoe UI', 'FontColor', cores{i}, 'Position', [34, h_box - 22, W_card_eff - 45, 18]);
                lamp = uilamp(pn, 'Position', [12, h_box - 20, 14, 14], 'Color', [0.7 0.75 0.8]);
                lp{end+1} = lamp;

                lbv = uilabel(pn, 'Text', textos_padrao{i}, 'FontSize', 16, 'FontWeight', 'bold', 'FontName', 'Segoe UI', 'FontColor', TEXT_DARK, 'HorizontalAlignment', 'right', 'Position', [12, 4, W_card_eff - 24, h_box - 26]);
                vp{end+1} = lbv;
            end

            app.LampRPM = lp{1};     app.SinRPMVal = vp{1};
            app.LampTorque = lp{2};  app.SinTorqueVal = vp{2};
            app.LampLift = lp{3};    app.SinLiftVal = vp{3};
            app.LampDrag = lp{4};    app.SinDragVal = vp{4};
            app.LampHinge = lp{5};   app.SinHingeVal = vp{5};
            app.LampPitot = lp{6};   app.SinVelVal = vp{6};
            app.LampVenturi = lp{7}; app.SinFlowVal = vp{7};

            % Estado do Ensaio
            app.SinStatusPanel = uipanel(app.TabSinotica, 'BackgroundColor', PNL, 'BorderType', 'line', 'BorderColor', BORDER, 'Position', [xR, 10, W_card_eff, 68]);
            uilabel(app.SinStatusPanel, 'Text', 'Status do Ensaio:', 'FontSize', 10.5, 'FontColor', TEXT_MUT, 'FontWeight', 'bold', 'Position', [12, 40, 100, 18]);
            app.SinModoVal = uilabel(app.SinStatusPanel, 'Text', 'SISTEMA PARADO', 'FontSize', 11.5, 'FontWeight', 'bold', 'FontColor', TEXT_MUT, 'Position', [115, 40, W_card_eff - 125, 18]);

            uilabel(app.SinStatusPanel, 'Text', 'Tempo:', 'FontSize', 10.5, 'FontColor', TEXT_MUT, 'Position', [12, 12, 45, 18]);
            app.SinTempoVal = uilabel(app.SinStatusPanel, 'Text', '0.0 s', 'FontSize', 11.5, 'FontWeight', 'bold', 'FontColor', TEXT_DARK, 'Position', [60, 12, 75, 18]);

            uilabel(app.SinStatusPanel, 'Text', 'Amostras:', 'FontSize', 10.5, 'FontColor', TEXT_MUT, 'Position', [145, 12, 60, 18]);
            app.SinAmostrasVal = uilabel(app.SinStatusPanel, 'Text', '0 pts', 'FontSize', 11.5, 'FontWeight', 'bold', 'FontColor', TEXT_DARK, 'Position', [210, 12, 85, 18]);

            % =============================================================
            % TAB 2: FORÇAS AERODINÂMICAS (BALANÇA 514QD - ESCOPO GRADUAÇÃO)
            % =============================================================
            app.TabForcas = uitab(app.TabGroup, 'Title', 'Forças Aerodinâmicas', 'BackgroundColor', BG);

            H_tab_inner = tabH - 28;
            Y_top_cc = H_tab_inner - 14;
            Y_bottom_cc = 10;
            H_content_cc = Y_top_cc - Y_bottom_cc;

            w_kpi = min(400, max(320, floor(tabW * 0.22)));
            h_card_f = floor((H_content_cc - 16) / 3);

            sz_g = min(w_kpi - 40, h_card_f - 86);
            gx = floor((w_kpi - sz_g) / 2);
            gy = 44 + floor((h_card_f - 80 - sz_g) / 2);

            % --- CARD 1 (TOPO): SUSTENTAÇÃO LIFT (CH3) ---
            app.PanelCardLift = uipanel(app.TabForcas, 'Title', 'SUSTENTAÇÃO (LIFT)', ...
                                        'BackgroundColor', BG, 'BorderType', 'none', ...
                                        'Position', [12, Y_bottom_cc + 2*(h_card_f + 8), w_kpi, h_card_f], ...
                                        'FontWeight', 'bold', 'ForegroundColor', C_LIFT, 'FontName', 'Segoe UI', 'FontSize', 12);
            
            app.GaugeLift = uigauge(app.PanelCardLift, 'circular', 'Limits', [-50 50], 'Position', [gx, gy, sz_g, sz_g]);
            app.GaugeLift.FontSize = 12.5;
            app.LabelTitleLift = uilabel(app.PanelCardLift, 'Text', 'Faixa de Medição: -50 a +50 N', 'FontSize', 10.5, 'FontColor', TEXT_MUT, 'HorizontalAlignment', 'center', 'Position', [10, 26, w_kpi-20, 16]);
            app.LabelLiftVal = uilabel(app.PanelCardLift, 'Text', '0.0000 N', 'FontSize', 18, 'FontWeight', 'bold', 'FontName', 'Segoe UI', 'FontColor', C_LIFT, 'HorizontalAlignment', 'center', 'Position', [10, 4, w_kpi-20, 24]);

            % --- CARD 2 (MEIO): ARRASTO DRAG (CH4) ---
            app.PanelCardDrag = uipanel(app.TabForcas, 'Title', 'ARRASTO (DRAG)', ...
                                        'BackgroundColor', BG, 'BorderType', 'none', ...
                                        'Position', [12, Y_bottom_cc + h_card_f + 8, w_kpi, h_card_f], ...
                                        'FontWeight', 'bold', 'ForegroundColor', C_DRAG, 'FontName', 'Segoe UI', 'FontSize', 12);
            
            app.GaugeDrag = uigauge(app.PanelCardDrag, 'circular', 'Limits', [-50 50], 'Position', [gx, gy, sz_g, sz_g]);
            app.GaugeDrag.FontSize = 12.5;
            app.LabelTitleDrag = uilabel(app.PanelCardDrag, 'Text', 'Faixa de Medição: -50 a +50 N', 'FontSize', 10.5, 'FontColor', TEXT_MUT, 'HorizontalAlignment', 'center', 'Position', [10, 26, w_kpi-20, 16]);
            app.LabelDragVal = uilabel(app.PanelCardDrag, 'Text', '0.0000 N', 'FontSize', 18, 'FontWeight', 'bold', 'FontName', 'Segoe UI', 'FontColor', C_DRAG, 'HorizontalAlignment', 'center', 'Position', [10, 4, w_kpi-20, 24]);

            % --- CARD 3 (BASE): MOMENTO DE DOBRADIÇA HINGE (CH5) ---
            app.PanelCardHinge = uipanel(app.TabForcas, 'Title', 'MOMENTO DE DOBRADIÇA (HINGE)', ...
                                         'BackgroundColor', BG, 'BorderType', 'none', ...
                                         'Position', [12, Y_bottom_cc, w_kpi, h_card_f], ...
                                         'FontWeight', 'bold', 'ForegroundColor', [0.45 0.20 0.65], 'FontName', 'Segoe UI', 'FontSize', 12);
            
            app.GaugeHinge = uigauge(app.PanelCardHinge, 'circular', 'Limits', [-1 1], 'Position', [gx, gy, sz_g, sz_g]);
            app.GaugeHinge.FontSize = 12.5;
            app.LabelTitleHinge = uilabel(app.PanelCardHinge, 'Text', 'Faixa de Medição: -1.0 a +1.0 N.m', 'FontSize', 10.5, 'FontColor', TEXT_MUT, 'HorizontalAlignment', 'center', 'Position', [10, 26, w_kpi-20, 16]);
            app.LabelHingeVal = uilabel(app.PanelCardHinge, 'Text', '0.0000 N.m', 'FontSize', 18, 'FontWeight', 'bold', 'FontName', 'Segoe UI', 'FontColor', [0.45 0.20 0.65], 'HorizontalAlignment', 'center', 'Position', [10, 4, w_kpi-20, 24]);

            % --- COLUNA DIREITA: FILTRO POWERBI + GRÁFICO UNIFICADO EXPANDIDO ---
            x_forcas_r = w_kpi + 24;
            w_forcas_r = tabW - x_forcas_r - 16;
            h_bar_filtro = 32;
            y_bar_filtro = Y_top_cc - h_bar_filtro;

            % Barra Superior de Seleção de Forças
            app.PanelFiltroForcas = uipanel(app.TabForcas, 'BackgroundColor', [0.96 0.97 0.99], 'BorderColor', BORDER, ...
                                            'Position', [x_forcas_r, y_bar_filtro, w_forcas_r, h_bar_filtro]);
            
            uilabel(app.PanelFiltroForcas, 'Text', 'Seleção no Gráfico:', ...
                    'FontWeight', 'bold', 'FontSize', 11, 'FontColor', [0.15 0.25 0.40], ...
                    'Position', [10, 6, 130, 20]);
            
            app.CbPlotLift = uicheckbox(app.PanelFiltroForcas, 'Text', 'Sustentação', ...
                                        'Value', true, 'FontWeight', 'bold', 'FontSize', 11.5, 'FontColor', C_LIFT, ...
                                        'Position', [145, 6, 120, 20]);
            app.CbPlotLift.ValueChangedFcn = createCallbackFcn(app, @ForcasPlotFilterChanged, true);

            app.CbPlotDrag = uicheckbox(app.PanelFiltroForcas, 'Text', 'Arrasto', ...
                                        'Value', true, 'FontWeight', 'bold', 'FontSize', 11.5, 'FontColor', C_DRAG, ...
                                        'Position', [275, 6, 110, 20]);
            app.CbPlotDrag.ValueChangedFcn = createCallbackFcn(app, @ForcasPlotFilterChanged, true);

            app.CbPlotHinge = uicheckbox(app.PanelFiltroForcas, 'Text', 'Momento (Hinge)', ...
                                         'Value', false, 'FontWeight', 'bold', 'FontSize', 11.5, 'FontColor', [0.45 0.20 0.65], ...
                                         'Position', [395, 6, 150, 20]);
            app.CbPlotHinge.ValueChangedFcn = createCallbackFcn(app, @ForcasPlotFilterChanged, true);

            app.BtnPlotTodas = uibutton(app.PanelFiltroForcas, 'push', 'Text', 'Todas', ...
                                        'FontSize', 10, 'FontWeight', 'bold', ...
                                        'BackgroundColor', [0.90 0.95 1.00], 'FontColor', [0.10 0.40 0.75], ...
                                        'Position', [w_forcas_r - 140, 4, 62, 24]);
            app.BtnPlotTodas.ButtonPushedFcn = createCallbackFcn(app, @BtnPlotTodasPushed, true);

            app.BtnPlotNenhuma = uibutton(app.PanelFiltroForcas, 'push', 'Text', 'Limpar', ...
                                          'FontSize', 10, ...
                                          'BackgroundColor', [0.98 0.98 0.98], 'FontColor', [0.45 0.45 0.45], ...
                                          'Position', [w_forcas_r - 72, 4, 62, 24]);
            app.BtnPlotNenhuma.ButtonPushedFcn = createCallbackFcn(app, @BtnPlotNenhumaPushed, true);

            % Gráfico Unificado Expandido até a Base da Aba (Sem o painel inferior)
            y_plot_uni = Y_bottom_cc;
            h_plot_uni = y_bar_filtro - y_plot_uni - 6;

            app.AxesForcasUnificado = uiaxes(app.TabForcas, 'Position', [x_forcas_r, y_plot_uni, w_forcas_r, h_plot_uni], ...
                                             'Color', [1 1 1]);
            title(app.AxesForcasUnificado, 'Histórico Temporal Unificado da Balança 514QD: Sustentação L(t), Arrasto D(t) e Momento Hinge M_z(t)', ...
                  'Color', [0.12 0.20 0.35], 'FontWeight', 'bold', 'FontSize', 12.5);
            xlabel(app.AxesForcasUnificado, 'Tempo Decorrido (s)', 'FontWeight', 'bold', 'FontSize', 11.5);
            grid(app.AxesForcasUnificado, 'on'); app.AxesForcasUnificado.GridColor = [0.88 0.90 0.94]; app.AxesForcasUnificado.GridAlpha = 0.8;

            % Configuração de Eixo Duplo (yyaxis):
            yyaxis(app.AxesForcasUnificado, 'left');
            ylabel(app.AxesForcasUnificado, 'Forças Aerodinâmicas: Lift & Drag [N]', 'FontWeight', 'bold', 'FontSize', 11.5);
            app.AxesForcasUnificado.YColor = [0.10 0.30 0.50];
            app.AxesForcasUnificado.YLim   = [-1.0 5.0];
            app.aLineLift = animatedline(app.AxesForcasUnificado, 'Color', C_LIFT, 'LineWidth', 2.4, 'MaximumNumPoints', 50000, 'DisplayName', 'Sustentação');
            app.aLineDrag = animatedline(app.AxesForcasUnificado, 'Color', C_DRAG, 'LineWidth', 2.4, 'MaximumNumPoints', 50000, 'DisplayName', 'Arrasto');

            yyaxis(app.AxesForcasUnificado, 'right');
            ylabel(app.AxesForcasUnificado, '');
            app.AxesForcasUnificado.YColor = [0.85 0.85 0.85];
            app.AxesForcasUnificado.YLim   = [-0.5 0.5];
            app.aLineHinge = animatedline(app.AxesForcasUnificado, 'Color', [0.45 0.20 0.65], 'LineWidth', 2.4, 'MaximumNumPoints', 50000, 'DisplayName', 'Momento (Hinge)', 'Visible', 'off');

            legend(app.AxesForcasUnificado, [app.aLineLift, app.aLineDrag], 'Location', 'northwest', 'FontSize', 10.5, 'FontWeight', 'bold');
            yyaxis(app.AxesForcasUnificado, 'left');

            % Painel Balança inferior removido da visualização (mantido vazio)
            app.PanelBalanca = [];
            app.LabelResumoLift = [];
            app.LabelResumoDrag = [];
            app.LabelResumoHinge = [];

            % =============================================================
            % TAB 3: PRESSÕES & MANOMETRIA (50/50: MANÔMETROS EM U E GRÁFICOS)
            % =============================================================
            app.TabFluidos = uitab(app.TabGroup, 'Title', 'Pressões & Manometria (Tubo em U)', 'BackgroundColor', BG);

            app.PanelGaugePitot = [];
            app.PanelGaugeVenturi = [];
            app.GaugePitot = [];
            app.GaugeVenturi = [];
            app.LabelTitleGaugePitot = [];
            app.LabelTitleGaugeVenturi = [];
            app.LabelPitotVal = [];
            app.LabelVenturiVal = [];

            w_half = floor((tabW - 32) / 2);
            w_mano_col = w_half;
            x_mano = 10;
            x_plots = x_mano + w_mano_col + 12;
            w_plots_col = tabW - x_plots - 10;

            % -------------------------------------------------------------
            % METADE ESQUERDA (50%): COLUNAS LÍQUIDAS REAIS (MANÔMETROS EM TUBO EM U)
            % -------------------------------------------------------------
            app.PanelManometrosU = uipanel(app.TabFluidos, 'Title', 'MANOMETRIA EM U — COLUNAS LÍQUIDAS REAIS (ÁGUA DESTILADA)', ...
                                          'BackgroundColor', PNL, 'BorderColor', BORDER, ...
                                          'Position', [x_mano, Y_bottom_cc, w_mano_col, H_content_cc], ...
                                          'FontWeight', 'bold', 'ForegroundColor', [0.15 0.25 0.40], 'FontName', 'Segoe UI', 'FontSize', 12);
            
            w_each_m = floor((w_mano_col - 24) / 2);
            h_ax_avail_cc = H_content_cc - 114;
            w_ax_avail_cc = w_each_m - 20;
            w_ax_cc = min(w_ax_avail_cc, floor(h_ax_avail_cc * (17 / 28)));
            h_ax_cc = floor(w_ax_cc * (28 / 17));
            x_ax1_cc = 12 + floor((w_each_m - w_ax_cc) / 2);
            x_ax2_cc = 12 + w_each_m + floor((w_each_m - w_ax_cc) / 2);
            y_ax_cc = 8 + floor((h_ax_avail_cc - h_ax_cc) / 2);

            % --- MANÔMETRO EM U 1 (ESQUERDA) ---
            app.LabelManoPitotTitle = uilabel(app.PanelManometrosU, 'Text', '', 'Visible', 'off', 'Position', [12, H_content_cc - 20, w_each_m, 1]);
            app.LabelManoPitotVal = uilabel(app.PanelManometrosU, 'Text', ['' char(916) 'h = 0.00 mmH_2O  (0.0 Pa)'], 'FontSize', 18, 'FontWeight', 'bold', 'FontColor', [0.00 0.45 0.55], 'HorizontalAlignment', 'center', 'Position', [12, H_content_cc - 66, w_each_m, 28]);
            app.LabelManoPitotLevels = uilabel(app.PanelManometrosU, 'Text', 'Coluna Alta: 50.0 mm   |   Coluna Baixa: 50.0 mm', 'FontSize', 14.5, 'FontWeight', 'bold', 'FontColor', [0.20 0.28 0.38], 'HorizontalAlignment', 'center', 'Position', [12, H_content_cc - 96, w_each_m, 24]);

            app.AxesManometroPitot = uiaxes(app.PanelManometrosU, 'Position', [x_ax1_cc, y_ax_cc, w_ax_cc, h_ax_cc], ...
                                            'Color', [0.98 0.99 1.00], 'XColor', 'none', 'YColor', 'none', ...
                                            'XLim', [-8.5 8.5], 'YLim', [-3.5 24.5]);
            app.AxesManometroPitot.DataAspectRatio = [1 1 1];
            app.AxesManometroPitot.Toolbar.Visible = 'off';
            disableDefaultInteractivity(app.AxesManometroPitot);
            hold(app.AxesManometroPitot, 'on');

            % Geometria Alta do Manômetro em U (Canal 1)
            raio_t = 1.3; xL_t = -4.5; xR_t = +4.5; y_top_t = 21.5; y_bnd_t = 0.0;
            R_ctr_t = 4.5; R_in_t = R_ctr_t - raio_t; R_out_t = R_ctr_t + raio_t;
            th_t = linspace(pi, 2*pi, 60);
            xo_bnd_t = R_out_t * cos(th_t); yo_bnd_t = y_bnd_t + R_out_t * sin(th_t) * 0.45;
            xi_bnd_t = R_in_t  * cos(th_t); yi_bnd_t = y_bnd_t + R_in_t  * sin(th_t) * 0.45;
            cVidro = [0.45 0.55 0.68]; cFl = [0.10 0.65 0.95]; cMen = [0.85 0.98 1.00];

            % Paredes de vidro verticais e curva inferior
            plot(app.AxesManometroPitot, [xL_t-raio_t xL_t-raio_t], [y_bnd_t y_top_t], 'Color', cVidro, 'LineWidth', 2.8);
            plot(app.AxesManometroPitot, [xL_t+raio_t xL_t+raio_t], [y_bnd_t y_top_t], 'Color', cVidro, 'LineWidth', 2.8);
            plot(app.AxesManometroPitot, [xR_t-raio_t xR_t-raio_t], [y_bnd_t y_top_t], 'Color', cVidro, 'LineWidth', 2.8);
            plot(app.AxesManometroPitot, [xR_t+raio_t xR_t+raio_t], [y_bnd_t y_top_t], 'Color', cVidro, 'LineWidth', 2.8);
            plot(app.AxesManometroPitot, xo_bnd_t, yo_bnd_t, 'Color', cVidro, 'LineWidth', 2.8);
            plot(app.AxesManometroPitot, xi_bnd_t, yi_bnd_t, 'Color', cVidro, 'LineWidth', 2.8);

            % Bocais de conexão no topo com fontes grandes e legíveis
            patch(app.AxesManometroPitot, [xL_t-1.6 xL_t+1.6 xL_t+1.6 xL_t-1.6], [y_top_t y_top_t y_top_t+0.8 y_top_t+0.8], [0.85 0.35 0.20], 'EdgeColor', 'none');
            text(app.AxesManometroPitot, xL_t, y_top_t+1.8, '(+) HIGH', 'Color', [0.85 0.25 0.15], 'FontWeight', 'bold', 'FontSize', 11.5, 'HorizontalAlignment', 'center');
            patch(app.AxesManometroPitot, [xR_t-1.6 xR_t+1.6 xR_t+1.6 xR_t-1.6], [y_top_t y_top_t y_top_t+0.8 y_top_t+0.8], [0.15 0.50 0.85], 'EdgeColor', 'none');
            text(app.AxesManometroPitot, xR_t, y_top_t+1.8, '(-) LOW', 'Color', [0.15 0.45 0.80], 'FontWeight', 'bold', 'FontSize', 11.5, 'HorizontalAlignment', 'center');

            % Curva inferior preenchida com fluido
            patch(app.AxesManometroPitot, [xo_bnd_t, fliplr(xi_bnd_t)], [yo_bnd_t, fliplr(yi_bnd_t)], cFl, 'EdgeColor', 'none', 'FaceAlpha', 0.88);

            % Colunas de líquido e meniscos (Repouso em y=8.0)
            app.ManometroPitotPatchL = patch(app.AxesManometroPitot, [xL_t-raio_t xL_t+raio_t xL_t+raio_t xL_t-raio_t], [y_bnd_t y_bnd_t 8.0 8.0], cFl, 'EdgeColor', 'none', 'FaceAlpha', 0.88);
            app.ManometroPitotMeniscoL = plot(app.AxesManometroPitot, [xL_t-raio_t xL_t+raio_t], [8.0 8.0], 'Color', cMen, 'LineWidth', 3.5);
            app.ManometroPitotPatchR = patch(app.AxesManometroPitot, [xR_t-raio_t xR_t+raio_t xR_t+raio_t xR_t-raio_t], [y_bnd_t y_bnd_t 8.0 8.0], cFl, 'EdgeColor', 'none', 'FaceAlpha', 0.88);
            app.ManometroPitotMeniscoR = plot(app.AxesManometroPitot, [xR_t-raio_t xR_t+raio_t], [8.0 8.0], 'Color', cMen, 'LineWidth', 3.5);

            % Linha de Zero Central de Referência
            plot(app.AxesManometroPitot, [xL_t-1.6 xR_t+1.6], [8.0 8.0], '--', 'Color', [0.75 0.65 0.15], 'LineWidth', 1.4);
            text(app.AxesManometroPitot, -6.4, 8.0, 'Zero', 'Color', [0.75 0.60 0.10], 'FontSize', 11.5, 'FontWeight', 'bold', 'HorizontalAlignment', 'right');
            app.txtCotaPitot = text(app.AxesManometroPitot, 0, 9.0, '\Delta h = 0.0 mmH_2O', 'Color', [0.00 0.45 0.65], 'FontSize', 13, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % --- MANÔMETRO EM U 2 (DIREITA) ---
            app.LabelManoVenturiTitle = uilabel(app.PanelManometrosU, 'Text', '', 'Visible', 'off', 'Position', [12 + w_each_m, H_content_cc - 20, w_each_m, 1]);
            app.LabelManoVenturiVal = uilabel(app.PanelManometrosU, 'Text', ['' char(916) 'h = 0.00 mmH_2O  (0.0 Pa)'], 'FontSize', 18, 'FontWeight', 'bold', 'FontColor', [0.10 0.50 0.25], 'HorizontalAlignment', 'center', 'Position', [12 + w_each_m, H_content_cc - 66, w_each_m, 28]);
            app.LabelManoVenturiLevels = uilabel(app.PanelManometrosU, 'Text', 'Coluna Alta: 100.0 mm   |   Coluna Baixa: 100.0 mm', 'FontSize', 14.5, 'FontWeight', 'bold', 'FontColor', [0.20 0.28 0.38], 'HorizontalAlignment', 'center', 'Position', [12 + w_each_m, H_content_cc - 96, w_each_m, 24]);

            app.AxesManometroVenturi = uiaxes(app.PanelManometrosU, 'Position', [x_ax2_cc, y_ax_cc, w_ax_cc, h_ax_cc], ...
                                              'Color', [0.98 0.99 1.00], 'XColor', 'none', 'YColor', 'none', ...
                                              'XLim', [-8.5 8.5], 'YLim', [-3.5 24.5]);
            app.AxesManometroVenturi.DataAspectRatio = [1 1 1];
            app.AxesManometroVenturi.Toolbar.Visible = 'off';
            disableDefaultInteractivity(app.AxesManometroVenturi);
            hold(app.AxesManometroVenturi, 'on');

            % Paredes de vidro verticais e curva inferior
            plot(app.AxesManometroVenturi, [xL_t-raio_t xL_t-raio_t], [y_bnd_t y_top_t], 'Color', cVidro, 'LineWidth', 2.8);
            plot(app.AxesManometroVenturi, [xL_t+raio_t xL_t+raio_t], [y_bnd_t y_top_t], 'Color', cVidro, 'LineWidth', 2.8);
            plot(app.AxesManometroVenturi, [xR_t-raio_t xR_t-raio_t], [y_bnd_t y_top_t], 'Color', cVidro, 'LineWidth', 2.8);
            plot(app.AxesManometroVenturi, [xR_t+raio_t xR_t+raio_t], [y_bnd_t y_top_t], 'Color', cVidro, 'LineWidth', 2.8);
            plot(app.AxesManometroVenturi, xo_bnd_t, yo_bnd_t, 'Color', cVidro, 'LineWidth', 2.8);
            plot(app.AxesManometroVenturi, xi_bnd_t, yi_bnd_t, 'Color', cVidro, 'LineWidth', 2.8);

            % Bocais de conexão no topo
            patch(app.AxesManometroVenturi, [xL_t-1.6 xL_t+1.6 xL_t+1.6 xL_t-1.6], [y_top_t y_top_t y_top_t+0.8 y_top_t+0.8], [0.85 0.35 0.20], 'EdgeColor', 'none');
            text(app.AxesManometroVenturi, xL_t, y_top_t+1.8, '(+) HIGH', 'Color', [0.85 0.25 0.15], 'FontWeight', 'bold', 'FontSize', 11.5, 'HorizontalAlignment', 'center');
            patch(app.AxesManometroVenturi, [xR_t-1.6 xR_t+1.6 xR_t+1.6 xR_t-1.6], [y_top_t y_top_t y_top_t+0.8 y_top_t+0.8], [0.15 0.50 0.85], 'EdgeColor', 'none');
            text(app.AxesManometroVenturi, xR_t, y_top_t+1.8, '(-) LOW', 'Color', [0.15 0.45 0.80], 'FontWeight', 'bold', 'FontSize', 11.5, 'HorizontalAlignment', 'center');

            % Curva inferior preenchida com fluido
            patch(app.AxesManometroVenturi, [xo_bnd_t, fliplr(xi_bnd_t)], [yo_bnd_t, fliplr(yi_bnd_t)], cFl, 'EdgeColor', 'none', 'FaceAlpha', 0.88);

            % Colunas de líquido e meniscos
            app.ManometroVenturiPatchL = patch(app.AxesManometroVenturi, [xL_t-raio_t xL_t+raio_t xL_t+raio_t xL_t-raio_t], [y_bnd_t y_bnd_t 8.0 8.0], cFl, 'EdgeColor', 'none', 'FaceAlpha', 0.88);
            app.ManometroVenturiMeniscoL = plot(app.AxesManometroVenturi, [xL_t-raio_t xL_t+raio_t], [8.0 8.0], 'Color', cMen, 'LineWidth', 3.5);
            app.ManometroVenturiPatchR = patch(app.AxesManometroVenturi, [xR_t-raio_t xR_t+raio_t xR_t+raio_t xR_t-raio_t], [y_bnd_t y_bnd_t 8.0 8.0], cFl, 'EdgeColor', 'none', 'FaceAlpha', 0.88);
            app.ManometroVenturiMeniscoR = plot(app.AxesManometroVenturi, [xR_t-raio_t xR_t+raio_t], [8.0 8.0], 'Color', cMen, 'LineWidth', 3.5);

            % Linha de Zero Central
            plot(app.AxesManometroVenturi, [xL_t-1.6 xR_t+1.6], [8.0 8.0], '--', 'Color', [0.75 0.65 0.15], 'LineWidth', 1.4);
            text(app.AxesManometroVenturi, -6.4, 8.0, 'Zero', 'Color', [0.75 0.60 0.10], 'FontSize', 11.5, 'FontWeight', 'bold', 'HorizontalAlignment', 'right');
            app.txtCotaVenturi = text(app.AxesManometroVenturi, 0, 9.0, '\Delta h = 0.0 mmH_2O', 'Color', [0.10 0.50 0.25], 'FontSize', 13, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % -------------------------------------------------------------
            % METADE DIREITA (50%): GRÁFICOS TEMPORAIS EMPILHADOS
            % -------------------------------------------------------------
            h_p_box = floor((H_content_cc - 12) / 2);

            % Gráfico Superior: Pressão Diferencial 1
            app.AxesPitot = uiaxes(app.TabFluidos, 'Position', [x_plots, Y_bottom_cc + h_p_box + 12, w_plots_col, h_p_box], ...
                                   'Color', [1 1 1], 'XColor', [0.2 0.25 0.3], 'YColor', [0.2 0.25 0.3]);
            title(app.AxesPitot, 'Histórico Temporal de Pressão Diferencial 1 — \Delta h_1(t) [mmH_2O]', 'Color', C_PIT, 'FontWeight', 'bold', 'FontSize', 11.5);
            ylabel(app.AxesPitot, 'Pressão (mmH_2O)', 'FontWeight', 'bold', 'FontSize', 10.5);
            xlabel(app.AxesPitot, 'Tempo (s)', 'FontWeight', 'bold', 'FontSize', 10.5);
            app.AxesPitot.YLim = [-1.0, 15.0];
            grid(app.AxesPitot, 'on'); app.AxesPitot.GridColor = [0.88 0.90 0.94]; app.AxesPitot.GridAlpha = 0.8;

            % Gráfico Inferior: Pressão Diferencial 2
            app.AxesVenturi = uiaxes(app.TabFluidos, 'Position', [x_plots, Y_bottom_cc, w_plots_col, h_p_box], ...
                                     'Color', [1 1 1], 'XColor', [0.2 0.25 0.3], 'YColor', [0.2 0.25 0.3]);
            title(app.AxesVenturi, 'Histórico Temporal de Pressão Diferencial 2 — \Delta h_2(t) [mmH_2O]', 'Color', [0.10 0.55 0.35], 'FontWeight', 'bold', 'FontSize', 11.5);
            ylabel(app.AxesVenturi, 'Pressão (mmH_2O)', 'FontWeight', 'bold', 'FontSize', 10.5);
            xlabel(app.AxesVenturi, 'Tempo (s)', 'FontWeight', 'bold', 'FontSize', 10.5);
            app.AxesVenturi.YLim = [-1.0, 15.0];
            grid(app.AxesVenturi, 'on'); app.AxesVenturi.GridColor = [0.88 0.90 0.94]; app.AxesVenturi.GridAlpha = 0.8;


            % =============================================================
            % TAB 4: DATA LOGGER & HISTÓRICO (EXPANDIDO)
            % =============================================================
            app.TabLogger = uitab(app.TabGroup, 'Title', 'Data Logger & Histórico', 'BackgroundColor', BG);

            uilabel(app.TabLogger, 'Text', 'Canal Selecionado:', 'FontSize', 12, 'FontWeight', 'bold', 'FontColor', TEXT_DARK, 'Position', [20 tabH-55 140 24]);
            app.LogCanalDropdown = uidropdown(app.TabLogger);
            app.LogCanalDropdown.Items = { ...
                'CH1 - Rotação do Ventilador (RPM)', ...
                'CH2 - Torque no Eixo Motor (N.m)', ...
                'CH3 - Força de Sustentação / Lift (N)', ...
                'CH4 - Força de Arrasto / Drag (N)', ...
                'CH5 - Momento de Dobradiça / Hinge (N.m)', ...
                'CH6 - Pressão Diferencial 1 (Pa)', ...
                'CH7 - Pressão Diferencial 2 (Pa)'};
            app.LogCanalDropdown.ItemsData = 1:7;
            app.LogCanalDropdown.Value = 1;
            app.LogCanalDropdown.Position = [170 tabH-55 360 26];
            app.LogCanalDropdown.ValueChangedFcn = createCallbackFcn(app, @LogCanalDropdownValueChanged, true);

            app.ClearLogButton = uibutton(app.TabLogger, 'push', 'Text', 'Limpar Visualização', 'Position', [550 tabH-55 160 26]);
            app.ClearLogButton.ButtonPushedFcn = createCallbackFcn(app, @ClearLogButtonPushed, true);

            app.AxesLogger = uiaxes(app.TabLogger, 'Position', [20 140 tabW-40 tabH-210], 'Color', [1 1 1], 'XColor', [0.2 0.25 0.3], 'YColor', [0.2 0.25 0.3]);
            title(app.AxesLogger, 'Registro Histórico Contínuo da Variável Selecionada', 'Color', [0.15 0.35 0.65], 'FontWeight', 'bold');
            grid(app.AxesLogger, 'on'); app.AxesLogger.GridColor = [0.88 0.90 0.94]; app.AxesLogger.GridAlpha = 0.8;

            pStat = uipanel(app.TabLogger, 'Title', 'Estatísticas da Janela Selecionada', 'BackgroundColor', PNL, 'BorderColor', BORDER, 'Position', [20 15 tabW-40 105], 'FontWeight', 'bold', 'ForegroundColor', TEXT_DARK, 'FontName', 'Segoe UI', 'FontSize', 11);
            
            w_st = (tabW - 100) / 4;
            uilabel(pStat, 'Text', 'Valor Mínimo:', 'FontSize', 11, 'FontColor', TEXT_MUT, 'Position', [30 48 150 18]);
            app.LogStatMin = uilabel(pStat, 'Text', '---', 'FontSize', 22, 'FontWeight', 'bold', 'FontColor', TEXT_DARK, 'Position', [30 15 180 30]);

            uilabel(pStat, 'Text', 'Valor Médio:', 'FontSize', 11, 'FontColor', TEXT_MUT, 'Position', [30+w_st 48 150 18]);
            app.LogStatMean = uilabel(pStat, 'Text', '---', 'FontSize', 22, 'FontWeight', 'bold', 'FontColor', [0.10 0.45 0.70], 'Position', [30+w_st 15 180 30]);

            uilabel(pStat, 'Text', 'Valor Máximo:', 'FontSize', 11, 'FontColor', TEXT_MUT, 'Position', [30+2*w_st 48 150 18]);
            app.LogStatMax = uilabel(pStat, 'Text', '---', 'FontSize', 22, 'FontWeight', 'bold', 'FontColor', TEXT_DARK, 'Position', [30+2*w_st 15 180 30]);

            uilabel(pStat, 'Text', 'Desvio Padrão (σ):', 'FontSize', 11, 'FontColor', TEXT_MUT, 'Position', [30+3*w_st 48 150 18]);
            app.LogStatStd = uilabel(pStat, 'Text', '---', 'FontSize', 22, 'FontWeight', 'bold', 'FontColor', TEXT_DARK, 'Position', [30+3*w_st 15 180 30]);

            % =============================================================
            % TAB 5: ENSAIO DE VENTILADORES (MÁQUINAS DE FLUXO)
            % =============================================================
            app.TabVentilador = uitab(app.TabGroup, 'Title', 'Ensaio de Ventiladores', 'BackgroundColor', BG);

            y_top_v  = tabH - 90;
            y_sub_v  = tabH - 114;
            h_card_v = 88;
            y_card_v = tabH - 128 - h_card_v;
            w_gap_v  = 14;
            w_card_v = floor((tabW - 40 - 3 * w_gap_v) / 4);

            app.LabelVentTitle = uilabel(app.TabVentilador, ...
                'Text', 'Laboratório de Máquinas de Fluxo — Curvas Características de Ventiladores (Didacta Italia PN 20 DNT)', ...
                'FontSize', 13.5, 'FontWeight', 'bold', 'FontColor', [0.12 0.20 0.35], ...
                'Position', [20 y_top_v tabW-40 24]);
            app.LabelVentSub = uilabel(app.TabVentilador, ...
                'Text', 'Módulo desenvolvido para simplificar a realização do roteiro de laboratório recebido.', ...
                'FontSize', 10.5, 'FontColor', TEXT_MUT, ...
                'Position', [20 y_sub_v tabW-40 18]);

            % 4 Cards Superiores com os valores medidos da bancada
            % Card 1: Rotação N (RPM)
            pCard1 = uipanel(app.TabVentilador, 'BackgroundColor', PNL, 'BorderColor', BORDER, 'Position', [20 y_card_v w_card_v h_card_v]);
            uilabel(pCard1, 'Text', 'CH1: ROTAÇÃO DO MOTOR (N)', 'FontSize', 10.5, 'FontWeight', 'bold', 'FontColor', [0.10 0.50 0.20], 'Position', [14 h_card_v-26 w_card_v-28 18]);
            app.CardVentRPMVal = uilabel(pCard1, 'Text', '0 RPM', 'FontSize', 24, 'FontWeight', 'bold', 'FontColor', TEXT_DARK, 'Position', [14 26 w_card_v-28 36]);
            app.CardVentRPMSub = uilabel(pCard1, 'Text', 'Freq: 0.0 Hz | Sensor Indutivo', 'FontSize', 9.5, 'FontColor', TEXT_MUT, 'Position', [14 6 w_card_v-28 18]);

            % Card 2: Torque Teixo (N.m)
            pCard2 = uipanel(app.TabVentilador, 'BackgroundColor', PNL, 'BorderColor', BORDER, 'Position', [20 + w_card_v + w_gap_v, y_card_v, w_card_v, h_card_v]);
            uilabel(pCard2, 'Text', 'CH2: TORQUE NO EIXO (Teixo)', 'FontSize', 10.5, 'FontWeight', 'bold', 'FontColor', [0.85 0.35 0.10], 'Position', [14 h_card_v-26 w_card_v-28 18]);
            app.CardVentTorqueVal = uilabel(pCard2, 'Text', '0.0000 N·m', 'FontSize', 24, 'FontWeight', 'bold', 'FontColor', TEXT_DARK, 'Position', [14 26 w_card_v-28 36]);
            app.CardVentTorqueSub = uilabel(pCard2, 'Text', 'Potência no Eixo: 0.0 W (0.00 cv)', 'FontSize', 9.5, 'FontColor', TEXT_MUT, 'Position', [14 6 w_card_v-28 18]);

            % Card 3: Pressão Estática ΔPest (mmH2O / Pa)
            pCard3 = uipanel(app.TabVentilador, 'BackgroundColor', PNL, 'BorderColor', BORDER, 'Position', [20 + 2*(w_card_v + w_gap_v), y_card_v, w_card_v, h_card_v]);
            uilabel(pCard3, 'Text', 'CH6: PRESSÃO ESTÁTICA (ΔPest)', 'FontSize', 10.5, 'FontWeight', 'bold', 'FontColor', [0.00 0.45 0.75], 'Position', [14 h_card_v-26 w_card_v-28 18]);
            app.CardVentPitotVal = uilabel(pCard3, 'Text', '0.00 mmH2O', 'FontSize', 24, 'FontWeight', 'bold', 'FontColor', TEXT_DARK, 'Position', [14 26 w_card_v-28 36]);
            app.CardVentPitotSub = uilabel(pCard3, 'Text', '0.0 Pa | Transdutor AutoTran', 'FontSize', 9.5, 'FontColor', TEXT_MUT, 'Position', [14 6 w_card_v-28 18]);

            % Card 4: Pressão no Venturi ΔPventuri (mmH2O / Pa)
            pCard4 = uipanel(app.TabVentilador, 'BackgroundColor', PNL, 'BorderColor', BORDER, 'Position', [20 + 3*(w_card_v + w_gap_v), y_card_v, w_card_v, h_card_v]);
            uilabel(pCard4, 'Text', 'CH7: PRESSÃO NO VENTURI (ΔPventuri)', 'FontSize', 10.5, 'FontWeight', 'bold', 'FontColor', [0.10 0.55 0.60], 'Position', [14 h_card_v-26 w_card_v-28 18]);
            app.CardVentVenturiVal = uilabel(pCard4, 'Text', '0.00 mmH2O', 'FontSize', 24, 'FontWeight', 'bold', 'FontColor', TEXT_DARK, 'Position', [14 26 w_card_v-28 36]);
            app.CardVentVenturiSub = uilabel(pCard4, 'Text', '0.0 Pa | Transdutor AutoTran', 'FontSize', 9.5, 'FontColor', TEXT_MUT, 'Position', [14 6 w_card_v-28 18]);

            app.PanelVentCards = {pCard1, pCard2, pCard3, pCard4};

            % Gráfico Inferior Contínuo de Estabilidade Temporal
            y_ax_v = 15;
            h_ax_v = max(120, y_card_v - y_ax_v - 12);
            app.AxesVentilador = uiaxes(app.TabVentilador, 'Position', [20 y_ax_v tabW-40 h_ax_v], 'Color', [1 1 1]);
            title(app.AxesVentilador, 'Verificação Visual de Regime Permanente — Resposta Temporal de Pressões Diferenciais e Torque no Eixo', ...
                'Color', [0.12 0.20 0.35], 'FontWeight', 'bold', 'FontSize', 12);
            xlabel(app.AxesVentilador, 'Tempo Decorrido (s)', 'FontWeight', 'bold', 'FontSize', 10.5);
            grid(app.AxesVentilador, 'on'); app.AxesVentilador.GridColor = [0.88 0.90 0.94]; app.AxesVentilador.GridAlpha = 0.8;

            yyaxis(app.AxesVentilador, 'left');
            ylabel(app.AxesVentilador, 'Pressões Diferenciais [mmH_2O]', 'FontWeight', 'bold', 'FontSize', 10.5);
            app.AxesVentilador.YColor = [0.00 0.45 0.75];
            app.aLineVentPitot   = animatedline(app.AxesVentilador, 'Color', [0.00 0.45 0.75], 'LineWidth', 2.2, 'MaximumNumPoints', 50000, 'DisplayName', 'ΔPest (Estática)');
            app.aLineVentVenturi = animatedline(app.AxesVentilador, 'Color', [0.10 0.55 0.60], 'LineWidth', 2.2, 'MaximumNumPoints', 50000, 'DisplayName', 'ΔPventuri (Venturi)');

            yyaxis(app.AxesVentilador, 'right');
            ylabel(app.AxesVentilador, 'Torque no Eixo do Motor [N·m]', 'FontWeight', 'bold', 'FontSize', 10.5);
            app.AxesVentilador.YColor = [0.85 0.35 0.10];
            app.aLineVentTorque  = animatedline(app.AxesVentilador, 'Color', [0.85 0.35 0.10], 'LineWidth', 2.2, 'MaximumNumPoints', 50000, 'DisplayName', 'Torque Teixo [N·m]');

            legend(app.AxesVentilador, 'Location', 'northwest', 'FontSize', 10, 'FontWeight', 'bold');
            yyaxis(app.AxesVentilador, 'left');

            % =============================================================
            % TAB 6: CONFIGURAÇÕES
            % =============================================================
            app.TabConfig = uitab(app.TabGroup, 'Title', 'Configurações', 'BackgroundColor', BG);

            w_cfg1 = floor(tabW * 0.33);
            w_cfg2 = floor(tabW * 0.29);
            w_cfg3 = tabW - w_cfg1 - w_cfg2 - 50;
            panelH = tabH - 40;

            % -------------------------------------------------------------
            % Coluna 1: Calibração de Sensores & Fatores de Escala
            % -------------------------------------------------------------
            pCfg1 = uipanel(app.TabConfig, 'Title', 'Calibração de Sensores & Fatores de Escala', ...
                'BackgroundColor', PNL, 'BorderColor', BORDER, ...
                'Position', [15 15 w_cfg1 panelH], ...
                'FontWeight', 'bold', 'ForegroundColor', TEXT_DARK, 'FontName', 'Segoe UI', 'FontSize', 12);
            
            % Espaçamento generoso para evitar qualquer sobreposição com o título
            y_f = panelH - 52;
            dy_cfg = 34;

            uilabel(pCfg1, 'Text', 'K_rpm (Ganho Tacômetro):', 'Position', [18 y_f w_cfg1-135 22], 'FontColor', TEXT_DARK, 'FontName', 'Segoe UI', 'FontSize', 12);
            app.CfgKRPMField = uieditfield(pCfg1, 'numeric', 'Value', app.fator_escala_rpm, 'Position', [w_cfg1-105 y_f-2 88 26], 'FontName', 'Segoe UI', 'FontSize', 12.5);

            y_f = y_f - dy_cfg;
            uilabel(pCfg1, 'Text', 'Offset RPM (Ajuste Zero):', 'Position', [18 y_f w_cfg1-135 22], 'FontColor', TEXT_DARK, 'FontName', 'Segoe UI', 'FontSize', 12);
            app.CfgOffsetRPMField = uieditfield(pCfg1, 'numeric', 'Value', app.offset_rpm, 'Position', [w_cfg1-105 y_f-2 88 26], 'FontName', 'Segoe UI', 'FontSize', 12.5);

            y_f = y_f - dy_cfg;
            uilabel(pCfg1, 'Text', 'K_torque (N·m/V):', 'Position', [18 y_f w_cfg1-135 22], 'FontColor', TEXT_DARK, 'FontName', 'Segoe UI', 'FontSize', 12);
            app.CfgKTorqueField = uieditfield(pCfg1, 'numeric', 'Value', 1.0, 'Position', [w_cfg1-105 y_f-2 88 26], 'FontName', 'Segoe UI', 'FontSize', 12.5);

            y_f = y_f - dy_cfg;
            uilabel(pCfg1, 'Text', 'K_lift (N/V):', 'Position', [18 y_f w_cfg1-135 22], 'FontColor', TEXT_DARK, 'FontName', 'Segoe UI', 'FontSize', 12);
            app.CfgKLiftField = uieditfield(pCfg1, 'numeric', 'Value', 1.0, 'Position', [w_cfg1-105 y_f-2 88 26], 'FontName', 'Segoe UI', 'FontSize', 12.5);

            y_f = y_f - dy_cfg;
            uilabel(pCfg1, 'Text', 'K_drag (N/V):', 'Position', [18 y_f w_cfg1-135 22], 'FontColor', TEXT_DARK, 'FontName', 'Segoe UI', 'FontSize', 12);
            app.CfgKDragField = uieditfield(pCfg1, 'numeric', 'Value', 1.0, 'Position', [w_cfg1-105 y_f-2 88 26], 'FontName', 'Segoe UI', 'FontSize', 12.5);

            y_f = y_f - dy_cfg;
            uilabel(pCfg1, 'Text', 'K_hinge (N·m/V):', 'Position', [18 y_f w_cfg1-135 22], 'FontColor', TEXT_DARK, 'FontName', 'Segoe UI', 'FontSize', 12);
            app.CfgKHingeField = uieditfield(pCfg1, 'numeric', 'Value', 1.0, 'Position', [w_cfg1-105 y_f-2 88 26], 'FontName', 'Segoe UI', 'FontSize', 12.5);

            y_f = y_f - dy_cfg;
            uilabel(pCfg1, 'Text', 'Tara / Zero Pitot (V):', 'Position', [18 y_f w_cfg1-135 22], 'FontColor', TEXT_DARK, 'FontName', 'Segoe UI', 'FontSize', 12);
            app.CfgTaraPitotField = uieditfield(pCfg1, 'numeric', 'Value', 0.800, 'Position', [w_cfg1-105 y_f-2 88 26], 'FontName', 'Segoe UI', 'FontSize', 12.5);

            y_f = y_f - dy_cfg;
            uilabel(pCfg1, 'Text', 'Tara / Zero Venturi (V):', 'Position', [18 y_f w_cfg1-135 22], 'FontColor', TEXT_DARK, 'FontName', 'Segoe UI', 'FontSize', 12);
            app.CfgTaraVenturiField = uieditfield(pCfg1, 'numeric', 'Value', 0.800, 'Position', [w_cfg1-105 y_f-2 88 26], 'FontName', 'Segoe UI', 'FontSize', 12.5);

            y_f = y_f - dy_cfg;
            uilabel(pCfg1, 'Text', 'Fator Filtro EMA α:', 'Position', [18 y_f w_cfg1-135 22], 'FontColor', TEXT_DARK, 'FontName', 'Segoe UI', 'FontSize', 12);
            app.CfgAlphaField = uieditfield(pCfg1, 'numeric', 'Value', 0.08, 'Position', [w_cfg1-105 y_f-2 88 26], 'FontName', 'Segoe UI', 'FontSize', 12.5);

            % Botões de Ação na Coluna 1
            y_f = y_f - 48;
            app.CfgAplicarButton = uibutton(pCfg1, 'push', 'Text', 'Salvar e Aplicar Configurações', ...
                'BackgroundColor', GRN, 'FontColor', [1 1 1], 'FontWeight', 'bold', 'FontSize', 12.5, ...
                'Position', [18 y_f w_cfg1-36 34]);
            app.CfgAplicarButton.ButtonPushedFcn = createCallbackFcn(app, @AplicarConfigPushed, true);

            y_f = y_f - 40;
            app.BtnRestaurarPadrao = uibutton(pCfg1, 'push', 'Text', 'Restaurar Valores Padrão', ...
                'BackgroundColor', [0.90 0.93 0.98], 'FontColor', [0.10 0.35 0.70], 'FontWeight', 'bold', 'FontSize', 12, ...
                'Position', [18 y_f w_cfg1-36 32]);
            app.BtnRestaurarPadrao.ButtonPushedFcn = createCallbackFcn(app, @RestaurarPadroesPushed, true);

            y_f = y_f - 32;
            app.CfgInfoLabel = uilabel(pCfg1, 'Text', 'Parâmetros de calibração carregados com sucesso.', ...
                'FontSize', 10, 'FontName', 'Segoe UI', 'FontColor', [0.05 0.55 0.20], ...
                'Position', [18 y_f w_cfg1-36 22]);

            % -------------------------------------------------------------
            % Coluna 2: Habilitação de Canais de Hardware (NI-DAQmx)
            % -------------------------------------------------------------
            pCfg2 = uipanel(app.TabConfig, 'Title', 'Habilitação de Canais de Hardware', ...
                'BackgroundColor', PNL, 'BorderColor', BORDER, ...
                'Position', [25+w_cfg1 15 w_cfg2 panelH], ...
                'FontWeight', 'bold', 'ForegroundColor', TEXT_DARK, 'FontName', 'Segoe UI', 'FontSize', 12);
            
            uilabel(pCfg2, 'Text', 'Controle Individual dos Canais (NI-DAQmx):', ...
                'FontSize', 11.5, 'FontWeight', 'bold', 'FontColor', [0.10 0.40 0.70], ...
                'Position', [18 panelH-52 w_cfg2-36 20]);

            % Linhas com Switch Slider para cada canal (CH1 a CH7)
            y_sw = panelH - 96;
            dy_sw = 48;

            % CH1: RPM
            uilabel(pCfg2, 'Text', 'CH1: ctr0 (PFI0) — RPM Motor', 'FontSize', 11.5, 'FontWeight', 'bold', 'FontColor', TEXT_DARK, 'Position', [18 y_sw w_cfg2-150 18]);
            uilabel(pCfg2, 'Text', 'Sensor Indutivo (Selet BEG12)', 'FontSize', 9.5, 'FontColor', [0.45 0.45 0.45], 'Position', [18 y_sw-14 w_cfg2-150 14]);
            app.SwCanalRPM = uiswitch(pCfg2, 'slider', 'Items', {'OFF', 'ON'}, 'Value', 'ON', 'Position', [w_cfg2-105 y_sw-8 45 20]);
            app.SwCanalRPM.ValueChangedFcn = createCallbackFcn(app, @CanalSwitchChanged, true);

            % CH2: Torque
            y_sw = y_sw - dy_sw;
            uilabel(pCfg2, 'Text', 'CH2: ai5 [DIFF] — Torque Eixo', 'FontSize', 11.5, 'FontWeight', 'bold', 'FontColor', TEXT_DARK, 'Position', [18 y_sw w_cfg2-150 18]);
            uilabel(pCfg2, 'Text', 'Transmissor DY510 (0 a 10 V)', 'FontSize', 9.5, 'FontColor', [0.45 0.45 0.45], 'Position', [18 y_sw-14 w_cfg2-150 14]);
            app.SwCanalTorque = uiswitch(pCfg2, 'slider', 'Items', {'OFF', 'ON'}, 'Value', 'ON', 'Position', [w_cfg2-105 y_sw-8 45 20]);
            app.SwCanalTorque.ValueChangedFcn = createCallbackFcn(app, @CanalSwitchChanged, true);

            % CH3: Lift
            y_sw = y_sw - dy_sw;
            uilabel(pCfg2, 'Text', 'CH3: ai0 [DIFF] — Sustentação (Lift)', 'FontSize', 11.5, 'FontWeight', 'bold', 'FontColor', TEXT_DARK, 'Position', [18 y_sw w_cfg2-150 18]);
            uilabel(pCfg2, 'Text', 'Balança 514QD (Amp AD8226)', 'FontSize', 9.5, 'FontColor', [0.45 0.45 0.45], 'Position', [18 y_sw-14 w_cfg2-150 14]);
            app.SwCanalLift = uiswitch(pCfg2, 'slider', 'Items', {'OFF', 'ON'}, 'Value', 'ON', 'Position', [w_cfg2-105 y_sw-8 45 20]);
            app.SwCanalLift.ValueChangedFcn = createCallbackFcn(app, @CanalSwitchChanged, true);

            % CH4: Drag
            y_sw = y_sw - dy_sw;
            uilabel(pCfg2, 'Text', 'CH4: ai1 [DIFF] — Arrasto (Drag)', 'FontSize', 11.5, 'FontWeight', 'bold', 'FontColor', TEXT_DARK, 'Position', [18 y_sw w_cfg2-150 18]);
            uilabel(pCfg2, 'Text', 'Balança 514QD (Amp AD8226)', 'FontSize', 9.5, 'FontColor', [0.45 0.45 0.45], 'Position', [18 y_sw-14 w_cfg2-150 14]);
            app.SwCanalDrag = uiswitch(pCfg2, 'slider', 'Items', {'OFF', 'ON'}, 'Value', 'ON', 'Position', [w_cfg2-105 y_sw-8 45 20]);
            app.SwCanalDrag.ValueChangedFcn = createCallbackFcn(app, @CanalSwitchChanged, true);

            % CH5: Hinge
            y_sw = y_sw - dy_sw;
            uilabel(pCfg2, 'Text', 'CH5: ai2 [DIFF] — Momento (Hinge)', 'FontSize', 11.5, 'FontWeight', 'bold', 'FontColor', TEXT_DARK, 'Position', [18 y_sw w_cfg2-150 18]);
            uilabel(pCfg2, 'Text', 'Balança 514QD (Amp AD8226)', 'FontSize', 9.5, 'FontColor', [0.45 0.45 0.45], 'Position', [18 y_sw-14 w_cfg2-150 14]);
            app.SwCanalHinge = uiswitch(pCfg2, 'slider', 'Items', {'OFF', 'ON'}, 'Value', 'ON', 'Position', [w_cfg2-105 y_sw-8 45 20]);
            app.SwCanalHinge.ValueChangedFcn = createCallbackFcn(app, @CanalSwitchChanged, true);

            % CH6: Pitot
            y_sw = y_sw - dy_sw;
            uilabel(pCfg2, 'Text', 'CH6: ai4 [RSE] — Pressão Tubo Pitot', 'FontSize', 11.5, 'FontWeight', 'bold', 'FontColor', TEXT_DARK, 'Position', [18 y_sw w_cfg2-150 18]);
            uilabel(pCfg2, 'Text', 'AutoTran 600D (0 a 5 V / 0 a 1250 Pa)', 'FontSize', 9.5, 'FontColor', [0.45 0.45 0.45], 'Position', [18 y_sw-14 w_cfg2-150 14]);
            app.SwCanalPitot = uiswitch(pCfg2, 'slider', 'Items', {'OFF', 'ON'}, 'Value', 'ON', 'Position', [w_cfg2-105 y_sw-8 45 20]);
            app.SwCanalPitot.ValueChangedFcn = createCallbackFcn(app, @CanalSwitchChanged, true);

            % CH7: Venturi
            y_sw = y_sw - dy_sw;
            uilabel(pCfg2, 'Text', 'CH7: ai3 [RSE] — Pressão Tubo Venturi', 'FontSize', 11.5, 'FontWeight', 'bold', 'FontColor', TEXT_DARK, 'Position', [18 y_sw w_cfg2-150 18]);
            uilabel(pCfg2, 'Text', 'AutoTran 600D (0 a 5 V / 0 a 1250 Pa)', 'FontSize', 9.5, 'FontColor', [0.45 0.45 0.45], 'Position', [18 y_sw-14 w_cfg2-150 14]);
            app.SwCanalVenturi = uiswitch(pCfg2, 'slider', 'Items', {'OFF', 'ON'}, 'Value', 'ON', 'Position', [w_cfg2-105 y_sw-8 45 20]);
            app.SwCanalVenturi.ValueChangedFcn = createCallbackFcn(app, @CanalSwitchChanged, true);

            % -------------------------------------------------------------
            % Coluna 3: Fundamentação Teórica & Documentação
            % -------------------------------------------------------------
            pCfg3 = uipanel(app.TabConfig, 'Title', 'Fundamentação Teórica & Documentação', ...
                'BackgroundColor', PNL, 'BorderColor', BORDER, ...
                'Position', [35+w_cfg1+w_cfg2 15 w_cfg3 panelH], ...
                'FontWeight', 'bold', 'ForegroundColor', TEXT_DARK, 'FontName', 'Segoe UI', 'FontSize', 12);
            
            % Bloco Teórico 1: Mecânica dos Fluidos
            y_t = panelH - 52;
            uilabel(pCfg3, 'Text', '1. MECÂNICA DOS FLUIDOS NO TÚNEL DE VENTO (Fox & McDonald)', 'FontSize', 12, 'FontWeight', 'bold', 'FontColor', [0.10 0.40 0.70], 'Position', [18 y_t w_cfg3-36 22]);
            
            y_t = y_t - 46;
            
            y_t = y_t - 48;
            uilabel(pCfg3, 'Text', '\bullet \; \mathbf{Venturi \; e \; Vazao:} \quad Q = A_2 \sqrt{\frac{2 \Delta P_{\mathrm{venturi}}}{\rho [ (A_1/A_2)^2 - 1 ]}} = A_1 v_1 = A_2 v_2', 'FontSize', 12.5, 'Interpreter', 'latex', 'FontColor', TEXT_DARK, 'Position', [25 y_t w_cfg3-45 46]);

            y_t = y_t - 44;
            uilabel(pCfg3, 'Text', '\bullet \; \mathbf{Reynolds:} \quad Re = \frac{\rho \cdot v \cdot c}{\mu} \quad (\mu \approx 1{,}81 \times 10^{-5} \; \mathrm{Pa}\cdot\mathrm{s})', 'FontSize', 12.5, 'Interpreter', 'latex', 'FontColor', TEXT_DARK, 'Position', [25 y_t w_cfg3-45 40]);

            y_t = y_t - 40;

            y_t = y_t - 46;
            uilabel(pCfg3, 'Text', '\bullet \; \mathbf{Sustentacao \; (C_L):} \quad C_L = \frac{L}{q \cdot S} \quad ( \frac{dC_L}{d\alpha} \approx 2\pi, \quad \alpha_{\mathrm{estol}} \approx 16^\circ )', 'FontSize', 12.5, 'Interpreter', 'latex', 'FontColor', TEXT_DARK, 'Position', [25 y_t w_cfg3-45 44]);

            y_t = y_t - 46;
            uilabel(pCfg3, 'Text', '\bullet \; \mathbf{Arrasto \; e \; Polar \; (C_D):} \quad C_D = \frac{D}{q \cdot S} = C_{D0} + \frac{C_L^2}{\pi \cdot e \cdot AR}', 'FontSize', 12.5, 'Interpreter', 'latex', 'FontColor', TEXT_DARK, 'Position', [25 y_t w_cfg3-45 44]);

            y_t = y_t - 46;
            uilabel(pCfg3, 'Text', '\bullet \; \mathbf{Momento \; Balanca \; 514QD:} \quad C_m = \frac{M}{q \cdot S \cdot c}, \quad M_{\mathrm{pivo}} = -(x_{\mathrm{pivo}} - x_{\mathrm{cp}}) \cdot L', 'FontSize', 12.5, 'Interpreter', 'latex', 'FontColor', TEXT_DARK, 'Position', [25 y_t w_cfg3-45 44]);

            y_t = y_t - 42;
            uilabel(pCfg3, 'Text', '\bullet \; \mathbf{Eficiencia \; Aerodinamica:} \quad E = \frac{L}{D} = \frac{C_L}{C_D}', 'FontSize', 12.5, 'Interpreter', 'latex', 'FontColor', TEXT_DARK, 'Position', [25 y_t w_cfg3-45 38]);

            % Botão de Ação no Rodapé: Guia Técnico & Manual de Operação
            app.BtnManualOperacao = uibutton(pCfg3, 'push', 'Text', 'Abrir Manual de Instruções & Operação do Túnel (Guia Técnico)', ...
                'Position', [18 20 w_cfg3-36 40], 'BackgroundColor', TEL, 'FontColor', [1 1 1], 'FontWeight', 'bold', 'FontSize', 13);
            app.BtnManualOperacao.ButtonPushedFcn = createCallbackFcn(app, @abrirManualOperacao, true);
            % --- Carregar Configurações Salvas (Persistência) ---
            if exist('config_tunel.mat', 'file')
                try
                    cfg = load('config_tunel.mat');
                    if isfield(cfg, 'fator_escala_rpm'),   app.fator_escala_rpm = cfg.fator_escala_rpm; end
                    if isfield(cfg, 'offset_rpm'),         app.offset_rpm = cfg.offset_rpm; end
                    if ~isempty(app.CfgKRPMField) && isvalid(app.CfgKRPMField)
                        app.CfgKRPMField.Value = app.fator_escala_rpm;
                    end
                    if ~isempty(app.CfgOffsetRPMField) && isvalid(app.CfgOffsetRPMField)
                        app.CfgOffsetRPMField.Value = app.offset_rpm;
                    end
                    if isfield(cfg, 'fator_escala_torque')
                        app.fator_escala_torque = cfg.fator_escala_torque;
                        if ~isempty(app.CfgKTorqueField) && isvalid(app.CfgKTorqueField), app.CfgKTorqueField.Value = cfg.fator_escala_torque; end
                    end
                    if isfield(cfg, 'fator_escala_lift')
                        app.fator_escala_lift = cfg.fator_escala_lift;
                        if ~isempty(app.CfgKLiftField) && isvalid(app.CfgKLiftField), app.CfgKLiftField.Value = cfg.fator_escala_lift; end
                    end
                    if isfield(cfg, 'fator_escala_drag')
                        app.fator_escala_drag = cfg.fator_escala_drag;
                        if ~isempty(app.CfgKDragField) && isvalid(app.CfgKDragField), app.CfgKDragField.Value = cfg.fator_escala_drag; end
                    end
                    if isfield(cfg, 'fator_escala_hinge')
                        app.fator_escala_hinge = cfg.fator_escala_hinge;
                        if ~isempty(app.CfgKHingeField) && isvalid(app.CfgKHingeField), app.CfgKHingeField.Value = cfg.fator_escala_hinge; end
                    end
                    if isfield(cfg, 'alpha')
                        app.alpha = cfg.alpha;
                        if ~isempty(app.CfgAlphaField) && isvalid(app.CfgAlphaField), app.CfgAlphaField.Value = app.alpha; end
                    end
                    if isfield(cfg, 'tara_pitot')
                        app.tara_pitot = cfg.tara_pitot;
                        if ~isempty(app.CfgTaraPitotField) && isvalid(app.CfgTaraPitotField), app.CfgTaraPitotField.Value = app.tara_pitot; end
                    end
                    if isfield(cfg, 'tara_venturi')
                        app.tara_venturi = cfg.tara_venturi;
                        if ~isempty(app.CfgTaraVenturiField) && isvalid(app.CfgTaraVenturiField), app.CfgTaraVenturiField.Value = app.tara_venturi; end
                    end
                    
                    if isfield(cfg, 'habilitarCanalRPM'),     app.habilitarCanalRPM = cfg.habilitarCanalRPM; end
                    if isfield(cfg, 'habilitarCanalTorque'),  app.habilitarCanalTorque = cfg.habilitarCanalTorque; end
                    if isfield(cfg, 'habilitarCanalLift'),    app.habilitarCanalLift = cfg.habilitarCanalLift; end
                    if isfield(cfg, 'habilitarCanalDrag'),    app.habilitarCanalDrag = cfg.habilitarCanalDrag; end
                    if isfield(cfg, 'habilitarCanalHinge'),   app.habilitarCanalHinge = cfg.habilitarCanalHinge; end
                    if isfield(cfg, 'habilitarCanalPitot'),   app.habilitarCanalPitot = cfg.habilitarCanalPitot; end
                    if isfield(cfg, 'habilitarCanalVenturi'), app.habilitarCanalVenturi = cfg.habilitarCanalVenturi; end

                    if app.habilitarCanalRPM,     app.SwCanalRPM.Value = 'ON'; else, app.SwCanalRPM.Value = 'OFF'; end
                    if app.habilitarCanalTorque,  app.SwCanalTorque.Value = 'ON'; else, app.SwCanalTorque.Value = 'OFF'; end
                    if app.habilitarCanalLift,    app.SwCanalLift.Value = 'ON'; else, app.SwCanalLift.Value = 'OFF'; end
                    if app.habilitarCanalDrag,    app.SwCanalDrag.Value = 'ON'; else, app.SwCanalDrag.Value = 'OFF'; end
                    if app.habilitarCanalHinge,   app.SwCanalHinge.Value = 'ON'; else, app.SwCanalHinge.Value = 'OFF'; end
                    if app.habilitarCanalPitot,   app.SwCanalPitot.Value = 'ON'; else, app.SwCanalPitot.Value = 'OFF'; end
                    if app.habilitarCanalVenturi, app.SwCanalVenturi.Value = 'ON'; else, app.SwCanalVenturi.Value = 'OFF'; end

                    app.AplicarConfigPushed([]);
                    app.CfgInfoLabel.Text = 'Sessão restaurada! Parâmetros carregados de config_tunel.mat';
                catch
                end
            else
                app.AplicarConfigPushed([]);
            end

            % --- Inicialização dos AnimatedLines para Gráficos de Alta Performance ---
            if isempty(app.aLineLift) || ~isvalid(app.aLineLift)
                yyaxis(app.AxesForcasUnificado, 'left');
                app.aLineLift  = animatedline(app.AxesForcasUnificado, 'Color', C_LIFT, 'LineWidth', 2.4, 'MaximumNumPoints', 50000, 'DisplayName', 'Sustentação');
                app.aLineDrag  = animatedline(app.AxesForcasUnificado, 'Color', C_DRAG, 'LineWidth', 2.4, 'MaximumNumPoints', 50000, 'DisplayName', 'Arrasto');
                yyaxis(app.AxesForcasUnificado, 'right');
                app.aLineHinge = animatedline(app.AxesForcasUnificado, 'Color', [0.45 0.20 0.65], 'LineWidth', 2.4, 'MaximumNumPoints', 50000, 'DisplayName', 'Momento (Hinge)', 'Visible', 'off');
                yyaxis(app.AxesForcasUnificado, 'left');
            end
            app.AxesLift  = app.AxesForcasUnificado;
            app.AxesDrag  = app.AxesForcasUnificado;
            app.AxesHinge = app.AxesForcasUnificado;
            app.aLinePitot      = animatedline(app.AxesPitot,      'Color', C_PIT,             'LineWidth', 2, 'MaximumNumPoints', 50000);
            app.aLineVenturi    = animatedline(app.AxesVenturi,    'Color', [0.10 0.55 0.35],  'LineWidth', 2, 'MaximumNumPoints', 50000);
            app.aLineLogger     = animatedline(app.AxesLogger,     'Color', [0.10 0.25 0.50],  'LineWidth', 2, 'MaximumNumPoints', 50000);

            % --- Timer Principal Desacoplado de IHM (25 Hz = 40 ms com Descarte Ativo) ---
            app.TimerPrincipal = timer('ExecutionMode', 'fixedSpacing', ...
                                       'Period', 0.040, ...
                                       'BusyMode', 'drop', ...
                                       'TimerFcn', @(src, evt) app.callbackTimerDemo(src, evt));

            app.ForcasPlotFilterChanged();
            app.redimensionarInterface();
            app.UIFigure.Visible = 'on';
                end
    end

    % Construtor e Destrutor da Aplicação
    methods (Access = public)

        function CanalSwitchChanged(app, ~)
            app.habilitarCanalRPM     = strcmp(app.SwCanalRPM.Value, 'ON');
            app.habilitarCanalTorque  = strcmp(app.SwCanalTorque.Value, 'ON');
            app.habilitarCanalLift    = strcmp(app.SwCanalLift.Value, 'ON');
            app.habilitarCanalDrag    = strcmp(app.SwCanalDrag.Value, 'ON');
            app.habilitarCanalHinge   = strcmp(app.SwCanalHinge.Value, 'ON');
            app.habilitarCanalPitot   = strcmp(app.SwCanalPitot.Value, 'ON');
            app.habilitarCanalVenturi = strcmp(app.SwCanalVenturi.Value, 'ON');
            
            app.TabGroupSelectionChanged();
        end

        function PresetTodosCanais(app, ~, ~)
            app.SwCanalRPM.Value     = 'ON';
            app.SwCanalTorque.Value  = 'ON';
            app.SwCanalLift.Value    = 'ON';
            app.SwCanalDrag.Value    = 'ON';
            app.SwCanalHinge.Value   = 'ON';
            app.SwCanalPitot.Value   = 'ON';
            app.SwCanalVenturi.Value = 'ON';
            app.CanalSwitchChanged();
        end

        function PresetBancadaRPMTorqueLift(app, ~, ~)
            app.SwCanalRPM.Value     = 'ON';
            app.SwCanalTorque.Value  = 'ON';
            app.SwCanalLift.Value    = 'ON';
            app.SwCanalDrag.Value    = 'OFF';
            app.SwCanalHinge.Value   = 'OFF';
            app.SwCanalPitot.Value   = 'OFF';
            app.SwCanalVenturi.Value = 'OFF';
            app.CanalSwitchChanged();
        end

        function PresetApenasForcas(app, ~, ~)
            app.SwCanalRPM.Value     = 'OFF';
            app.SwCanalTorque.Value  = 'OFF';
            app.SwCanalLift.Value    = 'ON';
            app.SwCanalDrag.Value    = 'ON';
            app.SwCanalHinge.Value   = 'ON';
            app.SwCanalPitot.Value   = 'OFF';
            app.SwCanalVenturi.Value = 'OFF';
            app.CanalSwitchChanged();
        end

        function app = app_v10
            createComponents(app);
            registerApp(app, app.UIFigure);
            if nargout == 0, clear app; end
        end

        function delete(app)
            % 1. Desativa sinalização de sistema ativo
            app.sistemaAtivo = false;
            
            % 2. Para e deleta o timer principal da GUI
            try
                if ~isempty(app.TimerPrincipal) && isvalid(app.TimerPrincipal)
                    stop(app.TimerPrincipal);
                    delete(app.TimerPrincipal);
                    app.TimerPrincipal = [];
                end
            catch
            end
            
            % 3. Desconecta listeners e para/descarta sessões DAQ de hardware
            try
                if ~isempty(app.dq)
                    try, app.dq.ScansAvailableFcn = []; catch, end
                    try, stop(app.dq); catch, end
                    try, flush(app.dq); catch, end
                    try, delete(app.dq); catch, end
                    app.dq = [];
                end
            catch
            end
            
            try
                if ~isempty(app.dqCtr)
                    try, stop(app.dqCtr); catch, end
                    try, flush(app.dqCtr); catch, end
                    try, delete(app.dqCtr); catch, end
                    app.dqCtr = [];
                end
            catch
            end
            
            % 4. Reset do subsistema DAQ da NI para liberar todas as threads em background
            try
                daqreset;
            catch
            end

            % 5. Desvincula o callback e fecha a janela gráfica
            try
                if ~isempty(app.UIFigure) && isvalid(app.UIFigure)
                    app.UIFigure.CloseRequestFcn = '';
                    delete(app.UIFigure);
                end
            catch
            end
        end
    end
end
