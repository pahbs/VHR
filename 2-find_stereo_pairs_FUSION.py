#-------------------------------------------------------------------------------
# Name:        Get_stereo_pairs.py
# Purpose:
#
# Author:      pmontesa
#
# Created:     30/04/2014
#               June 2014: jvandenh edits >>
#                   1. output unique (pseudo-)stereo pairs to csv
#                   2. include deltaTime variables and full metadata for imagery in csv
#                   3. include options to filter by (pseudo-)stereo pair parameters
#                   4. calculate convergence angle directly in this script and export to csv
#                   5. include all csv fields in shp dbf
#
# Copyright:   (c) pmontesa 2014
# Licence:     <your licence>
#-------------------------------------------------------------------------------
"""
Finds and footprints stereo pair coverage within an image directory

After running the HiRes footprinting code, this script reads the *_metadata.csv file
Untar the data's .tar files and read the XML data
Identify stereo pairs based on name,time, date, and center lat/lons

Create a stereo pair record listing both members of stereo pairs, as well as satellite ephemeris
info and camera info for each image pair.
    MEANSATEL, MEANSATAZ, MEANOFVA, EPHEMx, EPHEMy, EPHEMz
Create a stereo overlap box used to generate a shapefile of stereo coverage (approx)
Gets cloud cover info from the XML (from one of the 2 in the pair - they should be generally close)

Output: shapefile and corresponding csv. Use csv to run 'calc_stereo_pair_angles.py'
"""
# USER INPUTS
termPrompt = 1   # 0: require terminal input; 1:edit here
if termPrompt == 0:
    directRaw = raw_input('Enter full NTF directory name (ie /raid1/imagery): ')
else:
    directRaw =  'I:/projects/CAR/high-res'        #'F:/PGC_hi_res'

outFileNameEnd = '_STEREO_info-TEST'

matchRC = False # do RC tiles need to match?
maxDeltaT = 0 # maximum allowable time difference in seconds between stereo imagery; 0: no time limit
maxLatDelta = 90 # max allowable difference in lat; default: 0.05
maxLonDelta = 90 # max allowable difference in lon; default: 0.17
maxCloudCov = 100 # max allowable CC in either image
minConvAng = 0

direct = directRaw + "/"

###############################################
# Import and function definitions
import os, sys, math, osgeo
from osgeo import ogr, osr, gdal
import shapefile as shp
#import gdalinfo
import tarfile
import datetime, time
from datetime import datetime
gdal.AllRegister() #register all raster format drivers
###############################################
start_time = time.time()
# Function for calculating a 3x3 determinant
def det3(a1, b1, c1, a2, b2, c2, a3, b3, c3):
    res = a1*b2*c3+a2*b3*c1+a3*b1*c2-a1*b3*c2-a2*b1*c3-a3*b2*c1
    return res

def calcConvergenceAngle(alpha1,theta1,alpha2,theta2,x1,y1,z1,x2,y2,z2,lat,lon):
    # Converts degrees to radians
    dtr = math.atan(1.0)/45.0

    # Set Earth Radius
    r = 6378137   # WGS84 equatorial earth radius in meters

    a = math.sin(alpha1*dtr) * math.sin(alpha2*dtr)+ math.cos(alpha1*dtr) * math.cos(alpha2*dtr)* math.cos((theta1-theta2)*dtr)
    con_ang = math.acos(a)/dtr

    x0 = r * math.cos(lat*dtr) * math.cos(lon*dtr)
    y0 = r * math.cos(lat*dtr) * math.sin(lon*dtr)
    z0 = r * math.sin(lat*dtr)

    a = det3(y0,z0,1.0,y1,z1,1.0,y2,z2,1.0)
    b = -det3(x0,z0,1.0,x1,z1,1.0,x2,z2,1.0)
    c = det3(x0,y0,1.0,x1,y1,1.0,x2,y2,1.0)

##    print alpha1,alpha2,theta1,theta2
##    print a,b,c
##    print x0,y0,z0

    if int(a) == 0 or int(b) == 0 or int(c) == 0:
        return (-99999,-99999,-99999)
    else:
        sc = abs(a*x0 + b*y0 + c*z0)/(math.sqrt(x0*x0+y0*y0+z0*z0) * math.sqrt(a*a + b*b + c*c))
        bie_ang = math.asin(sc)/dtr
        a = x1+x2-2*x0
        b = y1+y2-2*y0
        c = z1+z2-2*z0
        sc = abs(a*x0 + b*y0 + c*z0)/(math.sqrt(x0*x0+y0*y0+z0*z0) * math.sqrt(a*a + b*b + c*c))
        asym_ang = math.asin(sc) / dtr
        return (con_ang,asym_ang,bie_ang)


#############################

# Read csv of stereo metadata
if direct.split('/')[1] == '':  # script called at drive root
    fileName = direct.strip('/').strip(':')
