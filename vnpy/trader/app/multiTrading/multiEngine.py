# encoding: UTF-8

import json
import traceback
import shelve
from collections import OrderedDict
from datetime import datetime

from vnpy.event import Event
from vnpy.trader.vtFunction import getJsonPath, getTempPath
from vnpy.trader.vtEvent import (EVENT_TICK, EVENT_TRADE, EVENT_POSITION, 
                                 EVENT_TIMER, EVENT_ORDER)
from vnpy.trader.vtObject import (VtSubscribeReq, VtOrderReq, 
                                  VtCancelOrderReq, VtLogData)
from vnpy.trader.vtConstant import (DIRECTION_LONG, DIRECTION_SHORT, 
                                    OFFSET_OPEN, OFFSET_CLOSE, 
                                    PRICETYPE_LIMITPRICE)

from .multiBase import (MultiLeg, MultiMulti, EVENT_MULTITRADING_TICK,
                        EVENT_MULTITRADING_POS, EVENT_MULTITRADING_LOG,
                        EVENT_MULTITRADING_ALGO, EVENT_MULTITRADING_ALGOLOG)
from .multiAlgo import SpreadOptionAlgo 

EVENT_MULTITRADING_STOP = 'eMultiTradingStop'

########################################################################
class MultiDataEngine(object):
    """多标的数据计算引擎"""
    settingFileName = 'Multi_setting.json'
    settingFilePath = getJsonPath(settingFileName, __file__)

    #----------------------------------------------------------------------
    def __init__(self, mainEngine, eventEngine):
        """Constructor"""
        self.mainEngine = mainEngine
        self.eventEngine = eventEngine
        
        # 腿、价差相关字典
        self.legDict = {}                   # vtSymbol:StLeg
        self.multiDict = {}                 # name:MultiMulti
        self.vtSymbolMultiDict = {}         # vtSymbol:MultiMulti
        
        self.registerEvent()
        
    #----------------------------------------------------------------------
    def loadSetting(self):
        """加载配置"""
        try:
            with open(self.settingFilePath) as f:
                l = json.load(f)
                
                for setting in l:
                    result, msg = self.createMulti(setting)
                    self.writeLog(msg)
                self.writeLog(u'组合配置加载完成')
        except:
            content = u'组合配置加载出错，原因：' + traceback.format_exc()
            self.writeLog(content)
            
    #----------------------------------------------------------------------
    def saveSetting(self):
        """保存配置"""
        with open(self.settingFilePath) as f:
            pass
        
    #----------------------------------------------------------------------
    def createMulti(self, setting):
        """创建多标的组合"""
        result = False
        msg = ''
        
        # 检查价差重名
        if setting['name'] in self.multiDict:
            msg = u'%s组合存在重名' %setting['name']
            return result, msg
        
        # 检查腿是否已使用
        l = []
        l.append(setting['activeLeg']['vtSymbol'])
        for d in setting['passiveLegs']:
            l.append(d['vtSymbol'])
            
        for vtSymbol in l:
            if vtSymbol in self.vtSymbolMultiDict:
                existingMulti = self.vtSymbolMultiDict[vtSymbol]
                msg = u'%s合约已经存在于%s价差中' 
                return result, msg
        
        # 创建组合
        multi = MultiMulti()
        multi.name = setting['name']
        self.multiDict[multi.name] = multi
        
        #创建主动腿
        activeSetting = setting['activeLeg']
        
        activeLeg = MultiLeg()
        activeLeg.vtSymbol = activeSetting['vtSymbol']
        activeLeg.ratio = activeSetting['ratio']
        activeLeg.multiplier = activeSetting['multiplier']
        activeLeg.payup = activeSetting['payup']
        
        multi.addActiveLeg(activeLeg) 
        self.legDict[activeLeg.vtSymbol] = activeLeg
        self.vtSymbolMultiDict[activeLeg.vtSymbol] = multi
        
        self.subscribeMarketData(activeLeg.vtSymbol)
        
        # 创建被动腿
        passiveSettingList = setting['passiveLegs']
        
        for d in passiveSettingList:
            passiveLeg = MultiLeg()
            passiveLeg.vtSymbol = d['vtSymbol']
            passiveLeg.ratio = d['ratio']
            passiveLeg.multiplier = d['multiplier']
            passiveLeg.payup = d['payup']
            
            multi.addPassiveLeg(passiveLeg)
            self.legDict[passiveLeg.vtSymbol] = passiveLeg
            self.vtSymbolMultiDict[passiveLeg.vtSymbol] = multi
            
            self.subscribeMarketData(passiveLeg.vtSymbol)
        
        # 初始化组合价格
        multi.initMulti()
        
        self.putMultiTickEvent(multi)
        self.putMultiPosEvent(multi)                    #不适用
        
        #返回结果
        result = True
        msg = u'%s组合创建成功' %multi.name
        return result, msg
    
    #----------------------------------------------------------------------
    def processTickEvent(self, event):
        """处理行情推送"""
        # 检查行情是否需要处理
        tick = event.dict_['data']
        print 'process tickEvent'
        if tick.vtSymbol not in self.legDict:
            return
        
        # 更新腿价格
        leg = self.legDict[tick.vtSymbol]
        leg.bidPrice = tick.bidPrice1
        leg.askPrice = tick.askPrice1
        leg.bidVolume = tick.bidVolume1
        leg.askVolume = tick.askVolume1
        
        # 更新组合价格
        multi = self.vtSymbolMultiDict[tick.vtSymbol]
        multi.calculatePrice()
        
        # 发出事件
        self.putMultiTickEvent(multi)
        
    #----------------------------------------------------------------------
    def putMultiTickEvent(self, multi):
        """发出价差行情更新事件"""
        event1 = Event(EVENT_MULTITRADING_TICK + multi.name)
        event1.dict_['data'] = multi
        self.eventEngine.put(event1)
        
        event2 = Event(EVENT_MULTITRADING_TICK)
        event2.dict_['data'] = multi
        self.eventEngine.put(event2)     
        
    #----------------------------------------------------------------------
    def processTradeEvent(self, event):
        """处理成交推送"""
        # 检查成交是否需要处理
        trade = event.dict_['data']
        print 'process trade'
        if trade.vtSymbol not in self.legDict:
            return
        
        # 更新腿持仓
        leg = self.legDict[trade.vtSymbol]
        direction = trade.direction
        offset = trade.offset
        
        if direction == DIRECTION_LONG:
            if offset == OFFSET_OPEN:
                leg.longPos += trade.volume
            else:
                leg.shortPos -= trade.volume
        else:
            if offset == OFFSET_OPEN:
                leg.shortPos += trade.volume
            else:
                leg.longPos -= trade.volume
        leg.netPos = leg.longPos - leg.shortPos
        
        # 更新价差持仓
        multi = self.vtSymbolMultiDict[trade.vtSymbol]
        multi.calculatePos()                            # 不适用
        
        # 推送价差持仓更新
        self.putMultiPosEvent(multi)                    # 不适用
        
    #----------------------------------------------------------------------
    def processPosEvent(self, event):
        """处理持仓推送"""
        # 检查持仓是否需要处理
        pos = event.dict_['data']
        print 'process pos event'
        if pos.vtSymbol not in self.legDict:
            return
        
        # 更新腿持仓
        leg = self.legDict[pos.vtSymbol]
        direction = pos.direction
        
        if direction == DIRECTION_LONG:
            leg.longPos = pos.position
        else:
            leg.shortPos = pos.position 
        leg.netPos = leg.longPos - leg.shortPos         # 有疑问
        
        # 更新组合持仓
        multi = self.vtSymbolMultiDict[pos.vtSymbol]
        multi.calculatePrice()
        
        # 推送组合持仓更新
        self.putMultiPosEvent(multi)
        
    #----------------------------------------------------------------------
    def putMultiPosEvent(self, multi):
        """发出组合持仓事件"""
        event1 = Event(EVENT_MULTITRADING_POS+multi.name)
        event1.dict_['data'] = multi
        self.eventEngine.put(event1)
        
        event2 = Event(EVENT_MULTITRADING_POS)
        event2.dict_['data'] = multi
        self.eventEngine.put(event2)
           
        
    #----------------------------------------------------------------------
    def registerEvent(self):
        """"""
        self.eventEngine.register(EVENT_TICK, self.processTickEvent)
        self.eventEngine.register(EVENT_TRADE, self.processTradeEvent)
        self.eventEngine.register(EVENT_POSITION, self.processPosEvent)
        
    #----------------------------------------------------------------------
    def subscribeMarketData(self, vtSymbol):
        """订阅行情"""
        contract = self.mainEngine.getContract(vtSymbol)
        if not contract:
            self.writeLog(u'订阅行情失败， 找不到该合约%s' %vtSymbol)
            return
        
        req = VtSubscribeReq()
        req.symbol = contract.symbol
        req.exchange = contract.exchange
        self.mainEngine.subscribe(req, contract.gatewayName)
        
    #----------------------------------------------------------------------
    def writeLog(self, content):
        """发出日志"""
        log = VtLogData()
        log.logContent = content
        print content
        
        event = Event(EVENT_MULTITRADING_LOG)
        event.dict_['data'] = log
        self.eventEngine.put(event)
        
    #----------------------------------------------------------------------
    def getAllMultis(self):
        """获取所有的组合"""
        return self.multiDict.values()
        
        
    
