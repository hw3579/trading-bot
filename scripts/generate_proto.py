#!/usr/bin/env python3
"""
生成protobuf代码的脚本
"""

import subprocess
import sys
import os

def generate_proto():
    """生成protobuf代码到proto文件夹"""
    print("🔄 正在生成protobuf代码...")
    
    try:
        # 生成到proto文件夹
        cmd = [
            sys.executable, '-m', 'grpc_tools.protoc',
            '--proto_path=proto',  # 源文件目录
            '--python_out=proto',  # Python输出目录
            '--grpc_python_out=proto',  # gRPC输出目录
            'proto/trading_service.proto'  # 源文件
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ protobuf代码生成成功")
            
            # 修复gRPC文件中的导入路径
            grpc_file = 'proto/trading_service_pb2_grpc.py'
            if os.path.exists(grpc_file):
                with open(grpc_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 替换导入语句为相对导入
                content = content.replace(
                    'import trading_service_pb2 as trading__service__pb2',
                    'from . import trading_service_pb2 as trading__service__pb2'
                )
                
                with open(grpc_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print("🔧 已修复gRPC文件导入路径")
            
            print("📁 生成文件:")
            print("   - proto/trading_service_pb2.py")
            print("   - proto/trading_service_pb2_grpc.py")
        else:
            print(f"❌ 生成失败: {result.stderr}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    generate_proto()
