"""
author: Hana Hourston
date: Jan. 23, 2020

about: This script is adapted from Jody Klymak's at https://gist.github.com/jklymak/b39172bd0f7d008c81e32bf0a72e2f09 for processing raw ADCP data.

Variables reshaped so as to have station coordinate
"""

import os
import csv
import numpy as np
import matplotlib.pyplot as plt
import xarray as xr
import pandas as pd
import datetime
from pycurrents.adcp.rdiraw import Multiread
from pycurrents.adcp import rdiraw
from pycurrents.data import timetools
from pycurrents.adcp.transform import heading_rotate
# import pycurrents.adcp.adcp_nc as adcp_nc
# from pycurrents.adcp.transform import rdi_xyz_enu
import pycurrents.adcp.transform as transform

#this prints out the Multiread() function code
#import inspect
#print(inspect.getsource(Multiread))


# Specify raw ADCP file to create nc file from
# raw .000 file
inFile = "/home/hourstonh/Documents/Hana_D_drive/ADCP_processing/callR_fromPython/20568-A1-56.000"
# csv metadata file
file_meta = "/home/hourstonh/Documents/Hana_D_drive/ADCP_processing/ADCP/a1_20160713_20170513_0480m/P01/a1_20160713_20170513_0480m_meta_L1.csv"


# Splice file name to get output netCDF file name
outname = os.path.basename(inFile)[:-3] + 'adcp.L1.nc'; print(outname)

# Get model and timestamp from raw file csv metadata file
# Instrument frequency is not included in the metadata files, so not included in "model". Frequency optional, apparently
meta_dict = {}
model = ""
with open(file_meta) as csv_file:
    csv_reader = csv.reader(csv_file, delimiter = ',')
    line_count = 0
    for row in csv_reader:
        # extract all metadata from csv file into dictionary -- some items not passed to netCDF file but are extracted anyway
        if row[0] != "Name":
            meta_dict[row[0]] = row[1]
            # create variables for model
            if row[0] == "instrumentSubtype":
                if row[1] == "Workhorse":
                    model = "wh"
                    model_long = "RDI WH Long Ranger"
                    manufacturer = 'teledyne rdi'
                elif row[1] == "Broadband":
                    model = "bb"
                    model_long = "RDI BB"
                    manufacturer = 'teledyne rdi'
                elif row[1] == "Narrowband":
                    model = "nb"
                    model_long = "RDI NB"
                    manufacturer = 'teledyne rdi'
                elif row[1] == "Sentinel V":  #missing from documentation
                    model = "sv"
                    model_long = "RDI SV"
                    manufacturer = 'teledyne rdi'
                elif row[1] == "Multi-Cell Doppler Current Profiler":
                    model = ""
                    model_long = "Sontek MC DCP"
                    manufacturer = 'sontek'
                else:
                    continue
            else:
                continue
if model == "":
    print("No valid instrumentSubtype detected")
    

# Multiread(fnames, sonar, yearbase=None, alias=None, gap=None, min_nprofs=1, gbinsonar=None, ibad=None)
# sonar: 'nb', 'bb', 'wh', or 'os' optionally followed by freq and pingtype, or a Sonar instance
# os = "Ocean Surveyor"
data = rdiraw.rawfile(inFile, model)

vel = data.read(varlist=['Velocity'])
amp = data.read(varlist=['Intensity'])
cor = data.read(varlist=['Correlation'])
pg = data.read(varlist=['PercentGood'])
#data = m.read()  #data outputs the kind of output we're looking for


# Get timestamp from "data" object just created
# In R, the start time was obtained from the "adp" object created within R
# data.yearbase is an integer of the year that the timeseries starts (e.g., 2016)
data_origin = str(data.yearbase) + '-01-01' #convert to date object; NEED TIME ZONE = UTC

## Set up dimensions

# time = pd.to_datetime(data.dday, unit='D', origin=pd.Timestamp('2016-01-01')) #original code line
# convert time variable to elapsed time since 1970-01-01T00:00:00Z; dtype='datetime64[ns]'
# t = pd.to_datetime(data.dday, unit='D', origin=data_origin, utc=True)[0].strftime('%Y-%m-%d %H:%M:%S.%f') + str(pd.to_datetime(data.dday, unit='D', origin=data_origin, utc=True)[0].nanosecond)
time_us = np.array(pd.to_datetime(vel.dday, unit='D', origin=data_origin, utc=True).strftime('%Y-%m-%d %H:%M:%S.%f'), dtype='datetime64')
station = np.array([float(meta_dict['station_number'])]) # Should dimensions be integers or arrays?
nchar = np.array(range(1, 100)) #was (1,24) which was the same as R code originally

