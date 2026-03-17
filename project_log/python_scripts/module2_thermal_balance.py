"""
module2_thermal_balance.py
==========================
HTC Airship Disaster Relief System — Module 2: Reactor Thermal Energy Balance

Computes Q_reaction, Q_preheat, and Q_net as functions of moisture fraction
and mass flow rate (m_dot) for two primary feedstocks.

Inputs:  module1_output.json  (produced by module1_payload.py)
Outputs: module2_output.json  (consumed by module5_integration.py)
         matplotlib figures   (one per feedstock, Q_net vs. moisture)

Architecture: functional — pure functions, explicit arguments, no global state.
Module 5 extension point: Q_net here excludes heat exchanger recovery (ε term)
and pump work (W_pump). Both are subtracted in Module 5.

Author:  [student name]
Project: HTC Airship Disaster Relief — Senior ME Capstone
"""

import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os

# ==============================================================================
# CONSTANTS BLOCK
# All physical constants and literature values defined here with source notes.
# No magic numbers are embedded in any equation below.
# ==============================================================================

C_P_WATER = 4180.0      # [J/kg·K] specific heat of liquid water
                         # Source: NIST WebBook, water at ~25°C

T_FEED_C  = 20.0         # [°C] feed inlet temperature
                         # PLACEHOLDER — assumed near-ambient; revise for
                         # cold-climate or tropical deployment scenarios

# Feedstock parameters
# PLACEHOLDER values — replace with peer-reviewed HTC literature values before
# using results for design decisions.
# Recommended sources:
#   Kambo & Dutta (2015) "A comparative review of biochar and hydrochar..."
#   Funke & Ziegler (2010) "Hydrothermal carbonization of biomass..."
#   Reza et al. (2013) for sewage sludge HTC yields

FEEDSTOCKS = {
    "municipal_food_waste": {
        "HHV_dry_J_per_kg": 16.0e6,   # [J/kg dry] PLACEHOLDER
                                        # Typical range: 14–18 MJ/kg dry
                                        # Source: literature TBD
        "eta_HTC":          0.60,      # [-] HTC conversion efficiency PLACEHOLDER
                                        # Fraction of feedstock HHV recovered
                                        # as hydrochar + process energy
                                        # Typical range: 0.55–0.70
                                        # Source: literature TBD
        "label":            "Municipal Food Waste"
    },
    "sewage_sludge": {
        "HHV_dry_J_per_kg": 12.0e6,   # [J/kg dry] PLACEHOLDER
                                        # Typical range: 10–15 MJ/kg dry
                                        # Source: literature TBD
        "eta_HTC":          0.55,      # [-] HTC conversion efficiency PLACEHOLDER
                                        # Sewage sludge typically lower than food waste
                                        # due to higher ash and inorganic content
                                        # Source: literature TBD
        "label":            "Sewage Sludge"
    }
}

MOISTURE_RANGE = np.linspace(0.0, 1.0, 50)   # [-] moisture fraction sweep
                                               # 0.0 = bone dry, 1.0 = pure water


# ==============================================================================
# FUNCTIONS
# ==============================================================================

def calc_Q_reaction(m_dot, HHV_dry, eta_HTC, moisture_fraction):
    """
    Calculate thermal energy released by HTC reaction.

    Parameters
    ----------
    m_dot            : float  [kg/s]  total (wet basis) mass flow rate
    HHV_dry          : float  [J/kg]  higher heating value of dry feedstock
    eta_HTC          : float  [-]     HTC conversion efficiency (0–1)
    moisture_fraction: float  [-]     mass fraction of water in wet feedstock (0–1)

    Returns
    -------
    Q_reaction : float  [W]  thermal power released by HTC conversion

    Equation
    --------
    Q_reaction = m_dot * HHV_dry * eta_HTC * (1 - moisture_fraction)

    Assumptions
    -----------
    # ASSUMPTION: HHV_dry applies to the dry fraction only — wet basis
    #             correction applied via (1 - moisture_fraction).
    # ASSUMPTION: eta_HTC is treated as a fixed scalar; in reality it varies
    #             weakly with T_reactor and residence time. Module 5 can
    #             sweep eta_HTC as a sensitivity parameter.
    # ASSUMPTION: Q_reaction is evaluated at steady-state throughput m_dot.
    #             Startup transients are not modeled.
    """
    dry_fraction = 1.0 - moisture_fraction
    Q_reaction = m_dot * HHV_dry * eta_HTC * dry_fraction
    return Q_reaction   # [W]


