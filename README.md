# Lung Segmentation Tool

## Overview

This package contains scripts to perform lung segmentation on a CT scan, and view the result using OpenGL.

The segmentation functions are based on a traditional CV-based algorithm, described in the [Kaggle DSB 2017 Tutorial](https://www.kaggle.com/c/data-science-bowl-2017#tutorial).

## Requirements

This package requires Python 3.

To get the source code and install dependencies:

    git clone git@github.com:tristanpenman/lung-segmentation-tool.git
    cd lung-segmentation-tool
    pip install -r requirements.txt

You may choose to install the package on your system:

    pip install .

## Usage

Included in this package is an executable script called `lung-segmentation-tool`, which can be used to load CT scans in MetaImage (.mhd) and DICOM (.dcm) format.

This tool can be launched from the command line, with options to configure the step size of the generated mesh:

    lung-segmentation-tool \
        --scan-path ${PATH_TO_SCAN} \
        --step-size 1

Choosing a larger step size will shorten the time taken to generate a mesh, at the cost of lower detail.

If you have cloned the git repository, but not installed the package, you may need to set your `PYTHONPATH` environment variable when running `lung-segmentation-tool`:

    PYTHONPATH=`pwd` ./bin/lung-segmentation-tool \
        --scan-path ${PATH_TO_SCAN} \
        --step-size 1

## Screenshot

Successfully loading and segmenting a CT scan will look something like this:

![Screenshot](screenshot.png)

On the left is the segmentation view. You can rotate and zoom using the left-mouse button and scroll-wheel.

On the top-right is the transverse view.

Below that are two views. On the left is the sagital view, and on the right is the frontal view.

Clicking and dragging on the transverse view will change slices shown on the views below it.

## Known issues and limitations

Interaction with the transverse, sagital and frontal views is limited.

Currently only the transverse view will respond to mouse events, changing the slices in the sagital and frontal views to be centered at the location that is selected.

The sagital and frontal views do not respond to mouse events at all.

The aim is add planes to the 3D segmented view, to show exactly which location in the scan has been selected via the 2D views.

## License

This code is licensed under the MIT License.

See the LICENSE file for more information.
