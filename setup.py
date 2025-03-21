"""
Setup script for Mario Trader Beta
"""
from setuptools import setup, find_packages

setup(
    name="mario_trader",
    version="1.0.0",
    description="MetaTrader 5 trading bot using SMA Crossover Strategy with RSI confirmation",
    author="Mario Trader",
    packages=find_packages(),
    install_requires=[
        "MetaTrader5>=5.0.33",
        "numpy>=1.20.0",
        "pandas>=1.2.0",
        "matplotlib>=3.4.0",
        "scikit-learn>=0.24.0",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Topic :: Office/Business :: Financial :: Investment",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "mario-trader=main:main",
        ],
    },
) 