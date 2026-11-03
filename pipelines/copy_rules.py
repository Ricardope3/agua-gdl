"""Copy rules shared by pipelines/promesas.py and scripts/lint_copy.py."""
import re
import unicodedata

# Wording that claims intent; allowed only inside a quote. Matched against plain() text.
BANNED = re.compile(r"\b(miente|mienten|mintio|mintieron|mintiendo|mentira|mentiras|engana|enganan|enganando|engano|enganaron|traiciono|traicionaron)\b")


def plain(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().casefold()
