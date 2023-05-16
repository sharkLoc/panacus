#!/usr/bin/env python3

#
# std import
#
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter as ADHF
from sys import stdout, stderr, exit
from functools import partial
from os import fdopen, path
import re

#
# third party packages
#

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

from sklearn.linear_model import LinearRegression
from scipy.optimize import curve_fit
import seaborn as sns

PAT_PANACUS = re.compile('^#.+panacus (\S+) (.+)')

def humanize_number(i, precision=0):

    assert i >= 0, f'non-negative number assumed, but received "{i}"'

    order = 0
    x = i
    if i > 0:
        order = int(np.log10(i))//3
        x = i/10**(order*3)

    human_r= ['', 'K', 'M', 'B', 'D']
    return '{:,.{prec}f}{:}'.format(x, human_r[order], prec=precision)


def calibrate_yticks_text(yticks):
    prec = 0
    yticks_text = list(map(partial(humanize_number, precision=prec), yticks))
    while len(set(yticks_text)) < len(yticks_text):
        prec += 1
        yticks_text = list(map(partial(humanize_number, precision=prec), yticks))

    return yticks_text

def compute_growth(Y):

    quad = lambda x, *y: y[0]*x**y[1]
    X = np.arange(len(Y))+1
    Xp = np.arange(len(Y))+1
    popt, pcov = curve_fit(quad, X, Y, p0=[1, 1], maxfev=1000*len(Y))
    return popt, quad(Xp, *popt)


def plot(df, fname, counttype, out, estimate_growth=False):

    # setup fancy plot look
    sns.set_theme(style='darkgrid')
    sns.set_color_codes('colorblind')
    sns.set_palette('husl')
    sns.despine(left=True, bottom=True)

    # let's do it!
    for i, (c,q) in enumerate(df.columns):
        df[(c, q)].plot.bar(figsize=(10, 6), color=f'C{i}', label=f'coverage $\geq {c}$, quorum $\geq {q}$')
        if estimate_growth and q == 1:
            popt, curve = compute_growth(df[(c,q)].array)
            plt.plot(curve, '--',  color='black', label=f'coverage $\geq {c}$, quorum $\geq {q}$, LS-fit to $m X^γ$ (m={humanize_number(popt[0],1)}, γ={popt[1]:.3f})')
    _ = plt.xticks(rotation=65)

    yticks, _ = plt.yticks()
    plt.yticks(yticks, calibrate_yticks_text(yticks))

    plt.title(f'Pangenome growth ({fname})')
    plt.ylabel(f'#{counttype}')
    plt.xlabel('samples')
    plt.legend(loc='lower left')
    plt.tight_layout()
    plt.savefig(out, format='pdf')
    plt.close()


if __name__ == '__main__':
    description='''
    Visualize growth stats. PDF file will be plotted to stdout.
    '''
    parser = ArgumentParser(formatter_class=ADHF, description=description)
    parser.add_argument('growth_stats', type=open,
            help='Growth table computed by panacus')
    parser.add_argument('-e', '--estimate_growth_params', action='store_true',
            help='Estimate growth parameters based on least-squares fit')

    args = parser.parse_args()

    with open(args.growth_stats.name) as growth:
        header = next(growth)
        m = PAT_PANACUS.match(header)

        if not m:
            print(f'Input file "{args.growth_stats.name}" has wrong header. It doesn\'t seem to be generated by panacus, exiting.', file=stderr)
            exit(1)
        command, arg_list = m.groups()

        if command not in ['ordered-histgrowth', 'histgrowth', 'growth']:
            print(f'Input file "{args.growth_stats.name}" is not a growth table, exiting.', file=stderr)
            exit(1)

        arg_list = arg_list.split(' ')
        counttype = 'node'
        if '-c' in arg_list:
            counttype = arg_list[arg_list.index('-c')+1]
        elif '--count' in arg_list:
            counttype = arg_list[arg_list.index('--count')+1]

    df = pd.read_csv(args.growth_stats, sep='\t', header=[1,2], index_col=[0])
    df.columns = df.columns.map(lambda x: (int(x[0]), int(x[1])))
    df = df.reindex(sorted(df.columns, key=lambda x: (x[1], x[0])), axis=1)
    with fdopen(stdout.fileno(), 'wb', closefd=False) as out:
        plot(df, path.basename(args.growth_stats.name), counttype, out, estimate_growth=args.estimate_growth_params)

