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
    """Power-system mass: m_ps = alpha * P = alpha * F * c / (2*eta)."""
    return alpha * F * c / (2.0 * eta)


def m_p(c, F, t):
    """Propellant mass: m_p = (F/c) * t."""
    return F * t / c


def stuhlinger_velocity(eta, alpha, t):
    """Vch = sqrt(2*eta*t/alpha) — minimizer of m_ps + m_p."""
    return np.sqrt(2.0 * eta * t / alpha)


def epsilon(eta, alpha, t, dV):
    """Dimensionless group eps = alpha*dV^2 / (2*eta*tm)."""
    return alpha * dV**2 / (2.0 * eta * t)


def payload_ratio_c(c, eta, alpha, t, dV):
    """
    lambda(c) = exp(-dV/c)
                - (alpha*c^2 / (2*eta*t)) * (1 - exp(-dV/c))
    Depends on eta, alpha, t, dV.  Thrust F cancels out.
    """
    z = dV / c
    e = np.exp(-np.clip(z, 0.0, 700.0))
    return e - (alpha * c**2 / (2.0 * eta * t)) * (1.0 - e)


def payload_ratio_z(z, eps):
    """lambda(z) = exp(-z) - eps*(1 - exp(-z))/z^2."""
    z   = np.asarray(z, dtype=float)
    e   = np.exp(-np.clip(z, 0.0, 700.0))
    return e - eps * (1.0 - e) / (z**2)


def find_copt(eta, alpha, t, dV):
    """
    Maximize lambda(z) robustly:
      1. Log-spaced coarse grid to locate the global peak.
      2. Bounded local refinement around that peak.
    This avoids scipy getting stuck at a boundary.
    """
    eps = epsilon(eta, alpha, t, dV)

    # --- coarse log-grid scan ---
    z_grid  = np.logspace(-4, 2, 20000)
    lam_g   = payload_ratio_z(z_grid, eps)
    lam_g[~np.isfinite(lam_g)] = -np.inf
    i       = int(np.argmax(lam_g))

    # --- narrow window around grid peak ---
    z_lo = z_grid[max(i - 2, 0)]
    z_hi = z_grid[min(i + 2, len(z_grid) - 1)]
    if z_hi <= z_lo:
        z_lo = 0.5 * z_grid[i]
        z_hi = 2.0 * z_grid[i]

    # --- local refinement ---
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

        # ── Plot area (left) ────────────────────────────────────────
        plot_frame = ttk.Frame(main)
        plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.fig      = Figure(figsize=(9, 7), dpi=100)
        self.ax_mass  = self.fig.add_subplot(2, 1, 1)
        self.ax_obj   = self.fig.add_subplot(2, 1, 2)

        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        NavigationToolbar2Tk(self.canvas, plot_frame)

        # ── Control panel (right) ────────────────────────────────────
        ctrl = ttk.Frame(main, padding=12)
        ctrl.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Label(ctrl, text="Inputs",
                  font=("Segoe UI", 13, "bold")).pack(anchor=tk.W, pady=(0, 6))

        self.entries = {}
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

        ttk.Button(ctrl, text="Update", command=self.update)\
            .pack(fill=tk.X, pady=(10, 0))

        ttk.Separator(ctrl, orient="horizontal").pack(fill=tk.X, pady=10)

        ttk.Label(ctrl, text="Outputs",
                  font=("Segoe UI", 13, "bold")).pack(anchor=tk.W, pady=(0, 6))

        self.out_vars = {}
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
            ttk.Label(row, textvariable=v,
                      font=("Consolas", 10, "bold")).pack(side=tk.RIGHT)
            self.out_vars[key] = v

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

        Vch              = stuhlinger_velocity(eta, alpha, t)
        Copt, lam_opt, eps = find_copt(eta, alpha, t, dV)
        err              = 100.0 * (Copt - Vch) / Copt

        self.out_vars["Vch"].set(f"{Vch:,.2f}")
        self.out_vars["Copt"].set(f"{Copt:,.2f}")
        self.out_vars["err"].set(f"{err:+.3f}")
        self.out_vars["eps"].set(f"{eps:.4g}")
        self.out_vars["lam"].set(f"{lam_opt:.6f}")

        # Shared x-range: always contains Vch, Copt, and a sense of ΔV
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

        # Vch  → red dashed
        ax.axvline(Vch,  color="red",    ls="--", lw=1.8,
                   label=fr"$V_{{ch}}$ = {Vch:,.0f} m/s")
        # Copt → purple solid
        ax.axvline(Copt, color="purple", ls="-",  lw=1.8,
                   label=fr"$C_{{opt}}$ = {Copt:,.0f} m/s")

        # marker on the total-mass curve at Vch
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

        # Vch  → red dashed
        ax.axvline(Vch,  color="red",    ls="--", lw=1.8,
                   label=fr"$V_{{ch}}$ = {Vch:,.0f} m/s")
        # Copt → purple solid  (should sit exactly at the peak)
        ax.axvline(Copt, color="purple", ls="-",  lw=1.8,
                   label=fr"$C_{{opt}}$ = {Copt:,.0f} m/s")

        # purple dot at the true maximum
        ax.plot(Copt, lam_opt, "o", color="purple", ms=9, zorder=5)

        # y-limits framed tightly around the real peak
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
            fr"  $C_{{opt}}$ = {Copt:,.0f} m/s)"
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