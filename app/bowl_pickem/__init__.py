"""
Bowl Pick'em Blueprint
Flask Blueprint for Bowl Pick'em feature
"""
from flask import Blueprint

# Import the blueprint from routes
from .routes import bp

# Make the blueprint available when importing this module
__all__ = ['bp']