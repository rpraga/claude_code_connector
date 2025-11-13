"""Setup script for Metabase Migrator."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="metabase-migrator",
    version="1.0.0",
    author="Metabase Migrator",
    description="A tool to migrate Metabase questions between databases",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[
        "requests>=2.31.0",
        "pyyaml>=6.0",
        "click>=8.1.0",
        "python-dotenv>=1.0.0",
        "tabulate>=0.9.0",
        "colorama>=0.4.6",
    ],
    entry_points={
        "console_scripts": [
            "metabase-migrator=metabase_migrator.cli:cli",
        ],
    },
)
