import array
import csv
import multiprocessing
import pickle
import random
import sys
import time
from pathlib import Path

import cadet
import emcee
import emcee.autocorr as autocorr
import numpy
import numpy as np
import pandas
import SALib.sample.sobol_sequence
import scipy
import scipy.spatial
from sklearn.cluster import KMeans

import CADETMatch.cache as cache
import CADETMatch.evo as evo
import CADETMatch.kde_generator as kde_generator
import CADETMatch.pareto as pareto
import CADETMatch.progress as progress
import CADETMatch.util as util
import CADETMatch.sub as sub
import CADETMatch.pop as pop
import arviz

name = "MCMC"

import shutil

import joblib
import jstyleson
from addict import Dict

import CADETMatch.de as de
import CADETMatch.de_snooker as de_snooker
import CADETMatch.stretch as stretch

min_acceptance = 0.05
acceptance_delta = 0.02


def log_previous(cadetValues, kde_previous, kde_previous_scaler):
    # find the right values to use
    col = len(kde_previous_scaler.scale_)
    values = cadetValues[-col:]
    values_shape = numpy.array(values).reshape(1, -1)
    values_scaler = kde_previous_scaler.transform(values_shape)
    score = kde_previous.score_samples(values_scaler)
    return score


def log_likelihood(individual, json_path):
    if json_path != cache.cache.json_path:
        cache.cache.setup_dir(json_path)
        util.setupLog(cache.cache.settings["resultsDirLog"], "main.log")
        cache.cache.setup(json_path, False)

    if "kde_previous" not in log_likelihood.__dict__:
        kde_previous, kde_previous_scaler = kde_generator.getKDEPrevious(cache.cache)
        log_likelihood.kde_previous = kde_previous
        log_likelihood.kde_previous_scaler = kde_previous_scaler

    if "kde" not in log_likelihood.__dict__:
        kde, kde_scaler = kde_generator.getKDE(cache.cache)
        log_likelihood.kde = kde
        log_likelihood.scaler = kde_scaler

    scores, csv_record, meta_score, results, individual = evo.fitness(
        individual, json_path
    )

    if results is None:
        multiprocessing.get_logger().info(
            "log_likelihood results is None %s (%s)",
            individual,
            util.convert_individual_inputorder(individual, cache.cache),
        )
        return -numpy.inf, scores, csv_record, meta_score, results, individual

    if results is not None and log_likelihood.kde_previous is not None:
        logPrevious = log_previous(
            individual, log_likelihood.kde_previous, log_likelihood.kde_previous_scaler
        )
    else:
        logPrevious = 0.0

    scores_shape = numpy.array(scores)
    scores_shape = scores_shape.reshape(1, -1)

    score_scaler = log_likelihood.scaler.transform(scores_shape)

    score_kde = log_likelihood.kde.score_samples(score_scaler)

    score = score_kde + logPrevious

    return score, scores, csv_record, meta_score, results, individual


def log_posterior_vectorize(
    population,
    json_path,
    cache,
    halloffame,
    meta_hof,
    grad_hof,
    progress_hof,
    result_data,
    writer,
    csvfile,
):
    results = cache.map_function(
        log_posterior, ((population[i], json_path) for i in range(len(population)))
    )
    results = process(
        population,
        cache,
        halloffame,
        meta_hof,
        grad_hof,
        progress_hof,
        result_data,
        results,
        writer,
        csvfile,
    )
    return results


def outside_bounds(x, cache):
    for i, lb, ub in zip(x, cache.MIN_VALUE, cache.MAX_VALUE):
        if i < lb or i > ub:
            return True
    return False


def log_posterior(x):
    theta, json_path = x
    if json_path != cache.cache.json_path:
        cache.cache.setup_dir(json_path)
        util.setupLog(cache.cache.settings["resultsDirLog"], "main.log")
        cache.cache.setup(json_path)

    if outside_bounds(theta, cache.cache):
        multiprocessing.get_logger().info(
            "individual is outside of range %s (%s)",
            theta,
            util.convert_individual_inputorder(theta, cache.cache),
        )
        return (
            -numpy.inf,
            theta,
            cache.cache.WORST,
            [],
            cache.cache.WORST_META,
            None,
            theta,
        )

    ll, scores, csv_record, meta_score, results, individual = log_likelihood(
        theta, json_path
    )

    if results is None:
        multiprocessing.get_logger().info(
            "log_posterior results is None %s (%s)",
            theta,
            util.convert_individual_inputorder(theta, cache.cache),
        )
        return (
            -numpy.inf,
            theta,
            cache.cache.WORST,
            [],
            cache.cache.WORST_META,
            None,
            individual,
        )
    else:
        return ll, theta, scores, csv_record, meta_score, results, individual


def addChain(*args):
    temp = [arg for arg in args if arg is not None]
    if len(temp) > 1:
        return numpy.concatenate(temp, axis=1)
    else:
        return numpy.array(temp[0])