def calc_Q_preheat(m_dot, moisture_fraction, c_p_water, T_reactor_C, T_feed_C):
    """
    Calculate thermal energy required to heat the water fraction of feed
    from inlet temperature to reactor operating temperature.

    Parameters
    ----------
    m_dot            : float  [kg/s]   total (wet basis) mass flow rate
    moisture_fraction: float  [-]      mass fraction of water in wet feedstock (0–1)
    c_p_water        : float  [J/kg·K] specific heat of water
    T_reactor_C      : float  [°C]     reactor operating temperature
    T_feed_C         : float  [°C]     feed inlet temperature

    Returns
    -------
    Q_preheat : float  [W]  thermal power required for feed preheating

    Equation
    --------
    Q_preheat = m_dot * moisture_fraction * c_p_water * (T_reactor_C - T_feed_C)

    Assumptions
    -----------
    # ASSUMPTION: Entire water fraction is heated from T_feed to T_reactor.
    #             No flash evaporation or phase separation modeled here.
    #             HTC operates at autogenous pressure, so water remains liquid
    #             throughout — this assumption is physically consistent.
    # ASSUMPTION: Heat exchanger recovery is excluded here. The ε correction
    #             (Q_preheat_net = Q_preheat * (1 - ε)) is applied in Module 5
    #             to keep this function general and independently testable.
    # ASSUMPTION: c_p_water is constant over the temperature range T_feed to
    #             T_reactor. Variation is ~5% over 20–250°C — acceptable for
    #             first-pass analysis.
    # ASSUMPTION: The dry solids fraction has negligible heat capacity compared
    #             to the water fraction. For high-moisture feeds (>0.5) this is
    #             conservative. For low-moisture feeds, revisit.
    """
    delta_T = T_reactor_C - T_feed_C
    Q_preheat = m_dot * moisture_fraction * c_p_water * delta_T
    return Q_preheat    # [W]


def calc_Q_net(Q_reaction, Q_preheat):
    """
    Calculate net thermal energy available from the HTC reactor.

    This is the gross energy balance before heat exchanger recovery and
    parasitic loads. Module 5 extends this by subtracting:
        - Q_preheat_net_reduction = Q_preheat * ε    (heat recovery credit)
        - W_pump                                      (slurry pump work)
        - W_auxiliary                                 (instrumentation, controls)

    Parameters
    ----------
    Q_reaction : float  [W]  thermal power from HTC conversion
    Q_preheat  : float  [W]  thermal power required for preheating

    Returns
    -------
    Q_net : float  [W]  net thermal power (positive = energy surplus)

    Equation
    --------
    Q_net = Q_reaction - Q_preheat

    Notes
    -----
    # NOTE: Q_net is intentionally structured for Module 5 extension.
    #       Heat exchanger recovery (ε term) and pump/auxiliary work are
    #       subtracted in Module 5 without restructuring this function:
    #
    #       Module 5 form:
    #         Q_net_effective = Q_reaction - Q_preheat*(1 - ε) - W_pump - W_aux
    #                         = Q_net + Q_preheat*ε - W_pump - W_aux
    #
    #       Q_net = 0 is the crossover moisture threshold (no recovery, no losses).
    #       Positive Q_net is necessary but not sufficient for self-sufficiency.
    """
    Q_net = Q_reaction - Q_preheat
    return Q_net    # [W]


def find_crossover_moisture(moisture_array, Q_net_array):
    """
    Find the moisture fraction at which Q_net crosses zero (energy breakeven).

    Uses linear interpolation between the two points bracketing Q_net = 0.
    Returns None if Q_net is always positive or always negative.

    Parameters
    ----------
    moisture_array : np.ndarray  [-]  moisture fraction values (sorted ascending)
    Q_net_array    : np.ndarray  [W]  corresponding Q_net values

    Returns
    -------
    crossover : float or None  [-]  moisture fraction where Q_net = 0
    """
    for i in range(len(Q_net_array) - 1):
        if Q_net_array[i] >= 0 and Q_net_array[i + 1] < 0:
            # Linear interpolation
            m0, m1 = moisture_array[i], moisture_array[i + 1]
            q0, q1 = Q_net_array[i], Q_net_array[i + 1]
            crossover = m0 - q0 * (m1 - m0) / (q1 - q0)
            return crossover
    return None     # No crossover found in range


