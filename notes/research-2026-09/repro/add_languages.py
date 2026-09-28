"""Add languages to font-resources-translations.json.

Weights, slopes and axis names are given word for word. Widths are composed
from a base word and a modifier (Extra / Semi / Ultra) by each language's own
rule, so compound forms stay consistent within a language.
"""

import json
import sys

PATH = sys.argv[1]

WEIGHTS = ["Hairline", "Thin", "Extralight", "Light", "Book", "Regular", "Medium",
           "Semibold", "Bold", "Extrabold", "Heavy", "Black"]
SLOPES = ["Upright", "Italic", "Oblique", "Slanted"]
AXES = ["Weight", "Width", "Optical size", "Slant", "Italic", "Contrast"]
WIDTH_BASES = ["Compressed", "Condensed", "Narrow", "Normal", "Wide", "Extended", "Expanded"]
WIDTH_KEYS = {
    "Extra Compressed": ("Extra", "Compressed"), "Compressed": (None, "Compressed"),
    "Ultra Condensed": ("Ultra", "Condensed"), "Extra Condensed": ("Extra", "Condensed"),
    "Condensed": (None, "Condensed"), "Semi Condensed": ("Semi", "Condensed"),
    "Narrow": (None, "Narrow"), "Normal": (None, "Normal"), "Wide": (None, "Wide"),
    "Extra Wide": ("Extra", "Wide"), "Semi Extended": ("Semi", "Extended"),
    "Extended": (None, "Extended"), "Extra Extended": ("Extra", "Extended"),
    "Ultra Extended": ("Ultra", "Extended"), "Semi Expanded": ("Semi", "Expanded"),
    "Expanded": (None, "Expanded"), "Extra Expanded": ("Extra", "Expanded"),
    "Ultra Expanded": ("Ultra", "Expanded"),
}

# mode: "space" = "Mod base" (base lowercased, sentence case),
#       "Space" = "Mod Base" (title case kept), "attach" = "Modbase"
L = {}

L["it"] = dict(
    w="Filiforme|Sottile|Extraleggero|Leggero|Book|Normale|Medio|Semigrassetto|Grassetto|Extragrassetto|Pesante|Nero",
    s="Tondo|Corsivo|Obliquo|Inclinato",
    d="Compresso|Condensato|Stretto|Normale|Largo|Esteso|Espanso",
    mods={"Extra": ("Extra", "attach"), "Semi": ("Semi", "attach"), "Ultra": ("Ultra", "attach")},
    a="Peso|Larghezza|Dimensione ottica|Inclinazione|Corsivo|Contrasto")
L["pl"] = dict(
    w="Włosowy|Cienki|Ekstralekki|Lekki|Książkowy|Zwykły|Średni|Półgruby|Pogrubiony|Ekstrapogrubiony|Ciężki|Czarny",
    s="Prosty|Kursywa|Pochyły|Nachylony",
    d="Ściśnięty|Zwężony|Wąski|Normalny|Szeroki|Rozszerzony|Rozciągnięty",
    mods={"Extra": ("Ekstra", "attach"), "Semi": ("Pół", "attach"), "Ultra": ("Ultra", "attach")},
    a="Grubość|Szerokość|Rozmiar optyczny|Nachylenie|Kursywa|Kontrast")
L["cs"] = dict(
    w="Vlasové|Tenké|Extra lehké|Lehké|Knižní|Obyčejné|Střední|Polotučné|Tučné|Extra tučné|Těžké|Černé",
    s="Stojaté|Kurzíva|Šikmé|Nakloněné",
    d="Stlačené|Zúžené|Úzké|Normální|Široké|Rozšířené|Roztažené",
    mods={"Extra": ("Extra", "space"), "Semi": ("Polo", "attach"), "Ultra": ("Ultra", "space")},
    a="Tloušťka|Šířka|Optická velikost|Sklon|Kurzíva|Kontrast")
L["sk"] = dict(
    w="Vlasové|Tenké|Extra ľahké|Ľahké|Knižné|Normálne|Stredné|Polotučné|Tučné|Extra tučné|Ťažké|Čierne",
    s="Rovné|Kurzíva|Šikmé|Naklonené",
    d="Stlačené|Zúžené|Úzke|Normálne|Široké|Rozšírené|Roztiahnuté",
    mods={"Extra": ("Extra", "space"), "Semi": ("Polo", "attach"), "Ultra": ("Ultra", "space")},
    a="Hrúbka|Šírka|Optická veľkosť|Sklon|Kurzíva|Kontrast")