## Set up variables that need it

# DTUT8601 should have dtype='|S23' ? this is where nchar=23 comes in?
time_DTUT8601 = pd.to_datetime(vel.dday, unit='D', origin=data_origin, utc=True).strftime('%Y-%m-%d %H:%M:%S') #don't need %Z in strftime

# Overwrite serial number to include the model: upper returns uppercase
meta_dict['serialNumber'] = model.upper() + meta_dict['serialNumber']
# Add instrument model variable value here for cleanliness
meta_dict['instrumentModel'] = '{} ADCP {}kHz ({})'.format(model_long, data.sysconfig['kHz'], meta_dict['serialNumber'])

# what is a masked array? bt_depth

sensor_dep = np.nanmean(vel.XducerDepth)


# Make into netCDF file
# unknown items in data.VL: EnsNumMSB (ensemble number ?), BIT, MPT_minutes/seconds/hundredths, ADC0-ADC7, ESW, spare1, spare2, RTCCentury/.../hundredths     

#Reshape variables so as to include station
#v1 = data.vel1.data.reshape((1, len(time_us), len(data.dep)))

# variable reshaping


def reshape_3d(variable):
    return variable.reshape((1, len(variable), len(data.dep)))


def reshape_2d(variable):
    return variable.reshape((1, len(variable)))


out = xr.Dataset(coords={'time': time_us, 'distance': data.dep, 'station': station, 'nchar': nchar},
                 data_vars={'time_var': (['time'], time_us),
                            'distance_var': (['distance'], data.dep),
                            'station_var': (['station'], station),
                            'LCEWAP01': (['time', 'distance', 'station'], reshape_3d(vel.vel1.data)),
                            'LCNSAP01': (['time', 'distance', 'station'], reshape_3d(vel.vel2.data)),
                            'LRZAAP01': (['time', 'distance', 'station'], vel.vel3.data),
                            'LERRAP01': (['time', 'distance', 'station'], vel.vel4.data),
                            'ELTMEP01': (['time', 'station'], time_us),
                            'TNIHCE01': (['time', 'distance', 'station'], amp.amp1),
                            'TNIHCE02': (['time', 'distance', 'station'], amp.amp2),
                            'TNIHCE03': (['time', 'distance', 'station'], amp.amp3),
                            'TNIHCE04': (['time', 'distance', 'station'], amp.amp4),
                            'CMAGZZ01': (['time', 'distance', 'station'], cor.cor1),
                            'CMAGZZ02': (['time', 'distance', 'station'], cor.cor2),
                            'CMAGZZ03': (['time', 'distance', 'station'], cor.cor3),
                            'CMAGZZ04': (['time', 'distance', 'station'], cor.cor4),
                            'PCGDAP00': (['time', 'distance', 'station'], pg.pg1),
                            'PCGDAP02': (['time', 'distance', 'station'], pg.pg2),
                            'PCGDAP03': (['time', 'distance', 'station'], pg.pg3),
                            'PCGDAP04': (['time', 'distance', 'station'], pg.pg4),
                            'PTCHGP01': (['time', 'station'], vel.pitch),
                            'HEADCM01': (['time', 'station'], vel.heading),
                            'ROLLGP01': (['time', 'station'], vel.roll),
                            'TEMPPR01': (['time', 'station'], vel.temperature),
                            'DISTTRAN': (['station', 'distance'], vel.dep - sensor_dep),
                            'PPSAADCP': (['time', 'station'], vel.XducerDepth),
                            'ALATZZ01': (['station'], np.array([float(meta_dict['latitude'])])),
                            'ALONZZ01': (['station'], np.array([float(meta_dict['longitude'])])),
                            'latitude': (['station'], np.array([float(meta_dict['latitude'])])),
                            'longitude': (['station'], np.array([float(meta_dict['longitude'])])),
                            'PRESPR01': (['time', 'station'], vel.VL['Pressure']),
                            'SVELCV01': (['time', 'station'], vel.VL['SoundSpeed']),
                            'DTUT8601': (['time', 'nchar'], time_DTUT8601),
                            'filename': (['station', 'nchar'], np.array([outname[-4]])),
                            'instrument_serial_number': (['station', 'nchar'], np.array([meta_dict['serialNumber']])),
                            'instrument_model': (['station', 'nchar'], np.array([meta_dict['instrumentModel']]))})

# Add attributes to each variable:
# making lists of variables that need the same attributes could help shorten this part of the script, but how?
# it may also make it harder to rename variables in the future...

fillValue = '1e35'

