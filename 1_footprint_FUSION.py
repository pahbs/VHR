#!/usr/local/bin/python
############
#[1] Script outputs a metadata txt file for each NTF or TIF raster in (all subfolders of) a given directory;
#[2] crawls a given directory and outputs each image's metadata into a single csv;
#[3] takes metadata csv and converts csv rows to shp's and kml's
#
# To use:
# 1. Download shapefile package and place shapefile.py in same directory as python.exe
#    download: http://code.google.com/p/pyshp/
#    documentation: http://pythonhosted.org/Python%20Shapefile%20Library/
# 2. Update working directory containing raster imagery (directRaw) or enter
#    enter at terminal prompt
# 3. Update raster image type (rasterExt)
#
# Output:
#   - a [raster name]_metadata.txt for each image
#   - a csv, [directory]_metadata.csv, where each row contains an image's metadata
#   - a shp with complete dbf and projection information for each csv row
#   - a kml with attribute information for each csv row, color-coded and folder-separated
#     by year and satellite name
#
# Updated 6/19/2014 by Puddlez: 1. gdalinfo doesnt work on FUSION. Inserted code to get necessary coord info from XML instead.
#                               2. removed KML code until I can figure out how it works and why it gives an error after tweaking the code above. Probably a simple fix.
#                               3. removed a bunch of UTM related code
#                               4. Inserted a filter function to exclude files with specified strings within their names (I dont want to consider Gambit and IKONOS data now)
# Updated 6/13/2014 by Puddlez: inserted import time to be able to access strptime, changed str 'time' to 'acqtime'
# Updated 4/29/2014 by Puddlez: inserted code that untars, opens, reads lines, and get vars from an
#                               image's XML file. Added 'findFile' function.
# Updated 4/17/2014 by Puddlez: got rid of rasterExtNTF and rasterExtTIF and created single var rasterExt
# Last updated 04/11/2013 by Jamon Van Den Hoek jamon.vandenhoek@nasa.gov
# Updated on 12/09/13 by PMM -> inserted if statements for xycoords to sepatate x from y within line reading 'Lower Left, 'Upper Right', 'Lower Right'...quick fix for a stereo_mangrove footprint run.
###############################################

# USER INPUTS
termPrompt = 1   # 0: require terminal input; 1:edit here
if termPrompt == 0:
    directRaw = raw_input('Enter full NTF directory name (ie /raid1/imagery): ')
else:
    directRaw = 'F:\29Feb2012\29Feb2012JaimeNickeson1581180719-2012-02-29_03709416\MEDIA_0_USB\052509477010_01\DVD_VOL_1\052509477010_01\052509477010_01_P001_PAN'
    #'/raid1/WV1/stereo/siberia/in_pairs/psdo_emb' #'/raid1/WV1/stereo/siberia/in_pairs'

kmlFolderSort = 0  # 0: sort kml features into folders by year/satellite; 1: a thousand times 'no'

#rasterExtNTF = '.ntf' #any extension with a GDAL-supported driver will work
rasterExts = ['.ntf','tif']

direct = directRaw + "/"

# Exclude files that have these strings
excList = ['DZB','IK']  # Gambit and IKONOS scenes

###############################################
# Import and function definitions
import os, sys, math, osgeo
from osgeo import ogr, osr, gdal
import shapefile as shp
#import gdalinfo
import tarfile
import zipfile
import datetime
import time
from datetime import datetime
gdal.AllRegister() #register all raster format drivers

# For finding a specific file within a top level dir
def findFile(name, path):
    for root, dirs, files in os.walk(path):
        if name in files:
            return os.path.join(root, name)

# Define the 'any' function which isnt available in Python 2.4
def any(iterable):
    for element in iterable:
        if element:
            return True
    return False

# Dont list images with certain strings in their names
def filtFunc(s, stringList):
    return not any(x in s for x in stringList)

###############################################
# Collect file names in working directory and subfolders therein

namesList = []
pathroot = []
roots = []

