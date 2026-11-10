"""Toy category tree, classifier, LEGO series, licences (characters), brands and age parsing.

The tree follows what Czech shoppers search (Marketing Miner, 9. 11. 2026): LEGO is by far the biggest topic (146k/month,
then Technic, Botanicals, Minecraft, Star Wars, Duplo…), then gifts by age ("dárek pro kluka 10 let"), characters
(Stitch, Bluey, Tlapková patrola, Minecraft) and classic categories (deskové hry, puzzle, plyšák, RC auta, panenky).

classify(rec) looks at the product title first (it is the most reliable signal across shops), then at the shop's own
category path; a veto list throws out everything that is not a toy (books, office supplies, pet food, prams…).
"""
import re
import unicodedata

I = re.I

# ------------------------------------------------------------------ tree
# slug: (name, parent, h1/title noun phrase, short blurb for cards)
TREE = {
    "lego": ("LEGO", None, "LEGO stavebnice", "Sety všech řad, od Duplo po Technic"),
    "stavebnice": ("Stavebnice", None, "Stavebnice", "Magnetické, Merkur, Cobi, Playmobil"),
    "stavebnice/magneticke": ("Magnetické stavebnice", "stavebnice", "Magnetické stavebnice", ""),
    "stavebnice/playmobil": ("Playmobil", "stavebnice", "Playmobil", ""),
    "stavebnice/kostky-a-kompatibilni": ("Kostky a kompatibilní stavebnice", "stavebnice", "Stavebnice kostky (Cobi, Cada, Sluban…)", ""),
    "stavebnice/kovove-a-technicke": ("Kovové a technické stavebnice", "stavebnice", "Kovové a technické stavebnice (Merkur, Seva, Cheva)", ""),
    "stavebnice/drevene": ("Dřevěné stavebnice a kostky", "stavebnice", "Dřevěné stavebnice a kostky", ""),
    "stavebnice/ostatni": ("Další stavebnice", "stavebnice", "Stavebnice pro děti", ""),
    "panenky": ("Panenky", None, "Panenky a doplňky", "Barbie, miminka, domečky a kočárky"),
    "panenky/barbie-a-modelky": ("Barbie a módní panenky", "panenky", "Barbie a módní panenky", ""),
    "panenky/miminka": ("Panenky miminka", "panenky", "Panenky miminka (Baby Born a další)", ""),
    "panenky/domecky": ("Domečky pro panenky", "panenky", "Domečky pro panenky", ""),
    "panenky/kocarky": ("Kočárky pro panenky", "panenky", "Kočárky pro panenky", ""),
    "panenky/doplnky": ("Doplňky pro panenky", "panenky", "Oblečky a doplňky pro panenky", ""),
    "panenky/ostatni": ("Další panenky", "panenky", "Panenky pro holčičky", ""),
    "auta-a-vlacky": ("Auta, vláčky a letadla", None, "Autíčka, vláčky a letadla", "Autíčka, autodráhy, Bruder i vláčkodráhy"),
    "auta-a-vlacky/autodrahy": ("Autodráhy a garáže", "auta-a-vlacky", "Autodráhy, garáže a parkoviště", ""),
    "auta-a-vlacky/vlacky": ("Vláčky a vláčkodráhy", "auta-a-vlacky", "Vláčky a vláčkodráhy", ""),
    "auta-a-vlacky/stroje-a-traktory": ("Stavební stroje a traktory", "auta-a-vlacky", "Stavební stroje, traktory a nákladní auta", ""),
    "auta-a-vlacky/letadla-a-lode": ("Letadla, lodě a vrtulníky", "auta-a-vlacky", "Letadla, lodě a vrtulníky", ""),
    "auta-a-vlacky/auticka": ("Autíčka", "auta-a-vlacky", "Autíčka pro děti", ""),
    "rc-modely": ("Na dálkové ovládání", None, "Hračky na dálkové ovládání", "RC auta, drony a roboti na ovladač"),
    "rc-modely/auta": ("RC auta", "rc-modely", "Auta na dálkové ovládání", ""),
    "rc-modely/drony": ("Drony a letadla", "rc-modely", "Drony a RC letadla", ""),
    "rc-modely/ostatni": ("Další RC hračky", "rc-modely", "RC hračky na ovladač", ""),
    "plysaci": ("Plyšáci", None, "Plyšáci a plyšové hračky", "Mazlíci od malých po obří"),
    "spolecenske-hry": ("Společenské hry", None, "Deskové a společenské hry", "Deskovky, karetní a párty hry"),
    "spolecenske-hry/deskove": ("Deskové hry", "spolecenske-hry", "Deskové hry", ""),
    "spolecenske-hry/karetni": ("Karetní hry", "spolecenske-hry", "Karetní hry", ""),
    "spolecenske-hry/party": ("Párty a vědomostní hry", "spolecenske-hry", "Párty a vědomostní hry", ""),
    "spolecenske-hry/detske": ("Hry pro nejmenší", "spolecenske-hry", "Společenské hry pro malé děti", ""),
    "spolecenske-hry/hlavolamy": ("Hlavolamy a logické hry", "spolecenske-hry", "Hlavolamy a logické hry", ""),
    "spolecenske-hry/doplnky": ("Doplňky k hrám", "spolecenske-hry", "Rozšíření a doplňky ke společenským hrám", ""),
    "sberatelske-karty": ("Sběratelské karty", None, "Sběratelské karty", "Pokémon, Magic, Lorcana, One Piece"),
    "puzzle": ("Puzzle", None, "Puzzle", "Pro děti i dospělé, 3D i dřevěná"),
    "puzzle/detske": ("Puzzle pro děti", "puzzle", "Puzzle pro děti", ""),
    "puzzle/pro-dospele": ("Puzzle pro dospělé", "puzzle", "Puzzle pro dospělé (500 a více dílků)", ""),
    "puzzle/3d": ("3D puzzle", "puzzle", "3D puzzle", ""),
    "figurky-a-zviratka": ("Figurky a zvířátka", None, "Figurky a zvířátka", "Schleich, akční hrdinové, dinosauři"),
    "figurky-a-zviratka/akcni": ("Akční figurky", "figurky-a-zviratka", "Akční figurky a hrdinové", ""),
    "figurky-a-zviratka/zviratka": ("Zvířátka a farma", "figurky-a-zviratka", "Figurky zvířátek", ""),
    "figurky-a-zviratka/dinosauri": ("Dinosauři", "figurky-a-zviratka", "Dinosauři hračky", ""),
    "figurky-a-zviratka/sberatelske": ("Sběratelské figurky", "figurky-a-zviratka", "Sběratelské figurky (Funko Pop a další)", ""),
    "kreativni": ("Kreativní hračky", None, "Kreativní a výtvarné hračky", "Sady na tvoření, malování, modelína"),
    "kreativni/sady": ("Kreativní sady", "kreativni", "Kreativní sady pro děti", ""),
    "kreativni/malovani": ("Malování a kreslení", "kreativni", "Malování a kreslení pro děti", ""),
    "kreativni/modelina-a-sliz": ("Modelína, písek a sliz", "kreativni", "Modelína, kinetický písek a sliz", ""),
    "kreativni/koralky-a-sperky": ("Korálky a šperky", "kreativni", "Korálky a výroba šperků", ""),
    "naucne": ("Naučné a STEM", None, "Naučné a vzdělávací hračky", "Experimenty, roboti, mikroskopy"),
    "naucne/experimenty": ("Experimenty a věda", "naucne", "Vědecké sady a experimenty", ""),
    "naucne/roboti-a-programovani": ("Roboti a programování", "naucne", "Roboti a programovací hračky", ""),
    "naucne/ostatni": ("Hrou k učení", "naucne", "Naučné hračky", ""),
    "pro-nejmensi": ("Pro nejmenší", None, "Hračky pro miminka a batolata", "Chrastítka, motorické hračky, do vany"),
    "pro-nejmensi/chrastitka-a-kousatka": ("Chrastítka a kousátka", "pro-nejmensi", "Chrastítka a kousátka", ""),
    "pro-nejmensi/do-vany": ("Hračky do vany", "pro-nejmensi", "Hračky do vany", ""),
    "pro-nejmensi/motoricke": ("Motorické a vkládačky", "pro-nejmensi", "Motorické hračky a vkládačky", ""),
    "pro-nejmensi/hraci-deky": ("Hrací deky a hrazdičky", "pro-nejmensi", "Hrací deky a hrazdičky", ""),
    "pro-nejmensi/tahaci-a-odstrkovadla": ("Tahací hračky a chodítka", "pro-nejmensi", "Tahací hračky a chodítka", ""),
    "pro-nejmensi/ostatni": ("Pro miminka", "pro-nejmensi", "Hračky pro miminka", ""),
    "hrajeme-si-na": ("Hrajeme si na…", None, "Hračky na hraní rolí", "Kuchyňky, nářadí, doktor, obchod"),
    "hrajeme-si-na/kuchynky": ("Kuchyňky a nádobí", "hrajeme-si-na", "Dětské kuchyňky a nádobíčko", ""),
    "hrajeme-si-na/naradi": ("Nářadí a dílna", "hrajeme-si-na", "Dětské nářadí a ponky", ""),
    "hrajeme-si-na/doktor-a-povolani": ("Doktor a povolání", "hrajeme-si-na", "Hrajeme si na doktora a povolání", ""),
    "hrajeme-si-na/obchod-a-domacnost": ("Obchod a domácnost", "hrajeme-si-na", "Obchod, pokladna a domácnost", ""),
    "hrajeme-si-na/krasa": ("Kadeřnice a krása", "hrajeme-si-na", "Dětská kosmetika na hraní a kadeřnice", ""),
    "hrajeme-si-na/zbrane-a-rytiri": ("Rytíři, piráti a pistole", "hrajeme-si-na", "Meče, pistole a výbava rytířů", ""),
    "venku": ("Na ven a na zahradu", None, "Hračky na zahradu a ven", "Do vody, na písek, odrážedla"),
    "venku/do-vody": ("Do vody a bazény", "venku", "Hračky do vody a bazény", ""),
    "venku/na-pisek": ("Na písek", "venku", "Hračky na písek", ""),
    "venku/odrazedla": ("Odrážedla a tříkolky", "venku", "Odrážedla a tříkolky", ""),
    "venku/zahrada": ("Zahradní hry a domečky", "venku", "Zahradní hry, domečky a skluzavky", ""),
    "venku/ostatni": ("Hry venku", "venku", "Hračky na ven", ""),
    "elektronika": ("Interaktivní hračky", None, "Interaktivní hračky a dětská elektronika", "Roboti, mazlíčci, fotoaparáty"),
    "kostymy-a-party": ("Kostýmy a party", None, "Dětské kostýmy a party", "Karneval, Halloween, oslavy"),
    "drevene": ("Dřevěné hračky", None, "Dřevěné hračky", "Montessori a klasika ze dřeva"),
    "hudebni": ("Hudební hračky", None, "Hudební hračky a nástroje", "Bubínky, xylofony, klávesy"),
    "fan-darky": ("Dárky pro fanoušky", None, "Merch a dárky pro fanoušky", "Hrnky, lampičky a doplňky z filmů a her"),
}
TOP = [k for k, v in TREE.items() if v[1] is None]

