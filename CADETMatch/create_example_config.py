#This script generates all the h5 example files
from pathlib import Path
from cadet import H5, Cadet
from addict import Dict
import numpy
import pandas
import json
import shutil
import CADETMatch.util

def create_experiments(defaults):
    config = Dict()
    config.CADETPath = Cadet.cadet_path
    config.resultsDir = 'results'
    config.searchMethod = 'UNSGA3'
    config.population = defaults.population
    config.gradVector = True
    
    parameter1 = Dict()
    parameter1.location = '/input/model/unit_001/COL_DISPERSION'
    parameter1.min = 1e-10
    parameter1.max = 1e-6
    parameter1.component = -1
    parameter1.bound = -1
    parameter1.transform = 'auto'

    parameter2 = Dict()
    parameter2.location = '/input/model/unit_001/COL_POROSITY'
    parameter2.min = 0.2
    parameter2.max = 0.7
    parameter2.component = -1
    parameter2.bound = -1
    parameter2.transform = 'auto'

    config.parameters = [parameter1, parameter2]

    experiment1 = Dict()
    experiment1.name = 'main'
    experiment1.csv = 'dextran.csv'
    experiment1.HDF5 = 'dextran.h5'
    experiment1.output_path = '/output/solution/unit_002/SOLUTION_OUTLET_COMP_000'

    config.experiments = [experiment1,]

    feature1 = Dict()
    feature1.name = "main_feature"
    feature1.type = 'DextranShape'

    experiment1.scores = [feature1,]

    experiments_dir = defaults.base_dir / "experiments"

    single = experiments_dir / "single"
    single.mkdir(parents=True, exist_ok=True)

    multiple = experiments_dir / "multiple"
    multiple.mkdir(parents=True, exist_ok=True)

    advanced = experiments_dir / "multiple_advanced"
    advanced.mkdir(parents=True, exist_ok=True)

    create_common(single, config)   
    

    #multiple
    experiment1 = Dict()
    experiment1.name = 'main1'
    experiment1.csv = 'dextran1.csv'
    experiment1.HDF5 = 'dextran1.h5'
    experiment1.output_path = '/output/solution/unit_002/SOLUTION_OUTLET_COMP_000'

    experiment2 = Dict()
    experiment2.name = 'main2'
    experiment2.csv = 'dextran2.csv'
    experiment2.HDF5 = 'dextran2.h5'
    experiment2.output_path = '/output/solution/unit_002/SOLUTION_OUTLET_COMP_000'

    feature1 = Dict()
    feature1.name = "main_feature"
    feature1.type = 'DextranShape'

    experiment1.scores = [feature1,]
    experiment2.scores = [feature1,]

    config.experiments = [experiment1, experiment2]
     
    create_common(multiple, config)   

    #multiple advanced
    #multiple
    experiment1 = Dict()
    experiment1.name = 'dextran'
    experiment1.csv = 'dextran.csv'
    experiment1.HDF5 = 'dextran.h5'
    experiment1.output_path = '/output/solution/unit_002/SOLUTION_OUTLET_COMP_000'

    experiment2 = Dict()
    experiment2.name = 'non'
    experiment2.csv = 'non.csv'
    experiment2.HDF5 = 'non.h5'
    experiment2.output_path = '/output/solution/unit_002/SOLUTION_OUTLET_COMP_000'

    feature1 = Dict()
    feature1.name = "main_feature"
    feature1.type = 'DextranShape'

    feature2 = Dict()
    feature2.name = "main_feature"
    feature2.type = 'Shape'
    feature2.decay = 1

    experiment1.scores = [feature1,]
    experiment2.scores = [feature2,]

    config.experiments = [experiment1, experiment2]

    parameter3 = Dict()
    parameter3.location = '/input/model/unit_001/FILM_DIFFUSION'
    parameter3.min = 1e-9
    parameter3.max = 1e-4
    parameter3.component = 0
    parameter3.bound = 0
    parameter3.transform = 'auto'
    parameter3.experiments = ["non"]

    parameter4 = Dict()
    parameter4.location = '/input/model/unit_001/PAR_POROSITY'
    parameter4.min = 0.2
    parameter4.max = 0.7
    parameter4.component = -1
    parameter4.bound = -1
    parameter4.transform = 'auto'
    parameter4.experiments = ["non"]

    config.parameters = [parameter1, parameter2, parameter3, parameter4]
     
    create_common(advanced, config)

