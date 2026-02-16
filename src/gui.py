from __future__ import annotations

import json
import math
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
        self.azimuth_min = tk.StringVar(value="-")
        self.azimuth_max = tk.StringVar(value="-")
        self._wtg_var_traces: list[tuple[tk.Variable, str]] = []

        self._build_ui()
        self._bind_live_updates()
        self._refresh_wtg_azimuths()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(root, highlightthickness=0)
        scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)

        scrollable.bind(
            "<Configure>",
            lambda _: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        canvas_window = canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(canvas_window, width=event.width))
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(sequence, lambda event: self._on_mousewheel(canvas, event))

        io_frame = ttk.LabelFrame(scrollable, text="Input")
        io_frame.pack(fill=tk.X, pady=6)
        self._file_picker_row(io_frame, "Panoramica master", self.image_path, self._pick_image)

        camera_frame = ttk.LabelFrame(scrollable, text="Camera")
        camera_frame.pack(fill=tk.X, pady=6)
        self._entry_row(camera_frame, "Camera X", self.camera_x, 0)
        self._entry_row(camera_frame, "Camera Y", self.camera_y, 1)
        self._entry_row(camera_frame, "Camera Z", self.camera_z, 2)
        self._entry_row(camera_frame, "Focale mm", self.focal_mm, 3)
        self._entry_row(camera_frame, "Sensor W mm", self.sensor_w, 4)
        self._entry_row(camera_frame, "Sensor H mm", self.sensor_h, 5)

        crop_frame = ttk.LabelFrame(scrollable, text="Crop (opzionale)")
        crop_frame.pack(fill=tk.X, pady=6)
        self._entry_row(crop_frame, "X", self.crop_x, 0)
        self._entry_row(crop_frame, "Y", self.crop_y, 1)
        self._entry_row(crop_frame, "Width", self.crop_w, 2)
        self._entry_row(crop_frame, "Height", self.crop_h, 3)

        wtg_frame = ttk.LabelFrame(scrollable, text="WTG (max 15)")
        wtg_frame.pack(fill=tk.BOTH, expand=False, pady=6)
        self._build_wtg_table(wtg_frame)

        options = ttk.LabelFrame(scrollable, text="Parametri")
        options.pack(fill=tk.X, pady=6)
        self._entry_row(options, "FOV scale", self.fov_scale, 0)
        self._entry_row(options, "Line thickness", self.line_thickness, 1)
        self._entry_row(options, "Circle thickness", self.circle_thickness, 2)
        self._entry_row(options, "Text thickness", self.text_thickness, 3)
        self._entry_row(options, "Font size", self.font_size, 4)

        ttk.Checkbutton(options, text="Disegna ID turbine", variable=self.draw_ids).grid(
            row=5, column=0, columnspan=2, sticky="w", padx=8, pady=4
        )

        colors = ttk.LabelFrame(scrollable, text="Colori")
        colors.pack(fill=tk.X, pady=6)
        self._entry_row(colors, "Linea", self.line_color, 0)
        self._entry_row(colors, "Cerchio", self.circle_color, 1)
        self._entry_row(colors, "Testo", self.text_color, 2)

        buttons = ttk.Frame(scrollable)
        buttons.pack(fill=tk.X, pady=8)
        ttk.Button(buttons, text="Azzera dati WTG", command=self.clear_wtg_data).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(buttons, text="Genera Overlay", command=self.generate_overlay).pack(side=tk.LEFT)

        log_frame = ttk.LabelFrame(scrollable, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=6)
        self.log_text = tk.Text(log_frame, height=16)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _on_mousewheel(self, canvas: tk.Canvas, event) -> None:
        if event.num == 4:
            canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            canvas.yview_scroll(1, "units")
        else:
            canvas.yview_scroll(int(-event.delta / 120), "units")

    def _build_wtg_table(self, parent: ttk.LabelFrame) -> None:
        header_labels = ["ID", "X", "Y", "Z", "Tower H (m)", "Rotor D (m)", "Azimuth (deg)"]
        for col, label in enumerate(header_labels):
            ttk.Label(parent, text=label).grid(row=0, column=col, sticky="w", padx=5, pady=4)

        for row in range(1, self.MAX_WTG + 1):
            wtg_id = tk.StringVar(value=f"WTG-{row}")
            x_var = tk.StringVar(value="")
            y_var = tk.StringVar(value="")
            z_var = tk.StringVar(value="")
            tower_h = tk.StringVar(value="")
            rotor_d = tk.StringVar(value="")
            azimuth = tk.StringVar(value="-")

            ttk.Entry(parent, textvariable=wtg_id, width=12).grid(row=row, column=0, padx=5, pady=2)
            ttk.Entry(parent, textvariable=x_var, width=12).grid(row=row, column=1, padx=5, pady=2)
            ttk.Entry(parent, textvariable=y_var, width=12).grid(row=row, column=2, padx=5, pady=2)
            ttk.Entry(parent, textvariable=z_var, width=12).grid(row=row, column=3, padx=5, pady=2)
            ttk.Entry(parent, textvariable=tower_h, width=12).grid(row=row, column=4, padx=5, pady=2)
            ttk.Entry(parent, textvariable=rotor_d, width=12).grid(row=row, column=5, padx=5, pady=2)
            ttk.Entry(parent, textvariable=azimuth, width=12, state="readonly").grid(row=row, column=6, padx=5, pady=2)

            self.wtg_rows.append(
                {
                    "id": wtg_id,
                    "x": x_var,
                    "y": y_var,
                    "z": z_var,
                    "tower_height_m": tower_h,
                    "rotor_diameter_m": rotor_d,
                    "azimuth": azimuth,
                }
            )

        stats_row = self.MAX_WTG + 1
        ttk.Label(parent, text="Azimuth min").grid(row=stats_row, column=5, sticky="e", padx=5, pady=(8, 4))
        ttk.Entry(parent, textvariable=self.azimuth_min, width=12, state="readonly").grid(
            row=stats_row, column=6, sticky="w", padx=5, pady=(8, 4)
        )
        ttk.Label(parent, text="Azimuth max").grid(row=stats_row + 1, column=5, sticky="e", padx=5, pady=(2, 6))
        ttk.Entry(parent, textvariable=self.azimuth_max, width=12, state="readonly").grid(
            row=stats_row + 1, column=6, sticky="w", padx=5, pady=(2, 6)
        )

        plot_frame = ttk.LabelFrame(parent, text="Grafico osservatore / WTG")
        plot_frame.grid(row=stats_row, column=0, columnspan=5, rowspan=2, sticky="nsew", padx=5, pady=6)
        self.position_canvas = tk.Canvas(plot_frame, width=560, height=260, bg="white", highlightthickness=1, highlightbackground="#cfcfcf")
        self.position_canvas.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    @staticmethod
    def _safe_float(value: str) -> float | None:
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def _azimuth_deg(x0: float, y0: float, xt: float, yt: float) -> float:
        return (math.degrees(math.atan2(xt - x0, yt - y0)) + 360.0) % 360.0

    def _bind_live_updates(self) -> None:
        tracked_vars: list[tk.Variable] = [self.camera_x, self.camera_y]
        for row in self.wtg_rows:
            tracked_vars.extend([row["id"], row["x"], row["y"]])

        for var in tracked_vars:
            trace_id = var.trace_add("write", lambda *_: self._refresh_wtg_azimuths())
            self._wtg_var_traces.append((var, trace_id))

    def _refresh_wtg_azimuths(self) -> None:
        cx = self._safe_float(self.camera_x.get())
        cy = self._safe_float(self.camera_y.get())
        azimuth_values: list[float] = []

        for row in self.wtg_rows:
            tx = self._safe_float(row["x"].get())
            ty = self._safe_float(row["y"].get())
            if cx is None or cy is None or tx is None or ty is None:
                row["azimuth"].set("-")
                continue
            az = self._azimuth_deg(cx, cy, tx, ty)
            row["azimuth"].set(f"{az:.2f}")
            azimuth_values.append(az)

        if azimuth_values:
            self.azimuth_min.set(f"{min(azimuth_values):.2f}")
            self.azimuth_max.set(f"{max(azimuth_values):.2f}")
        else:
            self.azimuth_min.set("-")
            self.azimuth_max.set("-")

        self._draw_position_plot(cx, cy)

    def _draw_position_plot(self, cx: float | None, cy: float | None) -> None:
        canvas = self.position_canvas
        canvas.delete("all")

        width = int(canvas.winfo_width() or canvas["width"])
        height = int(canvas.winfo_height() or canvas["height"])
        margin = 24
        points: list[tuple[str, float, float, str]] = []

        if cx is not None and cy is not None:
            points.append(("observer", cx, cy, "OBS"))

        for row in self.wtg_rows:
            tx = self._safe_float(row["x"].get())
            ty = self._safe_float(row["y"].get())
            if tx is None or ty is None:
                continue
            label = row["id"].get().strip() or "WTG"
            points.append(("wtg", tx, ty, label))

        canvas.create_rectangle(1, 1, width - 1, height - 1, outline="#e0e0e0")
        if not points:
            canvas.create_text(width // 2, height // 2, text="Inserire osservatore e WTG per visualizzare il grafico", fill="#666")
            return

        xs = [p[1] for p in points]
        ys = [p[2] for p in points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(max_x - min_x, 1.0)
        span_y = max(max_y - min_y, 1.0)
        scale = min((width - 2 * margin) / span_x, (height - 2 * margin) / span_y)

        def to_canvas(px: float, py: float) -> tuple[float, float]:
            x = margin + (px - min_x) * scale
            y = height - margin - (py - min_y) * scale
            return x, y

        canvas.create_line(margin, height - margin, width - margin, height - margin, fill="#bdbdbd")
        canvas.create_line(margin, margin, margin, height - margin, fill="#bdbdbd")
        canvas.create_text(width - margin, height - margin + 12, text="X", fill="#777")
        canvas.create_text(margin - 10, margin, text="Y", fill="#777")

        for ptype, px, py, label in points:
            cx_plot, cy_plot = to_canvas(px, py)
            if ptype == "observer":
                canvas.create_rectangle(cx_plot - 6, cy_plot - 6, cx_plot + 6, cy_plot + 6, fill="#1f77b4", outline="#1f77b4")
                canvas.create_text(cx_plot + 9, cy_plot - 10, text=label, anchor="w", fill="#1f77b4", font=("TkDefaultFont", 9, "bold"))
            else:
                canvas.create_oval(cx_plot - 4, cy_plot - 4, cx_plot + 4, cy_plot + 4, fill="#d62728", outline="#d62728")
                canvas.create_text(cx_plot + 8, cy_plot - 8, text=label, anchor="w", fill="#444")

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
            row["azimuth"].set("-")
        self._refresh_wtg_azimuths()
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
