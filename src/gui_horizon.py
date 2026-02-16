from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.horizon import build_from_json_config
from core.horizon_plot import render_horizon_png


class HorizonApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("WTG Horizon Tool")
        self.geometry("900x650")

        self.json_path = tk.StringVar()
        self.output_png = tk.StringVar(value="horizon.png")
        self.transparent = tk.BooleanVar(value=False)

        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)

        io = ttk.LabelFrame(root, text="Input / Output")
        io.pack(fill=tk.X, pady=6)

        ttk.Label(io, text="Config JSON").grid(row=0, column=0, sticky="w", padx=8, pady=5)
        ttk.Entry(io, textvariable=self.json_path, width=80).grid(row=0, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(io, text="Sfoglia", command=self._pick_json).grid(row=0, column=2, padx=8, pady=5)

        ttk.Label(io, text="Output PNG").grid(row=1, column=0, sticky="w", padx=8, pady=5)
        ttk.Entry(io, textvariable=self.output_png, width=80).grid(row=1, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(io, text="Salva come", command=self._pick_png).grid(row=1, column=2, padx=8, pady=5)

        ttk.Checkbutton(io, text="Sfondo trasparente", variable=self.transparent).grid(
            row=2, column=1, sticky="w", padx=8, pady=5
        )

        io.columnconfigure(1, weight=1)

        buttons = ttk.Frame(root)
        buttons.pack(fill=tk.X, pady=6)
        ttk.Button(buttons, text="Genera PNG", command=self.generate).pack(side=tk.LEFT)

        log_frame = ttk.LabelFrame(root, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=6)
        self.log = tk.Text(log_frame, height=20)
        self.log.pack(fill=tk.BOTH, expand=True)

    def _pick_json(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if path:
            self.json_path.set(path)

    def _pick_png(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if path:
            self.output_png.set(path)

    def _append(self, text: str) -> None:
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)

    def generate(self) -> None:
        self.log.delete("1.0", tk.END)
        try:
            config_path = Path(self.json_path.get())
            if not config_path.exists():
                raise FileNotFoundError("Seleziona un file JSON valido")

            data = build_from_json_config(config_path)
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
