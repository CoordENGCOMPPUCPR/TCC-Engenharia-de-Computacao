# testes unitarios do modulo 3 — modulo3.py
# todos rodam sem dependencias externas — diretorios temporarios com .png vazios
#
# executar:
#   python3 -m unittest tests/unitarios/test_modulo3.py -v

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "modulo3"))
import contextlib
import io
from unittest import mock

import modulo3
from modulo3 import (
    add_sint_suffix,
    copy_files,
    extract_plate,
    generate_index,
    list_images,
)


def _create_fake_image(directory: Path, name: str) -> Path:
    path = directory / name
    path.touch()
    return path


def _read_index(path: Path) -> list[tuple[str, str]]:
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                name, plate = line.split(",", 1)
                entries.append((name, plate))
    return entries


def _placas(path: Path) -> set[str]:
    return {p for _, p in _read_index(path)}


def _arquivos(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir())


# roda o main() real do modulo, com argumentos de linha de comando e saida em pasta temporaria
def _rodar_main(base: Path, argv_extra: list[str], nome_saida: str):
    dir_saida = base / nome_saida
    argv = ["modulo3.py"] + argv_extra + ["--saida", str(dir_saida)]
    buf = io.StringIO()
    with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(buf):
        modulo3.main()
    return dir_saida, buf.getvalue()


def _sint_do_train(dir_saida: Path) -> list[str]:
    return [n for n in _arquivos(dir_saida / "train") if n.endswith("_sint.png")]


def _setup_dir_limpas(base: Path, train_plates: list[str],
                      val_plates: list[str], test_plates: list[str]) -> Path:
    dir_limpas = base / "dir_limpas"
    for split, plates in [("train", train_plates), ("val", val_plates), ("test", test_plates)]:
        split_dir = dir_limpas / split
        split_dir.mkdir(parents=True)
        for plate in plates:
            _create_fake_image(split_dir, f"{plate}_img_000001.png")
    return dir_limpas


def _setup_dir_sinteticas(base: Path, plates: list[str]) -> Path:
    dir_sint = base / "dir_sinteticas"
    dir_sint.mkdir(parents=True)
    for plate in plates:
        _create_fake_image(dir_sint, f"{plate}_img_000001.png")
    return dir_sint


# reproduz o fluxo do main: reais + sinteticas no train, val e test sem sinteticas
def _montar_saida(base: Path, dir_limpas: Path, dir_sint: Path) -> Path:
    dir_saida = base / "saida"
    train_names = copy_files(
        list_images(dir_limpas / "train"), dir_saida / "train")
    sint_names = copy_files(
        list_images(dir_sint), dir_saida / "train", rename_sint=True)
    val_names = copy_files(
        list_images(dir_limpas / "val"), dir_saida / "val")
    test_names = copy_files(
        list_images(dir_limpas / "test"), dir_saida / "test")

    generate_index(train_names + sint_names, dir_saida / "train.txt")
    generate_index(val_names, dir_saida / "val.txt")
    generate_index(test_names, dir_saida / "test.txt")
    return dir_saida


# EXTRACT_PLATE ----------------------------------------------------------

class TestExtractPlate(unittest.TestCase):

    # formato padrao
    def test_formato_padrao(self):
        self.assertEqual(extract_plate("ABC1234_img_000001.png"), "ABC1234")

    # remove _sint antes de extrair
    def test_com_sufixo_sint(self):
        self.assertEqual(extract_plate("ABC1234_img_000001_sint.png"), "ABC1234")

    # placa mercosul
    def test_placa_mercosul(self):
        self.assertEqual(extract_plate("MER1C23_img_000001.png"), "MER1C23")


# ADD_SINT_SUFFIX --------------------------------------------------------

class TestAddSintSuffix(unittest.TestCase):

    # adiciona _sint antes da extensao
    def test_adiciona_sufixo(self):
        self.assertEqual(add_sint_suffix("ABC1234_img_000001.png"),
                         "ABC1234_img_000001_sint.png")

    # preserva extensao original
    def test_preserva_extensao(self):
        self.assertEqual(add_sint_suffix("foto.jpg"), "foto_sint.jpg")