def converged_bounds(chain, length, error_level):
    if chain.shape[1] < (2 * length):
        return False, None, None, None
    lb = []
    ub = []
    mid = []

    start = chain.shape[1] - length
    stop = chain.shape[1]
    for i in range(start, stop):
        temp_chain = chain[:, :i, :]
        temp_chain_shape = temp_chain.shape
        temp_chain_flat = temp_chain.reshape(
            temp_chain_shape[0] * temp_chain_shape[1], temp_chain_shape[2]
        )
        hdi = arviz.hdi(temp_chain, hdi_prob=0.9)
        lb_5 = hdi[:,0]
        ub_95 = hdi[:,1]
        mid_50 = numpy.mean(temp_chain_flat, axis=0)

        lb.append(lb_5)
        ub.append(ub_95)
        mid.append(mid_50)

    lb = numpy.array(lb)
    ub = numpy.array(ub)
    mid = numpy.array(mid)

    if numpy.all(numpy.std(lb, axis=0) < error_level) and numpy.all(
        numpy.std(ub, axis=0) < error_level
    ):
        return (
            True,
            numpy.mean(lb, axis=0),
            numpy.mean(mid, axis=0),
            numpy.mean(ub, axis=0),
        )
    else:
        multiprocessing.get_logger().info(
            "bounds have not yet converged lb min: %s max: %s std: %s  ub min %s max: %s std: %s",
            numpy.array2string(numpy.min(lb, axis=0), precision=3, separator=","),
            numpy.array2string(numpy.max(lb, axis=0), precision=3, separator=","),
            numpy.array2string(numpy.std(lb, axis=0), precision=4, separator=","),
            numpy.array2string(numpy.min(ub, axis=0), precision=3, separator=","),
            numpy.array2string(numpy.max(ub, axis=0), precision=3, separator=","),
            numpy.array2string(numpy.std(ub, axis=0), precision=4, separator=","),
        )
        return False, None, None, None


def rescale(cache, lb, mid, ub, old_lb, old_ub, mcmc_store):
    "give a new lb and ub that will rescale so that the previous lb and ub takes up about 1/2 of the search width"
    new_size = len(lb)
    old_lb_slice = old_lb[:new_size]
    old_ub_slice = old_ub[:new_size]

    center = mid
    old_center = (old_ub + old_lb) / 2.0

    new_lb = lb - 2 * (center - lb)

    new_lb = numpy.max([new_lb, old_lb_slice], axis=0)

    new_ub = ub + 2 * (ub - center)

    new_ub = numpy.min([new_ub, old_ub_slice], axis=0)

    lb_trans = numpy.ones([3, len(old_lb)]) * old_lb
    ub_trans = numpy.ones([3, len(old_ub)]) * old_ub
    center_trans = numpy.ones([3, len(old_ub)]) * old_center

    lb_trans[1, :new_size] = lb
    lb_trans[2, :new_size] = new_lb

    ub_trans[1, :new_size] = ub
    ub_trans[2, :new_size] = new_ub

    center_trans[1, :new_size] = center
    center_trans[2, :new_size] = center

    lb_trans_conv = util.convert_population_inputorder(lb_trans, cache)
    center_trans_conv = util.convert_population_inputorder(center_trans, cache)
    ub_trans_conv = util.convert_population_inputorder(ub_trans, cache)

    mcmc_store.root.bounds_change.lb_trans = lb_trans
    mcmc_store.root.bounds_change.ub_trans = ub_trans
    mcmc_store.root.bounds_change.center_trans = center_trans
    mcmc_store.root.bounds_change.lb_trans_conv = lb_trans_conv
    mcmc_store.root.bounds_change.center_trans_conv = center_trans_conv
    mcmc_store.root.bounds_change.ub_trans_conv = ub_trans_conv

    multiprocessing.get_logger().info(
        """rescaling bounds (simulator space)  \nold_lb: %s \nold_center: %s \nold_ub: %s
    \nlb5: %s \ncenter: %s \nub5: %s
    \nnew_lb: %s \nnew_center: %s \nnew_ub: %s
    \nbounds (search space)
    \nold_lb: %s \nold_center: %s \nold_ub: %s
    \nlb5: %s \ncenter: %s \nub5: %s
    \nnew_lb: %s \nnew_center: %s \nnew_ub: %s""",
        numpy.array2string(lb_trans_conv[0], precision=3, separator=","),
        numpy.array2string(center_trans_conv[0], precision=3, separator=","),
        numpy.array2string(ub_trans_conv[0], precision=3, separator=","),
        numpy.array2string(lb_trans_conv[1], precision=3, separator=","),
        numpy.array2string(center_trans_conv[1], precision=3, separator=","),
        numpy.array2string(ub_trans_conv[1], precision=3, separator=","),
        numpy.array2string(lb_trans_conv[2], precision=3, separator=","),
        numpy.array2string(center_trans_conv[2], precision=3, separator=","),
        numpy.array2string(ub_trans_conv[2], precision=3, separator=","),
        numpy.array2string(lb_trans[0], precision=3, separator=","),
        numpy.array2string(center_trans[0], precision=3, separator=","),
        numpy.array2string(ub_trans[0], precision=3, separator=","),
        numpy.array2string(lb_trans[1], precision=3, separator=","),
        numpy.array2string(center_trans[1], precision=3, separator=","),
        numpy.array2string(ub_trans[1], precision=3, separator=","),
        numpy.array2string(lb_trans[2], precision=3, separator=","),
        numpy.array2string(center_trans[2], precision=3, separator=","),
        numpy.array2string(ub_trans[2], precision=3, separator=","),
    )

    return lb_trans[2], center_trans[2], ub_trans[2]


def flatten(chain):
    chain_shape = chain.shape
    flat_chain = chain.reshape(chain_shape[0] * chain_shape[1], chain_shape[2])
    return flat_chain


