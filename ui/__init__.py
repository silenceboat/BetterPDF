"""
DeepRead AI - UI Framework

A PySide6-based UI framework for the DeepRead AI PDF reader application.

This package contains all visual components, layouts, and interactions.
The user implements the core business logic in separate packages.
"""

__version__ = "0.1.0"

from .main_window import MainWindow

__all__ = ["MainWindow"]