# ------------------------------------------------------------------ veto: not a toy
PET_PATH = re.compile(r"Pro mazlíčky|\| Pes \||\| Kočka \||pro psy|pro kočky|Dárkové poukazy", I)
VETO_PATH = re.compile(r"^(E-knihy|Knihy|Kniha)\b|Kočárky(?! pro panenky)|Autosedačk|Kojení|Krmení|Přebalov|Dudlík|"
                       r"Ložní prádlo|Dětské postýlky|Péče o|Oblečení|Oděvy|Obuv|Kancelář|Tonery|Psací potřeby|Školní potřeby|Diáře|Náhradní díly|"
                       r"Kosmetika a parfém|Drogerie|Nábytek", I)
VETO_TITLE = re.compile(r"\b(kočárek(?! pro panenky| pro panenku| pro panny| pro bábiky)|autosedačk|pamlsk|granule|obojek|vodítko|"
                        r"tričko|mikina|ponožky|pyžamo|kšiltovk|čepice|legíny|tepláky|bunda|"
                        r"e-?kniha|audiokniha|toner|cartridge|šanon|kalendář 20\d\d|diář|"
                        r"odsávačka|prsní|kojenecká lahev|dudlík|plenk|přebalovací|"
                        r"postýlk|matrace|deka do kočárku|nosítko|chůvička|"
                        r"talíř|ubrous|kelímk|ubrus|dortov\w* svíčk|svíčka dortov|brčk|okenní fóli|samolepky na zeď|zástěra|"
                        r"hračka pro (psy|psa|kočky|kočku)|pro psy|pro kočky|dárkový poukaz|cukrová vata|bonbon|lízátk|čokolád)", I)

