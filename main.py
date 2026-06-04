import json
import io
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any
from openai import OpenAI

app = FastAPI(title="AI Data Cleansing Pro")

# OpenAIクライアントの初期化
client = OpenAI()

# テスト用の固定社内アカウント設定
VALID_USER = "admin"
VALID_PASS = "secret123"
SECURE_TOKEN = "secure-corporate-token-jwt-style-2026"

# チャンク処理用のデータ型定義
class ChunkPayload(BaseModel):
    records: List[Dict[str, Any]]
    rules: List[str]
    columns: List[str]

# ログインリクエスト用のデータ型定義
class LoginPayload(BaseModel):
    username: str
    password: str

# 🔒 バックエンドAPIガード
def verify_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="認証トークンが見つかりません。再ログインしてください。")
    token = authorization.split(" ")[1]
    if token != SECURE_TOKEN:
        raise HTTPException(status_code=401, detail="無効なトークンです。アクセスが拒否されました。")
    return token

# --- 🎨 100%日本語・シンプルログイン＆ダッシュボード内蔵Web画面 ---
@app.get("/", response_class=HTMLResponse)
async def get_ui():
    html_content = """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI Data Cleansing Pro (Enterprise)</title>
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    </head>
    <body class="bg-slate-50 text-slate-800 min-h-screen font-sans">
        
        <div id="auth_container" class="min-h-screen flex items-center justify-center px-4">
            <div class="max-w-md w-full bg-white p-8 rounded-2xl shadow-xl border border-slate-200 space-y-6">
                <div class="text-center">
                    <h2 class="text-2xl font-bold text-slate-900">🔒 社内システムログイン</h2>
                    <p class="text-xs text-slate-400 mt-1">AI Data Cleansing Pro (Enterprise Edition)</p>
                </div>
                <div id="login_error" class="hidden bg-rose-50 text-rose-600 text-xs p-3 rounded-lg font-medium border border-rose-200"></div>
                <div class="space-y-4">
                    <div>
                        <label class="block text-xs font-bold text-slate-500 mb-1">社内ユーザーID</label>
                        <input type="text" id="username" class="w-full text-sm p-3 border border-slate-300 rounded-xl focus:outline-blue-500" placeholder="IDを入力してください (テスト用: admin)">
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-slate-500 mb-1">パスワード</label>
                        <input type="password" id="password" class="w-full text-sm p-3 border border-slate-300 rounded-xl focus:outline-blue-500" placeholder="パスワードを入力してください (テスト用: secret123)">
                    </div>
                    <button id="login_btn" class="w-full bg-slate-900 hover:bg-slate-800 text-white font-bold py-3 rounded-xl shadow-md transition-all cursor-pointer">
                        ログイン
                    </button>
                </div>
                <p class="text-[10px] text-slate-400 text-center">※このシステムは社内限定です。アクセスログは企業セキュリティポリシーに基づき完全に監査されています。</p>
            </div>
        </div>

        <div id="main_app_container" class="max-w-7xl mx-auto px-4 py-8 hidden">
            <div class="mb-8 border-b border-slate-200 pb-4 flex justify-between items-center">
                <div>
                    <h1 class="text-3xl font-bold text-slate-900 flex items-center gap-2">🪄 AI Data Cleansing Professional</h1>
                    <p class="text-sm text-slate-500 mt-1">【エンタープライズ製品版】認証ガード・大容量データ分散チャンク技術搭載。Excel完全同期システム。</p>
                </div>
                <button id="logout_btn" class="text-xs bg-slate-200 hover:bg-slate-300 text-slate-700 font-bold py-2 px-4 rounded-xl transition-all cursor-pointer">
                    🚪 ログアウト
                </button>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
                <div class="lg:col-span-1 bg-white p-6 rounded-xl shadow-xs border border-slate-200 h-fit">
                    <h3 class="text-lg font-bold text-slate-800 mb-4 border-b pb-2">🎛️ クレンジング設定</h3>
                    <div class="space-y-3">
                        <label class="flex items-center gap-2 cursor-pointer text-sm">
                            <input type="checkbox" id="rule_company" checked class="w-4 h-4 text-blue-600 rounded">
                            <span>「㈱」「(株)」を「株式会社」に統一</span>
                        </label>
                        <label class="flex items-center gap-2 cursor-pointer text-sm">
                            <input type="checkbox" id="rule_address" checked class="w-4 h-4 text-blue-600 rounded">
                            <span>住所の英数字・ハイフンを半角統一</span>
                        </label>
                        <label class="flex items-center gap-2 cursor-pointer text-sm">
                            <input type="checkbox" id="rule_phone" class="w-4 h-4 text-blue-600 rounded">
                            <span>電話番号のハイフンを削除</span>
                        </label>
                        <label class="flex items-center gap-2 cursor-pointer text-sm">
                            <input type="checkbox" id="rule_fillna" class="w-4 h-4 text-blue-600 rounded">
                            <span>空欄セルを「不明」で埋める</span>
                        </label>
                    </div>
                    <div class="mt-4">
                        <label class="block text-xs font-bold text-slate-500 mb-1">追加のカスタム指示（自由記述）</label>
                        <textarea id="custom_rule" class="w-full text-xs p-2 border border-slate-300 rounded-md h-20 focus:outline-blue-500" placeholder="例：『メールアドレスを小文字化』"></textarea>
                    </div>
                    <div class="mt-4 border-t pt-3">
                        <label class="block text-xs font-bold text-slate-500 mb-1">💡 1回あたりの処理行数（スライス幅）</label>
                        <select id="chunk_size" class="w-full text-xs p-2 border border-slate-300 rounded-md focus:outline-blue-500">
                            <option value="5">5行ずつ（超精密・低エラー）</option>
                            <option value="10" selected>10行ずつ（実務最適バランス）</option>
                            <option value="20">20行ずつ（高速処理重視）</option>
                        </select>
                    </div>
                </div>

                <div class="lg:col-span-3 space-y-6">
                    <div class="bg-white p-6 rounded-xl shadow-xs border border-slate-200">
                        <h4 class="text-md font-bold text-slate-800 mb-3">📥 Step 1: 対象ファイルのインポート</h4>
                        <div id="drop_zone" class="border-2 border-slate-300 border-dashed rounded-xl p-8 text-center cursor-pointer hover:bg-blue-50 transition-all">
                            <p class="text-sm text-slate-600">CSVまたはExcelファイルをここにドロップ、またはクリックして選択</p>
                            <p class="text-xs text-slate-400 mt-1">（大容量データ対応 / 自動構造解析システム搭載）</p>
                            <input type="file" id="file_input" class="hidden" accept=".csv, .xlsx">
                        </div>
                        <div id="file_info" class="mt-3 text-xs text-blue-600 font-bold hidden"></div>
                    </div>

                    <div class="text-center hidden" id="action_area">
                        <button id="exec_btn" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-8 rounded-xl shadow-md transition-all cursor-pointer w-full">
                            🚀 クレンジングを一括実行する
                        </button>
                    </div>

                    <div id="loading_area" class="hidden space-y-3 p-6 bg-white rounded-xl border border-slate-200 shadow-xs">
                        <div class="flex justify-between text-sm font-bold text-slate-700">
                            <span id="progress_status">🔄 データを解析中...</span>
                            <span id="progress_percent">0%</span>
                        </div>
                        <div class="w-full bg-slate-100 rounded-full h-3 overflow-hidden">
                            <div id="progress_bar" class="bg-blue-600 h-3 rounded-full transition-all duration-300" style="width: 0%"></div>
                        </div>
                    </div>

                    <div id="summary_area" class="hidden grid grid-cols-1 md:grid-cols-3 gap-4 bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
                        <div class="p-4 bg-slate-50 border border-slate-100 rounded-xl">
                            <p class="text-xs font-bold text-slate-500 uppercase tracking-wider">総処理行数</p>
                            <p id="summary_total_rows" class="text-2xl font-bold text-slate-900 mt-1">0 行</p>
                        </div>
                        <div class="p-4 bg-amber-50/50 border border-amber-100 rounded-xl">
                            <p class="text-xs font-bold text-amber-700 uppercase tracking-wider">AIが修正した行数</p>
                            <div class="flex items-baseline gap-2 mt-1">
                                <p id="summary_changed_rows" class="text-2xl font-bold text-amber-900">0 行</p>
                                <span id="summary_changed_rows_delta" class="text-xs text-amber-600 font-medium"></span>
                            </div>
                        </div>
                        <div class="p-4 bg-blue-50/50 border border-blue-100 rounded-xl">
                            <p class="text-xs font-bold text-blue-700 uppercase tracking-wider">AIが修正した総セル数</p>
                            <div class="flex items-baseline gap-2 mt-1">
                                <p id="summary_changed_cells" class="text-2xl font-bold text-blue-900">0 箇所</p>
                                <span id="summary_changed_cells_delta" class="text-xs text-blue-600 font-medium"></span>
                            </div>
                        </div>
                    </div>

                    <div id="result_area" class="hidden space-y-4">
                        <div class="bg-white p-6 rounded-xl shadow-xs border border-slate-200">
                            <h4 class="text-md font-bold text-slate-800 mb-2">📝 Step 2: クレンジング済みデータの最終レビュー（手動修正可能）</h4>
                            <p class="text-xs text-blue-600 mb-4">💡 黄色いセルがAIによって修正された箇所です。セルをダブルクリックしてその場で手動修正も可能です。</p>
                            
                            <div class="overflow-x-auto border border-slate-200 rounded-lg max-h-96">
                                <table id="data_table" class="w-full text-left border-collapse text-sm">
                                </table>
                            </div>

                            <div class="mt-6 flex justify-end">
                                <button id="download_btn" class="bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-3 px-6 rounded-xl shadow-md transition-all cursor-pointer flex items-center gap-2">
                                    📥 CSVファイルとして出力
                                </button>
                            </div>
                        </div>
                    </div>

                </div>
            </div>
        </div>

        <script>
            const authContainer = document.getElementById('auth_container');
            const mainAppContainer = document.getElementById('main_app_container');
            const loginBtn = document.getElementById('login_btn');
            const logoutBtn = document.getElementById('logout_btn');
            const loginError = document.getElementById('login_error');

            const dropZone = document.getElementById('drop_zone');
            const fileInput = document.getElementById('file_input');
            const fileInfo = document.getElementById('file_info');
            const actionArea = document.getElementById('action_area');
            const execBtn = document.getElementById('exec_btn');
            const loadingArea = document.getElementById('loading_area');
            const resultArea = document.getElementById('result_area');
            const dataTable = document.getElementById('data_table');
            const downloadBtn = document.getElementById('download_btn');
            
            const progressStatus = document.getElementById('progress_status');
            const progressPercent = document.getElementById('progress_percent');
            const progressBar = document.getElementById('progress_bar');
            const summaryArea = document.getElementById('summary_area');

            let parsedData = null;

            // 🔒 ページ読み込み時のセッション確認
            window.addEventListener('DOMContentLoaded', () => {
                const token = sessionStorage.getItem('auth_token');
                if (token) { showApp(); }
            });

            // 🔒 ログイン実行
            loginBtn.addEventListener('click', async () => {
                const u = document.getElementById('username').value;
                const p = document.getElementById('password').value;
                loginError.classList.add('hidden');

                try {
                    const res = await fetch('/api/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ username: u, password: p })
                    });
                    if (!res.ok) throw new Error('ユーザーIDまたはパスワードが正しくありません');
                    
                    const data = await res.json();
                    sessionStorage.setItem('auth_token', data.token);
                    showApp();
                } catch (err) {
                    loginError.textContent = `❌ ${err.message}`;
                    loginError.classList.remove('hidden');
                }
            });

            // 🔒 ログアウト処理
            logoutBtn.addEventListener('click', () => {
                sessionStorage.removeItem('auth_token');
                location.reload();
            });

            function showApp() {
                authContainer.classList.add('hidden');
                mainAppContainer.classList.remove('hidden');
            }

            // 業務クレンジング機能
            dropZone.addEventListener('click', () => fileInput.click());
            dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('bg-blue-50', 'border-blue-400'); });
            dropZone.addEventListener('dragleave', () => { dropZone.classList.remove('bg-blue-50', 'border-blue-400'); });
            dropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropZone.classList.remove('bg-blue-50', 'border-blue-400');
                if (e.dataTransfer.files.length > 0) { uploadAndParseFile(e.dataTransfer.files[0]); }
            });
            fileInput.addEventListener('change', (e) => { if (e.target.files.length > 0) { uploadAndParseFile(e.target.files[0]); } });

            // 1. ファイル構造解析
            async function uploadAndParseFile(file) {
                fileInfo.textContent = '⏳ ファイルの構造を解析中...';
                fileInfo.classList.remove('hidden');
                actionArea.classList.add('hidden');
                resultArea.classList.add('hidden');
                summaryArea.classList.add('hidden');

                const formData = new FormData();
                formData.append('file', file);

                try {
                    const response = await fetch('/api/parse', { 
                        method: 'POST', 
                        headers: { 'Authorization': `Bearer ${sessionStorage.getItem('auth_token')}` },
                        body: formData 
                    });
                    if (!response.ok) throw new Error('ファイルの解析に失敗しました。認証エラーの可能性があります。');
                    
                    parsedData = await response.json();
                    fileInfo.textContent = '📄 解析完了: ' + file.name + ' (総行数: ' + parsedData.rows.length + ' 行)';
                    actionArea.classList.remove('hidden');
                } catch (err) {
                    fileInfo.textContent = '❌ エラー: ' + err.message;
                    parsedData = null;
                }
            }

            // 2. 🚀 分散チャンク処理 ＋ リアルタイム進捗バー ＋ ダッシュボード集計
            execBtn.addEventListener('click', async () => {
                if (!parsedData) return;
                actionArea.classList.add('hidden');
                loadingArea.classList.remove('hidden');
                resultArea.classList.add('hidden');
                summaryArea.classList.add('hidden');

                const rules = [];
                if (document.getElementById('rule_company').checked) rules.push('- 会社名や取引先名が含まれる列の「㈱」や「(株)」を「株式会社」に統一。');
                if (document.getElementById('rule_address').checked) rules.push('- 住所情報が含まれる列の英数字、郵便番号、ハイフン、長音記号をすべて半角に統一。');
                if (document.getElementById('rule_phone').checked) rules.push('- 電話番号が含まれる列の記号をすべて削除し、数字のみの形式に統一。');
                if (document.getElementById('rule_fillna').checked) rules.push('- 空欄、空文字のセルを一律で「不明」という文字列に置き換え。');
                const customVal = document.getElementById('custom_rule').value;
                if (customVal) rules.push('【最優先追加指示】: ' + customVal);

                const chunkSize = parseInt(document.getElementById('chunk_size').value);
                const totalRows = parsedData.rows.length;
                const cleanedRows = [];

                for (let start = 0; start < totalRows; start += chunkSize) {
                    const end = Math.min(start + chunkSize, totalRows);
                    const chunkRecords = parsedData.rows.slice(start, end);

                    const currentPercent = Math.round((start / totalRows) * 100);
                    progressStatus.textContent = '🔄 AIクレンジング進行中: ' + totalRows + '行中 ' + start + '行完了';
                    progressPercent.textContent = currentPercent + '%';
                    progressBar.style.width = currentPercent + '%';

                    try {
                        const res = await fetch('/api/clean-chunk', {
                            method: 'POST',
                            headers: { 
                                'Content-Type': 'application/json',
                                'Authorization': `Bearer ${sessionStorage.getItem('auth_token')}`
                            },
                            body: JSON.stringify({
                                records: chunkRecords,
                                rules: rules,
                                columns: parsedData.columns
                            })
                        });
                        if (!res.ok) throw new Error('データ処理に失敗しました。');
                        
                        const chunkResult = await res.json();
                        cleanedRows.push(...chunkResult.data);
                    } catch (err) {
                        alert('処理が中断されました: ' + err.message);
                        loadingArea.classList.add('hidden');
                        actionArea.classList.remove('hidden');
                        return;
                    }
                }

                progressBar.style.width = '100%';
                progressPercent.textContent = '100%';
                progressStatus.textContent = '✨ すべてのデータの精密クレンジングが完了しました！';

                // 📊 【ダッシュボード自動集計ロジック】オリジナルと結果の比較
                let changedRowsCount = 0;
                let changedCellsCount = 0;

                cleanedRows.forEach((row, rIdx) => {
                    const origRow = parsedData.rows[rIdx];
                    if (origRow) {
                        let isRowChanged = false;
                        parsedData.columns.forEach(col => {
                            if (origRow[col] !== row[col]) {
                                changedCellsCount++;
                                isRowChanged = true;
                            }
                        });
                        if (isRowChanged) { changedRowsCount++; }
                    }
                });

                // ダッシュボードのカード数値を書き換え
                document.getElementById('summary_total_rows').textContent = `${totalRows} 行`;
                document.getElementById('summary_changed_rows').textContent = `${changedRowsCount} 行`;
                document.getElementById('summary_changed_rows_delta').textContent = `(${changedRowsCount}件の変更)`;
                document.getElementById('summary_changed_cells').textContent = `${changedCellsCount} 箇所`;
                document.getElementById('summary_changed_cells_delta').textContent = `(${changedCellsCount}セルの最適化)`;

                setTimeout(() => {
                    renderTable(parsedData.columns, parsedData.rows, cleanedRows);
                    loadingArea.classList.add('hidden');
                    summaryArea.classList.remove('hidden'); // ダッシュボードを出現させる
                    resultArea.classList.remove('hidden');
                }, 500);
            });

            function renderTable(columns, original, cleaned) {
                dataTable.innerHTML = '';
                const thead = document.createElement('thead');
                thead.className = 'bg-slate-100 text-slate-700 font-bold sticky top-0 z-10';
                const headerRow = document.createElement('tr');
                columns.forEach(col => {
                    const th = document.createElement('th');
                    th.className = 'p-3 border-b border-slate-200';
                    th.textContent = col;
                    headerRow.appendChild(th);
                });
                thead.appendChild(headerRow);
                dataTable.appendChild(thead);

                const tbody = document.createElement('tbody');
                cleaned.forEach((row, rIdx) => {
                    const tr = document.createElement('tr');
                    tr.className = 'hover:bg-slate-50 border-b border-slate-100';
                    columns.forEach(col => {
                        const td = document.createElement('td');
                        td.className = 'p-3 text-slate-700 outline-none focus:bg-blue-50 focus:ring-1 focus:ring-blue-400';
                        td.contentEditable = 'true';
                        td.textContent = row[col] || '';
                        if (original[rIdx] && original[rIdx][col] !== row[col]) {
                            td.className += ' bg-amber-100 text-amber-900 font-medium';
                        }
                        tr.appendChild(td);
                    });
                    tbody.appendChild(tr);
                });
                dataTable.appendChild(tbody);
            }

            downloadBtn.addEventListener('click', () => {
                const rows = Array.from(dataTable.querySelectorAll('tr'));
                const csvContent = rows.map(tr => {
                    const cells = Array.from(tr.querySelectorAll('th, td'));
                    return cells.map(cell => {
                        let text = cell.textContent.replaceAll('"', '"' + '"');
                        return '"' + text + '"';
                    }).join(',');
                }).join(String.fromCharCode(10));

                const bom = new Uint8Array([0xEF, 0xBB, 0xBF]);
                const blob = new Blob([bom, csvContent], { type: 'text/csv;charset=utf-8;' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                const dateStr = new Date().toISOString().slice(0,10).replace(/-/g, '');
                a.href = url;
                a.download = '修正データ_' + dateStr + '.csv';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# --- 🔒 認証API ---
@app.post("/api/login")
async def login(payload: LoginPayload):
    if payload.username == VALID_USER and payload.password == VALID_PASS:
        return {"token": SECURE_TOKEN}
    raise HTTPException(status_code=400, detail="IDまたはパスワードが間違っています。")


# --- 🤖 バックエンド機能1: ファイルパース ---
@app.post("/api/parse")
async def parse_file(file: UploadFile = File(...), token: str = Depends(verify_token)):
    try:
        contents = await file.read()
        if file.filename.endswith('.xlsx'):
            df = pd.read_excel(io.BytesIO(contents))
        else:
            try:
                df = pd.read_csv(io.BytesIO(contents), encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(io.BytesIO(contents), encoding='cp932')
        
        if len(df.columns) == 1 and "," in str(df.columns[0]):
            raw_col = df.columns[0]
            new_columns = [c.strip().strip('"').strip("'") for c in raw_col.split(",")]
            fixed_rows = []
            for val in df[raw_col]:
                row_vals = [str(v).strip().strip('"').strip("'") for v in str(val).split(",")]
                if len(row_vals) < len(new_columns):
                    row_vals += [""] * (len(new_columns) - len(row_vals))
                elif len(row_vals) > len(new_columns):
                    row_vals = row_vals[:len(new_columns)]
                fixed_rows.append(row_vals)
            df = pd.DataFrame(fixed_rows, columns=new_columns)

        df.columns = [str(c) for c in df.columns]
        df_str = df.astype(str).replace('nan', '')
        
        return JSONResponse(content={
            "columns": list(df_str.columns),
            "rows": json.loads(df_str.to_json(orient="records", force_ascii=False))
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"ファイル解析失敗: {str(e)}")


# --- 🤖 バックエンド機能2: 分散クレンジングAPI ---
@app.post("/api/clean-chunk")
async def clean_chunk(payload: ChunkPayload, token: str = Depends(verify_token)):
    try:
        chunk_json_str = json.dumps(payload.records, ensure_ascii=False)
        rules_prompt_string = "\\n".join(payload.rules)
        
        properties_schema = {str(col): {"type": "string"} for col in payload.columns}
        required_schema = [str(col) for col in payload.columns]
        
        json_schema = {
            "name": "chunk_cleansing_schema",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": properties_schema,
                            "required": required_schema,
                            "additionalProperties": False
                        }
                    }
                },
                "required": ["data"],
                "additionalProperties": False
            }
        }

        prompt = """
        提供された名簿データ（一部切り出し）について、以下の【クレンジングルール】を適用して綺麗なデータに整形してください。

        【クレンジングルール】
        __RULES__
        - ルールに該当しない列名やデータは絶対に書き換えず、そのまま保持してください。行数や列の構造を変形させることは厳禁です。

        【対象データ】
        __DATA__
        """.replace("__RULES__", rules_prompt_string).replace("__DATA__", chunk_json_str)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a precise data engineering assistant. You must output valid JSON matching the required schema perfectly."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_schema", "json_schema": json_schema},
            temperature=0.0
        )

        result_json = json.loads(response.choices[0].message.content)
        return JSONResponse(content={"data": result_json.get("data", [])})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"チャンク処理失敗: {str(e)}")