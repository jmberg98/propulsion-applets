import math
import heapq
import tkinter as tk
from collections import defaultdict


class SolarSystemSubwayMap:
    G0 = 9.80665  # m/s^2

    def __init__(self, root):
        self.root = root
        self.root.title("The Solar System - Subway Map")
        self.root.geometry("1180x860")
        self.root.minsize(1040, 800)

        self.reachable_nodes = set()
        self.reachable_edges = set()
        self.current_budget = None

        container = tk.Frame(root, bg="#f3f3f3")
        container.pack(fill="both", expand=True)

        # Smaller map so the calculator is always visible
        self.canvas = tk.Canvas(
            container,
            width=1180,
            height=650,
            bg="#f3f3f3",
            highlightthickness=0
        )
        self.canvas.pack(side="bottom", fill="x")

        self.control_frame = tk.Frame(
            container,
            bg="#e6e6e6",
            padx=14,
            pady=12,
            bd=1,
            relief="ridge"
        )
        self.control_frame.pack(side="top", fill="x")

        # Smaller scale than before
        self.x_scale = 1.15
        self.y_scale = 0.5

        self.dx = 55
        self.dy = 40

        self._build_map_data()
        self._compute_shortest_paths_from_earth()
        self._build_controls()
        self.draw_map()

    def _build_controls(self):
        self.isp_var = tk.StringVar(value="450")
        self.propellant_var = tk.StringVar(value="600000")
        self.structural_var = tk.StringVar(value="40000")
        self.payload_var = tk.StringVar(value="10000")

        self.result_var = tk.StringVar(value="Enter rocket parameters below to calculate a Delta-V budget.")
        self.status_var = tk.StringVar(value="")
        self.summary_var = tk.StringVar(value="")

        tk.Label(
            self.control_frame,
            text="Rocket calculator",
            bg="#e6e6e6",
            fg="#111111",
            font=("Arial", 12, "bold")
        ).grid(row=0, column=0, columnspan=10, sticky="w", pady=(0, 8))

        tk.Label(
            self.control_frame,
            text="Δv = Isp × g0 × ln((propellant + structural + payload) / (structural + payload))",
            bg="#e6e6e6",
            fg="#222222",
            font=("Arial", 10)
        ).grid(row=1, column=0, columnspan=10, sticky="w", pady=(0, 10))

        tk.Label(
            self.control_frame,
            text="Specific impulse Isp (s):",
            bg="#e6e6e6",
            font=("Arial", 10)
        ).grid(row=2, column=0, sticky="w", padx=(0, 6))

        tk.Entry(
            self.control_frame,
            textvariable=self.isp_var,
            width=10,
            font=("Arial", 10)
        ).grid(row=2, column=1, sticky="w", padx=(0, 18))

        tk.Label(
            self.control_frame,
            text="Propellant mass (kg):",
            bg="#e6e6e6",
            font=("Arial", 10)
        ).grid(row=2, column=2, sticky="w", padx=(0, 6))

        tk.Entry(
            self.control_frame,
            textvariable=self.propellant_var,
            width=12,
            font=("Arial", 10)
        ).grid(row=2, column=3, sticky="w", padx=(0, 18))

        tk.Label(
            self.control_frame,
            text="Structural mass (kg):",
            bg="#e6e6e6",
            font=("Arial", 10)
        ).grid(row=2, column=4, sticky="w", padx=(0, 6))

        tk.Entry(
            self.control_frame,
            textvariable=self.structural_var,
            width=12,
            font=("Arial", 10)
        ).grid(row=2, column=5, sticky="w", padx=(0, 18))

        tk.Label(
            self.control_frame,
            text="Payload mass (kg):",
            bg="#e6e6e6",
            font=("Arial", 10)
        ).grid(row=2, column=6, sticky="w", padx=(0, 6))

        tk.Entry(
            self.control_frame,
            textvariable=self.payload_var,
            width=12,
            font=("Arial", 10)
        ).grid(row=2, column=7, sticky="w", padx=(0, 18))

        tk.Button(
            self.control_frame,
            text="Calculate",
            command=self.calculate_from_inputs,
            bg="#ffffff",
            font=("Arial", 10, "bold"),
            padx=10,
            pady=3
        ).grid(row=2, column=8, sticky="w", padx=(0, 8))

        tk.Button(
            self.control_frame,
            text="Clear",
            command=self.clear_highlights,
            bg="#ffffff",
            font=("Arial", 10),
            padx=10,
            pady=3
        ).grid(row=2, column=9, sticky="w")

        for child in self.control_frame.winfo_children():
            if isinstance(child, tk.Entry):
                child.bind("<Return>", lambda event: self.calculate_from_inputs())

        tk.Label(
            self.control_frame,
            textvariable=self.result_var,
            bg="#e6e6e6",
            fg="#111111",
            font=("Arial", 10, "bold"),
            justify="left",
            anchor="w"
        ).grid(row=3, column=0, columnspan=10, sticky="w", pady=(12, 2))

        tk.Label(
            self.control_frame,
            textvariable=self.status_var,
            bg="#e6e6e6",
            fg="#B22222",
            font=("Arial", 10),
            justify="left",
            anchor="w"
        ).grid(row=4, column=0, columnspan=10, sticky="w", pady=(0, 2))

        tk.Label(
            self.control_frame,
            textvariable=self.summary_var,
            bg="#e6e6e6",
            fg="#333333",
            font=("Arial", 9),
            justify="left",
            anchor="w",
            wraplength=1100
        ).grid(row=5, column=0, columnspan=10, sticky="w", pady=(6, 0))

    def _build_map_data(self):
        C = {
            "blue":   "#6FA4E3",
            "gray":   "#9B9B9B",
            "orange": "#FF8C1C",
            "gold":   "#D4A128",
            "cyan":   "#46D3F3",
            "royal":  "#244CFF",
            "red":    "#C24A35",
            "brown":  "#8B4A1E",
            "olive":  "#9A9725",
            "beige":  "#B1A89D",
            "tan":    "#BE9755",
        }

        self.nodes = {
            "earth":    {"x": 392, "y": 895, "kind": "circle",   "label": "Earth", "offset": (0, 20)},
            "leo":      {"x": 392, "y": 792, "kind": "transfer", "orientation": "h", "length": 64,
                         "label": "Low Earth Orbit\n(150 km)", "offset": (42, 0)},
            "ei":       {"x": 392, "y": 646, "kind": "transfer", "orientation": "h", "length": 118,
                         "label": "Earth Intercept", "offset": (86, 0)},
            "inter":    {"x": 392, "y": 305, "kind": "transfer", "orientation": "h", "length": 118,
                         "label": "Intercept", "offset": (0, 24)},
            "j_lo":     {"x": 392, "y": 212, "kind": "circle"},
            "jupiter":  {"x": 392, "y": 112, "kind": "circle",   "label": "Jupiter", "offset": (0, -18)},

            "moon_i":   {"x": 300, "y": 715, "kind": "circle"},
            "moon_lo":  {"x": 205, "y": 715, "kind": "circle"},
            "moon":     {"x": 110, "y": 715, "kind": "circle",   "label": "Moon", "offset": (-18, -12)},
            "geo":      {"x": 486, "y": 715, "kind": "circle",   "label": "Geostationary Orbit", "offset": (16, 0)},

            "merc_i":   {"x": 300, "y": 570, "kind": "circle"},
            "merc_lo":  {"x": 205, "y": 570, "kind": "circle"},
            "mercury":  {"x": 110, "y": 570, "kind": "circle",   "label": "Mercury", "offset": (-18, 0)},

            "venus_i":  {"x": 300, "y": 490, "kind": "circle"},
            "venus_lo": {"x": 205, "y": 490, "kind": "circle"},
            "venus":    {"x": 10,  "y": 490, "kind": "circle",   "label": "Venus", "offset": (-18, 0)},

            "saturn_i_hub": {"x": 530, "y": 395, "kind": "transfer", "orientation": "v", "length": 48},
            "saturn_lo":    {"x": 650, "y": 395, "kind": "circle"},
            "saturn":       {"x": 770, "y": 395, "kind": "circle", "label": "Saturn", "offset": (18, 0)},

            "titan_i":  {"x": 630, "y": 340, "kind": "circle"},
            "titan_lo": {"x": 690, "y": 340, "kind": "circle"},
            "titan":    {"x": 770, "y": 340, "kind": "circle",   "label": "Titan", "offset": (18, 0)},

            "uranus_i": {"x": 530, "y": 490, "kind": "circle"},
            "uranus_lo":{"x": 650, "y": 490, "kind": "circle"},
            "uranus":   {"x": 770, "y": 490, "kind": "circle",   "label": "Uranus", "offset": (18, 0)},

            "nept_i":   {"x": 530, "y": 570, "kind": "circle"},
            "nept_lo":  {"x": 650, "y": 570, "kind": "circle"},
            "neptune":  {"x": 770, "y": 570, "kind": "circle",   "label": "Neptune", "offset": (18, 0)},

            "io_i":     {"x": 323, "y": 272, "kind": "circle"},
            "io_lo":    {"x": 252, "y": 272, "kind": "circle"},
            "io":       {"x": 190, "y": 272, "kind": "circle",   "label": "Io", "offset": (-16, 0)},

            "eu_i":     {"x": 286, "y": 228, "kind": "circle"},
            "eu_lo":    {"x": 252, "y": 192, "kind": "circle"},
            "europa":   {"x": 215, "y": 148, "kind": "circle",   "label": "Europa", "offset": (-16, -8)},

            "call_i":   {"x": 455, "y": 245, "kind": "circle"},
            "call_lo":  {"x": 500, "y": 245, "kind": "circle"},
            "callisto": {"x": 585, "y": 245, "kind": "circle",   "label": "Callisto", "offset": (16, 0)},

            "gan_i":    {"x": 448, "y": 205, "kind": "circle"},
            "gan_lo":   {"x": 490, "y": 165, "kind": "circle"},
            "ganymede": {"x": 560, "y": 125, "kind": "circle",   "label": "Ganymede", "offset": (16, 0)},

            "mars_i_hub": {"x": 250, "y": 350, "kind": "transfer", "orientation": "v", "length": 56},
            "mars_lo":    {"x": 95,  "y": 350, "kind": "circle"},
            "mars":       {"x": 10,  "y": 350, "kind": "circle", "label": "Mars", "offset": (-16, 0)},

            "dei_i":    {"x": 95,  "y": 310, "kind": "circle"},
            "dei_lo":   {"x": 52,  "y": 310, "kind": "circle"},
            "deimos":   {"x": 10,  "y": 310, "kind": "circle",   "label": "Deimos", "offset": (-16, 0)},

            "pho_i":    {"x": 95,  "y": 425, "kind": "circle"},
            "pho_lo":   {"x": 52,  "y": 425, "kind": "circle"},
            "phobos":   {"x": 10,  "y": 425, "kind": "circle",   "label": "Phobos", "offset": (-16, 0)},
        }

        self.segments = [
            {"parent": "earth",   "child": "leo",      "dv": 9400,  "color": C["blue"]},
            {"parent": "leo",     "child": "ei",       "dv": 3210,  "color": C["blue"]},
            {"parent": "ei",      "child": "inter",    "dv": 3360,  "color": C["red"]},
            {"parent": "inter",   "child": "j_lo",     "dv": 17200, "color": C["brown"]},
            {"parent": "j_lo",    "child": "jupiter",  "dv": 45000, "color": C["red"]},

            {"parent": "leo",     "child": "moon_i",   "dv": 3260,  "color": C["gray"]},
            {"parent": "moon_i",  "child": "moon_lo",  "dv": 680,   "color": C["gray"]},
            {"parent": "moon_lo", "child": "moon",     "dv": 1730,  "color": C["gray"]},
            {"parent": "leo",     "child": "geo",      "dv": 3910,  "color": C["blue"]},

            {"parent": "ei",      "child": "merc_i",   "dv": 8650,  "color": C["gray"]},
            {"parent": "merc_i",  "child": "merc_lo",  "dv": 1220,  "color": C["gray"]},
            {"parent": "merc_lo", "child": "mercury",  "dv": 3060,  "color": C["gray"]},

            {"parent": "ei",      "child": "venus_i",  "dv": 340,   "color": C["orange"]},
            {"parent": "venus_i", "child": "venus_lo", "dv": 2940,  "color": C["orange"]},
            {"parent": "venus_lo","child": "venus",    "dv": 27000, "color": C["orange"]},

            {"parent": "ei",           "child": "saturn_i_hub", "dv": 4500,  "color": C["gold"]},
            {"parent": "saturn_i_hub", "child": "saturn_lo",    "dv": 10230, "color": C["gold"]},
            {"parent": "saturn_lo",    "child": "saturn",       "dv": 30000, "color": C["gold"]},
            {"parent": "saturn_i_hub", "child": "titan_i",      "dv": 3060,  "color": C["gold"]},
            {"parent": "titan_i",      "child": "titan_lo",     "dv": 660,   "color": C["gold"], "shift": (0, -12)},
            {"parent": "titan_lo",     "child": "titan",        "dv": 7600,  "color": C["gold"]},

            {"parent": "ei",       "child": "uranus_i",  "dv": 5380,  "color": C["cyan"]},
            {"parent": "uranus_i", "child": "uranus_lo", "dv": 6120,  "color": C["cyan"]},
            {"parent": "uranus_lo","child": "uranus",    "dv": 18000, "color": C["cyan"]},

            {"parent": "ei",      "child": "nept_i",    "dv": 5390,  "color": C["royal"]},
            {"parent": "nept_i",  "child": "nept_lo",   "dv": 6750,  "color": C["royal"]},
            {"parent": "nept_lo", "child": "neptune",   "dv": 19000, "color": C["royal"]},

            {"parent": "inter",   "child": "io_i",      "dv": 1030,  "color": C["olive"]},
            {"parent": "io_i",    "child": "io_lo",     "dv": 730,   "color": C["olive"]},
            {"parent": "io_lo",   "child": "io",        "dv": 1850,  "color": C["olive"]},

            {"parent": "io_i",    "child": "eu_i",      "dv": 890,   "color": C["tan"]},
            {"parent": "eu_i",    "child": "eu_lo",     "dv": 580,   "color": C["tan"]},
            {"parent": "eu_lo",   "child": "europa",    "dv": 1480,  "color": C["tan"]},

            {"parent": "inter",   "child": "call_i",    "dv": 5140,  "color": C["beige"]},
            {"parent": "call_i",  "child": "call_lo",   "dv": 70,    "color": C["olive"], "shift": (0, -12)},
            {"parent": "call_lo", "child": "callisto",  "dv": 1760,  "color": C["olive"]},

            {"parent": "inter",   "child": "gan_i",     "dv": 6700,  "color": C["gray"]},
            {"parent": "gan_i",   "child": "gan_lo",    "dv": 700,   "color": C["gray"]},
            {"parent": "gan_lo",  "child": "ganymede",  "dv": 1970,  "color": C["gray"]},

            {"parent": "inter",      "child": "mars_i_hub", "dv": 1060, "color": C["red"]},
            {"parent": "mars_i_hub", "child": "mars_lo",    "dv": 1440, "color": C["red"]},
            {"parent": "mars_lo",    "child": "mars",       "dv": 3800, "color": C["red"]},

            {"parent": "mars_i_hub", "child": "dei_i",      "dv": 990,  "color": C["tan"]},
            {"parent": "dei_i",      "child": "dei_lo",     "dv": 2,    "color": C["tan"], "shift": (0, -12)},
            {"parent": "dei_lo",     "child": "deimos",     "dv": 4,    "color": C["tan"], "shift": (0, -12)},

            {"parent": "mars_i_hub", "child": "pho_i",      "dv": 1280, "color": C["tan"]},
            {"parent": "pho_i",      "child": "pho_lo",     "dv": 3,    "color": C["tan"], "shift": (0, 12)},
            {"parent": "pho_lo",     "child": "phobos",     "dv": 8,    "color": C["tan"], "shift": (0, 12)},
        ]

        self.annotations = [
            {"text": "Low Orbit", "x": 218, "y": 735, "angle": 0},
            {"text": "Intercept", "x": 322, "y": 738, "angle": -47},

            {"text": "Low Orbit", "x": 218, "y": 583, "angle": 0},
            {"text": "Intercept", "x": 328, "y": 598, "angle": -48},

            {"text": "Low Orbit", "x": 220, "y": 503, "angle": 0},
            {"text": "Intercept", "x": 340, "y": 563, "angle": -46},

            {"text": "Low Orbit", "x": 124, "y": 352, "angle": 0},
            {"text": "Intercept", "x": 300, "y": 405, "angle": -38},

            {"text": "Low Orbit", "x": 66, "y": 294, "angle": 0},
            {"text": "Intercept", "x": 148, "y": 314, "angle": -37},

            {"text": "Low Orbit", "x": 66, "y": 444, "angle": 0},
            {"text": "Intercept", "x": 148, "y": 426, "angle": 34},

            {"text": "Low Orbit", "x": 278, "y": 270, "angle": 0},
            {"text": "Intercept", "x": 345, "y": 270, "angle": -55},

            {"text": "Low Orbit", "x": 252, "y": 192, "angle": -35},
            {"text": "Intercept", "x": 300, "y": 230, "angle": -35},

            {"text": "Low Orbit", "x": 475, "y": 244, "angle": 0},
            {"text": "Intercept", "x": 433, "y": 275, "angle": 53},

            {"text": "Low Orbit", "x": 470, "y": 184, "angle": -42},
            {"text": "Intercept", "x": 440, "y": 228, "angle": 55},

            {"text": "Low Orbit\n(5000 km)", "x": 410, "y": 175, "angle": 0},

            {"text": "Low Orbit", "x": 603, "y": 408, "angle": 0},
            {"text": "Intercept", "x": 560, "y": 446, "angle": 51},

            {"text": "Low Orbit", "x": 667, "y": 326, "angle": 0},
            {"text": "Intercept", "x": 580, "y": 360, "angle": -41},

            {"text": "Low Orbit", "x": 610, "y": 503, "angle": 0},
            {"text": "Intercept", "x": 548, "y": 535, "angle": 51},

            {"text": "Low Orbit", "x": 610, "y": 583, "angle": 0},
            {"text": "Intercept", "x": 548, "y": 597, "angle": 49},
        ]

    def _compute_shortest_paths_from_earth(self):
        adjacency = defaultdict(list)

        for seg in self.segments:
            adjacency[seg["parent"]].append((seg["child"], seg["dv"]))

        dist = {node_id: math.inf for node_id in self.nodes}
        prev = {}

        dist["earth"] = 0
        heap = [(0, "earth")]

        while heap:
            cur_dist, node = heapq.heappop(heap)
            if cur_dist != dist[node]:
                continue

            for neighbor, weight in adjacency[node]:
                new_dist = cur_dist + weight
                if new_dist < dist[neighbor]:
                    dist[neighbor] = new_dist
                    prev[neighbor] = node
                    heapq.heappush(heap, (new_dist, neighbor))

        self.shortest_dv = {k: v for k, v in dist.items() if v < math.inf}
        self.shortest_prev = prev

    def t(self, x, y):
        return self.dx + x * self.x_scale, self.dy + y * self.y_scale

    def tsx(self, value):
        return value * self.x_scale

    def tsy(self, value):
        return value * self.y_scale

    def tsu(self, value):
        return value * min(self.x_scale, self.y_scale)

    def parse_positive_float(self, text, name):
        text = text.strip().replace(",", "")
        if not text:
            raise ValueError(f"{name} is required.")
        value = float(text)
        if value <= 0:
            raise ValueError(f"{name} must be greater than 0.")
        return value

    def parse_nonnegative_float(self, text, name):
        text = text.strip().replace(",", "")
        if not text:
            raise ValueError(f"{name} is required.")
        value = float(text)
        if value < 0:
            raise ValueError(f"{name} cannot be negative.")
        return value

    def calculate_from_inputs(self):
        try:
            isp = self.parse_positive_float(self.isp_var.get(), "Specific impulse Isp")
            propellant = self.parse_nonnegative_float(self.propellant_var.get(), "Propellant mass")
            structural = self.parse_nonnegative_float(self.structural_var.get(), "Structural mass")
            payload = self.parse_nonnegative_float(self.payload_var.get(), "Payload mass")

            if propellant <= 0:
                raise ValueError("Propellant mass must be greater than 0.")

            mf = structural + payload
            m0 = propellant + mf

            if mf <= 0:
                raise ValueError("Structural mass + payload mass must be greater than 0.")

            budget = isp * self.G0 * math.log(m0 / mf)
            mass_ratio = m0 / mf

            self.current_budget = budget
            self.status_var.set("")
            self.result_var.set(
                f"m0 = {m0:,.1f} kg, mf = {mf:,.1f} kg, mass ratio = {mass_ratio:.3f}, "
                f"Delta-V budget = {budget:,.1f} m/s ({budget / 1000:.2f} km/s)"
            )

            self.update_reachability(budget)

        except ValueError as e:
            self.status_var.set(str(e))

    def update_reachability(self, budget):
        self.reachable_nodes = {
            node_id for node_id, total_dv in self.shortest_dv.items()
            if total_dv <= budget
        }

        self.reachable_edges = set()
        for node_id in self.reachable_nodes:
            cur = node_id
            while cur in self.shortest_prev:
                parent = self.shortest_prev[cur]
                self.reachable_edges.add((parent, cur))
                cur = parent

        self.update_summary()
        self.draw_map()

    def update_summary(self):
        items = []
        for node_id, node in self.nodes.items():
            if node_id in self.reachable_nodes and node.get("label"):
                label = node["label"].replace("\n", " ")
                items.append((self.shortest_dv[node_id], label))

        items.sort(key=lambda x: x[0])

        if items:
            self.summary_var.set(
                "Reachable labeled nodes: " +
                "; ".join(f"{label} ({dv:,.0f} m/s)" for dv, label in items)
            )
        else:
            self.summary_var.set("No labeled nodes are reachable with the current Delta-V budget.")

    def clear_highlights(self):
        self.reachable_nodes.clear()
        self.reachable_edges.clear()
        self.current_budget = None
        self.result_var.set("Enter rocket parameters below to calculate a Delta-V budget.")
        self.status_var.set("")
        self.summary_var.set("")
        self.draw_map()

    def draw_map(self):
        self.canvas.delete("all")

        self.canvas.create_text(
            18, 14,
            text="The Solar System",
            anchor="nw",
            fill="#111111",
            font=("Arial", 23, "bold")
        )
        self.canvas.create_text(
            18, 46,
            text="A subway map",
            anchor="nw",
            fill="#111111",
            font=("Arial", 13, "bold")
        )

        if self.current_budget is not None:
            self.canvas.create_text(
                1160, 18,
                text=f"Budget: {self.current_budget:,.0f} m/s",
                anchor="ne",
                fill="#222222",
                font=("Arial", 11, "bold")
            )

        for seg in self.segments:
            self.draw_segment(seg)

        for node_id, node in self.nodes.items():
            if node["kind"] == "transfer":
                self.draw_transfer_node(node_id, node)

        for seg in self.segments:
            self.draw_segment_label(seg)

        for node_id, node in self.nodes.items():
            if node["kind"] == "circle":
                self.draw_circle_node(node_id, node)

        for node_id, node in self.nodes.items():
            if node.get("label"):
                self.draw_node_label(node_id, node)

        for ann in self.annotations:
            x, y = self.t(ann["x"], ann["y"])
            self.canvas.create_text(
                x, y,
                text=ann["text"],
                angle=ann.get("angle", 0),
                fill="#333333",
                font=("Arial", 7, "italic")
            )

    def draw_segment(self, seg):
        p = self.nodes[seg["parent"]]
        c = self.nodes[seg["child"]]
        x1, y1 = self.t(p["x"], p["y"])
        x2, y2 = self.t(c["x"], c["y"])

        width_outer = max(10, self.tsu(16))
        width_inner = max(6, self.tsu(10))

        highlighted = (seg["parent"], seg["child"]) in self.reachable_edges

        if highlighted:
            self.canvas.create_line(
                x1, y1, x2, y2,
                fill="#FFF2A8",
                width=width_outer + 8,
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND
            )

        self.canvas.create_line(
            x1, y1, x2, y2,
            fill="#111111",
            width=width_outer,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND
        )
        self.canvas.create_line(
            x1, y1, x2, y2,
            fill=seg["color"],
            width=width_inner,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND
        )

        self.draw_arrow_marker(x1, y1, x2, y2, highlighted)

    def draw_arrow_marker(self, x1, y1, x2, y2, highlighted=False):
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length < 35:
            return

        ux = dx / length
        uy = dy / length
        px = -uy
        py = ux

        frac = 0.72 if length > 60 else 0.58
        tip_x = x1 + dx * frac
        tip_y = y1 + dy * frac

        arrow_len = max(7, self.tsu(9))
        arrow_w = max(5, self.tsu(6))

        if highlighted:
            arrow_w += 2

        base_x = tip_x - ux * arrow_len
        base_y = tip_y - uy * arrow_len

        self.canvas.create_polygon(
            tip_x, tip_y,
            base_x + px * (arrow_w / 2), base_y + py * (arrow_w / 2),
            base_x - px * (arrow_w / 2), base_y - py * (arrow_w / 2),
            fill="#FFF6C7" if highlighted else "#fff6da",
            outline=""
        )

    def draw_segment_label(self, seg):
        p = self.nodes[seg["parent"]]
        c = self.nodes[seg["child"]]
        x1, y1 = self.t(p["x"], p["y"])
        x2, y2 = self.t(c["x"], c["y"])

        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2

        sx, sy = seg.get("shift", (0, 0))
        mx += self.tsx(sx)
        my += self.tsy(sy)

        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        if angle > 90:
            angle -= 180
        if angle < -90:
            angle += 180

        highlighted = (seg["parent"], seg["child"]) in self.reachable_edges

        self.canvas.create_text(
            mx + 1, my + 1,
            text=str(seg["dv"]),
            angle=angle,
            fill="#7A5A00" if highlighted else "#111111",
            font=("Arial", 9, "italic")
        )
        self.canvas.create_text(
            mx, my,
            text=str(seg["dv"]),
            angle=angle,
            fill="#FFFBEA" if highlighted else "#fff7df",
            font=("Arial", 9, "italic")
        )

    def draw_circle_node(self, node_id, node):
        x, y = self.t(node["x"], node["y"])
        r = max(4, self.tsu(6))
        highlighted = node_id in self.reachable_nodes

        if highlighted:
            glow = r + 6
            self.canvas.create_oval(
                x - glow, y - glow, x + glow, y + glow,
                fill="#FFD54A",
                outline=""
            )

        self.canvas.create_oval(
            x - r, y - r, x + r, y + r,
            fill="#fffdf5" if highlighted else "white",
            outline="#111111",
            width=2
        )

    def draw_transfer_node(self, node_id, node):
        x, y = self.t(node["x"], node["y"])
        highlighted = node_id in self.reachable_nodes

        if node["orientation"] == "h":
            length = self.tsx(node.get("length", 60))
            x1, y1, x2, y2 = x - length / 2, y, x + length / 2, y
        else:
            length = self.tsy(node.get("length", 60))
            x1, y1, x2, y2 = x, y - length / 2, x, y + length / 2

        if highlighted:
            self.canvas.create_line(
                x1, y1, x2, y2,
                fill="#FFD54A",
                width=max(14, self.tsu(20)),
                capstyle=tk.ROUND
            )

        self.canvas.create_line(
            x1, y1, x2, y2,
            fill="#111111",
            width=max(10, self.tsu(16)),
            capstyle=tk.ROUND
        )
        self.canvas.create_line(
            x1, y1, x2, y2,
            fill="white",
            width=max(6, self.tsu(10)),
            capstyle=tk.ROUND
        )

    def draw_node_label(self, node_id, node):
        x, y = self.t(node["x"], node["y"])
        dx, dy = node.get("offset", (12, -10))
        tx = x + self.tsx(dx)
        ty = y + self.tsy(dy)

        if abs(dx) < 4:
            anchor = "n" if dy > 0 else "s"
        else:
            anchor = "w" if dx > 0 else "e"

        self.canvas.create_text(
            tx, ty,
            text=node["label"],
            anchor=anchor,
            fill="#6B4E00" if node_id in self.reachable_nodes else "#111111",
            font=("Arial", 9, "bold")
        )


if __name__ == "__main__":
    root = tk.Tk()
    app = SolarSystemSubwayMap(root)
    root.mainloop()