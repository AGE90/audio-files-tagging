"""
This module leverages `pyprojroot` to dynamically locate the root directory of the project
and create paths relative to it. By using the `here()` function from `pyprojroot`, the
project root is automatically detected based on common root indicators (e.g., `.git/`, 
`pyproject.toml`, or `setup.py`).

This enables consistent and portable path handling across the project, ensuring that 
relative paths are resolved reliably, regardless of the script's location within the 
project structure.

Dependencies:
-------------
- pyprojroot: Detects the root of the project.
- pathlib: Provides an object-oriented interface for handling filesystem paths.
"""

from pathlib import Path
from collections.abc import Callable, Iterable

from pyprojroot import here


def make_dir_function(dir_name: str | Iterable[str]) -> Callable[..., Path]:
    """
    Generate a function that constructs a path relative to the project directory, 
    extending it with the provided subdirectory or subdirectories.

    Parameters
    ----------
    dir_name : Union[str, Iterable[str]]
        The name of the subdirectory (or a list of subdirectories) to append to the 
        project root. If a single string is provided, it is treated as a single subdirectory. 
        If an iterable of strings (e.g., a list) is provided, it will be joined into a path 
        string, with separators dependent on the operating system.

    Returns
    -------
    Callable[..., Path]
        A function that, when called, returns the full path relative to the project directory.
        The returned function can accept additional arguments to further extend the path.
    """
    def dir_path(*args: str) -> Path:
        # Join the dir_name and any additional arguments as a path relative to the project root
        if isinstance(dir_name, str):
            return here().joinpath(dir_name, *args)
        return here().joinpath(*dir_name, *args)

    return dir_path

# Create the project directory function
project_dir = make_dir_function('')

# Define a comprehensive list of directory types
dir_types: list[list[str]] = [
    ['data'],                   # Base data folder
    ['notebooks'],              # Jupyter notebooks folder
    ['logs'],                   # Logs folder
    ['tests'],                  # Unit test files
    ['docs'],                   # Documentation files
]

# Use a dictionary to store dynamically created directory functions
dir_functions: dict[str, Callable[..., Path]] = {}

# Dynamically create directory functions and store them in the dictionary
for dir_type in dir_types:
    DIR_VAR_NAME = '_'.join(dir_type) + '_dir'  # Create variable name like 'data_raw_dir'
    dir_functions[DIR_VAR_NAME] = make_dir_function(dir_type)

# Example usage:
# You can now access directories dynamically via the dir_functions dictionary
data_dir = dir_functions['data_dir']
notebooks_dir = dir_functions['notebooks_dir']
logs_dir = dir_functions['logs_dir']
tests_dir = dir_functions['tests_dir']
docs_dir = dir_functions['docs_dir']

# # Example print statements to show directory paths
# print(f'Data Directory: {data_dir()}')
