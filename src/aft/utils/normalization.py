"""
A module for string normalization functions.
"""

import re

def normalize_spaces(text: str) -> str:
    """
    Normalizes multiple consecutive spaces in a string to a single space.
    Also removes leading/trailing spaces.

    Parameters
    ----------
    text : str
        The input string.

    Returns
    -------
    str
        The string with normalized spaces.
    
    Example:
    >>> normalize_spaces("  Hello   World!  ")
    "Hello World!"
    
    """
    # Replace any sequence of one or more whitespace characters (\s+) with a single space.
    # Then, remove any leading or trailing whitespace using .strip().
    normalized_text = re.sub(r'\s+', ' ', text).strip()
    return normalized_text

