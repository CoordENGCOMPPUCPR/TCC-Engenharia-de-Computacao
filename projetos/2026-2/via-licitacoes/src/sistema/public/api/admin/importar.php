<?php
require_once __DIR__ . '/../../../src/config/config.php';
require_once __DIR__ . '/../../../src/config/database.php';
require_once __DIR__ . '/../../../src/config/importadores.php';
require_once __DIR__ . '/../../../src/core/Auth.php';
require_once __DIR__ . '/../../../src/core/Response.php';

Auth::exigirAdmin();
$db = Database::getConnection();
$user = Auth::usuario();
$action = $_GET['action'] ?? $_POST['action'] ?? '';
$formato = $_GET['formato'] ?? $_POST['formato'] ?? 'PNCP';

if (!isset($IMPORTADORES[$formato])) {
    Response::error('Formato de importação não reconhecido.');
}
$CONFIG = $IMPORTADORES[$formato];

/* =====================================================
   UTILITÁRIOS
   ===================================================== */

function normalizarNome(string $s): string
{
    $s = str_replace(
        ['á','à','ã','â','ä','é','è','ê','ë','í','ì','î','ï','ó','ò','õ','ô','ö','ú','ù','û','ü','ç','ñ',
         'Á','À','Ã','Â','Ä','É','È','Ê','Ë','Í','Ì','Î','Ï','Ó','Ò','Õ','Ô','Ö','Ú','Ù','Û','Ü','Ç','Ñ'],
        ['a','a','a','a','a','e','e','e','e','i','i','i','i','o','o','o','o','o','u','u','u','u','c','n',
         'a','a','a','a','a','e','e','e','e','i','i','i','i','o','o','o','o','o','u','u','u','u','c','n'],
        $s
    );
    $s = strtolower($s);
    return preg_replace('/[^a-z0-9]/', '', $s);
}

function lerXLSX(string $caminho): array
{
    if (!class_exists('ZipArchive')) throw new Exception('Extensão ZIP não habilitada.');
    $zip = new ZipArchive();
    if ($zip->open($caminho) !== true) throw new Exception('Não foi possível abrir o XLSX.');

    $strings = [];
    $ssXml = $zip->getFromName('xl/sharedStrings.xml');
    if ($ssXml !== false) {
        $ss = simplexml_load_string($ssXml);
        foreach ($ss->si as $si) {
            if (isset($si->t)) $strings[] = (string)$si->t;
            else { $txt = ''; foreach ($si->r as $r) $txt .= (string)$r->t; $strings[] = $txt; }
        }
    }

    $sheetXml = $zip->getFromName('xl/worksheets/sheet1.xml');
    if ($sheetXml === false) throw new Exception('Planilha não encontrada.');

    $sheet = simplexml_load_string($sheetXml);
    $linhas = [];
    foreach ($sheet->sheetData->row as $row) {
        $linha = [];
        foreach ($row->c as $c) {
            $ref  = (string)$c['r'];
            $col  = preg_replace('/\d+/', '', $ref);
            $tipo = (string)$c['t'];
            if ($tipo === 's')          $valor = $strings[(int)$c->v] ?? '';
            elseif ($tipo === 'inlineStr') $valor = (string)$c->is->t;
            else                          $valor = (string)$c->v;
            $linha[$col] = $valor;
        }
        $linhas[] = $linha;
    }
    $zip->close();
    return $linhas;
}

function lerCSV(string $caminho): array
{
    $linhas = [];
    $h = fopen($caminho, 'r');
    if (!$h) throw new Exception('Não foi possível abrir o CSV.');
    $primeira = fgets($h); rewind($h);
    $delim = (substr_count($primeira, ';') > substr_count($primeira, ',')) ? ';' : ',';
    while (($row = fgetcsv($h, 0, $delim)) !== false) $linhas[] = $row;
    fclose($h);
    return $linhas;
}