def create_scores(defaults):
    create_shared_scores(defaults)
    create_ceiling(defaults)
    create_fractionation(defaults)
    create_slicing(defaults)

def create_slicing(defaults):
    "create all the scores that have the same config except for the score name"
    config = Dict()
    config.CADETPath = Cadet.cadet_path
    config.resultsDir = 'results'
    config.searchMethod = 'UNSGA3'
    config.population = defaults.population
    config.gradVector = True
    
    parameter1 = Dict()
    parameter1.location = '/input/model/unit_001/COL_DISPERSION'
    parameter1.min = 1e-10
    parameter1.max = 1e-6
    parameter1.component = -1
    parameter1.bound = -1
    parameter1.transform = 'auto'

    parameter2 = Dict()
    parameter2.location = '/input/model/unit_001/COL_POROSITY'
    parameter2.min = 0.2
    parameter2.max = 0.7
    parameter2.component = -1
    parameter2.bound = -1
    parameter2.transform = 'auto'

    config.parameters = [parameter1, parameter2]

    experiment1 = Dict()
    experiment1.name = 'main'
    experiment1.csv = 'dextran.csv'
    experiment1.HDF5 = 'dextran.h5'
    experiment1.output_path = '/output/solution/unit_002/SOLUTION_OUTLET_COMP_000'

    config.experiments = [experiment1,]

    feature1 = Dict()
    feature1.name = "feature_front"
    feature1.type = 'ShapeFront'
    feature1.start = 250
    feature1.stop = 350

    feature2 = Dict()
    feature2.name = "feature_back"
    feature2.type = 'ShapeBack'
    feature2.start = 330
    feature2.stop = 430

    experiment1.scores = [feature1,feature2]

    scores_dir = defaults.base_dir / "scores" 

    dir = scores_dir / "misc" / "multiple_scores_slicing"

    create_common(dir, config)

def create_fractionation(defaults):
    "create the ceiling"
    config = Dict()
    config.CADETPath = Cadet.cadet_path
    config.resultsDir = 'results'
    config.searchMethod = 'UNSGA3'
    config.population = defaults.population
    config.gradVector = True
    
    parameter1 = Dict()
    parameter1.location = ['/input/model/unit_001/adsorption/LIN_KA','/input/model/unit_001/adsorption/LIN_KD']
    parameter1.minKA = 1e-6
    parameter1.maxKA = 1e-2
    parameter1.minKEQ = 1e-3
    parameter1.maxKEQ = 1e3
    parameter1.component = 0
    parameter1.bound = 0
    parameter1.transform = 'auto_keq'

    parameter2 = Dict()
    parameter2.location = ['/input/model/unit_001/adsorption/LIN_KA','/input/model/unit_001/adsorption/LIN_KD']
    parameter2.minKA = 1e-6
    parameter2.maxKA = 1e-2
    parameter2.minKEQ = 1e-3
    parameter2.maxKEQ = 1e3
    parameter2.component = 1
    parameter2.bound = 0
    parameter2.transform = 'auto_keq'

    config.parameters = [parameter1, parameter2]

    experiment1 = Dict()
    experiment1.name = 'main'
    experiment1.csv = 'data_sum.csv'
    experiment1.HDF5 = 'fraction.h5'
    experiment1.output_path = '/output/solution/unit_002/SOLUTION_OUTLET_COMP_000'

    config.experiments = [experiment1,]

    feature1 = Dict()
    feature1.name = "sum_signal"
    feature1.type = 'Shape'
    feature1.output_path = ['/output/solution/unit_002/SOLUTION_OUTLET_COMP_000', '/output/solution/unit_002/SOLUTION_OUTLET_COMP_001']
    feature1.csv = 'data_sum.csv'

    feature2 = Dict()
    feature2.name = "fractionation"
    feature2.type = 'fractionationSlide'
    feature2.unit_name = "unit_002"
    feature2.fraction_csv = 'frac.csv'

    experiment1.scores = [feature1,feature2]

    scores_dir = defaults.base_dir / "scores"
    dir = scores_dir / "fractionationSlide"

    create_common(dir, config)


    #modify for fractionationSSE

    dir = scores_dir / "other" / "fractionationSSE"

    config.experiments[0].scores[1].type = "fractionationSSE" 
    config.experiments[0].scores[0].type = "SSE" 

    create_common(dir, config)

    dir = scores_dir / "misc" / "multiple_components"

    config.experiments[0].scores[1].type = "Shape" 
    config.experiments[0].scores[1].output_path = '/output/solution/unit_002/SOLUTION_OUTLET_COMP_001'
    config.experiments[0].scores[1].csv = 'comp1.csv'

    config.experiments[0].scores[0].type = "Shape" 
    config.experiments[0].scores[0].output_path = '/output/solution/unit_002/SOLUTION_OUTLET_COMP_000'
    config.experiments[0].scores[0].csv = 'comp0.csv'

    create_common(dir, config)

