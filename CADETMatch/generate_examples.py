import create_examples
import create_example_config
import subprocess
import sys
from pathlib import Path
from cadet import H5, Cadet
from addict import Dict

defaults = Dict()
defaults.cadet_path = Path(sys.argv[2]).as_posix()
defaults.base_dir = Path(sys.argv[1]).resolve()
defaults.flow_rate = 2.88e-8 # m^3/s
defaults.ncol = 100
defaults.npar = 10
defaults.abstol = 1e-8
defaults.algtol = 1e-10
defaults.reltol = 1e-8
defaults.lin_ka1 = 4e-4
defaults.lin_ka2 = 1e-4
defaults.lin_kd1 = 4e-3
defaults.lin_kd2 = 1e-3
defaults.col_dispersion = 2e-7
defaults.film_diffusion = 1e-6
defaults.par_diffusion = 3e-11

population = int(sys.argv[3])
mcmc_population = int(sys.argv[4])

if population:
    defaults.population = population
else:
    defaults.population = 20

if mcmc_population:
    defaults.MCMCpopulation = mcmc_population
else:
    defaults.MCMCpopulation = 20

Cadet.cadet_path = defaults.cadet_path

if __name__ == "__main__":
    create_examples.main(defaults)
    create_example_config.main(defaults)

