'''
This script will identify overlapping areas within a feature class, and keep the overlapping area for a single feature 
based on the attribute of a field.  For example, if you have a polygon Zone 1 and a polygon Zone 2 that overlap, the overlapping
portion of Zone 2 will be deleted.

Make a copy before using, since this will permanently modify the input data.

'''

import arcpy
import os

## Set Inputs
# the name of the field that tells you which polygon to keep
dataField = 'Zone'

# determine the sorting for this field. 
#If sortDescending = True,  the polygon with the highest value will be retained (all others clipped)
#If sortDescending = False, the polygon with the lowest  value will be retained (all others clipped)
sortDescending = False

# the name or path to your polygon FC
polygons = 'polygonLayerName'

# Output FC and table to use with Count Overlapping. These get deleted at the end.
overlapFC = os.path.join(arcpy.env.scratchGDB,'overlapFC')
overlapTable = os.path.join(arcpy.env.scratchGDB,'overlapTable')

## Run Script
# Set minimum overlap count to 2
arcpy.analysis.CountOverlappingFeatures(polygons, overlapFC, 2, overlapTable)

# Get list of OIDs for overlapFC and loop through them
overlaps = [row[0] for row in arcpy.da.SearchCursor(overlapFC, "OBJECTID")]

for overlap in overlaps:
    # Get the list of polygon OIDs for that overlap
    polys = [row[0] for row in arcpy.da.SearchCursor(overlapTable, "ORIG_OID",where_clause = 'OVERLAP_OID = '+str(overlap))]
    
    # Select them
    arcpy.management.SelectLayerByAttribute(polygons, 'NEW_SELECTION', "OBJECTID IN ({:s})".format(','.join(f"{x}" for x in polys)))
    
    # Extract data from selection as lists of OID and dataField
    rankOID  = [row[0] for row in arcpy.da.SearchCursor(polygons,"OBJECTID")]   
    rankData = [row[0] for row in arcpy.da.SearchCursor(polygons, dataField)]
    
    # Sort OIDs based on ascending values of dataField (so the first OID is the most lowest/first value in Datafield)
    clipOIDs = [x for _, x in sorted(zip(rankData, rankOID),reverse=sortDescending)]
    
    # Keep the desired OID, the remaining list will all be clipped
    keepOID = clipOIDs.pop(0)
    keepShape = [row[0] for row in arcpy.da.SearchCursor(polygons, "SHAPE@",where_clause = 'OBJECTID = '+str(keepOID))][0]
    
    # Loop through and clip
    with arcpy.da.UpdateCursor(polygons,"SHAPE@",where_clause="OBJECTID IN ({:s})".format(','.join(f"{x}" for x in clipOIDs))) as cursor:
        for row in cursor:
            oldShape=row[0]
            newShape=oldShape.difference(keepShape)
            cursor.updateRow((newShape,))

# Delete intermediate overlap layers
arcpy.management.Delete(overlapFC)
arcpy.management.Delete(overlapTable)