def run_module2(module1_df, feedstocks, moisture_array, T_feed_C, c_p_water):
    """
    Execute Module 2 thermal balance sweep across all (T, r, tau, m_dot)
    combinations from Module 1 output and across the full moisture range.

    Parameters
    ----------
    module1_df     : pd.DataFrame  Module 1 output — must contain columns:
                                   [T_C, r_m, tau_s, m_dot_kg_s]
    feedstocks     : dict          Feedstock parameter dictionary (see FEEDSTOCKS)
    moisture_array : np.ndarray    [-]  moisture fraction values to sweep
    T_feed_C       : float         [°C] feed inlet temperature
    c_p_water      : float         [J/kg·K] specific heat of water

    Returns
    -------
    results_df : pd.DataFrame  with columns:
                 [T_C, r_m, tau_s, m_dot_kg_s, feedstock,
                  moisture, Q_reaction_W, Q_preheat_W, Q_net_W]
    """
    records = []

    for feedstock_key, feedstock_params in feedstocks.items():
        HHV_dry  = feedstock_params["HHV_dry_J_per_kg"]
        eta_HTC  = feedstock_params["eta_HTC"]

        for _, row in module1_df.iterrows():
            T_C        = row["T_C"]
            r_m        = row["r_m"]
            tau_s      = row["tau_s"]
            m_dot      = row["m_dot_kg_s"]

            for moisture in moisture_array:
                Q_reaction = calc_Q_reaction(m_dot, HHV_dry, eta_HTC, moisture)
                Q_preheat  = calc_Q_preheat(m_dot, moisture, c_p_water, T_C, T_feed_C)
                Q_net      = calc_Q_net(Q_reaction, Q_preheat)

                records.append({
                    "T_C":          T_C,
                    "r_m":          r_m,
                    "tau_s":        tau_s,
                    "m_dot_kg_s":   m_dot,
                    "feedstock":    feedstock_key,
                    "moisture":     round(moisture, 6),
                    "Q_reaction_W": round(Q_reaction, 4),
                    "Q_preheat_W":  round(Q_preheat,  4),
                    "Q_net_W":      round(Q_net,       4),
                })

    results_df = pd.DataFrame(records)
    return results_df


# ==============================================================================
# DRIVER BLOCK
# ==============================================================================

