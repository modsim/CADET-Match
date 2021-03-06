import numpy
import scipy.interpolate
import scipy.stats
from addict import Dict

import CADETMatch.score as score
import CADETMatch.util as util

name = "derivative_similarity_hybrid2"
settings = Dict()
settings.adaptive = True
settings.badScore = 0
settings.meta_mask = True
settings.count = 4
settings.failure = (
    [0.0] * settings.count,
    1e6,
    1,
    numpy.array([0.0]),
    numpy.array([0.0]),
    numpy.array([1e6]),
    [1.0] * settings.count,
)


def run(sim_data, feature):
    "Order is Pearson, Value High, Time High, Value Low, Time Low"
    sim_time_values, sim_data_values = util.get_times_values(
        sim_data["simulation"], feature
    )
    selected = feature["selected"]

    exp_data_values = feature["value"][selected]
    exp_time_values = feature["time"][selected]

    sim_spline = util.create_spline(exp_time_values, sim_data_values).derivative(1)
    exp_spline = util.create_spline(exp_time_values, exp_data_values).derivative(1)

    exp_data_values_spline = exp_spline(exp_time_values)
    sim_data_values_spline = sim_spline(exp_time_values)

    score_corr, diff_time = score.cross_correlate(
        exp_time_values, sim_data_values_spline, exp_data_values_spline
    )

    [highs, lows] = util.find_peak(exp_time_values, sim_data_values_spline)

    temp = [
        score.pear_corr(
            scipy.stats.pearsonr(
                sim_spline(exp_time_values), exp_spline(exp_time_values)
            )[0]
        ),
        feature["time_function"](diff_time),
        feature["value_function_high"](highs[1]),
        feature["value_function_low"](lows[1]),
    ]

    return (
        temp,
        util.sse(sim_data_values, exp_data_values),
        len(sim_data_values),
        sim_time_values,
        sim_data_values,
        exp_data_values,
        [1.0 - i for i in temp],
    )


def setup(sim, feature, selectedTimes, selectedValues, CV_time, abstol):
    temp = {}
    exp_spline = util.create_spline(selectedTimes, selectedValues).derivative(1)

    [high, low] = util.find_peak(selectedTimes, exp_spline(selectedTimes))

    temp["peak_high"] = high
    temp["peak_low"] = low

    temp["time_function"] = score.time_function(CV_time, high[0], diff_input=True)
    temp["value_function_high"] = score.value_function(high[1], abstol, 0.1)
    temp["value_function_low"] = score.value_function(low[1], abstol, 0.1)
    return temp


def headers(experimentName, feature):
    name = "%s_%s" % (experimentName, feature["name"])
    temp = [
        "%s_Derivative_Similarity_hybrid" % name,
        "%s_Time" % name,
        "%s_High_Value" % name,
        "%s_Low_Value" % name,
    ]
    return temp