# ------------------------------------------------------------------ title rules (ordered, first match wins)
T = lambda s: re.compile(s, I)
TITLE_RULES = [
    ("sberatelske-karty", T(r"(booster|starter deck|elite trainer|pokémon tcg|pokemon tcg|magic: the gathering|mtg\b|lorcana|one piece card|yu-?gi-?oh|"
                            r"flesh and blood|digimon card|dragon ball super card|sběratelsk\w* kart|binder|sleeves|obaly na karty|deck box|kartičk)")),
    ("lego", T(r"\blego\b")),
    ("stavebnice/playmobil", T(r"\bplaymobil\b")),
    ("puzzle/3d", T(r"\b3d puzzle|puzzle 3d|puzzleball|3d model\w* puzzle")),
    ("puzzle/pro-dospele", T(r"\bpuzzle\b.*\b(500|750|1000|1 000|1500|1 500|2000|2 000|3000|4000|5000|9000|18000)\b|\b(500|1000|1500|2000|3000)\s*d(ílk|il)\w*.*puzzle")),
    ("puzzle/detske", T(r"\bpuzzle\b|skládačk|\bpexeso\b")),
    ("stavebnice/magneticke", T(r"magnetick\w* stavebnic|magformers|connetix|geomag|magnetic tiles|magnetick\w* (kostky|dílky)|magnetick\w* destičk")),
    ("stavebnice/kovove-a-technicke", T(r"\bmerkur\b|\bseva\b|\bcheva\b|eitech|boffin|meccano")),
    ("stavebnice/kostky-a-kompatibilni", T(r"\bcobi\b|\bcada\b|\bsluban\b|\bblue brixx|\bbluebrixx|mould king|\bqman\b|\bmega bloks|mega construx|clics|stavebnice.*kostk|kostky.*stavebnic")),
    ("rc-modely/drony", T(r"\bdron\b|\bdrony\b|kvadrokopt|quadcopter|rc letadl|rc vrtul|vrtulník na (dálkové|ovlád)")),
    ("rc-modely/auta", T(r"\brc\b.*(auto|auta|bagr|tank|truck|buggy|monster|crawler|nákladn)|(auto|auta|bagr|tank|traktor)\b.*(na dálkové ovládání|\brc\b|na ovladač)|\bRTR\b")),
    ("rc-modely/ostatni", T(r"na dálkové ovládání|\brc\b(?!\w)|na ovladač")),
    ("sberatelske-karty", T(r"\bpokémon\b.*\b(karty|kartičky|booster|tin|blister|collection)\b")),
    ("figurky-a-zviratka/sberatelske", T(r"\bfunko\b|\bpop!|\bbitty pop|\bkidrobot|sběratelsk\w* figurk|blind box|labubu|smiski|sonny angel")),
    ("panenky/domecky", T(r"domeček pro panenky|domek pro panenky|domeček pro panenku|dům pro panenky|dreamhouse|domeček s panenk|panenkovský domeček")),
    ("panenky/kocarky", T(r"kočárek pro panenk|kočárek pro panny|kočárky pro panenk|kočík pre bábik|kočárek pro panenku")),
    ("panenky/doplnky", T(r"(oblečk|oblečení|šaty|botičky|postýlka|sedačka|nosítko|doplňky|nočník|lahvička|židlička|vanička)\b.*\b(pro panenk|pro panenky|panenky|panenek|baby born)|\bpro panenky\b")),
    ("panenky/barbie-a-modelky", T(r"\bbarbie\b|\bmonster high\b|\brainbow high\b|\bl\.?o\.?l\.? surprise|\bbratz\b|\bpolly pocket|\bdisney princezn|\benchantimals|\bsteffi\b|\bevi love|\bmódní panenk")),
    ("panenky/miminka", T(r"\bbaby born\b|\bbaby annabell|\bpanenk\w* miminko|\bmiminko\b.*panenk|\bpanenka bábätko|\bnenuco|\bcry babies|\breborn|\bpanenka.*(miminko|bobas|batole)")),
    ("panenky/ostatni", T(r"\bpanenk\w*|\bpanna\b|\bbábik")),
    ("auta-a-vlacky/autodrahy", T(r"autodráh|\bgaráž\b|parkovací dům|\bparkoviště\b|závodní dráh|hot wheels.*(dráh|set|track)|carrera")),
    ("auta-a-vlacky/vlacky", T(r"vláčkodráh|\bvláček|\bvláčky\b|\bvlak\b|\blokomotiv|koleje|\bbrio\b.*(vlak|dráha)|tomáš a přátelé|thomas & friends")),
    ("auta-a-vlacky/stroje-a-traktory", T(r"\bbruder\b|\btraktor|\bbagr\b|\bnakladač|\bjeřáb\b|\bbuldozer|\bsklápěč|\bdomíchávač|\bkombajn|\bnákladní auto|\bkamion|\bstavební stroj|\bsiku\b.*(farm|trakt)")),
    ("auta-a-vlacky/letadla-a-lode", T(r"\bletadlo\b|\bletadla\b|\bletiště|\bvrtulník|\bhelikopt|\bloď\b|\blodě\b|\blodička|\bplachetnic|\bponorka|\braketa\b")),
    ("auta-a-vlacky/auticka", T(r"\bautíčk|\bauto\b|\bauta\b|\bhot wheels|\bmatchbox|\bsiku\b|\bmajorette|\bwelly\b|\bbburago|\bmaisto\b|\bkovový model|\bmodel auta|\bhasičsk\w* auto|\bpolicejní auto|\bsanitk|1:(18|24|32|36|43|64)\b")),
    ("figurky-a-zviratka/dinosauri", T(r"\bdinosaur|\bdino\b|\bt-?rex|\btyranosaur|\bjurassic")),
    ("figurky-a-zviratka/zviratka", T(r"\bschleich\b|\bpapo\b|\bcollecta\b|\bfigurka (koně|kůň|psa|zvíř)|\bzvířátk|\bfarma\b|\bkoník\b|\bstáj\b|\bzoo\b")),
    ("figurky-a-zviratka/akcni", T(r"akční figurk|\bfigurka\b|\bfigurky\b|\bsuperhrdin|\btransformers\b|\bspider-?man\b.*figur|\bavengers\b|\bnerf\b")),
    ("plysaci", T(r"\bplyš|\bplyšov|\bmazlík|\bmuchláček|\bjellycat\b|\bsquishmallow|\bteddy|\bmedvídek\b|\bmaskot\b|\bpeluche")),
    ("spolecenske-hry/doplnky", T(r"rozšíření|\bexpansion\b|\bkostky\b.*(d6|d20|rpg)|\bplayset\b.*(hra)|herní podložk|\bplaymat\b|insert do hry|organizér do hry")),
    ("spolecenske-hry/karetni", T(r"karetní hra|\bkarty\b.*hra|hrací karty|\bdobble\b|\bčerný petr\b|\bprší\b|\buno\b|\bkanasta|\bpoker\b|\bdixit\b.*karty|\bspeed cups|\bkocouří")),
    ("spolecenske-hry/party", T(r"párty hra|party hra|vědomostní|\bkvíz|\bquiz|\bactivity\b|\bpictionary|\bkrycí jména|\bdixit\b|\bpiškvork|\bscrabble|\bbang!|\bpřesmyčk")),
    ("spolecenske-hry/hlavolamy", T(r"hlavolam|rubik|\blogická hra|\blogik\b|\bsmart games|\bkostka\b.*\b(3x3|4x4|speed)|\bspeedcub|\btangram|\bsudoku")),
    ("spolecenske-hry/detske", T(r"\bčlověče,? nezlob|\bpexeso|\bdomino|\bkačenk\w* hra|\bhra pro (nejmenší|děti)|\bdětská hra|\bhra\b.*\bod [3-5] let")),
    ("spolecenske-hry/deskove", T(r"desková hra|\bstrategická hra|\brodinná hra|\bspolečenská hra|\bdeskovk|\bkooperativní hra|\bhra\b|\bcatan|\bcarcassonne|\bticket to ride|\bmonopoly|\bdobyvatel|\bazul\b|\bcodenames")),
    ("naucne/roboti-a-programovani", T(r"\brobot\w*\b.*(programov|stavebnic|kód|code)|programovac|\bmicro:bit|\barduino|\bmbot\b|\bozobot|\bbee-?bot|\bcoding")),
    ("naucne/experimenty", T(r"experiment|\bvědeck|\bchemick|\bmikroskop|\bdalekohled|\bteleskop|\bkrystal\w* (sada|pěstov)|\bsopka\b|\bfyzik|\bkouzelnick\w* (sada|souprava)|\bkouzla\b")),
    ("pro-nejmensi/chrastitka-a-kousatka", T(r"chrastítk|kousátk|\bkousac|\bmuchláček")),
    ("pro-nejmensi/do-vany", T(r"do vany|do vody pro (děti|nejmenší)|\bkačenk\w* do|stříkací (hračk|zvířátk)|koupací")),
    ("pro-nejmensi/hraci-deky", T(r"hrací dek|hrazdičk|hrací podložka pro (miminka|nejmenší)|\bhrací centrum pro miminka|hrací hrazd")),
    ("pro-nejmensi/tahaci-a-odstrkovadla", T(r"tahací|\bchodítk|\bodstrkovadl|\bposuvn\w* hračk|na tahání")),
    ("pro-nejmensi/motoricke", T(r"motorick|\bvkládačk|\bnavlékač|\bpřevlékač|\bkostka\b.*aktivit|\bactivity (cube|kostka)|\bspirál\w* s kuličk|\bmontessori")),
    ("hrajeme-si-na/kuchynky", T(r"kuchyňk|\bnádobíčk|\bdětsk\w* (nádobí|kuchy)|\bpotraviny na hraní|\bdřevěn\w* (ovoce|zelenin|potravin)|\bkrájení|\bčajov\w* souprava|\bvařič\b|\bkávovar\b.*(hrač|dětsk)")),
    ("hrajeme-si-na/naradi", T(r"\bponk\b|\bdílna\b|\bnářadí\b|\bvrtačk\w*\b.*(hrač|dětsk)|\bkufřík s nářadím|\bdětsk\w* (vrtačka|šroubovák|kladivo)")),
    ("hrajeme-si-na/doktor-a-povolani", T(r"\bdoktor|\blékař|\bveterinář|\bpolicist|\bhasič\w* (sada|helma|výbav)|\bpovolání|\bstetoskop|\bkufřík (doktor|lékař)")),
    ("hrajeme-si-na/obchod-a-domacnost", T(r"\bpokladn|\bobchod\w*\b.*(hrač|dětsk|na hraní)|\bnákupní vozík|\bvysavač\w*\b.*(dětsk|hrač)|\bžehličk|\bpračk\w*\b.*(dětsk|hrač)|\búklidov\w* set")),
    ("hrajeme-si-na/krasa", T(r"\bkadeřn|\bčesací hlav|\bdětsk\w* (líčidl|kosmetik)|\bmake-?up\w* (set|sada)|\blaky na nehty pro|\bmanikúr")),
    ("hrajeme-si-na/zbrane-a-rytiri", T(r"\bmeč\b|\bštít\b|\brytíř|\bpirát|\bpistol|\bpuška|\bsamopal|\bkulovnic|\bbambitk|\bluk a šíp|\bvodní pistol|\bnerf\b|\bblaster|\bkuše\b")),
    ("venku/do-vody", T(r"\bbazén|\bnafukovac|\bkruh do vody|\brukávky|\bvodní (dělo|pistol|hrací|svět)|\bpodvodní|\bplav")),
    ("venku/na-pisek", T(r"\bna písek|\bbábovk|\bpískoviště|\bkyblík|\blopatka\b|\bhrabičky")),
    ("venku/odrazedla", T(r"\bodrážedl|\btříkolk|\bkoloběžk|\bodrážecí|\bjezdítk|\bhoupací kůň|\bhoupací zvířátk|\bkolo bez pedál")),
    ("venku/zahrada", T(r"\bskluzavk|\bhoupačk|\bprolézačk|\bdomeček na zahrad|\bzahradní domeček|\btrampolín|\bstan\b|\bteepee|\bkuželky|\bpétanque|\bpetanque|\bbadminton|\bfrisbee|\bmölkky")),
    ("venku/ostatni", T(r"\bbublifuk|\bbubliny|\bdrak\b.*(létací|pouštění)|\blétající drak|\bkřídy na chodník|\bchůdy|\bskákací")),
    ("kreativni/modelina-a-sliz", T(r"\bmodelín|\bplastelín|\bkinetick\w* písek|\bsliz\b|\bslime\b|\bplay-?doh|\bmodelovací hmot|\bkeramick\w* hlína|\bmodurit")),
    ("kreativni/koralky-a-sperky", T(r"\bkorálk|\bnavlékací|\bnáramk\w*\b.*(výrob|sada)|\bšperk\w*\b.*(výrob|sada|tvoř)|\bzažehlovací|\bhama\b|\baqua ?beads")),
    ("kreativni/malovani", T(r"\bomalovánk|\bmalování|\bmalovací|\bvodovk|\bfixy\b|\bpastelk|\bkřídy\b|\bkreslicí|\btabul\w*\b.*(magnet|kresl|dětsk)|\bmagnetick\w* tabul|\bmalba podle čísel|\bmalování podle|\bkreslení")),
    ("kreativni/sady", T(r"kreativní|\btvoření|\bvyrob si|\bsada na\b.*(výrob|tvoř|šit|pletení)|\bdiamantov\w* malov|\bškrabací obráz|\bnažehl|\bvyšívání|\bpletení|\bmýdla\b.*výrob|\bsvíčk\w* výrob")),
    ("hudebni", T(r"\bxylofon|\bbubín|\bbuben|\bklávesy|\bpiano\b|\bkytar|\bfoukací|\bharmonik|\bhudební (hračk|nástroj|sada)|\bmikrofon|\bkaraoke|\bflétn|\btrubk|\bčinel")),
    ("kostymy-a-party", T(r"\bkostým|\bpřevlek|\bmaska\b|\bparoka|\bkarneval|\bhalloween|\bbalón|\bbalon|\bfrkačk|\bparty\b|\bkonfet|\bnarozeninov\w* (svíčk|dekor)|\bdorty?\b.*(zápich|dekor)")),
    ("elektronika", T(r"\binteraktivní|\btamagotchi|\bfurby|\bdětsk\w* (fotoaparát|kamera|hodinky|notebook|tablet|vysílačk)|\bvysílačky|\bhovorka|\btonies|\btoniebox|\bkouzelné čtení|\belektronick\w* (hra|hračk)|\bmluvící|\bsvítící\b.*projekt|\blampička\b.*projekt")),
    ("drevene", T(r"\bdřevěn")),
    ("fan-darky", T(r"\bhrnek\b|\bhrnky\b|\bsklenice\b|\blahev\b|\bláhev\b|\blampa\b|\blampička|\bklíčenk|\bplakát|\bpolštář\b|\bbatoh\b|\bpenál\b|\bpeněženk|\bzápisník|\bpodtácky|\bdeka\b|\bosušk|\bovladač\b.*(stojan|držák)")),
    ("stavebnice/ostatni", T(r"\bstavebnic")),
    ("naucne/ostatni", T(r"\bnauč|\bvzdělávací|\bškola hrou|\bpočítání|\babeceda|\bglóbus|\bmapa\b|\bhodiny\b.*učení|\bslabik|\bkvído")),
    ("pro-nejmensi/ostatni", T(r"\bpro miminka\b|\bpro nejmenší\b|\bod narození\b|\b0\+|\bbaby\b")),
]