def change_bounds_json(cache, lb, ub, mcmc_store):
    "change the bounds based on lb and ub and then save it as a new json file and return the path to the new file"
    multiprocessing.get_logger().info("change_bounds_json  lb %s  ub %s", lb, ub)
    lb_trans = util.convert_individual_inputorder(lb, cache)
    ub_trans = util.convert_individual_inputorder(ub, cache)

    settings_file = Path(cache.json_path)
    settings_file_backup = settings_file.with_suffix(".json.backup")

    new_name = "%s_bounds%s" % (settings_file.stem, settings_file.suffix)

    new_settings_file = settings_file.with_name(new_name)

    with settings_file.open() as json_data:
        settings = jstyleson.load(json_data)

        idx = 0
        for parameter in settings["parameters"]:
            transform = cache.transforms[parameter["transform"]](parameter, cache)
            count = transform.count
            if count:
                multiprocessing.get_logger().warn("%s %s %s", idx, count, transform)
                lb_local = lb_trans[idx : idx + count]
                ub_local = ub_trans[idx : idx + count]
                transform.setBounds(parameter, lb_local, ub_local)
                idx = idx + count

        with new_settings_file.open(mode="w") as json_data:
            jstyleson.dump(settings, json_data, indent=4, sort_keys=False)

        mcmc_store.root.bounds_change.json = jstyleson.dumps(
            settings["parameters"], sort_keys=False
        )

    # copy the original file to a backup name
    shutil.copy(settings_file, settings_file_backup)

    # copy over our new settings file to the original file also
    # this is so that external programs also see the new bounds
    with settings_file.open(mode="w") as json_data:
        jstyleson.dump(settings, json_data, indent=4, sort_keys=False)

    return new_settings_file.as_posix()


def process_sampler_auto_bounds_write(cache, mcmc_store):
    bounds_seq = mcmc_store.root.bounds_acceptance
    bounds_chain = mcmc_store.root.bounds_full_chain

    (
        bounds_chain,
        bounds_chain_flat,
        bounds_chain_transform,
        bounds_chain_flat_transform,
    ) = process_chain(bounds_chain, cache, len(bounds_seq) - 1)

    mcmc_store.root.bounds_full_chain_transform = bounds_chain_transform
    mcmc_store.root.bounds_flat_chain = bounds_chain_flat
    mcmc_store.root.bounds_flat_chain_transform = bounds_chain_flat_transform


def select_best_kmeans(chain, probability):
    chain_shape = chain.shape
    flat_chain = chain.reshape(chain_shape[0] * chain_shape[1], chain_shape[2])
    flat_probability = numpy.squeeze(probability.reshape(-1, 1))

    # unique
    flat_chain_unique, unique_indexes = numpy.unique(
        flat_chain, return_index=True, axis=0
    )
    flat_probability_unique = flat_probability[unique_indexes]

    # remove low probability
    flat_prob = numpy.exp(flat_probability_unique)
    max_prob = numpy.max(flat_prob)
    min_prob = max_prob / 10  # 10% of max prob cutoff

    selected = (flat_prob >= min_prob) & (flat_prob <= max_prob)

    flat_chain = flat_chain_unique[selected]
    flat_probability = flat_probability_unique[selected]

    if len(flat_chain) > (2 * chain_shape[0]):
        # kmeans clustering
        km = KMeans(chain_shape[0])
        km.fit(flat_chain)

        dist = scipy.spatial.distance.cdist(flat_chain, km.cluster_centers_)

        idx_closest = numpy.argmin(dist, 0)

        closest = dist[idx_closest, range(chain_shape[0])]

        best_chain = flat_chain[idx_closest]
        best_prob = flat_probability[idx_closest]
    else:
        pop_size = chain.shape[0]
        sort_idx = numpy.argsort(flat_probability_unique)
        sort_idx = sort_idx[numpy.isfinite(sort_idx)]

        best = sort_idx[-pop_size:]

        best_chain = flat_chain_unique[best, :]
        best_prob = flat_probability_unique[best]

    return best_chain, best_prob


def auto_high_probability(cache, checkpoint, sampler, iterations=100):
    auto_chain = None
    auto_probability = None

    pop_size = checkpoint["populationSize"]

    finished = None
    prev_prob = -1e308

    while not finished:
        chain, probability = auto_high_probability_iterations(
            cache, checkpoint, sampler, iterations
        )

        # store chain
        auto_chain = addChain(auto_chain, chain)
        auto_probability = addChain(auto_probability, probability)

        best_chain, best_prob = select_best_kmeans(auto_chain, auto_probability)

        multiprocessing.get_logger().info("best_chain %s", best_chain)
        multiprocessing.get_logger().info("best_prob %s", best_prob)

        checkpoint["p_bounds"] = best_chain
        checkpoint["ln_prob_bounds"] = best_prob
        checkpoint["rstate_bounds"] = None

        best_prob = numpy.max(best_prob)
        
        change = numpy.abs(best_prob - prev_prob)/numpy.abs(prev_prob)
        
        if change < 0.01:
            finished=True
        else:
            print(f"Auto high probability has not converged yet, change {change} > 0.01")
            prev_prob = best_prob

    return auto_chain, auto_probability


