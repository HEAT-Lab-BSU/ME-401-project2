"""
module1_payload.py
==================
Module 1: Payload & Buoyancy Feasibility
HTC Airship Disaster Relief System

Inputs:  module3_output.json (produced by module3_pressure_vessel.py)
Outputs: module1_output.json, matplotlib figure (N vs r_m per T_reactor)

Governing logic:
  1. Scale vessel mass from Module 3 by MODULE_MASS_SCALE_FACTOR to get
     total module mass (plumbing, internals, structure included).
  2. Divide airship payload by module mass to get integer module count N.
  3. Use reactor geometry and N to compute total system mass flow rate m_dot.

Self-sufficiency constraint context:
  m_dot produced here feeds Module 2 (thermal balance) and Module 5
  (integration). This module establishes the feasible throughput envelope
  that all downstream analysis operates within.
"""

import json
import math
import os

import matplotlib.pyplot as plt
import pandas as pd

# ==============================================================================
# CONSTANTS BLOCK
# All physical constants and design parameters defined here.
# No magic numbers in equations below.
# ==============================================================================

# --- Airship Platform ---
# Source: Flying Whales official specifications (flyingwhales.fr)
# ASSUMPTION: published payload figure used directly —
#             verify against operator data before final analysis
AIRSHIP_PAYLOAD_KG = 60000.0   # [kg] Flying Whales LCA60T rated payload — PLACEHOLDER verify
AIRSHIP_NAME       = "Flying Whales LCA60T"

# Airlander 10 as secondary reference (parametric override — uncomment to use)
# Source: HAV (Hybrid Air Vehicles) published specifications
# AIRSHIP_PAYLOAD_KG = 10000.0  # [kg] HAV Airlander 10 — PLACEHOLDER verify
# AIRSHIP_NAME       = "HAV Airlander 10"

# --- Module Mass Scale Factor ---
# Accounts for plumbing, internals, structural framing beyond bare vessel shell.
# Source: engineering judgment
# ASSUMPTION: refine with detailed BOM in future analysis
MODULE_MASS_SCALE_FACTOR = 1.5   # [-] dimensionless multiplier on M_vessel

# --- Slurry Properties ---
# ASSUMPTION: rho_slurry = 1000 kg/m³ (water-equivalent density)
#             Refine with solids content data when available.
#             Valid for low-solids slurry (<15% by mass, near-Newtonian regime).
RHO_SLURRY = 1000.0   # [kg/m³]

# --- Reactor Geometry ---
# Fill fraction: fraction of reactor volume occupied by slurry during operation.
# ASSUMPTION: fill_fraction = 1.0 (maximalist feasibility model — upper bound on m_dot)
#             Real operation will be lower; use as bounding case.
FILL_FRACTION = 1.0   # [-]

# Vessel length: fixed geometric parameter for this sweep.
# Selected as a representative modular unit length.
# ASSUMPTION: L_m = 3.0 m. Adjust as geometry is refined.
VESSEL_LENGTH_M = 3.0   # [m]

# --- Residence Times to Sweep ---
# Three candidate residence times covering short, medium, and long HTC operation.
# Source: HTC literature range (1–4 hours typical for municipal feedstocks)
RESIDENCE_TIMES_S = [3600, 7200, 14400]   # [s] = [1 hr, 2 hr, 4 hr]

# --- NOTE: Volume / Cargo Bay Check (future work) ---
# This module does not check whether the physical envelope of N reactor modules
# fits within the airship cargo bay dimensions. Payload mass budget is the only
# constraint applied here. A volumetric feasibility check against cargo bay
# geometry should be added once platform bay dimensions are confirmed.
# Flag: future work item — volumetric constraint not yet implemented.


# ==============================================================================
# FUNCTIONS
# ==============================================================================

def calc_module_mass(M_vessel_kg, scale_factor):
    """
    Compute total reactor module mass including plumbing, internals, and structure.

    The bare vessel shell mass from Module 3 is multiplied by a scale factor
    to account for components not captured by the hoop-stress shell model.

    Parameters
    ----------
    M_vessel_kg : float
        Bare pressure vessel shell mass [kg], from Module 3 output.
    scale_factor : float
        Dimensionless multiplier [-]. Default: MODULE_MASS_SCALE_FACTOR = 1.5.
        ASSUMPTION: engineering judgment; refine with detailed BOM.

    Returns
    -------
    M_module_kg : float
        Total module mass [kg].

    Equation
    --------
    M_module = M_vessel * scale_factor
    """
    M_module_kg = M_vessel_kg * scale_factor
    return M_module_kg


def calc_module_count(payload_kg, M_module_kg):
    """
    Compute the maximum integer number of reactor modules the airship can carry.

    Uses floor division: partial modules cannot be deployed, so fractional
    result is rounded down. Returns 0 if module mass exceeds payload — caller
    should flag this as an infeasible design point.

    Parameters
    ----------
    payload_kg : float
        Airship rated payload capacity [kg].
    M_module_kg : float
        Total mass per reactor module [kg].

    Returns
    -------
    N : int
        Maximum number of deployable modules. May be 0 (infeasible).

    Equation
    --------
    N = floor(payload_kg / M_module_kg)

    Notes
    -----
    If N == 0, the (T_reactor, r) combination produces a vessel too heavy
    for the airship platform. These rows are dropped in run_module1().
    """
    if M_module_kg <= 0:
        raise ValueError("M_module_kg must be positive.")
    N = math.floor(payload_kg / M_module_kg)
    return N


