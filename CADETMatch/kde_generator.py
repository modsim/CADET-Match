#This module simulates noise (systemic and random) to use for kernel density estimation based on experimental data

#Currently the randomness is

#Pump flow rate
#Pump delay
#Base noise
#Signal noise

import itertools
import score
from cadet import Cadet
from pathlib import Path
import numpy
import scoop
import sys
from sklearn.neighbors.kde import KernelDensity
from sklearn.model_selection import cross_val_score
from sklearn.decomposition import PCA
from sklearn import preprocessing
import copy

bw_tol = 1e-4

import warnings
with warnings.catch_warnings():
    warnings.filterwarnings("ignore",category=FutureWarning)
    import h5py

import scipy.optimize

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import util
import cache

from scoop import futures
import synthetic_error

import os

def bandwidth_score(bw, data, store):
    bandwidth = 10**bw[0]
    kde_bw = KernelDensity(kernel='exponential', bandwidth=bandwidth, atol=bw_tol)
    scores = cross_val_score(kde_bw, data, cv=3)
    store.append( [bandwidth, -max(scores)] )
    return -max(scores)

def get_bandwidth(scores, cache):
    store = []
    result = scipy.optimize.differential_evolution(bandwidth_score, bounds = [(-4, 1),], 
                                               args = (scores,store,))
    bandwidth = 10**result.x[0]
    scoop.logger.info("selected bandwidth %s", bandwidth)

    store = numpy.array(store)

    mcmcDir = Path(cache.settings['resultsDirMCMC'])
    plt.scatter(numpy.log10(store[:,0]), store[:,1])
    plt.xlabel('bandwidth')
    plt.ylabel('cross_val_score')
    plt.savefig(str(mcmcDir / "log_bandwidth.png" ), bbox_inches='tight')
    plt.close()

    plt.scatter(store[:,0], store[:,1])
    plt.xlabel('bandwidth')
    plt.ylabel('cross_val_score')
    plt.savefig(str(mcmcDir / "bandwidth.png" ), bbox_inches='tight')
    plt.close()

    return bandwidth, store

def mirror(data):
    data_min = numpy.max(data,0) - data
    data_mask = numpy.ma.masked_equal(data_min, 0.0, copy=False)
    min_value = data_mask.min(axis=0)
    
    data_mirror = 1 + 1 - numpy.copy(data) + min_value
    full_data = numpy.vstack([data_mirror, data])
    
    return full_data

def getPCA(data):
    pca = PCA(n_components = 1e-3, svd_solver = 'full')
    pca.fit(mirror(data))
    return pca

def getScaler(data):
    scaler = preprocessing.RobustScaler().fit(data)
    return scaler

def getKDE(cache, scores, bw):
    #scores = generate_data(cache)

    scores_mirror = mirror(scores)
    pca = getPCA(scores_mirror)

    #scores_pca = pca.transform(scores_mirror)

    scaler = getScaler(scores_mirror)

    scores_scaler = scaler.transform(scores_mirror)

    kde = KernelDensity(kernel='exponential', bandwidth=bw, atol=bw_tol).fit(scores_scaler)

    plotKDE(cache, kde, scores_scaler)

    #do kde stuff
    #return kde
    return kde, pca, scaler

def generate_data(cache):
    scores, simulations = generate_synthetic_error(cache)

    if scores is None:
        reference_result = setupReferenceResult(cache)

        try:
            variations = cache.settings['kde']['variations']
        except KeyError:
            variations = 100

        simulations = [reference_result]
        for i in range(variations):
            simulations.append(mutate(cache, reference_result))

        plotVariations(cache, temp)

        scores = []
        for first,second in itertools.combinations(temp, 2):
            scores.append(score_sim(first, second, cache))

        scores = numpy.array(scores)

    mcmcDir = Path(cache.settings['resultsDirMCMC'])
    save_scores = mcmcDir / 'scores_used.npy'

    numpy.save(save_scores, scores)

    scores_mirror = mirror(scores)
    #pca = getPCA(scores_mirror)

    #scores_pca = pca.transform(scores_mirror)

    scaler = getScaler(scores_mirror)

    scores_scaler = scaler.transform(scores_mirror)

    bandwidth, store = get_bandwidth(scores_scaler, cache)

    #writeVariations(cache, scores_scaler, bandwidth, simulations, store)

    return scores, bandwidth

