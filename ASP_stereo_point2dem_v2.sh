#!/bin/bash
cd /raid1/WV1/stereo
#######################BEGIN USER INPUT####################################################
### EDIT BEFORE EACH RUN
# [1] Specify location of the stereo pairs
#
#inIMAGEdir="/raid1/WV1/stereo/siberia/in_pairs/PGC/ftp_agic_umn_edu/2014apr03/imagery/WV01_20120906_102001001D0ADA00_102001001FD73200"
#inIMAGEdir="/raid1/WV1/stereo/siberia/in_pairs/received_may2014/500093320020_01/500093320020_01_P001_PAN"
#inIMAGEdir="/raid1/WV1/stereo/siberia/in_pairs/PGC/ftp_agic_umn_edu/2014apr03/imagery/WV01_20120906_102001001D0ADA00_102001001FD73200"
inIMAGEdir="/raid1/WV1/stereo/siberia/in_pairs/received_jan212014/500098790070_01/500098790070_01_P001_PAN"

# [2] Specify output file stem
#
#fileSTEM="WV01_12SEP06_P002"
#fileSTEM="WV02_13APR02_P001"
#fileSTEM="WV01_12SEP06_P003"
fileSTEM="WV02_12AUG07_P001"

# [3] Set-up output stereo directory
#
outSTEdir="/raid1/WV1/stereo/siberia/out_ste_$fileSTEM"
mkdir $outSTEdir

# Copy stereo.default into outSTEdir AND to inIMAGEdir
# 	b/c the cmd is run from inIMAGEdir
#
cp stereo.default $outSTEdir/stereo.default
cp stereo.default $inIMAGEdir/stereo.default
cp stereo_point2dem_v2 $outSTEdir/stereo_point2dem_v2_$fileSTEM

# [4] Image dir
#
cd $inIMAGEdir/

rm left.tif
rm right.tif
rm left.xml
rm right.xml

# [5] Set-up symbolic links for readability
#
#ln -s 06SEP12WV010500012SEP06054826-P1BS-052880009070_01_P002.ntf left.tif 
#ln -s 12SEP06054826-P1BS-052880009070_01_P002.XML left.xml
#ln -s 06SEP12WV010500012SEP06054826-P1BS-500063277180_01_P002.ntf right.tif
#ln -s 12SEP06054826-P1BS-500063277180_01_P002.XML right.xml

ln -s 12AUG07055318-P1BS_R1C1-500098790070_01_P001.NTF left.tif
ln -s 12AUG07055318-P1BS_R1C1-500098790070_01_P001.XML left.xml
ln -s 12AUG07055411-P1BS_R1C1-500098790070_01_P001.NTF right.tif
ln -s 12AUG07055411-P1BS_R1C1-500098790070_01_P001.XML right.xml
#######################END USER INPUT######################################################

# Clipping
#gdal_translate -co compress=lzw -co TILED=yes -co INTERLEAVE=BAND -co BLOCKXSIZE=256 -co BLOCKYSIZE=256 -co compress=lzw -srcwin 0 0 9000 25000 left.tif left_clip.tif
#gdal_translate -co compress=lzw -co TILED=yes -co INTERLEAVE=BAND -co BLOCKXSIZE=256 -co BLOCKYSIZE=256 -co compress=lzw -srcwin 0 0 9000 25000 right.tif right_clip.tif

#-----------------------
# If clipping done, change below ALL INPUT in this block to left_clip.tif, etc


# Map-project with resolution of 'native'; --tr 2
#/raid1/hi_res/bin/StereoPipeline-2.3.0-x86_64-Linux-GLIBC-2.5/bin/mapproject -t rpc --t_srs "EPSG:32648" /raid1/WV1/stereo/siberia/in_DEM/aster_gdem2_siberia.tif left.tif left.xml left_proj.tif
#/raid1/hi_res/bin/StereoPipeline-2.3.0-x86_64-Linux-GLIBC-2.5/bin/mapproject -t rpc --t_srs "EPSG:32648" /raid1/WV1/stereo/siberia/in_DEM/aster_gdem2_siberia.tif right.tif right.xml right_proj.tif

# Crop to small region for speed
#gdal_translate -projwin 729779.000 7861347.000 749779.000 7851347.000 left_proj.tif left_clip2_proj.tif
#gdal_translate -projwin 729779.000 7861347.000 749779.000 7851347.000 right_proj.tif right_clip2_proj.tif
#-----------------------

# The STEREO call, with some commands that overwrite the defaults in stereo.default
# Using 'nice -19' with 'threads=<a-lot-of-threads>' lets you use a ton of threads but wont let you hog them if they are needed by others (it gives the job low priority)

# With results from mapproject
# nice -19 stereo --threads=15 left_proj.tif right_proj.tif left.xml right.xml $outSTEdir/out /raid1/WV1/stereo/in_DEM/aster_gdem2_siberia.tif --alignment-method none --corr-timeout 720 --subpixel-mode 2
# No mapproject
# TESTing with subpix mode 1

nice -19 stereo --threads=15 left.tif right.tif left.xml right.xml $outSTEdir/out --corr-timeout 1440 --subpixel-mode 2


# Gen DEM with:
# holes filled with --nodata-value
nice -19 point2dem --threads=15 -r earth --utm 48 --nodata-value -32768 $outSTEdir/out-PC.tif -o $outSTEdir/$fileSTEM-out-holes 

# Gen DEM with:
# holes filled; interpolated
# --orthoimage
nice -19 point2dem --threads=15 -r earth --utm 48 $outSTEdir/out-PC.tif -o $outSTEdir/$fileSTEM-out-fill --orthoimage $outSTEdir/out-L.tif