L["hu"] = dict(
    w="Hajszálvékony|Vékony|Extra könnyű|Könnyű|Könyv|Normál|Közepes|Közepesen félkövér|Félkövér|Extra félkövér|Nehéz|Fekete",
    s="Álló|Dőlt|Ferde|Döntött",
    d="Tömörített|Keskenyített|Keskeny|Normál|Széles|Kiterjesztett|Szélesített",
    mods={"Extra": ("Extra", "space"), "Semi": ("Fél", "attach"), "Ultra": ("Ultra", "space")},
    a="Vastagság|Szélesség|Optikai méret|Dőlésszög|Dőlt|Kontraszt")
L["sl"] = dict(
    w="Lasno|Tanko|Ekstra lahko|Lahko|Knjižno|Navadno|Srednje|Polkrepko|Krepko|Ekstra krepko|Težko|Črno",
    s="Pokončno|Ležeče|Poševno|Nagnjeno",
    d="Stisnjeno|Zoženo|Ozko|Normalno|Široko|Razširjeno|Raztegnjeno",
    mods={"Extra": ("Ekstra", "space"), "Semi": ("Pol", "attach"), "Ultra": ("Ultra", "space")},
    a="Debelina|Širina|Optična velikost|Naklon|Ležeče|Kontrast")
L["ro"] = dict(
    w="Filiform|Subțire|Extra ușor|Ușor|Book|Obișnuit|Mediu|Semialdin|Aldin|Extra aldin|Greu|Negru",
    s="Drept|Cursiv|Oblic|Înclinat",
    d="Comprimat|Condensat|Îngust|Normal|Lat|Extins|Expandat",
    mods={"Extra": ("Extra", "space"), "Semi": ("Semi", "attach"), "Ultra": ("Ultra", "space")},
    a="Grosime|Lățime|Dimensiune optică|Înclinare|Cursiv|Contrast")
L["nb"] = dict(
    w="Hårfin|Tynn|Ekstra lett|Lett|Bok|Vanlig|Medium|Halvfet|Fet|Ekstra fet|Tung|Svart",
    s="Opprett|Kursiv|Skrå|Skråstilt",
    d="Komprimert|Kondensert|Smal|Normal|Bred|Utvidet|Ekspandert",
    mods={"Extra": ("Ekstra", "space"), "Semi": ("Halv", "attach"), "Ultra": ("Ultra", "space")},
    a="Vekt|Bredde|Optisk størrelse|Helning|Kursiv|Kontrast")
L["ca"] = dict(
    w="Filiforme|Fina|Extralleugera|Lleugera|Book|Normal|Mitjana|Seminegreta|Negreta|Extranegreta|Pesada|Negra",
    s="Rodona|Cursiva|Obliqua|Inclinada",
    d="Comprimida|Condensada|Estreta|Normal|Ampla|Estesa|Expandida",
    mods={"Extra": ("Extra", "attach"), "Semi": ("Semi", "attach"), "Ultra": ("Ultra", "attach")},
    a="Pes|Amplada|Mida òptica|Inclinació|Cursiva|Contrast")
L["bg"] = dict(
    w="Косъмен|Тънък|Екстра светъл|Светъл|Книжен|Обикновен|Среден|Полуудебелен|Получер|Екстра удебелен|Тежък|Черен",
    s="Прав|Курсив|Наклонен|Скосен",
    d="Сгъстен|Сбит|Тесен|Нормален|Широк|Разширен|Разтеглен",
    mods={"Extra": ("Екстра", "space"), "Semi": ("Полу", "attach"), "Ultra": ("Ултра", "space")},
    a="Дебелина|Ширина|Оптичен размер|Наклон|Курсив|Контраст")
L["be"] = dict(
    w="Валасяны|Тонкі|Экстрасветлы|Светлы|Кніжны|Звычайны|Сярэдні|Паўтлусты|Тлусты|Экстратлусты|Цяжкі|Чорны",
    s="Прамы|Курсіў|Нахільны|Нахілены",
    d="Сціснуты|Звужаны|Вузкі|Нармальны|Шырокі|Пашыраны|Расцягнуты",
    mods={"Extra": ("Экстра", "attach"), "Semi": ("Паў", "attach"), "Ultra": ("Ультра", "attach")},
    a="Таўшчыня|Шырыня|Аптычны памер|Нахіл|Курсіў|Кантраст")
L["mk"] = dict(
    w="Влакнест|Тенок|Екстра лесен|Лесен|Книжен|Обичен|Среден|Полузадебелен|Задебелен|Екстра задебелен|Тежок|Црн",
    s="Исправен|Курзив|Кос|Наклонет",
    d="Компресиран|Збиен|Тесен|Нормален|Широк|Проширен|Раширен",
    mods={"Extra": ("Екстра", "space"), "Semi": ("Полу", "attach"), "Ultra": ("Ултра", "space")},
    a="Дебелина|Ширина|Оптичка големина|Наклон|Курзив|Контраст")