# Time
var = out.time_var
var.attrs['units'] = "seconds since 1970-01-01T00:00:00Z"
var.attrs['long_name'] = "time"
var.attrs['cf_role'] = "profile_id"
var.attrs['calendar'] = "gregorian"

# Bin distances
var = out.distance_var
var.attrs['units'] = "metres"
var.attrs['long_name'] = "distance"

# Station
var = out.station_var
var.attrs['long_name'] = "station"
var.attrs['cf_role'] = "timeseries_id"
var.attrs['standard_name'] = "platform_name"
var.attrs['longitude'] = float(meta_dict['longitude'])
var.attrs['latitude'] = float(meta_dict['latitude'])

# LCEWAP01: eastward velocity (vel1); all velocities have many overlapping attribute values (but not all)
var = out.LCEWAP01
var.attrs['units'] = 'm/sec'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'eastward_sea_water_velocity'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['generic_name'] = 'u'
var.attrs['flag_meanings'] = meta_dict['flag_meaning']
var.attrs['flag_values'] = meta_dict['flag_values']
var.attrs['References'] = meta_dict['flag_references']
var.attrs['legency_GF3_code'] = 'SDN:GF3::EWCT'
var.attrs['sdn_parameter_name'] = 'Eastward current velocity (Eulerian measurement) in the water body by moored acoustic doppler current profiler (ADCP)'
var.attrs['sdn_uom_urn'] = 'SDN:P06::UVAA'
var.attrs['sdn_uom_name'] = 'Metres per second'
var.attrs['standard_name'] = 'eastward_sea_water_velocity'
var.attrs['data_max'] = np.nanmax(vel.vel1)
var.attrs['data_min'] = np.nanmin(vel.vel1)
var.attrs['valid_max'] = 1000
var.attrs['valid_min'] = -1000

# LCNSAP01: northward velocity (vel2)
var = out.LCNSAP01
var.attrs['units'] = 'm/sec'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'northward_sea_water_velocity'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['generic_name'] = 'v'
var.attrs['flag_meanings'] = meta_dict['flag_meaning']
var.attrs['flag_values'] = meta_dict['flag_values']
var.attrs['References'] = meta_dict['flag_references']
var.attrs['legency_GF3_code'] = 'SDN:GF3::NSCT'
var.attrs['sdn_parameter_name'] = 'Northward current velocity (Eulerian measurement) in the water body by moored acoustic doppler current profiler (ADCP)'
var.attrs['sdn_uom_urn'] = 'SDN:P06::UVAA'
var.attrs['sdn_uom_name'] = 'Metres per second'
var.attrs['standard_name'] = 'northward_sea_water_velocity'
var.attrs['data_max'] = np.nanmax(vel.vel2)
var.attrs['data_min'] = np.nanmin(vel.vel2)
var.attrs['valid_max'] = 1000
var.attrs['valid_min'] = -1000

# LRZAAP01: vertical velocity (vel3)
var = out.LRZAAP01
var.attrs['units'] = 'm/sec'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'upward_sea_water_velocity'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['generic_name'] = 'w'
var.attrs['flag_meanings'] = meta_dict['flag_meaning']
var.attrs['flag_values'] = meta_dict['flag_values']
var.attrs['References'] = meta_dict['flag_references']
var.attrs['legency_GF3_code'] = 'SDN:GF3::VCSP'
var.attrs['sdn_parameter_name'] = 'Upward current velocity (Eulerian measurement) in the water body by moored acoustic doppler current profiler (ADCP)'
var.attrs['sdn_uom_urn'] = 'SDN:P06::UVAA'
var.attrs['sdn_uom_name'] = 'Metres per second'
var.attrs['standard_name'] = 'upward_sea_water_velocity'
var.attrs['data_max'] = np.nanmax(vel.vel3)
var.attrs['data_min'] = np.nanmin(vel.vel3)
var.attrs['valid_max'] = 1000
var.attrs['valid_min'] = -1000

# LERRAP01: error velocity (vel4)
var = out.LERRAP01
var.attrs['units'] = 'm/sec'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'error_velocity_in_sea_water'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['generic_name'] = 'e'
var.attrs['flag_meanings'] = meta_dict['flag_meaning']
var.attrs['flag_values'] = meta_dict['flag_values']
var.attrs['References'] = meta_dict['flag_references']
var.attrs['legency_GF3_code'] = 'SDN:GF3::ERRV'
var.attrs['sdn_parameter_name'] = 'Current velocity error in the water body by moored acoustic doppler current profiler (ADCP)'
var.attrs['sdn_uom_urn'] = 'SDN:P06::UVAA'
var.attrs['sdn_uom_name'] = 'Metres per second'
var.attrs['data_max'] = np.nanmax(vel.vel4)
var.attrs['data_min'] = np.nanmin(vel.vel4)
var.attrs['valid_max'] = 2000
var.attrs['valid_min'] = -2000