# shop category paths -> category (used when the title does not decide)
PATH_RULES = [
    ("sberatelske-karty", T(r"Sběratelské kartičky|Sběratelské karty")),
    ("lego", T(r"LEGO")),
    ("stavebnice/playmobil", T(r"Playmobil")),
    ("puzzle/3d", T(r"3D puzzle")),
    ("puzzle/detske", T(r"Puzzle|Hlavolamy a puzzle")),
    ("stavebnice/magneticke", T(r"Magnetické")),
    ("stavebnice/drevene", T(r"Dřevěné stavebnice|Dřevěné kostky")),
    ("stavebnice/ostatni", T(r"Stavebnic")),
    ("rc-modely/ostatni", T(r"RC modely|dálkové ovládání")),
    ("panenky/doplnky", T(r"Doplňky pro panenky")),
    ("panenky/ostatni", T(r"Panenky")),
    ("auta-a-vlacky/stroje-a-traktory", T(r"Stavební stroje|Traktory|Nákladní auta|Kombajny|BWORLD")),
    ("auta-a-vlacky/autodrahy", T(r"Autodráhy")),
    ("auta-a-vlacky/vlacky", T(r"Vláčky|Vlaky")),
    ("auta-a-vlacky/auticka", T(r"Auta vlaky|Auta a autíčka|Autíčka|Osobní auta|Autíčka a doprava")),
    ("figurky-a-zviratka/zviratka", T(r"Zvířata|Figurky a zvířátka > Zvířátka")),
    ("figurky-a-zviratka/akcni", T(r"Figurky|Postavy z TV")),
    ("plysaci", T(r"Plyšov|Plyšáci")),
    ("spolecenske-hry/karetni", T(r"Karetní hry")),
    ("spolecenske-hry/party", T(r"Párty hry|Vědomostní")),
    ("spolecenske-hry/detske", T(r"Dětské hry")),
    ("spolecenske-hry/doplnky", T(r"Příslušenství ke společenským hrám")),
    ("spolecenske-hry/deskove", T(r"Společenské hry|Stolní hry|Deskové hry|Strategické hry|Rodinné hry|^Hry")),
    ("naucne/ostatni", T(r"Kreativní a naučné hračky > Škola hrou|Naučné|Kvído")),
    ("kreativni/sady", T(r"Kreativní|Výtvarné|Hračky a tvoření")),
    ("pro-nejmensi/ostatni", T(r"Hračky pro nejmenší|BABY|Chrastítka|Motorické hračky|Hračky do kočárku|Hrací deky")),
    ("venku/odrazedla", T(r"Odrážedla")),
    ("venku/ostatni", T(r"Na ven a sport|Hračky na zahradu|Do vody")),
    ("elektronika", T(r"Dětská elektronika|Interaktivní")),
    ("hrajeme-si-na/doktor-a-povolani", T(r"Dětské role a profese|Hrajeme si na|Povolání")),
    ("kostymy-a-party", T(r"Kostýmy|Party")),
    ("drevene", T(r"Dřevěné")),
    ("fan-darky", T(r"Merchandise|Merch|Sběratelství")),
]

