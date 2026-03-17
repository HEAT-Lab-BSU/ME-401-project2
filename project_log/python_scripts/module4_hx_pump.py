# =============================================================================
# module4_hx_pump.py
# HTC Airship Disaster Relief System — Module 4: Heat Exchanger & Pump Work
# =============================================================================
# Module 4 stubs — calculation bodies deferred.
# Implement before running Module 5 with non-zero HX recovery or pump work.
# =============================================================================

import json
import os

# =============================================================================
# CONSTANTS BLOCK
# All physical constants and design parameters defined here.
# No magic numbers in equations.
# Sources annotated inline.
# =============================================================================

C_P_WATER       = 4180.0   # [J/kg·K]  specific heat of water — Engineering toolbox / standard reference
ETA_PUMP        = 0.65     # [-]       slurry pump efficiency — PLACEHOLDER; typical centrifugal slurry pump range 0.55–0.75
AUX_FRACTION    = 0.075    # [-]       auxiliary load as fraction of Q_net — PLACEHOLDER; midpoint of 5–10% design estimate
EPSILON_DEFAULT = 0.70     # [-]       heat exchanger effectiveness — PLACEHOLDER; realistic counterflow HX target


# =============================================================================
# FUNCTION STUBS
# Docstrings define the I/O contract for Module 5.
# Bodies are `pass` — implement before Module 5 integration.
# =============================================================================

def calc_Q_recovered(m_dot, c_p_hot, c_p_cold, T_hot_in, T_cold_in, epsilon):
    """
    Calculate heat recovered by the counterflow heat exchanger using the ε-NTU method.

    This function computes how much thermal energy from the hot reactor outlet
    stream is transferred to the cold feed stream, reducing the net preheat
    demand on the reactor.

    Parameters
    ----------
    m_dot : float
        Mass flow rate [kg/s]. Assumed equal for both hot and cold streams
        (single-pass, same fluid). Passed from Module 1 output.
    c_p_hot : float
        Specific heat of the hot stream (reactor outlet) [J/kg·K].
        Use C_P_WATER = 4180.0 for water-dominant slurry.
    c_p_cold : float
        Specific heat of the cold stream (feed) [J/kg·K].
        Use C_P_WATER = 4180.0 for water-dominant slurry.
    T_hot_in : float
        Inlet temperature of the hot stream [°C].
        Set equal to T_reactor (reactor operating temperature, 180–250°C).
    T_cold_in : float
        Inlet temperature of the cold stream [°C].
        Set equal to T_feed (ambient feed temperature, typically 15–30°C).
    epsilon : float
        Heat exchanger effectiveness [-], dimensionless, range 0.0 to 0.85.
        Represents the fraction of maximum possible heat transfer achieved.
        Use EPSILON_DEFAULT = 0.70 as the baseline design value.

    Returns
    -------
    Q_recovered : float
        Heat recovered from the hot stream and delivered to the cold stream [W].

    Method
    ------
    ε-NTU method, counterflow configuration, steady-state, no phase change.

    Equations (to implement):
        C_hot  = m_dot * c_p_hot          # [W/K] heat capacity rate, hot stream
        C_cold = m_dot * c_p_cold         # [W/K] heat capacity rate, cold stream
        C_min  = min(C_hot, C_cold)       # [W/K] controlling (minimum) capacity rate
        Q_max  = C_min * (T_hot_in - T_cold_in)   # [W] theoretical maximum heat transfer
        Q_recovered = epsilon * Q_max     # [W] actual heat recovered

    # ASSUMPTION: steady-state counterflow heat exchanger
    # ASSUMPTION: no phase change in either stream within the HX
    # ASSUMPTION: fouling neglected at this analysis stage
    # ASSUMPTION: both streams have the same mass flow rate m_dot
    """
    pass


def calc_Q_preheat_net(Q_preheat, Q_recovered):
    """
    Calculate the net preheat demand after heat exchanger recovery.

    This function reduces the gross preheat requirement (energy needed to
    bring the cold feed up to reactor temperature) by the amount recovered
    from the hot outlet stream. The result is the actual thermal load
    that must be supplied by the reactor's exothermic output.

    Parameters
    ----------
    Q_preheat : float
        Gross preheat energy demand [W].
        Computed in Module 2 as:
            Q_preheat = m_dot * moisture_fraction * C_P_WATER * (T_reactor - T_feed)
        Passed directly from Module 2 output (module2_output.json).
    Q_recovered : float
        Heat recovered by the heat exchanger [W].
        Output of calc_Q_recovered() in this module.

    Returns
    -------
    Q_preheat_net : float
        Net preheat demand after heat recovery [W].
        This is the term subtracted from Q_reaction in the Module 5 energy balance:
            Q_net = Q_reaction - Q_loss - Q_preheat_net

    Equation (to implement):
        Q_preheat_net = Q_preheat - Q_recovered

    # ASSUMPTION: Q_recovered does not exceed Q_preheat
    #             (i.e., HX cannot supply more heat than the feed requires)
    #             If Q_recovered > Q_preheat, Q_preheat_net should be clipped to 0.
    """
    pass