# ELTMEP01: seconds since 1970
var = out.ELTMEP01
var.attrs['units'] = 'seconds since 1970-01-01T00:00:00Z'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'time_02'
var.attrs['legency_GF3_code'] = 'SDN:GF3::N/A'
var.attrs['sdn_parameter_name'] = 'Elapsed time (since 1970-01-01T00:00:00Z)'
var.attrs['sdn_uom_urn'] = 'SDN:P06::UTBB'
var.attrs['sdn_uom_name'] = 'Seconds'
var.attrs['standard_name'] = 'time'

# TNIHCE01: echo intensity beam 1
var = out.TNIHCE01
var.attrs['units'] = 'counts'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'ADCP_echo_intensity_beam_1'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['generic_name'] = 'AGC'
var.attrs['legency_GF3_code'] = 'SDN:GF3::BEAM_01'
var.attrs['sdn_parameter_name'] = 'Echo intensity from the water body by moored acoustic doppler current profiler (ADCP) beam 1'
var.attrs['sdn_uom_urn'] = 'SDN:P06::UCNT'
var.attrs['sdn_uom_name'] = 'Counts'
var.attrs['data_min'] = np.nanmin(amp.amp1)
var.attrs['data_max'] = np.nanmax(amp.amp1)

# TNIHCE02: echo intensity beam 2
var = out.TNIHCE02
var.attrs['units'] = 'counts'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'ADCP_echo_intensity_beam_2'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['generic_name'] = 'AGC'
var.attrs['legency_GF3_code'] = 'SDN:GF3::BEAM_02'
var.attrs['sdn_parameter_name'] = 'Echo intensity from the water body by moored acoustic doppler current profiler (ADCP) beam 2'
var.attrs['sdn_uom_urn'] = 'SDN:P06::UCNT'
var.attrs['sdn_uom_name'] = 'Counts'
var.attrs['data_min'] = np.nanmin(amp.amp2)
var.attrs['data_max'] = np.nanmax(amp.amp2)

# TNIHCE03: echo intensity beam 3
var = out.TNIHCE03
var.attrs['units'] = 'counts'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'ADCP_echo_intensity_beam_3'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['generic_name'] = 'AGC'
var.attrs['legency_GF3_code'] = 'SDN:GF3::BEAM_03'
var.attrs['sdn_parameter_name'] = 'Echo intensity from the water body by moored acoustic doppler current profiler (ADCP) beam 3'
var.attrs['sdn_uom_urn'] = 'SDN:P06::UCNT'
var.attrs['sdn_uom_name'] = 'Counts'
var.attrs['data_min'] = np.nanmin(amp.amp3)
var.attrs['data_max'] = np.nanmax(amp.amp3)

# TNIHCE04: echo intensity beam 4
var = out.TNIHCE04
var.attrs['units'] = 'counts'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'ADCP_echo_intensity_beam_4'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['generic_name'] = 'AGC'
var.attrs['legency_GF3_code'] = 'SDN:GF3::BEAM_04'
var.attrs['sdn_parameter_name'] = 'Echo intensity from the water body by moored acoustic doppler current profiler (ADCP) beam 4'
var.attrs['sdn_uom_urn'] = 'SDN:P06::UCNT'
var.attrs['sdn_uom_name'] = 'Counts'
var.attrs['data_min'] = np.nanmin(amp.amp4)
var.attrs['data_max'] = np.nanmax(amp.amp4)

# PCGDAP00 - 4: percent good beam 1-4
var = out.PCGDAP00
var.attrs['units'] = 'percent'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'percent_good_beam_1'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['generic_name'] = 'PGd'
var.attrs['legency_GF3_code'] = 'SDN:GF3::PGDP_01'
var.attrs['sdn_parameter_name'] = 'Acceptable proportion of signal returns by moored acoustic doppler current profiler (ADCP) beam 1'
var.attrs['sdn_uom_urn'] = 'SDN:P06::UPCT'
var.attrs['sdn_uom_name'] = 'Percent'
var.attrs['data_min'] = np.nanmin(pg.Pg1)
var.attrs['data_max'] = np.nanmax(pg.Pg1)

