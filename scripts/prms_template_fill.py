#--------------------------------
# Name:         prms_template_fill.py
# Purpose:      Fill PRMS Parameter File Template
# Notes:        ArcGIS 10.2 Version
# Author:       Charles Morton
# Created       2015-04-27
# Python:       2.7
#--------------------------------

import argparse
from collections import defaultdict
import ConfigParser
import csv
import datetime as dt
import itertools
import logging
import os
import re
import sys

import arcpy
from arcpy import env

from support_functions import *

################################################################################

def prms_template_fill(config_path, overwrite_flag=False, debug_flag=False):
    """Fill PRMS Parameter Template File

    Args:
        config_file: Project config file path
        ovewrite_flag: boolean, overwrite existing files
        debug_flag: boolean, enable debug level logging
    Returns:
        None
    """

    try:
        ## Initialize hru_parameters class
        hru_param = hru_parameters()

        ## Open config file
        config = ConfigParser.ConfigParser()
        try: 
            config.readfp(open(config_file))
        except:
            logging.error('\nERROR: Config file could not be read, '+
                          'is not an input file, or does not exist\n'+
                          'ERROR: config_file = {0}\n').format(config_file)
            raise SystemExit()

        ## Log DEBUG to file
        log_file_name = 'prms_template_log.txt'
        log_console = logging.FileHandler(
            filename=os.path.join(hru.log_ws, log_file_name), mode='w')
        log_console.setLevel(logging.DEBUG)
        log_console.setFormatter(logging.Formatter('%(message)s'))
        logging.getLogger('').addHandler(log_console)
        logging.info('\nFilling PRMS Parameter File Template')
        
        ## Read parameters from config file
        hru_polygon_path  = config.get('INPUTS', 'hru_fishnet_path')
        hru_param.fid_field = config.get('INPUTS', 'orig_fid_field')
        prms_parameter_path  = config.get('INPUTS', 'prms_parameter_path')
        ##prms_template_path  = config.get('INPUTS', 'prms_template_path')
        prms_dimen_csv_path  = config.get('INPUTS', 'prms_dimen_csv_path')
        prms_param_csv_path  = config.get('INPUTS', 'prms_param_csv_path')
        parameter_ws = config.get('INPUTS', 'parameter_folder')

        ## Scratch workspace
        try: scratch_name = config.get('INPUTS', 'scratch_name')
        except: scratch_name = 'in_memory'

        ## Cascades
        crt_ws = os.path.join(parameter_ws, 'cascade_work')
        crt_dimension_path = os.path.join(crt_ws, 'parameter_dimensions.txt')
        crt_parameter_path = os.path.join(crt_ws, 'cascade.param')
        crt_gw_parameter_path = os.path.join(crt_ws, 'groundwater_cascade.param')

        ## Read some HRU Parameter Fields from config file
        hru_id_field = config.get('INPUTS', 'hru_id_field')
        hru_type_field = config.get('INPUTS', 'hru_type_field')
        hru_area_field = config.get('INPUTS', 'hru_area_field')
        hru_col_field = config.get('INPUTS', 'hru_col_field')
        hru_row_field = config.get('INPUTS', 'hru_row_field')
        lake_id_field = config.get('INPUTS', 'lake_id_field')
        iseg_field = config.get('INPUTS', 'iseg_field')
        krch_field = config.get('INPUTS', 'krch_field')
        outseg_field = config.get('INPUTS', 'outseg_field')
        subbasin_field = config.get('INPUTS', 'subbasin_field')
        flow_dir_field = config.get('INPUTS', 'flow_dir_field')
        ppt_zone_id_field = config.get('INPUTS', 'ppt_zone_id_field')

        ## Strings to search PRMS parameter file for
        file_header_str = 'Default file generated by model\nVersion: 1.7'
        dimen_header_str = '** Dimensions **'
        param_header_str = '** Parameters **'
        break_str = '####'

        ## Check input paths
        if not arcpy.Exists(hru_polygon_path):
            logging.error(
                '\nERROR: Fishnet ({0}) does not exist'.format(hru_polygon_path))
            raise SystemExit()
        ##if not os.path.isfile(prms_template_path):
        ##    logging.error('\nERROR: The template parameter file does not exist\n')
        ##    raise SystemExit()
        if not os.path.isfile(prms_dimen_csv_path):
            logging.error('\nERROR: The dimensions CSV file does not exist\n')
            raise SystemExit()
        if not os.path.isfile(prms_param_csv_path):
            logging.error('\nERROR: The parameters CSV file does not exist\n')
            raise SystemExit()
        if os.path.isfile(prms_parameter_path): os.remove(prms_parameter_path)
        if not os.path.isdir(crt_ws): 
            logging.error(
                ('\nERROR: Cascades folder does not exist'+
                 '\nERROR:   {0}'+
                 '\nERROR: Try re-running gsflow_stream_parameters.py\n').format(
                     crt_ws))
            raise SystemExit()
        if not os.path.isfile(crt_dimension_path): 
            logging.error(
                ('\nERROR: Cascades dimension file does not exist'+
                 '\nERROR:   {0}'+
                 '\nERROR: Try re-running gsflow_stream_parameters.py\n').format(
                     crt_dimension_path))
            raise SystemExit()
        if not os.path.isfile(crt_parameter_path): 
            logging.error(
                ('\nERROR: Cascades parameter file does not exist'+
                 '\nERROR:   {0}'+
                 '\nERROR: Try re-running gsflow_stream_parameters.py & CRT\n').format(
                     crt_parameter_path))
            raise SystemExit()
        if not os.path.isfile(crt_gw_parameter_path): 
            logging.error(
                ('\nERROR: Groundwater cascades parameter file does not exist'+
                 '\nERROR:   {0}'+
                 '\nERROR: Try re-running gsflow_stream_parameters.py & CRT\n').format(
                     crt_gw_parameter_path))
            raise SystemExit()


        ## Get number of cells in fishnet
        fishnet_count = int(arcpy.GetCount_management(
            hru_polygon_path).getOutput(0))
        logging.info('  Fishnet cells: {0}'.format(fishnet_count))


        ## Read in dimensions from CSV
        logging.info('\nReading dimensions CSV')
        dimen_size_dict = dict()
        with open(prms_dimen_csv_path, 'r') as input_f:
            dimen_lines = input_f.readlines()
        input_f.close()
        ## Dimensions can be set to a value, a field, or not set
        dimen_lines = [l.strip().split(',') for l in dimen_lines]
        header = dimen_lines[0]
        for line in dimen_lines[1:]:
            dimen_size = line[header.index('SIZE')]
            if dimen_size in ['CALCULATED']:
                pass
            elif not dimen_size:
                dimen_size_dict[line[header.index('NAME')]] = ''
            else:
                dimen_size_dict[line[header.index('NAME')]] = int(dimen_size)
            del dimen_size

        ## These parameters equal the fishnet cell count
        for dimen_name in ['ngw', 'ngwcell', 'nhru', 'nhrucell', 'nssr']:
            dimen_size_dict[dimen_name] = fishnet_count
            logging.info('  {0} = {1}'.format(
                dimen_name, dimen_size_dict[dimen_name]))

        ## Getting number of lakes
        logging.info('\nCalculating number of lake cells')
        logging.info('  Lake cells are {0} >= 0'.format(
            lake_id_field))
        value_fields = (hru_id_field, lake_id_field)
        with arcpy.da.SearchCursor(hru_polygon_path, value_fields) as s_cursor:
            dimen_size_dict['nlake'] = len(list(
                [int(row[1]) for row in s_cursor if int(row[1]) > 0]))
        logging.info('  nlakes = {0}'.format(dimen_size_dict['nlake']))

        ## Getting number of stream cells
        logging.info('Calculating number of stream cells')
        logging.info('  Stream cells are {0} >= 0'.format(
            krch_field))
        value_fields = (hru_id_field, krch_field)
        with arcpy.da.SearchCursor(hru_polygon_path, value_fields) as s_cursor:
            dimen_size_dict['nreach'] = len(list(
                [int(row[1]) for row in s_cursor if int(row[1]) > 0]))
        logging.info('  nreach = {0}'.format(dimen_size_dict['nreach']))

        ## Getting number of stream segments
        logging.info('Calculating number of unique stream segments')
        logging.info('  Stream segments are {0} >= 0'.format(
            iseg_field))
        value_fields = (hru_id_field, iseg_field)
        with arcpy.da.SearchCursor(hru_polygon_path, value_fields) as s_cursor:
            dimen_size_dict['nsegment'] = len(list(set(
                [int(row[1]) for row in s_cursor if int(row[1]) > 0])))
        logging.info('  nsegment = {0}'.format(dimen_size_dict['nsegment']))

        ## Getting number of subbasins
        logging.info('Calculating number of unique subbasins')
        logging.info('  Subbasins are {0} >= 0'.format(
            subbasin_field))
        value_fields = (hru_id_field, subbasin_field)
        with arcpy.da.SearchCursor(hru_polygon_path, value_fields) as s_cursor:
            dimen_size_dict['nsub'] = len(list(set(
                [int(row[1]) for row in s_cursor if int(row[1]) > 0])))
        logging.info('  nsub = {0}'.format(dimen_size_dict['nsub']))

        ## Read in CRT dimensions
        logging.info('\nReading CRT dimensions')
        with open(crt_dimension_path, 'r') as input_f:
            crt_dimen_lines = [line.strip() for line in input_f.readlines()]
        input_f.close()
        crt_dimen_break_i_list = [
            i for i,x in enumerate(crt_dimen_lines) if x == break_str]
        for i in crt_dimen_break_i_list:
            logging.info('  {0} = {1}'.format(
                crt_dimen_lines[i+1], crt_dimen_lines[i+2]))
            dimen_size_dict[crt_dimen_lines[i+1]] = int(crt_dimen_lines[i+2])
        del crt_dimen_lines, crt_dimen_break_i_list

        ## Link HRU fishnet field names to parameter names in '.param'
        param_name_dict = dict()
        param_width_dict = dict()
        param_dimen_count_dict = dict()
        param_dimen_names_dict = dict()
        param_values_count_dict = dict()
        param_type_dict = dict()
        param_default_dict = dict()
        param_values_dict = defaultdict(dict)
       
        ## Read in parameters from CSV
        logging.info('\nReading parameters CSV')
        with open(prms_param_csv_path, 'r') as input_f:
            param_lines = input_f.readlines()
        input_f.close()
        param_lines = [l.strip().split(',') for l in param_lines]
        header = param_lines[0]
        for line in param_lines[1:]:
            ## Get parameters from CSV line
            param_name = line[header.index('NAME')]
            param_width = line[header.index('WIDTH')]
            ## This assumes multiple dimensions are separated by semicolon
            dimen_names = line[header.index('DIMENSION_NAMES')].split(';')
            ## Check that parameter type is 1, 2, 3, or 4
            param_type = int(line[header.index('TYPE')])
            if param_type not in [1,2,3,4]:
                logging.error(
                    ('\nERROR: Parameter type {0} is invalid'+
                     '\nERROR: {1}').format(param_type, line))
                raise SystemExit()
            ## This will initially read defaults in as a list
            param_default = line[header.index('DEFAULT_VALUE'):]
            ## Removing empty strings avoids checking ints/floats 
            param_default = [l for l in param_default if l]
            ## For empty lists, set to none
            if not param_default: param_default = None 
            ## For single value lists, get first value
            ## Check that param_default is a number or field name
            elif len(param_default) == 1:
                param_default = param_default[0]
                if isfloat(param_default) and param_type == 1:
                    param_default = int(param_default)
                elif isfloat(param_default) and param_type in [2,3]:
                    param_default = float(param_default)
                elif param_default == 'CALCULATED':
                    pass
                elif param_default == 'CRT':
                    pass
                elif arcpy.ListFields(hru_polygon_path, param_default):
                    pass
                else:
                    logging.error(
                        ('\nERROR: Default value {0} was not parsed'+
                         '\nERROR: {1}').format(param_default, line))
                    raise SystemExit()
            ## For multi-value lists, convert values to int/float
            elif len(param_default) >= 2:
                if param_type == 1:
                    param_default = map(int, param_default)
                elif param_type in [2,3]:
                    param_default = map(float, param_default)
                else:
                    logging.error(
                        ('\nERROR: Default value {0} was not parsed'+
                         '\nERROR: {1}').format(param_default, line))
                    raise SystemExit()
            
            ## Check that dimension names are valid
            for dimen_name in dimen_names:
                if dimen_name not in dimen_size_dict.keys():
                    logging.error(
                        ('\nERROR: The dimension {0} is not set in the '+
                         'dimension CSV file').format(dimen_name))
                    raise SystemExit()  
            ## Calculate number of dimensions
            dimen_count = str(len(dimen_names))
            ## Calculate number of values
            values_count = prod(
                [int(dimen_size_dict[dn]) for dn in dimen_names
                 if dimen_size_dict[dn]])
            ## Write parameter to dictionaries
            param_name_dict[param_name] = param_name
            param_width_dict[param_name] = param_width
            param_dimen_count_dict[param_name] = dimen_count
            param_dimen_names_dict[param_name] = dimen_names
            param_values_count_dict[param_name] = values_count
            param_type_dict[param_name] = param_type
            param_default_dict[param_name] = param_default

        ## Apply default values to full dimension
        logging.info('\nSetting static parameters from defaults')
        for param_name, param_default in param_default_dict.items():
            param_values_count = param_values_count_dict[param_name]
            ## Skip if not set
            if param_default is None: continue
            ## Skip if still a string (field names)
            elif type(param_default) is str: continue
            ## For float/int, apply default across dimension size
            elif type(param_default) is float or type(param_default) is int:
                for i in xrange(param_values_count):
                    param_values_dict[param_name][i] = param_default
            ## For lists of floats, match up one-to-one for now
            elif len(param_default) == param_values_count:
                for i in xrange(param_values_count):
                    param_values_dict[param_name][i] = param_default[i]
            else:
                logging.error(
                    ('\nERROR: The default value(s) ({0}) could not be '+
                     'broadcast to the dimension length ({1})').format(
                         param_default, param_values_count))
                raise SystemExit()

        ## Read in HRU parameter data from fishnet polygon
        logging.info('\nReading in variable parameters from fishnet')
        param_field_dict = dict(
            [(k,v) for k,v in param_default_dict.items()
             if type(v) is str and v not in ['CALCULATED', 'CRT']])
        value_fields = param_field_dict.values()
        ## Use HRU_ID to uniquely identify each cell
        if hru_id_field not in value_fields:
            value_fields.append(hru_id_field)
        hru_id_i = value_fields.index(hru_id_field)
        ## Read in each cell parameter value
        with arcpy.da.SearchCursor(hru_polygon_path, value_fields) as s_cursor:
            for row in s_cursor:
                for field_i, (param, field) in enumerate(param_field_dict.items()):
                    if param_type_dict[param] == 1:
                        param_values_dict[param][row[hru_id_i]] = int(row[field_i])
                    elif param_type_dict[param] in [2, 3]:
                        param_values_dict[param][row[hru_id_i]] = float(row[field_i])
                    elif param_type_dict[param] == 4:
                        param_values_dict[param][row[hru_id_i]] = row[field_i]
                    ##param_values_dict[param][row[hru_id_i]] = row[field_i]

        ## The following will override the parameter CSV values
        ## Calculate basin_area from active cells (land and lake)
        logging.info('\nCalculating basin area')
        param_name_dict['basin_area'] = 'basin_area'
        param_width_dict['basin_area'] = 0
        param_dimen_count_dict['basin_area'] = 1
        param_dimen_names_dict['basin_area'] = ['one']
        param_values_count_dict['basin_area'] = dimen_size_dict['one']
        param_type_dict['basin_area'] = 2
        value_fields = (hru_id_field, hru_type_field, hru_area_field)
        with arcpy.da.SearchCursor(hru_polygon_path, value_fields) as s_cursor:
            param_values_dict['basin_area'][0] = sum(
                [float(row[2]) for row in s_cursor if int(row[1]) >= 1])
        logging.info('  basin_area = {0} acres'.format(
            param_values_dict['basin_area'][0]))

        ## Calculate number of columns
        logging.info('\nCalculating number of columns')
        param_name_dict['ncol'] = 'ncol'
        param_width_dict['ncol'] = 0
        param_dimen_count_dict['ncol'] = 1
        param_dimen_names_dict['ncol'] = ['one']
        param_values_count_dict['ncol'] = dimen_size_dict['one']
        param_type_dict['ncol'] = 1
        value_fields = (hru_id_field, hru_col_field)
        with arcpy.da.SearchCursor(hru_polygon_path, value_fields) as s_cursor:
            param_values_dict['ncol'][0] = len(
                list(set([int(row[1]) for row in s_cursor])))
        logging.info('  ncol = {0}'.format(
            param_values_dict['ncol'][0]))

        ## Calculate mean monthly maximum temperature for all active cells
        logging.info('\nCalculating tmax_index')
        logging.info('  Converting Celsius to Farenheit')
        param_name_dict['tmax_index'] = 'tmax_index'
        param_width_dict['tmax_index'] = 15
        param_dimen_count_dict['tmax_index'] = 1
        param_dimen_names_dict['tmax_index'] = ['nmonths']
        param_values_count_dict['tmax_index'] = dimen_size_dict['nmonths']
        param_type_dict['tmax_index'] = 2
        tmax_field_list = ['TMAX_{0:02d}'.format(m) for m in range(1,13)]
        for i, tmax_field in enumerate(tmax_field_list):
            tmax_values = [row[1] for row in arcpy.da.SearchCursor(
                hru_polygon_path, (hru_type_field, tmax_field),
                where_clause='"{0}" >= 1'.format(hru_type_field))]
            tmax_c = sum(tmax_values) / len(tmax_values)
            tmax_f = 1.8 * tmax_c + 32
            param_values_dict['tmax_index'][i] = tmax_f
            logging.info('  {0} = {1}'.format(
                tmax_field, param_values_dict['tmax_index'][i]))
            del tmax_values

        ## Calculate mean monthly maximum temperature for all active cells
        logging.info('\nCalculating rain_adj/snow_adj')
        ratio_field_list = ['PPT_RT_{0:02d}'.format(m) for m in range(1,13)]
        param_name_dict['rain_adj'] = 'rain_adj'
        param_width_dict['rain_adj'] = 4
        param_dimen_count_dict['rain_adj'] = 2
        param_dimen_names_dict['rain_adj'] = ['nhru', 'nmonths']
        param_values_count_dict['rain_adj'] = 12 * fishnet_count
        param_type_dict['rain_adj'] = 2
        param_name_dict['snow_adj'] = 'snow_adj'
        param_width_dict['snow_adj'] = 4
        param_dimen_count_dict['snow_adj'] = 2
        param_dimen_names_dict['snow_adj'] = ['nhru', 'nmonths']
        param_values_count_dict['snow_adj'] = 12 * fishnet_count
        param_type_dict['snow_adj'] = 2
        ratio_values = []
        for i, ratio_field in enumerate(ratio_field_list):
            ratio_values.extend([
                float(row[1]) for row in sorted(arcpy.da.SearchCursor(
                    hru_polygon_path, (hru_id_field, ratio_field)))])
        for i, value in enumerate(ratio_values):
            param_values_dict['rain_adj'][i] = value
            param_values_dict['snow_adj'][i] = value
        del ratio_values

        ## Calculate mean monthly maximum temperature for all active cells
        logging.info('\nCalculating subbasin_down')
        param_name_dict['subbasin_down'] = 'subbasin_down'
        param_width_dict['subbasin_down'] = 0
        param_dimen_count_dict['subbasin_down'] = 1
        param_dimen_names_dict['subbasin_down'] = ['nsub']
        param_values_count_dict['subbasin_down'] = dimen_size_dict['nsub']
        param_type_dict['subbasin_down'] = 1
        ## Get list of subbasins and downstream cell for each stream/lake cell
        ## Downstream is calulated from flow direction
        ##logging.info("Cell out-flow dictionary")
        cell_dict = dict()
        fields = [
            hru_type_field, krch_field, lake_id_field, subbasin_field,
            flow_dir_field, hru_col_field, hru_row_field, hru_id_field]
        for row in arcpy.da.SearchCursor(hru_polygon_path, fields):
            ## Skip inactive cells
            if int(row[0]) == 0: continue
            ## Skip non-lake and non-stream cells
            if (int(row[1]) == 0 and int(row[2]) == 0): continue
            ## Read in parameters
            cell = (int(row[5]), int(row[6]))
            ## next_row_col(FLOW_DIR, CELL)
            ## HRU_ID, SUBBASIN, NEXT_CELL
            cell_dict[cell] = [
                int(row[7]), int(row[3]), next_row_col(int(row[4]), cell)]
            del cell
        ## Get subset of cells is subbasin <> next_subbasin
        subbasin_list = []
        for cell, row in cell_dict.items():
            if row[2] not in cell_dict.keys():
                ## Set exit gauge subbasin to 0
                subbasin_list.append([row[1], 0])
            elif row[1] <> cell_dict[row[2]][1]:
                subbasin_list.append([row[1], cell_dict[row[2]][1]])
        for i, (subbasin, subbasin_down) in enumerate(sorted(subbasin_list)):
            param_values_dict['subbasin_down'][i] = subbasin_down
            logging.debug('  {0}'.format(param_values_dict['subbasin_down'][i]))
        del subbasin_list


        ## lake_hru parameter
        logging.info('\nCalculating LAKE_HRU from HRU_ID for all lake HRU\'s')
        param_name_dict['lake_hru'] = 'lake_hru'
        param_width_dict['lake_hru'] = 0
        param_dimen_count_dict['lake_hru'] = 1
        param_dimen_names_dict['lake_hru'] = ['nlake']
        param_values_count_dict['lake_hru'] = dimen_size_dict['nlake']
        param_type_dict['lake_hru'] = 1
        lake_hru_id_list = [
            row[1] for row in arcpy.da.SearchCursor(
                hru_polygon_path, (hru_type_field, hru_id_field))
            if int(row[0]) == 2]
        for i,lake_hru_id in enumerate(sorted(lake_hru_id_list)):
            logging.info('  {0} {1}'.format(i, lake_hru_id))
            param_values_dict['lake_hru'][i] = lake_hru_id


        ## Read in CRT parameters
        logging.info('\nReading CRT parameters')
        with open(crt_parameter_path, 'r') as input_f:
            crt_param_lines = [line.strip() for line in input_f.readlines()]
        input_f.close()
        ## Using enumerate iterator to get .next method
        crt_param_enumerate = enumerate(crt_param_lines)
        for crt_param_line in crt_param_enumerate:
            if crt_param_line[1] == break_str:
                ## Skip break string
                crt_param_line = crt_param_enumerate.next()
                ## Read parameter name and get next line
                param_name = crt_param_line[1]
                param_name_dict[param_name] = param_name
                param_width_dict[param_name] = 0
                crt_param_line = crt_param_enumerate.next()
                ## Read dimension count and get next line
                param_dimen_count_dict[param_name] = int(crt_param_line[1])
                crt_param_line = crt_param_enumerate.next()
                ## For each dimen (based on count) read in dimension name
                param_dimen_names_dict[param_name] = []
                for dimen_i in range(param_dimen_count_dict[param_name]):
                    param_dimen_names_dict[param_name].append(crt_param_line[1])
                    crt_param_line = crt_param_enumerate.next()
                ## Read in number of parameter values
                param_values_count_dict[param_name] = int(crt_param_line[1])
                crt_param_line = crt_param_enumerate.next()
                ## Read in parameter type
                param_type_dict[param_name] = int(crt_param_line[1])
                ## Read in parameter values
                ## Get next in loop is place intentionally
                ## Placing  after getting the value causes it to skip next break
                for i in range(param_values_count_dict[param_name]):
                    crt_param_line = crt_param_enumerate.next()
                    if param_type_dict[param_name] == 1:
                        param_values_dict[param_name][i] = int(crt_param_line[1])
                    if param_type_dict[param_name] in [2, 3]:
                        param_values_dict[param_name][i] = float(crt_param_line[1])
                    if param_type_dict[param_name] == 4:
                        param_values_dict[param_name][i] = crt_param_line[1]

        ## Read in CRT groundwater parameters
        logging.info('Reading CRT groundwater parameters')
        with open(crt_gw_parameter_path, 'r') as input_f:
            crt_param_lines = [line.strip() for line in input_f.readlines()]
        input_f.close()
        ## Using enumerate iterator to get .next method
        crt_param_enumerate = enumerate(crt_param_lines)
        for crt_param_line in crt_param_enumerate:
            if crt_param_line[1] == break_str:
                ## Skip break string
                crt_param_line = crt_param_enumerate.next()
                ## Read parameter name and get next line
                param_name = crt_param_line[1]
                param_name_dict[param_name] = param_name
                param_width_dict[param_name] = 0
                crt_param_line = crt_param_enumerate.next()
                ## Read dimension count and get next line
                param_dimen_count_dict[param_name] = int(crt_param_line[1])
                crt_param_line = crt_param_enumerate.next()
                ## For each dimen (based on count) read in dimension name
                param_dimen_names_dict[param_name] = []
                for dimen_i in range(param_dimen_count_dict[param_name]):
                    param_dimen_names_dict[param_name].append(crt_param_line[1])
                    crt_param_line = crt_param_enumerate.next()
                ## Read in number of parameter values
                param_values_count_dict[param_name] = int(crt_param_line[1])
                crt_param_line = crt_param_enumerate.next()
                ## Read in parameter type
                param_type_dict[param_name] = int(crt_param_line[1])
                ## Read in parameter values
                ## Get next in loop is place intentionally
                ## Placing  after getting the value causes it to skip next break
                for i in range(param_values_count_dict[param_name]):
                    crt_param_line = crt_param_enumerate.next()
                    if param_type_dict[param_name] == 1:
                        param_values_dict[param_name][i] = int(crt_param_line[1])
                    if param_type_dict[param_name] in [2, 3]:
                        param_values_dict[param_name][i] = float(crt_param_line[1])
                    if param_type_dict[param_name] == 4:
                        param_values_dict[param_name][i] = crt_param_line[1]
        del crt_param_enumerate, crt_param_lines, crt_param_line

        ## Add lake HRU's to groundwater cascades
        logging.info('Modifying CRT groundwater parameters for all lake HRU\'s')
        logging.info('  gw_up_id = HRU_ID (lake)')
        logging.info('  gw_down_id = 0')
        ##logging.info('  gw_strmseg_down_id = OUTSEG')
        logging.info('  gw_strmseg_down_id = 2')
        logging.info('  gw_pct_up = 1')
        lake_hru_id_dict = dict([
            (row[1], row[2]) for row in arcpy.da.SearchCursor(
                hru_polygon_path, (hru_type_field, hru_id_field, outseg_field))
            if int(row[0]) == 2])
        for lake_hru_id, outseg in sorted(lake_hru_id_dict.items()):
            i = dimen_size_dict['ncascdgw']
            dimen_size_dict['ncascdgw'] += 1
            param_values_dict['gw_up_id'][i] = lake_hru_id
            param_values_dict['gw_down_id'][i] = 0
	    ## DEADBEEF - PRMS didn't like when set to OUTSEG, but 2 worked?
            ##param_values_dict['gw_strmseg_down_id'][i] = outseg
            param_values_dict['gw_strmseg_down_id'][i] = 2
            param_values_dict['gw_pct_up'][i] = 1.00
        param_values_count_dict['gw_up_id'] = dimen_size_dict['ncascdgw']
        param_values_count_dict['gw_down_id'] = dimen_size_dict['ncascdgw']
        param_values_count_dict['gw_strmseg_down_id'] = dimen_size_dict['ncascdgw']
        param_values_count_dict['gw_pct_up'] = dimen_size_dict['ncascdgw']
        logging.info('  ncascade = {0}'.format(dimen_size_dict['ncascade']))
        logging.info('  ncascdgw = {0}'.format(dimen_size_dict['ncascdgw']))


        ## DEADBEEF
        ## Override -999 values
        ##logging.info('\nChanging SOIL_MOIST_MAX nodata (-999) to 2')
        ##for i,v in param_values_dict['soil_moist_max'].items():
        ##    if v == -999: param_values_dict['soil_moist_max'][i] = 2
        ##logging.info('Changing SOIL_RECHR_MAX nodata (-999) to 1')
        ##for i,v in param_values_dict['soil_rechr_max'].items():
        ##    if v == -999: param_values_dict['soil_rechr_max'][i] = 1
        ##logging.info('Changing SAT_THRESHOLD nodata (-999) to 4')
        ##for i,v in param_values_dict['sat_threshold'].items():
        ##    if v == -999: param_values_dict['sat_threshold'][i] = 4
        
        ## Override negative values
        ##logging.info('Changing negative SSR2GW_RATE (< 0) to 0.1 (PRMS default)')
        ##for i,v in param_values_dict['ssr2gw_rate'].items():
        ##    if v < 0: param_values_dict['ssr2gw_rate'][i] = 0.1
        ##raw_input('ENTER')


        ## Write dimensions/parameters to PRMS param file
        logging.info('\nWriting parameter file')
        with open(prms_parameter_path, 'w') as output_f:
            output_f.write(file_header_str + '\n')
            ## Dimensions
            output_f.write(dimen_header_str + '\n')
            ## Write dimensions that are known first
            ##remove_list = []
            logging.info('  Set dimensions')
            for dimen_name, dimen_size in sorted(dimen_size_dict.items()):
                if not dimen_size: continue
                logging.debug('    {0}'.format(dimen_name))
                output_f.write(break_str+'\n')
                output_f.write(dimen_name+'\n')
                output_f.write(str(dimen_size)+'\n')
                ## DEADBEEF - It seems bad to remove items during iteration
                del dimen_size_dict[dimen_name]
                ##remove_list.append(dimen_name)
            ##for dimen_name in remove_list: del dimen_size_dict[dimen_name]
            ## Then write unset dimensions
            logging.info('  Unset dimensions')
            for dimen_name in sorted(dimen_size_dict.keys()):
                logging.debug('  {0}'.format(dimen_name))
                output_f.write(break_str+'\n')
                output_f.write(dimen_name+'\n')
                output_f.write(str(dimen_size_dict[dimen_name])+'\n')
             
            ## Parameters
            output_f.write(param_header_str + '\n')
            ## Write unset parameters first
            logging.info('  Unset parameters')
            for param_name in sorted(param_name_dict.keys()):
                if param_name in param_values_dict.keys(): continue
                logging.debug('    {0}'.format(param_name))
                output_f.write(break_str+'\n')
                output_f.write('{0} {1}\n'.format(
                    param_name, param_width_dict[param_name]))
                output_f.write('{0}\n'.format(param_dimen_count_dict[param_name]))
                for dimen_name in param_dimen_names_dict[param_name]:
                    output_f.write(dimen_name + '\n')
                output_f.write(str(param_values_count_dict[param_name]) + '\n')
                param_type = param_type_dict[param_name]
                output_f.write(str(param_type) + '\n')
                output_f.write('' + '\n')
                ## DEADBEEF - It seems bad to remove items during iteration
                del param_name_dict[param_name]
                ##del param_width_dict[param_name]
                ##del param_dimen_count_dict[param_name]
                ##del param_dimen_names_dict[param_name]
                ##del param_values_count_dict[param_name]
                ##del param_type_dict[param_name]
            
            ## Then write set parameters
            logging.info('  Set parameters')
            for param_name in sorted(param_name_dict.keys()):
                logging.debug('  {0}'.format(param_name))
                output_f.write(break_str+'\n')
                output_f.write('{0} {1}\n'.format(
                    param_name, param_width_dict[param_name]))
                output_f.write('{0}\n'.format(param_dimen_count_dict[param_name]))
                for dimen_name in param_dimen_names_dict[param_name]:
                    output_f.write(dimen_name + '\n')
                output_f.write(str(param_values_count_dict[param_name]) + '\n')
                param_type = param_type_dict[param_name]
                output_f.write(str(param_type) + '\n')
                for i, param_value in param_values_dict[param_name].items():
                    if param_type == 1:
                        output_f.write('{0:d}'.format(param_value) + '\n')
                    elif param_type == 2:
                        output_f.write('{0:f}'.format(param_value) + '\n')
                    elif param_type == 3:
                        output_f.write('{0:f}'.format(param_value) + '\n')
                    elif param_type == 4:
                        output_f.write('{0}'.format(param_value) + '\n')
        ## Close file
        output_f.close()

    except:
        logging.exception('Unhandled Exception Error\n\n')
        raw_input('ENTER')

    finally:
        pass