for rasterExt in rasterExts:
    for root, dirs, files in os.walk(direct):
        for files in files:
            if files.endswith(rasterExt) or files.endswith(rasterExt.upper()):
                # Filter for only appending files that dont have the excList strings
                if filtFunc(files.split('/')[-1], excList):
                    root = root.replace('//','/').replace('\\','/')
                    roots.append(root + '/' + files)
                    namesList.append(files)
                    pathroot.append(root)

###############################################
# Use gdalinfo to make metadata txt from each raster

a = 0
while a < len(roots):
    if roots[a].endswith('.TIF') or roots[a].endswith('.tif'):
        rasterExt = '.TIF'
    if roots[a].endswith('.NTF') or roots[a].endswith('.ntf'):
        rasterExt = '.NTF'

    textname = roots[a].strip(rasterExt).strip(rasterExt.upper())

    if list(direct)[0] != list(textname)[0]:
        textname = list(direct)[0] + textname
    sys.stdout = open(textname+'_metadata.txt','w') #ready to collect gdalinfo output and dump into txt file
    gdal.SetConfigOption('NITF_OPEN_UNDERLYING_DS', 'NO')
    try:
        gdalinfo.main(['foo',roots[a]]) #'foo' is a dummy variable
        print('trying gdalinfo...')
    except:
        print('cannot run gdalinfo on ' + textname + rasterExt)
    a += 1

sys.stdout.close()
reload(sys)

print('---------------')
print(str(a) + ' metadata txt files successfully created')

###############################################
# Create csv to hold metadata

if direct.split('/')[1] == '': #script called at drive root
    fileName = direct.strip('/').strip(':')
else: #script called at subdirectory
    fileName = directRaw.split('/')[len(directRaw.split('/'))-1]

csvOut = open(direct+fileName+'_metadata.csv', 'w') #named for folder containing imagery
# CSV Header
csvOut.write('Directory,Name,Satellite,Bands,Acq Date,CloudCover,Country,Sun Elev,Sun Az,View Angle,LL,LR,UR,UL,Data Source,acqtime,MeanYGSD,MeanXGSD,MeanSatEl,MeanSatAz,MeanONVA,ephemX,ephemY,ephemZ,centLat,centLon,XMLcloudcov\n')

###############################################
# Export metadata.txt info to a directory metadata csv

print('COORDINATE EXTRACTION')
# Counter and list to hold names of images with very bad coordinates
badFileCounter = 0

badCoordFilesList = []
# To hold names of satellites
satList = ''

