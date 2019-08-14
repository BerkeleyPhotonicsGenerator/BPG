from distutils.core import setup


setup(name='BPG',
      version='0.8.5',
      description='Berkeley Photonics Generator',
      install_requires=[
          'setuptools>=18.5',
          'PyYAML>=5.1',
          'numpy>=1.10',
          'pytest>=4',
          'matplotlib>=3',
          'gdspy>=1.4',
          'scipy>=1.1.0',
          'memory_profiler>=0.54.0',
          'Jinja2>=2.10.1',
      ],
      url='https://github.com/pvnbhargava/BPG',
      packages=['BPG'],
      scripts=['BPG/bpg']
      )
