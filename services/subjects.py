"""
School / university subjects for the «📚 Bu qaysi fan bo‘yicha?» step, and a quick guess of the subject
from the topic (no AI request: word stems in Uzbek Latin / Cyrillic, Russian and English).

guess("Sun'iy intellekt va kelajak") -> "Informatika / IT"; guess("Bozor iqtisodiyoti") -> "Iqtisodiyot".
Returns "" when nothing matches (then no button is pre-selected).
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

# (name shown on the button, stems that point to it)
SUBJECTS: List[Tuple[str, Tuple[str, ...]]] = [
    ("Iqtisodiyot", ("iqtisod", "bozor", "moliya", "bank", "marketing", "biznes", "menejment", "buxgalter",
                     "soliq", "investitsi", "tadbirkor", "inflyatsi", "byudjet", "экономи", "рынок", "финанс",
                     "маркетинг", "бизнес", "менеджмент", "econom", "market", "financ", "business", "management")),
    ("Adabiyot", ("adabiyot", "she'r", "sher ", "roman", "qissa", "doston", "navoiy", "qodiriy", "cho'lpon",
                  "chulpon", "hikoya", "g'azal", "литератур", "поэ", "роман", "literatur", "poem", "novel")),
    ("Biologiya", ("biolog", "hujayra", "o'simlik", "hayvon", "fotosintez", "genetik", "evolyutsi", "ekolog",
                   "organizm", "bakteri", "virus", "dnk", "биолог", "клетк", "растен", "животн", "фотосинтез",
                   "генети", "эколог", "biology", "cell", "plant", "animal", "photosynth", "genet", "ecolog")),
    ("Dinshunoslik", ("din", "islom", "qur'on", "masjid", "imom", "diniy", "xristian", "budd", "религи", "ислам",
                      "религия", "religio", "islam")),
    ("Falsafa", ("falsafa", "faylasuf", "mantiq", "etika", "философ", "этик", "логик", "philosoph", "ethic")),
    ("Fizika", ("fizika", "kuch", "energiya", "elektr", "magnit", "yorug'lik", "atom", "kvant", "harakat",
                "tezlik", "termodinami", "dinamik", "mexanik", "nyuton", "optika", "gravitatsi", "физик", "энерги", "электр", "магнит", "квант", "physic", "energy",
                "electric", "quantum")),
    ("Geografiya", ("geograf", "iqlim", "materik", "okean", "daryo", "tog'", "aholi", "xarita", "география",
                    "климат", "материк", "океан", "geograph", "climate", "ocean", "continent")),
    ("Huquq", ("huquq", "qonun", "konstitutsiya", "sud", "jinoyat", "fuqaro", "davlat va huquq", "право",
               "закон", "конституц", "суд", "law", "legal", "constitution", "court")),
    ("Informatika / IT", ("informatika", "kompyuter", "dastur", "algoritm", "internet", "sun'iy intellekt",
                          "suniy intellekt", "sun’iy intellekt", "intellekt", "robot", "kiberxavfsiz", "ma'lumotlar",
                          "tarmoq", "python", "web", "sayt", "ilova", "texnologiya", "raqamli", "информати", "компьютер",
                          "программ", "алгоритм", "интернет", "искусствен", "технолог", "computer", "program",
                          "software", "algorithm", "artificial intelligence", " ai ", "data", "cyber", "digital")),
    ("Kimyo", ("kimyo", "kimyoviy", "modda", "reaksiya", "molekula", "kislota", "element", "химия", "химическ",
               "реакц", "молекул", "кислот", "chemi", "molecul", "acid", "reaction")),
    ("Matematika", ("matemat", "algebra", "geometri", "tenglama", "funksiya", "integral", "hosila", "son ",
                    "sonlar", "statistik", "ehtimol", "teorema", "pifagor", "kasr", "foiz", "logarifm", "trigonometri", "математ", "алгебр", "геометр", "уравнен", "функци",
                    "интеграл", "math", "algebra", "geometr", "equation", "statistic", "probabil")),
    ("Ona tili / Tilshunoslik", ("ona tili", "o'zbek tili", "tilshunos", "grammatika", "imlo", "fonetika",
                                 "leksika", "morfologiya", "sintaksis", "nutq", "lingvist", "языкозн",
                                 "граммати", "лингвист", "linguist", "grammar")),
    ("Pedagogika / Ta'lim", ("pedagog", "ta'lim", "talim", "o'qitish", "tarbiya", "o'quvchi", "metodika",
                             "maktab", "педагог", "образован", "обучен", "воспитан", "pedagog", "education",
                             "teaching")),
    ("Psixologiya", ("psixolog", "ruhiy", "stress", "xulq", "shaxs", "психолог", "стресс", "личност",
                     "psycholog", "stress", "behavio")),
    ("Rus tili", ("rus tili", "русский язык", "russian language")),
    ("Ingliz tili", ("ingliz tili", "english", "английск")),
    ("San'at va madaniyat", ("san'at", "madaniyat", "musiqa", "rassom", "teatr", "kino", "me'morchilik",
                             "dizayn", "искусств", "культур", "музык", "театр", "архитектур", "art ", "culture",
                             "music", "architect", "design")),
    ("Sport", ("sport", "jismoniy", "futbol", "olimpiada", "mashq", "salomatlik", "спорт", "физическ",
               "футбол", "олимпи", "football", "olympic", "fitness")),
    ("Tarix", ("tarix", "temur", "amir", "xonlig", "imperiya", "urush", "qadimgi", "sivilizatsiya", "mustaqillik",
               "история", "истори", "войн", "импери", "цивилизац", "history", "histor", "war ", "empire",
               "civiliz")),
    ("Tibbiyot", ("tibbiyot", "kasallik", "davolash", "salomatlik", "dori", "yurak", "qon", "shifokor",
                  "vaksina", "medits", "медицин", "болезн", "лечен", "здоров", "сердц", "вакцин", "medic",
                  "disease", "health", "vaccine", "heart")),
    ("Ekologiya", ("ekolog", "atrof-muhit", "atrof muhit", "ifloslan", "tabiat", "chiqindi", "orol", "экологи",
                   "окружающ", "загрязн", "environment", "pollution", "climate change")),
]
NAMES: List[str] = [name for name, _ in SUBJECTS]


def _norm(text: str) -> str:
    text = " " + (text or "").lower() + " "
    return re.sub(r"[ʻʼ‘’`´]", "'", text)


def _has(text: str, stem: str) -> bool:
    core = stem.strip()
    if len(core) <= 3:   # short stems ("din", "qon", "sud", "ai") only as whole words: not inside "dinamika"
        return re.search(r"(?<![\w'])" + re.escape(core) + r"(?![\w'])", text) is not None
    return stem in text


def guess(topic: str) -> str:
    """The most likely subject of a topic, or "" when no stem matches."""
    text = _norm(topic)
    scores: Dict[str, int] = {}
    for name, stems in SUBJECTS:
        n = sum(len(s) for s in stems if _has(text, s))   # longer matches weigh more ("sun'iy intellekt" > "art")
        if n:
            scores[name] = n
    if not scores:
        return ""
    return max(scores, key=lambda k: scores[k])
