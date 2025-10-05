# MapSys Extractor

[🇺🇸 English](README.md) | [🇷🇴 Română](README.ro.md)

Instrumente pentru export și inspecție proiecte MapSys.

MapSys este un produs software creat de GeoTop SRL din Odorheiu Secuiesc,
România. MapSys permite generarea eficientă de planuri digitale și pregătirea,
utilizarea și interogarea datelor spațiale cu funcții specializate, având ca
scop crearea unui model de date relațional încărcat cu informații validate
topologic. Astfel de date pot fi folosite în MapSys sau în orice aplicație
GIS/gestionare de date alfanumerice.

Acest proiect open-source conține un utilitar pentru linia de comandă care te
ajută să transformi proiecte MapSys în DXF și să explorezi conținutul
proiectelor.

Deoarece formatul fișierelor nu este documentat deschis, structura lor a
trebuit să fie determinată prin examinarea fișierelelor produse de program.
Semnificația multor câmpuri este încă necunoscută. Verifică întotdeauna
rezultatul și raportează o problemă dacă nu corespunde cu sursa.

## Ce face acest proiect

- Caută un fișier „principal” MapSys (`*.pr5`) într-un director
  și citește fișierele de date asociate găsite lângă acesta
  (puncte, polilinii, texte, straturi etc.).
- Convertește ceea ce găsește într-un desen DXF standard pe care îl poți
  deschide în software CAD (AutoCAD, BricsCAD, DraftSight, vizualizatoare
  gratuite etc.).
- Cei care știu să scrie script-uri Python pot folosi librăria
  pentru prelucrarea datelor extrase și în alte moduri decât cele conținute
  de prezenta aplicație.

## Instalare

Pașii de mai jos sunt pentru începători. Ei arată cum să:

1) Instalezi Python.
2) Creezi un „mediu virtual” (environment în engleză) privat.
3) Obții proiectul de pe GitHub.
4) Îl instalezi pe calculator și să îl rulezi.

După ce faci asta o dată pe computer, data viitoare este suficient să activezi
mediul și să folosești unealta.

### 1) Instalează Python (versiunea 3.11 sau mai nouă)

- Windows:
  - Mergi pe site-ul oficial Python: `https://www.python.org/downloads/`
  - Descarcă „Python 3.x” pentru Windows și rulează instalatorul.
  - Important: Pe primul ecran, bifează „Add Python to PATH”, apoi apasă Install.
  - După instalare, deschide PowerShell și tastează:

    ```powershell
    python --version
    ```

    Ar trebui să vezi ceva de genul `Python 3.11.8` (orice 3.11+ este OK).

- macOS:
  - Vizitează `https://www.python.org/downloads/` și instalează ultimul 3.x
    pentru macOS.
  - Deschide Terminal și tastează `python3 --version` pentru confirmare.

- Linux (Ubuntu/Debian):
  - Deschide Terminal și rulează:

  ```bash
  sudo apt update && sudo apt install -y python3 python3-venv python3-pip
  ```

  - Confirmă cu: `python3 --version`

### 2) Creează un mediu virtual (păstrează lucrurile curate)

Alege un folder în care vrei să păstrezi acest proiect (de exemplu,
`D:\tools\mapsys-extractor` pe Windows sau `~/tools/mapsys-extractor` pe
macOS/Linux). Apoi:

- Windows PowerShell:

  ```powershell
  python -m venv .venv
  . .venv\Scripts\Activate.ps1
  ```

- macOS/Linux Terminal:

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

Dacă activarea a reușit, promptul tău va afișa `(.venv)` la început. Cât timp
este activ, orice librării/scripturi instalezi rămân în acest folder.

### 3) Obține proiectul de pe GitHub

Dacă ai Git instalat, poți clona sursa. Dacă nu, apasă butonul verde
„Code” pe GitHub și descarcă arhiva ZIP, apoi dezarhiveaz-o în folderul ales.

Folosind Git (recomandat):

```bash
git clone https://github.com/pyl1b/mapsys-extractor.git
echo cd mapsys-extractor
```

