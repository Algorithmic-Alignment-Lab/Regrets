"""
encoding_utils.py

This module provides utility functions for encoding and decoding data, including custom JSON encoders and object-to-dictionary converters.
"""
class CustomEncoder(json.JSONEncoder):
    """Custom JSON encoder for handling datetime objects."""
    def default(self, obj):
        if isinstance(obj, pd.Timestamp) or isinstance(obj, datetime.datetime):
            return obj.isoformat()
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)
    
def object_as_dict(obj):
    """Convert an object to a dictionary, excluding private attributes."""
    return {key: value for key, value in obj.__dict__.items() if not key.startswith('_')}