# encoding: UTF-8

# 重载sys模块，设置默认字符串编码方式为utf8
try:
    reload         # Python 2
except NameError:  # Python 3
    from importlib import reload

import sys
reload(sys)

try:
    sys.setdefaultencoding('utf8')
except AttributeError:
    pass

from qtpy import QtCore, QtWidgets

# vn.trader模块
from vnpy.event import EventEngine
from vnpy.trader.vtEngine import MainEngine

# 加载底层接口
from vnpy.trader.gateway import ctpGateway

sys.path.append(r'C:\vnpy\vnpy\trader\app')
from multiTrading.multiEngine import MultiDataEngine, MultiAlgoEngine, MultiEngine
from vnpy.event import Event,EVENT_TIMER
from datetime import datetime
from time import sleep
import multiTrading

########################################################################
class CloseEventEngine(QtCore.QObject):
    """mainEngine退出事件"""
    signal = QtCore.Signal(type(Event()))

    #----------------------------------------------------------------------
    def __init__(self, mainEngine, eventEngine):
        """Constructor"""
        super(CloseEventEngine, self).__init__()
        self.mainEngine = mainEngine
        self.eventEngine = eventEngine
        self.eventEngine.register(EVENT_TIMER, self.signal.emit)
        self.signal.connect(self.processStopEvent)
        
    #----------------------------------------------------------------------
    def processStopEvent(self):
        """关闭事件引擎"""
        nowStr = datetime.now().strftime('%H:%M:%S')     
        if nowStr > '25:00:00':
            self.mainEngine.exit()
            print u'退出主引擎'
            self.mainEngine.writeLog(u'退出主引擎')
            QtCore.QCoreApplication.quit()
            print u'程序结束'
            self.mainEngine.writeLog(u'退出程序')
        
#----------------------------------------------------------------------
def main():
    """主程序入口"""
    # 创建Qt应用对象
    qApp = QtCore.QCoreApplication([])
    
    # 创建事件引擎
    ee = EventEngine()
    
    # 创建主引擎
    me = MainEngine(ee)
    
    # 添加交易接口
    me.addGateway(ctpGateway)    
    
    # 添加应用
    me.addApp(multiTrading)    
    # 交易接口连接
    me.connect(ctpGateway.gatewayName)
    
    # 引擎开始前需要查询一次合约
    gateway = me.getGateway(ctpGateway.gatewayName)
    tdApi = gateway.tdApi
    
    # 等到查询持仓情况
    while True:
        if not tdApi.symbolSizeDict:
            sleep(0.5)
            print 'sleep to wait for reqQryInstrument to finish!'
        else:
            print 'reqQryInstrument finished!'
            break    
    # 组合模块
    multiEngine = me.appDict[multiTrading.appName]
    multiEngine.init()
    multiDataEngine = multiEngine.dataEngine
    multiAlgoEngine = multiEngine.algoEngine    
    
    # 创建关闭事件
    closeEventEngine = CloseEventEngine(me, ee)
    
    # 在主线程中启动Qt事件循环
    sys.exit(qApp.exec_())
    
if __name__ == '__main__':
    main()