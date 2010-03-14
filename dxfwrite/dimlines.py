#!/usr/bin/env python
#coding:utf-8
# Author:  mozman
# Purpose: simple dimension lines, not autocad dimlines
# module belongs to package: dxfwrite.py
# Created: 10.03.2010
# Copyright (C) 2010, Manfred Moitzi
# License: GPLv3

""" Simple 2D dimension lines build with basic dxf entities, but not the basic
dxf dimension-entity!

OBJECTS

DimStyle
    describes a dimension style

DimensionLine
    A simple straight dimension line with two or more points
DimensionAngle
    angle dimensioning
DimensionArc
    arc dimensioning
DimensionRadius
    radius dimensioning

PUBLIC MEMBERS

dimstyles
    dimstyle container
    use get(name) to get a dimstyle, 'Default' if name does not exist
    use add(dimstyle) to add a new dimstyle

PUBLIC FUNCTIONS

setup(drawing)
    add necessary block- and layer-definitions to drawing
"""
from math import radians, hypot

from dxfwrite.ray import Ray2D
from dxfwrite import DXFEngine, DXFList
import dxfwrite.const as const

DIMENSIONS_MIN_DISTANCE = 0.05
DIMENSIONS_FLOATINGPOINT = '.'

class _DimStyle(dict):
    """ _DimStyle parameter struct, a dumb object just to store values """
    default_values = [
        # tick block name, use setup to generate default blocks
        ('tick', 'DIMTICK_ARCH'),
        # scale factor for ticks-block
        ('tickfactor', 1.),
        # tick2x means tick is drawn only for one side, insert tick a second
        # time rotated about 180 degree, but only one time at the dimension line
        # ends, this is usefull for arrow-like ticks. hint: set dimlineext to 0.
        ('tick2x', False),
        # dimension value scale factor, value = drawing-units * scale
        ('scale', 100.),
        # round dimension value to roundval fractional digits
        ('roundval', 0),
        # round dimension value to half untits, round 0.4, 0.6 to 0.5
        ('roundhalf', False),
        # dimension value text color
        ('textcolor', 7),
        # dimension value text height
        ('height', .5),
        # dimension text prefix and suffix like 'x=' ... ' cm'
        ('prefix', ''),
        ('suffix', ''),
        # dimension value text style
        ('style', 'ISOCPEUR'),
        # default layer for whole dimension object
        ('layer', 'DIMENSIONS'),
        # dimension line color index (0 from layer)
        ('dimlinecolor', 7),
        # dimension line extensions (in dimline direction, left and right)
        ('dimlineext', .3),
        # draw dimension value text <textabove> drawing-units above the
        # dimension line
        ('textabove', 0.2),
        # switch extension line False=off, True=on
        ('dimextline', True),
        # dimension extension line color index (0 from layer)
        ('dimextlinecolor', 5),
        # gap between measure target point and end of extension line
        ('dimextlinegap', 0.3)
        ]
    def __init__(self, name, **kwargs):
        super(_DimStyle, self).__init__(_DimStyle.default_values)
        # dimestyle name
        self['name'] = name
        self.update(kwargs)

    def __getattr__(self, attr):
        return self[attr]

    def __setattr__(self, attr, value):
        self[attr] = value

