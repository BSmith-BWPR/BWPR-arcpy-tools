'''
A modified version of Join Field that allows user to overwrite existing fields in the input target dataset

Note that this is not as robust as Join Field (there is no Validate Join button, and duplicate keys will always use the LAST value to join)
But it can be used as an Excel style VLOOKUP to populate an existing field

Version History
    1.0 (11/2/2022)        Script created.

'''

import arcpy

class JoinFieldOverwrite(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Join Field Overwrite"
        self.description = "Performs Join Field with option to overwrite existing fields in Input"
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        
        in_features = arcpy.Parameter(
            displayName="Input Feature or Table",
            name="in_features",
            datatype= ["GPTableView","GPFeatureLayer"],
            parameterType="Required",
            direction="Input")

        in_key = arcpy.Parameter(
            displayName="Input Join Field",
            name="in_key",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        #instead of using dependencies and a Field Type, we are using a GPString value list we will populate later
        in_key.filter.type = "ValueList"
        in_key.filter.list = []
        
        join_features = arcpy.Parameter(
            displayName="Join Table or Feature",
            name="join_features",
            datatype= ["GPTableView","GPFeatureLayer"],
            parameterType="Required",
            direction="Input")

        join_key = arcpy.Parameter(
            displayName="Join Table Field",
            name="join_key",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        join_key.filter.type = "ValueList"
        join_key.filter.list = []
        
        fieldnames = arcpy.Parameter(
            displayName='',
            name='fieldnames',
            datatype='GPValueTable',
            parameterType='Required',
            direction='Input')
        fieldnames.columns = [['GPString', 'Transfer Fields:'], ['GPString', 'Added to Target as:']]
        
        overwrite = arcpy.Parameter(
            displayName="Clear / Overwrite behavior",
            name="overwrite",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        overwrite.filter.list = ['Clear all existing values','Overwrite existing values','Do not overwrite']
        overwrite.value = 'Overwrite existing values'
        
        params = [in_features,in_key,join_features,join_key,fieldnames,overwrite]

        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        #use this dictionary so we can reference parameters by name instead of index.
        p = {p.name: p for p in parameters} 
        
        #populate drop downs for input and join fields
        if p['in_features'].altered and not p['in_features'].hasBeenValidated:
            p['in_key'].filter.list = [f.name for f in arcpy.ListFields(p['in_features'].value) 
                                            if f.type not in ['Geometry','Blob'] 
                                            and f.name.lower() not in ['shape_area','shape_length']]
            p['in_key'].value = None
        
        if p['join_features'].altered and not p['join_features'].hasBeenValidated:
            p['join_key'].filter.list = [f.name for f in arcpy.ListFields(p['join_features'].value) 
                                            if f.type not in ['Geometry','Blob'] 
                                            and f.name.lower() not in ['shape_area','shape_length']]
            # also clear everything below if this is updated
            p['join_key'].value = None
            p['fieldnames'].value = None
            
        #once the join key is defined
        if p['join_key'].altered and not p['join_key'].hasBeenValidated:
            # list the remaining fields in join_features (not already used as key)
            joinfields = [f.name for f in arcpy.ListFields(p['join_features'].value) 
                                            if f.type not in ['Geometry','Blob'] 
                                            and f.name.lower() not in ['shape_area','shape_length']
                                            and f.name not in [p['join_key'].valueAsText,arcpy.Describe(p['join_features'].value).OIDFieldName]]
            
            #[f for f in p['join_key'].filter.list if f is not (p['join_key'].valueAsText or arcpy.Describe(p['join_features'].value).OIDFieldName)]
            # target fields are the same as joinfields to start with
            targetfields = [arcpy.ValidateFieldName(x) for x in joinfields]
           
            #create list of lists, showing the field values for join and target. This is the GPValueTable
            #[['val1', 'name1'],['val2', 'name2']]
            valtbl   = []
            for idx, val in enumerate(joinfields):
                valtbl.append([val,targetfields[idx]])
            
            #define GPValueTable, and filter the first field to only allow field vals
            p['fieldnames'].values = valtbl               
            p['fieldnames'].filters[0].type = 'ValueList'
            p['fieldnames'].filters[0].list = joinfields
        
        #if either the target or the field mapping has changed
        if (p['in_features'].altered and not p['in_features'].hasBeenValidated) or (p['fieldnames'].altered and not p['fieldnames'].hasBeenValidated):
            #get list of existing target names and new target names
            if p['in_features'].value and p['fieldnames'].value:
                targetfields = [val[1] for val in p['fieldnames'].values]
                existingfields = [f.name for f in arcpy.ListFields(p['in_features'].valueAsText)]
                #if there's any overlap, enable overwrite field
                if len(set(targetfields).intersection(existingfields)) > 0:
                    p['overwrite'].enabled = True
                else:
                    p['overwrite'].enabled = False
                    
        return
        
    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        p = {p.name: p for p in parameters} 
        #Throw a warning if there are duplicate values in the join_key field.
        if p['join_key'].altered and not p['join_key'].hasBeenValidated and p['join_features'].value:
            listvals = [row[0] for row in arcpy.da.SearchCursor(p['join_features'].value, p['join_key'].value)]
            if len(listvals) < len(set(listvals)):
                p['join_key'].setWarningMessage('Duplicate values found in Join Key field. Last instance will be used')
        
        #Throw a warning if the field types for the two key fields don't match
        if (p['join_key'].altered and not p['join_key'].hasBeenValidated and p['join_features'].value) or (p['in_key'].altered and not p['in_key'].hasBeenValidated and p['in_features'].value):
            if p['join_features'].value and p['join_key'].value and p['in_key'].value and p['in_features'].value:
                in_type   = arcpy.ListFields(p['in_features'].value,p['in_key'].valueAsText)[0].type
                join_type = arcpy.ListFields(p['join_features'].value,p['join_key'].valueAsText)[0].type
                if in_type != join_type:
                    p['join_key'].setWarningMessage('Field types for Input and Join keys do not match. Tool may not work.')
                
        #if ValueTable exists
        if p['fieldnames'].value:
            #clear message
            p['fieldnames'].clearMessage()
            #get list of field names to add to target
            targetfields = [val[1] for val in p['fieldnames'].values]
            #if we have the input defined
            if p['in_features'].value:
                warnMsg = ''
                errMsg = ''
                #compare each new field name to existing field names, add warning if it exists already
                existingfields = [f.name for f in arcpy.ListFields(p['in_features'].valueAsText)]
                for name in targetfields:
                    if name in existingfields:
                        warnMsg = warnMsg + "\nField '{}' already exists.".format(name)
                        #if the field exists and is read only, throw an error
                        if not arcpy.ListFields (p['in_features'].valueAsText,name)[0].editable:
                            errMsg = errMsg + "\nField '{}' is not editable.".format(name)
                if len(warnMsg) > 0:
                    warnMsg = warnMsg +'\nSpecify desired overwrite behavior.'
                    p['fieldnames'].setWarningMessage(warnMsg)
                if len(errMsg) > 0:
                    p['fieldnames'].setErrorMessage(errMsg)
                    
                #Compare data types for each pair of existing fields/join fields to overwrite.
                if p['join_features'].value:
                    joinfields   = [val[0] for val in p['fieldnames'].values]
                    targetfields = [val[1] for val in p['fieldnames'].values]
                    existingfields = [f.name for f in arcpy.ListFields(p['in_features'].valueAsText)]
                    for f in set(targetfields).intersection(existingfields):
                        j = joinfields[targetfields.index(f)]
                        in_type   = arcpy.ListFields(p['in_features'].value,f)[0].type
                        join_type = arcpy.ListFields(p['join_features'].value,j)[0].type
                        if in_type in ['Date'] and join_type not in ['Date']:
                            errMsg = errMsg + '\nField [{}] input type ({}) will not match join type ({}).'.format(f,in_type,join_type)
                        if in_type in ['Integer','SmallInteger'] and join_type not in ['Single','Double','Integer','SmallInteger']:
                            errMsg = errMsg + '\nField [{}] input type ({}) will not match join type ({}).'.format(f,in_type,join_type)
                        if in_type in ['Integer','SmallInteger'] and join_type in ['Single','Double']:
                            warnMsg = warnMsg + '\nField [{}] input type ({}) does not match join type ({}) and may be coerced.'.format(f,in_type,join_type)
                        if in_type in ['String'] and join_type not in ['String']:
                            warnMsg = warnMsg + '\nField [{}] input type ({}) does not match join type ({}) and will be coerced.'.format(f,in_type,join_type)
                        if in_type in ['Single','Double'] and not join_type in ['Single','Double','Integer','SmallInteger']:
                            warnMsg = warnMsg + '\nField [{}] input type ({}) will not match join type ({})'.format(f,in_type,join_type)
                    if len(warnMsg) > 0:
                        p['fieldnames'].setWarningMessage(warnMsg)
                    if len(errMsg) > 0:
                        p['fieldnames'].setErrorMessage(errMsg)    
            #also check for duplicate field names and throw error. Names must be unique.
            if len(targetfields) != len(set(targetfields)):
                p['fieldnames'].setErrorMessage('Target Field names must be unique')
        
            
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        p = {p.name: p for p in parameters} 
        
        in_features     = p['in_features'].value
        in_key          = p['in_key'].valueAsText
        join_features   = p['join_features'].value
        join_key        = p['join_key'].valueAsText
        fieldnames      = p['fieldnames'].values
        overwrite       = p['overwrite'].valueAsText
        
        #get join fields and target fields
        messages.AddMessage('Identifying fields to join...')
        joinfields      = [val[0] for val in fieldnames]
        targetfields    = [val[1] for val in fieldnames]
        existingfields  = [f.name for f in arcpy.ListFields(in_features) if f.type not in ['Geometry','Blob']]
        
        #define which fields to overwrite, and which to simply add using Join Field
        overwritefields = list(set(targetfields).intersection(existingfields))
        newfields = list(set(targetfields).difference(overwritefields))
        
        # loop through the overwrite fields
        for f in overwritefields:
            #f is the field to write (input), j is the field in the join table
            j = joinfields[targetfields.index(f)]
            messages.AddMessage('Overwriting field {} with joined field {}...'.format(f,j))
            #Build the lookup dictionary
            d_lookup = {}
            with arcpy.da.SearchCursor(join_features,[join_key,j]) as cursor:
                for row in cursor:
                    d_lookup[row[0]] = row[1]
                        
            #Use the dictionary to update the input data
            with arcpy.da.UpdateCursor(in_features,[in_key,f]) as cursor:
                for row in cursor:
                    #if clearing all values, set return to None
                    if overwrite in ['Clear all existing values']:
                        row[1] = None
                        cursor.updateRow(row)
                    #if overwriting, or if return is currently empty, populate it.
                    if overwrite in ['Clear all existing values','Overwrite existing values'] or row[1] is None or str(row[1]).strip()=='':
                        if row[0] in d_lookup.keys():
                            if row[1] != d_lookup[row[0]]:
                                messages.AddMessage('---Row {} set to value {}'.format(row[0],d_lookup[row[0]]))
                                row[1] = d_lookup[row[0]]
                                cursor.updateRow(row)
        
        # define field mapping for new fields to add (since user has ability to rename the joined fields)
        fms = arcpy.FieldMappings()
        for f in newfields:
            #f is the field to write (input), j is the field in the join table
            j = joinfields[targetfields.index(f)]
            #create field map, add from join, and rename to f.
            fm  = arcpy.FieldMap()
            fm.addInputField(join_features,j)
            f_name = fm.outputField
            f_name.name = f
            f_name.aliasName = f
            fm.outputField = f_name
            fm.mergeRule = 'Last' #so it matches how the vlookup above works.
            fms.addFieldMap(fm)
        
        #Join Field
        if len(newfields)>0:
            messages.AddMessage('Calling Join Field to add {} new fields...'.format(len(newfields)))
            arcpy.management.JoinField(in_features, in_key, join_features, join_key, newfields, "USE_FM", fms)
        
        return
        