# Loop through metadata txt files and/or the .XML files and extract tags and coordinates
try1cnt = 0
try2cnt = 0
try3cnt = 0
try4cnt = 0
try5cnt = 0
fileCounter = 0
while fileCounter < len(namesList):
    if roots[fileCounter].endswith('.TIF') or roots[fileCounter].endswith('.tif'):
        rasterExt = '.TIF'
    if roots[fileCounter].endswith('.NTF') or roots[fileCounter].endswith('.ntf'):
        rasterExt = '.NTF'
    names = roots[fileCounter].strip(rasterExt).strip(rasterExt.lower())
    names = names.replace('//','/')
    if list(direct)[0] != list(names)[0]:
        names = list(direct)[0] + names
    # This depends on having corresponding NTF and metadata files...
    #   This could be problematic if unexpected raster file name format is encountered
    # Trying to account for unexpected rasters
    # Gambit: starts with 'DZB'

    if os.path.exists(names+'_metadata.txt'):
        myfile = open(names+'_metadata.txt', 'r')
        lines = myfile.readlines()
    else:
        myfile = ''
        lines = ''

    #############
    # OPEN THE XML
    #
    # Now look for .XMLs, which hold additional info
    myfileXML = ''
    if os.path.exists(names+'.xml'):
        myfileXML = open(names+'.xml', 'r')
        #print('Opened xml: try 1')
        try1cnt += 1

    # Sometimes XML is capitalized...
    if os.path.exists(names+'.XML'):
        myfileXML = open(names+'.XML', 'r')
        #print('Opened XML: try 2')
        try2cnt += 1

    # Sometimes the XML is named differently..strip the first *16* chars from the name string
    if os.path.exists(pathroot[fileCounter]+names.split('/')[-1][16:].split('.')[0]+'.XML'):
    	 myfileXML = open(pathroot[fileCounter]+names.split('/')[-1][16:].split('.')[0]+'.XML')
	 #print('Opened XML: try 3')
         try3cnt += 1

    # Maybe XMLs not yet untarred...
    if os.path.exists(names + '.tar'):
        tar = tarfile.open(names + '.tar')

        for tarEl in tar.getmembers():
            #print(os.path.basename(tarEl.name))
            fyleName = str(tarEl).split(' ')[1].replace("'","")
            if fyleName.endswith('.XML') and len(fyleName.split('README'))<2:
                fyle = fyleName
                tar.extract(tarEl, pathroot[fileCounter])
        # Find the XML that was just untarred
        #print(pathroot[fileCounter])
        myfileXML = open(findFile(fyle.split('/')[-1], pathroot[fileCounter]), 'r')
        #print('Opened XML from untarring: try 4')
        try4cnt += 1

    # Sometimes the TAR is named differently..strip the first *16* chars from the name string
    if os.path.exists(pathroot[fileCounter]+names.split('/')[-1][16:].split('.')[0]+'.tar'):
        names = pathroot[fileCounter]+names.split('/')[-1][16:].split('.')[0]
        tar = tarfile.open(names + '.tar')

        for tarEl in tar.getmembers():
            #print(os.path.basename(tarEl.name))
            fyleName = str(tarEl).split(' ')[1].replace("'","")
            if fyleName.endswith('.XML') and len(fyleName.split('README'))<2:
                fyle = fyleName
                tar.extract(tarEl, pathroot[fileCounter])
        # Find the XML that was just untarred
        #print(pathroot[fileCounter])
        myfileXML = open(findFile(fyle.split('/')[-1], pathroot[fileCounter]), 'r')

        try5cnt += 1
        #print('Opened XML: try 5')


    #print('Current file: ',names)

    # Read the XML file line by line
    if myfileXML == '':
        linesXML = ''
    else:
        linesXML = myfileXML.readlines()

    # Initialize variables which should be overwritten below
    getCoords = ''
    spectrum=''
    satellite=''
    QBIKsatellite=''
    idate=''
    zone=''
    cloud=''
    country=''
    sun_el=''
    sun_az=''
    view_angle=''
    coordinateList= []
    # This set is from the .XML file
    acqtime = ''
    meanXGSD = ''
    meanYGSD = ''
    meanSatEl = 0
    meanSatAz = 0
    meanONVA = 0   ## mean off-nadir view angle
    ephemX = 0
    ephemY = 0
    ephemZ = 0
    ullon = 0
    ullat = 0
    urlon = 0
    urlat = 0
    lllon = 0
    lllat = 0
    lrlon = 0
    lrlat = 0
    cloudcover = 0


    # Look at each line in metadata txt and pull out useful tags
    for line in lines:
        if 'NITF_IID2=' in line:
            satellite = line.split('=')
            satellite = satellite[1][7:11]
        if 'NITF_PIAIMC_SENSNAME=' in line: #for Ikonos
            satellite = line.split('=')
            satellite = satellite[1].strip('\n')
        if 'IK01' in line:
            satellite = 'IKONOS'
        if 'WV01' in line:
            satellite = 'WV01'
        if 'WV02' in line:
            satellite = 'WV02'
        if 'NITF_STDIDC_MISSION=' in line:
            satellite = line.split('=')
            satellite = satellite[1].strip('\n')
        if 'NITF_ISORCE=' in line: #for some Quickbird-2 and Ikonos images with different satellite naming conventions
            QBIKsatellite = line.split('=')
            QBIKsatellite = QBIKsatellite[1].strip('\n')
        if 'NITF_ICAT=' in line:
            spectrum = line.split('=')
            spectrum = spectrum[1].strip('\n')
        if 'NITF_IDATIM=' in line:
            idate = line.split('=')
            idate = idate[1][0:8]
        if 'NITF_STDIDC_ACQUISITION_DATE=' in line:
            idate = line.split('=')
            idate = idate[1].strip('\n')
            #itime = idate[1][8:16]
        if 'PROJCS["WGS 84 / UTM zone' in line:
            print("Landsat 8 file")
            imageUTM = True
            zone = line.split()[-1].split('N')[0]
            north_south = True
        if 'PROJCS["UTM Zone' in line:
            imageUTM = True
            zone = line.split()[2].strip(',')
            if line.split()[3] == 'Northern':
                north_south = True
            elif line.split()[3] == 'Southern':
                north_south = False
        if 'false_northing' in line:
            imageUTM = True
            if line.split(',')[1].strip('\n').strip(']') == '0':
                north_south = True
            else:
                north_south = False
        if 'NITF_IGEOLO=' in line: # only relevant for UTM imagery
            zone = line.split('=')
            zone = zone[1].strip('\n')
            if zone[2] == 'M': #southern hemisphere, UTM
                north_south = False
            if zone[2] == 'N': #northern hemisphere, UTM
                north_south = True
            zone = zone[0:2] # this should grab UTM zone

        if 'ESRI_MD_PERCENT_CLOUD_COVER=' in line:
            cloud = line.split('=')
            cloud = cloud[1].strip('\n')
        if 'NITF_PIAIMC_CLOUDCVR=' in line:
            cloud = line.split('=')
            cloud = cloud[1].strip('\n')
        if 'NITF_STDIDC_COUNTRY=' in line:
            country = line.split('=')
            country = country[1].strip('\n')
        if 'NITF_USE00A_SUN_EL=' in line:
            sun_el = line.split('=')
            sun_el = sun_el[1].strip('\n')
        if 'NITF_USE00A_SUN_AZ=' in line:
            sun_az = line.split('=')
            sun_az = sun_az[1].strip('\n')
        if 'NITF_USE00A_OBL_ANG=' in line:
            view_angle = line.split('=')
            view_angle = view_angle[1].strip('\n')
        # 1st attempt to gather corner coordinates
        if '-> ' in line: #this should happen four times, once for each corner
            xycoord = line.split()
            xycoord=xycoord[2].strip('(,)').strip('0').strip(',')
            xycoord = xycoord.split(',')
            xycoord = xycoord[::-1]
            xycoord = ' '.join(xycoord)
            coordinateList.append(xycoord)
            #if len(coordinateList) == 4:
            #    print(' - '+namesList[fileCounter] + ': 4 corner lat-lon coordinates found')
    # Now read from XML
    for line in linesXML:
        if 'IK01' in line:
            satellite = 'IKONOS'
        if 'WV01' in line:
            satellite = 'WV01'
        if 'WV02' in line:
            satellite = 'WV02'
        if 'QB02' in line:
            satellite = 'QB02'
        if 'OV' in line:
            satellite = 'OV05'
        if 'TLCTIME' in line:
            idate = line.split('>')
            idate = idate[1].split('T')[0]
            idate = idate.split('-')
            idate = str(idate[0]+idate[1]+idate[2])
        #if 'FIRSTLINETIME' in line:
	     # This is not working with Python 2.4.3 on FUSION...
            #acqtime = time.strptime(line.replace('<','>').split('>')[2],"%Y-%m-%dT%H:%M:%S.%fZ")
        if 'MEANCOLLECTEDROWGSD' in line:
            meanYGSD = float(line.replace('<','>').split('>')[2])
        if 'MEANCOLLECTEDCOLGSD' in line:
            meanXGSD = float(line.replace('<','>').split('>')[2])
        if 'MEANSATEL' in line:
            meanSatEl = float(line.replace('<','>').split('>')[2])
        if 'MEANSATAZ' in line:
            meanSatAz = float(line.replace('<','>').split('>')[2])
        if 'MEANOFFNADIRVIEWANGLE' in line:
            meanONVA = float(line.replace('<','>').split('>')[2])
        # Get Satellite Ephemeris using the first entry in EPHEMLISTList.
        if '<EPHEMLIST>' in line and float(line.replace('<','>').replace('>', ' ').split(' ')[2]) == 1:
            ephemX = float(line.replace('<','>').replace('>', ' ').split(' ')[3])
            ephemY = float(line.replace('<','>').replace('>', ' ').split(' ')[4])
            ephemZ = float(line.replace('<','>').replace('>', ' ').split(' ')[5])
        if 'CLOUDCOVER' in line:
            cloudcover = 100 * float(line.replace('<','>').split(('>'))[2])
        # Get coords and get approx center of image in lat,lon
        if '<BAND_P>' in line:
            getCoords = True
        if '<BAND_N>' in line:
            getCoords = True
        if getCoords == True:
            if 'ULLON' in line:
                ullon = float(line.replace('<','>').split(('>'))[2])
            if 'ULLAT' in line:
                ullat = float(line.replace('<','>').split(('>'))[2])
            if 'URLON' in line:
                urlon = float(line.replace('<','>').split(('>'))[2])
            if 'URLAT' in line:
                urlat = float(line.replace('<','>').split(('>'))[2])
            if 'LLLON' in line:
                lllon = float(line.replace('<','>').split(('>'))[2])
            if 'LLLAT' in line:
                lllat = float(line.replace('<','>').split(('>'))[2])
            if 'LRLON' in line:
                lrlon = float(line.replace('<','>').split(('>'))[2])
            if 'LRLAT' in line:
                lrlat = float(line.replace('<','>').split(('>'))[2])
                #print('lrlat: '+str(lrlat))
        if '</BAND_P>' in line:
            getCoords = False
        if '</BAND_N>' in line:
            getCoords = False
        #print('ullat: '+str(ullat))
        maxLat = max(ullat,urlat,lllat,lrlat)
        minLat = min(ullat,urlat,lllat,lrlat)
        maxLon = max(ullon,urlon,lllon,lrlon)
        minLon = min(ullon,urlon,lllon,lrlon)
        centLat = minLat + (maxLat - minLat)/2
        centLon = minLon + (maxLon - minLon)/2

    coordinateList.append(str(lllat)+' '+str(lllon))
    coordinateList.append(str(lrlat)+' '+str(lrlon))
    coordinateList.append(str(urlat)+' '+str(urlon))
    coordinateList.append(str(ullat)+' '+str(ullon))
    #print('coords: '+str(coordinateList))

    #if len(coordinateList) == 4:
        #print(' - '+namesList[fileCounter] + ': 4 corner lat-lon coordinates found')

    spec=''
    sat=''


    # Convert shorthand to explicit names
    if spectrum == 'MULTI' or spectrum == 'MS':
        spec = 'Multispectral'
    if spectrum == 'MONO' or spectrum == 'VIS':
        spec = 'Panchromatic'
    if satellite == 'QB02' or QBIKsatellite == 'QB02':
        sat = 'Quickbird 2'
    if satellite == 'WV01':
        sat = 'WorldView 1'
    if satellite == 'WV02':
        sat = 'WorldView 2'
    if satellite == 'OV05':
        sat = 'Orbview 5'
    if satellite == 'IKONOS_01' or satellite == 'SI01' or satellite == 'IK01' or satellite == 'IKONOS' or QBIKsatellite == 'SPACE IMAGING SATELLITE' or  QBIKsatellite == 'IKONOS':
        sat = 'Ikonos 1'

    # Track which satellites provided imagery
    if sat in satList:
        True
    else:
        satList= satList + ', '+sat

    # Collect imagery date
    y = idate[0:4]
    m = idate[4:6]
    d = idate[6:8]
    date = y + '-'+ m + '-'+ d


    # If UL, LL, UR, LR in hand, write metadata into csv row
    if len(coordinateList) == 4:
        coords = ', '.join(coordinateList)
        csvOut.write(pathroot[fileCounter].strip('/')+'/,'+namesList[fileCounter]+','+sat+','+spec+','+date+','+cloud+','+country+','+sun_el+','+sun_az+','+view_angle+','+coords+',NGA-NASA,'+str(acqtime)+','+str(meanYGSD)+','+str(meanXGSD)+','+str(meanSatEl)+','+str(meanSatAz)+','+str(meanONVA)+','+str(ephemX)+','+str(ephemY)+','+str(ephemZ)+','+str(centLat)+','+str(centLon)+','+str(cloudcover)+','+'\n')
    if os.path.exists(names+'_metadata.txt'):
        myfile.close()
    if os.path.exists(names + '.xml') or os.path.exists(names + '.XML') or os.path.exists(pathroot[fileCounter]+names.split('/')[-1][16:]+'.XML'):
        myfileXML.close()

    fileCounter += 1

