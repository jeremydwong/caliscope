# I know that this is not really how tests are structured, but I'm just
# trying to begin getting in the habit of writing a test in a separate file
# from the code I'm developing...

# %%
import pyxy3d.logger

logger = pyxy3d.logger.get(__name__)

from pathlib import Path
import numpy as np
import sys
from PyQt6.QtWidgets import QApplication
from pyxy3d import __root__
from pyxy3d.calibration.capture_volume.capture_volume import CaptureVolume
from pyxy3d.calibration.capture_volume.helper_functions.get_point_estimates import (
    get_point_estimates,
)
from pyxy3d.calibration.capture_volume.point_estimates import PointEstimates
from pyxy3d.cameras.camera_array_initializer import CameraArrayInitializer
from pyxy3d.session import Session
from pyxy3d.calibration.charuco import Charuco
from pyxy3d.cameras.camera_array import CameraData
import cv2
from pyxy3d.gui.vizualize.capture_volume_visualizer import CaptureVolumeVisualizer
from pyxy3d.gui.vizualize.capture_volume_dialog import CaptureVolumeDialog
import pickle

session_directory = Path(__root__, "tests", "4_cameras_endofday")

REOPTIMIZE_ARRAY = False

if REOPTIMIZE_ARRAY:
    point_data_csv_path = Path(session_directory, "point_data.csv")

    config_path = Path(session_directory, "config.toml")
    array_initializer = CameraArrayInitializer(config_path)
    camera_array = array_initializer.get_best_camera_array()
    point_estimates = get_point_estimates(camera_array, point_data_csv_path)

    print(f"Optimizing initial camera array configuration ")

    capture_volume = CaptureVolume(camera_array, point_estimates)
    capture_volume.save(session_directory, "initial")
    capture_volume.optimize()
    capture_volume.save(session_directory, "optimized")
else:

    saved_CV_path = Path(session_directory, "capture_volume_stage_1_optimized.pkl")
    with open(saved_CV_path, "rb") as f:
        capture_volume: CaptureVolume = pickle.load(f)
    point_estimates = capture_volume.point_estimates
    camera_array = capture_volume.camera_array

# config_path = Path(session_directory, "config.toml")
session = Session(session_directory)
charuco_board = session.charuco.board

sync_indices = point_estimates.sync_indices
test_sync_index = sync_indices[28]

charuco_ids = point_estimates.point_id[sync_indices == test_sync_index]
unique_charuco_id = np.unique(charuco_ids)
unique_charuco_id.sort()

# pull out the 3d point estimate indexes associated with the chosen sync_index
# note that this will include duplicates
obj_indices = point_estimates.obj_indices[sync_indices == test_sync_index]
# now get the actual x,y,z estimate associated with these unique charucos
obj_xyz = point_estimates.obj[obj_indices]
sorter = np.argsort(charuco_ids)
unique_charuco_xyz_index = sorter[
    np.searchsorted(charuco_ids, unique_charuco_id, sorter=sorter)
]
# need to get charuco ids associated with the 3 point positions
world_corners_xyz = obj_xyz[unique_charuco_xyz_index]
# Convert 3d coordinates into 2d camera coordinates. Just pick a camera:

# need to get x,y,z estimates in board world...
board_corners_xyz = charuco_board.chessboardCorners[unique_charuco_id]


############################## POSSIBLE SOLUTION ON PAUSE ######################
# Commenting out code associated with attempts to use board pose....
# attempting alternate approach of calculating R|T that minimizes the difference
# between 

# anchor_camera: CameraData = camera_array.cameras[list(camera_array.cameras.keys())[0]]

# charuco_image_points, jacobian = cv2.projectPoints(
#     world_corners_xyz,
#     rvec=anchor_camera.rotation,
#     tvec=anchor_camera.translation,
#     cameraMatrix=anchor_camera.matrix,
#     distCoeffs=np.array(
#         [0, 0, 0, 0, 0], dtype=np.float32
#     ),  # For origin setting, assume perfection
# )

# # use solvepnp and not estimate poseboard.....
# retval, rvec, tvec = cv2.solvePnP(
#     board_corners_xyz,
#     charuco_image_points,
#     cameraMatrix=anchor_camera.matrix,
#     distCoeffs=np.array([0, 0, 0, 0, 0], dtype=np.float32),
# )
# # convert rvec to 3x3 rotation matrix
# logger.info(f"Rotation vector is {rvec}")
# rvec = cv2.Rodrigues(rvec)[0]
# logger.info(f"Rotation vector is {rvec}")
##########################################################################

###overwriting rvec and tvec to test out my understanding
rvec = cv2.Rodrigues(np.expand_dims(np.array([3.14159,0,0], dtype=np.float32), 1))[0]
# note that these translations result in the system moving in the negative direction
tvec = np.array([[0,1,0]]).T


#%%
# I believe this is the transformation to be applied
# or perhaps the inverse, let's find out...
new_origin_transform = np.hstack([rvec, tvec])
new_origin_transform = np.vstack(
    [new_origin_transform, np.array([0, 0, 0, 1], np.float32)]
)

# board_anchor_pose_transformation = np.matmul(
#     # np.linalg.inv(anchor_transform), np.linalg.inv(board_anchor_pose_transformation) 
#     anchor_transform, board_anchor_pose_transformation 
#     )

logger.info("About to attempt to change camera array")
# %%
# array_rotation =




for port, camera_data in camera_array.cameras.items():
    # camera_data.translation = camera_data.translation + tvec[:,0]
    # logger.info(f"Attempting to update camera at port {port}")
    old_transformation = camera_data.transformation
    new_transformation = np.dot(old_transformation, new_origin_transform)
    camera_data.transformation = new_transformation


# change the point estimates to reflect the new origin
xyz = capture_volume.point_estimates.obj
scale = np.expand_dims(np.ones(xyz.shape[0]), 1)
xyzh = np.hstack([xyz, scale])

new_origin_xyzh = np.matmul(np.linalg.inv(new_origin_transform), xyzh.T).T
# new_origin_xyzh = np.matmul(board_pose_transformation,xyzh.T).T
capture_volume.point_estimates.obj = new_origin_xyzh[:, 0:3]
#%%

capture_volume.save(session_directory, "new_origin")

logger.info("About to visualize the camera array")

# Here is the plan: from a given sync_index, find which camera has the most points represented on it.
# or wait...does this matter...can I just project back to the camera from the 3d points

#%%

app = QApplication(sys.argv)
vizr = CaptureVolumeVisualizer(capture_volume=capture_volume)
# vizr = CaptureVolumeVisualizer(camera_array = capture_volume.camera_array)

vizr_dialog = CaptureVolumeDialog(vizr)
vizr_dialog.show()

sys.exit(app.exec())
# %%