### 4) Instalează unealta în mediul tău

Cu mediul virtual încă activ și din folderul `mapsys-extractor`, rulează:

- Windows PowerShell:

  ```powershell
  python -m pip install --upgrade pip
  python -m pip install -e .
  ```

- macOS/Linux:

  ```bash
  python3 -m pip install --upgrade pip
  python3 -m pip install -e .
  ```

Aceasta instalează biblioteca și comanda `mapsys-extractor`.

### 5) Încearcă

Afișează ajutorul pentru a confirma că este instalat:

```bash
mapsys-ex --help
```

Mai târziu, când revii să folosești unealta, doar reactivează mediul (pasul 2)
și poți continua.

### 6) Utilizare

Pregătește un folder care conține proiectul tău MapSys. Plasează fișierul
„principal” al proiectului (ex. `ceva.pr5`) și fișierele însoțitoare în același
folder.

Creează un fișier șablon dxf. Poate conține elemente sau poate fi gol;
folosim șablonul deoarece aplicația poate fi configurată să exporte punctele
MapSys ca blocuri cu atribute, caz în care acest fișier șablon trebuie să
conțină definiția blocului. Vezi ajutorul pentru comanda `to-dxf`
(`mapsys to-dxf --help`) pentru lista de argumente legate de exportul blocurilor.

```bash
mapsys to-dxf PATH/CĂTRE/FOLDERUL/TĂU \
  --dxf-template template.dxf \
  --dxf PATH/CĂTRE/OUTPUT/proiectul-tău.dxf
```

Dacă totul merge bine, un fișier `proiectul-tău.dxf` va fi creat în același
folder cu fișierul .pr5.

## Utilizare din linia de comandă

Afișează comenzile și opțiunile disponibile:

```bash
mapsys --help
```

Toate comenzile au câteva opțiuni comune: `--debug/--no-debug`,
`--trace/--no-trace`, și `--log-file` pentru a redirecționa logurile. Versiunea
este disponibilă prin `--version`.

Exportă un singur proiect dintr-un director care conține exact un fișier `.pr5`:

```bash
mapsys to-dxf /cale/către/proiect \
  --dxf-template template.dxf \
  --dxf /cale/către/output.dxf
```

Exportă toate proiectele găsite într-un arbore de directoare (un DXF pentru
fiecare fișier `.pr5`):

```bash
mapsys to-dxf-dir /cale/către/rădăcină \
  --dxf-template template.dxf
```

Note:

- Șablonul ar trebui să definească cel puțin un bloc `POINT` cu atribute
  `NAME`, `SOURCE` și `Z`. Dacă nu există, se va crea un cerc pentru fiecare
  punct.
- Unealta derivează numele straturilor și culorile din straturile MapSys.
- Când folosești `to-dxf`, directorul trebuie să conțină un singur fișier `.pr5`.

### Export XLSX

Această optiune e mai degrabă pentru depanare; poate eventuall fi utilă foaia
în care sunt extrase punctele.

Exportă un singur proiect într-un fișier Excel:

```bash
mapsys to-xlsx /cale/către/proiect \
  --xlsx /cale/către/output.xlsx
```

Exportă toate proiectele în Excel sub un arbore de directoare:

```bash
mapsys to-xlsx-dir /cale/către/rădăcină --max-depth -1 --exclude-backup
```

Detalii:

- Foi: `NO5_points`, `TS5_texts`, `TE5_meta`, `AR5_polys`, `AS5_offsets`,
  `AL5_layers`, și dacă sunt disponibile `PR5_layers`, `PR5_after`, `PR5_fonts`.
- Coloane: structurile imbricate sunt aplatizate în mai multe coloane, iar o
  coloană `idx` este adăugată cu indexul de la 0 al rândului.
- Tipuri: numerele reale sunt formatate la 3 zecimale; necunoscutele scrise ca
  text; octeții ca șiruri hexazecimale.

## Structura proiectului

Prezentare de ansamblu a celor mai relevante foldere și fișiere:

