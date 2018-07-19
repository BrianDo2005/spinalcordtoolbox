#!/usr/bin/env python
# -*- coding: utf-8
# Functions processing segmentation data

import os, math
import numpy as np
import sct_utils as sct
from sct_image import Image, set_orientation
from sct_straighten_spinalcord import smooth_centerline
import msct_shape
from msct_types import Centerline
from spinalcordtoolbox.centerline import optic
from spinalcordtoolbox.metrics import average_per_slice_or_level

# on v3.2.2 and earlier, the following volumes were output by default, which was a waste of time (people don't use it)
OUTPUT_CSA_VOLUME = 0
OUTPUT_ANGLE_VOLUME = 0


def compute_shape(im_seg, remove_temp_files=1, verbose=1):
    """
    This function characterizes the shape of the spinal cord, based on the segmentation
    Shape properties are computed along the spinal cord and averaged per z-slices.
    Option is to provide intervertebral disks to average shape properties over vertebral levels (fname_discs).
    WARNING: the segmentation needs to be binary.
    """
    shape_properties = msct_shape.compute_properties_along_centerline(im_seg=im_seg,
                                                                      smooth_factor=0.0,
                                                                      interpolation_mode=0,
                                                                      remove_temp_files=remove_temp_files,
                                                                      verbose=verbose)
    # TODO: when switching to Python3, replace iteritems() by items()
    headers = []
    metrics = []
    for key, value in shape_properties.iteritems():
        # Making sure all entries added to metrics have results
        if not value == []:
            headers.append(key)
            metrics.append(np.array(value))
    return metrics, headers


def compute_shape_from_file(fname_segmentation, slices='', vert_levels='', fname_vert_levels='', perslice=0, perlevel=0,
                  file_out='shape', overwrite=0, remove_temp_files=1, verbose=1):
    """
    This function is a wrapper for compute_shape()
    """
    im_seg = Image(fname_segmentation)
    metrics, headers = compute_shape(im_seg, remove_temp_files=1, verbose=1)
    # write output file
    average_per_slice_or_level(metrics, header=headers,
                               slices=slices, perslice=perslice, vert_levels=vert_levels, perlevel=perlevel,
                               fname_vert_levels=fname_vert_levels, file_out=file_out, overwrite=overwrite)


