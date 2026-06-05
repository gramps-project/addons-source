# -*- coding: utf-8 -*-
"""
Provides morphological generation of East Slavic patronymics (Russian, Ukrainian,
Belarusian) based on the father's given name, gender, reference year, and
orthographic script preferences.
"""

import re
from typing import TYPE_CHECKING

from name_processor.models.constants import LOCALE_RU, REFORM_YEAR

if TYPE_CHECKING:
    from name_processor.models.audit import RuleContext

# Sibilant characters that trigger -evich/-evna instead of -ovich/-ovna
SIBILANTS = set("жшчщцЖШЧЩЦ")

# Hard consonants for pre-reform terminal hard sign 'ъ' mapping
HARD_CONSONANTS = set("бвгджзклмнпрстфхцчшщБВГДЖЗКЛМНПРСТФХЦЧШЩ")

# Cyrillic vowels for pre-reform decimal 'і' replacement rules
CYRILLIC_VOWELS = set("аеиоуыэюяѣАЕИОУЫЭЮЯѢіІйЙ")

# Epoch constants for chronological period classification
EPOCH_PRE_REFORM = "pre_reform"
EPOCH_POST_REFORM = "post_reform"

# Slavic surname regex markers (Cyrillic and Latin transliterated)
SLAVIC_SURNAME_PATTERN = re.compile(
    r"(ов|ев|ин|ын|енко|чук|ко|ова|ева|ина|ына|ский|ская|цкий|цкая|ov|ova|ev|eva|in|ina|yn|yna|enko|chuk|sky|skiy|skaya)$",
    re.IGNORECASE,
)