def create_ceiling(defaults):
    "create the ceiling"
    config = Dict()
    config.CADETPath = Cadet.cadet_path
    config.resultsDir = 'results'
    config.searchMethod = 'UNSGA3'
    config.population = defaults.population
    config.gradVector = True
    
    parameter1 = Dict()
    parameter1.location = '/input/model/unit_000/sec_000/CONST_COEFF'
    parameter1.min = 0.1
    parameter1.max = 5.0
    parameter1.component = 0
    parameter1.bound = 0
    parameter1.transform = 'auto'

    config.parameters = [parameter1,]

    experiment1 = Dict()
    experiment1.name = 'main'
    experiment1.csv = 'flat.csv'
    experiment1.HDF5 = 'flat.h5'
    experiment1.output_path = '/output/solution/unit_002/SOLUTION_OUTLET_COMP_000'

    config.experiments = [experiment1,]

    feature1 = Dict()
    feature1.name = "main_feature"
    feature1.type = 'Ceiling'
    feature1.max_value = 1.0

    experiment1.scores = [feature1,]

    scores_dir = defaults.base_dir / "scores"
    dir = scores_dir / "Ceiling"
    score_name = dir.name

    create_common(dir, config)

def create_shared_scores(defaults):
    "create all the scores that have the same config except for the score name"
    config = Dict()
    config.CADETPath = Cadet.cadet_path
    config.resultsDir = 'results'
    config.searchMethod = 'UNSGA3'
    config.population = defaults.population
    config.gradVector = True
    
    parameter1 = Dict()
    parameter1.location = '/input/model/unit_001/COL_DISPERSION'
    parameter1.min = 1e-10
    parameter1.max = 1e-6
    parameter1.component = -1
    parameter1.bound = -1
    parameter1.transform = 'auto'

    parameter2 = Dict()
    parameter2.location = '/input/model/unit_001/COL_POROSITY'
    parameter2.min = 0.2
    parameter2.max = 0.7
    parameter2.component = -1
    parameter2.bound = -1
    parameter2.transform = 'auto'

    config.parameters = [parameter1, parameter2]

    experiment1 = Dict()
    experiment1.name = 'main'
    experiment1.csv = 'dextran.csv'
    experiment1.HDF5 = 'dextran.h5'
    experiment1.output_path = '/output/solution/unit_002/SOLUTION_OUTLET_COMP_000'

    config.experiments = [experiment1,]

    feature1 = Dict()
    feature1.name = "main_feature"
    feature1.type = 'DextranShape'

    experiment1.scores = [feature1,]

    dextran_paths = ['DextranShape', 'Shape', 'ShapeBack', 'ShapeFront', 'SSE', 
                     'other/curve', 'other/DextranSSE', 'other/ShapeDecay',
                     'other/ShapeDecayNoDer', 'other/ShapeDecaySimple', 'other/ShapeNoDer', 
                     'other/ShapeOnly', 'other/ShapeSimple', 'other/similarity', 
                     'other/similarityDecay']

    scores_dir = defaults.base_dir / "scores"

    for path in dextran_paths:
        dir = scores_dir / path
        score_name = dir.name
        temp_config = config.deepcopy()
        temp_config.experiments[0].scores[0].type = score_name

        if score_name in ('Shape', 'ShapeBack', 'ShapeFront'):
            temp_config.experiments[0].scores[0].decay = 0
            temp_config.experiments[0].scores[0].derivative = 1

        if score_name in ('ShapeBack', 'ShapeFront'):
            temp_config.experiments[0].scores[0].max_percent = 0.98
            temp_config.experiments[0].scores[0].min_percent = 0.02

        create_common(dir, temp_config)


