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

EVENT_MULTILOCAL_POSITION = 'eMultiLocalPos'
EVENT_MULTI_TRADE = 'eMultiTrade'

Multi_POSITION_DB_NAME = 'VnTrader_Multi_Db'

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
        self.legDict = {}                   # vtSymbol:StLegDictList stLegDict={multi.name:stLeg}
        self.multiDict = {}                 # name:MultiMulti
        self.vtSymbolMultiDict = {}         # vtSymbol:MultiMultiList
        self.multiNameOrderDict = {}        # multi.name:vtOrderIDList
        #self.vtOrderIDMultiDict = {}        # vtOderID:multi
        
        self.registerEvent()
        
        self.startTime = datetime.now().strftime('%H:%M:%S')
        
        self.qryLocalPosCount  = 0 
        self.qryLocalPosDistance = 6
        
        self.isLocalPosChecked = False
        
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
        with open(self.settingFilePath, mode='w') as f:
            fileContentDictList = []
            for multi in self.multiDict.values():
                fileContentDict = {}
                fileContentDict['name'] = multi.name
                
                # 获取主动腿配置
                activeLeg = multi.activeLeg 
                activeLegSetting = {}
                activeLegSetting['vtSymbol'] = activeLeg.vtSymbol
                activeLegSetting['ratio'] = activeLeg.ratio
                activeLegSetting['multiplier'] = activeLeg.multiplier
                activeLegSetting['payup'] = activeLeg.payup
                
                fileContentDict['activeLeg'] = activeLegSetting
                
                # 获取被动腿配置
                passiveLegs = multi.passiveLegs
                passiveLegsSettings = []
                for passiveLeg in passiveLegs:
                    passiveLegSetting = {}
                    passiveLegSetting['vtSymbol'] = passiveLeg.vtSymbol
                    passiveLegSetting['ratio'] = passiveLeg.ratio
                    passiveLegSetting['multiplier'] = passiveLeg.multiplier
                    passiveLegSetting['payup'] = passiveLeg.payup
                    passiveLegsSettings.append(passiveLegSetting)
                
                fileContentDict['passiveLegs'] = passiveLegsSettings
                
                fileContentDictList.append(fileContentDict)
                
            json.dump(fileContentDictList, f, 
                     indent=4)
            f.close()
            
        
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
        #l = []
        #l.append(setting['activeLeg']['vtSymbol'])
        #for d in setting['passiveLegs']:
            #l.append(d['vtSymbol'])
            
        #for vtSymbol in l:
            #if vtSymbol in self.vtSymbolMultiDict:
                #existingMulti = self.vtSymbolMultiDict[vtSymbol]
                #msg = u'%s合约已经存在于%s价差中' %(vtSymbol, existingMulti.name)
                #return result, msg
        
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
        
        tempLegDict = {multi.name:activeLeg}
        if activeLeg.vtSymbol not in self.legDict:
            self.legDict[activeLeg.vtSymbol] = [tempLegDict]
        else:
            self.legDict[activeLeg.vtSymbol].append(tempLegDict)
        
        if activeLeg.vtSymbol not in self.vtSymbolMultiDict:
            self.vtSymbolMultiDict[activeLeg.vtSymbol] = [multi]
        else:
            self.vtSymbolMultiDict[activeLeg.vtSymbol].append(multi)
        
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
            
            tempLegDict = {multi.name:passiveLeg}
            if passiveLeg.vtSymbol not in self.legDict:
                self.legDict[passiveLeg.vtSymbol] = [tempLegDict]
            else:
                self.legDict[passiveLeg.vtSymbol].append(tempLegDict)
            
            if passiveLeg.vtSymbol not in self.vtSymbolMultiDict:
                self.vtSymbolMultiDict[passiveLeg.vtSymbol] = [multi]
            else:
                self.vtSymbolMultiDict[passiveLeg.vtSymbol].append(multi)
            
            self.subscribeMarketData(passiveLeg.vtSymbol)
        
        # 初始化组合
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
        if tick.vtSymbol not in self.legDict:
            return
        #print 'process tickEvent'
        # 更新腿价格
        legList = self.legDict[tick.vtSymbol]
        
        for i in legList:
            leg = i.values()[0]
            leg.bidPrice = tick.bidPrice1
            leg.askPrice = tick.askPrice1
            leg.bidVolume = tick.bidVolume1
            leg.askVolume = tick.askVolume1
        

        #print str(leg.bidPrice)+leg.vtSymbol
        
        # 更新组合价格
        multiList = self.vtSymbolMultiDict[tick.vtSymbol]
        for multi in multiList:
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
        if not self.isLocalPosChecked:
            return
        # 检查成交是否需要处理
        trade = event.dict_['data']
        tradeT = trade.tradeTime
        multiName = trade.multiName 
        
        # 排除之前的成交单
        if tradeT < self.startTime:
            return
        #print 'process trade'
        if trade.vtSymbol not in self.legDict:
            return
        
        multi = self.multiDict[multiName]
        #multi = self.vtOrderIDMultiDict[vtOrderID]
        
        # 更新腿持仓
        allLegs = multi.allLegs
        for leg in allLegs:
            if leg.vtSymbol == trade.vtSymbol:
                break
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
        #print str(leg.netPos)+trade.vtSymbol+'longPos:'+str(leg.longPos)+'shortPos:'+str(leg.shortPos)+'tradeVolume:'+str(trade.volume)
        
        # 更新价差持仓
        multi.calculatePos()                            # 不适用 适用于用来计算组合持仓
        
        # 推送价差持仓更新
        self.putMultiPosEvent(multi)                    
        
    #----------------------------------------------------------------------
    def processPosEvent(self, event):
        """处理持仓推送,本地持仓查询推送,按标的分次推送，仿真交易所"""
        # 检查持仓是否需要处理
        # singlePos 为本地持仓查询的结果{vtSymbol:[posDetail,...]},posDetail为{'name':multi.name,'longPos':volume, 'shortPos':volume}
        singlePos = event.dict_['data']
        #nowStr = datetime.now().strftime('%H:%M:%S')
        #print 'process pos event'+nowStr
        vtSymbol = singlePos.keys()[0]
        
        if vtSymbol not in self.legDict:
            return 
        
        multiList = self.vtSymbolMultiDict[vtSymbol]
        for pos in singlePos.values()[0]:
            multiName = pos['name']
            
            # 更新腿持仓
            legList = self.legDict[vtSymbol]
            for legDict in legList:
                if multiName in legDict:
                    break
            
            for multi in multiList:
                if multi.name == multiName:
                    break
            
            leg = legDict.values()[0]    
            leg.longPos = pos['longPos']
            leg.shortPos = pos['shortPos']
            
            leg.netPos = leg.longPos - leg.shortPos
        
            # 更新组合持仓
            multi.calculatePos()
        
            # 推送组合持仓更新
            self.putMultiPosEvent(multi)
            
    #----------------------------------------------------------------------
    def processCTPPosEvent(self, event):
        """处理CTP持仓事件，用于初始化仓位"""
        pass
        
        
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
    def processTimerEvent(self, event):
        """处理时间事件，定期查询本地持仓"""
        self.qryLocalPosCount += 1
        if self.qryLocalPosCount >= self.qryLocalPosDistance:
            self.qryLocalPosCount = 0
            posList = self.getMultiLocalPos()
            self.isLocalPosChecked = True
            for pos in posList:
                posEvent = Event(EVENT_MULTILOCAL_POSITION)
                posEvent.dict_['data'] = pos
                self.eventEngine.put(posEvent)
                
    #----------------------------------------------------------------------
    def getMultiLocalPos(self):
        """获得组合的本地持仓posList:[{vtSymbol:[{'name':multi.name,'longPos':volume,'shortPos':volume}]}]"""
        posList = []
        dbClient = self.mainEngine.dbClient
        db = dbClient[Multi_POSITION_DB_NAME]
        collectionNames = db.collection_names()
        for i in collectionNames:
            pos = {}
            posKey = i
            posValue = []
            collection = db[i]
            for j in collection.find({}):
                tempPos = {}
                tempPos['name'] = j['name']
                tempPos['longPos'] = j['longPos']
                tempPos['shortPos'] = j['shortPos']
                posValue.append(tempPos)
            
            if not posValue:
                continue
            pos[posKey] = posValue
            
            posList.append(pos)
        
        return posList           
        
        
    #----------------------------------------------------------------------
    def registerEvent(self):
        """"""
        self.eventEngine.register(EVENT_TICK, self.processTickEvent)
        self.eventEngine.register(EVENT_MULTI_TRADE, self.processTradeEvent)
        self.eventEngine.register(EVENT_TIMER, self.processTimerEvent)
        self.eventEngine.register(EVENT_MULTILOCAL_POSITION, self.processPosEvent)
        
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
        #print content
        
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
        self.vtSymbolAlgoDict = {}              # vtSymbol:algoList
        self.vtOrderIDAlgoDict = {}            # vtOrderID:algo
        
        self.registerEvent()
        
        self.startTime = datetime.now().strftime('%H:%M:%S')
        
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
        
        #algo = self.vtSymbolAlgoDict.get(trade.vtSymbol, None)
        algo = self.vtOrderIDAlgoDict.get(trade.vtOrderID, None)
        tradeT = trade.tradeTime
        if tradeT < self.startTime:
            return
        print trade.__dict__
        print algo 
        print self.vtOrderIDAlgoDict
        
        if algo:
            # 分组合推送成交事件
            event = Event(EVENT_MULTI_TRADE)
            trade.multiName = algo.multiName
            event.dict_['data'] = trade
            self.eventEngine.put(event)            
            algo.updateTrade(trade)
            
            self.saveLocalMultiPosition(trade)
            
    #----------------------------------------------------------------------
    def uploadMultiPosition(self, posDict):
        """初始化持仓"""
        for pos in posDict.values()[0]:
            flt = {'name': pos['name']}
            self.mainEngine.dbUpdate(Multi_POSITION_DB_NAME, posDict.keys()[0], pos, flt, upsert=True)
    
    #----------------------------------------------------------------------
    def getDbPosition(self, vtSymbol):
        """获得特定品种的持仓"""
        posList = self.mainEngine.dbQuery(Multi_POSITION_DB_NAME, vtSymbol, {})
        return posList
        
    #----------------------------------------------------------------------
    def saveLocalMultiPosition(self, trade):
        """成交后将持仓写入数据库"""
        vtSymbol = trade.vtSymbol
        multiName = trade.multiName
        direction = trade.direction 
        
        posList = self.getDbPosition(vtSymbol)
        if posList:
            isExistPos = False
            for tempPos in posList:
                if tempPos['name'] == multiName:
                    pos = tempPos
                    isExistPos = True
                    break
        
            if not isExistPos:
                pos = {}
                pos['name'] = multiName
                pos['longPos'] = 0
                pos['shortPos'] = 0
                
            d = {}
            d['name'] = pos['name']
            d['longPos'] = pos['longPos']
            d['shortPos'] = pos['shortPos']
            if direction == DIRECTION_LONG:
                d['longPos'] = pos['longPos'] + trade.volume 
            else:
                d['shortPos'] = pos['shortPos'] + trade.volume
        
            flt = {'name': multiName}
            self.mainEngine.dbUpdate(Multi_POSITION_DB_NAME, vtSymbol, d, flt, True)
        else:
            d = {}
            d['name'] = multiName
            d['longPos'] = 0
            d['shortPos'] = 0
            if direction == DIRECTION_LONG:
                d['longPos'] += trade.volume
            else:
                d['shortPos'] += trade.volume
            
            flt = {'name': multiName}
            self.mainEngine.dbUpdate(Multi_POSITION_DB_NAME, vtSymbol, d, flt, True)            
            
        
            
    #----------------------------------------------------------------------
    def processOrderEvent(self, event):
        """处理委托事件"""
        order = event.dict_['data']
        
        #algo = self.vtSymbolAlgoDict.get(order.vtSymbol, None)
        algo = self.vtOrderIDAlgoDict.get(order.vtOrderID, None)
        if algo:
            algo.updateOrder(order)
            
    #----------------------------------------------------------------------
    def processTimerEvent(self, event):
        """"""
        for algo in self.algoDict.values():
            algo.updateTimer()
            
    #----------------------------------------------------------------------
    def sendOrder(self, vtSymbol, direction, offset, price, volume, payup=0, algo=None):
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
            if algo:
                self.vtOrderIDAlgoDict[vtOrderID] = algo
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
        event = Event(EVENT_MULTITRADING_ALGO + algo.algoName)          
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
        #setting = {}
        #for algo in self.algoDict.values():
            #setting[algo.multiName] = algo.getAlgoParams()
            
        #f = shelve.open(self.algoFilePath)
        #f['setting'] = setting
        #f.close()
        
        for algo in self.algoDict.values():
            algo.saveAlgoParamDict()
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
                if leg.vtSymbol not in self.vtSymbolAlgoDict:
                    self.vtSymbolAlgoDict[leg.vtSymbol] = [algo]
                else:
                    self.vtSymbolAlgoDict[leg.vtSymbol].append(algo)
                
        
        # 实际配置并未从此处读取        
        # 加载配置
        #f = shelve.open(self.algoFilePath)
        #print self.algoFilePath
        #setting = f.get('setting', None)
        #f.close()
        
        #if not setting:
            #return
        
        #for algo in self.algoDict.values():
            #if algo.multiName in setting:
                #d = setting[algo.multiName]
                #algo.setAlgoParams(d)
                
    #----------------------------------------------------------------------
    def stopAll(self):
        """停止全部算法"""
        for algo in self.algoDict.values():
            algo.stop()
            
        #self.saveSetting()
        
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
        algo = self.algoDict[multiName]
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
        
        #self.eventEngine.register(EVENT_TIMER, self.processStopEvent)
        
        ## 主引擎开关
        #self.active = True
        
    #----------------------------------------------------------------------
    def init(self):
        """初始化"""
        self.dataEngine.loadSetting()
        self.algoEngine.loadSetting()
        self.algoEngine.startAll()
        
    ##----------------------------------------------------------------------
    #def processStopEvent(self, event):
        #"""处理组合引擎关闭事件"""
        #nowStr = datetime.now().strftime('%H:%M:%S')
        #if not self.active:
            #return        
        #if nowStr > '15:01:00':
            #self.stop()
        
        
    #----------------------------------------------------------------------
    def stop(self):
        """停止"""
        self.dataEngine.saveSetting()
        
        self.algoEngine.stopAll()
        self.algoEngine.saveSetting()
        #self.active = False
    
        
    
    
        
    
    