# encoding: UTF-8

import json
import traceback
import shelve
from collections import OrderedDict

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
        self.legDict[activeLeg.vtSymboll] = activeLeg
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
        msg = u'%组合创建成功' %multi.name
        return result, msg
    
    #----------------------------------------------------------------------
    def processTickEvent(self, event):
        """处理行情推送"""
        # 检查行情是否需要处理
        tick = event.dict_['data']
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
        
        event = Event(EVENT_MULTITRADING_LOG)
        event.dict_['data'] = log
        self.eventEngine.put(event)
        
    #----------------------------------------------------------------------
    def getAllMultis(self):
        """获取所有的组合"""
        return self.multiDict.values()
        
        
    
########################################################################
class MultiAlgoEngine(object):
    """"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        pass
    
########################################################################
class MultiEngine(object):
    """"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        pass
        
    
    
        
    
    
        
    
    