class MorphologyService:
    @classmethod
    def apply_pre_reform_orthography(cls, text: str) -> str:
        """
        Applies historical pre-reform orthography rules to Cyrillic text:
        1. Replaces 'и' with 'і' if immediately followed by another vowel (e.g., Дмитріевичъ).
        2. Appends terminal hard sign 'ъ' to any word ending in a hard consonant (e.g., сынъ, Петровъ).
        """
        if not text:
            return text

        chars = list(text)
        # 1. Replace 'и' with 'і' before vowels
        for i in range(len(chars) - 1):
            if chars[i].lower() == "и" and chars[i + 1].lower() in CYRILLIC_VOWELS:
                chars[i] = "І" if chars[i].isupper() else "і"

        text = "".join(chars)

        # 2. Append terminal hard sign 'ъ' to words ending in hard consonants
        words = text.split(" ")
        reformed_words = []
        for word in words:
            if word and word[-1] in HARD_CONSONANTS:
                word = word + "ъ"
            reformed_words.append(word)

        return " ".join(reformed_words)

    @classmethod
    def normalize_to_modern(cls, text: str) -> str:
        """
        Normalizes pre-reform Cyrillic text to modern characters to ensure
        consistent morphological stem parsing.
        """
        if not text:
            return text
        # Strip terminal pre-reform hard sign if present, as it is an orthographic artifact
        text = text.strip()
        while text.endswith(("ъ", "Ъ")):
            text = text[:-1].strip()

        # Replace pre-reform characters with modern equivalents
        replacements = {
            "і": "и",
            "І": "И",
            "ѣ": "е",
            "Ѣ": "Е",
            "ѳ": "ф",
            "Ѳ": "Ф",
            "ѵ": "и",
            "Ѵ": "И",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    @classmethod
    def parse_stem(cls, father_name: str) -> tuple[str, str, str]:
        """
        Analyzes the father's given name ending to classify the linguistic stem.

        Returns a tuple of:
            (stem_type, genitive_base, modern_formal_base)
        """
        name = father_name.strip()
        if not name:
            return ("hard", "", "")

        # Normalize pre-reform script characters for robust stem analysis
        name = cls.normalize_to_modern(name)

        # Normalize case (Title Case)
        name = name[0].upper() + name[1:].lower() if len(name) > 1 else name.upper()

        # Exact mappings for irregular historical names
        # Note: Павел, Лев, and Пётр rely on unpredictable fleeting vowels (беглые гласные),
        #       and Яков utilizes an intrusive 'л'. These are genuine morphological
        #       irregularities in Russian and should remain in the dictionary.
        irregular_names = {
            "Яков": ("hard_irregular", "Яковлев", "Яковлев"),
            "Иаков": ("hard_irregular", "Иаковлев", "Иаковлев"),
            "Павел": ("hard", "Павлов", "Павл"),
            "Лев": ("hard", "Львов", "Льв"),
            "Михаил": ("hard", "Михайлов", "Михайл"),
            "Пётр": ("hard", "Петров", "Петр"),
            "Гаврила": ("hard", "Гаврилин", "Гаврил"),
            "Данила": ("hard", "Данилин", "Данил"),
            "Михайла": ("hard", "Михайлин", "Михайл"),
            "Иона": ("hard", "Ионин", "Ион"),
            "Дмитрий": ("yod_ii", "Дмитриев", "Дмитри"),
            "Димитрий": ("yod_ii", "Димитриев", "Димитри"),
            "Онуфрий": ("yod_ii", "Онуфриев", "Онуфри"),
            "Корний": ("yod_ii", "Корниев", "Корни"),
        }

        if name in irregular_names:
            return irregular_names[name]

        # 1. Contracted soft vowel stems (e.g., Илья)
        if name.endswith("ья"):
            base = name[:-1]  # Strip "я" -> "Иль"
            return ("contracted_ya", base + "ин", base)

        # 1b. Church Slavonic names ending in -ия (e.g., Илия, Захария)
        elif name.endswith("ия"):
            base = name[:-1]  # Strip "я" -> "Или"
            return ("soft", base + "ев", base)

        # 1c. Folk/Ukrainian stems ending in -о (e.g., Михайло, Петро, Данило)
        elif name.endswith("о"):
            base = name[:-1]  # Strip "о" -> "Михайл"
            return ("hard", base + "ов", base)

        # 2. Contracted hard vowel stems (e.g., Никита, Савва, Фома, Лука)
        elif name.endswith(("а", "я")) and not name.endswith("ия"):
            base = name[:-1]  # "Никит", "Савв", "Фом"
            return ("contracted_a", base + "ин", base)

        # 3. Yod stems ending in -ий (e.g., Дмитрий, Василий, Григорий)
        elif name.endswith("ий"):
            base_stem = name[:-2]  # Strip "ий"

            # Handle soft-yod shifts historically used in records.
            # Excludes strict Church Slavonic names that maintain the 'и' (Онуфрий, Корний)
            if name.endswith(
                ("лий", "рий", "ний", "тий", "сий", "дий", "вий", "пий", "бий")
            ):
                # Василий -> Василь-, Григорий -> Григорь-
                genitive_base = base_stem + "ьев"
                formal_base = base_stem + "ь"
            else:
                # Дмитрий -> Дмитри-, Онуфрий -> Онуфри-
                genitive_base = base_stem + "иев"
                formal_base = base_stem + "и"
            return ("yod_ii", genitive_base, formal_base)

        # 4. Yod stems ending in other diphthongs (e.g., Сергей, Николай)
        elif name.endswith(("ей", "ай", "ой")):
            base = name[:-1]  # Strip "й" -> "Серге", "Никола"
            return ("yod_ej", base + "ев", base)

        # 5. Soft consonant stems (e.g., Игорь)
        elif name.endswith("ь"):
            base = name[:-1]  # Strip "ь" -> "Игор"
            return ("soft", base + "ев", base)

        # 6. Sibilant stems (e.g., Жорж, Фриц)
        elif name[-1] in SIBILANTS:
            return ("sibilant", name + "ев", name)

        # 7. Standard hard consonant stems (e.g., Иван, Михаил)
        else:
            return ("hard", name + "ов", name)

    @classmethod
    def generate_east_slavic_patronymic(
        cls,
        father_name: str,
        is_male: bool,
        year: int | None = None,
        pre_reform_script: bool = False,
    ) -> str | None:
        """
        Generates a patronymic name from the father's given name according to the
        specified epoch and orthography.

        Args:
            father_name (str): Given name of the father (e.g., "Иван", "Дмитрий").
            is_male (bool): Target's gender.
            year (int, optional): Reference year (Y_ref) calculated via resolution hierarchy.
                                Defaults to modern standard (Post-reform) if None.
            pre_reform_script (bool): If True, re-enables pre-reform Cyrillic spelling rules.

        Returns:
            str: Correctly generated patronymic, or None if generation is impossible.
        """
        if not father_name or not father_name.strip():
            return None

        # Parse stem and bases
        stem_type, genitive_base, formal_base = cls.parse_stem(father_name)

        # Determine Chronological Epoch (Pivot Windows)
        epoch = (
            EPOCH_PRE_REFORM
            if (year is not None and year < REFORM_YEAR)
            else EPOCH_POST_REFORM
        )

        # Apply Epoch Strategies
        result = ""

        # 1. Pre-reform: Direct Class-Agnostic Genitive Suffix (e.g. Иван Сергеев Коваль)
        if epoch == EPOCH_PRE_REFORM:
            result = genitive_base if is_male else genitive_base + "а"

        # 2. Post-reform: Modern Formal Gender Suffix (-ovich / -ovna)
        else:
            if stem_type == "hard_irregular":
                result = formal_base + "ич" if is_male else formal_base + "на"
            elif stem_type == "contracted_ya":
                # Илья -> Ильич / Ильинична
                result = formal_base + "ич" if is_male else formal_base + "инична"
            elif stem_type == "contracted_a":
                # Никита -> Никитич / Никитична
                # Фома -> Фомич / Фоминична
                if father_name.strip().lower() in ("фома", "лука", "кузьма"):
                    result = formal_base + "ич" if is_male else formal_base + "инична"
                else:
                    result = formal_base + "ич" if is_male else formal_base + "ична"
            elif stem_type in ("soft", "yod_ii", "yod_ej", "sibilant"):
                # Игорь -> Игоревич / Игоревна
                # Дмитрий -> Дмитриевич / Дмитриевна
                # Сергей -> Сергеевич / Сергеевна
                # Жорж -> Жоржевич / Жоржевна
                result = formal_base + "евич" if is_male else formal_base + "евна"
            else:  # hard stems (Иван)
                result = formal_base + "ович" if is_male else formal_base + "овна"

        # Apply historical orthography replacements if requested
        if pre_reform_script and epoch != EPOCH_POST_REFORM:
            result = cls.apply_pre_reform_orthography(result)

        return result

    @classmethod
    def is_pre_reform(cls, ctx: "RuleContext", use_pre_reform: bool) -> bool:
        """Check if the context satisfies the pre-reform conditions."""
        return (
            ctx.locale == LOCALE_RU
            and ctx.reference_year is not None
            and ctx.reference_year < REFORM_YEAR
            and use_pre_reform
        )

    @classmethod
    def swap_patronymic_gender(
        cls, patronymic: str, to_male: bool, pre_reform: bool = False
    ) -> str:
        """Swaps the grammatical gender of an existing patronymic suffix."""
        if not patronymic:
            return patronymic

        if to_male:
            # Female to Male
            if patronymic.endswith("инична"):
                return patronymic[:-6] + "ич"
            elif patronymic.endswith("ична"):
                return patronymic[:-4] + "ич"
            elif patronymic.endswith("овна"):
                return patronymic[:-4] + "ович"
            elif patronymic.endswith("евна"):
                return patronymic[:-4] + "евич"
            elif patronymic.endswith("ова"):
                return patronymic[:-3] + ("овъ" if pre_reform else "ов")
            elif patronymic.endswith("ева"):
                return patronymic[:-3] + ("евъ" if pre_reform else "ев")
            elif patronymic.endswith("ина"):
                return patronymic[:-3] + ("инъ" if pre_reform else "ин")
        else:
            # Male to Female
            if patronymic.endswith("ович"):
                return patronymic[:-4] + "овна"
            elif patronymic.endswith("евич"):
                return patronymic[:-4] + "евна"
            elif patronymic.endswith("ич"):
                # Check soft contracted stem (Илья -> Ильинична)
                base = patronymic[:-2]
                if base.endswith("ь") or base.lower() in ("иль", "кузьм", "фом"):
                    return base + "инична"
                return base + "ична"
            elif patronymic.endswith("овъ"):
                return patronymic[:-3] + "ова"
            elif patronymic.endswith("евъ"):
                return patronymic[:-3] + "ева"
            elif patronymic.endswith("инъ"):
                return patronymic[:-3] + "ина"
            elif patronymic.endswith("ов"):
                return patronymic[:-2] + "ова"
            elif patronymic.endswith("ев"):
                return patronymic[:-2] + "ева"
            elif patronymic.endswith("ин"):
                return patronymic[:-2] + "ина"

        return patronymic

    @classmethod
    def modern_to_archaic(
        cls, patronymic: str, is_male: bool, pre_reform: bool = False
    ) -> str:
        """Converts a modern formal patronymic to an archaic possessive genitive."""
        if not patronymic:
            return patronymic

        if is_male:
            if patronymic.endswith("ович"):
                return patronymic[:-4] + ("овъ" if pre_reform else "ов")
            elif patronymic.endswith("евич"):
                return patronymic[:-4] + ("евъ" if pre_reform else "ев")
            elif patronymic.endswith("ич"):
                return patronymic[:-2] + ("инъ" if pre_reform else "ин")
        else:
            if patronymic.endswith("овна"):
                return patronymic[:-4] + "ова"
            elif patronymic.endswith("евна"):
                return patronymic[:-4] + "ева"
            elif patronymic.endswith("инична"):  # Moved BEFORE "ична"
                return patronymic[:-6] + "ина"
            elif patronymic.endswith("ична"):
                return patronymic[:-4] + "ина"

        return patronymic

    @classmethod
    def archaic_to_modern(cls, patronymic: str, is_male: bool) -> str:
        """Converts an archaic possessive genitive to a modern formal patronymic."""
        if not patronymic:
            return patronymic

        # Strip terminal hard sign ъ
        pat = cls.normalize_to_modern(patronymic)
        if is_male:
            if pat.endswith("ов"):
                return pat[:-2] + "ович"
            elif pat.endswith("ев"):
                return pat[:-2] + "евич"
            elif pat.endswith("ин"):
                return pat[:-2] + "ич"
        else:
            if pat.endswith("ова"):
                return pat[:-3] + "овна"
            elif pat.endswith("ева"):
                return pat[:-3] + "евна"
            elif pat.endswith("ина"):
                return pat[:-3] + "ична"

        return patronymic