def calc_pump_work(m_dot, P_autogenous_pa, rho_slurry, eta_pump):
    """
    Calculate the mechanical work required to pressurize the slurry feed
    to reactor operating pressure.

    Pump work is the primary parasitic mechanical load on the system.
    It must be overcome by the recovered energy for the system to be
    self-sufficient. Dominated by the pressurization term; pipe friction
    is deferred to a later analysis stage.

    Parameters
    ----------
    m_dot : float
        Mass flow rate of slurry feed [kg/s].
        Passed from Module 1 output.
    P_autogenous_pa : float
        Autogenous reactor pressure [Pa].
        Derived from T_reactor via steam tables (Module 3 polynomial fit).
        Typical range: 10–40 bar → 1.0e6–4.0e6 Pa.
    rho_slurry : float
        Density of the feed slurry [kg/m³].
        Typical range: 950–1100 kg/m³ as a function of moisture and solids content.
        Use 1000 kg/m³ as a first-pass estimate for water-dominant slurry.
    eta_pump : float
        Pump isentropic efficiency [-], dimensionless.
        Use ETA_PUMP = 0.65 as the placeholder for slurry service.

    Returns
    -------
    W_pump : float
        Pump shaft work required to pressurize the feed [W].

    Equation (to implement):
        W_pump = m_dot * P_autogenous_pa / (rho_slurry * eta_pump)

    # ASSUMPTION: pump work dominated by pressurization against P_autogenous
    # ASSUMPTION: Darcy-Weisbach pipe friction term deferred to future analysis
    # ASSUMPTION: eta_pump = 0.65 is a placeholder for slurry service
    # ASSUMPTION: feed enters pump at approximately atmospheric pressure (1 bar inlet)
    """
    pass


def calc_W_auxiliary(Q_net_W, aux_fraction):
    """
    Estimate the auxiliary electrical load of the system as a fraction of
    the net thermal output.

    Auxiliary loads include instrumentation, control systems, communications,
    lighting, and other non-process electrical demands. At this stage, these
    are estimated as a fixed fraction of Q_net rather than itemized.

    Parameters
    ----------
    Q_net_W : float
        Net thermal output of the reactor [W].
        Computed in Module 2 / Module 5 as:
            Q_net = Q_reaction - Q_loss - Q_preheat_net
    aux_fraction : float
        Auxiliary load as a fraction of Q_net [-], dimensionless.
        Use AUX_FRACTION = 0.075 (midpoint of 5–10% design range).
        This is a PLACEHOLDER pending itemized auxiliary load analysis.

    Returns
    -------
    W_auxiliary : float
        Estimated auxiliary electrical load [W].

    Equation (to implement):
        W_auxiliary = Q_net_W * aux_fraction

    # ASSUMPTION: aux_fraction = 0.075 is a PLACEHOLDER — midpoint of 5–10% range
    # ASSUMPTION: auxiliary load scales linearly with Q_net (proportional model)
    # ASSUMPTION: no fixed baseline auxiliary load at zero throughput
    #             (i.e., standby/idle power not captured at this stage)
    """
    pass


# =============================================================================
# DRIVER BLOCK
# Runs when this file is executed directly: python module4_hx_pump.py
# Confirms that module2_output.json loads without error.
# Does NOT call any stub functions — bodies are pass.
# =============================================================================

if __name__ == "__main__":

    # --- Load Module 2 handoff output ---
    output_filename = "module2_output.json"

    if not os.path.exists(output_filename):
        print(f"WARNING: '{output_filename}' not found in working directory.")
        print("         Place module2_output.json alongside this script before running Module 5.")
    else:
        with open(output_filename, "r") as f:
            module2_data = json.load(f)
        print(f"SUCCESS: '{output_filename}' loaded without error.")
        print(f"         Keys found: {list(module2_data.keys())}")

    print()
    print("=" * 60)
    print("Module 4 stubs loaded. I/O contracts defined. Ready for Module 5.")
    print("=" * 60)
    print()
    print("Functions defined (bodies are `pass` — implement before Module 5):")
    print("  calc_Q_recovered(m_dot, c_p_hot, c_p_cold, T_hot_in, T_cold_in, epsilon)")
    print("  calc_Q_preheat_net(Q_preheat, Q_recovered)")
    print("  calc_pump_work(m_dot, P_autogenous_pa, rho_slurry, eta_pump)")
    print("  calc_W_auxiliary(Q_net_W, aux_fraction)")
    print()
    print("Constants defined:")
    print(f"  C_P_WATER       = {C_P_WATER} J/kg·K")
    print(f"  ETA_PUMP        = {ETA_PUMP}  [-]  PLACEHOLDER")
    print(f"  AUX_FRACTION    = {AUX_FRACTION} [-]  PLACEHOLDER")
    print(f"  EPSILON_DEFAULT = {EPSILON_DEFAULT}  [-]  PLACEHOLDER")