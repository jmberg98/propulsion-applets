import tkinter as tk
from tkinter import ttk
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk
)
from scipy.optimize import minimize_scalar


# -----------------------------------------------------------------
# Governing equations
# -----------------------------------------------------------------
def m_ps(c, F, eta, alpha):
    return alpha * F * c / (2.0 * eta)


def m_p(c, F, t):
    return F * t / c


def stuhlinger_velocity(eta, alpha, t):
    return np.sqrt(2.0 * eta * t / alpha)


def epsilon(eta, alpha, t, dV):
    return alpha * dV**2 / (2.0 * eta * t)


def payload_ratio_c(c, eta, alpha, t, dV):
    z = dV / c
    e = np.exp(-np.clip(z, 0.0, 700.0))
    return e - (alpha * c**2 / (2.0 * eta * t)) * (1.0 - e)


def payload_ratio_z(z, eps):
    z   = np.asarray(z, dtype=float)
    e   = np.exp(-np.clip(z, 0.0, 700.0))
    return e - eps * (1.0 - e) / (z**2)


def find_copt(eta, alpha, t, dV):
    eps = epsilon(eta, alpha, t, dV)

    z_grid  = np.logspace(-4, 2, 20000)
    lam_g   = payload_ratio_z(z_grid, eps)
    lam_g[~np.isfinite(lam_g)] = -np.inf
    i       = int(np.argmax(lam_g))

    z_lo = z_grid[max(i - 2, 0)]
    z_hi = z_grid[min(i + 2, len(z_grid) - 1)]
    if z_hi <= z_lo:
        z_lo = 0.5 * z_grid[i]
        z_hi = 2.0 * z_grid[i]

    res   = minimize_scalar(
        lambda z: -payload_ratio_z(z, eps),
        bounds=(z_lo, z_hi),
        method="bounded",
        options={"xatol": 1e-12},
    )
    z_opt   = res.x
    lam_opt = float(payload_ratio_z(z_opt, eps))
    c_opt   = dV / z_opt
    return c_opt, lam_opt, eps


# -----------------------------------------------------------------
# Classification helpers
# -----------------------------------------------------------------
def classify_thruster(c):
    if c < 1_470:
        return "Cold Gas"
    elif c < 3_920:
        return "Resistojet"
    elif c < 11_770:
        return "Arcjet"
    elif c < 24_500:
        return "Hall Thruster / PPT"
    elif c < 78_500:
        return "Gridded Ion Engine"
    else:
        return "MPD / VASIMR"


def classify_power_source(alpha):
    if alpha >= 5.0:
        return "Chemical (Rankine)"
    elif alpha >= 1.0:
        return "Chemical / RTG"
    elif alpha >= 0.1:
        return "RTG / Solar (deep-space)"
    elif alpha >= 0.01:
        return "Solar (near-Earth)"
    elif alpha >= 0.001:
        return "Nuclear fission"
    else:
        return "Nuclear (advanced)"


G0 = 9.80665