################################################################################

import operator
def prod(iterable):
    return reduce(operator.mul, iterable, 1)

def isfloat(s):
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False

##class dimension():
##    def __init__(self, i, data_lines):
##        self.i = i
##        self.NAME = data_lines[0]
##        self.SIZE = int(data_lines[1])
##        print self.NAME, self.SIZE
##
##class parameter():
##    ##type_dict = dict()
##    ##type_dict[1] = 'INTEGER'
##    ##type_dict[2] = 'FLOAT'
##    ##type_dict[3] = 'DOUBLE'
##    ##type_dict[4] = 'STRING'
##    def __init__(self, i, data_lines):
##        self.i = i
##        #### Not all names have a width (hvr_hru_pct, gvr_hru_id, gvr_cell_id)
##        try: self.NAME, self.WIDTH = data_lines[0].split()
##        except ValueError: self.NAME, self.WIDTH = data_lines[0], 0
##        #### There can be multiple dimensions
##        self.NO_DIMENSIONS = int(data_lines[1])
##        self.DIMENSION_NAMES = []
##        for i in range(self.NO_DIMENSIONS):
##            self.DIMENSION_NAMES.append(data_lines[2+i])
##        self.N_VALUES = int(data_lines[3+i])
##        self.TYPE = data_lines[4+i]
##        self.VALUE = data_lines[5+i:]
##        print self.NAME, self.WIDTH, self.NO_DIMENSIONS,
##        print self.DIMENSION_NAMES, self.N_VALUES, self.TYPE

