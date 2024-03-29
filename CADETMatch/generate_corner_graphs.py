import sys

import matplotlib
import matplotlib.style as mplstyle

mplstyle.use("fast")

matplotlib.use("Agg")

size = 20

matplotlib.rc("font", size=size)  # controls default text sizes
matplotlib.rc("axes", titlesize=size)  # fontsize of the axes title
matplotlib.rc("axes", labelsize=size)  # fontsize of the x and y labels
matplotlib.rc("xtick", labelsize=size)  # fontsize of the tick labels
matplotlib.rc("ytick", labelsize=size)  # fontsize of the tick labels
matplotlib.rc("legend", fontsize=size)  # legend fontsize
matplotlib.rc("figure", titlesize=size)  # fontsize of the figure title
matplotlib.rc("figure", autolayout=True)

import itertools
import logging

# parallelization
import multiprocessing
import os
import warnings
from pathlib import Path

import corner
import numpy
import pandas
import scipy.interpolate
import seaborn as sns
from addict import Dict
from cadet import H5
from matplotlib import figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from mpl_toolkits.mplot3d import Axes3D

import CADETMatch.loggerwriter as loggerwriter
import CADETMatch.util as util
from CADETMatch.cache import cache


def new_range(flat_chain):
    lb_data, mid_data, ub_data = numpy.percentile(flat_chain, [5, 50, 95], 0)

    distance = numpy.max(
        numpy.abs(numpy.array([lb_data - mid_data, ub_data - mid_data])), axis=0
    )

    lb_range = mid_data - 2 * distance
    ub_range = mid_data + 2 * distance

    return numpy.array([lb_range, ub_range])


def main():
    cache.setup_dir(sys.argv[1])
    util.setupLog(cache.settings["resultsDirLog"], "graph_corner.log")
    cache.setup(sys.argv[1])

    multiprocessing.get_logger().info("graphing directory %s", os.getcwd())

    resultDir = Path(cache.settings["resultsDirBase"])
    result_lock = resultDir / "result.lock"


    mcmcDir = Path(cache.settings["resultsDirMCMC"])
    mcmc_h5 = mcmcDir / "mcmc.h5"
    result_h5 = resultDir / "result.h5"

    if mcmc_h5.exists():
        data_mcmc = H5()
        data_mcmc.filename = mcmc_h5.as_posix()
        data_mcmc.load(lock=True)

        data_results = None
    else:
        data_results = H5()
        data_results.filename = result_h5.as_posix()
        data_results.load(lock=True)

        data_mcmc = None

    graphCorner(cache, data_mcmc, data_results)


def plotChain(flat_chain, flat_chain_transform, headers, out_dir, prefix):
    multiprocessing.get_logger().info("plotting chain")
    if len(flat_chain) > 1e5:
        indexes = numpy.random.choice(flat_chain.shape[0], int(1e5), replace=False)
        chain = flat_chain[indexes]
        chain_transform = flat_chain_transform[indexes]
    else:
        chain = flat_chain
        chain_transform = flat_chain_transform

    if len(chain) == 0:
        return

    # stat corner plot
    fig_size = 6 * len(headers)
    fig = corner.corner(
        chain,
        quantiles=(0.16, 0.5, 0.84),
        show_titles=True,
        labels=headers,
        bins=20,
        range=new_range(chain).T,
        use_math_text=True,
        title_fmt=".2g",
    )
    fig.set_size_inches((fig_size, fig_size))
    fig.savefig(str(out_dir / ("%s_corner.png" % prefix)))

    fig = corner.corner(
        chain_transform,
        quantiles=(0.16, 0.5, 0.84),
        show_titles=True,
        labels=headers,
        bins=20,
        range=new_range(chain_transform).T,
        use_math_text=True,
        title_fmt=".2g",
    )
    fig.set_size_inches((fig_size, fig_size))
    fig.savefig(str(out_dir / ("%s_corner_transform.png" % prefix)))