########################################################################
class MultiAlgoEngine(object):
    """组合算法交易引擎"""
    algoFileName = 'multiTradingAlgo.vt'
    algoFilePath = getTempPath(algoFileName)

    #----------------------------------------------------------------------
    def __init__(self, dataEngine, mainEngine, eventEngine):
        """Constructor"""
        self.dataEngine = dataEngine
        self.mainEngine = mainEngine
        self.eventEngine = eventEngine
        
        self.algoDict = OrderedDict()           # multiName:algo
        self.vtSymbolAlgoDict = {}              # vtSymbol:algo
        
        self.registerEvent()
        
    #----------------------------------------------------------------------
    def registerEvent(self):
        """注册事件监听"""
        self.eventEngine.register(EVENT_MULTITRADING_TICK, self.processMultiTickEvent)
        self.eventEngine.register(EVENT_MULTITRADING_POS, self.processMultiPosEvent)
        self.eventEngine.register(EVENT_TRADE, self.processTradeEvent)
        self.eventEngine.register(EVENT_ORDER, self.processOrderEvent)
        self.eventEngine.register(EVENT_TIMER, self.processTimerEvent)
        
    #----------------------------------------------------------------------
    def processMultiTickEvent(self, event):
        """处理组合行情事件"""
        multi = event.dict_['data']
        
        # 若组合的买卖价均为0， 则意味着尚未初始化，直接返回
        if not multi.bidPrice and not multi.askPrice:
            return 
        
        algo = self.algoDict.get(multi.name, None)
        if algo:
            algo.updateMultiTick(multi)
            
    #----------------------------------------------------------------------
    def processMultiPosEvent(self, event):
        """处理组合持仓事件"""
        multi = event.dict_['data']
        
        algo = self.algoDict.get(multi.name, None)
        if algo:
            algo.updateMultiPos(multi)
            
    #----------------------------------------------------------------------
    def processTradeEvent(self, event):
        """处理成交事件"""
        trade = event.dict_['data']
        
        algo = self.vtSymbolAlgoDict.get(trade.vtSymbol, None)
        if algo:
            algo.updateTrade(trade)
            
    #----------------------------------------------------------------------
    def processOrderEvent(self, event):
        """处理委托事件"""
        order = event.dict_['data']
        
        algo = self.vtSymbolAlgoDict.get(order.vtSymbol, None)
        if algo:
            algo.updateOrder(order)
            
    #----------------------------------------------------------------------
    def processTimerEvent(self, event):
        """"""
        for algo in self.algoDict.values():
            algo.updateTimer()
            
    #----------------------------------------------------------------------
    def sendOrder(self, vtSymbol, direction, offset, price, volume, payup=0):
        """发单"""
        contract = self.mainEngine.getContract(vtSymbol)
        if not contract:
            return ''
        
        req = VtOrderReq()
        req.symbol = contract.symbol
        req.exchange = contract.exchange
        req.vtSymbol = contract.vtSymbol
        req.direction = direction
        req.offset = offset
        req.volume = int(volume)
        req.priceType = PRICETYPE_LIMITPRICE
        
        if direction == DIRECTION_LONG:
            req.price = price + payup * contract.priceTick
        else:
            req.price = price - payup * contract.priceTick
            
        # 委托转换
        reqList = self.mainEngine.convertOrderReq(req)
        vtOrderIDList = []
        
        for req in reqList:
            vtOrderID = self.mainEngine.sendOrder(req, contract.gatewayName)
            vtOrderIDList.append(vtOrderID)
        
        return vtOrderIDList
        
    #----------------------------------------------------------------------
    def cancelOrder(self, vtOrderID):
        """撤单"""
        order = self.mainEngine.getOrder(vtOrderID)
        if not order:
            return
        
        req = VtCancelOrderReq()
        req.symbol = order.symbol
        req.exchange = order.exchange
        req.frontID = order.frontID
        req.sessionID = order.sessionID
        req.orderID = order.orderID
        
        self.mainEngine.cancelOrder(req, order.gatewayName)
        
    #----------------------------------------------------------------------
    def buy(self, vtSymbol, price, volume, payup=0):
        """买入"""
        l = self.sendOrder(vtSymbol, DIRECTION_LONG, OFFSET_OPEN, price, volume, payup)
        return l
    
    #----------------------------------------------------------------------
    def sell(self, vtSymbol, price, volume, payup=0):
        """卖出"""
        l = self.sendOrder(vtSymbol, DIRECTION_SHORT, OFFSET_CLOSE, price, volume, payup)
        return l
    
    #----------------------------------------------------------------------
    def short(self, vtSymbol, price, volume, payup=0):
        """卖空"""
        l = self.sendOrder(vtSymbol, DIRECTION_SHORT, OFFSET_OPEN, price, volume, payup)
        return l
    
    #----------------------------------------------------------------------
    def cover(self, vtSymbol, price, volume, payup=0):
        """平空"""
        l = self.sendOrder(vtSymbol, DIRECTION_LONG, OFFSET_CLOSE, price, volume, payup)
        return l
    
    #----------------------------------------------------------------------
    def putAlgoEvent(self, algo):
        """发出算法状态更新事件"""
        event = Event(EVENT_MULTITRADING_ALGO + algo.name)          #algo.name是否应为algo.spreadName
        self.eventEngine.put(event)
        
    #----------------------------------------------------------------------
    def writeLog(self, content):
        """输出日志"""
        log = VtLogData()
        log.logContent = content
        
        event = Event(EVENT_MULTITRADING_ALGOLOG)
        event.dict_['data'] = log
        
        self.eventEngine.put(event)
        
    #----------------------------------------------------------------------
    def saveSetting(self):
        """保存算法配置"""
        setting = {}
        for algo in self.algoDict.values():
            setting[algo.multiName] = algo.getAlgoParams()
            
        f = shelve.open(self.algoFilePath)
        f['setting'] = setting
        f.close()
        
    #----------------------------------------------------------------------
    def loadSetting(self):
        """加载算法配置"""
        # 创建算法对象
        l = self.dataEngine.getAllMultis()
        for multi in l:
            algo = SpreadOptionAlgo(self, multi)
            self.algoDict[multi.name] = algo
            
            # 保存腿代码和算法对象的映射
            for leg in multi.allLegs:
                self.vtSymbolAlgoDict[leg.vtSymbol] = algo
                
        # 加载配置
        f = shelve.open(self.algoFilePath)
        setting = f.get('setting', None)
        f.close()
        
        if not setting:
            return
        
        for algo in self.algoDict.values():
            if algo.multiName in setting:
                d = setting[algo.multiName]
                algo.setAlgoParams(d)
                
    #----------------------------------------------------------------------
    def stopAll(self):
        """停止全部算法"""
        for algo in self.algoDict.values():
            algo.stop()
        
    #----------------------------------------------------------------------
    def startAll(self):
        """启动全部算法"""
        for algo in self.algoDict.values():
            algo.start()            
    
    #----------------------------------------------------------------------
    def startAlgo(self, multiName):
        """启动算法"""
        algo = self.algoDict[multiName]
        algoActive = algo.start()
        return algoActive
    
    #----------------------------------------------------------------------
    def stopAlgo(self, multiName):
        """停止算法"""
        algo = self.algoDict[multiName]
        algoActive = algo.stop()
        return algoActive
    
    #----------------------------------------------------------------------
    def getAllAlgoParams(self):
        """获取所有算法的参数"""
        return [algo.getAlgoParams() for algo in self.algoDict.values()]
    
    #----------------------------------------------------------------------
    def setAlgoBuyPrice(self, multiName, buyPrice):
        """设置算法买开价格"""
        algo = self.algoDict[multiName]
        algo.setBuyPrice(buyPrice)
        
    #----------------------------------------------------------------------
    def setAlgoSellPrice(self, multiName, sellPrice):
        """设置算法卖平价格"""
        algo = self.algoDict.values()
        algo.setSellPrice(sellPrice)
        
    #----------------------------------------------------------------------
    def setAlgoShortPrice(self, multiName, shortPrice):
        """设置算法空开价格"""
        algo = self.algoDict[multiName]
        algo.setShortPrice(shortPrice)
        
    #----------------------------------------------------------------------
    def setAlgoCoverPrice(self, multiName, coverPrice):
        """设置算法买平价格"""
        algo = self.algoDict[multiName]
        algo.setCoverPrice(coverPrice)
        
    #----------------------------------------------------------------------
    def  setAlgoMode(self, multiName, mode):
        """设置算法工作模式"""
        algo = self.algoDict[multiName]
        algo.setMode(mode)
        
    #----------------------------------------------------------------------
    def setAlogMaxOrderSize(self, multiName, maxOrderSize):
        """设置算法单笔委托限制"""
        algo = self.algoDict[multiName]
        algo.setMaxOrderSize(maxOrderSize)
        
    #----------------------------------------------------------------------
    def setAlgoMaxPosSize(self, multiName, maxPosSize):
        """设置算法持仓限制"""
        algo = self.algoDict[multiName]
        algo.setMaxPosSize(maxPosSize)       
        
    
