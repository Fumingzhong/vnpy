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
from datetime import date,datetime
sys.path.append(r'C:\boSpreadArbitrage')
from dataEngine import windDataEngine 
from collections import OrderedDict 

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
                print self.algoParamsDict
                if not self.algoParamsDict and l:
                    self.writeLog(u'文件无对应组合参数配置')
                elif not l:
                    self.writeLog(u'文件内容为空')
                else:
                    self.writeLog(u'组合参数配置加载完成')
        except:
            content = u'组合参数配置加载出错，原因：' + traceback.format_exc()
            print content
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
        self.direction = self.d['direction']
        self.amount = self.d['amount']
        self.bandWidth = self.d['bandWidth']
        self.ratio = self.d['ratio']
        self.isFixed = self.d['isFixed']
        self.volDays = self.d['volDays']
        self.hlDays = self.d['hlDays']
        
        # 加载合约信息
        self.activeLeg = multi.activeLeg
        self.passiveLeg = multi.passiveLegs[0]
        
        self.contract1 = self.algoEngine.mainEngine.getContract(self.activeLeg.vtSymbol)
        self.contract2 = self.algoEngine.mainEngine.getContract(self.passiveLeg.vtSymbol)
        
        # 缓存上次成交的价差以及腿价格
        self.lastSpreadPrice = EMPTY_FLOAT   
        self.lastActiveOrderPrice = EMPTY_FLOAT
        self.lastPassiveOrderPrice = EMPTY_FLOAT
        
        # 由收到行情后进行计算
        if not self.isFixed:
            self.wDataEngine = windDataEngine()
            #self.endDate = EMPTY_STRING 
            self.sigma1 = self.getSigma(self.activeLeg.vtSymbol, self.volDays)
            self.sigma2 = self.getSigma(self.passiveLeg.vtSymbol, self.volDays) 
            self.amount = self.contract1.size * 10
            
            paramDict = {}
            activeProduct = ZfmFunctions().filterNumStr(self.contract1.symbol)
            passiveProduct = ZfmFunctions().filterNumStr(self.contract2.symbol)
            activeExchange = self.wDataEngine.getExchangeCode(activeProduct)
            passiveExchange = self.wDataEngine.getExchangeCode(passiveProduct)
            activeCode = '.'.join([self.contract1.symbol, activeExchange])
            passiveCode = '.'.join([self.contract2.symbol, passiveExchange])            
            paramDict['contractPair'] = [activeCode, passiveCode]
            paramDict['field'] = 'high,low,open,close'
            
            endDay = date.today().strftime('%Y-%m-%d')
            startDay = self.wDataEngine.w.tdaysoffset(-self.hlDays, endDay, 'Days=Trading').Data[0][0]
            startDay = startDay.strftime('%Y-%m-%d')
            startTime = startDay + ' 21:00:00'
            endTime = endDay + ' 15:15:00'  # 由于万德数据必须取到15分钟才能取到最后一根数据    
            
            paramDict['startTime'] = startTime
            paramDict['endTime'] = endTime
            paramDict['barSize'] = 15
            paramDict['productPair'] = [activeProduct, passiveProduct]
            paramDict['filePath'] = getJsonPath('TradeTime.json', __file__)
            paramDict['pairRatio'] = [1, -1]
            paramDict['formKey'] = multi.name
            
            self.high, self.low = self.getHighLow(paramDict)  
            self.rho = self.getRho(paramDict)
            print self.sigma1, self.sigma2, self.high, self.low, self.rho
    
    #----------------------------------------------------------------------
    def saveAlgoParamDict(self):
        """保存算法的参数"""
        K = self.K
        r = self.r
        endDate = self.endDate
        sigma1 = self.sigma1
        sigma2 = self.sigma2
        rho = self.rho
        cp = self.cp
        direction = self.direction
        amount = self.amount
        bandWidth = self.bandWidth
        ratio = self.ratio
        isFixed = self.isFixed
        volDays = self.volDays
        hlDays = self.hlDays
        
        paramDict = {}
        paramDict['K'] = K
        paramDict['r'] = r
        paramDict['endDate'] = endDate
        paramDict['sigma1'] = sigma1
        paramDict['sigma2'] = sigma2
        paramDict['rho'] = rho
        paramDict['cp'] = cp
        paramDict['direction'] = direction
        paramDict['amount'] = amount
        paramDict['bandWidth'] = bandWidth
        paramDict['ratio'] = ratio
        paramDict['isFixed'] = isFixed
        paramDict['volDays'] = volDays
        paramDict['hlDays'] = hlDays
        
        paramKey = self.multi.name
        
        ud = {paramKey: paramDict}
        
        # 打开原有文件
        with open(self.algoParamsFilePath) as f:
            d = json.load(f, 
                         object_pairs_hook=OrderedDict)
            f.close()
            
        # 更新后保存
        with open(self.algoParamsFilePath, mode='w') as f:
            d.update(ud)
            json.dump(d, f, 
                     indent=4)
            f.close()
        
        
            
    #----------------------------------------------------------------------
    def getSigma(self, symbol, volDays):
        """获得标的的历史波动率"""
        if '.' not in symbol:
            product = ZfmFunctions().filterNumStr(symbol)
            exchangeCode = self.wDataEngine.getExchangeCode(product)
            symbol = symbol + '.' + exchangeCode
        RSHisVol = self.wDataEngine.getRSHisVol(symbol, volDays, barSize=15, filePath='TradeTime.json')
        return RSHisVol
    
    #----------------------------------------------------------------------
    def getHighLow(self, paramDict):
        """获得价差的历史高点和低点"""
        highDict, lowDict = self.wDataEngine.getSpreadHighLow(paramDict)
        
        return highDict.values()[0][1], lowDict.values()[0][1]       
    
    #----------------------------------------------------------------------
    def getRho(self, paramDict):
        """获得相关性"""
        rho = self.wDataEngine.getSpreadRho(paramDict)
        
        return rho
        
    #----------------------------------------------------------------------
    def updateMultiTick(self, multi):
        """组合行情更新"""
        #print 'getTick'
        self.multi = multi
        isPosChecked = self.algoEngine.mainEngine.getGateway(self.contract1.gatewayName).tdApi.isPosChecked
        
        # 同时下单算套利单
        isSendActive = False
        isSendPassive = False        
        
        # 若算法没有启动则直接返回
        if not self.active:
            return  
        
        if not isPosChecked:
            return        
        # 到期直接返回，在持仓事件中平仓
        if not self.T:
            return        
        
        # 若当前已有主动腿委托则直接返回
        if (self.activeVtSymbol in self.legOrderDict and
            self.legOrderDict[self.activeVtSymbol]):
            self.cancelLegOrder(self.activeVtSymbol)
            return
        
        # 若当前已有被动腿委托则直接返回
        passiveVtSymbol = self.multi.passiveLegs[0].vtSymbol
        if (passiveVtSymbol in self.legOrderDict and
            self.legOrderDict[passiveVtSymbol]):
            self.cancelLegOrder(passiveVtSymbol)
            return    
    
        activeLeg = multi.activeLeg
        passiveLeg = multi.passiveLegs[0] 
        
        # 处理tick中tickstart与tickend之间仍有成交的情况
        if multi.time[:-4] > '14:59:00' and multi.time[:-4] <= '14:59:30':
            self.cancelLegOrder(activeLeg.vtSymbol)
            self.cancelLegOrder(passiveLeg.vtSymbol)
            return        
        
        priceTick1 = self.contract1.priceTick
        priceTick2 = self.contract2.priceTick
        s1 = self.roundToPriceTick(priceTick1, (activeLeg.bidPrice + activeLeg.askPrice)/2)
        s2 = self.roundToPriceTick(priceTick2, (passiveLeg.bidPrice * self.ratio + passiveLeg.askPrice * self.ratio)/2)
        
        # 控制价差下单范围
        lastSpreadPrice = self.lastSpreadPrice
        newSpreadPrice = s1 - self.ratio * s2
        
        if abs(newSpreadPrice - lastSpreadPrice) <= self.contract1.priceTick * activeLeg.payup:
            return
        
        if not self.isFixed:
            
            # 无法计算波动率以及相关性时 不做调仓
            if not self.sigma1 or not self.sigma2 or not self.rho:
                print 'sigma or rho does not exist!'
                return   
            
            self.direction = DIRECTION_SHORT
            
            # 缓存之前的期权类型
            lastCp = self.cp
            
            if self.high or (self.high == 0):
                if newSpreadPrice > self.high:
                    # K值第一次赋值
                    if not self.K and self.K != 0:
                        self.K = newSpreadPrice
                        self.cp = -1
                    # 突破方向改变
                    elif self.K and lastCp == 1:
                        self.K = newSpreadPrice
                        self.cp = -1
                        
            if self.low or (self.low == 0):           
                if newSpreadPrice < self.low:
                    # K值第一次赋值
                    if not self.K and self.K != 0:
                        self.K = newSpreadPrice
                        self.cp = 1
                    # 突破方向发生改变
                    elif self.K and lastCp == -1:
                        self.K = newSpreadPrice
                        self.cp = 1
            # K为空值
            if not self.K and self.K != 0:
                return
                
        
        # 获得腿的净持仓
        netPos1 = activeLeg.netPos
        netPos2 = passiveLeg.netPos
        
        spreadCalculator = KirkMethod(s1, s2, self.K, self.r, self.T, self.sigma1, self.sigma2, self.rho, self.cp)
        delta1, delta2 = spreadCalculator.OptionDelta()
        gamma1, gamma2 = spreadCalculator.OptionGamma()
        
        if self.direction == DIRECTION_SHORT:
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
        # 控制单腿下单价格范围
        elif abs(activePrice - self.lastActiveOrderPrice) <= activeLeg.payup * self.contract1.priceTick:
            pass
        else:
            for i in range(len(activeOffsetList)):
                activeOffset = activeOffsetList[i]
                activeVolume = activeVolumeList[i]
                print activeVtSymbol, activeDirection, activeOffset, activePrice, activeVolume
                self.sendLegOrder(activeVtSymbol, activeDirection, activeOffset, activePrice, 
                                 activeVolume)
                isSendActive = True
            
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
        elif abs(passivePrice - self.lastPassiveOrderPrice) <= passiveLeg.payup * self.contract2.priceTick:
            pass
        else:
            for i in range(len(passiveOffsetList)):
                passiveOffset = passiveOffsetList[i]
                passiveVolume = passiveVolumeList[i]
                print passiveVtSymbol, passiveDirection, passiveOffset, passivePrice, passiveVolume
                self.sendLegOrder(passiveVtSymbol, passiveDirection, passiveOffset, passivePrice, 
                                 passiveVolume)
                isSendPassive = True
                
        if isSendActive and isSendPassive:
            self.lastSpreadPrice = newSpreadPrice
            
        if isSendActive and not isSendPassive:
            self.lastActiveOrderPrice = s1
            
        if isSendPassive and not isSendActive:
            self.lastPassiveOrderPrice = s2        
        
    
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
        #print 'getPos'
        self.multi = multi
        
        activeLeg = multi.activeLeg
        passiveLeg = multi.passiveLegs[0] 
        
        # 同时下单算套利单
        isSendActive = False
        isSendPassive = False
        
        if not activeLeg.bidPrice or not activeLeg.askPrice or not passiveLeg.bidPrice or not passiveLeg.askPrice:
            return        
        
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
        # 到期平仓
        if not self.T or (self.K != 0 and not self.K):
            activePos = activeLeg.netPos
            passivePos = passiveLeg.netPos
            activeVtSymbol = activeLeg.vtSymbol
            passiveVtSymbol = passiveLeg.vtSymbol
            activePrice = self.roundToPriceTick(self.contract1.priceTick, (activeLeg.bidPrice + activeLeg.askPrice)/2)
            passivePrice = self.roundToPriceTick(self.contract2.priceTick, (passiveLeg.bidPrice + passiveLeg.askPrice)/2)
            if activePos < 0:
                activeDirection = DIRECTION_LONG
                activePrice = activePrice + activeLeg.payup * self.contract1.priceTick
            elif activePos > 0:
                activeDirection = DIRECTION_SHORT
                activePrice = activePrice - activeLeg.payup * self.contract1.priceTick
                
            if passivePos < 0:
                passiveDirection = DIRECTION_LONG
                passivePrice = passivePrice + passiveLeg.payup * self.contract2.priceTick
            elif passivePos > 0:
                passiveDirection = DIRECTION_SHORT
                passivePrice = passivePrice - passiveLeg.payup * self.contract2.priceTick
            
            if activePos:
                self.sendLegOrder(activeVtSymbol, activeDirection, OFFSET_CLOSE, 
                                 activePrice, 
                                 abs(activePos))
                
            if passivePos:
                self.sendLegOrder(passiveVtSymbol, passiveDirection, OFFSET_CLOSE, 
                                 passivePrice, 
                                 abs(passivePos))
            return 
        
        # 处理tick中tickstart与tickend之间仍有成交的情况
        if multi.time[:-4] > '14:59:00' and multi.time[:-4] <= '14:59:30':
            self.cancelLegOrder(activeLeg.vtSymbol)
            self.cancelLegOrder(passiveLeg.vtSymbol)
            return        
        # 执行价格为空，不做处理
        if self.K != 0 and not self.K:
            return
        priceTick1 = self.contract1.priceTick
        priceTick2 = self.contract2.priceTick
        s1 = self.roundToPriceTick(priceTick1, (activeLeg.bidPrice + activeLeg.askPrice)/2)
        s2 = self.roundToPriceTick(priceTick2, (passiveLeg.bidPrice * self.ratio + passiveLeg.askPrice * self.ratio)/2)
        
        # 同价差不刷单
        lastSpreadPrice = self.lastSpreadPrice
        newSpreadPrice = s1 - self.ratio * s2
        
        if abs(newSpreadPrice - lastSpreadPrice) <= self.contract1.priceTick * activeLeg.payup:
            return        
                
        # 获得腿的净持仓
        netPos1 = activeLeg.netPos
        netPos2 = passiveLeg.netPos
        
        spreadCalculator = KirkMethod(s1, s2, self.K, self.r, self.T, self.sigma1, self.sigma2, self.rho, self.cp)
        delta1, delta2 = spreadCalculator.OptionDelta()
        gamma1, gamma2 = spreadCalculator.OptionGamma()       
        
        if self.direction == DIRECTION_SHORT:
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
        # 控制单腿下单价格范围
        elif abs(activePrice - self.lastActiveOrderPrice) <= activeLeg.payup * self.contract1.priceTick:
            pass        
        else:
            for i in range(len(activeOffsetList)):
                activeOffset = activeOffsetList[i]
                activeVolume = activeVolumeList[i]
                print activeVtSymbol, activeDirection, activeOffset, activePrice, activeVolume
                self.sendLegOrder(activeVtSymbol, activeDirection, activeOffset, activePrice, 
                                 activeVolume)
                isSendActive = True
            
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
        elif abs(passivePrice - self.lastPassiveOrderPrice) <= passiveLeg.payup * self.contract2.priceTick:
            pass        
        else:
            for i in range(len(passiveOffsetList)):
                passiveOffset = passiveOffsetList[i]
                passiveVolume = passiveVolumeList[i]
                print passiveVtSymbol, passiveDirection, passiveOffset, passivePrice, passiveVolume
                self.sendLegOrder(passiveVtSymbol, passiveDirection, passiveOffset, passivePrice, 
                                 passiveVolume)  
                isSendPassive = True
                
        if isSendActive and isSendPassive:
            self.lastSpreadPrice = newSpreadPrice
            
        if isSendActive and not isSendPassive:
            self.lastActiveOrderPrice = s1
            
        if isSendPassive and not isSendActive:
            self.lastPassiveOrderPrice = s2
            
        
        
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
            if order.tradedVolume:    
                legVolume = order.totalVolume - order.tradedVolume
            else:
                legVolume = order.totalVolume
            
            # 报单量为0退出    
            if not legVolume or not leg.bidVolume or not leg.askVolume:
                return
            
            # 涨停或者跌停单撤销
            if not leg.bidVolume and legDirection == DIRECTION_LONG:
                return
            
            if not leg.askVolume and legDirection == DIRECTION_SHORT:
                return
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
                        break 
            else:
                for tradePeriod in self.passiveTradeTime:
                    if nowStr >= tradePeriod[0] and nowStr <= tradePeriod[1]:
                        isClosed = False
                        break                  
            # 是否休盘
            if isClosed:
                print 'it is not the trade time of ' + vtSymbol + 'nowStr:' + nowStr + 'periodStart:'+tradePeriod[0] + 'periodEnd:' + tradePeriod[1] 
                return

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
        self.saveAlgoParamDict()
        
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
        
    #----------------------------------------------------------------------
    def roundToPriceTick(self, priceTick, price):
        """取整价格到合约最小价格变动"""
        if not priceTick:
            return price
        
        newPrice = round(price/priceTick, 0) * priceTick
        return newPrice        
        
        
    
        
        
    
    
    
        
        
    
    