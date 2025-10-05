"""
Qwen3 + Perplexity API 集成
让 Qwen3 能够调用 Perplexity 进行在线搜索
"""

import os
import json
from transformers import AutoModelForCausalLM, AutoTokenizer
from openai import OpenAI # Azure OpenAI
import torch

class Qwen3WithPerplexity:
    """集成了 Perplexity 搜索能力的 Qwen3 助手"""
    
    def __init__(self, 
                 qwen_model="Qwen/Qwen3-0.6B",
                 perplexity_api_key=None,
                 perplexity_model="llama-3.1-sonar-small-128k-online"):
        """
        初始化
        
        Args:
            qwen_model: Qwen3 模型名称
            perplexity_api_key: Perplexity API Key
            perplexity_model: Perplexity 模型名称
        """
        print("🚀 正在初始化系统...")
        
        # 加载 Qwen3 模型
        print("1/2 加载 Qwen3 模型...")
        self.tokenizer = AutoTokenizer.from_pretrained(qwen_model)
        self.model = AutoModelForCausalLM.from_pretrained(
            qwen_model,
            torch_dtype="auto",
            device_map="auto"
        )
        
        # 配置 Perplexity
        print("2/2 配置 Perplexity API...")
        self.perplexity_key = perplexity_api_key or os.environ.get("PERPLEXITY_API_KEY")
        
        if not self.perplexity_key:
            print("⚠️  警告: 未设置 PERPLEXITY_API_KEY，搜索功能将不可用")
            self.perplexity_client = None
        else:
            self.perplexity_client = OpenAI(
                api_key=self.perplexity_key,
                base_url="https://api.perplexity.ai"
            )
            self.perplexity_model = perplexity_model
            print("✓ Perplexity API 已配置")
        
        # 定义工具
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "perplexity_search",
                    "description": "在互联网上搜索最新信息。适用于：当前新闻、实时数据、最新事件、产品价格、天气等需要联网的信息。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜索查询，应该清晰具体"
                            },
                            "recency": {
                                "type": "string",
                                "enum": ["day", "week", "month", "year"],
                                "description": "时间范围，默认为 month"
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        ]
        
        print("✓ 初始化完成！\n")
    
    def perplexity_search(self, query, recency="month"):
        """
        调用 Perplexity API 搜索
        
        Args:
            query: 搜索查询
            recency: 时间范围
        
        Returns:
            搜索结果
        """
        if not self.perplexity_client:
            return "错误：Perplexity API 未配置"
        
        try:
            print(f"🔍 正在搜索: {query}")
            response = self.perplexity_client.chat.completions.create(
                model=self.perplexity_model,
                messages=[
                    {"role": "user", "content": query}
                ],
                temperature=0.2,
                max_tokens=1024,
                search_recency_filter=recency
            )
            
            result = response.choices[0].message.content
            print(f"✓ 搜索完成，获得 {len(result)} 字符的结果\n")
            return result
            
        except Exception as e:
            return f"搜索错误: {str(e)}"
    
    def _qwen3_generate(self, messages, enable_thinking=True):
        """Qwen3 生成响应"""
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=enable_thinking
        )
        
        model_inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)
        
        with torch.no_grad():
            generated_ids = self.model.generate(
                **model_inputs,
                max_new_tokens=2048,
                temperature=0.7,
                do_sample=True,
                top_p=0.9,
                top_k=20,
            )
        
        output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist()
        return self.tokenizer.decode(output_ids, skip_special_tokens=True).strip()
    
    def chat(self, user_input, enable_search=True):
        """
        智能对话，自动判断是否需要搜索
        
        Args:
            user_input: 用户输入
            enable_search: 是否启用搜索功能
        
        Returns:
            回复内容
        """
        print(f"💬 用户: {user_input}\n")
        
        if not enable_search or not self.perplexity_client:
            # 直接使用 Qwen3 回答
            messages = [{"role": "user", "content": user_input}]
            response = self._qwen3_generate(messages, enable_thinking=True)
            print(f"🤖 Qwen3: {response}\n")
            return response
        
        # 第一步：让 Qwen3 判断是否需要搜索
        decision_prompt = f"""你是一个智能助手。请判断以下问题是否需要联网搜索最新信息。

问题：{user_input}

如果需要搜索（例如：最新新闻、当前价格、实时数据等），请回复：
SEARCH: <搜索查询>

如果不需要搜索（例如：常识问题、解释概念、编程帮助等），请回复：
NO_SEARCH

只回复上述格式之一，不要添加其他内容。"""
        
        decision_messages = [{"role": "user", "content": decision_prompt}]
        decision = self._qwen3_generate(decision_messages, enable_thinking=False)
        
        print(f"🧠 决策: {decision}\n")
        
        # 第二步：根据决策执行
        if decision.strip().startswith("SEARCH:"):
            # 提取搜索查询
            search_query = decision.replace("SEARCH:", "").strip()
            
            # 调用 Perplexity 搜索
            search_result = self.perplexity_search(search_query)
            
            # 让 Qwen3 整合搜索结果回答
            final_prompt = f"""基于以下搜索结果回答用户的问题。

用户问题：{user_input}

搜索结果：
{search_result}

请用清晰、准确的语言回答用户的问题。如果搜索结果中有具体数据或引用，请在回答中体现。"""
            
            final_messages = [{"role": "user", "content": final_prompt}]
            response = self._qwen3_generate(final_messages, enable_thinking=True)
            
            print(f"🤖 最终回答: {response}\n")
            return response
        else:
            # 不需要搜索，直接回答
            messages = [{"role": "user", "content": user_input}]
            response = self._qwen3_generate(messages, enable_thinking=True)
            print(f"🤖 Qwen3: {response}\n")
            return response
    
    def search_and_summarize(self, topic, recency="week"):
        """
        搜索并总结特定主题
        
        Args:
            topic: 主题
            recency: 时间范围
        """
        print(f"📚 正在搜索和总结: {topic}\n")
        
        # 搜索
        search_result = self.perplexity_search(f"{topic} 最新动态", recency)
        
        # 总结
        summary_prompt = f"""请对以下关于「{topic}」的信息进行总结：

{search_result}

总结要求：
1. 提取关键要点（3-5个）
2. 包含重要数据或事实
3. 语言简洁明了"""
        
        messages = [{"role": "user", "content": summary_prompt}]
        summary = self._qwen3_generate(messages, enable_thinking=False)
        
        print(f"📝 总结:\n{summary}\n")
        return summary