def compute_length(fname_segmentation, remove_temp_files, output_folder, overwrite, slices, vert_levels,
                   fname_vertebral_labeling='', verbose=0):
    from math import sqrt

    # Extract path, file and extension
    fname_segmentation = os.path.abspath(fname_segmentation)
    path_data, file_data, ext_data = sct.extract_fname(fname_segmentation)

    path_tmp = sct.tmp_create(basename="process_segmentation", verbose=verbose)

    # copy files into tmp folder
    sct.printv('cp ' + fname_segmentation + ' ' + path_tmp)
    sct.copy(fname_segmentation, path_tmp)

    if slices or vert_levels:
        # check if vertebral labeling file exists
        sct.check_file_exist(fname_vertebral_labeling)
        path_vert, file_vert, ext_vert = sct.extract_fname(fname_vertebral_labeling)
        sct.printv('cp ' + fname_vertebral_labeling + ' ' + path_tmp)
        sct.copy(fname_vertebral_labeling, path_tmp)
        fname_vertebral_labeling = file_vert + ext_vert

    # go to tmp folder
    curdir = os.getcwd()
    os.chdir(path_tmp)

    # Change orientation of the input centerline into RPI
    sct.printv('\nOrient centerline to RPI orientation...', param.verbose)
    im_seg = Image(file_data + ext_data)
    fname_segmentation_orient = 'segmentation_rpi' + ext_data
    im_seg_orient = set_orientation(im_seg, 'RPI')
    im_seg_orient.setFileName(fname_segmentation_orient)
    im_seg_orient.save()

    # Get dimension
    sct.printv('\nGet dimensions...', param.verbose)
    nx, ny, nz, nt, px, py, pz, pt = im_seg_orient.dim
    sct.printv('.. matrix size: ' + str(nx) + ' x ' + str(ny) + ' x ' + str(nz), param.verbose)
    sct.printv('.. voxel size:  ' + str(px) + 'mm x ' + str(py) + 'mm x ' + str(pz) + 'mm', param.verbose)

    # smooth segmentation/centerline
    x_centerline_fit, y_centerline_fit, z_centerline, x_centerline_deriv, y_centerline_deriv, z_centerline_deriv = smooth_centerline(
        fname_segmentation_orient, nurbs_pts_number=3000, phys_coordinates=False, all_slices=True, algo_fitting='nurbs',
        verbose=verbose)

    # average csa across vertebral levels or slices if asked (flag -z or -l)
    if slices or vert_levels:
        warning = ''
        if vert_levels and not fname_vertebral_labeling:
            sct.printv(
                '\nERROR: You asked for specific vertebral levels (option -vert) but you did not provide any vertebral labeling file (see option -vertfile). The path to the vertebral labeling file is usually \"./label/template/PAM50_levels.nii.gz\". See usage.\n',
                1, 'error')

        elif vert_levels and fname_vertebral_labeling:

            # from sct_extract_metric import get_slices_matching_with_vertebral_levels
            sct.printv('Selected vertebral levels... ' + vert_levels)

            # convert the vertebral labeling file to RPI orientation
            im_vertebral_labeling = Image(fname_vertebral_labeling)
            im_vertebral_labeling.change_orientation(orientation='RPI')

            # get the slices corresponding to the vertebral levels
            # TODO: refactor with the new get_slices_from_vertebral_levels()
            # slices, vert_levels_list, warning = get_slices_matching_with_vertebral_levels(data_seg, vert_levels, im_vertebral_labeling.data, 1)
            slices, vert_levels_list, warning = get_slices_matching_with_vertebral_levels_based_centerline(vert_levels,
                                                                                                           im_vertebral_labeling.data,
                                                                                                           z_centerline)

        elif not vert_levels:
            vert_levels_list = []

        if slices is None:
            length = np.nan
            slices = '0'
            vert_levels_list = []

        else:
            # parse the selected slices
            slices_lim = slices.strip().split(':')
            slices_list = range(int(slices_lim[0]), int(slices_lim[-1]) + 1)
            sct.printv('Spinal cord length slices ' + str(slices_lim[0]) + ' to ' + str(slices_lim[-1]) + '...',
                       type='info')

            length = 0.0
            for i in range(len(x_centerline_fit) - 1):
                if z_centerline[i] in slices_list:
                    length += sqrt(((x_centerline_fit[i + 1] - x_centerline_fit[i]) * px) ** 2 + (
                            (y_centerline_fit[i + 1] - y_centerline_fit[i]) * py) ** 2 + (
                                           (z_centerline[i + 1] - z_centerline[i]) * pz) ** 2)

        sct.printv('\nLength of the segmentation = ' + str(round(length, 2)) + ' mm\n', verbose, 'info')

        # write result into output file
        save_results(os.path.join(output_folder, 'length'), overwrite, fname_segmentation, 'length',
                     '(in mm)', length, np.nan, slices, actual_vert=vert_levels_list,
                     warning_vert_levels=warning)

    elif (not (slices or vert_levels)) and (overwrite == 1):
        sct.printv(
            'WARNING: Flag \"-overwrite\" is only available if you select (a) slice(s) or (a) vertebral level(s) (flag -z or -vert) ==> CSA estimation per slice will be output in .csv files only.',
            type='warning')
        length = np.nan

    else:
        # compute length of full centerline
        length = 0.0
        for i in range(len(x_centerline_fit) - 1):
            length += sqrt(((x_centerline_fit[i + 1] - x_centerline_fit[i]) * px) ** 2 + (
                    (y_centerline_fit[i + 1] - y_centerline_fit[i]) * py) ** 2 + (
                                   (z_centerline[i + 1] - z_centerline[i]) * pz) ** 2)

        sct.printv('\nLength of the segmentation = ' + str(round(length, 2)) + ' mm\n', verbose, 'info')
        # write result into output file
        save_results(os.path.join(output_folder, 'length'), overwrite, fname_segmentation, 'length', '(in mm)', length,
                     np.nan,
                     slices, actual_vert=[], warning_vert_levels='')

    # come back
    os.chdir(curdir)

    # Remove temporary files
    if remove_temp_files:
        sct.printv('\nRemove temporary files...', verbose)
        sct.rmtree(path_tmp)

    return length


