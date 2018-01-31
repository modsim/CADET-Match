import util
import pareto
import csv
from pathlib import Path

name = 'ScoreTest'

def run(cache, tools, creator):
    "run the parameter estimation"
    path = Path(cache.settings['resultsDirBase'], cache.settings['CSV'])
    with path.open('a', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quoting=csv.QUOTE_NONE)
        pop = cache.toolbox.population(n=0)

        if "seeds" in cache.settings:
            print(cache.settings['seeds'])
            seed_pop = [cache.toolbox.individual_guess([f(v) for f, v in zip(cache.settings['transform'], sublist)]) for sublist in cache.settings['seeds']]
            pop.extend(seed_pop)
            print(pop)

        hof = pareto.ParetoFront(similar=util.similar)

        invalid_ind = [ind for ind in pop if not ind.fitness.valid]
        util.eval_population(cache.toolbox, cache, invalid_ind, writer, csvfile, hof)

        return hof

def setupDEAP(cache, fitness, map_function, creator, base, tools):
    "setup the DEAP variables"
    creator.create("FitnessMax", base.Fitness, weights=[1.0] * cache.numGoals)
    creator.create("Individual", list, typecode="d", fitness=creator.FitnessMax, strategy=None)

    cache.toolbox.register("individual", util.generateIndividual, creator.Individual,
        len(cache.MIN_VALUE), cache.MIN_VALUE, cache.MAX_VALUE)
    cache.toolbox.register("population", tools.initRepeat, list, cache.toolbox.individual)

    cache.toolbox.register("individual_guess", util.initIndividual, creator.Individual)

    cache.toolbox.register("evaluate", fitness, json_path=cache.json_path)

    cache.toolbox.register('map', map_function)