print('Open XML Try 1 counts (has .xml extension): ',str(try1cnt))
print('Open XML Try 2 counts (has .XML extension): ',str(try2cnt))
print('Open XML Try 3 counts (.XML, & stripped first 16 chars from image name): ',str(try3cnt))
print('Open XML Try 4 counts (.XML from untarring): ',str(try4cnt))
print('')
print('METADATA TXT TO CSV')
print (' - '+str(len(namesList)-badFileCounter)+' files\' metadata included in ' + direct.split('/')[len(direct.split('/'))-2]+'_metadata.csv')
if(badFileCounter > 0):
    print (' - '+str(badFileCounter)+' files require manual input due to coordinate problems:')

csvOut.close()

if fileCounter == badFileCounter:
    sys.exit('\nSUMMARY\n - NO VALID IMAGES FOUND')

###############################################
# Prep to export csv contents to shp

csvDBF = open(direct+fileName+'_metadata.csv','r') #output from NTF-2_build_csv.py
shpOut = shp.Writer(shp.POLYGON)

###############################################
# Copy csv header into shp header

# Write shp header
# Note: all fields are cast as strings ('C') with length, 80, by default
shpHeader = csvDBF.readline()
i=0
while i < len(shpHeader.split(',')):
    if i == len(shpHeader.split(','))-1: #if last element
       shpOut.field(shpHeader.split(',')[i].strip('\n'),'C','80')
    else:
       shpOut.field(shpHeader.split(',')[i],'C','80')
    i+=1