def plotMCMCParam(out_dir, param, chain, header):
    multiprocessing.get_logger().info("plotting mcmc param %s", param)
    shape = chain.shape
    x = numpy.linspace(0, shape[1], shape[1])

    fig = figure.Figure(figsize=[10, 10])
    canvas = FigureCanvas(fig)
    graph = fig.add_subplot(1, 1, 1)

    graph.plot(x, chain[0, :, param], "r", label="5")
    graph.plot(x, chain[1, :, param], "k", label="mean")
    graph.plot(x, chain[2, :, param], "r", label="95")
    graph.fill_between(
        x, chain[0, :, param], chain[2, :, param], facecolor="r", alpha=0.5
    )
    graph.legend()
    graph.set_title(header)
    fig.set_size_inches((12, 12))
    print(header, header.replace("/", "_"))
    fig.savefig(str(out_dir / ("%s.png" % header.replace("/", "_"))))


def plotMCMCVars(out_dir, headers, data):
    for param_idx, header in enumerate(headers):
        if "train_chain_stat" in data.root:
            plotMCMCParam(
                out_dir,
                param_idx,
                data.root.train_chain_stat,
                "Train " + header + str(param_idx),
            )
            plotMCMCParam(
                out_dir,
                param_idx,
                data.root.train_chain_stat_transform,
                "Train " + header + " Transform" + str(param_idx),
            )

        if "run_chain_stat" in data.root:
            plotMCMCParam(
                out_dir,
                param_idx,
                data.root.run_chain_stat,
                "Run " + header + str(param_idx),
            )
            plotMCMCParam(
                out_dir,
                param_idx,
                data.root.run_chain_stat_transform,
                "Run " + header + " Transform" + str(param_idx),
            )


def keep_header(char):
    allowed = set("-0123456789")
    return char in allowed


def clean_header(header):
    splits = header.split()
    temp = [splits[0]]
    for string in splits[1:]:
        temp.append("".join([i for i in string if keep_header(i)]))
    return " ".join(temp)


