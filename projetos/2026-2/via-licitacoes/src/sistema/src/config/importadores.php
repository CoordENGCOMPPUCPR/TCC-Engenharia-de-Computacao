<?php
/**
 * Configuração de formatos de importação de planilhas.
 *
 * Como adicionar um novo formato:
 * 1. Crie um novo array em $IMPORTADORES com a chave identificadora (ex: 'COMPRAS_GOV')
 * 2. Preencha 'nome' (exibido no select), 'descricao', e 'mapa_colunas'
 * 3. O 'mapa_colunas' associa cada nome de coluna da planilha → nome do campo no banco
 * 4. Use '_ignorar' para colunas que não devem ser importadas
 * 5. Defina qual coluna é 'chave_unica' (usada para detectar duplicatas e atualizar)
 */

if (!defined('VIA_LICITACOES')) {
    define('VIA_LICITACOES', true);
}

$IMPORTADORES = [

    'PNCP' => [
        'nome'        => 'PNCP — Portal Nacional de Contratações Públicas',
        'descricao'   => 'Planilha exportada do PNCP com editais divulgados.',
        'chave_unica' => 'id_contratacao_pncp',
        'campos_data' => ['data_publicacao', 'inicio_propostas', 'fim_propostas'],
        'campos_valor'=> ['valor_estimado', 'valor_homologado'],
        'mapa_colunas' => [
            'linkdetalhes'         => 'link_detalhes',
            'edital'               => 'numero_licitacao',
            'ultimaatualizacao'    => '_ignorar',
            'datadivulgacaopncp'   => 'data_publicacao',
            'idcontratacaopncp'    => 'id_contratacao_pncp',
            'situacao'             => 'situacao_pncp',
            'modalidade'           => 'modalidade',
            'amparolegal'          => 'amparo_legal',
            'mododisputa'          => 'modo_disputa',
            'srp'                  => 'srp',
            'fonteorcamentaria'    => 'fonte_orcamentaria',
            'orgao'                => 'orgao',
            'unidade'              => 'unidade',
            'localidade'           => 'localidade',
            'orgaosubrogado'       => '_ignorar',
            'unidadesubrogada'     => '_ignorar',
            'localidadesubrogada'  => '_ignorar',
            'iniciopropostas'      => 'inicio_propostas',
            'fimpropostas'         => 'fim_propostas',
            'fonteplataforma'      => 'plataforma',
            'objeto'               => 'objeto',
            'valorestimado'        => 'valor_estimado',
            'valorhomalogado'      => 'valor_homologado',
        ],
    ],

        'COMPRAS_RS' => [
        'nome'        => 'Compras RS — Portal de Compras do Rio Grande do Sul',
        'descricao'   => 'Planilha exportada do portal Compras RS (CELIC e demais órgãos estaduais).',
        'chave_unica' => 'processo',
        'campos_data' => ['data_publicacao', 'inicio_propostas', 'fim_propostas'],
        'campos_valor'=> [],
        'mapa_colunas' => [
            // Colunas diretas
            'processo'                       => 'processo',
            'edital'                         => 'numero_licitacao',
            'link'                           => 'link_detalhes',
            'data_publicacao'                => 'data_publicacao',
            'datapublicacao'                 => 'data_publicacao',
            'modalidade'                     => 'modalidade',
            'objeto'                         => 'objeto',
            'abertura_sessao'                => 'inicio_propostas',
            'aberturasessao'                 => 'inicio_propostas',
            'central_de_compras'             => 'central_compras',
            'centraldecompras'               => 'central_compras',

            // Colunas "Ident_*" (o portal exporta as informações principais com esse prefixo)
            'ident_processo'                 => 'processo',
            'ident_edital'                   => 'numero_licitacao',
            'ident_modalidade'               => 'modalidade',
            'ident_data_de_publicacao'       => 'data_publicacao',
            'ident_objeto'                   => 'objeto',
            'ident_criterio_de_julgamento'   => 'criterio_julgamento',
            'ident_modo_de_disputa'          => 'modo_disputa',
            'ident_tipo_de_objeto'           => 'tipo_objeto',
            'ident_local'                    => 'localidade',
            'ident_orgao_requisitante'       => 'orgao_requisitante',
            'ident_situacao'                 => 'situacao_pncp',
            'ident_central_de_compras'       => 'central_compras',

            // JSONs que serão processados no parser (valores extraídos via regex)
            'det_lotes_json'                 => '_json_lotes',
            'det_identificacao_json'         => '_json_identificacao',

            // Ignorar as demais
            'det_titulo'                     => '_ignorar',
            'det_contato_json'               => '_ignorar',
            'det_documentos_json'            => '_ignorar',
            'det_historico_json'             => '_ignorar',
            'det_esclarecimentos_json'       => '_ignorar',
            'qtd_documentos'                 => '_ignorar',
            'qtd_lotes'                      => '_ignorar',
            'qtd_historico'                  => '_ignorar',
        ],
        'uf_padrao' => 'RS',
    ],

    // ⬇️ PRÓXIMOS FORMATOS ENTRAM AQUI ⬇️
    //
    // 'COMPRAS_GOV' => [
    //     'nome'        => 'Compras.gov.br',
    //     'descricao'   => 'Planilha exportada do portal federal.',
    //     'chave_unica' => 'numero_licitacao',
    //     'campos_data' => ['data_publicacao'],
    //     'campos_valor'=> ['valor_estimado'],
    //     'mapa_colunas' => [
    //         'numerodoprocesso' => 'numero_licitacao',
    //         'objeto'           => 'objeto',
    //         ...
    //     ],
    // ],
    //
    // 'BLL' => [ ... ],
    // 'LICITANET' => [ ... ],
];