function normalizarData(?string $v): ?string
{
    if ($v === null) return null;
    $v = trim($v);
    if ($v === '') return null;
    if (preg_match('#^(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2})#', $v, $m))
        return "{$m[3]}-{$m[2]}-{$m[1]} {$m[4]}:{$m[5]}:00";
    if (preg_match('#^(\d{2})/(\d{2})/(\d{4})#', $v, $m))
        return "{$m[3]}-{$m[2]}-{$m[1]}";
    if (preg_match('#^\d{4}-\d{2}-\d{2}#', $v)) return substr($v, 0, 10);
    return null;
}

function normalizarValor($v): ?float
{
    if ($v === null) return null;
    if (is_numeric($v)) { $f = (float)$v; return $f == 0 ? null : $f; }
    $v = trim((string)$v);
    if ($v === '') return null;
    $u = strtoupper($v);
    if (str_contains($u, 'SIGILOSO') || str_contains($u, 'NÃO INFORM') || str_contains($u, 'NAO INFORM')) return null;
    $v = str_replace(['R$', ' ', "\xc2\xa0"], '', $v);
    if (preg_match('/^\d{1,3}(\.\d{3})+(,\d+)?$/', $v)) return (float)str_replace(',', '.', str_replace('.', '', $v));
    if (preg_match('/^\d+,\d+$/', $v)) return (float)str_replace(',', '.', $v);
    if (preg_match('/^\d+(\.\d+)?$/', $v)) return (float)$v;
    return null;
}

/**
 * Extrai o valor estimado a partir do JSON de lotes (Compras RS)
 */
function extrairValorDosLotes(?string $jsonLotes): ?float
{
    if (!$jsonLotes) return null;
    $lotes = json_decode($jsonLotes, true);
    if (!is_array($lotes)) return null;

    // Compras RS costuma ter "valor_estimado" ou "valor_total" por lote
    foreach ($lotes as $lote) {
        foreach (['valor_estimado','valor_total','valor_maximo','valor'] as $campo) {
            if (!empty($lote[$campo]) && is_numeric(str_replace([',','.'],['.','.'], $lote[$campo]))) {
                return (float) str_replace(',', '.', $lote[$campo]);
            }
        }
    }
    return null;
}

/**
 * Extrai a data de início das propostas do JSON de lotes
 */
function extrairInicioPropostas(?string $jsonLotes): ?string
{
    if (!$jsonLotes) return null;
    $lotes = json_decode($jsonLotes, true);
    if (!is_array($lotes)) return null;

    foreach ($lotes as $lote) {
        if (!empty($lote['abertura_propostas'])) {
            return normalizarData($lote['abertura_propostas']);
        }
    }
    return null;
}

/**
 * Extrai dados do JSON de identificação (Compras RS)
 * Retorna array associativo com campos padronizados.
 */
function extrairDaIdentificacao(?string $jsonIdent): array
{
    if (!$jsonIdent) return [];
    $d = json_decode($jsonIdent, true);
    if (!is_array($d)) return [];

    $out = [];
    if (!empty($d['Objeto']))              $out['objeto'] = $d['Objeto'];
    if (!empty($d['Órgão Requisitante']))  $out['orgao_requisitante'] = $d['Órgão Requisitante'];
    if (!empty($d['Central de compras']))  $out['central_compras'] = $d['Central de compras'];
    if (!empty($d['Critério de julgamento'])) $out['criterio_julgamento'] = $d['Critério de julgamento'];
    if (!empty($d['Modo de disputa']))     $out['modo_disputa'] = $d['Modo de disputa'];
    if (!empty($d['Tipo de objeto']))      $out['tipo_objeto'] = $d['Tipo de objeto'];
    if (!empty($d['Modalidade']))          $out['modalidade'] = $d['Modalidade'];
    if (!empty($d['Data de publicação']))  $out['data_publicacao'] = normalizarData($d['Data de publicação']);
    if (!empty($d['Local']))               $out['localidade'] = $d['Local'];
    return $out;
}

/**
 * Separa localidade em (municipio, uf) para Compras RS
 * Formatos possíveis: "Pouso Alto/MG", "PORTO ALEGRE - RS", ou endereço completo.
 */
