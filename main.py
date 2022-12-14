import open3d as o3d
import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial.transform import Rotation as R
import cv2
import json
import os
from tqdm import tqdm
from utils.ply_load import load as ply_load
import argparse

def rotate_view(vis, start_ex, heading, elevation):
    ctr = vis.get_view_control()
    camera_params = ctr.convert_to_pinhole_camera_parameters()
    vis.update_renderer()
    rot = np.eye(4)
    rot[:3, :3] = R.from_euler('xyz', [0, 90, 90], degrees=True).as_matrix()
    rot = rot.dot(start_ex)
    rot_st = np.eye(4)
    rot_st[:3, :3] = R.from_euler('y', -90, degrees=True).as_matrix()
    rot = rot_st.dot(rot)
    rot_y = np.eye(4)
    rot_y[:3, :3] = R.from_euler('y', heading, degrees=False).as_matrix()
    rot = rot_y.dot(rot)
    rot_x = np.eye(4)
    rot_x[:3, :3] = R.from_euler('x', elevation, degrees=False).as_matrix()
    rot = rot_x.dot(rot)
    camera_params.extrinsic = rot
    ctr.convert_from_pinhole_camera_parameters(camera_params)
    vis.update_renderer()
    return True


def save_2d_seg(scan_id, view_point_id, heading, elevation, view_index, location, mesh):
    vis = o3d.visualization.Visualizer()
    vis.create_window(width=1280, height=1024)
    vis.add_geometry(mesh)

    view_control = vis.get_view_control()

    trans = np.array([[1, 0.000000, 0.000000, 0],
                      [0.000000, -1, 0.000000, 0],
                      [0.000000, 0.000000, -1, 0],
                      [0.000000, 0.000000, 0.000000, 1.000000]])

    trans[:, -1] = [location['x'], location['y'], location['z'], 1]

    # manipulate camera
    vis.update_renderer()
    camera_params = view_control.convert_to_pinhole_camera_parameters()

    # set intrinsic parameters
    # camera_params.intrinsic.set_intrinsics(1280, 1024, 1076.33, 1076.54, 639.5, 511.5)
    # view_control.convert_from_pinhole_camera_parameters(camera_params)

    camera_params.extrinsic = trans
    rotate_view(vis, trans, heading, elevation)
    vis.update_renderer()

    camera_params = view_control.convert_to_pinhole_camera_parameters()
    pinhole_parameters = view_control.convert_to_pinhole_camera_parameters()
    view_control.convert_from_pinhole_camera_parameters(pinhole_parameters)
    output_image = vis.capture_screen_float_buffer(True)

    # resize image -> (640, 480)
    output_image = np.asarray(output_image)
    output_image = output_image[:, :, :3]
    output_image = cv2.resize(output_image, (640, 480))

    output_dir = "./output_segs"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_path = os.path.join(output_dir, f"{scan_id}_{view_point_id}_{str(view_index).zfill(2)}.png")
    plt.imsave(output_path, np.asarray(output_image), dpi=1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ids', default="./ids.json")
    parser.add_argument('--states', default="./states/")
    parser.add_argument('--scans', default="./data/v1/scans")
    args = parser.parse_args()

    # get region id
    with open(args.ids, "r") as f:
        ids = json.load(f)

    for idx in range(len(ids)):
        print(f"> process {idx+1} / {len(ids)} ...")
        scan_id = ids[idx]["scan_id"]
        for view_point_id in tqdm(ids[idx]["viewpoint_ids"]):
            json_file = f"{scan_id}_{view_point_id}_state.json"

            if not os.path.exists(os.path.join(args.states, json_file)):
                continue
            # json read
            with open(os.path.join(args.states, json_file)) as f:
                data = json.load(f)

            scan_dir = os.path.join(args.scans, scan_id)
            house_dir = os.path.join(scan_dir, 'house_segmentations')

            with open(os.path.join(house_dir, 'panorama_to_region.txt')) as f:
                lines = f.readlines()
                for line in lines:
                    line = line.strip()
                    line = line.split(' ')
                    if line[1] == view_point_id:
                        region_id = line[2]
                        break

            if region_id == '-1':
                continue

            # get color.ply
            reg_seg_dir = os.path.join(scan_dir, "region_segmentations")
            ply_path = os.path.join(reg_seg_dir, f"region{region_id}.ply")
            sem_seg_path = os.path.join(reg_seg_dir, f"region{region_id}.semseg.json")
            f_segs_path = os.path.join(reg_seg_dir, f"region{region_id}.fsegs.json")
            out_path = os.path.join(reg_seg_dir, f"region{region_id}_color.ply")
            if not os.path.exists(out_path):
                with open('./object_colors.json') as color_file:
                    color_data = json.load(color_file)
                colors = np.array(color_data['colors'])
                _, mesh = ply_load(ply_path, colors, sem_seg_path, f_segs_path, out_path)
            else:
                mesh = o3d.io.read_triangle_mesh(out_path)

            # camera position
            for i in range(len(data)):
                scan_id = data[i]['scanId']
                view_point_id = data[i]['viewpointId']
                heading = data[i]['heading'] * (-1)
                elevation = data[i]['elevation'] * (-1)
                view_index = data[i]['viewIndex']
                location = {}
                location['x'] = data[i]['location']['x'] * (-1)
                location['y'] = data[i]['location']['y']
                location['z'] = data[i]['location']['z']

                save_2d_seg(scan_id, view_point_id, heading, elevation, view_index, location, mesh)


if __name__ == "__main__":
    main()