def create_search(defaults):
    config = Dict()
    config.CADETPath = Cadet.cadet_path
    config.resultsDir = 'results'
    
    parameter1 = Dict()
    parameter1.location = '/input/model/unit_001/COL_DISPERSION'
    parameter1.min = 1e-10
    parameter1.max = 1e-6
    parameter1.component = -1
    parameter1.bound = -1
    parameter1.transform = 'auto'

    parameter2 = Dict()
    parameter2.location = '/input/model/unit_001/COL_POROSITY'
    parameter2.min = 0.2
    parameter2.max = 0.7
    parameter2.component = -1
    parameter2.bound = -1
    parameter2.transform = 'auto'

    config.parameters = [parameter1, parameter2]

    experiment1 = Dict()
    experiment1.name = 'main'
    experiment1.csv = 'dextran.csv'
    experiment1.HDF5 = 'dextran.h5'
    experiment1.output_path = '/output/solution/unit_002/SOLUTION_OUTLET_COMP_000'

    config.experiments = [experiment1,]

    feature1 = Dict()
    feature1.name = "main_feature"
    feature1.type = 'DextranShape'

    experiment1.scores = [feature1,]

    create_nsga3(defaults, config)
    create_unsga3(defaults, config)
    create_multistart(defaults, config)
    create_graphspace(defaults, config)
    create_scoretest(defaults, config)
    create_gradient(defaults, config)
    create_early_stopping(defaults, config)
    create_refine_shape(defaults, config)
    create_refine_sse(defaults, config)
    create_altScore(defaults, config)
    create_mcmc_stage1(defaults, config)
    create_mcmc_stage2(defaults, config)

def create_common(dir, config, altDir=None):
    if altDir is not None:
        config.baseDir = altDir.as_posix()
    else:
        config.baseDir = dir.as_posix()

    match_config_file = dir / 'dextran.json'

    with open(match_config_file.as_posix(), 'w') as json_file:
        json.dump(config.to_dict(), json_file, indent='\t')

def create_mcmc_stage1(defaults, config):
    dir = defaults.base_dir / "search" / "mcmc" / "stage1"
    config = config.deepcopy()
    config.searchMethod = 'UNSGA3'
    config.population = defaults.population
    config.continueMCMC = 1
    config.MCMCpopulationSet = defaults.MCMCpopulation

    error_model = Dict()
    error_model.file_path = "dextran.h5"
    error_model.experimental_csv = "dextran.csv"
    error_model.name = "main"
    error_model.units = [2]
    error_model.delay = [0.0, 2.0]
    error_model.flow = [1.0, 0.001]
    error_model.load = [1.0, 0.001]
    error_model.uv_noise_norm = [1.0, 0.001]

    config.errorModelCount = 1000
    config.errorModel = [error_model,]
    create_common(dir, config)

def create_mcmc_stage2(defaults, config):
    dir = defaults.base_dir / "search" / "mcmc" / "stage2"
    config = config.deepcopy()
    config.baseDir = dir.as_posix()
    config.searchMethod = 'UNSGA3'
    config.population = defaults.population
    config.continueMCMC = 1
    config.MCMCpopulationSet = defaults.MCMCpopulation

    error_model = Dict()
    error_model.file_path = "non.h5"
    error_model.experimental_csv = "non.csv"
    error_model.name = "main"
    error_model.units = [2]
    error_model.delay = [0.0, 2.0]
    error_model.flow = [1.0, 0.001]
    error_model.load = [1.0, 0.001]
    error_model.uv_noise_norm = [1.0, 0.001]

    config.errorModelCount = 1000
    config.errorModel = [error_model,]

    config.experiments[0].csv = "non.csv"
    config.experiments[0].HDF5 = "non.h5"

    config.experiments[0].scores[0].type = "Shape"
    config.experiments[0].scores[0].decay = 1

    parameter1 = Dict()
    parameter1.location = '/input/model/unit_001/FILM_DIFFUSION'
    parameter1.min = 1e-12
    parameter1.max = 1e-2
    parameter1.component = -1
    parameter1.bound = -1
    parameter1.transform = 'auto'

    parameter2 = Dict()
    parameter2.location = '/input/model/unit_001/PAR_POROSITY'
    parameter2.min = 0.2
    parameter2.max = 0.7
    parameter2.component = -1
    parameter2.bound = -1
    parameter2.transform = 'auto'

    config.parameters = [parameter1, parameter2]

    mcmc_h5 = Path(defaults.base_dir / "search" / "mcmc" / "stage1" / "results" / "mcmc_refine" / "mcmc" / "mcmc.h5")
    config.mcmc_h5 = mcmc_h5.as_posix()

    match_config_file = dir / 'non.json'

    with open(match_config_file.as_posix(), 'w') as json_file:
        json.dump(config.to_dict(), json_file, indent='\t')

