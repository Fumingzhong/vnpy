# encoding: UTF-8

from __future__ import division 
from math import floor
from datetime import datetime

from vnpy.trader.vtConstant import (EMPTY_INT, EMPTY_FLOAT, 
                                    EMPTY_STRING, EMPTY_UNICODE)


EVENT_MULTITRADING_TICK = 'eMultiTradingTick'
EVENT_MULTITRADING_POS = 'eMultiTradingPos'
EVENT_MULTITRADING_LOG = 'eMultiTradingLog'
EVENT_MULTITRADING_ALGO = 'eMultiTradingAlgo'
EVENT_MULTITRADING_ALGOLOG = 'eMultiTradingAlogLog'


########################################################################
class MultiLeg(object):
    """"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        self.vtSymbol  = EMPTY_STRING       #代码
        self.ratio = EMPTY_INT              #实际交易时合约比例 #不适用
        self.multiplier = EMPTY_FLOAT       #计算价差时的乘数
        self.payup  = EMPTY_INT             #对冲时的超价tick
        
        self.bidPrice =  EMPTY_FLOAT    
        self.askPrice = EMPTY_FLOAT
        self.bidVolume = EMPTY_INT
        self.askVolume = EMPTY_INT
        
        self.longPos =  EMPTY_INT
        self.shortPos = EMPTY_INT
        self.netPos = EMPTY_INT
    
    
########################################################################
class MultiMulti(object):
    """"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        self.name = EMPTY_UNICODE           #名称
        self.symbol = EMPTY_STRING          #代码（组合）
        
        self.activeLeg = None               #主动腿
        self.passiveLegs = []               #被动腿（支持多条）
        self.allLegs = []                   #所有腿
        
        #仅用于查看
        self.bidPrice = EMPTY_FLOAT
        self.askPrice = EMPTY_FLOAT
        self.bidVolume = EMPTY_INT
        self.askVolume = EMPTY_INT
        self.time = EMPTY_STRING
        
        #暂不适用
        self.longPos = EMPTY_INT
        self.shortPos = EMPTY_INT
        self.netPost = EMPTY_INT
        
    #----------------------------------------------------------------------
    def initMulti(self):
        """初始化价差"""
        # 价差至少要有一条腿
        if not self.activeLeg:
            return
        
        #生成所有腿列表
        self.allLegs.append(self.activeLeg)
        self.allLegs.extend(self.passiveLegs)
        
        #生成价差代码
        legSymbolList = []
        
        for leg in self.allLegs:
            if leg.multiplier >= 0:
                legSymbol = '+%s*%s' %(leg.multiplier, leg.vtSymbol)
            else:
                legSymbol = '%s*%s' %(leg.multiplier, leg.vtSymbol)
            legSymbolList.append(legSymbol)
            
        self.symbol = ''.join(legSymbolList)
        
    #----------------------------------------------------------------------
    def calculatePrice(self):
        """计算价格"""
        # 清空价格和委托量
        self.bidPrice = EMPTY_FLOAT
        self.askPrice = EMPTY_FLOAT
        self.bidVolume = EMPTY_INT
        self.askVolume = EMPTY_INT 
        
        #遍历腿列表
        for n, leg in enumerate(self.allLegs):
            # 过滤有某条腿尚未初始化的情况（无挂单量）
            if not leg.bidVolume or not leg.askVolume:
                self.bidPrice = EMPTY_FLOAT
                self.askPrice = EMPTY_FLOAT
                self.bidVolume = EMPTY_INT
                self.askVolume = EMPTY_INT
                return
            # 计算价格
            if leg.multiplier > 0:
                self.bidPrice += leg.bidPrice * leg.multiplier
                self.askPrice += leg.askPrice * leg.multiplier
            else:
                self.bidPrice += leg.bidPrice * leg.multiplier
                self.askPrice += leg.askPrice * leg.multiplier
                
            # 计算报单量
            if leg.ratio > 0:
                legAdjustedBidVolume = floor(leg.bidVolume/leg.ratio)
                legAdjustedAskVolume = floor(leg.askVolume/leg.ratio)
            else:
                legAdjustedBidVolume = floor(leg.askVolume/abs(leg.ratio))
                legAdjustedAskVolume = floor(leg.bidVolume/abs(leg.ratio))
                
            if n == 0:
                self.bidVolume = legAdjustedBidVolume                       #对于第一条腿，直接初始化
                self.askVolume = legAdjustedAskVolume
            else:
                
                self.bidVolume = min(self.bidVolume, legAdjustedBidVolume)  #对于后续的腿，价差可交易报单量取最小值
                self.askVolume = min(self.askVolume, legAdjustedAskVolume)
                
        # 更新时间
        self.time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        
    #----------------------------------------------------------------------
    def calculatePos(self):
        """计算持仓"""
        # 组合持仓暂不适用
        pass
    
    #----------------------------------------------------------------------
    def addActiveLeg(self, leg):
        """添加主动腿"""
        self.activeLeg = leg
        
    #----------------------------------------------------------------------
    def addPassiveLeg(self, leg):
        """添加被动腿"""
        self.passiveLegs.append(leg)
        
        
        
        
    
    