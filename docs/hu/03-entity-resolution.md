[English](../en/03-entity-resolution.md) · **Magyar** · [↑ README](../../README.hu.md)

# Névegyesítés — egy cég, húsz írásmód

## Miért ez a nehéz rész

Egy vevő nevét senki nem gépeli be kétszer ugyanúgy. Az évek során egy vevő akár **kilenc**
különböző írásmódot gyűjtött össze. Minden későbbi szám — évenkénti vevőszám, új vs visszatérő,
országonkénti árbevétel, partnerenkénti win rate — pontosan annyit ér, amennyit a válasz arra, hogy
*„ez a két sor ugyanaz a cég?"*

A két lehetséges hiba nem egyenértékű:

| hiba | hatás | észrevehetőség |
|---|---|---|
| **kimaradt összevonás** (egy cég kettőként számolva) | túl magas vevőszám, felfújt „új partner" | látható: két hasonló név egymás mellett egy listában |
| **hibás összevonás** (két cég egyként számolva) | árbevétel csendben átkerül egyik vevőről a másikra | minden összesítésben láthatatlan |

A tervezési elv tehát: **az olcsó hibát automatizáljuk, a drágát emberre hagyjuk.**

## A folyamat

```mermaid
flowchart TB
    RAW[nyers név a lapról<br/>'Cég-Nyolc Zrt. (B telephely)'] --> N[normalizálás<br/>kisbetű · ékezet le · írásjel → szóköz<br/>cégforma-végződés le]
    N --> K['ceg nyolc b telephely']
    K --> S[hasonlóság minden partnerrel<br/>és minden tárolt aliasszal<br/>hossz szerinti szűrés · ismert alias = 1,0]
    S --> Z{pontszám}
    Z -->|≥ 0,95 zöld| AUTO[automatikusan elfogadva]
    Z -->|0,85–0,95 sárga| H[az operátor dönt]
    Z -->|< 0,85 piros| H
    H -->|elfogad| P
    H -->|másik partnerhez rendel| AL[új alias tárolva]
    H -->|új partner| NEW[új PM-xxxx]
    AUTO --> P[kanonikus partner<br/>PM-0123]
    AL --> P
    NEW --> P
```

### 1. Normalizálás (`etl/transform.py::normalize_name`)

Kisbetű → ékezet le (Unicode NFKD) → az írásjelek, **a kötőjelet is beleértve**, szóközzé válnak →
szóközök összevonása → a végére horgonyzott cégforma-végződés levágása (31 minta: *Kft., Zrt., Bt.,
GmbH, AG, s.r.o., Sp. z o.o., B.V., Ltd., Inc.* …) → szóközök újbóli összevonása.

| nyers (szintetikus) | normalizált |
|---|---|
| `Cég 007 Kft.` | `ceg 007` |
| `CÉG 007 kft` | `ceg 007` |
| `Ceg-007` | `ceg 007` |
| `Company 044 Sp. z o.o.` | `company 044` |

A normalizálás egymagában elintézi a nagyját: az operátori DB-ben 1 146 különböző normalizált
írásmód tartozik 991 partnerhez — a mögöttük álló nyers írásmódok ennél jóval többen vannak.

### 2. Jelöltek és pontszám