- `mapsys/cli.py`: Interfața din linia de comandă (comenzile `to-dxf` și
  `to-dxf-dir`). Configurează logarea și încarcă variabile de mediu.
- `mapsys/__main__.py`: Punct de intrare care rulează CLI la `python -m mapsys`
  sau comanda `mapsys`.
- `mapsys/dxf/to_dxf.py`: Constructorul pentru export DXF. Conține `Builder`-ul
  care creează straturi, inserează blocuri de puncte, scrie polilinii și texte
  și salvează fișierul DXF.
- `mapsys/dxf/dxf_colors.py`: Utilitare pentru maparea culorilor și grosimilor
  de linie MapSys în valori DXF.
- `mapsys/parser/`: Extragereadin fișiere MapSys/VA50 folosite de
  proiecte:
  - `pr5_main.py`: Citește metadatele „principale” ale proiectului și
    definițiile straturilor.
  - `al5_poly_layer.py`: Maparea poliliniilor pe straturi.
  - `ar5_polys.py`: Secvențe de polilinii și atributele lor.
  - `as5_vertices.py`: Indici de vertecși ai poliliniilor.
  - `n05_points.py`: Coordonatele punctelor.
  - `te5_text_meta.py`: Metadate de poziționare și stil pentru texte.
  - `ts5_text_store.py`: Stocarea și decodarea textelor.
  - `content.py`: Agregator convenabil care le leagă între ele.
  - `mdb_support.py`: Extragerea opțională a tabelelor `.mdb/.accdb` Microsoft
    Access prin ODBC, pentru date asociate.
- `tests/`: Teste automate care verifică parseurile și exportul DXF. Include
  teste pentru exportul XLSX și comenzile CLI.

## Depanare

- Exportul DXF eșuează imediat: asigură-te că folderul tău conține exact un
  fișier `.pr5` principal și că ai furnizat o cale validă `--dxf-template`.
- Pe Windows, dacă folosești `mdb_support.py` pentru baze de date Access, s-ar
  putea să ai nevoie de driverul ODBC Microsoft Access Database Engine. Pe
  Linux, o alternativă este `mdbtools` cu unixODBC (driver `{MDBToolsODBC}`).
- Dacă `mapsys` nu este găsit, asigură-te că mediul virtual este activat și că
  ai instalat pachetul cu `pip install -e .`.

## Dezvoltare

Instalează uneltele de dezvoltare și rulează verificările:

### Sarcini comune

```bash
# Formatare
make format

# Lint
make lint

# Teste (type-check + pytest)
make test

# Repară automat probleme simple de lint
make delint
```

Punctul de intrare al CLI este `mapsys.__main__:cli` și poate fi invocat cu:

```bash
python -m mapsys --help
```

### Conventii de proiect

- Cod tipizat, module mici, nume clare.
- Preferă biblioteca standard și un set minim de dependențe.
- Urmează configurarea de formatare și linting ruff din `pyproject.toml`.
- Păstrează API-urile publice stabile; dacă le schimbi, actualizează
  `CHANGELOG.md`.

### Publicare (Release)

Pe mașina locală creează pachetul și testează-l.

```bash
pip install build twine
python -m build
twine check dist/*
```

Schimbă `## [Unreleased]` cu numele noii versiuni în `CHANGELOG.md`, apoi creează
un commit, apoi creează un tag nou și publică-l pe GitHub:

```bash
git add .
git commit -m "Release version 0.1.0"

git tag -a v0.1.0 -m "Release version 0.1.0"

git push origin v0.1.0
# sau
git push origin --tags
```

Pe pagina repository-ului GitHub, creează un Release nou. Acesta va declanșa
workflow-ul pentru publicarea în PyPi.

## Licență și atribuire

Vezi `LICENSE` pentru termenii licenței.

MapSys este un produs al GeoTop SRL (Odorheiu Secuiesc, România). Toate mărcile
înregistrate aparțin proprietarilor lor. Scopul acestui proiect este
asigurarea interoperabilității între utilizatorii de programe CAD.
Autorul nu este afiliat cu GeoTop SRL.