# ============ 使用示例 ============

if __name__ == "__main__":
    # 设置你的 API Key
    # 方法1: 直接传入
    api_key = "pplx-xxxxxxxxxxxxx"  # 替换为你的真实 API key
    
    # 方法2: 从环境变量读取（推荐）
    # api_key = None  # 会自动从 PERPLEXITY_API_KEY 读取
    
    # 创建助手
    assistant = Qwen3WithPerplexity(perplexity_api_key=api_key)
    
    print("=" * 70)
    print("示例1: 需要搜索的问题（最新信息）")
    print("=" * 70)
    assistant.chat("2025年最新的AI技术突破有哪些？")
    
    print("=" * 70)
    print("示例2: 不需要搜索的问题（常识）")
    print("=" * 70)
    assistant.chat("什么是机器学习？")
    
    print("=" * 70)
    print("示例3: 搜索并总结")
    print("=" * 70)
    assistant.search_and_summarize("Qwen3 模型", recency="month")
    
    print("=" * 70)
    print("示例4: 实时数据查询")
    print("=" * 70)
    assistant.chat("今天的比特币价格是多少？")
    
    print("=" * 70)
    print("示例5: 特定产品查询")
    print("=" * 70)
    assistant.chat("iPhone 16 Pro 的主要特性和价格")