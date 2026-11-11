#!/usr/bin/env python3
"""Writes content/landings/gap.json: landing pages for queries that people search (Marketing Miner content gap 11. 11. 2026 against heureka,
bambule, mrakyhracek, pompo, 4kids, ministerstvohracek). One row = one page; patterns are matched on the folded (no diacritics) product title.
Re-run after editing the table:  python3 scripts/gap_landings_gen.py"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "content/landings/gap.json"
# slug | h1 | [any regex] | parent | options (cat, none, all, sex, price, age, offers, min, index_min, hubs, home, icon, lead, title, desc)
T = [
    # ---- hubs people type most
    ("hracky-pro-holky", "Hračky pro holky", [], "/kategorie/", dict(sex="f", min=12, home=True, hubs=["/darky/"], icon="panenka", lead="Hračky, které obchody řadí pro holky: panenky, kreativní sady, LEGO Friends, plyšáci. Porovnejte ceny a vyberte podle věku.")),
    ("hracky-pro-kluky", "Hračky pro kluky", [], "/kategorie/", dict(sex="m", min=12, home=True, hubs=["/darky/"], icon="auto", lead="Hračky, které obchody řadí pro kluky: auta, stavebnice, LEGO, RC modely. Porovnejte ceny a vyberte podle věku.")),
    ("hracky-pro-deti", "Hračky pro děti", [], "/kategorie/", dict(offers=3, min=24, home=True, icon="party", lead="Nejčastěji srovnávané hračky pro děti: ty, které najdete ve třech a více obchodech, takže si snadno ohlídáte nejlepší cenu.")),
    # ---- RC, auta, stroje
    ("odrazedlo-motorka", "Odrážedlo motorka", [r"\bodrazedl\w*"], "/venku/odrazedla/", dict(all=[r"\b(motork\w*|motocykl\w*|motorbike)\b"], min=6)),
    ("odrazedla-auto", "Odrážedla ve tvaru auta", [r"\bodrazedl\w*"], "/venku/odrazedla/", dict(all=[r"\b(aut\w+|autic\w+|traktor\w*|mini cooper|beetle)\b"], min=6)),
    ("odrazedla-pro-nejmensi", "Odrážedla pro nejmenší", [r"\bodrazedl\w*"], "/venku/odrazedla/", dict(age=[None, 36], age_unknown=True, min=6, lead="Odrážedla pro děti od 1 roku: nižší sedátko, měkká kola a lehká konstrukce.")),
    ("hasicska-auta", "Hasičská auta pro děti", [r"\bhasic\w*", r"\bhasici\b"], "/auta-a-vlacky/", dict(all=[r"\b(aut\w+|autic\w+|vuz|vozidl\w+|zebrik\w*|stanic\w+)\b"], min=6)),
    ("policejni-auta-a-stanice", "Policejní auta a stanice", [r"\bpolicejn\w*", r"\bpolicie\b"], "/auta-a-vlacky/", dict(min=6)),
    ("popelarska-auta", "Popelářská auta", [r"\bpopelar\w*"], "/auta-a-vlacky/", dict(min=6)),
    ("bagry-pro-deti", "Bagry pro děti", [r"\bbagr\w*", r"\bnakladac\w*"], "/auta-a-vlacky/stroje-a-traktory/", dict(min=6)),
    ("traktory-pro-deti", "Traktory pro děti", [r"\btraktor\w*"], "/auta-a-vlacky/stroje-a-traktory/", dict(min=6)),
    ("motorky-pro-deti", "Motorky pro děti", [r"\bmotork\w*", r"\bmotocykl\w*"], "/kategorie/", dict(none=[r"\bodrazedl\w*"], min=8)),
    ("ctyrkolky-pro-deti", "Čtyřkolky pro děti", [r"\bctyrkol\w*"], "/kategorie/", dict(min=6)),
    ("slapaci-auta", "Šlapací auta a vozítka", [r"\bslapaci\b", r"\bslapadl\w*"], "/venku/", dict(min=6)),
    ("elektricka-vozitka-pro-deti", "Elektrická auta a vozítka pro děti", [r"\belektrick\w* (aut\w+|vozitk\w+|motork\w+|ctyrkol\w+|traktor\w*)"], "/venku/", dict(min=6)),
    ("hot-wheels-drahy", "Hot Wheels dráhy", [r"\bhot wheels\b"], "/auta-a-vlacky/autodrahy/", dict(all=[r"\b(draha|drahy|dráha|track|trasa|set|souprava|garaz\w*)\b"], min=6)),
    ("drevene-vlacky", "Dřevěné vláčky a vláčkodráhy", [r"\bvlac\w*", r"\bvlak\w*", r"\bvlackodrah\w*"], "/auta-a-vlacky/vlacky/", dict(all=[r"\bdrev\w*"], min=6)),
    # ---- panenky, doplňky, hraní rolí
    ("retro-kocarky-pro-panenky", "Retro kočárky pro panenky", [r"\bretro\b"], "/panenky/kocarky/", dict(all=[r"\bkocar\w*"], min=6)),
    ("domecky-pro-barbie", "Domečky a karavany pro Barbie", [r"\bdomec\w*", r"\bkaravan\w*", r"\bdream ?house\b"], "/panenky/domecky/", dict(all=[r"\b(barbie|panenk\w+|polly|lol|l\.o\.l)\b"], min=6)),
    ("karavany-pro-panenky", "Karavany pro panenky", [r"\bkaravan\w*", r"\bcamper\b"], "/panenky/", dict(min=6)),
    ("dreveny-domecek-pro-panenky", "Dřevěné domečky pro panenky", [r"\bdomec\w*"], "/panenky/domecky/", dict(all=[r"\bdrev\w*"], min=6)),
    ("postylky-pro-panenky", "Postýlky a kolébky pro panenky", [r"\bpostylk\w*", r"\bkolebk\w*"], "/panenky/", dict(min=6)),
    ("detske-pokladny", "Dětské pokladny", [r"\bpokladn\w*"], "/hrajeme-si-na/obchod-a-domacnost/", dict(none=[r"\bpokladnick\w*"], min=6)),
    ("detske-vysavace", "Dětské vysavače", [r"\bvysavac\w*"], "/hrajeme-si-na/", dict(min=6)),
    ("detske-sici-stroje", "Dětské šicí stroje", [r"\bsici (stroj\w*)\b", r"\bsiti\b"], "/hrajeme-si-na/", dict(all=[r"\bstroj\w*"], min=5)),
    ("detske-mikrofony", "Dětské mikrofony a karaoke", [r"\bmikrofon\w*", r"\bkaraoke\b"], "/hudebni/", dict(min=6)),
    ("detske-kytary", "Dětské kytary", [r"\bkytar\w*"], "/hudebni/", dict(min=6)),
    ("vysilacky-walkie-talkie", "Vysílačky pro děti", [r"\bwalkie\b", r"\bvysilack\w*"], "/elektronika/", dict(min=6)),
    ("interaktivni-stolky", "Interaktivní stolečky", [r"\binteraktivni\b"], "/pro-nejmensi/", dict(all=[r"\b(stolek|stolecek|stoleck\w*|stolky)\b"], min=6)),
    # ---- ven, voda, zahrada
    ("vodni-pistole", "Vodní pistole", [r"\bvodni pistol\w*", r"\bstrikaci pistol\w*", r"\bvodni (strikack\w*|kulomet\w*)", r"\bsuper soaker\b"], "/venku/do-vody/", dict(min=6)),
    ("detske-bazeny", "Dětské bazény", [r"\bbazen\w*", r"\bbazenek\b"], "/venku/do-vody/", dict(none=[r"\bkulicky\b", r"\bbazen na kulicky\b", r"\bplast\w+ kulick\w+"], min=6)),
    ("skluzavky", "Dětské skluzavky", [r"\bskluzavk\w*", r"\bklouzack\w*"], "/venku/zahrada/", dict(min=6)),
    ("piskoviste", "Pískoviště pro děti", [r"\bpiskovist\w*"], "/venku/na-pisek/", dict(min=6)),
    ("detske-stany", "Dětské stany a tee-pee", [r"\bstan\b", r"\bstany\b", r"\bteepee\b", r"\btee pee\b", r"\btipi\b"], "/venku/", dict(none=[r"\bstanice\b"], min=6)),
    ("nafukovaci-kresla-pro-deti", "Nafukovací křesla a lehátka pro děti", [r"\bnafukovaci (kresl\w*|pohov\w*|lehatk\w*|zidl\w*)"], "/venku/", dict(min=6)),
    ("bublifuky", "Bublifuky", [r"\bbublifuk\w*", r"\bmydlove bubliny\b"], "/venku/", dict(min=6)),
    # ---- hry, hlavolamy, sporty
    ("stolni-fotbal", "Stolní fotbal", [r"\bstolni fotbal\w*", r"\bfotbalek\b"], "/spolecenske-hry/", dict(min=5)),
    ("stolni-hokej", "Stolní hokej", [r"\bstolni hokej\w*", r"\bair ?hockey\b"], "/spolecenske-hry/", dict(min=5)),
    ("pop-it", "Pop it – praskací bubliny", [r"\bpop[ -]?it\b", r"\bpraskaci bubl\w*"], "/kategorie/", dict(min=6, lead="Pop it hračky: praskání bublin jako antistresová pomůcka i společenská hra. Porovnejte ceny a tvary.")),
    ("clovece-nezlob-se", "Člověče, nezlob se", [r"\bclovece[ ,]*nezlob se\b", r"\bnezlob se\b"], "/spolecenske-hry/", dict(min=5, lead="Člověče, nezlob se v klasickém, dřevěném i velkém provedení. Porovnejte ceny a velikosti hrací desky.")),
    ("karetni-hra-uno", "UNO a podobné karetní hry", [r"\buno\b"], "/spolecenske-hry/karetni/", dict(min=5)),
    ("tech-deck-fingerboardy", "Tech Deck a fingerboardy", [r"\btech deck\b", r"\bfingerboard\w*"], "/kategorie/", dict(min=5)),
    ("kreslici-tabulky", "Kreslicí a magnetické tabulky", [r"\bkreslic\w* tabul\w*", r"\bmagneticka tabul\w*", r"\btabule pro deti\b", r"\bkreslici tabule\b", r"\bkridova tabul\w*"], "/kreativni/", dict(min=6)),
    # ---- plyš a nejmenší
    ("plysovi-medvedi", "Plyšoví medvědi", [r"\bmedved\w*", r"\bmedvidek\b", r"\bteddy\b"], "/plysaci/", dict(cat=["plysaci"], min=6)),
    ("usinacci", "Usínáčci", [r"\businac\w*"], "/pro-nejmensi/", dict(min=5)),
    ("choditka", "Chodítka pro děti", [r"\bchoditk\w*"], "/pro-nejmensi/tahaci-a-odstrkovadla/", dict(min=6)),
    ("odstrkovadla", "Odstrkovadla pro děti", [r"\bodstrkovadl\w*"], "/pro-nejmensi/tahaci-a-odstrkovadla/", dict(min=5)),
    ("pokladnicky", "Pokladničky pro děti", [r"\bpokladnick\w*"], "/kategorie/", dict(min=6)),
    # ---- značky a licence (mimo existující /znacky/ a /hracky-*/)
    ("hracky-enchantimals", "Hračky Enchantimals", [r"\benchantimal\w*"], "/panenky/", dict(min=6)),
    ("hracky-vip-pets", "Hračky VIP Pets", [r"\bvip pets\b"], "/figurky-a-zviratka/", dict(min=6)),
    ("hracky-mala-morska-vila", "Hračky Malá mořská víla", [r"\bmala morska vila\b", r"\bariel\b", r"\blittle mermaid\b"], "/kategorie/", dict(min=6)),
    ("hracky-grogu-mandalorian", "Grogu a Mandalorian: hračky a LEGO", [r"\bgrogu\b", r"\bmandalorian\w*", r"\bbaby yoda\b"], "/kategorie/", dict(min=6)),
    ("hracky-seva-stavebnice", "Stavebnice Seva", [r"\bseva\b"], "/stavebnice/kovove-a-technicke/", dict(min=6)),
    # ---- LEGO motivy a vozidla (hledaná jména)
    ("lego/avatar", "LEGO Avatar", [r"\bavatar\w*"], "/lego/", dict(cat=["lego"], min=5)),
    ("lego/stranger-things", "LEGO Stranger Things", [r"\bstranger things\b"], "/lego/", dict(cat=["lego"], min=3, index_min=5)),
    ("lego/stitch", "LEGO Stitch", [r"\bstitch\b"], "/lego/", dict(cat=["lego"], min=3, index_min=5)),
    ("lego/spiderman", "LEGO Spider-Man", [r"\bspider[ -]?man\b", r"\bspidey\b"], "/lego/", dict(cat=["lego"], min=6)),
    ("lego/batman", "LEGO Batman", [r"\bbatman\b"], "/lego/", dict(cat=["lego"], min=6)),
    ("lego/ferrari", "LEGO Ferrari", [r"\bferrari\b"], "/lego/", dict(cat=["lego"], min=3, index_min=4)),
    ("lego/porsche", "LEGO Porsche", [r"\bporsche\b"], "/lego/", dict(cat=["lego"], min=3, index_min=4)),
    ("lego/lamborghini", "LEGO Lamborghini", [r"\blamborghini\b"], "/lego/", dict(cat=["lego"], min=3, index_min=4)),
    ("lego/titanic", "LEGO Titanic", [r"\btitanic\b"], "/lego/", dict(cat=["lego"], min=1, index_min=1)),
    ("lego/motorky", "LEGO motorky", [r"\bmotork\w*", r"\bmotocykl\w*", r"\bkawasaki\b", r"\bducati\b", r"\bharley\b", r"\bbmw r\b"], "/lego/", dict(cat=["lego"], min=5)),
    ("lego/duplo-vlacky", "LEGO Duplo vláčky", [r"\bvlac\w*", r"\bvlak\w*", r"\bparni\b"], "/lego/duplo/", dict(cat=["lego"], all=[r"\bduplo\b"], min=4, index_min=6)),
    ("lego/domy-a-domky", "LEGO domy a domečky", [r"\bdom\b", r"\bdomek\b", r"\bdomec\w*", r"\bdum\b", r"\brodinny dum\b"], "/lego/", dict(cat=["lego"], none=[r"\bkostky\b"], min=6)),
    ("lego/fotbal", "LEGO fotbal", [r"\bfotbal\w*", r"\bworld cup\b", r"\bfifa\b"], "/lego/", dict(cat=["lego"], min=3, index_min=4)),
    ("lego/kostky", "LEGO kostky a boxy s kostkami", [r"\bklasick\w+ kostk\w+", r"\bclassic\b", r"\bkostky\b", r"\bstavebni kostky\b"], "/lego/classic/", dict(cat=["lego"], min=6)),
    # ---- vlastnosti a materiály (ručně kvůli shodě rodu v češtině)
    ("hracky-na-baterie", "Hračky na baterie", [r"\bna baterie\b", r"\bna baterky\b", r"\bbateriov\w*"], "/kategorie/", dict(offers=2, min=20, icon="rc")),
    ("svitici-hracky", "Svítící hračky", [r"\bsvitic\w*", r"\bsviti\b", r"\bled\b", r"\bs led\b"], "/kategorie/", dict(min=12)),
    ("hracky-se-zvukem", "Hračky se zvukem a světlem", [r"\bse zvuk\w*", r"\bzvukov\w*", r"\bs efekt\w*"], "/kategorie/", dict(offers=2, min=20)),
    ("drevena-auta", "Dřevěná autíčka a auta", [r"\bdrev\w*"], "/auta-a-vlacky/", dict(all=[r"\b(aut\w+|autic\w+|nakladak\w*)\b"], min=6)),
    ("drevene-spolecenske-hry", "Dřevěné společenské hry", [r"\bdrev\w*"], "/spolecenske-hry/", dict(cat=["spolecenske-hry"], min=6)),
    ("drevene-kuchynky", "Dřevěné kuchyňky pro děti", [r"\bdrev\w*"], "/hrajeme-si-na/kuchynky/", dict(cat=["hrajeme-si-na"], all=[r"\bkuchyn\w*"], min=5)),
    ("hadrove-panenky", "Hadrové panenky", [r"\bhadrov\w*", r"\btextiln\w+ panenk\w*"], "/panenky/", dict(min=6)),
    ("retro-hracky", "Retro hračky", [r"\bretro\b", r"\bvintage\b", r"\bnostalg\w*"], "/kategorie/", dict(min=10)),
    ("boxy-na-hracky", "Boxy a úložné koše na hračky", [r"\b(box|boxy|kos|kose|truhla|truhlicka|organizer|regal\w*) na hracky\b", r"\bulozn\w+ (box|kos|prostor|regal)\w*"], "/kategorie/", dict(min=5)),
    # ---- dárky pro dospělé (vysoká hledanost, mapujeme na LEGO/puzzle/hry)
    ("darek-pro-muze", "Dárek pro muže", [r"\btechnic\b", r"\bicons\b", r"\bspeed champions\b", r"\bferrari\b", r"\bporsche\b", r"\bstar wars\b", r"\bharry potter\b", r"\bformule\b", r"\bbugatti\b", r"\blamborghini\b", r"\bmclaren\b"], "/darky/", dict(cat=["lego"], price=[800, None], age=[168, None], min=10, home=False, icon="party", lead="Dárky pro muže, kteří rádi staví: LEGO Technic, Icons, Speed Champions a auta, Star Wars a Harry Potter pro dospělé.")),
    ("darek-pro-zenu", "Dárek pro ženu", [r"\bbotanic\w*", r"\bkvet\w+", r"\bkytic\w*", r"\bruze\b", r"\borchid\w*", r"\bbonsai\b", r"\bsakura\b", r"\bfriends\b", r"\bicons\b"], "/darky/", dict(cat=["lego"], price=[500, None], age=[168, None], min=10, icon="party", lead="Dárky pro ženy: LEGO květiny, Botanicals, bonsaje a dekorace, které vydrží na polici.")),
    ("darek-pro-maminku", "Dárek pro maminku", [r"\bbotanic\w*", r"\bkvet\w+", r"\bkytic\w*", r"\bruze\b", r"\borchid\w*", r"\bbonsai\b", r"\bpuzzle\b"], "/darky/", dict(price=[300, 3000], offers=2, min=10, icon="party", lead="Dárky pro maminku, které potěší: LEGO květiny, relaxační puzzle a hry na večery.", all=[r"\b(botanic\w*|kvet\w+|kytic\w*|ruze|orchid\w*|bonsai|puzzle)\b"])),
    ("darek-pro-tatu", "Dárek pro tátu", [r"\btechnic\b", r"\bicons\b", r"\bformule\b", r"\bstar wars\b", r"\bferrari\b", r"\bporsche\b", r"\bspeed champions\b", r"\bmodel\w* aut\w*", r"\brc\b"], "/darky/", dict(price=[600, None], offers=2, min=10, icon="party")),
    ("darek-pro-kamaradku", "Dárek pro kamarádku", [r"\bbotanic\w*", r"\bkvet\w+", r"\bfriends\b", r"\bpuzzle\b", r"\bkoralk\w*", r"\bsperk\w*"], "/darky/", dict(price=[150, 1200], offers=2, min=10, icon="party")),
    ("darek-pro-ucitelku", "Dárek pro učitelku", [r"\bpuzzle\b", r"\bspolecenska hra\b", r"\bkoralk\w*", r"\bsada\b"], "/darky/", dict(price=[100, 600], offers=3, min=10, icon="party", lead="Drobné dárky pro paní učitelku do 600 Kč: kreativní sady, hry a hlavolamy, které potěší i po škole.")),
]


def main():
    out = []
    for slug, h1, anyr, parent, o in T:
        rules = {}
        if anyr:
            rules["any"] = anyr
        for k in ("all", "none", "cat", "sex", "price", "age", "offers", "age_unknown"):
            if k in o:
                rules[k] = o[k]
        rec = {"slug": slug, "h1": h1, "parent": parent, "group": slug.split("/")[0] if slug.startswith("lego/") is False else "lego-" + slug.split("/")[1], "rules": rules,
               "min": o.get("min", 6), "index_min": o.get("index_min", max(o.get("min", 6) * 2, 12))}
        for k in ("hubs", "home", "icon", "lead", "title", "desc"):
            if k in o:
                rec[k] = o[k]
        out.append(rec)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(len(out), "landing records ->", OUT)


if __name__ == "__main__":
    main()