A hasonlóság a `difflib.SequenceMatcher` aránya a normalizált szövegeken — szándékosan egyszerű, és
egy operátornak is elmagyarázható („94%-ban hasonló"). Két korlát tartja olcsón és biztonságosan:

- **hossz szerinti szűrés**: azokat a jelölteket, amelyek hossza 40%-nál (varázsló) / 15%-nál
  (köteg) jobban eltér, egyáltalán nem hasonlítja össze;
- **rövid nevet soha nem von össze automatikusan** kötegelt futásban (< 6 karakter) — az `abc` és
  az `abd` szövegként 67%-ban azonos, cégként 0%-ban.

### 3. Zónák egyetlen küszöb helyett

| zóna | pontszám | mi történik | mérve (34 import-menet, 2026 márc.–jún.) |
|---|---|---|---|
| zöld | ≥ 0,95 | automatikusan elfogadva | 6 131 név-ellenőrzés |
| sárga | 0,85–0,95 | az operátor dönt | 17 (5 elfogadva · 10 másik partnerhez rendelve · 2 új) |
| piros | < 0,85 | az operátor dönt | 906 (79 meglévő partnerhez rendelve · 827 új partner) |

A piros lista **a piros neveket egymással is összeveti**, és 0,6 fölött „hasonló ehhez: …" jelzést
mutat — így ha ugyanannak az ismeretlen cégnek két új írásmódja érkezik ugyanabban a fájlban, még
azelőtt kiderül, hogy két partner lenne belőlük (`admin/routes/import_wizard.py`).

*A számok az összes menet név-ellenőrzései — ugyanazt a nevet minden olyan menetben újra
ellenőrizzük, amelyben szerepel; az operátor munkaterhét mérik, nem a különböző cégek számát.*

### 4. A döntést tároljuk, nem hozzuk meg újra

Minden döntés az **operátori DB**-be kerül (`admin/db/schema.sql`):

| tábla | mit tárol |
|---|---|
| `partner_master` | a kanonikus partnert (`PM-0001` …), megjelenítendő nevet, országot, megjegyzéseket |
| `partner_aliases` | minden valaha látott írásmódot → a partnerét, a forrással (`extract` / `manual` / `fuzzy_merge`); partner + normalizált név szerint egyedi |
| `partner_merges` | ha két kanonikus partnerről kiderül, hogy egy: melyik maradt, melyik olvadt be, és miért |

A következő negyedévben ugyanaz az elírás pontos alias-találat — nincs kérdés. Az első importhoz
több száz döntés kellett; a későbbiekhez csak néhány.

### 5. Két partner utólagos összevonása

`admin/routes/partners.py` (összevonás): a beolvasztott partner aliasai átkerülnek a megmaradóhoz,
a megjelenítendő neve is alias lesz, az összevonás indokkal naplózódik, majd a beolvasztott rekord
törlődik. Az ajánlatok a következő ETL-futáskor automatikusan követik, mert az aliasokon keresztül
kapcsolódnak — a származtatott DB-ben semmit nem szerkesztünk kézzel.

## A kötegelt út

Az önálló ETL-nek (`run_etl.py`) saját, szigorúbb automatikus lépése van az operátor nélküli
futásokhoz: hasonlóság ≥ 0,92, legalább 6 karakteres nevek, hosszeltérés ≤ 15%; az összevont
kulcsokból átirányító aliasok lesznek. Erre rakódnak rá az operátori DB döntései. *(Két azonosító-séma
— a kötegelt `P-` és a varázslós `PM-` — még mindig együtt él a származtatott DB-ben; lásd
[Kimenet](09-outcome.md).)*

## Ország: a második azonossági kérdés

„Melyik országbeli ez a vevő?" — ugyanolyan típusú probléma, és a banki riport fő bontása a
belföldi vs külföldi. A szabály: **akivel ténylegesen üzletelünk**, nem a cégjegyzéki bejegyzés és
nem a csoport-központ. Egy hatstratégiás feloldó javasol, mindegyik módszer- és bizonyosság-címkével;
331 döntést ember hozott meg, és ezek mindent felülírnak. Részletek:
[A káosz, F1–F4](01-the-mess.md#f-országok).

## Terv vs megépült

| terv | megépült | megjegyzés |
|---|---|---|
| a hasonló nevek automatikus összevonása | automatikusan csak 0,95 fölött; a többiről ember dönt | a hibás összevonás minden összesítésben láthatatlan |
| egy megtisztított partnerlista | partnertörzs, **és mellette** minden írásmód aliasként | a lista akkor is helyes marad, ha jövőre ugyanaz az elírás visszajön |
| egyetlen egyeztető | két út (köteg + varázsló) eltérő küszöbökkel | a kötegelt útnak nem kell operátor; a varázsló útján születik az ítélet |
| partner-dúsítás cégjegyzékből (iparág, méret) | csak az ország | a többi parkolópályán — nincs becsült adat |
