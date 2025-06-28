import streamlit as st
import requests
import os
import time
import json
import boto3
from dotenv import load_dotenv
import time

# .env を読み込む
load_dotenv()

# 推論プロファイルの ARN（Claude 3 用）
# inference_profile_arn = os.getenv("BEDROCK_INFERENCE_PROFILE_ARN")

# Bedrock クライアント設定
bedrock = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "ap-northeast-1"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)
# session = boto3.Session(profile_name="Bedrock", region_name="ap-northeast-1")
# bedrock = session.client("bedrock-runtime")


def get_inference_profile_arn(selected_model):
    arn = ''
    if selected_model == 'Claude 3 Sonnet':
        arn = inference_profile_arn = os.getenv("BEDROCK_INFERENCE_PROFILE_ARN_3")
    if selected_model == 'Claude 3.7 Sonnet':
        arn = inference_profile_arn = os.getenv("BEDROCK_INFERENCE_PROFILE_ARN_37")
    if selected_model == 'Claude Sonnet 4':
        arn = inference_profile_arn = os.getenv("BEDROCK_INFERENCE_PROFILE_ARN_4")
    return arn

# Claude に問い合わせる共通関数
# def ask_claude_3(prompt, system_prompt, selected_model):
#     response = bedrock.invoke_model(
#         modelId=get_inference_profile_arn(selected_model),  # ← ここが推論プロファイル ARN
#         contentType="application/json",
#         accept="application/json",
#         body=json.dumps({
#             "messages": [
#                 {"role": "system", "content": system_prompt},
#                 {"role": "user", "content": prompt}
#             ],
#             "temperature": 0.5,
#             "max_tokens": 16384
#         })
#     )
#     result = json.loads(response['body'].read())
#     return result["content"][0]["text"].strip()

def ask_claude_3(prompt, system_prompt, selected_model):
    response = bedrock.invoke_model(
        modelId=get_inference_profile_arn(selected_model),
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",  # ✅ Claude用必須
            "messages": [
                {"role": "user", "content": f"{system_prompt}\n\n{prompt}"}
            ],
            "max_tokens": 1024,
            "temperature": 0.5
        })
    )
    result = json.loads(response['body'].read())
    return result["content"][0]["text"].strip()

# Claude 3.7/4 Sonnet を呼び出す関数
def ask_claude_4(prompt, system_prompt, selected_model):
    response = bedrock.invoke_model(
        modelId=get_inference_profile_arn(selected_model),  # ← ここが推論プロファイル ARN
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",  # Claude 3 では必須
            "system": system_prompt,  # ここに system プロンプト
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.5,
            "max_tokens": 16384  # Claude 3 の通常出力は 1,024 ～ 4,096 程度が適切
        })
    )
    result = json.loads(response['body'].read())
    # Claude 3 の出力構造は content: [{ "text": "..." }]
    return result["content"][0]["text"].strip()

# Claude 3.7 Sonnet を呼び出す関数
def ask_claude_37(prompt, system_prompt):
    response = bedrock.invoke_model(
        modelId=inference_profile_arn,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",  # Claude 3.x 必須
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5,
            "max_tokens": 16384  # 通常は 1024〜4096 程度が適切
        })
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"].strip()

# PubMed検索クエリ生成
def ask_gpt_for_pubmed_query(user_input):
    system_prompt = """
あなたはPubMedの検索クエリを作成する専門家です。
日本語の医学的な質問に対して、PubMedで検索するための英語の検索クエリを作成してください。
検索クエリが作成できない場合は、空文字を返してください。

【ルール】
1. 回答は検索キーワード（検索式）のみで返してください。説明は不要です。
2. クエリはPubMedの検索構文に従い、論理演算子（AND, OR）を使用してください。
3. 基本形式: (疾患名 OR 同義語) AND (目的) AND (対象) AND ("2020"[PDat] : "3000"[PDat])
"""
    if model == 'Claude 3 Sonnet':
        return ask_claude_3(user_input, system_prompt, model)
    else:
        return ask_claude_4(user_input, system_prompt, model)
        

# Abstractを日本語で要約
def summarize_in_japanese(abstract_text):
    system_prompt = "PubMedから取得したAbstractです。日本語で、情報量を落とさずに箇条書きで、要約してください。箇条書きは、読みやすくするためひとつずつ改行してください。"
    prompt = f"--- Abstract ---\n{abstract_text}"
    try:
        if model == 'Claude 3 Sonnet':
            return ask_claude_3(prompt, system_prompt, model)
        else:
            return ask_claude_4(prompt, system_prompt, model)
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

# PubMedの論文情報とAbstractを取得
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

# Streamlit UI
# st.set_page_config(page_title="医療文献検索AI", layout="wide")
# st.title("🧠 医療文献検索チャット (PubMed + Claude 3)")

# user_input = st.chat_input("調べたい医学的な質問を入力してください")

# if user_input:
#     with st.chat_message("user"):
#         st.markdown(user_input)

#     with st.chat_message("assistant"):
#         with st.spinner("🔍 PubMed検索クエリを生成中..."):
#             query = ask_gpt_for_pubmed_query(user_input)
#             st.markdown(f"**🔍 検索クエリ**: {query}")

#         with st.spinner("📚 論文を検索中..."):
#             pmids = search_pubmed(query)

#         if not pmids:
#             st.error("❌ 該当する論文が見つかりませんでした。")
#         else:
#             for pmid in pmids:
#                 time.sleep(1)  # API負荷軽減
#                 data = fetch_pubmed_metadata(pmid)

#                 st.markdown("----")
#                 st.subheader(f"📄 {data['title']}")
#                 st.markdown(f"👨‍⚕️ **著者:** {data['authors']}　｜　📅 **発表日:** {data['pubdate']}")
#                 st.markdown(f"🔗 [PubMedリンクはこちら]({data['url']})")

