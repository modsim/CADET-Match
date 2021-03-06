import csv
import multiprocessing
import pickle
import random
import time
from pathlib import Path

import numpy
from deap import algorithms

import CADETMatch.pareto as pareto
import CADETMatch.progress as progress
import CADETMatch.sub as sub
import CADETMatch.util as util

stallRate = 1.25
progressRate = 0.75


def stop_iteration(best, stalled, cache):
    best = util.translate_meta_min(best, cache)
    stopAverage = cache.settings.get("stopAverage", 0.0)
    stopBest = cache.settings.get("stopBest", 0.0)
    stopRMSE = cache.settings.get("stopRMSE", 0.0)
    if best[2] <= stopAverage or best[1] <= stopBest or stalled or best[-1] <= stopRMSE:
        return True
    else:
        return False


def eaMuPlusLambda(
    population,
    toolbox,
    mu,
    lambda_,
    cxpb,
    mutpb,
    ngen,
    settings,
    stats=None,
    verbose=__debug__,
    tools=None,
    cache=None,
):
    """from DEAP function but with checkpoiting"""
    assert lambda_ >= mu, "lambda must be greater or equal to mu."

    checkpointFile = Path(
        settings["resultsDirMisc"], settings.get("checkpointFile", "check")
    )

    sim_start = generation_start = time.time()

    path = Path(cache.settings["resultsDirBase"], cache.settings["csv"])
    result_data = {
        "input": [],
        "output": [],
        "output_meta": [],
        "results": {},
        "times": {},
        "input_transform": [],
        "input_transform_extended": [],
        "strategy": [],
        "mean": [],
        "confidence": [],
    }
    with path.open("a", newline="") as csvfile:
        writer = csv.writer(csvfile, delimiter=",", quoting=csv.QUOTE_ALL)

        if checkpointFile.exists():
            with checkpointFile.open("rb") as cp_file:
                cp = pickle.load(cp_file)
            population = cp["population"]
            start_gen = cp["generation"]

            halloffame = cp["halloffame"]
            meta_hof = cp["meta_halloffame"]
            grad_hof = cp["grad_halloffame"]
            progress_hof = cp["progress_halloffame"]
            random.setstate(cp["rndstate"])
            cache.generationsOfProgress = cp["generationsOfProgress"]
            cache.lastProgressGeneration = cp["lastProgressGeneration"]

            if cp["gradCheck"] > cache.settings.get("gradCheck", 0.0):
                gradCheck = cp["gradCheck"]
            else:
                gradCheck = cache.settings.get("gradCheck", 0.0)
        else:
            # Start a new evolution
            start_gen = 0

            gradCheck = settings.get("gradCheck", 0.0)

            if cache.metaResultsOnly:
                halloffame = pareto.DummyFront()
            else:
                halloffame = pareto.ParetoFront(
                    similar=pareto.similar, similar_fit=pareto.similar_fit(cache)
                )
            meta_hof = pareto.ParetoFrontMeta(
                similar=pareto.similar,
                similar_fit=pareto.similar_fit_meta(cache),
                slice_object=cache.meta_slice,
            )
            grad_hof = pareto.ParetoFront(
                similar=pareto.similar, similar_fit=pareto.similar_fit(cache)
            )
            progress_hof = pareto.ParetoFrontMeta(
                similar=pareto.similar,
                similar_fit=pareto.similar_fit_meta(cache),
                slice_object=cache.meta_slice,
            )

            # Evaluate the individuals with an invalid fitness
            invalid_ind = [ind for ind in population if not ind.fitness.valid]
            if invalid_ind:
                stalled, stallWarn, progressWarn = util.eval_population(
                    toolbox,
                    cache,
                    invalid_ind,
                    writer,
                    csvfile,
                    halloffame,
                    meta_hof,
                    progress_hof,
                    -1,
                    result_data,
                )

                progress.writeProgress(
                    cache,
                    -1,
                    population,
                    halloffame,
                    meta_hof,
                    grad_hof,
                    progress_hof,
                    sim_start,
                    generation_start,
                    result_data,
                )
                sub.graph_process(cache, "First")
                sub.graph_corner_process(cache, last=False)

            cp = dict(
                population=population,
                generation=start_gen,
                halloffame=halloffame,
                rndstate=random.getstate(),
                gradCheck=gradCheck,
                meta_halloffame=meta_hof,
                grad_halloffame=grad_hof,
                generationsOfProgress=cache.generationsOfProgress,
                lastProgressGeneration=cache.lastProgressGeneration,
                progress_halloffame=progress_hof,
            )

            with checkpointFile.open("wb") as cp_file:
                pickle.dump(cp, cp_file)

        gen = start_gen  # this covers the case where the start_gen is higher than our stop gen so the loop never runs
        # Begin the generational process
        for gen in range(start_gen, ngen + 1):
            generation_start = time.time()
            # Vary the population
            offspring = algorithms.varAnd(population, toolbox, cxpb, mutpb)

            # Evaluate the individuals with an invalid fitness
            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            stalled, stallWarn, progressWarn = util.eval_population(
                toolbox,
                cache,
                invalid_ind,
                writer,
                csvfile,
                halloffame,
                meta_hof,
                progress_hof,
                gen,
                result_data,
            )

            gradCheck, newChildren = cache.toolbox.grad_search(
                gradCheck, offspring, cache, writer, csvfile, grad_hof, meta_hof, gen
            )
            offspring.extend(newChildren)

            # Select the next generation population
            population[:] = toolbox.select(offspring + population, mu)

            progress.writeProgress(
                cache,
                gen,
                offspring,
                halloffame,
                meta_hof,
                grad_hof,
                progress_hof,
                sim_start,
                generation_start,
                result_data,
            )
            sub.graph_process(cache, gen)
            sub.graph_corner_process(cache, last=False)

            cp = dict(
                population=population,
                generation=gen,
                halloffame=halloffame,
                rndstate=random.getstate(),
                gradCheck=gradCheck,
                meta_halloffame=meta_hof,
                grad_halloffame=grad_hof,
                generationsOfProgress=cache.generationsOfProgress,
                lastProgressGeneration=cache.lastProgressGeneration,
                progress_halloffame=progress_hof,
            )

            if stallWarn:
                maxPopulation = cache.settings["maxPopulation"] * len(cache.MIN_VALUE)
                newLambda_ = int(lambda_ * stallRate)
                lambda_ = min(newLambda_, maxPopulation)

            if progressWarn:
                minPopulation = cache.settings["minPopulation"] * len(cache.MIN_VALUE)
                newLambda_ = int(lambda_ * progressRate)
                lambda_ = max(newLambda_, minPopulation)

            with checkpointFile.open("wb") as cp_file:
                pickle.dump(cp, cp_file)

            best = meta_hof.getBestScores()

            if stop_iteration(best, stalled, cache):
                break

        if cache.finalGradRefinement:
            gen = gen + 1
            best_individuals = [cache.toolbox.individual_guess(i) for i in meta_hof]
            gradCheck, newChildren = cache.toolbox.grad_search(
                gradCheck,
                best_individuals,
                cache,
                writer,
                csvfile,
                grad_hof,
                meta_hof,
                gen,
                check_all=True,
                result_data=result_data,
            )
            if newChildren:
                progress.writeProgress(
                    cache,
                    gen,
                    newChildren,
                    halloffame,
                    meta_hof,
                    grad_hof,
                    progress_hof,
                    sim_start,
                    generation_start,
                    result_data,
                )

        population = [cache.toolbox.individual_guess(i) for i in meta_hof]
        stalled, stallWarn, progressWarn = util.eval_population_final(
            cache.toolbox,
            cache,
            population,
            writer,
            csvfile,
            halloffame,
            meta_hof,
            progress_hof,
            gen + 1,
            result_data,
        )
        progress.writeProgress(
            cache,
            gen + 1,
            population,
            halloffame,
            meta_hof,
            grad_hof,
            progress_hof,
            sim_start,
            generation_start,
            result_data,
        )

        util.finish(cache)
        sub.graph_corner_process(cache, last=True)
        return halloffame


