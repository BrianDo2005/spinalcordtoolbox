#!/usr/bin/env python
#########################################################################################
#
# Calculate b-value.
#
# N.B. SI unit for gyromagnetic ratio is radian per second per tesla, therefore need to multiply by 2pi.
#
# ---------------------------------------------------------------------------------------
# Copyright (c) 2013 Polytechnique Montreal <www.neuro.polymtl.ca>
# Authors: Julien Cohen-Adad
# Modified: 2014-07-10
#
# About the license: see the file LICENSE.TXT
#########################################################################################


import sys
import os
import getopt
import math


# main
#=======================================================================================================================
def main():

    # Initialization
    GYRO = float(42.576 * 10 ** 6) # gyromagnetic ratio (in Hz.T^-1)
    gradamp = []
    bigdelta = []
    smalldelta = []

    # Check input parameters
    try:
        opts, args = getopt.getopt(sys.argv[1:],'hg:b:d:')
    except getopt.GetoptError:
        usage()
    for opt, arg in opts:
        if opt == '-h':
            usage()
        elif opt in ('-g'):
            gradamp = float(arg)
        elif opt in ('-b'):
            bigdelta = float(arg)
        elif opt in ('-d'):
            smalldelta = float(arg)

    # display usage if a mandatory argument is not provided
    if gradamp == [] or bigdelta == [] or smalldelta == []:
        usage()

    # print arguments
    print '\nCheck parameters:'
    print '  gradient amplitude ..... '+str(gradamp*1000)+' mT/m'
    print '  big delta .............. '+str(bigdelta*1000)+' ms'
    print '  small delta ............ '+str(smalldelta*1000)+' ms'
    print '  gyromagnetic ratio ..... '+str(GYRO)+' Hz/T'
    print ''

    bvalue = ( 2 * math.pi * GYRO * gradamp * smalldelta ) ** 2 * (bigdelta - smalldelta/3)

    print 'b-value = '+str(bvalue / 10**6)+' mm^2/s\n'
    return bvalue




# Print usage
# ==========================================================================================
def usage():
    print '\n' \
        ''+os.path.basename(__file__)+'\n' \
        '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n' \
        'Part of the Spinal Cord Toolbox <https://sourceforge.net/projects/spinalcordtoolbox>\n' \
        '\n'\
        'DESCRIPTION\n' \
        '  Calculate b-value (in mm^2/s).\n' \
        '\n' \
        'USAGE\n' \
        '  '+os.path.basename(__file__)+' -g <gradamp> -b <bigdelta> -d <smalldelta>\n' \
        '\n' \
        'MANDATORY ARGUMENTS\n' \
        '  -g <gradamp>      Amplitude of diffusion gradients (in T/m)\n' \
        '  -b <bigdelta>     Big delta: time between both diffusion gradients (in s)\n' \
        '  -d <smalldelta>   Small delta: duration of each diffusion gradient (in s)\n' \
        '\n' \
        'OPTIONAL ARGUMENTS\n' \
        '  -h                help. Show this message\n' \
        '\n'\
        'EXAMPLE\n' \
        '  '+os.path.basename(__file__)+' -i segmentation.nii \n'

    # exit program
    sys.exit(2)



#=======================================================================================================================
# Start program
#=======================================================================================================================
if __name__ == "__main__":
    # call main function
    main()
