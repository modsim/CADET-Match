import CADETMatch.util as util
import random
from pathlib import Path
import csv
import CADETMatch.pareto as pareto
import scoop
import time
import array

name = "Gradient"

def run(cache, tools, creator):
    "run the parameter estimation"
    random.seed()

    sim_start = generation_start = time.time()
    result_data = {'input':[], 'output':[], 'output_meta':[], 'results':{}, 'times':{}, 'input_transform':[], 'input_transform_extended':[], 'strategy':[], 
                   'mean':[], 'confidence':[]}

    pop = []

    if "seeds" in cache.settings:
        seed_pop = [cache.toolbox.individual_guess([f(v) for f, v in zip(cache.settings['transform'], sublist)]) for sublist in cache.settings['seeds']]
        pop.extend(seed_pop)

    gradCheck = cache.badScore

    hof = pareto.ParetoFront(similar=util.similar, similar_fit=util.similar_fit)
    meta_hof = pareto.ParetoFront(similar=util.similar, similar_fit=util.similar_fit_meta)
    grad_hof = pareto.ParetoFront(similar=util.similar, similar_fit=util.similar_fit)

    path = Path(cache.settings['resultsDirBase'], cache.settings['csv'])
    with path.open('a', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quoting=csv.QUOTE_ALL)

        scoop.logger.info("Population %s", pop)

        gradCheck, newChildren = cache.toolbox.grad_search(gradCheck, pop, cache, writer, csvfile, hof, 
                                                           meta_hof, -1, check_all=True, filterOverlap=False)

        stalled, stallWarn, progressWarn = util.eval_population(cache.toolbox, cache, newChildren, writer, csvfile, hof, meta_hof, -1, result_data)

        scoop.logger.info("gradCheck %s", gradCheck)
        scoop.logger.info("newChildren %s", newChildren)

        avg, bestMin, bestProd = util.averageFitness(newChildren, cache)
        
        util.writeProgress(cache, -1, newChildren, hof, meta_hof, grad_hof, avg, bestMin, bestProd, sim_start, generation_start, result_data)
        
        util.finish(cache)
        util.graph_corner_process(cache, last=True)

        return hof

def setupDEAP(cache, fitness, grad_fitness, grad_search, map_function, creator, base, tools):
    "setup the DEAP variables"
    creator.create("FitnessMax", base.Fitness, weights=[1.0] * cache.numGoals)
    creator.create("Individual", array.array, typecode="d", fitness=creator.FitnessMax, strategy=None, mean=None, confidence=None)

    creator.create("FitnessMaxMeta", base.Fitness, weights=[1.0, 1.0, 1.0, -1.0])
    creator.create("IndividualMeta", array.array, typecode="d", fitness=creator.FitnessMaxMeta, strategy=None)
    cache.toolbox.register("individualMeta", util.initIndividual, creator.IndividualMeta, cache)

    cache.toolbox.register("individual", util.generateIndividual, creator.Individual,
        len(cache.MIN_VALUE), cache.MIN_VALUE, cache.MAX_VALUE, cache)
    
    cache.toolbox.register("individual_guess", util.initIndividual, creator.Individual, cache)

    cache.toolbox.register("evaluate", fitness, json_path=cache.json_path)
    cache.toolbox.register("evaluate_grad", grad_fitness, json_path=cache.json_path)
    cache.toolbox.register('grad_search', grad_search)

    cache.toolbox.register('map', map_function)
