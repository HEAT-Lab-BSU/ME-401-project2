"""
module3_pressure_vessel.py
--------------------------
HTC Airship Disaster Relief System — Module 3: Pressure Vessel Mechanical Analysis

Purpose:
    Compute required wall thickness and vessel mass as a function of reactor
    operating temperature and vessel inner radius. Higher temperature drives
    higher autogenous pressure (via steam saturation curve), which requires
    thicker walls, which increases module mass and reduces the number of
    modules the airship can carry (feeds back into Module 1).

Governing equations:
    Hoop stress (thin-wall):   sigma_hoop = P * r / t
    Required wall thickness:   t = P * r / (sigma_allowable * eta_weld)
    Shell mass:                M_shell = rho_steel * 2 * pi * r * L * t
    Total vessel mass:         M_vessel = M_shell * (1 + end_cap_frac)

Module coupling:
    -> Outputs M_vessel(T_reactor) feed into Module 1 (payload budget)
    -> T_reactor is a shared design parameter with Modules 2 and 5
    -> P_autogenous derived here is reused in Module 5 (pump work)

Author:  m.hewes
Version: 1.0
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import json
from math import pi

# CoolProp is used only in get_autogenous_pressure().
# Install via: pip install CoolProp
import CoolProp.CoolProp as CP


# ==============================================================================
# CONSTANTS BLOCK
# All physical literals are defined here. No numeric literals appear in
# equations below. Add source citations as you verify each value.
# ==============================================================================

SIGMA_YIELD_PA    = 205e6    # [Pa]  316 SS yield strength — source: ASME BPVC / MatWeb
SAFETY_FACTOR     = 3.5      # [-]   pressure vessel service — source: ASME BPVC Div.1
WELD_EFFICIENCY   = 0.85     # [-]   radiographed weld — source: ASME BPVC UW-12
RHO_STEEL         = 8000.0   # [kg/m³] 316 SS density — source: MatWeb
END_CAP_MASS_FRAC = 0.175    # [-]   ellipsoidal heads add ~17.5% to shell mass
                             #       source: Moss (2004), Pressure Vessel Design Manual

# Derived allowable stress (computed from constants, not hard-coded)
SIGMA_ALLOWABLE_PA = SIGMA_YIELD_PA / SAFETY_FACTOR   # [Pa]

# Sweep ranges
T_REACTOR_RANGE = [180, 200, 220, 250]            # [°C] operating temperature sweep
R_VESSEL_RANGE  = np.linspace(0.5, 1.0, 20)      # [m]  inner radius sweep
                                                   # NOTE: radius optimization is deferred.
                                                   # Selecting the optimal radius requires a
                                                   # transient thermal analysis (heat loss vs.
                                                   # throughput vs. wall mass) — future work.

L_VESSEL = 3.0   # [m] vessel length — placeholder. A proper length requires volumetric
                 # throughput and residence time (from Module 2 outputs). Treat as a
                 # sensitivity parameter until Module 2 is implemented.


# ==============================================================================
# FUNCTIONS
# ==============================================================================

def get_autogenous_pressure(T_celsius):
    """
    Return the saturation pressure of water at a given temperature.

    HTC reactors operate under autogenous pressure — the reactor is sealed and
    pressurizes to the saturation pressure of water at the operating temperature.
    This function wraps CoolProp to return that value.

    Parameters
    ----------
    T_celsius : float or array-like
        Reactor temperature [°C]

    Returns
    -------
    P_sat : float or np.ndarray
        Saturation pressure [Pa]

    CoolProp call:
        PropsSI('P', 'T', T_kelvin, 'Q', 0, 'Water')
        'Q' = 0 selects the saturated liquid curve, which is the correct
        physical condition for the liquid-vapor interface in the sealed reactor.

    Assumptions:
        - Pure water saturation curve is used as a proxy for the slurry.
          Dissolved organics shift the saturation point slightly; this
          approximation is acceptable at the scoping stage.
    """
    T_celsius = np.atleast_1d(np.array(T_celsius, dtype=float))
    T_kelvin  = T_celsius + 273.15
    P_sat     = np.array([CP.PropsSI('P', 'T', T_k, 'Q', 0, 'Water') for T_k in T_kelvin])
    return P_sat if len(P_sat) > 1 else float(P_sat[0])


def calc_wall_thickness(P_pa, r_m, sigma_allowable_pa, eta_weld):
    """
    Compute required wall thickness using the thin-wall hoop stress equation.

    Derived from: sigma_hoop = P * r / t  =>  t = P * r / (sigma_allowable * eta_weld)

    Parameters
    ----------
    P_pa             : float  Internal pressure [Pa]
    r_m              : float  Inner radius [m]
    sigma_allowable_pa: float Allowable stress = yield strength / safety factor [Pa]
    eta_weld         : float  Weld efficiency factor [-], typically 0.85

    Returns
    -------
    t : float
        Required wall thickness [m]

    Assumptions:
        # ASSUMPTION: thin-wall approximation valid when t/r < 0.1 — flag if violated.
        # For HTC pressures (~10–40 bar) and radii in the 0.5–1.0 m range this
        # holds comfortably, but the check is included for completeness.
    """
    t = (P_pa * r_m) / (sigma_allowable_pa * eta_weld)
    return t


def calc_vessel_mass(r_m, L_m, t_m, rho_steel, end_cap_frac):
    """
    Compute total vessel mass (cylindrical shell + end caps).

    Shell equation:
        M_shell = rho_steel * 2 * pi * r * L * t
        (surface area of a thin cylindrical shell times wall thickness times density)

    End cap correction:
        M_vessel = M_shell * (1 + end_cap_frac)

    Parameters
    ----------
    r_m          : float  Inner radius [m]
    L_m          : float  Vessel length [m]
    t_m          : float  Wall thickness [m]
    rho_steel    : float  Steel density [kg/m³]
    end_cap_frac : float  End cap mass as fraction of shell mass [-]

    Returns
    -------
    M_vessel : float
        Total vessel mass [kg]

    Assumptions:
        # ASSUMPTION: end cap mass approximated as a fixed fraction of shell mass.
        # This is based on ellipsoidal (2:1) head geometry at typical HTC vessel
        # proportions. Refine with the exact ellipsoidal head formula in future analysis:
        #   M_head = rho * pi * r^2 * t * (2/3) for a 2:1 ellipsoidal head (per head).
    """
    M_shell  = rho_steel * 2 * pi * r_m * L_m * t_m
    M_vessel = M_shell * (1 + end_cap_frac)
    return M_vessel


def run_module3_sweep(T_list, r_array, L, material_constants):
    """
    Sweep wall thickness and vessel mass over a grid of T_reactor and r_vessel.

    Parameters
    ----------
    T_list             : list of float  Reactor temperatures to evaluate [°C]
    r_array            : np.ndarray     Inner radii to evaluate [m]
    L                  : float          Vessel length [m]
    material_constants : dict           Must contain keys:
                                          'sigma_allowable_pa', 'eta_weld',
                                          'rho_steel', 'end_cap_frac'

    Returns
    -------
    results_df : pd.DataFrame
        Columns: T_C, P_Pa, r_m, t_m, thin_wall_valid, M_vessel_kg
    """
    sigma_allowable = material_constants['sigma_allowable_pa']
    eta_weld        = material_constants['eta_weld']
    rho_steel       = material_constants['rho_steel']
    end_cap_frac    = material_constants['end_cap_frac']

    rows = []

    for T_c in T_list:
        P_pa = get_autogenous_pressure(T_c)

        for r in r_array:
            t = calc_wall_thickness(P_pa, r, sigma_allowable, eta_weld)

            # Thin-wall validity check: approximation holds when t/r < 0.1
            thin_wall_valid = bool((t / r) < 0.1)
            if not thin_wall_valid:
                print(f"  WARNING: thin-wall assumption violated at "
                      f"T={T_c}°C, r={r:.3f} m  (t/r = {t/r:.3f})")

            M_vessel = calc_vessel_mass(r, L, t, rho_steel, end_cap_frac)

            rows.append({
                'T_C':           T_c,
                'P_Pa':          round(P_pa, 1),
                'r_m':           round(r, 4),
                't_m':           round(t, 6),
                'thin_wall_valid': thin_wall_valid,
                'M_vessel_kg':   round(M_vessel, 2),
            })

    results_df = pd.DataFrame(rows)
    return results_df


# ==============================================================================
# DRIVER BLOCK
# ==============================================================================

if __name__ == "__main__":

    material_constants = {
        'sigma_allowable_pa': SIGMA_ALLOWABLE_PA,
        'eta_weld':           WELD_EFFICIENCY,
        'rho_steel':          RHO_STEEL,
        'end_cap_frac':       END_CAP_MASS_FRAC,
    }

    print("=" * 60)
    print("MODULE 3 — Pressure Vessel Mechanical Analysis")
    print("=" * 60)

    # --- Run sweep ---
    results_df = run_module3_sweep(
        T_list=T_REACTOR_RANGE,
        r_array=R_VESSEL_RANGE,
        L=L_VESSEL,
        material_constants=material_constants,
    )

    # --- Print summary table ---
    print("\nSample results (first 10 rows):")
    print(results_df.head(10).to_string(index=False))

    # --- Print key design insight ---
    print("\nVessel mass at r=0.5 m per temperature:")
    summary = results_df[results_df['r_m'] == results_df['r_m'].min()]
    for _, row in summary.iterrows():
        print(f"  T={row['T_C']}°C  P={row['P_Pa']/1e5:.1f} bar  "
              f"t={row['t_m']*1000:.1f} mm  M_vessel={row['M_vessel_kg']:.1f} kg")

    # --- Plot: M_vessel vs r_m, one curve per T_reactor ---
    fig, ax = plt.subplots(figsize=(8, 5))

    for T_c in T_REACTOR_RANGE:
        subset = results_df[results_df['T_C'] == T_c]
        ax.plot(subset['r_m'], subset['M_vessel_kg'], marker='o', label=f"T = {T_c}°C")

    ax.set_xlabel("Inner radius r [m]")
    ax.set_ylabel("Vessel mass M_vessel [kg]")
    ax.set_title("Module 3: Vessel Mass vs. Radius at HTC Operating Temperatures\n"
                 f"(L = {L_VESSEL} m, 316 SS, SF = {SAFETY_FACTOR}, η_weld = {WELD_EFFICIENCY})")
    ax.legend()
    ax.grid(True)
    plt.tight_layout()
    plt.savefig("module3_vessel_mass.png", dpi=150)
    print("\nPlot saved to module3_vessel_mass.png")
    plt.show()

    # --- Save results to JSON ---
    metadata = {
        "module":            "module3_pressure_vessel",
        "T_reactor_C_values": T_REACTOR_RANGE,
        "r_vessel_m_values":  list(np.round(R_VESSEL_RANGE, 4)),
        "L_vessel_m":         L_VESSEL,
        "units": {
            "T":        "degC",
            "P":        "Pa",
            "r":        "m",
            "t":        "m",
            "M_vessel": "kg",
        }
    }

    output = {
        "metadata": metadata,
        "records":  results_df.to_dict(orient="records"),
    }

    with open("module3_output.json", "w") as f:
        json.dump(output, f, indent=2)

    print("Results saved to module3_output.json")
    print("=" * 60)