else:                           # script called at subdirectory
    fileName = directRaw.split('/')[len(directRaw.split('/'))-1]

csvStereo = open(direct+fileName+'_metadata.csv', 'r') #named for folder containing imagery

# Get the header
header = csvStereo.readline()
# Get the position of the cols of interest
nameIdx = header.split(',').index('Raster Name')
timeIdx = header.split(',').index('time')
LatIdx = header.split(',').index('centLat')
LonIdx = header.split(',').index('centLon')
sensBands = header.split(',').index('Sensor Bands')

LLIdx = header.split(',').index('LL')
LRIdx = header.split(',').index('LR')
URIdx = header.split(',').index('UR')
ULIdx = header.split(',').index('UL')

stereoDict = {} # indexed by image name; will hold metadata

for line in csvStereo.readlines():
    curImageName = line.split(',')[nameIdx]
    curImageTime = line.split(',')[timeIdx]
    if curImageTime != '':
        t_cur = datetime.strptime(curImageTime,"%Y-%m-%d %H:%M:%S.%f")

    if line.split(',')[LatIdx] != '':
        curImageLat = float(line.split(',')[LatIdx])
    if line.split(',')[LonIdx] != '':
        curImageLon = float(line.split(',')[LonIdx])

    curImageSB = line.split(',')[sensBands]

    curMeanSatEl = float(line.split(',')[-10])
    curMeanSatAz = float(line.split(',')[-9])
    curMeanONVA = float(line.split(',')[-8])
    curEphemX = float(line.split(',')[-7])
    curEphemY = float(line.split(',')[-6])
    curEphemZ = float(line.split(',')[-5])
    curImageCC = float(line.split(',')[-2])

    # Get corner coords for current image
    curLL = line.split(',')[LLIdx].split()
    curLL = [float(curLL[0]),float(curLL[1])] # format --> [lat,lon]

    curLR = line.split(',')[LRIdx].split()
    curLR = [float(curLR[0]),float(curLR[1])]

    curUR = line.split(',')[URIdx].split()
    curUR = [float(curUR[0]),float(curUR[1])]

    curUL = line.split(',')[ULIdx].split()
    curUL = [float(curUL[0]),float(curUL[1])]

    # stereoDict[image] = [sensor, date/time, cloud cover, center lat, center lon, LL, LR, UR, UL,
    #                       sat el, sat az, ONVA, ephemX, ephemY, ephemZ]
    stereoDict[curImageName] = [curImageSB,t_cur,curImageCC,curImageLat,curImageLon,curLL,curLR,curUR,curUL,
                                curMeanSatEl,curMeanSatAz,curMeanONVA,curEphemX,curEphemY,curEphemZ]

stereoNameList = stereoDict.keys()

# Prepare a csv to hold stereo pair info
csvSTEREOFOOT = open(direct+fileName+outFileNameEnd+'.csv', 'w') # named for folder containing imagery
csvSTEREOFOOT.write('Image_1,Image_2,Sensor,Date_1,Date_2,Time_1,Time_2,'+ # header
                    'deltaYear,deltaMonth,deltaDay,deltaHour,CloudCov_1,CloudCov_2,'+
                    'ovlapCentLat,ovlapCentLon,ovlapLLx,ovlapLLy,ovlapLRx,ovlapLRy,ovlapURx,ovlapURy,ovlapULx,ovlapULy,'+
                    'MeanSatEl_1,MeanSatAz_1,MeanONVA_1,ephemX_1,ephemY_1,ephemZ_1,'+
                    'MeanSatEl_2,MeanSatAz_2,MeanONVA_2,ephemX_2,ephemY_2,ephemZ_2,'+
                    'convAngle,asymAngle,bieAngle\n')

