# WTG Overlay Generator (Aerogeneratori)

Applicazione desktop Python con GUI (Tkinter) per generare overlay PNG trasparenti da sovrapporre a panoramiche fotografiche.

## Funzionalità principali (Overlay turbine)

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
│   │   ├── overlay_renderer.py
│   │   ├── dtm_sampler.py
│   │   ├── horizon.py
│   │   └── horizon_plot.py
│   ├── gui.py
│   ├── gui_horizon.py
│   ├── gui_unified.py
│   └── main.py
├── docs/
│   └── wtg_unified_algorithm.md
├── example.json
├── README.md
├── requirements.txt
└── build_scripts/
    ├── build_windows.bat
    └── hooks/
        └── hook-rasterio.py
Installazione
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller
Tool 1: Overlay turbine su panoramica
Avvio GUI
python src/gui.py
Input JSON
Vedi example.json per lo schema completo.

Regole crop
Se crop.w <= 0 o crop.h <= 0 viene generato overlay su immagine master.

Se il crop è attivo, l'overlay viene generato con dimensione crop.w x crop.h e viene applicato offset (u-crop.x, v-crop.y).

Output
overlay.png (trasparente nelle aree senza disegni)

report nel pannello log GUI con:

turbine processate

turbine disegnate

turbine scartate + motivo

Tool 2: Orizzonte (DEM/DTM -> PNG)
Tool dedicato per generare il profilo orizzonte da GeoTIFF e sovrapporre turbine.

Moduli
src/core/dtm_sampler.py: campionamento quote su GeoTIFF (bilineare con fallback nearest).

src/core/horizon.py: calcolo skyline, angoli turbine, marker direzione vista.

src/core/horizon_plot.py: rendering Matplotlib del PNG (horizon.png).

src/gui_horizon.py: GUI Tkinter per lanciare il tool inserendo i parametri turbine direttamente a interfaccia (max 5).

Avvio GUI orizzonte
python src/gui_horizon.py
Schema JSON supportato (esempio)
{
  "dtm": {"geotiff_path": "path/to/dtm.tif"},
  "observer": {"position_xyz": [281915, 4832489, 655], "eye_height_m": 1.6},
  "azimuth": {"start_deg": 350.0, "end_deg": 20.0, "step_deg": 0.2},
  "range": {"max_m": 30000, "step_m": 0},
  "view_direction": {"mode": "centroid"},
  "turbines": [
    {
      "id": "WTG01",
      "base_xyz": [283116.0, 4832098.0, 867.0],
      "tower_height_m": 119.0,
      "rotor_diameter_m": 162.0
    }
  ],
  "output": {"png_path": "horizon.png", "transparent": false}
}
range.step_m = 0 usa automaticamente il pixel size del DTM.

Tool 3: Unified Camera View
GUI principale in src/gui_unified.py per generare camera_view.png (skyline + turbine in prospettiva) e opzionalmente horizon_profile.png.


Batch shapefile punti osservatore
Modalità opzionale in `src/gui_unified.py`:

- Attivare checkbox **Batch shapefile**
- Selezionare shapefile `.shp` di punti (campo attributo obbligatorio `Nome`)
- Selezionare cartella output batch

Per ogni punto vengono generati:
- `<Nome>_camera_view.png`
- `<Nome>_horizon_profile.png` (se abilitato)

Nel batch l'intervallo azimutale è calcolato automaticamente per ogni osservatore con finestra 180° centrata sull'azimut medio circolare delle turbine (`az_start = center-90`, `az_end = center+90`).

Esempio testuale nel repo: `examples/observer_points.geojson` (3 punti, campo `Nome`).
Genera lo shapefile locale con `python examples/create_observer_shapefile.py`.

Dipendenze aggiuntive per batch:
- `pyshp`

Avvio
python src/gui_unified.py
Note operative
Salvataggio/caricamento configurazione JSON supporta tutti i parametri GUI.

Quota osservatore calcolata da DTM: Z = DTM(X,Y) + eye_height.

Quota base di ogni WTG calcolata da DTM in (X,Y).

Descrizione algoritmo in docs/wtg_unified_algorithm.md.

Build Windows (.exe)
Build Overlay (gui.py)
build_scripts\build_windows.bat
Lo script usa PyInstaller con hook dedicato (build_scripts/hooks/hook-rasterio.py) e flag espliciti per rasterio:

pyinstaller --noconsole --onefile --name WTGOverlay src/gui.py --additional-hooks-dir build_scripts/hooks --hidden-import rasterio.sample --collect-submodules rasterio --collect-data rasterio
Build Unified (gui_unified.py)
python -m PyInstaller --noconsole --onefile --name WTGUnifiedView src\gui_unified.py --additional-hooks-dir build_scripts/hooks --hidden-import rasterio.sample --collect-submodules rasterio --collect-data rasterio
Troubleshooting packaging
Se all'avvio dell'exe compare errore simile a:

ModuleNotFoundError: No module named 'rasterio.sample'
ricostruire l'exe nello stesso ambiente Python in cui rasterio è installato, usando i flag/hook sopra.
Se il problema persiste, cancellare build/ e dist/ prima di ricompilare.

