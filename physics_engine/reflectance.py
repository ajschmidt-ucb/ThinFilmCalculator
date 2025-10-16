# physics_engine/reflectance.py
import numpy as np
# FIX: Corrected import to use the nk_data_loader module
from .nk_data_loader import get_refractive_index 

def calculate_reflectance(layers: list[tuple[str, float]], substrate: str, 
                          lambda_nm: np.ndarray, theta_inc_deg: float) -> tuple[np.ndarray, np.ndarray]:
    """Implements the Parratt Recursion Relation for spectral reflectance (from calculateReflectance.m)."""
    
    theta_inc_rad = np.deg2rad(theta_inc_deg)
    num_films = len(layers)
    num_lambda = len(lambda_nm)
    
    # 1. Get ALL Refractive Indices and thicknesses
    materials_list = ['Air'] + [layer[0] for layer in layers] + [substrate]
    thicknesses_array = np.array([0.0] + [layer[1] for layer in layers] + [0.0])
    N_all = [get_refractive_index(mat, lambda_nm) for mat in materials_list]

    n0_sin_theta0 = N_all[0].real * np.sin(theta_inc_rad) # Incident medium is Air (n0=1)
    
    # Complex reflection coefficients (initialized for the recursion start at the substrate)
    # r_s and r_p will hold r_{j+1} from the previous iteration
    r_s = np.zeros(num_lambda, dtype=np.complex128)
    r_p = np.zeros(num_lambda, dtype=np.complex128)
    
    # Loop from j = N (last film) down to j = 0 (ambient medium)
    # This runs from num_films down to 0, matching the full MATLAB iteration range.
    for j in range(num_films, -1, -1):
        
        n_j = N_all[j]       # N_j (current layer's index)
        n_next = N_all[j+1]  # N_j+1 (layer below's index)
        d_j = thicknesses_array[j]
        
        # --- 2. Calculate k_z (Complex Z-component of wave vector) ---
        k_z_j = (2 * np.pi / lambda_nm) * np.lib.scimath.sqrt(n_j**2 - n0_sin_theta0**2)
        k_z_next = (2 * np.pi / lambda_nm) * np.lib.scimath.sqrt(n_next**2 - n0_sin_theta0**2)
        
        # --- 3. Calculate Normalized Admittance-like Term f_j ---
        f_j_s = k_z_j; f_next_s = k_z_next
        f_j_p = k_z_j / n_j**2; f_next_p = k_z_next / n_next**2
        
        # --- 4. Calculate Fresnel Term F_j (Reflection at j/j+1 interface) ---
        F_j_s = (f_j_s - f_next_s) / (f_j_s + f_next_s)
        F_j_p = (f_j_p - f_next_p) / (f_j_p + f_next_p)
        
        # --- 5. Calculate Phase Term a_j ---
        # If j=0 (Air), d_j=0, so a_j = exp(0) = 1.
        a_j = np.exp(1j * 2 * k_z_j * d_j)
        
        # --- 6. The Parratt Recursion (FIXED to match MATLAB structure) ---
        # r_s/r_p holds r_{j+1} from the previous iteration (or r_{N+1}=0 initially)
        r_next_s = r_s
        r_next_p = r_p
        
        # r_j = a_j * [F_j + r_{j+1}] / [1 + F_j * r_{j+1}]
        r_s = a_j * (F_j_s + r_next_s) / (1 + F_j_s * r_next_s)
        r_p = a_j * (F_j_p + r_next_p) / (1 + F_j_p * r_next_p)
            
    # --- 7. Final Reflectance (R = |r_0|^2) ---
    # After the loop, r_s/r_p holds r_0.
    Rs = np.abs(r_s)**2
    Rp = np.abs(r_p)**2
    
    return Rs, Rp