L["ky"] = dict(
    w="Кылдай|Ичке|Өтө жеңил|Жеңил|Китептик|Кадимки|Орточо|Жарым калың|Калың|Өтө калың|Оор|Кара",
    s="Түз|Курсив|Кыйшык|Жантайган",
    d="Кысылган|Тарытылган|Тар|Нормалдуу|Кең|Кеңейтилген|Жайылган",
    mods={"Extra": ("Өтө", "space"), "Semi": ("Жарым", "space"), "Ultra": ("Ультра", "space")},
    a="Калыңдык|Туурасы|Оптикалык өлчөм|Жантаюу|Курсив|Контраст")
L["tt"] = dict(
    w="Чәчсыман|Нечкә|Бик җиңел|Җиңел|Китап|Гадәти|Уртача|Ярым калын|Калын|Бик калын|Авыр|Кара",
    s="Туры|Курсив|Кыек|Авышкан",
    d="Кысылган|Тарайтылган|Тар|Нормаль|Киң|Киңәйтелгән|Җәелгән",
    mods={"Extra": ("Бик", "space"), "Semi": ("Ярым", "space"), "Ultra": ("Ультра", "space")},
    a="Калынлык|Киңлек|Оптик зурлык|Авышлык|Курсив|Контраст")
L["uz"] = dict(
    w="Qildek|Ingichka|Juda yengil|Yengil|Kitobiy|Oddiy|Oʻrta|Yarim qalin|Qalin|Juda qalin|Ogʻir|Qora",
    s="Tik|Kursiv|Qiya|Ogʻma",
    d="Siqilgan|Toraytirilgan|Tor|Normal|Keng|Kengaytirilgan|Yoyilgan",
    mods={"Extra": ("Juda", "space"), "Semi": ("Yarim", "space"), "Ultra": ("Ultra", "space")},
    a="Qalinlik|Kenglik|Optik oʻlcham|Qiyalik|Kursiv|Kontrast")
L["az"] = dict(
    w="Tük kimi|Nazik|Çox yüngül|Yüngül|Kitab|Adi|Orta|Yarımqalın|Qalın|Çox qalın|Ağır|Qara",
    s="Düz|Kursiv|Çəp|Maili",
    d="Sıxılmış|Daraldılmış|Dar|Normal|Geniş|Genişləndirilmiş|Yayılmış",
    mods={"Extra": ("Çox", "space"), "Semi": ("Yarım", "attach"), "Ultra": ("Ultra", "space")},
    a="Qalınlıq|En|Optik ölçü|Meyl|Kursiv|Kontrast")
L["et"] = dict(
    w="Juuksepeen|Õhuke|Eriti kerge|Kerge|Raamatu|Tavaline|Keskmine|Poolpaks|Paks|Eriti paks|Raske|Must",
    s="Püstine|Kursiiv|Kaldu|Kallutatud",
    d="Kokkusurutud|Kitsendatud|Kitsas|Normaalne|Lai|Laiendatud|Venitatud",
    mods={"Extra": ("Eriti", "space"), "Semi": ("Pool", "attach"), "Ultra": ("Ultra", "space")},
    a="Paksus|Laius|Optiline suurus|Kalle|Kursiiv|Kontrast")
L["lv"] = dict(
    w="Matiņa|Tievs|Īpaši viegls|Viegls|Grāmatas|Parasts|Vidējs|Pustrekns|Trekns|Īpaši trekns|Smags|Melns",
    s="Taisns|Slīpraksts|Slīps|Sagāzts",
    d="Saspiests|Sašaurināts|Šaurs|Normāls|Plats|Paplašināts|Izstiepts",
    mods={"Extra": ("Īpaši", "space"), "Semi": ("Pus", "attach"), "Ultra": ("Ultra", "space")},
    a="Biezums|Platums|Optiskais izmērs|Slīpums|Slīpraksts|Kontrasts")
L["lt"] = dict(
    w="Plauko storio|Plonas|Itin lengvas|Lengvas|Knyginis|Įprastas|Vidutinis|Pusiau paryškintas|Paryškintas|Itin paryškintas|Sunkus|Juodas",
    s="Stačias|Kursyvas|Įstrižas|Pasviręs",
    d="Suspaustas|Susiaurintas|Siauras|Normalus|Platus|Išplėstas|Ištemptas",
    mods={"Extra": ("Itin", "space"), "Semi": ("Pusiau", "space"), "Ultra": ("Ultra", "space")},
    a="Storis|Plotis|Optinis dydis|Posvyris|Kursyvas|Kontrastas")
