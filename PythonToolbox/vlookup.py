'''
Performs Excel style VLOOKUP. User defines key and return value fields for both the input (to be modified) and lookup (source of data) features/tables.

Version History
    1.0 (7/2/21)        Added tool
    1.1 (5/2/22)        Modified to be able to populate date fields
    
    UPDATE - This tool has been deprecated.  See Join Field Overwrite for an improved version. Only keeping this up because it
             does let you read Excel files directly, and Join Field Overwrite only works with table views / feature classes in the TOC.

'''

import arcpy
import pandas as pd

class VLookup(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "VLookup"
        self.description = "Performs the equivalent of Excel VLOOKUP"
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        params = []
        
        in_features = arcpy.Parameter(
            displayName="Input Feature or Table",
            name="in_features",
            datatype= ["GPTableView","GPFeatureLayer"],
            parameterType="Required",
            direction="Input")

        in_key = arcpy.Parameter(
            displayName="Input Join Field (used to lookup return value)",
            name="in_key",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        #instead of using dependencies and a Field Type, we are using a GPString value list we will populate later
        in_key.filter.type = "ValueList"
        #in_key.filter.list = []
        
        in_return = arcpy.Parameter(
            displayName="Input Return Field (to be populated)",
            name="in_return",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        in_return.filter.type = "ValueList"
        #in_return.filter.list = []

        look_type = arcpy.Parameter(
            displayName="Define data source type for lookup",
            name="look_type",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        look_type.filter.list = ['Excel', 'ESRI']
        look_type.value = 'Excel'
        
        look_excel = arcpy.Parameter(
            displayName="Lookup Excel file",
            name="look_excel",
            datatype= "DEFile",
            parameterType="Optional",
            direction="Input")
        look_excel.filter.list = ['csv','xls', 'xlsx']
        
        look_excelSheet = arcpy.Parameter(
            displayName="Lookup worksheet",
            name="look_excelSheet",
            datatype= "GPString",
            parameterType="Optional",
            direction="Input")
        look_excelSheet.filter.type = "ValueList"
        look_excelSheet.filter.list = []
        
        look_esri = arcpy.Parameter(
            displayName="Lookup table or feature",
            name="look_esri",
            datatype= ["GPTableView","GPFeatureLayer"],
            parameterType="Optional",
            direction="Input")

        look_key = arcpy.Parameter(
            displayName="Lookup Join Field",
            name="look_key",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        look_key.filter.type = "ValueList"
        look_key.filter.list = []
        
        look_return = arcpy.Parameter(
            displayName="Lookup Return Field",
            name="look_return",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        look_return.filter.type = "ValueList"
        look_return.filter.list = []
        
        overwrite = arcpy.Parameter(
            displayName="Clear / Overwrite behavior",
            name="overwrite",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        overwrite.filter.list = ['Clear all existing values','Overwrite existing values','Do not overwrite']
        overwrite.value = 'Overwrite existing values'
        
        params.append(in_features)      #0
        params.append(in_key)           #1
        params.append(in_return)        #2
        params.append(look_type)        #3
        params.append(look_excel)       #4
        params.append(look_excelSheet)  #5
        params.append(look_esri)        #6
        params.append(look_key)         #7
        params.append(look_return)      #8
        params.append(overwrite)        #9

        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        
        #disable 4-8
        parameters[4].enabled = False
        parameters[5].enabled = False
        parameters[6].enabled = False
        #parameters[7].enabled = False
        #parameters[8].enabled = False
        
        #if in_features is selected, reset key/return and populate filter lists
        if parameters[0].altered and not parameters[0].hasBeenValidated:
            #parameters[1].value = None
            #parameters[2].value = None
            parameters[1].filter.list = [f.name for f in arcpy.ListFields(parameters[0].value) 
                                            if f.type not in ['Geometry','Blob'] 
                                            and f.name.lower() not in ['shape_area','shape_length']]
            parameters[2].filter.list = [f.name for f in arcpy.ListFields(parameters[0].value) 
                                if f.type not in ['Geometry','Blob'] 
                                and f.name.lower() not in ['shape_area','shape_length']]
        

        #if type changes, clear everything below it
        #if parameters[3].altered and not parameters[3].hasBeenValidated:
            #parameters[4].value = None
            #parameters[5].value = None
            #parameters[6].value = None
            #parameters[7].value = None
            #parameters[8].value = None

        if parameters[3].valueAsText in ['Excel']:
            parameters[4].enabled = True
            parameters[5].enabled = True
            #if workbook is define, list the sheets
            if parameters[4].altered and not parameters[4].hasBeenValidated:
                parameters[5].filter.list = pd.ExcelFile(parameters[4].valueAsText).sheet_names
            #when 5(Excel sheet) is first set, populate 7/8 list. If 5 has a value, make sure 7/8 stay enabled
            #if parameters[5].value:
            #    parameters[7].enabled = True
            #    parameters[8].enabled = True
            if parameters[5].altered and not parameters[5].hasBeenValidated:
                #populate list for 7,8 (key and return fields)
                parameters[7].filter.list = list(pd.read_excel(parameters[4].valueAsText, sheet_name=parameters[5].valueAsText).columns)
                parameters[8].filter.list = list(pd.read_excel(parameters[4].valueAsText, sheet_name=parameters[5].valueAsText).columns)
        else:
            parameters[6].enabled = True
            #if 6 has value (ESRI source defined)
            #if parameters[6].value:
            #    parameters[7].enabled = True
            #    parameters[8].enabled = True
            if parameters[6].altered and not parameters[6].hasBeenValidated:
                #populate list for 7,8 (key and return fields)
                parameters[7].filter.list = [f.name for f in arcpy.ListFields(parameters[6].value) 
                                                if f.type not in ['Geometry'] 
                                                and f.name.lower() not in ['shape_area','shape_length']]
                parameters[8].filter.list = [f.name for f in arcpy.ListFields(parameters[6].value) 
                                                if f.type not in ['Geometry']]


        return
        
    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        
        #Throw a warning if there are duplicate values in the lookup_key field.
        #if Excel selected, load dataframe and run duplicated()
        if parameters[4].value and parameters[5].value and parameters[7].value:
            if pd.read_excel(parameters[4].valueAsText, sheet_name=parameters[5].valueAsText, usecols = [parameters[7].valueAsText]).duplicated().sum()>0:
                parameters[7].setWarningMessage('Duplicate values found in Key field. Last instance will be used')
        #if esri selected, get unique and compare to rows to test for dupes
        if parameters[6].value and parameters[7].value:
            if len(set(row[0] for row in arcpy.da.SearchCursor(parameters[6].value, parameters[7].value))) < int(arcpy.GetCount_management(parameters[6].value).getOutput(0)):
                parameters[7].setWarningMessage('Duplicate values found in Key field. Last instance will be used')
         
        #Check that key and return aren't the same field for Input or Lookup
        if parameters[1].value and parameters[2].value:
            if parameters[1].value == parameters[2].value:
                parameters[1].setErrorMessage('Key and Return fields cannot be identical')
                parameters[2].setErrorMessage('Key and Return fields cannot be identical')
        if parameters[7].value and parameters[8].value:
            if parameters[7].value == parameters[8].value:
                parameters[7].setErrorMessage('Key and Return fields cannot be identical')
                parameters[8].setErrorMessage('Key and Return fields cannot be identical') 
        
        #If Excel selected, make sure there are at least two valid fields in that sheet
        if parameters[4].value and parameters[5].value:
            if len(list(pd.read_excel(parameters[4].valueAsText, sheet_name=parameters[5].valueAsText).columns)) < 2:
                parameters[5].setErrorMessage('Please select an Excel sheet with at least two valid data fields')
                
        
        
        ##Compare data types for the Return Fields to make sure the script won't crash, and warn user about coercion.
        #ArcPy types are Date, Double, Integer, SmallInteger, String
        #Pandas types (from excel) are object, int64, datetime64[ns], float64
        
        #if both return fields are populated
        if parameters[2].value and parameters[8].value:
            #compare esri data types and show warnings as necessary
            if parameters[3].valueAsText == 'ESRI':
                inType =  arcpy.ListFields(parameters[0].value,parameters[2].valueAsText)[0].type
                lookType = arcpy.ListFields(parameters[6].value,parameters[8].valueAsText)[0].type
                if inType in ['Date'] and lookType not in ['Date']:
                    parameters[8].setErrorMessage('Lookup Return field type ({}) will not match Input Return field type {})'.format(lookType,inType))
                if inType in ['Integer','SmallInteger'] and lookType in ['Single','Double']:
                    parameters[8].setWarningMessage('Lookup Return field type ({}) does not match Input Return field type ({}) and may be coerced'.format(lookType,inType))
                if inType in ['Integer','SmallInteger'] and lookType not in ['Single','Double','Integer','SmallInteger']:
                    parameters[8].setErrorMessage('Lookup Return field type ({}) will not match Input Return field type ({})'.format(lookType,inType))
                if inType in ['String'] and lookType not in ['String']:
                    parameters[8].setWarningMessage('Lookup Return field type ({}) does not match Input Return field type ({}) and may be coerced'.format(lookType,inType))
                if inType in ['Single','Double'] and not lookType in ['Single','Double','Integer','SmallInteger']:
                    parameters[8].setWarningMessage('Lookup Return field type ({}) will not match Input Return field type ({})'.format(lookType,inType))
            else: #compare esri to pandas data types and show warnings as necessary
                inType =  arcpy.ListFields(parameters[0].value,parameters[2].valueAsText)[0].type
                #get pandas type from data frame from excel. Change object to string, just so the user can interpret it
                lookType = pd.read_excel(parameters[4].valueAsText, sheet_name=parameters[5].valueAsText)[parameters[8].valueAsText].dtype.name
                if lookType == 'object':lookType='String'

                if inType in ['Date'] and lookType not in ['datetime64[ns]']:
                    parameters[8].setWarningMessage('Lookup Return field type ({}) may not match Input Return field type ({}) - Verify results'.format(lookType,inType))
                if inType in ['Integer','SmallInteger'] and lookType in ['float64']:
                    parameters[8].setWarningMessage('Lookup Return field type ({}) does not match Input Return field type ({}) and may be coerced'.format(lookType,inType))
                if inType in ['Integer','SmallInteger'] and lookType not in ['int64','float64']:
                    parameters[8].setErrorMessage('Lookup Return field type ({}) will not match Input Return field type ({})'.format(lookType,inType))
                if inType in ['String'] and lookType not in ['String']:
                    parameters[8].setWarningMessage('Lookup Return field type ({}) does not match Input Return field type ({}) and may be coerced'.format(lookType,inType))
                if inType in ['Single','Double'] and not lookType in ['int64','float64']:
                    parameters[8].setWarningMessage('Lookup Return field type ({}) will not match Input Return field type ({})'.format(lookType,inType))
            
        ##Add another set of checks to make sure the Key fields are the same type too (all warnings, no errors, since the script won't fail, it just won't change any table values)    
        
            
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        #filename = r"C:\Users\PWSMIT32\Documents\ArcGIS\Projects\Tool_Dev\Lookuptest.xlsx"
        
        #get vars
        in_features = parameters[0].value
        in_key      = parameters[1].valueAsText
        in_return   = parameters[2].valueAsText
        look_type   = parameters[3].valueAsText
        look_excel  = parameters[4].valueAsText
        look_excelSheet = parameters[5].valueAsText
        look_esri   = parameters[6].value
        look_key    = parameters[7].valueAsText
        look_return = parameters[8].valueAsText
        overwrite   = parameters[9].valueAsText
            
        
#look_excel = r"C:\Users\PWSMIT32\Documents\ArcGIS\Projects\Tool_Dev\Lookuptest.xlsx"
#look_excelSheet = 'Sheet1'
#look_key = 'IntField'
#look_return = 'TextField'
        inKeyType =  arcpy.ListFields(in_features,in_key)[0].type
        inRetType =  arcpy.ListFields(in_features,in_return)[0].type
        
        #Build the lookup dictionary from the excel/esri src
        look_dict = {}
        if look_type == 'Excel':
            look_df   = pd.read_excel(look_excel, sheet_name=look_excelSheet,usecols = [look_key,look_return])
            #If we are populating a date field, we need to convert the pandas from object to datetime
            if inRetType in ['Date']:
                look_df[look_return] = pd.to_datetime(look_df[look_return])
            # Might need to also coerce integers into strings
            if inKeyType in ['String'] and look_df[look_key].dtype.name != 'object':
                look_df[look_key] = look_df[look_key].astype(str)
            look_dict = dict(zip(look_df[look_key],look_df[look_return]))
        else:
            with arcpy.da.SearchCursor(look_esri,[look_key,look_return]) as cursor:
                for row in cursor:
                    look_dict[row[0]] = row[1]
        
        #Use the dictionary to update the input data
        with arcpy.da.UpdateCursor(in_features,[in_key,in_return]) as cursor:
            for row in cursor:
                #if clearing all values, set return to None
                if overwrite in ['Clear all existing values']:
                    row[1] = None
                #if overwriting, or if return is currently empty, populate it.
                if overwrite in ['Clear all existing values','Overwrite existing values'] or row[1] is None or str(row[1]).strip()=='':
                    if row[0] in look_dict.keys():
                        messages.AddMessage('Key {} and new value {}'.format(row[0],look_dict[row[0]]))
                        row[1] = look_dict[row[0]]
                cursor.updateRow(row)
        
        return
