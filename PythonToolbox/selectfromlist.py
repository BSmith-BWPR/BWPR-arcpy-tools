"""
User defines source of list of values (ESRI or Excel).  Selects all features in target matching that list.
    
Version History
    1.0 (04/14/2022)        Created
"""

import arcpy
import pandas as pd

class SelectFromList(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Select from List"
        self.description = "Selects all target features found in list"
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        params = []
        
        in_features = arcpy.Parameter(
            displayName="Input Target Layer to Select",
            name="in_features",
            datatype= ["GPTableView","GPFeatureLayer"],
            parameterType="Required",
            direction="Input")

        in_field = arcpy.Parameter(
            displayName="Input Target Field to Select On",
            name="in_field",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        #instead of using dependencies and a Field Type, we are using a GPString value list we will populate later
        in_field.filter.type = "ValueList"
        
        sel_type = arcpy.Parameter(
            displayName="Selection Type",
            name="sel_type",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        sel_type.filter.type = "ValueList"
        sel_type.filter.list = ['NEW_SELECTION','ADD_TO_SELECTION','REMOVE_FROM_SELECTION','SUBSET_SELECTION']
        sel_type.value = 'NEW_SELECTION'
        
        list_type = arcpy.Parameter(
            displayName="Define List Data Source",
            name="list_type",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        list_type.filter.list = ['Excel', 'ESRI']
        list_type.value = 'Excel'
        
        excelFile = arcpy.Parameter(
            displayName="Excel File",
            name="excelFile",
            datatype= "DEFile",
            parameterType="Optional",
            direction="Input")
        excelFile.filter.list = ['csv','xls', 'xlsx']
        
        excelSheet = arcpy.Parameter(
            displayName="Worksheet Name",
            name="excelSheet",
            datatype= "GPString",
            parameterType="Optional",
            direction="Input")
        excelSheet.filter.type = "ValueList"
        excelSheet.filter.list = []
        
        esriFile = arcpy.Parameter(
            displayName="Feature or Table",
            name="esriFile",
            datatype= ["GPTableView","GPFeatureLayer"],
            parameterType="Optional",
            direction="Input")

        list_field = arcpy.Parameter(
            displayName="List Field",
            name="list_field",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        list_field.filter.type = "ValueList"
        list_field.filter.list = []
        
        
        params.append(in_features)     #0
        params.append(in_field)        #1
        params.append(sel_type)        #2
        params.append(list_type)       #3
        params.append(excelFile)       #4
        params.append(excelSheet)      #5
        params.append(esriFile)        #6
        params.append(list_field)      #7


        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        
        p = {p.name: p for p in parameters}
        
        #disable until type known
        p['excelFile'].enabled  = False
        p['excelSheet'].enabled = False
        p['esriFile'].enabled   = False
        #if in_features is selected, reset key/return and populate filter lists
        if p['in_features'].altered and not p['in_features'].hasBeenValidated:
            p['in_field'].filter.list = [f.name for f in arcpy.ListFields(parameters[0].value) 
                                            if f.type not in ['Geometry','Blob']]

        if p['list_type'].valueAsText in ['Excel']:
            p['excelFile'].enabled  = True
            p['excelSheet'].enabled = True
            #if workbook is define, list the sheets
            if p['excelFile'].altered and not p['excelFile'].hasBeenValidated:
                p['excelSheet'].filter.list = pd.ExcelFile(p['excelFile'].valueAsText).sheet_names
                
            if p['excelSheet'].altered and not p['excelSheet'].hasBeenValidated:
                p['list_field'].filter.list = list(pd.read_excel(p['excelFile'].valueAsText, sheet_name=p['excelSheet'].valueAsText).columns)
                
                
        else:
            p['esriFile'].enabled = True
            if p['esriFile'].altered and not p['esriFile'].hasBeenValidated:
                #populate list for 7,8 (key and return fields)
                p['list_field'].filter.list = [f.name for f in arcpy.ListFields(parameters[6].value) 
                                                if f.type not in ['Geometry','Blob']]


        return
        
    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        
        p = {p.name: p for p in parameters}
        
        if p['in_field'].altered and not p['in_field'].hasBeenValidated:
            in_type =  arcpy.ListFields(p['in_features'].valueAsText,p['in_field'].valueAsText)[0].type
            if in_type in ['Date']:
                p['in_field'].setWarningMessage('Tool not set up to work with dates yet...')
            else:
                p['in_field'].clearMessage()
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        
        p = {p.name: p for p in parameters}
        #get parameters
        in_features = p['in_features'].valueAsText
        in_field    = p['in_field'].valueAsText
        sel_type    = p['sel_type'].valueAsText
        list_type   = p['list_type'].valueAsText
        excelFile   = p['excelFile'].valueAsText
        excelSheet  = p['excelSheet'].valueAsText
        esriFile    = p['esriFile'].valueAsText
        list_field  = p['list_field'].valueAsText
        
        #Build the list from the excel/esri src
        stringFlag = 0
        if list_type == 'Excel':
            df = pd.read_excel(excelFile, sheet_name=excelSheet,usecols = [list_field], dtype=str)
            sel_list = df[list_field].dropna().unique().tolist()
        else:
            sel_list = sorted({row[0] for row in arcpy.da.SearchCursor(esriFile, [list_field])},key=lambda x: (x is None, x))

        
        #Define the query based on if in_field is numeric or string
        in_type =  arcpy.ListFields(in_features,in_field)[0].type
        if in_type.lower() in ('string','guid','globalid'):
            query = in_field+" IN ({:s})".format(','.join(f"'{x}'" for x in sel_list))
        else:
            query = in_field+" IN ({:s})".format(','.join(f"{x}" for x in sel_list))
        
        arcpy.AddMessage('{}'.format(query))
        #and select by attribute
        arcpy.management.SelectLayerByAttribute(in_features, sel_type, query)
        
        return