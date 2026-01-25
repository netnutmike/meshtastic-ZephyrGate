"""
ZephyrGate Setup Configuration

Makes ZephyrGate installable as a Python package, allowing plugins to import
from 'src' modules.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    requirements = [
        line.strip() 
        for line in requirements_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="zephyrgate",
    version="1.0.0",
    description="Unified Meshtastic Gateway with Plugin System",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="ZephyrGate Team",
    author_email="team@zephyrgate.example.com",
    url="https://github.com/zephyrgate/zephyrgate",
    license="MIT",
    
    # Package discovery
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    
    # Include package data
    include_package_data=True,
    
    # Dependencies
    install_requires=requirements,
    
    # Python version requirement
    python_requires=">=3.10",
    
    # Entry points
    entry_points={
        "console_scripts": [
            "zephyrgate=main:main",
        ],
    },
    
    # Classifiers
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Communications :: Ham Radio",
        "Topic :: System :: Networking",
    ],
    
    # Keywords
    keywords="meshtastic gateway mesh-network lora ham-radio",
)
