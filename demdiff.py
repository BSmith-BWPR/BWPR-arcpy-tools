"""
Accepts two DEMs, performs raster calculator to get difference, removes positive values to return only erosion
    
Version History
    1.0 (6/12/20)       Created
    2.0 (6/23/20)       Additional inputs, script now outputs a dissolved polygon with populated fields for volume change
    3.0 (8/24/21)       Dissolve Optional. User input time elapsed between DEMs. Fields renamed and metadata improved for clarity.
    4.0 (10/11/21)      Changed reprojection/snap/resample methods. Convert to cf based on cell size (instead of resampling). Default to image service DEMs.
    4.1 (10/03/23)      Buffered input polygons so we don't miss edge cells 
"""

import os
import arcpy
from arcpy import env
from arcpy.sa import *

arcpy.env.overwriteOutput=True

class DEMdifference(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "DEM Difference"
        self.description = "Returns the volume change (net change and net erosion) between two DEMs inside polygon boundary"
        self.canRunInBackground = False

    def getParameterInfo(self):
        #Define parameter definitions
        params = []
        
        #params[0] 
        in_raster_new = arcpy.Parameter(
            displayName="Input Latest Raster Data",
            name="in_raster_new",
            datatype=["GPRasterLayer","DERasterDataset"],
            parameterType="Required",               # Required|Optional|Derived
            direction="Input")                      # Input|Output
        in_raster_new.value = r"https://gis.aacounty.org/image/services/DEM/DEM_2020/ImageServer"
        
        #params[1]
        in_raster_ref = arcpy.Parameter(
            displayName="Input Reference Raster Data",
            name="in_raster_ref",
            datatype=["GPRasterLayer","DERasterDataset"],
            parameterType="Required",
            direction="Input")
        in_raster_ref.value = r"https://gis.aacounty.org/image/services/DEM/DEM_2017/ImageServer"
        
        #params[2]
        years = arcpy.Parameter(
            displayName="Number of Years between DEM",
            name="years",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input")
        years.value = 4
            
        #params[3]
        in_poly = arcpy.Parameter(
            displayName="Input Polygon Boundary",
            name="in_poly",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input")
        #set filter, this feature class must be a polygon
        in_poly.filter.list = ["Polygon"]
        
        #params[4]
        zone_field = arcpy.Parameter(
            displayName="Input Field to Define Dissolved Zones",
            name="zone_field",
            datatype="Field",
            parameterType="Optional",
            direction="Input")
        #set dependency, this must be a field from in_poly    
        zone_field.parameterDependencies = [in_poly.name]
        
        #params[5]
        out_work = arcpy.Parameter(
            displayName="Output Workspace",
            name="out_work",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")
        out_work.value = arcpy.env.scratchGDB
        
        #params[6] 
        out_poly = arcpy.Parameter(
            displayName="Output Polygon with Summary Statistics",
            name="out_poly",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Output")
        out_poly.value = os.path.join(arcpy.env.scratchGDB,'DiffPoly')
        
        #params[7]
        out_ras = arcpy.Parameter(
            displayName="Output DEM Difference raster",
            name="out_ras",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Output")
        out_ras.value = os.path.join(arcpy.env.scratchGDB,'DiffRas')
        
        params =   [in_raster_new,  #0
                    in_raster_ref,  #1
                    years,          #2
                    in_poly,        #3
                    zone_field,     #4
                    out_work,       #5
                    out_poly,       #6
                    out_ras]        #7
        
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        #when the input polygon changes, assign default names to output polygon and raster
        if parameters[3].value and parameters[3].altered and not parameters[3].hasBeenValidated:
            parameters[6].value = os.path.join(parameters[5].valueAsText,arcpy.Describe(parameters[3].valueAsText).Name+"_DiffPoly")
            parameters[7].value = os.path.join(parameters[5].valueAsText,arcpy.Describe(parameters[3].valueAsText).Name+"_DiffRas")
            
        #when input workspace changes, update output paths
        if parameters[5].altered and not parameters[5].hasBeenValidated:
            if parameters[3].value:
                parameters[6].value = os.path.join(parameters[5].valueAsText,arcpy.Describe(parameters[3].valueAsText).Name+"_DiffPoly")
                parameters[7].value = os.path.join(parameters[5].valueAsText,arcpy.Describe(parameters[3].valueAsText).Name+"_DiffRas")
            else:
                parameters[6].value = os.path.join(parameters[5].valueAsText,"DiffPoly")
                parameters[7].value = os.path.join(parameters[5].valueAsText,"DiffRas")
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        arcpy.env.overwriteOutput = True
        
        #Define parameters
        in_raster_new=  parameters[0].valueAsText
        in_raster_ref=  parameters[1].valueAsText
        years=          parameters[2].valueAsText
        in_poly=        parameters[3].valueAsText
        zone_field=     parameters[4].valueAsText
        out_work=       parameters[5].valueAsText
        out_poly=       parameters[6].valueAsText
        out_ras=        parameters[7].valueAsText
        
        #combine workspace and poly/ras names for full path to outputs
        out_poly = os.path.join(out_work,out_poly)
        out_ras  = os.path.join(out_work,out_ras)
        
        #Check for optional zone_field, if empty, set to OID
        if zone_field is None:
            zone_field = arcpy.Describe(in_poly).OIDFieldName
            messages.addMessage("No Dissolve Zone Field specified, using OID...")
        
        #Dissolve in_poly using zone_field, save as out_poly
        messages.addMessage("Dissolving input polygons on zone field...")
        arcpy.env.addOutputsToMap = 1
        arcpy.Dissolve_management(in_poly, out_poly, zone_field,"","SINGLE_PART")
        
        #Check for volume fields and add them
        messages.addMessage("Adding volume fields...")
        if len(arcpy.ListFields(out_poly,"Vol_Net")) == 0:
            arcpy.AddField_management(out_poly, "Vol_Net", "DOUBLE")
        if len(arcpy.ListFields(out_poly,"Vol_Erosion")) == 0:
            arcpy.AddField_management(out_poly, "Vol_Erosion", "DOUBLE")
        if len(arcpy.ListFields(out_poly,"VolYr_Erosion")) == 0:
            arcpy.AddField_management(out_poly, "VolYr_Erosion", "DOUBLE")

        #create temp file names for later calculations
        arcpy.env.addOutputsToMap = 0
        tempNew     = os.path.join(arcpy.env.scratchGDB,"tempNew")
        tempRef     = os.path.join(arcpy.env.scratchGDB,"tempRef")
        #tempMinus   = os.path.join(arcpy.env.scratchGDB,"tempMinus")
        tempNull    = os.path.join(arcpy.env.scratchGDB,"tempNull") 
        tempTbl     = os.path.join(arcpy.env.scratchGDB,"tempTbl")
        tempNetTbl  = os.path.join(arcpy.env.scratchGDB,"tempNetTbl")
        #tempNet     = os.path.join(arcpy.env.scratchGDB,"tempNet"))
        
        ### Update Oct 2023. When input rasters are different cell sizes, the extract by mask can miss a few edge cells
        ###     for the smaller raster. So we'll just buffer the polygon by 5', that should do it.
        polyBuff     = os.path.join(arcpy.env.scratchGDB,"polyBuff")
        arcpy.analysis.PairwiseBuffer(
            in_features=out_poly,
            out_feature_class=polyBuff,
            buffer_distance_or_field="5 Feet",
            dissolve_option="ALL",
            dissolve_field=None,
            method="PLANAR",
            max_deviation="5 Feet"
        )

        #set extent for everything just to make sure we aren't processing the entire DEM
        arcpy.env.extent = polyBuff
        
        #extract by mask to clip both rasters
        messages.addMessage("Extracting rasters to polygon mask...")
        extract_new = ExtractByMask(in_raster_new, polyBuff)
        extract_ref = ExtractByMask(in_raster_ref, polyBuff)
        
        #extract_new.save(os.path.join(arcpy.env.scratchGDB,"extract_new"))
        #extract_ref.save(os.path.join(arcpy.env.scratchGDB,"extract_ref"))
        
        #determine the cell size of the largest raster, and set environments
        maxcell = max(arcpy.Describe(extract_new).meanCellHeight,arcpy.Describe(extract_ref).meanCellHeight)
        arcpy.env.snapRaster= extract_ref
        arcpy.env.cellSize  = maxcell
        
        #project/resample rasters to exactly line up
        messages.addMessage("Projecting/Resampling rasters to {}' and snapping...".format(maxcell))
        #arcpy.Resample_management(extract_new, tempNew, maxcell, "BILINEAR")
        #arcpy.Resample_management(extract_ref, tempRef, maxcell, "BILINEAR")
        arcpy.management.ProjectRaster(extract_new, tempNew, arcpy.SpatialReference(2893), 'BILINEAR', maxcell)
        arcpy.management.ProjectRaster(extract_ref, tempRef, arcpy.SpatialReference(2893), 'BILINEAR', maxcell)
        
        #take difference
        messages.addMessage("Calculating DEM Difference...")
        arcpy.Minus_3d(tempNew, tempRef, out_ras)     
        cellAdjustment = arcpy.Describe(out_ras).meanCellHeight * arcpy.Describe(out_ras).meanCellHeight
        #messages.addMessage("DEM Difference raster has a cell size of: {}'".format(arcpy.Describe(out_ras).meanCellHeight))
        messages.addMessage("--- An adjustment factor of {} will be used to provide results in cubic feet.".format(cellAdjustment))
        
        #replace positive values with Null
        messages.addMessage("Remove positive volume changes (Aggradation) to define Erosion Volume...")
        tempNull = SetNull(out_ras, out_ras, "VALUE > 0")
               
        #resample to 1 foot grid - NOT ANYMORE! Just multiply by cell size squared.
        #messages.addMessage("Resampling Erosion Volume to 1 foot grid...")
        #arcpy.env.addOutputsToMap = 1
        #arcpy.Resample_management(tempNull, out_ras, 1, "NEAREST")
                   
        #Run Zonal Stats
        messages.addMessage("Calculating Erosion zonal statistics...")
        ZonalStatisticsAsTable(out_poly, zone_field, tempNull, tempTbl,"DATA","SUM")
        
        #Join Zonal stats back to polygon, and calculate volume total and annual volume
        #Use cell size adjustment to make sure results are in cubic feet
        #messages.addMessage("Populating Erosion volume fields in output polygon...")
        arcpy.JoinField_management(out_poly, zone_field, tempTbl, zone_field, ["SUM"])
        arcpy.CalculateField_management(out_poly, "Vol_Erosion", "!SUM! * -1 * {}".format(cellAdjustment), "PYTHON3")
        arcpy.CalculateField_management(out_poly, "VolYr_Erosion", "{0} / {1}".format('!Vol_Erosion!',years), "PYTHON3")
        arcpy.DeleteField_management(out_poly,"SUM")
              
        #resample to 1 foot grid - NOT ANYMORE! Just multiply by cell size squared.
        #messages.addMessage("Resampling to 1 foot grid (Net Volume)...")
        #arcpy.Resample_management(tempMinus, out_ras, 1, "NEAREST")
        
        #Run Zonal Stats (Net Volume)
        messages.addMessage("Calculating Net Volume zonal statistics...")
        ZonalStatisticsAsTable(out_poly, zone_field, out_ras, tempNetTbl,"DATA","SUM")
        arcpy.JoinField_management(out_poly, zone_field, tempNetTbl, zone_field, ["SUM"])
        arcpy.CalculateField_management(out_poly, "Vol_Net", "!SUM! * {}".format(cellAdjustment), "PYTHON3")

        #clean up
        messages.addMessage("Deleting intermediate files and fields...")
        #arcpy.Delete_management(tempMinus)
        arcpy.Delete_management([tempNull,tempTbl,tempNetTbl,tempNew,tempRef,polyBuff])
        arcpy.DeleteField_management(out_poly,"SUM")
        
        return