class _DimStyles(object):
    """ DimStyle container
    """
    def __init__(self):
        self._styles = {}
        self.default = _DimStyle('Default')

    def get(self, name):
        """ get DimStyle()object by name """
        return self._styles.get(name, self.default)

    def new(self, name, **kwargs):
        """ create a new dimstyle """
        style = _DimStyle(name, **kwargs)
        self._styles[name] = style
        return style

    @staticmethod
    def setup(drawing):
        """ insert necessary definition into drawing

        ticks
            DIMTICK_ARCH, DIMTICK_DOT, DIMTICK_ARROW
        layer
            DIMENSIONS
        """
        # default pen assignment:
        # 1 : 1.40mm - red
        # 2 : 0.35mm - yellow
        # 3 : 0.70mm - green
        # 4 : 0.50mm - cyan
        # 5 : 0.13mm - blue
        # 6 : 1.00mm - magenta
        # 7 : 0.25mm - white/black
        # 8, 9 : 2.00mm
        # >=10 : 1.40mm
        def block(name, elements):
            """ create the block entity """
            tick = DXFEngine.block(name, (0., 0.))
            for element in elements:
                tick.add(element)
            return tick

        dimcolor = dimstyles.default.dimextlinecolor
        byblock = const.BYBLOCK

        elements = [
            DXFEngine.line(( 0., +.5), (0., -.5), color=dimcolor,
                           layer=byblock),
            DXFEngine.line((-.2, -.2), (.2, +.2), color=4, layer=byblock)
        ]
        drawing.blocks.add(block('DIMTICK_ARCH', elements))

        elements = [
            DXFEngine.line((0., .5), (0., -.5), color=dimcolor, layer=byblock),
            DXFEngine.circle(radius=.1, color=4, layer=byblock)
        ]
        drawing.blocks.add(block('DIMTICK_DOT', elements))

        elements = [
            DXFEngine.line((0., .5), (0., -.50), color=dimcolor, layer=byblock),
            DXFEngine.solid([(0, 0), (.3, .05), (.3,-.05)], color=7,
                            layer=byblock)
        ]
        drawing.blocks.add(block('DIMTICK_ARROW', elements))
        drawing.add_layer('DIMENSIONS')

dimstyles = _DimStyles() # use this factory tu create new dimstyles

class _DimensionBase(object):
    """ Abstract base class for dimension lines """
    def __init__(self, dimstyle, layer):
        self.dimstyle = dimstyles.get(dimstyle)
        self.layer = layer
        self.data = DXFList()

    def prop(self, property_name):
        """ get dimension line properties by name with the possibility to
        override several properties.
        """
        if property_name == 'layer':
            return self.layer if self.layer else self.dimstyle.layer
        else: # pass through self.dimstyle object DimStyle()
            return self.dimstyle[property_name]

    def _build_dimline(self):
        """ build dimension line object with basic dxf entities """
        raise NotImplementedError("override abstract method _build_dimline")

    def __dxf__(self):
        """ get the dxf string """
        self._build_dimline()
        return self.data.__dxf__()