########################################################################
class MultiEngine(object):
    """组合引擎"""

    #----------------------------------------------------------------------
    def __init__(self, mainEngine, eventEngine):
        """Constructor"""
        self.mainEngine = mainEngine
        self.eventEngine = eventEngine
        
        self.dataEngine = MultiDataEngine(mainEngine, eventEngine)
        self.algoEngine = MultiAlgoEngine(self.dataEngine, mainEngine, eventEngine)
        
        self.eventEngine.register(EVENT_MULTITRADING_STOP, self.processStopEvent)
        
    #----------------------------------------------------------------------
    def init(self):
        """初始化"""
        self.dataEngine.loadSetting()
        self.algoEngine.loadSetting()
        
    #----------------------------------------------------------------------
    def putStopEvent(self):
        """推送组合引擎关闭事件"""
        event = Event(type_=EVENT_MULTITRADING_STOP)
        if datetime.now().strftime('%H:%M:%S') > '16:00:00':
            self.eventEngine.put(event)
        
    #----------------------------------------------------------------------
    def processStopEvent(self, event):
        """处理组合引擎关闭事件"""
        self.mainEngine.exit()
        self.stop()
        
        
    #----------------------------------------------------------------------
    def stop(self):
        """停止"""
        self.dataEngine.saveSetting()
        
        self.algoEngine.stopAll()
        self.algoEngine.saveSetting()
    
        
    
    
        
    
    