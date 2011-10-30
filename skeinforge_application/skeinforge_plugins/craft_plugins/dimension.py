#! /usr/bin/env python
"""
This page is in the table of contents.
Dimension adds Adrian's extruder distance E value so firmware does not have to calculate it on it's own and can set the extruder speed in relation to the distance that needs to be extruded.  Some printers don't support this.  Extruder distance is described at:

http://blog.reprap.org/2009/05/4d-printing.html

and in Erik de Bruijn's conversion script page at:

http://objects.reprap.org/wiki/3D-to-5D-Gcode.php

The dimension manual page is at:

http://fabmetheus.crsndoo.com/wiki/index.php/Skeinforge_Dimension

Nophead wrote an excellent article on how to set the filament parameters:

http://hydraraptor.blogspot.com/2011/03/spot-on-flow-rate.html

==Operation==
The default 'Activate Dimension' checkbox is off.  When it is on, the functions described below will work, when it is off, the functions will not be called.

==Settings==
===Extrusion Distance Format Choice===
Default is 'Absolute Extrusion Distance' because in Adrian's description the distance is absolute.  In future, because the relative distances are smaller than the cumulative absolute distances, hopefully the firmware will be able to use relative distance.

====Absolute Extrusion Distance====
When selected, the extrusion distance output will be the total extrusion distance to that gcode line.

====Relative Extrusion Distance====
When selected, the extrusion distance output will be the extrusion distance from the last gcode line.

===Extruder Retraction Speed===
Default is 13.3 mm/s.

Defines the extruder retraction feed rate.  A high value will allow the retraction operation to complete before much material oozes out.  If your extruder can handle it, this value should be much larger than your feed rate.

As an example, I have a feed rate of 48 mm/s and a 'Extruder Retraction Speed' of 150 mm/s.

===Filament===
====Filament Diameter====
Default is 2.8 millimeters.

Defines the filament diameter.

====Filament Packing Density====
Default is 0.85.  This is for ABS.

Defines the effective filament packing density.

The default value is so low for ABS because ABS is relatively soft and with a pinch wheel extruder the teeth of the pinch dig in farther, so it sees a smaller effective diameter.  With a hard plastic like PLA the teeth of the pinch wheel don't dig in as far, so it sees a larger effective diameter, so feeds faster, so for PLA the value should be around 0.97.  This is with Wade's hobbed bolt.  The effect is less significant with larger pinch wheels.

Overall, you'll have to find the optimal filament packing density by experiment.

===Retract Within Island===
Default is off.

When selected, retraction will work even when the next thread is within the same island.  If it is not selected, retraction will only work when crossing a boundary.

===Retraction Distance===
Default is zero.

Defines the amount the extruder retracts (sucks back) the extruded filament whenever an extruder stop is commanded.  Using this seems to help prevent stringing.  e.g. If set to 10 the extruder reverses the distance required to pull back 10mm of filament.  In fact this does not actually happen but if you set this distance by trial and error you can get to a point where there is very little ooze from the extruder when it stops which is not normally the case. 

===Restart Extra Distance===
Default is zero.

Defines the restart extra distance when the thread restarts.  The restart distance will be the retraction distance plus the restart extra distance.

If this is greater than zero when the extruder starts this distance is added to the retract value giving extra filament.  It can be a negative value in which case it is subtracted from the retraction distance.  On some Repstrap machines a negative value can stop the build up of plastic that can occur at the start of perimeters.

==Examples==
The following examples dimension the file Screw Holder Bottom.stl.  The examples are run in a terminal in the folder which contains Screw Holder Bottom.stl and dimension.py.

> python dimension.py
This brings up the dimension dialog.

> python dimension.py Screw Holder Bottom.stl
The dimension tool is parsing the file:
Screw Holder Bottom.stl
..
The dimension tool has created the file:
.. Screw Holder Bottom_dimension.gcode

"""

#Init has to be imported first because it has code to workaround the python bug where relative imports don't work if the module is imported as a main module.
import __init__

