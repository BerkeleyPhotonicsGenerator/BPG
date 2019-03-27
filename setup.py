from distutils.core import setup


setup(name='BPG',
      version='0.8.1',
      description='Berkeley Photonics Generator',
      install_requires=[
          'setuptools>=18.5',
          'PyYAML>=4.2b1',
          'numpy>=1.10',
          'pytest',
          'memory_profiler>=0.54.0',
      ],
      url='https://github.com/pvnbhargava/BPG',
      packages=['BPG'],
      scripts=['BPG/bpg']
      )