def auto_high_probability_iterations(cache, checkpoint, sampler, iterations):
    auto_chain = None
    auto_probability = None
    best = -numpy.inf

    for i in range(iterations):
        state = next(
            sampler.sample(
                checkpoint["p_bounds"],
                log_prob0=checkpoint["ln_prob_bounds"],
                rstate0=checkpoint["rstate_bounds"],
                iterations=1,
            )
        )

        p = state.coords
        ln_prob = state.log_prob
        random_state = state.random_state

        if any(ln_prob > best):
            best = numpy.max(ln_prob)

        accept = numpy.mean(sampler.acceptance_fraction)

        auto_chain = addChain(auto_chain, p[:, numpy.newaxis, :])
        auto_probability = addChain(auto_probability, ln_prob[:, numpy.newaxis])

        multiprocessing.get_logger().info(
            "auto run: idx: %s accept: %.3f max ln(prob): %.3f", i, accept, best
        )

        checkpoint["p_bounds"] = p
        checkpoint["ln_prob_bounds"] = ln_prob
        checkpoint["rstate_bounds"] = random_state

    sampler.reset()
    return auto_chain, auto_probability

def sampler_auto_bounds(cache, checkpoint, sampler, checkpointFile, mcmc_store):
    bounds_seq = checkpoint.get("bounds_seq", [])

    bounds_chain = checkpoint.get("bounds_chain", None)
    bounds_probability = checkpoint.get("bounds_probability", None)

    checkInterval = 25

    parameters = len(cache.MIN_VALUE)

    if "mcmc_h5" in cache.settings:
        data = cadet.H5()
        data.filename = cache.settings["mcmc_h5"]
        data.load(paths=["/bounds_change/center_trans"], lock=True)
        previous_parameters = data.root.bounds_change.center_trans.shape[1]
    else:
        previous_parameters = 0

    new_parameters = parameters - previous_parameters

    finished = False

    generation = checkpoint["idx_bounds"]

    sampler.iterations = checkpoint["sampler_iterations"]
    sampler.naccepted = checkpoint["sampler_naccepted"]

    auto_chain, auto_probability = auto_high_probability(
        cache, checkpoint, sampler, iterations=100
    )

    mcmc_store.root.bounds.auto_chain = auto_chain
    mcmc_store.root.bounds.auto_probability = auto_probability

    mcmc_store.save(lock=True)

    while not finished:
        state = next(
            sampler.sample(
                checkpoint["p_bounds"],
                log_prob0=checkpoint["ln_prob_bounds"],
                rstate0=checkpoint["rstate_bounds"],
                iterations=1,
            )
        )

        p = state.coords
        ln_prob = state.log_prob
        random_state = state.random_state

        accept = numpy.mean(sampler.acceptance_fraction)
        bounds_seq.append(accept)

        bounds_chain = addChain(bounds_chain, p[:, numpy.newaxis, :])
        bounds_probability = addChain(bounds_probability, ln_prob[:, numpy.newaxis])

        multiprocessing.get_logger().info(
            "run:  idx: %s accept: %.3f", generation, accept
        )

        generation += 1

        checkpoint["p_bounds"] = p
        checkpoint["ln_prob_bounds"] = ln_prob
        checkpoint["rstate_bounds"] = random_state
        checkpoint["idx_bounds"] = generation
        checkpoint["bounds_chain"] = bounds_chain
        checkpoint["bounds_probability"] = bounds_probability
        checkpoint["bounds_seq"] = bounds_seq
        checkpoint["bounds_iterations"] = sampler.iterations
        checkpoint["bounds_naccepted"] = sampler.naccepted

        mcmc_store.root.bounds_acceptance = numpy.array(bounds_seq).reshape(-1, 1)
        mcmc_store.root.bounds_full_chain = bounds_chain
        mcmc_store.root.bounds_probability = bounds_probability
        mcmc_store.root.bounds_probability_flat = bounds_probability.reshape(-1, 1)

        write_interval(
            cache.checkpointInterval,
            cache,
            checkpoint,
            checkpointFile,
            mcmc_store,
            process_sampler_auto_bounds_write,
        )
        sub.graph_corner_process(cache, last=False)

        if generation % checkInterval == 0:
            converged, lb, mid, ub = converged_bounds(
                bounds_chain[:, :, :new_parameters], 200, 1e-3
            )

            if converged:
                finished = True

                write_interval(
                    -1,
                    cache,
                    checkpoint,
                    checkpointFile,
                    mcmc_store,
                    process_sampler_auto_bounds_write,
                )

                new_min_value, center, new_max_value = rescale(
                    cache,
                    lb,
                    mid,
                    ub,
                    numpy.array(cache.MIN_VALUE),
                    numpy.array(cache.MAX_VALUE),
                    mcmc_store,
                )

                p_chain, ln_prob = select_best_kmeans(bounds_chain, bounds_probability)

                p_chain_trans = util.convert_population_inputorder(p_chain, cache)

                multiprocessing.get_logger().info(
                    "before bounds conversion %s", p_chain_trans
                )
                multiprocessing.get_logger().info(
                    "before bounds conversion p_chain %s", p_chain
                )

                json_path = change_bounds_json(
                    cache, new_min_value, new_max_value, mcmc_store
                )
                cache.resetTransform(json_path)
                sampler.log_prob_fn.args[0] = json_path
                sampler.log_prob_fn.args[1] = cache

                p_chain = numpy.array(
                    [util.convert_individual_inverse(i, cache) for i in p_chain_trans]
                )

                p_chain_trans = util.convert_population_inputorder(p_chain, cache)

                multiprocessing.get_logger().info(
                    "after bounds conversion %s", p_chain_trans
                )
                multiprocessing.get_logger().info(
                    "after bounds conversion p_chain %s", p_chain
                )

                checkpoint["state"] = "chain"
                checkpoint["p_chain"] = p_chain
                checkpoint["ln_prob_chain"] = ln_prob
                checkpoint["rstate_chain"] = None
                checkpoint["starting_population"] = p_chain

                write_checkpoint(-1, checkpoint, checkpointFile)

                sampler.reset()
            else:
                multiprocessing.get_logger().info(
                    "bounds have not yet converged in gen %s", generation
                )


