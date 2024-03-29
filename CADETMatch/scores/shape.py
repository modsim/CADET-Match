import numpy
import scipy.interpolate
import scipy.stats
from addict import Dict

import CADETMatch.score as score
import CADETMatch.smoothing as smoothing
import CADETMatch.util as util

name = "Shape"


def get_settings(feature):
    settings = Dict()
    settings.adaptive = True
    settings.badScore = 1
    settings.meta_mask = True

    derivative = feature.get("derivative", 1)

    settings.graph = 1
    settings.graph_frac = 0

    if derivative:
        settings.count = 6
        settings.graph_der = 1
    else:
        settings.count = 3
        settings.graph_der = 0
    return settings


def run(sim_data, feature):
    "similarity, value, start stop"
    sim_time_values, sim_data_values = util.get_times_values(
        sim_data["simulation"], feature
    )
    selected = feature["selected"]

    exp_data_values = feature["value"][selected]
    exp_time_values = feature["time"][selected]
    exp_data_values_spline = feature["exp_data_values_spline"]

    sim_data_values_smooth, sim_data_values_der_smooth = smoothing.full_smooth(
        exp_time_values,
        sim_data_values,
        feature["critical_frequency"],
        feature["smoothing_factor"],
        feature["critical_frequency_der"],
    )

    [high, low] = util.find_peak(exp_time_values, sim_data_values_smooth)

    time_high, value_high = high

    pearson, diff_time = score.pearson_spline(
        exp_time_values, sim_data_values_smooth, feature["smooth_value"]
    )

    derivative = feature.get("derivative", 1)

    if derivative:
        pearson_der = score.pearson_offset(
            diff_time,
            exp_time_values,
            sim_data_values_der_smooth,
            exp_data_values_spline,
        )
        [highs_der, lows_der] = util.find_peak(
            exp_time_values, sim_data_values_der_smooth
        )

    temp = [
        pearson,
        feature["value_function"](value_high),
        feature["time_function"](numpy.abs(diff_time)),
    ]

    if derivative:
        temp.extend(
            [
                pearson_der,
                feature["value_function_high"](highs_der[1]),
                feature["value_function_low"](lows_der[1]),
            ]
        )

    return (
        temp,
        util.sse(sim_data_values, exp_data_values),
        len(sim_data_values),
        sim_time_values,
        sim_data_values,
        exp_data_values
    )


def setup(sim, feature, selectedTimes, selectedValues, CV_time, abstol, cache):
    name = "%s_%s" % (sim.root.experiment_name, feature["name"])
    s, crit_fs, crit_fs_der = smoothing.find_smoothing_factors(
        selectedTimes, selectedValues, name, cache
    )

    exp_data_values_smooth, exp_data_values_der_smooth = smoothing.full_smooth(
        selectedTimes, selectedValues, crit_fs, s, crit_fs_der
    )

    [high, low] = util.find_peak(selectedTimes, exp_data_values_der_smooth)

    temp = {}
    temp["peak"] = util.find_peak(selectedTimes, exp_data_values_smooth)[0]

    decay = feature.get("decay", 0)

    if decay:
        temp["time_function"] = score.time_function_decay(feature["time"][-1])
    else:
        temp["time_function"] = score.time_function(feature["time"][-1], 0.1 * CV_time)

    temp["value_function"] = score.value_function(temp["peak"][1], abstol)
    temp["value_function_high"] = score.value_function(
        high[1], numpy.abs(high[1]) / 1000
    )
    temp["value_function_low"] = score.value_function(low[1], numpy.abs(low[1]) / 1000)
    temp["peak_max"] = max(selectedValues)
    temp["smoothing_factor"] = s
    temp["critical_frequency"] = crit_fs
    temp["critical_frequency_der"] = crit_fs_der
    temp["smooth_value"] = exp_data_values_smooth
    temp["exp_data_values_spline"] = exp_data_values_der_smooth
    return temp


def headers(experimentName, feature):
    name = "%s_%s" % (experimentName, feature["name"])
    derivative = feature.get("derivative", 1)
    temp = ["%s_Similarity" % name, "%s_Value" % name, "%s_Time" % name]

    if derivative:
        temp.extend(
            [
                "%s_Derivative_Similarity" % name,
                "%s_Der_High_Value" % name,
                "%s_Der_Low_Value" % name,
            ]
        )
    return temp