function separarLocalidadeRS(?string $localidade): array
{
    $localidade = trim((string)$localidade);
    if ($localidade === '') return ['', ''];

    // "Cidade/UF"
    if (preg_match('#^(.+?)\s*/\s*([A-Z]{2})\s*$#', $localidade, $m)) {
        return [trim($m[1]), $m[2]];
    }
    // "... - Cidade - UF" ou "... - CIDADE - UF"
    if (preg_match('#-\s*([A-Za-zÀ-ÿ\s]+?)\s*-\s*([A-Z]{2})\s*$#', $localidade, $m)) {
        return [trim($m[1]), $m[2]];
    }
    return ['', ''];
}


function normalizarBooleano($v): int
{
    $u = strtolower(trim((string)$v));
    return in_array($u, ['sim', 's', 'yes', 'true', '1'], true) ? 1 : 0;
}

/**
 * Extrai "Cidade/UF" em municipio + uf
 */
function separarLocalidade(?string $localidade): array
{
    $localidade = trim((string)$localidade);
    if (preg_match('#^(.+?)\s*/\s*([A-Z]{2})$#', $localidade, $m)) {
        return [trim($m[1]), $m[2]];
    }
    return ['', ''];
}

/**
 * Processa linhas do arquivo bruto em um array associativo [campo_banco => valor]
 */
function processarLinhas(array $rows, array $config): array
{
    $resultado = [];
    foreach ($rows as $r) {
        $item = [];
        foreach ($r as $campo => $valor) {
            $item[$campo] = $valor;
        }
        $resultado[] = $item;
    }
    return $resultado;
}

/* =====================================================
   ACTIONS
   ===================================================== */