# LIST_IMAGES ------------------------------------------------------------

class TestListImages(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    # ignora arquivos que nao sao imagem
    def test_lista_apenas_imagens(self):
        _create_fake_image(self.tmp_path, "img.png")
        _create_fake_image(self.tmp_path, "img.jpg")
        (self.tmp_path / "readme.txt").touch()
        (self.tmp_path / "data.csv").touch()
        result = list_images(self.tmp_path)
        self.assertEqual(len(result), 2)

    # diretorio inexistente retorna lista vazia
    def test_diretorio_inexistente_retorna_vazio(self):
        result = list_images(Path("/caminho/que/nao/existe"))
        self.assertEqual(result, [])

    # resultado sempre ordenado por nome
    def test_ordenacao_por_nome(self):
        _create_fake_image(self.tmp_path, "c.png")
        _create_fake_image(self.tmp_path, "a.png")
        _create_fake_image(self.tmp_path, "b.png")
        result = list_images(self.tmp_path)
        names = [f.name for f in result]
        self.assertEqual(names, ["a.png", "b.png", "c.png"])


# DATA LEAKAGE ----------------------------------------------------------

class TestDataLeakage(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    # placas de train nao aparecem em val/test
    def test_placas_train_nao_aparecem_em_val_test(self):
        dir_limpas = _setup_dir_limpas(
            self.tmp_path,
            train_plates=["AAA1111", "BBB2222", "CCC3333"],
            val_plates=["DDD4444", "EEE5555"],
            test_plates=["FFF6666", "GGG7777"],
        )
        dir_sint = _setup_dir_sinteticas(self.tmp_path, ["AAA1111", "BBB2222"])
        dir_saida = _montar_saida(self.tmp_path, dir_limpas, dir_sint)

        placas_train = _placas(dir_saida / "train.txt")
        placas_val = _placas(dir_saida / "val.txt")
        placas_test = _placas(dir_saida / "test.txt")

        # cada indice tem exatamente as placas do seu split (evita passar com indice vazio)
        self.assertEqual(placas_train, {"AAA1111", "BBB2222", "CCC3333"})
        self.assertEqual(placas_val, {"DDD4444", "EEE5555"})
        self.assertEqual(placas_test, {"FFF6666", "GGG7777"})

        self.assertEqual(placas_train & placas_val, set())
        self.assertEqual(placas_train & placas_test, set())
        self.assertEqual(placas_val & placas_test, set())

    # sinteticas de placas do train nao contaminam val/test
    def test_sintetica_de_placa_real_nao_vaza_para_val_test(self):
        dir_limpas = _setup_dir_limpas(
            self.tmp_path,
            train_plates=["AAA1111", "BBB2222"],
            val_plates=["CCC3333"],
            test_plates=["DDD4444"],
        )
        dir_sint = _setup_dir_sinteticas(self.tmp_path, ["AAA1111", "BBB2222"])
        dir_saida = _montar_saida(self.tmp_path, dir_limpas, dir_sint)

        # train: 2 reais + 2 sinteticas, com nomes distintos (nenhuma sobrescreve a real)
        arquivos_train = _arquivos(dir_saida / "train")
        self.assertEqual(len(arquivos_train), 4)
        self.assertEqual(sum(n.endswith("_sint.png") for n in arquivos_train), 2)

        # val e test: nenhum arquivo nem entrada de indice com _sint
        for split in ("val", "test"):
            for nome in _arquivos(dir_saida / split):
                self.assertNotIn("_sint", nome)
            for nome, _ in _read_index(dir_saida / f"{split}.txt"):
                self.assertNotIn("_sint", nome)

        placas_train = _placas(dir_saida / "train.txt")
        self.assertEqual(placas_train, {"AAA1111", "BBB2222"})
        self.assertEqual(_placas(dir_saida / "val.txt"), {"CCC3333"})
        self.assertEqual(_placas(dir_saida / "test.txt"), {"DDD4444"})
        self.assertEqual(placas_train & _placas(dir_saida / "val.txt"), set())
        self.assertEqual(placas_train & _placas(dir_saida / "test.txt"), set())


# PAREAMENTO IMAGEM-ROTULO -----------------------------------------------

class TestPareamento(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    # rotulo no indice bate com a placa do nome do arquivo
    def test_rotulo_no_indice_bate_com_nome_do_arquivo(self):
        d = self.tmp_path / "imgs"
        d.mkdir()

        _create_fake_image(d, "ABC1234_img_001.png")
        _create_fake_image(d, "XYZ9876_img_002.png")

        names = [f.name for f in list_images(d)]
        index_path = self.tmp_path / "index.txt"
        generate_index(names, index_path)

        self.assertEqual(dict(_read_index(index_path)), {
            "ABC1234_img_001.png": "ABC1234",
            "XYZ9876_img_002.png": "XYZ9876",
        })

    # sintetica _sint mantem rotulo correto
    def test_pareamento_com_sinteticas(self):
        d = self.tmp_path / "imgs"
        d.mkdir()

        _create_fake_image(d, "ABC1234_img_001_sint.png")

        names = [f.name for f in list_images(d)]
        index_path = self.tmp_path / "index.txt"
        generate_index(names, index_path)

        entries = _read_index(index_path)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][1], "ABC1234")


# SINTETICAS SO NO TREINO -----------------------------------------------

class TestSinteticasSoNoTreino(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    # val e test mantem os nomes originais; as sinteticas so existem no train, com sufixo
    def test_val_e_test_nao_contem_sinteticas(self):
        dir_limpas = _setup_dir_limpas(
            self.tmp_path,
            train_plates=["AAA1111"],
            val_plates=["BBB2222"],
            test_plates=["CCC3333"],
        )
        dir_sint = _setup_dir_sinteticas(self.tmp_path, ["AAA1111"])
        dir_saida = _montar_saida(self.tmp_path, dir_limpas, dir_sint)

        self.assertEqual(_arquivos(dir_saida / "val"), ["BBB2222_img_000001.png"])
        self.assertEqual(_arquivos(dir_saida / "test"), ["CCC3333_img_000001.png"])
        self.assertEqual(_arquivos(dir_saida / "train"),
                         ["AAA1111_img_000001.png", "AAA1111_img_000001_sint.png"])


# CONSISTENCIA PASTA-INDICE ----------------------------------------------

class TestConsistenciaPastaIndice(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    # arquivos na pasta == entradas no indice
    def test_toda_imagem_tem_entrada_e_vice_versa(self):
        d = self.tmp_path / "split"
        d.mkdir()

        _create_fake_image(d, "AAA1111_img_001.png")
        _create_fake_image(d, "BBB2222_img_002.png")
        _create_fake_image(d, "CCC3333_img_003.png")

        names = [f.name for f in list_images(d)]
        index_path = self.tmp_path / "split.txt"
        generate_index(names, index_path)

        arquivos_na_pasta = {f.name for f in list_images(d)}
        arquivos_no_indice = {name for name, _ in _read_index(index_path)}

        self.assertEqual(len(arquivos_no_indice), 3)
        self.assertEqual(arquivos_na_pasta, arquivos_no_indice)


# CONTAGEM DE SINTETICAS -------------------------------------------------
# rodam o main() real, que e quem escolhe as sinteticas

class TestContagemSinteticas(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _rodar(self, n_reais: int, n_sint: int, proporcao: float, seed: int = 42,
               nome_saida: str = "saida"):
        dir_limpas = _setup_dir_limpas(
            self.tmp_path,
            train_plates=[f"R{i:02d}" for i in range(1, n_reais + 1)],
            val_plates=["VAL01"], test_plates=["TST01"])
        dir_sint = _setup_dir_sinteticas(
            self.tmp_path, [f"S{i:02d}" for i in range(1, n_sint + 1)])
        return _rodar_main(self.tmp_path, [
            "--dir_limpas", str(dir_limpas), "--dir_sinteticas", str(dir_sint),
            "--proporcao", str(proporcao), "--seed", str(seed)], nome_saida)

    # proporcao 0.5 com 4 reais = 2 sinteticas, distintas e vindas da pasta
    def test_proporcao_05(self):
        dir_saida, log = self._rodar(n_reais=4, n_sint=10, proporcao=0.5)
        sint = _sint_do_train(dir_saida)
        self.assertEqual(len(sint), 2)
        self.assertEqual(len(set(sint)), 2)
        self.assertEqual(len(_arquivos(dir_saida / "train")), 6)
        self.assertTrue(all(n.split("_")[0] in {f"S{i:02d}" for i in range(1, 11)} for n in sint))
        self.assertNotIn("AVISO", log)

    # proporcao 1.0 com 4 reais = 4 sinteticas
    def test_proporcao_1(self):
        dir_saida, log = self._rodar(n_reais=4, n_sint=10, proporcao=1.0)
        sint = _sint_do_train(dir_saida)
        self.assertEqual(len(sint), 4)
        self.assertEqual(len(set(sint)), 4)

    # mais sinteticas solicitadas do que disponiveis usa todas e avisa
    def test_proporcao_maior_que_disponivel_usa_todas(self):
        dir_saida, log = self._rodar(n_reais=10, n_sint=2, proporcao=1.0)
        sint = _sint_do_train(dir_saida)
        self.assertEqual(len(sint), 2)
        self.assertIn("AVISO", log)
        self.assertIn("so ha 2 disponiveis", log)


# REPRODUTIBILIDADE ------------------------------------------------------

class TestReprodutibilidade(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _sinteticas_escolhidas(self, seed: int, nome_saida: str) -> list[str]:
        base = self.tmp_path / nome_saida
        base.mkdir()
        dir_limpas = _setup_dir_limpas(
            base, train_plates=[f"R{i:02d}" for i in range(10)],
            val_plates=["VAL01"], test_plates=["TST01"])
        dir_sint = _setup_dir_sinteticas(base, [f"P{i:03d}" for i in range(20)])
        dir_saida, _ = _rodar_main(base, [
            "--dir_limpas", str(dir_limpas), "--dir_sinteticas", str(dir_sint),
            "--proporcao", "0.5", "--seed", str(seed)], "saida")
        return _sint_do_train(dir_saida)

    # mesma seed produz mesma amostra
    def test_mesma_seed_mesma_amostra(self):
        amostra_1 = self._sinteticas_escolhidas(42, "a")
        amostra_2 = self._sinteticas_escolhidas(42, "b")
        self.assertEqual(len(amostra_1), 5)
        self.assertEqual(amostra_1, amostra_2)

    # seeds diferentes produzem amostras diferentes
    def test_seeds_diferentes_amostras_diferentes(self):
        amostra_1 = self._sinteticas_escolhidas(42, "a")
        amostra_2 = self._sinteticas_escolhidas(99, "b")
        self.assertNotEqual(amostra_1, amostra_2)


# PROPORCAO ZERO ---------------------------------------------------------

class TestProporcaoZero(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    # proporcao 0.0 nao inclui sinteticas e mantem todas as reais
    def test_proporcao_zero_sem_sinteticas(self):
        dir_limpas = _setup_dir_limpas(
            self.tmp_path,
            train_plates=["AAA1111", "BBB2222"],
            val_plates=["CCC3333"],
            test_plates=["DDD4444"],
        )
        dir_sint = _setup_dir_sinteticas(self.tmp_path, ["AAA1111", "BBB2222"])
        dir_saida, _ = _rodar_main(self.tmp_path, [
            "--dir_limpas", str(dir_limpas), "--dir_sinteticas", str(dir_sint),
            "--proporcao", "0.0"], "saida")

        self.assertEqual(_arquivos(dir_saida / "train"),
                         ["AAA1111_img_000001.png", "BBB2222_img_000001.png"])
        for name, _ in _read_index(dir_saida / "train.txt"):
            self.assertNotIn("_sint", name)


if __name__ == "__main__":
    unittest.main()