from datetime import date
from fabmetheus_utilities.fabmetheus_tools import fabmetheus_interpret
from fabmetheus_utilities.geometry.solids import triangle_mesh
from fabmetheus_utilities import archive
from fabmetheus_utilities import euclidean
from fabmetheus_utilities import gcodec
from fabmetheus_utilities import intercircle
from fabmetheus_utilities import settings
from skeinforge_application.skeinforge_utilities import skeinforge_craft
from skeinforge_application.skeinforge_utilities import skeinforge_polyfile
from skeinforge_application.skeinforge_utilities import skeinforge_profile
import math
import os
import sys


__author__ = 'Enrique Perez (perez_enrique@yahoo.com)'
__date__ = '$Date: 2008/02/05 $'
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'


def getCraftedText( fileName, gcodeText = '', repository=None):
	'Dimension a gcode file or text.'
	return getCraftedTextFromText( archive.getTextIfEmpty(fileName, gcodeText), repository )

def getCraftedTextFromText(gcodeText, repository=None):
	'Dimension a gcode text.'
	if gcodec.isProcedureDoneOrFileIsEmpty( gcodeText, 'dimension'):
		return gcodeText
	if repository == None:
		repository = settings.getReadRepository( DimensionRepository() )
	if not repository.activateDimension.value:
		return gcodeText
	return DimensionSkein().getCraftedGcode(gcodeText, repository)

def getNewRepository():
	'Get new repository.'
	return DimensionRepository()

def writeOutput(fileName, shouldAnalyze=True):
	'Dimension a gcode file.'
	skeinforge_craft.writeChainTextWithNounMessage(fileName, 'dimension', shouldAnalyze)