# PCGDAP02: percent good beam 2
var = out.PCGDAP02
var.attrs['units'] = 'percent'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'percent_good_beam_2'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['generic_name'] = 'PGd'
var.attrs['legency_GF3_code'] = 'SDN:GF3::PGDP_02'
var.attrs['sdn_parameter_name'] = 'Acceptable proportion of signal returns by moored acoustic doppler current profiler (ADCP) beam 2'
var.attrs['sdn_uom_urn'] = 'SDN:P06::UPCT'
var.attrs['sdn_uom_name'] = 'Percent'
var.attrs['data_min'] = np.nanmin(pg.Pg2)
var.attrs['data_max'] = np.nanmax(pg.Pg2)

# PCGDAP03: percent good beam 3
var = out.PCGDAP03
var.attrs['units'] = 'percent'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'percent_good_beam_3'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['generic_name'] = 'PGd'
var.attrs['legency_GF3_code'] = 'SDN:GF3::PGDP_03'
var.attrs['sdn_parameter_name'] = 'Acceptable proportion of signal returns by moored acoustic doppler current profiler (ADCP) beam 3'
var.attrs['sdn_uom_urn'] = 'SDN:P06::UPCT'
var.attrs['sdn_uom_name'] = 'Percent'
var.attrs['data_min'] = np.nanmin(pg.Pg3)
var.attrs['data_max'] = np.nanmax(pg.Pg3)

# PCGDAP03: percent good beam 4
var = out.PCGDAP04
var.attrs['units'] = 'percent'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'percent_good_beam_4'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['generic_name'] = 'PGd'
var.attrs['legency_GF3_code'] = 'SDN:GF3::PGDP_04'
var.attrs['sdn_parameter_name'] = 'Acceptable proportion of signal returns by moored acoustic doppler current profiler (ADCP) beam 4'
var.attrs['sdn_uom_urn'] = 'SDN:P06::UPCT'
var.attrs['sdn_uom_name'] = 'Percent'
var.attrs['data_min'] = np.nanmin(pg.Pg4)
var.attrs['data_max'] = np.nanmax(pg.Pg4)

# PTCHGP01: pitch
var = out.PTCHGP01
var.attrs['units'] = 'degrees'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'pitch'
var.attrs['sensor_type'] = 'adcp'
var.attrs['legency_GF3_code'] = 'SDN:GF3::PTCH'
var.attrs['sdn_parameter_name'] = 'Orientation (pitch) of measurement platform by inclinometer'
var.attrs['sdn_uom_urn'] = 'SDN:P06::UAAA'
var.attrs['sdn_uom_name'] = 'Degrees'
var.attrs['standard_name'] = 'platform_pitch_angle'
var.attrs['data_min'] = np.nanmin(vel.pitch)
var.attrs['data_max'] = np.nanmax(vel.pitch)

# ROLLGP01: roll
var = out.ROLLGP01
var.attrs['units'] = 'degrees'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'roll'
var.attrs['sensor_type'] = 'adcp'
var.attrs['legency_GF3_code'] = 'SDN:GF3::ROLL'
var.attrs['sdn_parameter_name'] = 'Orientation (roll angle) of measurement platform by inclinometer (second sensor)'
var.attrs['sdn_uom_urn'] = 'SDN:P06::UAAA'
var.attrs['sdn_uom_name'] = 'Degrees'
var.attrs['standard_name'] = 'platform_roll_angle'
var.attrs['data_min'] = np.nanmin(vel.roll)
var.attrs['data_max'] = np.nanmax(vel.roll)

# DISTTRAN: height of sea surface
var = out.DISTTRAN
var.attrs['units'] = 'm'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'height of sea surface'
var.attrs['generic_name'] = 'height'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['legency_GF3_code'] = 'SDN:GF3::HGHT'
var.attrs['sdn_uom_urn'] = 'SDN:P06::ULAA'
var.attrs['sdn_uom_name'] = 'Metres'
var.attrs['data_min'] = np.nanmin(vel.dep)
var.attrs['data_max'] = np.nanmax(vel.dep)

# TEMPPR01: transducer temp
var = out.TEMPPR01
var.attrs['units'] = 'degrees celsius'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'ADCP Transducer Temp.'
var.attrs['generic_name'] = 'temp'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['legency_GF3_code'] = 'SDN:GF3::te90'
var.attrs['sdn_parameter_name'] = 'Temperature of the water body'
var.attrs['sdn_uom_urn'] = 'SDN:P06::UPAA'
var.attrs['sdn_uom_name'] = 'Celsius degree'
var.attrs['data_min'] = np.nanmin(vel.temperature)
var.attrs['data_max'] = np.nanmax(vel.temperature)

