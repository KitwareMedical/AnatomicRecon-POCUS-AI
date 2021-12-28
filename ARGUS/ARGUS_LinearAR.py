from os import path

import itk

import ARGUSUtils_Timing
from ARGUSUtils_IO import *
from ARGUSUtils_Linearization import *
from ARGUSUtils_ARNet import *
from ARGUSUtils_ROINet import *

class ARGUS_LinearAR:
    def __init__(self, device_name='cpu', model_dir='Models'):
        self.device = torch.device(device_name)

        arnet_model_filename = path.join(model_dir, "BAMC_PTX_ARUNET-3D-PR-Final15", "best_model.vfold_0.pth")
        roinet_model_filename = path.join(model_dir, "BAMC_PTX_ROINet-StdDevExtended-ExtrudedNS-Final15", "best_model.vfold_0.pth")

        self.arnet_model = arnet_load_model(arnet_model_filename, self.device)
        self.roinet_model = roinet_load_model(roinet_model_filename,self.device)
    
    def predict(self, filename, debug=False, stats=None):
        time_this = ARGUSUtils_Timing.time_this
        if stats:
            time_this = stats.time
    
        with time_this("all"):
            with time_this("Read Video"):
                us_video = load_video(filename)

            with time_this("Process Video"):
                with time_this("Linearization Video"):
                    us_video_linear = linearize_video(us_video).transpose([2,1,0])

                with time_this("Preprocess for ARNet"):
                    arnet_input_tensor = arnet_preprocess_video(us_video_linear)

                if(debug):
                    itk.imwrite(itk.GetImageFromArray(arnet_input_tensor[0,0,:,:,:]),
                        "ARUNet_preprocessed_input.mha")

                with time_this("ARNet Inference Time:"):
                    arnet_output = arnet_inference(arnet_input_tensor,self.arnet_model,
                        self.device)
                
                if(debug):
                    itk.imwrite(itk.GetImageFromArray(arnet_output),
                        "ARUNet_output.mha")

                with time_this("ROI Extraction Time:"):
                    roinet_input_roi = roinet_segment_roi(us_video_linear,arnet_output)

                if(debug):
                    itk.imwrite(itk.GetImageFromArray(roinet_input_roi.astype(np.float32)),
                        "ROINet_input_roi.mha")

                with time_this("Preprocess for ROINet"):
                    roinet_input_tensor = roinet_preprocess_roi(roinet_input_roi)

                if(debug):
                    itk.imwrite(itk.GetImageFromArray(roinet_input_tensor[0,:,:,:]),
                        "ROINet_preprocessed_input.mha")

                with time_this("ROINet Inference Time:"):
                    decision,not_sliding_count,sliding_count,class_array = roinet_inference(
                        roinet_input_tensor,self.roinet_model,self.device,True)

                if(debug):
                    itk.imwrite( itk.GetImageFromArray(class_array),"ARGUS_output.mha")
                    print(decision,not_sliding_count,sliding_count)

        return dict(
            decision=decision,
            not_sliding_count=not_sliding_count,
            sliding_count=sliding_count,
            # debug info
            arnet_input_tensor=arnet_input_tensor,
            arnet_output=arnet_output,
            roinet_input_roi=roinet_input_roi,
            roinet_input_tensor=roinet_input_tensor,
            class_array=class_array,
        )