def process_interval(cache, mcmc_store, interval_chain, interval_chain_transform):
    hdi = arviz.hdi(interval_chain_transform, hdi_prob=0.9)
    lb_5 = hdi[:,0]
    ub_95 = hdi[:,1]
    mid_50 = numpy.mean(flatten(interval_chain_transform), axis=0)

    hdi_stat = numpy.vstack([lb_5, mid_50, ub_95])[:, numpy.newaxis, :]

    mcmc_store.root.percentile["mean"] = mid_50
    mcmc_store.root.percentile["lb_hdi_90"] = lb_5
    mcmc_store.root.percentile["ub_hdi_90"] = ub_95

    flat_interval = interval(interval_chain, cache)
    flat_interval_transform = interval(interval_chain_transform, cache)

    mcmcDir = Path(cache.settings["resultsDirMCMC"])
    flat_interval.to_csv(mcmcDir / "percentile.csv")
    flat_interval_transform.to_csv(mcmcDir / "percentile_transform.csv")


def process_sampler_burn_write(cache, mcmc_store):
    train_chain = mcmc_store.root.train_full_chain
    burn_seq = mcmc_store.root.burn_seq
    train_chain_stat = mcmc_store.root.train_chain_stat

    (
        train_chain,
        train_chain_flat,
        train_chain_transform,
        train_chain_flat_transform,
    ) = process_chain(train_chain, cache, len(burn_seq) - 1)

    mcmc_store.root.train_full_chain_transform = train_chain_transform
    mcmc_store.root.train_flat_chain = train_chain_flat
    mcmc_store.root.train_flat_chain_transform = train_chain_flat_transform

    train_chain_stat, _, train_chain_stat_transform, _ = process_chain(
        train_chain_stat, cache, len(burn_seq) - 1
    )

    mcmc_store.root.train_chain_stat_transform = train_chain_stat_transform

def process_sampler_run_write(cache, mcmc_store):
    chain = mcmc_store.root.full_chain
    chain_seq = mcmc_store.root.mcmc_acceptance
    run_chain_stat = mcmc_store.root.run_chain_stat

    chain, chain_flat, chain_transform, chain_flat_transform = process_chain(
        chain, cache, len(chain_seq) - 1
    )

    mcmc_store.root.full_chain_transform = chain_transform
    mcmc_store.root.flat_chain = chain_flat
    mcmc_store.root.flat_chain_transform = chain_flat_transform

    run_chain_stat, _, run_chain_stat_transform, _ = process_chain(
        run_chain_stat, cache, len(chain_seq) - 1
    )

    mcmc_store.root.run_chain_stat_transform = run_chain_stat_transform

    interval_chain = chain_flat
    interval_chain_transform = chain_flat_transform
    process_interval(cache, mcmc_store, chain, chain_transform)


