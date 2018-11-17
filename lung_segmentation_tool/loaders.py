# -*- coding: utf-8 -*-

import os
import numpy as np
import pydicom
import SimpleITK as sitk


def get_pixels_in_hounsfield_units(slices):
    image = np.stack([s.pixel_array for s in slices])
    image = image.astype(np.int16)
    image[image == -2000] = 0

    for slice_number in range(len(slices)):
        intercept = slices[slice_number].RescaleIntercept
        slope = slices[slice_number].RescaleSlope
        if slope != 1:
            image[slice_number] = slope * image[slice_number].astype(np.float64)
            image[slice_number] = image[slice_number].astype(np.int16)
        image[slice_number] += np.int16(intercept)

    return np.array(image, dtype=np.int16)


def load_dicom_files(scan_path):
    # Read all slices in the given directory
    slices = [pydicom.read_file(os.path.join(scan_path, s)) for s in os.listdir(scan_path)]
    slices.sort(key=lambda x: float(x.ImagePositionPatient[2]))
    # Infer slice thickness...
    try:
        # Based on distance between ImagePositionPatient z-value for first two slices
        slice_thickness = np.abs(slices[0].ImagePositionPatient[2] -
                                 slices[1].ImagePositionPatient[2])
    except (AttributeError, IndexError):
        # Fallback to SliceLocation if ImagePositionPatient z-value is not available
        slice_thickness = np.abs(slices[0].SliceLocation - slices[1].SliceLocation)
    spacing = [slice_thickness, slices[0].PixelSpacing[0], slices[0].PixelSpacing[1]]
    return slices, spacing, slices[0].Rows, slices[0].Columns


def load_mhd_file(scan_path):
    itk_img = sitk.ReadImage(scan_path)
    img_array = sitk.GetArrayFromImage(itk_img)
    size = itk_img.GetSize()
    return img_array, np.array(itk_img.GetSpacing())[::-1], size[1], size[0]


def normalize(image):
    min_bound = -1000.0
    max_bound = 400.0
    image = (image - min_bound) / (max_bound - min_bound)
    image[image > 1] = 1.
    image[image < 0] = 0.
    return image