#                 if data['abstract']:
#                     with st.spinner("📝 要約生成中..."):
#                         summary = summarize_in_japanese(data['abstract'])
#                     st.success(f"📝 要約: {summary}")
#                 else:
#                     st.warning("⚠️ この論文にはAbstractが含まれていません。")


# ----------------------------------------------
# サイドバーのタイトルを表示
st.sidebar.title("Options")

# サイドバーにオプションボタンを設置
model = st.sidebar.radio("生成AIを選択(バージョンが上がるほど、高機能)", (
    "Claude 3 Sonnet", "Claude 3.7 Sonnet", "Claude Sonnet 4"
), index=2)

# サイドバーにボタンを設置
# clear_button = st.sidebar.button("Clear Conversation", key="clear")

# サイドバーにスライダーを追加し、temperatureを0から2までの範囲で選択可能にする
# 初期値は0.0、刻み幅は0.1とする
# temperature = st.sidebar.slider("Temperature:", min_value=0.0, max_value=2.0, value=0.0, step=0.1)

# Streamlitはmarkdownを書けばいい感じにHTMLで表示してくれます
# (もちろんメイン画面でも使えます)
# st.sidebar.markdown("## Costs")
# st.sidebar.markdown("**Total cost**")
# for i in range(3):
#     st.sidebar.markdown(f"- ${i+0.01}")  # 説明のためのダミー
# ----------------------------------------------

# セッション初期化（構造化されたメッセージ）
if "messages" not in st.session_state:
    st.session_state.messages = []

st.set_page_config(page_title="医療文献検索AI", layout="wide")
st.title("🧠 医療文献検索チャット (PubMed + Claude)")

# ✅ チャット履歴の再描画（構造ごとに表示）
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            for block in msg["content"]:
                if block["type"] == "query":
                    st.markdown(f"**🔍 検索クエリ**: `{block['query']}`")
                elif block["type"] == "paper":
                    st.markdown("----")
                    st.subheader(f"📄 {block['title']}")
                    st.markdown(f"👨‍⚕️ **著者:** {block['authors']}　｜　📅 **発表日:** {block['pubdate']}")
                    st.markdown(f"🔗 [PubMedリンクはこちら]({block['url']})")
                    if block["summary"]:
                        st.success(f"📝 要約: {block['summary']}")
                    else:
                        st.warning("⚠️ この論文にはAbstractが含まれていません。")
                elif block["type"] == "error":
                    st.error(block["message"])

# ユーザー入力欄
user_input = st.chat_input("調べたい医学的な質問を入力してください")

if user_input:
    # ユーザー入力を保存・表示
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # アシスタント応答処理
    with st.chat_message("assistant"):
        response_blocks = []

        # with st.spinner("🔍 PubMed検索クエリを生成中..."):
        #     query = ask_gpt_for_pubmed_query(user_input)
        #     st.markdown(f"**🔍 検索クエリ**: `{query}`")
        #     response_blocks.append({"type": "query", "query": query})


        # with st.spinner("🔍 PubMed検索クエリを生成中..."):
        #     query = ask_gpt_for_pubmed_query(user_input).strip()

        #     if query == "":
        #         warning_msg = "⚠️ 適切な医学的な質問を入力してください。"
        #         st.warning(warning_msg)

        #         # 表示＋履歴に追加（構造化）
        #         response_blocks.append({"type": "error", "message": warning_msg})
        #         st.session_state.messages.append({
        #             "role": "assistant",
        #             "content": response_blocks
        #         })
        #         # この後の処理はスキップ
        #         st.stop()

        with st.spinner("🔍 PubMed検索クエリを生成中..."):
            try:
                query = ask_gpt_for_pubmed_query(user_input).strip()
            except Exception as e:
                error_msg = f"❌ クエリ生成中にエラーが発生しました: {str(e)}"
                st.error(error_msg)
                response_blocks.append({"type": "error", "message": error_msg})
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_blocks
                })
                st.stop()

            print(f"[DEBUG] raw query: '{query}'") 

            if not query or query == '""':
                warning_msg = "⚠️ 適切な医学的な質問を入力してください。"
                st.warning(warning_msg)
                response_blocks.append({"type": "error", "message": warning_msg})
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_blocks
                })
                st.stop()

        st.markdown(f"**🔍 検索クエリ**: `{query}`")
        response_blocks.append({"type": "query", "query": query})           
            
        with st.spinner("📚 論文を検索中..."):
            pmids = search_pubmed(query)

        if not pmids:
            error_msg = "❌ 該当する論文が見つかりませんでした。"
            st.error(error_msg)
            response_blocks.append({"type": "error", "message": error_msg})
        else:
            for pmid in pmids:
                time.sleep(1)
                data = fetch_pubmed_metadata(pmid)

                st.markdown("----")
                st.subheader(f"📄 {data['title']}")
                st.markdown(f"👨‍⚕️ **著者:** {data['authors']}　｜　📅 **発表日:** {data['pubdate']}")
                st.markdown(f"🔗 [PubMedリンクはこちら]({data['url']})")

                summary_text = ""
                if data['abstract']:
                    with st.spinner("📝 要約生成中..."):
                        summary_text = summarize_in_japanese(data['abstract'])
                    st.success(f"📝 要約: {summary_text}")
                else:
                    st.warning("⚠️ この論文にはAbstractが含まれていません。")

                response_blocks.append({
                    "type": "paper",
                    "title": data["title"],
                    "authors": data["authors"],
                    "pubdate": data["pubdate"],
                    "url": data["url"],
                    "summary": summary_text
                })

        # アシスタント応答を構造化して保存
        st.session_state.messages.append({"role": "assistant", "content": response_blocks})