def create_altScore(defaults, config):
    dir = defaults.base_dir / "search" / "other" / "altScore"
    dir.mkdir(parents=True, exist_ok=True)
    config = config.deepcopy()
    config.searchMethod = 'AltScore'
    config.population = 0
    config.PreviousResults = (defaults.base_dir / "search" / "nsga3" / "results" / "result.h5").as_posix()
    config.experiments[0].scores[0].type = "Shape"
    config.resultsDir = (dir / "results").as_posix()
    config.resultsDirOriginal = (defaults.base_dir / "search" / "nsga3" / "results").as_posix()
    create_common(dir, config, altDir = (defaults.base_dir / "search" / "nsga3"))

def create_refine_shape(defaults, config):
    dir = defaults.base_dir / "search" / "other" / "refine_shape"
    config = config.deepcopy()
    config.searchMethod = 'UNSGA3'
    config.population = defaults.population
    config.gradVector = False
    create_common(dir, config)

def create_refine_sse(defaults, config):
    dir = defaults.base_dir / "search" / "other" / "refine_sse"
    config = config.deepcopy()
    config.searchMethod = 'UNSGA3'
    config.population = defaults.population
    config.gradVector = True
    create_common(dir, config)

def create_early_stopping(defaults, config):
    dir = defaults.base_dir / "search" / "other" / "early_stopping"
    config = config.deepcopy()
    config.searchMethod = 'UNSGA3'
    config.population = defaults.population
    config.gradVector = True
    config.stopAverage = 1e-3
    config.stopBest = 1e-3
    create_common(dir, config)

def create_gradient(defaults, config):
    dir = defaults.base_dir / "search" / "gradient"
    config = config.deepcopy()
    config.searchMethod = 'Gradient'
    config.population = 0
    config.gradVector = 1
    config.experiments[0].scores[0].type = "SSE"
    config.seeds = [[2e-7, 0.37],[1e-7, 0.37],[2e-7, 0.41],[1e-6, 0.5],[1e-10, 0.2]]

    create_common(dir, config)

def create_scoretest(defaults, config):
    dir = defaults.base_dir / "search" / "scoretest"
    config = config.deepcopy()
    config.searchMethod = 'ScoreTest'
    config.population = 0
    config.seeds = [[2e-7, 0.37],[1e-7, 0.37],[2e-7, 0.41],[1e-6, 0.5]]

    create_common(dir, config)

def create_graphspace(defaults, config):
    dir = defaults.base_dir / "search" / "graphSpace"
    config = config.deepcopy()
    config.searchMethod = 'GraphSpace'
    config.population = defaults.population
    config.gradVector = True

    create_common(dir, config)

def create_multistart(defaults, config):
    dir = defaults.base_dir / "search" / "multistart"
    config = config.deepcopy()
    config.searchMethod = 'Multistart'
    config.population = defaults.population
    config.gradVector = True
    create_common(dir, config)

def create_nsga3(defaults, config):
    dir = defaults.base_dir / "search" / "nsga3"
    config = config.deepcopy()
    config.searchMethod = 'NSGA3'
    config.population = defaults.population
    config.stallGenerations = 10
    config.finalGradRefinement = True
    config.gradVector = True
    create_common(dir, config)

def create_unsga3(defaults, config):
    dir = defaults.base_dir / "search" / "unsga3"
    config = config.deepcopy()
    config.searchMethod = 'UNSGA3'
    config.population = defaults.population
    config.stallGenerations = 10
    config.finalGradRefinement = True
    config.gradVector = True
    create_common(dir, config)

def create_transforms(defaults):
    create_transforms_dextran(defaults)
    create_transforms_non(defaults)
    create_experiments_linear(defaults)
    create_experiments_cstr(defaults)
    create_experiments_linear_exp(defaults)
    create_experiments_index(defaults)

