# Berkeley Photonics Generator 
[![Build Status](https://dev.azure.com/pvnbhargava/BPG_CICD/_apis/build/status/BerkeleyPhotonicsGenerator.BPG?branchName=master)](https://dev.azure.com/pvnbhargava/BPG_CICD/_build/latest?definitionId=2&branchName=master)
The Berkeley Photonics Generator (BPG) is a Python framework that enables you to generate and simulate silicon photonics 
layout. BPG leverages the [BAG 2.0 framework](https://github.com/ucb-art/BAG_framework), and has similar syntax and 
file structure.

## Table of Contents
- [Documentation](#Documentation)
- [Installation](#Installation)
- [Usage](#Usage)
- [Contributing](#Contributing)
- [Credits](#Credits)

## Documentation
Once cloned, the most up to date BPG user manual can be found at `./BPG/docs/BPG_User_Manual.pdf`. Alternatively, you
can read it online [here](docs/BPG_User_Manual.pdf). A readthedocs website will be hosted once the repo is made public

## Installation
We highly recommend you use an [Anaconda](https://www.anaconda.com/distribution/) environment with a Python version 
greater than 3.6. BPG generally will not function with Python versions less than 3.6, and requires packages with 
C/C++ dependencies that are most easily installed using Anaconda.

Once Anaconda is set up, please run the following commands to install packages with C/C++ dependencies:
```bash
conda install numpy
conda install rtree
conda install shapely
```

Finally, actually install BPG with:
```bash
pip install bpg
```

BPG generally generates output layouts in the GDSII format. To view these layouts, we recommend you install and use the 
free open-source software package, [Klayout](https://klayout.de).

## Usage
1) In order to setup a brand new workspace, navigate to a clean folder and run `bpg setup_workspace`. This will copy in
a directory with sample technology information, and a new file called `sourceme.sh`
2) Next run `source sourceme.sh` to set up all of the environment variables needed. This soruce file assumes that you 
are using a bash/sh/zsh shell.
3) At this point any layout generator can be run by executing `python <PATH TO PYTHONFILE>`

BPG is based on the idea of creating parametrized layout generators. These layout generators (internally referred to 
as templates or masters) contain a generic procedural description of how to construct a device given a set 
of technology and device parameters. Every layout generator must subclass `BPG.PhotonicTemplateBase`. An example of a 
basic rectangular waveguide is provided in `BPG/examples/Waveguide.py`. You can find the implementation for PhotonicTemplateBase
in `BPG/template.py`

In order to use this template to generate a real GDS/LSF, we create a `BPG.PhotonicLayoutManager` instance, and pass it a specification
yaml file which describes what parameters to use. This design can then be exported directly into GDS with `BPG.PhotonicLayoutManager.generate_gds()`
or to Lumerical with `BPG.PhotonicLayoutManager.generate_lsf()` (after calling generate_flat_gds). You can find the implementation
of PhotonicLayoutManager in `BPG/layout_manager.py`

More detail and screenshots coming soon...

## Contributing
We'd love your help in building and improving BPG! Please create an issue and contact Pavan at 
pvnbhargava@berkeley.edu before sending your first pull request. Please make sure to run the test suite (run_tests.py)
in the Photonics_Dev repo prior to making your pull request.

## Credits
Thanks to [Sidney Buchbinder](https://github.com/sbuchbinder),
[Ruocheng Wang](https://github.com/Ruocheng-Wang),
and [Brian Sun](https://github.com/bsun598) for building many of the core features in BPG!
