import multiprocessing

import numpy
import pandas
import scipy.optimize
from addict import Dict

import CADETMatch.score as score
import CADETMatch.util as util

name = "fractionationSlide"


def get_settings(feature):
    settings = Dict()
    settings.adaptive = True
    settings.badScore = 1
    settings.meta_mask = True

    data = pandas.read_csv(feature["fraction_csv"])
    headers = data.columns.values.tolist()
    comps = len(headers[2:])

    settings.count = 3 * comps
    settings.graph_der = 0
    settings.graph = 0
    settings.graph_frac = 1
    return settings


def goal(offset, frac_exp, sim_data_time, spline, start, stop):
    frac_sim = util.fractionate_spline(start + offset, stop + offset, spline)
    return float(numpy.sum((frac_exp - frac_sim) ** 2))


def run(sim_data, feature):
    simulation = sim_data["simulation"]
    timeFunc = feature["timeFunc"]
    components = feature["components"]
    numComponents = len(components)
    samplesPerComponent = feature["samplesPerComponent"]
    data = feature["data"]
    CV_time = feature["CV_time"]
    start = feature["start"]
    stop = feature["stop"]
    funcs = feature["funcs"]

    time_center = (start + stop) / 2.0

    times = simulation.root.output.solution.solution_times

    scores = []

    sim_values_sse = []
    exp_values_sse = []

    graph_sim = {}
    graph_exp = {}
    graph_sim_offset = {}

    for component, value_func in funcs:
        exp_values = numpy.array(data[str(component)])
        selected = numpy.isfinite(exp_values)
        sim_value = simulation.root.output.solution[feature["unit"]][
            "solution_outlet_comp_%03d" % component
        ]

        spline = scipy.interpolate.InterpolatedUnivariateSpline(times, sim_value, ext=1)

        lb = times[numpy.argmax(sim_value)] - times[-1]
        ub = times[numpy.argmax(sim_value)] - times[0]

        # getting a starting point estimate
        offsets = numpy.linspace(lb, ub, 100)
        errors = numpy.array(
            [
                goal(
                    offset,
                    exp_values[selected],
                    times,
                    spline,
                    start[selected],
                    stop[selected],
                )
                for offset in offsets
            ]
        )
        idx_min = numpy.argmin(errors)

        offset_start, min_offsets, min_errors = util.find_opt_poly(
            offsets, errors, idx_min
        )

        result_powell = scipy.optimize.minimize(
            goal,
            offset_start,
            args=(exp_values[selected], times, spline, start[selected], stop[selected]),
            method="powell",
            bounds=[
                (min_offsets[0], min_offsets[-1]),
            ],
        )

        time_offset = result_powell.x[0]

        fracOffset = util.fractionate_spline(
            start[selected] - time_offset, stop[selected] - time_offset, spline
        )

        # if the simulation scale and exp scale are too different the estimation of similarity, offset etc is not accurate discard if value max/min > 1e3
        max_exp = max(exp_values[selected])
        max_sim = max(fracOffset)
        if max(max_exp, max_sim) / min(max_exp, max_sim) > 1e3:
            value_score = 0
            pear = 0
            time_score = 0
        else:
            value_score = value_func(max(fracOffset))
            pear = score.pear_corr(
                scipy.stats.pearsonr(exp_values[selected], fracOffset)[0]
            )
            time_score = timeFunc(abs(time_offset))

        exp_values_sse.extend(exp_values[selected])
        sim_values_sse.extend(fracOffset)

        scores.append(pear)
        scores.append(time_score)
        scores.append(value_score)

        graph_sim[component] = list(zip(start[selected], stop[selected], fracOffset))
        graph_exp[component] = list(
            zip(start[selected], stop[selected], exp_values[selected])
        )

        graph_sim_offset[component] = time_offset

    sim_data["graph_exp"] = graph_exp
    sim_data["graph_sim"] = graph_sim
    sim_data["graph_sim_offset"] = graph_sim_offset

    return (
        scores,
        util.sse(numpy.array(sim_values_sse), numpy.array(exp_values_sse)),
        len(sim_values_sse),
        time_center,
        numpy.array(sim_values_sse),
        numpy.array(exp_values_sse)
    )


def setup(sim, feature, selectedTimes, selectedValues, CV_time, abstol, cache):
    temp = {}
    data = pandas.read_csv(feature["fraction_csv"])
    rows, cols = data.shape

    headers = data.columns.values.tolist()

    start = numpy.array(data.iloc[:, 0])
    stop = numpy.array(data.iloc[:, 1])

    smallestTime = min(start - stop)
    abstolFraction = abstol * smallestTime

    funcs = []

    for idx, component in enumerate(headers[2:], 2):
        value = numpy.array(data.iloc[:, idx])
        funcs.append((int(component), score.value_function(max(value), abstolFraction)))

    temp["data"] = data
    temp["start"] = start
    temp["stop"] = stop
    temp["timeFunc"] = score.time_function_decay(feature["time"][-1])
    temp["components"] = [int(i) for i in headers[2:]]
    temp["samplesPerComponent"] = rows
    temp["CV_time"] = CV_time
    temp["funcs"] = funcs
    temp["unit"] = feature["unit_name"]
    temp["peak_max"] = data.iloc[:, 2:].max().min()
    return temp


def headers(experimentName, feature):
    data = pandas.read_csv(feature["fraction_csv"])
    rows, cols = data.shape

    data_headers = data.columns.values.tolist()

    temp = []
    for component in data_headers[2:]:
        temp.append(
            "%s_%s_Component_%s_Similarity"
            % (experimentName, feature["name"], component)
        )
        temp.append(
            "%s_%s_Component_%s_Time" % (experimentName, feature["name"], component)
        )
        temp.append(
            "%s_%s_Component_%s_Value" % (experimentName, feature["name"], component)
        )
    return temp
