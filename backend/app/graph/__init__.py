"""
Builds the routable pgRouting graph from raw source data. Splits OSM ways
into edges and computes attribute scores (greenness, noise, urbanness, sightseeing)
for each one. Runs only in the worker.
"""

__all__ = []  # defines public API for module
