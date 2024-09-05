"""
User inputs table view or feature class. Opens a copy of the attribute table in Excel (viewing only, not for editing).
    
Version History
    1.0 (6/4/21)        Created
    1.1 (9/14/21)       Patch to remove all Geometry field types
    2.0 (12/15/21)      User can now select which fields to print, and auto-fit column widths
    2.1 (01/07/22)      Check row count against Excel limit. truncate and throw warning.
    3.0 (04/18/22)      OVERHAUL - copying the ESRI TableToExcel source code, and modifying it slightly to select fields and output/open to temp location
"""

import arcpy
import os
import sys
import pandas as pd
import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl import Workbook, load_workbook
import openpyxl.styles
import openpyxl.cell
from datetime import datetime

## B SMITH June 2024 add illegal char check
import re
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

class ViewInExcel(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "View in Excel"
        self.description = "View Attribute Table in Excel"
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        params = []
        
        tbl = arcpy.Parameter(
            datatype = ["GPTableView","GPFeatureLayer"],
            name = "tbl",
            displayName = 'Input layer or table',
            parameterType = 'Required',
            direction = 'Input')
            
        use_field_alias = arcpy.Parameter(
            displayName="Use field alias as column header",
            name="use_field_alias",
            datatype="GPBoolean",
            parameterType="Required",
            direction="Input")
        use_field_alias.value = True
        
        use_domain_desc = arcpy.Parameter(
            displayName="Use domain and subtype descriptions",
            name="use_domain_desc",
            datatype="GPBoolean",
            parameterType="Required",
            direction="Input")
        use_domain_desc.value = True    
        
        field_list = arcpy.Parameter(
            displayName = "Select Fields",
            name = "field_list",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input",
            multiValue=True)
        field_list.filter.type = "ValueList"
        field_list.filter.list = []
        
        auto_width = arcpy.Parameter(
            displayName="Automatically adjust column widths",
            name="auto_width",
            datatype="GPBoolean",
            parameterType="Required",
            direction="Input")
        auto_width.value = True      
        
        params.append(tbl)
        params.append(use_field_alias)
        params.append(use_domain_desc)
        params.append(auto_width)
        params.append(field_list)
        
        return params

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        p = {p.name: p for p in parameters} 
        
        # Update the list of fields once an input table/feature layer is selected
        # Omit geometry and blob types, default to select all.
        if p['tbl'].altered and not p['tbl'].hasBeenValidated: 
            p['field_list'].filter.list  = [f.name  for f in arcpy.ListFields(p['tbl'].value) if f.type not in ['Geometry','Blob']]
            p['field_list'].value        = [f.name  for f in arcpy.ListFields(p['tbl'].value) if f.type not in ['Geometry','Blob']]
                
        return
        
    def updateMessages(self, parameters):
        p = {p.name: p for p in parameters}
        #If too many fields are selected, throw an error
        if p['field_list'].value and p['field_list'].altered and not p['field_list'].hasBeenValidated:
            if len(p['field_list'].values) > 255:
                p['field_list'].setErrorMessage('Maximum number of fields is 255')
            else:
                p['field_list'].clearMessage
        #If too many rows, throw a warning
        if p['tbl'].altered and not p['tbl'].hasBeenValidated: 
            count = int(arcpy.management.GetCount(p['tbl'].valueAsText).getOutput(0))
            if count > 1048575:
                p['tbl'].setWarningMessage("Input data rows ({}) exceeds the Excel row limit. Only the first 1,048,575 rows written to Excel".format(count))
            else:
                p['tbl'].clearMessage
        return

    def execute(self, parameters, messages):
        
        p = {p.name: p for p in parameters}
        #get parameters
        tbl             = p['tbl'].valueAsText
        field_list      = p['field_list'].valueAsText.split(";")      #need to split this string of field names into a list of strings
        auto_width      = p['auto_width'].value
        use_domain_desc = p['use_domain_desc'].value
        use_field_alias = p['use_domain_desc'].value
        
        class clsField(object):
            """ Class to hold properties and behavior of the output fields """

            @property
            def alias(self):
                return self._field.aliasName

            @property
            def name(self):
                return self._field.name

            @property
            def domain(self):
                return self._field.domain

            @property
            def type(self):
                return self._field.type

            @property
            def length(self):
                return self._field.length

            def __init__(self, f, i, subtypes, cvdomains):
                """ Create the object from a describe field object """
                self._field = f
                self.subtype_field = ''
                self.domain_desc = {}
                self.subtype_desc = {}
                self.index = i

                # Get coded value domain info from field
                if f.domain:
                    for cvd in cvdomains:
                        if cvd.name == f.domain:
                            self.domain_desc = {0: cvd.codedValues}

                # Get coded value domain info from subtype
                for st_key in subtypes.keys():
                    st_val = subtypes[st_key]
                    if st_val['SubtypeField'] == f.name:
                        self.subtype_desc[st_key] = st_val['Name']
                        self.subtype_field = f.name
                    for k in st_val['FieldValues'].keys():
                        v = st_val['FieldValues'][k]
                        if k == f.name:
                            if len(v) == 2:
                                if v[1]:
                                    self.domain_desc[st_key] = v[1].codedValues
                                    self.subtype_field = st_val['SubtypeField']

            def __repr__(self):
                """ Nice representation for debugging  """
                return '<clsfield object name={}, alias={}, domain_desc={}>'.format(
                    self.name, self.alias, self.domain_desc)

            def updateValue(self, row, fields):
                """ Update value based on domain description """
                value = row[self.index]
                if self.subtype_field:
                    subtype_val = row[fields.index(self.subtype_field)]
                else:
                    subtype_val = 0

                if self.subtype_desc:
                    value = self.subtype_desc[row[self.index]]

                if self.domain_desc:
                    try:
                        value = self.domain_desc[subtype_val][row[self.index]]
                    except:
                        pass  # not all subtypes will have domain

                # Return the validated value
                return value


        # create openpyxl style
        style0 = openpyxl.styles.NamedStyle(name="Style0")
        style0.font = openpyxl.styles.Font(bold=True, size=12)
        style0.border = openpyxl.styles.Border(
            bottom=openpyxl.styles.Side(style='medium', color="000000"))
        style0.alignment = openpyxl.styles.Alignment(horizontal="center")
        style0.fill = openpyxl.styles.PatternFill(start_color='e6e6e6',
                                                  end_color='e6e6e6',
                                                  fill_type='solid')


        def WriteOnlyCellEx(ws, value):
            cell = openpyxl.cell.WriteOnlyCell(ws, value)
            cell.style = style0
            return cell


        def get_field_defs(in_table, field_list, use_domain_desc):
            """ returns nice field definition """
            desc = arcpy.Describe(in_table)

            subtypes = {}
            cvdomains = {}
            if use_domain_desc:
                try:
                    subtypes = arcpy.da.ListSubtypes(in_table)
                except:
                    pass
                ws = os.path.dirname(arcpy.Describe(in_table).catalogPath)
                if arcpy.Describe(ws).dataType == 'FeatureDataset':
                    ws = os.path.dirname(ws)
                cvdomains = [i for i in arcpy.da.ListDomains(ws)
                             if (i.domainType == 'CodedValue')]

            fields = []
            for i, field in enumerate([f for f in desc.fields
                                        if f.type in ["Date", "Double", "Guid",
                                                     "Integer", "OID", "Single",
                                                     "SmallInteger", "String",
                                                     "GlobalID"]
                                        and f.name in field_list]):
                fields.append(clsField(field, i, subtypes, cvdomains))
                
            return fields


        def validate_sheet_name(sheet_name):
            """ Validate sheet name to excel limitations
                 - 31 character length
                 - there characters not allowed : \ / ? * [ ]
            """
            import re
            if len(sheet_name) > 31:
                sheet_name = sheet_name[:31]

            # Replace invalid sheet character names with an underscore
            r = re.compile(r'[:\\\/?*\[\]]')
            sheet_name = r.sub("_", sheet_name)

            return sheet_name

        def table_to_excel(in_table, field_list, output, use_field_alias=False,
                           use_domain_desc=False):
            """ Writes a table to an Excel file """

            fields = get_field_defs(in_table, field_list, use_domain_desc)

            # write field names into row 0
            field_names = [i.name for i in fields]

            # use openpyxl to write generate output xlsx file
            workbook = Workbook(write_only=True)
            worksheet = workbook.create_sheet()
            worksheet.title = validate_sheet_name(tbl)

            # set the column names with style
            worksheet.append(
                [WriteOnlyCellEx(worksheet,
                                 (i.alias if use_field_alias else i.name))
                 for i in fields])

            # set column width
            for index, field in enumerate(fields):
                continue  # skip, not supported with WriteOnlyCell
                if field.type == 'String':
                    worksheet.column_dimensions[col_letter].width = min(50,
                                                                        field.length)
                else:
                    worksheet.column_dimensions[col_letter].width = 16

            # Loop through input rows
            rowcount = 1
            with arcpy.da.SearchCursor(in_table, field_names) as cursor:
                for row in cursor:
                    if rowcount < 1048575:
                        # convert to list which allows item assignment
                        rowUpdated = list(row)

                        for col_index, value in enumerate(row):
                            if fields[col_index].domain_desc or fields[col_index].subtype_desc:
                                value = fields[col_index].updateValue(row, field_names)
                                
                                # update
                                rowUpdated[col_index] = Cvalue
                                
                        ## BS June 2024 CHECK FOR ILLEGAL CHARACTERS
                        for i, r in enumerate(rowUpdated):
                            if isinstance(r, str):
                                rowUpdated[i] = re.sub(ILLEGAL_CHARACTERS_RE, '', r)
                            else:
                                rowUpdated[i] = r
                        
                        #messages.AddMessage("{}".format(rowUpdated))
                        worksheet.append(rowUpdated)
                        rowcount += 1

            # save workbook out to file
            workbook.save(output)
            del(workbook)

        #define temp file ouput and call function to create/populate spreadsheet
        fpath = os.path.join(os.environ.get("TMP"),arcpy.Describe(tbl).name+'_Attributes_'+datetime.now().strftime("%Y%m%d%H%M%S")+'.xlsx')
        table_to_excel(tbl, field_list, fpath, use_field_alias,use_domain_desc)
        
        #widen columns as necessary
        if auto_width:
            sheetname = validate_sheet_name(tbl)
            #Lets get the max length of each field's headers or values
            df = pd.read_excel(fpath, sheet_name=sheetname, dtype=str)
            header_length = [len(c) for c in df.columns]
            value_length  = [df[column].astype(str).str.len().max() for column in df]
            #take the larger of the header/data, add a buffer of 3, but cap at 100. This is the list of column widths for Excel.
            column_widths = [min(100,max([x+3,y+3])) for x,y in zip(header_length,value_length)]
            
            #with openpyxl, open the workbook and edit the column widths
            wb = load_workbook(filename = fpath)
            
            ws = wb[sheetname]
            for i, column_width in enumerate(column_widths,1):  # ,1 to start at 1
                ws.column_dimensions[get_column_letter(i)].width = column_width
            #save changes
            wb.save(filename = fpath)
            
        #open the file
        os.startfile(fpath)
        
            
        return
        