class DimensionRepository:
	'A class to handle the dimension settings.'
	def __init__(self):
		'Set the default settings, execute title & settings fileName.'
		skeinforge_profile.addListsToCraftTypeRepository('skeinforge_application.skeinforge_plugins.craft_plugins.dimension.html', self )
		self.fileNameInput = settings.FileNameInput().getFromFileName( fabmetheus_interpret.getGNUTranslatorGcodeFileTypeTuples(), 'Open File for Dimension', self, '')
		self.openWikiManualHelpPage = settings.HelpPage().getOpenFromAbsolute('http://fabmetheus.crsndoo.com/wiki/index.php/Skeinforge_Dimension')
		self.activateDimension = settings.BooleanSetting().getFromValue('Activate Volumetric Extrusion (Stepper driven Extruders)', self, True )
		settings.LabelSeparator().getFromRepository(self)
		settings.LabelDisplay().getFromName('- Filament Settings - YOU NEED TO HAVE YOUR EXTRUDER E-STEPS CALIBRATED FIRST -', self )
		settings.LabelDisplay().getFromName('http://josefprusa.cz/skeinforge-40-volumetric-calibration', self )
		settings.LabelDisplay().getFromName('- Filament -', self )
		self.filamentDiameter = settings.FloatSpin().getFromValue(1.0, 'Filament Diameter (mm):', self, 6.0, 2.8)
		self.filamentPackingDensity = settings.FloatSpin().getFromValue(0.7, 'E-Steps corrector:', self, 1.3, 1.0)
		self.activateCalibration = settings.BooleanSetting().getFromValue('Are You Calibrating?', self, False )
		self.MeasuredXSection = settings.FloatSpin().getFromValue(0.20, 'Measured Width of Extrusion:', self, 2.0, 0.5)
		settings.LabelSeparator().getFromRepository(self)
		settings.LabelDisplay().getFromName('- Fighting Oooze -', self )
		settings.LabelSeparator().getFromRepository(self)
		settings.LabelDisplay().getFromName('- Filament Retraction Settings -', self )
		self.activateFixedRetract = settings.BooleanSetting().getFromValue('Use fixed Retraction', self, True )
		self.activateAdaptiveRetract = settings.BooleanSetting().getFromValue('Use adaptive Retraction', self, False )
		self.extruderRetractionSpeed = settings.FloatSpin().getFromValue( 4.0, 'Extruder Retraction Speed (mm/s):', self, 34.0, 13.3 )
		settings.LabelSeparator().getFromRepository(self)
		settings.LabelDisplay().getFromName('- Fixed retraction settings -', self )
		self.retractionDistance = settings.FloatSpin().getFromValue( 0.0, 'Retraction Distance (millimeters):', self, 100.0, 0.0 )
		self.restartExtraDistance = settings.FloatSpin().getFromValue( 0.0, 'Restart Extra Distance (millimeters):', self, 100.0, 0.0 )
		settings.LabelDisplay().getFromName('- When to retract ? -', self )
		self.retractWithinIsland = settings.BooleanSetting().getFromValue('Retract Within Island', self, False)
		self.minimumTravelForRetraction = settings.FloatSpin().getFromValue(0.0, 'Minimum Travelmove after Retraction (millimeters):', self, 2.0, 1.0)

		settings.LabelSeparator().getFromRepository(self)
		settings.LabelDisplay().getFromName('- Adaptive retraction settings -', self )
		self.oozeRate = settings.FloatSpin().getFromValue( 0, 'Oozerate (mm/min):', self, 200, 75 )
		self.afterOooze = settings.FloatSpin().getFromValue( 0.0, 'Retraction loss (mm):', self, 2.0, 1.0 )
		self.maxRetract = settings.FloatSpin().getFromValue( 0, 'Maximum Retract Limit (mm):', self, 40, 20 )
		self.minRetract = settings.FloatSpin().getFromValue( 0, 'Minimum Retract threshold(mm):', self, 1.0 , 0.3 )

		settings.LabelSeparator().getFromRepository(self)
		settings.LabelDisplay().getFromName('- Firmware Related Stuff -', self )
		self.useFilamentDiameter = settings.BooleanSetting().getFromValue('Consider Filament Diameter?', self, True )
		self.maximumEValueBeforeReset = settings.FloatSpin().getFromValue(0.0, 'Maximum E Value before Reset (float):', self, 999999.9, 91234.0)
		extrusionDistanceFormatLatentStringVar = settings.LatentStringVar()
		self.extrusionDistanceFormatChoiceLabel = settings.LabelDisplay().getFromName('Extrusion Distance Format Choice: ', self )
		settings.Radio().getFromRadio( extrusionDistanceFormatLatentStringVar, 'Absolute Extrusion Distance', self, True )
		self.relativeExtrusionDistance = settings.Radio().getFromRadio( extrusionDistanceFormatLatentStringVar, 'Relative Extrusion Distance', self, False )



		self.executeTitle = 'Dimension'

	def execute(self):
		'Dimension button has been clicked.'
		fileNames = skeinforge_polyfile.getFileOrDirectoryTypesUnmodifiedGcode(self.fileNameInput.value, fabmetheus_interpret.getImportPluginFileNames(), self.fileNameInput.wasCancelled)
		for fileName in fileNames:
			writeOutput(fileName)


class DimensionSkein:
	'A class to dimension a skein of extrusions.'
	def __init__(self):
		'Initialize.'
		self.absoluteDistanceMode = True
		self.boundaryLayers = []
		self.distanceFeedRate = gcodec.DistanceFeedRate()
		self.feedRateMinute = None
		self.isExtruderActive = False
		self.layerIndex = -1
		self.lineIndex = 0
		self.maximumZTravelFeedRatePerSecond = None
		self.oldLocation = None
		self.operatingFlowRate = None
		self.retractionRatio = 1.0
		self.totalExtrusionDistance = 0.0
		self.travelFeedRatePerSecond = None
		self.zDistanceRatio = 5.0
		self.oldFlowRateString = None
		self.autoRetractDistance = 0
		self.timeToNextThread = None
		self.layerThickness = 0
		self.perimeterWidth = 0
		self.filamentXsection = 0
		self.nozzleXsection = 0
		self.flowRate = 0
		self.extrusionReduction = 1

	def addLinearMoveExtrusionDistanceLine(self, extrusionDistance):
		'Get the extrusion distance string from the extrusion distance.'
		if self.repository.extruderRetractionSpeed.value != 0.0:
			self.distanceFeedRate.output.write('G1 F%s\n' % self.extruderRetractionSpeedMinuteString)
			self.distanceFeedRate.output.write('G1%s\n' % self.getExtrusionDistanceStringFromExtrusionDistance(extrusionDistance))
			self.distanceFeedRate.output.write('G1 F%s\n' % self.distanceFeedRate.getRounded(self.feedRateMinute))

	def getCraftedGcode(self, gcodeText, repository):
		'Parse gcode text and store the dimension gcode.'
		self.repository = repository
