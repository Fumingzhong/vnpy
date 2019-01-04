# encoding: UTF-8

from __future__ import division 
from math import floor
from datetime import datetime

from vnpy.trader.vtConstant import (EMPTY_INT, EMPTY_FLOAT, 
                                    EMPTY_STRING, EMPTY_UNICODE)
from vnpy.trader.vtConstant import DIRECTION_LONG, DIRECTION_SHORT


EVENT_MULTITRADING_TICK = 'eMultiTradingTick'
EVENT_MULTITRADING_POS = 'eMultiTradingPos'
EVENT_MULTITRADING_LOG = 'eMultiTradingLog'
EVENT_MULTITRADING_ALGO = 'eMultiTradingAlgo'
EVENT_MULTITRADING_ALGOLOG = 'eMultiTradingAlogLog'


########################################################################
class zfmLegPos(object):
    """腿持仓信息"""

    #----------------------------------------------------------------------
    def __init__(self, longPos=0, shortPos=0, posPrice=0, tradingPnl=0, positionPnl=0, totalPnl=0, turnover=0, commission=0, slippage=0, netPnl=0):
        """Constructor"""
        self.vtSymbol = EMPTY_STRING
        self.longPos = longPos
        self.shortPos = shortPos
        self.netPos = longPos - shortPos
        
        self.posPrice = posPrice             
        self.closePrice = EMPTY_FLOAT
        
        self.tradingPnl = EMPTY_FLOAT
        self.positionPnl = EMPTY_FLOAT
        self.totalPnl = EMPTY_FLOAT
        
        self.turnover = 0
        self.commission = 0
        self.slippage = 0 
        self.netPnl = 0 
        
        self.longTrade = 0
        self.shortTrade = 0
        
    #----------------------------------------------------------------------
    def update(self, trade):
        """汇总多单成交和空单成交"""
        if trade.direction == DIRECTION_LONG:
            if not self.longTrade:
                self.longTrade = trade
            else:
                self.longTrade.price = (self.longTrade.volume * self.longTrade.price + trade.volume * trade.price)/(self.longTrade.volume + trade.volume)
                self.longTrade.price = round(self.longTrade.price, 2)
                self.longTrade.volume += trade.volume
                self.longTrade.tradeTime = trade.tradeTime                
        else:
            if not self.shortTrade:
                self.shortTrade = trade
            else:
                self.shortTrade.price = (self.shortTrade.volume * self.shortTrade.price + trade.volume * trade.price)/(self.shortTrade.volume + trade.volume)
                self.shortTrade.price = round(self.shortTrade.price, 2)
                self.shortTrade.volume += trade.volume
                self.shortTrade.tradeTime = trade.tradeTime
    
    #----------------------------------------------------------------------
    def calculatePnl(self, closePrice, size=1, rate=0, slippage=0):
        """计算盈亏"""
        self.closePrice = closePrice
        # 多头部分
        if not self.longTrade:
            pass
        else:
            self.longPos += self.longTrade.volume
            self.turnover += self.longTrade.volume * size * self.longTrade.price
            self.slippage += self.longTrade.volume * size * slippage
            self.commission += self.longTrade.volume * size * self.longTrade.price * rate
            if self.netPos > 0:
                self.posPrice = (self.netPos * self.posPrice + self.longTrade.volume * self.longTrade.price)/(self.netPos + self.longTrade.volume)
                self.posPrice = round(self.posPrice, 2)
                self.positionPnl = (self.netPos + self.longTrade.volume) * (self.closePrice - self.posPrice) * size
                
            elif self.netPos < 0:
                if self.longTrade.volume + self.netPos > 0:
                    self.tradingPnl += self.netPos * (self.longTrade.price - self.posPrice) * size
                    self.posPrice = self.longTrade.price
                    self.positionPnl = (self.longTrade.volume + self.netPos) * (self.closePrice - self.posPrice) * size
                    
                elif self.longTrade.volume + self.netPos < 0:
                    self.tradingPnl += self.longTrade.volume * (self.posPrice - self.longTrade.volume) * size
                    self.positionPnl = (self.longTrade.volume + self.netPos) * (self.closePrice - self.posPrice) * size
                    
                else:
                    self.tradingPnl += self.longTrade.volume * (self.posPrice - self.longTrade.price) * size
                    self.posPrice = 0
                    self.positionPnl = 0
                    
            else:
                self.posPrice = self.longTrade.price
                self.positionPnl = self.longTrade.volume * (self.closePrice - self.longTrade.price) * size
                
            self.netPos += self.longTrade.volume
            # 计算完之后成交清零
            self.longTrade = 0
                                            
        # 空头部分
        if not self.shortTrade:
            pass
        else:
            self.shortPos += self.shortTrade.volume
            self.turnover += self.shortTrade.volume * size * self.shortTrade.price
            self.slippage += self.shortTrade.volume * size * slippage
            self.commission += self.shortTrade.volume * size * self.shortTrade.price * rate
            if self.netPos < 0:
                self.posPrice = (self.netPos * self.posPrice - self.shortTrade.volume * self.shortTrade.price) / (self.netPos - self.shortTrade.volume)
                self.posPrice = round(self.posPrice, 2)
                self.positionPnl = (self.netPos - self.shortTrade.volume) * (self.closePrice - self.posPrice) * size
            elif self.netPos > 0:
                if self.netPos - self.shortTrade.volume > 0:
                    self.tradingPnl += self.shortTrade.volume * (self.shortTrade.price - self.posPrice) * size
                    self.positionPnl = (self.netPos - self.shortTrade.volume) * (self.closePrice - self.posPrice) * size
                elif self.netPos - self.shortTrade.volume < 0:
                    self.tradingPnl += self.netPos * (self.shortTrade.price - self.posPrice) * size
                    self.posPrice = self.shortTrade.price
                    self.positionPnl = (self.netPos - self.shortTrade.volume) * (self.posPrice - self.shortTrade.price) * size
                else:
                    self.tradingPnl += self.shortTrade.volume * (self.shortTrade.price - self.posPrice) * size
                    self.posPrice = 0
                    self.positionPnl = 0
            else:
                self.posPrice = self.shortTrade.price 
                self.positionPnl = self.shortTrade.volume * (self.shortTrade.price - self.posPrice)
                
            self.netPos -= self.shortTrade.volume
            # 计算完之后成交清零
            self.shortTrade = 0
            
        assert self.netPos == self.longPos - self.shortPos
        
        self.netPnl = self.totalPnl - self.commission - self.slippage
    
    
