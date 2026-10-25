# HDL Buspro įrenginių skanavimo ir pridėjimo įrankis — įgyvendinimo planas

Būsena (2026-10-25): **etapai 0–5 atlikti — MVP**: skaneris ir testavimas (`pybuspro/scanner/`, servisai `buspro.scan` ir `buspro.test_channel`, `tools/hdl_probe.py scan|set|pulse`), entity iš skenavimo (`storage.py`, `switch`/`light` `async_setup_entry`), šoninis skydelis (`frontend/buspro-panel.js`, `panel.py`, WS `buspro/*` komandos `websocket_api.py`). Etapo 0 rezultatai pagal du Setup Tool 2 Wireshark įrašus — `docs/protocol-captures/2026-10-25-analysis.md` (jie turi pirmenybę prieš 2 skyriaus spėjimus).

## 1. Tikslas

Home Assistant viduje turi atsirasti **vienas įrankis** (šoninio meniu skydelis „HDL Buspro"), kuriuo galima:

1. **Praskanuoti HDL magistralę** per esamą IP šliuzą.
2. Iš rezultatų sąrašo **pasirinkti įrenginį** (pvz. `1.89 — „Rėlių modulis 1 aukštas"`).
3. Pamatyti **to įrenginio kanalus / jutiklius / išėjimus su pavadinimais, nuskaitytais iš paties įrenginio**, ir **gyvas jų reikšmes** (rėlės ON/OFF, dimerio %, temperatūra, lux, judesys, sausi kontaktai…).
4. **Patikrinti prieš pridedant** — kiekvienam kanalui yra mygtukai **ON / OFF** (dimeriui slankiklis, užuolaidai ▲ ■ ▼), kad būtų galima įsitikinti, jog tai tas kanalas, kurio ieškoma.
5. Sudėti **varneles** ir paspaudus „Pridėti pasirinktus" sukurti **Home Assistant entity** (`switch`, `light`, `cover`, `sensor`, `binary_sensor`, …), kuriuos jau galima valdyti — **be YAML redagavimo ir be HA perkrovimo**.

Esama YAML konfigūracija **lieka veikti nepakeista** (jokio breaking change).

## 2. Ką radau internete (tyrimo rezultatai)

Paieška atlikta 2026-10-25. Dalis svetainių nebuvo pasiekiamos iš šios aplinkos (`community.home-assistant.io`, `scribd.com`, `dev.iridi.com`, `ftpmirror.your.org` — DNS klaida), todėl jų turinio **nematėme**. `SmartHouseBrain` agentas šiuo metu nepasiekiamas (nėra jokios kitos aktyvios sesijos) — klausimai jam surašyti 10 skyriuje.

### 2.1 Svarbiausias radinys — jau yra HA integracija su skanavimu

[`marsh4200/ar_hdl_buspro`](https://github.com/marsh4200/ar_hdl_buspro) (HACS, „UI-only setup", PR [#41](https://github.com/marsh4200/ar_hdl_buspro/pull/41) sulietas 2026-10-09). Eiga: *Add gateway → Scan the bus → Select devices → Done*, automatinis tipo atpažinimas, daugiakanalių rėlių skaidymas į atskirus switch.

Iš jos kodo ir aprašymo (per `discovery.py`, `classify.py`) išmokome **patikrintą skanavimo algoritmą** (žr. 4 skyrių). **Svarbu dėl licencijos:** jos `hdl_catalog.py` pažymėtas *„All rights reserved. Proprietary and confidential"*, o repo turi `licensing.py`. **Jokio jų kodo ar katalogo kopijuoti negalima** — viskas rašoma iš naujo, remiantis tik protokolo faktais. Pooria-nek/RelayModule_library — GPL-2.0, taip pat tik kaip žinių šaltinis, ne kopijavimui.

Kuo mūsų įrankis turi skirtis (ko iš aprašymo nematyti): **kanalų pavadinimai, nuskaityti iš paties įrenginio**, ir **ON/OFF testas prieš pridedant**. Ar ar_hdl_buspro turi testavimą — nepatikrinta.

### 2.2 Patikrinta protokolo informacija

Šaltiniai: oficialus **„HDL-BUS control and operate code" (2013-01-08)** PDF, kurį naudoja [`node-red-contrib-hdl`](https://github.com/estbeetoo/node-red-contrib-hdl) (PDF išgautas ir perskaitytas lokaliai), [`caligo-mentis/smart-bus`](https://github.com/caligo-mentis/smart-bus) (parseriai pagal „Operation Code of HDL Buspro v1.111"), ir ar_hdl_buspro skanerio kodas.

| Funkcija | Opkodas (užklausa → atsakymas) | Payload | Patikimumas |
|---|---|---|---|
| Vieno kanalo valdymas | `0x0031` → `0x0032` | užklausa: `[kanalas, lygis, min, sek]`; atsakymas (**broadcast**): `[kanalas, 0xF8=OK/0xF5=klaida, lygis, kanalų_sk, bitų kaukė ⌈n/8⌉ B]` | oficialus PDF; **kaukė patvirtinta įrašais** (PDF rašo „lygiai") |
| Visų kanalų būsena | `0x0033` → `0x0034` | atsakymas: `[kanalų_sk, lygis_1 … lygis_N]` | oficialus PDF |
| Realus kanalo lygis | `0x0038` → `0x0039` | kaip `0x0034` | oficialus PDF |
| Universal switch | `0xE01C` (valdymas, ON=`0xFF`) → `0xE01D`; `0xE018 [n]` → `0xE019 [n, 1/0]`; `0xE017` broadcast `[būsenos…]` | | oficialus PDF |
| Užuolaida | `0xE3E0 [n, 0=stop/1=open/2=close]` → `0xE3E1`; `0xE3E2 [n]` → `0xE3E3` | | oficialus PDF |
| Grindų šildymas (DLP) | `0x1944` → `0x1945`: `[tipas, temp, būsena, režimas, normal, day, night, away]` | | oficialus PDF + smart-bus |
| Jutiklis 8in1/12in1 | `0x1645` → `0x1646`: `[ok, temp(−20), lux_hi, lux_lo, judesys, sonic, DC1, DC2]`; broadcast `0x1647` | | PDF + smart-bus (jau naudojama `sensor.py`) |
| Sensors-in-one | `0x1604` → `0x1605`: `[ok, temp(−20), lux u16, drėgmė, oras, dujos, judesys, DC1, DC2]` | | PDF + smart-bus |
| Sausas kontaktas | `0x15CE [1, n]` → `0x15CF [?, n, būsena]` | | smart-bus + ar_hdl_buspro |
| Judesio jutiklis | `0xDB00` → `0xDB01` | | PDF + smart-bus |
| Temperatūra | `0xE3E7 [kanalas]` → `0xE3E8`; broadcast `0xE3E5` | | PDF + smart-bus |
| **Įrenginio pavadinimas (remark)** | `0x000E []` → `0x000F` (payload = remark baitai) | | **patvirtinta įrašais** (Setup Tool paieška = broadcast `0x000E`) |
| **Modulio savaiminis aprašas** | `0xE548 [r1, r2, (subnet,dev)×≤32]` → `0xE549` | atsakymas: `[echo 2B][remark 20B][(big,small,count)×N]` | **veikiantis kodas** (HDL Setup Tool 2 mechanizmas) |

**`0xE549` funkcijų trejetai `(big, small, count)`** — įrenginys pats pasako, kas jame yra, todėl **nereikia didelio modelių katalogo**:

| big | prasmė |
|---|---|
| 1 | šviesos išėjimai: `small=0` dimeris, `small=1` rėlė; `count` = kanalų skaičius |
| 2 | užuolaidos |
| 4 | panelė: `small=0` zonos (sausi kontaktai), kitaip mygtukai |
| 5 | jutikliai: `small=0` arba `25` sausi kontaktai, `small=2` temperatūra, kiti — tikri jutikliai |
| 7 | kondicionierius (AC) |
| 8 | grindų šildymas |
| 0 | ne funkcija (bazinio skydelio adresas) — praleisti |

### 2.3 Kanalų pavadinimai (`0xF00E`) — **patvirtinta įrašais**

- `0xF00E [kanalas]` → `0xF00F [kanalas][20 B]`; nepavadintas kanalas = `0xFF`×20. Setup Tool kiekvieną užklausą siunčia 3 kartus; atsakymas ~60–80 ms.
- Koduotė — **cp1257** (22 lietuviški pavadinimai, visi teisingi). Dekodavimo eilė `utf-8` → `cp1257` → `gbk` → `latin-1` tinka: nė vienas cp1257 pavadinimas nėra validus UTF-8. (ar_hdl_buspro palieka tik ASCII — tai sugadintų `ąčęėįšųūž`.)
- Paieškos laikai: po broadcast `0x000E` atsakymai ateina per ~5 s, bet vienas raundas randa ~87 % įrenginių → reikia 4–5 raundų.

### 2.4 Kiti praktiniai dalykai

- Šliuzas UDP **6000**; gavimui reikia klausytis to paties porto (kaip jau daro `udp_client.py`). Jei portą užėmęs kitas procesas — broadcast'ai praleidžiami.
- **Dauguma rėlių/dimerių modulių ignoruoja *broadcast* `0x0033`** ir atsako tik į siųstą jiems tiesiogiai → po broadcast fazės būtina **directed** užklausa kiekvienam rastam įrenginiui.
- Tipo kodas `0x0086` reiškia skirtingus gaminius HDL ir Smart-Bus → nepasikliauti vien kodu, bet įrenginio atsakymu.
- Šliuzai (`0x1209`, `0x120B`, `0x02F5`) ir logikos moduliai (`0x0455`, `0x0457`) neturi būti siūlomi kaip entity.
- `0xF003` → `0xF004` — MAC skaitymas (8 B), **patvirtinta įrašais**: Setup Tool jį skaito kiekvienam rastam įrenginiui. Tinka pastoviam HA įrenginio ID (adresą galima pakeisti, MAC — ne). `0xE5F5` įrašuose nematytas.

## 3. Dabartinė repo būklė (kas padeda, kas trukdo)

| Radinys | Reikšmė planui |
|---|---|
| `__init__.py::async_setup_entry` **neperduoda platformų** (`async_forward_entry_setups` nėra); entity kuriami tik per YAML `async_setup_platform` | Reikia pridėti platformų persiuntimą ir `async_setup_entry` kiekvienoje platformoje |
| Config entry saugo tik `host`/`port`; `hass.data[DOMAIN] = BusproModule` (YAML kelias – `async_setup` – naudoja tą patį raktą) | Skydelį/WS registruoti iš bendros vietos; YAML-only vartotojai be config entry įrankio negaus (arba reikia `async_step_import`) |
| `Buspro.register_telegram_received_all_messages_cb` – **vienas** callback'as, niekur nenaudojamas | Pakeisti į kelių klausytojų sąrašą |
| `TelegramHelper` nežinomą opkodą/įrenginio tipą paverčia `None` (`Generics.get_enum_value`) | `0xE549`, `0x000F`, `0xF00F` šiuo metu nepasiektų skanerio → saugoti `operate_code_raw` ir papildyti `OperateCode` |
| `_callback_all_messages(None)` (CRC klaida) → `telegram.target_address` ant `None` | Pridėti `None` apsaugą |
| Siuntimas be tarpų (`send_telegram` iškart) | Reikia siuntimo eilės su ~50 ms tarpu (skanavimas + HA startup skaitymai) |
| Nėra request/response mechanizmo (viskas „fire-and-forget" + callback) | Reikia `await request(...)` su laukimu atsakymo |
| `Device` objektai niekada neišsiregistruoja (`unregister_*` nenaudojamas, nėra `async_will_remove_from_hass`) | Būtina dinaminiam entity šalinimui |
| Entity neturi `device_info` | Naujiems entity pridėti (grupuoti pagal HDL įrenginį) |
| **Klaida:** `buspro.send_message` servisas (savavališkas opkodas + payload) **neveikia** — `service_send_message` perduoda `operate_code` kaip `list[int]`, o `TelegramHelper.build_send_buffer` daro `telegram.operate_code.value` → `AttributeError: 'list' object has no attribute 'value'` (patikrinta lokaliai su `[240,14]` ir README pavyzdžiu `[4,78]`) | Pataisyti (2 baitų sąrašą paversti `bytes`) — tai reikalinga ir 0 etapui, ir savaime naudinga klaidos ištaisymas |
| `unique_id` = `device_identifier`, pvz. `(1, 89)-3` | Naudoti tą patį formatą → vėliau galima migruoti iš YAML be dublikatų |
| Nėra testų, CI | Pridėti `tests/` su `FakeBus` |

## 4. Skanavimo algoritmas (mūsų realizacija)

Skanavimas yra **fono užduotis** su progreso įvykiais (ne blokuojanti forma). Klausytojas (`add_telegram_listener`) renka **visą** srautą, o aktyvios užklausos tik „išprovokuoja" atsakymus.

**A fazė — pasyvus klausymas + broadcast „provokacijos"** (trukmė pasirenkama 30 / 60 / 90 s — trumpiau nerekomenduojama: vienas `0x000E` raundas randa tik ~87 % įrenginių, atsakymai ateina per ~5 s, todėl `0x000E` kartoti ≥4 kartus kas ~10 s; kitos provokacijos kas 2,5 s, tarp kadrų 50 ms), siunčiama į `255.255`:
`0x0033 []`, `0x1645 []`, `0x1604 []`, `0x1944 []`, `0x15CE [1,1]`, `0xE018 [1]`, `0xE3E2 [1]` ir `[2]`, `0xDB00 []`, `0xE3E7 [1]`, `0x000E []`.
Kiekvienas gautas telegrama sukuria/papildo `ScannedDevice` pagal šaltinio adresą ir tipo kodą (baitai 19–20 UDP pakete).

**B fazė — modulio savaiminis aprašas**: broadcast `0xE548 [r1, r2, išskyrimo sąrašas]` (r1,r2 atsitiktiniai 1–255; išskyrimo sąrašas = jau atsakiusių `(subnet,device)` poros, ≤32, rotuojama per raundus — taip daro ir HDL Setup Tool, kad nebūtų audros). Atsakymai `0xE549` → remark + funkcijų trejetai.

**C fazė — directed skaitymas**: kiekvienam rastam įrenginiui siunčiama `0x0033` tiesiogiai (2 raundai, 2 s klausymas) → kanalų skaičius ir būsenos. Dimerio požymis: bent vienas lygis ∉ {0, 100}.

**D fazė — identifikavimas** tiems, kas dar neaiškūs: directed `0x1604`, `0x1645`, `0xDB00`, `0xE3E7 [1]`, `0x1944`, `0x15CE [1,1]`, `0xE3E2 [1]`, `0x000E`. Sausų kontaktų modulio zonų skaičius: `0x15CE [1,z]`, z=2…24.

**E fazė — pavadinimai (mūsų papildymas)**: directed `0x000E` (įrenginio pavadinimas) ir `0xF00E [kanalas]` kiekvienam išėjimo kanalui 1…N (laukti `0xF00F`; per vieną įrenginį paeiliui, ne lygiagrečiai). Jei neatsako — kanalas pavadinamas `Kanalas N`.

**Saugikliai**: ignoruoti šaltinius `(200,200)`, `(0,0)`, `(255,255)`, savo `VirtualSingleChannel` adresus ir šliuzų/logikos tipus; fazių ribos (~20 s / 30 s / 25 s, bendras ≤ ~80 s); „Atšaukti" mygtukas; visi laikai konfigūruojami konstantomis.

**Klasifikavimo pirmenybė**: (1) vartotojo „tipo override"; (2) `0xE549` savaiminis aprašas; (3) mūsų **nedidelė** žinomų tipų lentelė (esami 17 kodų iš `enums.py` + bendruomenės papildymai JSON faile); (4) elgsena skanavimo metu (atsakė į `0x0033` → išėjimų modulis). Įrenginys, atsakęs į `0x0033`, niekada nepervertinamas lentele.

## 5. Architektūra

```
┌────────────────────────── Home Assistant ──────────────────────────┐
│  Šoninis skydelis „HDL Buspro"   (frontend/buspro-panel.js)         │
│        │  hass.callWS / subscribeMessage                            │
│  ┌─────▼───────────────────────────────────────────────────────┐   │
│  │ websocket_api.py  (admin-only):                              │   │
│  │  scan/start|cancel|subscribe, devices/list, device/read,     │   │
│  │  channel/test, entities/add|remove|list                      │   │
│  └─────┬──────────────────────┬─────────────────────────────────┘   │
│        │                      │                                     │
│  ┌─────▼─────────┐   ┌────────▼─────────┐   ┌─────────────────────┐ │
│  │ BusScanner    │   │ BusController    │   │ EntityStore (Store) │ │
│  │ (pybuspro/    │   │ set/read kanalai │   │ .storage/buspro.*   │ │
│  │  scanner)     │   │ test + atstatymas│   │ + dispatcher signal │ │
│  └─────┬─────────┘   └────────┬─────────┘   └──────┬──────────────┘ │
│        │                      │                    │ SIGNAL_ADDED    │
│  ┌─────▼──────────────────────▼──────┐   ┌─────────▼──────────────┐ │
│  │ pybuspro.Buspro                   │   │ switch/light/cover/    │ │
│  │  listeners[], request(), siuntimo │   │ sensor/binary_sensor/  │ │
│  │  eilė (50 ms), raw opkodai        │   │ climate: async_setup_  │ │
│  └─────┬─────────────────────────────┘   │ entry + YAML (kaip buvo)│ │
│        │ UDP :6000                        └────────────────────────┘ │
└────────┼───────────────────────────────────────────────────────────┘
         ▼
   HDL IP šliuzas  ⇄  HDL magistralė
```

**Kodėl šoninis skydelis, o ne options-flow:** formos HA flow'e neturi veikiančių ON/OFF mygtukų ir gyvų reikšmių; flow'as reikalautų „pasirink kanalą → perjunk → pateik formą" ciklo. Skydelis duoda lentelę su gyvomis reikšmėmis, mygtukais ir varnelėmis. Options-flow paliekamas tik nustatymams (skanavimo trukmė, siuntimo tarpas, šaltinio adresas).

**Kodėl `Store`, o ne `config_entry.options`:** pridėjimas/šalinimas be perkrovimo (options update_listener perkraunamų visą integraciją); `Store` patenka į HA atsargines kopijas. Versijuota schema (`version`, migracija).

## 6. Duomenų modeliai

```python
ScannedDevice:  subnet, device, type_code, model, remark, firmware?, online,
                functions[(big,small,count)], channels: list[ScannedChannel], last_seen
ScannedChannel: number, kind  # output | curtain | sensor | dry_contact | universal_switch | ac | floor_heat
                name, name_source  # device | default | user
                value          # 0..100 | bool | float | None
                default_platform, supports  # ["on_off","dim","open_close"] ...
EntitySpec (saugoma):
  {"id":"1.89.3.switch","platform":"switch","subnet":1,"device":89,"channel":3,
   "name":"Svetainė – LED juosta","options":{"running_time":0},
   "source":{"type_code":"0x01AC","name_from":"device"}}
```

Numatytasis entity tipas: `big=1,small=1` → `switch` (galima pakeisti į `light`); `small=0` → `light` (dimeris); mišrūs moduliai (pvz. HDL-MRCU) — pagal kanalą; `big=2` → `cover`; `big=4,small=0` ir `big=5,small∈{0,25}` → `binary_sensor` (dry_contact); `big=5` kiti → `sensor` (temperatūra, lux) + `binary_sensor` (judesys); `big=7` → `climate`; `big=8` → floor-heating `climate` (dabartinis `climate.py` tik AC — reikės atskirti). Universal switch'ų skaičius nenustatomas — UI leidžia pridėti rankiniu numeriu, o `0xE017` broadcast ilgis duoda užuominą.

## 7. ON/OFF testas (privalomas reikalavimas)

- Veikia **per magistralę tiesiogiai** (`BusController`), **be HA entity** — todėl galimas dar nieko nepridėjus.
- Valdymas: rėlė `0x0031 [ch,100|0,0,0]`; dimeris — slankiklis 0–100; užuolaida `0xE3E0 [n,1|0|2]`; universal switch `0xE01C [n,0xFF|0]`. AC/šildymas — tik skaitymas MVP.
- **Patvirtinimas realia būsena**: po komandos laukiama `0x0032` (broadcast, `payload[1]==0xF8`) ≤1,5 s; jei nėra — directed `0x0033`/`0x0038`. UI rodo „✔ patvirtinta: 100 %" arba „⚠ neatsakė".
- **Gyvi atnaujinimai**: skydelis prenumeruoja (`scan/subscribe`); klausytojas pasyviai dekoduoja `0x0032`, `0x0034`, `0xE01D`, `0xE017`, `0x1646/1647`, `0x1605`, `0xE3E3` ir stumia į UI (su throttling). Fizinis jungiklis sienoje taip pat atsispindi.
- **„Impulsas" režimas** (rekomenduojamas numatytasis pirmam testui): įjungia N s (numatyta 2) ir **grąžina ankstesnę būseną**; atstatymas vykdomas serveryje (veikia ir uždarius naršyklę; atšaukiamas/įvykdomas integracijos išjungimo metu).
- **Saugumas**: tik admin; pirmą kartą įspėjimas „tai realiai perjungs apkrovą (siurblys, šildymas, durys…)"; ne dažniau kaip 1 komanda / 300 ms į kanalą; testai loguojami.

## 8. Etapai ir priėmimo kriterijai

Dydžiai: **S** ≈ pusdienis, **M** ≈ 1–2 d., **L** ≈ 3+ d. (apytiksliai, vienam žmogui).

| # | Etapas | Dydis | Priėmimo kriterijus |
|---|---|---|---|
| **0** | **Protokolo patikra su tikra įranga** (blokuoja E etapą) | S | Pirmiausia pataisyti `buspro.send_message` (žr. 3 skyrių, ~5 eilutės), tuomet išsiųsti `0x000E`, `0xF00E [1]`, `0xE548 [..]`; `buspro.telegram` debug žurnale užfiksuoti atsakymus ir įrašyti į `docs/protocol-captures/*.md`. Patvirtintos opkodų vertės, remark ilgis, koduotė (lietuviškos raidės), `0xE549` išdėstymas. **Alternatyva be jokio kodo:** Wireshark (UDP 6000) kol HDL Buspro Setup Tool 2 daro „Search" ir atidaro kanalų pavadinimus. |
| **1** | Bibliotekos pamatai: `operate_code_raw`, nauji `OperateCode`, `None` apsauga, kelių klausytojų sąrašas, `request()`, siuntimo eilė, remark dekoderis, `0xE549` parseris | M | Vienetiniai testai praeina; esami YAML platformų veikimas nepakitęs |
| **2** | `BusScanner` (A–E fazės) + `FakeBus` simuliatorius + servisas `buspro.scan` (rezultatas į žurnalą/`diagnostics`) | L | Su `FakeBus` (8 kan. rėlė, 6 kan. dimeris, 12in1, užuolaidų modulis, DLP) randami visi įrenginiai su teisingais kanalų skaičiais; su tikra įranga tas pats |
| **3** | `BusController` + testo logika (on/off/impulsas/lygis, patvirtinimas, gyvi atnaujinimai) | M | Rėlės kanalas perjungiamas ir UI gauna patvirtinimą ≤1,5 s; „impulsas" grąžina būseną |
| **4** | `EntityStore` + platformų `async_setup_entry` (**pirmiausia `switch` ir `light`**) + `device_info` + dinaminis pridėjimas/šalinimas + `async_will_remove_from_hass` | L | Pridėjus per WS (be UI) entity atsiranda be perkrovimo, išlieka po restarto, šalinimas nepalieka callback'ų; dublikatas su YAML aptinkamas |
| **5** | WebSocket API + skydelis (lentelė, varnelės, ON/OFF, „Pridėti pasirinktus") — **MVP** | L | Visas 1 skyriaus scenarijus veikia relėms ir dimeriams |
| **6** | Likę tipai: `cover`, `sensor`, `binary_sensor` (judesys, DC, universal switch), `climate` | L | Kiekvienam tipui „skaityti + (kur taikoma) testuoti + pridėti" |
| **7** | Apdaila: `lt`/`en` vertimai, README skyrius, `diagnostics.py` (nežinomų tipų kodų išrašas), „tipo override", repair'ai | M | Nežinomas įrenginys parodomas su kodu ir galima nurodyti tipą |

**MVP = etapai 0–5** (rėlės ir dimeriai — tavo pagrindinis pavyzdys).

## 9. Testavimo strategija

- `tests/fakebus.py` — atmintyje esantis UDP pakaitalas su simuliuotais įrenginiais (atsakinėja `0x0033/0x0031/0x000E/0xF00E/0xE548…`, gali „ignoruoti broadcast `0x0033`", gali neatsakyti, gali siųsti `0x0032` broadcast'ą).
- `pytest` vienetiniai: telegramų parsing/CRC, `0xE549` parseris, remark dekoderis (utf-8/cp1257), skanerio fazės, testo patvirtinimas/impulsas, išskyrimo sąrašo rotacija.
- HA lygis su `pytest-homeassistant-custom-component`: WS komandos (admin-only), platformų `async_setup_entry`, dinaminis pridėjimas/šalinimas, `unique_id` dublikatai, `Store` migracija.
- CI (GitHub Actions): `pytest`, `hassfest`, HACS validation.
- **Rankinis sąrašas su tikra įranga**: (1) skanas randa visus žinomus įrenginius; (2) pavadinimai sutampa su Setup Tool; (3) ON/OFF fiziškai perjungia; (4) fizinio jungiklio paspaudimas atsispindi UI; (5) HA restartas — entity išlieka ir turi būseną; (6) skanavimas nesutrikdo veikiančių entity.

## 10. Rizikos, atviri klausimai

**Rizikos**
1. ~~`0xF00E/0xF00F` vertės ir formatas nepatvirtinti~~ — patvirtinta etape 0. Lieka: 8 įrenginių tipai neatsako į `0xE548` (DLP panelės, logikos/IP moduliai, kai kurie jutikliai) → klasifikuoti pagal `0x0033` atsakymą ir pasyvius broadcast'us.
2. Šliuzas gali neperduoti broadcast į magistralę arba UDP broadcast atsakymų negauna HA konteineris (Docker be `host` tinklo, VLAN) → fallback: directed „šluota" per nurodytus subnet'us (rate-limited) ir pasyvus klausymas.
3. Magistralės apkrova (9600 baud): siuntimo eilė su 50 ms tarpu, fazių ribos, išskyrimo sąrašas.
4. Realus apkrovos perjungimas testo metu → impulsas + įspėjimas + admin.
5. HA versijos: `panel_custom`, `async_register_static_paths` (≈ HA 2024.7+), `async_forward_entry_setups`. → nustatyti `homeassistant` minimalią versiją `hacs.json`.
6. Dviguba `BusproModule` (YAML `buspro:` + config entry) — jau dabar rizika; įrankis palaikomas **tik su config entry**.
7. Licencija: nekopijuoti ar_hdl_buspro / GPL kodo ar katalogo.

**Sprendimai, kuriuos reikia priimti (rekomendacija pirmoje vietoje)**
1. UI forma: **šoninis skydelis (rekomenduojama)** vs. tik options-flow.
2. Minimali HA versija: **2024.7+ (rekomenduojama; patikrinti)**.
3. YAML-only vartotojai: **reikalauti config entry** (vėliau `async_step_import`) vs. palaikyti iškart.
4. UI kalbos: **lt + en** (rekomenduojama).
5. Pirmo testo numatytasis režimas: **„impulsas" su grąžinimu** (rekomenduojama).

**Klausimai `SmartHouseBrain` agentui (kai bus pasiekiamas)**
- Ar jūsų projekte patvirtinote `0xF00E/0xF00F` (kanalo remark) ir tikslų payload bei koduotę?
- Ar `0x000F` atsakymas visada 20 B remark be kanalo baito; kaip tvarkote lietuviškas raides?
- Kuriuose įrenginiuose `0xE548` nepadeda ir ką naudojate vietoj to?
- Kokie realūs tarpai tarp kadrų saugūs su jūsų šliuzu; ar broadcast atsakymai pasiekia HA konteinerį?
- Ar turite žinomų tipų kodų lentelę, kurią galima legaliai bendrinti (ne ar_hdl_buspro)?

## 11. Failų pokyčiai (santrauka)

**Biblioteka `custom_components/buspro/pybuspro/`**
- `helpers/enums.py` — nauji `OperateCode`: `0x000E/F`, `0xF00E/F` (patvirtinti etape 0), `0xE548/9`.
- `core/telegram.py`, `helpers/telegram_helper.py` — `operate_code_raw`, `None` apsauga.
- `buspro.py` — `add_telegram_listener/remove`, `async request(...)`.
- `transport/network_interface.py` — siuntimo eilė su minimaliu tarpu.
- **naujas** `scanner/` — `scanner.py`, `models.py`, `module_reply.py` (`0xE549`), `remarks.py` (dekoderis), `type_codes.py` (maža lentelė), `controller.py` (`BusController`).

**HA integracija `custom_components/buspro/`**
- `__init__.py` — `PLATFORMS`, `async_forward_entry_setups`, `async_unload_entry`, `BusproModule.scanner/controller/store`, WS + skydelio registracija, servisai `scan`, `test_channel`; `service_send_message` pataisymas (`operate_code` sąrašas → `bytes`).
- **nauji** `storage.py`, `websocket_api.py`, `panel.py`, `frontend/buspro-panel.js` (be build žingsnio, grynas web component), `diagnostics.py`.
- `switch.py`, `light.py`, `cover.py`, `sensor.py`, `binary_sensor.py`, `climate.py` — `async_setup_entry`, `device_info`, `async_will_remove_from_hass`.
- `manifest.json` — `dependencies`: `http`, `websocket_api`, `frontend`, `panel_custom`; versija.
- `config_flow.py` — options flow (skanavimo trukmė, tarpas, šaltinio adresas).
- `services.yaml`, `strings.json`, `translations/{en,lt,no}.json`.
- `tests/`, `.github/workflows/`, `README.md` skyrius.

## 12. Šaltiniai

- [marsh4200/ar_hdl_buspro](https://github.com/marsh4200/ar_hdl_buspro) ir [PR #41](https://github.com/marsh4200/ar_hdl_buspro/pull/41) — skanavimo eiga, `0xE548/0xE549`, laikai (tik žinioms; kodas proprietary).
- [caligo-mentis/smart-bus](https://github.com/caligo-mentis/smart-bus) — opkodų payload išdėstymas (MIT).
- [estbeetoo/node-red-contrib-hdl](https://github.com/estbeetoo/node-red-contrib-hdl) — nuoroda į oficialų „HDL-BUS Pro operation codes (Eng) Jan 08 2013" PDF.
- [Pooria-nek/RelayModule_library](https://github.com/Pooria-nek/RelayModule_library) — kanalo remark struktūra (GPL-2.0, tik žinioms).
- [HDL Buspro Setup Tool 2 vadovas](https://www.hdlaonline.com/eshop/en/support/products/manuals/buspro/buspro-systeme-hbst2/um_hdl-buspro-setup-tool-2-(2018-01-29).aspx) — „fast search", kanalų remark redagavimas.
- [eyesoft/home_assistant_buspro](https://github.com/eyesoft/home_assistant_buspro) — pirminis šio repo šaltinis (rankinis YAML).
