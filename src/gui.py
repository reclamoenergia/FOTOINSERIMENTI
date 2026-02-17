from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image

from core.overlay_renderer import OverlayStyle, load_scene_config, render_overlay, summary_to_lines


class OverlayApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("WTG Overlay Generator")
        self.geometry("860x720")

        self.json_path = tk.StringVar()
        self.image_path = tk.StringVar()

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

        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)

        io_frame = ttk.LabelFrame(root, text="Input")
        io_frame.pack(fill=tk.X, pady=6)

        self._file_picker_row(io_frame, "JSON file", self.json_path, self._pick_json)
        self._file_picker_row(io_frame, "Panoramica master", self.image_path, self._pick_image)

        crop_frame = ttk.LabelFrame(root, text="Crop (opzionale)")
        crop_frame.pack(fill=tk.X, pady=6)
        self._entry_row(crop_frame, "X", self.crop_x, 0)
        self._entry_row(crop_frame, "Y", self.crop_y, 1)
        self._entry_row(crop_frame, "Width", self.crop_w, 2)
        self._entry_row(crop_frame, "Height", self.crop_h, 3)

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

        generate_btn = ttk.Button(root, text="Genera Overlay", command=self.generate_overlay)
        generate_btn.pack(fill=tk.X, pady=8)

        log_frame = ttk.LabelFrame(root, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=6)
        self.log_text = tk.Text(log_frame, height=16)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _file_picker_row(self, parent: ttk.LabelFrame, label: str, var: tk.StringVar, command) -> None:
        row = parent.grid_size()[1]
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(parent, textvariable=var, width=80).grid(row=row, column=1, sticky="ew", padx=8, pady=4)
        ttk.Button(parent, text="Sfoglia", command=command).grid(row=row, column=2, padx=8, pady=4)
        parent.columnconfigure(1, weight=1)

    def _entry_row(self, parent, label: str, var: tk.Variable, row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(parent, textvariable=var, width=24).grid(row=row, column=1, sticky="w", padx=8, pady=4)

    def _pick_json(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if path:
            self.json_path.set(path)

    def _pick_image(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[
                ("PNG", "*.png"),
                ("JPEG", "*.jpg *.jpeg"),
                ("TIFF", "*.tif *.tiff"),
                ("All files", "*.*"),
            ]
        )
        if path:
            self.image_path.set(path)

    def _append_log(self, line: str) -> None:
        self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)

    def _parse_int(self, value: str, field: str, *, min_value: int | None = None) -> int:
        try:
            parsed = int(value)
        except ValueError as exc:
            raise ValueError(f"Campo non valido: {field} deve essere un intero") from exc

        if min_value is not None and parsed < min_value:
            raise ValueError(f"Campo non valido: {field} deve essere >= {min_value}")
        return parsed

    def _parse_float(self, value: str, field: str, *, min_value: float | None = None) -> float:
        try:
            parsed = float(value)
        except ValueError as exc:
            raise ValueError(f"Campo non valido: {field} deve essere un numero") from exc

        if min_value is not None and parsed < min_value:
            raise ValueError(f"Campo non valido: {field} deve essere >= {min_value}")
        return parsed

    def generate_overlay(self) -> None:
        self.log_text.delete("1.0", tk.END)
        try:
            json_file = Path(self.json_path.get())
            image_file = Path(self.image_path.get())

            if not json_file.exists():
                raise FileNotFoundError("Selezionare un JSON valido")
            if not image_file.exists():
                raise FileNotFoundError("Selezionare una panoramica valida")

            scene = load_scene_config(json_file)

            with Image.open(image_file) as im:
                scene.image_width, scene.image_height = im.size

            scene.crop.x = self._parse_int(self.crop_x.get(), "Crop X", min_value=0)
            scene.crop.y = self._parse_int(self.crop_y.get(), "Crop Y", min_value=0)
            scene.crop.w = self._parse_int(self.crop_w.get(), "Crop Width", min_value=0)
            scene.crop.h = self._parse_int(self.crop_h.get(), "Crop Height", min_value=0)
            scene.fov_scale = self._parse_float(self.fov_scale.get(), "FOV scale", min_value=0.1)

            style = OverlayStyle(
                line_thickness=self._parse_int(self.line_thickness.get(), "Line thickness", min_value=1),
                circle_thickness=self._parse_int(self.circle_thickness.get(), "Circle thickness", min_value=1),
                text_thickness=self._parse_int(self.text_thickness.get(), "Text thickness", min_value=0),
                draw_ids=bool(self.draw_ids.get()),
                font_size=self._parse_int(self.font_size.get(), "Font size", min_value=1),
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
                        "json_input": str(json_file),
                        "image_input": str(image_file),
                        "crop": {
                            "x": scene.crop.x,
                            "y": scene.crop.y,
                            "w": scene.crop.w,
                            "h": scene.crop.h,
                        },
                        "fov_scale": scene.fov_scale,
                        "style": {
                            "line_thickness": style.line_thickness,
                            "circle_thickness": style.circle_thickness,
                            "text_thickness": style.text_thickness,
                            "font_size": style.font_size,
                            "draw_ids": style.draw_ids,
                            "line_color": style.line_color,
                            "circle_color": style.circle_color,
                            "text_color": style.text_color,
                        },
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