#		self.calibrationFactor = 1
		self.filamentRadius = 0.5 * repository.filamentDiameter.value
		self.minimumTravelForRetraction = self.repository.minimumTravelForRetraction.value
		self.doubleMinimumTravelForRetraction = self.minimumTravelForRetraction + self.minimumTravelForRetraction
		self.lines = archive.getTextLines(gcodeText)
		self.parseInitialization()
		if not self.repository.retractWithinIsland.value:
			self.parseBoundaries()

		
#		if repository.activateCalibration.value:
#			self.calibrationFactor = (((self.layerThickness**2/4)*math.pi)+self.layerThickness*(xSectionCorrector -self.layerThickness))/(((self.layerThickness**2/4)*math.pi)+self.layerThickness *(self.perimeterWidth-self.layerThickness))
#		self.newfilamentPackingDensity = repository.filamentPackingDensity.value * self.calibrationFactor
#		print('****************E-Steps corrector Value (For Calibration)**********************:')
#		print( 'E-Steps corrector Value (For Calibration) STEPPER EXTRUDERS ONLY :', self.newfilamentPackingDensity )
#		print('****************E-Steps corrector Value (For Calibration)**********************')
#		self.flowScaleSixty = 60.0 * ((((self.layerThickness+self.perimeterWidth)/4) ** 2 * math.pi )/filamentPackingArea) / self.calibrationFactor
#		self.flowScaleSixty = 60.0 * (self.extrusionXsection/filamentPackingArea)/ self.calibrationFactor
#		self.flowScaleSixty = 60.0 * self.layerThickness * self.perimeterWidth / filamentPackingArea
#		print ('filamentPackingArea self.calibrationFactor',filamentPackingArea ,self.calibrationFactor)
#		if self.calibrationFactor is None:
#			print('Measured extrusion width cant be 0, either un-check calibration or set measured width to what you have measured!')
#		if not self.operatingFlowRate:
#			print('There is no operatingFlowRate so dimension will do nothing.')
#			return gcodeText
		self.restartDistance = self.repository.retractionDistance.value + self.repository.restartExtraDistance.value
		self.extruderRetractionSpeedMinuteString = self.distanceFeedRate.getRounded(60.0 * self.repository.extruderRetractionSpeed.value)
		if not self.maximumZTravelFeedRatePerSecond  and not self.travelFeedRatePerSecond :
			self.zDistanceRatio = self.travelFeedRatePerSecond / self.maximumZTravelFeedRatePerSecond
		for lineIndex in xrange(self.lineIndex, len(self.lines)):
			self.parseLine( lineIndex )
		return self.distanceFeedRate.output.getvalue()

	def getDimensionedArcMovement(self, line, splitLine):
		'Get a dimensioned arc movement.'
		if not self.oldLocation :
			return line
		relativeLocation = gcodec.getLocationFromSplitLine(self.oldLocation, splitLine)
		self.oldLocation += relativeLocation
		distance = gcodec.getArcDistance(relativeLocation, splitLine)
		return line + self.getExtrusionDistanceString(distance, splitLine)

	def getDimensionedLinearMovement( self, line, splitLine ):
		'Get a dimensioned linear movement.'
		distance = 0.0

		if self.absoluteDistanceMode:
			location = gcodec.getLocationFromSplitLine(self.oldLocation, splitLine)
			if self.oldLocation != None:
				distance = abs( location - self.oldLocation )
			self.oldLocation = location
		else:
			if not self.oldLocation :
				print('Warning: There was no absolute location when the G91 command was parsed, so the absolute location will be set to the origin.')
				self.oldLocation = Vector3()
			location = gcodec.getLocationFromSplitLine(None, splitLine)
			distance = abs( location )
			self.oldLocation += location
		return line + self.getExtrusionDistanceString(distance, splitLine )

	def getDistanceToNextThread(self, lineIndex):
		'Get the travel distance to the next thread.'
		if not self.oldLocation :
			return None
		isActive = False
		location = self.oldLocation
		for afterIndex in xrange(lineIndex + 1, len(self.lines)):
			line = self.lines[afterIndex]
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			if firstWord == 'G1':
				if isActive:
					location = gcodec.getLocationFromSplitLine(location, splitLine)
					if not self.repository.retractWithinIsland.value:
						locationEnclosureIndex = self.getSmallestEnclosureIndex(location.dropAxis())
						if locationEnclosureIndex != self.getSmallestEnclosureIndex(self.oldLocation.dropAxis()):
							return None
					locationMinusOld = location - self.oldLocation
					xyTravel = abs(locationMinusOld.dropAxis())
					zTravelMultiplied = locationMinusOld.z * self.zDistanceRatio
					self.timeToNextThread = math.sqrt(xyTravel * xyTravel + zTravelMultiplied * zTravelMultiplied)/ self.feedRateMinute*60