def calc_mdot_from_geometry(r_m, L_m, fill_fraction, residence_time_s, N, rho_slurry):
    """
    Compute total system mass flow rate across all deployed reactor modules.

    Each reactor is treated as a cylindrical batch vessel. The effective
    continuous throughput is approximated as the volume of slurry processed
    per residence time interval, summed across N modules.

    Parameters
    ----------
    r_m : float
        Inner radius of reactor vessel [m].
    L_m : float
        Reactor vessel length [m].
    fill_fraction : float
        Fraction of reactor volume filled with slurry [-].
        ASSUMPTION: fill_fraction = 1.0 (maximalist feasibility upper bound).
    residence_time_s : float
        HTC reaction residence time [s].
    N : int
        Number of deployed reactor modules [-].
    rho_slurry : float
        Slurry density [kg/m³].
        ASSUMPTION: rho_slurry = 1000 kg/m³ (near-water; low-solids slurry).

    Returns
    -------
    m_dot : float
        Total system mass flow rate [kg/s] across N modules.

    Equations
    ---------
    V_reactor = pi * r_m^2 * L_m * fill_fraction    [m³, per module]
    m_dot = (V_reactor * rho_slurry * N) / residence_time_s   [kg/s]
    """
    V_reactor = math.pi * r_m**2 * L_m * fill_fraction   # [m³] per module
    m_dot = (V_reactor * rho_slurry * N) / residence_time_s   # [kg/s] total
    return m_dot


def run_module1(module3_df, payload_kg, airship_name, residence_times_s, L_m):
    """
    Execute Module 1 sweep over all (T_reactor, r, residence_time) combinations.

    Loads Module 3 vessel mass data, computes module mass and count for the
    given airship payload, then derives mass flow rate for each residence time.
    Infeasible rows (N == 0) are dropped before returning.

    Parameters
    ----------
    module3_df : pd.DataFrame
        DataFrame loaded from module3_output.json.
        Required columns: ['T_C', 'r_m', 'M_vessel_kg']
    payload_kg : float
        Airship rated payload [kg].
    airship_name : str
        Human-readable airship platform identifier for metadata.
    residence_times_s : list of float
        Residence times to sweep [s].
    L_m : float
        Vessel length [m].

    Returns
    -------
    results_df : pd.DataFrame
        Columns: [T_C, r_m, M_vessel_kg, M_module_kg, N, tau_s, m_dot_kg_s]
        Rows with N == 0 are excluded.
    """
    records = []

    for _, row in module3_df.iterrows():
        T_C        = row["T_C"]
        r_m        = row["r_m"]
        M_vessel   = row["M_vessel_kg"]

        M_module = calc_module_mass(M_vessel, MODULE_MASS_SCALE_FACTOR)
        N        = calc_module_count(payload_kg, M_module)

        if N == 0:
            # INFEASIBLE: vessel too heavy for airship payload at this (T, r).
            # Flag to console and skip.
            print(f"  [INFEASIBLE] T={T_C}°C, r={r_m:.2f}m — "
                  f"M_module={M_module:.1f} kg exceeds payload {payload_kg:.0f} kg. "
                  f"Dropping row.")
            continue

        for tau_s in residence_times_s:
            m_dot = calc_mdot_from_geometry(
                r_m, L_m, FILL_FRACTION, tau_s, N, RHO_SLURRY
            )
            records.append({
                "T_C"         : T_C,
                "r_m"         : r_m,
                "M_vessel_kg" : M_vessel,
                "M_module_kg" : M_module,
                "N"           : N,
                "tau_s"       : tau_s,
                "m_dot_kg_s"  : m_dot,
            })

    results_df = pd.DataFrame(records)
    return results_df


def print_summary(results_df, airship_name, payload_kg):
    """
    Print a human-readable summary of key Module 1 results.

    For each T_reactor, reports: maximum module count and the resulting
    m_dot range across all radii and residence times.

    Parameters
    ----------
    results_df : pd.DataFrame
        Output of run_module1().
    airship_name : str
        Airship platform label.
    payload_kg : float
        Airship payload [kg].
    """
    print("\n" + "=" * 60)
    print("MODULE 1 SUMMARY — Payload & Buoyancy Feasibility")
    print(f"Platform : {airship_name}")
    print(f"Payload  : {payload_kg:.0f} kg")
    print(f"Scale factor (plumbing/internals): {MODULE_MASS_SCALE_FACTOR}")
    print("=" * 60)

    for T_C in sorted(results_df["T_C"].unique()):
        subset = results_df[results_df["T_C"] == T_C]
        N_max     = subset["N"].max()
        N_min     = subset["N"].min()
        mdot_max  = subset["m_dot_kg_s"].max()
        mdot_min  = subset["m_dot_kg_s"].min()
        print(f"\n  T_reactor = {T_C}°C")
        print(f"    Module count N : {N_min} – {N_max}  (across r sweep)")
        print(f"    m_dot range    : {mdot_min:.4f} – {mdot_max:.4f} kg/s  "
              f"({mdot_min*3600:.1f} – {mdot_max*3600:.1f} kg/hr)")

    print("\n" + "=" * 60)


