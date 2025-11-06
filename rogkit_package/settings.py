"""
Rogkit package settings and path configuration.

Defines script directory, root directory, TOML sample path, and data directory.
"""
import os

script_dir = os.path.dirname(os.path.abspath(__file__))

# root dir is script dir's less the last folder name
root_dir = script_dir.rsplit('/', 1)[0]
toml_sample_path = os.path.join(root_dir, 'rogkit_sample.toml')

data_dir = os.path.join(root_dir, 'data')