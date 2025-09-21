#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup

DESCRIPTION = \
    'Python scripts to perform lung segmentation on a CT scan and view the output using OpenGL'

INSTALL_REQUIRES = [
    'click', 'euclid3', 'numpy', 'opencv-python', 'pydicom', 'pyglet', 'scikit-image', 'SimpleITK'
]


setup(name='Lung Segmentation Tool',
      packages=['lung_segmentation_tool'],
      url='https://github.com/tristanpenman/lung-segmentation-tool',
      description=DESCRIPTION,
      install_requires=INSTALL_REQUIRES,
      entry_points={
          'console_scripts': [
              'lung-segmentation-tool=lung_segmentation_tool.cli:main',
          ],
      },
      license='MIT'
      )
