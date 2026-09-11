import pymorphy3

_morph = pymorphy3.MorphAnalyzer()


def decline_name(name: str, case: str = "nomn") -> str:
    """Склоняет имя по падежам.
    case: nomn (кто? Миша), gent (кого? Миши), datv (кому? Мише),
          accs (кого? Мишу), ablt (кем? Мишей), loct (о ком? Мише)
    """
    if not name:
        return name

    # Специальный случай — «Малыш»
    if name.lower() in ("малыш", "малышка"):
        forms = {
            "nomn": "Малыш",
            "gent": "Малыша",
            "datv": "Малышу",
            "accs": "Малыша",
            "ablt": "Малышом",
            "loct": "Малыше",
        }
        return forms.get(case, name)

    try:
        parses = _morph.parse(name)
        if not parses:
            return name

        # Предпочитаем разбор как имя собственное
        chosen = None
        for p in parses:
            if "Name" in p.tag:
                chosen = p
                break
        if chosen is None:
            chosen = parses[0]

        inflected = chosen.inflect({case})
        if inflected:
            return inflected.word.capitalize()
        return name
    except Exception as e:
        print(f"Ошибка склонения имени '{name}': {e}")
        return name


def guess_gender(name: str):
    """Определяет пол по имени: 'masc', 'femn' или None."""
    if not name:
        return None
    try:
        parses = _morph.parse(name)
        for p in parses:
            if "Name" in p.tag and p.tag.gender in ("masc", "femn"):
                return p.tag.gender
        for p in parses:
            if p.tag.gender in ("masc", "femn"):
                return p.tag.gender
    except Exception:
        pass
    return None