def extract_centerline(fname_segmentation, remove_temp_files, verbose=0, algo_fitting='hanning', type_window='hanning',
                       window_length=80, use_phys_coord=True, file_out='centerline'):
    """
    Extract centerline from a binary or weighted segmentation by computing the center of mass. Create centerline
    coordinates (.csv), image with one pixel per slice (.nii.gz) and JIM-compatible ROI file (.roi)
    :param fname_segmentation:
    :param remove_temp_files:
    :param verbose:
    :param algo_fitting:
    :param type_window:
    :param window_length:
    :param use_phys_coord: TODO: Explain the pros/cons of use_phys_coord.
    :param file_out:
    :return: None
    """
    # TODO: centerline coordinate should have the same orientation as the input image
    # TODO: no need for unecessary i/o. Everything could be done in RAM

    # Open segmentation volume
    im_seg = Image(fname_segmentation)
    # Change orientation
    native_orientation = im_seg.change_orientation('RPI')
    # Save as temp file
    path_tmp = sct.tmp_create()
    fname_tmp_seg = os.path.join(path_tmp, 'fname_tmp_seg.nii.gz')
    im_seg.setFileName(fname_tmp_seg)
    im_seg.save()
    data = im_seg.data

    # extract centerline and smooth it
    if use_phys_coord:
        # fit centerline, smooth it and return the first derivative (in physical space)
        x_centerline_fit, y_centerline_fit, z_centerline, \
        x_centerline_deriv, y_centerline_deriv, z_centerline_deriv = smooth_centerline(
            fname_tmp_seg, algo_fitting=algo_fitting, type_window=type_window, window_length=window_length,
            nurbs_pts_number=3000, phys_coordinates=True, verbose=verbose, all_slices=False)
        centerline = Centerline(x_centerline_fit, y_centerline_fit, z_centerline, x_centerline_deriv,
                                y_centerline_deriv, z_centerline_deriv)

        # average centerline coordinates over slices of the image (floating point)
        x_centerline_fit_rescorr, y_centerline_fit_rescorr, z_centerline_rescorr, \
        x_centerline_deriv_rescorr, y_centerline_deriv_rescorr, z_centerline_deriv_rescorr = \
            centerline.average_coordinates_over_slices(im_seg)

        # compute z_centerline in image coordinates (discrete)
        voxel_coordinates = im_seg.transfo_phys2pix(
            [[x_centerline_fit_rescorr[i], y_centerline_fit_rescorr[i], z_centerline_rescorr[i]] for i in
             range(len(z_centerline_rescorr))])
        x_centerline_voxel = [coord[0] for coord in voxel_coordinates]
        y_centerline_voxel = [coord[1] for coord in voxel_coordinates]
        z_centerline_voxel = [coord[2] for coord in voxel_coordinates]

    else:
        # fit centerline, smooth it and return the first derivative (in voxel space but FITTED coordinates)
        x_centerline_voxel, y_centerline_voxel, z_centerline_voxel, \
        x_centerline_deriv, y_centerline_deriv, z_centerline_deriv = smooth_centerline(
            'segmentation_RPI.nii.gz', algo_fitting=algo_fitting, type_window=type_window, window_length=window_length,
            nurbs_pts_number=3000, phys_coordinates=False, verbose=verbose, all_slices=True)

    if verbose == 2:
        # TODO: code below does not work
        import matplotlib.pyplot as plt

        # Creation of a vector x that takes into account the distance between the labels
        nz_nonz = len(z_centerline_voxel)
        x_display = [0 for i in range(x_centerline_voxel.shape[0])]
        y_display = [0 for i in range(y_centerline_voxel.shape[0])]
        for i in range(0, nz_nonz, 1):
            x_display[int(z_centerline_voxel[i] - z_centerline_voxel[0])] = x_centerline[i]
            y_display[int(z_centerline_voxel[i] - z_centerline_voxel[0])] = y_centerline[i]

        plt.figure(1)
        plt.subplot(2, 1, 1)
        plt.plot(z_centerline_voxel, x_display, 'ro')
        plt.plot(z_centerline_voxel, x_centerline_voxel)
        plt.xlabel("Z")
        plt.ylabel("X")
        plt.title("x and x_fit coordinates")

        plt.subplot(2, 1, 2)
        plt.plot(z_centerline_voxel, y_display, 'ro')
        plt.plot(z_centerline_voxel, y_centerline_voxel)
        plt.xlabel("Z")
        plt.ylabel("Y")
        plt.title("y and y_fit coordinates")
        plt.show()

    # Create an image with the centerline
    # TODO: write the center of mass, not the discrete image coordinate (issue #1938)
    im_centerline = im_seg.copy()
    data_centerline = im_centerline.data * 0
    # Find z-boundaries above which and below which there is no non-null slices
    min_z_index, max_z_index = int(round(min(z_centerline_voxel))), int(round(max(z_centerline_voxel)))
    # loop across slices and set centerline pixel to value=1
    for iz in range(min_z_index, max_z_index + 1):
        data_centerline[int(round(x_centerline_voxel[iz - min_z_index])),
                        int(round(y_centerline_voxel[iz - min_z_index])),
                        int(iz)] = 1
    # assign data to centerline image
    im_centerline.data = data_centerline
    # reorient centerline to native orientation
    im_centerline.change_orientation(native_orientation)
    # save nifti volume
    fname_centerline = file_out + '.nii.gz'
    im_centerline.setFileName(fname_centerline)
    im_centerline.changeType('uint8')
    im_centerline.save()
    # display stuff
    sct.display_viewer_syntax([fname_segmentation, fname_centerline], colormaps=['gray', 'green'])

    # output csv with centerline coordinates
    fname_centerline_csv = file_out + '.csv'
    f_csv = open(fname_centerline_csv, 'w')
    f_csv.write('x,y,z\n')  # csv header
    for i in range(min_z_index, max_z_index + 1):
        f_csv.write("%d,%d,%d\n" % (int(i),
                                    x_centerline_voxel[i - min_z_index],
                                    y_centerline_voxel[i - min_z_index]))
    f_csv.close()
    # TODO: display open syntax for csv

    # create a .roi file
    fname_roi_centerline = optic.centerline2roi(fname_image=fname_centerline,
                                                folder_output='./',
                                                verbose=verbose)

    # Remove temporary files
    if remove_temp_files:
        sct.printv('\nRemove temporary files...', verbose)
        sct.rmtree(path_tmp)