# -----------------------------------------------------------------
# Tkinter application
# -----------------------------------------------------------------
class StuhlingerApp:
    INPUT_DEFS = [
        ("eta",    "Efficiency η",              0.65),
        ("F",      "Thrust F [N]",              1.0 ),
        ("alpha",  "Specific mass α [kg/W]",    0.02),
        ("t_days", "Mission time tₘ [days]",    180.0),
        ("dV",     "Delta-V ΔV [m/s]",          3000.0),
    ]

    def __init__(self, root):
        self.root = root
        root.title("Stuhlinger Curve Applet")
        root.geometry("1200x780")

        main = ttk.Frame(root)
        main.pack(fill=tk.BOTH, expand=True)

        plot_frame = ttk.Frame(main)
        plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.fig      = Figure(figsize=(9, 7), dpi=100)
        self.ax_mass  = self.fig.add_subplot(2, 1, 1)
        self.ax_obj   = self.fig.add_subplot(2, 1, 2)

        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        NavigationToolbar2Tk(self.canvas, plot_frame)

        ctrl = ttk.Frame(main, padding=12)
        ctrl.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Label(ctrl, text="Inputs",
                  font=("Segoe UI", 13, "bold")).pack(anchor=tk.W, pady=(0, 6))

        self.entries = {}
        self.power_src_var = tk.StringVar()

        for key, label, default in self.INPUT_DEFS:
            row = ttk.Frame(ctrl)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=label, width=24).pack(side=tk.LEFT)
            ent = ttk.Entry(row, width=12, justify="right")
            ent.insert(0, str(default))
            ent.pack(side=tk.RIGHT)
            ent.bind("<Return>",   lambda e: self.update())
            ent.bind("<FocusOut>", lambda e: self.update())
            self.entries[key] = ent

            if key == "alpha":
                sub = ttk.Frame(ctrl)
                sub.pack(fill=tk.X, pady=(0, 4))
                ttk.Label(sub, text="", width=4).pack(side=tk.LEFT)
                ttk.Label(
                    sub,
                    textvariable=self.power_src_var,
                    foreground="#8B4513",
                    font=("Consolas", 9, "italic"),
                    anchor="e",
                ).pack(side=tk.RIGHT)

        ttk.Button(ctrl, text="Update", command=self.update)\
            .pack(fill=tk.X, pady=(10, 0))

        ttk.Separator(ctrl, orient="horizontal").pack(fill=tk.X, pady=10)

        ttk.Label(ctrl, text="Outputs",
                  font=("Segoe UI", 13, "bold")).pack(anchor=tk.W, pady=(0, 6))

        self.out_vars   = {}
        self.out_labels = {}

        self.isp_vch_var  = tk.StringVar()
        self.isp_copt_var = tk.StringVar()
        self.thruster_var = tk.StringVar()

        for key, label in [
            ("Vch",  "Stuhlinger Vch [m/s]"),
            ("Copt", "Optimum Copt [m/s]"),
            ("err",  "Error E [%]"),
            ("eps",  "ε (dimensionless)"),
            ("lam",  "λ at Copt"),
        ]:
            row = ttk.Frame(ctrl)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=label, width=22).pack(side=tk.LEFT)
            v = tk.StringVar()
            lbl = ttk.Label(row, textvariable=v,
                            font=("Consolas", 10, "bold"))
            lbl.pack(side=tk.RIGHT)
            self.out_vars[key]   = v
            self.out_labels[key] = lbl

            if key == "Vch":
                sub = ttk.Frame(ctrl)
                sub.pack(fill=tk.X, pady=(0, 4))
                ttk.Label(sub, text="", width=4).pack(side=tk.LEFT)
                ttk.Label(
                    sub,
                    textvariable=self.isp_vch_var,
                    foreground="#b05000",
                    font=("Consolas", 9, "italic"),
                    anchor="e",
                ).pack(side=tk.RIGHT)

            if key == "Copt":
                sub_isp = ttk.Frame(ctrl)
                sub_isp.pack(fill=tk.X, pady=(0, 2))
                ttk.Label(sub_isp, text="", width=4).pack(side=tk.LEFT)
                self.isp_copt_label = ttk.Label(
                    sub_isp,
                    textvariable=self.isp_copt_var,
                    foreground="#b05000",
                    font=("Consolas", 9, "italic"),
                    anchor="e",
                )
                self.isp_copt_label.pack(side=tk.RIGHT)

                sub_thr = ttk.Frame(ctrl)
                sub_thr.pack(fill=tk.X, pady=(0, 4))
                ttk.Label(sub_thr, text="", width=4).pack(side=tk.LEFT)
                ttk.Label(
                    sub_thr,
                    textvariable=self.thruster_var,
                    foreground="#5500aa",
                    font=("Consolas", 9, "italic"),
                    anchor="e",
                ).pack(side=tk.RIGHT)

        ttk.Separator(ctrl, orient="horizontal").pack(fill=tk.X, pady=10)
        ttk.Label(
            ctrl,
            text=("Note: F cancels out of the\n"
                  "payload-ratio objective λ(c).\n"
                  "ε = α ΔV² / (2 η tₘ) controls\n"
                  "the entire shape of λ(z)."),
            foreground="#555",
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

        self.update()

    # ----------------------------------------------------------------
    def _read_inputs(self):
        try:
            vals = {k: float(self.entries[k].get()) for k, *_ in self.INPUT_DEFS}
        except ValueError:
            return None
        if any(vals[k] <= 0 for k in ("eta", "F", "alpha", "t_days", "dV")):
            return None
        if vals["eta"] > 1.0:
            return None
        vals["t"] = vals["t_days"] * 86400.0
        return vals

    # ----------------------------------------------------------------
    def update(self):
        v = self._read_inputs()
        if v is None:
            return

        eta   = v["eta"]
        F     = v["F"]
        alpha = v["alpha"]
        t     = v["t"]
        dV    = v["dV"]

        Vch                  = stuhlinger_velocity(eta, alpha, t)
        Copt, lam_opt, eps   = find_copt(eta, alpha, t, dV)
        err                  = 100.0 * abs(Copt - Vch) / Copt

        isp_vch  = Vch  / G0
        isp_copt = Copt / G0

        # Fields that are always valid
        self.out_vars["Vch"].set(f"{Vch:.2f}")
        self.out_vars["eps"].set(f"{eps:.4g}")
        self.isp_vch_var.set(f"Isp = {isp_vch:.1f} s")

        if lam_opt <= 0:
            # ── CHANGE: Copt row also shows "MISSION NOT POSSIBLE" ──
            self.out_vars["Copt"].set("MISSION NOT POSSIBLE")
            self.out_labels["Copt"].configure(foreground="red",
                                              font=("Consolas", 10, "bold"))
            self.out_vars["err"].set("N/A")
            self.out_labels["err"].configure(foreground="red",
                                             font=("Consolas", 10, "bold"))
            self.out_vars["lam"].set("MISSION NOT POSSIBLE")
            self.out_labels["lam"].configure(foreground="red",
                                             font=("Consolas", 10, "bold"))
            self.isp_copt_var.set("MISSION NOT POSSIBLE")
            self.isp_copt_label.configure(foreground="red",
                                          font=("Consolas", 9, "bold"))
        else:
            # ── CHANGE: reset Copt row to normal ────────────────────
            self.out_vars["Copt"].set(f"{Copt:.2f}")
            self.out_labels["Copt"].configure(foreground="black",
                                              font=("Consolas", 10, "bold"))
            self.out_vars["err"].set(f"{err:.3f}")
            self.out_labels["err"].configure(foreground="black",
                                             font=("Consolas", 10, "bold"))
            self.out_vars["lam"].set(f"{lam_opt:.6f}")
            self.out_labels["lam"].configure(foreground="black",
                                             font=("Consolas", 10, "bold"))
            self.isp_copt_var.set(f"Isp = {isp_copt:.1f} s")
            self.isp_copt_label.configure(foreground="#b05000",
                                          font=("Consolas", 9, "italic"))

        self.thruster_var.set(f"({classify_thruster(Copt)})")
        self.power_src_var.set(f"({classify_power_source(alpha)})")

        c_ref  = max(Vch, Copt, dV)
        c_low  = max(c_ref * 0.02, 1.0)
        c_high = c_ref * 3.0
        c_grid = np.linspace(c_low, c_high, 1200)

        # ── Mass plot ──────────────────────────────────────────────
        mps_g = m_ps(c_grid, F, eta, alpha)
        mp_g  = m_p(c_grid, F, t)
        tot_g = mps_g + mp_g

        ax = self.ax_mass
        ax.clear()
        ax.plot(c_grid, mps_g, color="C0",    lw=1.8,
                label=r"$m_{ps}$ (power system)")
        ax.plot(c_grid, mp_g,  color="C1",    lw=1.8,
                label=r"$m_p$ (propellant)")
        ax.plot(c_grid, tot_g, color="green", lw=2.8,
                label=r"$m_{ps}+m_p$")

        ax.axvline(Vch,  color="red",    ls="--", lw=1.8,
                   label=fr"$V_{{ch}}$ = {Vch:.0f} m/s  ({isp_vch:.0f} s)")
        ax.axvline(Copt, color="purple", ls="-",  lw=1.8,
                   label=fr"$C_{{opt}}$ = {Copt:.0f} m/s  ({isp_copt:.0f} s)")

        mtot_vch = m_ps(Vch, F, eta, alpha) + m_p(Vch, F, t)
        ax.plot(Vch, mtot_vch, "r^", ms=9, zorder=5)

        ax.set_xlabel("Exhaust velocity c [m/s]")
        ax.set_ylabel("Mass [kg]")
        ax.set_title("Propulsion-system masses (Stuhlinger problem)")
        ax.set_xlim(c_low, c_high)
        ax.set_ylim(0, 5.0 * mtot_vch)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right", fontsize=8)

        # ── Objective plot ─────────────────────────────────────────
        lam_g = payload_ratio_c(c_grid, eta, alpha, t, dV)

        ax = self.ax_obj
        ax.clear()
        ax.plot(c_grid, lam_g, color="green", lw=2.2,
                label=r"$\lambda(c)$")
        ax.axhline(0, color="k", lw=0.6)

        ax.axvline(Vch,  color="red",    ls="--", lw=1.8,
                   label=fr"$V_{{ch}}$ = {Vch:.0f} m/s  ({isp_vch:.0f} s)")
        ax.axvline(Copt, color="purple", ls="-",  lw=1.8,
                   label=fr"$C_{{opt}}$ = {Copt:.0f} m/s  ({isp_copt:.0f} s)")

        ax.plot(Copt, lam_opt, "o", color="purple", ms=9, zorder=5)

        finite_mask = np.isfinite(lam_g)
        if finite_mask.any():
            lam_vis_max = np.nanmax(lam_g[finite_mask])
            lam_vis_min = np.nanmin(lam_g[finite_mask])
            pad = 0.1 * (lam_vis_max - lam_vis_min + 1e-12)
            ax.set_ylim(lam_vis_min - pad, lam_vis_max + pad)

        ax.set_xlim(c_low, c_high)
        ax.set_xlabel("Exhaust velocity c [m/s]")
        ax.set_ylabel(r"Payload ratio $\lambda = m_L / m_0$")
        ax.set_title(
            fr"Objective function   ($\varepsilon$ = {eps:.3g},"
            fr"  $C_{{opt}}$ = {Copt:.0f} m/s)"
        )
        ax.grid(True, alpha=0.3)
        ax.legend(loc="lower right", fontsize=8)

        self.fig.tight_layout()
        self.canvas.draw_idle()


# -----------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    StuhlingerApp(root)
    root.mainloop()