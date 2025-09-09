# file_finder.py
"""
文件查找器 - 根据file_name和章节标题查找对应的txt文件
"""

import os
import glob
from typing import List, Dict, Any


class FileFinder:
    """
    文件查找器
    根据file_name和章节标题查找对应的txt文件
    """
    
    def __init__(self):
        """初始化文件查找器"""
        self.base_path = "替换为本地目录"
        print("[FileFinder] 文件查找器初始化完成")
    
    def find_section_files(self, file_name: str, section_titles: List[str]) -> Dict[str, Any]:
        """
        根据file_name和章节标题查找对应的txt文件
        
        Args:
            file_name: 文件名，格式如 "2025-03-12_180305.SZ_南方顺丰物流REIT_南方顺丰仓储物流封闭式基础设施证券投资基金招募说明书.pdf"
            section_titles: 章节标题列表
            
        Returns:
            Dict[str, Any]: 查找结果
            {
                "success": bool,
                "found_files": List[str],     # 找到的txt文件路径列表
                "missing_sections": List[str], # 未找到的章节
                "target_folder": str,         # 目标文件夹路径
                "error": str                  # 错误信息（可选）
            }
        """
        print(f"[FileFinder] 开始查找文件")
        print(f"  文件名: {file_name}")
        print(f"  章节标题: {section_titles}")
        
        try:
            # 步骤1：解析文件名，提取基金代码
            fund_code = self._extract_fund_code(file_name)
            if not fund_code:
                return {
                    "success": False,
                    "found_files": [],
                    "missing_sections": section_titles,
                    "target_folder": "",
                    "error": f"无法从文件名 {file_name} 中提取基金代码"
                }
            
            # 步骤2：构建目标文件夹路径
            folder_name = file_name.replace('.pdf', '').replace('.PDF', '')
            target_folder = os.path.join(self.base_path, fund_code, folder_name)
            
            print(f"[FileFinder] 目标文件夹: {target_folder}")
            
            # 步骤3：检查文件夹是否存在
            if not os.path.exists(target_folder):
                return {
                    "success": False,
                    "found_files": [],
                    "missing_sections": section_titles,
                    "target_folder": target_folder,
                    "error": f"目标文件夹不存在: {target_folder}"
                }
            
            # 步骤4：查找每个章节对应的txt文件
            found_files = []
            missing_sections = []
            
            for section_title in section_titles:
                section_files = self._find_files_for_section(target_folder, section_title)
                if section_files:
                    found_files.extend(section_files)
                    print(f"[FileFinder] ✅ 找到章节 '{section_title}' 的文件: {len(section_files)} 个")
                else:
                    missing_sections.append(section_title)
                    print(f"[FileFinder] ❌ 未找到章节 '{section_title}' 的文件")
            
            # 去重
            found_files = list(set(found_files))
            
            result = {
                "success": len(found_files) > 0,
                "found_files": found_files,
                "missing_sections": missing_sections,
                "target_folder": target_folder
            }
            
            if len(found_files) == 0:
                result["error"] = f"所有章节的txt文件都未找到"
            
            print(f"[FileFinder] 查找完成，找到 {len(found_files)} 个文件")
            return result
            
        except Exception as e:
            print(f"[FileFinder] 文件查找异常: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "success": False,
                "found_files": [],
                "missing_sections": section_titles,
                "target_folder": "",
                "error": f"文件查找异常: {str(e)}"
            }
    
    def _extract_fund_code(self, file_name: str) -> str:
        """
        从文件名中提取基金代码
        
        文件名格式: "日期-基金代码-基金简称-文件名.pdf"
        例如: "2025-03-12_180305.SZ_南方顺丰物流REIT_南方顺丰仓储物流封闭式基础设施证券投资基金招募说明书.pdf"
        """
        try:
            # 移除文件扩展名
            name_without_ext = file_name.replace('.pdf', '').replace('.PDF', '')
            
            # 按下划线分割
            parts = name_without_ext.split('_')
            
            if len(parts) >= 2:
                # 第二部分应该是基金代码
                fund_code = parts[1]
                print(f"[FileFinder] 提取的基金代码: {fund_code}")
                return fund_code
            else:
                print(f"[FileFinder] 文件名格式不符合预期: {file_name}")
                return ""
                
        except Exception as e:
            print(f"[FileFinder] 基金代码提取异常: {e}")
            return ""
    
    def _find_files_for_section(self, target_folder: str, section_title: str) -> List[str]:
        """
        在目标文件夹中查找指定章节的txt文件
        
        Args:
            target_folder: 目标文件夹路径
            section_title: 章节标题
            
        Returns:
            List[str]: 找到的txt文件路径列表
        """
        try:
            # 构建匹配模式: *章节标题.txt
            pattern = os.path.join(target_folder, f"*{section_title}.txt")
            
            print(f"[FileFinder] 查找模式: {pattern}")
            
            # 使用glob查找文件
            matching_files = glob.glob(pattern)
            
            # 过滤确实存在的文件
            existing_files = [f for f in matching_files if os.path.isfile(f)]
            
            if existing_files:
                print(f"[FileFinder] 章节 '{section_title}' 找到文件: {existing_files}")
            else:
                print(f"[FileFinder] 章节 '{section_title}' 未找到匹配文件")
                
                # 尝试列出文件夹中的所有txt文件，用于调试
                all_txt_files = glob.glob(os.path.join(target_folder, "*.txt"))
                if all_txt_files:
                    print(f"[FileFinder] 文件夹中存在的txt文件: {[os.path.basename(f) for f in all_txt_files[:5]]}...")
                else:
                    print(f"[FileFinder] 文件夹中没有任何txt文件")
            
            return existing_files
            
        except Exception as e:
            print(f"[FileFinder] 章节文件查找异常: {e}")
            return []
    
    def get_file_content(self, file_path: str) -> str:
        """
        读取文件内容
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 文件内容
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            print(f"[FileFinder] 读取文件成功: {file_path}, 长度: {len(content)} 字符")
            return content
            
        except Exception as e:
            print(f"[FileFinder] 读取文件失败 {file_path}: {e}")
            return ""
    
    def get_combined_content(self, file_paths: List[str]) -> str:
        """
        合并多个文件的内容
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            str: 合并后的内容
        """
        combined_content = ""
        
        for file_path in file_paths:
            content = self.get_file_content(file_path)
            if content:
                # 添加文件标识
                file_name = os.path.basename(file_path)
                combined_content += f"\n\n=== 文件: {file_name} ===\n"
                combined_content += content
        
        print(f"[FileFinder] 合并内容完成，总长度: {len(combined_content)} 字符")
        return combined_content


# 测试函数
if __name__ == "__main__":
    finder = FileFinder()
    
    # 测试文件查找
    test_file_name = "2025-03-12_180305.SZ_南方顺丰物流REIT_南方顺丰仓储物流封闭式基础设施证券投资基金招募说明书.pdf"
    test_sections = ["基础设施项目基本情况", "基金费用与税收"]
    
    print(f"=== 测试文件查找 ===")
    result = finder.find_section_files(test_file_name, test_sections)
    print(f"查找结果: {result}")