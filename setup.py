"""
Setup configuration for PharmIntel.
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = ""
if readme_file.exists():
    long_description = readme_file.read_text(encoding="utf-8")

setup(
    name="pharmintel",
    version="1.0.0",
    author="PharmIntel Team",
    description="Comprehensive Pharmaceutical Intelligence System",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "pandas>=2.0.0",
        "openpyxl>=3.1.0",
        "sqlalchemy>=2.0.0",
        "fastapi>=0.104.0",
        "uvicorn>=0.24.0",
        "streamlit>=1.28.0",
        "plotly>=5.17.0",
        "python-multipart>=0.0.6",
        "pydantic>=2.4.0",
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
        "reportlab>=4.0.0",
        "jinja2>=3.1.2",
        "numpy>=1.24.0",
        "scipy>=1.11.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "black>=23.10.0",
            "flake8>=6.1.0",
            "mypy>=1.6.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "pharmintel=pharmintel.cli.commands:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Healthcare Industry",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
