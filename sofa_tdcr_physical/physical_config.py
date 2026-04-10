"""
Shared physical parameters for the TDCR “physical-grade” simulation.

Edit these values to match your real hardware spool/motor geometry.
"""

# Geometry (mm)
LENGTH_MM = 111.0
NUM_SECTIONS = 3
TENDONS_PER_SECTION = 3
NUM_CABLES = NUM_SECTIONS * TENDONS_PER_SECTION  # 9

# FEM annulus radii (must contain your tdcr_surface.stl geometry)
INNER_R_MM = 6.5
OUTER_R_MM = 18.5

# Cable routing (matches sofa_tdcr/tdcr.py spirit)
CABLE_OFFSET_MM = 12.0
CABLE_STEP_MM = 8.0
CABLE_R_MM = 0.5

# Tendon angular placements around the axis (degrees)
CABLE_ANGLES_DEG = [90.0, 210.0, 330.0]

# Material
YOUNG_KPA = 600.0
POISSON = 0.45
TOTAL_MASS_G = 30.0

# Base constraint
BASE_FIX_Y_MM = 12.0

# Spool/motor model
# theta_rad -> deltaL_mm via deltaL = spool_radius_mm * (theta - theta0)
SPOOL_RADIUS_MM = 8.0
THETA0_RAD = 0.0
MAX_PULL_MM = 25.0

THETA_MIN_RAD = THETA0_RAD
THETA_MAX_RAD = THETA0_RAD + (MAX_PULL_MM / SPOOL_RADIUS_MM)

# Command/actuation limits
SIM_RAMP_DISP_MM_PER_STEP = 0.3

# Keyboard increments
KEY_STEP_THETA_RAD = 0.05

# Control / logging
LOG_EVERY_N_STEPS = 1
STATE_SETTLE_STEPS = 5
SOFA_STEP_WAIT_S = 0.08
RESET_WAIT_S = 0.4

# Filenames (written inside this folder)
CMD_FILE = "tdcr_physical_cmd.json"
STATE_FILE = "tdcr_physical_state.json"
JSONL_LOG_FILE = "tdcr_physical_log.jsonl"

