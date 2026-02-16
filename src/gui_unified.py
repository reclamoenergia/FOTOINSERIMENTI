from __future__ import annotations

import json
from pathlib import Path
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np

from core.camera_model import camera_pose_from_forward, forward_from_az_el_deg, intrinsics_from_photo
from core.dtm import DTM
from core.horizon import azimuth_deg, compute_horizon_profile, elevation_deg, interpolate_horizon_elevation
from core.render_camera_view import render_camera_view_png
from core.render_profile import render_horizon_profile_png


class UnifiedViewApp(tk.Tk):
    MAX_TURBINES = 10

    def __init__(self) -> None:
        super().__init__()
        self.title("WTG Unified View")
        self.geometry("1250x930")

        self._init_vars()
        self._build_ui()

    def _init_vars(self) -> None:
        self.geotiff_path = tk.StringVar()
        self.output_png = tk.StringVar(value="camera_view.png")
        self.transparent = tk.BooleanVar(value=False)
        self.gen_profile = tk.BooleanVar(value=False)

        self.focal_mm = tk.StringVar(value="50")
        self.sensor_w = tk.StringVar(value="36")
        self.sensor_h = tk.StringVar(value="24")
        self.out_w = tk.StringVar(value="4000")
        self.out_h = tk.StringVar(value="3000")
        self.camera_level = tk.BooleanVar(value=True)
        self.fov_scale = tk.StringVar(value="1.0")

        self.obs_x = tk.StringVar()
        self.obs_y = tk.StringVar()
        self.eye_h = tk.StringVar(value="1.6")

        self.view_mode = tk.StringVar(value="auto")
        self.view_az = tk.StringVar(value="0.0")
        self.view_el = tk.StringVar(value="0.0")

        self.az_start = tk.StringVar(value="330")
        self.az_end = tk.StringVar(value="30")
        self.az_step = tk.StringVar(value="0.5")
        self.max_range = tk.StringVar(value="30000")
        self.sample_step = tk.StringVar(value="0")
        self.debug_points = tk.BooleanVar(value=False)

        self.turbine_rows: list[dict[str, tk.StringVar]] = []

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(root)
        top.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(top)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_io_section(left)
        self._build_camera_section(left)
        self._build_observer_section(left)
        self._build_view_section(left)
        self._build_horizon_section(left)
        self._build_turbines_section(left)

        btns = ttk.Frame(left)
        btns.pack(fill=tk.X, pady=8)
        ttk.Button(btns, text="Genera vista", command=self.generate).pack(side=tk.LEFT)

        log_box = ttk.LabelFrame(root, text="Log")
        log_box.pack(fill=tk.BOTH, expand=True, pady=6)
        self.log = tk.Text(log_box, height=12)
        self.log.pack(fill=tk.BOTH, expand=True)

    def _build_io_section(self, parent):
        f = ttk.LabelFrame(parent, text="Input / Output")
        f.pack(fill=tk.X, pady=4)
        ttk.Label(f, text="GeoTIFF DTM").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(f, textvariable=self.geotiff_path, width=70).grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        ttk.Button(f, text="Sfoglia", command=self._pick_geotiff).grid(row=0, column=2, padx=6, pady=4)

        ttk.Label(f, text="Output camera PNG").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(f, textvariable=self.output_png, width=70).grid(row=1, column=1, sticky="ew", padx=6, pady=4)
        ttk.Button(f, text="Salva come", command=self._pick_output_png).grid(row=1, column=2, padx=6, pady=4)
        ttk.Checkbutton(f, text="Sfondo trasparente", variable=self.transparent).grid(row=2, column=1, sticky="w", padx=6)
        ttk.Checkbutton(f, text="Genera anche horizon_profile.png", variable=self.gen_profile).grid(row=3, column=1, sticky="w", padx=6)
        f.columnconfigure(1, weight=1)

    def _build_camera_section(self, parent):
        f = ttk.LabelFrame(parent, text="Camera / Foto")
        f.pack(fill=tk.X, pady=4)
        entries = [
            ("Focal (mm)", self.focal_mm, 0, 0),
            ("Sensor W (mm)", self.sensor_w, 0, 2),
            ("Sensor H (mm)", self.sensor_h, 0, 4),
            ("Output width px", self.out_w, 1, 0),
            ("Output height px", self.out_h, 1, 2),
            ("FOV scale", self.fov_scale, 1, 4),
        ]
        for label, var, r, c in entries:
            ttk.Label(f, text=label).grid(row=r, column=c, sticky="w", padx=6, pady=4)
            ttk.Entry(f, textvariable=var, width=12).grid(row=r, column=c + 1, padx=6, pady=4, sticky="w")
        ttk.Checkbutton(f, text="Camera in bolla", variable=self.camera_level).grid(row=2, column=0, sticky="w", padx=6, pady=4)

    def _build_observer_section(self, parent):
        f = ttk.LabelFrame(parent, text="Osservatore")
        f.pack(fill=tk.X, pady=4)
        for i, (label, var) in enumerate((("Observer X", self.obs_x), ("Observer Y", self.obs_y), ("Eye height", self.eye_h))):
            ttk.Label(f, text=label).grid(row=0, column=i * 2, sticky="w", padx=6, pady=4)
            ttk.Entry(f, textvariable=var, width=12).grid(row=0, column=i * 2 + 1, padx=6, pady=4, sticky="w")
        ttk.Label(f, text="Quota osservatore = DTM(X,Y) + eye height").grid(row=1, column=0, columnspan=4, sticky="w", padx=6)

    def _build_view_section(self, parent):
        f = ttk.LabelFrame(parent, text="Direzione di vista")
        f.pack(fill=tk.X, pady=4)
        ttk.Radiobutton(f, text="Auto: centro turbine", variable=self.view_mode, value="auto").grid(row=0, column=0, padx=6, pady=4, sticky="w")
        ttk.Radiobutton(f, text="Manuale", variable=self.view_mode, value="manual").grid(row=0, column=1, padx=6, pady=4, sticky="w")
        ttk.Label(f, text="Azimuth view (deg)").grid(row=1, column=0, sticky="w", padx=6)
        ttk.Entry(f, textvariable=self.view_az, width=12).grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(f, text="Elevation view (deg)").grid(row=1, column=2, sticky="w", padx=6)
        ttk.Entry(f, textvariable=self.view_el, width=12).grid(row=1, column=3, sticky="w", padx=6)

    def _build_horizon_section(self, parent):
        f = ttk.LabelFrame(parent, text="Orizzonte (DTM)")
        f.pack(fill=tk.X, pady=4)
        vals = [
            ("Az start", self.az_start),
            ("Az end", self.az_end),
            ("Az step", self.az_step),
            ("Max range (m)", self.max_range),
            ("Sampling step (m)", self.sample_step),
        ]
        for i, (label, var) in enumerate(vals):
            ttk.Label(f, text=label).grid(row=0, column=i * 2, sticky="w", padx=6, pady=4)
            ttk.Entry(f, textvariable=var, width=10).grid(row=0, column=i * 2 + 1, sticky="w", padx=6, pady=4)
        ttk.Checkbutton(f, text="Mostra punti orizzonte (debug)", variable=self.debug_points).grid(row=1, column=0, columnspan=3, sticky="w", padx=6)

    def _build_turbines_section(self, parent):
        f = ttk.LabelFrame(parent, text="Turbine")
        f.pack(fill=tk.X, pady=4)
        headers = ["ID", "X", "Y", "Tower H", "Rotor D"]
        for c, h in enumerate(headers):
            ttk.Label(f, text=h).grid(row=0, column=c, padx=5, pady=3, sticky="w")

        for r in range(1, self.MAX_TURBINES + 1):
            row = {
                "id": tk.StringVar(value=f"WTG{r:02d}"),
                "x": tk.StringVar(),
                "y": tk.StringVar(),
                "th": tk.StringVar(),
                "rd": tk.StringVar(),
            }
            self.turbine_rows.append(row)
            ttk.Entry(f, textvariable=row["id"], width=10).grid(row=r, column=0, padx=3, pady=2)
            ttk.Entry(f, textvariable=row["x"], width=12).grid(row=r, column=1, padx=3, pady=2)
            ttk.Entry(f, textvariable=row["y"], width=12).grid(row=r, column=2, padx=3, pady=2)
            ttk.Entry(f, textvariable=row["th"], width=10).grid(row=r, column=3, padx=3, pady=2)
            ttk.Entry(f, textvariable=row["rd"], width=10).grid(row=r, column=4, padx=3, pady=2)

        btns = ttk.Frame(f)
        btns.grid(row=self.MAX_TURBINES + 1, column=0, columnspan=6, sticky="w", pady=6)
        ttk.Button(btns, text="Carica turbine da JSON", command=self._load_turbines_json).pack(side=tk.LEFT)
        ttk.Button(btns, text="Carica config JSON", command=self._load_config_json).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="Salva config JSON", command=self._save_config_json).pack(side=tk.LEFT, padx=6)

    def _pick_geotiff(self):
        p = filedialog.askopenfilename(filetypes=[("GeoTIFF", "*.tif *.tiff"), ("All", "*.*")])
        if p:
            self.geotiff_path.set(p)

    def _pick_output_png(self):
        p = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if p:
            self.output_png.set(p)

    def _append(self, s: str):
        self.log.insert(tk.END, s + "\n")
        self.log.see(tk.END)

    def _collect_turbines(self) -> list[dict]:
        out: list[dict] = []
        for i, r in enumerate(self.turbine_rows, start=1):
            if not r["x"].get().strip():
                continue
            vals = [r["y"].get().strip(), r["th"].get().strip(), r["rd"].get().strip()]
            if not all(vals):
                raise ValueError(f"Riga turbina {i} incompleta")
            out.append(
                {
                    "id": r["id"].get().strip() or f"WTG{i:02d}",
                    "base_xyz": [float(r["x"].get()), float(r["y"].get())],
                    "tower_height_m": float(r["th"].get()),
                    "rotor_diameter_m": float(r["rd"].get()),
                }
            )
        if not out:
            raise ValueError("Inserire almeno una turbina")
        return out

    def _load_turbines_json(self):
        p = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not p:
            return
        with Path(p).open("r", encoding="utf-8") as f:
            data = json.load(f)
        turbines = data.get("turbines", data if isinstance(data, list) else [])
        for i, r in enumerate(self.turbine_rows):
            if i < len(turbines):
                t = turbines[i]
                r["id"].set(str(t.get("id", f"WTG{i+1:02d}")))
                base = t.get("base_xyz", ["", "", ""])
                r["x"].set(str(base[0]))
                r["y"].set(str(base[1]))
                r["th"].set(str(t.get("tower_height_m", "")))
                r["rd"].set(str(t.get("rotor_diameter_m", "")))
            else:
                for k in ("x", "y", "th", "rd"):
                    r[k].set("")

    def _load_config_json(self):
        p = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not p:
            return
        with Path(p).open("r", encoding="utf-8") as f:
            cfg = json.load(f)

        self.geotiff_path.set(str(cfg.get("dtm", "")))

        observer = cfg.get("observer", {})
        self.obs_x.set(str(observer.get("x", "")))
        self.obs_y.set(str(observer.get("y", "")))
        self.eye_h.set(str(observer.get("eye_height_m", self.eye_h.get())))

        camera = cfg.get("camera", {})
        self.focal_mm.set(str(camera.get("focal_mm", self.focal_mm.get())))
        self.sensor_w.set(str(camera.get("sensor_w_mm", self.sensor_w.get())))
        self.sensor_h.set(str(camera.get("sensor_h_mm", self.sensor_h.get())))
        self.out_w.set(str(camera.get("width_px", self.out_w.get())))
        self.out_h.set(str(camera.get("height_px", self.out_h.get())))
        self.fov_scale.set(str(camera.get("fov_scale", self.fov_scale.get())))
        self.camera_level.set(bool(camera.get("camera_level", self.camera_level.get())))

        view = cfg.get("view", {})
        self.view_mode.set(str(view.get("mode", self.view_mode.get())))
        self.view_az.set(str(view.get("azimuth_deg", self.view_az.get())))
        self.view_el.set(str(view.get("elevation_deg", self.view_el.get())))

        horizon = cfg.get("horizon", {})
        self.az_start.set(str(horizon.get("az_start", self.az_start.get())))
        self.az_end.set(str(horizon.get("az_end", self.az_end.get())))
        self.az_step.set(str(horizon.get("az_step", self.az_step.get())))
        self.max_range.set(str(horizon.get("max_range_m", self.max_range.get())))
        self.sample_step.set(str(horizon.get("step_m", self.sample_step.get())))
        self.debug_points.set(bool(horizon.get("debug_points", self.debug_points.get())))

        output = cfg.get("output", {})
        self.output_png.set(str(output.get("camera_png", self.output_png.get())))
        self.transparent.set(bool(output.get("transparent", self.transparent.get())))
        self.gen_profile.set(bool(output.get("generate_horizon_profile", self.gen_profile.get())))

        for i, r in enumerate(self.turbine_rows):
            if i < len(cfg.get("turbines", [])):
                t = cfg["turbines"][i]
                base = t.get("base_xyz", ["", ""])
                r["id"].set(str(t.get("id", f"WTG{i+1:02d}")))
                r["x"].set(str(base[0]))
                r["y"].set(str(base[1]))
                r["th"].set(str(t.get("tower_height_m", "")))
                r["rd"].set(str(t.get("rotor_diameter_m", "")))
            else:
                for k in ("x", "y", "th", "rd"):
                    r[k].set("")

    def _save_config_json(self):
        p = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not p:
            return
        cfg = {
            "dtm": self.geotiff_path.get(),
            "observer": {
                "x": self.obs_x.get(),
                "y": self.obs_y.get(),
                "eye_height_m": self.eye_h.get(),
            },
            "camera": {
                "focal_mm": self.focal_mm.get(),
                "sensor_w_mm": self.sensor_w.get(),
                "sensor_h_mm": self.sensor_h.get(),
                "width_px": self.out_w.get(),
                "height_px": self.out_h.get(),
                "fov_scale": self.fov_scale.get(),
                "camera_level": self.camera_level.get(),
            },
            "view": {"mode": self.view_mode.get(), "azimuth_deg": self.view_az.get(), "elevation_deg": self.view_el.get()},
            "horizon": {
                "az_start": self.az_start.get(),
                "az_end": self.az_end.get(),
                "az_step": self.az_step.get(),
                "max_range_m": self.max_range.get(),
                "step_m": self.sample_step.get(),
                "debug_points": self.debug_points.get(),
            },
            "output": {
                "camera_png": self.output_png.get(),
                "transparent": self.transparent.get(),
                "generate_horizon_profile": self.gen_profile.get(),
            },
            "turbines": self._collect_turbines(),
        }
        with Path(p).open("w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

    def generate(self):
        self.log.delete("1.0", tk.END)
        try:
            t0 = time.perf_counter()
            geotiff = Path(self.geotiff_path.get().strip())
            if not geotiff.exists():
                raise FileNotFoundError("GeoTIFF non trovato")

            turbines = self._collect_turbines()
            ox = float(self.obs_x.get())
            oy = float(self.obs_y.get())
            eye_h = float(self.eye_h.get())
            with DTM(geotiff) as dtm:
                s = dtm.sample_nearest(ox, oy)
                if s.value is None:
                    raise ValueError("Observer fuori dal DTM o su nodata")
                oz = float(s.value) + eye_h

                for t in turbines:
                    tx, ty = t["base_xyz"]
                    ts = dtm.sample_nearest(tx, ty)
                    if ts.value is None:
                        raise ValueError(f"Turbina {t['id']} fuori dal DTM o su nodata")
                    t["base_xyz"] = [tx, ty, float(ts.value)]

            az_plot, elev_horizon, _, stats = compute_horizon_profile(
                dtm_path=geotiff,
                observer_xy=(ox, oy),
                observer_z=oz,
                az_start=float(self.az_start.get()),
                az_end=float(self.az_end.get()),
                az_step=float(self.az_step.get()),
                max_range=float(self.max_range.get()),
                step_m=float(self.sample_step.get()),
            )

            hubs = np.array([
                [t["base_xyz"][0], t["base_xyz"][1], t["base_xyz"][2] + t["tower_height_m"]] for t in turbines
            ])
            centroid = hubs.mean(axis=0)
            auto_az = azimuth_deg(ox, oy, float(centroid[0]), float(centroid[1]))
            auto_el = elevation_deg(oz, float(centroid[2]), float(np.hypot(centroid[0] - ox, centroid[1] - oy)))
            self.view_az.set(f"{auto_az:.3f}")
            if self.view_mode.get() == "auto":
                view_az = auto_az
                view_el = auto_el
            else:
                view_az = float(self.view_az.get())
                view_el = float(self.view_el.get())

            intr = intrinsics_from_photo(
                focal_mm=float(self.focal_mm.get()),
                sensor_mm=(float(self.sensor_w.get()), float(self.sensor_h.get())),
                width_px=int(self.out_w.get()),
                height_px=int(self.out_h.get()),
                fov_scale=float(self.fov_scale.get()),
            )

            forward = forward_from_az_el_deg(view_az, view_el)
            pose = camera_pose_from_forward(np.array([ox, oy, oz], dtype=float), forward)

            out_png = Path(self.output_png.get().strip() or "camera_view.png")
            cam_res = render_camera_view_png(
                output_path=out_png,
                intr=intr,
                pose=pose,
                az_plot=az_plot,
                elev_horizon_deg=elev_horizon,
                view_az_deg=view_az,
                view_elev_deg=view_el,
                turbines=turbines,
                transparent=self.transparent.get(),
            )

            if self.gen_profile.get():
                profile_path = out_png.with_name("horizon_profile.png")
                render_horizon_profile_png(
                    output_path=profile_path,
                    az_plot=az_plot,
                    elev_horizon=elev_horizon,
                    observer_xyz=(ox, oy, oz),
                    turbines=turbines,
                    focal_mm=float(self.focal_mm.get()),
                    sensor_w_mm=float(self.sensor_w.get()),
                    sensor_h_mm=float(self.sensor_h.get()),
                    view_az_deg=view_az,
                    view_elev_deg=view_el,
                    transparent=self.transparent.get(),
                )
                self._append(f"horizon_profile: {profile_path}")

            self._append(f"camera_view: {out_png}")
            self._append(f"Nodata samples: {stats['nodata_samples']}")
            self._append(f"Turbine in FOV/frame: {', '.join(cam_res.inside_ids) if cam_res.inside_ids else 'none'}")
            self._append(f"Turbine fuori FOV/frame: {', '.join(cam_res.outside_ids) if cam_res.outside_ids else 'none'}")
            for t in turbines:
                tid = t["id"]
                bx, by, bz = t["base_xyz"]
                d = max(float(np.hypot(bx - ox, by - oy)), 1e-6)
                az = azimuth_deg(ox, oy, bx, by)
                e_base = elevation_deg(oz, bz, d)
                e_hub = elevation_deg(oz, bz + t["tower_height_m"], d)
                e_tip = elevation_deg(oz, bz + t["tower_height_m"] + t["rotor_diameter_m"] * 0.5, d)
                e_hor = interpolate_horizon_elevation(az_plot, elev_horizon, az)
                self._append(
                    f"{tid}: az={az:.2f} elev_base={e_base:.2f} elev_hub={e_hub:.2f} elev_tip={e_tip:.2f} elev_horizon={e_hor:.2f}"
                )

            dt = time.perf_counter() - t0
            self._append(f"Tempo totale: {dt:.2f}s")
            messagebox.showinfo("Completato", f"Vista generata: {out_png}")
        except Exception as e:
            self._append(f"Errore: {e}")
            messagebox.showerror("Errore", str(e))


if __name__ == "__main__":
    app = UnifiedViewApp()
    app.mainloop()