################################################################################

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='PRMS Template Fill',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '-i', '--ini', required=True,
        help='Project input file', metavar='PATH')
    parser.add_argument(
        '-o', '--overwrite', default=False, action="store_true", 
        help='Force overwrite of existing files')
    parser.add_argument(
        '--debug', default=logging.INFO, const=logging.DEBUG,
        help='Debug level logging', action="store_const", dest="loglevel")
    args = parser.parse_args()

    ## Create Basic Logger
    logging.basicConfig(level=args.loglevel, format='%(message)s')

    #### Get PRMS config file
    ##ini_re = re.compile('\w*.ini$', re.I)
    ##try: 
    ##    ini_path = sys.argv[1]
    ##except IndexError:
    ##    ini_path = get_ini_file(workspace, ini_re, 'prms_template_fill')
    ##del ini_re

    ## Run Information
    logging.info('\n{0}'.format('#'*80))
    log_f = '{0:<20s} {1}'
    logging.info(log_f.format(
        'Run Time Stamp:', dt.datetime.now().isoformat(' ')))
    logging.info(log_f.format('Current Directory:', os.getcwd()))
    logging.info(log_f.format('Script:', os.path.basename(sys.argv[0])))

    ## Fill PRMS Parameter Template File
    prms_template_fill(
        config_path=args.ini, overwrite_flag=args.overwrite,
        debug_flag=args.loglevel==logging.DEBUG)