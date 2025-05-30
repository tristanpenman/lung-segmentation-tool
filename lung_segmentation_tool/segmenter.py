# -*- coding: utf-8 -*-

import numpy as np

from skimage import measure


def generate_mesh_from_scan(binary_image, step_size):
    threshold = 0
    p = binary_image.transpose(2, 1, 0)
    return measure.marching_cubes(p, threshold, step_size=step_size)


def largest_label_volume(im, bg=-1):
    vals, counts = np.unique(im, return_counts=True)
    counts = counts[vals != bg]
    vals = vals[vals != bg]
    return vals[np.argmax(counts)] if counts.any() else None


def segment_lungs(image, fill_lung_structures=True):
    # Threshold so that 1 is background, 2 is lung structure
    binary_image = np.array(image > -320, dtype=np.int8)+1
    # Label connected regions of mask
    labels = measure.label(binary_image)
    # Pick voxel in corner to determine label for air
    background_label = labels[0, 0, 0]
    # Fill air around person in binary image
    binary_image[background_label == labels] = 2

    if fill_lung_structures:
        for i, axial_slice in enumerate(binary_image):
            # Back to 0s and 1s
            axial_slice = axial_slice - 1
            # Label connected regions in slice
            labeling = measure.label(axial_slice)
            # Find largest connected region, indicating presence of lung tissue
            l_max = largest_label_volume(labeling, bg=0)
            if l_max is not None:
                binary_image[i][labeling != l_max] = 1

    # Back to 0s and 1s; and invert
    binary_image -= 1
    binary_image = 1 - binary_image

    labels = measure.label(binary_image, background=0)
    l_max = largest_label_volume(labels, bg=0)
    if l_max is not None:
        binary_image[labels != l_max] = 0

    return binary_image