class DimensionLine(_DimensionBase):
    """ Simple straight dimension line with two or more measure points, build
    with basic dxf entities. This is NOT a dxf dimension entity. And This is
    a 2D element, so all z-values will be ignored!

    INIT PARAMS

    pos
        position of dimension line, line goes through this point
    measure_points
        list of points to dimension (two or more)
    angle
       angle of dimension line
    dimstyle
       dimstyle name, 'Default' - style is the default value
    layer
       dimension line layer, override the default value of dimstyle
    """
    def __init__(self, pos, measure_points, angle=0., dimstyle='Default',
                 layer=None):
        super(DimensionLine, self).__init__(dimstyle, layer)
        self.angle = angle
        self.measure_points = measure_points
        self.text_override = [""] * self.section_count
        self.dimlinepos = vector2d(pos)

    def set_text(self, section, text):
        """ Set and override the text of the dimension text for the given
        dimension line section.
        """
        self.text_override[section] = text

    def _setup_dimension_line(self):
        """ calc setup values and determines the point order of the dimension
        line points.
        """
        self.measure_points = [vector2d(point)
                               for point in self.measure_points]

        dimlineray = Ray2D(self.dimlinepos, angle=radians(self.angle))
        self.dimline_points = [ self._get_point_on_dimline(point, dimlineray)
                                for point in self.measure_points ]
        self.point_order = self._indices_of_sorted_points(self.dimline_points)
        self._build_vectors()

    def _get_dimline_point(self, index):
        """ get point on the dimension line, index runs left to right
        """
        return self.dimline_points[self.point_order[index]]

    def _get_section_points(self, section):
        """ get start and end point on the dimension line of dimension section
        """
        return (self._get_dimline_point(section),
                self._get_dimline_point(section+1))

    def _get_dimline_bounds(self):
        """ get thr first and the last point of dimension line """
        return (self._get_dimline_point(0),
                self._get_dimline_point(-1))

    @property
    def section_count(self):
        """ count of dimline sections """
        return len(self.measure_points)-1
    @property
    def point_count(self):
        """ count of dimline points """
        return len(self.measure_points)

    def _build_dimline(self):
        """ build dimension line object with basic dxf entities """
        self._setup_dimension_line()
        self._draw_dimline()
        if self.prop('dimextline'):
            self._draw_extension_lines()
        self._draw_text()
        self._draw_ticks()

    @staticmethod
    def _indices_of_sorted_points(points):
        """ get indices of points, for points sorted by x, y values """
        indexed_points = [(idx, point) for idx, point in enumerate(points)]
        indexed_points.sort(_cmp_indexed_points)
        return list([idx for idx, point in indexed_points])

    def _build_vectors(self):
        """ build unit vectors, parallel and normal to dimension line """
        point1, point2 = self._get_dimline_bounds()
        self.parallel_vector = unit_vector(vsub(point2, point1))
        self.normal_vector = normal_vector(self.parallel_vector)

    @staticmethod
    def _get_point_on_dimline(point, dimray):
        """ get the measure target point projection on the dimension line """
        return dimray.intersect(dimray.normal_through(point))

    def _draw_dimline(self):
        """ build dimension line entity """
        start_point, end_point = self._get_dimline_bounds()

        dimlineext = self.prop('dimlineext')
        if dimlineext > 0:
            start_point = vsub(start_point,
                               vmul_scalar(self.parallel_vector, dimlineext))
            end_point = vadd(end_point,
                             vmul_scalar(self.parallel_vector, dimlineext))

        self.data.append(DXFEngine.line(
            start_point, end_point,
            color=self.prop('dimlinecolor'),
            layer=self.prop('layer')))

    def _draw_extension_lines(self):
        """ build the extension lines entities"""
        dimextlinegap = self.prop('dimextlinegap')
        for dimline_point, target_point in \
            zip(self.dimline_points, self.measure_points):
            if distance(dimline_point, target_point) > \
               max(dimextlinegap, DIMENSIONS_MIN_DISTANCE):
                direction_vector = unit_vector(vsub(target_point,
                                                    dimline_point))
                target_point = vsub(target_point, vmul_scalar(direction_vector,
                                                              dimextlinegap))
                self.data.append(DXFEngine.line(
                    dimline_point,
                    target_point,
                    color=self.prop('dimextlinecolor'),
                    layer=self.prop('layer')))

    def _draw_text(self):
        """ build the dimension value text entity """
        for section in range(self.section_count):
            dimvalue_text = self._get_dimvalue_text(section)
            insert_point = self._get_text_insert_point(section)
            self.data.append(DXFEngine.text(
                text=dimvalue_text,
                insert=insert_point,
                height=self.prop('height'),
                halign=const.CENTER,
                valign=const.MIDDLE,
                layer= self.prop('layer'),
                rotation=self.angle,
                style=self.prop('style'),
                alignpoint=insert_point))

    def _get_dimvalue_text(self, section):
        """ get the dimension value as text, distance from point1 to point2 """
        override = self.text_override[section]
        if len(override):
            return override
        point1, point2 = self._get_section_points(section)

        dimvalue = distance(point1, point2) * self.prop('scale')
        dimtext = "{0:.{1}f}".format(dimvalue, self.prop('roundval'))
        if DIMENSIONS_FLOATINGPOINT in dimtext:
            # remove successional zeros
            dimtext.rstrip('0')
            # remove floating point as last char
            dimtext.rstrip(DIMENSIONS_FLOATINGPOINT)
        return self.prop('prefix') + dimtext + self.prop('suffix')

    def _get_text_insert_point(self, section):
        """ get the dimension value text insert point """
        point1, point2 = self._get_section_points(section)
        dist = self.prop('height') / 2. + self.prop('textabove')
        return vadd(midpoint(point1, point2),
                    vmul_scalar(self.normal_vector, dist))

    def _draw_ticks(self):
        """ insert the dimension line ticks, (markers on the dimension line) """
        def tick(point, rotate=False):
            """ build the insert-entity for the tick block """
            return DXFEngine.insert(
                insert=point,
                blockname=self.prop('tick'),
                rotation=self.angle + (180. if rotate else 0.),
                xscale=self.prop('tickfactor'),
                yscale=self.prop('tickfactor'),
                layer=self.prop('layer'))

        def set_tick(index, rotate=False):
            """ add tick to dxf data """
            self.data.append(tick(self._get_dimline_point(index), rotate))

        if self.prop('tick2x'):
            for index in range(0, self.point_count-1):
                set_tick((index), False)
            for index in range(1, self.point_count):
                set_tick((index), True)
        else:
            for index in range(self.point_count):
                set_tick((index), False)

