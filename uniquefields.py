"""
Prints list of unique values for a field.
    
Version History
    1.0 (12/09/21)       Created
    1.1 (12/14/21)       BS - modified to allow table view inputs, changed in_field to type "field", and added choice between excel or text file
    1.2 (01/07/22)       BS - changed in_field back to string so we can exclude shape/blob types. Check for Max Excel rows.
"""

import os
import arcpy
import pandas as pd
from datetime import datetime

class UniqueFieldValues(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Unique Field Values"
        self.description = "Returns a list of unique field values"
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        params = []
        
        #params[0]
        in_table = arcpy.Parameter(
            displayName = "Table of Feature Class",
            name = "in_tabl",
            datatype = ["GPTableView","GPFeatureLayer"],
            parameterType = "Required",
            direction = "Input")

       
        #params[1]
        in_field = arcpy.Parameter(
            displayName = "Select Field",
            name = "in_field",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
        in_field.filter.type = "ValueList"
        in_field.filter.list = []
        #in_field.parameterDependencies = [in_table.name]
            
        #params[2]
        file_type = arcpy.Parameter(
            displayName="Open list as Excel or Text?",
            name="file_type",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        file_type.filter.list = ['Excel', 'Text']
        file_type.value = 'Text'
        
        params.append(in_table)
        params.append(in_field)
        params.append(file_type)
        
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        if parameters[0].value:
            parameters[1].filter.list = [f.name for f in arcpy.ListFields(parameters[0].value) if f.type not in ['Geometry','Blob']]
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
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
        in_table =  parameters[0].ValueAsText
        in_field =  parameters[1].ValueAsText
        file_type=  parameters[2].ValueAsText
        
        def unique_values(table , field):
            with arcpy.da.SearchCursor(table, [field]) as cursor:
                return sorted({row[0] for row in cursor},key=lambda x: (x is None, x))
                
        uniquefieldvals = unique_values(in_table,in_field)
        
        #save file differently depending on text / excel
        if file_type == 'Text':
            text = os.path.join(os.environ.get("TMP"),'UniqueFieldValues_'+in_field+'_'+datetime.now().strftime("%Y%m%d%H%M%S")+'.txt')
            with open(text, 'w') as txtfile:
                txtfile.writelines(str(i).strip("()") + "\n" for i in uniquefieldvals)
            os.startfile(text)
        else:
            df = pd.DataFrame(uniquefieldvals,columns=[in_field])
            #check max rows and truncate if necessary
            if df.shape[0] > 1048575:
                messages.addWarningMessage("Unique values ({}) exceed the Excel row limit. Only the first 1,048,575 values written to Excel".format(df.shape[0]))
                df = df.head(1048575)
            excel = os.path.join(os.environ.get("TMP"),'UniqueFieldValues_'+in_field+'_'+datetime.now().strftime("%Y%m%d%H%M%S")+'.xlsx')
            df.to_excel(excel, index=False) 
            os.startfile(excel)
        return