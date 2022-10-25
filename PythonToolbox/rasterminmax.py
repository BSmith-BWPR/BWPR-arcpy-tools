"""
Takes a raster layer and sets symbology to a user defined min/max stretch
    
Version History
    1.0 (03/21/22)      Created       


"""

import arcpy

class setRasStretch(object):

    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Set Raster Symbology"
        self.description = "Quickly set a raster to custom min/max stretch symbology"
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        
        rasList = arcpy.Parameter(
            displayName="Input Raster(s)",
            name="rasList",
            datatype="GPRasterLayer",
            parameterType="Required",
            direction="Input",
            multiValue = True)
            
        minVal = arcpy.Parameter(
            displayName="Minimum stretch value",
            name="minVal",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input")
        minVal.value = 30
        
        maxVal = arcpy.Parameter(
            displayName="Maximum stretch value",
            name="maxVal",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input")
        maxVal.value = 100
        
        cRamp = arcpy.Parameter(
            displayName="Define colorramp",
            name="cRamp",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
            
        p = arcpy.mp.ArcGISProject('CURRENT')
        # Get elevation color ramps, sort them
        cList = [c.name for c in p.listColorRamps('Elev*')]
        cSort = [i for (v, i) in sorted((v, i) for (i, v) in enumerate([int(x.split("#")[-1]) for x in cList]))]
        cList = [cList[i] for i in cSort]
        cRamp.filter.list = cList
        cRamp.value = 'Elevation #1'

        params = [rasList,minVal,maxVal,cRamp]
        
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        
        #Get the input data
        rasList =  parameters[0].values
        minVal  =  parameters[1].Value
        maxVal  =  parameters[2].Value
        cRamp   =  parameters[3].valueAsText
        
        #get current project and map view
        p = arcpy.mp.ArcGISProject('CURRENT')
        m = p.activeMap
        
        

        for ras in rasList:
            messages.addMessage('Updating symbology for raster: {}'.format(ras.name))
            #get raster layer
            lyr  = m.listLayers(ras.name)[0]

            #set symbology (color ramp, labels, stretch type)
            sym = lyr.symbology
            sym.updateColorizer('RasterStretchColorizer')
            sym.colorizer.stretchType = 'MinimumMaximum'
            cr = p.listColorRamps(cRamp)[0]
            sym.colorizer.colorRamp = cr
            sym.colorizer.minLabel = "Min: " + str(minVal)
            sym.colorizer.maxLabel = "Max: " + str(maxVal)
            lyr.symbology = sym

            #use CIM to set custom statistics
            cim_lyr = lyr.getDefinition('V2')
            cim_lyr.colorizer.statsType = 'GlobalStats'
            cim_lyr.colorizer.useCustomStretchMinMax = True
            cim_lyr.colorizer.stretchStats.min = minVal
            cim_lyr.colorizer.stretchStats.max = maxVal
            lyr.setDefinition(cim_lyr)
        
        return