class DimensionAngle(_DimensionBase):
    """ Draw an angle dimensioning line at dimline pos from start to end,
    dimension text is the angle build of the three points start-center-end.
    """
    def __init__(self, dimlinepos, center, start, end,
                 dimstyle='Default', layer=None):
        super(DimensionAngle, self).__init__(dimstyle, layer)
        self.dimlinepos = vector2d(dimlinepos)
        self.center = vector2d(center)
        self.start = vector2d(start)
        self.end = vector2d(end)

    def _build_dimline(self):
        """ build dimension line object with basic dxf entities """
        pass

class DimensionArc(_DimensionBase):
    """ Arc is defined by start- and endpoint on arc and the centerpoint, or
    by three points lying on the arc if acr3points is True. Measured length goes
    from start- to endpoint. The dimension line goes through the dimlinepos.
    """
    def __init__(self, dimlinepos, center, start, end, arc3points=False,
                 dimstyle='Default', layer=None):
        super(DimensionArc, self).__init__(dimstyle, layer)
        self.dimlinepos = vector2d(dimlinepos)
        self.start = vector2d(start)
        self.end = vector2d(end)
        if arc3points:
            self.center = center_of_3points_arc(vector2d(center),
                                                self.start, self.end)
        else:
            self.center = vector2d(center)
        self.radius = distance(self.center, self.start)

    def _build_dimline(self):
        """ build dimension line object with basic dxf entities """
        pass

class DimensionRadius(_DimensionBase):
    """ Draw a radius dimension line from target in direction of center with
    length drawing units.
    """
    def __init__(self, center, target, length=3.,
                 dimstyle='Default', layer=None):
        super(DimensionRadius, self).__init__(dimstyle, layer)
        self.center = vector2d(center)
        self.target = vector2d(target)
        self.length = float(length)

    def _build_dimline(self):
        """ build dimension line object with basic dxf entities """
        pass

def _cmp_indexed_points(ipoint1, ipoint2):
    """ compare indexed points, sorted in order x, y

    element = (index, point-tuple)
    example: [(0, (1,2)), (2, (5,7)), (1, (9,8))]
    """
    point1 = ipoint1[1]
    point2 = ipoint2[1]
    if point1[0] == point2[0]:
        return cmp(point1[1], point2[1])
    return cmp(point1[0], point2[0])

#---- private 2d algorithmic functions

def vector2d(vector):
    """ return a 2d point """
    return (vector[0], vector[1])

def magnitude(vector):
    """ length of a 2d vector """
    return hypot(vector[0], vector[1])

def unit_vector(vector):
    """ 2d unit vector """
    return vdiv_scalar(vector, magnitude(vector))

def normal_vector(vector):
    """ 2d perpendicular vector """
    return (-vector[1], vector[0])

def distance(point1, point2):
    """ calc distance between two 2d points """
    return hypot(point1[0]-point2[0], point1[1]-point2[1])

def midpoint(point1, point2):
    """ calc midpoint between point1 and point2 """
    return vdiv_scalar(vadd(point1, point2), 2.)

def vsub(vector1, vector2):
    """ substract vectors """
    return (vector1[0]-vector2[0], vector1[1]-vector2[1])

def vadd(vector1, vector2):
    """ add vectors """
    return (vector1[0]+vector2[0], vector1[1]+vector2[1])

def vdiv_scalar(vector, scalar):
    """ div vectors """
    return (vector[0]/scalar, vector[1]/scalar)

def vmul_scalar(vector, scalar):
    """ mul vector with scalar """
    return (vector[0]*scalar, vector[1]*scalar)

def center_of_3points_arc(point1, point2, point3):
    """ calc center point of 3 point arc

    Circle is defined by the points point1, point2 and point3.
    """
    ray1 = Ray2D(point1, point2)
    ray2 = Ray2D(point1, point3)
    midpoint1 = midpoint(point1, point2)
    midpoint2 = midpoint(point1, point3)
    center_ray1 = ray1.normal_through(midpoint1)
    center_ray2 = ray2.normal_through(midpoint2)
    return center_ray1.intersect(center_ray2)