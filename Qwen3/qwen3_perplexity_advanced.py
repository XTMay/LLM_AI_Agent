"""
Qwen3 + Perplexity 高级集成
使用更智能的工具调用机制
"""

import os
import json
import re
from transformers import AutoModelForCausalLM, AutoTokenizer
from openai import OpenAI
import torch

class SmartAssistant:
    """智能助手：结合 Qwen3 推理 + Perplexity 搜索"""
    
    def __init__(self, perplexity_api_key=None):
        print("🚀 初始化智能助手系统...\n")
        
        # Qwen3
        self.tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-0.6B")
        self.model = AutoModelForCausalLM.from_pretrained(
            "Qwen/Qwen3-0.6B",
            torch_dtype="auto",
            device_map="auto"
        )
        
        # Perplexity
        api_key = perplexity_api_key or os.environ.get("PERPLEXITY_API_KEY")
        self.perplexity = OpenAI(
            api_key=api_key,
            base_url="https://api.perplexity.ai"
        ) if api_key else None
        
        # 工具定义
        self.tools_description = """
你有以下工具可以使用：

1. **web_search(query: str, recency: str)**
   - 功能：在互联网上搜索最新信息
   - 参数：
     * query: 搜索内容（清晰具体）
     * recency: 时间范围（day/week/month/year，默认 month）
   - 适用于：最新新闻、当前价格、实时数据、产品评测等

使用格式：
<tool_call>
{"name": "web_search", "arguments": {"query": "搜索内容", "recency": "month"}}
</tool_call>

当你需要最新、实时的信息时，使用 web_search 工具。
当用户问题可以用你的知识直接回答时，不需要使用工具。
"""
        
        print("✓ 系统初始化完成\n")
    
    def _generate(self, messages):
        """生成回复"""
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=True
        )
        
        model_inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)
        
        with torch.no_grad():
            generated_ids = self.model.generate(
                **model_inputs,
                max_new_tokens=3000,
                temperature=0.7,
                do_sample=True,
            )
        
        output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist()
        return self.tokenizer.decode(output_ids, skip_special_tokens=True).strip()
    
    def web_search(self, query, recency="month"):
        """Web 搜索工具"""
        if not self.perplexity:
            return "错误：Perplexity API 未配置"
        
        print(f"  🔍 搜索: {query}")
        
        try:
            response = self.perplexity.chat.completions.create(
                model="llama-3.1-sonar-small-128k-online",
                messages=[{"role": "user", "content": query}],
                temperature=0.2,
                max_tokens=1500,
                search_recency_filter=recency
            )
            
            result = response.choices[0].message.content
            print(f"  ✓ 搜索完成 ({len(result)} 字符)\n")
            return result
        except Exception as e:
            return f"搜索错误: {str(e)}"
    
    def execute_tool(self, tool_call_str):
        """执行工具调用"""
        try:
            # 提取工具调用信息
            match = re.search(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', 
                            tool_call_str, re.DOTALL)
            
            if not match:
                return None
            
            tool_call = json.loads(match.group(1))
            tool_name = tool_call.get("name")
            arguments = tool_call.get("arguments", {})
            
            print(f"🔧 执行工具: {tool_name}")
            print(f"   参数: {arguments}\n")
            
            if tool_name == "web_search":
                return self.web_search(
                    arguments.get("query"),
                    arguments.get("recency", "month")
                )
            
            return None
        except Exception as e:
            print(f"⚠️  工具执行错误: {e}")
            return None
    
    def chat(self, user_input, max_iterations=3):
        """
        智能对话，支持多轮工具调用
        
        Args:
            user_input: 用户输入
            max_iterations: 最大迭代次数
        """
        print("=" * 70)
        print(f"💬 用户: {user_input}")
        print("=" * 70 + "\n")
        
        messages = [
            {
                "role": "system", 
                "content": f"你是一个智能助手，可以使用工具获取最新信息。\n\n{self.tools_description}"
            },
            {
                "role": "user", 
                "content": user_input
            }
        ]
        
        for iteration in range(max_iterations):
            print(f"🔄 迭代 {iteration + 1}/{max_iterations}")
            print("-" * 70)
            
            # 生成响应
            response = self._generate(messages)
            
            # 检查是否有工具调用
            if "<tool_call>" in response:
                print("💭 助手思考: 需要使用工具\n")
                
                # 执行工具
                tool_result = self.execute_tool(response)
                
                if tool_result:
                    # 添加工具结果到对话
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user", 
                        "content": f"<tool_result>\n{tool_result}\n</tool_result>\n\n基于上述搜索结果，请回答我的问题。"
                    })
                    continue
            
            # 没有工具调用，返回最终答案
            print(f"🤖 最终回答:\n{response}\n")
            return response
        
        return "抱歉，经过多次尝试仍无法完成任务。"
    
    def multi_step_research(self, topic):
        """
        多步骤研究：自动进行多次搜索和分析
        
        Args:
            topic: 研究主题
        """
        print(f"📚 开始深度研究: {topic}\n")
        print("=" * 70 + "\n")
        
        # 步骤1: 概况搜索
        print("📍 步骤1: 搜索主题概况")
        overview = self.web_search(f"{topic} 综述 概况")
        
        # 步骤2: 最新动态
        print("📍 步骤2: 搜索最新动态")
        latest = self.web_search(f"{topic} 最新进展 2025", recency="month")
        
        # 步骤3: 深度分析
        print("📍 步骤3: 综合分析")
        
        analysis_prompt = f"""请基于以下信息，对「{topic}」进行深度分析：

【概况信息】
{overview}

【最新动态】
{latest}

请提供：
1. 核心概念和定义
2. 最新发展趋势
3. 关键数据和事实
4. 未来展望

分析要全面、客观、有深度。"""
        
        messages = [{"role": "user", "content": analysis_prompt}]
        analysis = self._generate(messages)
        
        print("=" * 70)
        print("📊 研究报告:")
        print("=" * 70)
        print(analysis)
        print("\n")
        
        return analysis
    
    def compare_topics(self, topic1, topic2):
        """
        对比分析两个主题
        
        Args:
            topic1: 主题1
            topic2: 主题2
        """
        print(f"⚖️  对比分析: {topic1} vs {topic2}\n")
        
        # 分别搜索
        info1 = self.web_search(f"{topic1} 详细介绍 特点")
        info2 = self.web_search(f"{topic2} 详细介绍 特点")
        
        # 对比分析
        compare_prompt = f"""请对比分析以下两个主题：

【{topic1}】
{info1}

【{topic2}】
{info2}

请从以下角度进行对比：
1. 核心特点
2. 优势和劣势
3. 应用场景
4. 发展趋势

以表格或清晰的结构呈现。"""
        
        messages = [{"role": "user", "content": compare_prompt}]
        comparison = self._generate(messages)
        
        print("📊 对比结果:")
        print("=" * 70)
        print(comparison)
        print("\n")
        
        return comparison


# ============ 使用示例 ============

if __name__ == "__main__":
    # 初始化（记得设置你的 API key）
    assistant = SmartAssistant(perplexity_api_key="pplx-xxxxxxxxxxxxx")
    
    # 示例1: 智能对话（自动判断是否需要搜索）
    print("\n" + "🌟" * 35)
    print("示例1: 智能对话 - 需要搜索")
    print("🌟" * 35 + "\n")
    assistant.chat("Qwen3 模型的最新版本有什么新特性？")
    
    # 示例2: 智能对话（不需要搜索）
    print("\n" + "🌟" * 35)
    print("示例2: 智能对话 - 不需要搜索")
    print("🌟" * 35 + "\n")
    assistant.chat("解释一下什么是 Transformer 架构")
    
    # 示例3: 多步骤研究
    print("\n" + "🌟" * 35)
    print("示例3: 深度研究")
    print("🌟" * 35 + "\n")
    assistant.multi_step_research("大语言模型的对齐技术")
    
    # 示例4: 对比分析
    print("\n" + "🌟" * 35)
    print("示例4: 对比分析")
    print("🌟" * 35 + "\n")
    assistant.compare_topics("ChatGPT", "Claude")