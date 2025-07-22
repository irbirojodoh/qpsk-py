#!/usr/bin/env python3
"""
Setup script for QPSK Digital Communication System
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="qpsk-communication",
    version="1.0.0",
    author="QPSK Project Team",
    author_email="qpsk@example.com",
    description="Packet-based QPSK Digital Communication System with GNU Radio",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/irbirojodoh/qpsk-py",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)",
        "Topic :: Communications :: Ham Radio",
    ],
    python_requires=">=3.6",
    install_requires=[
        "numpy>=1.19.0",
        "gnuradio>=3.8.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "black",
            "flake8",
        ],
    },
    entry_points={
        "console_scripts": [
            "qpsk-transmit=src.transmitter.cli:main",
            "qpsk-receive=src.receiver.cli:main",
        ],
    },
)
