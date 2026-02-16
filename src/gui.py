from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image

from core.overlay_renderer import OverlayStyle, parse_scene_payload, render_overlay, summary_to_lines


class OverlayApp(tk.Tk):
    MAX_WTG = 15

    def __init__(self) -> None:
        super().__init__()
        self.title("WTG Overlay Generator")
        self.geometry("1100x900")

        self.image_path = tk.StringVar()

        self.camera_x = tk.StringVar(value="0.0")
        self.camera_y = tk.StringVar(value="-2000.0")
        self.camera_z = tk.StringVar(value="150.0")
        self.focal_mm = tk.StringVar(value="50.0")
        self.sensor_w = tk.StringVar(value="36.0")
        self.sensor_h = tk.StringVar(value="24.0")

        self.crop_x = tk.StringVar(value="0")
        self.crop_y = tk.StringVar(value="0")
        self.crop_w = tk.StringVar(value="0")
        self.crop_h = tk.StringVar(value="0")
        self.fov_scale = tk.StringVar(value="1.0")

        self.line_thickness = tk.StringVar(value="3")
        self.circle_thickness = tk.StringVar(value="3")
        self.text_thickness = tk.StringVar(value="1")
        self.font_size = tk.StringVar(value="18")
        self.draw_ids = tk.BooleanVar(value=True)

        self.line_color = tk.StringVar(value="#00FF00")
        self.circle_color = tk.StringVar(value="#FFA500")
        self.text_color = tk.StringVar(value="#FFFFFF")

        self.wtg_rows: list[dict[str, tk.StringVar]] = []

        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)

        io_frame = ttk.LabelFrame(root, text="Input")
        io_frame.pack(fill=tk.X, pady=6)
        self._file_picker_row(io_frame, "Panoramica master", self.image_path, self._pick_image)

        camera_frame = ttk.LabelFrame(root, text="Camera")
        camera_frame.pack(fill=tk.X, pady=6)
        self._entry_row(camera_frame, "Camera X", self.camera_x, 0)
        self._entry_row(camera_frame, "Camera Y", self.camera_y, 1)
        self._entry_row(camera_frame, "Camera Z", self.camera_z, 2)
        self._entry_row(camera_frame, "Focale mm", self.focal_mm, 3)
        self._entry_row(camera_frame, "Sensor W mm", self.sensor_w, 4)
        self._entry_row(camera_frame, "Sensor H mm", self.sensor_h, 5)

        crop_frame = ttk.LabelFrame(root, text="Crop (opzionale)")
        crop_frame.pack(fill=tk.X, pady=6)
        self._entry_row(crop_frame, "X", self.crop_x, 0)
        self._entry_row(crop_frame, "Y", self.crop_y, 1)
        self._entry_row(crop_frame, "Width", self.crop_w, 2)
        self._entry_row(crop_frame, "Height", self.crop_h, 3)

        wtg_frame = ttk.LabelFrame(root, text="WTG (max 15)")
        wtg_frame.pack(fill=tk.BOTH, expand=False, pady=6)
        self._build_wtg_table(wtg_frame)

        options = ttk.LabelFrame(root, text="Parametri")
        options.pack(fill=tk.X, pady=6)
        self._entry_row(options, "FOV scale", self.fov_scale, 0)
        self._entry_row(options, "Line thickness", self.line_thickness, 1)
        self._entry_row(options, "Circle thickness", self.circle_thickness, 2)
        self._entry_row(options, "Text thickness", self.text_thickness, 3)
        self._entry_row(options, "Font size", self.font_size, 4)

        ttk.Checkbutton(options, text="Disegna ID turbine", variable=self.draw_ids).grid(
            row=5, column=0, columnspan=2, sticky="w", padx=8, pady=4
        )

        colors = ttk.LabelFrame(root, text="Colori")
        colors.pack(fill=tk.X, pady=6)
        self._entry_row(colors, "Linea", self.line_color, 0)
        self._entry_row(colors, "Cerchio", self.circle_color, 1)
        self._entry_row(colors, "Testo", self.text_color, 2)

        buttons = ttk.Frame(root)
        buttons.pack(fill=tk.X, pady=8)
        ttk.Button(buttons, text="Azzera dati WTG", command=self.clear_wtg_data).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(buttons, text="Genera Overlay", command=self.generate_overlay).pack(side=tk.LEFT)

        log_frame = ttk.LabelFrame(root, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=6)
        self.log_text = tk.Text(log_frame, height=16)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _build_wtg_table(self, parent: ttk.LabelFrame) -> None:
        header_labels = ["ID", "X", "Y", "Z", "Tower H (m)", "Rotor D (m)"]
        for col, label in enumerate(header_labels):
            ttk.Label(parent, text=label).grid(row=0, column=col, sticky="w", padx=5, pady=4)

        for row in range(1, self.MAX_WTG + 1):
            wtg_id = tk.StringVar(value=f"WTG-{row}")
            x_var = tk.StringVar(value="")
            y_var = tk.StringVar(value="")
            z_var = tk.StringVar(value="")
            tower_h = tk.StringVar(value="")
            rotor_d = tk.StringVar(value="")

            ttk.Entry(parent, textvariable=wtg_id, width=12).grid(row=row, column=0, padx=5, pady=2)
            ttk.Entry(parent, textvariable=x_var, width=12).grid(row=row, column=1, padx=5, pady=2)
            ttk.Entry(parent, textvariable=y_var, width=12).grid(row=row, column=2, padx=5, pady=2)
            ttk.Entry(parent, textvariable=z_var, width=12).grid(row=row, column=3, padx=5, pady=2)
            ttk.Entry(parent, textvariable=tower_h, width=12).grid(row=row, column=4, padx=5, pady=2)
            ttk.Entry(parent, textvariable=rotor_d, width=12).grid(row=row, column=5, padx=5, pady=2)

            self.wtg_rows.append(
                {
                    "id": wtg_id,
                    "x": x_var,
                    "y": y_var,
                    "z": z_var,
                    "tower_height_m": tower_h,
                    "rotor_diameter_m": rotor_d,
                }
            )

    def _file_picker_row(self, parent: ttk.LabelFrame, label: str, var: tk.StringVar, command) -> None:
        row = parent.grid_size()[1]
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(parent, textvariable=var, width=80).grid(row=row, column=1, sticky="ew", padx=8, pady=4)
        ttk.Button(parent, text="Sfoglia", command=command).grid(row=row, column=2, padx=8, pady=4)
        parent.columnconfigure(1, weight=1)

    def _entry_row(self, parent, label: str, var: tk.Variable, row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(parent, textvariable=var, width=24).grid(row=row, column=1, sticky="w", padx=8, pady=4)

    def _pick_image(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.tif;*.tiff"), ("All files", "*.*")]
        )
        if path:
            self.image_path.set(path)

    def _append_log(self, line: str) -> None:
        self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)

    def clear_wtg_data(self) -> None:
        for row in self.wtg_rows:
            row["id"].set("")
            row["x"].set("")
            row["y"].set("")
            row["z"].set("")
            row["tower_height_m"].set("")
            row["rotor_diameter_m"].set("")
        self._append_log("Dati WTG azzerati.")

    def _collect_turbines(self) -> list[dict]:
        turbines = []
        for i, row in enumerate(self.wtg_rows, start=1):
            x_raw = row["x"].get().strip().lower()
            if x_raw in {"", "null", "none"}:
                continue

            y_raw = row["y"].get().strip()
            z_raw = row["z"].get().strip()
            tower_raw = row["tower_height_m"].get().strip()
            rotor_raw = row["rotor_diameter_m"].get().strip()

            if not all([y_raw, z_raw, tower_raw, rotor_raw]):
                raise ValueError(f"WTG riga {i}: compilare Y, Z, tower e rotor quando X è valorizzato")

            turbines.append(
                {
                    "id": row["id"].get().strip() or f"WTG-{i}",
                    "base_xyz": [float(x_raw), float(y_raw), float(z_raw)],
                    "tower_height_m": float(tower_raw),
                    "rotor_diameter_m": float(rotor_raw),
                }
            )

        return turbines

    def _collect_scene_payload(self) -> dict:
        payload = {
            "camera": {
                "position_xyz": [
                    float(self.camera_x.get()),
                    float(self.camera_y.get()),
                    float(self.camera_z.get()),
                ],
                "focal_mm": float(self.focal_mm.get()),
                "sensor_mm": [float(self.sensor_w.get()), float(self.sensor_h.get())],
            },
            "image": {
                "crop": {
                    "x": int(self.crop_x.get()),
                    "y": int(self.crop_y.get()),
                    "w": int(self.crop_w.get()),
                    "h": int(self.crop_h.get()),
                },
                "fov_scale": float(self.fov_scale.get()),
            },
            "turbines": self._collect_turbines(),
        }
        return payload

    def generate_overlay(self) -> None:
        self.log_text.delete("1.0", tk.END)
        try:
            image_file = Path(self.image_path.get())

            if not image_file.exists():
                raise FileNotFoundError("Selezionare una panoramica valida")

            payload = self._collect_scene_payload()
            scene = parse_scene_payload(payload)

            with Image.open(image_file) as im:
                scene.image_width, scene.image_height = im.size

            style = OverlayStyle(
                line_thickness=int(self.line_thickness.get()),
                circle_thickness=int(self.circle_thickness.get()),
                text_thickness=int(self.text_thickness.get()),
                draw_ids=bool(self.draw_ids.get()),
                font_size=int(self.font_size.get()),
                line_color=self.line_color.get(),
                circle_color=self.circle_color.get(),
                text_color=self.text_color.get(),
            )

            output_path = image_file.with_name("overlay.png")
            summary = render_overlay(scene=scene, output_path=output_path, style=style)

            params_out = image_file.with_name("overlay_params.json")
            with open(params_out, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "image_input": str(image_file),
                        "camera": {
                            "position_xyz": list(scene.camera_position),
                            "focal_mm": scene.focal_mm,
                            "sensor_mm": list(scene.sensor_mm),
                        },
                        "image": {
                            "crop": {
                                "x": scene.crop.x,
                                "y": scene.crop.y,
                                "w": scene.crop.w,
                                "h": scene.crop.h,
                            },
                            "fov_scale": scene.fov_scale,
                        },
                        "turbines": [
                            {
                                "id": t.turbine_id,
                                "base_xyz": list(t.base_xyz),
                                "tower_height_m": t.tower_height_m,
                                "rotor_diameter_m": t.rotor_diameter_m,
                            }
                            for t in scene.turbines
                        ],
                    },
                    f,
                    indent=2,
                )

            for line in summary_to_lines(summary):
                self._append_log(line)
            self._append_log(f"Parametri salvati: {params_out}")

            messagebox.showinfo("Completato", f"Overlay generato: {output_path}")
        except Exception as exc:
            self._append_log(f"Errore: {exc}")
            messagebox.showerror("Errore", str(exc))


if __name__ == "__main__":
    app = OverlayApp()
    app.mainloop()