def compute_csa(im_seg, verbose, remove_temp_files, algo_fitting='hanning', type_window='hanning', window_length=80,
                angle_correction=True, use_phys_coord=True):
    """
    Compute CSA.
    Note: segmentation can be binary or weighted for partial volume effect.
    :param im_seg:
    :param verbose:
    :param remove_temp_files:
    :param algo_fitting:
    :param type_window:
    :param window_length:
    :param angle_correction:
    :param use_phys_coord:
    :return:
    """
    # TODO: do everything in RAM instead of adding unecessary i/o. For that we need a wrapper for smooth_centerline()
    # create temporary folder
    path_tmp = sct.tmp_create()
    # change orientation to RPI
    im_seg.change_orientation('RPI')
    nx, ny, nz, nt, px, py, pz, pt = im_seg.dim
    fname_seg = os.path.join(path_tmp, 'segmentation_RPI.nii.gz')
    im_seg.setFileName(fname_seg)
    im_seg.save()

    # # Extract min and max index in Z direction
    data_seg = im_seg.data
    X, Y, Z = (data_seg > 0).nonzero()
    min_z_index, max_z_index = min(Z), max(Z)

    # if angle correction is required, get segmentation centerline
    # Note: even if angle_correction=0, we should run the code below so that z_centerline_voxel is defined (later used
    # with option -vert). See #1791
    if use_phys_coord:
        # fit centerline, smooth it and return the first derivative (in physical space)
        x_centerline_fit, y_centerline_fit, z_centerline, x_centerline_deriv, y_centerline_deriv, z_centerline_deriv = \
            smooth_centerline(fname_seg, algo_fitting=algo_fitting, type_window=type_window,
                              window_length=window_length, nurbs_pts_number=3000, phys_coordinates=True,
                              verbose=verbose, all_slices=False)
        centerline = Centerline(x_centerline_fit, y_centerline_fit, z_centerline, x_centerline_deriv,
                                y_centerline_deriv, z_centerline_deriv)

        # average centerline coordinates over slices of the image
        x_centerline_fit_rescorr, y_centerline_fit_rescorr, z_centerline_rescorr, x_centerline_deriv_rescorr, \
        y_centerline_deriv_rescorr, z_centerline_deriv_rescorr = centerline.average_coordinates_over_slices(im_seg)

        # compute Z axis of the image, in physical coordinate
        axis_X, axis_Y, axis_Z = im_seg.get_directions()

        # compute z_centerline in image coordinates for usage in vertebrae mapping
        z_centerline_voxel = [coord[2] for coord in im_seg.transfo_phys2pix(
            [[x_centerline_fit_rescorr[i], y_centerline_fit_rescorr[i], z_centerline_rescorr[i]] for i in
             range(len(z_centerline_rescorr))])]

    else:
        # fit centerline, smooth it and return the first derivative (in voxel space but FITTED coordinates)
        x_centerline_fit, y_centerline_fit, z_centerline, x_centerline_deriv, y_centerline_deriv, z_centerline_deriv = \
            smooth_centerline(fname_seg, algo_fitting=algo_fitting, type_window=type_window, window_length=window_length,
            nurbs_pts_number=3000, phys_coordinates=False, verbose=verbose, all_slices=True)

        # correct centerline fitted coordinates according to the data resolution
        x_centerline_fit_rescorr, y_centerline_fit_rescorr, z_centerline_rescorr, \
        x_centerline_deriv_rescorr, y_centerline_deriv_rescorr, z_centerline_deriv_rescorr = \
            x_centerline_fit * px, y_centerline_fit * py, z_centerline * pz, \
            x_centerline_deriv * px, y_centerline_deriv * py, z_centerline_deriv * pz

        axis_Z = [0.0, 0.0, 1.0]

    # Compute CSA
    sct.printv('\nCompute CSA...', verbose)

    # Empty arrays in which CSA for each z slice will be stored
    csa = np.zeros(max_z_index - min_z_index + 1)
    angles = np.zeros(max_z_index - min_z_index + 1)

    for iz in range(min_z_index, max_z_index + 1):
        if angle_correction:
            # in the case of problematic segmentation (e.g., non continuous segmentation often at the extremities), display a warning but do not crash
            try:
                # normalize the tangent vector to the centerline (i.e. its derivative)
                tangent_vect = normalize(np.array(
                    [x_centerline_deriv_rescorr[iz - min_z_index], y_centerline_deriv_rescorr[iz - min_z_index],
                     z_centerline_deriv_rescorr[iz - min_z_index]]))

            except IndexError:
                sct.printv(
                    'WARNING: Your segmentation does not seem continuous, which could cause wrong estimations at the problematic slices. Please check it, especially at the extremities.',
                    type='warning')

            # compute the angle between the normal vector of the plane and the vector z
            angle = np.arccos(np.vdot(tangent_vect, axis_Z))
        else:
            angle = 0.0

        # compute the number of voxels, assuming the segmentation is coded for partial volume effect between 0 and 1.
        number_voxels = np.sum(data_seg[:, :, iz])

        # compute CSA, by scaling with voxel size (in mm) and adjusting for oblique plane
        csa[iz - min_z_index] = number_voxels * px * py * np.cos(angle)
        angles[iz - min_z_index] = math.degrees(angle)

    # TODO: DEAL WITH THE STUFF BELOW
    # if OUTPUT_CSA_VOLUME:
    #     # output volume of csa values
    #     # TODO: only output if asked for (people don't use it)
    #     sct.printv('\nCreate volume of CSA values...', verbose)
    #     data_csa = data_seg.astype(np.float32, copy=False)
    #     # loop across slices
    #     for iz in range(min_z_index, max_z_index + 1):
    #         # retrieve seg pixels
    #         x_seg, y_seg = (data_csa[:, :, iz] > 0).nonzero()
    #         seg = [[x_seg[i], y_seg[i]] for i in range(0, len(x_seg))]
    #         # loop across pixels in segmentation
    #         for i in seg:
    #             # replace value with csa value
    #             data_csa[i[0], i[1], iz] = csa[iz - min_z_index]
    #     # replace data
    #     im_seg.data = data_csa
    #     # set original orientation
    #     # TODO: FIND ANOTHER WAY!!
    #     # im_seg.change_orientation(orientation) --> DOES NOT WORK!
    #     # set file name -- use .gz because faster to write
    #     im_seg.setFileName('csa_volume_RPI.nii.gz')
    #     im_seg.changeType('float32')
    #     # save volume
    #     im_seg.save()
    #     # get orientation of the input data
    #     im_seg_original = Image('segmentation.nii.gz')
    #     orientation = im_seg_original.orientation
    #     sct.run(['sct_image', '-i', 'csa_volume_RPI.nii.gz', '-setorient', orientation, '-o',
    #              'csa_volume_in_initial_orientation.nii.gz'])
    #     sct.generate_output_file(os.path.join(path_tmp, "csa_volume_in_initial_orientation.nii.gz"),
    #                              os.path.join(output_folder,
    #                                           'csa_image.nii.gz'))  # extension already included in name_output
    #
    # if OUTPUT_ANGLE_VOLUME:
    #     # output volume of angle values
    #     # TODO: only output if asked for (people don't use it)
    #     sct.printv('\nCreate volume of angle values...', verbose)
    #     data_angle = data_seg.astype(np.float32, copy=False)
    #     # loop across slices
    #     for iz in range(min_z_index, max_z_index + 1):
    #         # retrieve seg pixels
    #         x_seg, y_seg = (data_angle[:, :, iz] > 0).nonzero()
    #         seg = [[x_seg[i], y_seg[i]] for i in range(0, len(x_seg))]
    #         # loop across pixels in segmentation
    #         for i in seg:
    #             # replace value with csa value
    #             data_angle[i[0], i[1], iz] = angles[iz - min_z_index]
    #     # replace data
    #     im_seg.data = data_angle
    #     # set original orientation
    #     # TODO: FIND ANOTHER WAY!!
    #     # im_seg.change_orientation(orientation) --> DOES NOT WORK!
    #     # set file name -- use .gz because faster to write
    #     im_seg.setFileName('angle_volume_RPI.nii.gz')
    #     im_seg.changeType('float32')
    #     # save volume
    #     im_seg.save()
    #     # get orientation of the input data
    #     im_seg_original = Image('segmentation.nii.gz')
    #     orientation = im_seg_original.orientation
    #     sct.run(['sct_image', '-i', 'angle_volume_RPI.nii.gz', '-setorient', orientation, '-o',
    #              'angle_volume_in_initial_orientation.nii.gz'])
    #     sct.generate_output_file(os.path.join(path_tmp, "angle_volume_in_initial_orientation.nii.gz"),
    #                              os.path.join(output_folder,
    #                                           'angle_image.nii.gz'))  # extension already included in name_output

    # Remove temporary files
    if remove_temp_files:
        sct.printv('\nRemove temporary files...')
        sct.rmtree(path_tmp)

    # prepare output
    metrics = [csa, angles]
    headers = ['CSA [mm^2]','Angle between cord and S-I direction [deg]']
    return metrics, headers



