import unittest
from unittest import mock

import zapopan_reportes as zr


class SeparaTest(unittest.TestCase):
    def test_spellings_of_one_word_match(self):
        self.assertEqual(zr.separa("RESINDENCIAL VIRREYES"), zr.separa("RESIDENCIAL VIRREYES"))
        self.assertEqual(zr.separa("REIDENCIAL GUADALUPE 2DA SECCION"), zr.separa("RESIDENCIAL GUADALUPE SEGUNDA SECC"))
        self.assertEqual(zr.separa("EL FORTIN II"), ["2"])
        self.assertEqual(zr.separa("HACIENDA DE SAN ANTONIO DEL VALLE ETAPA I"), ["1", "ETAPA"])

    def test_names_from_the_list_are_caught(self):
        self.assertEqual(zr.separa("JARD UNIVERSIDAD SEC 6"), ["6", "SECCION"])
        self.assertEqual(zr.separa("GUADALUPE INN CONDOMINIO UNO"), ["1", "CONDOMINIO"])
        self.assertEqual(zr.separa("JARDINES CHAPALITA RES"), ["RESIDENCIAL"])
        self.assertEqual(zr.separa("MIRADOR PTE"), ["PONIENTE"])

    def test_plain_names_have_none(self):
        self.assertEqual(zr.separa("HACIENDA DEL TEPEYAC"), [])
        self.assertEqual(zr.separa("VALLARTA LA PATRIA"), [])

    def test_every_alias_keeps_its_words(self):
        for k, v in zr.ALIAS.items():
            self.assertEqual(zr.separa(k), zr.separa(v), f"{k} -> {v}")


class PlantedJoinTest(unittest.TestCase):
    """Joins from the 18 Nov review that must stay out: build() exits on each."""

    def test_planted_joins_fail(self):
        for k, v in [("RESIDENCIAL LA ESTANCIA", "LA ESTANCIA"), ("RESINDENCIAL VIRREYES", "VIRREYES"),
                     ("GUADALUPE INN CONDOMINIO UNO", "GUADALUPE INN"), ("LOMAS DE SEMINARIO NORTE", "LOMAS DEL SEMINARIO")]:
            with self.subTest(k=k), mock.patch.dict(zr.ALIAS, {k: v}):
                with self.assertRaises(SystemExit) as e:
                    zr.build()
                self.assertIn("section, number or «residencial»", str(e.exception))


if __name__ == "__main__":
    unittest.main()
