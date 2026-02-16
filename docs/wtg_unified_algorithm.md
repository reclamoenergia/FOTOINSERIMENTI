# WTG Unified View – Descrizione algoritmo

Questo documento descrive il flusso dell'algoritmo usato dalla GUI `src/gui_unified.py` per generare:

- `camera_view.png` (vista prospettica con skyline + turbine)
- opzionalmente `horizon_profile.png`

## 1) Input dei parametri

La GUI raccoglie:

- percorso DTM GeoTIFF
- parametri osservatore (`x`, `y`, `eye_height_m`)
- parametri camera (focale, sensore, risoluzione, scala FOV)
- impostazioni orizzonte (intervallo azimutale, passo, range)
- lista turbine (`id`, `x`, `y`, `tower_height_m`, `rotor_diameter_m`)
- output (`camera_png`, trasparenza, profilo orizzonte opzionale)

La configurazione completa può essere salvata/ricaricata in JSON.

## 2) Quota da DTM (osservatore + turbine)

### Osservatore

La quota osservatore non è inserita manualmente:

1. si campiona il DTM in `(obs_x, obs_y)` con nearest;
2. si verifica che il campione sia valido (non nodata, dentro raster);
3. si calcola `obs_z = quota_dtm + eye_height_m`.

### Turbine

Per ogni turbina:

1. si usa la coppia `(x, y)` inserita in GUI/JSON;
2. si campiona la quota base dal DTM;
3. si compone `base_xyz = [x, y, z_dtm]`;
4. in caso di nodata/fuori DTM si blocca l'elaborazione con errore esplicito.

In questo modo tutte le quote base sono coerenti con il terreno reale del GeoTIFF.

## 3) Calcolo profilo orizzonte

Con `compute_horizon_profile(...)` viene calcolato lo skyline DTM dal punto osservatore, usando:

- range azimutale `az_start ... az_end`
- passo `az_step`
- raggio massimo `max_range`
- passo campionamento `step_m` (o automatico se 0)

Output principali:

- `az_plot`: vettore azimutale
- `elev_horizon`: elevazione orizzonte per ciascun azimut
- statistiche campionamento (`nodata_samples`, ecc.)

## 4) Direzione della camera

La direzione può essere:

- **Auto**: verso il centroide dei mozzi turbine;
- **Manuale**: azimut/elevazione inseriti dall'utente.

In auto:

1. si costruiscono i mozzi `hub = base_z + tower_height_m`;
2. si calcola il centroide 3D dei mozzi;
3. si ricavano azimut/elevazione di vista dal punto osservatore.

## 5) Modello camera e pose

Si ricavano le intrinseche pinhole con `intrinsics_from_photo(...)` da:

- focale
- sensore
- risoluzione
- `fov_scale`

Poi si crea il vettore `forward` da azimut/elevazione e la posa camera 3D con `camera_pose_from_forward(...)`.

## 6) Rendering

### `camera_view.png`

`render_camera_view_png(...)` riceve:

- intrinseche + posa
- profilo orizzonte (`az_plot`, `elev_horizon`)
- lista turbine con quote base già campionate da DTM

e disegna skyline + elementi turbine in prospettiva, con output trasparente opzionale.

### `horizon_profile.png` (opzionale)

Se abilitato, `render_horizon_profile_png(...)` produce il grafico del profilo orizzonte e dei marker turbine.

## 7) Report e diagnostica

Nel log GUI vengono riportati:

- path output generati
- numero campioni nodata
- turbine dentro/fuori FOV
- per ogni turbina: azimut, elevazioni (base/mozzo/pala), elevazione orizzonte interpolata
- tempo totale di esecuzione

## 8) JSON di configurazione

Il JSON salvato include tutti i parametri usati dalla GUI:

- `dtm`
- `observer`
- `camera`
- `view`
- `horizon`
- `output`
- `turbines`

Il caricamento JSON ripristina la sessione (inclusa la tabella turbine), così da poter rieseguire la stessa configurazione senza reinserimento manuale.
