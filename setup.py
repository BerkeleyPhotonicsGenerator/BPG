from distutils.core import setup


setup(name='BPG',
      version='0.0.1',
      description='Berkeley Photonics Generator',
      install_requires=[
          'setuptools>=18.5',
          'PyYAML>=3.11',
          'numpy>=1.10',
          'pytest',
          'memory_profiler>=0.54.0',
      ],
      url='https://github.com/pvnbhargava/BPG',
      packages=['BPG']
      )
