"""
Sum (Count) features in zone by type and add results to input polygon
    
Version History
    1.0 (10/11/21)       Created JT
    2.0 (01/19/22)       Reworked to allow use to define summary field names, and optional new output

"""

import arcpy
import os
from arcpy import env
from arcpy.sa import *
import pandas as pd
import numpy as np


class CountFeaturesInZone(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Count Features In Zone"
        self.description = "Count features in polygon zone by type and add result fields to input polygon"
        self.canRunInBackground = False

    def getParameterInfo(self):
        #Define parameter definitions
        params = []      
           
        sumfeature = arcpy.Parameter( #0
            displayName="Feature to Sum",
            name="sumfeature",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input")
            
        sumfeaturefield = arcpy.Parameter( #1
            displayName="Feature Field to Sum",
            name="sumfeaturefield",
            datatype="GPString",
            parameterType="Required",
            direction="Input")    
        
        sumzone = arcpy.Parameter(  #2
            displayName="Target Zone Features",
            name="sumzone",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input")
        sumzone.filter.list = ["Polygon"]
 
        sumzonefield = arcpy.Parameter(  #3
            displayName="Target Feature Zone Field",
            name="sumzonefield",
            datatype="GPString",
            parameterType="Required",
            direction="Input") 
 
        fieldnames = arcpy.Parameter(
            displayName='',
            name='fieldnames',
            datatype='GPValueTable',
            parameterType='Required',
            direction='Input',
            category = 'Summary Field Names')
        fieldnames.columns = [['GPString', 'Feature Field Values'], ['GPString', 'Name of Output Sum Field']]
    
    
        makenew = arcpy.Parameter(
            displayName="Create new output feature class?",
            name="makenew",
            datatype="GPBoolean",
            parameterType="Required",
            direction="Input")
        makenew.value = False
        
        output = arcpy.Parameter(
            displayName="Output Feature Class",
            name="output",
            datatype="DEFeatureClass",
            parameterType="Optional",
            direction="Output",
            enabled=False)
            
        params =   [sumfeature,         #0
                    sumfeaturefield,    #1
                    sumzone,            #2
                    sumzonefield,       #3
                    fieldnames,         #4
                    makenew,            #5
                    output]             #6          


        return params            

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True
        
    def updateParameters(self, parameters):
        #if Feature to Sum is defined/changed, populate field list
        if parameters[0].value and not parameters[0].hasBeenValidated:
            parameters[1].filter.list = [f.name for f in arcpy.ListFields(parameters[0].value) if f.type in ['String','Integer','SmallInteger']]
        
        #if Target Zone Features is defined/changed, populate field list
        if parameters[2].value and not parameters[2].hasBeenValidated:
            parameters[3].filter.list = [f.name for f in arcpy.ListFields(parameters[2].value) if f.type in ['OID','String','Integer','Double','Single','SmallInteger']]
            
        #if user wants to create new output, let them, and prepopulate name
        if parameters[5].value:
            parameters[6].enabled = True
        else:
            parameters[6].enabled = False
        if not parameters[5].hasBeenValidated and parameters[2].value:
            #use validate and unique to make sure the output fc name is good
            outname = arcpy.CreateUniqueName(arcpy.ValidateTableName(arcpy.Describe(parameters[2].valueAsText).aliasName,arcpy.env.workspace),arcpy.env.workspace)
            parameters[6].value = outname
            
        #populate value table whenever 'feature field to sum' is selected
        if parameters[1].altered and not parameters[1].hasBeenValidated:
            #convert everything to string
            featvals = list(set(str(row[0]) for row in arcpy.da.SearchCursor(parameters[0].valueAsText, parameters[1].valueAsText)))
            #check for nulls /empties and assign them names so we can sort
            #featvals = ['_Null' if x is None else x for x in featvals]
            featvals = ['_Null' if x == 'None' else x for x in featvals]
            featvals = ['_EmptyString' if x=='' else x for x in featvals]
            featvals = sorted(featvals)
            #name fields for each value as 'Sum_val', validated as field names
            fldnames = [arcpy.ValidateFieldName(('Sum_'+str(x))) for x in featvals]
            #create list of lists, showing the field values and the output sum field names. This is the GPValueTable
            #[['val1', 'name1'],['val2', 'name2']]
            valtbl   = []
            for idx, val in enumerate(featvals):
                valtbl.append([val,fldnames[idx]])
            
            #define GPValueTable, and filter the first field to only allow field vals
            parameters[4].values = valtbl               
            parameters[4].filters[0].type = 'ValueList'
            parameters[4].filters[0].list = featvals


    def updateMessages(self, parameters):
        #if ValueTable is updated
        if parameters[4].altered and not parameters[4].hasBeenValidated:
            #clear message
            parameters[4].clearMessage()
            #get list of field names
            checknames = []
            for idx,val in enumerate(parameters[4].values):
                checknames.append(val[1])
            #if we have the sumzone fc defined
            if parameters[2].value:
                warn = 0
                warning = ''
                #compare each new field name to existing field names, add warning if it exists already
                existname = [f.name for f in arcpy.ListFields(parameters[2].valueAsText)]
                for name in checknames:
                    if name in existname:
                        warn = 1
                        warning = warning + "Field '{}' already exists and will be replaced. ".format(name)
                if warn > 0:
                    parameters[4].setWarningMessage(warning)
                    
            #also check for duplicate field names and throw error. Names must be unique.
            if len(checknames) != len(set(checknames)):
                parameters[4].setErrorMessage('Field names must be unique')
                
        #also warn if new output will overwrite something
        if parameters[6].altered and not parameters[6].hasBeenValidated:
            if arcpy.Exists(parameters[6].valueAsText):
                parameters[6].setWarningMessage('Existing feature class will be overwritten')
       
        return
        
    def execute(self, parameters, messages):
        """The source code of the tool."""
        
        arcpy.env.addOutputsToMap = True
        arcpy.env.overwriteOutput = True

        messages.addMessage("------------------------")
        for param in parameters:
            messages.addMessage("%s = %s" % (param.name, param.valueAsText))
        messages.addMessage("------------------------") 
        
        #Define parameters    
        SumFeature      = parameters[0].valueAsText
        SumFeatureField = parameters[1].valueAsText
        SumZone         = parameters[2].valueAsText
        SumZoneField    = parameters[3].valueAsText
        GPValueTable    = parameters[4].values
        MakeNew         = parameters[5].value
        Output          = parameters[6].valueAsText

        #if they want new output, copy it and redefine vars
        if MakeNew:
            messages.addMessage("Creating new output {}".format(Output))
            arcpy.management.CopyFeatures(SumZone, Output)
            SumZone = Output
        arcpy.env.addOutputsToMap = False
        
        #turn GPValueTable into list of field values and field names
        fieldvals  = []
        fieldnames = []
        for idx, val in enumerate(GPValueTable):
            fieldvals.append(val[0])
            fieldnames.append(val[1])

        #Turn empty strings and None back into those vals
        #using -999 for nulls since pandas doesn't allow null int
        fieldvals = ['-999' if x=='_Null' else x for x in fieldvals]
        fieldvals = ['' if x=='_EmptyString' else x for x in fieldvals]

        #create a dictionary to get values from the field names
        messages.addMessage("Defining Dictionary of values and field names...")
        d_nameval = {}
        for idx, val in enumerate(fieldnames):
            d_nameval[val] = fieldvals[idx]

        #create a dictionary to get list of OIDs for each value in SumZoneField
        messages.addMessage("Defining zones...")
        d_zoneOID = {}
        #different query is Zone field is string or numeric
        zType = [f.type for f in arcpy.ListFields(SumZone) if f.name == SumZoneField][0]
        if zType == 'String':
            for z in set(row[0] for row in arcpy.da.SearchCursor(SumZone, SumZoneField)):
                d_zoneOID[z] = [row[0] for row in arcpy.da.SearchCursor(SumZone, arcpy.Describe(SumZone).OIDFieldName,where_clause = SumZoneField+" = '"+z+"'")]
        else:   
            for z in set(row[0] for row in arcpy.da.SearchCursor(SumZone, SumZoneField)):
                d_zoneOID[z] = [row[0] for row in arcpy.da.SearchCursor(SumZone, arcpy.Describe(SumZone).OIDFieldName,where_clause = SumZoneField+" = "+str(z))]
                
        #Use summarize within, with the group field, to create our temp output fc and tbl.
        messages.addMessage("Summarizing data within zones...")
        tempfc  = arcpy.CreateUniqueName("sumwithfc", arcpy.env.scratchGDB)
        temptbl = arcpy.CreateUniqueName("sumwithtbl", arcpy.env.scratchGDB)
        arcpy.analysis.SummarizeWithin(SumZone, SumFeature, tempfc, "KEEP_ALL", None, "ADD_SHAPE_SUM", '', SumFeatureField, "NO_MIN_MAJ", "NO_PERCENT", temptbl)
        
        #convert table to pandas dataframe, must faster to query!
        #using -999 for nulls since pandas doesn't allow null int
        messages.addMessage("Creating dataframe...")
        df = pd.DataFrame(arcpy.da.TableToNumPyArray(temptbl,'*',skip_nulls=False,null_value='-999'))
        #convert vals to strings since that's what GPValueTable provided
        df[SumFeatureField] = df[SumFeatureField].astype(str)
        
        #and delete SummarizeWithin outputs, since we don't need them anymore
        messages.addMessage("Deleting intermediate results...")
        arcpy.management.Delete(tempfc)
        arcpy.management.Delete(temptbl)
        
        #add fields to SumZone
        messages.addMessage("Adding Fields...")
        fieldnames.append('Feature_Sum')
        arcpy.management.DeleteField(SumZone,fieldnames)
        for f in fieldnames:
            arcpy.management.AddField(SumZone, f, 'LONG')
        
        #start populating data. For each zone
        messages.addMessage("Populating summary fields in output feature class...")
        for z in d_zoneOID:
            #define query for just these zones
            id_list = d_zoneOID[z] 
            query_oid = arcpy.Describe(SumZone).OIDFieldName+" IN ({:s})".format(','.join(f"{x}" for x in id_list))
            #and query down the dataframe to just this zone
            df2 = df[df['Join_ID'].isin(id_list)]
            #select the rows for just this zone, and the fields we are interested in
            with arcpy.da.UpdateCursor(SumZone,fieldnames,where_clause=query_oid) as cursor:
                for row in cursor:
                    #now loop through the fields and query the vals from the df
                    for i0 in range(len(d_nameval)):
                        #get list of JoinID (OID of original zones) and the type / unique val of feature field
                        type_list = [d_nameval[fieldnames[i0]]]
                        #query down the dataframe to just those vals
                        df3 = df2[df2[SumFeatureField].isin(type_list)]
                        #sum the Count column (last column) in df
                        row[i0] = sum(df3[df3.columns[-1]])
                    #feature_sum is just the sum of the other fields
                    row[len(fieldnames)-1] = sum(row[0:len(fieldnames)-1])
                    cursor.updateRow(row)
                    
        messages.addMessage("Script Complete!")            
#End