if __name__ == "__main__":

    # --------------------------------------------------------------------------
    # 1. Load Module 1 output
    # --------------------------------------------------------------------------
    INPUT_FILE  = "module1_output.json"
    OUTPUT_FILE = "module2_output.json"

    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(
            f"'{INPUT_FILE}' not found. Run module1_payload.py first.\n"
            f"Working directory: {os.getcwd()}"
        )

    with open(INPUT_FILE, "r") as f:
        module1_data = json.load(f)

    module1_df = pd.DataFrame(module1_data["records"])
    print(f"Loaded {len(module1_df)} rows from {INPUT_FILE}")
    print(f"Columns: {list(module1_df.columns)}")
    print(f"T_C values: {sorted(module1_df['T_C'].unique())}")
    print(f"r_m values: {sorted(module1_df['r_m'].unique())}")
    print()

    # --------------------------------------------------------------------------
    # 2. Run Module 2 sweep
    # --------------------------------------------------------------------------
    results_df = run_module2(
        module1_df    = module1_df,
        feedstocks    = FEEDSTOCKS,
        moisture_array= MOISTURE_RANGE,
        T_feed_C      = T_FEED_C,
        c_p_water     = C_P_WATER,
    )
    print(f"Module 2 sweep complete: {len(results_df)} total records")
    print()

    # --------------------------------------------------------------------------
    # 3. Print crossover moisture thresholds
    # --------------------------------------------------------------------------
    print("=" * 60)
    print("CROSSOVER MOISTURE THRESHOLDS (Q_net = 0)")
    print("=" * 60)

    # Use a representative (T, r) combination for the printed summary.
    # Choose the median T and the first r value from Module 1.
    T_rep = sorted(module1_df["T_C"].unique())[len(module1_df["T_C"].unique()) // 2]
    r_rep = sorted(module1_df["r_m"].unique())[0]

    for feedstock_key, feedstock_params in FEEDSTOCKS.items():
        label = feedstock_params["label"]
        print(f"\nFeedstock: {label}")

        sub = results_df[
            (results_df["feedstock"] == feedstock_key) &
            (results_df["T_C"]       == T_rep) &
            (results_df["r_m"]       == r_rep)
        ]

        for tau_val in sorted(sub["tau_s"].unique()):
            tau_sub = sub[sub["tau_s"] == tau_val].sort_values("moisture")
            crossover = find_crossover_moisture(
                tau_sub["moisture"].values,
                tau_sub["Q_net_W"].values
            )
            m_dot_val = tau_sub["m_dot_kg_s"].iloc[0]
            if crossover is not None:
                print(f"  τ = {tau_val/3600:.1f} hr | m_dot = {m_dot_val:.4f} kg/s"
                      f" | crossover moisture = {crossover:.3f} ({crossover*100:.1f}%)")
            else:
                q_min = tau_sub["Q_net_W"].min()
                q_max = tau_sub["Q_net_W"].max()
                print(f"  τ = {tau_val/3600:.1f} hr | m_dot = {m_dot_val:.4f} kg/s"
                      f" | no crossover in range "
                      f"(Q_net min={q_min/1000:.1f} kW, max={q_max/1000:.1f} kW)")

    print()

    # --------------------------------------------------------------------------
    # 4. Matplotlib figures — one per feedstock
    # --------------------------------------------------------------------------
    for feedstock_key, feedstock_params in FEEDSTOCKS.items():
        label = feedstock_params["label"]

        sub = results_df[
            (results_df["feedstock"] == feedstock_key) &
            (results_df["T_C"]       == T_rep) &
            (results_df["r_m"]       == r_rep)
        ]

        fig, ax = plt.subplots(figsize=(9, 6))

        for tau_val in sorted(sub["tau_s"].unique()):
            tau_sub = sub[sub["tau_s"] == tau_val].sort_values("moisture")
            m_dot_val = tau_sub["m_dot_kg_s"].iloc[0]
            Q_net_kW  = tau_sub["Q_net_W"].values / 1000.0

            ax.plot(
                tau_sub["moisture"].values,
                Q_net_kW,
                label=f"τ = {tau_val/3600:.1f} hr  (ṁ = {m_dot_val:.3f} kg/s)"
            )

            # Mark Q_net = 0 crossover
            crossover = find_crossover_moisture(
                tau_sub["moisture"].values,
                tau_sub["Q_net_W"].values
            )
            if crossover is not None:
                ax.axvline(
                    x=crossover,
                    color="gray",
                    linestyle=":",
                    linewidth=0.8,
                    alpha=0.6
                )
                ax.annotate(
                    f"x={crossover:.2f}",
                    xy=(crossover, 0),
                    xytext=(crossover + 0.02, ax.get_ylim()[0] * 0.5
                            if ax.get_ylim()[0] < 0 else 5),
                    fontsize=7,
                    color="gray"
                )

        # Q_net = 0 reference line
        ax.axhline(y=0, color="black", linewidth=1.2, linestyle="--", label="Q_net = 0")

        ax.set_xlabel("Moisture Fraction  [-]", fontsize=12)
        ax.set_ylabel("Q_net  [kW]", fontsize=12)
        ax.set_title(
            f"Module 2 — Net Thermal Power vs. Moisture\n"
            f"{label}  |  T_reactor = {T_rep}°C  |  r = {r_rep} m\n"
            f"(ε = 0, no heat recovery — gross balance only)",
            fontsize=11
        )
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()

        fig_name = f"module2_{feedstock_key}_T{int(T_rep)}_r{r_rep:.2f}.png"
        fig.savefig(fig_name, dpi=150)
        print(f"Figure saved: {fig_name}")

    plt.show()

    # --------------------------------------------------------------------------
    # 5. Save output JSON
    # --------------------------------------------------------------------------
    output = {
        "metadata": {
            "module":        "module2_thermal_balance",
            "feedstocks":    list(FEEDSTOCKS.keys()),
            "moisture_range": [float(MOISTURE_RANGE[0]), float(MOISTURE_RANGE[-1])],
            "T_feed_C":      T_FEED_C,
            "T_rep_C":       T_rep,
            "r_rep_m":       r_rep,
            "units": {
                "Q_reaction": "W",
                "Q_preheat":  "W",
                "Q_net":      "W",
                "m_dot":      "kg/s",
                "moisture":   "fraction (0=dry, 1=pure water)"
            },
            "notes": [
                "Q_net here is gross balance only (no heat exchanger recovery, no pump work).",
                "Module 5 applies ε correction and subtracts W_pump + W_auxiliary.",
                "All feedstock HHV and eta_HTC values are PLACEHOLDERS — replace with literature."
            ]
        },
        "records": results_df.to_dict(orient="records")
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nOutput saved: {OUTPUT_FILE}  ({len(results_df)} records)")
    print("Module 2 complete.")