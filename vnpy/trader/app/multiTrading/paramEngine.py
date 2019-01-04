# encoding:UTF-8
import sys
sys.path.append('C:\boSpreadArbitrage')
from dataEngine import loadJson
from vnpy.trader.vtConstant import (EMPTY_INT, EMPTY_FLOAT, EMPTY_STRING)

########################################################################
class ZfmSpreadParam(object):
    """价差参数类"""
    #----------------------------------------------------------------------
    def __init__(self, paramSetting = None):
        """Constructor"""
        if not paramSetting:
            self.K = EMPTY_FLOAT
            self.r = EMPTY_FLOAT
            self.endDate = EMPTY_STRING
            self.sigmaList = list()
            self.rho = EMPTY_FLOAT
            self.cp = EMPTY_INT
            self.direction = EMPTY_STRING
            self.amount = EMPTY_INT
            self.bandWidth = EMPTY_FLOAT
            self.ratio = EMPTY_FLOAT
        
    
    
########################################################################
class ParamEngine(object):
    """参数计算引擎"""

    #----------------------------------------------------------------------
    def __init__(self, paramFile = None):
        """Constructor"""
        if paramFile:
            d = loadJson(paramFile)
        else:
            pass
        
        
    
    