#					self.autoRetractDistance = (self.timeToNextThread)**0.5 / (abs(self.repository.oozeRate.value)/60)
#					self.autoRetractDistance = self.timeToNextThread * abs(self.repository.oozeRate.value)/60
					self.RetractDistance = self.timeToNextThread**0.5 * (self.repository.oozeRate.value/60)
					if self.RetractDistance < self.repository.minRetract.value :
						self.autoRetractDistance = self.repository.minRetract.value
#						print ('min',self.autoRetractDistance)
					elif self.RetractDistance > self.repository.maxRetract.value :
						self.autoRetractDistance = self.repository.maxRetract.value
#						print ('max',self.autoRetractDistance)
					else: 
						self.autoRetractDistance = self.RetractDistance
#						print ('reg',self.autoRetractDistance)
#					print ('retract',self.autoRetractDistance)
					return math.sqrt(xyTravel * xyTravel + zTravelMultiplied * zTravelMultiplied)
			elif firstWord == 'M101':
				isActive = True
			elif firstWord == 'M103':
				isActive = False
		return None

	def getExtrusionDistanceString( self, distance, splitLine ):
		'Get the extrusion distance string.'
		self.feedRateMinute = gcodec.getFeedRateMinute( self.feedRateMinute, splitLine )
		if not self.isExtruderActive:
			return ''
		if distance == 0.0:
			return ''
		if distance < 0.0:
			print('Warning, the distance is less than zero in getExtrusionDistanceString in dimension; so there will not be an E value')
			print(distance)
			print(splitLine)
			return ''
		self.extrusionXsection=((self.layerThickness/2+self.perimeterWidth/2)/2) ** 2 * math.pi
#		print ('self.layerThickness , self.perimeterWidth',self.layerThickness,self.perimeterWidth)
		self.filamentXsection =(self.repository.filamentDiameter.value/2) ** 2 * math.pi
#		xSectionCorrector = self.repository.MeasuredXSection.value
#		filamentPackingArea = (math.pi * (self.filamentRadius ** 2)) * self.repository.filamentPackingDensity.value
#		print (	'useFilamentDiameter'	, self.repository.useFilamentDiameter.value)
		if self.repository.useFilamentDiameter.value :
			self.extrusionReduction = self.filamentXsection / self.extrusionXsection
		else:
			self.extrusionReduction = 1
		minimizer = 	self.extrusionReduction
#		print ('self.extrusionReduction',self.extrusionReduction)
#		extrusionRate = self.flowRate *  self.extrusionXsection #* self.flowScaleSixty in mm3/mm
#		scaledFlowRate = extrusionRate * self.extrusionReduction
#		scaledFlowRate = (self.flowRate*((self.extrusionXsection/filamentPackingArea)/self.calibrationFactor))/distance
		scaledFlowRate = (self.flowRate * 10 *  self.extrusionXsection )