def sampler_run(cache, checkpoint, sampler, checkpointFile, mcmc_store):
    chain_seq = checkpoint.get("chain_seq", [])

    run_chain = checkpoint.get("run_chain", None)
    run_probability = checkpoint.get("run_probability", None)

    run_chain_stat = checkpoint.get("run_chain_stat", None)

    iat = checkpoint.get("integrated_autocorrelation_time", [])

    checkInterval = 25

    parameters = len(cache.MIN_VALUE)

    finished = False

    generation = checkpoint["idx_chain"]

    sampler.iterations = checkpoint["sampler_iterations"]
    sampler.naccepted = checkpoint["sampler_naccepted"]
    tau_percent = None

    while not finished:
        state = next(
            sampler.sample(
                checkpoint["p_chain"],
                log_prob0=checkpoint["ln_prob_chain"],
                rstate0=checkpoint["rstate_chain"],
                iterations=1,
            )
        )

        p = state.coords
        ln_prob = state.log_prob
        random_state = state.random_state

        accept = numpy.mean(sampler.acceptance_fraction)
        chain_seq.append(accept)

        run_chain = addChain(run_chain, p[:, numpy.newaxis, :])
        run_probability = addChain(run_probability, ln_prob[:, numpy.newaxis])

        hdi = arviz.hdi(run_chain, hdi_prob=0.9)
        lb_5 = hdi[:,0]
        ub_95 = hdi[:,1]
        mid_50 = numpy.mean(flatten(run_chain), axis=0)

        hdi_stat = numpy.vstack([lb_5, mid_50, ub_95])[:, numpy.newaxis, :]

        run_chain_stat = addChain(
            run_chain_stat,
            hdi_stat,
        )

        multiprocessing.get_logger().info(
            "run:  idx: %s accept: %.3f", generation, accept
        )

        generation += 1

        checkpoint["p_chain"] = p
        checkpoint["ln_prob_chain"] = ln_prob
        checkpoint["rstate_chain"] = random_state
        checkpoint["idx_chain"] = generation
        checkpoint["run_chain"] = run_chain
        checkpoint["run_probability"] = run_probability
        checkpoint["chain_seq"] = chain_seq
        checkpoint["sampler_iterations"] = sampler.iterations
        checkpoint["sampler_naccepted"] = sampler.naccepted
        checkpoint["run_chain_stat"] = run_chain_stat

        mcmc_store.root.full_chain = run_chain
        mcmc_store.root.mcmc_acceptance = numpy.array(chain_seq).reshape(-1, 1)
        mcmc_store.root.run_chain_stat = run_chain_stat
        mcmc_store.root.run_probability = run_probability
        mcmc_store.root.run_probability_flat = run_probability.reshape(-1, 1)

        if generation % checkInterval == 0:
            try:
                tau = autocorr.integrated_time(
                    numpy.swapaxes(run_chain, 0, 1), tol=cache.MCMCTauMult +2   #the first two auto-correlation times will be discard as burn-in
                )
                multiprocessing.get_logger().info(
                    "Mean acceptance fraction: %s %0.3f tau: %s with shape: %s",
                    generation,
                    accept,
                    tau,
                    run_chain.shape,
                )
                if numpy.any(numpy.isnan(tau)):
                    multiprocessing.get_logger().info(
                        "tau is NaN and clearly not complete %s", generation
                    )
                else:
                    multiprocessing.get_logger().info(
                        "we have run long enough and can quit %s", generation
                    )
                    finished = True
            except autocorr.AutocorrError as err:
                multiprocessing.get_logger().info(str(err))
                tau = err.tau
            multiprocessing.get_logger().info(
                "Mean acceptance fraction: %s %0.3f tau: %s", generation, accept, tau
            )

            temp_iat = [generation]
            temp_iat.extend(tau)
            iat.append(temp_iat)
            checkpoint["integrated_autocorrelation_time"] = iat

            mcmc_store.root.integrated_autocorrelation_time = numpy.array(iat)

            tau = numpy.array(tau)
            tau_percent = generation / (tau * cache.MCMCTauMult)

            mcmc_store.root.tau_percent = tau_percent.reshape(-1, 1)

        write_interval(
            cache.checkpointInterval,
            cache,
            checkpoint,
            checkpointFile,
            mcmc_store,
            process_sampler_run_write,
        )
        sub.mle_process(cache, last=False)
        sub.graph_corner_process(cache, last=False)

    #need to remove the first two IAT from the results before final storage

    burn = int(numpy.ceil(numpy.max(tau)) * 2)

    checkpoint["p_chain"] = p
    checkpoint["ln_prob_chain"] = ln_prob
    checkpoint["rstate_chain"] = random_state
    checkpoint["idx_chain"] = generation
    checkpoint["run_chain"] = run_chain[:,burn:,:]
    checkpoint["run_probability"] = run_probability[:,burn:]
    checkpoint["chain_seq"] = chain_seq[burn:]


    mcmc_store.root.full_chain = mcmc_store.root.full_chain[:, burn:, :]
    mcmc_store.root.mcmc_acceptance = mcmc_store.root.mcmc_acceptance[burn:]
    mcmc_store.root.run_chain_stat = mcmc_store.root.run_chain_stat[:, burn:, :]
    mcmc_store.root.run_probability = mcmc_store.root.run_probability[:,burn:]
    mcmc_store.root.run_probability_flat = mcmc_store.root.run_probability.reshape(-1, 1)

    mcmc_store.root.train_full_chain = mcmc_store.root.full_chain[:, :burn, :]
    mcmc_store.root.burn_seq = mcmc_store.root.mcmc_acceptance[:burn]
    mcmc_store.root.train_chain_stat = mcmc_store.root.run_chain_stat[:, :burn, :]
    mcmc_store.root.train_probability = mcmc_store.root.run_probability[:,:burn]
    mcmc_store.root.train_probability_flat = mcmc_store.root.train_probability

    process_sampler_burn_write(cache, mcmc_store)

    checkpoint["state"] = "complete"

    write_interval(
        -1, cache, checkpoint, checkpointFile, mcmc_store, process_sampler_run_write
    )


def write_checkpoint(interval, checkpoint, checkpointFile):
    "write the checkpoint and mcmc data at most every n seconds"
    if "last_time" not in write_checkpoint.__dict__:
        write_checkpoint.last_time = time.time()

    if time.time() - write_checkpoint.last_time > interval:
        with checkpointFile.open("wb") as cp_file:
            pickle.dump(checkpoint, cp_file)

        write_checkpoint.last_time = time.time()


def write_interval(
    interval, cache, checkpoint, checkpointFile, mcmc_store, process_mcmc_store
):
    "write the checkpoint and mcmc data at most every n seconds"
    if "last_time" not in write_interval.__dict__:
        write_interval.last_time = time.time()

    write_checkpoint(interval, checkpoint, checkpointFile)

    if time.time() - write_interval.last_time > interval:
        writeMCMC(cache, mcmc_store, process_mcmc_store)

        write_interval.last_time = time.time()


