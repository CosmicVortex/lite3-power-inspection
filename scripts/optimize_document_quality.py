#!/usr/bin/env python3
"""
绝影Lite3项目 - 文档质量优化工具
自动分析并优化Markdown文档的排版和结构
"""

import re
import sys
from pathlib import Path
from collections import defaultdict

class DocumentOptimizer:
    """文档质量优化器"""
    
    def __init__(self, docs_dir: Path):
        self.docs_dir = docs_dir
        self.analysis_results = {}
        
    def analyze_document(self, doc_path: Path) -> dict:
        """分析单个文档的质量指标"""
        content = doc_path.read_text(encoding='utf-8')
        lines = content.split('\n')
        
        analysis = {
            "文件": doc_path.name,
            "总行数": len(lines),
            "总字符数": len(content),
            "标题统计": {"H1": 0, "H2": 0, "H3": 0, "H4+": 0},
            "表格数量": 0,
            "代码块数量": 0,
            "列表项数量": 0,
            "链接数量": 0,
            "空行数量": 0,
            "问题列表": [],
            "建议改进": []
        }
        
        # 统计标题层级
        for line in lines:
            if line.startswith('####'):
                analysis["标题统计"]["H4+"] += 1
            elif line.startswith('###'):
                analysis["标题统计"]["H3"] += 1
            elif line.startswith('##'):
                analysis["标题统计"]["H2"] += 1
            elif line.startswith('#'):
                analysis["标题统计"]["H1"] += 1
        
        # 统计表格
        table_lines = [l for l in lines if l.startswith('|') and '---' not in l]
        analysis["表格数量"] = len(table_lines) // 2
        
        # 统计代码块
        code_blocks = re.findall(r'```', content)
        analysis["代码块数量"] = len(code_blocks) // 2
        
        # 统计列表项
        list_items = [l for l in lines if l.strip().startswith('- ') or 
                     l.strip().startswith('* ') or re.match(r'^\s*\d+\.', l)]
        analysis["列表项数量"] = len(list_items)
        
        # 统计链接
        links = re.findall(r'\[.*?\]\(.*?\)', content)
        analysis["链接数量"] = len(links)
        
        # 统计空行
        empty_lines = [l for l in lines if l.strip() == '']
        analysis["空行数量"] = len(empty_lines)
        
        # 检测问题
        self._detect_issues(content, lines, analysis)
        
        return analysis
    
    def _detect_issues(self, content: str, lines: list, analysis: dict):
        """检测文档质量问题"""
        
        # 问题1: 缺少目录
        if not any('目录' in l or 'Table of Contents' in l for l in lines[:30]):
            analysis["问题列表"].append("缺少目录")
            analysis["建议改进"].append("在文档开头添加自动生成目录")
        
        # 问题2: 标题层级跳跃
        current_level = 0
        for i, line in enumerate(lines):
            match = re.match(r'^(#{1,6})\s', line)
            if match:
                level = len(match.group(1))
                if current_level > 0 and level > current_level + 1:
                    analysis["问题列表"].append(f"标题层级跳跃: H{current_level} → H{level} (第{i+1}行)")
                current_level = level
        
        # 问题3: 表格过多
        if analysis["表格数量"] > 15:
            analysis["问题列表"].append(f"表格过多({analysis['表格数量']}个)")
            analysis["建议改进"].append("考虑将部分表格内容改为列表或合并")
        elif analysis["表格数量"] == 0 and analysis["总行数"] > 100:
            analysis["问题列表"].append("缺少表格，关键信息建议用表格呈现")
        
        # 问题4: 代码块过多
        if analysis["代码块数量"] > 12:
            analysis["问题列表"].append(f"代码块过多({analysis['代码块数量']}个)")
            analysis["建议改进"].append("精简示例代码，只保留核心部分")
        
        # 问题5: 文档过长
        if analysis["总行数"] > 400:
            analysis["问题列表"].append(f"文档较长({analysis['总行数']}行)")
            analysis["建议改进"].append("考虑拆分为多个文档")
        elif analysis["总行数"] < 50 and analysis["总字符数"] > 0:
            analysis["问题列表"].append("文档较短，建议补充内容")
        
        # 问题6: 缺少版本信息
        if not re.search(r'版本.*V\d+\.\d+', content):
            analysis["问题列表"].append("缺少版本信息")
        
        # 问题7: 缺少编制信息
        if not re.search(r'编制人.*陈伟', content):
            analysis["问题列表"].append("缺少编制人信息")
    
    def generate_table_of_contents(self, doc_path: Path) -> str:
        """为文档生成目录"""
        content = doc_path.read_text(encoding='utf-8')
        lines = content.split('\n')
        
        toc_lines = ["\n## 目录\n"]
        
        for line in lines:
            # H2标题
            match = re.match(r'^## (.+)$', line.strip())
            if match:
                title = match.group(1).strip()
                toc_lines.append(f"- [{title}](#{self._slugify(title)})")
            
            # H3标题（二级目录）
            match = re.match(r'^### (.+)$', line.strip())
            if match:
                title = match.group(1).strip()
                toc_lines.append(f"  - [{title}](#{self._slugify(title)})")
        
        return '\n'.join(toc_lines) + "\n"
    
    def _slugify(self, text: str) -> str:
        """生成URL友好的标识符"""
        # 移除特殊字符，保留中文、字母、数字和连字符
        slug = re.sub(r'[^\w\u4e00-\u9fff-]', '-', text.lower())
        slug = re.sub(r'-+', '-', slug).strip('-')
        return slug
    
    def optimize_document(self, doc_path: Path, dry_run: bool = True) -> dict:
        """优化单个文档"""
        original_content = doc_path.read_text(encoding='utf-8')
        lines = original_content.split('\n')
        
        optimized_lines = []
        toc_generated = False
        skip_next = 0
        
        for i, line in enumerate(lines):
            # 跳过已处理的内容
            if skip_next > 0:
                skip_next -= 1
                continue
            
            # 在文档头部插入目录（如果还没有）
            if not toc_generated and line.strip() == '' and i > 10 and i < 30:
                toc = self.generate_table_of_contents(doc_path)
                optimized_lines.append(toc)
                toc_generated = True
                continue
            
            # 修复标题层级：H1后应该是H2，不是H3
            if line.startswith('## ') and i + 1 < len(lines):
                next_line = lines[i + 1]
                # 如果下一行是H3，且这是第一个二级标题，保持原样
                # 否则提示可能需要调整
                if next_line.startswith('### ') and not toc_generated:
                    # 自动插入空行改善视觉分隔
                    optimized_lines.append(line)
                    optimized_lines.append('')
                    continue
            
            optimized_lines.append(line)
        
        optimized_content = '\n'.join(optimized_lines)
        
        return {
            "原始行数": len(lines),
            "优化后行数": len(optimized_content.split('\n')),
            "目录已生成": toc_generated,
            "变更内容": []  # 可以扩展为详细变更列表
        }
    
    def batch_optimize(self, output_dir: Path = None, dry_run: bool = True):
        """批量优化文档"""
        if output_dir is None:
            output_dir = self.docs_dir / "_optimized"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results = {
            "统计": {},
            "优化详情": []
        }
        
        print("=" * 80)
        print("【文档质量优化报告】")
        print("=" * 80)
        
        for doc_file in sorted(self.docs_dir.glob("*.md")):
            print(f"\n📄 处理: {doc_file.name}")
            
            # 分析
            analysis = self.analyze_document(doc_file)
            self.analysis_results[doc_file.name] = analysis
            
            # 显示分析结果
            print(f"   行数: {analysis['总行数']}, 表格: {analysis['表格数量']}, 代码块: {analysis['代码块数量']}")
            
            if analysis["问题列表"]:
                print(f"   ⚠️ 发现问题:")
                for issue in analysis["问题列表"]:
                    print(f"      - {issue}")
            
            if analysis["建议改进"]:
                print(f"   💡 改进建议:")
                for suggestion in analysis["建议改进"]:
                    print(f"      • {suggestion}")
            
            # 生成优化版本（如果需要）
            if not dry_run:
                optimization_result = self.optimize_document(doc_file, dry_run=False)
                output_file = output_dir / f"optimized_{doc_file.name}"
                output_file.write_text(
                    '\n'.join(self.optimize_document(doc_file, dry_run=False)["优化后内容"]),
                    encoding='utf-8'
                )
                print(f"   ✅ 已保存到: {output_file.name}")
        
        # 汇总统计
        total_docs = len(self.analysis_results)
        docs_with_issues = sum(1 for r in self.analysis_results.values() if r["问题列表"])
        total_tables = sum(r["表格数量"] for r in self.analysis_results.values())
        total_code_blocks = sum(r["代码块数量"] for r in self.analysis_results.values())
        
        print("\n" + "=" * 80)
        print("【优化统计汇总】")
        print("=" * 80)
        print(f"  总文档数: {total_docs}")
        print(f"  有问题文档: {docs_with_issues}")
        print(f"  总表格数: {total_tables}")
        print(f"  总代码块数: {total_code_blocks}")
        print("\n💡 提示: 运行 --no-dry-run 参数生成优化后的文档")
        
        return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='绝影Lite3项目文档质量优化工具')
    parser.add_argument('--no-dry-run', action='store_true', help='实际执行优化')
    parser.add_argument('--output', type=str, help='输出目录')
    args = parser.parse_args()
    
    docs_dir = Path("docs/01-技术方案")
    output_dir = Path(args.output) if args.output else None
    
    optimizer = DocumentOptimizer(docs_dir)
    optimizer.batch_optimize(output_dir=output_dir, dry_run=not args.no_dry_run)


if __name__ == "__main__":
    main()
