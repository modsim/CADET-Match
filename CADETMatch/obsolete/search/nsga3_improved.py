import array
import random

import CADETMatch.checkpoint_algorithms as checkpoint_algorithms
import CADETMatch.nsga3_selection as nsga3_selection
import CADETMatch.pareto as pareto
import CADETMatch.util as util

name = "NSGA3_improved"


def run(cache, tools, creator):
    "run the parameter estimation"
    random.seed()
    parameters = len(cache.MIN_VALUE)

    populationSize = parameters * cache.settings["population"]
    CXPB = cache.settings["crossoverRate"]

    totalGenerations = parameters * cache.settings["generations"]

    pop = cache.toolbox.population(n=populationSize)

    if "seeds" in cache.settings:
        seed_pop = [
            cache.toolbox.individual_guess(
                [f(v) for f, v in zip(cache.settings["transform"], sublist)]
            )
            for sublist in cache.settings["seeds"]
        ]
        pop.extend(seed_pop)
    return checkpoint_algorithms.eaMuPlusLambda(
        pop,
        cache.toolbox,
        mu=populationSize,
        lambda_=populationSize,
        cxpb=CXPB,
        mutpb=cache.settings["mutationRate"],
        ngen=totalGenerations,
        settings=cache.settings,
        tools=tools,
        cache=cache,
    )


def setupDEAP(
    cache, fitness, grad_fitness, grad_search, map_function, creator, base, tools
):
    "setup the DEAP variables"
    creator.create("FitnessMax", base.Fitness, weights=[1.0] * cache.numGoals)
    creator.create(
        "Individual",
        array.array,
        typecode="d",
        fitness=creator.FitnessMax,
        strategy=None,
        mean=None,
        confidence=None,
    )

    creator.create("FitnessMaxMeta", base.Fitness, weights=[1.0, 1.0, 1.0, -1.0])
    creator.create(
        "IndividualMeta",
        array.array,
        typecode="d",
        fitness=creator.FitnessMaxMeta,
        strategy=None,
    )
    cache.toolbox.register(
        "individualMeta", util.initIndividual, creator.IndividualMeta, cache
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
        "mate", util.mutationNSGA3_cross, low=cache.MIN_VALUE, up=cache.MAX_VALUE
    )

    if cache.adaptive:
        cache.toolbox.register(
            "mutate",
            util.mutationNSGA3_mutate,
            low=cache.MIN_VALUE,
            up=cache.MAX_VALUE,
            indpb=1.0 / len(cache.MIN_VALUE),
        )
        cache.toolbox.register(
            "force_mutate",
            util.mutationNSGA3_mutate,
            low=cache.MIN_VALUE,
            up=cache.MAX_VALUE,
            indpb=1.0 / len(cache.MIN_VALUE),
        )
    else:
        cache.toolbox.register(
            "mutate",
            util.mutPolynomialBounded,
            eta=1.0,
            low=cache.MIN_VALUE,
            up=cache.MAX_VALUE,
            indpb=1.0 / len(cache.MIN_VALUE),
        )
        cache.toolbox.register(
            "force_mutate",
            util.mutPolynomialBounded,
            eta=1.0,
            low=cache.MIN_VALUE,
            up=cache.MAX_VALUE,
            indpb=1.0 / len(cache.MIN_VALUE),
        )

    cache.toolbox.register("select", nsga3_selection.sel_nsga_iii)
    cache.toolbox.register("evaluate", fitness, json_path=cache.json_path)
    cache.toolbox.register("evaluate_grad", grad_fitness, json_path=cache.json_path)
    cache.toolbox.register("grad_search", grad_search)

    cache.toolbox.register("map", map_function)
