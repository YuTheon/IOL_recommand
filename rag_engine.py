"""
RAG 引擎模块 - 基于 LlamaIndex + ChromaDB 的本地知识库问答服务
用于人工晶体（IOL）推荐的智能辅助决策
"""

import os
import logging
import chromadb
from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    StorageContext,
    Settings,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "docs")
DEFAULT_CHROMA_DIR = os.path.join(os.path.dirname(__file__), "data", "chroma_db")
DEFAULT_COLLECTION_NAME = "iol_knowledge"
DEFAULT_OLLAMA_MODEL = "qwen2.5"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_EMBED_MODEL = "BAAI/bge-small-zh-v1.5"


class KnowledgeBase:
    """本地 RAG 知识库，负责文档索引和智能问答"""

    def __init__(
        self,
        data_dir=DEFAULT_DATA_DIR,
        chroma_dir=DEFAULT_CHROMA_DIR,
        collection_name=DEFAULT_COLLECTION_NAME,
        ollama_model=DEFAULT_OLLAMA_MODEL,
        ollama_base_url=DEFAULT_OLLAMA_BASE_URL,
        embed_model_name=DEFAULT_EMBED_MODEL,
    ):
        self.data_dir = data_dir
        self.chroma_dir = chroma_dir
        self.collection_name = collection_name

        # 配置 LLM（本地 Ollama）
        self.llm = Ollama(
            model=ollama_model,
            base_url=ollama_base_url,
            request_timeout=120.0,
        )

        # 配置 Embedding 模型（HuggingFace 本地推理）
        self.embed_model = HuggingFaceEmbedding(model_name=embed_model_name)

        # 全局设置
        Settings.llm = self.llm
        Settings.embed_model = self.embed_model

        # 初始化 ChromaDB 客户端
        os.makedirs(self.chroma_dir, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=self.chroma_dir)

        # 尝试加载已有索引
        self._index = None
        self._load_existing_index()

    def _load_existing_index(self):
        """尝试从已有的 Chroma 集合中加载索引"""
        try:
            chroma_collection = self.chroma_client.get_collection(self.collection_name)
            if chroma_collection.count() > 0:
                vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
                self._index = VectorStoreIndex.from_vector_store(vector_store)
                logger.info(
                    "已加载现有知识库，文档数: %d", chroma_collection.count()
                )
        except Exception:
            logger.info("未找到现有知识库，需要先调用 ingest_documents() 建立索引")

    def ingest_documents(self, data_dir=None):
        """
        读取指定目录下的 PDF/TXT 文件，切分并存入 Chroma 向量库。

        Args:
            data_dir: 文档目录路径，默认使用 ./data/docs

        Returns:
            dict: 包含索引状态信息
        """
        target_dir = data_dir or self.data_dir

        if not os.path.exists(target_dir):
            raise FileNotFoundError(f"文档目录不存在: {target_dir}")

        # 读取文档
        reader = SimpleDirectoryReader(
            input_dir=target_dir,
            recursive=True,
            required_exts=[".pdf", ".txt", ".md", ".docx"],
        )
        documents = reader.load_data()

        if not documents:
            raise ValueError(f"目录 {target_dir} 中未找到支持的文档文件")

        logger.info("共读取 %d 个文档", len(documents))

        # 删除旧集合（如果存在），重新创建
        try:
            self.chroma_client.delete_collection(self.collection_name)
        except Exception:
            pass

        chroma_collection = self.chroma_client.create_collection(self.collection_name)

        # 文本切分
        splitter = SentenceSplitter(chunk_size=512, chunk_overlap=64)

        # 构建向量索引
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        self._index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            transformations=[splitter],
        )

        doc_count = chroma_collection.count()
        logger.info("知识库索引完成，共 %d 个文本块", doc_count)

        return {
            "success": True,
            "message": f"成功索引 {len(documents)} 个文档，生成 {doc_count} 个文本块",
            "doc_count": len(documents),
            "chunk_count": doc_count,
        }

    def query(self, question: str) -> dict:
        """
        知识库问答：始终通过 LLM 回答，若知识库索引可用则检索相关文档作为引用。

        Args:
            question: 用户的问题

        Returns:
            dict: {"answer": str, "references": list[dict]}
                  references 中每项: {"source": 文件名, "text": 相关片段}
        """
        references = []
        context_text = ""

        # 1. 如果索引存在，先检索相关文档片段
        if self._index is not None:
            try:
                retriever = self._index.as_retriever(similarity_top_k=5)
                nodes = retriever.retrieve(question)
                for node in nodes:
                    source = node.metadata.get("file_name", "未知来源")
                    text_snippet = node.get_content().strip()
                    if text_snippet:
                        references.append({
                            "source": source,
                            "text": text_snippet[:300],  # 截取前300字作为引用预览
                            "score": round(node.score, 3) if node.score else None,
                        })
                if references:
                    context_text = "\n\n".join(
                        f"【参考文献 {i+1} - {ref['source']}】\n{ref['text']}"
                        for i, ref in enumerate(references)
                    )
            except Exception as e:
                logger.warning("知识库检索失败，将仅使用 LLM 直接回答: %s", e)

        # 2. 构建 Prompt，让 LLM 回答（有无检索结果均可）
        if context_text:
            prompt = (
                f"你是一位专业的眼科人工晶体（IOL）顾问。请根据以下参考资料回答用户问题。\n"
                f"如果参考资料中包含相关信息，请在回答中引用；如果参考资料不足以回答，"
                f"请结合你的专业知识进行补充回答。\n\n"
                f"## 参考资料\n{context_text}\n\n"
                f"## 用户问题\n{question}\n\n"
                f"请用中文回答，格式清晰，重点突出。"
            )
        else:
            prompt = (
                f"你是一位专业的眼科人工晶体（IOL）顾问。请直接回答以下问题。\n\n"
                f"## 用户问题\n{question}\n\n"
                f"请用中文回答，格式清晰，重点突出。"
            )

        # 3. 调用 LLM 生成回答
        try:
            response = self.llm.complete(prompt)
            answer = str(response).strip()

            if not answer:
                answer = "抱歉，未能生成有效回答，请尝试换个问题。"

            return {"answer": answer, "references": references}

        except Exception as e:
            logger.error("LLM 回答生成失败: %s", e)
            return {
                "answer": f"查询过程中出现错误: {e}",
                "references": [],
            }

    def query_recommendation(self, patient_data, base_result):
        """
        结合患者生理参数和决策树初步结果，利用 RAG 生成晶体推荐及医学解释。

        Args:
            patient_data: dict，患者参数，例如：
                {
                    "axial_length": 24.5,
                    "se_value": -1.2,
                    "affected_eye": "left",
                    "flag": 0,  # 是否散光
                }
            base_result: str，决策树得出的初步推荐结果

        Returns:
            str: RAG 生成的推荐文本（包含晶体型号建议和医学解释）
        """
        if self._index is None:
            return self._fallback_response(patient_data, base_result)

        # 构建查询 Prompt
        prompt = self._build_query_prompt(patient_data, base_result)

        try:
            query_engine = self._index.as_query_engine(
                similarity_top_k=5,
                response_mode="compact",
            )
            response = query_engine.query(prompt)
            result_text = str(response).strip()

            if not result_text or result_text == "Empty Response":
                return self._fallback_response(patient_data, base_result)

            return result_text

        except Exception as e:
            logger.error("RAG 查询失败: %s", e)
            return self._fallback_response(patient_data, base_result)

    def _build_query_prompt(self, patient_data, base_result):
        """构建发送给 LLM 的查询 Prompt"""
        axial_length = patient_data.get("axial_length", "未知")
        se_value = patient_data.get("se_value", "未知")
        affected_eye = patient_data.get("affected_eye", "未知")
        has_astigmatism = "是" if patient_data.get("flag") == 1 else "否"

        prompt = f"""你是一位专业的眼科人工晶体（IOL）选型顾问。请根据以下患者数据和初步决策结果，
结合检索到的医学文献知识，给出详细的晶体推荐方案。

## 患者参数
- 患眼: {affected_eye}
- 眼轴长度 (AL): {axial_length} mm
- 等效球镜 (SE): {se_value} D
- 是否有散光: {has_astigmatism}

## 决策树初步结果
{base_result}

## 请输出以下内容
1. **推荐晶体类型**：基于患者参数和文献，推荐具体的IOL类型
2. **推荐晶体型号**：给出具体品牌和型号
3. **屈光度预留建议**：根据眼轴长度给出术后屈光度预留方案
4. **推荐计算公式**：推荐适合该眼轴长度的IOL度数计算公式
5. **医学依据**：引用相关文献或指南中的关键信息作为推荐依据

请用中文回答，格式清晰，重点突出。"""

        return prompt

    def _fallback_response(self, patient_data, base_result):
        """当 RAG 不可用时，使用规则引擎作为 fallback"""
        axial_length = patient_data.get("axial_length")
        se_value = patient_data.get("se_value")
        flag = patient_data.get("flag", 0)

        parts = [base_result]

        # 单焦/多焦建议
        if axial_length is not None:
            if "单" in base_result:
                parts.append(_get_single_focus_suggestion(axial_length, se_value))
            elif any(kw in base_result for kw in ["多焦", "EDOF", "三焦"]):
                if se_value is not None:
                    parts.append(_get_multi_focus_suggestion(se_value))

        # 散光
        if flag == 1:
            parts.append("建议植入散光矫正晶体")

        # 晶体型号
        combined = "\n".join(parts)
        models = _get_lens_model(combined)
        parts.append("推荐晶体型号：\n" + "\n".join(f"- {m}" for m in models))

        # 计算公式
        if axial_length is not None:
            formula = _get_formula_recommendation(axial_length)
            parts.append(f"推荐公式: {formula['formula']}")
            parts.append(
                "相关链接:\n"
                + "\n".join(f"- {n}: {u}" for n, u in formula["links"].items())
            )

        parts.append("\n（注意：当前为规则引擎结果，知识库尚未加载）")
        return "\n".join(parts)