# ------------------------------------------------------------------ LEGO series
LEGO_SERIES = [
    ("technic", "LEGO Technic", r"technic"), ("duplo", "LEGO DUPLO", r"duplo"), ("city", "LEGO City", r"city"),
    ("friends", "LEGO Friends", r"friends"), ("star-wars", "LEGO Star Wars", r"star wars"), ("ninjago", "LEGO Ninjago", r"ninjago"),
    ("minecraft", "LEGO Minecraft", r"minecraft"), ("harry-potter", "LEGO Harry Potter", r"harry potter"),
    ("creator", "LEGO Creator", r"creator"), ("icons", "LEGO Icons", r"icons|creator expert"),
    ("botanicals", "LEGO Botanicals (květiny)", r"botanical|botanicals|květin|kytic|orchidej|bonsaj|bonsai|růž"),
    ("speed-champions", "LEGO Speed Champions", r"speed champions"), ("marvel", "LEGO Marvel", r"marvel|avengers|spider-?man"),
    ("dc", "LEGO DC Batman", r"\bdc\b|batman"), ("disney", "LEGO Disney", r"disney|frozen|ledové království|wish"),
    ("classic", "LEGO Classic", r"classic"), ("ideas", "LEGO Ideas", r"ideas"), ("architecture", "LEGO Architecture", r"architecture"),
    ("art", "LEGO Art", r"\bart\b"), ("jurassic-world", "LEGO Jurassic World", r"jurassic"), ("sonic", "LEGO Sonic", r"sonic"),
    ("super-mario", "LEGO Super Mario", r"super mario|mario"), ("dreamzzz", "LEGO DreamZzz", r"dreamzzz"),
    ("fortnite", "LEGO Fortnite", r"fortnite"), ("animal-crossing", "LEGO Animal Crossing", r"animal crossing"),
    ("gabby", "LEGO Gabbyin domeček", r"gabby"), ("pan-prstenu", "LEGO Pán prstenů", r"pán prstenů|lord of the rings|lotr"),
    ("wednesday", "LEGO Wednesday", r"wednesday"), ("minifigures", "LEGO Minifigurky", r"minifig"),
    ("formule-1", "LEGO Formule 1", r"\bf1\b|formule 1|formula 1"), ("bluey", "LEGO Bluey", r"bluey"),
    ("stitch", "LEGO Stitch", r"stitch"), ("pokemon", "LEGO Pokémon", r"pok[eé]mon"), ("adventni-kalendar", "LEGO adventní kalendář", r"adventní kalendář|advent"),
]
LEGO_SERIES_RX = [(s, n, re.compile(r"lego\W*(" + rx + r")|(" + rx + r").*\blego|\blego\b.*\b(" + rx + r")", I)) for s, n, rx in LEGO_SERIES]

