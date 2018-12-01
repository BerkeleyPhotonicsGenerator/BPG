# Berkeley Photonics Generator 
The Berkeley Photonics Generator (BPG) is a Python framework that enables you to generate and simulate silicon photonics 
layout. BPG leverages the [BAG 2.0 framework](https://github.com/ucb-art/BAG_framework), and has similar syntax and 
file structure. BPG is primarily focused on enabling photonic simulation through Lumerical, but other open-source options will 
be added later.

## Table of Contents
- [Installation](#Installation)
- [Documentation](#Documentation)
- [Usage](#Usage)
- [Contributing](#Contributing)
- [Credits](#Credits)

## Installation
BPG is a plugin to BAG, and relies on it for many core functions. BAG requires a very specific environment setup; 
to get a compatible standalone development file structure with environmental variables, please install BPG through 
the [Photonics_Dev](https://github.com/pvnbhargava/Photonics_Dev) repository.

*NOTE!* progress is being made on removing the requirement for Photonics_Dev, so the submodule pointers may be out of date.
Please go into the BPG submodule and `git pull origin master` to get the latest version of the code.

## Documentation
Once cloned, the most up to date BPG user manual can be found at `./BPG/docs/BPG_User_Manual.pdf`. Alternatively, you
can read it online [here](docs/BPG_User_Manual.pdf). A readthedocs website will be hosted once the repo is made public

## Usage
1) In order to start BPG, a number of environmental variables must be setup:
```bash
cd Photonics_Dev
source workspace_setup/.bashrc
```
2) Next run `./start_bag.sh` to launch an ipython session with the proper python path.
3) Before creating your first layout generator, please run `run -i BPG/run_tests.py` to ensure that everything has been 
installed properly.
4) At this point any layout generator can be run by executing `run -i <PATH TO PYTHONFILE>`

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
