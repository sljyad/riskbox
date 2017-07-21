#!/usr/bin/env python
#
############################################################################
#
# MODULE:	r.impact.tsunami
# AUTHOR(S):	Massimiliano Cannata, Monia Molilnari
#		IST-SUPSI
# PURPOSE:	Estimates the tsunami wave generated by slide impact
# COPYRIGHT:	(C) 2011 by the GRASS Development Team
#
#		This program is free software under the GNU General Public
#		License (>=v2). Read the file COPYING that comes with GRASS
#		for details.
#
#############################################################################

#%Module
#% description: Estimates the wave generated by slide impact
#% keywords: rester, hazard, flooding, tsunami
#%End
#%option
#% key: elevation
#% type: string
#% gisprompt: old,cell,raster
#% description: Name of elevation map including bathymetry
#% required : yes
#%end
#%option
#% key: lake
#% type: string
#% gisprompt: old,cell,raster
#% description: Name of lake depth map, with NULL values out of the lake
#% required : yes
#%end
#%option
#% key: s_rho
#% type: double
#% description: bulk slide density [Kg/m3]
#% required : yes
#%end
#%option
#% key: s_por
#% type: double
#% description: bulk slide porosity [%]
#% required : no
#% answer: 0
#%end
#%option
#% key: s_vol
#% type: double
#% description: Bulk slide volume [m3]
#% required : yes
#%end
#%option
#% key: s_width
#% type: double
#% description: Slide width [m]
#% required : yes
#%end
#%option
#% key: s_thick
#% type: double
#% description: Slide thickness [m]
#% required : yes
#%end
#%option
#% key: i_east
#% type: double
#% description: Easting coordinate of the impact point on the lake
#% required : yes
#%end
#%option
#% key: i_north
#% type: double
#% description: Northing coordinate of the impact point on the lake
#% required : yes
#%end
#%option
#% key: i_depth
#% type: double
#% description: still water depth in the area of impact [m]
#% required : yes
#%end
#%option
#% key: i_vel
#% type: double
#% description: Impact velocity [m/s]
#% required : yes
#%end
#%option
#% key: i_slope
#% type: double
#% description: Impact inclination angle [deg]
#% required : yes
#%end
#%option
#% key: i_azimut
#% type: double
#% description: Impact azimut angle [deg]
#% required : yes
#%end
#%option
#% key: shadow
#% type: string
#% gisprompt: old,cell,raster
#% description: Name of shadow map
#% required : no
#%end
#%option
#% key: wbc
#% type: double
#% description: wave break condition [m]
#% answer: 0.8
#% required : no
#%end
#%option
#% key: inund
#% type: string
#% gisprompt: new,cell,raster
#% description: Output raster map name for inundation
#% key_desc : name
#% required : yes
#%end
#%option
#% key: wave
#% type: string
#% gisprompt: new,cell,raster
#% description: Output raster map name for wave height
#% required : no
#%end
#%flag
#% key: a
#% description: Apply angle limitation mask (-90 deg to 90 deg)
#%end
#%flag
#% key: g
#% description: Output only report in gui format
#%end
#%flag
#% key: c
#% description: Output limitations check report
#%end
#%flag
#% key: w
#% description: Output maximum wave characteristics report
#%end
#%flag
#% key: t
#% description: do not delete temporary files
#%end
#%flag
#% key: s
#% description: apply solid mass type correction
#%end

import sys
import os
import math
import time
import atexit
import grass.script as grass
#from grass.script import core as grass

