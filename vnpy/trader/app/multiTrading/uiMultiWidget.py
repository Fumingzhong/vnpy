# encoding: UTF-8

from collections import OrderedDict

from six import text_type

from vnpy.event import Event
from vnpy.trader.uiQt import QtWidgets, QtCore
from vnpy.trader.uiBasicWidget import (BasicMonitor, BasicCell, PnlCell,
                                       AskCell, BidCell, BASIC_FONT)

from .multiBase import (EVENT_MULTITRADING_TICK, EVENT_MULTITRADING_POS,
                        EVENT_MULTITRADING_LOG, EVENT_MULTITRADING_ALGO,
                        EVENT_MULTITRADING_ALGOLOG)
from .multiAlgo import MultiAlgoTemplate

STYLESHEET_START = 'background-color: rgb(111,255,244); color: black'
STYLESHEET_STOP = 'background-color: rgb(255,201,111); color: black'


########################################################################
class MultiTickMonitor(BasicMonitor):
    """多标的组合行情监控 """

    #----------------------------------------------------------------------
    def __init__(self, mainEngine, eventEngine, parent=None):
        """Constructor"""
        super(MultiTickMonitor, self).__init__(mainEngine, eventEngine, parent)
        
        d = OrderedDict()
        d['name'] = {'chinese':u'组合名称', 'cellType':BasicCell}
        d['bidPrice'] = {'chinese':u'买价', 'cellType':BidCell}
        d['bidVolume'] = {'chinese':u'买量', 'cellType':BidCell}
        d['askPrice'] = {'chinese':u'卖价', 'cellType':AskCell}
        d['askVolume'] = {'chinese':u'卖量', 'cellType':AskCell}
        d['time'] = {'chinese':u'时间', 'cellType':BasicCell}
        d['symbol'] = {'chinese':u'组合公式', 'cellType':BasicCell}
        self.setHeaderDict(d)
        
        self.setDataKey('name')
        self.setEventType(EVENT_MULTITRADING_TICK)
        self.setFont(BASIC_FONT)
        
        self.initTable()
        self.registerEvent()
    
    
########################################################################
class MultiPosMonitor(BasicMonitor):
    """多标的持仓监控"""

    #----------------------------------------------------------------------
    def __init__(self, mainEngine, eventEngine, parent=None):
        """Constructor"""
        super(MultiPosMonitor, self).__init__(mainEngine, eventEngine, parent)
        
        d = OrderedDict()
        d['name'] = {'chinese':u'组合名称', 'cellType':BasicCell}
        d['netPos'] = {'chinese':u'净仓', 'cellType':PnlCell}
        d['longPos'] = {'chinese':u'多仓', 'cellType':BasicCell}
        d['shortPos'] = {'chinese':u'空仓', 'cellType':BasicCell}
        d['symbol'] = {'chinese':u'代码', 'cellType':BasicCell}
        self.setHeaderDict(d)
        
        self.setDataKey('name')
        self.setEventType(EVENT_MULTITRADING_POS)
        self.setFont(BASIC_FONT)
        
        self.initTable()
        self.registerEvent()
    
########################################################################
class MultiLogMonitor(QtWidgets.QTextEdit):
    """多标的日志监控"""
    signal = QtCore.Signal(type(Event()))

    #----------------------------------------------------------------------
    def __init__(self, mainEngine, eventEngine, parent=None):
        """Constructor"""
        super(MultiLogMonitor, self).__init__(parent)
        
        self.eventEngine = eventEngine
        
        self.registerEvent()
    
    #----------------------------------------------------------------------
    def processLogEvent(self, event):
        """处理日志事件"""
        log = event.dict_['data']
        content = '%s:%s' %(log.logTime, log.logContent)
        self.append(content)
        
    #----------------------------------------------------------------------
    def registerEvent(self):
        """注册事件监听"""
        self.signal.connect(self.processLogEvent)
        
        self.eventEngine.register(EVENT_MULTITRADING_LOG, self.signal.emit)
        
        
########################################################################
class MultiAlgoLogMonitor(BasicMonitor):
    """多标的算法日志监控"""

    #----------------------------------------------------------------------
    def __init__(self, mainEngine, eventEngine, parent=None):
        """Constructor"""
        super(MultiAlgoLogMonitor, self).__init__(mainEngine, eventEngine, parent)
        
        d = OrderedDict()
        d['logTime'] = {'chinese':u'时间', 'cellType':BasicCell}
        d['logContent'] = {'chinese':u'信息', 'cellType':BasicCell}
        self.setHeaderDict(d)
        
        self.setEventType(EVENT_MULTITRADING_ALGOLOG)
        self.setFont(BASIC_FONT)
        
        self.initTable()
        self.registerEvent()
    
      
########################################################################
class MultiBuyPriceSpinBox(QtWidgets.QDoubleSpinBox):
    """"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        pass
        
########################################################################
class MultiSellPriceSpinBox(QtWidgets.QDoubleSpinBox):
    """"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        pass
    
########################################################################
class MultiShortPriceSpinBox(QtWidgets.QDoubleSpinBox):
    """"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        pass
    
########################################################################
class MultiCoverPriceSpinBox(QtWidgets.QDoubleSpinBox):
    """"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        pass
    
########################################################################
class MultiMaxPosSizeSpinBox(QtWidgets.QSpinBox):
    """"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        pass
    
########################################################################
class MultiMaxOrderSizeSpinBox(QtWidgets.QSpinBox):
    """"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        pass
    
########################################################################
class MultiModeComboBox(QtWidgets.QComboBox):
    """"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        pass
    
########################################################################
class MultiActiveButton(QtWidgets.QPushButton):
    """"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        pass
    
########################################################################
class MultiAlgoManager(QtWidgets.QTableWidget):
    """"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        pass
    
########################################################################
class MultiGroup(QtWidgets.QGroupBox):
    """"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        pass
        
########################################################################
class MultiManager(QtWidgets.QWidget):
    """"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        pass
        
    
    
        
    
    
        
        
    
    
        
        
    
    
        
    
    
        
        
    
    
        
        
    
    
        
        
    
    
        
        
    
    
        
        
    
    
        
    
    
    
    
        
    
    
        
        
    
    
        
        
    
    