def plot_N_vs_r(results_df, airship_name, payload_kg):
    """
    Produce figure: module count N vs inner radius r_m, one curve per T_reactor.

    Residence time is not differentiated in this plot because N is independent
    of residence time (N depends only on vessel mass, which depends on T and r).

    Parameters
    ----------
    results_df : pd.DataFrame
        Output of run_module1().
    airship_name : str
        Used in plot title.
    payload_kg : float
        Used in plot title.
    """
    # N is the same for all tau at a given (T, r) — deduplicate
    plot_df = results_df[["T_C", "r_m", "N"]].drop_duplicates()

    fig, ax = plt.subplots(figsize=(8, 5))

    for T_C in sorted(plot_df["T_C"].unique()):
        subset = plot_df[plot_df["T_C"] == T_C].sort_values("r_m")
        ax.plot(subset["r_m"], subset["N"],
                marker="o", label=f"T = {T_C}°C")

    ax.set_xlabel("Inner Reactor Radius, r [m]")
    ax.set_ylabel("Module Count, N [-]")
    ax.set_title(
        f"Module 1: Module Count vs Reactor Radius\n"
        f"Platform: {airship_name}  |  Payload: {payload_kg:.0f} kg  |  "
        f"Scale factor: {MODULE_MASS_SCALE_FACTOR}"
    )
    ax.legend(title="T_reactor")
    ax.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig("module1_N_vs_r.png", dpi=150)
    print("\nFigure saved: module1_N_vs_r.png")
    plt.show()


def save_output(results_df, payload_kg, residence_times_s, filename="module1_output.json"):
    """
    Serialize Module 1 results to JSON with metadata header.

    Parameters
    ----------
    results_df : pd.DataFrame
        Output of run_module1().
    payload_kg : float
        Airship payload used in this run [kg].
    residence_times_s : list of float
        Residence times swept [s].
    filename : str
        Output filename. Default: 'module1_output.json'.
    """
    output = {
        "metadata": {
            "module"           : "module1_payload",
            "airship_platform" : AIRSHIP_NAME,
            "payload_kg"       : payload_kg,
            "scale_factor"     : MODULE_MASS_SCALE_FACTOR,
            "vessel_length_m"  : VESSEL_LENGTH_M,
            "fill_fraction"    : FILL_FRACTION,
            "rho_slurry_kg_m3" : RHO_SLURRY,
            "residence_times_s": residence_times_s,
            "units": {
                "r_m"         : "m",
                "M_vessel_kg" : "kg",
                "M_module_kg" : "kg",
                "m_dot_kg_s"  : "kg/s",
                "tau_s"       : "s",
            },
            "assumptions": [
                "MODULE_MASS_SCALE_FACTOR=1.5: engineering judgment; refine with BOM",
                "fill_fraction=1.0: maximalist upper bound on throughput",
                "rho_slurry=1000 kg/m³: near-water density; valid <15% solids",
                "Payload figure from published spec — verify with operator data",
                "Volume/cargo bay check not performed — future work item",
            ]
        },
        "records": results_df.to_dict(orient="records")
    }

    with open(filename, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Results saved: {filename}  ({len(results_df)} rows)")


# ==============================================================================
# DRIVER BLOCK
# ==============================================================================

if __name__ == "__main__":

    # --- Load Module 3 output ---
    input_file = "module3_output.json"
    if not os.path.exists(input_file):
        raise FileNotFoundError(
            f"'{input_file}' not found. Run module3_pressure_vessel.py first."
        )

    with open(input_file, "r") as f:
        module3_data = json.load(f)

    module3_df = pd.DataFrame(module3_data["records"])
    print(f"Loaded {len(module3_df)} rows from {input_file}")
    print(f"Columns: {list(module3_df.columns)}")

    # --- Run Module 1 ---
    results_df = run_module1(
        module3_df       = module3_df,
        payload_kg       = AIRSHIP_PAYLOAD_KG,
        airship_name     = AIRSHIP_NAME,
        residence_times_s= RESIDENCE_TIMES_S,
        L_m              = VESSEL_LENGTH_M,
    )

    if results_df.empty:
        print("\nWARNING: No feasible design points found. "
              "All (T, r) combinations exceeded payload budget. "
              "Check MODULE_MASS_SCALE_FACTOR or AIRSHIP_PAYLOAD_KG.")
    else:
        # --- Print summary ---
        print_summary(results_df, AIRSHIP_NAME, AIRSHIP_PAYLOAD_KG)

        # --- Plot ---
        plot_N_vs_r(results_df, AIRSHIP_NAME, AIRSHIP_PAYLOAD_KG)

        # --- Save output ---
        save_output(results_df, AIRSHIP_PAYLOAD_KG, RESIDENCE_TIMES_S)