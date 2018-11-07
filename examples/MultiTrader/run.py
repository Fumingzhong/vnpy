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
from time import sleep

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
    
    
    # 交易接口连接
    me.connect(ctpGateway.gatewayName)
    
    # 引擎开始前需要查询一次合约
    gateway = me.getGateway(ctpGateway.gatewayName)
    tdApi = gateway.tdApi
    tdApi.reqID += 1
    tdApi.reqQryInstrument({}, tdApi.reqID)  
    # 组合模块
    multiEngine = MultiEngine(me, ee)
    multiEngine.init()
    multiDataEngine = multiEngine.dataEngine
    multiAlgoEngine = multiEngine.algoEngine
    multiAlgoEngine.startAll()
    
    # 在主线程中启动Qt事件循环
    sys.exit(qApp.exec_())
    
if __name__ == '__main__':
    main()