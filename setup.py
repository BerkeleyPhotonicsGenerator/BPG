from setuptools import find_packages, setup
from pathlib import Path

here = Path(__file__).parent
readme = (here / "README.md").read_text()

setup(
    name='BerkeleyPhotonicsGenerator',
    version='0.8.5',
    author='Pavan Bhargava and Sidney Buchbinder',
    author_email='pvnbhargava@berkeley.edu',
    description='A Python framework for generating masks and simulating integrated optical systems',
    long_description=readme,
    long_description_content_type="text/markdown",
    install_requires=[
        'setuptools>=18.5',
        'PyYAML>=5.1',
        'numpy>=1.10',
        'pytest>=4',
        'matplotlib>=3',
        'gdspy==1.4',
        'scipy>=1.1.0',
        'memory_profiler>=0.54.0',
        'Jinja2>=2.10.1',
    ],
    url='https://github.com/BerkeleyPhotonicsGenerator/BPG',
    license='BSD-3-Clause',
    packages=find_packages(exclude=("tests", "docs")),
    scripts=['BPG/bpg'],
    include_package_data=True,
)
