import unittest

from copy_rules import KNOWN_ERRORS, known_errors


class KnownErrors(unittest.TestCase):
    def test_examples(self):
        for e in KNOWN_ERRORS:
            with self.subTest(e["id"]):
                self.assertIn(e, [k for k, _ in known_errors(e["bad"])], "misses its bad example")
                self.assertNotIn(e, [k for k, _ in known_errors(e["good"])], "flags its good example")

    def test_promise_date_noun_and_registry_discussion(self):
        rule = next(e for e in KNOWN_ERRORS if e["id"] == "bot-promise-date")
        date = "14 de " + "octubre"
        for text in (
            f"La promesa del {date} fue «por máximo un día».",
            f"Registro de correcciones: la promesa del {date} era incorrecta.",
        ):
            with self.subTest(text=text):
                self.assertIn(rule, [e for e, _ in known_errors(text)])

    def test_sin_cortes_totales_only_flags_a_misquote(self):
        rule = next(e for e in KNOWN_ERRORS if e["id"] == "sin-cortes-totales")
        self.assertNotIn(rule, [e for e, _ in known_errors("El programa tendría racionamientos sin cortes totales.")])
        self.assertIn(rule, [e for e, _ in known_errors("El programa tendría «sin cortes " + "totales».")])

    def test_siapa_table_nondelivery_variants(self):
        rule = next(e for e in KNOWN_ERRORS if e["id"] == "siapa-numeros-no-entregados")
        for text in (
            "El SIAPA no ha entregado los " + "números.",
            "Su tabla no se ha " + "entregado.",
            "La tabla de valores: No " + "entregada.",
        ):
            with self.subTest(text=text):
                self.assertIn(rule, [e for e, _ in known_errors(text)])
        self.assertNotIn(rule, [e for e, _ in known_errors("El oficio no incluye la tabla de valores.")])


if __name__ == "__main__":
    unittest.main()