def run(cache):
    "run the parameter estimation"
    random.seed()
    checkpointFile = Path(
        cache.settings["resultsDirMisc"], cache.settings.get("checkpointFile", "check")
    )
    checkpoint = getCheckPoint(checkpointFile, cache)

    mcmcDir = Path(cache.settings["resultsDirMCMC"])
    mcmc_h5 = mcmcDir / "mcmc.h5"
    mcmc_store = cadet.H5()
    mcmc_store.filename = mcmc_h5.as_posix()

    if mcmc_h5.exists():
        mcmc_store.load(lock=True)

    parameters = len(cache.MIN_VALUE)

    MCMCpopulationSet = cache.settings.get("MCMCpopulationSet", None)
    if MCMCpopulationSet is not None:
        populationSize = MCMCpopulationSet
    else:
        populationSize = parameters * cache.settings["MCMCpopulation"]

    # Population must be even
    populationSize = populationSize + populationSize % 2

    # due to emcee 3.0 and RedBlueMove there is a minimum population size to work correctly based on the number of paramters
    populationSize = max(parameters * 2, populationSize)

    if checkpoint["state"] == "start":
        multiprocessing.get_logger().info("setting up kde")
        kde, kde_scaler = kde_generator.setupKDE(cache)
        checkpoint["state"] = "auto_bounds"

        with checkpointFile.open("wb") as cp_file:
            pickle.dump(checkpoint, cp_file)
    else:
        multiprocessing.get_logger().info("loading kde")
        kde, kde_scaler = kde_generator.getKDE(cache)

    path = Path(cache.settings["resultsDirBase"], cache.settings["csv"])
    with path.open("a", newline="") as csvfile:
        writer = csv.writer(csvfile, delimiter=",", quoting=csv.QUOTE_ALL)

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
            "mcmc_score": [],
        }
        halloffame = pareto.DummyFront()
        meta_hof = pareto.ParetoFront(dimensions=len(cache.WORST_META),
            similar=pareto.similar,
            similar_fit=pareto.similar_fit_meta(cache),
            slice_object=cache.meta_slice,
        )
        grad_hof = pareto.DummyFront()
        progress_hof = None

        sampler = emcee.EnsembleSampler(
            populationSize,
            parameters,
            log_posterior_vectorize,
            args=[
                cache.json_path,
                cache,
                halloffame,
                meta_hof,
                grad_hof,
                progress_hof,
                result_data,
                writer,
                csvfile,
            ],
            moves=[
                (de_snooker.DESnookerMove(), 0.1),
                (de.DEMove(), 0.9 * 0.9),
                (de.DEMove(gamma0=1.0), 0.9 * 0.1),
            ],
            vectorize=True,
        )

        if checkpoint["state"] == "auto_bounds":
            sampler_auto_bounds(cache, checkpoint, sampler, checkpointFile, mcmc_store)
            sub.graph_corner_process(cache, last=False, interval=60)


        if checkpoint["state"] == "chain":
            sampler_run(cache, checkpoint, sampler, checkpointFile, mcmc_store)
            sub.graph_corner_process(cache, last=False, interval=60)

    chain = checkpoint["run_chain"]
    chain_shape = chain.shape
    chain = chain.reshape(chain_shape[0] * chain_shape[1], chain_shape[2])

    if checkpoint["state"] == "complete":
        util.finish(cache)
        checkpoint["state"] = "plot_finish"

        with checkpointFile.open("wb") as cp_file:
            pickle.dump(checkpoint, cp_file)

    if checkpoint["state"] == "plot_finish":
        sub.mle_process(cache, last=True)
        sub.prior_process(cache)
        sub.tube_process(cache, last=True)
        sub.graph_corner_process(cache, last=True)
    return numpy.mean(chain, 0)


def get_population(base, size, diff=0.02):
    new_population = base
    row, col = base.shape
    multiprocessing.get_logger().info("%s", base)

    multiprocessing.get_logger().info("row %s size %s", row, size)
    if row < size:
        # create new entries
        indexes = numpy.random.choice(new_population.shape[0], size - row, replace=True)
        temp = new_population[indexes, :]
        rand = numpy.random.normal(1.0, diff, size=temp.shape)
        new_population = numpy.concatenate([new_population, temp * rand])
    if row > size:
        # randomly select entries to keep
        indexes = numpy.random.choice(new_population.shape[0], size, replace=False)
        multiprocessing.get_logger().info("indexes: %s", indexes)
        new_population = new_population[indexes, :]
    return new_population


def resetPopulation(checkpoint, cache):
    populationSize = checkpoint["populationSize"]
    parameters = len(cache.MIN_VALUE)

    if cache.settings.get("PreviousResults", None) is not None:
        multiprocessing.get_logger().info("running with previous best results")
        previousResultsFile = Path(cache.settings["PreviousResults"])
        results_h5 = cadet.H5()
        results_h5.filename = previousResultsFile.as_posix()
        results_h5.load(paths=["/meta_population_transform"], lock=True)
        previousResults = results_h5.root.meta_population_transform

        row, col = previousResults.shape
        multiprocessing.get_logger().info(
            "row: %s col: %s  parameters: %s", row, col, parameters
        )
        if col < parameters:
            mcmc_h5 = Path(cache.settings.get("mcmc_h5", None))
            mcmcDir = mcmc_h5.parent
            mle_h5 = mcmcDir / "mle.h5"

            data = cadet.H5()
            data.filename = mle_h5.as_posix()
            data.load(lock=True)
            multiprocessing.get_logger().info("%s", list(data.root.keys()))
            stat_MLE = data.root.stat_MLE.reshape(1, -1)
            previousResults = numpy.hstack(
                [previousResults, numpy.repeat(stat_MLE, row, 0)]
            )
            multiprocessing.get_logger().info(
                "row: %s  col:%s   shape: %s", row, col, previousResults.shape
            )

        population = get_population(previousResults, populationSize, diff=0.02)
        checkpoint["starting_population"] = population
        checkpoint["starting_population"] = [
            util.convert_individual_inverse(i, cache) for i in population
        ]
        multiprocessing.get_logger().info("startup population: %s", population)
        multiprocessing.get_logger().info(
            "startup: %s", checkpoint["starting_population"]
        )
    else:
        checkpoint["starting_population"] = SALib.sample.sobol_sequence.sample(
            populationSize, parameters
        )
    checkpoint["p_bounds"] = checkpoint["starting_population"]


