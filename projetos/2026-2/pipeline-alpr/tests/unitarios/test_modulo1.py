# testes unitarios do modulo 1 — modulo1.py
# todos rodam sem modelos YOLO (pesos nao necessarios)
#
# executar:
#   python3 -m unittest tests/unitarios/test_modulo1.py -v

import math
import sys
import tempfile
import types
import unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "modulo1"))
from modulo1 import (
    MIN_QUAD_AREA,
    TARGET_H,
    TARGET_W,
    crop_bbox_and_pad,
    crop_with_margin,
    detect_corners,
    parse_annotation,
    rectify_and_resize,
    validate_quadrilateral,
)


# PARSE_ANNOTATION -------------------------------------------------------

class TestParseAnnotation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    # arquivo completo retorna plate e corners
    def test_plate_e_corners_retorna_ambos(self):
        txt = self.tmp_path / "img.txt"
        txt.write_text("plate: ABC1234\ncorners: 10,20 30,20 30,40 10,40\n")
        corners, plate = parse_annotation(txt)
        self.assertEqual(plate, "ABC1234")
        self.assertEqual(corners, [(10.0, 20.0), (30.0, 20.0), (30.0, 40.0), (10.0, 40.0)])

    # plate sem corners retorna corners = None
    def test_so_plate_corners_none(self):
        txt = self.tmp_path / "img.txt"
        txt.write_text("plate: XYZ9999\ntype: car\nlayout: Brazilian\n")
        corners, plate = parse_annotation(txt)
        self.assertEqual(plate, "XYZ9999")
        self.assertIsNone(corners)

    # arquivo inexistente retorna (None, None)
    def test_arquivo_inexistente_retorna_none(self):
        corners, plate = parse_annotation(self.tmp_path / "nao_existe.txt")
        self.assertIsNone(corners)
        self.assertIsNone(plate)

    # corners invalido retorna None, plate preservado
    def test_corners_mal_formatado_nao_quebra(self):
        txt = self.tmp_path / "img.txt"
        txt.write_text("plate: ABC1234\ncorners: isso nao e valido\n")
        corners, plate = parse_annotation(txt)
        self.assertEqual(plate, "ABC1234")
        self.assertIsNone(corners)

    # campos extras nao interferem
    def test_campos_extras_sao_ignorados(self):
        txt = self.tmp_path / "img.txt"
        txt.write_text("type: car\nplate: ODE2510\nlayout: Brazilian\ncorners: 1,2 3,2 3,4 1,4\n")
        corners, plate = parse_annotation(txt)
        self.assertEqual(plate, "ODE2510")
        self.assertEqual(len(corners), 4)


# CROP_WITH_MARGIN -------------------------------------------------------

