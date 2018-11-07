# encoding: UTF-8
from __future__ import division 
from math import floor
import sys
sys.path.append(r'D:\pythonworkspace\codeFromZuo')
sys.path.append(r'D:\pythonworkspace\marketMonitor')
from SpreadOption import KirkMethod
from ZFMFunctions import ZfmFunctions
from vnpy.trader.vtConstant import (EMPTY_INT, EMPTY_FLOAT, 
                                    EMPTY_STRING, EMPTY_UNICODE,
                                    DIRECTION_LONG, DIRECTION_SHORT,
                                    OFFSET_OPEN, OFFSET_CLOSE,
                                    STATUS_ALLTRADED, STATUS_CANCELLED, STATUS_REJECTED)
from vnpy.trader.vtFunction import getJsonPath 
import json
import traceback
from datetime import date


########################################################################
class MultiAlgoTemplate(object):
    """组合算法交易模板"""
    
    algoParamsDict = {}                             # 策略参数
    algoParamsFileName = 'MultiAlgoParams_setting.json'
    algoParamsFilePath = getJsonPath(algoParamsFileName, __file__)

    #----------------------------------------------------------------------
    def __init__(self, algoEngine, multi):
        """Constructor"""
        self.algoEngine = algoEngine                # 算法引擎
        self.multiName = multi.name                 # 组合名称
        self.multi = multi                          # 组合对象
        
        self.algoName = EMPTY_STRING                # 算法名称
        self.active = False                         # 工作状态
        
        self.maxPosSize = EMPTY_INT                 # 最大单边持仓
        self.maxOrderSize = EMPTY_INT               # 最大单笔委托量
        
        #如果有文件则加载文件中的参数，无的话则在策略中输入
        try:
            self.algoParamsDict = self.loadAlgoSetting()
        except:
            self.writeLog(u'策略参数在类内赋值')
        # 算法参数初始化
        __d = self.__dict__
        print self.algoParamsDict
        if not self.algoParamsDict:
            pass
        else:
            for (k,v) in self.algoParamsDict.items():
                __d[k] = v
            
            self.__dict__ = __d
        
    #----------------------------------------------------------------------
    def updateMultiTick(self, multi):
        """"""
        raise NotImplementedError
    
    #----------------------------------------------------------------------
    def updateMultiPos(self, multi):
        """"""        
        raise NotImplementedError
    
    #----------------------------------------------------------------------
    def updateTrade(self, trade):
        """"""
        raise NotImplementedError
    
    #----------------------------------------------------------------------
    def updateOrder(self, order):
        """"""
        raise NotImplementedError
    
    #----------------------------------------------------------------------
    def updateTimer(self):
        """"""
        raise NotImplementedError
    
    #----------------------------------------------------------------------
    def start(self):
        """"""
        raise NotImplementedError
    
    #----------------------------------------------------------------------
    def stop(self):
        """"""
        raise NotImplementedError
    
        
    #----------------------------------------------------------------------
    def setMaxOrderSize(self, maxOrderSize):
        """设置最大单笔委托数量"""
        self.maxOrderSize = maxOrderSize
        
    #----------------------------------------------------------------------
    def setMaxPosSize(self, maxPosSize):
        """设置最大持仓数量"""
        self.maxPosSize = maxPosSize
        
    #----------------------------------------------------------------------
    def putEvent(self):
        """发出算法更新事件"""
        self.algoEngine.putAlgoEvent(self)
        
    #----------------------------------------------------------------------
    def writeLog(self, content):
        """输出算法日志"""
        print content
        prefix = ''.join([self.multiName, self.algoName])
        content = ':'.join([prefix, content])
        self.algoEngine.writeLog(content)
        
    #----------------------------------------------------------------------
    def getAlgoParams(self):
        """获得算法参数"""
        d = self.__dict__
        return d
    
    
    #----------------------------------------------------------------------
    def loadAlgoSetting(self):
        """加载策略参数文件"""
        try:
            with open(self.algoParamsFilePath) as f:
                l = json.load(f)
                self.algoParamsDict = l.get(self.multi.name, {})
                if not self.algoParamsDict and l:
                    self.writeLog(u'文件无对应组合参数配置')
                elif not l:
                    self.writeLog(u'文件内容为空')
                else:
                    self.writeLog(u'组合参数配置加载完成')
        except:
            content = u'组合参数配置加载出错，原因：' + traceback.format_exc()
            self.writeLog(content)
        return self.algoParamsDict
    #----------------------------------------------------------------------
    def setAlgoParams(self, d):
        """设置算法参数"""
        pass
        
        
        
        
        
        
        
        
        
        
        
        
    
