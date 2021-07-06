import numpy as np
from scipy.stats import multivariate_normal
from scipy.stats import mode
import skimage
from skimage import measure
import sys

def get_rectilinear_resampling_map(mask, ray_density = 0.5, blur = 0.5):
#     mask is boolean array for US image
#     ray_density is number of rays per pixel in outer curve in US image
#     blur os variance of 2D gaussian used for weights

    try:
        assert(blur > 0)
    except:
        sys.exit("blur needs to be greater than zero")

    midline = np.shape(mask)[1] // 2 

    # get top left, top right, bottom left, bottom right "true" points of mask
    left_indices = np.asarray(np.where(mask[:,0:midline] == 1))
    right_indices = np.asarray(np.where(mask[:,midline:] == 1))

    tl = left_indices[:,np.argmin(left_indices[0])]
    tr = right_indices[:,np.argmin(right_indices[0])] + np.array([0,midline])
    bl = left_indices[:,np.argmin(left_indices[1])]
    br = right_indices[:,np.argmax(right_indices[1])] + np.array([0,midline])
    
    # get "center" point of circles in US image
    
    sl = (bl[1] - tl[1])/(bl[0]-tl[0])
    sr = (br[1] - tr[1])/(br[0]-tr[0])

    center_x = -((-sl* tl[0] + tl[1] + sr *tr[0] - tr[1])/(sl - sr)) 
    center_y = -((-sl* sr *tl[0] + sr* tl[1] + sl *sr *tr[0] - sl* tr[1])/(sl - sr))

    center = np.array([center_x, center_y])

    inner_radius = (np.linalg.norm(center - tl)+ np.linalg.norm(center - tr))/2
    outer_radius = (np.linalg.norm(center - bl)+ np.linalg.norm(center - br))/2

    radii = np.array([inner_radius, outer_radius])

    # determine total angle of the sector in the image

    left = np.linalg.norm(center - bl)
    right = np.linalg.norm(center - br)
    across = np.linalg.norm(bl - br)
    total_angle = np.arccos((left**2 + right**2 - across**2) / (2*left*right))

    # calculate bottom angle (angle of left side wrt midline)

    bottom_angle = np.arcsin((bl[1]-midline)/left)
    top_angle = np.arcsin((br[1]-midline)/right)

    # determine the x and y sizes of the resampled image
    # from ray density. y size will be sector depth

    target_xsize = int(ray_density*(outer_radius)*total_angle + 0.5) # arc length (pixels) times ray density
    target_ysize = int(outer_radius - inner_radius + 0.5) # depth of US image

    # create mapping tensor

    mapping = np.zeros([target_ysize, target_xsize, 11])

    thetas = np.linspace(bottom_angle, bottom_angle+total_angle, target_xsize + 2)
    rads = np.linspace(inner_radius, outer_radius, target_ysize + 2)

    for i in range(target_xsize):
        for j in range(target_ysize): 
            
            theta = thetas[i + 1]
            rad = rads[j + 1]
            
            x = np.cos(theta)*rad + center_x
            y = np.sin(theta)*rad + center_y
            
            kernel_center_x = int(np.round(x))
            kernel_center_y = int(np.round(y))

            kernel_weights = np.zeros([3,3])

            G = multivariate_normal([x,y], np.eye(2)*blur)
            for m in range(3):
                for n in range(3):
                    i0 = kernel_center_x + m - 1
                    i1 = kernel_center_y + n - 1
                    if (mask[i0,i1]):
                        kernel_weights[m,n] = G.pdf([i0,i1])
                    else:
                        kernel_weights[m,n] = 0.0

            if (np.sum(kernel_weights) == 0):
#                 print(i,j, "ij")
#                 print(kernel_center_x, kernel_center_y, "kc")
#                 sys.exit("sum of kernel weights was 0")
                kernel_weights = kernel_weights.reshape(9)
                mapping[j,i] = np.concatenate(([kernel_center_x, kernel_center_y], kernel_weights))
                continue

            kernel_weights = kernel_weights / np.sum(kernel_weights)
            kernel_weights = kernel_weights.reshape(9)

            mapping[j,i] = np.concatenate(([kernel_center_x, kernel_center_y], kernel_weights))
        
    return mapping


def get_resampled_image_from_mapping(image, mapping):
    # image is the original 2D image to be resampled
    # mapping is the mapping tensor generated by get_rectilinear_resampling_map
    
    if (len(np.shape(image))!=2):
        sys.exit("image is not 2D--must be 2D")
    
    dims = np.shape(mapping)[:2]
    res = np.zeros(dims)
    
    for i in range(dims[0]):
        for j in range(dims[1]):
            meta = mapping[i,j]
            kcx, kcy = meta[:2]
            kcx, kcy = int(kcx), int(kcy)
            kernel_weights = meta[2:]
            kernel_weights = np.reshape(kernel_weights, (3,3))
            window = image[kcx-1:kcx+2,kcy-1:kcy+2]
            try:
                val = np.sum(np.multiply(window, kernel_weights))
            except:
                print(kcx, kcy, "kernel center coords")
                print(np.shape(window), "window shape")
                print(np.shape(kernel_weights), "kernel shape")
                print(window)
                print(kernel_weights)
                sys.exit("couldn't do kernel multiply")
            res[i,j] = val

    return res   


def get_US_mask_from_image(image):
	# assumes center pixel belongs to US image
    mask = image > 0.006 # threshold
    labelled = skimage.measure.label(mask)
    center = np.asarray(np.shape(image)) // 2
    num = labelled[center[0],center[1]]
    USmask = labelled == num
    return USmask
