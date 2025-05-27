from scipy.stats import multivariate_normal
import numpy as np
import math

bit_gen = np.random.PCG64(32220789340897324098232347119065234157809)
rnd_gen = np.random.Generator(bit_generator=bit_gen)

def generate_cov_matrix(dim: int, variance: float, correlation: float):
    """
    Generate a covariance matrix for a multivariate normal distribution with
    strong dependence and given variance.

    Parameters:
    dim (int): Number of dimensions.
    variance (float): Desired variance for each marginal distribution.
    correlation (float): Correlation between the variables (close to 1 for strong dependence).

    Returns:
    np.ndarray: A valid covariance matrix.
    """
    # Create a correlation matrix with off-diagonal values set to the correlation coefficient
    correlation_matrix = np.full((dim, dim), correlation)
    np.fill_diagonal(correlation_matrix, 1)  # Diagonal should be 1 (self-correlation)

    # Convert correlation matrix to covariance matrix using variance
    covariance_matrix = correlation_matrix * variance

    return covariance_matrix

def multivariate_random_walk(node_count, step_size, n_steps, correlation, variance, bound_low, bound_high):
    # Generate covariance matrix
    cov_matrix = generate_cov_matrix(dim=node_count, variance=variance, correlation=correlation)

    samples = np.zeros((n_steps, node_count))
    # Start in the middle between the bounds
    samples[0] = (bound_low + bound_high) / 2.0

    for i in range(1, n_steps):
        rands = multivariate_normal.rvs(None, cov_matrix)
        for j in range(node_count):
            if rands[j] < 0.0:
                samples[i, j] = samples[i - 1, j] + step_size
            else:
                samples[i, j] = samples[i - 1, j] - step_size
            samples[i, j] = max(min(samples[i, j], bound_high), bound_low)
    return samples

# -----
# TODO: temporary tests
# -----
import matplotlib.pyplot as plt

samples = multivariate_random_walk(node_count=3,
                                   correlation=0.9,
                                   variance=0.05,
                                   bound_low=0.0,
                                   bound_high=5.0,
                                   step_size=0.01,
                                   n_steps=100_000)

plt.plot(samples)
plt.show()
