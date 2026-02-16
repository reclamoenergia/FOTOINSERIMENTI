# WTG Overlay Generator (Aerogeneratori)

Applicazione desktop Python con GUI (Tkinter) per generare un `overlay.png` trasparente da sovrapporre a panoramiche fotografiche.

## Funzionalità

- Proiezione pinhole coerente con coordinate 3D del mondo.
- Look-at automatico camera -> centroide dei mozzi turbine.
- Disegno torri (linee) e rotori (cerchi).
- Supporto crop (`x,y,w,h`) senza alterare la prospettiva.
- Parametro `fov_scale` per taratura rapida su panoramiche stitchate.
- Log turbine disegnate/scartate e motivazione.

## Struttura progetto

```text
project/
├── src/
│   ├── core/
│   │   ├── camera.py
│   │   ├── projection.py
│   │   └── overlay_renderer.py
│   ├── gui.py
│   └── main.py
├── example.json
├── README.md
├── requirements.txt
└── build_scripts/
    └── build_windows.bat
```

## Installazione

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller
```

## Esecuzione (sviluppo)

```bash
python src/gui.py
```

## Input JSON

Vedi `example.json` per lo schema completo.

## Regole crop

- Se `crop.w <= 0` o `crop.h <= 0` viene generato overlay su immagine master.
- Se il crop è attivo, l'overlay viene generato con dimensione `crop.w x crop.h` e viene applicato offset `(u-crop.x, v-crop.y)`.

## Build Windows (.exe)

```bat
build_scripts\build_windows.bat
```

Lo script usa PyInstaller con hook dedicato (`build_scripts/hooks/hook-rasterio.py`) e flag espliciti per rasterio:

```bat
pyinstaller --noconsole --onefile --name WTGOverlay src/gui.py --additional-hooks-dir build_scripts/hooks --hidden-import rasterio.sample --collect-submodules rasterio --collect-data rasterio
```

## Troubleshooting packaging

Se all'avvio dell'exe compare errore simile a:

```text
ModuleNotFoundError: No module named 'rasterio.sample'
```

ricostruire l'exe nello stesso ambiente Python in cui `rasterio` è installato e usare lo script `build_scripts\build_windows.bat` aggiornato (include hook + hidden-import/collect-submodules/data). Se il problema persiste, cancellare `build/` e `dist/` prima di ricompilare.

## Output

- `overlay.png` (trasparente nelle aree senza disegni)
- report nel pannello log GUI con:
  - turbine processate
  - turbine disegnate
  - turbine scartate + motivo

