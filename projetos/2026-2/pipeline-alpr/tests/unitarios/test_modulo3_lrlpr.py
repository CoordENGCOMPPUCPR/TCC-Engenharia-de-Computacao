# testes unitarios do modulo3_LRLPR.py — dataset hibrido sobre LRLPR-26
#
# executar:
#   python3 -m unittest tests/unitarios/test_modulo3_lrlpr.py -v

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "modulo3"))
import contextlib
import io
from unittest import mock

import modulo3_LRLPR
from modulo3_LRLPR import (
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
    argv = ["modulo3_LRLPR.py"] + argv_extra + ["--saida", str(dir_saida)]
    buf = io.StringIO()
    with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(buf):
        modulo3_LRLPR.main()
    return dir_saida, buf.getvalue()


def _sint_do_train(dir_saida: Path) -> list[str]:
    return [n for n in _arquivos(dir_saida / "train") if n.endswith("_sint.png")]


def _setup_dir_lrlpr(base: Path, train_plates: list[str],
                     val_plates: list[str]) -> Path:
    dir_lrlpr = base / "dir_lrlpr"
    for split, plates in [("train", train_plates), ("val", val_plates)]:
        split_dir = dir_lrlpr / split
        split_dir.mkdir(parents=True)
        for plate in plates:
            _create_fake_image(split_dir, f"{plate}_00001_lr001.png")
    return dir_lrlpr


def _setup_dir_sinteticas(base: Path, plates: list[str]) -> Path:
    dir_sint = base / "dir_sinteticas"
    dir_sint.mkdir(parents=True)
    for plate in plates:
        _create_fake_image(dir_sint, f"{plate}_00001_lr001.png")
    return dir_sint


# reproduz o fluxo do main: reais + sinteticas no train, val sem sinteticas
def _montar_saida(base: Path, dir_lrlpr: Path, dir_sint: Path) -> Path:
    dir_saida = base / "saida"
    train_names = copy_files(
        list_images(dir_lrlpr / "train"), dir_saida / "train")
    sint_names = copy_files(
        list_images(dir_sint), dir_saida / "train", rename_sint=True)
    val_names = copy_files(
        list_images(dir_lrlpr / "val"), dir_saida / "val")

    generate_index(train_names + sint_names, dir_saida / "train.txt")
    generate_index(val_names, dir_saida / "val.txt")
    return dir_saida


# EXTRACT_PLATE ----------------------------------------------------------

class TestExtractPlateLRLPR(unittest.TestCase):

    # formato LRLPR padrao
    def test_formato_lrlpr(self):
        self.assertEqual(extract_plate("ABC1234_00001_lr001.png"), "ABC1234")

    # remove _sint antes de extrair
    def test_formato_lrlpr_com_sint(self):
        self.assertEqual(extract_plate("ABC1234_00001_lr001_sint.png"), "ABC1234")

    # placa mercosul
    def test_placa_mercosul(self):
        self.assertEqual(extract_plate("MER1C23_00010_hr003.jpg"), "MER1C23")


# ADD_SINT_SUFFIX --------------------------------------------------------

class TestAddSintSuffixLRLPR(unittest.TestCase):

    # adiciona _sint antes da extensao
    def test_formato_lrlpr(self):
        self.assertEqual(
            add_sint_suffix("ABC1234_00001_lr001.png"),
            "ABC1234_00001_lr001_sint.png")


# DATA LEAKAGE ----------------------------------------------------------

class TestDataLeakageLRLPR(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    # placas de train nao aparecem em val
    def test_placas_train_nao_aparecem_em_val(self):
        dir_lrlpr = _setup_dir_lrlpr(
            self.tmp_path,
            train_plates=["AAA1111", "BBB2222"],
            val_plates=["CCC3333", "DDD4444"],
        )
        dir_sint = _setup_dir_sinteticas(self.tmp_path, ["AAA1111"])
        dir_saida = _montar_saida(self.tmp_path, dir_lrlpr, dir_sint)

        placas_train = _placas(dir_saida / "train.txt")
        placas_val = _placas(dir_saida / "val.txt")

        # cada indice tem exatamente as placas do seu split (evita passar com indice vazio)
        self.assertEqual(placas_train, {"AAA1111", "BBB2222"})
        self.assertEqual(placas_val, {"CCC3333", "DDD4444"})
        self.assertEqual(placas_train & placas_val, set())

    # sinteticas de placas do train nao vazam para val
    def test_sintetica_da_placa_de_train_nao_vaza_para_val(self):
        dir_lrlpr = _setup_dir_lrlpr(
            self.tmp_path,
            train_plates=["AAA1111", "BBB2222"],
            val_plates=["CCC3333"],
        )
        dir_sint = _setup_dir_sinteticas(self.tmp_path, ["AAA1111", "BBB2222"])
        dir_saida = _montar_saida(self.tmp_path, dir_lrlpr, dir_sint)

        # train: 2 reais + 2 sinteticas, com nomes distintos (nenhuma sobrescreve a real)
        arquivos_train = _arquivos(dir_saida / "train")
        self.assertEqual(len(arquivos_train), 4)
        self.assertEqual(sum(n.endswith("_sint.png") for n in arquivos_train), 2)

        # val: nenhum arquivo nem entrada de indice com _sint
        for nome in _arquivos(dir_saida / "val"):
            self.assertNotIn("_sint", nome)
        for nome, _ in _read_index(dir_saida / "val.txt"):
            self.assertNotIn("_sint", nome)

        placas_train = _placas(dir_saida / "train.txt")
        placas_val = _placas(dir_saida / "val.txt")
        self.assertEqual(placas_train, {"AAA1111", "BBB2222"})
        self.assertEqual(placas_val, {"CCC3333"})
        self.assertEqual(placas_train & placas_val, set())


# PAREAMENTO IMAGEM-ROTULO -----------------------------------------------

class TestPareamentoLRLPR(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    # indice extrai placa correta do formato LRLPR
    def test_rotulo_correto_formato_lrlpr(self):
        d = self.tmp_path / "imgs"
        d.mkdir()
        _create_fake_image(d, "ABC1234_00001_lr001.png")
        _create_fake_image(d, "XYZ9876_00002_hr003.png")

        names = [f.name for f in list_images(d)]
        index_path = self.tmp_path / "index.txt"
        generate_index(names, index_path)

        self.assertEqual(dict(_read_index(index_path)), {
            "ABC1234_00001_lr001.png": "ABC1234",
            "XYZ9876_00002_hr003.png": "XYZ9876",
        })

    # sintetica _sint mantem placa correta
    def test_rotulo_correto_com_sintetica_lrlpr(self):
        d = self.tmp_path / "imgs"
        d.mkdir()
        _create_fake_image(d, "ABC1234_00001_lr001_sint.png")

        names = [f.name for f in list_images(d)]
        index_path = self.tmp_path / "index.txt"
        generate_index(names, index_path)

        entries = _read_index(index_path)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][1], "ABC1234")


# SINTETICAS SO NO TREINO -----------------------------------------------

class TestSinteticasSoNoTreinoLRLPR(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    # val mantem os nomes originais; a sintetica so existe no train, com sufixo
    def test_val_nao_contem_sinteticas(self):
        dir_lrlpr = _setup_dir_lrlpr(
            self.tmp_path,
            train_plates=["AAA1111"],
            val_plates=["BBB2222"],
        )
        dir_sint = _setup_dir_sinteticas(self.tmp_path, ["AAA1111"])
        dir_saida = _montar_saida(self.tmp_path, dir_lrlpr, dir_sint)

        self.assertEqual(_arquivos(dir_saida / "val"), ["BBB2222_00001_lr001.png"])
        self.assertEqual(_arquivos(dir_saida / "train"),
                         ["AAA1111_00001_lr001.png", "AAA1111_00001_lr001_sint.png"])


# CONSISTENCIA PASTA-INDICE ----------------------------------------------

class TestConsistenciaPastaIndiceLRLPR(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    # arquivos copiados == entradas no indice
    def test_toda_imagem_tem_entrada_e_vice_versa(self):
        d = self.tmp_path / "split"
        d.mkdir()
        _create_fake_image(d, "AAA1111_00001_lr001.png")
        _create_fake_image(d, "BBB2222_00002_lr001.png")

        names = [f.name for f in list_images(d)]
        index_path = self.tmp_path / "split.txt"
        generate_index(names, index_path)

        arquivos_na_pasta = {f.name for f in list_images(d)}
        arquivos_no_indice = {name for name, _ in _read_index(index_path)}
        self.assertEqual(len(arquivos_no_indice), 2)
        self.assertEqual(arquivos_na_pasta, arquivos_no_indice)


# CONTAGEM DE SINTETICAS -------------------------------------------------
# rodam o main() real, que e quem escolhe as sinteticas

class TestContagemSinteticasLRLPR(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _rodar(self, n_reais: int, n_sint: int, proporcao: float, seed: int = 42):
        dir_lrlpr = _setup_dir_lrlpr(
            self.tmp_path,
            train_plates=[f"R{i:02d}" for i in range(1, n_reais + 1)],
            val_plates=["VAL01"])
        dir_sint = _setup_dir_sinteticas(
            self.tmp_path, [f"S{i:02d}" for i in range(1, n_sint + 1)])
        return _rodar_main(self.tmp_path, [
            "--dir_lrlpr", str(dir_lrlpr), "--dir_sinteticas", str(dir_sint),
            "--proporcao", str(proporcao), "--seed", str(seed)], "saida")

    # proporcao 0.5 com 4 reais = 2 sinteticas, distintas e vindas da pasta
    def test_proporcao_05(self):
        dir_saida, log = self._rodar(n_reais=4, n_sint=10, proporcao=0.5)
        sint = _sint_do_train(dir_saida)
        self.assertEqual(len(sint), 2)
        self.assertEqual(len(set(sint)), 2)
        self.assertEqual(len(_arquivos(dir_saida / "train")), 6)
        self.assertTrue(all(n.split("_")[0] in {f"S{i:02d}" for i in range(1, 11)} for n in sint))
        self.assertNotIn("AVISO", log)

    # mais sinteticas solicitadas do que disponiveis usa todas e avisa
    def test_proporcao_maior_que_disponivel_usa_todas(self):
        dir_saida, log = self._rodar(n_reais=10, n_sint=2, proporcao=1.0)
        self.assertEqual(len(_sint_do_train(dir_saida)), 2)
        self.assertIn("AVISO", log)
        self.assertIn("so ha 2 disponiveis", log)

    # proporcao 0.0 nao inclui sinteticas e mantem todas as reais
    def test_proporcao_zero_sem_sinteticas(self):
        dir_lrlpr = _setup_dir_lrlpr(
            self.tmp_path,
            train_plates=["AAA1111", "BBB2222"],
            val_plates=["CCC3333"],
        )
        dir_sint = _setup_dir_sinteticas(self.tmp_path, ["AAA1111", "BBB2222"])
        dir_saida, _ = _rodar_main(self.tmp_path, [
            "--dir_lrlpr", str(dir_lrlpr), "--dir_sinteticas", str(dir_sint),
            "--proporcao", "0.0"], "saida")

        self.assertEqual(_arquivos(dir_saida / "train"),
                         ["AAA1111_00001_lr001.png", "BBB2222_00001_lr001.png"])
        for name, _ in _read_index(dir_saida / "train.txt"):
            self.assertNotIn("_sint", name)


# REPRODUTIBILIDADE ------------------------------------------------------

class TestReprodutibilidadeLRLPR(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _sinteticas_escolhidas(self, seed: int, nome: str) -> list[str]:
        base = self.tmp_path / nome
        base.mkdir()
        dir_lrlpr = _setup_dir_lrlpr(
            base, train_plates=[f"R{i:02d}" for i in range(10)], val_plates=["VAL01"])
        dir_sint = _setup_dir_sinteticas(base, [f"P{i:03d}" for i in range(20)])
        dir_saida, _ = _rodar_main(base, [
            "--dir_lrlpr", str(dir_lrlpr), "--dir_sinteticas", str(dir_sint),
            "--proporcao", "0.5", "--seed", str(seed)], "saida")
        return _sint_do_train(dir_saida)

    # mesma seed produz mesma amostra; seed diferente produz outra
    def test_mesma_seed_mesma_amostra(self):
        amostra_1 = self._sinteticas_escolhidas(42, "a")
        amostra_2 = self._sinteticas_escolhidas(42, "b")
        amostra_3 = self._sinteticas_escolhidas(99, "c")
        self.assertEqual(len(amostra_1), 5)
        self.assertEqual(amostra_1, amostra_2)
        self.assertNotEqual(amostra_1, amostra_3)


if __name__ == "__main__":
    unittest.main()