# ------------------------------------------------------------------ licences / characters (cross-category pages /hracky-<slug>/)
LICENCES = [
    ("stitch", "Stitch", r"\bstitch\b|lilo"), ("bluey", "Bluey", r"\bbluey\b"), ("tlapkova-patrola", "Tlapková patrola", r"tlapková patrola|paw patrol"),
    ("minecraft", "Minecraft", r"minecraft"), ("pokemon", "Pokémon", r"pok[eé]mon|pikachu"), ("harry-potter", "Harry Potter", r"harry potter|bradavic|hogwarts"),
    ("ledove-kralovstvi", "Ledové království", r"ledové království|\bfrozen\b|\belsa\b"), ("spiderman", "Spider-Man", r"spider-?man|spidey"),
    ("star-wars", "Star Wars", r"star wars|mandalorian|baby yoda|grogu"), ("barbie", "Barbie", r"\bbarbie\b"), ("hot-wheels", "Hot Wheels", r"hot wheels"),
    ("prasatko-peppa", "Prasátko Peppa", r"peppa"), ("krtek", "Krtek", r"\bkrtek\b|krteček|krtečk"), ("gabbyin-domecek", "Gabbyin domeček", r"gabby"),
    ("sonic", "Sonic", r"\bsonic\b"), ("super-mario", "Super Mario", r"super mario|\bmario\b"), ("disney-princezny", "Disney princezny", r"princezn\w* disney|disney princ"),
    ("auta-disney", "Auta (Disney Cars)", r"\bmcqueen|disney cars|\bblesk mcqueen"), ("dinosauri", "Dinosauři", r"dinosaur|jurassic|t-?rex"),
    ("labubu", "Labubu", r"labubu"), ("fortnite", "Fortnite", r"fortnite"), ("stranger-things", "Stranger Things", r"stranger things|demogorgon"),
    ("hello-kitty", "Hello Kitty", r"hello kitty|kuromi|my melody"), ("marvel", "Marvel", r"\bmarvel\b|avengers|iron man|hulk\b"),
    ("batman", "Batman", r"\bbatman\b"), ("transformers", "Transformers", r"transformers"), ("my-little-pony", "My Little Pony", r"my little pony"),
    ("wednesday", "Wednesday", r"wednesday"), ("jednorozci", "Jednorožci", r"jednorož|unicorn"), ("ninjago", "Ninjago", r"ninjago"),
    ("mimoni", "Mimoni", r"mimoň|minion"), ("pat-a-mat", "Pat a Mat", r"pat a mat"), ("tomas-a-pratele", "Tomáš a přátelé", r"tomáš a přátelé|thomas"),
    ("kapybara", "Kapybara", r"kapybar|capybar"), ("squishmallows", "Squishmallows", r"squishmallow"),
    ("bakugan", "Bakugan", r"bakugan"), ("lol-surprise", "L.O.L. Surprise", r"l\.?o\.?l\.? surprise|\blol surprise"), ("rainbow-high", "Rainbow High", r"rainbow high"),
    ("nerf", "Nerf", r"\bnerf\b"), ("gravitrax", "GraviTrax", r"gravitrax"), ("tonies", "Tonies", r"\btonies\b|toniebox"), ("monster-high", "Monster High", r"monster high"),
    ("roblox", "Roblox", r"\broblox"), ("five-nights-at-freddys", "Five Nights at Freddy's", r"five nights|\bfnaf\b"), ("kpop-demon-hunters", "K-Pop Demon Hunters", r"k-?pop demon hunters|demon hunters"),
    ("dragon-ball", "Dragon Ball", r"dragon ball"), ("naruto", "Naruto", r"\bnaruto\b"), ("cocomelon", "Cocomelon", r"cocomelon"), ("spidey", "Spidey a jeho úžasní přátelé", r"\bspidey\b"),
    ("kuromi", "Kuromi a My Melody", r"\bkuromi\b|my melody"), ("pikachu", "Pikachu", r"\bpikachu\b"), ("baby-born", "Baby Born", r"baby born"), ("polly-pocket", "Polly Pocket", r"polly pocket"),
    ("hello-kitty-friends", "Sanrio", r"\bsanrio\b|cinnamoroll"), ("bing", "Bing", r"\bbing\b"), ("sam-hasic", "Požárník Sam", r"pozarnik sam|hasic sam"), ("masha-medved", "Máša a medvěd", r"\bmasa a medved|masha"),
]
LICENCES_RX = [(s, n, re.compile(rx, I)) for s, n, rx in LICENCES]

