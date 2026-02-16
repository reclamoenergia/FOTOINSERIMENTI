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

Script interno:

```bat
pyinstaller --noconsole --onefile --name WTGOverlay src/gui.py
```

## Output

- `overlay.png` (trasparente nelle aree senza disegni)
- report nel pannello log GUI con:
  - turbine processate
  - turbine disegnate
  - turbine scartate + motivo



## Tool Orizzonte (DEM/DTM -> PNG)

È disponibile un tool dedicato per generare il profilo orizzonte da GeoTIFF e sovrapporre le turbine.

### Moduli

- `src/core/dtm_sampler.py`: campionamento quote su GeoTIFF (bilineare con fallback nearest).
- `src/core/horizon.py`: calcolo skyline, angoli turbine, marker direzione vista.
- `src/core/horizon_plot.py`: rendering Matplotlib del PNG (`horizon.png`).
- `src/gui_horizon.py`: GUI Tkinter per lanciare il tool inserendo i parametri turbine direttamente a interfaccia (max 5).

### Avvio GUI orizzonte

```bash
python src/gui_horizon.py
```

### Schema JSON supportato

```json
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
```

`range.step_m = 0` usa automaticamente il pixel size del DTM.
