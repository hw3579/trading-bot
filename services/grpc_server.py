#!/usr/bin/env python3
"""
gRPC服务器 - 处理交易数据查询请求
监听端口: 10001
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from concurrent import futures

import grpc
from grpc import aio

# 添加根目录到Python路径，以便导入生成的protobuf文件
sys.path.append(str(Path(__file__).parent.parent))

import proto.trading_service_pb2 as trading_service_pb2
import proto.trading_service_pb2_grpc as trading_service_pb2_grpc

import asyncio
import logging
import grpc
from concurrent import futures
import os
import sys
import base64
from io import BytesIO

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入项目模块
from generate_charts import TechnicalAnalysisChart
from examples.smart_mtf_sr_example import load_okx_data


def load_exchange_data(exchange: str, symbol: str, timeframe: str = "5m"):
    """
    通用数据加载函数
    
    Args:
        exchange: 交易所名称 (okx, hyperliquid)
        symbol: 交易对符号
        timeframe: 时间框架
        
    Returns:
        pandas.DataFrame: OHLCV数据
    """
    import pandas as pd
    
    symbol = symbol.upper()
    
    if exchange.lower() == 'okx':
        # 使用现有的OKX加载函数
        return load_okx_data(symbol)
    elif exchange.lower() == 'hyperliquid':
        # Hyperliquid数据加载逻辑
        data_path = f"hyperliquid/data_raw/{symbol}/{symbol.lower()}_{timeframe}_latest.csv"
        
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"找不到数据文件: {data_path}")
        
        # 读取CSV数据
        df = pd.read_csv(data_path)
        
        # 转换datetime列为索引
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        
        # 确保数据按时间排序
        df.sort_index(inplace=True)
        
        # 重命名列以匹配标准格式
        if 'o' in df.columns:
            df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'vol': 'volume'}, inplace=True)
        
        return df
    else:
        raise ValueError(f"不支持的交易所: {exchange}")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TradingServiceImpl(trading_service_pb2_grpc.TradingServiceServicer):
    """交易服务实现"""
    
    def __init__(self):
        self.chart_generator = TechnicalAnalysisChart(figsize=(16, 12))
        logger.info("🎯 交易服务已初始化")
    
    async def GetChart(self, request, context):
        """获取图表数据"""
        try:
            logger.info(f"📊 收到图表请求: {request.exchange} {request.symbol} {request.timeframe} {request.count}")
            
            # 验证参数
            if request.exchange not in ["okx", "hyperliquid"]:
                return trading_service_pb2.ChartResponse(
                    success=False,
                    message="不支持的交易所，请使用 'okx' 或 'hyperliquid'"
                )
            
            if request.count <= 0 or request.count > 1000:
                return trading_service_pb2.ChartResponse(
                    success=False,
                    message="K线数量必须在 1-1000 之间"
                )
            
            # 加载数据
            if request.exchange.lower() == 'okx':
                df = load_exchange_data('okx', request.symbol, request.timeframe)
            elif request.exchange.lower() == 'hyperliquid':
                df = load_exchange_data('hyperliquid', request.symbol, request.timeframe)
            else:
                return trading_service_pb2.ChartResponse(
                    success=False,
                    error_message=f"不支持的交易所: {request.exchange}"
                )
            
            if df is None or len(df) < 50:
                return trading_service_pb2.ChartResponse(
                    success=False,
                    message=f"无法获取 {request.exchange} {request.symbol} 数据或数据不足"
                )
            
            # 生成图表
            chart_buffer = self.chart_generator.generate_chart_from_dataframe(
                df=df,
                symbol=request.symbol,
                timeframe=request.timeframe,
                candles=request.count,
                return_buffer=True
            )
            
            if chart_buffer is None:
                return trading_service_pb2.ChartResponse(
                    success=False,
                    message="图表生成失败"
                )
            
            # 读取图表数据
            chart_data = chart_buffer.getvalue()
            
            logger.info(f"✅ 图表生成成功: {request.symbol} {request.timeframe}, 大小: {len(chart_data)} 字节")
            
            return trading_service_pb2.ChartResponse(
                success=True,
                message=f"✅ {request.symbol} {request.timeframe} 图表生成成功",
                chart_data=chart_data
            )
            
        except Exception as e:
            logger.error(f"❌ 图表生成失败: {e}")
            return trading_service_pb2.ChartResponse(
                success=False,
                message=f"图表生成失败: {str(e)}"
            )
    
    async def GetExchangeStatus(self, request, context):
        """获取交易所状态"""
        try:
            logger.info(f"📡 收到交易所状态请求: {request.exchange}")
            
            # 检查交易所数据目录是否存在
            data_dir = f"{request.exchange}/data_raw"
            if not os.path.exists(data_dir):
                return trading_service_pb2.ExchangeStatusResponse(
                    success=False,
                    exchange=request.exchange,
                    online=False,
                    last_update=0,
                    symbols=[]
                )
            
            # 获取支持的交易对
            symbols = []
            for symbol_dir in os.listdir(data_dir):
                if os.path.isdir(os.path.join(data_dir, symbol_dir)):
                    symbols.append(symbol_dir)
            
            return trading_service_pb2.ExchangeStatusResponse(
                success=True,
                exchange=request.exchange,
                online=True,
                last_update=0,  # 可以添加实际的最后更新时间
                symbols=symbols
            )
            
        except Exception as e:
            logger.error(f"❌ 获取交易所状态失败: {e}")
            return trading_service_pb2.ExchangeStatusResponse(
                success=False,
                exchange=request.exchange,
                online=False,
                last_update=0,
                symbols=[]
            )
    
    async def GetSupportResistance(self, request, context):
        """获取支撑阻力位数据"""
        try:
            logger.info(f"🎯 收到S/R数据请求: {request.exchange} {request.symbol} {request.timeframe}")
            
            # 加载S/R数据
            sr_file = f"{request.exchange}/data_sr/{request.symbol}/{request.symbol.lower()}_{request.timeframe}_latest_sr.csv"
            
            if not os.path.exists(sr_file):
                return trading_service_pb2.SRResponse(
                    success=False,
                    message=f"未找到 {request.exchange} {request.symbol} {request.timeframe} 的S/R数据"
                )
            
            # 这里可以添加读取和解析S/R数据的逻辑
            # 暂时返回简单响应
            return trading_service_pb2.SRResponse(
                success=True,
                message="S/R数据获取成功",
                data=trading_service_pb2.SRData(
                    current_price=0.0,
                    total_zones=0,
                    zones=[]
                )
            )
            
        except Exception as e:
            logger.error(f"❌ 获取S/R数据失败: {e}")
            return trading_service_pb2.SRResponse(
                success=False,
                message=f"获取S/R数据失败: {str(e)}"
            )

async def serve():
    """启动gRPC服务器 - 主函数"""
    await start_grpc_server()

async def start_grpc_server(host: str = "0.0.0.0", port: int = 10001):
    """启动gRPC服务器 - 可被外部调用"""
    logger.info("🎯 交易服务已初始化")
    
    server = grpc.aio.server()
    
    # 注册服务
    service_impl = TradingServiceImpl()
    trading_service_pb2_grpc.add_TradingServiceServicer_to_server(service_impl, server)
    
    # 监听端口
    listen_addr = f'{host}:{port}'
    server.add_insecure_port(listen_addr)
    
    logger.info(f"🚀 gRPC 服务器启动中...")
    logger.info(f"🌐 监听地址: {listen_addr}")
    
    await server.start()
    logger.info("✅ gRPC 服务器已启动")
    
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("👋 收到停止信号")
        await server.stop(grace=5)

if __name__ == '__main__':
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        logger.info("👋 gRPC 服务器已停止")
