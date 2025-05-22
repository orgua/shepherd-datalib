from scipy.stats import multivariate_normal
import numpy as np
import math

import click
from pathlib import Path
from shepherd_core import Writer as ShepherdWriter
from shepherd_core.data_models.base.calibration import CalibrationPair, CalibrationSeries
from shepherd_core.data_models.task import Compression
from shepherd_core.commons import SAMPLERATE_SPS_DEFAULT

STEP_WIDTH = 1.0 / SAMPLERATE_SPS_DEFAULT

# def on_windows_norm_distrib_dc(node_count, total_steps, on_steps, duty_cycle, period_variance):
#     '''
#     Generates a 2-d array (time x node) containing node states (0 = off, 1.0 = on).
#     Fixed size on-windows are placed periodically with the given variance such that
#     the average duty cycle matches the given value.
#     '''
#
#     return on_windows_norm_distrib(node_count=node_count,
#                                    total_steps=total_steps,
#                                    on_steps=on_steps,
#                                    period_mean=on_steps / duty_cycle,
#                                    period_variance=period_variance)

def on_windows_norm_distrib(node_count, total_steps, on_steps, period_mean, period_variance):
    '''
    Generates a 2-d array (time x node) containing node states (0 = off, 1.0 = on).
    Fixed size on windows are placed periodically according to the specified normal
    distribution.
    '''

    samples = np.zeros((total_steps, node_count))
    step = np.zeros((node_count))

    while True:
        # Sample multivariate normal with covariance = identity * variance (no correlation)
        random = multivariate_normal.rvs(mean=period_mean,
                                         cov=period_variance,
                                         size=node_count,
                                         random_state=rnd_gen)
        # Convert to int to generate period lengths for each node
        period_steps = np.round(random).astype(int)
        # Increase node steps
        step += period_steps
        # Done once the 'slowest' node has reached the step limit
        if min(step) > total_steps:
            break
        # Place an on window at each node's current step
        for i in range(node_count):
            samples[int(step[i]) : int(step[i]) + on_steps, i] = 1.0
    return samples


# Transition props (p1, p2)
# p1 - chance to go up if down
# p2 - chance to stay up if already up
# duty cycle = dc: avg chance to be up at a step
# => avg chance that previous was down = (1 - dc)
# => avg chance that previous was up = dc
# => dc = (1 - dc) * p1 + dc * p2
# onduration = on: avg step count up at a time
# => avg chance to stay up = p2
# => avg chance for on=x: p2 ** (x - 1) * (1 - p2)
# => on = sum i=1 to inf (i * p(on=i)) = sum i=1 to inf (i * p2 ** (i - 1) * (1 - p2))
# => on = 1 / (1 - p2)
# parameters:
# p2 = 1 - (1 / on)
# p1 = (dc - dc * p2) / (1 - dc) = dc * (1 - dc) * (1 - p2)
def random_distrib(node_count, total_steps, avg_duty_cycle, avg_on_steps, rnd_gen):
    '''
    Generates a 2-d array (time x node) containing node states (0 = off, 1.0 = on).
    Each node's state is randomly generated such that the average duty cycle and on
    steps match the given values using a markov process.
    '''

    p2 = 1.0 - (1.0 / avg_on_steps)
    p1 = avg_duty_cycle * (1 - p2) / (1 - avg_duty_cycle)
    transition_probs = np.array([p1, p2])

    samples = np.zeros((total_steps, node_count))

    for i in range(1, total_steps):
        # Generate random vector (1 value per node)
        random = rnd_gen.random(node_count)
        # Get probability vector
        probabilities = transition_probs[samples[i - 1].astype(int)]
        # Generate updated states
        samples[i] = random < probabilities
    return samples

@click.command()
@click.option('--avg-duty-cycle', type=click.FLOAT, required=True)
@click.option('--avg-on-duration', type=click.FLOAT, required=True)
@click.option('--on-voltage', type=click.FLOAT, required=True)
@click.option('--on-current', type=click.FLOAT, required=True)
@click.option('--seed', type=click.INT, default=None)
@click.pass_context
def generate_random_independent(ctx, avg_duty_cycle, avg_on_duration, on_voltage, on_current, seed):
    assert avg_duty_cycle <= 1.0

    output_dir = ctx.obj['output_dir']
    node_count = ctx.obj['node_count']
    duration = ctx.obj['duration']
    voltage_gain = ctx.obj['voltage_gain']
    current_gain = ctx.obj['current_gain']

    total_steps = math.ceil(duration / STEP_WIDTH)

    calibrationSeries = CalibrationSeries(voltage=CalibrationPair(gain=voltage_gain, offset=0),
                                          current=CalibrationPair(gain=current_gain, offset=0))

    rnd_gen = np.random.Generator(bit_generator=np.random.PCG64(seed))
    samples = random_distrib(node_count=node_count,
                             total_steps=int(total_steps),
                             avg_duty_cycle=avg_duty_cycle,
                             avg_on_steps=avg_on_duration / STEP_WIDTH,
                             rnd_gen=rnd_gen)

    time = np.arange(stop=total_steps * STEP_WIDTH, step=STEP_WIDTH)

    for i in range(node_count):
        hostname = f'sheep{i}'
        # TODO consider generating samples transposed. might speed up stuff here
        voltage = samples[::, i]
        # TODO how to generate current?? -> ask ingmar
        current = 100e-3 * samples[::, i]

        with ShepherdWriter(file_path=output_dir / f'{hostname}.h5',
                            compression=Compression.gzip1,
                            mode='harvester',
                            datatype='ivsample', # IV-trace
                            window_samples=0, # 0 since dt is IV-trace
                            cal_data = calibrationSeries) as writer:
            writer.store_hostname(hostname)
            writer.append_iv_data_si(timestamp=time, voltage=voltage, current=current)

if __name__ == "__main__":
    cli()

# -------
# TODO: temporary tests
# -------
import matplotlib.pyplot as plt

def print_stats(samples):
    '''
    Given a numpy array (time x node) computes the average duty cycle
    and average on duration.
    '''

    # sum of all on steps / total steps (nodecnt * stepcount)
    dc = np.sum(samples) / np.prod(samples.shape)
    print(f'AVG Duty Cycle: {dc}')

    # Find all on windows and compute average duration
    on_durs = []
    for n in range(samples.shape[1]):
        # Convert to boolean array
        condition = samples[::, n] == 1.0
        # Compute transitions (assume t < 0: off, insert transition at the end)
        transitions = np.concatenate(([condition[0]],
                                      condition[:-1] != condition[1:],
                                      [True]))
        # Compute transition locations
        trans_locs = transitions.nonzero()[0]
        # Compute on durations (every 2nd difference between locations)
        node_on_durs = np.diff(trans_locs)[::2]
        # Append to list
        on_durs += list(node_on_durs)
    print(f'AVG On Duration: {sum(on_durs) / len(on_durs)}')

# samples = random_distrib(3, 10_000, 0.2, 10)
# print_stats(samples)
# plt.plot(samples)
# plt.show()