def main():
    #temporary map names
    global tm, t
    tm = {}
    t = True
    #read user inputs
    dtm = options['elevation']
    lake = options['lake']
    rho = float(options['s_rho'])
    por = float(options["s_por"])
    vol = float(options['s_vol'])
    width = float(options['s_width'])
    thick = float(options['s_thick'])
    east = float(options['i_east'])
    north = float(options['i_north'])
    idepth = float(options['i_depth'])
    vel = float(options['i_vel'])
    slope = float(options['i_slope'])
    azi = float(options['i_azimut'])
    wbc = float(options['wbc'])
    shadow = options['shadow']
    outI = options["inund"]
    outH = options["wave"]
    quiet = flags["g"]

    #print "outH=%s" %(options)

    #check if output map exist
    mapset = grass.gisenv()['MAPSET']
    if not grass.overwrite():
        if grass.find_file(outI, element = 'cell', mapset = mapset)['file']:
            grass.fatal(_("Raster map <%s> already exists.") % outI)
        if grass.find_file(outH, element = 'cell', mapset = mapset)['file']:
            grass.fatal(_("Raster map <%s> already exists.") % outH)
    
    # initialize costants & env variables
    rho_w = 1000
    g =  9.80665
    region = grass.region()

    # prepare temporary map raster names
    processid = "%.7f" % time.time()
    tm["distance"] = "distance_" + processid
    tm["impact"] = "impact_" + processid
    tm["field"] = "field_" + processid
    tm["azimut"] = "azimut_" + processid
    tm["gamma"] = "gamma_"+ processid
    tm["H"] = "H_"+ processid
    tm["T"] = "T_"+ processid
    tm["L"] = "L_"+ processid
    #tm["dzw"] = "dzw_"+ processid
    tm["zones"] = "zones_"+ processid
    tm["zoneSUM"] = "zoneSUM_"+ processid
    tm["runup"] = "runup_"+ processid    
    tm["ruline"] = "ruline_"+ processid
    tm["slope"] = "slope_"+ processid
    #tm["ru_mask"] = "ru_mask_"+ processid
    #tm["ru_grow"] = "ru_grow_"+ processid
    tm["wave_elev"] = "wave_elev_"+ processid
    tm["elev"] = "elev_"+ processid
    #tm["inond"] = "inond_"+ processid
    
    #check temporary map names are not existing maps
    for key, value in tm.items():
        if grass.find_file(value, element = 'cell', mapset = mapset)['file']:
            grass.fatal(_("Temporary raster map <%s> already exists.") % value)

    
    #step 0 - Calculate water height at impact coordinates
    #============================================================================================
    if not flags["g"]:
        grass.message("step 0")
    i_hw = grass.read_command("r.what", flags="f",map=lake,coordinates=[(east,north)]).split("|")[-2]
    if i_hw=="*":
        grass.fatal(_("Coordinates <%s,%s> are not on the lake.") %(east,north))
    else:
        #i_hw = float(i_hw)
        i_hw = idepth

    #step 1 - Estimate impulse wave product parameter P (Heller, 2007; Heller and Hager, 2009)
    #==========================================================================================    
    if not flags["g"]:
        grass.message("step 1")
    M = ( rho * vol ) / ( rho_w * width * math.pow(i_hw,2) )
    S = thick / i_hw
    F = vel / math.sqrt( g * i_hw )
    P = F * math.sqrt(S) * math.pow(M,0.25) * math.sqrt( math.cos( 6.0 / 7.0 * math.radians(slope) ) )
    if not flags["g"]:
        grass.message("M=%s - S=%s - F=%s - P=%s" %(M,S,F,P))

    #step 2 - Estimate maximum wave informations (Heller, 2007)
    #  [Hm = height, Tm=period, a=amplitude, c=celerity, Lm=length, rm=distance from impact]
    #============================================================================================
    if not flags["g"]:
        grass.message("step 2")
    Hm = (5.0/9.0) * math.pow(P,4.0/5.0) * i_hw 
    Tm = 9 * math.sqrt(P) * math.sqrt(i_hw/g)
    a = 4.0 / 5.0 * Hm
    c = math.sqrt( g * (i_hw+a) )
    Lm = Tm * c
    rm = (11.0/2.0) * math.sqrt(P) * i_hw
    #grass.message( "%s * %s * %s" %((5.0/9.0),math.pow(P,4.0/5.0),i_hw) )
    #grass.message("Hm=%s - Tm=%s - a=%s - c=%s - Lm=%s - rm=%s" %(Hm,Tm,a,c,Lm,rm))
    
    #step 3 - Estimate near field [0] (x<rm) and far field (x>rm) [1]
    #============================================================================================
    #calculate impact map
    if not flags["g"]:
        grass.message("step 3")
    i_col = math.floor( (east - region["w"]) / region["ewres"]) + 1
    i_row = math.floor( (region["n"] - north) / region["nsres"]) + 1
    grass.mapcalc(" $impact = if( col()==$icol && row()==$irow, 1, null() )", impact=tm["impact"], icol=i_col, irow=i_row, quiet=quiet)
    #grass.message("col=%s - row=%s east=%s north=%s" %(i_col,i_row,east,north))
    #calculate distance map
    grass.run_command("r.grow.distance", input=tm["impact"], distance=tm["distance"], quiet=quiet)
    #calculate far field (=1) and near field (=0)
    grass.mapcalc(" $field = if( $distance>$rm,1,0)", field=tm["field"], distance=tm["distance"], rm=rm, quiet=quiet)

    #step 4 - Calculate wave height in the far field
    #============================================================================================
    #calculate azimut map
    if not flags["g"]:
        grass.message("step 4")
    grass.mapcalc(""" $azimut = \
                        if( x()-$east==0 && y()-$north==0,null(), \
                          if( x()-$east==0 && y()-$north>0, 90, \
                            if( x()-$east==0 && y()-$north<0, 270, \
                              if( x()-$east>0 && y()-$north>0, atan(      (x()-$east) / (y()-$north) ), \
                                if( x()-$east<0 && y()-$north>0, atan(    (x()-$east) / (y()-$north) ) +360, \
                                  if( x()-$east>0 && y()-$north<0, atan(  (x()-$east) / (y()-$north) ) +180, \
                                    if( x()-$east<0 && y()-$north<0, atan((x()-$east) / (y()-$north) ) +180,-1 ) \
                                  ) \
                                ) \
                              ) \
                            ) \
                          ) \
                        ) """, azimut=tm["azimut"], east=east, north=north, quiet=quiet)
    #calculate direction map
    grass.mapcalc(" $gamma = $azimut - $impact_azimut", gamma=tm["gamma"],azimut=tm["azimut"],impact_azimut=azi, quiet=quiet)
    

    #calculate wave propagation in the far field (H=height, T=period, L=length), in the near field values are Hm,Tm,Lm
    grass.mapcalc(" $H = if($field==1,(3.0/2.0) * pow($P,(4.0/5.0)) * pow(cos(2.0/3.0*$gamma),2) * pow(($distance/$ihw),-2.0/3.0) * $ihw ,$Hm)",
                    H = tm["H"], P = P, gamma = tm["gamma"], distance = tm["distance"], ihw = i_hw, Hm = Hm, field = tm["field"], quiet=quiet)

    #accounting for solid mass type
    if flags["s"]:
        rf = (a / (0.26*F))/a
        print "rf=%s" %rf
        grass.mapcalc(" $H = if($lake>0, $H * $rf, $H)",
                    H = tm["H"], field = tm["field"], rf = rf, lake = lake, overwrite = True, quiet=quiet)     

    #accounting for shoaling effect
    grass.mapcalc(" $H = if($lake>0 && $field==1, $H * pow(($ihw/$lake),(1.0/4.0)), $H)",
                    H = tm["H"], field = tm["field"], ihw = i_hw, lake = lake, overwrite = True, quiet=quiet)                    
        
    grass.mapcalc(" $T = if($lake>0 && $field==1, 15 * pow($H/$ihw,1.0/4.0) * sqrt($ihw/$g), $Tm)",
                    T = tm["T"], H = tm["H"], ihw = i_hw, g = g, Tm = Tm, lake = lake, field = tm["field"], quiet=quiet)
                    
    grass.mapcalc(" $L = if($lake>0 && $field==1, $T * $c, $Lm)",
                    L = tm["L"], T = tm["T"], c = c, Lm = Lm, lake = lake, field = tm["field"], quiet=quiet)
    
    if outH is not "":
        grass.run_command("g.copy",rast="%s,%s" %(tm["H"],outH), overwrite=True)

    #step 5 - Calculate run-up
    #============================================================================================
    if not flags["g"]:
        grass.message("step 5")

    #calculate runup zones: 
    #   - 1 = wave propagation zone
    #   - 100 = runup propagation zone
    #   - 10000 = coast terrain
    #   - 0 = wave generation (near field)
    #   N.B.: wbc = H/h, wave break condition
    #wbc = 0.8 --> following Coast Engineering Manual
    #wbc = 0.521 -- follwoing equations limits
    grass.mapcalc("$zones = if( isnull($lake), 10000, if($field==0, 0, if($H/$lake>$wbc, 100, 1)))", 
                zones=tm["zones"],lake=lake,H=tm["H"],field=tm["field"], wbc=wbc, quiet=quiet)

    #calculate runup line (2=runup line, 1=coast line affected by runup, 3=coast line not affected by runup)
    grass.run_command("r.neighbors", input=tm["zones"], output=tm["zoneSUM"], method="sum", size=3, quiet=quiet)
    grass.mapcalc("""$ruline = if($ZO==1 && $ZOS>10000 && $ZOS<80000,1, \
                                    if($ZO==1 && $ZOS>100 && $ZOS<900,2, \
                                        if($ZO==100 && $ZOS>10000 && $ZOS<80000,3,0) \
                                      ) \
                                  )""",
                    ruline = tm["ruline"], ZO=tm["zones"], ZOS=tm["zoneSUM"], quiet=quiet)

    #calculate runup maximum height at runup line               
    grass.run_command("r.slope.aspect", elevation=dtm, slope=tm["slope"], quiet=quiet)
    grass.mapcalc("""$runup = if($ruline==2, 1.25*pow($H/$h,5/4)*pow($H/$L,-3/20)*pow(90/$slope,1/5)*$h, \
                                    if($ruline==1, $H,0) \
                                )""",
                    runup=tm["runup"], ruline=tm["ruline"], H=tm["H"], h=lake, L=tm["L"], slope=tm["slope"], overwrite=True, quiet=quiet)

    #calculate elevation surface (dtm + water level)
    grass.mapcalc("$elev = if(isnull($lake),$dtm,$lake+$dtm)", elev=tm["elev"], lake=lake, dtm=dtm, overwrite=True, quiet=quiet)

    #calculate wave elevation in cm
    grass.mapcalc("$wave_elev = if($runup!=0, float($runup+$elev)*100,0.0)",
                    wave_elev=tm["wave_elev"],runup=tm["runup"],elev=tm["elev"],overwrite=True, quiet=quiet)
    
    tm["outA"] = outI+"A_"+ processid
    tm["outB"] = outI+"B_"+ processid

        #due to non-support of floating raster for grass7 version of r.surf.idw, we need to do pre- and post- conversion of CELL type to DCELL type
    info_wave_elev = grass.parse_command('r.info', map=tm["wave_elev"], flags='r') # get min and max info

    minimal=float(info_wave_elev['min'])
    maximal=float(info_wave_elev['max'])
    
    minimal_decimals = str(minimal)[::-1].find('.') # get number of decimals
    maximal_decimals = str(maximal)[::-1].find('.') # get number of decimals
    
    decimals = max(minimal_decimals, maximal_decimals)
 
    newminimal = int(10**decimals * minimal) # min value for float to integer conversion
    newmaximal = int(10**decimals * maximal) # max value for float to integer conversion
   
    rule = str(minimal) + ":" + str(maximal) + ":" + str(newminimal) + ":" + str(newmaximal)
    rule_invert = str(newminimal) + ":" + str(newmaximal) + ":" + str(minimal) + ":" + str(maximal)

    print "number of decimals for float to integer conversion : ",decimals
    print "rule for float to integer conversion : ",rule
    print "rule for integer to float conversion : ",rule_invert

    grass.write_command("r.recode", input=tm["wave_elev"], output='tmp2', rules='-', stdin=rule, overwrite=True)
    grass.run_command("r.surf.idw", input='tmp2', output='tmp3', npoints=1, quiet=True, overwrite = True)
    grass.write_command("r.recode", flags="d", input='tmp3', output=tm["outA"], rules='-', stdin=rule_invert, overwrite=True)

    #info1 = grass.parse_command('r.info', map=tm["wave_elev"], flags='r')
    #info2 = grass.parse_command('r.info', map='tmp2', flags='r')
    #info3 = grass.parse_command('r.info', map='tmp3', flags='r')
    #info4 = grass.parse_command('r.info', map=tm["outA"], flags='r')
    #info2_c = grass.parse_command('r.info', map='tmp2', flags='g')
    #info3_c = grass.parse_command('r.info', map='tmp3', flags='g')
    #info1_c = grass.parse_command('r.info', map=tm["wave_elev"], flags='g')
    #info4_c = grass.parse_command('r.info', map=tm["outA"], flags='g')

    #print "info1", info1,info1_c
    #print "info2",info2,info2_c
    #print "info3",info3,info3_c
    #print "info4",info4,info4_c
    
    grass.run_command("g.remove", flags="f", type="raster", name="tmp2,tmp3,tmp4", quiet=True)

    #calculate inundation in m
    grass.mapcalc("$inondB = if($zones==10000 && $elev<$inondA/100.0, ($inondA/100.0)-$elev,null())",
                    inondB=tm["outB"],inondA=tm["outA"],elev=tm["elev"],zones=tm["zones"],overwrite=True, quiet=quiet)
    grass.run_command("r.neighbors", input=tm["outB"], output=outI, selection=tm["outB"], overwrite=True)
    #grass.run_command("r.neighbors", input=tm["outB"], output=outI, selection=tm["outB"], overwrite=True, quiet=quiet)

    #mask output inundation
    if options['shadow'] is not '':
        grass.mapcalc("$inond=if($shadow,$inond,null())",inond=outI,shadow=shadow,overwrite=True, quiet=quiet)
    if flags['a']:
        grass.mapcalc("$inond=if($gamma>-90 && $gamma<90,$inond,null())",inond=outI,gamma=tm["gamma"],overwrite=True, quiet=quiet)

    
    #GENERATE A REPORTS
    report = ""
    if not flags["g"]:
        grass.message("step 6 - generating reporting")
    if flags['w']:
        report += "=====================================================\n"
        report += "=============    MAXIMUM WAVE HEIGHT    =============\n"
        report += "=====================================================\n"
        report += "Hm=%s\n" % Hm
        report += "Tm=%s\n" % Tm
        report += "Lm=%s\n" % Lm
        report += "a=%s\n" % a
        report += "c=%s\n" % c
        report += "rm=%s\n" % rm
    if flags['c']:
        report += "=====================================================\n"
        report += "==========    LIMITING CONDITIONS REPORT    =========\n"
        report += "=====================================================\n"
        #slide froude number
        report += "Slide Froude number limitation (0.86<= F <= 6.83):"
        if F>= 0.86 and F<= 6.83:
            report += " value=%s respected=%s\n" %(F,True)
        else:
            report += " value=%s respected=%s\n" %(F,False)
        #Relative slide thickness
        report += "Relative slide thickness (0.09<= S <= 1.64):"
        if S>= 0.09 and S<= 1.64:
            report += " value=%s respected=%s\n" %(S,True)
        else:
            report += " value=%s respected=%s\n" %(S,False)
        #Relative slide mass
        report += "Relative slide mass (0.11<= M <= 10.02):"
        if S>= 0.11 and S<= 10.02:
            report += " value=%s respected=%s\n" %(M,True)
        else:
            report += " value=%s respected=%s\n" %(M,False)
        #Relative slide density
        report += "Relative slide density (0.59<= D <= 1.72):"
        D = (rho/1000)
        if D>= 0.59  and D<= 1.72:
            report += " value=%s respected=%s\n" %(D,True)
        else:
            report += " value=%s respected=%s\n" %(D,False)
        #Relative granulate density
        report += "Relative granulate density (0.96<= Dg <= 2.75):"
        Dg = (1-0.01*por)/1000
        if Dg>= 0.96  and Dg<= 2.75:
            report += " value=%s respected=%s\n" %(Dg,True)
        else:
            report += " value=%s respected=%s\n" %(Dg,False)
        #Relative slide volume
        report += "Relative slide volume (0.05<= V <= 5.94):"
        V = vol/(width*thick*thick)
        if V>= 0.05  and V<= 5.94:
            report += " value=%s respected=%s\n" %(V,True)
        else:
            report += " value=%s respected=%s\n" %(V,False)
        #Relative slide width
        report += "Relative slide width (0.74<= B <= 3.33):"
        B = width/thick
        if B>= 0.74  and B<= 3.33:
            report += " value=%s respected=%s\n" %(B,True)
        else:
            report += " value=%s respected=%s\n" %(B,False)
        #Bulk slide porosity
        report += "Bulk slide porosity (30.7<= por <= 43.3):"
        if por>= 30.7  and por<= 43.3:
            report += " value=%s respected=%s\n" %(por,True)
        else:
            report += " value=%s respected=%s\n" %(por,False)
        #Slide impact angle
        report += "Slide impact angle (30deg<= beta <= 90deg):"
        if slope>= 30  and slope<= 90:
            report += " value=%s respected=%s\n" %(slope,True)
        else:
            report += " value=%s respected=%s\n" %(slope,False)
        #Impulse product parameter
        report += "Impulse product parameter (0.17<= P <= 8.13):"
        if P>= 0.17  and P<= 8.13:
            report += " value=%s respected=%s\n" %(P,True)
        else:
            report += " value=%s respected=%s\n" %(P,False)
        """
        #temporary maps for reporting
        #tm["rrd"]="rrd_"+processid
        #tm["rrdB"]="rrdB_"+processid
        #tm["rws"]="rws_"+processid
        #tm["rwsB"]="rwsB_"+processid
        #Relative radial distance
        report += "Relative radial distance (5<= r/h <= 30):"
        if options['shadow'] is not '':
            grass.mapcalc("$rrd=if(!isnull($lake) && $shadow,$distance/$H,null())", rrd=tm["rrd"], lake=lake, shadow=shadow , distance=tm["distance"], H=tm["H"], quiet=quiet)
        elif flags['a']:
            grass.mapcalc("$rrd=if(!isnull($lake) && ($gamma>-90 || $gamma<90),$distance/$H,null())", rrd=tm["rrd"], lake=lake, gamma=tm["gamma"], distance=tm["distance"], H=tm["H"], quiet=quiet)
        grass.mapcalc("$rrdB=if($rrd<=30 && $rrd>=5,1,0)", rrdB=tm["rrdB"], rrd=tm["rrd"])
        ret = grass.read_command("r.univar",map=tm["rrdB"],flags="g")
        info = {}
        for l in ret.split("\n"):
            s = l.split("=")
            if len(s)==2:
                info[s[0]]=float(s[1])
        report += "value=%s respected=%s%%\n" %(info["mean"], info["sum"]*100 / (info["cells"]-info["null_cells"]))
        #Relative wave stepness
        report += "Relative wave stepness"
        if options['shadow'] is not '':
            grass.mapcalc("$rws=if($ruline==2 && $shadow,$H/$L,null())", rws=tm["rws"], ruline=tm["ruline"], shadow=shadow , H=tm["H"], L=tm["L"])
        elif flags['a']:
            grass.mapcalc("$rws=if($ruline==2 && ($gamma>-90 || $gamma<90),$H/$L,null())", rws=tm["rws"], ruline=tm["ruline"], gamma=tm["gamma"], H=tm["H"], L=tm["L"])
        grass.mapcalc("$rwsB=if($rws<=30 && $rws>=5,1,0)", rwsB=tm["rwsB"], rws=tm["rws"])
        ret = grass.read_command("r.univar",map=tm["rwsB"],flags="g")
        info = {}
        for l in ret.split("\n"):
            s = l.split("=")
            if len(s)==2:
                info[s[0]]=float(s[1])
        report += "value=%s respected=%s%%\n" %(info["mean"], info["sum"]*100 / (info["cells"]-info["null_cells"]))
        """
    if flags["c"] or flags["w"]:
        report += "=====================================================\n"
        print report

        """
        report = "Relative radial distance (5<= r/h <= 30):"
        B = tm["gamma"]/lake
        if slope>= 0.74  && slope<= 3.33:
            report += " value=%s respected=%s\n" %(B,True)
        else:
            report += " value=%s respected=%s\n" %(B,False)
        """
    
    if not flags["t"]:
        grass.run_command("g.remove", flags="f", type="raster", name=",".join([tm[m] for m in tm.keys()]), quiet=True)
        grass.run_command("g.remove", type="raster", name=",".join([tm[m] for m in tm.keys()]), quiet=True)
    t = False
    
def cleanup():
    if t:
        grass.run_command("g.remove", flags="f", type="raster", name=",".join([tm[m] for m in tm.keys()]), quiet=True)
        grass.run_command("g.remove", type="raster", name=",".join([tm[m] for m in tm.keys()]), quiet=True)

if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()