def synthetic_error_simulation(json_path):
    if json_path != cache.cache.json_path:
        cache.cache.setup(json_path)

    file_path = cache.cache.settings['kde_synthetic']['file_path']
    delay_settings = cache.cache.settings['kde_synthetic']['delay']
    flow_settings = cache.cache.settings['kde_synthetic']['flow']
    load_settings = cache.cache.settings['kde_synthetic']['load']
    error_slope_settings = cache.cache.settings['kde_synthetic']['error_slope']
    error_base_settings = cache.cache.settings['kde_synthetic']['error_base']
    base_settings = cache.cache.settings['kde_synthetic']['base']
    count_settings = cache.cache.settings['kde_synthetic']['count']
    experimental_csv = cache.cache.settings['kde_synthetic']['experimental_csv']

    dir_base = Path(cache.cache.settings.get('baseDir'))
    file = dir_base / file_path

    data = numpy.loadtxt(experimental_csv, delimiter=',')
    times = data[:,0]

    temp = Cadet()
    temp.filename = bytes(file)
    temp.load()

    util.setupSimulation(temp, times)

    nsec = temp.root.input.solver.sections.nsec

    def post_function(simulation):
        error_slope = numpy.random.normal(error_slope_settings[0], error_slope_settings[1], 1)[0]
        base = numpy.max(simulation.root.output.solution.unit_002.solution_outlet_comp_000)/1000.0
        error_base = numpy.random.normal(base, base/error_base_settings, len(simulation.root.output.solution.unit_002.solution_outlet_comp_000))
        simulation.root.output.solution.unit_002.solution_outlet_comp_000 = simulation.root.output.solution.unit_002.solution_outlet_comp_000 * error_slope + error_base
    
    error_delay = Cadet(temp.root)

    delays = numpy.abs(numpy.random.normal(delay_settings[0], delay_settings[1], nsec))
    
    synthetic_error.pump_delay(error_delay, delays)

    flow = numpy.random.normal(flow_settings[0], flow_settings[1], error_delay.root.input.solver.sections.nsec)
    
    synthetic_error.error_flow(error_delay, flow)
    
    load = numpy.random.normal(load_settings[0], load_settings[1], error_delay.root.input.solver.sections.nsec)
    
    synthetic_error.error_load(error_delay, load)

    result = util.runExperiment(None, cache.cache.settings['experiments'][0], cache.cache.settings, cache.cache.target, error_delay, 60.0, cache.cache, fullPrecision=True, post_function=post_function)

    if result is not None:
        os.remove(result['path'])

    return result

def generate_synthetic_error(cache):
    if 'kde_synthetic' in cache.settings:
        count_settings = int(cache.settings['kde_synthetic']['count'])
        results = []
        for result in futures.map(synthetic_error_simulation, [cache.json_path] * count_settings):
            
            #result = synthetic_error_simulation(cache.json_path)
            if result is not None:
                results.append(result)

        scores = []
        outputs = []
        simulations = []
        for result in results:
            scores.append(result['scores'])
            outputs.append(result['simulation'].root.output.solution.unit_002.solution_outlet_comp_000)
            simulations.append(result['simulation'])

        scores = numpy.array(scores)
        outputs = numpy.array(outputs)

        times = results[0]['simulation'].root.input.solver.user_solution_times

        dir_base = cache.settings.get('resultsDirBase')
        file = dir_base / 'kde_data.h5'

        with h5py.File(file, 'w') as hf:
            hf.create_dataset('scores', data=scores, compression="gzip")
            hf.create_dataset('outputs', data=outputs, compression="gzip")
            hf.create_dataset('times', data=times, compression="gzip")
        
        return scores, simulations

    return None, None

