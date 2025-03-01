"""
Setup script for Mario Trader Beta
"""
from setuptools import setup, find_packages

setup(
    name="mario_trader",
    version="0.1.0",
    description="A MetaTrader 5 trading bot",
    author="Mario Trader",
    packages=find_packages(),
    install_requires=[
        "MetaTrader5>=5.0.45",
        "pandas>=2.0.3",
        "numpy>=1.24.3",
        "requests>=2.31.0",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "mario-trader=main:main",
        ],
    },
) 