########################################################################
class zfmMultiPos(object):
    """组合持仓信息"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        self.name = EMPTY_STRING
        self.activePos = 0
        self.passivePos = 0
        
        self.positionPrice = 0
        self.multiPrice = 0
        
        self.tradingPnl = 0
        self.positionPnl = 0 
        self.totalPnl = 0
        
        self.turnover = 0
        self.commission = 0
        self.slippage = 0
        self.netPnl = 0
        
        self.multiPos = 0
        
    #----------------------------------------------------------------------
    def addActivePos(self, pos):
        """增加主动腿持仓情况"""
        self.activePos = pos
        
    #----------------------------------------------------------------------
    def addPassivePos(self, pos):
        """增加被动腿持仓情况"""
        self.passivePos = pos
        
    #----------------------------------------------------------------------
    def setMultiPrice(self, multiPrice):
        """设置组合现价"""
        self.multiPrice = multiPrice
        
    #----------------------------------------------------------------------
    def calculatePnl(self):
        """计算盈亏"""
        if not self.activePos or not self.passivePos:
            print 'activePos or passivePos not initialized!!'
            return
        
        self.positionPrice = self.activePos.posPrice - self.passivePos.posPrice 
        self.tradingPnl = self.activePos.tradingPnl + self.passivePos.tradingPnl
        self.positionPnl = self.activePos.positionPnl + self.passivePos.positionPnl
        self.turnover = self.activePos.turnover + self.passivePos.turnover
        self.commission = self.activePos.commission + self.passivePos.commission
        self.netPnl = self.activePos.netPnl + self.passivePos.netPnl   
        
        self.multiPos = min(abs(self.activePos.netPos), abs(self.passivePos.netPos))
        if self.activePos.netPos < 0:
            self.multiPos = -self.multiPos
           
    
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
        
        
        
        
    
    