def graphCorner(cache, data_mcmc=None, data_results=None):
    multiprocessing.get_logger().info("plotting corner plots")
    headers = list(cache.parameter_headers_actual)
    headers = [clean_header(header) for header in headers]

    if data_mcmc is not None:
        data = data_mcmc

        out_dir = cache.settings["resultsDirProgress"]

        if "tau_percent" in data.root:
            multiprocessing.get_logger().info("plotting tau plots")
            fig = figure.Figure(figsize=[10, 10])
            canvas = FigureCanvas(fig)
            graph = fig.add_subplot(1, 1, 1)

            tau_percent = numpy.squeeze(data.root.tau_percent)
            max_values = numpy.ones(tau_percent.shape)
            tau_percent = numpy.min([tau_percent, max_values], 0)

            graph.bar(list(range(len(headers))), tau_percent, tick_label=headers)
            fig.set_size_inches((12, 12))
            fig.savefig(str(out_dir / "tau_percent.png"))

        if "flat_chain" in data.root:
            multiprocessing.get_logger().info("plot flat chain")
            plotChain(
                data.root.flat_chain,
                data.root.flat_chain_transform,
                headers,
                out_dir,
                "full",
            )

        if "integrated_autocorrelation_time" in data.root:
            iat = data.root.integrated_autocorrelation_time

            multiprocessing.get_logger().info("plot integrated autocorrelation time")
            fig = figure.Figure(figsize=[10, 10])
            canvas = FigureCanvas(fig)
            graph = fig.add_subplot(1, 1, 1)

            for i in range(1, iat.shape[1]):
                graph.plot(iat[:, 0], iat[:, i], label=i)
            graph.set_title("Integrated Autocorrelation Time")
            graph.set_xlabel("Step")
            graph.set_ylabel("IAT")
            graph.legend()
            fig.set_size_inches((12, 12))
            fig.savefig(str(out_dir / "integrated_autocorrelation_time.png"))

            fig = figure.Figure(figsize=[10, 10])
            canvas = FigureCanvas(fig)
            graph = fig.add_subplot(1, 1, 1)
            tau = cache.MCMCTauMult
            for i in range(1, iat.shape[1]):
                progress = (iat[:, 0] / tau) / iat[:, i]
                progress[progress > 1] = 1
                graph.plot(iat[:, 0], progress, label=i)
            graph.set_title("Integrated Autocorrelation Time Progress")
            graph.set_xlabel("Step")
            graph.set_ylabel("Progress")
            graph.legend()
            fig.set_size_inches((12, 12))
            fig.savefig(str(out_dir / "integrated_autocorrelation_time_progress.png"))

        if "mcmc_acceptance" in data.root:
            multiprocessing.get_logger().info("plot mcmc acceptance")
            fig = figure.Figure(figsize=[10, 10])
            canvas = FigureCanvas(fig)
            graph = fig.add_subplot(1, 1, 1)
            graph.plot(util.get_confidence(data.root.mcmc_acceptance))
            graph.set_title("MCMC Acceptance")
            graph.set_xlabel("Step")
            graph.set_ylabel("Acceptance")
            fig.set_size_inches((12, 12))
            fig.savefig(str(out_dir / "mcmc_acceptance.png"))

        plotChain(
            data.root.train_flat_chain,
            data.root.train_flat_chain_transform,
            headers,
            out_dir,
            "train",
        )
        plotMCMCVars(out_dir, headers, data)

    else:
        data = data_results

        if len(data.root.input) > 1e5:
            indexes = numpy.random.choice(
                data.root.input.shape[0], int(1e5), replace=False
            )
            data_input = data.root.input[indexes]
            data_input_transform = data.root.input_transform[indexes]
            weight_min = data.root.output_meta[indexes, 1]
            weight_prod = data.root.output_meta[indexes, 2]
            all_scores = data.root.output[indexes]
        else:
            data_input = data.root.input
            data_input_transform = data.root.input_transform
            weight_min = data.root.output_meta[:, 1]
            weight_prod = data.root.output_meta[:, 2]
            all_scores = data.root.output

        max_scores = numpy.max(all_scores, 1)
        acceptable = max_scores > 0.01

        if numpy.any(acceptable):
            multiprocessing.get_logger().info(
                "graphing remove %s points", len(max_scores) - numpy.sum(acceptable)
            )

            data_input = data_input[acceptable]
            data_input_transform = data_input_transform[acceptable]
            weight_min = weight_min[acceptable]
            weight_prod = weight_prod[acceptable]

        out_dir = cache.settings["resultsDirProgress"]

        create_corner(out_dir, "corner.png", headers, data_input, weights=None)
        create_corner(
            out_dir, "corner_min.png", headers, data_input, weights=weight_min
        )
        create_corner(
            out_dir, "corner_prod.png", headers, data_input, weights=weight_prod
        )

        # transformed entries
        create_corner(
            out_dir, "corner_transform.png", headers, data_input_transform, weights=None
        )
        create_corner(
            out_dir,
            "corner_min_transform.png",
            headers,
            data_input_transform,
            weights=weight_min,
        )
        create_corner(
            out_dir,
            "corner_prod_transform.png",
            headers,
            data_input_transform,
            weights=weight_prod,
        )


def create_corner(dir, filename, headers, data, weights=None):
    if len(data) <= len(headers):
        multiprocessing.get_logger().info(
            "There is not enough data to generate corner plots"
        )
        return
    if numpy.all(numpy.min(data, 0) < numpy.max(data, 0)):
        if weights is None or numpy.max(weights) > numpy.min(weights):
            bounds = new_range(data).T

            fig_size = 6 * len(headers)
            fig = corner.corner(
                data,
                quantiles=(0.16, 0.5, 0.84),
                show_titles=True,
                labels=headers,
                bins=20,
                range=new_range(data).T,
                use_math_text=True,
                title_fmt=".2g",
            )
            fig.set_size_inches((fig_size, fig_size))
            fig.savefig(str(dir / filename))

            df = pandas.DataFrame(data, columns=headers)
            fig = sns.PairGrid(df, diag_sharey=False, height=fig_size)
            fig.map_lower(sns.kdeplot)
            fig.map_upper(sns.scatterplot)
            fig.map_diag(sns.kdeplot, lw=3)

            for row_num, row in enumerate(bounds):
                for col_num, col in enumerate(bounds):
                    if row_num == col_num:
                        fig.axes[row_num, col_num].set_xlim(*row)
                    else:
                        fig.axes[row_num, col_num].set_xlim(*col)
                        fig.axes[row_num, col_num].set_ylim(*row)

            fig.savefig(str(dir / ("sns_%s" % filename)))


if __name__ == "__main__":
    main()