stereoPairsDict={}
image1Idx = 0
numPairs = 0
errorConvAng = 0
while image1Idx < len(stereoNameList)-1:
    image2Idx = image1Idx+1
    while image2Idx < len(stereoNameList):
        #print '1: '+str(image1Idx)+', 2: '+str(image2Idx)
        image1Name = stereoNameList[image1Idx]
        image2Name = stereoNameList[image2Idx]

        image1SB = stereoDict[image1Name][0]
        image2SB = stereoDict[image2Name][0]

        image1Time = stereoDict[image1Name][1]
        image2Time = stereoDict[image2Name][1]
        t_dif = abs(image1Time-image2Time)

        image1CC = stereoDict[image1Name][2]
        image2CC = stereoDict[image2Name][2]
        if image1CC == -99900.0: image1CC = 100
        if image2CC == -99900.0: image2CC = 100

        image1Lat = stereoDict[image1Name][3]
        image1Lon = stereoDict[image1Name][4]
        image2Lat = stereoDict[image2Name][3]
        image2Lon = stereoDict[image2Name][4]
        lat_dif = abs(image1Lat-image2Lat)
        lon_dif = abs(image1Lon-image2Lon)

        # Now for a potential stereo pair, get the polygon of overlap
        # Get corner coords for match image
        #   max UL x        min UR x
        #   min UL y        min UR y
        #
        #   max LL x        min LR x
        #   max LL y        max LR y

        image1LL = stereoDict[image1Name][5] # format --> [lat,lon]
        image1LR = stereoDict[image1Name][6]
        image1UR = stereoDict[image1Name][7]
        image1UL = stereoDict[image1Name][8]

        image2LL = stereoDict[image2Name][5]
        image2LR = stereoDict[image2Name][6]
        image2UR = stereoDict[image2Name][7]
        image2UL = stereoDict[image2Name][8]

        # these variables need to be updated following calculation
        # of the actual geometry of the overlap
        ovlapLL = [float(max(image1LL[0],image2LL[0])),float(max(image1LL[1],image2LL[1]))]
        ovlapLR = [float(max(image1LR[0],image2LR[0])),float(max(image1LR[1],image2LR[1]))]
        ovlapUR = [float(max(image1UR[0],image2UR[0])),float(max(image1UR[1],image2UR[1]))]
        ovlapUL = [float(max(image1UL[0],image2UL[0])),float(max(image1UL[1],image2UL[1]))]

        maxLat = max(ovlapUL[0],ovlapUR[0])
        minLat = min(ovlapLL[0],ovlapLR[0])
        maxLon = max(ovlapUL[1],ovlapUR[1])
        minLon = min(ovlapLL[1],ovlapLR[1])
        ovlapCentLat = minLat + (maxLat - minLat)/2
        ovlapCentLon = minLon + (maxLon - minLon)/2


        meanSatEl1 = stereoDict[image1Name][9]
        meanSatAz1 = stereoDict[image1Name][10]
        meanSatONVA1 = stereoDict[image1Name][11]
        ephemX1 = stereoDict[image1Name][12]
        ephemY1 = stereoDict[image1Name][13]
        ephemZ1 = stereoDict[image1Name][14]

        meanSatEl2 = stereoDict[image2Name][9]
        meanSatAz2 = stereoDict[image2Name][10]
        meanSatONVA2 = stereoDict[image2Name][11]
        ephemX2 = stereoDict[image2Name][12]
        ephemY2 = stereoDict[image2Name][13]
        ephemZ2 = stereoDict[image2Name][14]

        # returns (con_ang,asym_ang,bie_ang)
        # calcConvergenceAngle(alpha1,theta1,alpha2,theta2,x1,y1,z1,x2,y2,z2,lat,lon)
        convAng = calcConvergenceAngle(meanSatEl1,meanSatAz1,meanSatEl2,meanSatAz2,ephemX1,ephemY1,ephemZ1,ephemX2,ephemY2,ephemZ2,ovlapCentLat,ovlapCentLon)
        if convAng == (-99999,-99999,-99999): errorConvAng+=1

        # Make sure a given pair:
        #   1. wont be identical (do not grab the same record when reiterating through the csv)
        #   2. will be either both PAN or both MS
        #   3. were acquired within appropriate time window
        #   4. center points were close enough in space
        #   5. have suitable cloud cover
        #   optional >>
        #   6. won't be different 'RC' tiles that for some reason dont get removed with if lines below
        if matchRC:
            if image1Name.split('_')[1] != image2Name.split('_')[1]: break
        if maxDeltaT !=0:
            if int(t_dif.seconds) <= maxDeltaT: break
        if image1Name != '' and image2Name != '' and image1Name != image2Name and\
            image1SB == image2SB and \
            lat_dif <= maxLatDelta and lon_dif <= maxLonDelta and \
            image1CC <= maxCloudCov and image2CC <= maxCloudCov and convAng[0]>=minConvAng:

            #print "Found a stereo pair: Time dif= " + str(abs(t_dif.total_seconds()))
            #print "     Current Image Name: " + line2.split(',')[0]+' '+ curImageName
            #print "     Paired Image Name: " + line2.split(',')[0]+' '+ matchImageName

            # Write out the csv file
            csvSTEREOFOOT.write(image1Name+','+image2Name+','+image1SB+','+# Image_1,Image_2,Sensor,
            image1Time.strftime("%Y-%m-%d")+','+image2Time.strftime("%Y-%m-%d")+','+ # Date_1, Date_2,
            image1Time.strftime("%H:%M:%S.%f")+','+image2Time.strftime("%H:%M:%S.%f")+','+ # Time_1,Time_2,
            str(abs(image1Time.year-image2Time.year))+','+str(abs(image1Time.month-image2Time.month))+','+ # deltaYear,deltaMonth,
            str(abs(image1Time.day-image2Time.day))+','+str(abs(image1Time.hour-image2Time.hour))+','+ # deltaDay,deltaHour,
            str(stereoDict[image1Name][2])+','+str(stereoDict[image2Name][2])+','+ # CloudCov_1,CloudCov_2,
            str(ovlapCentLat)+','+str(ovlapCentLon)+','+ # ovlapCentLat,ovlapCentLon
            str(ovlapLL[0])+','+str(ovlapLL[1])+','+str(ovlapLR[0])+','+str(ovlapLR[1])+','+ # ovlapLLx,ovlapLLy,ovlapLRx,ovlapLRy,
            str(ovlapUR[0])+','+str(ovlapUR[1])+','+str(ovlapUL[0])+','+str(ovlapUL[1])+','+ # ovlapURx,ovlapURy,ovlapULx,ovlapULy,
            str(meanSatEl1)+','+str(meanSatAz1)+','+str(meanSatONVA1)+','+str(ephemX1)+','+str(ephemY1)+','+str(ephemZ1)+','+ # MeanSatEl_1,MeanSatAz_1,MeanONVA_1,ephemX_1,ephemY_1,ephemZ_1,
            str(meanSatEl2)+','+str(meanSatAz2)+','+str(meanSatONVA2)+','+str(ephemX2)+','+str(ephemY2)+','+str(ephemZ2)+','+ # MeanSatEl_2,MeanSatAz_2,MeanONVA_2,ephemX_2,ephemY_2,ephemZ_2
            str(convAng[0])+','+str(convAng[1])+','+str(convAng[2])+'\n') # convAngle,asymAngle,bieAngle
            numPairs+=1
        image2Idx+=1
    image1Idx+=1


