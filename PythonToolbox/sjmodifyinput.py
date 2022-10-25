"""
ESRI Spatial Join, but the input target dataset is modified. User can add or edit existing fields based on spatial join
    
Version History
    1.0 (02/28/2022)       Created
"""

import os
import arcpy


class SpatialJoinModify(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Spatial Join (Modify Input)"
        self.description = "Performs ESRI Spatial Join, but modifying the input instead of creating new feature class"
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        params = []
        
        #0
        target_features = arcpy.Parameter(
            displayName="Target Features",
            name="target_features",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input")
        
        #1
        join_features = arcpy.Parameter(
            displayName="Join Features",
            name="join_features",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input")    

        #2
        fieldnames = arcpy.Parameter(
            displayName='',
            name='fieldnames',
            datatype='GPValueTable',
            parameterType='Required',
            direction='Input',
            category = 'Summary Field Names')
        fieldnames.columns = [['GPString', 'Join Feature Fields:'], ['GPString', 'Added to Target as:']]
         
        #3
        match_option = arcpy.Parameter(
            displayName="Match Option",
            name="match_option",
            datatype="GPString",
            parameterType="Required",
            direction="Input")    
        match_option.filter.list = ['Intersect','Within a distance','Contains','Completely contains','Within','Completely Within','Are identical to',
                                    'Boundary touches','Share a line segment with','Have their center in','Closest','Largest Overlap']
        match_option.value = 'Intersect'
        
        #4
        search_radius = arcpy.Parameter(
            displayName="Search Radius",
            name="search_radius",
            datatype="GPLinearUnit",
            parameterType="Optional",
            direction="Input")  
        
        #5
        overwrite = arcpy.Parameter(
            displayName="Overwrite Options",
            name="overwrite",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
            category = 'Summary Field Names')
        overwrite.filter.list = ['Do not overwrite','Overwrite only if spatial join found','Overwrite with Nulls if no spatial join found']
        overwrite.value = 'Overwrite only if spatial join found'
        overwrite.enabled = False
        
        params = [target_features,join_features,fieldnames,match_option,search_radius,overwrite]
        
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        
        if parameters[1].altered and not parameters[1].hasBeenValidated:
            #get field list from join features
            joinfields = [f.name for f in arcpy.ListFields(parameters[1].value) 
                                            if f.type not in ['Geometry','Blob','OID'] 
                                            and f.name.lower() not in ['shape_area','shape_length']]
            
            #create copy for field list to add to target
            targetfields = [arcpy.ValidateFieldName(x) for x in joinfields]
            
            #create list of lists, showing the field values for join and target. This is the GPValueTable
            #[['val1', 'name1'],['val2', 'name2']]
            valtbl   = []
            for idx, val in enumerate(joinfields):
                valtbl.append([val,targetfields[idx]])
            
            #define GPValueTable, and filter the first field to only allow field vals
            parameters[2].values = valtbl               
            parameters[2].filters[0].type = 'ValueList'
            parameters[2].filters[0].list = joinfields
        
        #if either the target or the field mapping has changed
        if (parameters[0].altered and not parameters[0].hasBeenValidated) or (parameters[2].altered and not parameters[2].hasBeenValidated):
            #get list of existing target names and new target names
            if parameters[0].value and parameters[2].value:
                checknames = [val[1] for val in parameters[2].values]
                existname = [f.name for f in arcpy.ListFields(parameters[0].valueAsText)]
                #if there's any overlap, enable overwrite field
                if len(set(checknames).intersection(existname)) > 0:
                    parameters[5].enabled = True
                else:
                    parameters[5].enabled = False
        
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        #if ValueTable exists
        if parameters[2].value:
            #clear message
            parameters[2].clearMessage()
            #get list of field names to add to target
            checknames = [val[1] for val in parameters[2].values]
            #if we have the target defined
            if parameters[0].value:
                warnMsg = ''
                errMsg = ''
                #compare each new field name to existing field names, add warning if it exists already
                existname = [f.name for f in arcpy.ListFields(parameters[0].valueAsText)]
                for name in checknames:
                    if name in existname:
                        warnMsg = warnMsg + "Field '{}' already exists.\n".format(name)
                        #if the field exists and is read only, throw an error
                        if not arcpy.ListFields (parameters[0].valueAsText,name)[0].editable:
                            errMsg = errMsg + "Field '{}' is not editable.\n".format(name)
                if len(warnMsg) > 0:
                    parameters[2].setWarningMessage(warnMsg+'Specify desired overwrite behavior.')
                if len(errMsg) > 0:
                    parameters[2].setErrorMessage(errMsg)
                    
            #also check for duplicate field names and throw error. Names must be unique.
            if len(checknames) != len(set(checknames)):
                parameters[2].setErrorMessage('Target Field names must be unique')
        
        #also enforce the match_option based on the geometry type
        if (parameters[0].altered and not parameters[0].hasBeenValidated) or (parameters[1].altered and not parameters[1].hasBeenValidated) or (parameters[3].altered and not parameters[3].hasBeenValidated):
            if parameters[0].value and parameters[1].value and parameters[3].value:
                parameters[3].clearMessage()
                target_geom = arcpy.Describe(parameters[0].valueAsText).shapeType
                join_geom   = arcpy.Describe(parameters[1].valueAsText).shapeType
                match_option= parameters[3].ValueAsText.replace(" ", "_").upper()
                                    
                if (match_option in ['CONTAINS','COMPLETELY_CONTAINS']) and ((target_geom == 'Point') or (target_geom == 'Polyline' and join_geom == 'Polygon')):
                    parameters[3].setErrorMessage('ERROR 000561: Relationship invalid for selected layers.')
                    
                if (match_option in ['WITHIN','COMPLETELY_WITHIN']) and ((target_geom == 'Polygon' and join_geom != 'Polygon') or (target_geom != 'Point' and join_geom == 'Point')):
                    parameters[3].setErrorMessage('ERROR 000561: Relationship invalid for selected layers.')
                    
                if (match_option in ['ARE_IDENTICAL_TO']) and (target_geom != join_geom):
                    parameters[3].setErrorMessage('ERROR 000561: Relationship invalid for selected layers.')
                    
                if (match_option in ['SHARE_A_LINE_SEGMENT_WITH']) and (target_geom == 'Point' or join_geom == 'Point'):
                    parameters[3].setErrorMessage('ERROR 000561: Relationship invalid for selected layers.')
                    
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        #Print parameters
        messages.addMessage("------------------------")
        for param in parameters:
            messages.addMessage("%s = %s" % (param.name, param.valueAsText))
        messages.addMessage("------------------------") 
        
        arcpy.env.addOutputsToMap = 0
        arcpy.env.overwriteOutput = True
        
        #Get the input data
        target_features = parameters[0].ValueAsText
        join_features   = parameters[1].ValueAsText
        fieldnames      = parameters[2].values
        match_option    = parameters[3].ValueAsText.replace(" ", "_").upper()
        search_radius   = parameters[4].Value
        overwrite       = parameters[5].Value
            
        ### field mappings won't seem to let us completely ignore existing fields (like if the same field exists in target and join, it 
        ### will always try to add values from target. That is not the desired behavior for this function, so we need to first extract just
        ### geometry and OID from target_features to do our SJ
        messages.addMessage("Extracting target features...")
        tempFC = arcpy.CreateUniqueName("tempFC", arcpy.env.scratchGDB)
        fms = arcpy.FieldMappings()
        fm  = arcpy.FieldMap()
        fm.addInputField(target_features,arcpy.Describe(target_features).OIDFieldName)
        f_name = fm.outputField
        #give this a silly name instead of worrying about if any of our layers already had ORIG_FID in them.
        f_name.name = 'zzzORIG_FIDzzz'
        f_name.aliasName = 'ORIG_FID'
        fm.outputField = f_name
        fms.addFieldMap(fm)
        arcpy.conversion.FeatureClassToFeatureClass(target_features, arcpy.env.scratchGDB, os.path.basename(tempFC), '', fms)
        
            ## This didn't work if target and join features had same field name
            #create field mappings for SJ output
            #messages.addMessage("Defining Field Map...")
            #fms = arcpy.FieldMappings()
            #for val in fieldnames:
            #    #create new field map using join field, but with output name of target field
            #    fm  = arcpy.FieldMap()
            #    fm.addInputField(join_features,val[0])
            #    f_name = fm.outputField
            #    f_name.name = val[1]
            #    fm.outputField = f_name
            #    fms.addFieldMap(fm)
        
        #create temporary file for SJ
        tempSJ = arcpy.CreateUniqueName("tempSJ", arcpy.env.scratchGDB)
        messages.addMessage("Performing Spatial Join...")
        arcpy.analysis.SpatialJoin(tempFC, join_features, tempSJ, "JOIN_ONE_TO_ONE", "KEEP_ALL", match_option=match_option, search_radius=search_radius)
        
        #get list of existing fields and fields to add to target
        existname = [f.name for f in arcpy.ListFields(target_features)]
        newname   = [val[1] for val in fieldnames]
        targetoid = arcpy.Describe(target_features).OIDFieldName
        
        #if we have fields that don't exist in the target features, (i.e. new fields to add), use Join Field
        addfields = list(set(newname)-set(existname))
        if len(addfields) > 0:
            messages.addMessage("Adding fields to target: {}...".format(addfields))
            arcpy.management.JoinField(target_features, targetoid, tempSJ, 'zzzORIG_FIDzzz', addfields)
        
        #If we're updating existing target fields, use this vlookup script
        updatefields = list(set(existname).intersection(newname))
        if len(updatefields) > 0:
            messages.addMessage("Updating fields in target: {}...".format(updatefields))
            #empty lookup dictionary
            look_dict = {}
            fnum = len(updatefields)
            #loop through the SJ output
            with arcpy.da.SearchCursor(tempSJ,['zzzORIG_FIDzzz']+updatefields+['Join_Count']) as cursor:
                for row in cursor:
                    #for each field, populate the dict. Adding 1 since we're ignoring TARGET_FID
                    look_dict[row[0]] = []
                    for i0 in range(fnum):
                        look_dict[row[0]].append(row[i0+1])
                    #also append the Join_Count
                    look_dict[row[0]].append(row[-1])
            #now loop through Target and update using this dict
            with arcpy.da.UpdateCursor(target_features,[targetoid]+updatefields) as cursor:
                for row in cursor:
                    #for each field
                    for i0 in range(fnum):
                        #Define from dictionary based on overwrite behavior specified
                        if overwrite != 'Do not overwrite' or row[i0+1] is None or str(row[i0+1]).strip()=='':
                            if overwrite == 'Overwrite only if spatial join found':
                                #if join count isn't 0
                                if look_dict[row[0]][-1] > 0:
                                    row[i0+1] = look_dict[row[0]][i0]
                            else:
                                row[i0+1] = look_dict[row[0]][i0]
                    cursor.updateRow(row)
        
        #and delete intermediate FCs
        messages.addMessage("Cleaning up...")
        arcpy.management.Delete(tempFC)
        arcpy.management.Delete(tempSJ)
        
        messages.addMessage("Script complete!")
        return