def compute_csa_from_file(fname_segmentation, overwrite, verbose, remove_temp_files, slices, vert_levels,
                          fname_vert_levels='', perslice=0, perlevel=0, algo_fitting='hanning',
                          type_window='hanning', window_length=80, angle_correction=True, use_phys_coord=True,
                          file_out='csa'):
    """
    Wrapper for compute_csa()
    :param fname_segmentation:
    :param overwrite:
    :param verbose:
    :param remove_temp_files:
    :param slices:
    :param vert_levels:
    :param fname_vertebral_labeling:
    :param perslice:
    :param perlevel:
    :param algo_fitting:
    :param type_window:
    :param window_length:
    :param angle_correction:
    :param use_phys_coord:
    :param file_out:
    :return:
    """
    im_seg = Image(fname_segmentation)
    metrics, headers = compute_csa(im_seg, verbose, remove_temp_files, algo_fitting=algo_fitting,
                                   type_window=type_window, window_length=window_length,
                                   angle_correction=angle_correction, use_phys_coord=use_phys_coord)

    # write output file
    average_per_slice_or_level(metrics, header=headers,
                               slices=slices, perslice=perslice, vert_levels=vert_levels, perlevel=perlevel,
                               fname_vert_levels=fname_vert_levels, file_out=file_out, overwrite=overwrite)


