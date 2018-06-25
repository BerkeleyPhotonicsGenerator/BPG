# Berkeley Photonics Generator 
The Berkeley Photonics Generator (BPG) is a Python framework that enables the generation and simulation of photonics layout

# Installation Instructions
gdspy is a required dependency for BPG to function. It is recommended that gdspy is installed as an editable installation:

```
cd Photonics_Dev/BPG/BPG
pip install -e gdspy
```

if gdspy successfully installs, it should be accessible anywhere in your python installation by running `import gdspy`

Similarly, BPG should be added as an editable installation via pip. Navigate to the Photonics_Dev folder and run:

```
cd Photonics_Dev
pip install -e BPG
```

If BPG successfully installs, it should be accessible anywhere in your python installation by running `import BPG` 
Whenever any changes are made to the BPG package via git, they will be made available immediately.

# Basic Usage Instructions
...