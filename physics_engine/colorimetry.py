import numpy as np
from scipy.interpolate import interp1d

# Assuming cie_data_loader.py is in the same package (or accessible via your path)
from .cie_data_loader import get_cie_1931_cmfs, get_d65_spd 

def calculate_colorimetry(reflectance: np.ndarray, lambda_nm: np.ndarray) -> tuple[np.ndarray, float, float]:
    """
    Calculates sRGB color and CIE xy chromaticity from spectral reflectance 
    using manual interpolation and the hardcoded standard data.
    
    :param reflectance: Spectral reflectance array (R(lambda)).
    :param lambda_nm: Wavelengths array (in nm) corresponding to reflectance.
    :return: Tuple (R_sRGB_255, x, y) where R_sRGB_255 is a 3-element array [R, G, B] (0-255)
    """
    
    # --- Step 1: Define Common Wavelength Grid (380-780 nm, 1 nm step) ---
    lambda_full = np.arange(380, 781, 1, dtype=np.float64)
    delta_lambda = 1.0 # 1 nm step
    
    # Check if input data needs interpolation (to avoid recalculating CMFs and D65 data every time)
    # The MATLAB script resamples if the input lambda array is not the full 380:1:780 grid.
    if len(reflectance) != len(lambda_full) or not np.array_equal(lambda_nm, lambda_full):
        # A. Reflectance (R) - Interpolate to the 1 nm grid
        
        # FIX: Use 'extrapolate' to match MATLAB's linear extrapolation ('extrap')
        R_interp_func = interp1d(lambda_nm, reflectance, kind='linear', fill_value=0.0, bounds_error=False)      
        reflectance_aligned = R_interp_func(lambda_full)
        
        # FIX: Clamp any negative extrapolated values to 0, matching MATLAB
        reflectance_aligned[reflectance_aligned < 0] = 0
        
        # Update the inputs for the next steps
        reflectance = reflectance_aligned
        lambda_nm = lambda_full
    
    # --- Step 2: Load and Interpolate Standard Data ---
    
    # B. Standard CIE 1931 Color Matching Functions (CMFs)
    # We assume the CMF data is already on the 1 nm grid (lambda_full)
    lambda_cmf_std, x_bar_std, y_bar_std, z_bar_std = get_cie_1931_cmfs()
    x_bar = x_bar_std
    y_bar = y_bar_std
    z_bar = z_bar_std
    
    # C. White Light Source (Illuminant D65: Standard Daylight)
    lambda_d65_std, spd_d65_std = get_d65_spd()

    # Interpolate the 5 nm step D65 data to the 1 nm wavelength grid
    spd_interp_func = interp1d(lambda_d65_std, spd_d65_std, kind='linear', fill_value=0, bounds_error=False)
    spd_source = spd_interp_func(lambda_full)
    spd_source[spd_source < 0] = 0 # Ensure no negative values
  
    # --- Step 3: Calculate Tristimulus Values (XYZ) ---
    # XYZ = sum(R * S * CMF * delta_lambda)
    
    integrated_x = reflectance * spd_source * x_bar * delta_lambda
    integrated_y = reflectance * spd_source * y_bar * delta_lambda
    integrated_z = reflectance * spd_source * z_bar * delta_lambda
    
    # Summation for Tristimulus Values
    X = np.sum(integrated_x)
    Y = np.sum(integrated_y)
    Z = np.sum(integrated_z)

    # --- Step 4: Normalization (to White Point) ---
    # Y_white is the luminance of the perfect white diffuser (R=1) under the illuminant S
    Y_white = np.sum(spd_source * y_bar * delta_lambda)
    
    X_n = X / Y_white
    Y_n = Y / Y_white
    Z_n = Z / Y_white

    # --- Step 5: Calculate Chromaticity (xy) ---
    
    sum_XYZ = X + Y + Z
    # Handle division by zero for black or near-black colors
    if sum_XYZ == 0:
        x, y = 0.0, 0.0
    else:
        x = X / sum_XYZ
        y = Y / sum_XYZ
    
    # --- Step 6: XYZ to sRGB Conversion (Linear and Gamma) ---
    
    # Linear sRGB Calculation (XYZ to Linear sRGB) - D65 white point
    M_xyz_to_linear_rgb = np.array([
        [ 3.2406, -1.5372, -0.4986],
        [-0.9689,  1.8758,  0.0415],
        [ 0.0557, -0.2040,  1.0570 ]
    ])
    
    XYZ_norm = np.array([X_n, Y_n, Z_n])
    R_linear = M_xyz_to_linear_rgb @ XYZ_norm
    
    # Apply sRGB Gamma Correction and CLAMPING 
    R_sRGB_normalized = np.zeros(3)
    for i in range(3):
        V_linear = R_linear[i]
        
        # sRGB Companding (Gamma Correction)
        if V_linear <= 0.0031308:
            V_sRGB = V_linear * 12.92
        else:
            V_sRGB = 1.055 * (V_linear**(1/2.4)) - 0.055
            
        # Clamping to [0, 1] range before scaling to 255
        V_sRGB = np.clip(V_sRGB, 0.0, 1.0)
        R_sRGB_normalized[i] = V_sRGB

    # Scale to 0-255 range and convert to integer
    R_sRGB_255 = np.round(R_sRGB_normalized * 255).astype(np.int32)
    
    return R_sRGB_255, x, y
