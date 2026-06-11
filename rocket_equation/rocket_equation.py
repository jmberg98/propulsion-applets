import math
import tkinter as tk
from tkinter import ttk


class SubwayDeltaVApplet:
    def __init__(self, root):
        self.root = root
        self.root.title("Subway Delta-V Applet")
        self.root.geometry("1400x930")
        self.root.minsize(1200, 850)

        self._build_ui()
        self._build_map_data()
        self.update_map()

    def _build_ui(self):
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        control = ttk.Frame(self.root, padding=12)
        control.grid(row=0, column=0, sticky="ns")

        canvas_frame = ttk.Frame(self.root, padding=8)
        canvas_frame.grid(row=0, column=1, sticky="nsew")
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)

        ttk.Label(control, text="Subway ΔV Applet", font=("Arial", 16, "bold")).pack(anchor="w", pady=(0, 12))

        self.structural_var = tk.StringVar(value="2000")
        self.payload_var = tk.StringVar(value="1000")
        self.propellant_var = tk.StringVar(value="50000")
        self.isp_var = tk.StringVar(value="9000")  # treated as m/s directly, per prompt

        self._add_entry(control, "Structural Mass (kg)", self.structural_var)
        self._add_entry(control, "Payload Mass (kg)", self.payload_var)
        self._add_entry(control, "Propellant Mass (kg)", self.propellant_var)
        self._add_entry(control, "Specific Impulse (m/s)", self.isp_var)

        ttk.Button(control, text="Update Map", command=self.update_map).pack(fill="x", pady=(10, 8))

        ttk.Separator(control, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(control, text="Total ΔV Budget", font=("Arial", 11, "bold")).pack(anchor="w")
        self.dv_output_var = tk.StringVar(value="0 m/s")
        ttk.Label(control, textvariable=self.dv_output_var, font=("Arial", 14)).pack(anchor="w", pady=(2, 10))

        self.status_var = tk.StringVar(value="")
        ttk.Label(
            control,
            textvariable=self.status_var,
            foreground="red",
            wraplength=260,
            justify="left"
        ).pack(anchor="w", pady=(0, 10))

        ttk.Label(
            control,
            text=(
                "Equation used:\n"
                "ΔV = c · ln((m_struct + m_payload + m_prop) / (m_struct + m_payload))\n\n"
                "The map lights segments when the cumulative ΔV required to reach that node "
                "is less than or equal to the available ΔV budget."
            ),
            wraplength=260,
            justify="left"
        ).pack(anchor="w", pady=(6, 0))

        self.canvas = tk.Canvas(
            canvas_frame,
            width=1040,
            height=900,
            bg="#000000",
            highlightthickness=0
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.root.bind("<Return>", self.update_map)

    def _add_entry(self, parent, label, variable):
        ttk.Label(parent, text=label).pack(anchor="w", pady=(4, 0))
        entry = ttk.Entry(parent, textvariable=variable, width=22)
        entry.pack(anchor="w", fill="x", pady=(2, 4))

    def _build_map_data(self):
        # Simple labels only; swap these if you later want exact destination names.
        self.nodes = {
            # Main trunk
            "launch":  {"x": 510, "y": 860, "label": "Launch",     "show": True,  "offset": (0, 22),  "hub": True},
            "parking": {"x": 510, "y": 760, "label": "Parking",    "show": True,  "offset": (14, 0),  "hub": True},
            "hub":     {"x": 510, "y": 610, "label": "Hub",        "show": True,  "offset": (14, 0),  "hub": True},
            "upper":   {"x": 510, "y": 330, "label": "Upper Hub",  "show": True,  "offset": (14, 0),  "hub": True},
            "top1":    {"x": 510, "y": 230, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "top2":    {"x": 510, "y": 140, "label": "Top",        "show": True,  "offset": (14, -6), "hub": False},

            # Lower-left / lower-right from parking
            "ll1":     {"x": 420, "y": 680, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "ll2":     {"x": 330, "y": 680, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "ll3":     {"x": 240, "y": 680, "label": "Gray-L",     "show": True,  "offset": (-14, 0), "hub": False},
            "lr1":     {"x": 640, "y": 680, "label": "Right-Low",  "show": True,  "offset": (14, 0),  "hub": False},

            # Left branches from hub
            "gm1":     {"x": 420, "y": 560, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "gm2":     {"x": 330, "y": 560, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "gm3":     {"x": 240, "y": 560, "label": "Gray-M",     "show": True,  "offset": (-14, 0), "hub": False},

            "or1":     {"x": 420, "y": 470, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "or2":     {"x": 330, "y": 470, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "or3":     {"x": 240, "y": 470, "label": "Orange-M",   "show": True,  "offset": (-14, 0), "hub": False},

            # Right branches from hub
            "gold1":   {"x": 640, "y": 470, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "gold2":   {"x": 800, "y": 470, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "gold3":   {"x": 950, "y": 470, "label": "Gold-M",     "show": True,  "offset": (14, 0),  "hub": False},
            "gold4":   {"x": 760, "y": 400, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "gold5":   {"x": 860, "y": 400, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "gold6":   {"x": 950, "y": 400, "label": "Gold-U",     "show": True,  "offset": (14, 0),  "hub": False},

            "cyan1":   {"x": 640, "y": 540, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "cyan2":   {"x": 800, "y": 540, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "cyan3":   {"x": 950, "y": 540, "label": "Cyan",       "show": True,  "offset": (14, 0),  "hub": False},

            "blue1":   {"x": 640, "y": 620, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "blue2":   {"x": 800, "y": 620, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "blue3":   {"x": 950, "y": 620, "label": "Blue",       "show": True,  "offset": (14, 0),  "hub": False},

            # Upper left / right branches from upper hub
            "ul1":     {"x": 450, "y": 280, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "ul2":     {"x": 360, "y": 280, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "ul3":     {"x": 270, "y": 280, "label": "UL-Low",     "show": True,  "offset": (-14, 0), "hub": False},
            "ul4":     {"x": 440, "y": 240, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "ul5":     {"x": 380, "y": 200, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "ul6":     {"x": 320, "y": 160, "label": "UL-High",    "show": True,  "offset": (-14, -6), "hub": False},

            "ur1":     {"x": 610, "y": 280, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "ur2":     {"x": 690, "y": 280, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "ur3":     {"x": 770, "y": 280, "label": "UR-Low",     "show": True,  "offset": (14, 0),  "hub": False},
            "ur4":     {"x": 610, "y": 240, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "ur5":     {"x": 680, "y": 200, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "ur6":     {"x": 760, "y": 160, "label": "UR-High",    "show": True,  "offset": (14, -6), "hub": False},

            # Left-side hub and branches from upper hub
            "lhub":    {"x": 390, "y": 350, "label": "",           "show": False, "offset": (0, 0),   "hub": True},
            "lred1":   {"x": 290, "y": 350, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "lred2":   {"x": 200, "y": 350, "label": "Left-Red",   "show": True,  "offset": (-14, 0), "hub": False},

            "ltop1":   {"x": 320, "y": 280, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "ltop2":   {"x": 260, "y": 240, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "ltop3":   {"x": 200, "y": 240, "label": "Left-Top",   "show": True,  "offset": (-14, 0), "hub": False},

            "lbot1":   {"x": 320, "y": 420, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "lbot2":   {"x": 260, "y": 420, "label": "",           "show": False, "offset": (0, 0),   "hub": False},
            "lbot3":   {"x": 200, "y": 420, "label": "Left-Bot",   "show": True,  "offset": (-14, 0), "hub": False},
        }

        C = {
            "blue":   "#5FA8FF",
            "gray":   "#9A9A9A",
            "orange": "#FF8C1A",
            "gold":   "#D7A22A",
            "cyan":   "#43C8E8",
            "royal":  "#244EFF",
            "red":    "#C24832",
            "brown":  "#A0572C",
            "olive":  "#9A9727",
            "beige":  "#B4AAA0",
            "tan":    "#C7A15A",
        }

        # All visible ΔV values from the supplied image are encoded below.
        self.segments = [
            # Main trunk
            {"parent": "launch",  "child": "parking", "dv": 9400,  "color": C["blue"]},
            {"parent": "parking", "child": "hub",     "dv": 3210,  "color": C["blue"]},
            {"parent": "hub",     "child": "upper",   "dv": 3360,  "color": C["red"]},
            {"parent": "upper",   "child": "top1",    "dv": 17200, "color": C["brown"]},
            {"parent": "top1",    "child": "top2",    "dv": 45000, "color": C["red"]},

            # Lower left / lower right from parking
            {"parent": "parking", "child": "ll1",     "dv": 3260,  "color": C["gray"]},
            {"parent": "ll1",     "child": "ll2",     "dv": 680,   "color": C["gray"]},
            {"parent": "ll2",     "child": "ll3",     "dv": 1730,  "color": C["gray"]},
            {"parent": "parking", "child": "lr1",     "dv": 3910,  "color": C["blue"]},

            # Left branches from hub
            {"parent": "hub",     "child": "gm1",     "dv": 8650,  "color": C["gray"]},
            {"parent": "gm1",     "child": "gm2",     "dv": 1220,  "color": C["gray"]},
            {"parent": "gm2",     "child": "gm3",     "dv": 3060,  "color": C["gray"]},

            {"parent": "hub",     "child": "or1",     "dv": 340,   "color": C["orange"]},
            {"parent": "or1",     "child": "or2",     "dv": 2940,  "color": C["orange"]},
            {"parent": "or2",     "child": "or3",     "dv": 27000, "color": C["orange"]},

            # Right branches from hub
            {"parent": "hub",     "child": "gold1",   "dv": 4500,  "color": C["gold"]},
            {"parent": "gold1",   "child": "gold2",   "dv": 10230, "color": C["gold"]},
            {"parent": "gold2",   "child": "gold3",   "dv": 30000, "color": C["gold"]},
            {"parent": "gold1",   "child": "gold4",   "dv": 3060,  "color": C["gold"]},
            {"parent": "gold4",   "child": "gold5",   "dv": 660,   "color": C["gold"], "shift": (0, -6)},
            {"parent": "gold5",   "child": "gold6",   "dv": 7600,  "color": C["gold"]},

            {"parent": "hub",     "child": "cyan1",   "dv": 5380,  "color": C["cyan"]},
            {"parent": "cyan1",   "child": "cyan2",   "dv": 6120,  "color": C["cyan"]},
            {"parent": "cyan2",   "child": "cyan3",   "dv": 18000, "color": C["cyan"]},

            {"parent": "hub",     "child": "blue1",   "dv": 5390,  "color": C["royal"]},
            {"parent": "blue1",   "child": "blue2",   "dv": 6750,  "color": C["royal"]},
            {"parent": "blue2",   "child": "blue3",   "dv": 19000, "color": C["royal"]},

            # Upper-left branches
            {"parent": "upper",   "child": "ul1",     "dv": 1030,  "color": C["olive"]},
            {"parent": "ul1",     "child": "ul2",     "dv": 730,   "color": C["olive"]},
            {"parent": "ul2",     "child": "ul3",     "dv": 1850,  "color": C["olive"]},

            {"parent": "ul1",     "child": "ul4",     "dv": 890,   "color": C["tan"]},
            {"parent": "ul4",     "child": "ul5",     "dv": 580,   "color": C["tan"]},
            {"parent": "ul5",     "child": "ul6",     "dv": 1480,  "color": C["tan"]},

            # Upper-right branches
            {"parent": "upper",   "child": "ur1",     "dv": 5140,  "color": C["beige"]},
            {"parent": "ur1",     "child": "ur2",     "dv": 70,    "color": C["olive"], "shift": (0, -8)},
            {"parent": "ur2",     "child": "ur3",     "dv": 1760,  "color": C["olive"]},

            {"parent": "upper",   "child": "ur4",     "dv": 6700,  "color": C["gray"]},
            {"parent": "ur4",     "child": "ur5",     "dv": 700,   "color": C["gray"]},
            {"parent": "ur5",     "child": "ur6",     "dv": 1970,  "color": C["gray"]},

            # Left-side hub and its branches
            {"parent": "upper",   "child": "lhub",    "dv": 1060,  "color": C["red"]},
            {"parent": "lhub",    "child": "lred1",   "dv": 1440,  "color": C["red"]},
            {"parent": "lred1",   "child": "lred2",   "dv": 3800,  "color": C["red"]},

            {"parent": "lhub",    "child": "ltop1",   "dv": 990,   "color": C["tan"]},
            {"parent": "ltop1",   "child": "ltop2",   "dv": 2,     "color": C["tan"], "shift": (0, -8)},
            {"parent": "ltop2",   "child": "ltop3",   "dv": 4,     "color": C["tan"], "shift": (0, -8)},

            {"parent": "lhub",    "child": "lbot1",   "dv": 1280,  "color": C["tan"]},
            {"parent": "lbot1",   "child": "lbot2",   "dv": 3,     "color": C["tan"], "shift": (0, 8)},
            {"parent": "lbot2",   "child": "lbot3",   "dv": 8,     "color": C["tan"], "shift": (0, 8)},
        ]

        # Cumulative ΔV to each node from launch
        self.cumulative_dv = {"launch": 0}
        for seg in self.segments:
            self.cumulative_dv[seg["child"]] = self.cumulative_dv[seg["parent"]] + seg["dv"]

    def parse_float(self, value, name):
        try:
            v = float(value.replace(",", "").strip())
        except Exception:
            raise ValueError(f"Invalid value for {name}.")
        if v < 0:
            raise ValueError(f"{name} must be non-negative.")
        return v

    def compute_budget(self):
        structural = self.parse_float(self.structural_var.get(), "Structural Mass")
        payload = self.parse_float(self.payload_var.get(), "Payload Mass")
        propellant = self.parse_float(self.propellant_var.get(), "Propellant Mass")
        c = self.parse_float(self.isp_var.get(), "Specific Impulse")

        dry_mass = structural + payload
        if dry_mass <= 0:
            raise ValueError("Structural Mass + Payload Mass must be greater than zero.")

        wet_mass = dry_mass + propellant
        if wet_mass <= dry_mass:
            return 0.0

        return c * math.log(wet_mass / dry_mass)

    def darken(self, hex_color, factor=0.28):
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        r = int(r * factor)
        g = int(g * factor)
        b = int(b * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

    def reachable(self, node_id, budget):
        return budget >= self.cumulative_dv.get(node_id, float("inf"))

    def update_map(self, event=None):
        try:
            budget = self.compute_budget()
            self.dv_output_var.set(f"{budget:,.0f} m/s")
            self.status_var.set("")
        except ValueError as e:
            budget = 0.0
            self.dv_output_var.set("0 m/s")
            self.status_var.set(str(e))

        self.draw_map(budget)

    def draw_map(self, budget):
        self.canvas.delete("all")

        self.canvas.create_text(
            18, 18,
            anchor="nw",
            text="Simplified ΔV Subway Map",
            fill="white",
            font=("Arial", 15, "bold")
        )

        self.canvas.create_text(
            18, 42,
            anchor="nw",
            text=f"Available ΔV Budget: {budget:,.0f} m/s",
            fill="#d7ffd9",
            font=("Arial", 11)
        )

        # Draw segments first
        for seg in self.segments:
            self.draw_segment(seg, budget)

        # Draw nodes on top
        for node_id, node in self.nodes.items():
            self.draw_node(node_id, node, budget)

    def draw_segment(self, seg, budget):
        p = self.nodes[seg["parent"]]
        c = self.nodes[seg["child"]]

        x1, y1 = p["x"], p["y"]
        x2, y2 = c["x"], c["y"]

        active = self.reachable(seg["child"], budget)
        color = seg["color"] if active else self.darken(seg["color"], 0.28)

        # thicker dark underlay for readability
        self.canvas.create_line(
            x1, y1, x2, y2,
            fill="#111111",
            width=18,
            capstyle=tk.ROUND
        )
        self.canvas.create_line(
            x1, y1, x2, y2,
            fill=color,
            width=12,
            capstyle=tk.ROUND
        )

        # Label position: midpoint + perpendicular offset
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy) or 1.0

        ox = (-dy / length) * 12
        oy = (dx / length) * 12

        shift = seg.get("shift", (0, 0))
        tx = mx + ox + shift[0]
        ty = my + oy + shift[1]

        text_color = "#fff2c6" if active else "#a9a9a9"

        self.canvas.create_text(
            tx, ty,
            text=str(seg["dv"]),
            fill=text_color,
            font=("Arial", 9, "bold")
        )

    def draw_node(self, node_id, node, budget):
        x, y = node["x"], node["y"]
        active = self.reachable(node_id, budget)

        r = 8 if node.get("hub", False) else 6
        fill = "white" if active else "#1c1c1c"
        outline = "#7dff94" if active else "#cfcfcf"

        self.canvas.create_oval(
            x - r, y - r, x + r, y + r,
            fill=fill,
            outline=outline,
            width=2
        )

        if node.get("show", False) and node.get("label"):
            dx, dy = node.get("offset", (12, -10))
            if abs(dx) < 4:
                anchor = "n" if dy > 0 else "s"
            else:
                anchor = "w" if dx > 0 else "e"

            label_color = "#e6ffe8" if active else "#9c9c9c"

            self.canvas.create_text(
                x + dx, y + dy,
                text=node["label"],
                fill=label_color,
                anchor=anchor,
                font=("Arial", 10, "bold")
            )


if __name__ == "__main__":
    root = tk.Tk()
    app = SubwayDeltaVApplet(root)
    root.mainloop()