def nsga2(populationSize, ngen, cache, tools):
    """NSGA2 with checkpointing"""
    # fix max population to be a multiple of 4
    cache.settings["maxPopulation"] = cache.settings["maxPopulation"] + (
        -cache.settings["maxPopulation"] % 4
    )

    cxpb = cache.settings["crossoverRate"]
    checkpointFile = Path(
        cache.settings["resultsDirMisc"], cache.settings.get("checkpointFile", "check")
    )

    path = Path(cache.settings["resultsDirBase"], cache.settings["csv"])
    result_data = {
        "input": [],
        "output": [],
        "output_meta": [],
        "results": {},
        "times": {},
        "input_transform": [],
        "input_transform_extended": [],
        "strategy": [],
        "mean": [],
        "confidence": [],
    }
    with path.open("a", newline="") as csvfile:
        writer = csv.writer(csvfile, delimiter=",", quoting=csv.QUOTE_ALL)

        if checkpointFile.exists():
            with checkpointFile.open("rb") as cp_file:
                cp = pickle.load(cp_file)
            population = cp["population"]
            start_gen = cp["generation"]

            halloffame = cp["halloffame"]
            meta_hof = cp["meta_halloffame"]
            grad_hof = cp["grad_halloffame"]
            progress_hof = cp["progress_halloffame"]
            random.setstate(cp["rndstate"])
            cache.generationsOfProgress = cp["generationsOfProgress"]
            cache.lastProgressGeneration = cp["lastProgressGeneration"]

            if cp["gradCheck"] > cache.settings.get("gradCheck", 0.0):
                gradCheck = cp["gradCheck"]
            else:
                gradCheck = cache.settings.get("gradCheck", 0.0)

        else:
            # Start a new evolution

            population = cache.toolbox.population(n=populationSize)

            if "seeds" in cache.settings:
                seed_pop = [
                    cache.toolbox.individual_guess(
                        [f(v) for f, v in zip(cache.settings["transform"], sublist)]
                    )
                    for sublist in cache.settings["seeds"]
                ]
                population.extend(seed_pop)

            start_gen = 0

            if cache.metaResultsOnly:
                halloffame = pareto.DummyFront()
            else:
                halloffame = pareto.ParetoFront(
                    similar=pareto.similar, similar_fit=pareto.similar_fit(cache)
                )
            meta_hof = pareto.ParetoFrontMeta(
                similar=pareto.similar,
                similar_fit=pareto.similar_fit_meta(cache),
                slice_object=cache.meta_slice,
            )
            grad_hof = pareto.ParetoFront(
                similar=pareto.similar, similar_fit=pareto.similar_fit(cache)
            )
            progress_hof = pareto.ParetoFrontMeta(
                similar=pareto.similar,
                similar_fit=pareto.similar_fit_meta(cache),
                slice_object=cache.meta_slice,
            )
            gradCheck = cache.settings.get("gradCheck", 0.0)

        sim_start = generation_start = time.time()

        # Evaluate the individuals with an invalid fitness
        invalid_ind = [ind for ind in population if not ind.fitness.valid]
        if invalid_ind:
            stalled, stallWarn, progressWarn = util.eval_population(
                cache.toolbox,
                cache,
                invalid_ind,
                writer,
                csvfile,
                halloffame,
                meta_hof,
                progress_hof,
                -1,
                result_data,
            )

            progress.writeProgress(
                cache,
                -1,
                population,
                halloffame,
                meta_hof,
                grad_hof,
                progress_hof,
                sim_start,
                generation_start,
                result_data,
            )
            sub.graph_process(cache, "First")
            sub.graph_corner_process(cache, last=False)

        # This is just to assign the crowding distance to the individuals
        # no actual selection is done
        population = cache.toolbox.select(population, len(population))

        cp = dict(
            population=population,
            generation=start_gen,
            halloffame=halloffame,
            rndstate=random.getstate(),
            gradCheck=gradCheck,
            meta_halloffame=meta_hof,
            grad_halloffame=grad_hof,
            generationsOfProgress=cache.generationsOfProgress,
            lastProgressGeneration=cache.lastProgressGeneration,
            progress_halloffame=progress_hof,
        )

        with checkpointFile.open("wb") as cp_file:
            pickle.dump(cp, cp_file)

        # Begin the generational process
        for gen in range(start_gen, ngen + 1):
            generation_start = time.time()
            # Vary the population
            offspring = tools.selTournamentDCD(population, len(population))
            offspring = [cache.toolbox.clone(ind) for ind in offspring]

            for ind1, ind2 in zip(offspring[::2], offspring[1::2]):
                if random.random() <= cxpb:
                    cache.toolbox.mate(ind1, ind2)

                cache.toolbox.mutate(ind1)
                cache.toolbox.mutate(ind2)
                del ind1.fitness.values, ind2.fitness.values

            # Evaluate the individuals with an invalid fitness
            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            stalled, stallWarn, progressWarn = util.eval_population(
                cache.toolbox,
                cache,
                invalid_ind,
                writer,
                csvfile,
                halloffame,
                meta_hof,
                progress_hof,
                gen,
                result_data,
            )

            gradCheck, newChildren = cache.toolbox.grad_search(
                gradCheck, offspring, cache, writer, csvfile, grad_hof, meta_hof, gen
            )
            offspring.extend(newChildren)

            progress.writeProgress(
                cache,
                gen,
                offspring,
                halloffame,
                meta_hof,
                grad_hof,
                progress_hof,
                sim_start,
                generation_start,
                result_data,
            )
            sub.graph_process(cache, gen)
            sub.graph_corner_process(cache, last=False)

            # Select the next generation population
            population = cache.toolbox.select(population + offspring, populationSize)

            if stallWarn:
                maxPopulation = cache.settings["maxPopulation"] * len(cache.MIN_VALUE)
                newPopulationSize = int(populationSize * stallRate)
                newPopulationSize += -newPopulationSize % 4
                newPopulationSize = min(newPopulationSize, maxPopulation)
                newPopulationSize += -newPopulationSize % 4

                diffSize = newPopulationSize - populationSize
                newPopulation = cache.toolbox.randomPopulation(n=diffSize)

                invalid_ind = [ind for ind in newPopulation if not ind.fitness.valid]
                util.eval_population(
                    cache.toolbox,
                    cache,
                    invalid_ind,
                    writer,
                    csvfile,
                    halloffame,
                    meta_hof,
                    progress_hof,
                    gen,
                    result_data,
                )

                # This is just to assign the crowding distance to the individuals
                # no actual selection is done
                newPopulation = cache.toolbox.select(newPopulation, len(newPopulation))

                population.extend(newPopulation)
                populationSize = newPopulationSize

            if progressWarn:
                minPopulation = cache.settings["minPopulation"] * len(cache.MIN_VALUE)
                newPopulationSize = int(populationSize * progressRate)
                newPopulationSize += -newPopulationSize % 4
                newPopulationSize = max(newPopulationSize, minPopulation)
                newPopulationSize += -newPopulationSize % 4

                diffSize = populationSize - newPopulationSize

                population = cache.toolbox.select(population, newPopulationSize)
                populationSize = newPopulationSize

            cp = dict(
                population=population,
                generation=gen,
                halloffame=halloffame,
                rndstate=random.getstate(),
                gradCheck=gradCheck,
                meta_halloffame=meta_hof,
                grad_halloffame=grad_hof,
                generationsOfProgress=cache.generationsOfProgress,
                lastProgressGeneration=cache.lastProgressGeneration,
                progress_halloffame=progress_hof,
            )

            hof = Path(cache.settings["resultsDirMisc"], "hof")
            with hof.open("wb") as data:
                numpy.savetxt(data, numpy.array(halloffame))
            with checkpointFile.open("wb") as cp_file:
                pickle.dump(cp, cp_file)

            best = meta_hof.getBestScores()

            if stop_iteration(best, stalled, cache):
                util.finish(cache)
                sub.graph_corner_process(cache, last=True)
                return halloffame

        util.finish(cache)
        sub.graph_corner_process(cache, last=True)
        return halloffame
