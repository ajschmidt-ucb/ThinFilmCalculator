Thin-Film Reflectance and Colorimetry Calculator

Developed by: 
Alexander J. Schmidt, PhD
Electrical Engineering and Computer Sciences
University of California, Berkeley
Prof. Salahuddin Laboratory and Marvell Nanofabrication Laboratory

A Python-based desktop application for calculating the spectral reflectance and colorimetric properties of multi-layer thin-film stacks. It implements the Parratt Recursion Relation for precise optical simulation.

Features

  * Multi-Layer Stack Simulation: Define and simulate a stack of thin-film layers on a substrate.
  * Parratt Recursion Relation: Utilizes a robust transfer-matrix method to calculate spectral reflectance (R(lambda)) for any angle of incidence and polarization (s and p).
  * Colorimetry Engine: Converts the calculated spectral reflectance into CIE xy chromaticity and displayable sRGB values, allowing for the direct visualization of thin-film color.
      * Uses standard CIE 1931 CMFs and D65 illuminant.
  * Refractive Index Management: Loads and interpolates n and k data from text files for various materials.
  * Interactive GUI: A user-friendly interface to manage layers, set parameters (angle, wavelength range), and execute calculations.
  * Matplotlib Visualization: Plots the spectral reflectance curve and a Color Chart for thickness sweeps.

Installation

The project requires Python 3.x and several standard libraries.

1.  Dependencies

Install the necessary Python packages using pip:

pip install numpy scipy PyQt6 matplotlib pyinstaller

To generate a standalone executable:

Windows: pyinstaller --onefile --windowed --name ""ThinFilmCalculator"" --add-data ""data;data"" gui_app.py
macOS/Linux: pyinstaller --onefile --windowed --name ""ThinFilmCalculator"" --add-data ""data:data"" gui_app.py

2.  Data Files

The physics engine relies on a collection of n and k material data files.

1.  Create a folder named data/ in the project's root directory.
2.  Place your material data files (e.g., Al.txt, Si.txt, etc., typically lambda, n, k columns) inside the data/ folder. The material name in the GUI must match the prefix of the filename (e.g., material 'Al' looks for Al.txt).

Usage

To start the application, simply run the main GUI file:

python gui_app.py

1.  Define the Stack: Use the GUI to add, configure (material and thickness), and remove thin-film layers.
2.  Set Parameters: Specify the incident angle (theta), wavelength range (lambda\_start, lambda\_end), and polarization (s/p).
3.  Run Simulation: Click Calculate Reflectance to see the R(lambda) plot and the resulting sRGB color.
4.  Thickness Sweep (Optional): Define a thickness range to generate a Color Chart visualization for a chosen layer.

Project Structure

.
|-- gui\_app.py \# Main application window and GUI logic (PyQt6)
|-- LayerRow.py \# Custom widget for managing a single layer in the GUI
|-- physics\_engine/
|   |-- reflectance.py \# Core physics: Parratt Recursion Relation for R(lambda)
|   |-- colorimetry.py \# Converts R(lambda) to CIE xy and sRGB color
|   |-- nk\_data\_loader.py \# Loads and interpolates n, k material data
|   |-- cie\_data\_loader.py \# Contains standard CIE data (CMFs, D65 SPD)
|-- data/
|   |-- Al.txt \# Example material n, k data file
|   |-- ...
|-- README.md
|-- LICENSE.txt \# Full text of the MIT License

Licensing

This project is licensed under the MIT License.

The full text of the license is provided in the included LICENSE.txt file.