# ---- Fallback 规则函数（从 app.py 原有逻辑提取） ----


def _get_single_focus_suggestion(axial_length, se_value=None):
    if axial_length <= 22.5:
        return "建议预留 0 ~ +0.5D"
    elif 22.5 < axial_length <= 24:
        return "建议预留 -0.5D"
    elif 24 < axial_length <= 26:
        if se_value is not None:
            if -3.0 <= se_value <= 0.5:
                return "建议预留 -0.5D ~ 0D"
            elif -6.0 <= se_value < -3.0:
                return "建议预留 -1.0D ~ -0.5D"
        return "需要SE值来确定具体建议"
    elif 26 < axial_length <= 27:
        return "建议预留 -1.0D"
    elif 27 < axial_length <= 28:
        return "建议预留 -2.5D ~ -2.0D"
    else:
        return "建议预留 -3.0D"


def _get_multi_focus_suggestion(se_value):
    if se_value >= 1.0:
        return "判定为远视眼，建议多焦点IOL附加度数小 或 植入EDOF IOL"
    elif se_value <= -3.0:
        return "判定为近视眼，建议多焦点IOL附加度数大"
    else:
        return "可自由选择多焦点IOL"


def _get_lens_model(result_text):
    if "多焦点 双焦IOL" in result_text:
        return ["爱尔康 SV25T0(+2.5D)", "爱尔康 SN6AD1(+3.0D)"]
    elif "多焦点 EDOF" in result_text:
        return ["强生眼力健 ZXR00 (新无极)"]
    elif "多焦点 三焦点IOL" in result_text:
        return ["爱尔康 TFNT00 (Pan-Optix)"]

    if any(keyword in result_text for keyword in ["单焦点", "预留"]):
        base_models = [
            "强生眼力健 ZMB00",
            "卡尔蔡司 AT LISA 839MP",
            "卡尔蔡司 AT LISA 809M",
        ]
        if "散光矫正" in result_text:
            base_models.append("卡尔蔡司 AT LISA TORIC 909M")
        return base_models

    return ["无匹配的晶体型号推荐"]


def _get_formula_recommendation(axial_length):
    if axial_length < 22:
        return {
            "formula": "Hoffer Q 或 Barrett Universal II",
            "links": {
                "Hoffer Q": "https://hofferqst.com/",
                "Barrett Universal II": "https://calc.apacrs.org/barrett_universal2105/",
            },
        }
    elif 22 <= axial_length <= 24.5:
        return {
            "formula": "SRK/T、Holladay 1 或 Barrett Universal II",
            "links": {
                "SRK/T": "http://eyecalc.org/srk-t/",
                "Holladay 1": "https://www.calculatorultra.com/zh/tool/holladay-1-formula-calculator.html",
                "Barrett Universal II": "https://calc.apacrs.org/barrett_universal2105/",
            },
        }
    else:
        return {
            "formula": "Holladay 2 或 Barrett Universal II",
            "links": {
                "Holladay 2": "https://www.hic-soap.com/calc",
                "Barrett Universal II": "https://calc.apacrs.org/barrett_universal2105/",
            },
        }
