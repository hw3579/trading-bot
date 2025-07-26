"""Smart MTF S/R 支撑阻力策略模块"""

import pandas as pd
import json
from typing import Dict, Any, Optional, Tuple
from indicators.smart_mtf_sr import compute_smart_mtf_sr
from config.config_loader import MonitorTarget

class SmartSRStrategy:
    """智能多时间框架支撑阻力策略
    
    该策略不是独立运行的，而是作为UTBot策略的辅助分析工具。
    当UTBot触发买卖信号时，会同时计算当前的支撑阻力位情况，
    并将分析结果附加到信号通知中。
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = "Smart_MTF_SR"
        
        # 从配置中读取参数，如果没有则使用默认值
        self.timeframes = config.get("timeframes", ["15", "60", "240"])
        self.show_swings = config.get("show_swings", True)
        self.show_pivots = config.get("show_pivots", False)
        self.show_fibonacci = config.get("show_fibonacci", False)
        self.show_order_blocks = config.get("show_order_blocks", False)
        self.show_volume_profile = config.get("show_volume_profile", False)
        self.show_psychological_levels = config.get("show_psychological_levels", True)
        self.show_within_percent = config.get("show_within_percent", 2.5)
        self.lookback_swings = config.get("lookback_swings", 3)
        self.cluster_percent = config.get("cluster_percent", 0.25)
        self.top_n = config.get("top_n", 8)
        self.reaction_lookback = config.get("reaction_lookback", 100)
        self.sort_by = config.get("sort_by", "Confluence")
        self.alert_confluence = config.get("alert_confluence", 4)
        self.min_confluence = config.get("min_confluence", 2)
        
    def calculate_sr_analysis(self, df: pd.DataFrame, symbol: str, timeframe: str, exchange: str) -> Dict[str, Any]:
        """
        计算支撑阻力位分析
        
        Args:
            df: OHLCV数据
            symbol: 交易对符号
            timeframe: 时间框架
            exchange: 交易所
            
        Returns:
            支撑阻力位分析结果
        """
        try:
            # 计算支撑阻力位
            result_df = compute_smart_mtf_sr(
                df,
                symbol=symbol,
                timeframe=timeframe,
                exchange=exchange,
                timeframes=self.timeframes,
                show_swings=self.show_swings,
                show_pivots=self.show_pivots,
                show_fibonacci=self.show_fibonacci,
                show_order_blocks=self.show_order_blocks,
                show_volume_profile=self.show_volume_profile,
                show_psychological_levels=self.show_psychological_levels,
                show_within_percent=self.show_within_percent,
                lookback_swings=self.lookback_swings,
                cluster_percent=self.cluster_percent,
                top_n=self.top_n,
                reaction_lookback=self.reaction_lookback,
                sort_by=self.sort_by,
                alert_confluence=self.alert_confluence,
                min_confluence=self.min_confluence
            )
            
            # 获取最新的支撑阻力位数据
            latest_sr_data = result_df.iloc[-1]['sr_data']
            
            if latest_sr_data and latest_sr_data != 'None':
                sr_json = json.loads(latest_sr_data)
                
                # 格式化支撑阻力位信息
                analysis = {
                    "timestamp": sr_json.get("timestamp"),
                    "current_price": sr_json.get("current_price"),
                    "total_zones": sr_json.get("total_zones", 0),
                    "support_count": sr_json.get("support_count", 0),
                    "resistance_count": sr_json.get("resistance_count", 0),
                    "max_confluence": sr_json.get("max_confluence", 0),
                    "max_reactions": sr_json.get("max_reactions", 0),
                    "key_support_levels": [],
                    "key_resistance_levels": [],
                    "market_context": ""
                }
                
                # 提取关键支撑位（前3个）
                support_levels = sr_json.get("support_levels", [])
                for level in support_levels[:3]:
                    analysis["key_support_levels"].append({
                        "price": level.get("level"),
                        "confluence": level.get("confluence"),
                        "reactions": level.get("reactions"),
                        "methods": ", ".join(level.get("methods", [])),
                        "distance_percent": abs(level.get("level", 0) - analysis["current_price"]) / analysis["current_price"] * 100
                    })
                
                # 提取关键阻力位（前3个）
                resistance_levels = sr_json.get("resistance_levels", [])
                for level in resistance_levels[:3]:
                    analysis["key_resistance_levels"].append({
                        "price": level.get("level"),
                        "confluence": level.get("confluence"),
                        "reactions": level.get("reactions"),
                        "methods": ", ".join(level.get("methods", [])),
                        "distance_percent": abs(level.get("level", 0) - analysis["current_price"]) / analysis["current_price"] * 100
                    })
                
                # 生成市场上下文分析
                analysis["market_context"] = self._generate_market_context(analysis)
                
                return analysis
            else:
                return {
                    "error": "无法获取支撑阻力位数据",
                    "current_price": float(df['close'].iloc[-1]),
                    "total_zones": 0
                }
                
        except Exception as e:
            return {
                "error": f"计算支撑阻力位时出错: {str(e)}",
                "current_price": float(df['close'].iloc[-1]) if not df.empty else 0,
                "total_zones": 0
            }
    
    def _generate_market_context(self, analysis: Dict[str, Any]) -> str:
        """生成市场上下文分析"""
        context_parts = []
        
        # 整体强度分析
        if analysis["max_confluence"] >= 4:
            context_parts.append("🔥 发现高汇聚度支撑阻力区域")
        elif analysis["max_confluence"] >= 2:
            context_parts.append("⚡ 存在中等强度支撑阻力区域")
        else:
            context_parts.append("📊 支撑阻力区域较弱")
        
        # 最近的关键位分析
        nearest_support = None
        nearest_resistance = None
        
        for support in analysis["key_support_levels"]:
            if support["distance_percent"] <= 2.0:  # 2%以内
                nearest_support = support
                break
        
        for resistance in analysis["key_resistance_levels"]:
            if resistance["distance_percent"] <= 2.0:  # 2%以内
                nearest_resistance = resistance
                break
        
        if nearest_support:
            context_parts.append(f"🛡️ 接近关键支撑位 {nearest_support['price']:.2f} (汇聚度:{nearest_support['confluence']})")
        
        if nearest_resistance:
            context_parts.append(f"🚧 接近关键阻力位 {nearest_resistance['price']:.2f} (汇聚度:{nearest_resistance['confluence']})")
        
        # 区域平衡分析
        if analysis["support_count"] > analysis["resistance_count"] * 1.5:
            context_parts.append("📈 下方支撑较强")
        elif analysis["resistance_count"] > analysis["support_count"] * 1.5:
            context_parts.append("📉 上方阻力较强")
        else:
            context_parts.append("⚖️ 支撑阻力相对平衡")
        
        return " | ".join(context_parts)
    
    def enhance_utbot_signal(self, signal_data: Dict[str, Any], df: pd.DataFrame) -> Dict[str, Any]:
        """
        为UTBot信号增强支撑阻力位分析
        
        Args:
            signal_data: UTBot的信号数据
            df: OHLCV数据
            
        Returns:
            增强后的信号数据
        """
        try:
            # 从signal_data中提取必要信息
            symbol = signal_data.get("symbol", "ETH")
            timeframe = signal_data.get("timeframe", "5m")
            exchange = signal_data.get("exchange", "okx")
            
            # 计算支撑阻力位分析
            sr_analysis = self.calculate_sr_analysis(df, symbol, timeframe, exchange)
            
            # 将支撑阻力位分析添加到信号数据中
            enhanced_signal = signal_data.copy()
            enhanced_signal["sr_analysis"] = sr_analysis
            
            # 生成增强的消息文本
            enhanced_signal["enhanced_message"] = self._format_enhanced_message(signal_data, sr_analysis)
            
            return enhanced_signal
            
        except Exception as e:
            # 如果分析失败，返回原始信号数据并添加错误信息
            enhanced_signal = signal_data.copy()
            enhanced_signal["sr_analysis"] = {"error": f"S/R分析失败: {str(e)}"}
            enhanced_signal["enhanced_message"] = signal_data.get("message", "")
            return enhanced_signal
    
    def _format_enhanced_message(self, signal_data: Dict[str, Any], sr_analysis: Dict[str, Any]) -> str:
        """格式化增强消息 - 只包含S/R分析信息"""
        try:
            # 只包含支撑阻力位分析，不重复信号信息
            message_parts = []
            
            # 添加支撑阻力位分析
            if "error" not in sr_analysis:
                message_parts.append(f"📊 支撑阻力位分析:")
                message_parts.append(f"🎯 发现 {sr_analysis.get('total_zones', 0)} 个S/R区域")
                message_parts.append(f"📈 支撑位: {sr_analysis.get('support_count', 0)} 个")
                message_parts.append(f"📉 阻力位: {sr_analysis.get('resistance_count', 0)} 个")
                message_parts.append(f"⚡ 最大汇聚度: {sr_analysis.get('max_confluence', 0)}")
                
                # 市场上下文
                if sr_analysis.get("market_context"):
                    message_parts.append(f"\n🔍 市场情况: {sr_analysis['market_context']}")
                
                # 关键位置信息
                key_supports = sr_analysis.get("key_support_levels", [])
                if key_supports:
                    message_parts.append(f"\n🛡️ 关键支撑位:")
                    for i, support in enumerate(key_supports[:2], 1):
                        message_parts.append(f"  {i}. ${support['price']:.2f} (汇聚度:{support['confluence']}, 距离:{support['distance_percent']:.1f}%)")
                
                key_resistances = sr_analysis.get("key_resistance_levels", [])
                if key_resistances:
                    message_parts.append(f"\n🚧 关键阻力位:")
                    for i, resistance in enumerate(key_resistances[:2], 1):
                        message_parts.append(f"  {i}. ${resistance['price']:.2f} (汇聚度:{resistance['confluence']}, 距离:{resistance['distance_percent']:.1f}%)")
            else:
                message_parts.append(f"⚠️ S/R分析: {sr_analysis.get('error', '未知错误')}")
            
            return "\n".join(message_parts)
            
        except Exception as e:
            # 如果格式化失败，返回错误信息
            return f"⚠️ S/R分析格式化失败: {str(e)}"
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """获取策略信息"""
        return {
            "name": self.name,
            "description": "智能多时间框架支撑阻力位分析策略（UTBot辅助）",
            "version": "1.0",
            "type": "auxiliary",  # 辅助策略
            "trigger_mode": "on_utbot_signal",  # 在UTBot信号触发时计算
            "config": self.config,
            "parameters": {
                "timeframes": self.timeframes,
                "show_swings": self.show_swings,
                "show_pivots": self.show_pivots,
                "show_fibonacci": self.show_fibonacci,
                "show_order_blocks": self.show_order_blocks,
                "show_volume_profile": self.show_volume_profile,
                "show_psychological_levels": self.show_psychological_levels,
                "cluster_percent": self.cluster_percent,
                "min_confluence": self.min_confluence
            }
        }
