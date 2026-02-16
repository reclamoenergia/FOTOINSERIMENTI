from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.horizon import build_from_config
from core.horizon_plot import render_horizon_png


class HorizonApp(tk.Tk):
    MAX_TURBINES = 5

    def __init__(self) -> None:
        super().__init__()
        self.title("WTG Horizon Tool")
        self.geometry("900x760")

        self.geotiff_path = tk.StringVar()
        self.observer_x = tk.StringVar()
        self.observer_y = tk.StringVar()
        self.observer_z = tk.StringVar()
        self.eye_height_m = tk.StringVar(value="1.6")

        self.az_start_deg = tk.StringVar(value="350")
        self.az_end_deg = tk.StringVar(value="20")
        self.az_step_deg = tk.StringVar(value="0.2")

        self.max_range_m = tk.StringVar(value="30000")
        self.step_m = tk.StringVar(value="0")

        self.turbine_rows: list[dict[str, tk.StringVar]] = []
        self.output_png = tk.StringVar(value="horizon.png")
        self.transparent = tk.BooleanVar(value=False)

        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)

        io = ttk.LabelFrame(root, text="Input / Output")
        io.pack(fill=tk.X, pady=6)

        ttk.Label(io, text="GeoTIFF").grid(row=0, column=0, sticky="w", padx=8, pady=5)
        ttk.Entry(io, textvariable=self.geotiff_path, width=80).grid(row=0, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(io, text="Sfoglia", command=self._pick_geotiff).grid(row=0, column=2, padx=8, pady=5)

        ttk.Label(io, text="Output PNG").grid(row=1, column=0, sticky="w", padx=8, pady=5)
        ttk.Entry(io, textvariable=self.output_png, width=80).grid(row=1, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(io, text="Salva come", command=self._pick_png).grid(row=1, column=2, padx=8, pady=5)

        ttk.Checkbutton(io, text="Sfondo trasparente", variable=self.transparent).grid(
            row=2, column=1, sticky="w", padx=8, pady=5
        )
        io.columnconfigure(1, weight=1)

        observer = ttk.LabelFrame(root, text="Posizione osservatore")
        observer.pack(fill=tk.X, pady=6)

        ttk.Label(observer, text="X").grid(row=0, column=0, sticky="w", padx=8, pady=5)
        ttk.Entry(observer, textvariable=self.observer_x, width=18).grid(row=0, column=1, padx=8, pady=5)
        ttk.Label(observer, text="Y").grid(row=0, column=2, sticky="w", padx=8, pady=5)
        ttk.Entry(observer, textvariable=self.observer_y, width=18).grid(row=0, column=3, padx=8, pady=5)
        ttk.Label(observer, text="Z").grid(row=0, column=4, sticky="w", padx=8, pady=5)
        ttk.Entry(observer, textvariable=self.observer_z, width=18).grid(row=0, column=5, padx=8, pady=5)
        ttk.Label(observer, text="Eye height (m)").grid(row=0, column=6, sticky="w", padx=8, pady=5)
        ttk.Entry(observer, textvariable=self.eye_height_m, width=10).grid(row=0, column=7, padx=8, pady=5)

        azimuth = ttk.LabelFrame(root, text="Intervallo azimut")
        azimuth.pack(fill=tk.X, pady=6)

        ttk.Label(azimuth, text="Start (°)").grid(row=0, column=0, sticky="w", padx=8, pady=5)
        ttk.Entry(azimuth, textvariable=self.az_start_deg, width=12).grid(row=0, column=1, padx=8, pady=5)
        ttk.Label(azimuth, text="End (°)").grid(row=0, column=2, sticky="w", padx=8, pady=5)
        ttk.Entry(azimuth, textvariable=self.az_end_deg, width=12).grid(row=0, column=3, padx=8, pady=5)
        ttk.Label(azimuth, text="Step (°)").grid(row=0, column=4, sticky="w", padx=8, pady=5)
        ttk.Entry(azimuth, textvariable=self.az_step_deg, width=12).grid(row=0, column=5, padx=8, pady=5)

        ttk.Label(azimuth, text="Range max (m)").grid(row=1, column=0, sticky="w", padx=8, pady=5)
        ttk.Entry(azimuth, textvariable=self.max_range_m, width=12).grid(row=1, column=1, padx=8, pady=5)
        ttk.Label(azimuth, text="Step campionamento (m)").grid(row=1, column=2, sticky="w", padx=8, pady=5)
        ttk.Entry(azimuth, textvariable=self.step_m, width=12).grid(row=1, column=3, padx=8, pady=5)

        turbines = ttk.LabelFrame(root, text="Turbine (max 5)")
        turbines.pack(fill=tk.X, pady=6)
        self._build_turbines_table(turbines)

        buttons = ttk.Frame(root)
        buttons.pack(fill=tk.X, pady=6)
        ttk.Button(buttons, text="Genera PNG", command=self.generate).pack(side=tk.LEFT)

        log_frame = ttk.LabelFrame(root, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=6)
        self.log = tk.Text(log_frame, height=16)
        self.log.pack(fill=tk.BOTH, expand=True)

    def _pick_geotiff(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("GeoTIFF", "*.tif *.tiff"), ("All files", "*.*")])
        if path:
            self.geotiff_path.set(path)

    def _pick_png(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if path:
            self.output_png.set(path)

    def _append(self, text: str) -> None:
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)

    def _build_turbines_table(self, parent: ttk.LabelFrame) -> None:
        headers = ["ID", "X", "Y", "Z", "Tower H (m)", "Rotor D (m)"]
        for col, header in enumerate(headers):
            ttk.Label(parent, text=header).grid(row=0, column=col, sticky="w", padx=5, pady=4)

        for i in range(1, self.MAX_TURBINES + 1):
            row = {
                "id": tk.StringVar(value=f"WTG{i:02d}"),
                "x": tk.StringVar(),
                "y": tk.StringVar(),
                "z": tk.StringVar(),
                "tower_height_m": tk.StringVar(),
                "rotor_diameter_m": tk.StringVar(),
            }
            self.turbine_rows.append(row)

            ttk.Entry(parent, textvariable=row["id"], width=14).grid(row=i, column=0, padx=5, pady=3, sticky="ew")
            ttk.Entry(parent, textvariable=row["x"], width=14).grid(row=i, column=1, padx=5, pady=3, sticky="ew")
            ttk.Entry(parent, textvariable=row["y"], width=14).grid(row=i, column=2, padx=5, pady=3, sticky="ew")
            ttk.Entry(parent, textvariable=row["z"], width=14).grid(row=i, column=3, padx=5, pady=3, sticky="ew")
            ttk.Entry(parent, textvariable=row["tower_height_m"], width=14).grid(row=i, column=4, padx=5, pady=3, sticky="ew")
            ttk.Entry(parent, textvariable=row["rotor_diameter_m"], width=14).grid(row=i, column=5, padx=5, pady=3, sticky="ew")

        for col in range(len(headers)):
            parent.columnconfigure(col, weight=1)

    def _collect_turbines(self) -> list[dict]:
        turbines: list[dict] = []
        for i, row in enumerate(self.turbine_rows, start=1):
            x_raw = row["x"].get().strip()
            if x_raw == "":
                continue

            y_raw = row["y"].get().strip()
            z_raw = row["z"].get().strip()
            tower_raw = row["tower_height_m"].get().strip()
            rotor_raw = row["rotor_diameter_m"].get().strip()

            if not all([y_raw, z_raw, tower_raw, rotor_raw]):
                raise ValueError(
                    f"Turbina riga {i}: compila Y, Z, Tower H e Rotor D quando X è valorizzato"
                )

            turbines.append(
                {
                    "id": row["id"].get().strip() or f"WTG{i:02d}",
                    "base_xyz": [float(x_raw), float(y_raw), float(z_raw)],
                    "tower_height_m": float(tower_raw),
                    "rotor_diameter_m": float(rotor_raw),
                }
            )

        if not turbines:
            raise ValueError("Inserisci almeno una turbina (X, Y, Z, Tower H, Rotor D)")

        return turbines

    def _build_config(self) -> dict:
        geotiff = Path(self.geotiff_path.get().strip())
        if not geotiff.exists():
            raise FileNotFoundError("Seleziona un percorso GeoTIFF valido")

        turbines = self._collect_turbines()

        return {
            "dtm": {"geotiff_path": str(geotiff)},
            "observer": {
                "position_xyz": [
                    float(self.observer_x.get()),
                    float(self.observer_y.get()),
                    float(self.observer_z.get()),
                ],
                "eye_height_m": float(self.eye_height_m.get()),
            },
            "azimuth": {
                "start_deg": float(self.az_start_deg.get()),
                "end_deg": float(self.az_end_deg.get()),
                "step_deg": float(self.az_step_deg.get()),
            },
            "range": {
                "max_m": float(self.max_range_m.get()),
                "step_m": float(self.step_m.get()),
            },
            "view_direction": {"mode": "centroid"},
            "turbines": turbines,
            "output": {
                "png_path": self.output_png.get().strip(),
                "transparent": self.transparent.get(),
            },
        }

    def generate(self) -> None:
        self.log.delete("1.0", tk.END)
        try:
            cfg = self._build_config()

            data = build_from_config(cfg)
            render_horizon_png(
                az_plot=data["az_plot"],
                elev_horizon=data["elev_horizon"],
                turbine_markers=data["turbine_markers"],
                view_marker=data["view_marker"],
                output_path=self.output_png.get(),
                transparent=self.transparent.get(),
            )

            self._append(f"PNG creato: {self.output_png.get()}")
            for marker in data["turbine_markers"]:
                visibility = "SOPRA" if marker.visible_hub else "SOTTO"
                self._append(
                    f"{marker.turbine_id}: az={marker.azimuth_deg:.2f}°, "
                    f"base={marker.e_base_deg:.2f}°, hub={marker.e_hub_deg:.2f}°, "
                    f"hor={marker.e_horizon_deg:.2f}° -> {visibility} orizzonte"
                )

        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Errore", str(exc))
            self._append(f"Errore: {exc}")


if __name__ == "__main__":
    app = HorizonApp()
    app.mainloop()
