# -*- coding: utf-8 -*-

import os
import numpy as np
import pydicom
import SimpleITK as sitk


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