L["is"] = dict(
    w="Hárfínt|Grannt|Afar létt|Létt|Bók|Venjulegt|Miðlungs|Hálffeitt|Feitt|Afar feitt|Þungt|Svart",
    s="Upprétt|Skáletrað|Hallandi|Hallað",
    d="Þjappað|Þétt|Mjótt|Eðlilegt|Breitt|Útvíkkað|Útþanið",
    mods={"Extra": ("Afar", "space"), "Semi": ("Hálf", "attach"), "Ultra": ("Ofur", "attach")},
    a="Þykkt|Breidd|Sjónræn stærð|Halli|Skáletur|Andstæða")
L["vi"] = dict(
    w="Siêu mảnh|Mảnh|Rất nhẹ|Nhẹ|Sách|Thường|Vừa|Bán đậm|Đậm|Rất đậm|Nặng|Đen",
    s="Đứng|Nghiêng|Xiên|Ngả",
    d="Nén|Co hẹp|Hẹp|Bình thường|Rộng|Mở rộng|Giãn",
    mods={"Extra": ("Rất", "space"), "Semi": ("Bán", "space"), "Ultra": ("Siêu", "space")},
    a="Độ đậm|Độ rộng|Kích thước quang học|Độ nghiêng|Nghiêng|Tương phản")
L["id"] = dict(
    w="Garis Rambut|Tipis|Ekstra Ringan|Ringan|Buku|Reguler|Sedang|Semi Tebal|Tebal|Ekstra Tebal|Berat|Hitam",
    s="Tegak|Miring|Oblik|Condong",
    d="Dimampatkan|Dipadatkan|Sempit|Normal|Lebar|Diperluas|Direntangkan",
    mods={"Extra": ("Ekstra", "Space"), "Semi": ("Semi", "Space"), "Ultra": ("Ultra", "Space")},
    a="Ketebalan|Lebar|Ukuran Optik|Kemiringan|Miring|Kontras")

SR_LATN = {
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Ђ": "Đ", "Е": "E", "Ж": "Ž", "З": "Z",
    "И": "I", "Ј": "J", "К": "K", "Л": "L", "Љ": "Lj", "М": "M", "Н": "N", "Њ": "Nj", "О": "O",
    "П": "P", "Р": "R", "С": "S", "Т": "T", "Ћ": "Ć", "У": "U", "Ф": "F", "Х": "H", "Ц": "C",
    "Ч": "Č", "Џ": "Dž", "Ш": "Š",
}
SR_LATN.update({k.lower(): v.lower() for k, v in list(SR_LATN.items())})


def compose(mod_rule, base):
    word, mode = mod_rule
    if mode == "attach":
        return word + base[0].lower() + base[1:]
    if mode == "space":
        return f"{word} {base[0].lower()}{base[1:]}"
    return f"{word} {base}"


def build(spec):
    w = spec["w"].split("|"); s = spec["s"].split("|"); d = spec["d"].split("|"); a = spec["a"].split("|")
    assert len(w) == 12 and len(s) == 4 and len(d) == 7 and len(a) == 6, spec
    bases = dict(zip(WIDTH_BASES, d))
    widths = {}
    for key, (mod, base) in WIDTH_KEYS.items():
        widths[key] = bases[base] if mod is None else compose(spec["mods"][mod], bases[base])
    return dict(zip(WEIGHTS, w)), dict(zip(SLOPES, s)), widths, dict(zip(AXES, a))


data = json.load(open(PATH, encoding="utf-8"))
sections = ("WEIGHT_LANG_VARIANTS", "ITALICS_LANG_VARIANTS", "WIDTH_LANG_VARIANTS", "AXIS_LANG_VARIANTS")
for lang, spec in L.items():
    for section, table in zip(sections, build(spec)):
        for key, value in table.items():
            assert lang not in data[section][key], (lang, key)
            data[section][key][lang] = value

# pt-PT: the existing pt words; sr-Latn: Serbian Cyrillic transliterated
for section in sections:
    for key, entry in data[section].items():
        entry["pt-PT"] = entry["pt"]
        entry["sr-Latn"] = "".join(SR_LATN.get(ch, ch) for ch in entry["sr"])

json.dump(data, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
open(PATH, "a", encoding="utf-8").write("\n")
langs = sorted({l for s in sections for e in data[s].values() for l in e})
print(len(langs), "languages:", ", ".join(langs))
