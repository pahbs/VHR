#!/bin/bash
cd /raid1/WV1/stereo
#######################BEGIN USER INPUT####################################################
### EDIT BEFORE EACH RUN
# [1] Specify location of the multispec data to ortho
inIMAGEdir="/raid1/WV1/stereo/siberia/in_pairs/received_jan212014/500098771090_01/500098771090_01_P001_MUL/"
inIMAGE="13APR06045340-M1BS-500098771090_01_P001.NTF"
inIMAGExml="${inIMAGE/.NTF/.XML}"

# [2] Specify out ortho image
outORTHOdir="/raid1/WV1/stereo/siberia/outORTHO/"
outORTHOimage=$outORTHOdir"${inIMAGE/.NTF/_ortho.tif}"

# [3] Specify DEM
#
inDEM="/raid1/WV1/stereo/siberia/out_ste_WV01_12SEP06_P002/WV01_12SEP06_P002-out-fill-DEM.tif"

cd $inIMAGEdir
/raid1/hi_res/bin/StereoPipeline-2.4.0_post-2014-05-21-x86_64-Linux-GLIBC-2.5/libexec/mapproject $inDEM $inIMAGE $inIMAGExml $outORTHOimage