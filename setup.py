#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distutils.core import setup

DESCRIPTION = \
    'Python scripts to perform lung segmentation on a CT scan and view the output using OpenGL'

SCRIPTS = [
    'bin/lung-segmentation-tool'
]

REQUIRES = [
    'click', 'euclid3', 'numpy', 'opencv-python', 'pydicom', 'pyglet', 'scikit-image', 'SimpleITK'
]


setup(name='Lung Segmentation Tool',
      packages=['lung_segmentation_tool'],
      scripts=SCRIPTS,
      url='https://github.com/tristanpenman/lung-segmentation-tool',
      description=DESCRIPTION,
      requires=REQUIRES,
      license='MIT'
      )
