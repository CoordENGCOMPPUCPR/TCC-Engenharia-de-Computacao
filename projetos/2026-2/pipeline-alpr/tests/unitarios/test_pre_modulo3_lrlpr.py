# testes unitarios do pre_modulo3_LRLPR.py
# preparacao do LRLPR-26: leitura de tracks, geracao de nomes e indices
#
# executar:
#   python3 -m unittest tests/unitarios/test_pre_modulo3_lrlpr.py -v

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "modulo3"))
from pre_modulo3_LRLPR import generate_index, process_tracks


def _create_track(base_dir: Path, rel_path: str, plate_text: str,
                  img_names: list[str]) -> Path:
    track_dir = base_dir / rel_path.rstrip("/")
    track_dir.mkdir(parents=True, exist_ok=True)

    ann = {"plate_text": plate_text, "plate_layout": "Brazilian"}
    (track_dir / "annotations.json").write_text(json.dumps(ann))

    for name in img_names:
        (track_dir / name).touch()

    return track_dir


def _read_index(path: Path) -> list[tuple[str, str]]:
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                name, plate = line.split(",", 1)
                entries.append((name, plate))
    return entries


# PROCESS_TRACKS ---------------------------------------------------------

class TestProcessTracks(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.train_dir = self.tmp_path / "train"
        self.train_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    # nome de saida contem placa, track id e tag
    def test_nome_gerado_contem_placa_track_e_tag(self):
        _create_track(
            self.train_dir,
            "Scenario-A/Brazilian/track_00001",
            "ABC1234",
            ["lr-001.png", "lr-002.png"],
        )
        dest = self.tmp_path / "dest"
        names = process_tracks(
            ["Scenario-A/Brazilian/track_00001"], self.train_dir, dest)

        self.assertEqual(len(names), 2)
        self.assertIn("ABC1234_00001_lr001.png", names)
        self.assertIn("ABC1234_00001_lr002.png", names)

    # hifen removido do tag: lr-001 -> lr001
    def test_hifen_removido_do_tag(self):
        _create_track(
            self.train_dir,
            "Scenario-A/Mercosur/track_00010",
            "MER1C23",
            ["hr-003.jpg"],
        )
        dest = self.tmp_path / "dest"
        names = process_tracks(
            ["Scenario-A/Mercosur/track_00010"], self.train_dir, dest)

        self.assertEqual(len(names), 1)
        self.assertIn("MER1C23_00010_hr003.jpg", names)

    # track inexistente e ignorado sem erro
    def test_track_inexistente_e_pulado(self):
        dest = self.tmp_path / "dest"
        names = process_tracks(
            ["Scenario-A/Brazilian/track_99999"], self.train_dir, dest)

        self.assertEqual(names, [])

    # track sem annotations.json e ignorado
    def test_track_sem_annotations_e_pulado(self):
        track_dir = self.train_dir / "Scenario-A/Brazilian/track_00002"
        track_dir.mkdir(parents=True)
        (track_dir / "lr-001.png").touch()

        dest = self.tmp_path / "dest"
        names = process_tracks(
            ["Scenario-A/Brazilian/track_00002"], self.train_dir, dest)

        self.assertEqual(names, [])

    # track com plate_text vazio e ignorado
    def test_track_sem_plate_text_e_pulado(self):
        track_dir = self.train_dir / "Scenario-A/Brazilian/track_00003"
        track_dir.mkdir(parents=True)
        ann = {"plate_text": "", "plate_layout": "Brazilian"}
        (track_dir / "annotations.json").write_text(json.dumps(ann))
        (track_dir / "lr-001.png").touch()

        dest = self.tmp_path / "dest"
        names = process_tracks(
            ["Scenario-A/Brazilian/track_00003"], self.train_dir, dest)

        self.assertEqual(names, [])

    # annotations.json e outros nao-imagem nao aparecem na saida
    def test_ignora_arquivos_nao_imagem(self):
        _create_track(
            self.train_dir,
            "Scenario-A/Brazilian/track_00004",
            "XYZ9876",
            ["lr-001.png"],
        )
        dest = self.tmp_path / "dest"
        names = process_tracks(
            ["Scenario-A/Brazilian/track_00004"], self.train_dir, dest)

        # so a imagem sai, e nada alem dela chega ao destino
        self.assertEqual(names, ["XYZ9876_00004_lr001.png"])
        self.assertEqual(sorted(f.name for f in dest.iterdir()), names)

    # arquivos fisicos existem no destino apos copia
    def test_imagens_sao_copiadas_para_destino(self):
        _create_track(
            self.train_dir,
            "Scenario-A/Brazilian/track_00005",
            "DEF5678",
            ["lr-001.png", "hr-001.png"],
        )
        dest = self.tmp_path / "dest"
        names = process_tracks(
            ["Scenario-A/Brazilian/track_00005"], self.train_dir, dest)

        self.assertEqual(sorted(names), ["DEF5678_00005_hr001.png", "DEF5678_00005_lr001.png"])
        self.assertEqual(sorted(f.name for f in dest.iterdir()), sorted(names))


# GENERATE_INDEX ---------------------------------------------------------

class TestGenerateIndexLRLPR(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    # placa extraida corretamente do formato LRLPR
    def test_placa_extraida_corretamente_do_formato_lrlpr(self):
        names = ["ABC1234_00001_lr001.png", "XYZ9876_00002_hr003.jpg"]
        index_path = self.tmp_path / "index.txt"
        generate_index(names, index_path)

        entries = _read_index(index_path)
        placas = {plate for _, plate in entries}
        self.assertEqual(placas, {"ABC1234", "XYZ9876"})

    # cada nome gera uma linha no indice
    def test_todas_entradas_presentes_no_indice(self):
        names = [f"P{i:03d}_00001_lr001.png" for i in range(5)]
        index_path = self.tmp_path / "index.txt"
        generate_index(names, index_path)

        entries = _read_index(index_path)
        self.assertEqual(len(entries), 5)

    # placa mercosul extraida corretamente
    def test_placa_mercosul_extraida_corretamente(self):
        names = ["MER1C23_00010_hr003.jpg"]
        index_path = self.tmp_path / "index.txt"
        generate_index(names, index_path)

        entries = _read_index(index_path)
        self.assertEqual(entries[0][1], "MER1C23")


# INTEGRIDADE DO SPLIT ---------------------------------------------------

class TestSplitIntegridade(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.train_dir = self.tmp_path / "train"
        self.train_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    # placas de train e val sao disjuntas
    def test_placas_train_e_val_sao_disjuntas(self):
        _create_track(
            self.train_dir, "Scenario-A/Brazilian/track_00001",
            "AAA1111", ["lr-001.png"])
        _create_track(
            self.train_dir, "Scenario-A/Brazilian/track_00002",
            "BBB2222", ["lr-001.png"])
        _create_track(
            self.train_dir, "Scenario-A/Brazilian/track_00003",
            "CCC3333", ["lr-001.png"])

        dest_train = self.tmp_path / "saida" / "train"
        dest_val = self.tmp_path / "saida" / "val"

        train_names = process_tracks(
            ["Scenario-A/Brazilian/track_00001",
             "Scenario-A/Brazilian/track_00002"],
            self.train_dir, dest_train)
        val_names = process_tracks(
            ["Scenario-A/Brazilian/track_00003"],
            self.train_dir, dest_val)

        saida = self.tmp_path / "saida"
        generate_index(train_names, saida / "train.txt")
        generate_index(val_names, saida / "val.txt")

        placas_train = {p for _, p in _read_index(saida / "train.txt")}
        placas_val = {p for _, p in _read_index(saida / "val.txt")}

        # cada split tem exatamente as placas dos seus tracks (evita passar com indice vazio)
        self.assertEqual(placas_train, {"AAA1111", "BBB2222"})
        self.assertEqual(placas_val, {"CCC3333"})
        self.assertEqual(placas_train & placas_val, set())
        self.assertEqual(len(list(dest_train.iterdir())), 2)
        self.assertEqual(len(list(dest_val.iterdir())), 1)

    # tracks de cenarios diferentes consolidados no mesmo split
    def test_multiplos_cenarios_consolidados(self):
        _create_track(
            self.train_dir, "Scenario-A/Brazilian/track_00001",
            "AAA1111", ["lr-001.png"])
        _create_track(
            self.train_dir, "Scenario-A/Mercosur/track_00002",
            "MER1C23", ["lr-001.png"])

        dest = self.tmp_path / "dest"
        names = process_tracks(
            ["Scenario-A/Brazilian/track_00001",
             "Scenario-A/Mercosur/track_00002"],
            self.train_dir, dest)

        placas = {n.split("_", 1)[0] for n in names}
        self.assertEqual(placas, {"AAA1111", "MER1C23"})


if __name__ == "__main__":
    unittest.main()