#		scaledFlowRate = extrusionRate * self.extrusionReduction
#		print ('self.extrusionXsection:',self.extrusionXsection)
#		print ('self.flowRate=',self.flowRate)
#		print ('scaledFlowRate=',scaledFlowRate)
#		return self.getExtrusionDistanceStringFromExtrusionDistance(scaledFlowRate/self.feedRateMinute * distance)
#		print('distance', distance)
#		print ('E=',self.getExtrusionDistanceStringFromExtrusionDistance((scaledFlowRate * distance) / self.extrusionReduction))
		return self.getExtrusionDistanceStringFromExtrusionDistance((scaledFlowRate * distance) / self.extrusionReduction)

	def getExtrusionDistanceStringFromExtrusionDistance( self, extrusionDistance ):
		'Get the extrusion distance string from the extrusion distance.'
		if self.repository.relativeExtrusionDistance.value:
			return ' E' + self.distanceFeedRate.getRounded( extrusionDistance )
		self.totalExtrusionDistance += extrusionDistance
		return ' E' + self.distanceFeedRate.getRounded( self.totalExtrusionDistance )

	def getRetractionRatio(self, lineIndex):
		'Get the retraction ratio.'
		distanceToNextThread = self.getDistanceToNextThread(lineIndex)
		if distanceToNextThread == None:
			return 1.0
		if distanceToNextThread >= self.doubleMinimumTravelForRetraction:
			return 1.0
		if distanceToNextThread <= self.minimumTravelForRetraction:
			return 0.0
		return (distanceToNextThread - self.minimumTravelForRetraction) / self.minimumTravelForRetraction

	def getSmallestEnclosureIndex(self, point):
		'Get the index of the smallest boundary loop which encloses the point.'
		boundaryLayer = self.boundaryLayers[self.layerIndex]
		for loopIndex, loop in enumerate(boundaryLayer.loops):
			if euclidean.isPointInsideLoop(loop, point):
				return loopIndex
		return None

	def parseBoundaries(self):
		'Parse the boundaries and add them to the boundary layers.'
		boundaryLoop = None
		boundaryLayer = None
		for line in self.lines[self.lineIndex :]:
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			if firstWord == '(</boundaryPerimeter>)':
				boundaryLoop = None
			elif firstWord == '(<boundaryPoint>':
				location = gcodec.getLocationFromSplitLine(None, splitLine)
				if boundaryLoop == None:
					boundaryLoop = []
					boundaryLayer.loops.append(boundaryLoop)
				boundaryLoop.append(location.dropAxis())
			elif firstWord == '(<layer>':
				boundaryLayer = euclidean.LoopLayer(float(splitLine[1]))
				self.boundaryLayers.append(boundaryLayer)
		for boundaryLayer in self.boundaryLayers:
			triangle_mesh.sortLoopsInOrderOfArea(False, boundaryLayer.loops)

	def parseInitialization(self):
		'Parse gcode initialization and store the parameters.'
		for self.lineIndex in xrange(len(self.lines)):
			line = self.lines[self.lineIndex]
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			self.distanceFeedRate.parseSplitLine(firstWord, splitLine)
			if firstWord == '(</extruderInitialization>)':
				self.distanceFeedRate.addTagBracketedProcedure('dimension')
				return
			elif firstWord == '(<layerThickness>':
				self.layerThickness = float(splitLine[1])
			elif firstWord == '(<maximumZDrillFeedRatePerSecond>':
				self.maximumZTravelFeedRatePerSecond = float(splitLine[1])
			elif firstWord == '(<maximumZTravelFeedRatePerSecond>':
				self.maximumZTravelFeedRatePerSecond = float(splitLine[1])
			elif firstWord == '(<operatingFeedRatePerSecond>':
				self.feedRateMinute = 60.0 * float(splitLine[1])
			elif firstWord == '(<operatingFlowRate>':
				self.operatingFlowRate = float(splitLine[1])