def getCheckPoint(checkpointFile, cache):
    if checkpointFile.exists():
        with checkpointFile.open("rb") as cp_file:
            checkpoint = pickle.load(cp_file)
    else:
        parameters = len(cache.MIN_VALUE)

        MCMCpopulationSet = cache.settings.get("MCMCpopulationSet", None)
        if MCMCpopulationSet is not None:
            populationSize = MCMCpopulationSet
        else:
            populationSize = parameters * cache.settings["MCMCpopulation"]

        # Population must be even
        populationSize = populationSize + populationSize % 2

        # due to emcee 3.0 and RedBlueMove there is a minimum population size to work correctly based on the number of paramters
        populationSize = max(parameters * 2, populationSize)

        checkpoint = {}
        checkpoint["state"] = "start"
        checkpoint["populationSize"] = populationSize
        resetPopulation(checkpoint, cache)

        checkpoint["ln_prob_bounds"] = None
        checkpoint["rstate_bounds"] = None
        checkpoint["idx_bounds"] = 0

        checkpoint["p_chain"] = None
        checkpoint["ln_prob_chain"] = None
        checkpoint["rstate_chain"] = None
        checkpoint["idx_chain"] = 0

        checkpoint["sampler_iterations"] = 0
        checkpoint["sampler_naccepted"] = numpy.zeros(populationSize)

    return checkpoint


def process(
    population_order,
    cache,
    halloffame,
    meta_hof,
    grad_hof,
    progress_hof,
    result_data,
    results,
    writer,
    csv_file,
):
    if "gen" not in process.__dict__:
        process.gen = 0

    if "sim_start" not in process.__dict__:
        process.sim_start = time.time()

    if "generation_start" not in process.__dict__:
        process.generation_start = time.time()

    population_lookup = {}
    fitnesses_lookup = {}

    log_likelihoods_lookup = {}

    keep = set()

    for ll, theta, fit, csv_line, meta_score, result, individual in results:
        log_likelihoods_lookup[tuple(individual)] = float(ll)
        if len(csv_line):
            # if csv_line is blank it means a simulation failed or is out of bounds, if this is handed on for
            # processing it will cause problems, failed simulations are arleady recorded and we don't want their
            # failure data in the recorers where other stuff picks it up
            keep.add(tuple(individual))

            fitnesses_lookup[tuple(individual)] = (
                fit,
                csv_line,
                meta_score,
                result,
                tuple(individual),
            )

            ind = pop.Individual(individual)
            population_lookup[tuple(individual)] = ind

    # everything above is async (unordered) and needs to be reordered based on the population_order
    population = [
        population_lookup[tuple(row)] for row in population_order if tuple(row) in keep
    ]
    fitnesses = [
        fitnesses_lookup[tuple(row)] for row in population_order if tuple(row) in keep
    ]
    log_likelihoods = [
        log_likelihoods_lookup[tuple(row)]
        for row in population_order
        if tuple(row) in keep
    ]
    log_likelihoods_all = [
        log_likelihoods_lookup[tuple(row)] for row in population_order
    ]

    stalled, stallWarn, progressWarn = util.process_population(
        cache,
        population,
        fitnesses,
        writer,
        csv_file,
        halloffame,
        meta_hof,
        progress_hof,
        process.gen,
        result_data,
    )

    progress.writeProgress(
        cache,
        process.gen,
        population,
        halloffame,
        meta_hof,
        grad_hof,
        progress_hof,
        process.sim_start,
        process.generation_start,
        result_data,
        line_log=False,
        probability=numpy.exp(log_likelihoods),
    )

    sub.graph_process(cache, process.gen)

    process.gen += 1
    process.generation_start = time.time()
    return log_likelihoods_all


def process_chain(chain, cache, idx):
    chain_shape = chain.shape
    flat_chain = chain.reshape(chain_shape[0] * chain_shape[1], chain_shape[2])

    flat_chain_transform = util.convert_population_inputorder(flat_chain, cache)
    chain_transform = flat_chain_transform.reshape(chain_shape)

    return chain, flat_chain, chain_transform, flat_chain_transform


def writeMCMC(cache, mcmc_store, process_mcmc_store):
    "write out the mcmc data so it can be plotted"
    process_mcmc_store(cache, mcmc_store)

    mcmc_store.save(lock=True)


def interval(chain, cache):
    hdi = arviz.hdi(chain, hdi_prob=0.9)
    lb_5 = hdi[:,0]
    ub_95 = hdi[:,1]
    mid_50 = numpy.mean(flatten(chain), axis=0)

    hdi_stat = numpy.vstack([lb_5, mid_50, ub_95])

    pd = pandas.DataFrame(hdi_stat.transpose(), columns=["lb_hdi_90", "mean", "ub_hdi_90"])
    pd.insert(0, "name", cache.parameter_headers_actual)
    pd.set_index("name")
    return pd