########################################################################
class SpreadOptionAlgo(MultiAlgoTemplate):
    """价差期权算法"""
    FINISHED_STATUS = [STATUS_ALLTRADED, STATUS_CANCELLED, STATUS_REJECTED]

    #----------------------------------------------------------------------
    def __init__(self, algoEngine, multi):
        """Constructor"""
        super(SpreadOptionAlgo, self).__init__(algoEngine, multi)
        
        self.algoName = u'SpreadOption'
        
        self.activeVtSymbol = multi.activeLeg.vtSymbol              # 主动腿代码
        
        # 缓存每条腿对象的字典
        self.legDict = {}
        self.legDict[multi.activeLeg.vtSymbol] = multi.activeLeg 
        for leg in multi.passiveLegs:
            self.legDict[leg.vtSymbol] = leg
        
        self.activeTaskDict = {}                                    # 主动腿需要下单的数量字典  vtSymbol:volume    
        self.hedgingTaskDict = {}                                   # 被动腿需要对冲的数量字典  vtSymbol:volume
        self.legOrderDict = {}                                      # vtSymbol: list of vtOrderID
        self.orderTradeDict = {}                                    # vtOrderID: tradedVolume 
        
    #----------------------------------------------------------------------
    def updateMultiTick(self, multi):
        """组合行情更新"""
        self.multi = multi
        
        # 若算法没有启动则直接返回
        if not self.active:
            return
        
        # 若当前已有主动腿委托则直接返回
        if (self.activeVtSymbol in self.legOrderDict and
            self.legOrderDict[self.activeVtSymbol]):
            return
        
        activeLeg = multi.activeLeg
        passiveLeg = multi.passiveLegs[0] 
        
        # 处理tick中tickstart与tickend之间仍有成交的情况
        if multi.time[:-4] > '14:59:00' and multi.time[:-4] <= '14:59:30':
            self.cancelLegOrder(activeLeg.vtSymbol)
            self.cancelLegOrder(passiveLeg.vtSymbol)
            return        
        
        # 加载策略所有参数
        d = self.algoParamsDict
        
        s1 = activeLeg.bidPrice 
        s2 = passiveLeg.bidPrice
        K = d['K']
        r = d['r']
        
        # 将截止日期转化成剩余时间长度
        endDate = d['endDate']
        startDate = date.today().strftime('%Y-%m-%d')
        T = round(len(ZfmFunctions().getTradeDays(startDate, endDate))/252,3)   # 剩余时间年化
        sigma1 = d['sigma1']
        sigma2 = d['sigma2']
        rho = d['rho']
        cp = d['cp']
        amount = d['amount']
        
        # 获得腿的净持仓
        netPos1 = activeLeg.netPos
        netPos2 = passiveLeg.netPos
        
        spreadCalculator = KirkMethod(s1, s2, K, r, T, sigma1, sigma2, rho, cp)
        delta1, delta2 = spreadCalculator.OptionDelta()
        
        if self.direction == 'short':
            delta1 = -delta1
            delta2 = -delta2
        else:
            pass
        
        contract1 = self.algoEngine.mainEngine.getContract(activeLeg.vtSymbol)
        contract2 = self.algoEngine.mainEngine.getContract(passiveLeg.vtSymbol)
        
        # 计算应建仓数量
        newNetPos1 = int(round(delta1 * amount / contract1.size, 0)) 
        newNetPos2 = int(round(delta2 * amount / contract2.size, 0))
        
        # 计算主动腿和被动腿委托量
        activeAdjustVolume = newNetPos1 - netPos1
        passiveAdjustVolume = newNetPos2 - netPos2
        
        # 主动腿下单参数
        activeVtSymbol = activeLeg.vtSymbol
        activeDirection = EMPTY_STRING
        activeOffset = EMPTY_STRING
        activePrice = EMPTY_FLOAT
        activeVolume = abs(activeAdjustVolume)
        
        if activeAdjustVolume > 0:
            activeDirection = DIRECTION_LONG
            activePrice = activeLeg.askPrice + activeLeg.payup * contract1.priceTick
        elif activeAdjustVolume < 0:
            activeDirection = DIRECTION_SHORT
            activePrice = activeLeg.bidPrice  - activeLeg.payup * contract1.priceTick
            
        if activeAdjustVolume and abs(newNetPos1) > abs(netPos1):
            activeOffset = OFFSET_OPEN
        elif activeAdjustVolume and abs(newNetPos1) < abs(netPos1):
            activeOffset = OFFSET_CLOSE
            
        # 排除不需要调仓的情况
        if not activeVolume:
            pass
        else:
            print activeVtSymbol, activeDirection, activeOffset, activePrice, activeVolume
            self.sendLegOrder(activeVtSymbol, activeDirection, activeOffset, activePrice, 
                             activeVolume)
            
        # 被动腿下单参数
        passiveVtSymbol = passiveLeg.vtSymbol
        passiveDirection = EMPTY_STRING
        passiveOffset = EMPTY_STRING
        passivePrice = EMPTY_FLOAT
        passiveVolume = abs(passiveAdjustVolume)
        
        if passiveAdjustVolume > 0:
            passiveDirection = DIRECTION_LONG
            passivePrice = passiveLeg.askPrice + passiveLeg.payup * contract2.priceTick
        elif passiveAdjustVolume < 0:
            passiveDirection = DIRECTION_SHORT
            passivePrice = passiveLeg.bidPrice - passiveLeg.payup * contract2.priceTick
            
        if passiveAdjustVolume and abs(newNetPos2) > abs(netPos2):
            passiveOffset = OFFSET_OPEN
        elif passiveAdjustVolume and abs(newNetPos2) < abs(netPos2):
            passiveOffset = OFFSET_CLOSE
        
        if not passiveVolume:
            pass
        else:
            print passiveVtSymbol, passiveDirection, passiveOffset, passivePrice, passiveVolume
            self.sendLegOrder(passiveVtSymbol, passiveDirection, passiveOffset, passivePrice, 
                             passiveVolume)
        
    #----------------------------------------------------------------------
    def updateMultiPos(self, multi):
        """价差持仓更新"""
        self.multi = multi
        
    #----------------------------------------------------------------------
    def updateTrade(self, trade):
        """成交更新"""
        pass
    
    #----------------------------------------------------------------------
    def updateOrder(self, order):
        """委托更新"""
        if not self.active:
            return
        
        vtOrderID = order.vtOrderID
        vtSymbol = order.vtSymbol
        newTradeVolume = order.tradedVolume
        lastTradedVolume = self.orderTradeDict.get(vtOrderID, 0)
        
        # 检查是否有新的成交
        if newTradeVolume > lastTradedVolume:
            self.orderTradeDict[vtOrderID] = newTradeVolume             # 缓存委托已成交数量
            volume = newTradeVolume - lastTradedVolume                  # 计算本次成交数量
            
            if vtSymbol == self.activeVtSymbol:
                self.newActiveLegTrade(vtSymbol, order.direction, volume)
            else:
                self.newPassiveLegTrade(vtSymbol, order.direction, volume)
                
        # 处理完成委托
        if order.status in self.FINISHED_STATUS:
            vtOrderID = order.vtOrderID
            vtSymbol = order.vtSymbol
            
            # 从委托列表中移除委托
            orderList = self.legOrderDict.get(vtSymbol, None)
            
            if orderList and vtOrderID in orderList:
                orderList.remove(vtOrderID)
                
        # 如果出现撤单或者被拒单重新发单       
        if order.status in self.FINISHED_STATUS[1:]:
            legVtSymbol = order.vtSymbol
            legDirection = order.direction
            legOffset = order.offset
            contract = self.algoEngine.mainEngine.getContract(legVtSymbol)
            leg = self.legDict[legVtSymbol]
            if legDirection == DIRECTION_LONG:
                legPrice = order.price + leg.payup * contract.priceTick
            else:
                legPrice = order.price - leg.payup * contract.priceTick
                
            legVolume = order.totalVolume
            
            #print legVtSymbol, legDirection, legOffset, legPrice, legVolume
            if not legVolume:
                pass
            else:
                self.sendLegOrder(legVtSymbol, legDirection, legOffset, legPrice, 
                                 legVolume)
            
    #----------------------------------------------------------------------
    def updateTimer(self):
        """计时更新"""
        pass
        
            
    #----------------------------------------------------------------------
    def start(self):
        """启动"""
        # 如果已经运行则直接返回状态
        if self.active:
            return self.active
        
        # 启动算法
        self.active = True
        self.writeLog(u'算法启动')
        
        return self.active
    
    #----------------------------------------------------------------------
    def stop(self):
        """停止"""
        if self.active:
            self.activeTaskDict.clear()
            self.hedgingTaskDict.clear()
            self.cancelAllOrders()
            
        self.active = False
        self.writeLog(u'算法停止')
        
        return self.active             
        
        
    #----------------------------------------------------------------------
    def sendLegOrder(self, legVtSymbol, legDirection, legOffset, legPrice, legVolume):
        """发送每条腿的委托"""
        legOrderList = self.algoEngine.sendOrder(legVtSymbol, legDirection, legOffset, legPrice, legVolume)
        # 保存到字典中
        if legVtSymbol not in self.legOrderDict:
            self.legOrderDict[legVtSymbol] = legOrderList
        else:
            self.legOrderDict[legVtSymbol].extend(legOrderList)
            
            
    #----------------------------------------------------------------------
    def newActiveLegTrade(self, vtSymbol, direction, volume):
        """新的主动成交"""
        pass
    
    #----------------------------------------------------------------------
    def newPassiveLegTrade(self, vtSymbol, direction, volume):
        """新的被动腿成交"""
        pass
        
        
    #----------------------------------------------------------------------
    def cancelLegOrder(self, vtSymbol):
        """撤销某条腿的委托"""
        if vtSymbol not in self.legOrderDict:
            return
        
        orderList = self.legOrderDict[vtSymbol]
        
        if not orderList:
            return
        
        for vtOrderID in orderList:
            self.algoEngine.cancelOrder(vtOrderID)
            
        self.writeLog(u'撤销%s的所有委托' %vtSymbol)
        
    #----------------------------------------------------------------------
    def cancelAllOrders(self):
        """撤销全部委托"""
        for orderList in self.legOrderDict.values():
            for vtOrderID in orderList:
                self.algoEngine.cancelOrder(vtOrderID)
                
        self.writeLog(u'全部撤单')        
        
        
    
        
        
    
    
    
        
        
    
    