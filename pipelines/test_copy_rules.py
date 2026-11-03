import unittest

from copy_rules import KNOWN_ERRORS, known_errors


class KnownErrors(unittest.TestCase):
    def test_examples(self):
        for e in KNOWN_ERRORS:
            with self.subTest(e["id"]):
                self.assertIn(e, [k for k, _ in known_errors(e["bad"])], "misses its bad example")
                self.assertNotIn(e, [k for k, _ in known_errors(e["good"])], "flags its good example")


if __name__ == "__main__":
    unittest.main()