class TestCropWithMargin(unittest.TestCase):

    # bbox no canto superior esquerdo com margem alta nao gera coord negativa
    def test_coordenadas_nunca_negativas(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        bbox = np.array([0.0, 0.0, 20.0, 20.0])
        crop, x_off, y_off = crop_with_margin(img, bbox, margin=0.5)
        self.assertGreaterEqual(x_off, 0)
        self.assertGreaterEqual(y_off, 0)
        # margem de 10 px vai para fora da imagem e e cortada: sobra 30x30 a partir de (0, 0)
        self.assertEqual((x_off, y_off), (0, 0))
        self.assertEqual(crop.shape[:2], (30, 30))

    # bbox no canto inferior direito nao ultrapassa limites
    def test_coordenadas_nao_excedem_limites(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        bbox = np.array([80.0, 80.0, 100.0, 100.0])
        crop, x_off, y_off = crop_with_margin(img, bbox, margin=0.5)
        h, w = img.shape[:2]
        self.assertLessEqual(x_off + crop.shape[1], w)
        self.assertLessEqual(y_off + crop.shape[0], h)
        # margem de 10 px a esquerda/acima; a direita/abaixo e cortada na borda
        self.assertEqual((x_off, y_off), (70, 70))
        self.assertEqual(crop.shape[:2], (30, 30))

    # placa proxima a borda com margem fica clampada
    def test_bbox_proxima_a_borda_nao_extrapola(self):
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        bbox = np.array([190.0, 5.0, 200.0, 50.0])
        crop, x_off, y_off = crop_with_margin(img, bbox, margin=0.2)
        h, w = img.shape[:2]
        self.assertGreaterEqual(x_off, 0)
        self.assertGreaterEqual(y_off, 0)
        self.assertLessEqual(x_off + crop.shape[1], w)
        self.assertLessEqual(y_off + crop.shape[0], h)
        # esquerda ganha 2 px de margem, topo e cortado em 0, direita para na borda
        self.assertEqual((x_off, y_off), (188, 0))
        self.assertEqual(crop.shape[:2], (59, 12))

    # margem zero preserva a bbox exata; margem positiva aumenta o recorte
    def test_margem_zero_preserva_bbox(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        bbox = np.array([10.0, 20.0, 50.0, 60.0])
        crop, x_off, y_off = crop_with_margin(img, bbox, margin=0.0)
        self.assertEqual(x_off, 10)
        self.assertEqual(y_off, 20)
        self.assertEqual(crop.shape[1], 40)
        self.assertEqual(crop.shape[0], 40)

        # margem de 50% de uma bbox 40x40 acrescenta 20 px de cada lado; esquerda e topo
        # passariam de 0 e sao cortados
        crop, x_off, y_off = crop_with_margin(img, bbox, margin=0.5)
        self.assertEqual((x_off, y_off), (0, 0))
        self.assertEqual(crop.shape[:2], (80, 70))

    # imagem 1x1 nao quebra
    def test_imagem_1x1_nao_quebra(self):
        img = np.zeros((1, 1, 3), dtype=np.uint8)
        bbox = np.array([0.0, 0.0, 1.0, 1.0])
        crop, x_off, y_off = crop_with_margin(img, bbox, margin=0.5)
        self.assertEqual(crop.shape, (1, 1, 3))
        self.assertEqual((x_off, y_off), (0, 0))

    # bbox com largura zero (x1 == x2) nao quebra
    def test_bbox_dimensao_zero_nao_quebra(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        bbox = np.array([50.0, 20.0, 50.0, 60.0])
        crop, x_off, y_off = crop_with_margin(img, bbox, margin=0.15)
        # sem largura: o recorte fica com largura 0 (sem erro); a altura ganha 6 px de margem em cada lado
        self.assertEqual(crop.shape[1], 0)
        self.assertEqual((x_off, y_off), (50, 14))
        self.assertEqual(crop.shape[0], 52)


# VALIDATE_QUADRILATERAL -------------------------------------------------

class TestValidateQuadrilateral(unittest.TestCase):

    # quadrilatero valido retorna true
    def test_quadrilatero_normal_retorna_true(self):
        corners = [(10.0, 10.0), (50.0, 10.0), (50.0, 30.0), (10.0, 30.0)]
        self.assertTrue(validate_quadrilateral(corners))

    # 4 pontos colineares retorna false
    def test_pontos_colineares_retorna_false(self):
        corners = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0)]
        self.assertFalse(validate_quadrilateral(corners))

    # area == MIN_QUAD_AREA rejeitada (condicao estritamente maior)
    def test_area_exatamente_no_limiar_retorna_false(self):
        lado = math.sqrt(MIN_QUAD_AREA)
        corners = [(0.0, 0.0), (lado, 0.0), (lado, lado), (0.0, lado)]
        self.assertFalse(validate_quadrilateral(corners))


# RECTIFY_AND_RESIZE -----------------------------------------------------

class TestRectifyAndResize(unittest.TestCase):

    # saida sempre TARGET_W x TARGET_H
    def test_saida_tem_dimensoes_alvo(self):
        img = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        corners = [(10.0, 10.0), (100.0, 10.0), (100.0, 80.0), (10.0, 80.0)]
        result = rectify_and_resize(img, corners, TARGET_W, TARGET_H)
        self.assertEqual(result.shape[1], TARGET_W)
        self.assertEqual(result.shape[0], TARGET_H)

    # so o que esta dentro do quadrilatero entra na saida: o entorno preto fica de fora
    def test_conteudo_so_do_interior_do_quadrilatero(self):
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        img[20:181, 20:181] = 200
        corners = [(20.0, 20.0), (180.0, 20.0), (180.0, 180.0), (20.0, 180.0)]
        result = rectify_and_resize(img, corners, TARGET_W, TARGET_H)
        self.assertEqual(result.dtype, np.uint8)
        self.assertGreater((result >= 190).mean(), 0.98)

    # imagem com conteudo nao gera saida toda preta
    def test_integridade_saida_nao_e_toda_preta(self):
        img = np.full((200, 200, 3), 128, dtype=np.uint8)
        corners = [(20.0, 20.0), (180.0, 20.0), (180.0, 180.0), (20.0, 180.0)]
        result = rectify_and_resize(img, corners, TARGET_W, TARGET_H)
        self.assertGreater(result.max(), 0)
        # imagem uniforme tem que sair uniforme, sem bordas pretas nem artefatos
        self.assertTrue((result == 128).all())

    # cada canto da entrada mapeia pro canto correspondente da saida
    def test_conteudo_mapeia_para_posicao_correta(self):
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        img[20:50, 20:50]     = [0, 0, 255]      # TL vermelho
        img[20:50, 150:180]   = [0, 255, 0]      # TR verde
        img[150:180, 150:180] = [255, 0, 0]      # BR azul
        img[150:180, 20:50]   = [0, 255, 255]    # BL amarelo

        corners = [(20.0, 20.0), (180.0, 20.0), (180.0, 180.0), (20.0, 180.0)]
        result = rectify_and_resize(img, corners, TARGET_W, TARGET_H)

        self.assertGreater(int(result[2, 2, 2]), 200)                    # TL vermelho
        self.assertGreater(int(result[2, TARGET_W - 3, 1]), 200)         # TR verde
        self.assertGreater(int(result[TARGET_H - 3, TARGET_W - 3, 0]), 200)  # BR azul
        self.assertGreater(int(result[TARGET_H - 3, 2, 1]), 200)         # BL amarelo
        self.assertGreater(int(result[TARGET_H - 3, 2, 2]), 200)

    # trocar TL<->BR produz saida diferente
    def test_ordem_dos_cantos_altera_saida(self):
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        img[20:60, 20:60] = 255

        corners_correto = [(20.0, 20.0), (180.0, 20.0), (180.0, 180.0), (20.0, 180.0)]
        corners_trocado = [(180.0, 180.0), (20.0, 180.0), (20.0, 20.0), (180.0, 20.0)]

        r1 = rectify_and_resize(img, corners_correto, TARGET_W, TARGET_H)
        r2 = rectify_and_resize(img, corners_trocado, TARGET_W, TARGET_H)

        self.assertFalse(np.array_equal(r1, r2))

    # trapezio branco retificado preenche >85% da saida
    def test_trapezio_e_retificado(self):
        img = np.zeros((200, 300, 3), dtype=np.uint8)
        trap = np.array([[60, 30], [240, 30], [280, 170], [20, 170]], dtype=np.int32)
        cv2.fillPoly(img, [trap], (255, 255, 255))

        corners = [(60.0, 30.0), (240.0, 30.0), (280.0, 170.0), (20.0, 170.0)]
        result = rectify_and_resize(img, corners, TARGET_W, TARGET_H)

        pixels_brancos = (result > 200).all(axis=2).sum()
        total = TARGET_W * TARGET_H
        self.assertGreater(pixels_brancos / total, 0.85)


# CROP_BBOX_AND_PAD ------------------------------------------------------

class TestCropBboxAndPad(unittest.TestCase):

    # saida sempre TARGET_W x TARGET_H
    def test_saida_tem_dimensoes_alvo(self):
        img = np.random.randint(0, 255, (300, 400, 3), dtype=np.uint8)
        corners = [(50.0, 40.0), (350.0, 40.0), (350.0, 250.0), (50.0, 250.0)]
        result = crop_bbox_and_pad(img, corners, TARGET_W, TARGET_H)
        self.assertIsNotNone(result)
        self.assertEqual(result.shape, (TARGET_H, TARGET_W, 3))

    # padding e cinza (128,128,128), nao preto
    def test_padding_e_cinza(self):
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        img[80:120, 90:110] = 255
        corners = [(90.0, 80.0), (110.0, 80.0), (110.0, 120.0), (90.0, 120.0)]
        result = crop_bbox_and_pad(img, corners, TARGET_W, TARGET_H)
        self.assertIsNotNone(result)
        np.testing.assert_array_equal(result[0, 0], [128, 128, 128])
        np.testing.assert_array_equal(result[0, TARGET_W - 1], [128, 128, 128])

    # conteudo fica centralizado na saida
    def test_conteudo_fica_centralizado(self):
        img = np.full((200, 200, 3), 200, dtype=np.uint8)
        corners = [(60.0, 60.0), (140.0, 60.0), (140.0, 140.0), (60.0, 140.0)]
        result = crop_bbox_and_pad(img, corners, TARGET_W, TARGET_H)
        self.assertIsNotNone(result)
        centro_y, centro_x = TARGET_H // 2, TARGET_W // 2
        self.assertGreater(int(result[centro_y, centro_x].max()), 128)

    # entrada larga nao estica verticalmente
    def test_proporcao_preservada(self):
        img = np.full((100, 400, 3), 200, dtype=np.uint8)
        corners = [(10.0, 10.0), (390.0, 10.0), (390.0, 90.0), (10.0, 90.0)]
        result = crop_bbox_and_pad(img, corners, TARGET_W, TARGET_H)
        self.assertIsNotNone(result)
        self.assertEqual(tuple(result[0, TARGET_W // 2]), (128, 128, 128))
        self.assertEqual(tuple(result[-1, TARGET_W // 2]), (128, 128, 128))
        # entrada 4:1 numa saida 2:1: ocupa a largura toda e so ~31 das 64 linhas (esticada ocuparia 64)
        linhas_conteudo = (result[:, TARGET_W // 2] != 128).any(axis=1).sum()
        self.assertTrue(30 <= linhas_conteudo <= 32)
        self.assertEqual(tuple(result[TARGET_H // 2, 0]), (200, 200, 200))

    # corners na borda da imagem nao extrapola
    def test_corners_na_borda_nao_extrapola(self):
        img = np.full((100, 100, 3), 200, dtype=np.uint8)
        corners = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
        result = crop_bbox_and_pad(img, corners, TARGET_W, TARGET_H)
        self.assertIsNotNone(result)
        self.assertEqual(result.shape, (TARGET_H, TARGET_W, 3))

    # bbox com area zero retorna None
    def test_regiao_degenerada_retorna_none(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        corners = [(50.0, 50.0), (50.0, 50.0), (50.0, 50.0), (50.0, 50.0)]
        result = crop_bbox_and_pad(img, corners, TARGET_W, TARGET_H)
        self.assertIsNone(result)


# DETECT_CORNERS ---------------------------------------------------------

# modelo de pose falso: devolve keypoints fixos, sem precisar dos pesos YOLO
class _Tensor:
    def __init__(self, arr):
        self._arr = np.array(arr, dtype=np.float32)

    def cpu(self):
        return self

    def numpy(self):
        return self._arr


class _ModeloPoseFalso:
    def __init__(self, keypoints):
        self._keypoints = keypoints

    def __call__(self, crop, conf, verbose=False):
        kp = self._keypoints
        keypoints = None if kp is None else _Keypoints([_Tensor(k) for k in kp])
        return [types.SimpleNamespace(keypoints=keypoints)]


class _Keypoints:
    def __init__(self, xy):
        self.xy = xy

    def __len__(self):
        return len(self.xy)


class TestDetectCorners(unittest.TestCase):
    crop = np.zeros((64, 128, 3), dtype=np.uint8)

    # devolve os 4 cantos na ordem TL, TR, BR, BL e o quadrilatero e valido
    def test_devolve_quatro_cantos_na_ordem(self):
        kpts = [[[10, 8], [118, 6], [120, 58], [8, 60]]]
        corners = detect_corners(_ModeloPoseFalso(kpts), self.crop, conf=0.5)
        self.assertEqual(len(corners), 4)
        esperado = [(10.0, 8.0), (118.0, 6.0), (120.0, 58.0), (8.0, 60.0)]
        for obtido, certo in zip(corners, esperado):
            self.assertEqual((float(obtido[0]), float(obtido[1])), certo)
        self.assertTrue(validate_quadrilateral(corners))

    # sem deteccao (nenhum keypoint ou menos de 4) retorna None
    def test_sem_keypoints_retorna_none(self):
        self.assertIsNone(detect_corners(_ModeloPoseFalso(None), self.crop, conf=0.5))
        self.assertIsNone(detect_corners(_ModeloPoseFalso([]), self.crop, conf=0.5))
        tres = [[[10, 8], [118, 6], [120, 58]]]
        self.assertIsNone(detect_corners(_ModeloPoseFalso(tres), self.crop, conf=0.5))


if __name__ == "__main__":
    unittest.main(verbosity=2)
