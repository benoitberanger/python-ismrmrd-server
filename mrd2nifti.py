# additional
import nibabel
import ismrmrd
import h5py
import numpy as np

# built-in
import argparse
import logging
import sys
import os

def main(args: argparse.Namespace) -> None:

    # create and fortmat a logger
    logging.basicConfig(
        level=logging.DEBUG,
        format='mrd2nifti:%(levelname)s:%(funcName)s: %(message)s'
       )
    logger = logging.getLogger(__name__)

    # check input file
    args.inputMRDh5 = os.path.expanduser(args.inputMRDh5)
    logger.info(f'Input .h5 MRD file : {args.inputMRDh5}')
    if not os.path.isfile(args.inputMRDh5):
        logger.error(f'Input .h5 MRD file does not exist')
        sys.exit(1)

    # prepare output file
    if args.outputNII is None:
        logger.info('no output nifti file specified, create one')
        args.outputNII = os.path.splitext(args.inputMRDh5)[0] + '.nii'
    logger.info(f'Output .nii file : {args.outputNII}')

    # open file, and explore it
    mrdFile = h5py.File(args.inputMRDh5)
    list_of_names = []
    mrdFile.visit(list_of_names.append)  # print the content recursively
    logger.info(f'h5 file content :\n{"\n".join(list_of_names)}')

    # fetch most recent group
    most_recent_dataset_name = list(mrdFile.keys())[-1]
    logger.warning('<LIMITATION> only process the most recent group')
    logger.info(f'most recent dataset: {most_recent_dataset_name}')

    # check for image_0 in the most recent group
    logger.warning('<LIMITATION> only try to process image_0')
    if 'image_0' in mrdFile.get(most_recent_dataset_name).keys():
        logger.info(f'image_0 found in {most_recent_dataset_name}')
        image_0 = mrdFile.get(most_recent_dataset_name).get('image_0')
    else:
        logger.critical(f'image_0 not in {most_recent_dataset_name}')
        mrdFile.close()
        sys.exit(1)

    # check for xml
    if 'xml' in mrdFile.get(most_recent_dataset_name).keys():
        logger.info(f'xml found in {most_recent_dataset_name}')
    else:
        logger.critical(f'xml not in {most_recent_dataset_name}')
        mrdFile.close()
        sys.exit(1)

    # check if image_0 has the correct subgroups
    image_0_keys = image_0.keys()
    if ('data' in image_0_keys) and ('header' in image_0_keys) and ('attributes' in image_0_keys):
        pass
    else:
        logger.critical(f'image_0 does not contain : data header attributes')
        mrdFile.close()
        sys.exit(1)

    mrdFile.close()

    mrdDataset = ismrmrd.Dataset(
        filename=args.inputMRDh5,
        dataset_name=most_recent_dataset_name,
        create_if_needed=False
    )
    groups = mrdDataset.list()

    # get MRD Header
    xml_header = mrdDataset.read_xml_header()
    xml_header = xml_header.decode("utf-8")
    mrdHeader = ismrmrd.xsd.CreateFromDocument(xml_header)

    # load image and print info
    mrdImage = mrdDataset.read_image('image_0', 0)
    mrdDataset.close()

    fieldOfView_mm_x = mrdHeader.encoding[0].reconSpace.fieldOfView_mm.x
    fieldOfView_mm_y = mrdHeader.encoding[0].reconSpace.fieldOfView_mm.y
    fieldOfView_mm_z = mrdHeader.encoding[0].reconSpace.fieldOfView_mm.z
    matrixSize_x     = mrdHeader.encoding[0].reconSpace.matrixSize.x
    matrixSize_y     = mrdHeader.encoding[0].reconSpace.matrixSize.y
    matrixSize_z     = mrdHeader.encoding[0].reconSpace.matrixSize.z
    voxelSize_mm_x   = fieldOfView_mm_x / matrixSize_x
    voxelSize_mm_y   = fieldOfView_mm_y / matrixSize_y
    voxelSize_mm_z   = fieldOfView_mm_z / matrixSize_z

    image_info = {
        'protocolName'     : mrdHeader.measurementInformation.protocolName,
        'fieldOfView_XYZmm': [fieldOfView_mm_x, fieldOfView_mm_y, fieldOfView_mm_z],
        'matrixSize_XYZ'   : [    matrixSize_x,     matrixSize_y,     matrixSize_z],
        'voxelSize_XYZmm'  : [  voxelSize_mm_x,   voxelSize_mm_y,   voxelSize_mm_z],
    }
    info_str = [f"{key}: {value}"  for key,value in image_info.items()]
    logger.info(f'image info :\n{"\n".join(info_str)}')

    logger.warning('!!! nifti affine WRONG : orientation is wrong, but the voxel size is. !!!')
    affine = np.diag([voxelSize_mm_x, voxelSize_mm_y, voxelSize_mm_z, 1])

    # [cha z y x] -> [x y z]
    data_chaZYX = mrdImage.data
    data_ZYX    = data_chaZYX[0,:,:,:]
    data_XYZ    = data_ZYX.transpose((2,1,0))
    data        = data_XYZ
    niiFile = nibabel.Nifti1Image(dataobj=data, affine=affine)
    nibabel.save(img=niiFile,filename=args.outputNII)
    logger.info(f'nifti file written : {args.outputNII}')

    sys.exit(0)

if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='MRD Image to nifti converter',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-i', '--input' , type=str, required=True , dest='inputMRDh5', help='Input .h5 MRD file')
    parser.add_argument('-o', '--output', type=str, required=False, dest='outputNII' , help='Output .nii file'  )
    args = parser.parse_args()

    # Run
    main(args)
