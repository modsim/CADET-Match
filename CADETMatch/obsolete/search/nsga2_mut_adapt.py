import random

import CADETMatch.checkpoint_algorithms as checkpoint_algorithms
import CADETMatch.util as util

name = "NSGA2_mut_adapt"


def run(cache, tools, creator):
    "run the parameter estimation"
    random.seed()

    parameters = len(cache.MIN_VALUE)

    populationSize = parameters * cache.settings["population"] + len(
        cache.settings.get("seeds", [])
    )

    # populationSize has to be a multiple of 4 so increase to the next multiple of 4
    populationSize += -populationSize % 4

    CXPB = cache.settings["crossoverRate"]

    totalGenerations = parameters * cache.settings["generations"]

    return checkpoint_algorithms.nsga2(populationSize, totalGenerations, cache, tools)


def setupDEAP(
    cache, fitness, grad_fitness, grad_search, map_function, creator, base, tools
):
    "setup the DEAP variables"
    creator.create("FitnessMax", base.Fitness, weights=[1.0] * cache.numGoals)
    creator.create(
        "Individual", list, typecode="d", fitness=creator.FitnessMax, strategy=None
    )

    cache.toolbox.register(
        "individual",
        util.generateIndividual,
        creator.Individual,
        len(cache.MIN_VALUE),
        cache.MIN_VALUE,
        cache.MAX_VALUE,
        cache,
    )

    if cache.sobolGeneration:
        cache.toolbox.register(
            "population", util.sobolGenerator, creator.Individual, cache
        )
    else:
        cache.toolbox.register(
            "population", tools.initRepeat, list, cache.toolbox.individual
        )
    cache.toolbox.register(
        "randomPopulation", tools.initRepeat, list, cache.toolbox.individual
    )

    cache.toolbox.register(
        "individual_guess", util.initIndividual, creator.Individual, cache
    )

    cache.toolbox.register(
        "mate",
        tools.cxSimulatedBinaryBounded,
        eta=5.0,
        low=cache.MIN_VALUE,
        up=cache.MAX_VALUE,
    )

    if cache.adaptive:
        cache.toolbox.register(
            "mutate",
            util.mutPolynomialBoundedAdaptive,
            eta=1.0,
            low=cache.MIN_VALUE,
            up=cache.MAX_VALUE,
            indpb=1.0 / len(cache.MIN_VALUE),
        )
        cache.toolbox.register(
            "force_mutate",
            util.mutPolynomialBoundedAdaptive,
            eta=1.0,
            low=cache.MIN_VALUE,
            up=cache.MAX_VALUE,
            indpb=1.0 / len(cache.MIN_VALUE),
        )
    else:
        cache.toolbox.register(
            "mutate",
            tools.mutPolynomialBounded,
            eta=2.0,
            low=cache.MIN_VALUE,
            up=cache.MAX_VALUE,
            indpb=1.0 / len(cache.MIN_VALUE),
        )
        cache.toolbox.register(
            "force_mutate",
            tools.mutPolynomialBounded,
            eta=2.0,
            low=cache.MIN_VALUE,
            up=cache.MAX_VALUE,
            indpb=1.0 / len(cache.MIN_VALUE),
        )

    cache.toolbox.register("select", tools.selNSGA2)
    cache.toolbox.register("evaluate", fitness, json_path=cache.json_path)
    cache.toolbox.register("evaluate_grad", grad_fitness, json_path=cache.json_path)
    cache.toolbox.register("grad_search", grad_search)

    cache.toolbox.register("map", map_function)