def label_vert(fname_seg, fname_label, fname_out='', verbose=1):
    """
    Label segmentation using vertebral labeling information. No orientation expected.
    :param fname_seg: file name of segmentation.
    :param fname_label: file name for a labelled segmentation that will be used to label the input segmentation
    :param fname_out: file name of the output labeled segmentation. If empty, will add suffix "_labeled" to fname_seg
    :param verbose:
    :return:
    """
    # Open labels
    im_disc = Image(fname_label)
    # Change the orientation to RPI so that the z axis corresponds to the superior-to-inferior axis
    im_disc.change_orientation('RPI')
    # retrieve all labels
    coord_label = im_disc.getNonZeroCoordinates()
    # compute list_disc_z and list_disc_value
    list_disc_z = []
    list_disc_value = []
    for i in range(len(coord_label)):
        list_disc_z.insert(0, coord_label[i].z)
        # '-1' to use the convention "disc labelvalue=3 ==> disc C2/C3"
        list_disc_value.insert(0, coord_label[i].value - 1)

    list_disc_value = [x for (y, x) in sorted(zip(list_disc_z, list_disc_value), reverse=True)]
    list_disc_z = [y for (y, x) in sorted(zip(list_disc_z, list_disc_value), reverse=True)]
    # label segmentation
    from sct_label_vertebrae import label_segmentation
    label_segmentation(fname_seg, list_disc_z, list_disc_value, fname_out=fname_out, verbose=verbose)