###############################################
# Create shp features
print('')
print('SHP/KML EXPORTS')

#holder for shp-formatted kml feature values
kmlFeatureList = []

countRast = 0
for line in csvDBF.readlines():
    # Extract corner coords
    polyLL = line.split(',')[10].split(' ')
    polyLL = [float(polyLL[1]),float(polyLL[0])]
    polyLR = line.split(',')[11].split()
    polyLR = [float(polyLR[1]),float(polyLR[0])]
    polyUR = line.split(',')[12].split()
    polyUR = [float(polyUR[1]),float(polyUR[0])]
    polyUL = line.split(',')[13].split()
    polyUL = [float(polyUL[1]),float(polyUL[0])]

    # Length of record has to equal number of fields
    file_dir=line.split(',')[0]
    file_name=line.split(',')[1]
    sat=line.split(',')[2]
    sensor=line.split(',')[3]
    date=line.split(',')[4]
    year=date.split('-')[0]
    ##date=date.split('/')[2]+'-'+date.split('/')[0]+'-'+date.split('/')[1] #reformatted YYYY/MM/DD
    cloud=line.split(',')[5]
    country=line.split(',')[6]
    sun_elev=line.split(',')[7]
    sun_az=line.split(',')[8]
    view_angle=line.split(',')[9].lstrip('0') #remove leading 0 if angle < 10
    #LL=line.split(',')[10].split(' ')[0]+','+line.split(',')[10].split(' ')[1]
    LL1 = float(line.split(',')[10].split(' ')[0])
    LL2 = float(line.split(',')[10].split(' ')[1])
    LL = "%.5f" % LL1 + ',' + "%.5f" % LL2
    #LR=line.split(',')[11].split(' ')[1]+','+line.split(',')[11].split(' ')[2]
    LR1 = float(line.split(',')[11].split(' ')[1])
    LR2 = float(line.split(',')[11].split(' ')[2])
    LR = "%.5f" % LR1 + ',' + "%.5f" % LR2
    #UR=line.split(',')[12].split(' ')[1]+','+line.split(',')[12].split(' ')[2]
    UR1 = float(line.split(',')[12].split(' ')[1])
    UR2 = float(line.split(',')[12].split(' ')[2])
    UR = "%.5f" % UR1 + ',' + "%.5f" % UR2
    #UL=line.split(',')[13].split(' ')[1]+','+line.split(',')[13].split(' ')[2]
    UL1 = float(line.split(',')[13].split(' ')[1])
    UL2 = float(line.split(',')[13].split(' ')[2])
    UL = "%.5f" % UL1 + ',' + "%.5f" % UL2
    data=line.split(',')[14]
    acqtime = line.split(',')[15]
    meanYGSD = line.split(',')[16]
    meanXGSD = line.split(',')[17]
    meanSatEl = line.split(',')[18]
    meanSatAz = line.split(',')[19]
    meanONVA = line.split(',')[20]
    ephemX = line.split(',')[21]
    ephemY = line.split(',')[22]
    ephemZ = line.split(',')[23]
    centLat = line.split(',')[24]
    centLon = line.split(',')[25]
    cloudcover = line.split(',')[26]

    # Create shp DBF and record geometry
    shpOut.record(file_dir,file_name,sat,sensor,date,cloud,country,sun_elev,sun_az,view_angle,LL,LR,UR,UL,data,acqtime,meanYGSD,meanXGSD,meanSatEl,meanSatAz,meanONVA,ephemX,ephemY,ephemZ,centLat,centLon,cloudcover)
    shpOut.poly(parts=[[polyLL, polyLR, polyUR, polyUL, polyLL]])

    #store shp-formatted values for sorting folders by year/satellite
    kmlFeatureList.append([year,sat,file_dir,file_name,sensor,date,cloud,country,sun_elev,sun_az,view_angle,LL,LR,UR,UL,data,acqtime,meanYGSD,meanXGSD,meanSatEl,meanSatAz,meanONVA,ephemX,ephemY,ephemZ,centLat,centLon,cloudcover])
                          # 0    1      2       3        4     5     6      7       8       9      10       11 12 13 14  15   16      17       18      19        20        21      22      23     24    25      26      27

    countRast+=1
    #print(' - '+ file_name)
print('direct: '+direct+fileName)
csvDBF.close()
shpOut.save(direct+fileName) #shp name is directory's name



###############################################
# Create the shp prj file
# http://geospatialpython.com/2011/02/create-prj-projection-file-for.html

# Using lat-lon by default
prj = open(direct+fileName+'.prj', "w")
epsg = 'GEOGCS["WGS 84",'
epsg += 'DATUM["WGS_1984",'
epsg += 'SPHEROID["WGS 84",6378137,298.257223563]]'
epsg += ',PRIMEM["Greenwich",0],'
epsg += 'UNIT["degree",0.0174532925199433]]'
prj.write(epsg)
prj.close()

###############################################
# Create kml features

# REMOVED THIS CODE FOR NOW

###############################################
# Summary

print('\nSUMMARY\n'+' - '+str(countRast)+ satList.lstrip(',') + ' footprints exported to ' + fileName + '.shp & '+ fileName + '.kml')
if(badFileCounter > 0):
    print (' - '+str(badFileCounter)+' footprints could not be exported due to coordinate problems')
    for badEntry in badCoordFilesList:
        print('   - '+badEntry)