def create_experiments_index(defaults):
    config = Dict()
    config.CADETPath = Cadet.cadet_path
    config.resultsDir = 'results'
    config.searchMethod = 'UNSGA3'
    config.population = defaults.population
    config.gradVector = True
    
    parameter1 = Dict()
    parameter1.location = '/input/model/unit_001/adsorption/LIN_KA'
    parameter1.min = 1e-6
    parameter1.max = 1e-2
    parameter1.index = 0
    parameter1.transform = 'auto'

    parameter2 = Dict()
    parameter2.location = '/input/model/unit_001/adsorption/LIN_KA'
    parameter2.min = 1e-6
    parameter2.max = 1e-2
    parameter2.index = 1
    parameter2.transform = 'auto'

    config.parameters = [parameter1, parameter2]

    experiment1 = Dict()
    experiment1.name = 'main'
    experiment1.csv = 'data_sum.csv'
    experiment1.HDF5 = 'fraction.h5'
    experiment1.output_path = '/output/solution/unit_002/SOLUTION_OUTLET_COMP_000'

    config.experiments = [experiment1,]

    feature1 = Dict()
    feature1.name = "comp0"
    feature1.type = 'Shape'
    feature1.output_path = '/output/solution/unit_002/SOLUTION_OUTLET_COMP_000'
    feature1.csv = 'comp0.csv'

    feature2 = Dict()
    feature2.name = "comp1"
    feature2.type = 'Shape'
    feature2.output_path = '/output/solution/unit_002/SOLUTION_OUTLET_COMP_001'
    feature2.csv = 'comp1.csv'

    experiment1.scores = [feature1,feature2]

    create_common(defaults.base_dir / "transforms" / "misc" / "index", config)

def create_experiments_linear_exp(defaults):
    config = Dict()
    config.CADETPath = Cadet.cadet_path
    config.resultsDir = 'results'
    config.searchMethod = 'UNSGA3'
    config.population = defaults.population
    config.gradVector = True
    
    parameter1 = Dict()
    parameter1.location = '/input/model/unit_001/COL_DISPERSION'
    parameter1.minLower = 1e-8
    parameter1.maxLower = 1e-6
    parameter1.minUpper = 1e-8
    parameter1.maxUpper = 1e-6
    parameter1.minX = 1
    parameter1.maxX = 3
    parameter1.x_name = 'pH'
    parameter1.component = -1
    parameter1.bound = -1
    parameter1.transform = 'norm_linear'
    
    config.parameters = [parameter1]

    experiment1 = Dict()
    experiment1.name = 'main1'
    experiment1.csv = 'dex1.csv'
    experiment1.HDF5 = 'dex1.h5'
    experiment1.pH = 1
    experiment1.output_path = '/output/solution/unit_002/SOLUTION_OUTLET_COMP_000'

    experiment2 = experiment1.deepcopy()
    experiment2.name = 'main2'
    experiment2.csv = 'dex2.csv'
    experiment2.HDF5 = 'dex2.h5'
    experiment2.pH = 2

    experiment3 = experiment1.deepcopy()
    experiment3.name = 'main3'
    experiment3.csv = 'dex3.csv'
    experiment3.HDF5 = 'dex3.h5'
    experiment3.pH = 3

    config.experiments = [experiment1, experiment2, experiment3]

    feature1 = Dict()
    feature1.name = "main_feature"
    feature1.type = 'Shape'
    feature1.decay = 1

    experiment1.scores = [feature1,]
    experiment2.scores = [feature1,]
    experiment3.scores = [feature1,]

    experiments_dir = defaults.base_dir / "transforms"

    create_common(experiments_dir / "norm_linear", config)

    parameter1.transform = 'linear'

    create_common(experiments_dir / "other" / "linear", config)

def create_experiments_cstr(defaults):
    config = Dict()
    config.CADETPath = Cadet.cadet_path
    config.resultsDir = 'results'
    config.searchMethod = 'UNSGA3'
    config.population = defaults.population
    config.gradVector = True
    
    parameter1 = Dict()
    parameter1.location = '/input/model/unit_001/INIT_VOLUME'
    parameter1.min = 1e-7
    parameter1.max = 1e-4
    parameter1.component = -1
    parameter1.bound = -1
    parameter1.transform = 'auto'

    parameter2 = Dict()
    parameter2.locationFrom = '/input/model/unit_001/INIT_VOLUME'
    parameter2.componentFrom = -1
    parameter2.boundFrom = -1
    parameter2.locationTo = '/input/model/unit_003/INIT_VOLUME'
    parameter2.componentTo = -1
    parameter2.boundTo = -1
    parameter2.transform = 'set_value'

    parameter3 = Dict()
    parameter3.location1 = '/input/model/unit_001/INIT_VOLUME'
    parameter3.component1 = -1
    parameter3.bound1 = -1
    parameter3.location2 = '/input/model/unit_003/INIT_VOLUME'
    parameter3.component2 = -1
    parameter3.bound2 = -1
    parameter3.locationSum = '/input/model/unit_004/INIT_VOLUME'
    parameter3.componentSum = -1
    parameter3.boundSum = -1
    parameter3.transform = 'sum'

    config.parameters = [parameter1,parameter2, parameter3]

    experiment1 = Dict()
    experiment1.name = 'main'
    experiment1.csv = 'cstr.csv'
    experiment1.HDF5 = 'cstr.h5'
    experiment1.output_path = '/output/solution/unit_002/SOLUTION_OUTLET_COMP_000'

    config.experiments = [experiment1,]

    feature1 = Dict()
    feature1.name = "main_feature"
    feature1.type = 'Shape'
    feature1.decay = 1

    experiment1.scores = [feature1,]

    experiments_dir = defaults.base_dir / "transforms"

    create_common(experiments_dir / "sum", config)

