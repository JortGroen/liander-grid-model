import pandapower as pp

_bus_params = {
        0.4:  dict(vn_kv=0.4,  min_vm_pu=0.90, max_vm_pu=1.10, s_sc_max_mva=10,  type="b"),
        10:   dict(vn_kv=10,   min_vm_pu=0.95, max_vm_pu=1.05, s_sc_max_mva=200, type="b"),
        20:   dict(vn_kv=20,   min_vm_pu=0.95, max_vm_pu=1.05, s_sc_max_mva=350, type="b"),
        50:   dict(vn_kv=50,   min_vm_pu=0.95, max_vm_pu=1.05, s_sc_max_mva=1500,type="b"),
    }   

def get_bus_params(voltage_level=10):
    return _bus_params[voltage_level]

def define_cables(net):
    cable_names = []

    # Low voltage cables
    pp.create_std_type(net, {
        "r_ohm_per_km": 0.387,   # Ω/km @20 °C
        "x_ohm_per_km": 0.080,   # Ω/km, trefoil
        "c_nf_per_km": 350,      # nF/km
        "max_i_ka":     0.250,   # kA
        "type":         "cs",     # cable, 3-core
        "vn_kv_line":   0.4
    }, name="CABLE_3x50_Cu_0.4kV", element="line")

    # Medium voltage cable 10kV
    pp.create_std_type(net, {
        "r_ohm_per_km": 0.206,
        "x_ohm_per_km": 0.0988,
        "c_nf_per_km": 358,
        "max_i_ka":     0.280,
        "type":         "cs",
        "vn_kv_line":   10
    }, name="CABLE_3x150_10kV", element="line")

    # Medium voltage cable 20kV
    pp.create_std_type(net, {
        "r_ohm_per_km": 0.125,
        "x_ohm_per_km": 0.119,
        "c_nf_per_km": 300,
        "max_i_ka":     0.355,
        "type":         "cs",
        "vn_kv_line":   20
    }, name="CABLE_1x240_20kV", element="line")

    # High voltage cable: 1×400 Al, 50 kV
    pp.create_std_type(net, {
        "r_ohm_per_km": 0.074,
        "x_ohm_per_km": 0.082,
        "c_nf_per_km": 180,
        "max_i_ka":     0.400,
        "type":         "cs",
        "vn_kv_line":   50
    }, name="CABLE_1x400_50kV", element="line")

    return cable_names

def define_transformers(net):
    """
    Adds Liander-style transformer std-types (≈2010 build year)
    covering LV/MV distribution and HV/MV primary substations.
    Call once right after you create your network object.
    """

    std_types = {
        # --- LV/MV kiosk transformers (Dyn5, tap changer on HV side ±2×2.5 %)
        "Trafo_400kVA_10_0.4": dict(
            sn_mva=0.4, vn_hv_kv=10, vn_lv_kv=0.4,
            vk_percent=4.0,  vkr_percent=1.2,
            pfe_kw=0.62,     i0_percent=0.3,
            shift_degree=30, tap_side="hv", tap_neutral=0,
            tap_max=2, tap_min=-2, tap_step_percent=2.5,
        ),

        "Trafo_630kVA_10_0.4": dict(
            sn_mva=0.63, vn_hv_kv=10, vn_lv_kv=0.4,
            vk_percent=6.0,  vkr_percent=1.1,    # Liander practice (forum)
            pfe_kw=0.81,     i0_percent=0.25,
            shift_degree=30, tap_side="hv", tap_neutral=0,
            tap_max=2, tap_min=-2, tap_step_percent=2.5,
        ),

        "Trafo_1000kVA_10_0.4": dict(
            sn_mva=1.0,  vn_hv_kv=10, vn_lv_kv=0.4,
            vk_percent=6.5, vkr_percent=0.9,
            pfe_kw=1.31,  i0_percent=0.2,
            shift_degree=30, tap_side="hv", tap_neutral=0,
            tap_max=2, tap_min=-2, tap_step_percent=2.5,
        ),

        # Optional 20 kV variant for rural feeders (identical core)
        "Trafo_1000kVA_20_0.4": dict(
            sn_mva=1.0,  vn_hv_kv=20, vn_lv_kv=0.4,
            vk_percent=6.5, vkr_percent=0.9,
            pfe_kw=1.35,  i0_percent=0.2,
            shift_degree=30, tap_side="hv", tap_neutral=0,
            tap_max=2, tap_min=-2, tap_step_percent=2.5,
        ),

        # --- Primary-substation transformers (YNd11, OLTC on HV, ±8×1.25 %)
        "Trafo_25MVA_50_10": dict(
            sn_mva=25,  vn_hv_kv=50, vn_lv_kv=10,
            vk_percent=10.0, vkr_percent=0.9,
            pfe_kw=22.6, i0_percent=0.4,
            shift_degree=30, tap_side="hv", tap_neutral=0,
            tap_max=8, tap_min=-8, tap_step_percent=1.25,
        ),

        "Trafo_40MVA_50_10": dict(
            sn_mva=40,  vn_hv_kv=50, vn_lv_kv=10,
            vk_percent=12.0, vkr_percent=1.0,
            pfe_kw=38.0, i0_percent=0.35,
            shift_degree=30, tap_side="hv", tap_neutral=0,
            tap_max=8, tap_min=-8, tap_step_percent=1.25,
        ),

        "Trafo_40MVA_50_20": dict(  # for future 20 kV roll-out
            sn_mva=40,  vn_hv_kv=50, vn_lv_kv=20,
            vk_percent=12.0, vkr_percent=1.0,
            pfe_kw=38.0, i0_percent=0.35,
            shift_degree=30, tap_side="hv", tap_neutral=0,
            tap_max=8, tap_min=-8, tap_step_percent=1.25,
        ),
    }

    for name, data in std_types.items():
        pp.create_std_type(net, data, name, element="trafo")
    
    return