def writeVariations(cache, scores, bandwidth, simulations, store):

    mcmcDir = Path(cache.settings['resultsDirMCMC'])

    mcmc_kde = mcmcDir / 'mcmc_kde.h5'

    bandwidth = numpy.array(bandwidth, dtype="f8")

    data, times = getData(simulations)

    store = numpy.array(store)

    with h5py.File(mcmc_kde, 'w') as hf:
        hf.create_dataset("bandwidth", data=bandwidth, maxshape=tuple(None for i in range(bandwidth.ndim)), fillvalue=[0])

        hf.create_dataset("scores", data=scores, maxshape=(None, len(scores[0])), compression="gzip")

        hf.create_dataset("bandwidth_scores", data=store, maxshape=(None,2), compression="gzip")

        for name, value in times.items():
            hf.create_dataset(name, data=value, maxshape=(None,), compression="gzip")

        for name, value in data.items():
            hf.create_dataset(name, data=value, maxshape=(None, len(value[0])), compression="gzip")

def getData(variations):

    data = {}
    times = {}

    for variation in variations:
        for experiment in variation:
            name = experiment['name']

            if 'data' in experiment:
                experiment_data = experiment['data']

                key = '%s_%s' % (name, "times")
                if key not in data:
                    times[key] = experiment_data[:,0]

                key = name
                if key not in data:
                    data[key] = []

                data[key].append(experiment_data[:,1])

            for feature in experiment['features']:
                feature_name = feature['name']
                
                if 'data' in feature:
                    experiment_data = feature['data']

                    key = '%s_%s' % (name, feature_name)
                    if key not in data:
                        data[key] = []
                    data[key].append(experiment_data[:,1])

    for key,value in data.items():
        data[key] = numpy.array(value)

    return data, times

def plotVariations(cache, temp):

    data, times = getData(temp)

    mcmcDir = Path(cache.settings['resultsDirMCMC'])

    for key,value in data.items():
        experiment = key.split('_unit', maxsplit=1)[0]

        time = times['%s_times' % experiment]

        mean = numpy.mean(value, 0)
        std = numpy.std(value, 0)
        minValues = numpy.min(value, 0)
        maxValues = numpy.max(value, 0)

        plt.plot(time, mean)
        plt.fill_between(time, mean - std, mean + std,
                    color='green', alpha=0.2)
        plt.fill_between(time, minValues, maxValues,
                    color='red', alpha=0.2)
        plt.xlabel('time(s)')
        plt.ylabel('conc mol/m^3')
        plt.savefig(str(mcmcDir / ("%s.png" % key ) ), bbox_inches='tight')
        plt.close()

        plt.plot(time, value.transpose(), 'g', alpha=0.04, linewidth=2)
        plt.xlabel('time(s)')
        plt.ylabel('conc mol/m^3')
        plt.savefig(str(mcmcDir / ("%s_probability.png" % key ) ), bbox_inches='tight')
        plt.close()

        plt.plot(time, value.transpose())
        plt.xlabel('time(s)')
        plt.ylabel('conc mol/m^3')
        plt.savefig(str(mcmcDir / ("%s_lines.png" % key ) ), bbox_inches='tight')
        plt.close()

def plotKDE(cache, kde, scores):
    return None

def setupReferenceResult(cache):
    #results = {}
    
    #for experiment in cache.settings['experiments']:
        
    #    templatePath = experiment['reference']
    #    templateSim = Cadet()
    #    templateSim.filename = templatePath
    #    templateSim.run()
    #    templateSim.load()
        
    #    results[experiment['name']] = {'simulation':templateSim}

    temp = []
    for experiment in cache.settings['experiments']:
        temp_exp = dict(experiment)

        if 'CSV' in temp_exp:
            temp_exp['data'] = numpy.loadtxt(temp_exp['CSV'], delimiter=',')

        for feature in temp_exp['features']:
            if 'CSV' in feature:
                feature['data'] = numpy.loadtxt(feature['CSV'], delimiter=',')
        temp.append(temp_exp)

    return temp