def create_experiments_linear(defaults):
    config = Dict()
    config.CADETPath = Cadet.cadet_path
    config.resultsDir = 'results'
    config.searchMethod = 'UNSGA3'
    config.population = defaults.population
    config.gradVector = True
    
    parameter1 = Dict()
    parameter1.location = ['/input/model/unit_001/adsorption/LIN_KA','/input/model/unit_001/adsorption/LIN_KD']
    parameter1.minKA = 1e-5
    parameter1.maxKA = 1e-3
    parameter1.minKEQ = 1e-2
    parameter1.maxKEQ = 1e2
    parameter1.component = 0
    parameter1.bound = 0
    parameter1.transform = 'auto_keq'

    config.parameters = [parameter1,]

    experiment1 = Dict()
    experiment1.name = 'main'
    experiment1.csv = 'lin.csv'
    experiment1.HDF5 = 'lin.h5'
    experiment1.output_path = '/output/solution/unit_002/SOLUTION_OUTLET_COMP_000'

    config.experiments = [experiment1,]

    feature1 = Dict()
    feature1.name = "main_feature"
    feature1.type = 'Shape'
    feature1.decay = 1

    experiment1.scores = [feature1,]

    experiments_dir = defaults.base_dir / "transforms"

    linear_paths = ['auto_keq', 'other/keq', 'other/norm_keq']

    for path in linear_paths:
        dir = experiments_dir / path
        score_name = dir.name
        temp_config = config.deepcopy()
        temp_config.parameters[0].transform = score_name

        create_common(dir, temp_config)

    #set_value estimate one concentration and set the other
    temp_config = config.deepcopy()

    parameter1 = Dict()
    parameter1.location = '/input/model/unit_000/sec_000/CONST_COEFF'
    parameter1.min = 1e-2
    parameter1.max = 1e0
    parameter1.component = 0
    parameter1.bound = 0
    parameter1.transform = 'auto'

    parameter2 = Dict()
    parameter2.locationFrom = '/input/model/unit_000/sec_000/CONST_COEFF'
    parameter2.componentFrom = 0
    parameter2.boundFrom = 0
    parameter2.locationTo = '/input/model/unit_000/sec_000/CONST_COEFF'
    parameter2.componentTo = 1
    parameter2.boundTo = 0
    parameter2.transform = 'set_value'

    temp_config.parameters = [parameter1,parameter2]
    create_common(experiments_dir / "set_value", temp_config)


def create_transforms_non(defaults):
    config = Dict()
    config.CADETPath = Cadet.cadet_path
    config.resultsDir = 'results'
    config.searchMethod = 'UNSGA3'
    config.population = defaults.population
    config.gradVector = True
    
    parameter1 = Dict()
    parameter1.location = '/input/model/unit_001/FILM_DIFFUSION'
    parameter1.min = 1e-8
    parameter1.max = 1e-4
    parameter1.component = 0
    parameter1.bound = 0
    parameter1.transform = 'auto_inverse'

    config.parameters = [parameter1,]

    experiment1 = Dict()
    experiment1.name = 'main'
    experiment1.csv = 'non.csv'
    experiment1.HDF5 = 'non.h5'
    experiment1.output_path = '/output/solution/unit_002/SOLUTION_OUTLET_COMP_000'

    config.experiments = [experiment1,]

    feature1 = Dict()
    feature1.name = "main_feature"
    feature1.type = 'Shape'
    feature1.decay = 1

    experiment1.scores = [feature1,]

    experiments_dir = defaults.base_dir / "transforms"
    create_common(experiments_dir / "auto_inverse", config)

    #
    parameter1 = Dict()
    parameter1.locationFrom = '/input/model/unit_001/COL_POROSITY'
    parameter1.componentFrom= -1
    parameter1.boundFrom = -1
    parameter1.locationTo = '/input/model/unit_001/PAR_POROSITY'
    parameter1.componentTo = -1
    parameter1.boundTo = -1
    parameter1.min = -0.1
    parameter1.max = 0.1    
    parameter1.transform = 'norm_add'

    config.parameters = [parameter1,]
    create_common(experiments_dir / "norm_add", config)


    parameter1 = Dict()
    parameter1.locationFrom = '/input/model/unit_001/COL_POROSITY'
    parameter1.componentFrom= -1
    parameter1.boundFrom = -1
    parameter1.locationTo = '/input/model/unit_001/PAR_POROSITY'
    parameter1.componentTo = -1
    parameter1.boundTo = -1
    parameter1.min = 0.8
    parameter1.max = 1.5    
    parameter1.transform = 'norm_mult'

    config.parameters = [parameter1,]
    create_common(experiments_dir / "norm_mult", config)