#				self.flowRate = self.operatingFlowRate
			elif firstWord == '(<perimeterWidth>':
				self.perimeterWidth = float(splitLine[1])
			elif firstWord == '(<travelFeedRatePerSecond>':
				self.travelFeedRatePerSecond = float(splitLine[1])
			elif firstWord == '(<nozzleDiameter>':
				self.nozzleDiameter = float(splitLine[1])
#				print ('ND',self.nozzleDiameter)
				self.nozzleXsection = (self.nozzleDiameter/2)**2*math.pi
			self.extrusionXsection = ((self.layerThickness + self.perimeterWidth)/4) ** 2 * math.pi
#			print('xtr-xsect, nozzle, lt, pw',self.extrusionXsection , self.nozzleXsection ,self.layerThickness,self.perimeterWidth )
			self.distanceFeedRate.addLine(line)
	def parseLine( self, lineIndex ):
		'Parse a gcode line and add it to the dimension skein.'
		line = self.lines[lineIndex].lstrip()
		splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
		if len(splitLine) < 1:
			return
		firstWord = splitLine[0]
		if firstWord == 'G2' or firstWord == 'G3':
			line = self.getDimensionedArcMovement( line, splitLine )
		if firstWord == 'G1':
			line = self.getDimensionedLinearMovement( line, splitLine )
		if firstWord == 'G90':
			self.absoluteDistanceMode = True
		elif firstWord == 'G91':
			self.absoluteDistanceMode = False
		elif firstWord == '(<layer>':
			if not self.repository.relativeExtrusionDistance.value:
				self.distanceFeedRate.addLine('M82')
			else: self.distanceFeedRate.addLine('M83')
			self.layerIndex += 1
		elif firstWord == 'M101':
#			print ('FR / AR',self.repository.activateFixedRetract.value,self.repository.activateAdaptiveRetract.value)
			if self.repository.activateFixedRetract.value:
				self.addLinearMoveExtrusionDistanceLine(self.restartDistance * self.retractionRatio)
			elif self.repository.activateAdaptiveRetract.value:
				self.addLinearMoveExtrusionDistanceLine((self.autoRetractDistance*10 / self.extrusionReduction)) #(self.restartDistance * self.retractionRatio))#* self.autoRetractDistance)
			if self.totalExtrusionDistance > self.repository.maximumEValueBeforeReset.value or self.repository.relativeExtrusionDistance.value:
				self.distanceFeedRate.addLine('G92 E0')
				self.totalExtrusionDistance = 0.0
			self.isExtruderActive = True
		elif firstWord == 'M103':
			if self.repository.activateFixedRetract.value:
#		    	self.retractionRatio = self.getRetractionRatio(lineIndex)
				self.addLinearMoveExtrusionDistanceLine(-self.repository.retractionDistance.value * self.retractionRatio)
			elif self.repository.activateAdaptiveRetract.value:
				self.retractionRatio = self.getRetractionRatio(lineIndex)
				self.addLinearMoveExtrusionDistanceLine((-(self.autoRetractDistance*10-self.repository.afterOooze.value)) / self.extrusionReduction)
			self.isExtruderActive = False
			#print('dtnt ttnt ted rr efr',self.distanceToNextThread , self.timeToNextThread , self.totalExtrusionDistance,self.retractionRatio , self.autoRetractDistance)
		elif firstWord == 'M108':
			self.operatingFlowRate = float( splitLine[1][1 :] )
			self.flowRate = self.operatingFlowRate
##			self.flowRate = float( splitLine[1][1 :] )
#			self.operatingFlowRate = float(splitLine[1])
#			self.flowRate = self.operatingFlowRate
#			print('frte=',self.flowRate)
		self.distanceFeedRate.addLine(line)
#		self.filamentXsection = (self.repository.filamentDiameter.value/2)**2 * math.pi
		self.filamentXsection = (math.pi * (self.filamentRadius ** 2)) * self.repository.filamentPackingDensity.value

def main():
	'Display the dimension dialog.'
	if len(sys.argv) > 1:
		writeOutput(' '.join(sys.argv[1 :]))
	else:
		settings.startMainLoopFromConstructor(getNewRepository())

if __name__ == '__main__':
	main()