def mutate(cache, reference_result):
    "generate variations of the data with different types of noise"
    result = []

    for experiment in reference_result:
        experiment_temp = copy.deepcopy(experiment)

        pump_delay_time = None

        if 'data' in experiment_temp:
            data = experiment_temp['data']
            
            pump_delay_time = pump_delay(cache, data, pump_delay_time)

            #pump_flow(cache, data)
            base_noise(cache, data)
            signal_noise(cache, data)

            experiment_temp['data'] = data

        for feature in experiment_temp['features']:
            if 'data' in feature:
                data = feature['data']
            
                pump_delay_time = pump_delay(cache, data, pump_delay_time)
                #pump_flow(cache, data)
                base_noise(cache, data)
                signal_noise(cache, data)
                feature['data'] = data
        
        result.append(experiment_temp)

    return result

def pump_delay(cache, data, pump_delay_time=None):
    "systemic error related to delays in the pump"
    "assume data is mono-spaced in time"
    "time is column 0 and values is column 1"
    times = data[:,0]

    #delay = numpy.random.uniform(0.0, 60.0, 1)
    if pump_delay_time is not None:
        dely = pump_delay_time
    else:
        try:
            pump_mean = cache.settings['kde']['pump_delay_mean']
        except KeyError:
            pump_mean = 0.0

        try:
            pump_std = cache.settings['kde']['pump_delay_std']
        except KeyError:
            pump_std = 1.0
            
        #delay = -1
        #while delay < 0:
        delay = numpy.random.normal(pump_mean, pump_std, 1)

    delay = delay[0]
    #interval = times[1] - times[0]
    #delay = quantize_delay(delay[0], interval)

    #data[:,1] = score.roll(data[:,1], delay)
    data[:,1] = score.roll_spline(data[:,0], data[:,1], -delay)

    return delay

def pump_flow(cache, tempSim):
    "random noise related to the pump flow rate"
    "assume 5% margin of error but no other changes to chromatogram"
    "assume change is small enough that the chromatogram shape does not change"
    "can't currently model this without simulation work"
    pass

def base_noise(cache, data):
    "add random noise based on baseline noise"
    "based on looking at experimental data"
    times = data[:,0]
    
    try:
        noise_std = cache.settings['kde']['base_noise_std']
    except KeyError:
        noise_std = 1e-7

    noise = numpy.random.normal(0.0, noise_std, len(times))

    data[:,1] = data[:,1] + noise * max(data[:,1])

def signal_noise(cache, data):
    "add noise to the signal"
    "based on looking at experimental error about +/- .5%"
    times = data[:,0]

    #0.003 base on experiments

    try:
        noise_std = cache.settings['kde']['signal_noise_std']
    except KeyError:
        noise_std = 0.003

    noise = numpy.random.normal(1.0, noise_std, len(times))


    data[:,1] = data[:,1] * noise

def get_outputs(tempSim):
    "get the outputs for tempSim so they can be mutated"
    temp = []
    for unitName, unit in tempSim.root.output.solution.items():
        if "unit" in unitName:
            for solutionName, solution in unit.items():
                if 'outlet' in solutionName:
                    temp.append( ((unitName, solutionName), solution) )
    return temp

def quantize_delay(delay, interval):
    return int(round(delay/float(interval))*float(interval)/interval)

def score_sim(first,second, cache):
    "score first vs second simulation"
    target = {}
    for experiment in first:
        target[experiment["name"]] = cache.setupExperiment(experiment)

    score_sim = []
    diff = 0
    for experiment in second:
        experimentName = experiment['name']

        data = experiment.get('data', None)

        for feature in experiment['features']:
            featureType = feature['type']
            featureName = feature['name']

            if data is None:
                data = feature.get('data', None)

            if featureType in cache.scores:
                scores, sse, sse_count, diff, minimize = cache.scores[featureType].run({'simulation':data}, target[experimentName][featureName])
                score_sim.extend(scores)

    return score_sim