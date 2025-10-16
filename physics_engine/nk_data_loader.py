# physics_engine/nk_data_loader.py
import numpy as np
from scipy.interpolate import interp1d
import sys
import os 
import warnings


class NKDataLoader:
    """Manages the loading, caching, and interpolation of refractive index data (from load_nk_data.m)."""
    _data_cache = {} 
    
    @staticmethod
    def _get_data_folder_path():
        """Gets the path to the 'data' folder, handling PyInstaller bundling."""
        # Check if the application is running from a PyInstaller bundle
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Path is inside the temp folder created by PyInstaller
            return os.path.join(sys._MEIPASS, 'data')
        else:
            # Path is relative to the script for development/normal run
            # NOTE: Assuming 'data' is at the root level next to 'gui_app.py'
            return 'data'
            
    # Use the static method to define the final path variable
    DATA_FOLDER = _get_data_folder_path()

    @staticmethod
    def load_and_interpolate(filename: str, lambda_nm: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Loads data from a file, caches it, and interpolates to target wavelengths."""
        if filename not in NKDataLoader._data_cache:
            data_path = os.path.join(NKDataLoader.DATA_FOLDER, filename)
            try:
                raw_data = np.loadtxt(data_path, skiprows=1) 
                
                cache_entry = {
                    'lambda': raw_data[:, 0],
                    'n': raw_data[:, 1],
                    'k': raw_data[:, 2]
                }
                NKDataLoader._data_cache[filename] = cache_entry
                
            except FileNotFoundError:
                raise FileNotFoundError(f"Material data file not found: {data_path}. Ensure it exists in the '{NKDataLoader.DATA_FOLDER}/' directory.")
            except Exception as e:
                raise Exception(f"Error reading or parsing data file {filename}: {e}")

        data = NKDataLoader._data_cache[filename]
        
        # Interpolate n and k - FIX: Use 'extrapolate' to match MATLAB's 'extrap'
        f_n = interp1d(data['lambda'], data['n'], kind='linear', 
                       bounds_error=False, fill_value='extrapolate') # <-- FIXED
        n = f_n(lambda_nm)
        
        f_k = interp1d(data['lambda'], data['k'], kind='linear', 
                       bounds_error=False, fill_value='extrapolate') # <-- FIXED
        k = f_k(lambda_nm)
        
        return n, k


def get_refractive_index(material: str, lambda_nm: np.ndarray) -> np.ndarray:
    # ... (rest of function is unchanged) ...
    """Returns the complex refractive index N = n + ik for a given material (from getRefractiveIndex.m)."""
    material_lower = material.lower()
    
    if material_lower == 'air':
        # Air has n=1, k=0 (complex index is 1 + 0i)
        return np.full_like(lambda_nm, 1.0, dtype=np.complex128)
        
    # Mapping the material string to its data file (matches MATLAB's switch block)
    file_map = {
        'a-ge': 'a-Ge.txt', 'a-si': 'a-Si.txt', 'poly-si': 'poly-Si.txt',
        'al': 'Al.txt', 'al2o3': 'Al2O3.txt', 'gaas': 'GaAs.txt',
        'ge': 'Ge.txt', 'hfn': 'HfN.txt', 'hfo2': 'HfO2.txt',
        'mgo': 'MgO.txt', 'ruo2': 'RuO2.txt', 'si': 'Si.txt',
        'si3n4': 'Si3N4.txt', 'sio': 'SiO.txt', 'sio2': 'SiO2.txt',
        'sno2': 'SnO2.txt', 'tio2': 'TiO2.txt', 'w': 'W.txt',
        'zno': 'ZnO.txt', 'zro2': 'ZrO2.txt'
    }
    
    if material_lower in file_map:
        filename = file_map[material_lower]
        n, k = NKDataLoader.load_and_interpolate(filename, lambda_nm)
        # N = n + i*k 
        return n + 1j * k 
    else:
        raise ValueError(f"Material '{material}' not found in the refractive index database.")