# ------------------------------------------------------------------ brands
BRAND_ALIAS = {
    "lego duplo": "LEGO", "lego": "LEGO", "lego technic": "LEGO", "lego city": "LEGO", "lego friends": "LEGO", "lego star wars": "LEGO",
    "lego ninjago": "LEGO", "lego creator": "LEGO", "lego minecraft": "LEGO", "lego harry potter": "LEGO", "lego icons": "LEGO",
    "alltoys halsall": "Alltoys", "alltoys intex": "Intex", "mga": "MGA Entertainment", "mga entertainment": "MGA Entertainment",
    "spin master": "Spin Master", "spinmaster": "Spin Master", "hasbro gaming": "Hasbro", "hasbro": "Hasbro", "mattel": "Mattel",
    "mattel games": "Mattel", "ravensburger": "Ravensburger", "schleich": "Schleich", "playmobil": "Playmobil", "bruder": "Bruder",
    "dino toys": "Dino Toys", "dino": "Dino Toys", "teddies": "Teddies", "rappa": "Rappa", "albi": "Albi", "mindok": "Mindok",
    "melissa & doug": "Melissa & Doug", "melissa and doug": "Melissa & Doug", "smoby": "Smoby", "simba": "Simba", "zapf creation": "Zapf Creation",
    "zapf": "Zapf Creation", "fisher-price": "Fisher-Price", "fisher price": "Fisher-Price", "vtech": "VTech", "clementoni": "Clementoni",
    "trefl": "Trefl", "educa": "Educa", "djeco": "Djeco", "janod": "Janod", "hape": "Hape", "woody": "Woody", "bigjigs": "Bigjigs",
    "bigjigs toys": "Bigjigs", "small foot": "small foot", "goki": "Goki", "lena": "Lena", "wader": "Wader", "siku": "Siku",
    "funko": "Funko", "funko pop!": "Funko", "the pokémon company": "Pokémon", "pokemon": "Pokémon", "pokémon": "Pokémon",
    "jellycat": "Jellycat", "squishmallows": "Squishmallows", "kazoo": "Kazoo", "geomag": "Geomag", "cobi": "Cobi",
    "efko": "Efko", "dromader": "Dromader", "seva": "Seva", "merkur": "Merkur", "lexibook": "Lexibook",
}
BAD_BRANDS = {"", "none", "null", "neuvedeno", "ostatní", "ostatni", "nezařazeno", "bez značky", "noname", "no name", "-", "n/a"}