def create_transforms_dextran(defaults):
    config = Dict()
    config.CADETPath = Cadet.cadet_path
    config.resultsDir = 'results'
    config.searchMethod = 'UNSGA3'
    config.population = defaults.population
    config.gradVector = True
    
    parameter1 = Dict()
    parameter1.location = '/input/model/unit_001/COL_POROSITY'
    parameter1.min = 0.2
    parameter1.max = 0.7
    parameter1.component = -1
    parameter1.bound = -1
    parameter1.transform = 'auto'

    config.parameters = [parameter1,]

    experiment1 = Dict()
    experiment1.name = 'main'
    experiment1.csv = 'dextran.csv'
    experiment1.HDF5 = 'dextran.h5'
    experiment1.output_path = '/output/solution/unit_002/SOLUTION_OUTLET_COMP_000'

    config.experiments = [experiment1,]

    feature1 = Dict()
    feature1.name = "main_feature"
    feature1.type = 'DextranShape'

    experiment1.scores = [feature1,]

    experiments_dir = defaults.base_dir / "transforms"

    dextran_paths = ['auto', 'other/log', 'other/norm', 'other/norm_log', 'other/null']

    for path in dextran_paths:
        dir = experiments_dir / path
        score_name = dir.name
        temp_config = config.deepcopy()
        temp_config.parameters[0].transform = score_name

        create_common(dir, temp_config)

    temp_config = config.deepcopy()

    parameter1 = Dict()
    parameter1.location = '/input/model/unit_001/CROSS_SECTION_AREA'
    parameter1.min = 1e-3
    parameter1.max = 1e-1
    parameter1.component = -1
    parameter1.bound = -1
    parameter1.transform = 'norm_diameter'

    temp_config.parameters = [parameter1,]

    create_common(experiments_dir / 'norm_diameter', temp_config)

    parameter1.transform = 'diameter'

    create_common(experiments_dir / 'other/diameter', temp_config)


    parameter1 = Dict()
    parameter1.area_location = '/input/model/unit_001/CROSS_SECTION_AREA'
    parameter1.length_location = '/input/model/unit_001/COL_LENGTH'
    parameter1.minVolume = 1e-6
    parameter1.maxVolume = 1e-4
    parameter1.minArea = 1e-5
    parameter1.maxArea = 1e-3
    parameter1.component = -1
    parameter1.bound = -1
    parameter1.transform = 'norm_volume_area'

    temp_config.parameters = [parameter1,]

    create_common(experiments_dir / 'norm_volume_area', temp_config)

    parameter1.transform = 'volume_area'

    create_common(experiments_dir / 'other/volume_area', temp_config)


    parameter1 = Dict()
    parameter1.area_location = '/input/model/unit_001/CROSS_SECTION_AREA'
    parameter1.length_location = '/input/model/unit_001/COL_LENGTH'
    parameter1.minVolume = 1e-6
    parameter1.maxVolume = 1e-4
    parameter1.minLength = 0.1
    parameter1.maxLength = 0.3
    parameter1.component = -1
    parameter1.bound = -1
    parameter1.transform = 'norm_volume_length'

    temp_config.parameters = [parameter1,]

    create_common(experiments_dir / 'norm_volume_length', temp_config)

    parameter1.transform = 'volume_length'

    create_common(experiments_dir / 'other/volume_length', temp_config)


def main(defaults):
    "create simulations by directory"
    create_experiments(defaults)
    create_scores(defaults)
    create_search(defaults)
    create_transforms(defaults)

if __name__ == "__main__":
    main()

