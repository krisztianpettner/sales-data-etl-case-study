[English](../en/02-ingestion.md) · **Magyar** · [↑ README](../../README.hu.md)

# Beolvasás — évente változó táblázatok olvasása

## A probléma egy mondatban

Minden év munkafüzetét az rendezte el, aki abban az évben vezette: oszlopokat szúrtak be, neveztek
át, rendeztek át; egy év két lapra oszlott; a régebbi években státusz oszlop egyáltalán nem volt. Egy
rögzített oszloppozíciókkal dolgozó olvasó nem hibára futna — hanem **csendben rossz mezőt olvasna**.

## A döntés: a szerkezet-tudás adat

Minden tudás arról, hogy *mi hol van*, egyetlen regiszterben él, az `etl/config.py`-ban:

```python
# a column map per layout era (1-based column numbers) — reusable building blocks
_TG1_COLS_LEGACY = {
    "quote_id": 2, "revision": 3, "partner_name": 4, "subject": 5,
    "request_date": 9, "deadline_date": 10, "sent_date": 12,
    "status": 13, "registry_number": 14, "total_value_eur": 15, "work_number": 16,
}
_TG1_COLS_2025 = {**_TG1_COLS_LEGACY, "country_domestic": 21, "country_name": 22, ...}

# one entry per importable file
FILE_CONFIG = {
    "TG1_2025": {"file": ROOT / "quotes_tg1_2025.xlsx", "sheet": "2025",
                 "start_row": 3, "cols": _TG1_COLS_2025},
    "TG1_2020": {"file": ROOT / "quotes_tg1_2020.xlsx",
                 "sheet": ["First half", "Second half"],        # one year, two sheets
                 "start_row": 4, "cols": _TG1_COLS_2022},       # no status column → tick boxes
    ...
}
```

*(Kivonat, egyszerűsítve; a fájlnevek szintetikusak.)*

**Egy új év egy konfig-bejegyzés.** Egy megváltozott elrendezés egy új oszloptérkép, általában az
előző kétsoros kiterjesztése. Magában a beolvasóban nincs évfüggő elágazás, egyetlen kivétellel: van-e
a fájlban státusz oszlop, vagy nincs.

| | darab (2026-10-13) |
|---|---:|
| fájl-bejegyzések a regiszterben | 8 aktív + 4 archivált év (megtartva, kikommentezve) |
| oszloptérképek | 14 (8 ajánlat-elrendezés, 5 partner-lap elrendezés, 1 kapcsolattartó-elrendezés) |
| mezők ajánlat-elrendezésenként | 14–24 |

## Az olvasó szabályai

Az `etl/extract.py::_read_sheet` egyetlen, általános sorolvasó (openpyxl, csak olvasás, csak értékek):

| szabály | miért |
|---|---|
| a beállított sornál kezd, az oszlopokat a beállított számok szerint képezi le | a fejlécsorok magassága és szövege évente más |
| **20 egymást követő üres sor** után megáll | a lapokon formázás és kósza sorok vannak messze az adat alatt |
| egy sor csak akkor számít, ha van azonosítója **és** partnere | a helykitöltő sorokat (`-` minden cellában) és a félig begépelt sorokat átugorja |
| egy lap lehet **lista** is | egy évet két féléves lapon vezettek |
| a `data/` erősebb a projekt gyökerénél | a valódi fájlok a `data/`-ban élnek; a gyökérben lévő azonos nevű fájlok tesztadatok (`config._resolve_file`) |

## Fejlécsorok és tételsorok (2. termékcsoport)

A 2. termékcsoport ajánlatainak tételsorai vannak. Két elrendezés létezik:

```mermaid
flowchart TB
    subgraph NEW["2023+ elrendezés"]
        H1[sor: Q2-26-118 · Cég 044 · státusz 'kiajánlva' · 1. tétel · 1 123]
        L1[sor: Q2-26-118 · státusz '[rendelés tételsora]' · 2. tétel · 18 400]
        L2[sor: Q2-26-118 · státusz '[rendelés tételsora]' · 3. tétel · 957]
    end
    subgraph OLD["régebbi elrendezés"]
        H2[sor: Q2-22-031 · Cég 052 · visszajelzés 'lerendelték' · 637]
        C1[sor: — nincs azonosító — · 2 db · 210]
        C2[sor: — nincs azonosító — · 1 db · 95]
    end
    NEW -->|leválasztás státusz-jelölő szerint| R[ajánlat-fejléc + tételsorok<br/>érték = az összes tétel összege]
    OLD -->|folytatósorok → utolsó fejléc<br/>előrekitöltés| R
```

*(Szintetikus sorok.)* Az ajánlat értéke **a fejléc-tétel és az összes tételsor összege**
(`transform.py::transform_tg2_quotes`); a tételsorok a saját táblájukban is megmaradnak.

## Ahol nincs státusz oszlop

| elrendezés | honnan nyerjük vissza a státuszt | kód |
|---|---|---|
| 1. termékcsoport, régebbi évek | öt jelölőnégyzet-oszlop (nyert / vesztett / elhalasztva / nem ajánlottunk / nyitott) → státusz-szöveg; ha nincs jelölés → „nyitott", ha van kiküldési dátum, egyébként „előkészítés alatt" | `extract.py::_derive_tg1_status_bitmask` |
| 2. termékcsoport, legrégebbi év | szabad szöveges visszajelzés → kulcsszó-szabályok („rendel" → nyert, „visszamond" → nem ajánlottunk, kiküldés utáni bármilyen más visszajelzés → vesztett) | `extract.py::_derive_tg2_status_feedback` |

A visszanyert szöveg ezután ugyanazon a státusz-térképen megy át, mint minden más év — a további
lépésekben egyetlen szókészlet van.

## Hiányzó és hibás értékek

Egyetlen jelölőkészlet jelenti mindenhol azt, hogy „nincs érték": `-`, `#N/A`, `#REF!`, „Hiányzik,
add meg!" (és ékezet nélküli írásmódja), „nincs cím", az üres szöveg (`config.MISSING_MARKERS`).
Ezek NULL-lá válnak, *mielőtt* bármely szabály rájuk nézne, így egy `#REF!`-ből soha nem lesz
`#REF!` nevű partner.

## Ugyanaz az olvasó, két belépési pont

| belépési pont | mire való |
|---|---|
| `etl/run_etl.py` | a kötegelt futás: minden beállított fájl, elejétől a végéig |
| az import-varázsló | az operátor egy vagy több fájlt tölt fel; a fájlkulcsot (termékcsoport + év) a fájlnévből ismeri fel, aztán ugyanaz a beolvasó fut (`admin/routes/import_wizard.py`) |

## Terv vs megépült

| terv | megépült | megjegyzés |
|---|---|---|
| „a" táblázat beolvasása | 8 elrendezés-korszak egyetlen olvasó mögött | az elcsúszás csak akkor látszott, amikor az összes évet egymás mellett megnyitottuk |
| státusz a státusz oszlopból | státusz oszlopból, jelölőnégyzetekből vagy prózából — utána egyetlen szókészlet | a régebbi évek különben használhatatlanok lettek volna |
| minden év betöltése 2020-tól | 2023-tól betöltve; a 2020–2022 a regiszterben marad, de kikapcsolva | ezek az évek csak CRM-ből származtak, és rossz mértékegységű értékeket hordoztak — jobban torzították a pipeline-t, mint amennyit hozzátettek |