# PPSAADCP: instrument depth (formerly DEPFP01)
var = data.PPSAADCP
var.attrs['units'] = 'm'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'instrument depth'
var.attrs['xducer_offset_from_bottom'] = ''
var.attrs['generic_name'] = 'depth'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['legency_GF3_code'] = 'SDN:GF3::DEPH'
var.attrs['sdn_parameter_name'] = 'Depth below surface of the water body'
var.attrs['sdn_uom_urn'] = 'SDN:P06::ULAA'
var.attrs['sdn_uom_name'] = 'Metres'
var.attrs['standard_name'] = 'depth'
var.attrs['data_min'] = np.nanmin(vel.XducerDepth)
var.attrs['data_max'] = np.nanmax(vel.XducerDepth)

# ALONZZ01, longitude
for var in [data.ALONZZ01, data.longitude]:
    var.attrs['units'] = 'degrees_east'
    var.attrs['long_name'] = 'longitude'
    var.attrs['legency_GF3_code'] = 'SDN:GF3::lon'
    var.attrs['sdn_parameter_name'] = 'Longitude east'
    var.attrs['sdn_uom_urn'] = 'SDN:P06::DEGE'
    var.attrs['sdn_uom_name'] = 'Degrees east'
    var.attrs['standard_name'] = 'longitude'

# ALATZZ01, latitude
for var in [data.ALATZZ01, data.latitude]:
    var.attrs['units'] = 'degrees_north'
    var.attrs['long_name'] = 'latitude'
    var.attrs['legency_GF3_code'] = 'SDN:GF3::lat'
    var.attrs['sdn_parameter_name'] = 'Latitude north'
    var.attrs['sdn_uom_urn'] = 'SDN:P06::DEGN'
    var.attrs['sdn_uom_name'] = 'Degrees north'
    var.attrs['standard_name'] = 'latitude'

# HEADCM01: heading
var = data.HEADCM01
var.attrs['units'] = 'degrees'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'heading'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['legency_GF3_code'] = 'SDN:GF3::HEAD'
var.attrs['sdn_parameter_name'] = 'Orientation (horizontal relative to true north) of measurement device {heading}'
var.attrs['sdn_uom_urn'] = 'SDN:P06::UAAA'
var.attrs['sdn_uom_name'] = 'Degrees'
var.attrs['data_min'] = np.nanmin(vel.heading)
var.attrs['data_max'] = np.nanmax(vel.heading)

# PRESPR01: pressure
var = data.PRESPR01
var.attrs['units'] = 'decibars'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'pressure'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['legency_GF3_code'] = 'SDN:GF3::PRES'
var.attrs['sdn_parameter_name'] = 'Pressure (spatial co-ordinate) exerted by the water body by profiling pressure sensor and corrected to read zero at sea level'
var.attrs['sdn_uom_urn'] = 'SDN:P06::UPDB'
var.attrs['sdn_uom_name'] = 'Decibars'
var.attrs['standard_name'] = 'sea_water_pressure'
var.attrs['data_min'] = np.nanmin(vel.VL['Pressure'])
var.attrs['data_max'] = np.nanmax(vel.VL['Pressure'])

# SVELCV01: sound velocity
var = data.SVELCV01
var.attrs['units'] = 'm/sec'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'speed of sound'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['legency_GF3_code'] = 'SDN:GF3::SVEL'
var.attrs['sdn_parameter_name'] = 'Sound velocity in the water body by computation from temperature and salinity by unspecified algorithm'
var.attrs['sdn_uom_urn'] = 'SDN:P06::UVAA'
var.attrs['sdn_uom_name'] = 'Metres per second'
var.attrs['standard_name'] = 'speed_of_sound_in_sea_water'
var.attrs['data_min'] = np.nanmin(vel.VL['SoundSpeed'])
var.attrs['data_max'] = np.nanmax(vel.VL['SoundSpeed'])

# DTUT8601: time values as ISO8601 string, YY-MM-DD hh:mm:ss
var = data.SVELCV01
var.attrs['note'] = 'time values as ISO8601 string, YY-MM-DD hh:mm:ss'
var.attrs['time_zone'] = 'UTC'
var.attrs['legency_GF3_code'] = 'SDN:GF3::time_string'
var.attrs['sdn_parameter_name'] = 'String corresponding to format \'YYYY-MM-DDThh:mm:ss.sssZ\' or other valid ISO8601 string'
var.attrs['sdn_uom_urn'] = 'SDN:P06::TISO'
var.attrs['sdn_uom_name'] = 'ISO8601'

