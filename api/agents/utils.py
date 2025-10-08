# api/agents/utils.py

from typing import Any, Dict, List

def sanitize_for_mongodb(data: Any) -> Any:
    """
    Recursively sanitize data to be MongoDB-safe.
    Handles large integers that exceed MongoDB's 8-byte limit.
    """
    if isinstance(data, dict):
        return {k: sanitize_for_mongodb(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_mongodb(item) for item in data]
    elif isinstance(data, int):
        # MongoDB can only handle up to 8-byte signed integers
        # Max: 9,223,372,036,854,775,807 (2^63 - 1)
        # Min: -9,223,372,036,854,775,808 (-2^63)
        MAX_INT = 2147483647  # Use 32-bit max for safety
        MIN_INT = -2147483648
        if data > MAX_INT:
            return MAX_INT
        elif data < MIN_INT:
            return MIN_INT
        return data
    elif isinstance(data, float):
        # Ensure float is valid
        if data != data:  # NaN check
            return 0.0
        return data
    else:
        return data