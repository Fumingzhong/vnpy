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
    
    tradeTimeFileName = 'TradeTime.json'            # 所有品种交易时间
    tradeTimeFilePath = getJsonPath(tradeTimeFileName, __file__)

    #----------------------------------------------------------------------
    def __init__(self, algoEngine, multi):
        """Constructor"""
        self.algoEngine = algoEngine                # 算法引擎
        self.multiName = multi.name                 # 组合名称
        self.multi = multi                          # 组合对象
        
        self.algoName = EMPTY_STRING                # 算法名称
        self.active = False                         # 工作状态
        
        self.maxPosSize = EMPTY_INT                 # 最大单边持仓         # 未用到
        self.maxOrderSize = EMPTY_INT               # 最大单笔委托量       # 未用到
        
        #如果有文件则加载文件中的参数，无的话则在策略中输入
        try:
            self.algoParamsDict = self.loadAlgoSetting()
        except:
            self.writeLog(u'策略参数在类内赋值')
        # 算法参数初始化
        __d = self.__dict__
        if not self.algoParamsDict:
            pass
        else:
            for (k,v) in self.algoParamsDict.items():
                __d[k] = v
            
            self.__dict__ = __d
            
        # 获得主动腿和被动腿的交易时间段
        self.activeTradeTime, self.passiveTradeTime = self.getMultiTradePeriods()
            
    #----------------------------------------------------------------------
    def getMultiTradePeriods(self):
        """获得腿的交易时间段"""
        # 初始化交易时间段
        activeTradeTime = []
        passiveTradeTime = []
        
        multi = self.multi
        activeLeg = multi.activeLeg
        passiveLeg = multi.passiveLegs[0]
        
        activeVtSymbol = activeLeg.vtSymbol 
        passiveVtSymbol = passiveLeg.vtSymbol
        
        activeProduct = ZfmFunctions().filterNumStr(activeVtSymbol).lower()
        passiveProduct = ZfmFunctions().filterNumStr(passiveVtSymbol).lower()
        # 读取交易时间段配置文件
        try:
            with open(self.tradeTimeFilePath) as f:
                l = json.load(f)
                if not l:
                    self.writeLog(u'交易时间文件内容为空')
                else:
                    for key in l.keys():
                        tempDict = l[key]
                        tempProducts = tempDict['products']
                        tempProducts = [x.lower() for x in tempProducts]
                        if activeProduct in tempProducts:
                            activeTradeTime = tempDict['timePeriods']
                            
                        if passiveProduct in tempProducts:
                            passiveTradeTime = tempDict['timePeriods']
        except:
            content = u'交易时间文件配置加载出错，原因：' + traceback.format_exc()
            self.writeLog(content)    
        
        return activeTradeTime, passiveTradeTime
                    
                
        
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
        prefix = ''.join([self.multiName, self.algoName])
        content = ':'.join([prefix, content])
        self.algoEngine.writeLog(content)
        
    #----------------------------------------------------------------------
    def getAlgoParams(self):
        """获得算法参数"""
        d = self.algoParamsDict
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
        
        self.activeTaskDict = {}                                    # 主动腿需要下单的数量字典  vtSymbol:volume    # 未用到
        self.hedgingTaskDict = {}                                   # 被动腿需要对冲的数量字典  vtSymbol:volume    # 未用到
        self.legOrderDict = {}                                      # vtSymbol: list of vtOrderID
        self.orderTradeDict = {}                                    # vtOrderID: tradedVolume 
        
        # 加载策略参数
        self.d = self.algoParamsDict
        
        self.K = self.d['K']
        self.r = self.d['r']
        self.endDate = self.d['endDate']
        self.startDate = date.today().strftime('%Y-%m-%d')
        self.T = len(ZfmFunctions().getTradeDays(self.startDate, self.endDate))   # 在spreadOption中年化
        self.sigma1 = self.d['sigma1']
        self.sigma2 = self.d['sigma2']
        self.rho = self.d['rho']
        self.cp = self.d['cp']
        self.amount = self.d['amount']
        self.bandWidth = self.d['bandWidth']
        self.ratio = self.d['ratio']
        
        # 加载合约信息
        self.activeLeg = multi.activeLeg
        self.passiveLeg = multi.passiveLegs[0]
        
        self.contract1 = self.algoEngine.mainEngine.getContract(self.activeLeg.vtSymbol)
        self.contract2 = self.algoEngine.mainEngine.getContract(self.passiveLeg.vtSymbol)
        
        
    #----------------------------------------------------------------------
    def updateMultiTick(self, multi):
        """组合行情更新"""
        self.multi = multi
        isPosChecked = self.algoEngine.mainEngine.getGateway(self.contract1.gatewayName).tdApi.isPosChecked
        
        # 若算法没有启动则直接返回
        if not self.active:
            return
        
        # 若当前已有主动腿委托则直接返回
        if (self.activeVtSymbol in self.legOrderDict and
            self.legOrderDict[self.activeVtSymbol]):
            return
        
        # 若当前已有被动腿委托则直接返回
        passiveVtSymbol = self.multi.passiveLegs[0].vtSymbol
        if (passiveVtSymbol in self.legOrderDict and
            self.legOrderDict[passiveVtSymbol]):
            return    
        
        if not isPosChecked:
            return
        activeLeg = multi.activeLeg
        passiveLeg = multi.passiveLegs[0] 
        
        # 处理tick中tickstart与tickend之间仍有成交的情况
        if multi.time[:-4] > '14:59:00' and multi.time[:-4] <= '14:59:30':
            self.cancelLegOrder(activeLeg.vtSymbol)
            self.cancelLegOrder(passiveLeg.vtSymbol)
            return        
        
        s1 = activeLeg.bidPrice 
        s2 = passiveLeg.bidPrice * self.ratio
        
        # 获得腿的净持仓
        netPos1 = activeLeg.netPos
        netPos2 = passiveLeg.netPos
        
        spreadCalculator = KirkMethod(s1, s2, self.K, self.r, self.T, self.sigma1, self.sigma2, self.rho, self.cp)
        delta1, delta2 = spreadCalculator.OptionDelta()
        gamma1, gamma2 = spreadCalculator.OptionGamma()
        
        if self.direction == 'short':
            delta1 = -delta1
            delta2 = -delta2
        else:
            pass
        
        ## 计算调仓的gamma最小值手数
        #minGamma1 = int(round(gamma1 * s1 * amount/contract1.size,0))
        #minGamma2 = int(round(gamma2 * s2 * amount/contract2.size,0))
        
        ## 计算总的手数
        #nUnit1 = int(round(amount/contract1.size,0))
        #nUnit2 = int(round(amount/contract2.size,0))
        
        # 计算应建仓数量
        newNetPos1 = int(round(delta1 * self.amount / self.contract1.size, 0)) 
        newNetPos2 = int(round(delta2 * self.amount * self.ratio / self.contract2.size, 0))
        print 'tick事件----'+activeLeg.vtSymbol+u'现仓1:'+str(netPos1)+u'现仓2:'+str(netPos2)+u'新仓1应为：'+str(newNetPos1)+u'新仓2应为:'+str(newNetPos2)  
        print 'tick事件----'+str(delta1)+activeLeg.vtSymbol, str(delta2)+passiveLeg.vtSymbol
        
        # 计算主动腿和被动腿委托量
        activeAdjustVolume = newNetPos1 - netPos1
        passiveAdjustVolume = newNetPos2 - netPos2
        
        # 主动腿下单参数
        activeVtSymbol = activeLeg.vtSymbol
        activeDirection = EMPTY_STRING
        activeOffset = EMPTY_STRING
        activePrice = EMPTY_FLOAT
        
        if activeAdjustVolume > 0 and abs(activeAdjustVolume) > self.bandWidth * abs(netPos1):
            activeDirection = DIRECTION_LONG
            activePrice = activeLeg.askPrice + activeLeg.payup * self.contract1.priceTick
        elif activeAdjustVolume < 0 and abs(activeAdjustVolume) > self.bandWidth * abs(netPos1):
            activeDirection = DIRECTION_SHORT
            activePrice = activeLeg.bidPrice  - activeLeg.payup * self.contract1.priceTick
            
            
        activeOffsetList, activeVolumeList = self.calculateOffsetAndVolume(activeAdjustVolume, newNetPos1, netPos1)
            
        # 排除不需要调仓的情况
        if not activePrice:
            pass
        else:
            for i in range(len(activeOffsetList)):
                activeOffset = activeOffsetList[i]
                activeVolume = activeVolumeList[i]
                print activeVtSymbol, activeDirection, activeOffset, activePrice, activeVolume
                self.sendLegOrder(activeVtSymbol, activeDirection, activeOffset, activePrice, 
                                 activeVolume)
            
        # 被动腿下单参数
        passiveVtSymbol = passiveLeg.vtSymbol
        passiveDirection = EMPTY_STRING
        passiveOffset = EMPTY_STRING
        passivePrice = EMPTY_FLOAT
        
        if passiveAdjustVolume > 0 and abs(passiveAdjustVolume) > self.bandWidth * abs(netPos2):
            passiveDirection = DIRECTION_LONG
            passivePrice = passiveLeg.askPrice + passiveLeg.payup * self.contract2.priceTick
        elif passiveAdjustVolume < 0 and abs(passiveAdjustVolume) > self.bandWidth * abs(netPos2):
            passiveDirection = DIRECTION_SHORT
            passivePrice = passiveLeg.bidPrice - passiveLeg.payup * self.contract2.priceTick
            
        passiveOffsetList, passiveVolumeList = self.calculateOffsetAndVolume(passiveAdjustVolume, newNetPos2, netPos2)
        
        if not passivePrice:
            pass
        else:
            for i in range(len(passiveOffsetList)):
                passiveOffset = passiveOffsetList[i]
                passiveVolume = passiveVolumeList[i]
                print passiveVtSymbol, passiveDirection, passiveOffset, passivePrice, passiveVolume
                self.sendLegOrder(passiveVtSymbol, passiveDirection, passiveOffset, passivePrice, 
                                 passiveVolume)
    
    #----------------------------------------------------------------------
    def calculateOffsetAndVolume(self, adjustVolume, newPos, pos):
        """计算下单方向和量"""
        offsetList = []
        volumeList = []
        
        prod = newPos * pos
        if not adjustVolume:
            pass
        else:
            if prod > 0:
                if abs(newPos) > abs(pos):
                    tempOffset = OFFSET_OPEN
                    tempVolume = abs(adjustVolume)
                else:
                    tempOffset = OFFSET_CLOSE
                    tempVolume = abs(adjustVolume)
                offsetList.append(tempOffset)
                volumeList.append(tempVolume)
            elif prod < 0:
                tempOffsetList = [OFFSET_CLOSE, OFFSET_OPEN]
                tempVolumeList = [abs(pos), abs(newPos)]
                offsetList.extend(tempOffsetList)
                volumeList.extend(tempVolumeList)
            else:
                if not pos:
                    tempOffset = OFFSET_OPEN
                    tempVolume = abs(newPos)
                else:
                    tempOffset = OFFSET_CLOSE
                    tempVolume = abs(pos)
                    
                offsetList.append(tempOffset)
                volumeList.append(tempVolume)   
        
        return offsetList, volumeList
                            
    #----------------------------------------------------------------------
    def updateMultiPos(self, multi):
        """价差持仓更新"""
        self.multi = multi
        # 若算法没有启动则直接返回
        if not self.active:
            return
        
        # 若当前已有主动腿委托则直接返回
        if (self.activeVtSymbol in self.legOrderDict and
            self.legOrderDict[self.activeVtSymbol]):
            return
        
        # 若当前已有被动腿委托则直接返回
        passiveVtSymbol = self.multi.passiveLegs[0].vtSymbol
        if (passiveVtSymbol in self.legOrderDict and
            self.legOrderDict[passiveVtSymbol]):
            return    
        
        activeLeg = multi.activeLeg
        passiveLeg = multi.passiveLegs[0] 
        
        if not activeLeg.bidPrice or not activeLeg.askPrice or not passiveLeg.bidPrice or not passiveLeg.askPrice:
            return
        
        # 处理tick中tickstart与tickend之间仍有成交的情况
        if multi.time[:-4] > '14:59:00' and multi.time[:-4] <= '14:59:30':
            self.cancelLegOrder(activeLeg.vtSymbol)
            self.cancelLegOrder(passiveLeg.vtSymbol)
            return        
        
        
        s1 = activeLeg.bidPrice 
        s2 = passiveLeg.bidPrice * self.ratio
                
        # 获得腿的净持仓
        netPos1 = activeLeg.netPos
        netPos2 = passiveLeg.netPos
        
        spreadCalculator = KirkMethod(s1, s2, self.K, self.r, self.T, self.sigma1, self.sigma2, self.rho, self.cp)
        delta1, delta2 = spreadCalculator.OptionDelta()
        gamma1, gamma2 = spreadCalculator.OptionGamma()       
        
        if self.direction == 'short':
            delta1 = -delta1
            delta2 = -delta2
        else:
            pass
        
        
        ## 计算调仓的gamma最小值手数
        #minGamma1 = int(round(gamma1 * s1 * amount/contract1.size,0))
        #minGamma2 = int(round(gamma2 * s2 * amount/contract2.size,0))
        
        ## 计算总的手数
        #nUnit1 = int(round(amount/contract1.size,0))
        #nUnit2 = int(round(amount/contract2.size,0))
        
        # 计算应建仓数量
        newNetPos1 = int(round(delta1 * self.amount / self.contract1.size, 0)) 
        newNetPos2 = int(round(delta2 * self.amount * self.ratio / self.contract2.size, 0))
        optionParams = [s1, s2, self.K, self.r, self.T, self.sigma1, self.sigma2, self.rho, self.cp]
        f = lambda x:[str(y) for y in x]
        paramsStr = '--'.join(f(optionParams))
        print 'pos事件----'+u'期权参数'+paramsStr
        print 'pos事件----'+activeLeg.vtSymbol+u'现仓1:'+str(netPos1)+u'现仓2:'+str(netPos2)+u'新仓1应为：'+str(newNetPos1)+u'新仓2应为:'+str(newNetPos2)  
        print 'pos事件----'+str(delta1)+activeLeg.vtSymbol, str(delta2)+passiveLeg.vtSymbol         
        
        # 计算主动腿和被动腿委托量
        activeAdjustVolume = newNetPos1 - netPos1
        passiveAdjustVolume = newNetPos2 - netPos2
        
        # 主动腿下单参数
        activeVtSymbol = activeLeg.vtSymbol
        activeDirection = EMPTY_STRING
        activeOffset = EMPTY_STRING
        activePrice = EMPTY_FLOAT
        
        if activeAdjustVolume > 0 and abs(activeAdjustVolume) > self.bandWidth * abs(netPos1):
            activeDirection = DIRECTION_LONG
            activePrice = activeLeg.askPrice + activeLeg.payup * self.contract1.priceTick
        elif activeAdjustVolume < 0 and abs(activeAdjustVolume) > self.bandWidth * abs(netPos1):
            activeDirection = DIRECTION_SHORT
            activePrice = activeLeg.bidPrice  - activeLeg.payup * self.contract1.priceTick
            
        activeOffsetList, activeVolumeList = self.calculateOffsetAndVolume(activeAdjustVolume, newNetPos1, netPos1)            
            
        # 排除不需要调仓的情况
        if not activePrice:
            pass
        else:
            for i in range(len(activeOffsetList)):
                activeOffset = activeOffsetList[i]
                activeVolume = activeVolumeList[i]
                print activeVtSymbol, activeDirection, activeOffset, activePrice, activeVolume
                self.sendLegOrder(activeVtSymbol, activeDirection, activeOffset, activePrice, 
                                 activeVolume)
            
        # 被动腿下单参数
        passiveVtSymbol = passiveLeg.vtSymbol
        passiveDirection = EMPTY_STRING
        passiveOffset = EMPTY_STRING
        passivePrice = EMPTY_FLOAT
        
        if passiveAdjustVolume > 0 and abs(passiveAdjustVolume) > self.bandWidth * abs(netPos2):
            passiveDirection = DIRECTION_LONG
            passivePrice = passiveLeg.askPrice + passiveLeg.payup * self.contract2.priceTick
        elif passiveAdjustVolume < 0 and abs(passiveAdjustVolume) > self.bandWidth * abs(netPos2):
            passiveDirection = DIRECTION_SHORT
            passivePrice = passiveLeg.bidPrice - passiveLeg.payup * self.contract2.priceTick
            
        passiveOffsetList, passiveVolumeList = self.calculateOffsetAndVolume(passiveAdjustVolume, newNetPos2, netPos2)        
        if not passivePrice:
            pass
        else:
            for i in range(len(passiveOffsetList)):
                passiveOffset = passiveOffsetList[i]
                passiveVolume = passiveVolumeList[i]
                print passiveVtSymbol, passiveDirection, passiveOffset, passivePrice, passiveVolume
                self.sendLegOrder(passiveVtSymbol, passiveDirection, passiveOffset, passivePrice, 
                                 passiveVolume)   
        
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
        if order.status == STATUS_CANCELLED:
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
            
            print legVtSymbol, legDirection, legOffset, legPrice, legVolume
            if order.cancelTime:
                nowStr = order.cancelTime
            else:
                nowStr = datetime.now().strftime('%H:%M:%S')
            
            
            isClosed = True
            if vtSymbol == self.activeVtSymbol:
                for tradePeriod in self.activeTradeTime:
                    if nowStr >= tradePeriod[0] and nowStr <= tradePeriod[1]:
                        isClosed = False
                        print 'it is not the trade time of ' + vtSymbol 
                        break
            else:
                for tradePeriod in self.passiveTradeTime:
                    if nowStr >= tradePeriod[0] and nowStr <= tradePeriod[1]:
                        isClosed = False
                        print 'it is not the trade time of ' + vtSymbol 
                        break                    
            # 是否休盘
            if isClosed:
                return
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
        self.writeLog(self.multiName+':'+u'算法停止')
        
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
        
        
    
        
        
    
    
    
        
        
    
    