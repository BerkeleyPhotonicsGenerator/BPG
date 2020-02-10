# Berkeley Photonics Generator 
[![Build Status](https://dev.azure.com/pvnbhargava/BPG_CICD/_apis/build/status/BerkeleyPhotonicsGenerator.BPG?branchName=master)](https://dev.azure.com/pvnbhargava/BPG_CICD/_build/latest?definitionId=2&branchName=master)
[![Documentation Status](https://readthedocs.org/projects/bpg/badge/?version=latest)](https://bpg.readthedocs.io/en/latest/?badge=latest)
[![DOI](https://zenodo.org/badge/137926394.svg)](https://zenodo.org/badge/latestdoi/137926394)

The Berkeley Photonics Generator (BPG) is a Python framework that enables you to generate and simulate silicon photonics 
layout. BPG leverages the [BAG 2.0 framework](https://github.com/ucb-art/BAG_framework), and has similar syntax and 
file structure. If you would like to cite this software in a publication, please use the following link:
[![DOI](https://zenodo.org/badge/137926394.svg)](https://zenodo.org/badge/latestdoi/137926394)

## Table of Contents
- [Documentation](#Documentation)
- [Installation](#Installation)
- [Usage](#Usage)
- [Contributing](#Contributing)
- [Credits](#Credits)

## Documentation
The most up to date BPG documentation can be found [here](https://bpg.readthedocs.io)

## Installation
WARNING: Installation instructions are currently in flux.

We highly recommend you use an [Anaconda](https://www.anaconda.com/distribution/) environment with a Python version 
greater than 3.6. BPG generally will not function with Python versions less than 3.6, and requires packages with 
C/C++ dependencies that are most easily installed using Anaconda.

Once Anaconda is set up, please run the following commands to install packages with C/C++ dependencies:
```bash
conda install numpy
conda install rtree
conda install shapely
```

Then clone and install BAG with in any folder with:
```bash
git clone git@github.com:ucb-art/BAG_Framework.git
cd BAG_Framework
pip install .
```

Finally clone and install BPG in any folder with:
```bash
git clone git@github.com:BerkeleyPhotonicsGenerator/BPG.git
cd BPG
pip install .
```

BPG generally generates output layouts in the GDSII format. To view these layouts, we recommend you install and use the 
free open-source software package, [Klayout](https://klayout.de).

## Usage
1) In order to setup a brand new workspace, navigate to a clean folder and run `bpg setup_workspace`. This will copy in
a directory with sample technology information, and a new file called `sourceme.sh`
2) Next run `source sourceme.sh` to set up all of the environment variables needed. This soruce file assumes that you 
are using a bash/sh/zsh shell.
3) At this point any layout generator can be run by executing `python <PATH TO PYTHONFILE>`

For more information check out the [getting started guide](https://bpg.readthedocs.io/en/latest/getting_started/root.html)


## Contributing
We'd love your help in building and improving BPG! Please create an issue and contact Pavan at 
pvnbhargava@berkeley.edu before sending your first pull request. Please make sure to run the test suite (run_tests.py)
in the Photonics_Dev repo prior to making your pull request.

## Credits
Thanks to [Sidney Buchbinder](https://github.com/sbuchbinder),
[Ruocheng Wang](https://github.com/Ruocheng-Wang),
and [Brian Sun](https://github.com/bsun598) for building many of the core features in BPG!
