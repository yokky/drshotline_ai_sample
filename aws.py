import streamlit as st
import requests
import os
import time
import json
import boto3
from dotenv import load_dotenv

# .env を読み込む
load_dotenv()

# Bedrock クライアント設定
bedrock = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "ap-northeast-1")
)

# Claude 3 Sonnet モデル ID（2024年6月時点）
# model_id = "anthropic.claude-sonnet-4-20250514-v1:0"
# model_id = "anthropic.claude-3-7-sonnet-20250219-v1:0"
model_id = "anthropic.claude-3-sonnet-20240229-v1:0"

# Claude に問い合わせる関数
def ask_claude(prompt, system_prompt):
    response = bedrock.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5,
            "max_tokens": 1024
        })
    )
    result = json.loads(response['body'].read())
    return result["content"][0]["text"].strip()

# PubMed検索用クエリ生成
def ask_gpt_for_pubmed_query(user_input):
    system_prompt = """
あなたはPubMedの検索クエリを作成する専門家です。
以下の日本語の医学的な質問に対して、PubMedで検索するための英語の検索クエリを作成してください。

【ルール】
1. 回答は検索キーワード（検索式）のみで返してください。説明は不要です。
2. クエリはPubMedの検索構文に従い、論理演算子（AND, OR）を使用してください。
3. 基本形式: (疾患名 OR 同義語) AND (目的) AND (対象) AND ("2020"[PDat] : "3000"[PDat])
"""
    return ask_claude(user_input, system_prompt)

# Abstractを日本語で要約
def summarize_in_japanese(abstract_text):
    system_prompt = "PubMedから取得したAbstractです。日本語で、情報量を落とさずに要約してください。"
    prompt = f"--- Abstract ---\n{abstract_text}"
    try:
        return ask_claude(prompt, system_prompt)
    except:
        return "要約に失敗しました。"

# PubMed検索
def search_pubmed(query, max_results=3):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results
    }
    res = requests.get(url, params=params).json()
    return res.get('esearchresult', {}).get('idlist', [])

# 論文情報とAbstract取得
def fetch_pubmed_metadata(pmid):
    summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    abstract_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    summary = requests.get(summary_url, params={"db": "pubmed", "id": pmid, "retmode": "json"}).json()
    doc = summary["result"][pmid]

    abstract_res = requests.get(abstract_url, params={"db": "pubmed", "id": pmid, "retmode": "text", "rettype": "abstract"})
    abstract_text = abstract_res.text.strip()

    return {
        "title": doc.get("title", ""),
        "authors": ", ".join([a["name"] for a in doc.get("authors", [])[:3]]),
        "pubdate": doc.get("pubdate", ""),
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "abstract": abstract_text
    }

# Streamlit アプリ
st.set_page_config(page_title="医療文献検索AI", layout="wide")
st.title("🧠 医療文献検索チャット (PubMed + Claude3)")

user_input = st.chat_input("調べたい医学的な質問を入力してください")

if user_input:
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("🔍 PubMed検索クエリを生成中..."):
            query = ask_gpt_for_pubmed_query(user_input)
            st.markdown(f"**🔍 検索クエリ**: {query}")

        with st.spinner("📚 論文を検索中..."):
            pmids = search_pubmed(query)

        if not pmids:
            st.error("❌ 該当する論文が見つかりませんでした。")
        else:
            for pmid in pmids:
                time.sleep(1)  # API負荷対策
                data = fetch_pubmed_metadata(pmid)

                st.markdown("----")
                st.subheader(f"📄 {data['title']}")
                st.markdown(f"👨‍⚕️ **著者:** {data['authors']}　｜　📅 **発表日:** {data['pubdate']}")
                st.markdown(f"🔗 [PubMedリンクはこちら]({data['url']})")

                if data['abstract']:
                    with st.spinner("📝 要約生成中..."):
                        summary = summarize_in_japanese(data['abstract'])
                    st.success(f"📝 要約: {summary}")
                else:
                    st.warning("⚠️ この論文にはAbstractが含まれていません。")