switch ($action) {

    case 'formatos':
        $lista = [];
        foreach ($IMPORTADORES as $chave => $c) {
            $lista[] = [
                'chave'     => $chave,
                'nome'      => $c['nome'],
                'descricao' => $c['descricao'],
            ];
        }
        Response::json(['success' => true, 'formatos' => $lista]);
        break;

    case 'preview':
        if (empty($_FILES['arquivo'])) Response::error('Nenhum arquivo enviado.');

        $f = $_FILES['arquivo'];
        if ($f['error'] !== UPLOAD_ERR_OK) Response::error('Erro no upload.');
        if ($f['size'] > 20 * 1024 * 1024) Response::error('Arquivo muito grande (máx. 20MB).');

        $ext = strtolower(pathinfo($f['name'], PATHINFO_EXTENSION));
        if (!in_array($ext, ['xlsx', 'xls', 'csv'])) Response::error('Formato não suportado.');

        $tmp = sys_get_temp_dir() . '/via_import_' . uniqid() . '.' . $ext;
        if (!move_uploaded_file($f['tmp_name'], $tmp)) Response::error('Falha ao salvar arquivo.');

        try {
            $rows = [];

            if ($ext === 'csv') {
                $linhas = lerCSV($tmp);
                $header = array_shift($linhas);
                $mapColunas = [];
                foreach ($header as $i => $nomeOriginal) {
                    $nomeNorm = normalizarNome($nomeOriginal);
                    $campo = $CONFIG['mapa_colunas'][$nomeNorm] ?? null;
                    if ($campo && $campo !== '_ignorar') $mapColunas[$i] = $campo;
                }
                foreach ($linhas as $l) {
                    $item = [];
                    foreach ($mapColunas as $i => $campo) $item[$campo] = $l[$i] ?? '';
                    if (empty(array_filter($item, fn($v) => trim((string)$v) !== ''))) continue;
                    $rows[] = $item;
                }
            } else {
                $bruto = lerXLSX($tmp);
                if (empty($bruto)) Response::error('Planilha vazia.');

                $headerRefs = array_shift($bruto);
                $mapColunas = [];
                foreach ($headerRefs as $col => $nomeOriginal) {
                    $nomeNorm = normalizarNome($nomeOriginal);
                    $campo = $CONFIG['mapa_colunas'][$nomeNorm] ?? null;
                    if ($campo && $campo !== '_ignorar') $mapColunas[$col] = $campo;
                }

                foreach ($bruto as $linhaRaw) {
                    $item = [];
                    foreach ($mapColunas as $col => $campo) $item[$campo] = $linhaRaw[$col] ?? '';
                    if (empty(array_filter($item, fn($v) => trim((string)$v) !== ''))) continue;
                    $rows[] = $item;
                }
            }
        } finally {
            @unlink($tmp);
        }

        if (empty($rows)) Response::error('Nenhuma linha válida encontrada.');

        // Detecta quais colunas o mapeamento encontrou
        $colunasEncontradas = array_keys($rows[0]);

                // === Processamento especial para formatos com JSON embutido (Compras RS) ===
        $temJsonLotes = in_array('_json_lotes', $colunasEncontradas, true);
        $temJsonIdent = in_array('_json_identificacao', $colunasEncontradas, true);

        if ($temJsonLotes || $temJsonIdent) {
            foreach ($rows as &$r) {
                if ($temJsonLotes && !empty($r['_json_lotes'])) {
                    $inicio = extrairInicioPropostas($r['_json_lotes']);
                    if ($inicio && empty($r['inicio_propostas'])) {
                        $r['inicio_propostas'] = $inicio;
                    }
                }
                if ($temJsonIdent && !empty($r['_json_identificacao'])) {
                    $extra = extrairDaIdentificacao($r['_json_identificacao']);
                    foreach ($extra as $k => $v) {
                        if (empty($r[$k]) || $r[$k] === '') {
                            $r[$k] = $v;
                        }
                    }
                }
                // Limpa os campos _json_* que não vão pro banco
                unset($r['_json_lotes'], $r['_json_identificacao']);
            }
            unset($r);

            // Recalcula colunas sem os _json_*
            $colunasEncontradas = array_values(array_filter(
                array_keys($rows[0]),
                fn($c) => !str_starts_with($c, '_json_')
            ));
        }

        // Analisa: novos / atualizados
        $chaveUnica = $CONFIG['chave_unica'];
        if (!in_array($chaveUnica, $colunasEncontradas, true)) {
            Response::error("A planilha não contém a coluna obrigatória '{$chaveUnica}'.");
        }

        $novos = 0;
        $atualizados = 0;
        $ignorados = 0;

        foreach ($rows as $r) {
            $chave = trim((string)($r[$chaveUnica] ?? ''));
            if ($chave === '') { $ignorados++; continue; }
            $hash = hash('sha256', $chave);
            $check = $db->prepare("SELECT id FROM licitacoes WHERE hash_registro = ? LIMIT 1");
            $check->execute([$hash]);
            if ($check->fetch()) $atualizados++;
            else $novos++;
        }

        // Salva JSON temporário
        $pastaTmp = STORAGE_PATH . '/tmp';
        if (!is_dir($pastaTmp)) mkdir($pastaTmp, 0775, true);
        $nomeTmp = 'import_' . $formato . '_' . date('Ymd_His') . '_' . bin2hex(random_bytes(4)) . '.json';
        
        // Garante que a pasta existe E é gravável
        $pastaTmp = STORAGE_PATH . '/tmp';
        if (!is_dir($pastaTmp)) {
            if (!mkdir($pastaTmp, 0775, true)) {
                Response::error('Não foi possível criar pasta temporária. Verifique permissões em /storage.');
            }
        }
        if (!is_writable($pastaTmp)) {
            Response::error('Pasta /storage/tmp não tem permissão de escrita.');
        }

        file_put_contents($pastaTmp . '/' . $nomeTmp, json_encode([
            'formato' => $formato,
            'rows'    => $rows,
        ], JSON_UNESCAPED_UNICODE));

        // Preview: 10 primeiras linhas
        $preview = array_slice($rows, 0, 10);

        Response::json([
            'success'      => true,
            'formato'      => $formato,
            'formato_nome' => $CONFIG['nome'],
            'total'        => count($rows),
            'novos'        => $novos,
            'atualizados'  => $atualizados,
            'ignorados'    => $ignorados,
            'colunas'      => $colunasEncontradas,
            'preview'      => $preview,
            'arquivo_tmp'  => $nomeTmp,
        ]);
        break;

    case 'confirmar':
        $arquivoTmp = basename($_POST['arquivo_tmp'] ?? '');
        if ($arquivoTmp === '') Response::error('Arquivo não encontrado.');

        $caminho = STORAGE_PATH . '/tmp/' . $arquivoTmp;

        $arquivoTmp = basename($_POST['arquivo_tmp'] ?? '');
        if ($arquivoTmp === '') Response::error('Nome de arquivo temporário não enviado.');

        $caminho = STORAGE_PATH . '/tmp/' . $arquivoTmp;

        if (!file_exists($caminho)) {
            // Debug: lista o que tem na pasta
            $existentes = is_dir(STORAGE_PATH . '/tmp')
                ? array_diff(scandir(STORAGE_PATH . '/tmp'), ['.', '..'])
                : [];
            Response::error(
                'Arquivo temporário não encontrado (' . $arquivoTmp . '). '
                . 'Arquivos disponíveis: ' . (empty($existentes) ? 'nenhum' : implode(', ', $existentes))
            );
        }


        if (!file_exists($caminho)) Response::error('Arquivo temporário expirou. Refaça o upload.');

        $pacote = json_decode(file_get_contents($caminho), true);
        if (!is_array($pacote) || empty($pacote['rows'])) Response::error('Arquivo inválido.');

        $rows = $pacote['rows'];
        $formatoArq = $pacote['formato'] ?? 'PNCP';
        if (!isset($IMPORTADORES[$formatoArq])) Response::error('Formato inválido no pacote.');
        $CONFIG = $IMPORTADORES[$formatoArq];
        $chaveUnica = $CONFIG['chave_unica'];

        // Fonte padrão
        $fonteNome = $CONFIG['nome'];
        $fonteId = $db->query("SELECT id FROM fontes_coleta WHERE nome = " . $db->quote($fonteNome) . " LIMIT 1")->fetchColumn();
        if (!$fonteId) {
            $db->prepare("INSERT INTO fontes_coleta (nome, url_base, tipo) VALUES (?, NULL, 'IMPORTACAO')")
               ->execute([$fonteNome]);
            $fonteId = $db->lastInsertId();
        }

        // Registra a importação
        // Se for admin hardcoded (id = 0), grava NULL em vez de 0
        $idUsuarioLog = (int)$user['id'];
        if ($idUsuarioLog <= 0) $idUsuarioLog = null;

        $ins = $db->prepare("
            INSERT INTO importacoes (id_usuario, formato, nome_arquivo, total_linhas, status)
            VALUES (?, ?, ?, ?, 'EM_ANDAMENTO')
        ");
        $ins->execute([$idUsuarioLog, $formatoArq, $arquivoTmp, count($rows)]);
        $importacaoId = $db->lastInsertId();

        $inseridos = 0;
        $atualizados = 0;
        $ignorados = 0;

        // Colunas que a tabela licitacoes aceita (whitelist)
        $colunasPermitidas = [
            'link_detalhes','id_contratacao_pncp','numero_licitacao','processo',
            'data_publicacao','situacao_pncp','modalidade','amparo_legal','modo_disputa',
            'criterio_julgamento','tipo_objeto','srp',
            'fonte_orcamentaria','orgao','central_compras','orgao_requisitante',
            'unidade','localidade','uf','municipio',
            'inicio_propostas','fim_propostas','plataforma','objeto',
            'valor_estimado','valor_homologado'
        ];

        $db->beginTransaction();
        try {
            foreach ($rows as $r) {
                $chave = trim((string)($r[$chaveUnica] ?? ''));
                if ($chave === '') { $ignorados++; continue; }
                $hash = hash('sha256', $chave);

                // Sanitiza e trata os campos
                $dados = [];
                foreach ($colunasPermitidas as $c) {
                    if (!array_key_exists($c, $r)) continue;
                    $v = $r[$c];

                    // Normalizações por tipo
                    if (in_array($c, ['data_publicacao','inicio_propostas','fim_propostas'], true)) {
                        $v = normalizarData($v);
                    } elseif (in_array($c, ['valor_estimado','valor_homologado'], true)) {
                        $v = normalizarValor($v);
                    } elseif ($c === 'srp') {
                        $v = normalizarBooleano($v);
                    } else {
                        $v = trim((string)$v) ?: null;
                    }
                    $dados[$c] = $v;
                }

                // Quebra localidade em uf/municipio
                if (!empty($dados['localidade'])) {
                    [$municipio, $uf] = separarLocalidadeRS($dados['localidade']);
                    if ($uf && empty($dados['uf'])) $dados['uf'] = $uf;
                    if ($municipio && empty($dados['municipio'])) $dados['municipio'] = $municipio;
                }

                // Aplica UF padrão do formato (ex: RS para Compras RS)
                if (empty($dados['uf']) && !empty($CONFIG['uf_padrao'])) {
                    $dados['uf'] = $CONFIG['uf_padrao'];
                }

                // Verifica se existe
                $check = $db->prepare("SELECT id FROM licitacoes WHERE hash_registro = ? LIMIT 1");
                $check->execute([$hash]);
                $idExistente = $check->fetchColumn();

                if ($idExistente) {
                    // UPDATE
                    $sets = [];
                    $params = [];
                    foreach ($dados as $col => $val) {
                        $sets[] = "{$col} = ?";
                        $params[] = $val;
                    }
                    $sets[] = "data_ultima_atualizacao = NOW()";
                    $sets[] = "origem_importacao = ?";
                    $params[] = $formatoArq;
                    $params[] = $idExistente;

                    $sql = "UPDATE licitacoes SET " . implode(', ', $sets) . " WHERE id = ?";
                    $db->prepare($sql)->execute($params);
                    $atualizados++;
                } else {
                    // INSERT
                    $dados['id_fonte'] = $fonteId;
                    $dados['hash_registro'] = $hash;
                    $dados['status'] = 'ABERTA';
                    $dados['origem_importacao'] = $formatoArq;
                    $dados['data_ultima_atualizacao'] = date('Y-m-d H:i:s');

                    $cols = array_keys($dados);
                    $placeholders = array_fill(0, count($cols), '?');
                    $sql = "INSERT INTO licitacoes (" . implode(',', $cols) . ") VALUES (" . implode(',', $placeholders) . ")";
                    $db->prepare($sql)->execute(array_values($dados));
                    $inseridos++;
                }
            }

            // Atualiza registro da importação
            $db->prepare("
                UPDATE importacoes
                SET total_novos = ?, total_atualizados = ?, total_ignorados = ?,
                    status = 'CONCLUIDO', data_fim = NOW(),
                    mensagem = ?
                WHERE id = ?
            ")->execute([
                $inseridos, $atualizados, $ignorados,
                "Formato $formatoArq — $inseridos novos, $atualizados atualizados, $ignorados ignorados",
                $importacaoId
            ]);

            // Log de execução
            $db->prepare("
                INSERT INTO logs_execucao (id_fonte, tipo_execucao, status, mensagem, quantidade_registros)
                VALUES (?, 'IMPORTACAO_XLSX', 'SUCESSO', ?, ?)
            ")->execute([
                $fonteId,
                "Importação $formatoArq — $inseridos novos, $atualizados atualizados",
                $inseridos + $atualizados
            ]);

            $db->commit();
        } catch (Throwable $e) {
            $db->rollBack();
            $db->prepare("UPDATE importacoes SET status='ERRO', mensagem=?, data_fim=NOW() WHERE id=?")
               ->execute([$e->getMessage(), $importacaoId]);
            Response::error('Erro na importação: ' . $e->getMessage(), 500);
        }

        @unlink($caminho);

        Response::success(
            "Importação concluída: $inseridos novos, $atualizados atualizados, $ignorados ignorados."
        );
        break;

    default:
        Response::error('Ação inválida.', 404);
}