# CMAGZZ01-4: correlation magnitude
var = data.CMAGZZ01
var.attrs['units'] = 'counts'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'ADCP_correlation_magnitude_beam_1'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['generic_name'] = 'CM'
var.attrs['legency_GF3_code'] = 'SDN:GF3::CMAG_01'
var.attrs['sdn_parameter_name'] = 'Correlation magnitude of acoustic signal returns from the water body by moored acoustic doppler current profiler (ADCP) beam 1'
var.attrs['data_min'] = np.nanmin(cor.cor1)
var.attrs['data_max'] = np.nanmax(cor.cor1)

var = data.CMAGZZ02
var.attrs['units'] = 'counts'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'ADCP_correlation_magnitude_beam_2'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['generic_name'] = 'CM'
var.attrs['legency_GF3_code'] = 'SDN:GF3::CMAG_02'
var.attrs['sdn_parameter_name'] = 'Correlation magnitude of acoustic signal returns from the water body by moored acoustic doppler current profiler (ADCP) beam 2'
var.attrs['data_min'] = np.nanmin(cor.cor2)
var.attrs['data_max'] = np.nanmax(cor.cor2)

var = data.CMAGZZ03
var.attrs['units'] = 'counts'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'ADCP_correlation_magnitude_beam_3'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['generic_name'] = 'CM'
var.attrs['legency_GF3_code'] = 'SDN:GF3::CMAG_03'
var.attrs['sdn_parameter_name'] = 'Correlation magnitude of acoustic signal returns from the water body by moored acoustic doppler current profiler (ADCP) beam 3'
var.attrs['data_min'] = np.nanmin(cor.cor3)
var.attrs['data_max'] = np.nanmax(cor.cor3)

var = data.CMAGZZ04
var.attrs['units'] = 'counts'
var.attrs['_FillValue'] = fillValue
var.attrs['long_name'] = 'ADCP_correlation_magnitude_beam_4'
var.attrs['sensor_type'] = 'adcp'
var.attrs['sensor_depth'] = sensor_dep
var.attrs['serial_number'] = meta_dict['serialNumber']
var.attrs['generic_name'] = 'CM'
var.attrs['legency_GF3_code'] = 'SDN:GF3::CMAG_04'
var.attrs['sdn_parameter_name'] = 'Correlation magnitude of acoustic signal returns from the water body by moored acoustic doppler current profiler (ADCP) beam 4'
var.attrs['data_min'] = np.nanmin(cor.cor4)
var.attrs['data_max'] = np.nanmax(cor.cor4)
#done variables


# Global attributes
# system configuration keys added to dataset as Global attributes
for key in data.sysconfig.keys():
    print(int(data.sysconfig[key]))
    print((data.sysconfig[key] is not bool))
    print(type(data.sysconfig[key]) is not bool)
    if type(data.sysconfig[key]) is not bool:
        out.attrs['sysconfig' + key] = data.sysconfig[key]
    else:
        out.attrs['sysconfig' + key] = int(data.sysconfig[key])

if data.sysconfig['convex'] == True:
    beamPattern = 'convex'
else:
    beamPattern = ''

if data.sysconfig['up'] == True:
    orientation = 'up'
else:
    orientation = 'down'

# Create more global attributes
# Not from metadata file:
processing_history = "Metadata read in from log sheet and combined with raw data to export as netCDF file."
out.attrs['processing_history'] = processing_history
out.attrs['time_coverage_duration'] = data.dday[-1]-data.dday[0]
out.attrs['time_coverage_duration_units'] = "days"
#^calculated from start and end times; in days: add time_coverage_duration_units?
out.attrs['cdm_data_type'] = "station"
out.attrs['number_of_beams'] = data.NBeams #change in python and R to numberOfBeams? from 'janus' -- .adcp files have 'numbeams'
#out.attrs['nprofs'] = data.nprofs #number of ensembles
out.attrs['numberOfCells'] = data.NCells
out.attrs['pings_per_ensemble'] = data.NPings
out.attrs['bin1Distance'] = data.Bin1Dist
#out.attrs['Blank'] = data.Blank #?? blanking distance?
out.attrs['cellSize'] = data.CellSize
out.attrs['pingtype'] = data.pingtype
out.attrs['transmit_pulse_length_cm'] = vel.FL['Pulse']
out.attrs['instrumentType'] = "adcp"
out.attrs['manufacturer'] = manufacturer
out.attrs['source'] = "R code: adcpProcess, github:"
now = datetime.datetime.now(); out.attrs['date_modified'] = now.strftime("%Y-%m-%d %H:%M:%S")
out.attrs['_FillValue'] = fillValue
out.attrs['featureType'] = "timeSeries"

