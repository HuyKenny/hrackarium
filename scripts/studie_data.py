"""derive functions of the data studies: state["agg"] (daily aggregates, scripts/catalog.py collect_study_data) -> numbers for scripts/studie.py."""
from datetime import date

import studie as ST
import taxonomy as X

MIN_ELIG = 500      # products with >= 7 days of our own price observations needed before "unseen original price" is quoted


def cz(n, d=1):
    return f"{n:.{d}f}".replace(".", ",")


def black_friday(agg):
    days = sorted(int(k) for k in agg)
    if len(days) < 2:
        return None
    last = agg[str(days[-1])]
    day = lambda k: date.fromordinal(k)
    first = day(days[0])
    share = lambda a: a["claim"] / a["n"] * 100 if a["n"] else 0
    ser = {"Podíl produktů s uvedenou slevou (%)": [(f"{day(k).day}. {day(k).month}.", round(share(agg[str(k)]), 1)) for k in days]}
    un = [(f"{day(k).day}. {day(k).month}.", round(agg[str(k)]["unseen"] / agg[str(k)]["elig"] * 100, 1)) for k in days if agg[str(k)]["elig"] >= MIN_ELIG]
    if len(un) >= 2:
        ser["Podíl slev s původní cenou, kterou jsme neviděli (%)"] = un
    have_unseen = last["elig"] >= MIN_ELIG
    unseen_share = last["unseen"] / last["elig"] * 100 if have_unseen else 0
    v = {"n": f'{last["n"]:,}'.replace(",", " "), "claim": f'{last["claim"]:,}'.replace(",", " "), "share": cz(share(last)), "med": last["med"], "p25": last["p25"], "p75": last["p75"],
         "first": f"{first.day}. {first.month}. {first.year}", "days": len(days), "last": f"{day(days[-1]).day}. {day(days[-1]).month}. {day(days[-1]).year}",
         "unseen": cz(unseen_share), "elig": f'{last["elig"]:,}'.replace(",", " "),
         "unseen_sentence": (f"U {cz(unseen_share)} % z těchto slev je uváděná původní cena vyšší než jakákoli cena, kterou jsme u produktu za posledních 14 dní viděli."
                             if have_unseen else "Zatím nemáme dost dlouhou historii, abychom mohli říct, u kolika slev byla původní cena skutečně k vidění.")}
    cats = sorted(((X.TREE[t][0], n, c, med) for t, (n, c, med) in last["cat"].items() if t in X.TREE and n >= 300 and c), key=lambda r: -r[2] / r[1])
    rows = [[n_, f'{n:,}'.replace(",", " "), f'{cz(c / n * 100)} %', f"{med} %"] for n_, n, c, med in cats]
    rows_csv = [[date.fromordinal(k).isoformat(), agg[str(k)]["n"], agg[str(k)]["claim"], agg[str(k)]["med"], agg[str(k)]["elig"], agg[str(k)]["unseen"]] for k in days]
    return {"vars": v, "updated": v["last"], "updated_iso": day(days[-1]).isoformat(), "coverage": f"{first.isoformat()}/{day(days[-1]).isoformat()}",
            "chart_html": ST.line_chart(ser, aria="Vývoj podílu produktů s uvedenou slevou"),
            "table_head": ["Kategorie", "Produktů", "Podíl se slevou", "Medián slevy"], "table_rows": rows,
            "csv_head": ["datum", "produktu", "s_uvedenou_slevou", "median_slevy_procent", "produktu_s_historii_7_dni", "pocet_s_nevidenou_puvodni_cenou"], "csv_rows": rows_csv}