# =======================================================================================================================
# Normalization
# =======================================================================================================================
def normalize(vect):
    norm = np.linalg.norm(vect)
    return vect / norm


# =======================================================================================================================
# Ellipse fitting for a set of data
# =======================================================================================================================
# http://nicky.vanforeest.com/misc/fitEllipse/fitEllipse.html
def Ellipse_fit(x, y):
    x = x[:, np.newaxis]
    y = y[:, np.newaxis]
    D = np.hstack((x * x, x * y, y * y, x, y, np.ones_like(x)))
    S = np.dot(D.T, D)
    C = np.zeros([6, 6])
    C[0, 2] = C[2, 0] = 2
    C[1, 1] = -1
    E, V = np.linalg.eig(np.dot(np.linalg.inv(S), C))
    n = np.argmax(np.abs(E))
    a = V[:, n]
    return a


# =======================================================================================================================
# Getting a and b parameter for fitted ellipse
# =======================================================================================================================
def ellipse_dim(a):
    b, c, d, f, g, a = a[1] / 2, a[2], a[3] / 2, a[4] / 2, a[5], a[0]
    up = 2 * (a * f * f + c * d * d + g * b * b - 2 * b * d * f - a * c * g)
    down1 = (b * b - a * c) * ((c - a) * np.sqrt(1 + 4 * b * b / ((a - c) * (a - c))) - (c + a))
    down2 = (b * b - a * c) * ((a - c) * np.sqrt(1 + 4 * b * b / ((a - c) * (a - c))) - (c + a))
    res1 = np.sqrt(up / down1)
    res2 = np.sqrt(up / down2)
    return np.array([res1, res2])


# =======================================================================================================================
# Detect edges of an image
# =======================================================================================================================
def edge_detection(f):
    img = Image.open(f)  # grayscale
    imgdata = np.array(img, dtype=float)
    G = imgdata
    # G = ndi.filters.gaussian_filter(imgdata, sigma)
    gradx = np.array(G, dtype=float)
    grady = np.array(G, dtype=float)

    mask_x = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]])

    mask_y = np.array([[1, 2, 1], [0, 0, 0], [-1, -2, -1]])

    width = img.size[1]
    height = img.size[0]

    for i in range(1, width - 1):
        for j in range(1, height - 1):
            px = np.sum(mask_x * G[(i - 1):(i + 1) + 1, (j - 1):(j + 1) + 1])
            py = np.sum(mask_y * G[(i - 1):(i + 1) + 1, (j - 1):(j + 1) + 1])
            gradx[i][j] = px
            grady[i][j] = py

    mag = scipy.hypot(gradx, grady)

    treshold = np.max(mag) * 0.9

    for i in range(width):
        for j in range(height):
            if mag[i][j] > treshold:
                mag[i][j] = 1
            else:
                mag[i][j] = 0

    return mag