def clean(s):
    return re.sub(r"\s+", " ", re.sub(r"[®™©]", "", s or "")).strip()


def brand_of(rec):
    b = clean(rec.get("b"))
    k = b.lower()
    if k in BAD_BRANDS:
        b, k = "", ""
    if k.startswith("lego"):
        return "LEGO"
    if k in BRAND_ALIAS:
        return BRAND_ALIAS[k]
    if not b and re.search(r"\blego\b", rec.get("t") or "", I):
        return "LEGO"
    return b[:40]


def slugify(s):
    s = unicodedata.normalize("NFKD", clean(s).lower().replace("&", " a "))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


# ------------------------------------------------------------------ age (in months; None = unknown)
AGE_RX = [
    (re.compile(r"\bod\s+(\d{1,2})\s*(měsíc|měs\.|m\b)", I), 1),
    (re.compile(r"\b(\d{1,2})\s*m\+", I), 1),
    (re.compile(r"\bod\s+(\d{1,2})\s*(let|roku|rok|roků|r\.)", I), 12),
    (re.compile(r"\b(\d{1,2})\s*\+\s*(let|r\.|roků)?(?!\s*(dílk|ks|kus|cm|mm|hráč))", I), 12),
    (re.compile(r"\bpro (děti )?(\d{1,2})\s*-\s*\d{1,2}\s*let", I), 12),
    (re.compile(r"\b(\d{1,2})\s*-\s*\d{1,2}\s*let\b", I), 12),
    (re.compile(r"\bvěk\w*:?\s*(od\s*)?(\d{1,2})\s*(let|roků|\+)", I), 12),
]
AGE_GROUP = {"newborn": 0, "infant": 0, "toddler": 12, "kids": 36, "adult": 144}


def age_of(rec):
    """Minimum age in months from the title, then the description, then the feed's age group. Plausible range only."""
    for text in (rec.get("t") or "", (rec.get("d") or "")[:600], rec.get("age") or ""):
        for rx, mult in AGE_RX:
            m = rx.search(text)
            if m:
                n = int(next(g for g in m.groups() if g and g.isdigit()))
                v = n * mult
                if 0 <= v <= 216 and not (mult == 12 and n > 18) and not (mult == 1 and n > 36):
                    return v
    a = (rec.get("age") or "").strip().lower()
    if a in AGE_GROUP:
        return AGE_GROUP[a]
    return None


# age bands used for pages: (slug, label, min months, max months) — a product fits a band when its minimum age lies in it
AGE_BANDS = [
    ("0-12-mesicu", "pro miminka (0–12 měsíců)", 0, 11),
    ("1-2-roky", "pro děti 1–2 roky", 12, 35),
    ("3-5-let", "pro děti 3–5 let", 36, 71),
    ("6-8-let", "pro děti 6–8 let", 72, 107),
    ("9-11-let", "pro děti 9–11 let", 108, 143),
    ("12-let-a-starsi", "pro děti od 12 let", 144, 216),
]


def gender_of(rec):
    """Only what the shop states (its own category paths or the feed field) — we do not guess from stereotypes."""
    s = (rec.get("cat") or "") + " | " + (rec.get("t") or "")
    g = (rec.get("sex") or "").lower()
    boys = bool(re.search(r"pro kluky|pro kluka|pro chlapce|letého kluka", s, I)) or g == "male"
    girls = bool(re.search(r"pro holky|pro holku|pro holčičky|letou holku|pro dívky", s, I)) or g == "female"
    return "m" if boys and not girls else "f" if girls and not boys else ""


def veto(rec):
    if PET_PATH.search(rec.get("cat") or ""):
        return True
    return bool(VETO_PATH.search(rec.get("cat") or "") and not re.search(r"Hračk", rec.get("cat") or "")) or bool(VETO_TITLE.search(rec.get("t") or ""))


def classify(rec):
    title = clean(rec.get("t"))
    if veto(rec):
        return None
    for slug, rx in TITLE_RULES:
        if rx.search(title):
            return slug
    path = rec.get("cat") or ""
    for slug, rx in PATH_RULES:
        if rx.search(path):
            return slug
    return None


def lego_series(title):
    t = clean(title)
    for s, n, rx in LEGO_SERIES_RX:
        if rx.search(t):
            return s
    return "ostatni"


def licences_of(title, desc=""):
    t = clean(title)
    return [s for s, n, rx in LICENCES_RX if rx.search(t)]


LEGO_SET = re.compile(r"\b(\d{5,6})\b")


def set_number(rec, brand):
    """LEGO / Playmobil / Bruder / Cobi set numbers identify a product across shops even without an EAN."""
    if brand not in ("LEGO", "Playmobil", "Bruder", "Cobi", "Schleich"):
        return ""
    m = LEGO_SET.search(clean(rec.get("t")))
    if m:
        return f"{brand.lower()}:{m.group(1)}"
    mpn = re.sub(r"\D", "", rec.get("mpn") or "")
    return f"{brand.lower()}:{mpn}" if 4 <= len(mpn) <= 7 else ""
