"""Helper functions for loading scan data."""

from pathlib import Path

import numpy as np
import pydicom
from pydicom.errors import InvalidDicomError
import SimpleITK


def load_dicom_files(scan_path):
    # Read all slices in the given directory
    slices = []
    for entry in Path(scan_path).iterdir():
        if not entry.is_file():
            continue
        try:
            dataset = pydicom.dcmread(str(entry))
        except InvalidDicomError:
            continue
        slices.append(dataset)

    if not slices:
        raise ValueError('No DICOM slices found in {}'.format(scan_path))

    def slice_sort_key(dataset):
        image_position = getattr(dataset, 'ImagePositionPatient', None)
        if image_position is not None:
            try:
                return float(image_position[2])
            except (IndexError, TypeError, ValueError):
                pass
        slice_location = getattr(dataset, 'SliceLocation', None)
        if slice_location is not None:
            try:
                return float(slice_location)
            except (TypeError, ValueError):
                pass
        return 0.0

    slices.sort(key=slice_sort_key)

    # Infer slice thickness...
    slice_thickness = None
    if len(slices) >= 2:
        image_position0 = getattr(slices[0], 'ImagePositionPatient', None)
        image_position1 = getattr(slices[1], 'ImagePositionPatient', None)
        if image_position0 is not None and image_position1 is not None:
            try:
                slice_thickness = float(np.abs(float(image_position0[2]) - float(image_position1[2])))
            except (IndexError, TypeError, ValueError):
                slice_thickness = None
        if slice_thickness is None:
            slice_location0 = getattr(slices[0], 'SliceLocation', None)
            slice_location1 = getattr(slices[1], 'SliceLocation', None)
            if slice_location0 is not None and slice_location1 is not None:
                try:
                    slice_thickness = float(np.abs(float(slice_location0) - float(slice_location1)))
                except (TypeError, ValueError):
                    slice_thickness = None

    if slice_thickness is None:
        raise ValueError('Unable to determine slice thickness for {}'.format(scan_path))

    pixel_spacing = getattr(slices[0], 'PixelSpacing', None)
    if pixel_spacing is None or len(pixel_spacing) < 2:
        raise ValueError('PixelSpacing metadata missing for {}'.format(scan_path))

    spacing = [slice_thickness, float(pixel_spacing[0]), float(pixel_spacing[1])]
    return slices, spacing, slices[0].Rows, slices[0].Columns


def load_mhd_file(scan_path):
    itk_img = SimpleITK.ReadImage(scan_path)
    img_array = SimpleITK.GetArrayFromImage(itk_img)
    size = itk_img.GetSize()
    return img_array, np.array(itk_img.GetSpacing())[::-1], size[1], size[0]
