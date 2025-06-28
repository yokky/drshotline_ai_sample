import streamlit as st
import requests
import os
import time

# APIキーとエンドポイント設定（.env または環境変数から）
api_key = os.getenv("api_key")
endpoint = os.getenv("api_base")
deployment_name = os.getenv("deployment_name")

# PubMed検索用クエリをGPTで生成
def ask_gpt_for_pubmed_query(user_input):
    system_input = """
あなたはPubMedの検索クエリを作成する専門家です。
以下の日本語の医学的な質問に対して、PubMedで検索するための英語の検索クエリを作成してください。

【ルール】
1. 回答は検索キーワード（検索式）のみで返してください。説明は不要です。
2. クエリはPubMedの検索構文に従い、論理演算子（AND, OR）を使用してください。
3. 基本形式: (疾患名 OR 同義語) AND (目的) AND (対象) AND ("2020"[PDat] : "3000"[PDat])
"""
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    }
    url = f"{endpoint}/openai/deployments/{deployment_name}/chat/completions?api-version=2023-05-15"
    data = {
        "messages": [
            {"role": "system", "content": system_input},
            {"role": "user", "content": user_input}
        ],
        "max_tokens": 16384,
        "temperature": 0.5
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()['choices'][0]['message']['content'].strip()

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

# PubMedから論文情報とAbstract取得
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

# AbstractをGPTで日本語要約
def summarize_in_japanese(abstract_text):
    # system_input = "以下はPubMedから取得したAbstractです。日本語で2〜3行で簡潔に要約してください。"
    system_input = f"""
PubMedから取得したAbstractです。日本語で、情報量を落とさずに圧縮してください。
"""
    prompt = f"--- Abstract ---\n{abstract_text}"

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    }
    url = f"{endpoint}/openai/deployments/{deployment_name}/chat/completions?api-version=2023-05-15"
    data = {
        "messages": [
            {"role": "system", "content": system_input},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 16384,
        "temperature": 0.5
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        return response.json()['choices'][0]['message']['content'].strip()
    except:
        return "要約に失敗しました。"

# Streamlitアプリ本体
st.set_page_config(page_title="医療文献検索AI", layout="wide")
st.title("🧠 医療文献検索チャット (PubMed + GPT)")

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