print "     Total num stereo pairs: " + str(numPairs)
csvStereo.close()
csvSTEREOFOOT.close()

"""
Create a SHP of the STEREO_info.csv (for testing)
"""
    ###############################################
# Prep to export csv contents to shp
csvFile2shp = direct+fileName+outFileNameEnd+'.csv'
csvStereoInfo = open(csvFile2shp, 'r')
shpOut = shp.Writer(shp.POLYGON)

    ###############################################
# Copy csv header into shp header

# Write shp header
# Note: all fields are cast as strings ('C') with length, 80, by default
shpHeader = csvStereoInfo.readline()
i=0
while i < len(shpHeader.split(',')):
    if i < 3 or i == 5 or i == 6: # image names, sensors
        shpOut.field(shpHeader.split(',')[i],'C','80')
    elif i == 3 or i == 4: # date fields
        shpOut.field(shpHeader.split(',')[i],'D','80')
    elif i <= 10: #deltaTime fields
        shpOut.field(shpHeader.split(',')[i],'I','80')
    elif i > 10: # including cloud cover and following fields
        shpOut.field(shpHeader.split(',')[i],'F','80')
    i+=1

# Create shp features
for line in csvStereoInfo.readlines():
    # Extract corner coords
    polyLL = [float(line.split(',')[15]),float(line.split(',')[16])]
    polyLR = [float(line.split(',')[17]),float(line.split(',')[18])]
    polyUR = [float(line.split(',')[19]),float(line.split(',')[20])]
    polyUL = [float(line.split(',')[21]),float(line.split(',')[22])]
    shpOut.poly(parts=[[polyLL, polyLR, polyUR, polyUL, polyLL]]) # record geometry

    # create shp DBF that parallels csv records
    lineList = line.split(',')
    shpOut.record(lineList[0],lineList[1],lineList[2],lineList[3],lineList[4],lineList[5],\
    lineList[6],lineList[7],lineList[8],lineList[9],lineList[10],\
    lineList[11],lineList[12],lineList[13],lineList[14],lineList[15],\
    lineList[16],lineList[17],lineList[18],lineList[19],lineList[20],\
    lineList[21],lineList[22],lineList[23],lineList[24],lineList[25],\
    lineList[26],lineList[27],lineList[28],lineList[29],lineList[30],\
    lineList[31],lineList[32],lineList[33],lineList[34],lineList[35],\
    lineList[36],lineList[37].strip('\n'))

shpName = csvFile2shp.strip('.csv')
shpOut.save(shpName) #shp name is directory's name
csvStereoInfo.close()
prj = open(shpName+'.prj', "w")
epsg = 'GEOGCS["WGS 84",'
epsg += 'DATUM["WGS_1984",'
epsg += 'SPHEROID["WGS 84",6378137,298.257223563]]'
epsg += ',PRIMEM["Greenwich",0],'
epsg += 'UNIT["degree",0.0174532925199433]]'
prj.write(epsg)
prj.close()

###############################################

print '     pairs with errored convergence angle calc: '+str(int(math.floor(errorConvAng/2)))
end_time = time.time()
duration = (end_time-start_time)/3600
print("     elapsed time was %g seconds" % duration)