# Metadata from the data object
out.attrs['firmware_version'] = str(vel.FL.FWV) + '.' + str(vel.FL.FWR) #firmwareVersion
out.attrs['frequency'] = str(data.sysconfig['kHz'])
out.attrs['beam_pattern'] = beamPattern
out.attrs['beam_angle'] = str(vel.FL.BeamAngle) #beamAngle
out.attrs['sensor_source'] = "" #sensorSource
out.attrs['sensors_avail'] = '' #sensors_avail
out.attrs['three_beam_used'] = vel.trans['threebeam'] #threeBeamUsed; boolean
out.attrs['valid_correlation_range'] = vel.FL['LowCorrThresh'] #lowCorrThresh
out.attrs['minmax_percent_good'] = "100" #hardcoded in oceNc_create(); should be percentGdMinimum? that value is being overwritten
#out.attrs['transmit_pulse_length_cm'] = '' #errorVelocityMaximum + m/s
out.attrs['transmit_pulse_length_cm'] = 1710 #xmitPulseLength
out.attrs['false_target_reject_values'] = 50 #falseTargetThresh
out.attrs['data_type'] = "adcp"
out.attrs['pred_accuracy'] = 1 #where does this come from? velocityResolution * 1000
out.attrs['Conventions'] = "CF-1.7"
out.attrs['creater_type'] = "person"
out.attrs['time_coverage_start'] = time_DTUT8601[0]
out.attrs['time_coverage_end'] = time_DTUT8601[-1]

#geospatial lat, lon, and vertical min/max calculations
out.attrs['geospatial_lat_min'] = meta_dict['latitude']
out.attrs['geospatial_lat_max'] = meta_dict['latitude']
out.attrs['geospatial_lat_units'] = "degrees_north"
out.attrs['geospatial_lon_min'] = meta_dict['longitude']
out.attrs['geospatial_lon_max'] = meta_dict['longitude']
out.attrs['geospatial_lon_units'] = "degrees_east"
out.attrs['orientation'] = orientation

#sensor_depth is a variable attribute, not a global attribute
if out.attrs['orientation'] == 'up':
    out.attrs['geospatial_vertical_min'] = sensor_dep - np.nanmax(vel.dep)
    out.attrs['geospatial_vertical_max'] = sensor_dep - np.nanmin(vel.dep)
elif out.attrs['orientation'] == 'down':
    out.attrs['geospatial_vertical_min'] = sensor_dep + np.nanmin(vel.dep)
    out.attrs['geospatial_vertical_max'] = sensor_dep + np.nanmax(vel.dep)

#Add select meta_dict items as global attributes
for k, v in meta_dict.items():
    if k == 'cut_lead_ensembles' or k == 'cut_trail_ensembles' or k == 'processing_level':
        pass
    elif k == 'serialNumber':
        out.attrs[k] = 'serial_number'
    else:
        out.attrs[k] = v

# Already have what we need from this below it
# for key in vel.trans.keys():
#     print(type(vel.trans[key]))
#     if type(data.trans[key]) is not bool:
#         out.attrs['trans' + key] = vel.trans[key]
#     else:
#         out.attrs['trans' + key] = int(vel.trans[key])

# rotate into earth **IF not in enu already.  This just makes the netcdf bigger so...
# Hana added if statement
if data.trans.coordsystem != 'earth':
    trans = transform.Transform(angle=20, geometry='convex')
    xyze = trans.beam_to_xyz(out.vel)
    print(np.shape(xyze))
    enu = transform.rdi_xyz_enu(xyze, out.heading, out.pitch, out['roll'], orientation='up')
    print(np.shape(enu))
    # Apply change in coordinates to velocities
    out['LCEWAP01'] = xr.DataArray(enu[:, :, 0], dims=['time', 'distance'])
    out['LCNSAP01'] = xr.DataArray(enu[:, :, 1], dims=['time', 'distance'])
    out['LRZAAP01'] = xr.DataArray(enu[:, :, 2], dims=['time', 'distance'])
    out['LERRAP01'] = xr.DataArray(enu[:, :, 3], dims=['time', 'distance'])
    out.attrs['processing_history'] = + processing_history + " The coordinate system was rotated into enu coordinates."

out.attrs['coord_system'] = 'enu'

# Is this a test of the new nc file made?
# out.attrs['rVL'] = data.rVL
print(outname) #oname
print(out.sysconfigkHz)
out.to_netcdf(outname, mode='w', format='NETCDF4')
out.close()
# out.attrs['VL'] = data.VL
# Use exclamation mark to access the underlying shell
#!ls - halt


#def main():