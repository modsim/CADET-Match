import util
import numpy

name = "norm_keq"
count = 2

def getUnit(location):
    return location[0].split('/')[3]

def untransform(seq, cache, parameter, fullPrecision=False):
    minKA = parameter['minKA']
    maxKA = parameter['maxKA']
    minKEQ = parameter['minKEQ']
    maxKEQ = parameter['maxKEQ']

    minValues = numpy.log([minKA, minKEQ])
    maxValues = numpy.log([maxKA, maxKEQ])

    values = numpy.array(seq)

    values = (maxValues - minValues) * values + minValues

    values = [numpy.exp(values[0]), numpy.exp(values[0])/(numpy.exp(values[1]))]

    if cache.roundParameters is not None and not fullPrecision:
        values = [util.RoundToSigFigs(i, cache.roundParameters) for i in values]

    headerValues = [values[0], values[1], values[0]/values[1]]
    return values, headerValues

def setSimulation(sim, parameter, seq, cache, fullPrecision=False):
    values, headerValues = untransform(seq, cache, parameter, fullPrecision)

    location = parameter['location']
    
    comp = parameter['component']
    bound = parameter['bound']
    
    unit = getUnit(location)
    boundOffset = util.getBoundOffset(sim.root.input.model[unit])

    position = boundOffset[comp] + bound
    sim[location[0].lower()][position] = values[0]
    sim[location[1].lower()][position] = values[1]

    return values, headerValues

def setupTarget(parameter):
    location = parameter['location']
    bound = parameter['bound']
    comp = parameter['component']

    sensitivityOk = 1
    nameKA = location[0].rsplit('/', 1)[-1]
    nameKD = location[1].rsplit('/', 1)[-1]
    unit = int(location[0].split('/')[3].replace('unit_', ''))

    return [(nameKA, unit, comp, bound), (nameKD, unit, comp, bound)], sensitivityOk

def getBounds(parameter):
    return [0.0, 0.0], [1.0, 1.0]

def getHeaders(parameter):
    location = parameter['location']
    nameKA = location[0].rsplit('/', 1)[-1]
    nameKD = location[1].rsplit('/', 1)[-1]
    bound = parameter['bound']
    comp = parameter['component']
    
    headers = []
    headers.append("%s Comp:%s Bound:%s" % (nameKA, comp, bound))
    headers.append("%s Comp:%s Bound:%s" % (nameKD, comp, bound))
    headers.append("%s/%s Comp:%s Bound:%s" % (nameKA, nameKD, comp, bound))
    return headers
