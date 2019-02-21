import util
import numpy
import calc_coeff

name = "norm_linear"
count = 2
count_extended = 2

def getUnit(location):
    return location.split('/')[3]

def transform(parameter):
    minLower = parameter['minLower']
    maxLower = parameter['maxLower']
    minUpper = parameter['minUpper']
    maxUpper = parameter['maxUpper']

    def trans_a(i):
        return (i - minLower)/(maxLower-minLower)

    def trans_b(i):
        return (i - minUpper)/(maxUpper-minUpper)

    return [trans_a, trans_b]

def untransform(seq, cache, parameter, fullPrecision=False):
    minLower = parameter['minLower']
    maxLower = parameter['maxLower']
    minUpper = parameter['minUpper']
    maxUpper = parameter['maxUpper']
    minX = parameter['minX']
    maxX = parameter['maxX']
    
    minValues = numpy.array([minLower, minUpper])
    maxValues = numpy.array([maxLower, maxUpper])

    values = numpy.array(seq)

    values = (maxValues - minValues) * values + minValues

    if cache.roundParameters is not None and not fullPrecision:
        values = [util.RoundToSigFigs(i, cache.roundParameters) for i in values]

    headerValues = values
    return values, headerValues

def setSimulation(sim, parameter, seq, cache, experiment, fullPrecision=False):
    values, headerValues = untransform(seq, cache, parameter, fullPrecision)

    if parameter.get('experiments', None) is None or experiment['name'] in parameter['experiments']:
        location = parameter['location']
    
        minX = parameter['minX']
        maxX = parameter['maxX']

        x_name = parameter['x_name']

        x_value = experiment[x_name]

        slope, intercept = calc_coeff.linear_coeff(minX, values[0], maxX, values[1])

        value = calc_coeff.linear(x_value, slope, intercept)

        try:
            comp = parameter['component']
            bound = parameter['bound']
            index = None
        except KeyError:
            index = parameter['index']
            bound = None

        if bound is not None:
            unit = getUnit(location)
            boundOffset = util.getBoundOffset(sim.root.input.model[unit])

            if comp == -1:
                position = ()
                sim[location.lower()] = value
            else:
                position = boundOffset[comp] + bound
                sim[location.lower()][position] = value

        if index is not None:
            sim[location.lower()][index] = value

    return values, headerValues

def setupTarget(parameter):
    location = parameter['location']
    bound = parameter['bound']
    comp = parameter['component']

    name = location.rsplit('/', 1)[-1]
    sensitivityOk = 1

    try:
        unit = int(location.split('/')[3].replace('unit_', ''))
    except ValueError:
        unit = ''
        sensitivityOk = 0

    return [(name, unit, comp, bound),], sensitivityOk

def getBounds(parameter):
    return [0.0, 0.0], [1.0, 1.0]

def getHeaders(parameter):
    bound = parameter['bound']
    comp = parameter['component']
    
    headers = []
    headers.append("Lower Comp:%s Bound:%s" % (comp, bound))
    headers.append("Upper Comp:%s Bound:%s" % (comp, bound))
    return headers

def getHeadersActual(parameter):
    return getHeaders(parameter)

def setBounds(parameter, lb, ub):
    parameter['minLower'] = lb[0]
    parameter['maxLower'] = ub[0]
    parameter['minUpper'] = lb[2]
    parameter['maxUpper'] = ub[2]



